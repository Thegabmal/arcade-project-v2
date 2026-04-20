import os
import time
import json
import threading
import functools
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"
MODEL_NAME_PRO = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
MAX_RETRIES = 2  # RPD=20/clé — 5 retries × 9 clés = 45 appels brûlés pour UN seul appel raté

# ── Clé payante (créateur) ────────────────────────────────────────────────────
# GEMINI_PAID_KEY : clé payante dédiée à l'agent créateur (génération 9 couches).
# Si absente, utilise GEMINI_API_KEY comme clé payante (comportement avant).
# RPD illimité sur la clé payante — pas de comptage journalier.
_PAID_KEY_RAW = os.getenv("GEMINI_PAID_KEY") or os.getenv("GEMINI_API_KEY")
if not _PAID_KEY_RAW:
    raise RuntimeError("Aucune clé payante trouvée (GEMINI_PAID_KEY ou GEMINI_API_KEY requis dans .env)")

import httpx as _httpx
_http_timeout = _httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)

_paid_client = genai.Client(
    api_key=_PAID_KEY_RAW,
    http_options=types.HttpOptions(httpxClient=_httpx.Client(timeout=_http_timeout))
)
_paid_key_lock = threading.Lock()
_paid_timestamps: list = []  # RPM tracking pour la clé payante
MAX_CALLS_PER_MINUTE_PAID = int(os.getenv("GEMINI_RPM_LIMIT_PAID", "200"))

# ── Rotation de clés gratuites ────────────────────────────────────────────────
# GEMINI_API_KEY (si pas de GEMINI_PAID_KEY) + GEMINI_API_KEY_1..N = clés gratuites
# Quand une clé fait 429, on passe à la suivante automatiquement.
# Quand TOUTES les clés gratuites sont épuisées → fallback automatique sur clé payante.
def _load_api_keys() -> list[str]:
    keys = []
    # Si GEMINI_PAID_KEY est défini, GEMINI_API_KEY est une clé gratuite aussi
    # Si GEMINI_PAID_KEY absent, GEMINI_API_KEY est payante — on ne la met PAS dans les clés gratuites
    if os.getenv("GEMINI_PAID_KEY"):
        k = os.getenv("GEMINI_API_KEY")
        if k:
            keys.append(k)
    # Clés gratuites numérotées (1 à 20)
    for i in range(1, 20):
        k = os.getenv(f"GEMINI_API_KEY_{i}")
        if k:
            keys.append(k)
    # Si aucune clé gratuite trouvée → on utilisera la clé payante comme fallback universel
    return keys

_api_keys = _load_api_keys()
_clients = [
    genai.Client(
        api_key=k,
        http_options=types.HttpOptions(httpxClient=_httpx.Client(timeout=_http_timeout))
    )
    for k in _api_keys
]
_current_key_idx = 0
_key_lock = threading.Lock()

# Timestamps par clé pour respecter le RPM par clé
_key_timestamps: dict[int, list] = {i: [] for i in range(len(_api_keys))}

# Compteur RPD par clé — persisté dans un fichier JSON, reset à minuit UTC
import datetime as _dt
_RPD_FILE = os.path.join(os.path.dirname(__file__), ".quota_rpd.json")

def _load_daily_counts() -> tuple[dict, str]:
    """Charge les compteurs RPD depuis le fichier. Retourne (counts, date)."""
    today = _dt.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        if os.path.exists(_RPD_FILE):
            with open(_RPD_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == today:
                counts = {int(k): v for k, v in data.get("counts", {}).items()}
                # Compléter si nouvelles clés ajoutées
                for i in range(len(_api_keys)):
                    counts.setdefault(i, 0)
                return counts, today
    except Exception:
        pass
    return {i: 0 for i in range(len(_api_keys))}, today

def _save_daily_counts():
    """Persiste les compteurs RPD dans le fichier."""
    try:
        with open(_RPD_FILE, "w") as f:
            json.dump({"date": _key_daily_reset_date, "counts": _key_daily_counts}, f)
    except Exception:
        pass

_key_daily_counts, _key_daily_reset_date = _load_daily_counts()

def _reset_daily_counts_if_needed():
    """Remet à zéro les compteurs RPD si on a changé de jour UTC."""
    global _key_daily_counts, _key_daily_reset_date
    today = _dt.datetime.utcnow().strftime("%Y-%m-%d")
    if _key_daily_reset_date != today:
        _key_daily_reset_date = today
        _key_daily_counts = {i: 0 for i in range(len(_api_keys))}
        _save_daily_counts()
        print(f"  [RPD] Compteurs journaliers remis à zéro ({today} UTC)", flush=True)

def get_quota_status() -> dict:
    """
    Retourne l'état du quota pour chaque clé.
    Utilisable sans faire d'appel API.
    """
    _reset_daily_counts_if_needed()
    status = {}
    for i, key in enumerate(_api_keys):
        used = _key_daily_counts.get(i, 0)
        status[f"cle_{i+1}"] = {
            "utilisés": used,
            "restants": max(0, MAX_CALLS_PER_DAY - used),
            "épuisée": used >= MAX_CALLS_PER_DAY,
            "key_hint": key[:8] + "..." + key[-4:],
        }
    total_used = sum(_key_daily_counts.get(i, 0) for i in range(len(_api_keys)))
    total_max = MAX_CALLS_PER_DAY * len(_api_keys)
    status["_total"] = {
        "utilisés": total_used,
        "restants": max(0, total_max - total_used),
        "générations_estimées": max(0, total_max - total_used) // 30,
    }
    return status

# Compat : client global (utilisé par quelques imports directs)
client = _paid_client if not _clients else _clients[0]

MAX_CALLS_PER_MINUTE = int(os.getenv("GEMINI_RPM_LIMIT", "4"))        # Free: 5 RPM/clé (source: ai.google.dev/pricing)
MAX_CALLS_PER_DAY = int(os.getenv("GEMINI_RPD_LIMIT", "19"))          # Free: 20 RPD/clé — payant: GEMINI_RPD_LIMIT=9999
WINDOW_SECONDS = 60        # Fenêtre RPM = 1 minute

# Pause globale partagée entre tous les threads — quand une clé déclenche la pause,
# TOUS les threads en cours la respectent. Évite les cascades de 429 multi-thread.
_api_pause_until: float = 0.0

def _get_current_client() -> tuple[int, object]:
    """Retourne (idx, client) de la clé courante."""
    with _key_lock:
        return _current_key_idx, _clients[_current_key_idx]

def _rotate_key(failed_idx: int) -> tuple[int, object]:
    """
    Passe à la clé suivante si failed_idx est encore la clé courante.
    Retourne (new_idx, new_client).
    """
    global _current_key_idx
    with _key_lock:
        if _current_key_idx == failed_idx:
            _current_key_idx = (failed_idx + 1) % len(_api_keys)
            # Log serveur uniquement — ne pas polluer le flux SSE
            print(
                f"  [Rotation clé] Clé {failed_idx+1}/{len(_api_keys)} épuisée "
                f"→ passage à la clé {_current_key_idx+1}",
                flush=True,
            )
        return _current_key_idx, _clients[_current_key_idx]

def _get_available_client() -> tuple[int, object]:
    """
    Retourne (idx, client) de la première clé GRATUITE ayant de la capacité disponible.
    Respecte RPM (4/min) ET RPD (19/jour) par clé.
    Si toutes les clés gratuites sont épuisées en RPD → raise _AllFreeKeysExhausted
      (l'appelant (call_gemini) bascule alors sur la clé payante).
    Si toutes les clés gratuites sont saturées en RPM → attend la fenêtre la plus proche.
    Si aucune clé gratuite disponible → raise _AllFreeKeysExhausted immédiatement.
    """
    global _current_key_idx, _key_timestamps
    n = len(_api_keys)
    if n == 0:
        raise _AllFreeKeysExhausted("Aucune clé gratuite configurée")

    with _key_lock:
        _reset_daily_counts_if_needed()
        now = time.time()

        # Nettoyer les timestamps RPM de toutes les clés
        for i in range(n):
            _key_timestamps[i] = [t for t in _key_timestamps.get(i, []) if now - t < WINDOW_SECONDS]

        # Chercher une clé gratuite disponible (RPM ET RPD)
        for offset in range(n):
            idx = (_current_key_idx + offset) % n
            rpd_ok = _key_daily_counts.get(idx, 0) < MAX_CALLS_PER_DAY
            rpm_ok = len(_key_timestamps[idx]) < MAX_CALLS_PER_MINUTE
            if rpd_ok and rpm_ok:
                _current_key_idx = idx
                _key_timestamps[idx].append(time.time())
                _key_daily_counts[idx] = _key_daily_counts.get(idx, 0) + 1
                _save_daily_counts()
                return idx, _clients[idx]

        # Vérifier si toutes les clés gratuites sont épuisées en RPD
        all_rpd_exhausted = all(
            _key_daily_counts.get(i, 0) >= MAX_CALLS_PER_DAY for i in range(n)
        )
        if all_rpd_exhausted:
            used = sum(_key_daily_counts.get(i, 0) for i in range(n))
            raise _AllFreeKeysExhausted(
                f"Quota journalier épuisé sur toutes les clés gratuites "
                f"({used}/{n * MAX_CALLS_PER_DAY} appels) — fallback clé payante"
            )

        # Toutes les clés gratuites en RPD sont saturées en RPM — attendre
        rpd_ok_keys = [i for i in range(n) if _key_daily_counts.get(i, 0) < MAX_CALLS_PER_DAY]
        best_idx = min(rpd_ok_keys, key=lambda i: _key_timestamps[i][0] if _key_timestamps[i] else 0)
        oldest = _key_timestamps[best_idx][0] if _key_timestamps[best_idx] else now
        wait = WINDOW_SECONDS - (now - oldest) + 0.5

    # Attente hors du lock pour ne pas bloquer les autres threads
    print(f"  [Rate limit] Clés gratuites saturées — attente {wait:.1f}s", flush=True)
    time.sleep(max(wait, 1.0))
    return _get_available_client()


class _AllFreeKeysExhausted(Exception):
    """Toutes les clés gratuites sont épuisées — l'appelant doit basculer sur la clé payante."""
    pass


def _get_paid_client_rate_limited():
    """
    Retourne le client payant en respectant son RPM.
    Attends si la fenêtre RPM est pleine.
    """
    global _paid_timestamps
    while True:
        with _paid_key_lock:
            now = time.time()
            _paid_timestamps = [t for t in _paid_timestamps if now - t < WINDOW_SECONDS]
            if len(_paid_timestamps) < MAX_CALLS_PER_MINUTE_PAID:
                _paid_timestamps.append(time.time())
                return _paid_client
            oldest = _paid_timestamps[0]
            wait = WINDOW_SECONDS - (now - oldest) + 0.5
        print(f"  [Paid RPM] Clé payante saturée — attente {wait:.1f}s", flush=True)
        time.sleep(max(wait, 1.0))


def _rate_limit_for_key(key_idx: int):
    """Compatibilité — délègue à _get_available_client (ignoré, key_idx non contraignant)."""
    # Ne plus utilisé directement — call_gemini utilise _get_available_client
    pass

_claude_rate_lock = threading.Lock()
_claude_last_call_time: float = 0.0
CLAUDE_API_DELAY = 1.0  # Claude Pro/API a des limites plus souples



def _claude_rate_limit():
    """Rate limiter indépendant pour les appels Claude (ne bloque pas Gemini)."""
    global _claude_last_call_time
    with _claude_rate_lock:
        now = time.time()
        elapsed = now - _claude_last_call_time
        if _claude_last_call_time > 0 and elapsed < CLAUDE_API_DELAY:
            time.sleep(CLAUDE_API_DELAY - elapsed)
        _claude_last_call_time = time.time()


def _make_generation_config(temperature, max_tokens, system_instruction, json_mode, disable_thinking):
    """Construit le GenerateContentConfig commun à call_gemini et call_gemini_paid."""
    config_params = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if system_instruction:
        config_params["system_instruction"] = system_instruction
    if json_mode:
        config_params["response_mime_type"] = "application/json"
    if disable_thinking:
        config_params["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**config_params)


def _extract_text_from_response(response) -> str:
    """Extrait le texte d'une réponse Gemini (gère thinking tokens)."""
    try:
        text = response.text
    except Exception:
        text = None
    if not text:
        text = ""
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts if candidate.content else []):
                if hasattr(part, "text") and part.text:
                    text += part.text
    # A6 : Détecter finish_reason == MAX_TOKENS
    try:
        for candidate in (response.candidates or []):
            _finish = str(getattr(candidate, 'finish_reason', '') or '')
            if 'MAX_TOKENS' in _finish.upper() or _finish == '2':
                print(f"  [A6] finish_reason=MAX_TOKENS — réponse potentiellement tronquée ({len(text)} chars)", flush=True)
                break
    except Exception:
        pass
    return text or ""


def call_gemini_paid(
    prompt: str,
    temperature: float = 0.3,
    system_instruction: str = None,
    json_mode: bool = False,
    max_tokens: int = 16384,
    disable_thinking: bool = False,
    model: str = None,
) -> str:
    """
    Appel Gemini sur la clé PAYANTE exclusivement (agent créateur — 9 couches).
    Pas de fallback sur clés gratuites, pas de RPD cap.
    Rate-limité sur son propre compteur RPM (MAX_CALLS_PER_MINUTE_PAID).
    """
    if len(prompt) > 120000:
        print(f"  [I6] Prompt très long : {len(prompt)} chars — risque de troncature input", flush=True)

    generation_config = _make_generation_config(temperature, max_tokens, system_instruction, json_mode, disable_thinking)

    import re as _re
    for attempt in range(MAX_RETRIES * 2):
        global _api_pause_until
        with _key_lock:
            pause_end = _api_pause_until
        remaining = pause_end - time.time()
        if remaining > 0:
            time.sleep(remaining)

        current_paid = _get_paid_client_rate_limited()
        try:
            response = current_paid.models.generate_content(
                model=model or MODEL_NAME,
                contents=prompt,
                config=generation_config,
            )
            return _extract_text_from_response(response)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                _retry_match = _re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", str(e), _re.IGNORECASE)
                wait = float(_retry_match.group(1)) + 1.0 if _retry_match else min(30 * (attempt + 1), 120)
                print(f"  [Paid 429] Attente {wait:.0f}s avant retry", flush=True)
                time.sleep(wait)
            elif "503" in error_str or "unavailable" in error_str:
                time.sleep(min((2 ** attempt) * 2, 30))
            else:
                if attempt >= MAX_RETRIES * 2 - 1:
                    raise
                time.sleep(5)

    raise RuntimeError(f"call_gemini_paid : échec après {MAX_RETRIES * 2} tentatives")


def call_gemini(
    prompt: str,
    temperature: float = 0.3,
    system_instruction: str = None,
    json_mode: bool = False,
    max_tokens: int = 16384,
    disable_thinking: bool = False,
    model: str = None,
) -> str:
    """
    Appel Gemini sur les clés GRATUITES d'abord, fallback automatique sur clé payante.
    Utilisé par tous les agents SAUF l'agent créateur (qui utilise call_gemini_paid).

    disable_thinking=True : désactive le thinking de Gemini 2.5-Flash pour préserver
    le budget de tokens pour la génération de code (évite les troncatures).
    """
    if len(prompt) > 120000:
        print(f"  [I6] Prompt très long : {len(prompt)} chars — risque de troncature input", flush=True)

    generation_config = _make_generation_config(temperature, max_tokens, system_instruction, json_mode, disable_thinking)

    import re as _re
    global _api_pause_until
    _consecutive_429 = 0

    # ── Tentatives sur clés gratuites ──
    if _api_keys:
        total_free_attempts = MAX_RETRIES * len(_api_keys)
        for attempt in range(total_free_attempts):
            with _key_lock:
                pause_end = _api_pause_until
            remaining = pause_end - time.time()
            if remaining > 0:
                print(f"  [Pause globale] Attente {remaining:.0f}s", flush=True)
                time.sleep(remaining)

            try:
                key_idx, current_client = _get_available_client()
            except _AllFreeKeysExhausted as exc:
                print(f"  [Clés gratuites] {exc} — fallback clé payante", flush=True)
                break  # Sortir de la boucle gratuite → tomber dans le fallback payant

            try:
                response = current_client.models.generate_content(
                    model=model or MODEL_NAME,
                    contents=prompt,
                    config=generation_config,
                )
                _consecutive_429 = 0
                return _extract_text_from_response(response)

            except Exception as e:
                error_str = str(e).lower()
                if "quota journalier épuisé" in error_str:
                    # Toutes les clés gratuites épuisées → fallback payant
                    print(f"  [Quota gratuit] RPD épuisé — fallback clé payante", flush=True)
                    break
                if "429" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                    _retry_match = _re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", str(e), _re.IGNORECASE)
                    _api_wait = float(_retry_match.group(1)) + 1.0 if _retry_match else None
                    _consecutive_429 += 1
                    if len(_api_keys) > 1:
                        _rotate_key(key_idx)
                        if _consecutive_429 >= len(_api_keys):
                            wait = _api_wait if _api_wait else 90
                            with _key_lock:
                                _api_pause_until = max(_api_pause_until, time.time() + wait)
                            print(f"  [Quota] Clés gratuites rate-limitées — fallback payant", flush=True)
                            break  # Fallback payant plutôt qu'attendre
                    else:
                        wait = _api_wait if _api_wait else min(15 * (attempt + 1), 90)
                        time.sleep(wait)
                elif "503" in error_str or "unavailable" in error_str:
                    _consecutive_429 = 0
                    time.sleep(min((2 ** (attempt % MAX_RETRIES)) * 2, 30))
                else:
                    _consecutive_429 = 0
                    if attempt == total_free_attempts - 1:
                        break  # Fallback payant
                    time.sleep(5)

    # ── Fallback sur clé payante ──
    print(f"  [Fallback payant] Utilisation clé payante pour appel non-créateur", flush=True)
    return call_gemini_paid(
        prompt=prompt, temperature=temperature, system_instruction=system_instruction,
        json_mode=json_mode, max_tokens=max_tokens, disable_thinking=disable_thinking,
        model=model,
    )


def call_gemini_json(prompt: str, temperature: float = 0.2, system_instruction: str = None, max_tokens: int = 24000, disable_thinking: bool = True) -> dict:
    """
    Appel Gemini avec retour JSON parsé automatiquement.
    max_tokens élevé par défaut pour éviter la troncature silencieuse du JSON.
    disable_thinking=True par défaut : évite les délais 30-90s du thinking sur les agents de support.
    """
    raw = call_gemini(
        prompt=prompt,
        temperature=temperature,
        system_instruction=system_instruction,
        json_mode=True,
        max_tokens=max_tokens,
        disable_thinking=disable_thinking,
    )
    # call_gemini garantit str non-None, mais peut être "" (thinking-only / blocked)
    if not raw or not raw.strip():
        raise ValueError("call_gemini_json: réponse vide (thinking-only ou réponse bloquée)")
    # Nettoyage des backticks que le modèle peut ajouter autour du JSON
    raw = raw.strip()
    if raw.startswith("```"):
        # Supprimer la première ligne (```json ou ```)
        lines = raw.split("\n", 1)
        raw = lines[1] if len(lines) > 1 else ""
        # Supprimer la fermeture ```
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]
    raw = raw.strip()
    if not raw:
        raise ValueError("call_gemini_json: JSON vide après nettoyage des backticks")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [JSON parse erreur] {e} — raw[:200]: {raw[:200]}", flush=True)
        raise


# ─────────────────────────────────────────────
# CLAUDE API (Anthropic) — pour l'agent Game Logics
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"

_anthropic_client = None

def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None and ANTHROPIC_API_KEY:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def call_claude(prompt: str, system: str = "", max_tokens: int = 4000, temperature: float = 0.5) -> str:
    """
    Appel Claude (Anthropic) avec retry exponentiel et fallback Gemini.
    """
    client_a = _get_anthropic_client()
    if client_a is None:
        # Pas de clé Anthropic — fallback Gemini (qui a son propre retry)
        return call_gemini(prompt, temperature=temperature, system_instruction=system or None, max_tokens=max_tokens)

    kwargs = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    for attempt in range(MAX_RETRIES):
        _claude_rate_limit()
        try:
            response = client_a.messages.create(**kwargs)
            if not response.content:
                raise ValueError("Claude: réponse vide (contenu bloqué ou absent)")
            return response.content[0].text or ""
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "rate" in error_str or "overloaded" in error_str
            if attempt == MAX_RETRIES - 1 or not is_rate_limit:
                # Dernière tentative ou erreur non-récupérable → fallback Gemini
                print(f"  [Claude API] Erreur : {e} — fallback Gemini")
                break
            wait = (2 ** attempt) * 5
            print(f"  [Claude API] Retry {attempt+1}/{MAX_RETRIES} dans {wait}s", flush=True)
            time.sleep(wait)
        return call_gemini(prompt, temperature=temperature, system_instruction=system or None, max_tokens=max_tokens)


def with_fallback(default_value):
    """
    Décorateur : retourne default_value si l'agent plante,
    au lieu de faire crasher tout le pipeline.
    Logue l'erreur dans le SSE stream si disponible.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                msg = f"[FALLBACK] {fn.__name__} a échoué : {e}"
                print(f"  {msg}")
                try:
                    from logger import coordinateur_log
                    coordinateur_log.warning(msg)
                except Exception:
                    pass
                # G3 : Marquer le fallback pour permettre la détection downstream
                if isinstance(default_value, dict):
                    return {**default_value, "_fallback_used": True}
                return default_value
        return wrapper
    return decorator

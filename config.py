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

# ── Rotation de clés API ──────────────────────────────────────────────────────
# Charge toutes les clés disponibles : GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3...
# Quand une clé fait 429, on passe à la suivante automatiquement.
def _load_api_keys() -> list[str]:
    keys = []
    # Clé principale
    k = os.getenv("GEMINI_API_KEY")
    if k:
        keys.append(k)
    # Clés supplémentaires numérotées (1 à 20)
    for i in range(1, 20):
        k = os.getenv(f"GEMINI_API_KEY_{i}")
        if k:
            keys.append(k)
    if not keys:
        raise RuntimeError("Aucune clé GEMINI_API_KEY trouvée dans .env")
    return keys

_api_keys = _load_api_keys()
# Timeout connect/write de 30s — détecte les connexions mortes sans bloquer les longues générations
# read=300s : 5 minutes max par réponse (couvre Pro 55k tokens) — évite les hangs infinis sur connexion bloquée
import httpx as _httpx
_http_timeout = _httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
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
client = _clients[0]

MAX_CALLS_PER_MINUTE = int(os.getenv("GEMINI_RPM_LIMIT", "4"))        # Free: 5 RPM/clé | Paid: monter à 50+
MAX_CALLS_PER_DAY = int(os.getenv("GEMINI_RPD_LIMIT", "19"))          # Free: 20 RPD/clé | Paid: mettre 9999
# La clé payante (index 0 = GEMINI_API_KEY) a une limite RPM bien plus haute (Flash ~1000 RPM)
# On lui donne une limite interne séparée pour ne pas la bloquer après les appels Pro de Phase 3.
MAX_CALLS_PER_MINUTE_PAID = int(os.getenv("GEMINI_RPM_LIMIT_PAID", "200"))
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
    Retourne (idx, client) de la première clé ayant de la capacité disponible.
    Respecte RPM (4/min) ET RPD (19/jour) par clé.
    Si toutes les clés sont saturées en RPM, attend la fenêtre la plus proche.
    Si toutes les clés sont épuisées en RPD, lève une RuntimeError immédiatement.
    """
    global _current_key_idx, _key_timestamps
    with _key_lock:
        _reset_daily_counts_if_needed()
        now = time.time()
        n = len(_api_keys)

        # Nettoyer les timestamps RPM de toutes les clés
        for i in range(n):
            _key_timestamps[i] = [t for t in _key_timestamps.get(i, []) if now - t < WINDOW_SECONDS]

        # Chercher une clé disponible (RPM ET RPD)
        for offset in range(n):
            idx = (_current_key_idx + offset) % n
            rpd_ok = _key_daily_counts.get(idx, 0) < MAX_CALLS_PER_DAY
            # La clé payante (index 0) a une limite RPM interne plus élevée
            rpm_limit = MAX_CALLS_PER_MINUTE_PAID if idx == 0 else MAX_CALLS_PER_MINUTE
            rpm_ok = len(_key_timestamps[idx]) < rpm_limit
            if rpd_ok and rpm_ok:
                _current_key_idx = idx
                _key_timestamps[idx].append(time.time())
                _key_daily_counts[idx] = _key_daily_counts.get(idx, 0) + 1
                _save_daily_counts()
                return idx, _clients[idx]

        # Vérifier si toutes les clés sont épuisées en RPD (quota journalier)
        all_rpd_exhausted = all(
            _key_daily_counts.get(i, 0) >= MAX_CALLS_PER_DAY for i in range(n)
        )
        if all_rpd_exhausted:
            used = sum(_key_daily_counts.get(i, 0) for i in range(n))
            raise RuntimeError(
                f"Quota journalier épuisé sur toutes les clés ({used}/{n * MAX_CALLS_PER_DAY} appels utilisés aujourd'hui). "
                f"Reset à minuit UTC."
            )

        # Toutes les clés disponibles en RPD sont saturées en RPM — attendre
        # Chercher la clé RPD-ok dont la fenêtre RPM se libère le plus tôt
        rpd_ok_keys = [i for i in range(n) if _key_daily_counts.get(i, 0) < MAX_CALLS_PER_DAY]
        best_idx = min(rpd_ok_keys, key=lambda i: _key_timestamps[i][0] if _key_timestamps[i] else 0)
        oldest = _key_timestamps[best_idx][0] if _key_timestamps[best_idx] else now
        wait = WINDOW_SECONDS - (now - oldest) + 0.5

    # Attente hors du lock pour ne pas bloquer les autres threads
    print(f"  [Rate limit] Toutes les clés saturées — attente {wait:.1f}s", flush=True)
    time.sleep(max(wait, 1.0))

    # Réappel récursif après l'attente
    return _get_available_client()


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
    Appel Gemini avec retry exponentiel sur les erreurs 429/503.
    Rate-limité globalement entre tous les threads.
    Retourne le texte de la réponse.

    disable_thinking=True : désactive le thinking de Gemini 2.5-Flash pour préserver
    le budget de tokens pour la génération de code (évite les troncatures).
    """
    # I6 : Alerte si prompt très long (risque de troncature côté input)
    if len(prompt) > 120000:
        print(f"  [I6] Prompt très long : {len(prompt)} chars — risque de troncature input", flush=True)

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

    generation_config = types.GenerateContentConfig(**config_params)

    import re as _re
    # Nombre de tentatives = MAX_RETRIES × nombre de clés disponibles
    total_attempts = MAX_RETRIES * len(_api_keys)
    # Compteur LOCAL — mais la PAUSE est globale (partagée entre tous les threads via _api_pause_until)
    _consecutive_429 = 0
    for attempt in range(total_attempts):
        # ── Respecter la pause globale déclenchée par n'importe quel thread ──
        global _api_pause_until
        with _key_lock:
            pause_end = _api_pause_until
        remaining = pause_end - time.time()
        if remaining > 0:
            print(f"  [Pause globale] Attente {remaining:.0f}s (rate limit partagé entre threads)", flush=True)
            time.sleep(remaining)

        key_idx, current_client = _get_available_client()
        try:
            response = current_client.models.generate_content(
                model=model or MODEL_NAME,
                contents=prompt,
                config=generation_config,
            )
            # gemini-2.5-flash peut avoir des thinking tokens — extraire uniquement le texte output
            try:
                text = response.text
            except Exception:
                text = None
            # Fallback si response.text est None ou a planté (réponse bloquée / thinking-only)
            if not text:
                text = ""
                for candidate in (response.candidates or []):
                    for part in (candidate.content.parts if candidate.content else []):
                        if hasattr(part, "text") and part.text:
                            text += part.text

            # A6 : Détecter finish_reason == MAX_TOKENS (troncature silencieuse)
            try:
                for candidate in (response.candidates or []):
                    _finish = str(getattr(candidate, 'finish_reason', '') or '')
                    if 'MAX_TOKENS' in _finish.upper() or _finish == '2':
                        print(f"  [A6] finish_reason=MAX_TOKENS — réponse potentiellement tronquée ({len(text)} chars)", flush=True)
                        # Ne pas rejeter — le code tronqué est géré par _autocomplete_truncated_js
                        break
            except Exception:
                pass

            # Succès : reset du compteur local
            _consecutive_429 = 0
            return text or ""

        except Exception as e:
            error_str = str(e).lower()
            # Quota journalier épuisé → erreur fatale, ne jamais retenter
            if "quota journalier" in error_str:
                raise
            if "429" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                # Extraire le délai suggéré par l'API ("retry in X.Xs")
                _retry_match = _re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", str(e), _re.IGNORECASE)
                _api_wait = float(_retry_match.group(1)) + 1.0 if _retry_match else None

                _consecutive_429 += 1
                if len(_api_keys) > 1:
                    _rotate_key(key_idx)
                    # Toutes les clés du cycle épuisées → pause globale (tous les threads attendent)
                    if _consecutive_429 >= len(_api_keys):
                        wait = _api_wait if _api_wait else 90
                        with _key_lock:
                            # Ne jamais raccourcir une pause déjà en cours
                            _api_pause_until = max(_api_pause_until, time.time() + wait)
                        print(
                            f"  [Quota] Toutes les clés rate-limitées — pause globale {wait:.0f}s",
                            flush=True,
                        )
                        time.sleep(wait)
                        _consecutive_429 = 0
                else:
                    # Une seule clé → utiliser le délai API si disponible
                    wait = _api_wait if _api_wait else min(15 * (attempt + 1), 90)
                    time.sleep(wait)
            elif "503" in error_str or "unavailable" in error_str:
                _consecutive_429 = 0
                wait = min((2 ** (attempt % MAX_RETRIES)) * 2, 30)  # max 30s par tentative
                time.sleep(wait)
            else:
                _consecutive_429 = 0
                if attempt == total_attempts - 1:
                    raise
                time.sleep(5)

    raise RuntimeError(f"Échec après {total_attempts} tentatives ({len(_api_keys)} clé(s))")


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

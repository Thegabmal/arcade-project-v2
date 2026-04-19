"""
Mémoire persistante entre les sessions.
Stocke les patterns réussis, les erreurs fréquentes, les stats globales.
"""

import os
import json
import datetime
import threading
from genre_profile import GenreProfile

MEMORY_FILE = "memory.json"
PATTERNS_FILE = "patterns_reussis.json"
MAX_PATTERNS = 20
MAX_SESSIONS = 200  # Rotation : on garde seulement les N dernières sessions

# Lock global — protège les lectures/écritures concurrentes sur les fichiers mémoire
# (agent_sauvegarde et agent_auto_learner peuvent écrire simultanément depuis Flask)
_memory_lock = threading.Lock()


def _load(filepath: str) -> dict:
    with _memory_lock:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


def _save(filepath: str, data: dict):
    with _memory_lock:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def init_memory():
    """Initialise les fichiers de mémoire s'ils n'existent pas."""
    if not os.path.exists(MEMORY_FILE):
        _save(MEMORY_FILE, {
            "sessions": [],
            "stats": {
                "total_games_generated": 0,
                "total_games_saved": 0,
                "scores_by_genre": {},
                "common_errors": [],
            }
        })
    if not os.path.exists(PATTERNS_FILE):
        _save(PATTERNS_FILE, {"patterns": []})


def save_session(
    prompt: str,
    genre_profile: GenreProfile,
    score_global: float,
    saved: bool,
    filename: str = "",
    errors: list = None,
):
    """Enregistre une session dans la mémoire."""
    data = _load(MEMORY_FILE)

    session = {
        "date": datetime.datetime.now().isoformat(),
        "prompt": prompt,
        "genre": genre_profile.genre_principal,
        "sous_genre": genre_profile.sous_genre,
        "score": score_global,
        "saved": saved,
        "filename": filename,
        "errors": errors or [],
    }
    data["sessions"].append(session)

    # Rotation : éviter la croissance illimitée du fichier mémoire
    if len(data["sessions"]) > MAX_SESSIONS:
        data["sessions"] = data["sessions"][-MAX_SESSIONS:]

    # Stats
    stats = data["stats"]
    stats["total_games_generated"] += 1
    if saved:
        stats["total_games_saved"] += 1

    genre = genre_profile.genre_principal
    if genre not in stats["scores_by_genre"]:
        stats["scores_by_genre"][genre] = []
    stats["scores_by_genre"][genre].append(score_global)

    _save(MEMORY_FILE, data)


def save_pattern(genre_profile: GenreProfile, score: float, code_snippet: str, notes: str = ""):
    """Sauvegarde un pattern réussi pour améliorer les futures générations."""
    data = _load(PATTERNS_FILE)
    patterns = data.get("patterns", [])

    pattern = {
        "date": datetime.datetime.now().isoformat(),
        "genre": genre_profile.genre_principal,
        "sous_genre": genre_profile.sous_genre,
        "score": score,
        "mecaniques": genre_profile.mecaniques_obligatoires,
        "style_visuel": genre_profile.style_visuel,
        "boucle_core": genre_profile.boucle_core,
        "code_snippet": code_snippet[:500],  # Extrait du code
        "notes": notes,
    }

    patterns.append(pattern)
    # Garder seulement les meilleurs patterns, triés par score
    patterns.sort(key=lambda x: x["score"], reverse=True)
    patterns = patterns[:MAX_PATTERNS]
    data["patterns"] = patterns
    _save(PATTERNS_FILE, data)


def get_patterns_for_genre(genre: str) -> list:
    """Récupère les patterns réussis pour un genre donné."""
    data = _load(PATTERNS_FILE)
    patterns = data.get("patterns", [])
    # D'abord les patterns du même genre, puis les autres
    same_genre = [p for p in patterns if p["genre"].lower() == genre.lower()]
    other = [p for p in patterns if p["genre"].lower() != genre.lower()]
    return same_genre[:5] + other[:3]


def get_errors_for_genre(genre: str, n: int = 5) -> list:
    """Retourne les erreurs fréquentes pour un genre donné (sessions échouées récentes)."""
    data = _load(MEMORY_FILE)
    sessions = data.get("sessions", [])
    errors = []
    for s in reversed(sessions):
        if s.get("genre", "").lower() == genre.lower() and not s.get("saved") and s.get("errors"):
            errors.extend(s["errors"])
        if len(errors) >= n * 2:
            break
    # Dédupliquer et garder les n plus fréquents
    seen = []
    for e in errors:
        if e and e not in seen:
            seen.append(e)
        if len(seen) >= n:
            break
    return seen


def save_validator_errors(genre: str, errors: list):
    """
    Enregistre les erreurs structurelles détectées par le validateur.
    Elles seront réutilisées dans erreurs_passees pour les sessions suivantes.
    """
    if not errors:
        return
    data = _load(MEMORY_FILE)
    stats = data.get("stats", {})
    genre_errors = stats.get("validator_errors_by_genre", {})
    existing = genre_errors.get(genre, [])
    for e in errors:
        if e and e not in existing:
            existing.append(e)
    genre_errors[genre] = existing[-20:]  # garder les 20 dernières max
    stats["validator_errors_by_genre"] = genre_errors
    data["stats"] = stats
    _save(MEMORY_FILE, data)


def get_validator_errors_for_genre(genre: str, n: int = 5) -> list:
    """Retourne les erreurs structurelles connues pour ce genre."""
    data = _load(MEMORY_FILE)
    errors = data.get("stats", {}).get("validator_errors_by_genre", {}).get(genre, [])
    return errors[-n:]


def get_stats() -> dict:
    """Retourne les statistiques globales."""
    data = _load(MEMORY_FILE)
    return data.get("stats", {})


def get_recent_sessions(n: int = 5) -> list:
    """Retourne les n dernières sessions."""
    data = _load(MEMORY_FILE)
    sessions = data.get("sessions", [])
    return sessions[-n:]


# ─────────────────────────────────────────────
# E — Mémoire d'erreurs par couche
# ─────────────────────────────────────────────

def save_layer_errors(genre: str, layer, errors: list):
    """
    Enregistre les erreurs survenues dans une couche spécifique pour un genre.
    layer : 1, '2a', '2b', 3, 4, 5 (int ou str).
    """
    if not errors:
        return
    data = _load(MEMORY_FILE)
    stats = data.setdefault("stats", {})
    layer_errors = stats.setdefault("layer_errors_by_genre", {})
    key = "%s_L%s" % (genre.lower(), str(layer))
    existing = layer_errors.get(key, [])
    for e in errors:
        if e and e not in existing:
            existing.append(str(e))
    layer_errors[key] = existing[-15:]
    stats["layer_errors_by_genre"] = layer_errors
    data["stats"] = stats
    _save(MEMORY_FILE, data)


def get_layer_errors(genre: str, layer, n: int = 4) -> list:
    """Retourne les erreurs connues pour une couche et un genre donnés."""
    data = _load(MEMORY_FILE)
    key = "%s_L%s" % (genre.lower(), str(layer))
    errors = data.get("stats", {}).get("layer_errors_by_genre", {}).get(key, [])
    return errors[-n:]

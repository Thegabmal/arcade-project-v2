"""
Genre Score Profiler — tracks scores by dimension for each genre.
Automatically identifies weak dimensions and injects targeted tips
into the creator's prompt to fix systematically low scores.

Storage: genre_scores.json (same directory as this file)
  {
    "rpg": {
      "count": 5,
      "dimensions": {
        "technique":  [7.4, 6.5, 8.1, 7.0, 6.8],
        "gameplay":   [8.1, 9.0, 8.5, 8.0, 7.5],
        "visuel":     [6.2, 5.8, 7.0, 6.5, 6.1],
        "execution":  [7.6, 8.0, 7.2, 6.9, 7.5],
        "playtester": [6.9, 7.5, 7.0, 7.2, 6.8]
      }
    },
    ...
  }
"""

import json
import os

PROFILE_FILE = os.path.join(os.path.dirname(__file__), "genre_scores.json")
WEAK_THRESHOLD = 7.0   # Dimension considérée "faible" sous ce seuil
MIN_GAMES = 2          # Minimum de jeux pour avoir un signal fiable
MAX_HISTORY = 10       # Garder les N dernières valeurs par dimension

DIMENSIONS = ["technique", "gameplay", "visuel", "execution", "playtester"]

# Conseils injectés dans le prompt créateur pour chaque dimension faible
_FOCUS_HINTS = {
    "technique": (
        "⚠ Technique historiquement faible pour ce genre → vérifie impérativement : "
        "DOMContentLoaded wrapper, requestAnimationFrame, delta time passé à TOUTES les fonctions, "
        "boucles inversées avec const X = arr[i], pas de const réassigné, gameState machine complète."
    ),
    "gameplay": (
        "⚠ Gameplay historiquement faible pour ce genre → assure-toi que le jeu est immédiatement jouable : "
        "contrôles réactifs dès l'écran menu, difficulté progressive (pas d'écran vide au départ), "
        "feedback visuel immédiat sur chaque action, restart fonctionnel en JS pur."
    ),
    "visuel": (
        "⚠ Visuel historiquement faible pour ce genre → soigne particulièrement : "
        "fond non noir (couleur de palette définie), entités visuellement distinctes du fond, "
        "HUD lisible avec score + vie en permanence, animations de hit/mort (flash ou particules), "
        "transitions entre états (menu→jeu→gameover)."
    ),
    "execution": (
        "⚠ Exécution Playwright historiquement faible pour ce genre → priorité absolue à : "
        "canvas visible dès le chargement (pas d'écran noir), click sur le menu fonctionne, "
        "aucune ReferenceError au démarrage, gameLoop lancée dans DOMContentLoaded, "
        "pas de location.reload() pour le restart."
    ),
    "playtester": (
        "⚠ Experience joueur historiquement faible pour ce genre → améliore : "
        "tutoriel implicite (contrôles affichés dans le menu), progression de difficulté smooth, "
        "sessions de 2-5 min (pas de niveaux infinis ou de mort instantanée), "
        "récompenses visuelles fréquentes (score qui monte, particules, sons)."
    ),
}


def _load() -> dict:
    if not os.path.exists(PROFILE_FILE):
        return {}
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record(genre: str, scores: dict) -> None:
    """
    Enregistre les scores d'une génération pour un genre.
    Appelé après CHAQUE génération (approuvée ou non) pour avoir un signal complet.

    scores = { "technique": 7.4, "gameplay": 8.1, "visuel": 6.2, "execution": 7.6, "playtester": 6.9 }
    """
    if not genre or not scores:
        return
    genre = genre.lower().strip()
    data = _load()

    if genre not in data:
        data[genre] = {"count": 0, "dimensions": {d: [] for d in DIMENSIONS}}

    data[genre]["count"] = data[genre].get("count", 0) + 1

    for dim in DIMENSIONS:
        val = scores.get(dim)
        if val is not None:
            history = data[genre]["dimensions"].setdefault(dim, [])
            history.append(round(float(val), 2))
            # Garder uniquement les MAX_HISTORY dernières valeurs
            if len(history) > MAX_HISTORY:
                data[genre]["dimensions"][dim] = history[-MAX_HISTORY:]

    _save(data)


def get_averages(genre: str) -> dict:
    """Retourne les moyennes par dimension pour un genre."""
    genre = genre.lower().strip()
    data = _load()
    profile = data.get(genre, {})
    dims = profile.get("dimensions", {})
    averages = {}
    for dim in DIMENSIONS:
        history = dims.get(dim, [])
        if history:
            averages[dim] = round(sum(history) / len(history), 2)
    return averages


def get_weak_dimensions(genre: str) -> list[str]:
    """
    Retourne les dimensions faibles (moyenne < WEAK_THRESHOLD) pour un genre.
    Ne retourne rien si le genre a moins de MIN_GAMES entrées.
    """
    genre = genre.lower().strip()
    data = _load()
    profile = data.get(genre, {})
    if profile.get("count", 0) < MIN_GAMES:
        return []

    dims = profile.get("dimensions", {})
    weak = []
    for dim in DIMENSIONS:
        history = dims.get(dim, [])
        if len(history) >= MIN_GAMES:
            avg = sum(history) / len(history)
            if avg < WEAK_THRESHOLD:
                weak.append(dim)
    return weak


def format_for_prompt(genre: str) -> str:
    """
    Retourne un bloc de texte à injecter dans le prompt créateur.
    Contient des conseils ciblés sur les dimensions historiquement faibles.
    Retourne une chaîne vide si pas assez de données.
    """
    weak = get_weak_dimensions(genre)
    if not weak:
        return ""

    avgs = get_averages(genre)
    lines = [
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"PROFIL GENRE '{genre.upper()}' — POINTS FAIBLES HISTORIQUES",
        f"(basé sur les générations précédentes de ce genre)",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for dim in weak:
        avg_str = f"{avgs[dim]:.1f}/10" if dim in avgs else "?"
        hint = _FOCUS_HINTS.get(dim, "")
        lines.append(f"\n[Moy. {dim}: {avg_str}] {hint}")

    return "\n".join(lines) + "\n"


def get_stats_summary() -> str:
    """Retourne un résumé lisible de tous les profils pour debug/logs."""
    data = _load()
    if not data:
        return "Aucun profil genre enregistré."
    lines = ["=== Genre Score Profiler ==="]
    for genre, profile in sorted(data.items()):
        count = profile.get("count", 0)
        avgs = {dim: round(sum(v)/len(v), 1) for dim, v in profile.get("dimensions", {}).items() if v}
        weak = [d for d, a in avgs.items() if a < WEAK_THRESHOLD]
        lines.append(f"  {genre:15s} ({count} jeux) — {avgs}")
        if weak:
            lines.append(f"    ⚠ Faible: {weak}")
    return "\n".join(lines)


def get_dashboard() -> dict:
    """
    Retourne les statistiques complètes pour le dashboard Flask /api/stats.
    Inclut : taux d'approbation, score moyen global, issues fréquentes, tendances.
    """
    data = _load()
    genres_stats = []
    for genre, profile in sorted(data.items()):
        count = profile.get("count", 0)
        dims = profile.get("dimensions", {})
        avgs = {dim: round(sum(v)/len(v), 2) for dim, v in dims.items() if v}
        # Score global pondéré (mêmes poids que coordinateur)
        weights = {"technique": 0.20, "gameplay": 0.25, "visuel": 0.15,
                   "execution": 0.20, "playtester": 0.10}
        global_avg = round(
            sum(avgs.get(d, 5.0) * w for d, w in weights.items()), 2
        )
        # Taux d'approbation estimé (exec >= 4.5 ET global >= 6.5)
        exec_hist = dims.get("execution", [])
        approved_count = sum(
            1 for i in range(min(len(exec_hist), count))
            if exec_hist[i] >= 4.5
        )
        approval_rate = round(approved_count / max(count, 1) * 100, 1)
        weak_dims = [d for d, a in avgs.items() if a < WEAK_THRESHOLD]
        genres_stats.append({
            "genre": genre,
            "count": count,
            "score_moyen": global_avg,
            "scores_par_dimension": avgs,
            "dimensions_faibles": weak_dims,
            "taux_approbation_estime": f"{approval_rate}%",
        })

    # Stats globales
    all_counts = [g["count"] for g in genres_stats]
    all_scores = [g["score_moyen"] for g in genres_stats]
    return {
        "genres": genres_stats,
        "total_genres": len(genres_stats),
        "total_jeux": sum(all_counts),
        "score_moyen_global": round(sum(all_scores) / max(len(all_scores), 1), 2),
        "patch_bank": _patch_bank_stats(),
        "stubs_frequents": _stubs_stats(),
    }


def _patch_bank_stats() -> dict:
    try:
        from patch_bank import stats as pb_stats
        return pb_stats()
    except Exception:
        return {}


def _stubs_stats() -> dict:
    try:
        from auto_learner import stubs_report
        r = stubs_report()
        return dict(list(r.items())[:5])  # top 5
    except Exception:
        return {}


if __name__ == "__main__":
    print(get_stats_summary())

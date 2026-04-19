"""
Agent Modérateur-Classificateur — Phase 1
Combine la modération et la classification en un seul appel API.
Valide le prompt ET identifie le genre/technologie en une seule requête.
"""

from config import call_gemini_json, with_fallback
from logger import phase1_log

SYSTEM = """Tu es un expert en jeux vidéo et en modération de contenu.
Tu analyses les demandes de jeux HTML5 : tu vérifies la faisabilité et identifies le genre en une seule réponse.
Tu réponds UNIQUEMENT en JSON valide."""


def run(prompt: str) -> dict:
    """
    Retourne un dict avec à la fois les données de modération ET de classification :
    {
      "valide": bool,
      "raison_rejet": str or null,
      "avertissements": [],
      "prompt_nettoye": str,
      "genre_principal": str,
      "sous_genre": str,
      "technologie": "canvas2d" | "threejs",
      "mots_cles": []
    }
    """
    phase1_log.agent_start("Modération & Classification", f"Analyse du prompt")

    result = _call(prompt)

    valide = result.get("valide", True)
    genre = result.get("genre_principal", "arcade")
    techno = result.get("technologie", "canvas2d")

    if not valide:
        phase1_log.agent_done("Modération & Classification", f"Rejeté: {result.get('raison_rejet', '?')}")
    else:
        phase1_log.agent_done("Modération & Classification", f"OK — {genre} ({techno})")

    return result


@with_fallback({
    "valide": True,
    "raison_rejet": None,
    "avertissements": [],
    "prompt_nettoye": "",
    "genre_principal": "arcade",
    "sous_genre": "action",
    "technologie": "canvas2d",
    "complexite_estimee": "moyenne",
    "mots_cles": []
})
def _call(prompt: str) -> dict:
    return call_gemini_json(f"""Analyse cette demande de jeu HTML5.

PROMPT UTILISATEUR : "{prompt}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÉTAPE 1 — MODÉRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vérifie que le prompt est valide pour générer un jeu HTML5.
REJET si : contenu haineux, pornographique, promotion de violence réelle, demande non liée aux jeux.
AUTORISÉ : violence fictive (shooters, combats, horreur), tout genre de jeu vidéo.
AVERTISSEMENT (pas de rejet) : demande très complexe, références ambiguës, prompt vague.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÉTAPE 2 — CLASSIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Identifie le genre principal et sous-genre.

TECHNOLOGIE :
- "threejs" si le prompt contient explicitement : 3D, three.js, fps, first-person, third-person, monde 3d,
  vue 3d, en 3 dimensions, 3 dimensions, shooter 3d, jeu 3d, environnement 3d
- "canvas2d" par défaut (y compris perspective isométrique, vue de dessus, vue de côté)

COMPLEXITÉ (pour adapter le budget de génération) :
- "simple" : jeu à 1-2 mécaniques, genre classique (pong, snake, breakout style)
- "moyenne" : jeu avec plusieurs systèmes, genre standard (platformer, shooter, puzzle)
- "elevee" : jeu avec systèmes complexes (RPG, tower defense, roguelike, 3D)

Réponds en JSON :
{{
  "valide": true,
  "raison_rejet": null,
  "avertissements": [],
  "prompt_nettoye": "prompt nettoyé sans < > et backticks",
  "genre_principal": "platformer | shooter | puzzle | rpg | racing | tower defense | survival | rhythm | arcade | fighting | autre",
  "sous_genre": "sous-genre précis (ex: bullet hell, metroidvania, match-3, dungeon crawler...)",
  "technologie": "canvas2d",
  "complexite_estimee": "simple | moyenne | elevee",
  "mots_cles": ["mot-clé 1", "mot-clé 2"]
}}""", temperature=0.1, max_tokens=2000)

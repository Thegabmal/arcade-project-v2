"""
Moderator-Classifier Agent — Phase 1
Combines moderation and classification in a single API call.
Validates the prompt AND identifies the genre/technology in one request.
"""

from config import call_gemini_json, with_fallback
from logger import phase1_log

SYSTEM = """You are an expert in video games and content moderation.
You analyze HTML5 game requests: you check feasibility and identify the genre in a single response.
You respond ONLY with valid JSON."""


def run(prompt: str) -> dict:
    """
    Returns a dict with both moderation AND classification data:
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
    phase1_log.agent_start("Moderation & Classification", f"Analyzing the prompt")

    result = _call(prompt)

    valide = result.get("valide", True)
    genre = result.get("genre_principal", "arcade")
    techno = result.get("technologie", "canvas2d")

    if not valide:
        phase1_log.agent_done("Moderation & Classification", f"Rejected: {result.get('raison_rejet', '?')}")
    else:
        phase1_log.agent_done("Moderation & Classification", f"OK — {genre} ({techno})")

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
    "is_narrative": False,
    "mots_cles": []
})
def _call(prompt: str) -> dict:
    return call_gemini_json(f"""Analyze this HTML5 game request.

USER PROMPT: "{prompt}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — MODERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Check that the prompt is valid for generating an HTML5 game.
REJECT if: hateful content, pornography, promotion of real violence, request unrelated to games.
ALLOWED: fictional violence (shooters, combat, horror), any video game genre.
WARNING (no rejection): very complex request, ambiguous references, vague prompt.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — CLASSIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Identify the main genre and sub-genre.

TECHNOLOGY:
- "threejs" if the prompt explicitly contains: 3D, three.js, fps, first-person, third-person, monde 3d,
  vue 3d, en 3 dimensions, 3 dimensions, shooter 3d, jeu 3d, environnement 3d
- "canvas2d" by default (including isometric perspective, top-down view, side view)

NARRATIVE MODE (is_narrative: true if):
- The prompt mentions a story, quest, scenario, characters, dialogues, RPG, visual novel,
  text adventure, tale, plot, narrative mission, main quest, narrative choice,
  point-and-click, adventure game, interactive story
- Intrinsically narrative genres: RPG, visual novel, point-and-click, adventure, narrative game
- Note: a shooter with "a story" = is_narrative:true + genre shooter

COMPLEXITY (to adapt the generation budget):
- "simple": game with 1-2 mechanics, classic genre (pong, snake, breakout style)
- "moyenne": game with multiple systems, standard genre (platformer, shooter, puzzle)
- "elevee": game with complex systems (RPG, tower defense, roguelike, 3D)

Respond in JSON:
{{
  "valide": true,
  "raison_rejet": null,
  "avertissements": [],
  "prompt_nettoye": "cleaned prompt without < > and backticks",
  "genre_principal": "platformer | shooter | puzzle | rpg | racing | tower defense | survival | rhythm | arcade | fighting | autre",
  "sous_genre": "precise sub-genre (e.g.: bullet hell, metroidvania, match-3, dungeon crawler...)",
  "technologie": "canvas2d",
  "complexite_estimee": "simple | moyenne | elevee",
  "is_narrative": false,
  "mots_cles": ["keyword 1", "keyword 2"]
}}""", temperature=0.1, max_tokens=2000)

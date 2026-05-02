"""
Genre Intelligence Agent — Phase 1
Merges agent_chercheur + agent_veilleur into a single API call.

Produces in one request:
  - Structured research (mechanics, references, pitfalls, standards, technical notes)
  - Trends text document (what's hot, winning core loop, what's dated)

Advantage vs two separate agents:
  - 1 API call instead of 2 (saves 6s on the rate limiter)
  - More coherent analysis: trends and mechanics come from the same source
  - Reference games enriched with mecanique_signature used in the trends doc
"""

from config import call_gemini_json, with_fallback
from genre_profile import Classification, Research
from logger import phase1_log
import rag

SYSTEM = """You are an expert in game design, game studies, and video game market trends.
You combine structured analysis and market research to provide a comprehensive knowledge base.
You know the fundamental mechanics of each genre AND what is popular today.
You respond ONLY with valid JSON."""


def run(classification: Classification) -> tuple[Research, str]:
    """
    Analyzes the genre and returns (Research, trends_text).
    - Research: structured data for the Enricher
    - trends_text: formatted document injected into the Creator
    """
    phase1_log.agent_start(
        "Genre Intelligence",
        f"Analyzing {classification.genre_principal} / {classification.sous_genre}"
    )

    # Enrichment via mechanics_kb (ChromaDB RAG) — silent fallback
    mechanics_refs = rag.search_mechanics(
        genre=classification.genre_principal,
        query=f"{classification.sous_genre} {classification.type_gameplay} {classification.ton}",
        n=3,
    )

    result = _call(classification, mechanics_refs)

    research = Research(
        mecaniques_populaires=result.get("mecaniques_populaires", []),
        mecaniques_tendance=result.get("mecaniques_tendance", []),
        jeux_reference=result.get("jeux_reference", []),
        pieges_courants=result.get("pieges_courants", []),
        standards_visuels=result.get("standards_visuels", []),
        techniques_recommandees=result.get("techniques_recommandees", []),
        core_loop_typique=result.get("core_loop_typique", ""),
        progression_typique=result.get("progression_typique", ""),
        notes_techniques=result.get("notes_techniques", ""),
    )

    tendances_text = _build_tendances_text(result, classification)

    phase1_log.agent_done(
        "Genre Intelligence",
        f"{len(research.mecaniques_populaires)} mechanics, "
        f"{len(research.jeux_reference)} references, "
        f"{len(tendances_text)} chars trends"
    )
    return research, tendances_text


def _build_tendances_text(result: dict, classification: Classification) -> str:
    """Builds the trends document from the returned JSON fields."""
    genre = classification.genre_principal.upper()

    jeux_section = ""
    for j in result.get("jeux_reference", [])[:6]:
        nom = j.get("nom", "?")
        force = j.get("points_forts", "")
        sig = j.get("mecanique_signature", "")
        jeux_section += f"\n- {nom}: {force}"
        if sig:
            jeux_section += f" | Signature: {sig}"

    mecaniques = "\n".join(f"- {m}" for m in result.get("mecaniques_tendance", []))
    dates = "\n".join(f"- {d}" for d in result.get("ce_qui_est_date", result.get("pieges_courants", [])))
    recette = "\n".join(f"- {r}" for r in result.get("recette_succes_html5", []))

    return f"""=== GENRE INTELLIGENCE: {genre} ===

CURRENT REFERENCE GAMES:{jeux_section}

TRENDING MECHANICS RIGHT NOW:
{mecaniques}

WINNING CORE LOOP:
{result.get("core_loop_typique", "")}

PROGRESSION PATTERNS:
{result.get("progression_typique", "")}

WHAT'S DATED / TO AVOID:
{dates}

SUCCESS RECIPE FOR AN HTML5 GAME:
{recette}

TECHNICAL NOTES:
{result.get("notes_techniques", "")}"""


def _fallback_research() -> Research:
    return Research(
        mecaniques_populaires=[],
        mecaniques_tendance=[],
        jeux_reference=[],
        pieges_courants=[],
        standards_visuels=[],
        techniques_recommandees=[],
        core_loop_typique="",
        progression_typique="",
        notes_techniques="",
    )


def _fallback_tendances(classification: Classification) -> str:
    return (
        f"=== TRENDS {classification.genre_principal.upper()} ===\n"
        f"Analysis unavailable — use general genre standards.\n"
        f"ESSENTIALS: clear core loop, immediate feedback, visible progression, replayability."
    )


@with_fallback({
    "mecaniques_populaires": [],
    "mecaniques_tendance": [],
    "jeux_reference": [],
    "pieges_courants": [],
    "standards_visuels": [],
    "techniques_recommandees": [],
    "core_loop_typique": "",
    "progression_typique": "",
    "notes_techniques": "",
    "ce_qui_est_date": [],
    "recette_succes_html5": [],
})
def _call(classification: Classification, mechanics_refs: list = None) -> dict:
    # Build the mechanics_kb reference block if available
    mechanics_context = ""
    if mechanics_refs:
        lines = []
        for ref in mechanics_refs:
            name = ref.get("game_name", "?")
            doc = ref.get("document", "")
            # Extract the first 3 lines of the document to stay concise
            short = "\n".join(doc.splitlines()[:6]) if doc else ""
            lines.append(f"--- {name} ---\n{short}")
        mechanics_context = (
            "\n\n=== MECHANICS REFERENCES (internal knowledge base) ===\n"
            + "\n\n".join(lines)
            + "\n=== END REFERENCES ===\n"
        )

    prompt = f"""Complete expert analysis of the following game genre to guide the creation of an HTML5 game.

GENRE: {classification.genre_principal}
SUB-GENRE: {classification.sous_genre}
TONE: {classification.ton}
AUDIENCE: {classification.public_cible}
EXPECTED VISUAL STYLE: {classification.style_visuel_attendu}
GAMEPLAY TYPE: {classification.type_gameplay}

Provide an analysis in two parts:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 1 — STRUCTURED ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. POPULAR MECHANICS (5-8): fundamental mechanics that define this genre today
2. TRENDING MECHANICS (3-5): what is modern and exciting in this genre currently
3. REFERENCE GAMES (5-7): the must-knows with their key strength AND their unique signature mechanic
4. COMMON PITFALLS (4-6): typical mistakes that ruin games in this genre
5. VISUAL STANDARDS: what players visually expect for this genre
6. RECOMMENDED TECHNIQUES: JS/Canvas approaches specific to this genre
7. CORE LOOP: the fundamental gameplay loop in one sentence ACTION → REWARD → TENSION
8. PROGRESSION: how this genre structures the difficulty ramp-up
9. TECHNICAL NOTES: HTML5 Canvas specifics for implementing this genre

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART 2 — TRENDS & RECIPES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. WHAT'S DATED / TO AVOID (4-5): patterns that make the game look old or amateurish
11. HTML5 SUCCESS RECIPE (4-5): concrete recommendations to maximize perceived quality
    taking into account HTML5 constraints (no external assets, single file, no native audio)

Respond in JSON:
{{
  "mecaniques_populaires": ["mechanic 1", "mechanic 2"],
  "mecaniques_tendance": ["trend 1", "trend 2"],
  "jeux_reference": [
    {{"nom": "...", "points_forts": "why it is popular", "mecanique_signature": "what makes it unique"}}
  ],
  "pieges_courants": ["pitfall 1", "pitfall 2"],
  "standards_visuels": ["standard 1", "standard 2"],
  "techniques_recommandees": ["technique 1", "technique 2"],
  "core_loop_typique": "ACTION → REWARD → TENSION → ACTION",
  "progression_typique": "how difficulty evolves in this genre",
  "notes_techniques": "important technical specifics for HTML5/Canvas/JS",
  "ce_qui_est_date": ["dated pattern 1", "dated pattern 2"],
  "recette_succes_html5": ["recommendation 1", "recommendation 2"]
}}"""

    return call_gemini_json(prompt, temperature=0.4, system_instruction=SYSTEM, max_tokens=16000)

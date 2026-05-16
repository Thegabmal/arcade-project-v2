"""
Enricher Agent — Phase 1
Combines classification and research to produce:
- A complete GenreProfile with adaptive evaluation criteria
- An ultra-detailed prompt for the Game Designer
- A technical prompt for the Creator

Two-pass design to avoid JSON truncation:
  Pass 1 (JSON)  — compact structured data (mechanics, QC criteria, style)
  Pass 2 (text)  — large text blobs (prompt_enrichi + prompt_technique) as plain text
"""

import json
from config import call_gemini_json, call_gemini, with_fallback
from genre_profile import Classification, Research, GenreProfile
from logger import phase1_log

SYSTEM = """You are a game design expert capable of transforming a simple request
into a complete creative and technical vision. You produce ultra-detailed prompts
that provide all the material needed to create an excellent game.
You respond ONLY in valid JSON."""

SYSTEM_TEXT = """You are a game design expert. Write detailed, structured design
specifications in plain text. Be specific, use numbers and formulas where relevant."""


def run(prompt_original: str, classification: Classification, research: Research) -> GenreProfile:
    phase1_log.agent_start("Enrichisseur", "Génération du GenreProfile complet")

    refs_str = "\n".join([
        f"  - {r['nom']}: {r.get('points_forts', '')}"
        for r in research.jeux_reference
    ])

    context = f"""ORIGINAL REQUEST: "{prompt_original}"

CLASSIFICATION:
- Genre: {classification.genre_principal}
- Sub-genre: {classification.sous_genre}
- Tone: {classification.ton}
- Audience: {classification.public_cible}
- Visual style: {classification.style_visuel_attendu}
- Gameplay type: {classification.type_gameplay}

RESEARCH:
- Popular mechanics: {json.dumps(research.mecaniques_populaires, ensure_ascii=False)}
- Trending mechanics: {json.dumps(research.mecaniques_tendance, ensure_ascii=False)}
- Typical core loop: {research.core_loop_typique}
- Typical progression: {research.progression_typique}
- Pitfalls to avoid: {json.dumps(research.pieges_courants, ensure_ascii=False)}
- Visual standards: {json.dumps(research.standards_visuels, ensure_ascii=False)}
- Technical notes: {research.notes_techniques}

REFERENCE GAMES:
{refs_str}"""

    result = _call_two_pass(context, classification, prompt_original)

    genre_profile = GenreProfile(
        genre_principal=classification.genre_principal,
        sous_genre=classification.sous_genre,
        ton=classification.ton,
        public_cible=classification.public_cible,
        type_gameplay=classification.type_gameplay,
        mecaniques_obligatoires=result.get("mecaniques_obligatoires", []),
        mecaniques_bonus=result.get("mecaniques_bonus", []),
        mecaniques_a_eviter=result.get("mecaniques_a_eviter", []),
        style_visuel=result.get("style_visuel", classification.style_visuel_attendu),
        palette_recommandee=result.get("palette_recommandee", ""),
        animations_cles=result.get("animations_cles", []),
        effets_importants=result.get("effets_importants", []),
        boucle_core=result.get("boucle_core", ""),
        structure_progression=result.get("structure_progression", ""),
        courbe_difficulte=result.get("courbe_difficulte", ""),
        criteres_qc_technique=result.get("criteres_qc_technique", []),
        criteres_qc_gameplay=result.get("criteres_qc_gameplay", []),
        criteres_qc_visuel=result.get("criteres_qc_visuel", []),
        jeux_reference=[r.get("nom", "") for r in research.jeux_reference],
        pieges_courants=research.pieges_courants,
        notes_techniques=research.notes_techniques,
        prompt_utilisateur_original=prompt_original,
        prompt_enrichi=result.get("prompt_enrichi", prompt_original),
        prompt_technique=result.get("prompt_technique", ""),
    )

    _nb_mecaniques = len(genre_profile.mecaniques_obligatoires)
    _prompt_len = len(genre_profile.prompt_enrichi)
    if _nb_mecaniques < 3:
        phase1_log.warning(f"G1 : seulement {_nb_mecaniques} mécanique(s) obligatoire(s) — attendu ≥ 3")
    if _prompt_len < 200:
        phase1_log.warning(f"G1 : prompt_enrichi trop court ({_prompt_len} chars) — attendu ≥ 200")
    else:
        phase1_log.info(f"G1 : GenreProfile validé — {_nb_mecaniques} mécaniques, prompt {_prompt_len} chars")

    phase1_log.agent_done("Enrichisseur", genre_profile.summary())
    phase1_log.info(f"Mécaniques obligatoires : {', '.join(genre_profile.mecaniques_obligatoires[:3])}...")
    phase1_log.info(f"Prompt enrichi : {len(genre_profile.prompt_enrichi)} caractères")

    return genre_profile


@with_fallback({
    "mecaniques_obligatoires": [],
    "mecaniques_bonus": [],
    "mecaniques_a_eviter": [],
    "style_visuel": "cartoon 2D",
    "palette_recommandee": "couleurs vives",
    "animations_cles": [],
    "effets_importants": [],
    "boucle_core": "",
    "structure_progression": "",
    "courbe_difficulte": "",
    "criteres_qc_technique": [],
    "criteres_qc_gameplay": [],
    "criteres_qc_visuel": [],
    "prompt_enrichi": "",
    "prompt_technique": "",
})
def _call_two_pass(context: str, classification: Classification, prompt_original: str) -> dict:
    # ── Pass 1: Compact JSON — structured data only, no large text blobs ──
    # Keeping this small (~4-6K chars output) prevents JSON decoder truncation.
    structural_prompt = f"""{context}

Generate a GenreProfile in JSON. Structured data only — no long text descriptions.

Rules for QC criteria:
- Weights must sum to EXACTLY 10.0 per category
- Each criterion must be verifiable in source code
- GAMEPLAY criteria must include: enemy variety, system depth, meta-loop

{{
  "mecaniques_obligatoires": ["...", "..."],
  "mecaniques_bonus": ["...", "..."],
  "mecaniques_a_eviter": ["...", "..."],
  "style_visuel": "one sentence",
  "palette_recommandee": "one sentence",
  "animations_cles": ["...", "..."],
  "effets_importants": ["...", "..."],
  "boucle_core": "2-3 sentences max",
  "structure_progression": "2-3 sentences with numeric values",
  "courbe_difficulte": "values only: x1.0 t=0, x1.5 t=60s, x2.5 t=120s",
  "criteres_qc_technique": [
    {{"nom": "...", "description": "...", "poids": 1.5, "comment_verifier": "..."}}
  ],
  "criteres_qc_gameplay": [
    {{"nom": "Enemy variety", "description": "At least 3 distinct enemy types", "poids": 2.0, "comment_verifier": "3+ types in ENEMY_DEFS"}},
    {{"nom": "...", "description": "...", "poids": 1.5, "comment_verifier": "..."}}
  ],
  "criteres_qc_visuel": [
    {{"nom": "...", "description": "...", "poids": 2.0, "comment_verifier": "..."}}
  ]
}}"""

    result = call_gemini_json(
        structural_prompt,
        temperature=0.4,
        system_instruction=SYSTEM,
        max_tokens=12000,
        disable_thinking=True,
    )

    # ── Pass 2: Plain text — large prompts without JSON overhead ──
    text_prompt = f"""{context}

Write two design prompts for this {classification.genre_principal} game.

=== GAME DESIGNER PROMPT ===
25-35 lines covering:
- Interconnected systems and their key interactions
- Numeric formulas (damage, economy, spawn rate, progression)
- Precise content (exact number of enemy types, upgrades, boss phases, power-ups)
- Meta-loop and emotional arc of a session
- Specific mechanics requested: {prompt_original}

=== TECHNICAL PROMPT ===
10-12 lines covering:
- Key objects/arrays and their structure
- Variable names for the dev console (player, enemies, bullets, score, wave)
- Genre-specific code patterns and critical implementation points

End your response after the technical prompt. Use === TECHNICAL PROMPT === as the only separator."""

    text_response = call_gemini(
        text_prompt,
        temperature=0.5,
        system_instruction=SYSTEM_TEXT,
        max_tokens=6000,
        disable_thinking=True,
    )

    separator = "=== TECHNICAL PROMPT ==="
    if separator in text_response:
        parts = text_response.split(separator, 1)
        prompt_enrichi = parts[0].replace("=== GAME DESIGNER PROMPT ===", "").strip()
        prompt_technique = parts[1].strip()
    else:
        prompt_enrichi = text_response.strip()
        prompt_technique = ""

    result["prompt_enrichi"] = prompt_enrichi
    result["prompt_technique"] = prompt_technique
    return result

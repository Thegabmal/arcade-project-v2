"""
Enricher Agent — Phase 1
Combines classification and research to produce:
- A complete GenreProfile with adaptive evaluation criteria
- An ultra-detailed prompt for the Game Designer
- A technical prompt for the Creator
This is the most important agent in Phase 1.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import Classification, Research, GenreProfile
from logger import phase1_log

SYSTEM = """You are a game design expert capable of transforming a simple request
into a complete creative and technical vision. You produce ultra-detailed prompts
that provide all the material needed to create an excellent game.
You respond ONLY in valid JSON."""


def run(prompt_original: str, classification: Classification, research: Research) -> GenreProfile:
    phase1_log.agent_start("Enrichisseur", "Génération du GenreProfile complet")

    # Construire le contexte
    refs_str = "\n".join([
        f"  - {r['nom']}: {r.get('points_forts', '')}"
        for r in research.jeux_reference
    ])

    prompt = f"""Tu dois créer un GenreProfile complet pour guider la génération d'un jeu HTML5 de qualité professionnelle.

DEMANDE ORIGINALE : "{prompt_original}"

CLASSIFICATION :
- Genre : {classification.genre_principal}
- Sous-genre : {classification.sous_genre}
- Ton : {classification.ton}
- Public : {classification.public_cible}
- Style visuel : {classification.style_visuel_attendu}
- Type gameplay : {classification.type_gameplay}

RECHERCHE :
- Mécaniques populaires : {json.dumps(research.mecaniques_populaires, ensure_ascii=False)}
- Mécaniques tendance : {json.dumps(research.mecaniques_tendance, ensure_ascii=False)}
- Core loop typique : {research.core_loop_typique}
- Progression typique : {research.progression_typique}
- Pièges à éviter : {json.dumps(research.pieges_courants, ensure_ascii=False)}
- Standards visuels : {json.dumps(research.standards_visuels, ensure_ascii=False)}
- Notes techniques : {research.notes_techniques}

JEUX RÉFÉRENCE :
{refs_str}

Génère un GenreProfile COMPLET et PROFOND :

1. MÉCANIQUES : liste précise des mécaniques obligatoires, bonus et à éviter
2. STYLE VISUEL : style, palette, animations clés, effets importants
3. DESIGN : boucle core avec formule, structure progression, courbe difficulté NUMÉRIQUE
4. CRITÈRES QC TECHNIQUE : 6-8 critères avec poids (SOMME EXACTE = 10.0) spécifiques à ce genre
5. CRITÈRES QC GAMEPLAY : 6-8 critères avec poids (SOMME EXACTE = 10.0) — incluant profondeur et variété
6. CRITÈRES QC VISUEL : 4-6 critères avec poids (SOMME EXACTE = 10.0) spécifiques à ce genre
7. PROMPT ENRICHI : 30-40 lignes pour le Game Designer incluant :
   - Les systèmes interconnectés et leurs interactions clés
   - Les formules numériques (dégâts, économie, spawn, progression)
   - Le contenu précis (nb types ennemis, upgrades, boss phases)
   - La meta-loop et l'arc émotionnel d'une session
8. PROMPT TECHNIQUE : 15-20 lignes pour le Créateur avec :
   - Architecture (objets, arrays, fonctions clés)
   - Noms de variables pour la dev console
   - Patterns de code spécifiques au genre
   - Points critiques d'implémentation

RÈGLES CRITÈRES QC :
- Les poids doivent sommer EXACTEMENT à 10.0
- Chaque critère doit être vérifiable dans le code source
- Les critères GAMEPLAY doivent inclure : variété ennemis, profondeur systèmes, meta-loop
- Les critères sont SPÉCIFIQUES au genre

Pour les critères QC, utilise ce format :
{{"nom": "...", "description": "...", "poids": 1.5, "comment_verifier": "présence dans le code de..."}}

Réponds en JSON :
{{
  "mecaniques_obligatoires": ["...", "..."],
  "mecaniques_bonus": ["...", "..."],
  "mecaniques_a_eviter": ["...", "..."],
  "style_visuel": "...",
  "palette_recommandee": "...",
  "animations_cles": ["...", "..."],
  "effets_importants": ["...", "..."],
  "boucle_core": "description complète incluant les interactions entre systèmes",
  "structure_progression": "description numérique : paliers, timings, déblocages",
  "courbe_difficulte": "description avec valeurs : '×1.0 à t=0, ×1.5 à t=60s, ×2.5 à t=120s'",
  "criteres_qc_technique": [
    {{"nom": "...", "description": "...", "poids": 1.5, "comment_verifier": "..."}}
  ],
  "criteres_qc_gameplay": [
    {{"nom": "Variété ennemis", "description": "Au moins 3 types d'ennemis distincts implémentés", "poids": 2.0, "comment_verifier": "présence de 3+ types dans ENEMY_DEFS ou équivalent"}},
    {{"nom": "...", "description": "...", "poids": 1.5, "comment_verifier": "..."}}
  ],
  "criteres_qc_visuel": [
    {{"nom": "...", "description": "...", "poids": 2.0, "comment_verifier": "..."}}
  ],
  "prompt_enrichi": "Prompt détaillé (40-60 lignes) pour le Game Designer incluant systèmes, formules, contenu précis, meta-loop, arc de session",
  "prompt_technique": "Prompt technique (20-25 lignes) pour le Créateur avec architecture, noms de variables, patterns spécifiques"
}}"""

    result = _call(prompt)

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

    # G1 : Validation GenreProfile post-génération
    _poids_total = sum(
        c.get("poids", 0) for c in (
            genre_profile.criteres_qc_technique +
            genre_profile.criteres_qc_gameplay +
            genre_profile.criteres_qc_visuel
        )
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
def _call(prompt: str) -> dict:
    # D4 : thinking activé pour l'enrichisseur (clé payante) — raisonnement profond pour le GenreProfile
    return call_gemini_json(prompt, temperature=0.5, system_instruction=SYSTEM, max_tokens=32000, disable_thinking=False)

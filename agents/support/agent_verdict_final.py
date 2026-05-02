"""
Final Verdict Agent — Support
Merges agent_benchmark + agent_neutre into a single call.

Combines:
  - Comparison against genre standards (benchmark)
  - Final approval verdict (neutral)

Advantage: one call instead of two, coherent verdict without possible contradiction
between the benchmark and the neutral agent (which sometimes disagreed).

Retourne {"evaluation": EvaluationResult, "verdict": dict}
- evaluation : EvaluationResult pour bundle.benchmark (score de comparaison genre)
- verdict : dict compatible avec agent_neutre (approuve, justification, etc.)
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, EvaluationResult, EvaluationBundle
from logger import support_log

SYSTEM = """Tu es un évaluateur expert indépendant de jeux HTML5.
Tu combines une comparaison aux standards du genre ET un verdict d'approbation final.
Tu es objectif, équilibré et constructif. Un jeu moyen reçoit un score moyen.
Tu réponds UNIQUEMENT en JSON valide."""

SEUIL_APPROBATION = 7.0  # Score minimum pour approuver (relevé depuis 6.5 — pipeline améliorée, démo Arcade AI)


def run(genre_profile: GenreProfile, gdd: dict, bundle: EvaluationBundle) -> dict:
    """
    Retourne {"evaluation": EvaluationResult, "verdict": dict}.
    - evaluation : score de benchmark (0-10) → va dans bundle.benchmark
    - verdict : dict d'approbation (approuve, justification, recommandation, etc.)
    """
    support_log.agent_start("Verdict Final", "Benchmark + Approbation")

    score_global = bundle.score_global()
    all_issues = bundle.all_issues()
    critiques = [i for i in all_issues if i.get("severite") == "critique"]
    has_blocking = bundle.has_blocking_issues()

    scores_detail = {
        "technique": bundle.qc_technique.score,
        "gameplay": bundle.qc_gameplay.score,
        "visuel": bundle.qc_visuel.score,
        "execution": bundle.execution.score,
        "playtester": bundle.playtester.score,
        "anti_pattern": bundle.anti_pattern.score,
    }

    points_forts_all = (
        bundle.qc_technique.points_forts[:2] +
        bundle.qc_gameplay.points_forts[:2] +
        bundle.qc_visuel.points_forts[:2]
    )

    prompt = f"""Évalue ce jeu HTML5 : compare-le aux standards du genre ET donne un verdict d'approbation.

JEU :
- Titre : {gdd.get("titre", "?")}
- Genre : {genre_profile.genre_principal} / {genre_profile.sous_genre}
- Concept : {gdd.get("concept", "")[:200]}
- Références du genre : {", ".join(genre_profile.jeux_reference[:5])}

SCORES OBTENUS (sur 10 chacun) :
{json.dumps(scores_detail, ensure_ascii=False)}
SCORE GLOBAL CALCULÉ : {score_global:.2f}/10

ISSUES CRITIQUES DÉTECTÉES : {len(critiques)}
{json.dumps(critiques[:3], ensure_ascii=False)}

POINTS FORTS :
{json.dumps(points_forts_all[:6], ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIE 1 — BENCHMARK GENRE ET DÉMO PROFESSIONNELLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RUBRIQUE DE BENCHMARK :
- 0-4 : Insuffisant — ne mérite pas d'être présenté
- 5-6 : Passable — acceptable en prototype mais pas en démo professionnelle
- 7-8 : Bon — présentable, répond aux attentes du genre
- 9-10 : Excellent — impressionne, digne d'une démo Arcade AI

Par rapport aux meilleurs jeux HTML5 du genre {genre_profile.genre_principal} :
1. Où se situe ce jeu sur la grille ci-dessus ?
2. Ce jeu serait-il PRÉSENTABLE dans une démo professionnelle (Arcade AI) ? Pourquoi ?
3. Qu'est-ce qui manque CONCRÈTEMENT pour atteindre le niveau 8/10 du genre ?
   (exemples : boss avec phases, combo system, 3+ types d'ennemis, power-ups, progression joueur)
4. Quels sont ses atouts distinctifs ?
5. Sa richesse de contenu est-elle adaptée aux contraintes HTML5 (fichier unique) ?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIE 2 — VERDICT D'APPROBATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Seuil d'approbation : score global ≥ {SEUIL_APPROBATION} ET aucune issue critique bloquante.
Issues bloquantes présentes : {"OUI" if has_blocking else "NON"}

Donne un verdict honnête et constructif :
- Le jeu est-il approuvé (jouable, présentable) ?
- Quel est son niveau de qualité ?
- Quelle est la recommandation principale ?

Réponds en JSON :
{{
  "benchmark": {{
    "score": 7.5,
    "niveau": "insuffisant / passable / bon / excellent",
    "presentable_demo": true,
    "raison_presentabilite": "Pourquoi ce jeu est (ou n'est pas) présentable en démo Arcade AI",
    "comparaison_genre": "Par rapport aux standards du genre...",
    "manque_pour_excellence": ["boss avec phases", "combo system", "..."],
    "atouts_distinctifs": ["...", "..."],
    "corrections_prioritaires": [
      {{"priorite": 1, "correction": "ajout boss 3 phases", "impact": "+1.5 pts gameplay"}}
    ]
  }},
  "verdict": {{
    "approuve": true,
    "score_final": {score_global:.1f},
    "niveau_qualite": "insuffisant / passable / bon / excellent",
    "justification": "Explication du verdict en 2-3 phrases précises et concrètes",
    "points_forts": ["...", "..."],
    "points_faibles": ["...", "..."],
    "recommandation": "Prêt pour démo Arcade AI / Améliorations mineures suffisantes / Corrections majeures nécessaires / À refaire"
  }}
}}"""

    result = _call(prompt)
    return _parse(result, score_global, has_blocking)


def _parse(result: dict, score_global: float, has_blocking: bool) -> dict:
    """Parse le résultat et retourne {"evaluation": EvaluationResult, "verdict": dict}."""

    # ── Benchmark → EvaluationResult ──
    bm = result.get("benchmark", {})
    ev = EvaluationResult(agent_name="Benchmark")
    ev.score = float(bm.get("score", score_global))
    ev.score = max(0.0, min(10.0, ev.score))
    ev.points_forts = bm.get("atouts_distinctifs", [])
    ev.commentaire_global = bm.get("comparaison_genre", "")

    corrections = bm.get("corrections_prioritaires", [])
    ev.issues = [
        {
            "severite": "majeur" if i == 0 else "mineur",
            "description": c.get("correction", ""),
            "suggestion": c.get("impact", "")
        }
        for i, c in enumerate(corrections)
    ]

    niveau_bm = bm.get("niveau", "?")
    support_log.score("Benchmark", ev.score)
    support_log.info(f"Niveau genre : {niveau_bm} | Adapté HTML5 : {bm.get('adapte_contraintes_html5', '?')}")

    # ── Verdict → dict ──
    vd_raw = result.get("verdict", {})
    # La source de vérité reste le score calculé — le LLM ne peut approuver
    # que si le score est proche du seuil (marge de 0.5), pas si clairement insuffisant
    approuve_par_score = score_global >= SEUIL_APPROBATION and not has_blocking
    approuve_llm = vd_raw.get("approuve", approuve_par_score)
    # LLM approval uniquement si score suffisamment proche du seuil (évite les faux positifs)
    approuve = approuve_par_score or (approuve_llm and score_global >= SEUIL_APPROBATION - 0.5 and not has_blocking)

    verdict = {
        "approuve": approuve,
        "score_final": score_global,
        "niveau_qualite": vd_raw.get("niveau_qualite", niveau_bm),
        "justification": vd_raw.get("justification", ""),
        "points_forts": vd_raw.get("points_forts", ev.points_forts),
        "points_faibles": vd_raw.get("points_faibles", []),
        "recommandation": vd_raw.get("recommandation", ""),
    }

    if approuve:
        support_log.success(f"APPROUVÉ — {verdict['niveau_qualite']} ({score_global:.1f}/10)")
    else:
        support_log.warning(
            f"NON APPROUVÉ — {verdict['niveau_qualite']} ({score_global:.1f}/10) : "
            f"{verdict['justification'][:80]}"
        )

    return {"evaluation": ev, "verdict": verdict}


@with_fallback({
    "benchmark": {
        "score": 5.0,
        "niveau": "passable",
        "comparaison_genre": "Analyse non disponible",
        "manque_pour_excellence": [],
        "atouts_distinctifs": [],
        "adapte_contraintes_html5": True,
        "corrections_prioritaires": [],
    },
    "verdict": {
        "approuve": False,
        "score_final": 5.0,
        "niveau_qualite": "passable",
        "justification": "Verdict automatique par défaut",
        "points_forts": [],
        "points_faibles": [],
        "recommandation": "Nécessite des améliorations",
    }
})
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.2, system_instruction=SYSTEM, max_tokens=12000)

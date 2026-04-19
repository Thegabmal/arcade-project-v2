"""
Agent Intelligence Genre — Phase 1
Fusion de agent_chercheur + agent_veilleur en un seul appel API.

Produit en une requête :
  - Research structurée (mécaniques, références, pièges, standards, notes techniques)
  - Document Tendances texte (ce qui cartonne, core loop gagnant, ce qui est daté)

Avantage vs les deux agents séparés :
  - 1 appel API au lieu de 2 (économie de 6s sur le rate limiter)
  - Analyse plus cohérente : tendances et mécaniques viennent de la même source
  - Jeux de référence enrichis avec mecanique_signature utilisée dans le doc tendances
"""

from config import call_gemini_json, with_fallback
from genre_profile import Classification, Research
from logger import phase1_log
import rag

SYSTEM = """Tu es un expert en game design, game studies et tendances du marché du jeu vidéo.
Tu combines analyse structurée et veille marché pour donner une base de connaissance complète.
Tu connais les mécaniques fondamentales de chaque genre ET ce qui est populaire aujourd'hui.
Tu réponds UNIQUEMENT en JSON valide."""


def run(classification: Classification) -> tuple[Research, str]:
    """
    Analyse le genre et retourne (Research, tendances_text).
    - Research : données structurées pour l'Enrichisseur
    - tendances_text : document formaté injecté dans le Créateur
    """
    phase1_log.agent_start(
        "Intelligence Genre",
        f"Analyse {classification.genre_principal} / {classification.sous_genre}"
    )

    # Enrichissement via mechanics_kb (ChromaDB RAG) — fallback silencieux
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
        "Intelligence Genre",
        f"{len(research.mecaniques_populaires)} mécaniques, "
        f"{len(research.jeux_reference)} références, "
        f"{len(tendances_text)} chars tendances"
    )
    return research, tendances_text


def _build_tendances_text(result: dict, classification: Classification) -> str:
    """Construit le document tendances à partir des champs JSON retournés."""
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

    return f"""=== INTELLIGENCE GENRE : {genre} ===

JEUX RÉFÉRENCE ACTUELS :{jeux_section}

MÉCANIQUES QUI CARTONNENT EN CE MOMENT :
{mecaniques}

CORE LOOP GAGNANT :
{result.get("core_loop_typique", "")}

PATTERNS DE PROGRESSION :
{result.get("progression_typique", "")}

CE QUI EST DATÉ / À ÉVITER :
{dates}

RECETTE SUCCÈS POUR UN JEU HTML5 :
{recette}

NOTES TECHNIQUES :
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
        f"=== TENDANCES {classification.genre_principal.upper()} ===\n"
        f"Analyse non disponible — utiliser les standards généraux du genre.\n"
        f"ESSENTIELS : core loop clair, feedback immédiat, progression visible, rejouabilité."
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
    # Construire le bloc de référence mechanics_kb si disponible
    mechanics_context = ""
    if mechanics_refs:
        lines = []
        for ref in mechanics_refs:
            name = ref.get("game_name", "?")
            doc = ref.get("document", "")
            # Extraire les 3 premières lignes du document pour rester concis
            short = "\n".join(doc.splitlines()[:6]) if doc else ""
            lines.append(f"--- {name} ---\n{short}")
        mechanics_context = (
            "\n\n=== RÉFÉRENCES MÉCANIQUES (base de connaissance interne) ===\n"
            + "\n\n".join(lines)
            + "\n=== FIN RÉFÉRENCES ===\n"
        )

    prompt = f"""Analyse experte complète du genre de jeu suivant pour guider la création d'un jeu HTML5.

GENRE : {classification.genre_principal}
SOUS-GENRE : {classification.sous_genre}
TON : {classification.ton}
PUBLIC : {classification.public_cible}
STYLE VISUEL ATTENDU : {classification.style_visuel_attendu}
TYPE GAMEPLAY : {classification.type_gameplay}

Fournis une analyse en deux parties :

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIE 1 — ANALYSE STRUCTURÉE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. MÉCANIQUES POPULAIRES (5-8) : mécaniques fondamentales qui définissent ce genre aujourd'hui
2. MÉCANIQUES TENDANCE (3-5) : ce qui est moderne et excitant dans ce genre actuellement
3. JEUX RÉFÉRENCE (5-7) : les incontournables avec leur point fort ET leur mécanique signature unique
4. PIÈGES COURANTS (4-6) : erreurs typiques qui ruinent les jeux de ce genre
5. STANDARDS VISUELS : ce que les joueurs attendent visuellement pour ce genre
6. TECHNIQUES RECOMMANDÉES : approches JS/Canvas spécifiques à ce genre
7. CORE LOOP : la boucle de gameplay fondamentale en une phrase ACTION → RÉCOMPENSE → TENSION
8. PROGRESSION : comment ce genre structure la montée en difficulté
9. NOTES TECHNIQUES : spécificités HTML5 Canvas pour implémenter ce genre

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIE 2 — TENDANCES & RECETTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. CE QUI EST DATÉ / À ÉVITER (4-5) : patterns qui font paraître le jeu vieux ou amateur
11. RECETTE SUCCÈS HTML5 (4-5) : recommandations concrètes pour maximiser la qualité perçue
    en tenant compte des contraintes HTML5 (pas d'assets externes, code unique, pas de son natif)

Réponds en JSON :
{{
  "mecaniques_populaires": ["mécanique 1", "mécanique 2"],
  "mecaniques_tendance": ["tendance 1", "tendance 2"],
  "jeux_reference": [
    {{"nom": "...", "points_forts": "pourquoi il est populaire", "mecanique_signature": "ce qui le rend unique"}}
  ],
  "pieges_courants": ["piège 1", "piège 2"],
  "standards_visuels": ["standard 1", "standard 2"],
  "techniques_recommandees": ["technique 1", "technique 2"],
  "core_loop_typique": "ACTION → RÉCOMPENSE → TENSION → ACTION",
  "progression_typique": "comment la difficulté évolue dans ce genre",
  "notes_techniques": "spécificités techniques importantes pour HTML5/Canvas/JS",
  "ce_qui_est_date": ["pattern daté 1", "pattern daté 2"],
  "recette_succes_html5": ["recommandation 1", "recommandation 2"]
}}"""

    return call_gemini_json(prompt, temperature=0.4, system_instruction=SYSTEM, max_tokens=16000)

"""
Agent Narrator — Phase 2 (optional, activated when is_narrative=True)
Generates the complete narrative context: 3-act story, quests, characters, dialogues.
This context is injected into the creator's prompt to produce a game with a real story.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, NarrativeContext
from logger import phase2_log

SYSTEM = """Tu es un scénariste de jeux vidéo expert, spécialisé dans les histoires interactives.
Tu conçois des narrations efficaces pour des jeux HTML5 — courtes, mémorables, jouables.

PRINCIPES CLÉS :
1. ÉCONOMIE NARRATIVE : une histoire de jeu doit se raconter en 10-15 minutes de jeu. Pas de roman.
2. AGENCY DU JOUEUR : chaque quête doit offrir au moins 1 choix qui change le déroulement.
3. PERSONNAGES DISTINCTIFS : 3-5 personnages max, chacun avec 1 trait fort et 1 motivation claire.
4. DIALOGUES COURTS : maximum 3 répliques par échange. Le joueur veut jouer, pas lire.
5. RÉCOMPENSES NARRATIVES : chaque acte doit débloquer quelque chose (zone, compétence, révélation).

STRUCTURE OBLIGATOIRE :
- Acte 1 (25%) : introduction du héros + problème immédiat + 1ère quête
- Acte 2 (50%) : complications + révélation du vrai ennemi + quêtes secondaires
- Acte 3 (25%) : confrontation finale + résolution + épilogue selon les choix du joueur

DIALOGUES : écrire des dialogues réels, pas des descriptions. Le créateur les copiera tels quels dans le code.

Tu réponds UNIQUEMENT en JSON valide."""


def run(genre_profile: GenreProfile) -> NarrativeContext:
    phase2_log.agent_start("Scénariste", f"Création narrative pour {genre_profile.genre_principal}")

    result = _call(genre_profile)

    narrative = NarrativeContext(
        titre=result.get("titre", ""),
        synopsis=result.get("synopsis", ""),
        acte1=result.get("acte1", ""),
        acte2=result.get("acte2", ""),
        acte3=result.get("acte3", ""),
        personnages=result.get("personnages", []),
        quetes=result.get("quetes", []),
        dialogues=result.get("dialogues", []),
        lore=result.get("lore", ""),
        ton_narratif=result.get("ton_narratif", ""),
    )

    phase2_log.agent_done(
        "Scénariste",
        f"Histoire : {narrative.titre} | {len(narrative.quetes)} quête(s) | {len(narrative.personnages)} perso(s)"
    )
    return narrative


@with_fallback({
    "titre": "La Quête Oubliée",
    "synopsis": "Un héros découvre un artefact ancien qui bouleverse l'équilibre du monde.",
    "acte1": "Le héros trouve l'artefact dans son village natal, maintenant en ruines.",
    "acte2": "La guilde des Ombres veut l'artefact. Le vrai ennemi est un ancien allié.",
    "acte3": "Confrontation finale dans la Tour des Anciens. Choix : détruire ou conserver l'artefact.",
    "personnages": [
        {"nom": "Kael", "role": "Héros", "motivation": "Venger son village", "description": "Guerrier solitaire au passé mystérieux"},
        {"nom": "Lyra", "role": "Alliée", "motivation": "Protéger les secrets anciens", "description": "Archiviste de la guilde des Sages"},
        {"nom": "Mordran", "role": "Antagoniste", "motivation": "Pouvoir absolu via l'artefact", "description": "Ancien mentor du héros, corrompu par l'ambition"}
    ],
    "quetes": [
        {"nom": "Les Ruines du Village", "objectif": "Découvrir ce qui s'est passé", "recompense": "Artefact + 50 XP", "dialogue_intro": "Kael : 'Mon village... réduit à cendres. Quelqu'un doit payer.'"},
        {"nom": "La Guilde des Ombres", "objectif": "Infiltrer le repaire ennemi", "recompense": "Clé de la Tour + 100 XP", "dialogue_intro": "Lyra : 'Je sais où ils se cachent. Mais le chemin est dangereux.'"},
        {"nom": "La Vérité sur Mordran", "objectif": "Affronter l'ancien mentor", "recompense": "Fin de l'histoire", "dialogue_intro": "Mordran : 'Tu ne comprends pas encore. L'artefact est MA destinée.'"}
    ],
    "dialogues": [
        {
            "perso": "Lyra",
            "texte": "L'artefact est plus ancien que notre guilde. Seul son porteur légitime peut le contrôler.",
            "choix": [
                {"texte": "Je suis prêt à le porter.", "consequence": "Lyra rejoint le groupe (+stats)"},
                {"texte": "Je préfère le détruire.", "consequence": "Lyra part, mais donne une carte secrète"}
            ]
        }
    ],
    "lore": "Il y a 500 ans, les Anciens ont fragmenté l'artefact pour éviter qu'un seul être ne détienne tout le pouvoir. Mordran a passé 30 ans à en rassembler les fragments.",
    "ton_narratif": "épique et sombre, avec quelques moments de légèreté"
})
def _call(genre_profile: GenreProfile) -> dict:
    prompt_context = f"""Genre : {genre_profile.genre_principal} / {genre_profile.sous_genre}
Ton attendu : {genre_profile.ton}
Mécanique principale : {genre_profile.boucle_core}
Prompt original : {genre_profile.prompt_utilisateur_original}
Style visuel : {genre_profile.style_visuel}"""

    return call_gemini_json(f"""Tu dois créer le contexte narratif complet pour un jeu vidéo HTML5.

CONTEXTE DU JEU :
{prompt_context}

CONTRAINTES TECHNIQUES :
- Les dialogues seront affichés dans une interface HTML5 Canvas 2D
- Maximum 80 caractères par ligne de dialogue (affichage limité)
- Les noms de quêtes seront utilisés comme identifiants JS (sans accents ni espaces si possible)
- Maximum 5 personnages, 5 quêtes, 3 échanges de dialogues

Génère le contexte narratif complet en JSON :
{{
  "titre": "titre du jeu (court, mémorable)",
  "synopsis": "résumé en 2-3 phrases percutantes",
  "acte1": "description de l'acte 1 (100 mots max) — introduction + premier enjeu",
  "acte2": "description de l'acte 2 (100 mots max) — complications + révélations",
  "acte3": "description de l'acte 3 (80 mots max) — confrontation finale + résolutions multiples",
  "lore": "contexte du monde en 3-4 phrases",
  "ton_narratif": "ex: épique, humoristique, sombre, mystérieux, ...",
  "personnages": [
    {{
      "nom": "Nom du personnage",
      "role": "Héros | Alliée | Antagoniste | Marchand | Guide",
      "motivation": "en une phrase",
      "description": "en une phrase",
      "stats_jeu": "ex: ATK:15 DEF:8 — ce personnage peut avoir des stats dans le jeu"
    }}
  ],
  "quetes": [
    {{
      "id": "quete_nom_sans_espaces",
      "nom": "Nom de la quête",
      "objectif": "description courte de l'objectif",
      "recompense": "ex: 50 pièces d'or, +10 ATK, nouvelle zone débloquée",
      "dialogue_intro": "Perso : 'texte du dialogue d'introduction à la quête'",
      "conditions_succes": "ex: tuer 5 ennemis, trouver l'objet X, parler au PNJ Y"
    }}
  ],
  "dialogues": [
    {{
      "id": "dialogue_nom",
      "perso": "Nom du personnage qui parle",
      "texte": "Texte principal (max 80 caractères)",
      "choix": [
        {{"texte": "Option 1 (max 40 chars)", "consequence": "description de la conséquence"}},
        {{"texte": "Option 2 (max 40 chars)", "consequence": "description de la conséquence"}}
      ]
    }}
  ]
}}""", temperature=0.7, max_tokens=4000)

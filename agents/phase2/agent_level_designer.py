"""
Agent Level Designer — Phase 2
Conçoit le contenu réel : vagues précises, rooms, events, courbe de difficulté fine.
Objectif : fournir au Créateur un "script de jeu" détaillé, pas des vœux pieux.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile
from logger import phase2_log

SYSTEM = """Tu es un Level Designer expert dont le rôle est de transformer un GDD en CONTENU JOUABLE CONCRET.

━━━ TON RÔLE ━━━
Tu ne décris pas des ambiances. Tu spécifies du CONTENU RÉEL :
- Vague 3 = 6 Grunts, 2 Tanks, spawn toutes les 1.2s depuis la gauche
- Room 2 = 4 gardes patrouille + 1 archer en hauteur + coffre verrouillé clé rouge
- Palier t=90s = vitesse +35%, nouveau type Shooter introduit, fréquence 900ms

━━━ RÈGLES DE CONTENU ━━━
1. VALEURS NUMÉRIQUES PRÉCISES (pas "rapide" ou "beaucoup") :
   - Fréquences en ms : 1200ms, pas "fréquent"
   - Vitesses en px/s ou multiplicateurs : 120px/s, pas "rapide"
   - HP, dégâts, coûts : nombres entiers précis

2. MINIMUM 6 PALIERS DE DIFFICULTÉ (pas 3 comme d'habitude) :
   t=0s, t=20s, t=45s, t=80s, t=120s, t=180s+
   Chaque palier = changement mesurable sur au minimum 2 paramètres

3. CONTENU GENRE-SPÉCIFIQUE :
   - SHOOTER/ACTION  : compositions de vagues précises, patterns de formation
   - RPG/DUNGEON     : layouts de rooms, contenu de chaque room, types d'ennemis par zone
   - TOWER DEFENSE   : chemins, compositions vagues numérotées, boss toutes les 5 vagues
   - PLATFORMER      : liste d'obstacles par niveau, positions approximatives, secrets
   - BASE BUILDER    : vagues d'attaque avec timing et composition exacte

4. EVENTS PLANIFIÉS (au moins 3 événements spéciaux en jeu) :
   Déclencheurs : temps, score, kill count, vague numéro

5. ANTI-FRUSTRATION OBLIGATOIRE :
   - Respawn window ou checkpoint après chaque zone difficile
   - Power-up garanti si HP < 20%
   - Reprise accessible après game over (pas recommencer depuis 0 sans progression)

6. REWARD PACING — LE JOUEUR DOIT RECEVOIR UNE RÉCOMPENSE TOUTES LES 45s MAXIMUM :
   - t=0-45s   : premier power-up ou loot garanti
   - t=45-90s  : level up ou upgrade débloqué ou boss mini
   - t=90-150s : événement spécial + récompense rare
   - t=150s+   : cycle accéléré, récompenses plus fréquentes
   Aucune "zone sèche" > 45s sans feedback positif → le joueur décroche

7. ACCÉLÉRATION OBLIGATOIRE APRÈS 5 MINUTES :
   - t=300s : vitesse ennemis ×1.4, spawn rate ×1.6, nouveau type d'ennemi élite
   - t=420s : boss intermédiaire ou événement "horde" (×3 ennemis pendant 15s)
   - t=540s+ : mode "frénésie" — tout s'emballe, le joueur en difficulté = tension max
   Sans cette accélération, le joueur compétent s'ennuie et arrête.

8. SURPRISE MECHANICS (maintenir la tension entre les vagues) :
   - 1 événement déclenché par seuil (score, kill count, ou temps fixe) : horde, buff temporaire
   - Drop rare (5% chance) : power-up transformant limité dans le temps (×2 dégâts pendant 15s)
   - Variation de composition : alterner vagues légères et lourdes (jamais 3 vagues identiques de suite)

Tu réponds UNIQUEMENT en JSON valide."""


def run(genre_profile: GenreProfile, gdd: dict, tech_specs: dict) -> dict:
    phase2_log.agent_start("Level Designer", f"Progression pour {genre_profile.genre_principal}")

    genre         = (genre_profile.genre_principal or "").lower()
    progression   = gdd.get("progression", {})
    systemes      = gdd.get("systemes_principaux", [])
    ennemis       = gdd.get("ennemis_ou_obstacles", [])
    contenu       = gdd.get("contenu_detaille", {})
    formules      = gdd.get("formules_cles", {})
    ennemis_stats = contenu.get("ennemis_stats", ennemis)

    # Section de contenu spécifique au genre
    genre_section = _genre_content_section(genre, gdd)

    prompt = f"""Conçois le contenu détaillé et la progression complète de ce jeu.
Tu dois fournir un "script de jeu" que le Créateur peut implémenter directement.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Genre    : {genre_profile.genre_principal} / {genre_profile.sous_genre}
Titre    : {gdd.get('titre', '?')}
Concept  : {gdd.get('concept', '')}
Core loop: {gdd.get('core_loop', {}).get('description', '')}
Progression GDD : {progression.get('type', '?')} — {progression.get('structure', '')}
Courbe   : {genre_profile.courbe_difficulte}

SYSTÈMES DISPONIBLES :
{json.dumps(systemes, ensure_ascii=False, indent=2)}

ENTITÉS/ENNEMIS DISPONIBLES (avec stats) :
{json.dumps(ennemis_stats, ensure_ascii=False, indent=2)}

FORMULES DÉJÀ DÉFINIES :
{json.dumps(formules, ensure_ascii=False, indent=2)}

PHYSIQUE :
- Gravité : {tech_specs.get('physique', {}).get('gravite', False)}
- Collisions : {tech_specs.get('physique', {}).get('collisions', 'AABB')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXIGENCES SPÉCIFIQUES AU GENRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{genre_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT JSON ATTENDU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Réponds en JSON :
{{
  "type_progression": "endless / niveaux / phases / monde ouvert",

  "introduction": {{
    "duree": "0-20s",
    "objectif_pedagogique": "Le joueur apprend X implicitement en faisant Y",
    "mecaniques_introduites": ["déplacement", "attaque basique"],
    "premier_ennemi_a": "t=5s",
    "premiere_mort_possible_a": "t=15s"
  }},

  "paliers_difficulte": [
    {{
      "id": 1, "declencheur": "t=0s",
      "vitesse_ennemis": 70, "frequence_spawn_ms": 2000, "hp_ennemis_mult": 1.0,
      "types_actifs": ["grunt"], "nb_ennemis_max_ecran": 4,
      "description": "Initiation — 1 seul type, rythme lent"
    }},
    {{
      "id": 2, "declencheur": "t=25s ou score=300",
      "vitesse_ennemis": 85, "frequence_spawn_ms": 1600, "hp_ennemis_mult": 1.15,
      "types_actifs": ["grunt", "fast"], "nb_ennemis_max_ecran": 6,
      "description": "Introduction du type rapide — joueur doit adapter"
    }},
    {{
      "id": 3, "declencheur": "t=55s ou score=700",
      "vitesse_ennemis": 100, "frequence_spawn_ms": 1300, "hp_ennemis_mult": 1.35,
      "types_actifs": ["grunt", "fast", "tank"], "nb_ennemis_max_ecran": 8,
      "description": "Tank introduit — nécessite stratégie de ciblage"
    }},
    {{
      "id": 4, "declencheur": "t=90s ou score=1500",
      "vitesse_ennemis": 115, "frequence_spawn_ms": 1050, "hp_ennemis_mult": 1.60,
      "types_actifs": ["grunt", "fast", "tank", "shooter"], "nb_ennemis_max_ecran": 10,
      "description": "Shooter introduit — pression depuis la distance"
    }},
    {{
      "id": 5, "declencheur": "t=130s ou score=2500",
      "vitesse_ennemis": 130, "frequence_spawn_ms": 850, "hp_ennemis_mult": 2.0,
      "types_actifs": ["tous"], "nb_ennemis_max_ecran": 14,
      "description": "Tous les types actifs — chaos contrôlé"
    }},
    {{
      "id": 6, "declencheur": "t=180s ou score=4000",
      "vitesse_ennemis": 160, "frequence_spawn_ms": 650, "hp_ennemis_mult": 2.8,
      "types_actifs": ["tous + elite"], "nb_ennemis_max_ecran": 18,
      "description": "Mode survie — pression maximale, légèrement injouable seul sans upgrades"
    }}
  ],

  "vagues_ou_phases": [
    {{
      "id": 1,
      "nom": "...",
      "description": "...",
      "composition": [
        {{"type": "grunt", "quantite": 5, "spawn_intervalle_ms": 1200, "direction": "gauche"}},
        {{"type": "tank",  "quantite": 1, "spawn_intervalle_ms": 0,    "direction": "droite", "delai_ms": 5000}}
      ],
      "duree_estimee": "45s",
      "recompense_completion": "power-up vitesse + 50 gold",
      "defi_principal": "...",
      "nouveautes": ["premier tank", "spawn bi-directionnel"]
    }}
  ],

  "events_planifies": [
    {{
      "id": "elite_wave",
      "declencheur": "t=60s",
      "nom": "Vague Élite",
      "description": "3 ennemis élite apparaissent simultanément — HP×3, dégâts×2",
      "recompense": "power-up rare garanti si vague survécue",
      "avertissement_visuel": "écran flash orange 2s avant"
    }},
    {{
      "id": "boss_1",
      "declencheur": "t=120s ou score=3000",
      "nom": "Boss — Nom du Boss",
      "hp": 500,
      "phases": [
        {{"phase": 1, "seuil_hp": 500, "attaque": "charge directe", "pattern": "straight line"}},
        {{"phase": 2, "seuil_hp": 250, "attaque": "invocation grunts x3", "pattern": "circle spawn"}},
        {{"phase": 3, "seuil_hp": 100, "attaque": "enrage — vitesse×2 + AOE", "pattern": "random"}}
      ],
      "recompense": "déblocage + score×3 + heal joueur"
    }},
    {{
      "id": "power_surge",
      "declencheur": "hp_joueur < 20%",
      "nom": "Dernier Recours",
      "description": "Power-up soin garanti drop depuis le prochain ennemi tué",
      "but": "anti-frustration — éviter la mort rapide injuste"
    }}
  ],

  "spawn_patterns": [
    {{
      "nom": "Ligne Frontale",
      "description": "5 ennemis spawned en ligne horizontale en haut de l'écran",
      "difficulte": "facile",
      "composition": "5× grunt, espacés de 60px",
      "frequence": "toutes les 8s en phase 1-2"
    }},
    {{
      "nom": "Double Flanc",
      "description": "2 groupes de 3 spawned simultanément à gauche ET droite",
      "difficulte": "moyen",
      "composition": "3× fast gauche + 3× fast droite",
      "frequence": "toutes les 15s à partir phase 3"
    }},
    {{
      "nom": "Embuscade",
      "description": "Tank au centre + 4 grunts qui l'encerclent autour du joueur",
      "difficulte": "difficile",
      "composition": "1× tank (centre) + 4× grunt (haut/bas/gauche/droite à 200px joueur)",
      "frequence": "1 fois par boss wave"
    }}
  ],

  "contenu_par_zone": {{genre_specific_content}},

  "courbe_difficulte": {{
    "progression": "par paliers progressifs",
    "parametres_evolutifs": [
      {{"parametre": "frequence_spawn_ms", "debut": 2000, "fin": 650,  "formule": "max(650, 2000 - t*9)"}},
      {{"parametre": "vitesse_ennemis",    "debut": 70,   "fin": 160,  "formule": "70 + t * 0.5"}},
      {{"parametre": "hp_ennemis_mult",    "debut": 1.0,  "fin": 2.8,  "formule": "1 + palier * 0.35"}}
    ],
    "anti_frustration": "power-up soin garanti si hp < 20% + invincibilité 2s post-hit"
  }},

  "valeurs_initiales": {{
    "vitesse_joueur": 150,
    "vitesse_monde": 0,
    "frequence_spawn_ms": 2000,
    "vie_joueur": 100,
    "degats_joueur": 10,
    "defense_joueur": 5,
    "gravite": 0,
    "vitesse_saut": 0,
    "score_par_ennemi_grunt": 10,
    "score_par_ennemi_tank": 35,
    "score_par_boss": 200,
    "gold_par_ennemi_grunt": 8,
    "gold_par_ennemi_tank": 25
  }},

  "equilibrage": {{
    "formule_score": "score += enemy.scoreValue * comboMult where comboMult = 1 + kills_sans_hit * 0.1",
    "formule_difficulte_adaptative": "si joueur n'a pas pris de dégâts depuis 30s → accélérer spawn×1.2",
    "second_chance": "Après mort : respawn avec 30% HP + 3s invincibilité + power-up aléatoire"
  }},

  "fin_de_jeu": {{
    "conditions_victoire": "...",
    "conditions_defaite": "HP = 0",
    "message_game_over": "...",
    "meta_progression": "Highscore sauvegardé + déblocages permanents si seuils atteints"
  }}
}}"""

    # Formatter le contenu genre-spécifique dans le prompt
    prompt = prompt.replace(
        '{genre_specific_content}',
        json.dumps(_build_zone_content(genre, gdd), ensure_ascii=False)
    )

    result = _call(prompt)
    nb_paliers = len(result.get("paliers_difficulte", []))
    nb_events  = len(result.get("events_planifies", []))
    nb_vagues  = len(result.get("vagues_ou_phases", []))
    phase2_log.agent_done(
        "Level Designer",
        f"{nb_vagues} vagues, {nb_paliers} paliers, {nb_events} events — {result.get('type_progression', '?')}"
    )
    return result


def _genre_content_section(genre: str, gdd: dict) -> str:
    """Exigences de contenu spécifiques au genre détecté."""
    if any(k in genre for k in ["base", "stratégie", "strategy", "builder", "clash", "rts"]):
        return """BASE BUILDER : spécifie pour chaque vague d'attaque :
- Composition précise (ex: vague 4 = 8 grunts + 3 tanks + 1 héros)
- Chemin emprunté (gauche, droite, haut, bas, multi-chemin)
- Timing de spawn entre chaque unité (ms)
- Récompense de victoire (or, XP, déblocage de bâtiment)
Spécifie aussi les bâtiments avec leurs stats à chaque niveau (HP, DPS, coût, portée)"""

    if any(k in genre for k in ["rpg", "dungeon", "aventure", "roguelite", "rogue"]):
        return """RPG/DUNGEON : décris chaque zone/étage avec :
- Nb de rooms (3-7), type de chaque room (combat, coffre, marchand, boss, repos)
- Composition ennemis par room avec HP et comportement
- Loot possible par room (probabilités)
- Layout de la boss room (obstacles, zones de danger)
Progression : stats qui augmentent par level (HP+20%, ATK+15% par level)"""

    if any(k in genre for k in ["tower", "defense", "td", "défense"]):
        return """TOWER DEFENSE : pour chaque vague numérotée (au moins 12 vagues) :
- Composition exacte : type, quantité, HP modificateur
- Chemin(s) emprunté(s)
- Timing entre chaque ennemi (ms)
- Boss toutes les 5 vagues avec HP×10 et récompense spéciale
Pour les tours : stats complètes (dégâts/s, portée, vitesse d'attaque, coût, coût upgrade)"""

    if any(k in genre for k in ["shoot", "shmup", "shooter", "bullet"]):
        return """SHOOTER : pour chaque vague :
- Formation de spawn (ligne, V, cercle, flanc, aléatoire)
- Types, quantités et vitesses précis
- Pattern de tir des ennemis ranged (vitesse projectile, cadence)
- Position d'apparition (haut, côtés, spawns aléatoires)
Boss : 3 phases avec patterns d'attaque différents, seuils HP précis"""

    if any(k in genre for k in ["platform", "plateforme", "saut"]):
        return """PLATFORMER : pour chaque niveau :
- Types et positions approximatives des plateformes (mobiles, disparaissantes, rebondissantes)
- Types et positions des ennemis (statique, patrouille, volant)
- Position des collectibles et secrets
- Obstacle signature du niveau (hazard unique)
Longueur estimée de chaque niveau et checkpoint position"""

    return """CONTENU GÉNÉRIQUE : spécifie au moins :
- 3 types d'ennemis avec comportements distincts, HP et vitesses précis
- 6 paliers de difficulté avec valeurs numériques
- 3 événements spéciaux planifiés (boss, vague élite, power-up garanti)
- Spawn patterns nommés avec compositions précises"""


def _build_zone_content(genre: str, gdd: dict) -> list:
    """Génère un contenu de zone minimal pour le JSON."""
    contenu = gdd.get("contenu_detaille", {})
    if any(k in genre for k in ["rpg", "dungeon"]):
        return [
            {"zone": "Étage 1", "rooms": 4, "types_rooms": ["combat×2", "coffre×1", "boss×1"],
             "ennemis": ["grunt×3", "archer×1"], "boss": "Elite Garde", "recompense": "loot commun + clé"},
            {"zone": "Étage 2", "rooms": 5, "types_rooms": ["combat×3", "marchand×1", "boss×1"],
             "ennemis": ["grunt×4", "mage×2"], "boss": "Golem de Pierre", "recompense": "loot rare"},
        ]
    if any(k in genre for k in ["tower", "defense"]):
        return [
            {"zone": "Chemin principal", "longueur_px": 1200, "virages": 3,
             "points_strategiques": ["entrée", "virage_1", "virage_2", "sortie"]},
        ]
    return [{"zone": "Carte principale", "description": "Zone de jeu principale"}]


@with_fallback({
    "type_progression": "endless",
    "paliers_difficulte": [
        {"id": 1, "declencheur": "t=0s",   "frequence_spawn_ms": 2000, "types_actifs": ["grunt"]},
        {"id": 2, "declencheur": "t=30s",  "frequence_spawn_ms": 1500, "types_actifs": ["grunt", "fast"]},
        {"id": 3, "declencheur": "t=60s",  "frequence_spawn_ms": 1200, "types_actifs": ["grunt", "fast", "tank"]},
        {"id": 4, "declencheur": "t=90s",  "frequence_spawn_ms": 950,  "types_actifs": ["tous"]},
        {"id": 5, "declencheur": "t=130s", "frequence_spawn_ms": 750,  "types_actifs": ["tous"]},
        {"id": 6, "declencheur": "t=180s", "frequence_spawn_ms": 600,  "types_actifs": ["tous + elite"]},
    ],
    "vagues_ou_phases": [],
    "events_planifies": [],
    "spawn_patterns": [],
    "valeurs_initiales": {"vitesse_joueur": 150, "frequence_spawn_ms": 2000, "vie_joueur": 100},
})
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.5, system_instruction=SYSTEM, max_tokens=32000)

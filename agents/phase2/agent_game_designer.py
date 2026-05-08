"""
Agent Game Designer — Phase 2
Creates a complete, deep, interconnected Game Design Document.
Goal: design a REAL GAME with content, not a 2-minute demo.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile
from logger import phase2_log

SYSTEM = """You are a senior Game Designer expert in gameplay depth.
Your mission: design games with real playable content, not 2-minute demos.

━━━ DEMO vs REAL GAME ━━━
DEMO     : 1 isolated system, 1-2 entity types, gameplay exhausted in 2 min, no "one more try"
REAL GAME: interconnected systems, progressive variety, rising tension, meta-loop that drives replay

━━━ 7 ABSOLUTE RULES OF DEPTH ━━━

RULE 1 — INTERCONNECTED SYSTEMS (minimum 3 systems that influence each other)
  Loop model: Resource → Upgrade → Stats → Combat Perf → Reward → Resource
  Each system must affect AT LEAST one other. Describe the interaction explicitly.

RULE 2 — PRECISE NUMERICAL FORMULAS (mandatory, no vague descriptions)
  Expected formula examples:
  - Damage    : dmg = Math.max(1, atk * mult - floor(def * 0.4))
  - Upgrade cost: cost = baseCost * Math.pow(1.6, level - 1)
  - XP level up : xpNeeded = 100 * Math.pow(level, 1.85)
  - Spawn rate  : interval = Math.max(400, 2000 - gameTime * 9) ms
  - Gold drop   : gold = baseGold * (1 + floor * 0.25) * rarityMult

RULE 3 — EXPLICIT META-LOOP
  Define EXACTLY why the player restarts after game over:
  options: personal score, content unlock, different build, rising challenge, leaderboard

RULE 4 — FELT PROGRESSION EVERY 2-3 MINUTES
  - New mechanic or new enemy type introduced
  - Numbers visibly increasing (level, ATK, tour count, wave number)
  - Event or mini-boss at each milestone (t=2min, t=4min, t=6min...)

RULE 5 — GUARANTEED MINIMUM VARIETY
  - 3+ DISTINCT enemy entity types (visually and behaviorally)
  - 3+ reward/power-up types with different effects
  - 2+ viable play strategies (player can win multiple ways)

RULE 6 — ECONOMIC BALANCE (avoid inflation and boredom plateau)
  - Gain/spend ratio: player must be able to buy 1 upgrade every 60-90s in normal play
  - Simple catch-up: guaranteed healing power-up in drops when HP < 25% (no history tracking)
  - Difficulty ramp after 5 min: spawn rate ×1.5, enemy HP ×1.3 — good players get bored otherwise
  - Continuous waves: always at least 1 active enemy during the "playing" phase

RULE 7 — PLAYER AGENCY (player must feel their choices matter)
  - Each upgrade must VISIBLY change gameplay (not just invisible +5% DPS)
  - At least 1 decision per session: "heal now or save for upgrade?"
  - 2 viable builds minimum: e.g. speed+low damage vs slow+high damage

━━━ PER-GENRE RULES ━━━

BASE BUILDER / STRATEGY:
  Full cycle: gather resources → build structures → defend waves → gather
  4+ building types (resource, attack, defense, support), 3 upgrade levels each
  Numbered waves with precise composition (e.g. wave 5 = 8 grunts + 2 tanks + 1 hero)
  Balanced economy: construction cost never > 60% of resources available at that moment

RPG / DUNGEON CRAWLER:
  3+ playable classes with distinct styles (warrior=tank, mage=burst, rogue=mobile)
  Loot system: common (70%), rare (25%), epic (5%) — stats +15%/+35%/+80% vs baseline
  Visible stats increasing each level: HP, ATK, DEF, SPD with formulas
  Boss per zone with 2-3 attack phases and unique pattern

TOWER DEFENSE:
  4+ towers with precise numeric ranges/damage/speed/effects
  Synergies: slowing tower × damage tower = ×1.5 effective DPS
  Economic incentive: keeping gold at end of wave = +5% next-wave bonus
  Enemy paths with tactical decision points

SHOOTER / ACTION:
  3+ weapons with different profiles (fast/weak, slow/strong, AoE)
  Elites and bosses: HP×5, unique attack pattern, special reward
  Waves with formations (line, flank, circle, ambush)
  Transformative power-ups: not just +HP, but "berserk mode 10s", "absorbing shield"

PLATFORMER:
  Full physics kit for the theme: coyote time, jump buffer, dash, wall jump if relevant
  Secrets and collectibles: 3+ per zone, unlockable with acquired skills
  Varied obstacles: moving, timed, interactive, environmental
  Thematically distinct zones with zone-specific hazard

PUZZLE:
  Irreducible, original signature mechanic
  3 phases: implicit tutorial (0-30%), rising complexity (30-70%), mastery required (70-100%)
  "Aha moments" intentionally designed at 3-4 key points
  Secondary mechanics introduced one at a time

You respond ONLY in valid JSON."""


def run(genre_profile: GenreProfile) -> dict:
    phase2_log.agent_start("Game Designer", f"GDD pour {genre_profile.genre_principal}")

    genre = (genre_profile.genre_principal or "").lower()
    mecaniques_str  = "\n".join([f"  - {m}" for m in genre_profile.mecaniques_obligatoires])
    bonus_str       = "\n".join([f"  - {m}" for m in genre_profile.mecaniques_bonus])
    eviter_str      = "\n".join([f"  - {m}" for m in genre_profile.mecaniques_a_eviter])

    # Section profondeur spécifique au genre
    depth_hint = _genre_depth_hint(genre)

    prompt = f"""Crée un Game Design Document PROFOND pour ce jeu HTML5.
Objectif : concevoir un VRAI JEU avec du contenu, pas une démo fonctionnelle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VISION DU JEU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{genre_profile.prompt_enrichi}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXTE DU GENRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Genre       : {genre_profile.genre_principal} / {genre_profile.sous_genre}
- Ton         : {genre_profile.ton} | Public : {genre_profile.public_cible}
- Boucle core : {genre_profile.boucle_core}
- Progression : {genre_profile.structure_progression}
- Difficulté  : {genre_profile.courbe_difficulte}
- Références  : {', '.join(genre_profile.jeux_reference[:5])}

MÉCANIQUES OBLIGATOIRES :
{mecaniques_str}

MÉCANIQUES BONUS :
{bonus_str}

MÉCANIQUES À ÉVITER :
{eviter_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXIGENCES DE PROFONDEUR — OBLIGATOIRES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{depth_hint}

CHECKLIST DE PROFONDEUR (à valider dans ton GDD) :
□ Au moins 3 systèmes qui s'INFLUENCENT mutuellement → décrire chaque lien dans interactions_systemes
□ Formules numériques pour : dégâts, coût upgrades, XP/level, spawn rate → section formules_cles
□ Meta-loop défini : POURQUOI recommencer après game over → section meta_loop
□ Arc de session minute par minute (que se passe-t-il à 1min, 3min, 5min ?) → session_arc
□ Stats précises de chaque type d'ennemi (HP, vitesse, dégâts, récompense) → ennemis_stats
□ 3+ upgrades avec coûts croissants et formules → upgrades_disponibles
□ 3+ power-ups avec effets distincts → non juste "+HP"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTRAINTES HTML5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Tout dans UN SEUL fichier HTML (graphismes Canvas procéduraux, pas d'assets)
- Session : 5-10 minutes (mais envie de rejouer après)
- 3-5 systèmes bien implémentés > 8 systèmes à moitié faits

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT JSON ATTENDU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Réponds en JSON :
{{
  "titre": "...",
  "tagline": "...",
  "concept": "Description en 3-4 phrases — inclure le hook et la promesse de profondeur",

  "core_loop": {{
    "description": "La boucle fondamentale en 1 phrase",
    "etapes": ["étape 1", "étape 2", "étape 3", "étape 4"],
    "duree_session": "X-Y minutes",
    "hook_immediat": "Ce qui accroche le joueur dans les 30 premières secondes"
  }},

  "systemes_principaux": [
    {{
      "nom": "...",
      "description": "Description précise avec mécaniques",
      "impact_gameplay": "Comment ça change concrètement ce que le joueur fait",
      "valeurs_cles": {{"stat1": 10, "stat2": 0.5}}
    }}
  ],

  "interactions_systemes": [
    {{
      "source": "nom_systeme_A",
      "cible": "nom_systeme_B",
      "description": "Comment A influence B concrètement",
      "exemple": "Tuer 5 ennemis → +50 gold → permet d'acheter upgrade → ATK +20%"
    }}
  ],

  "formules_cles": {{
    "degats": "dmg = Math.max(1, atk * mult - floor(def * 0.4))",
    "cout_upgrade": "cost = baseCost * Math.pow(1.6, level - 1)",
    "xp_level_up": "xpNeeded = 100 * Math.pow(level, 1.85)",
    "spawn_rate": "interval = Math.max(400, 2000 - gameTime * 9)",
    "gold_drop": "gold = baseGold * (1 + floor * 0.25)",
    "score": "score += baseScore * comboMult * levelMult"
  }},

  "meta_loop": {{
    "raison_rejouer": "Explication précise de ce qui pousse à recommencer",
    "elements_persistants": ["highscore", "déblocages", "..."],
    "hook_psychologique": "Le mécanisme émotionnel qui crée l'addiction saine",
    "session_arc": "0-1min: découverte, 1-3min: montée en puissance, 3-5min: tension max, 5min+: boss/finale"
  }},

  "contenu_detaille": {{
    "ennemis_stats": [
      {{"nom": "Grunt",  "hp": 20, "vitesse": 80,  "degats": 8,  "xp": 5,  "gold": 8,  "couleur": "#E74C3C", "comportement": "fonce vers le joueur"}},
      {{"nom": "Tank",   "hp": 90, "vitesse": 30,  "degats": 20, "xp": 15, "gold": 25, "couleur": "#8E44AD", "comportement": "lent et résistant au knockback"}},
      {{"nom": "Shooter","hp": 15, "vitesse": 40,  "degats": 10, "xp": 12, "gold": 20, "couleur": "#F39C12", "comportement": "reste à distance, tire des projectiles"}}
    ],
    "upgrades_disponibles": [
      {{"nom": "...", "effet": "ATK +20%", "cout_initial": 100, "scaling": "cost * 1.6^niveau", "niveaux_max": 5}},
      {{"nom": "...", "effet": "Vitesse +15%", "cout_initial": 80, "scaling": "cost * 1.5^niveau", "niveaux_max": 3}}
    ],
    "powerups": [
      {{"nom": "Soin",       "couleur": "#2ECC71", "duree": 0,  "effet": "restaure 30 HP"}},
      {{"nom": "Rage",       "couleur": "#E74C3C", "duree": 8,  "effet": "ATK x2 pendant 8s"}},
      {{"nom": "Bouclier",   "couleur": "#3498DB", "duree": 6,  "effet": "absorbe les 3 prochains coups"}},
      {{"nom": "Foudre",     "couleur": "#F1C40F", "duree": 0,  "effet": "tue tous les ennemis à l'écran"}}
    ],
    "boss": [
      {{
        "nom": "...",
        "hp": 500,
        "phases": [
          {{"phase": 1, "hp_seuil": 500, "comportement": "attaque directe", "pattern": "..."}},
          {{"phase": 2, "hp_seuil": 250, "comportement": "invoque des alliés", "pattern": "..."}},
          {{"phase": 3, "hp_seuil": 100, "comportement": "enrage, ATK x2, vitesse x1.5", "pattern": "..."}}
        ],
        "recompense": "power-up légendaire + score x3 + déblocage"
      }}
    ],
    "evenements_speciaux": [
      {{"declencheur": "t=2min ou score=500", "nom": "Vague Elite", "description": "...", "recompense": "..."}},
      {{"declencheur": "t=5min",              "nom": "Boss Rush",   "description": "...", "recompense": "..."}}
    ]
  }},

  "personnage_ou_entite": {{
    "description": "Le joueur contrôle quoi ?",
    "stats_initiales": {{"hp": 100, "atk": 10, "def": 5, "spd": 120}},
    "capacites": ["capacité passive", "compétence active (cooldown Xs)", "ultimate (rare)"],
    "feedback_visuel": "Comment le personnage réagit visuellement à chaque action"
  }},

  "progression": {{
    "type": "endless / niveaux / phases / monde ouvert",
    "structure": "Description de la structure",
    "deblocages": [
      {{"condition": "score > 1000", "deblocage": "nouveau type d'ennemi ou arme"}},
      {{"condition": "level 5",      "deblocage": "boss final accessible"}}
    ]
  }},

  "economie_du_jeu": {{
    "ressources": [
      {{"nom": "Gold", "gain": "8-25 par ennemi tué selon type", "depense": "upgrades et tours"}},
      {{"nom": "XP",   "gain": "5-15 par ennemi selon type", "depense": "level up automatique"}}
    ],
    "equilibre": "Description de l'équilibre gain/dépense pour éviter le déséquilibre",
    "consequences_echec": "Ce que le joueur perd et garde après un game over"
  }},

  "ennemis_ou_obstacles": [
    {{
      "nom": "...",
      "comportement": "description comportementale précise",
      "strategie_joueur": "comment le contrer efficacement",
      "introduit_a": "t=0s / score=200 / niveau 2"
    }}
  ],

  "interface": {{
    "elements_hud": ["HP barre", "score", "wave/level", "gold", "cooldowns"],
    "feedback_ui": "Animations, flashs, sons pour chaque action importante"
  }},

  "ambiance": {{
    "description_visuelle": "...",
    "palette_couleurs": "couleur fond, joueur, ennemis, UI",
    "style_artistique": "...",
    "atmosphere": "..."
  }},

  "rejouabilite": {{
    "elements": ["highscore personnel", "déblocage progressif", "builds différents"],
    "meta_progression": "Ce qui change entre deux parties",
    "duree_avant_lassitude": "Nombre estimé de sessions avant de s'en lasser"
  }},

  "specificites_techniques": "Détails d'implémentation importants pour le Créateur"
}}"""

    result = _call(prompt)
    nb_sys = len(result.get("systemes_principaux", []))
    nb_ennemis = len(result.get("contenu_detaille", {}).get("ennemis_stats", []))
    phase2_log.agent_done(
        "Game Designer",
        f"'{result.get('titre', '?')}' — {nb_sys} systèmes, {nb_ennemis} types d'ennemis, formules: {'oui' if result.get('formules_cles') else 'non'}"
    )
    return result


def _genre_depth_hint(genre: str) -> str:
    """Retourne des exigences de profondeur spécifiques au genre détecté."""
    if any(k in genre for k in ["base", "stratégie", "strategy", "builder", "clash", "rts"]):
        return """GENRE : BASE BUILDER / STRATÉGIE
▶ Cycle économique COMPLET : récolte → construction → défense → récolte (pas de cycle = démo)
▶ 4+ types de bâtiments : producteur ressources, attaque (tour), défense (mur/bouclier), support (boost)
▶ Chaque bâtiment : 3 niveaux d'upgrade avec coûts et stats précis
▶ Vagues d'attaque numérotées : composition précise par vague (ex: vague 3 = 6 grunts + 2 tanks)
▶ Bâtiment spécial débloqué à la vague 5 et à la vague 10
▶ Formule coût upgrade : cost = baseCost * 1.5^(level-1)
▶ Formule production : goldPerSec = mines * 2 * (1 + mineLevel * 0.3)"""

    if any(k in genre for k in ["rpg", "dungeon", "aventure", "roguelite", "rogue"]):
        return """GENRE : RPG / DUNGEON CRAWLER
▶ 3+ classes jouables avec statistiques et styles de combat DISTINCTS (pas juste couleurs différentes)
▶ Système de loot : 3 raretés (commun 70%, rare 25%, épique 5%) avec bonus de stats clairs
▶ Level up toutes les 3-4 minutes max — stats qui augmentent VISIBLEMENT (HP, ATK, DEF affichés)
▶ Boss par zone avec 2-3 phases et pattern d'attaque unique à chaque phase
▶ Formule dégâts RPG : dmg = Math.max(1, (atk * skillMult) - floor(def * 0.5)) + random(-2,2)
▶ Formule XP level up : xpNeeded = 100 * Math.pow(level, 1.8)
▶ Inventaire ou arbres de compétences même simplifié"""

    if any(k in genre for k in ["tower", "defense", "td", "défense"]):
        return """GENRE : TOWER DEFENSE
▶ 4+ types de tours avec stats précises (DPS, portée, vitesse d'attaque, coût, effet spécial)
▶ Synergies entre tours documentées (ex: Tower Gel + Tower Foudre = ×2.0 DPS)
▶ Système d'intérêt : or non dépensé en fin de vague génère +5-10% bonus vague suivante
▶ Vagues numérotées avec COMPOSITION PRÉCISE : type, quantité, timing de spawn
▶ Chemin(s) des ennemis avec points stratégiques pour placer les tours
▶ Formule DPS effectif : dps = (damage / attackRate) * (slow_mult si applicable)
▶ Upgrade tours : 3 niveaux avec tradeoffs (dégâts vs portée vs vitesse d'attaque)"""

    if any(k in genre for k in ["shoot", "shmup", "shooter", "spatial", "vaisseau", "bullet"]):
        return """GENRE : SHOOTER
▶ 3+ armes/modes de tir avec profils distincts : précis/lent/fort, rapide/faible, AoE/zone
▶ Patterns ennemis élaborés : formation ligne, flanc simultané, vague en V, embuscade
▶ Boss avec 3 phases : attaque directe, pattern unique, enrage (<25% HP)
▶ Power-ups transformants : pas juste +HP — "double canon 10s", "bouclier 3 hits", "bombe nucléaire"
▶ Formule score combo : score += baseScore * Math.pow(1.1, comboCount) pour inciter la chaîne de kills
▶ Progression arme : collecte X munitions spéciales → upgrade temporaire ou permanent"""

    if any(k in genre for k in ["platform", "plateforme", "saut", "jump"]):
        return """GENRE : PLATFORMER
▶ Kit physique complet selon thème : coyote time (100ms), jump buffer (120ms), wall jump si approprié
▶ Dash/dash aérien si thème action/ninja — animation distincte + invincibilité frames
▶ 3+ types d'obstacles : statiques, mobiles, temporisés, environnementaux (lava, spikes, vent)
▶ Collectibles cachés : 3-5 par niveau, accessibles avec compétences acquises plus tard
▶ Zones thématiques distinctes avec hazard unique : zone eau (ralentissement), zone feu (damage/sec)
▶ Formule gravité : player.vy += gravity * dt; player.vy = Math.min(player.vy, maxFallSpeed)
▶ Secrets et power-ups permanents qui changent le gameplay"""

    if any(k in genre for k in ["puzzle", "réflexion", "logique"]):
        return """GENRE : PUZZLE
▶ Mécanique signature irréductible et originale — pas juste Match-3 ou Tetris clone
▶ 3 phases de difficulté : intro implicite (5 niveaux), progression (10 niveaux), maîtrise (5 niveaux)
▶ Mécaniques secondaires introduites une par une (jamais 2 nouvelles règles au même niveau)
▶ "Aha moments" conçus : au moins 3 moments où le joueur comprend quelque chose de nouveau
▶ Formule score : bonus_temps * difficulte_niveau * combo_perfect_moves
▶ Niveaux générés ou hand-crafted — préciser lequel et pourquoi"""

    # Générique
    return """GENRE : ACTION / ARCADE
▶ 3+ types d'adversaires distincts (visuellement ET comportementalement)
▶ Progression claire toutes les 2-3 minutes (nouveau type, power-up, montée stats)
▶ Au moins 1 moment "wow" garanti (boss, capacité spéciale, power-up rare)
▶ Meta-loop explicit : score, déblocage, ou build différent pour recommencer
▶ Formule difficulté : paramètres qui augmentent avec le temps ou le score, jamais fixes"""


@with_fallback({"titre": "Arcade Game", "concept": "Un jeu arcade", "systemes_principaux": [],
                "formules_cles": {}, "meta_loop": {}, "contenu_detaille": {}})
def _call(prompt: str) -> dict:
    # D4 : thinking activé pour le game designer (clé payante) — créativité et cohérence maximales
    return call_gemini_json(prompt, temperature=0.7, system_instruction=SYSTEM, max_tokens=32000, disable_thinking=False)

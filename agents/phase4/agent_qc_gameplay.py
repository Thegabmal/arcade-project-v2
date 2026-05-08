"""
QC Gameplay Agent — Phase 4 (merged with agent_anti_pattern)
Evaluates gameplay quality AND detects anti-patterns in a single call.

Merge justified: both agents analyze the same game mechanics,
just from different angles (positive vs negative). A single call produces
a more coherent evaluation and saves a parallel slot.

Returns a dict {"gameplay": EvaluationResult, "anti_pattern": EvaluationResult}
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, EvaluationResult
from logger import phase4_log

SYSTEM = """You are an expert Game Designer AND a specialist in video game anti-patterns.
You analyze a game's gameplay from two complementary angles:
1. What works well (quality, fun, coherence)
2. What is problematic (anti-patterns, bad practices, frustration)
You provide a complete and honest evaluation. You respond ONLY in valid JSON."""


def _genre_checklist(genre: str, sous_genre: str) -> str:
    """
    Returns 5 hard must-haves for the given genre.
    Each absent item deducts 1.5 pts from the gameplay score.
    Returns '' if genre is unrecognised (no penalty applied).
    """
    g = (genre + " " + (sous_genre or "")).lower()

    if any(k in g for k in ["shmup", "shoot", "vaisseau", "spatial", "space", "galaga", "bullet"]):
        return (
            "1. VARIÉTÉ ENNEMIS : ≥ 3 types distincts avec comportements DIFFÉRENTS (pas juste vitesse)\n"
            "2. BOSS MULTI-PHASES : boss présent avec ≥ 2 phases déclenchées par seuil HP\n"
            "3. POWER-UPS : ≥ 2 types collectables avec effets visuellement distincts\n"
            "4. PATTERNS DE TIR : au moins 2 patterns ennemis différents (droit, visé, éventail…)\n"
            "5. SYSTÈME DE VAGUES : vague N+1 plus difficile que vague N (plus d'ennemis OU plus rapides OU nouveaux types)"
        )
    if any(k in g for k in ["platformer", "plateforme", "jump", "mario", "metroidvania"]):
        return (
            "1. PHYSIQUE JUSTE : coyote time (≥0.08s) OU jump buffer — sauts ne doivent pas rater à la limite\n"
            "2. VARIÉTÉ ENNEMIS : ≥ 2 types avec comportements distincts (patrouille, charge, projectile…)\n"
            "3. NIVEAUX OU SCROLL : ≥ 2 niveaux distincts OU monde scrollant avec zone finale\n"
            "4. COLLECTIBLES : pièces, étoiles ou power-ups qui changent le gameplay (pas juste déco)\n"
            "5. BOSS OU DÉFI FINAL : boss room OU niveau climax avec obstacle/ennemi renforcé"
        )
    if any(k in g for k in ["rpg", "aventure", "zelda", "action-rpg", "action rpg", "dungeon", "roguelite", "rogue"]):
        return (
            "1. COMBAT BILATÉRAL : les ennemis attaquent vraiment le joueur (IA tour ennemi ou attaque auto)\n"
            "2. PROGRESSION STATS : XP + level up OU loot qui augmente des stats visibles\n"
            "3. VARIÉTÉ ENNEMIS : ≥ 2 types avec stats et comportements distincts\n"
            "4. INTERACTION ENVIRONNEMENT : coffres, PNJ ou leviers déclenchables avec [E] ou clic\n"
            "5. CONDITION DE VICTOIRE : objectif clair (quête, boss final, étage max) — pas juste survie infinie"
        )
    if any(k in g for k in ["tower defense", "tower_defense", "td", "defense"]):
        return (
            "1. TYPES DE TOURS : ≥ 2 tours avec rôles distincts (dégâts, ralentissement, zone)\n"
            "2. ÉCONOMIE : gold gagné en tuant des ennemis, dépensé pour placer/améliorer des tours\n"
            "3. ANNONCE VAGUE : compte à rebours visible avant chaque vague + composition annoncée\n"
            "4. UPGRADE TOURS : au moins un palier d'amélioration de tour fonctionnel\n"
            "5. SANTÉ BASE : barre HP visible pour la base — game over si elle tombe à 0"
        )
    if any(k in g for k in ["puzzle", "match3", "match-3", "match 3"]):
        return (
            "1. DÉTECTION MATCH : correspondances de ≥ 3 en ligne vérifiées horizontalement ET verticalement\n"
            "2. CASCADE : après suppression, les tuiles tombent et génèrent de nouveaux matchs en chaîne\n"
            "3. VARIÉTÉ TUILES : ≥ 4 types de tuiles visuellement distincts\n"
            "4. SCORE COMBO : combinaisons successives multiplient les points\n"
            "5. PROGRESSION : niveaux avec objectif (score cible, nombre de matchs) OU difficulté croissante"
        )
    if any(k in g for k in ["runner", "endless", "course infinie", "infinite runner"]):
        return (
            "1. OBSTACLES VARIÉS : ≥ 2 types avec mécaniques de dodge différentes (sauter, s'accroupir, dévier)\n"
            "2. ACCÉLÉRATION : la vitesse augmente progressivement — début accessible, fin difficile\n"
            "3. MÉCANIQUE BONUS : double saut OU slide OU couloirs multiples (pas juste avancer+sauter)\n"
            "4. SCORE DISTANCE : score ou distance clairement visible et progressant\n"
            "5. GÉNÉRATION PROCÉDURALE : obstacles générés différemment à chaque run (pas séquence fixe)"
        )
    if any(k in g for k in ["breakout", "casse-briques", "brique", "arcade", "arkanoid", "pong"]):
        return (
            "1. ANGLE DE BALLE : l'angle de rebond varie selon la position de l'impact sur la raquette\n"
            "2. TYPES DE BRIQUES : ≥ 3 types (résistance différente, briques indestructibles, power-up drop)\n"
            "3. POWER-UPS : ≥ 2 types tombant des briques (balle large, multi-balles, laser…)\n"
            "4. VIES ET GAME OVER : système de vies (≥ 3) avec game over et écran de score\n"
            "5. NIVEAUX : ≥ 2 dispositions de briques différentes avec difficulté croissante"
        )
    if any(k in g for k in ["visual novel", "visual_novel", "roman visuel", "vn", "kinetic"]):
        return (
            "1. ARBRES DE DIALOGUE : ≥ 1 choix multiple avec conséquences narratives différentes\n"
            "2. PORTRAITS PERSONNAGES : illustrations ou dessins affichés pendant les dialogues\n"
            "3. FLAGS NARRATIFS : variables d'état (flags/chapitres) qui conditionnent la suite\n"
            "4. ≥ 3 SCÈNES/CHAPITRES : progression narrative en plusieurs actes distincts\n"
            "5. FIN CONDITIONNELLE : au moins 2 fins différentes selon les choix du joueur"
        )
    return ""


def run(code: str, genre_profile: GenreProfile, gdd: dict) -> dict:
    """
    Retourne {"gameplay": EvaluationResult, "anti_pattern": EvaluationResult}.
    Les deux résultats proviennent d'un seul appel LLM.
    """
    est_3d = genre_profile.technologie_rendu == "threejs"
    est_narratif = getattr(genre_profile, "is_narrative", False)

    _checklist_raw = _genre_checklist(genre_profile.genre_principal, genre_profile.sous_genre)
    genre_checklist_section = ""
    if _checklist_raw:
        genre_checklist_section = (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "INCONTOURNABLES DU GENRE — 5 CRITÈRES BLOQUANTS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Vérifie chacun EXPLICITEMENT dans le code. Chaque critère absent = -1.5 pts gameplay.\n"
            "Un jeu ne peut PAS dépasser 7.0 s'il en manque ≥ 2.\n\n"
            + _checklist_raw + "\n"
        )

    phase4_log.agent_start(
        "QC Gameplay + Anti-Pattern",
        f"{genre_profile.genre_principal} ({'3D' if est_3d else '2D'}{', narratif' if est_narratif else ''})"
    )

    criteres = genre_profile.criteres_qc_gameplay
    criteres_str = json.dumps(criteres, ensure_ascii=False) if criteres else ""
    pieges = json.dumps(genre_profile.pieges_courants, ensure_ascii=False)
    a_eviter = json.dumps(genre_profile.mecaniques_a_eviter, ensure_ascii=False)
    mecaniques_obligatoires = json.dumps(genre_profile.mecaniques_obligatoires, ensure_ascii=False)

    criteres_controls = (
        "- Contrôles 3D (pointer lock FPS, WASD+souris, caméra fluide)"
        if est_3d else
        "- Contrôles 2D réactifs (clavier/touch, réponse immédiate aux inputs)"
    )

    from utils import extract_js_sample
    code_extrait = extract_js_sample(code, 24000)

    prompt = f"""Analyse complète du gameplay de ce jeu {genre_profile.genre_principal} ({'Three.js 3D' if est_3d else 'Canvas 2D'}).

CODE :
```html
{code_extrait}
```

CONTEXTE :
- Genre : {genre_profile.genre_principal} / {genre_profile.sous_genre}
- Boucle core attendue : {genre_profile.boucle_core}
- Progression : {genre_profile.structure_progression}
- Difficulté : {genre_profile.courbe_difficulte}
- Public : {genre_profile.public_cible}
- Titre : {gdd.get("titre", "?")}

MÉCANIQUES OBLIGATOIRES POUR CE GENRE :
{mecaniques_obligatoires}

MÉCANIQUES À ÉVITER POUR CE GENRE :
{a_eviter}

F2 — COMPARAISON GDD vs IMPLÉMENTATION (fonctionnalités demandées vs réellement présentes) :
- Systèmes GDD attendus : {json.dumps([s.get('nom','') for s in gdd.get('systemes_principaux', [])[:5]], ensure_ascii=False)}
- Boss attendu : {json.dumps(gdd.get('contenu_detaille', {}).get('boss', [{}])[0].get('nom', 'non spécifié') if gdd.get('contenu_detaille', {}).get('boss') else 'non spécifié', ensure_ascii=False)}
- Ennemis attendus (stats) : {len(gdd.get('contenu_detaille', {}).get('ennemis_stats', []))} types définis dans GDD
- Power-ups attendus : {len(gdd.get('contenu_detaille', {}).get('powerups', []))} types définis dans GDD
→ PÉNALISER sévèrement si systèmes GDD absents du code (features demandées non implémentées)

CRITÈRES GAMEPLAY SPÉCIFIQUES AU GENRE :
{criteres_str}

RUBRIQUE DE SCORE GAMEPLAY (calibrage précis — sois honnête et sévère) :
- 0-3 : Jeu non fonctionnel ou core loop absente (stub vide, aucun ennemi, aucune collision)
- 4-5 : Core loop présente mais ultra-basique (1 ennemi, pas de boss, zéro système secondaire)
- 6   : Correct — core loop fonctionnelle + quelques systèmes mais manque de profondeur
- 7   : Bon — 2-3 types d'ennemis distincts, système de vagues, feedback basique présent
- 8   : Très bon — boss avec phases, power-ups, combo OU XP, particules et feedback riche
- 9   : Excellent — tous les systèmes du genre attendus, progression satisfaisante, très rejouable
- 10  : Exceptionnel — réserve uniquement pour un jeu vraiment mémorable (rare)
{genre_checklist_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIE 1 — PROFONDEUR ET RICHESSE GAMEPLAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITÈRES FONDAMENTAUX (base nécessaire) :
- Core loop implémentée et fonctionnelle (pas de stub, vraie logique)
- Clarté immédiate : instructions sur l'écran de menu, contrôles visibles
- Feedback visuel sur chaque action (tir, impact, mort, collecte)
- Progression de difficulté réelle (wave 1 ≠ wave 5 — plus d'ennemis, plus rapides, nouveaux types)
- Restart rapide et complet (toutes les variables remises à 0, pas de location.reload())
{criteres_controls}

CRITÈRES DE PROFONDEUR (ce qui fait un bon jeu — évalue chacun avec une note) :
- VARIÉTÉ ENNEMIS : combien de types distincts ? (1 type = insuffisant, 2 = passable, 3+ = bien)
  Vérifier que chaque type a un comportement DIFFÉRENT (pas juste vitesse changée)
- BOSS SYSTEM : y a-t-il un boss avec HP élevé ? Avec ≥ 2 phases de comportement selon son HP% ?
- PROGRESSION JOUEUR : XP + level up OU upgrades OU déverrouillage de capacités au fil du jeu ?
- POWER-UPS/COLLECTIBLES : ≥ 2 types distincts avec effets différents (durée, activation, feedback) ?
- SYSTÈME COMBO/MULTIPLICATEUR : kills consécutifs multiplient le score ? Timer de combo visible ?
- ÉCONOMIE : gold/points permettant d'acheter ou d'améliorer quelque chose ?
- ÉQUILIBRE : ni trop facile (ennemi trop lent), ni injuste (insta-kill) — valeurs numériques cohérentes ?

CRITÈRES SPÉCIFIQUES RPG (si genre = rpg / dungeon / aventure) :
- Tous les membres du groupe peuvent attaquer (pas un seul personnage actif)
- Les ennemis attaquent vraiment le joueur (IA tour ennemi exécutée)
- L'XP monte et déclenche des level ups visibles avec gain de stats
- Distinctions visuelles nettes entre classes de personnages
- Barres de vie visibles et colorées pour héros ET ennemis
- Loot sur mort ennemi (gold, potions) avec probabilités
- Log de combat ou textes flottants pour les dégâts

CRITÈRES SPÉCIFIQUES SHOOTER (si genre = shoot/shmup/space) :
- Patterns de tir ennemis variés (circulaire, éventail, visé, spirale)
- Boss avec au moins 3 patterns distincts selon phase HP
- Power-ups collectables avec effets visuellement distincts
- Difficulté progressive par vague (plus de balles, plus rapides, patterns complexes)

CRITÈRES SPÉCIFIQUES TOWER DEFENSE (si genre = tower defense/td) :
- Plusieurs types de tours avec portées et dégâts différents
- Système d'upgrade de tours fonctionnel
- Économie (gold) gagnée en tuant des ennemis, dépensée pour construire/upgrader
- Vagues avec compte à rebours visible et types d'ennemis annoncés
{"" if not est_narratif else """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITÈRES SPÉCIFIQUES JEU NARRATIF (OBLIGATOIRES — ce jeu est narratif)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- SYSTÈME DE QUÊTES : quests{} implémenté avec états active/done trackables
- MOTEUR DIALOGUE : showDialog()/showChoiceDialog() avec effet typewriter et choix navigables
- DIALOGUES JOUABLES : chaque PNJ principal a au moins un dialogue déclenchable (touche [E] ou clic)
- CHOIX NARRATIFS : au moins un arbre de décision avec choix multiples et conséquences différentes
- FLAGS NARRATIFS : flags{} permettant de conditionner des dialogues ou l'avancement de quêtes
- CONDITION DE VICTOIRE : liée à l'accomplissement de quêtes, pas juste au score
- COHÉRENCE HISTOIRE : le lore affiché correspond au synopsis défini (pas de placeholder générique)
- ÉTAT 'dialogue' : le jeu entre en état dialogue (mouvement bloqué) pendant les échanges

ANTI-PATTERNS NARRATIFS À PÉNALISER :
- Dialogues statiques (affichés instantanément, pas de typewriter) → mineur
- PNJs présents dans la map mais non interactables → majeur
- Quêtes affichées dans le HUD sans suivi d'avancement → majeur
- Texte placeholder "Lorem ipsum" ou "NPC says: Hello" → critique
- Système de choix affiché mais tous les choix mènent au même résultat → majeur
- Histoire sans début ni fin (pas d'écran de victoire narratif) → critique
"""}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIE 2 — ANTI-PATTERNS ET PIÈGES DU GENRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pièges spécifiques au genre :
{pieges}

Anti-patterns universels de game design :
- Mort soudaine sans avertissement ni feedback (insta-kill injuste)
- Difficulté basée sur la chance pure plutôt que le skill du joueur
- Spawn d'ennemis DIRECTEMENT sur le joueur (spawn killing)
- Répétitivité excessive : exactement les mêmes patterns en boucle sans variation
- Feedback insuffisant : le joueur ne comprend pas pourquoi il est mort
- Game over sans progression sauvegardée (highscore, XP, etc.)
- Instructions absentes ou incompréhensibles

Bugs runtime cachés qui rendent le jeu injouable :
- Boucle for-index sans `const e = arr[i]` → ReferenceError au premier ennemi
- Fonctions update qui utilisent dt sans l'avoir en paramètre → mouvements cassés
- loadGame() accède à data.x sans JSON.parse() → crash silencieux
- `dist` utilisée sans être calculée dans la même portée → NaN et collisions manquées
- eval() dans la logique du jeu → fuite mémoire (window.__devPatch est toléré : outil dev injecté après évaluation)

Anti-patterns spécifiques RPG :
- Combat à sens unique (seul le joueur attaque, les ennemis ne font rien)
- XP jamais distribuée ou level up sans effet sur les stats
- Tous les personnages identiques visuellement

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT DE RÉPONSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Réponds en JSON avec ces deux sections :
{{
  "gameplay": {{
    "criteres_evalues": [
      {{"nom": "...", "score_obtenu": 1.5, "score_max": 2.0, "present": true, "commentaire": "..."}}
    ],
    "mecaniques_presentes": ["mécanique trouvée et bien implémentée"],
    "mecaniques_manquantes": ["mécanique attendue mais absente"],
    "issues": [
      {{"severite": "critique / majeur / mineur", "description": "...", "suggestion": "..."}}
    ],
    "points_forts": ["...", "..."],
    "score_total": 7.5,
    "commentaire_global": "..."
  }},
  "anti_pattern": {{
    "anti_patterns_detectes": [
      {{
        "nom": "...",
        "description": "Ce qui est problématique dans le code",
        "severite": "critique / majeur / mineur",
        "correction_proposee": "..."
      }}
    ],
    "pieges_genre_evites": ["piège correctement évité"],
    "score_global": 8.0,
    "commentaire": "Synthèse : score = 10 - (critiques×2.5) - (majeurs×1.5) - (mineurs×0.5)"
  }}
}}"""

    result = _call(prompt)
    return _parse_both(result)


def _parse_both(result: dict) -> dict:
    """Parse les deux sections et retourne deux EvaluationResult."""

    # ── Gameplay ──
    gp_raw = result.get("gameplay", result)  # fallback si format plat
    gp = EvaluationResult(agent_name="QC Gameplay")
    gp.criteres = gp_raw.get("criteres_evalues", [])
    gp.issues = gp_raw.get("issues", [])
    gp.points_forts = gp_raw.get("points_forts", [])
    gp.score = float(gp_raw.get("score_total", 5.0))
    gp.commentaire_global = gp_raw.get("commentaire_global", "")
    gp.score = max(0.0, min(10.0, gp.score))

    manquantes = gp_raw.get("mecaniques_manquantes", [])
    if manquantes:
        phase4_log.warning(f"Mécaniques manquantes : {', '.join(manquantes[:3])}")
    phase4_log.score("QC Gameplay", gp.score)

    # ── Anti-Pattern ──
    ap_raw = result.get("anti_pattern", {})
    ap = EvaluationResult(agent_name="Anti-Pattern")
    anti_patterns = ap_raw.get("anti_patterns_detectes", [])
    ap.issues = [
        {
            "severite": p.get("severite", "mineur"),
            "description": p.get("description", ""),
            "suggestion": p.get("correction_proposee", "")
        }
        for p in anti_patterns
    ]
    ap.score = float(ap_raw.get("score_global", 7.0))
    ap.score = max(2.0, min(10.0, ap.score))  # plancher 2.0 — aucun vrai jeu ne mérite 0
    ap.commentaire_global = ap_raw.get("commentaire", "")
    ap.points_forts = ap_raw.get("pieges_genre_evites", [])

    critiques_ap = [p for p in anti_patterns if p.get("severite") == "critique"]
    majeurs_ap = [p for p in anti_patterns if p.get("severite") == "majeur"]
    phase4_log.score("Anti-Pattern", ap.score)
    if critiques_ap:
        phase4_log.warning(f"{len(critiques_ap)} anti-pattern(s) critique(s) : {critiques_ap[0].get('nom', '')}")
    if majeurs_ap:
        phase4_log.info(f"{len(majeurs_ap)} anti-pattern(s) majeur(s)")

    return {"gameplay": gp, "anti_pattern": ap}


@with_fallback({
    "gameplay": {
        "criteres_evalues": [], "issues": [], "points_forts": [],
        "score_total": 5.0, "commentaire_global": "Analyse indisponible",
        "mecaniques_presentes": [], "mecaniques_manquantes": []
    },
    "anti_pattern": {
        "anti_patterns_detectes": [], "pieges_genre_evites": [],
        "score_global": 7.0, "commentaire": "Analyse indisponible"
    }
})
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.3, system_instruction=SYSTEM, max_tokens=20000)

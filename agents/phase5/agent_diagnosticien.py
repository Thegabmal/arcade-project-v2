"""
Diagnostician Agent — Phase 5
Aggregates all evaluation results and produces a precise diagnosis:
- Which problems to fix with highest priority
- How to fix them concretely
- What must absolutely be preserved
"""

import json
from config import call_gemini_paid_json, with_fallback
from genre_profile import GenreProfile, EvaluationBundle
from logger import phase5_log

SYSTEM = """Tu es un expert en débogage de jeux HTML5 Canvas 2D/Three.js.
Tu identifies les problèmes au niveau du CODE (nom de fonction, variable, pattern exact).
RÈGLES STRICTES pour tes corrections :
- Cite le NOM EXACT de la fonction à modifier (ex: "dans updatePlayer()")
- Donne le PATTERN EXACT à chercher (ex: "cherche 'keys.moveLeft' et remplace par 'keys.left'")
- Donne la VALEUR CIBLE (ex: "change gravite de 0.1 à 0.4")
- PRIORITÉ aux bugs qui causent écran noir, boucle de jeu absente, crash au clic, ou contrôles inactifs
- Ne propose JAMAIS une réécriture complète sauf si le code fait < 1000 chars

PATTERNS DE CORRECTION CANVAS 2D :
- "Canvas absent" → vérifier que <canvas id="X"> existe dans le HTML body
- "Aucun canvas détecté" (Playwright) → même correction + vérifier getElementById('X') correspond à l'ID HTML
- "Écran noir/blanc/uni" → dans draw() : ctx.fillRect() DOIT être la 1ère opération, avant ctx.save()/translate()
- "Contrôles inactifs" → keys object : déclaration = handlers = update() doivent utiliser les MÊMES noms

PATTERNS DE CORRECTION THREE.JS :
- "Tout noir" → AmbientLight et DirectionalLight manquants — les ajouter à la scène
- "Canvas blanc" → scene.background non défini — ajouter scene.background = new THREE.Color(0x1a1a2e)
- "Entités non supprimées" → scene.remove(entity.mesh) avant splice()
- "Restart crash" → vérifier que restart réinitialise les arrays ET remove() tous les meshes de la scène
- "Canvas 3D non visible" → document.body.appendChild(renderer.domElement) manquant

BUGS RUNTIME FRÉQUENTS (PRIORITÉ CRITIQUE — causent crash silencieux ou jeu injouable) :
1. LOOP VAR INIT — for (let i=0; i<arr.length; i++) sans const p = arr[i] en première ligne → ReferenceError
   ❌ for (let i=0; i<enemies.length; i++) { enemy.x += enemy.vx * dt; }
   ✅ for (let i=enemies.length-1; i>=0; i--) { const enemy = enemies[i]; enemy.x += enemy.vx * dt; }
2. DT NON PASSÉ — function updateBullets() utilise dt sans l'avoir en paramètre → NaN partout
   ❌ function updateBullets() { b.x += b.vx * dt; }   update(dt) { updateBullets(); }
   ✅ function updateBullets(dt) { b.x += b.vx * dt; }  update(dt) { updateBullets(dt); }
3. JSON.PARSE MANQUANT — const data = localStorage.getItem(K); data.score → TypeError
   ✅ const raw = localStorage.getItem(K); const data = JSON.parse(raw || 'null'); if (!data) return;
4. VARIABLE NON DÉCLARÉE — if (closest) attack() sans let closest = null avant la boucle → ReferenceError
   ✅ let closest = null; for (const en of enemies) { ... if (...) closest = en; } if (closest) attack(closest);
5. EVENT LISTENER HORS DOM — canvas.addEventListener avant DOMContentLoaded → canvas=null → crash
   ✅ Tous les canvas.addEventListener DANS le callback DOMContentLoaded
6. CONST REASSIGNMENT — `const score = 0` puis `score += 10` → TypeError: Assignment to constant variable
   ❌ const score = 0; ... score += 10;   // TypeError crash silencieux
   ✅ let score = 0;   ... score += 10;   // utiliser let pour toute variable de game state mutable
7. FOR-OF SPLICE — `for (const e of enemies)` avec `enemies.splice(i,1)` dedans → éléments sautés
   ❌ for (const enemy of enemies) { if (enemy.hp<=0) enemies.splice(enemies.indexOf(enemy),1); }
   ✅ for (let i=enemies.length-1; i>=0; i--) { const enemy=enemies[i]; if (enemy.hp<=0) enemies.splice(i,1); }
8. location.reload() POUR RESTART → rechargement de page → flash + perte d'état
   ❌ if (gameOver && keys.r) location.reload();
   ✅ if (gameOver && keys.r) resetGame();   // fonction qui réinitialise les variables

EXEMPLE DE RÉPONSE JSON CORRECTE :
{
  "probleme_principal": "updateEnemies() crash : boucle for-index sans init locale const en = enemies[i]",
  "corrections_prioritaires": [
    {
      "priorite": 1, "domaine": "technique",
      "probleme": "Boucle for dans updateEnemies() accède à 'en' non déclaré",
      "correction": "Ajouter 'const en = enemies[i];' comme première ligne du corps du for-loop dans updateEnemies(), et inverser la boucle en 'i = enemies.length-1; i >= 0; i--' pour que splice() soit sûr",
      "impact_attendu": "score technique +2 points, plus de ReferenceError",
      "code_a_modifier": "updateEnemies",
      "module_concerne": "enemies"
    },
    {
      "priorite": 2, "domaine": "technique",
      "probleme": "updateProjectiles() utilise dt sans l'avoir en paramètre",
      "correction": "Changer 'function updateProjectiles()' en 'function updateProjectiles(dt)' et l'appeler 'updateProjectiles(dt)' dans update()",
      "impact_attendu": "score technique +1 point, projectiles se déplacent correctement",
      "code_a_modifier": "updateProjectiles",
      "module_concerne": "core"
    }
  ],
  "a_absolument_preserver": ["système de vagues WAVE_DEFS", "PALETTE de couleurs", "sfx stub"],
  "score_minimum_vise": 7.5,
  "instructions_patcher": "Corriger d'abord la boucle ennemis (risque de crash), puis dt des projectiles. Ne pas toucher au système de score ni à la physique joueur.",
  "module_principal_a_corriger": "enemies",
  "blocage_critique": false,
  "raison_blocage": ""
}
Tu réponds UNIQUEMENT en JSON valide."""


# ── Genre must-have static detector ──────────────────────────────────────────
# Each entry: (label, [regex_patterns_that_prove_it_IS_present])
# If NONE of the patterns match → the criterion is considered absent.
_GENRE_MUST_CHECKS: dict[str, list[tuple[str, list[str]]]] = {
    "shmup": [
        ("≥3 TYPES D'ENNEMIS distincts",   [r'ENEMY_DEFS\s*=', r"type\s*:\s*['\"](?:drone|fighter|tank|stealth|kamikaze|boss)", r'ENEMY_TYPES\s*=']),
        ("BOSS avec ≥2 PHASES",            [r'bossPhase|boss\.phase|phase\s*[>=<]\s*[23]|boss_phase']),
        ("POWER-UPS collectables",         [r'powerUp|powerups|PU_DEFS|POWERUP|power_up']),
        ("PATTERNS DE TIR variés",         [r'spread|spiral|aimed|burst|triple|fanfire|firePattern|bullet_pattern']),
        ("SYSTÈME DE VAGUES croissant",    [r'WAVE_DEFS|waveActive|updateWave|wave\s*\+\+|wave\s*\+=\s*1']),
    ],
    "platformer": [
        ("COYOTE TIME ou JUMP BUFFER",     [r'coyoteTime|coyote_time|jumpBuffer|jump_buffer|COYOTE_TIME|JUMP_BUFFER']),
        ("≥2 TYPES D'ENNEMIS",             [r'ENEMY_TYPES|enemy\.type|enemyType|type\s*:\s*["\'](?:patrol|charge|jump|flying|ground|walker)']),
        ("≥2 NIVEAUX ou monde scrollant",  [r'LEVEL_DEFS|LEVELS\s*=\s*\[|currentLevel|levelIndex|nextLevel|cam\.x']),
        ("COLLECTIBLES ou power-ups",      [r'collectible|coin|gem|star|powerUp|mushroom|pickup']),
        ("BOSS ou défi final",             [r'boss|BOSS|bossActive|bossRoom']),
    ],
    "rpg": [
        ("COMBAT BILATÉRAL (ennemis attaquent)", [r'enemy\.attack|enemyAtk|ennemi.*attaque|enemyDmg|enemy\.dmg|ennemis.*dégât']),
        ("XP + LEVEL UP",                  [r'xp\s*[+]=|addXP|gainXP|levelUp|level_up|checkLevelUp']),
        ("≥2 TYPES D'ENNEMIS",             [r'ENEMY_TYPES|enemy\.type|enemyType|slime|garde|archer|goblin|orc|troll']),
        ("INTERACTION ENVIRONNEMENT",      [r'interactable|coffre|chest|levier|lever|showDialog|[Ee]\s+key']),
        ("CONDITION DE VICTOIRE claire",   [r'quest.*done|quest.*complete|victory|victoire|boss.*mort|allQuestsDone']),
    ],
    "tower_defense": [
        ("≥2 TYPES DE TOURS distincts",    [r'TOWER_TYPES|TOWER_DEFS|towerType|tower\.type']),
        ("ÉCONOMIE gold",                  [r'gold\s*[+]=|addGold|gainGold|gold\s*-=|spendGold']),
        ("ANNONCE DE VAGUE",               [r'waveCountdown|waveCooldown|waveTimer|nextWave|wave_start']),
        ("UPGRADE DE TOUR",                [r'tower.*upgrade|upgradeTower|TOWER.*level|tower\.lvl|towerLevel']),
        ("SANTÉ DE LA BASE",               [r'baseHP|base_hp|baseHealth|base\.hp|base\.health']),
    ],
    "puzzle": [
        ("DÉTECTION MATCH horizontal+vertical", [r'checkMatch|findMatch|matchCheck|horizontal.*match|vertical.*match']),
        ("CASCADE après suppression",      [r'cascade|applyGravity|dropTiles|fillBoard|refill']),
        ("≥4 TYPES DE TUILES",             [r'TYPES\s*=\s*\[(?:[^]]{20,})\]|tileType|tile_type|gemType']),
        ("SCORE COMBO",                    [r'combo|COMBO|comboMult|chain_bonus|matchScore.*combo']),
        ("PROGRESSION niveaux",            [r'LEVELS\s*=\s*\[|currentLevel|levelIndex|nextLevel|levelTarget']),
    ],
    "runner": [
        ("≥2 TYPES D'OBSTACLES",           [r'OBSTACLE_TYPES|obstacle\.type|obstType|obst.*type|slide.*jump|OBST_DEFS']),
        ("ACCÉLÉRATION progressive",       [r'speed\s*[+]=|speed\s*\*=\s*1\.|gameSpeed.*\+|SPEED_RAMP|speedMultiplier']),
        ("MÉCANIQUE BONUS",                [r'doubleJump|double_jump|slide|crouch|dash|lane|laneChange']),
        ("SCORE ou DISTANCE visible",      [r'score\s*[+]=|distance\s*[+]=|dist\s*[+]=|scoreDisplay']),
        ("GÉNÉRATION PROCÉDURALE",         [r'Math\.random|rnd\(|spawnObstacle|generateObstacle|randomObstacle']),
    ],
    "breakout": [
        ("ANGLE DE BALLE variable",        [r'ball\.angle|ballAngle|impact.*angle|hitPoint|paddle.*hit|angle.*bounce']),
        ("≥3 TYPES DE BRIQUES",            [r'BRICK_DEFS|brickType|brick\.type|brick\.hp\s*[>=<]\s*[23]|BRICK_TYPES']),
        ("POWER-UPS depuis briques",       [r'powerUp|PU_DEFS|powerup.*drop|brick.*power|dropPowerup']),
        ("VIES et GAME OVER",              [r'lives\s*[->]=|livesCount|nbVies|loseLife|gameOver']),
        ("≥2 NIVEAUX avec layouts différents", [r'LEVELS\s*=\s*\[|LEVEL_DEFS|currentLevel|levelData|nextLevel']),
    ],
    "visual_novel": [
        ("ARBRE DE DIALOGUE avec choix",   [r'showChoiceDialog|choice.*dialog|NODES.*choices|choices\s*:\s*\[']),
        ("PORTRAITS de personnages",       [r'portrait|drawPortrait|CHARACTER.*img|character.*face|avatar']),
        ("FLAGS NARRATIFS",                [r'flags\s*[\[.]|flags\s*=\s*\{|setFlag|gameFlags|storyFlags']),
        ("≥3 SCÈNES ou CHAPITRES",         [r'chapter|scene.*[23456789]|NODES.*(?:\n.*){15,}|node.*id.*[3-9]']),
        ("≥2 FINS possibles",              [r'ending|END_[A-Z]|gameOver.*\w+|finale.*[AB]|victory.*type']),
    ],
}

# Alias for genres that share the same checks
_GENRE_ALIASES = {
    "dungeon": "rpg",  "dungeon_crawler": "rpg", "aventure": "rpg",
    "roguelite": "rpg", "rogue": "rpg",
    "shmup": "shmup", "shoot": "shmup", "vaisseau": "shmup", "spatial": "shmup",
    "plateforme": "platformer", "jump": "platformer",
    "tower defense": "tower_defense", "td": "tower_defense",
    "match3": "puzzle", "match-3": "puzzle",
    "endless": "runner", "runner": "runner",
    "breakout": "breakout", "arcade": "breakout",
    "visual novel": "visual_novel", "vn": "visual_novel",
}


def _detect_missing_genre_musts(code: str, genre: str, sous_genre: str) -> list[str]:
    """
    Statically checks the code for missing genre must-haves.
    Returns a list of human-readable strings for each absent criterion.
    """
    import re as _re
    g = (genre + " " + (sous_genre or "")).lower()

    key = None
    for alias, target in _GENRE_ALIASES.items():
        if alias in g:
            key = target
            break
    if not key:
        for k in _GENRE_MUST_CHECKS:
            if k in g:
                key = k
                break
    if not key:
        return []

    checks = _GENRE_MUST_CHECKS[key]
    missing = []
    for label, patterns in checks:
        present = any(_re.search(p, code, _re.IGNORECASE) for p in patterns)
        if not present:
            missing.append(label)
    return missing


def run(code: str, genre_profile: GenreProfile, bundle: EvaluationBundle, iteration: int,
        corrections_deja_tentees: list | None = None) -> dict:
    phase5_log.agent_start("Diagnosticien", f"Itération {iteration} — score global: {bundle.score_global():.1f}/10")

    all_issues = bundle.all_issues()
    points_forts = (
        bundle.qc_technique.points_forts +
        bundle.qc_gameplay.points_forts +
        bundle.qc_visuel.points_forts
    )

    scores = {
        "technique": bundle.qc_technique.score,
        "gameplay": bundle.qc_gameplay.score,
        "visuel": bundle.qc_visuel.score,
        "execution": bundle.execution.score,
        "playtester": bundle.playtester.score,
        "anti_pattern": bundle.anti_pattern.score,
        "benchmark": bundle.benchmark.score,
        "global": bundle.score_global(),
    }

    commentaires = {
        "technique": bundle.qc_technique.commentaire_global,
        "gameplay": bundle.qc_gameplay.commentaire_global,
        "visuel": bundle.qc_visuel.commentaire_global,
        "playtester": bundle.playtester.commentaire_global,
        "benchmark": bundle.benchmark.commentaire_global,
    }

    from utils import extract_js_sample
    code_echantillon = extract_js_sample(code, 28000)

    # Scores les plus bas en premier = priorités de correction
    scores_tries = sorted(
        [(k, v) for k, v in scores.items() if k != "global"],
        key=lambda x: x[1]
    )
    axes_prioritaires = [k for k, v in scores_tries[:3]]

    # E2/B3 : Extraire les erreurs JS brutes du test Playwright (stack traces réelles)
    _raw_js_errors = next(
        (c.get("commentaire", "") for c in bundle.execution.criteres if c.get("nom") == "Erreurs JS brutes"),
        ""
    )

    # Extraire les issues d'exécution Playwright séparément pour donner plus de contexte
    exec_issues = [i.get("description", "") for i in bundle.execution.issues if i.get("description")]

    # exec-first : si exec < 4.5, les erreurs Playwright passent en priorité absolue
    exec_score = bundle.execution.score
    exec_critical = exec_score < 4.5
    if exec_critical:
        # Forcer execution en première priorité
        axes_prioritaires = ["execution"] + [a for a in axes_prioritaires if a != "execution"]
        exec_context = (
            "\n🚨 BLOCAGE CRITIQUE — EXEC SCORE {:.1f}/10 (jeu non fonctionnel) :\n"
            "Les erreurs Playwright ci-dessous sont la cause principale. "
            "Corriger ces erreurs est LA SEULE PRIORITÉ — ignorer tous les autres axes.\n"
            "{}"
        ).format(exec_score, "\n".join(f"  ❌ {e}" for e in exec_issues) if exec_issues else "  (aucun détail disponible)")
    else:
        exec_context = (
            f"\nRÉSULTATS PLAYWRIGHT (exécution réelle, score {exec_score:.1f}/10) :\n"
            + "\n".join(f"- {e}" for e in exec_issues)
        ) if exec_issues else ""

    # Détection rapide des bugs runtime dans le code pour les inclure dans le diagnostic
    runtime_bugs_hints = []
    import re as _re
    if _re.search(r'for\s*\(\s*(?:let|var)\s+\w+\s*=\s*0.*?\.length', code):
        # Check for loops that don't have a const variable init as first line
        if not _re.search(r'for\s*\(\s*(?:let|var)\s+\w+\s*=.*?\)\s*\{\s*(?:const|let|var)\s+\w+\s*=', code):
            runtime_bugs_hints.append("⚠️ LOOP VAR INIT : boucle for-index détectée sans const X = arr[i] apparent")
    if _re.search(r'\*\s*dt\b', code) and _re.search(r'function\s+\w+\s*\([^)]*\)\s*\{[^}]*\*\s*dt\b', code):
        # Rough check for functions using dt without dt param
        fns_with_dt = _re.findall(r'function\s+(\w+)\s*\(([^)]*)\)\s*\{[^}]*\*\s*dt\b', code)
        missing_dt = [fn for fn, params in fns_with_dt if 'dt' not in params and fn not in ('gameLoop','animate','loop','tick','render','update','main')]
        if missing_dt:
            runtime_bugs_hints.append(f"⚠️ DT PASSING : fonctions sans paramètre dt : {', '.join(missing_dt[:3])}")
    if _re.search(r'localStorage\.getItem', code) and not _re.search(r'JSON\.parse', code):
        runtime_bugs_hints.append("⚠️ JSON.PARSE MANQUANT : localStorage.getItem sans JSON.parse()")
    if _re.search(r'window\.__(?:devPatch|debug|patch)|eval\(', code):
        runtime_bugs_hints.append("⚠️ EVAL/DEVPATCH détecté dans le code — à supprimer")
    # Détecter les boucles for-of qui splicent le tableau itéré
    _for_of_splices = _re.findall(
        r'for\s*\(\s*(?:const|let)\s+(\w+)\s+of\s+(\w+)\s*\)',
        code
    )
    _bad_for_of = []
    for _var, _arr in _for_of_splices:
        if len(_arr) < 3:
            continue
        _m = _re.search(rf'for\s*\(\s*(?:const|let)\s+{_re.escape(_var)}\s+of\s+{_re.escape(_arr)}\s*\)', code)
        if _m:
            _zone = code[_m.start():_m.start() + 2000]
            if _re.search(rf'\b{_re.escape(_arr)}\.splice\s*\(', _zone):
                _bad_for_of.append(f"{_var} of {_arr}")
    if _bad_for_of:
        runtime_bugs_hints.append(
            f"⚠️ FOR-OF+SPLICE : {_bad_for_of[:3]} — boucle for-of splice le tableau itéré → éléments sautés"
        )
    # Détecter les const réassignés (TypeError crash)
    _const_vars = set(_re.findall(r'\bconst\s+([a-z][a-zA-Z0-9_$]*)\s*=\s*(?:\d|null|false|true|\'|")', code))
    _reassigned = []
    for _v in _const_vars:
        if _re.search(rf'(?<![.\[a-zA-Z0-9_$]){_re.escape(_v)}\s*(?:\+|-|\*|/)?\s*=(?!=)', code):
            _reassigned.append(_v)
    if _reassigned:
        runtime_bugs_hints.append(
            f"⚠️ CONST REASSIGNMENT : {_reassigned[:4]} déclarés const mais réassignés → TypeError crash"
        )

    runtime_hint_str = ""
    if runtime_bugs_hints:
        runtime_hint_str = "\n\n⚠️ BUGS RUNTIME DÉTECTÉS AUTOMATIQUEMENT (priorité absolue) :\n" + "\n".join(runtime_bugs_hints)

    # Détection des systèmes de profondeur manquants (impact gameplay/playtester score)
    depth_missing = []
    import re as _re2
    if not _re2.search(r'boss|BOSS|bossActive|bossHP', code):
        depth_missing.append("BOSS ABSENT — aucun système boss détecté → playtester -1.5pt")
    elif not _re2.search(r'bossPhase|phase\s*[>=<]\s*[23]|boss\.phase|boss_phase', code):
        depth_missing.append("BOSS SANS PHASES — boss présent mais sans transitions de phase → gameplay -0.8pt")
    if not _re2.search(r'ENEMY_TYPES|enemyTypes|enemy\.type|e\.type|createEnemy.*type', code, _re2.IGNORECASE):
        depth_missing.append("UN SEUL TYPE D'ENNEMI — pas de variété → gameplay -1pt")
    if not _re2.search(r'combo|COMBO|comboTimer|comboMult', code, _re2.IGNORECASE):
        depth_missing.append("COMBO ABSENT — pas de système multiplicateur → playtester -0.5pt")
    if not _re2.search(r'particles\s*=\s*\[\]|spawnExplosion|spawnParticle', code):
        depth_missing.append("PARTICULES ABSENTES — pas d'effets de mort/impact → visuel -0.8pt")
    if not _re2.search(r'spawnFloatText|floatTexts|floatingText', code):
        depth_missing.append("FLOAT TEXTS ABSENTS — pas de feedback score flottant → visuel -0.5pt")
    if not _re2.search(r'powerUp|power_up|POWERUP|collectible', code, _re2.IGNORECASE):
        depth_missing.append("POWER-UPS ABSENTS — pas de collectibles → gameplay -0.5pt")

    depth_hint_str = ""
    if depth_missing and scores.get("gameplay", 10) < 7.5:
        depth_hint_str = (
            "\n\n📊 SYSTÈMES MANQUANTS (impactent le score gameplay/playtester) :\n"
            + "\n".join(f"  - {d}" for d in depth_missing)
            + "\n→ Si exec ≥ 6.0, proposer au moins 1-2 de ces systèmes en correction."
        )

    # Genre must-haves static check
    _missing_musts = _detect_missing_genre_musts(code, genre_profile.genre_principal, genre_profile.sous_genre or "")
    genre_musts_section = ""
    if _missing_musts and exec_score >= 4.5:  # only suggest depth additions if game runs
        genre_musts_section = (
            "\n🎯 MISSING GENRE MUST-HAVES (detected in code):\n"
            + "\n".join(f"  ✗ {m}" for m in _missing_musts)
            + "\n→ Each absent criterion costs -1.5 gameplay pts. Add as priority if exec >= 6.\n"
        )

    # Static visual quality checks
    _visual_issues = []
    if 'shadowBlur' not in code:
        _visual_issues.append("ZERO GLOW — no shadowBlur anywhere → visual score hard-capped at 6.5 — add ctx.shadowBlur on player/enemies")
    _has_arc_diag = bool(_re.search(r'ctx\.arc\s*\(', code))
    _has_bezier_diag = bool(_re.search(r'ctx\.bezier|ctx\.quadratic', code, _re.IGNORECASE))
    if not _has_arc_diag and not _has_bezier_diag:
        _visual_issues.append("RECTANGLE SPRITES — no arc/bezierCurveTo shapes → all entities are fillRect → visual score hard-capped at 6.5")
    if not _re.search(r'parallax|bgStars|_bgTimer|scrollY\s*[+-]=|stars\s*=\s*\[|bgScroll', code, _re.IGNORECASE):
        _visual_issues.append("STATIC BACKGROUND — no parallax/scrolling/stars detected → visual penalty -1.0")

    visual_issues_str = ""
    if _visual_issues and scores.get('visuel', 10) < 7.5:
        visual_issues_str = (
            "\n🎨 VISUAL ISSUES DETECTED IN CODE:\n"
            + "\n".join(f"  ✗ {v}" for v in _visual_issues)
            + "\n→ Fix these to raise visual score above 7.0. Use arc/bezier+shadowBlur on entities.\n"
        )

    # Bloc exec-first en tête si critique
    exec_header = f"{exec_context}\n" if exec_critical else ""

    # E2 : erreurs JS brutes pour le patcher
    raw_js_section = ""
    if _raw_js_errors:
        raw_js_section = f"\n🔴 ERREURS JS BRUTES PLAYWRIGHT (priorité absolue — stack traces réelles) :\n{_raw_js_errors}\n"

    # E6 : issues contextualisées par agent source
    _issues_by_source: dict = {}
    for _i in all_issues[:20]:
        _src = _i.get("source", "inconnu")
        _issues_by_source.setdefault(_src, []).append(_i.get("description", str(_i)))
    _issues_contextualized = "\n".join(
        f"[{src.upper()}] " + " | ".join(descs[:3])
        for src, descs in _issues_by_source.items()
    )

    # E5 : éviter de recommander les mêmes corrections déjà tentées
    _deja_tentees_str = ""
    if corrections_deja_tentees:
        # Garder les 10 plus récentes (déjà limitées par I7)
        _recent = corrections_deja_tentees[-10:]
        _deja_tentees_str = ("⛔ CORRECTIONS DÉJÀ TENTÉES SANS SUCCÈS (NE PAS REPRODUIRE) :\n"
                             + "\n".join(f"- {c}" for c in _recent)
                             + "\n→ Proposer des corrections DIFFÉRENTES de celles ci-dessus.\n")

    prompt = f"""Diagnostic de correction pour ce jeu {genre_profile.genre_principal} (itération {iteration}).
{exec_header}
SCORES (du plus bas au plus haut) :
{json.dumps(scores_tries, ensure_ascii=False)}
Axes prioritaires à corriger : {axes_prioritaires}
{'' if exec_critical else exec_context}{raw_js_section}{runtime_hint_str}{genre_musts_section}{visual_issues_str}{depth_hint_str}
{_deja_tentees_str}PROBLÈMES DÉTECTÉS PAR AGENT :
{_issues_contextualized}

PROBLÈMES DÉTECTÉS (détail) :
{json.dumps(all_issues[:15], ensure_ascii=False)}

POINTS FORTS (ne pas toucher) :
{json.dumps(points_forts[:8], ensure_ascii=False)}

COMMENTAIRES :
{json.dumps(commentaires, ensure_ascii=False)}

CODE DU JEU (JavaScript extrait, début + parties clés) :
```javascript
{code_echantillon}
```

Règles pour tes corrections :
- Cite le NOM EXACT de la fonction/variable à modifier
- Donne le pattern exact à chercher et la valeur cible
- PRIORITÉ 1 : bugs qui causent écran noir, crash, contrôles inactifs (exec bloqué)
- PRIORITÉ 2 si exec ≥ 6 : ajouter des systèmes de profondeur manquants (boss, combos, particules)
- Ne propose PAS de réécriture complète — corrections ciblées uniquement
- Bugs runtime détectés automatiquement → OBLIGATOIREMENT dans corrections_prioritaires

Réponds en JSON :
{{
  "probleme_principal": "Le problème #1 qui cause le plus de points perdus",
  "corrections_prioritaires": [
    {{
      "priorite": 1,
      "domaine": "technique|gameplay|visuel|ux",
      "probleme": "description précise du problème",
      "correction": "instruction exacte : quelle fonction, quel pattern chercher, quelle valeur mettre",
      "impact_attendu": "score X +N points",
      "code_a_modifier": "nom exact de la fonction ou variable concernée",
      "module_concerne": "core|player|enemies|physics|ui|renderer ou null"
    }}
  ],
  "a_absolument_preserver": ["ce qui fonctionne — NE PAS toucher"],
  "score_minimum_vise": {min(scores.get("global", 5) + 1.5, 9.0)},
  "instructions_patcher": "3-4 phrases : ordre des corrections, risques à éviter, validation attendue",
  "module_principal_a_corriger": "module le plus problématique ou null",
  "blocage_critique": false,
  "raison_blocage": ""
}}"""

    result = _call(prompt)

    # Sécurité : ne pas bloquer si le score global est déjà bon
    if scores.get("global", 0) >= 7.0 and result.get("blocage_critique"):
        result["blocage_critique"] = False
        result["raison_blocage"] = ""

    nb_corrections = len(result.get("corrections_prioritaires", []))
    phase5_log.agent_done(
        "Diagnosticien",
        f"{nb_corrections} corrections identifiees, probleme principal: {result.get('probleme_principal', '?')[:60]}"
    )
    return result


# _sample_code remplacé par utils.extract_js_sample


@with_fallback({
    "probleme_principal": "Analyse indisponible",
    "corrections_prioritaires": [],
    "a_absolument_preserver": [],
    "score_minimum_vise": 7.5,
    "instructions_patcher": "Améliorer le gameplay et les visuels.",
    "module_principal_a_corriger": None,
    "blocage_critique": False,
})
def _call(prompt: str) -> dict:
    # I12 : max_tokens élevé explicitement pour éviter JSON tronqué sur gros bundles d'issues
    return call_gemini_paid_json(prompt, temperature=0.3, system_instruction=SYSTEM,
                                 max_tokens=32000, disable_thinking=True)

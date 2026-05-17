"""
Code Validator — automatic validation and fixes without LLM.
Applies programmatic corrections to the generated JS code.

Public API:
    validate_and_fix(html: str) -> tuple[str, list[str], bool]
        - fixed_html    : HTML with applied corrections
        - issues        : list of "[AUTO-FIX] ..." and "CRITICAL: ..." strings
        - has_critical  : True if critical issues remain
"""

import re
import os
import json

from logger import coordinateur_log

# ─────────────────────────────────────────────────────────────
# COMMON_VARS — Variables globales fréquemment utilisées sans déclaration
# Clé = nom de variable, Valeur = valeur initiale JS
# ─────────────────────────────────────────────────────────────
COMMON_VARS: dict[str, str] = {
    # État global du jeu
    'score': '0',
    'lives': '3',
    'level': '1',
    'gameOver': 'false',
    'paused': 'false',
    'gameTime': '0',
    'currentLevel': '0',
    'currentPhase': '0',
    'bestScore': '0',

    # Entités
    'player': 'null',
    'boss': 'null',
    'enemies': '[]',
    'bullets': '[]',
    'particles': '[]',
    'items': '[]',
    'rooms': '[]',
    'map': '[]',
    'floatingTexts': '[]',
    'projectiles': '[]',
    'lootItems': '[]',
    'platforms': '[]',

    # Rendu
    'canvas': 'null',
    'ctx': 'null',
    'offscreen': 'null',
    'gctx': 'null',

    # Inputs
    'keys': '{}',
    'mouse': '{ x: 0, y: 0, clicked: false }',

    # Timing
    'dt': '0',
    'lastTime': '0',
    'animId': 'null',

    # Lookup / calculs intermédiaires
    'closest': 'null',
    'targetEnemy': 'null',
    'hit': 'false',
    'found': 'false',
    'angle': '0',
    'dx': '0',
    'dy': '0',
    'dist': '0',
    'distToPlayer': '0',
    'bullet': 'null',

    # Stats / progression
    'gold': '0',
    'xp': '0',
    'combo': '0',
    'wave': '0',
    'dmg': '0',
    'upgrade': 'null',
    'classId': 'null',
    'critChance': '0',
    'critMult': '1',
    'attempts': '0',

    # Effets visuels
    'shakeTimer': '0',
    'shakeMag': '0',
    'shakeTime': '0',
    'flashTimer': '0',
    'hitstopTimer': '0',

    # Caméra / positionnement
    'cameraX': '0',
    'cameraY': '0',
    'currentX': '0',
    'currentY': '0',

    # Gameplay divers
    'gameSpeedMultiplier': '1',
    'baseHealth': '0',

    # Tower defense
    'selectedTower': 'null',
    'hoveredTower': 'null',
    'placingTower': 'null',
    'selectedCell': 'null',
    'waveTimer': '0',

    # Platformer / action
    'facing': '1',
    'dashTimer': '0',
    'dashCooldown': '0',
    'dashCooldownTimer': '0',
    'dashDirectionX': '0',
    'dashDirectionY': '0',
    'coyoteTime': '0',
    'fireCooldown': '0',
    'chargeTimer': '0',
    'dashInvulnTimer': '0',
    'charIndex': '0',
    'dash_pressed': 'null',
    'attack_pressed': 'null',
    'invincible': 'false',
    'invincibleTimer': '0',

    # Mouvements ennemis / IA
    'moveX': '0',
    'moveY': '0',
    'currentLevelMap': '[]',
    'currentLevelIndex': '0',

    # États booléens courants
    'active': 'false',
    'clicked': 'null',
    'attack': 'null',
    'sfx': 'null',

    # Tower Defense — entités et config spécifiques (Session 4)
    'grid': '[]',
    'towers': '[]',
    'waveEnemies': '[]',
    'path': '[]',
    'pathNodes': '[]',
    'currentMoney': '100',
    'waveNumber': '0',
    'enemiesAlive': '0',
    'towerType': 'null',
    'CELL_SIZE': '40',

    # Platformer / adventure
    'gravity': '900',
    'currentRoom': '0',
    'mapData': '[]',
    'tilemap': '[]',
    'coins': '0',

    # RPG / dialogue
    'npcs': '[]',
    'quests': '[]',
    'dialogueActive': 'false',
    'currentDialogue': 'null',
    'selectedOption': '0',
    'npc': 'null',
    'option': 'null',
    'questId': 'null',

    # Shooter — power-ups / boss
    'powerups': '[]',
    'bossActive': 'false',
    'currentWave': '0',
    'waveDelay': '3',
    'waveProgress': '0',

    # Timers manquants (vus systématiquement dans les logs d'échec)
    'slowTimer': '0',
    'fireTimer': '0',
    'shootTimer': '0',
    'spawnTimer': '0',
    'bossTimer': '0',
    'hitTimer': '0',
    'invulnTimer': '0',
    'deathTimer': '0',
    'levelTimer': '0',
    'respawnTimer': '0',
    'comboTimer': '0',
    'shieldTimer': '0',
    'reloadTimer': '0',
    'staggerTimer': '0',
    'phaseTimer': '0',
    'transitionTimer': '0',
    'multiplierTimer': '0',
    'doubleTimer': '0',
    'speedBoostTimer': '0',
    'bombTimer': '0',
    'freezeTimer': '0',
    'rageTimer': '0',
    'stunTimer': '0',
    'multiplier': '1',
    'highScore': '0',
    'powerUps': '[]',
    'bossPhase': '0',
    'scrollSpeed': '1',
    'scrollY': '0',
    'gridSize': '50',
    'offset': '0',
    'waveAnnounce': '0',
    'waveAnnounceTxt': '""',
    'bulletPool': '[]',
    'shieldActive': 'false',

    # Variables intermédiaires — évitent ReferenceError dans les boucles
    'def': 'null',
    'action': 'null',
    'target': 'null',
    'current': 'null',
    'selected': 'null',
    'power': '0',
    'range': '0',
    'cost': '0',

    # Canvas dimensions — injected if missing (W/H no longer assumed always declared)
    'W': 'window.innerWidth',
    'H': 'window.innerHeight',

    # Fixed timestep game loop — CRITICAL: wrong defaults break the loop entirely
    'MAX_DT':      '0.1',        # cap delta-time cap — NEVER 0 (infinite loop)
    'FIXED_DT':    '1/60',       # fixed physics timestep
    'accumulator': '0',          # timestep accumulator

    # Spatial constants
    'TILE':   '32',              # tile size default
    'cam':    '{x:0,y:0}',      # camera default
    'center': 'null',

    # Common gameplay intermediates missing from COMMON_VARS
    'damage': '0',
    'room':   'null',
}

# Fichier de variables apprises dynamiquement par auto_learner
_LEARNED_VARS_FILE = os.path.join(os.path.dirname(__file__), "learned_vars.json")
_MIN_LEARNED_COUNT = 2   # Nb minimum de jeux pour qu'une var soit auto-injectée

# ─────────────────────────────────────────────────────────────
# STUBS — Fonctions fréquemment appelées mais non définies
# ─────────────────────────────────────────────────────────────
_STUBS: dict[str, str] = {
    'drawFloatingTexts': (
        'function drawFloatingTexts(ctx) {\n'
        '  if (!floatingTexts || !floatingTexts.length) return;\n'
        '  for (let i = floatingTexts.length - 1; i >= 0; i--) {\n'
        '    const ft = floatingTexts[i];\n'
        '    if (ft.life !== undefined) ft.life -= 0.016; else ft.ttl = (ft.ttl || 1) - 0.016;\n'
        '    const alive = ft.life !== undefined ? ft.life > 0 : ft.ttl > 0;\n'
        '    if (!alive) { floatingTexts.splice(i, 1); continue; }\n'
        '    ctx.save();\n'
        '    ctx.globalAlpha = Math.max(0, ft.life !== undefined ? ft.life : ft.ttl);\n'
        '    ctx.fillStyle = ft.color || \'#fff\';\n'
        '    ctx.font = (ft.size || 12) + \'px sans-serif\';\n'
        '    ctx.textAlign = \'center\';\n'
        '    ctx.fillText(ft.text || \'\', ft.x, ft.y);\n'
        '    ctx.restore();\n'
        '  }\n'
        '}'
    ),
    'drawParticles': (
        'function drawParticles(ctx) {\n'
        '  if (!particles || !particles.length) return;\n'
        '  for (let i = particles.length - 1; i >= 0; i--) {\n'
        '    const p = particles[i];\n'
        '    if (p.life !== undefined) p.life -= 0.016; else p.ttl = (p.ttl || 1) - 0.016;\n'
        '    const alive = p.life !== undefined ? p.life > 0 : p.ttl > 0;\n'
        '    if (!alive) { particles.splice(i, 1); continue; }\n'
        '    p.x += (p.vx || 0) * 0.016;\n'
        '    p.y += (p.vy || 0) * 0.016;\n'
        '    ctx.save();\n'
        '    ctx.globalAlpha = Math.max(0, p.life !== undefined ? p.life : p.ttl);\n'
        '    ctx.fillStyle = p.color || \'#fff\';\n'
        '    const sz = p.size || p.r || 3;\n'
        '    ctx.fillRect(p.x - sz / 2, p.y - sz / 2, sz, sz);\n'
        '    ctx.restore();\n'
        '  }\n'
        '}'
    ),
    'spawnFloatingText': (
        'function spawnFloatingText(x, y, text, color, size) {\n'
        '  if (!floatingTexts) return;\n'
        '  floatingTexts.push({ x: x, y: y, text: text, color: color || \'#fff\', '
        'size: size || 12, life: 1.0 });\n'
        '}'
    ),
    'updateParticles': (
        'function updateParticles(dt) {\n'
        '  if (!particles) return;\n'
        '  for (let i = particles.length - 1; i >= 0; i--) {\n'
        '    const p = particles[i];\n'
        '    p.x += (p.vx || 0) * dt;\n'
        '    p.y += (p.vy || 0) * dt;\n'
        '    if (p.life !== undefined) p.life -= dt;\n'
        '    else p.ttl = (p.ttl || 1) - dt;\n'
        '    const alive = p.life !== undefined ? p.life > 0 : p.ttl > 0;\n'
        '    if (!alive) particles.splice(i, 1);\n'
        '  }\n'
        '}'
    ),
    'spawnParticles': (
        'function spawnParticles(x, y, color, count) {\n'
        '  if (!particles) return;\n'
        '  for (let i = 0; i < (count || 5); i++) {\n'
        '    const a = Math.random() * Math.PI * 2;\n'
        '    const sp = 50 + Math.random() * 100;\n'
        '    particles.push({ x: x, y: y, vx: Math.cos(a)*sp, vy: Math.sin(a)*sp,\n'
        '      color: color || \'#fff\', size: 2 + Math.random()*3, life: 0.5 + Math.random()*0.5 });\n'
        '  }\n'
        '}'
    ),
    'fadeOut': (
        'function fadeOut(speed, onDone) {\n'
        '  if (typeof onDone === \'function\') onDone();\n'
        '}'
    ),
    'fadeIn': (
        'function fadeIn(speed, onDone) {\n'
        '  if (typeof onDone === \'function\') onDone();\n'
        '}'
    ),
    'fadeScreen': (
        'function fadeScreen(alpha, color) { /* stub */ }'
    ),
    'transitionTo': (
        'function transitionTo(newState) {\n'
        '  if (typeof gameState !== \'undefined\') gameState = newState;\n'
        '}'
    ),
}

# Méthodes d'objet sfx manquantes — patchées directement dans l'objet sfx existant
_SFX_MISSING_METHODS = ['init', 'stop', 'pause', 'resume', 'load', 'setVolume']


def _fix_sfx_missing_methods(script: str) -> tuple[str, list[str]]:
    """
    Détecte les appels sfx.X() pour des méthodes non définies dans l'objet sfx.
    Injecte les méthodes manquantes comme no-ops dans l'objet sfx existant.
    """
    import re as _re
    fixes = []

    # Trouver les méthodes sfx appelées
    called = set(_re.findall(r'\bsfx\.(\w+)\s*\(', script))
    if not called:
        return script, fixes

    # Trouver le contenu de l'objet sfx déclaré
    sfx_match = _re.search(r'\bsfx\s*=\s*\{([^}]{1,2000})\}', script, _re.DOTALL)
    if not sfx_match:
        return script, fixes

    sfx_body = sfx_match.group(1)
    # Méthodes déjà définies dans l'objet
    defined = set(_re.findall(r'\b(\w+)\s*\(', sfx_body))

    missing = [m for m in called if m not in defined and m in _SFX_MISSING_METHODS]
    if not missing:
        return script, fixes

    # Injecter les méthodes manquantes dans l'objet sfx
    inject = ', '.join(f'{m}(){{}}' for m in sorted(missing))
    new_sfx_body = sfx_body.rstrip().rstrip(',') + ', ' + inject
    script = script[:sfx_match.start(1)] + new_sfx_body + script[sfx_match.end(1):]
    fixes.append(f'[AUTO-FIX] sfx : méthodes manquantes injectées : {", ".join(sorted(missing))}')
    return script, fixes


# ─────────────────────────────────────────────────────────────
# FIX — Timers non initialisés dans les push d'ennemis/boss
# ─────────────────────────────────────────────────────────────

def _fix_enemy_timer_init(script: str) -> tuple[str, list[str]]:
    """
    Détecte les propriétés *Timer utilisées sur des objets ennemis/boss
    mais non initialisées dans les appels enemies.push({...}) ou boss={...}.
    Injecte les timers à 0 dans chaque objet factory incomplet.

    Exemple:
    ❌ enemies.push({ x, y, hp, speed })  ← chargeTimer, shootTimer absents
    ✅ enemies.push({ x, y, hp, speed, fireTimer: 0, chargeTimer: 0, shootTimer: 0 })
    """
    import re
    fixes = []

    # Trouver tous les *Timer utilisés dans le script (en.X, boss.X, enemy.X)
    timer_props_used = set(re.findall(
        r'(?:en|enemy|boss|mob|unit|e)\s*\.\s*(\w*[Tt]imer\w*)',
        script
    ))
    if not timer_props_used:
        return script, fixes

    # Pour chaque bloc enemies.push({ ... }) ou boss = { ... }
    # détecter les timers absents et les ajouter
    def _patch_object_literal(m: re.Match) -> str:
        obj_content = m.group(1)
        # propriétés déjà présentes dans cet objet
        present = set(re.findall(r'\b(\w+)\s*:', obj_content))
        missing_timers = [t for t in timer_props_used if t not in present]
        if not missing_timers:
            return m.group(0)
        inject = ', '.join(f'{t}: 0' for t in sorted(missing_timers))
        # Insérer avant la dernière accolade fermante
        new_content = obj_content.rstrip()
        if new_content.endswith(','):
            new_content += f' {inject}'
        else:
            new_content += f', {inject}'
        fixes.append(f'[AUTO-FIX] timers injectés dans push ennemi : {", ".join(sorted(missing_timers))}')
        return m.group(0).replace(obj_content, new_content, 1)

    # Matcher enemies.push({ ... }) sur une seule ligne (patterns courants)
    pattern = re.compile(
        r'(?:enemies|mobs|units|ennemis)\.push\(\s*(\{[^{}]{10,300}\})\s*\)',
        re.DOTALL
    )
    script = pattern.sub(_patch_object_literal, script)

    return script, fixes


# ─────────────────────────────────────────────────────────────
# FIX — Stubs playSound vides → implémentation WebAudio minimale
# ─────────────────────────────────────────────────────────────

def _fix_empty_playsound_stub(script: str) -> tuple[str, list[str]]:
    """
    Remplace les stubs vides `function playSound(...) {}` par une vraie
    implémentation WebAudio minimale. Un stub vide = sons absents en jeu.
    """
    # Détecter un stub playSound (corps vide ou avec juste un commentaire)
    stub_pattern = re.compile(
        r'(function\s+playSound\s*\([^)]*\)\s*\{)\s*(?://[^\n]*)?\s*(\})',
        re.MULTILINE
    )
    m = stub_pattern.search(script)
    if not m:
        return script, []

    # Vérifier que c'est vraiment un stub (corps vide ou 1 ligne)
    body = script[m.start(1) + len(m.group(1)):m.start(2)]
    if len(body.strip()) > 50:  # Corps déjà substantiel → pas un stub
        return script, []

    implementation = (
        "function playSound(freq, dur, type) {\n"
        "  try {\n"
        "    var ac = new (window.AudioContext || window.webkitAudioContext)();\n"
        "    var o = ac.createOscillator();\n"
        "    var g = ac.createGain();\n"
        "    o.connect(g); g.connect(ac.destination);\n"
        "    o.type = type || 'square';\n"
        "    o.frequency.value = freq || 440;\n"
        "    g.gain.setValueAtTime(0.3, ac.currentTime);\n"
        "    g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + (dur || 0.1));\n"
        "    o.start(); o.stop(ac.currentTime + (dur || 0.1));\n"
        "  } catch(e) {}\n"
        "}"
    )
    new_script = stub_pattern.sub(implementation, script, count=1)
    return new_script, ['[AUTO-FIX] playSound stub vide → implémentation WebAudio minimale']


# ─────────────────────────────────────────────────────────────
# ENGINE GUARD — remove null-overrides of sacred ENGINE globals
# ─────────────────────────────────────────────────────────────

# Variables declared by the ENGINE header — redeclaring them as null/0 kills the game
_ENGINE_SACRED = frozenset({
    'canvas', 'ctx', 'W', 'H', 'DPR', 'gameState', 'lastTime',
    'accumulator', 'Keys', 'Touch', 'Mouse',
})

_NULL_VALUES = r'(?:null|0|undefined|false|\'\'|"")'

# Build a single pattern that matches  var/let/const {name} = null/0/etc;
_SACRED_NULL_PAT = re.compile(
    r'(?m)^[ \t]*(?:var|let|const)\s+(?P<name>'
    + '|'.join(re.escape(n) for n in sorted(_ENGINE_SACRED))
    + r')\s*=\s*' + _NULL_VALUES + r'\s*;[ \t]*(?://[^\n]*)?\n',
)


def _sanitize_engine_globals(html: str) -> tuple[str, list[str]]:
    """
    Remove ENGINE-sacred variable redeclarations that crash the game:

    1. `var/let/const {sacred_name} = null/0/undefined` anywhere — overwrites ENGINE setup.
    2. `const/let {sacred_name} = <any value>` INSIDE a function body (depth > 0) —
       creates TDZ that makes every upstream reference in the same function throw
       "Cannot access 'X' before initialization". Classic case: LLM adds
       `const ctx = canvas.getContext('2d')` inside a draw function thinking ctx
       isn't in scope, but the ENGINE already declared it at module level.
    """
    fixes: list[str] = []

    if (
        "document.getElementById('gameCanvas')" not in html
        and 'getContext' not in html
    ):
        return html, []

    # Pass 1 — remove null/0/undefined assignments anywhere (existing rule)
    def _replace_null(m):
        name = m.group('name')
        fixes.append(f'[ENGINE GUARD] var {name} = null/0 removed — already declared in ENGINE')
        return ''

    new_html = _SACRED_NULL_PAT.sub(_replace_null, html)

    # Pass 2 — remove const/let sacred redeclarations inside function bodies (TDZ fix)
    # Extract the JS script section for depth tracking
    script_match = re.search(r'<script(?:\s[^>]*)?>(.+?)</script>', new_html, re.DOTALL | re.IGNORECASE)
    if not script_match:
        return new_html, fixes

    script = script_match.group(1)
    lines = script.split('\n')
    to_remove: set[int] = set()
    depth = 0
    in_str = False
    str_char = ''

    inner_decl_pat = re.compile(
        r'^[ \t]*(?:let|const)\s+(?P<name>' + '|'.join(re.escape(n) for n in sorted(_ENGINE_SACRED)) + r')\s*='
    )

    for i, line in enumerate(lines):
        for ch in line:
            if in_str:
                if ch == str_char:
                    in_str = False
                continue
            if ch in ('"', "'", '`'):
                in_str = True; str_char = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth - 1)
        if depth > 0:
            m = inner_decl_pat.match(line)
            if m:
                to_remove.add(i)
                fixes.append(
                    f'[ENGINE GUARD] const/let {m.group("name")} inside function removed — '
                    f'TDZ shadow of ENGINE module-level declaration'
                )

    if to_remove:
        cleaned = '\n'.join(ln for i, ln in enumerate(lines) if i not in to_remove)
        new_html = new_html[:script_match.start(1)] + cleaned + new_html[script_match.end(1):]

    return new_html, fixes


# ─────────────────────────────────────────────────────────────

def check_fill_placeholders(html: str) -> list[str]:
    """
    Detects remaining [FILL: ...] placeholders in the JS section of the generated game.
    Returns a list of placeholder labels found, or [] if the output is clean.
    A non-empty list means the LLM did not finish filling the template.
    """
    scripts = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
    if not scripts:
        return []
    js = max(scripts, key=len)
    return re.findall(r'\[FILL:\s*([^\]]+)\]', js)


def validate_and_fix(html: str) -> tuple[str, list[str], bool]:
    """
    Applique des corrections programmatiques sans LLM.
    Retourne (html_corrigé, issues_list, has_critical).

    issues contient des strings "[AUTO-FIX] ..." (corrections appliquées)
    et "CRITIQUE: ..." (problèmes persistants).
    has_critical = True si des mots-clés critiques sont présents dans issues.
    """
    if not html:
        return html or '', ['CRITIQUE: Code vide — aucun HTML généré'], True

    issues: list[str] = []

    # ── [FILL:] PLACEHOLDER CHECK — must run before Playwright ──────────────
    _remaining_fills = check_fill_placeholders(html)
    if _remaining_fills:
        labels = ', '.join(f'[FILL: {f}]' for f in _remaining_fills[:6])
        issues.append(
            f'CRITIQUE: {len(_remaining_fills)} [FILL:] placeholder(s) not replaced by LLM — '
            f'game will crash or be incomplete. Unfilled: {labels}'
        )

    # ── ENGINE GUARD: remove null-overrides of sacred globals (first, before anything else) ──
    html, engine_fixes = _sanitize_engine_globals(html)
    issues.extend(engine_fixes)

    # ── Vérification : présence d'un bloc <script> ──
    if '<script' not in html.lower():
        issues.append('CRITIQUE: Aucun bloc <script> trouvé dans le HTML généré')
        _log_results(issues)
        return html, issues, True

    # ── Extraction du script principal (le plus long, hors CDN src= et polyfills) ──
    # For 3D games: CDN <script src=>, polyfill <script>, then game <script>.
    # Picking the first block would target the polyfill, causing false positives
    # ("boucle de jeu manquante") and injecting RAF into the wrong block.
    _all_sm = list(re.finditer(
        r'(<script(?:\s[^>]*)?>)(.*?)(</script>)',
        html, re.DOTALL | re.IGNORECASE
    ))
    _valid_sm = [
        m for m in _all_sm
        if not re.search(r'\bsrc\s*=', m.group(1), re.IGNORECASE)
        and len(m.group(2).strip()) > 50
        and '// Polyfill' not in m.group(2)[:200]
    ]
    if not _valid_sm:
        issues.append('CRITIQUE: Aucun bloc <script> valide trouvé dans le HTML')
        _log_results(issues)
        return html, issues, True
    script_match = max(_valid_sm, key=lambda m: len(m.group(2)))

    prefix = html[:script_match.start(2)]
    script = script_match.group(2)
    suffix = html[script_match.end(2):]

    if len(script.strip()) < 200:
        issues.append('CRITIQUE: Bloc <script> trop court — code vide ou tronqué')
        _log_results(issues)
        return html, issues, True

    # ── Applications des correctifs dans l'ordre ──
    original_script = script

    # Gradient safety patch — prepended once, before any other transformation
    script, grad_fixes = _inject_gradient_safety(script)
    issues.extend(grad_fixes)

    script, for_const_fixes = _fix_for_const_loop(script)
    issues.extend(for_const_fixes)

    script, switch_const_fixes = _fix_const_in_switch_cases(script)
    issues.extend(switch_const_fixes)

    script, const_fixes = _fix_const_reassignments(script)
    issues.extend(const_fixes)

    script, draw_local_fixes = _fix_undeclared_draw_locals(script)
    issues.extend(draw_local_fixes)

    # ── Injection checkpoint: two independent groups so stubs survive var-injection failure ──
    try:
        from js_syntax_checker import check_and_report as _chk_inject
    except Exception:
        _chk_inject = lambda h: ([], False)  # noqa: E731

    # Group A: variable declarations (W/H/common vars) — may fail on template route
    _script_pre_vars = script
    _var_fixes_tentative, _gs_fixes_tentative = [], []
    _script_with_vars, _var_fixes_tentative = _fix_undeclared_common_vars(script)
    _script_with_vars, _gs_fixes_tentative = _fix_gamestateflow(_script_with_vars)
    _, _vars_broken = _chk_inject(prefix + _script_with_vars + suffix)
    if _vars_broken:
        issues.append('[SKIPPED var-injection] broke syntax — reverted (W/H not injected)')
    else:
        script = _script_with_vars
        issues.extend(_var_fixes_tentative)
        issues.extend(_gs_fixes_tentative)

    # Group B: stub functions — runs independently even if Group A failed
    _script_pre_stubs = script
    _script_with_stubs, stub_fixes = _inject_missing_stubs(script)
    _, _stubs_broken = _chk_inject(prefix + _script_with_stubs + suffix)
    if _stubs_broken:
        issues.append('[SKIPPED stub-injection] broke syntax — reverted')
    else:
        script = _script_with_stubs
        issues.extend(stub_fixes)

    script, handler_fixes = _fix_no_args_handlers_in_gameloop(script)
    issues.extend(handler_fixes)

    # B4b: inject missing calls for update*/draw* functions not called from game loop
    script, gameloop_call_fixes = _fix_missing_gameloop_calls(script)
    issues.extend(gameloop_call_fixes)

    script, type_name_fixes = _fix_type_vs_name_property(script)
    issues.extend(type_name_fixes)

    script, spawnplayer_fixes = _fix_spawnplayer_missing_dimensions(script)
    issues.extend(spawnplayer_fixes)

    script, spawn_fixes = _fix_spawn_missing_typeindex(script)
    issues.extend(spawn_fixes)

    script, draw_loop_fixes = _fix_draw_loop_missing_element_var(script)
    issues.extend(draw_loop_fixes)

    script, arrow_fixes = _fix_arrow_key_mapping(script)
    issues.extend(arrow_fixes)

    script, boss_fixes = _fix_boss_defs_access(script)
    issues.extend(boss_fixes)

    script, raf_fixes = _fix_missing_raf_in_domready(script)
    issues.extend(raf_fixes)

    script, si_fixes = _fix_setinterval_raf_parallel(script)
    issues.extend(si_fixes)

    script, splice_fixes = _fix_for_of_splice(script)
    if splice_fixes:
        issues.append(f'[AUTO-FIX] {splice_fixes} boucle(s) for-of avec splice → itération sur copie [...arr]')

    script, forin_fixes = _fix_forin_missing_assignment(script)
    issues.extend(forin_fixes)

    script, trailing_count = _fix_trailing_commas(script)
    if trailing_count:
        issues.append(f'[AUTO-FIX] {trailing_count} virgule(s) trailing supprimée(s) dans objets/tableaux')

    # K3 — Rollback partiel : si _dedup_declarations casse la syntaxe, annuler uniquement la dédup
    script_before_dedup = script
    script, dedup_count = _dedup_declarations(script)
    if dedup_count:
        _test_html_dedup = prefix + script + suffix
        try:
            from js_syntax_checker import check_and_report as _chk_dedup
            _dedup_issues, _dedup_broken = _chk_dedup(_test_html_dedup)
        except Exception:
            _dedup_broken = False
        if _dedup_broken:
            script = script_before_dedup
            issues.append(f'[SKIPPED] {dedup_count} redéclaration(s) — rollback (syntaxe cassée après dédup)')
        else:
            issues.append(f'[AUTO-FIX] {dedup_count} redéclaration(s) de variable(s) supprimée(s) → déduplication')

    script, timer_fixes = _fix_enemy_timer_init(script)
    issues.extend(timer_fixes)

    script, forindex_fixes = _fix_forindex_missing_element(script)
    issues.extend(forindex_fixes)

    script, stub_fixes = _fix_empty_playsound_stub(script)
    issues.extend(stub_fixes)

    script, sfx_fixes = _fix_sfx_missing_methods(script)
    issues.extend(sfx_fixes)

    script, eval_fixed = _fix_eval_in_production(script)
    if eval_fixed:
        issues.append('[AUTO-FIX] Patch de débogage window.__dev supprimé (eval en production)')

    script, ext_fixes = _fix_external_resources(script)
    issues.extend(ext_fixes)

    # ── Fix canvas setup manquant AVANT les diagnostics ──
    script, canvas_fixes = _fix_missing_canvas_setup(script)
    issues.extend(canvas_fixes)

    # ── Fix accolades orphelines — DÉSACTIVÉ (K2) ──
    # _fix_orphan_closing_braces supprime des } légitimes quand _dedup_declarations
    # retire des lignes avec { implicite → Unexpected end of input en cascade.
    # Le rollback dans _layer_gen.py gère le code cassé sans ce nettoyage agressif.
    # brace_diag = _fix_orphan_closing_braces(script)[1]  # diagnostic uniquement si besoin

    # ── Fix crochets orphelins ──
    script, bracket_fixes = _fix_orphan_closing_brackets(script)
    issues.extend(bracket_fixes)

    # ── Checks diagnostiques (pas de fix, juste signalement) ──
    has_critical = False
    diag = _diagnostic_checks(script)
    issues.extend(diag)
    if any('CRITIQUE' in i for i in diag):
        has_critical = True

    _log_results(issues)

    if script == original_script:
        return html, issues, has_critical

    return prefix + script + suffix, issues, has_critical


# ─────────────────────────────────────────────────────────────
# FIX 0a — for(const X = …) → for(let X = …)
# ─────────────────────────────────────────────────────────────

def _fix_for_const_loop(script: str) -> tuple[str, list[str]]:
    """
    Convertit for(const X = N; ...) en for(let X = N; ...).
    `const` dans un for classique avec incrémentation est une SyntaxError.
    Ne touche PAS à for(const X of ...) qui est valide.
    """
    fixes: list[str] = []
    pattern = re.compile(r'\bfor\s*\(\s*const\s+(\w+)\s*=')

    def repl(m: re.Match) -> str:
        fixes.append(
            f"[AUTO-FIX] for(const {m.group(1)}=...) → for(let {m.group(1)}=...) (évite SyntaxError)"
        )
        return f'for (let {m.group(1)} ='

    new_script = pattern.sub(repl, script)
    return new_script, fixes


# ─────────────────────────────────────────────────────────────
# FIX 0b — const/let en tête de case/default → var
# ─────────────────────────────────────────────────────────────

def _fix_const_in_switch_cases(script: str) -> tuple[str, list[str]]:
    """
    Convertit `const`/`let` en `var` lorsqu'ils apparaissent comme premier statement
    d'un bloc case/default sans accolades propres.
    Ex:  case 'play':\n    const x = 5;  →  case 'play':\n    var x = 5;
    Évite SyntaxError: Unexpected token 'const' dans les switch statements.
    """
    fixes: list[str] = []
    # Match: case X: ou default: → saut de ligne + indentation → const|let
    # On s'assure qu'il n'y a PAS de { entre le : et le const (pas de bloc explicite).
    pattern = re.compile(
        r'((?:case\s[^:{\n]+|default)\s*:)([ \t]*\n[ \t]*)(const|let)\b',
        re.MULTILINE
    )

    def replace(m: re.Match) -> str:
        between = m.group(2)
        if '{' in between:
            return m.group(0)  # bloc déjà présent — ne pas toucher
        kw = m.group(3)
        fixes.append(
            f"[AUTO-FIX] `{kw}` après case/default sans accolades → `var` (évite SyntaxError)"
        )
        return m.group(1) + between + 'var'

    new_script = pattern.sub(replace, script)
    return new_script, fixes


# ─────────────────────────────────────────────────────────────
# FIX 1 — const réassignés → let
# ─────────────────────────────────────────────────────────────

def _fix_const_reassignments(script: str) -> tuple[str, list[str]]:
    """
    Détecte les `const X` qui sont réassignés ailleurs et les convertit en `let`.
    Détecte : X = , X +=, X -=, X *=, X /=, X++, X--
    Évite les TypeError "Assignment to constant variable".
    """
    fixes: list[str] = []

    # Trouver tous les const de noms en camelCase/minuscules (pas les constantes SCREAMING_CASE)
    const_names = re.findall(r'\bconst\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=', script)
    if not const_names:
        return script, fixes

    # Travailler sur le script nettoyé (sans chaînes ni commentaires)
    stripped = _strip_strings_comments(script)

    # Pattern d'assignation (tout type) : X =, X +=, X -=, X++, X--
    # Capture uniquement les usages NON précédés d'un identifiant ou '.'
    _assign_re = re.compile(
        r'(?<![.\w])\b({name})\s*'
        r'(?:\+\+|--|(?:[+\-*/%|&^]=)|(?<!\=)=(?!=)(?!>))'
    )

    for name in set(const_names):
        if name.isupper() and len(name) > 2:
            continue  # CONSTANTES légitimes
        if len(name) <= 1:
            continue  # vars de boucle courantes

        pattern = re.compile(
            rf'(?<![.\w])\b{re.escape(name)}\s*'
            r'(?:\+\+|--|(?:[+\-*/%|&^]=)|=(?!=)(?!>))'
        )

        # Trouver toutes les positions d'assignation dans le code nettoyé
        reassigned = False
        for m in pattern.finditer(stripped):
            pos = m.start()
            # Regarder ce qui précède immédiatement (dans un rayon de 12 chars)
            pre = stripped[max(0, pos - 12):pos]
            # Si précédé par const/let/var + espaces → c'est la déclaration, pas une réassignation
            if re.search(r'\b(?:const|let|var)\s*$', pre):
                continue
            # Sinon → c'est une réassignation
            reassigned = True
            break

        if reassigned:
            new_script = re.sub(
                rf'\bconst\s+({re.escape(name)}\s*=)',
                rf'let \1',
                script, count=1
            )
            if new_script != script:
                script = new_script
                fixes.append(f'[AUTO-FIX] const \'{name}\' réassigné → converti en let (évite TypeError)')

    return script, fixes


# ─────────────────────────────────────────────────────────────
# FIX 2 — Variables communes non déclarées
# ─────────────────────────────────────────────────────────────

def _fix_undeclared_draw_locals(script: str) -> tuple[str, list[str]]:
    """
    Détecte les variables locales utilisées dans les fonctions draw*/update* sans déclaration.
    Pattern récurrent : L9 réécrit drawBackground/drawEnemies/drawBoss en utilisant des `var`
    qui étaient locales dans la version L6 (hpRatio, barX, barWidth, alpha, gradient, radius...).
    Injecte `var x = default;` au début du corps de chaque fonction concernée.
    """
    fixes: list[str] = []

    # Vars typiquement locales aux fonctions draw — avec leur valeur par défaut
    _DRAW_LOCALS: dict[str, str] = {
        'hpRatio': '1', 'hpPct': '1', 'ratio': '1', 'pct': '1',
        'barX': '0', 'barY': '0', 'barWidth': '0', 'barHeight': '6',
        'barColor': '"#00ff00"',
        'alpha': '1', 'opacity': '1',
        'gradient': 'null', 'grad': 'null', 'gradBoss': 'null',
        'glowSize': '0', 'pulse': '0',
        'radius': '0', 'scale': '1',
        'gradX': '0', 'gradY': '0',
        'offsetX': '0', 'offsetY': '0',
        'wobble': '0', 'bounce': '0',
        'brightness': '1', 'saturation': '1',
        'frameX': '0', 'frameY': '0',
    }

    # Trouver toutes les fonctions draw* et update*
    func_pattern = re.compile(r'\bfunction\s+((?:draw|update|render)\w*)\s*\(([^)]*)\)\s*\{')
    result = script
    offset = 0  # décalage cumulatif après injections

    for m in func_pattern.finditer(script):
        fname = m.group(1)
        params_str = m.group(2)
        params = {p.strip() for p in params_str.split(',') if p.strip()}

        # Extraire le corps de la fonction
        body_start = m.end()
        depth = 1
        i = body_start
        while i < len(script) and depth > 0:
            if script[i] == '{':
                depth += 1
            elif script[i] == '}':
                depth -= 1
            i += 1
        body = script[body_start:i - 1]

        # Vars déclarées dans le corps
        declared = params.copy()
        declared |= set(re.findall(r'\bvar\s+(\w+)', body))
        declared |= set(re.findall(r'\blet\s+(\w+)', body))
        declared |= set(re.findall(r'\bconst\s+(\w+)', body))

        # Vars utilisées mais non déclarées
        to_inject = []
        for vname, vdefault in _DRAW_LOCALS.items():
            if vname in declared:
                continue
            if not re.search(r'\b' + re.escape(vname) + r'\b', body):
                continue
            to_inject.append((vname, vdefault))

        if not to_inject:
            continue

        inject_str = ''.join(f'  var {n} = {v};\n' for n, v in to_inject)
        # Injecter juste après l'accolade ouvrante de la fonction
        insert_pos = m.end() + offset
        result = result[:insert_pos] + '\n' + inject_str + result[insert_pos:]
        offset += len('\n' + inject_str)
        fixes.append(
            f'[AUTO-FIX] {fname}(): {len(to_inject)} var(s) locales injectées '
            f'({", ".join(n for n, _ in to_inject)})'
        )

    return result, fixes


def _fix_draw_loop_missing_element_var(script: str) -> tuple[str, list[str]]:
    """
    Corrige le pattern drawEnemies/drawBullets/drawParticles/drawPowerUps où le for-loop
    itère sur un tableau avec `for (var i = 0; ...)` mais utilise `e.x` / `e.hp` sans
    déclarer `var e = array[i]` dans le corps.

    Symptôme : 'e is not defined' au runtime dans drawEnemies.
    Cause : L9 réécrit drawEnemies en utilisant `e` (copié depuis updateEnemies) sans
    ajouter `var e = enemies[i]`.
    """
    fixes = []

    # Table (nom de fonction → tableau qu'elle itère → variable d'itération)
    _DRAW_LOOPS = [
        (r'drawEnemy(?:ies)?',    'enemies',    'e'),
        (r'drawBullet(?:s)?',     'bullets',    'b'),
        (r'drawParticle(?:s)?',   'particles',  'p'),
        (r'drawPowerUp(?:s)?',    'powerUps',   'p'),
        (r'drawFloatText(?:s)?',  'floatTexts', 't'),
        (r'drawExplosion(?:s)?',  'explosions', 'ex'),
        (r'drawItem(?:s)?',       'items',      'item'),
        # update* aussi touchées par ce bug
        (r'updateParticle(?:s)?', 'particles',  'p'),
        (r'updateExplosion(?:s)?','explosions', 'ex'),
        (r'updatePowerUp(?:s)?',  'powerUps',   'p'),
        (r'updateItem(?:s)?',     'items',      'item'),
        (r'updateFloatText(?:s)?','floatTexts', 't'),
    ]

    result = script
    delta = 0

    for func_pat, arr, ivar in _DRAW_LOOPS:
        func_re = re.compile(
            r'\bfunction\s+(' + func_pat + r')\s*\([^)]*\)\s*\{', re.IGNORECASE
        )
        for m_func in func_re.finditer(script):
            fname = m_func.group(1)
            body_start = m_func.end()
            depth = 1
            i = body_start
            while i < len(script) and depth > 0:
                c = script[i]
                if c == '{': depth += 1
                elif c == '}': depth -= 1
                i += 1
            body = script[body_start:i - 1]

            # Vérifier si le corps contient un for-loop sur le tableau
            for_pat = re.compile(
                r'for\s*\(\s*var\s+\w+\s*=\s*0[^)]*' + re.escape(arr) + r'[^)]*\)\s*\{',
                re.DOTALL
            )
            m_for = for_pat.search(body)
            if not m_for:
                continue

            # Vérifier si `ivar` est déclaré dans le corps du for
            for_body_start = m_for.end()
            depth2 = 1
            j = for_body_start
            while j < len(body) and depth2 > 0:
                c = body[j]
                if c == '{': depth2 += 1
                elif c == '}': depth2 -= 1
                j += 1
            for_body = body[for_body_start:j - 1]

            # Détecter le vrai nom de variable utilisé : cherche `xx.` non déclaré
            # (peut être ivar='t' mais le code utilise 'ft', ou ivar='p' mais code utilise 'part')
            _candidates_to_check = {ivar}
            # Cherche tout `identifier.` dans le for-body qui n'est pas déclaré
            for _m_cand in re.finditer(r'\b([a-zA-Z_]\w*)\s*\.', for_body):
                _c = _m_cand.group(1)
                if _c in ('ctx', 'Math', 'window', 'document', 'console', 'PALETTE',
                           'player', 'boss', 'canvas', 'dt', 'i', 'j'):
                    continue
                _candidates_to_check.add(_c)

            for _ivar in _candidates_to_check:
                if re.search(r'\bvar\s+' + re.escape(_ivar) + r'\b', for_body):
                    continue  # déclaré
                if not re.search(r'\b' + re.escape(_ivar) + r'\s*\.', for_body):
                    continue  # non utilisé avec .prop
                # Vérifie que cette var n'est pas un param de fonction ou déclarée en dehors du for
                if re.search(r'\bvar\s+' + re.escape(_ivar) + r'\b', body[:m_for.start()]):
                    continue
                # Injecter `var _ivar = arr[i];` comme première ligne du for-body
                abs_for_body_start = m_func.start() + (body_start - m_func.start()) + m_for.end() + delta
                inject = f'\n        var {_ivar} = {arr}[i];\n        if (!{_ivar}) continue;\n'
                result = result[:abs_for_body_start] + inject + result[abs_for_body_start:]
                delta += len(inject)
                fixes.append(f'[AUTO-FIX] {fname}(): var {_ivar} = {arr}[i] injecté (évite "{_ivar} is not defined")')
                break  # une seule injection par for-loop

    return result, fixes


def _strip_js_comments(code: str) -> str:
    """Strip // and /* */ comments so variable detection doesn't match inside them."""
    code = re.sub(r'//[^\n]*', '', code)
    code = re.sub(r'/\*[\s\S]*?\*/', '', code)
    return code


def _fix_undeclared_common_vars(script: str) -> tuple[str, list[str]]:
    """
    Détecte les variables de COMMON_VARS utilisées mais non déclarées.
    Injecte `let varname = initval;` juste avant le DOMContentLoaded
    (ou en tête du script si DOMContentLoaded absent).
    """
    fixes: list[str] = []

    # Charger les variables apprises dynamiquement
    learned = _load_learned_vars()

    # Fusionner COMMON_VARS + learned (COMMON_VARS a la priorité)
    all_vars: dict[str, str] = {}
    all_vars.update(learned)
    all_vars.update(COMMON_VARS)  # écrase les learned si conflit

    # Collecte COMPLÈTE des déclarations existantes
    declared = _collect_declarations(script)

    # Strip comments for usage detection — prevents false positives from
    # // collision comments, 'state' string literals, CSS text, etc.
    script_no_comments = _strip_js_comments(script)

    to_inject: list[tuple[str, str]] = []

    # Variables déclarées dans le template HTML — JAMAIS réinjecter
    _TEMPLATE_GLOBALS = frozenset({'canvas', 'ctx', 'dt', 'lastTime', 'gameState'})
    for tg in _TEMPLATE_GLOBALS:
        declared.add(tg)

    # Variables intrinsèquement ctx/canvas — jamais injecter comme globals standalone
    _ctx_props = frozenset({
        'fillStyle', 'strokeStyle', 'lineWidth', 'font', 'textAlign',
        'textBaseline', 'globalAlpha', 'globalCompositeOperation',
        'imageSmoothingEnabled', 'shadowColor', 'shadowBlur', 'shadowOffsetX',
        'shadowOffsetY', 'lineCap', 'lineJoin', 'fillRect', 'clearRect',
        'drawImage', 'width', 'height', 'function', 'length', 'typeof',
        # Propriétés très génériques / risque de collision
        'event', 'description', 'effect', 'ennemis',
    })

    for varname, initval in all_vars.items():
        if varname in declared:
            continue
        if varname in _ctx_props:
            continue
        # Vérifier que la variable est réellement utilisée comme standalone
        # (use comment-stripped script to avoid false positives)
        if not _is_used_standalone(varname, script_no_comments):
            continue
        to_inject.append((varname, initval))

    if not to_inject:
        return script, fixes

    inject_lines = ''.join(f'let {n} = {v};\n' for n, v in to_inject)
    script = _inject_before_domready(script, inject_lines)

    for varname, initval in to_inject:
        fixes.append(f'[AUTO-FIX] \'{varname}\' utilisé sans déclaration → initialisé à {initval}')

    return script, fixes


def _is_used_standalone(varname: str, script: str) -> bool:
    """
    Retourne True si `varname` est utilisé comme variable standalone
    (pas uniquement comme clé d'objet ou propriété d'objet via obj.varname).
    """
    if not re.search(rf'\b{re.escape(varname)}\b', script):
        return False

    for m in re.finditer(rf'\b{re.escape(varname)}\b', script):
        pos = m.start()
        end = m.end()

        # Précédé d'un '.' → propriété d'objet → ignorer
        pre_char = script[pos - 1] if pos > 0 else ''
        if pre_char == '.':
            continue

        # Suivi de ':' (avec espaces éventuels) → clé d'objet littéral → ignorer
        # Ex: `lives: 3` dans `let player = { ... lives: 3, ... }`
        rest = script[end:end + 3].lstrip(' \t')
        if rest.startswith(':') and not rest.startswith('::'):
            continue

        # C'est une utilisation standalone
        return True

    return False


def _load_learned_vars() -> dict[str, str]:
    """Charge les variables apprises depuis learned_vars.json."""
    if not os.path.exists(_LEARNED_VARS_FILE):
        return {}
    try:
        with open(_LEARNED_VARS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            k: v['init']
            for k, v in data.items()
            if v.get('count', 0) >= _MIN_LEARNED_COUNT
            and k not in COMMON_VARS  # COMMON_VARS a la priorité
        }
    except Exception:
        return {}


def _inject_before_domready(script: str, code: str) -> str:
    """Injecte du code juste avant le DOMContentLoaded, ou en tête du script."""
    match = re.search(
        r'document\s*\.\s*addEventListener\s*\(\s*[\'"]DOMContentLoaded',
        script
    )
    if match:
        return script[:match.start()] + code + script[match.start():]
    return code + script


# ─────────────────────────────────────────────────────────────
# FIX 3 — GameState flow bloqué au menu sans transition
# ─────────────────────────────────────────────────────────────

def _fix_gamestateflow(script: str) -> tuple[str, list[str]]:
    """
    Détecte gameState bloqué à 'menu' sans transition vers 'playing'.
    Symptôme : gameState === 'menu' est testé dans update() mais aucun
    événement clavier/souris ne fait gameState = 'playing'.
    Correction : injecte un handler dans le bloc menu de update() ou
    directement dans gameLoop si le pattern est simple.
    """
    import re
    fixes: list[str] = []

    # Vérifier si gameState est utilisé
    if "gameState" not in script:
        return script, fixes

    # Vérifier si 'menu' est un état possible
    has_menu_state = bool(re.search(r"""gameState\s*[=!]==?\s*['"]menu['"]""", script))
    if not has_menu_state:
        return script, fixes

    # Vérifier si une transition vers 'playing' existe déjà
    has_playing_transition = bool(re.search(
        r"""gameState\s*=\s*['"]playing['"]""", script
    ))
    if has_playing_transition:
        return script, fixes

    # Vérifier si une fonction initGame/startGame/resetGame existe
    has_init = bool(re.search(r"function\s+(initGame|startGame|resetGame|init)\s*\(", script))
    init_call = "initGame()" if re.search(r"function\s+initGame\s*\(", script) else \
                "startGame()" if re.search(r"function\s+startGame\s*\(", script) else \
                "resetGame()" if re.search(r"function\s+resetGame\s*\(", script) else \
                "init()" if re.search(r"function\s+init\s*\(", script) else ""

    # Chercher le bloc if (gameState === 'menu') { ... } dans update ou gameLoop
    menu_block_pattern = re.compile(
        r"(if\s*\(\s*gameState\s*===?\s*['\"]menu['\"]\s*\)\s*\{)",
        re.IGNORECASE
    )
    m = menu_block_pattern.search(script)
    if m:
        # Injecter la transition dans le bloc menu existant
        insert_after = m.end()
        transition_code = (
            f"\n        if (keys[' '] || keys['Enter'] || keys['ArrowUp'] || mouseClicked) "
            f"{{ {'  ' + init_call + '; ' if init_call else ''}gameState = 'playing'; mouseClicked = false; }}"
        )
        script = script[:insert_after] + transition_code + script[insert_after:]
        fixes.append("[fix_gamestateflow] Transition menu→playing injectée dans le bloc menu de update()")
    else:
        # Chercher gameLoop ou requestAnimationFrame pour injection minimale
        gameloop_m = re.search(r"function\s+gameLoop\s*\(", script)
        if gameloop_m:
            # Ajouter un keydown listener global avant gameLoop
            listener_code = (
                "\n// [auto-fix] Transition menu → playing\n"
                "var mouseClicked = false;\n"
                "document.addEventListener('mousedown', function() { mouseClicked = true; });\n"
                "document.addEventListener('keydown', function(e) {\n"
                "  if (gameState === 'menu' && (e.code === 'Space' || e.code === 'Enter')) {\n"
                f"    {'  ' + init_call + '; ' if init_call else ''}gameState = 'playing';\n"
                "  }\n"
                "});\n"
            )
            script = script[:gameloop_m.start()] + listener_code + script[gameloop_m.start():]
            fixes.append("[fix_gamestateflow] Listener menu→playing injecté avant gameLoop()")

    # S'assurer que mouseClicked est déclaré si on l'utilise
    if fixes and "mouseClicked" not in script.split(fixes[0])[0]:
        # Déjà injecté dans le code ci-dessus ou déclaré ailleurs
        pass

    return script, fixes


# ─────────────────────────────────────────────────────────────
# FIX 4 — Stubs de fonctions manquantes
# ─────────────────────────────────────────────────────────────

def _inject_missing_stubs(script: str) -> tuple[str, list[str]]:
    """
    Détecte les appels à des fonctions communes non définies et injecte des stubs.
    """
    fixes: list[str] = []
    stubs_to_inject: list[str] = []

    for fn_name, stub_code in _STUBS.items():
        # La fonction est-elle appelée ?
        if not re.search(rf'\b{re.escape(fn_name)}\s*\(', script):
            continue
        # La fonction est-elle déjà définie ?
        if re.search(rf'\bfunction\s+{re.escape(fn_name)}\s*\(', script):
            continue
        # Définie comme méthode ou arrow function ?
        if re.search(rf'\b{re.escape(fn_name)}\s*[=:]\s*(?:function|\(|async)', script):
            continue
        stubs_to_inject.append(stub_code)
        fixes.append(f'[AUTO-FIX] {fn_name}: stub injecté')
        # Tracker l'injection pour l'auto-learner (promotion future dans SYSTEM_2D)
        try:
            from auto_learner import track_stub_injection
            track_stub_injection(fn_name)
        except Exception:
            pass

    if stubs_to_inject:
        inject_block = '\n\n'.join(stubs_to_inject) + '\n\n'
        script = _inject_before_domready(script, inject_block)

    return script, fixes


# ─────────────────────────────────────────────────────────────
# FIX 4a — Canvas setup manquant (getContext absent après troncature)
# ─────────────────────────────────────────────────────────────

def _fix_missing_canvas_setup(script: str) -> tuple[str, list[str]]:
    """
    Détecte l'absence de canvas.getContext('2d') et injecte un setup minimal
    au début du DOMContentLoaded (ou du script).
    Uniquement pour les jeux 2D (pas Three.js).
    """
    if 'getContext' in script or 'THREE.' in script:
        return script, []

    # Chercher si un canvas HTML est référencé (getElementById ou querySelector)
    has_canvas_ref = bool(re.search(r'getElementById\s*\([\'"].*canvas.*[\'"]\)|querySelector\s*\([\'"]canvas', script, re.IGNORECASE))

    # Canvas ID depuis le HTML (chercher dans les balises)
    canvas_id = 'gameCanvas'
    m_id = re.search(r'<canvas[^>]*\bid=["\']([^"\']+)["\']', script, re.IGNORECASE)
    if m_id:
        canvas_id = m_id.group(1)

    canvas_declared = bool(re.search(r'\b(?:let|const|var)\s+canvas\b', script))
    ctx_declared = bool(re.search(r'\b(?:let|const|var)\s+ctx\b', script))

    lines = []
    if not canvas_declared:
        lines.append(
            f"  canvas = document.getElementById('{canvas_id}') "
            f"|| document.querySelector('canvas');"
        )
    if not ctx_declared:
        lines.append("  ctx = canvas ? canvas.getContext('2d') : null;")
    else:
        lines.append("  if (!ctx && canvas) { ctx = canvas.getContext('2d'); }")
    lines.append("  if (canvas && !canvas.width) { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }")

    inject = "\n" + "\n".join(lines) + "\n"

    script = _inject_before_domready(script, inject)
    return script, ['[AUTO-FIX] canvas.getContext manquant — setup canvas injecté']


# ─────────────────────────────────────────────────────────────
# FIX 4d — Accolades orphelines (} isolée en début de ligne)
# ─────────────────────────────────────────────────────────────

def _fix_orphan_closing_braces(script: str) -> tuple[str, list[str]]:
    """
    Détecte et supprime les `}` orphelins qui font passer la profondeur de brace
    en dessous de 0, en tenant compte des chaînes et template literals.
    Plus précis que la suppression des premières lignes orphelines.
    """
    # Compter les { et } hors chaînes pour voir s'il y a un déséquilibre
    opens = closes = 0
    in_str, str_char, in_ml, escape = False, '', False, False
    for ch in script:
        if escape:
            escape = False
            continue
        if ch == '\\' and (in_str or in_ml):
            escape = True
            continue
        if in_ml:
            if ch == '`':
                in_ml = False
            continue
        if in_str:
            if ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str, str_char = True, ch
            continue
        if ch == '`':
            in_ml = True
            continue
        if ch == '{':
            opens += 1
        elif ch == '}':
            closes += 1

    excess = closes - opens
    if excess <= 0:
        return script, []  # équilibré ou manquant des } → pas d'orphelins à supprimer

    # Identifier QUELLES lignes contiennent des `}` qui font passer la profondeur < 0
    # On scanne ligne par ligne et on note les lignes orphelines (depth devient négatif)
    lines = script.split('\n')
    orphan_line_indices = set()
    depth = 0
    in_str2, str_char2, in_ml2, esc2 = False, '', False, False

    for li, line in enumerate(lines):
        for ch in line:
            if esc2:
                esc2 = False
                continue
            if ch == '\\' and (in_str2 or in_ml2):
                esc2 = True
                continue
            if in_ml2:
                if ch == '`':
                    in_ml2 = False
                continue
            if in_str2:
                if ch == str_char2:
                    in_str2 = False
                continue
            if ch in ('"', "'"):
                in_str2, str_char2 = True, ch
                continue
            if ch == '`':
                in_ml2 = True
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth < 0:
                    # Ce `}` est orphelin
                    orphan_line_indices.add(li)
                    depth = 0  # reset pour continuer l'analyse

    if not orphan_line_indices:
        # Fallback : supprimer les `excess` dernières lignes qui ne contiennent que `}`
        orphan_pat = re.compile(r'^[ \t]*\};?[ \t]*$', re.MULTILINE)
        all_matches = list(orphan_pat.finditer(script))
        # Prendre les dernières `excess` occurrences (les orphelins sont souvent en fin de fichier)
        to_remove = set(m.start() for m in all_matches[-excess:])
        removed = 0
        result_parts = []
        prev = 0
        for m in all_matches:
            if m.start() in to_remove:
                result_parts.append(script[prev:m.start()])
                prev = m.end()
                removed += 1
        result_parts.append(script[prev:])
        new_script = ''.join(result_parts)
        # Vérification rollback : suppression excessive ?
        opens_fb = sum(1 for ch in new_script if ch == '{')
        closes_fb = sum(1 for ch in new_script if ch == '}')
        if opens_fb > closes_fb:
            return script, ['[WARN] _fix_orphan_closing_braces fallback rollback : opens > closes après suppression']
        fixes = [f'[AUTO-FIX] {removed} accolade(s) orpheline(s) supprimée(s) (fin fichier)'] if removed else []
        return new_script, fixes

    # Supprimer les lignes orphelines identifiées (conserver l'ordre)
    new_lines = [line for li, line in enumerate(lines) if li not in orphan_line_indices]
    new_script = '\n'.join(new_lines)

    # Vérification post-suppression : si on a plus de { que de } dans le résultat,
    # on a supprimé un } légitime (confondu avec orphelin à cause du déséquilibre
    # introduit par _dedup_declarations). Rollback vers le script original.
    opens_new = closes_new = 0
    in_str3, str_char3, in_ml3, esc3 = False, '', False, False
    for ch in new_script:
        if esc3:
            esc3 = False
            continue
        if ch == '\\' and (in_str3 or in_ml3):
            esc3 = True
            continue
        if in_ml3:
            if ch == '`':
                in_ml3 = False
            continue
        if in_str3:
            if ch == str_char3:
                in_str3 = False
            continue
        if ch in ('"', "'"):
            in_str3, str_char3 = True, ch
            continue
        if ch == '`':
            in_ml3 = True
            continue
        if ch == '{':
            opens_new += 1
        elif ch == '}':
            closes_new += 1

    if opens_new > closes_new:
        # Suppression a créé un déséquilibre inverse → rollback
        return script, ['[WARN] _fix_orphan_closing_braces rollback : suppression créerait opens > closes']

    fixes = [f'[AUTO-FIX] {len(orphan_line_indices)} accolade(s) orpheline(s) supprimée(s) (profondeur < 0)']
    return new_script, fixes


# FIX 4e — Crochets orphelins (] isolé en début de ligne)
# ─────────────────────────────────────────────────────────────

def _fix_orphan_closing_brackets(script: str) -> tuple[str, list[str]]:
    """
    Détecte et supprime les `]` orphelins qui font passer la profondeur de crochet
    en dessous de 0. Même logique que _fix_orphan_closing_braces pour les [].
    """
    opens = closes = 0
    in_str, str_char, in_ml, escape = False, '', False, False
    for ch in script:
        if escape:
            escape = False
            continue
        if ch == '\\' and (in_str or in_ml):
            escape = True
            continue
        if in_ml:
            if ch == '`':
                in_ml = False
            continue
        if in_str:
            if ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str, str_char = True, ch
            continue
        if ch == '`':
            in_ml = True
            continue
        if ch == '[':
            opens += 1
        elif ch == ']':
            closes += 1

    excess = closes - opens
    if excess <= 0:
        return script, []

    lines = script.split('\n')
    orphan_line_indices = set()
    depth = 0
    in_str2, str_char2, in_ml2, esc2 = False, '', False, False

    for li, line in enumerate(lines):
        for ch in line:
            if esc2:
                esc2 = False
                continue
            if ch == '\\' and (in_str2 or in_ml2):
                esc2 = True
                continue
            if in_ml2:
                if ch == '`':
                    in_ml2 = False
                continue
            if in_str2:
                if ch == str_char2:
                    in_str2 = False
                continue
            if ch in ('"', "'"):
                in_str2, str_char2 = True, ch
                continue
            if ch == '`':
                in_ml2 = True
                continue
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth < 0:
                    orphan_line_indices.add(li)
                    depth = 0

    if not orphan_line_indices:
        orphan_pat = re.compile(r'^[ \t]*\];?[ \t]*$', re.MULTILINE)
        all_matches = list(orphan_pat.finditer(script))
        to_remove = set(m.start() for m in all_matches[-excess:])
        removed = 0
        result_parts = []
        prev = 0
        for m in all_matches:
            if m.start() in to_remove:
                result_parts.append(script[prev:m.start()])
                prev = m.end()
                removed += 1
        result_parts.append(script[prev:])
        new_script = ''.join(result_parts)
        fixes = [f'[AUTO-FIX] {removed} crochet(s) orphelin(s) supprimé(s) (fin fichier)'] if removed else []
        return new_script, fixes

    new_lines = [line for li, line in enumerate(lines) if li not in orphan_line_indices]
    fixes = [f'[AUTO-FIX] {len(orphan_line_indices)} crochet(s) orphelin(s) supprimé(s) (profondeur < 0)']
    return '\n'.join(new_lines), fixes


# ─────────────────────────────────────────────────────────────
# FIX 4c — for-in sans assignment (npc non déclaré dans for-in NPC_DEFS)
# ─────────────────────────────────────────────────────────────

def _fix_forin_missing_assignment(script: str) -> tuple[str, list[str]]:
    """
    Détecte les boucles `for (const KEY_Id in OBJ_DEFS)` où le LLM utilise
    `KEY` (sans "Id") sans l'avoir déclaré. Injecte `const KEY = OBJ_DEFS[KEY_Id];`
    comme première instruction du bloc.

    Exemple :
        for (const npcId in NPC_DEFS) {       → ajoute : const npc = NPC_DEFS[npcId];
        for (const towerId in TOWER_DEFS) {   → ajoute : const tower = TOWER_DEFS[towerId];
    """
    import re

    # Pattern : for (const VAR_Id in OBJ_DEFS) {
    pattern = re.compile(
        r'(for\s*\(\s*const\s+(\w+Id)\s+in\s+(\w+)\s*\)\s*\{)',
        re.MULTILINE
    )

    fixes = []
    result = script
    offset = 0

    for m in pattern.finditer(script):
        key_id = m.group(2)          # ex: "npcId"
        obj_name = m.group(3)        # ex: "NPC_DEFS"
        # Dériver le nom sans "Id" : npcId → npc
        short_name = key_id[:-2] if key_id.lower().endswith('id') else None
        if not short_name:
            continue

        # Vérifier que short_name est utilisé dans le bloc mais pas déclaré
        block_start = m.end() + offset
        # Chercher la fin du bloc (simple heuristique : jusqu'à la prochaine ligne vide ou })
        block_snippet = result[block_start:block_start + 500]
        # short_name est utilisé et n'est pas déjà déclaré ?
        already_declared = bool(re.search(
            rf'\b(?:const|let|var)\s+{re.escape(short_name)}\s*=',
            block_snippet
        ))
        if already_declared:
            continue
        is_used = bool(re.search(rf'\b{re.escape(short_name)}\b', block_snippet))
        if not is_used:
            continue

        # Injecter const short_name = obj_name[key_id]; au début du bloc
        injection = f'\n  const {short_name} = {obj_name}[{key_id}];'
        insert_pos = block_start
        result = result[:insert_pos] + injection + result[insert_pos:]
        offset += len(injection)
        fixes.append(f'[AUTO-FIX] {short_name} = {obj_name}[{key_id}] injecté dans boucle for-in')

    return result, fixes


# ─────────────────────────────────────────────────────────────
# FIX — for-index sans déclaration de l'élément (star is not defined)
# ─────────────────────────────────────────────────────────────

def _fix_forindex_missing_element(script: str) -> tuple[str, list[str]]:
    """
    Détecte les boucles `for (let i = 0; i < ARR.length; i++)` où le corps
    utilise SINGULAR.prop sans jamais déclarer `const SINGULAR = ARR[i]`.
    Injecte la déclaration manquante en première ligne du bloc.

    Exemple : for (let i = 0; i < stars.length; i++) { star.color ... }
              → injecte : const star = stars[i];
    """
    # Pluriel → singulier pour les noms courants dans les jeux
    PLURAL_TO_SINGULAR = {
        'stars': 'star', 'enemies': 'enemy', 'bullets': 'bullet',
        'particles': 'particle', 'projectiles': 'projectile', 'items': 'item',
        'towers': 'tower', 'obstacles': 'obstacle', 'platforms': 'platform',
        'coins': 'coin', 'powerups': 'powerup', 'npcs': 'npc',
        'rooms': 'room', 'tiles': 'tile', 'nodes': 'node', 'waves': 'wave',
        'effects': 'effect', 'explosions': 'explosion', 'orbs': 'orb',
        'gems': 'gem', 'drops': 'drop', 'targets': 'target',
    }
    # Aussi les formes en 's' simple : enemies→enemy déjà géré, mais aussi shots→shot etc.
    fixes = []
    lines = script.split('\n')
    result_lines = list(lines)
    offset = 0  # décalage d'index après injections

    for li, line in enumerate(lines):
        m = re.match(
            r'^(\s*)for\s*\(\s*(?:let|var)\s+i\s*=\s*0\s*;\s*i\s*<\s*(\w+)\.length\s*;\s*i\s*\+\+\s*\)\s*\{',
            line
        )
        if not m:
            continue
        indent = m.group(1)
        arr_name = m.group(2)  # ex: "stars"

        # Chercher le singulier correspondant
        singular = PLURAL_TO_SINGULAR.get(arr_name)
        if not singular:
            # Essai générique : retirer le 's' final
            if arr_name.endswith('s') and len(arr_name) > 2:
                singular = arr_name[:-1]
            else:
                continue

        # Chercher le corps de la boucle (jusqu'à la fermeture)
        body_lines = []
        depth = 1
        for j in range(li + 1, min(li + 80, len(lines))):
            body_lines.append(lines[j])
            depth += lines[j].count('{') - lines[j].count('}')
            if depth <= 0:
                break

        body_text = '\n'.join(body_lines)

        # Vérifier que singular est utilisé dans le corps
        if not re.search(rf'\b{re.escape(singular)}\b', body_text):
            continue

        # Vérifier qu'il n'est pas déjà déclaré dans le corps
        already = re.search(
            rf'\b(?:const|let|var)\s+{re.escape(singular)}\s*=',
            body_text
        )
        if already:
            continue

        # Injection après la ligne du for
        injection = f'{indent}    const {singular} = {arr_name}[i];'
        insert_idx = li + 1 + offset
        result_lines.insert(insert_idx, injection)
        offset += 1
        fixes.append(f'[AUTO-FIX] const {singular} = {arr_name}[i] injecté dans boucle for-index')

    return '\n'.join(result_lines), fixes


# ─────────────────────────────────────────────────────────────
# FIX 4b — for-of splice (mutation pendant itération)
# ─────────────────────────────────────────────────────────────

def _fix_missing_raf_in_domready(script: str) -> tuple[str, list[str]]:
    """
    Détecte les cas où requestAnimationFrame n'est jamais appelé dans DOMContentLoaded
    alors que gameLoop (ou équivalent) est défini. Injecte l'appel juste avant la
    fermeture du DOMContentLoaded.
    Évite de dupliquer un RAF déjà présent.
    """
    fixes: list[str] = []
    if 'requestAnimationFrame' in script:
        return script, fixes

    # Vérifier que setInterval / setTimeout ne sont pas là non plus (déjà une boucle)
    if 'setInterval' in script or 'setTimeout' in script:
        return script, fixes

    # Chercher si une fonction gameLoop / animate / loop / tick est définie
    loop_fn_match = re.search(
        r'\bfunction\s+(gameLoop|animate|loop|tick|render|mainLoop)\s*\(',
        script
    )
    if not loop_fn_match:
        return script, fixes

    loop_fn = loop_fn_match.group(1)

    # Chercher la fermeture du DOMContentLoaded : "});" ou "})" en fin de script
    # On cherche la dernière fermeture d'un addEventListener DOMContentLoaded
    dom_match = re.search(
        r'document\s*\.\s*addEventListener\s*\(\s*[\'"]DOMContentLoaded[\'"]',
        script
    )
    if not dom_match:
        # Pas de DOMContentLoaded → injection en fin de script
        inject = f"\n// Démarrage boucle principale\nrequestAnimationFrame({loop_fn});\n"
        script = script.rstrip() + inject
        fixes.append(f"[AUTO-FIX] requestAnimationFrame({loop_fn}) injecté en fin de script (RAF absent)")
        return script, fixes

    # Trouver la fermeture du callback DOMContentLoaded
    # Compter les accolades depuis la position du callback
    cb_start = script.find('{', dom_match.end())
    if cb_start == -1:
        return script, fixes
    depth = 0
    for i in range(cb_start, len(script)):
        if script[i] == '{':
            depth += 1
        elif script[i] == '}':
            depth -= 1
            if depth == 0:
                inject = f"\n  // Démarrage boucle principale\n  requestAnimationFrame({loop_fn});\n"
                script = script[:i] + inject + script[i:]
                fixes.append(f"[AUTO-FIX] requestAnimationFrame({loop_fn}) injecté dans DOMContentLoaded (RAF absent)")
                return script, fixes

    return script, fixes


def _fix_setinterval_raf_parallel(script: str) -> tuple[str, list[str]]:
    """
    Détecte setInterval(update|gameLoop|loop, N) + requestAnimationFrame en parallèle.
    Supprime le setInterval pour éviter la double vitesse.
    """
    fixes: list[str] = []
    if 'setInterval' not in script or 'requestAnimationFrame' not in script:
        return script, fixes

    # Pattern : setInterval(gameLoop|update|loop|render|tick|animate, ...)
    si_pattern = re.compile(
        r'setInterval\s*\(\s*(?:gameLoop|update|loop|render|tick|animate)\s*,\s*\d+\s*\)\s*;?',
        re.IGNORECASE
    )
    new_script, n = si_pattern.subn('/* setInterval supprimé — RAF actif */', script)
    if n:
        script = new_script
        fixes.append(f"[AUTO-FIX] setInterval (boucle principale) supprimé — requestAnimationFrame déjà présent (évite double vitesse)")

    return script, fixes


def _fix_for_of_splice(script: str) -> tuple[str, int]:
    """
    Convertit les boucles `for (const/let x of arr) { ... arr.splice(...) }` en itération
    sur une copie `for (const/let x of [...arr])` pour éviter les mutations pendant l'itération.
    Pattern : for (const|let VAR of ARRAY) { ...ARRAY.splice... }
    """
    import re

    pattern = re.compile(
        r'(for\s*\(\s*(?:const|let)\s+\w+\s+of\s+)(\w+)(\s*\))',
        re.MULTILINE
    )

    count = 0
    result = script
    # On cherche les blocs where le tableau cible contient un .splice()
    for m in pattern.finditer(script):
        arr_name = m.group(2)
        # Trouver le bloc { } qui suit
        block_start = script.find('{', m.end())
        if block_start == -1:
            continue
        # Scan du bloc (char-par-char)
        depth = 0
        block_end = block_start
        for idx in range(block_start, len(script)):
            if script[idx] == '{':
                depth += 1
            elif script[idx] == '}':
                depth -= 1
                if depth == 0:
                    block_end = idx
                    break
        block_body = script[block_start:block_end + 1]
        # Si le bloc contient arr.splice( → réécrire la boucle avec copie
        if re.search(rf'\b{re.escape(arr_name)}\.splice\s*\(', block_body):
            old = m.group(0)
            new = f"{m.group(1)}[...{arr_name}]{m.group(3)}"
            result = result.replace(old, new, 1)
            count += 1

    return result, count


# ─────────────────────────────────────────────────────────────
# FIX 4 — Trailing commas
# ─────────────────────────────────────────────────────────────

def _fix_trailing_commas(script: str) -> tuple[str, int]:
    """
    Supprime les virgules trailing dans les littéraux objet/tableau.
    Ex: { a: 1, b: 2, } → { a: 1, b: 2 }
    """
    # Pattern : virgule(s) suivie(s) optionnellement d'espaces/retours, puis } ou ]
    # On évite de toucher aux template literals (pas de regex pour ça, approche ligne par ligne)
    original = script
    # Supprimer virgule(s) juste avant } ou ] (avec whitespace optionnel entre)
    script = re.sub(r',(\s*[}\]])', r'\1', script)
    count = original.count(',') - script.count(',')
    return script, max(0, count)


# ─────────────────────────────────────────────────────────────
# FIX 5 — Déduplication des déclarations
# ─────────────────────────────────────────────────────────────

def _dedup_declarations(script: str) -> tuple[str, int]:
    """
    Supprime les redéclarations de variables (let/const/var X = ...).
    K1 — Scope tracking par profondeur d'accolades JS réelle.
    Clé = (nom, brace_depth) pour tous — plus de special-case COMMON_VARS qui
    supprimait des déclarations locales légitimes (var bullet=bullets[i] à depth=1
    retirée parce que var bullet=null existait à depth=0).
    Garde la PREMIÈRE occurrence par (nom, profondeur).
    """
    decl_pattern = re.compile(
        r'^([ \t]*)(?:let|const|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=',
        re.MULTILINE
    )
    seen: dict[tuple, int] = {}  # (name, brace_depth) → line_index
    lines = script.split('\n')
    to_remove: set[int] = set()

    # Tracker la profondeur d'accolades JS hors strings/commentaires
    depth = 0
    in_str = False
    str_char = ''
    in_ml_comment = False
    escape = False

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        # Commentaire ligne entière → skip (ne pas modifier depth, ne pas déduper)
        if stripped.startswith('//') or stripped.startswith('*'):
            continue

        # Mise à jour de la profondeur caractère par caractère
        for ch in line:
            if escape:
                escape = False
                continue
            if in_ml_comment:
                if ch == '/' and line[max(0, line.index(ch)-1):line.index(ch)] == '*':
                    in_ml_comment = False
                continue
            if in_str:
                if ch == '\\':
                    escape = True
                elif ch == str_char:
                    in_str = False
                continue
            if ch in ('"', "'", '`'):
                in_str = True
                str_char = ch
            elif ch == '/' and not in_str:
                # Début commentaire inline → reste de la ligne ignorée pour depth
                break
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth - 1)

        m = decl_pattern.match(line)
        if m:
            name = m.group(2)
            # Ne pas déduper les déclarations qui ouvrent un bloc multi-ligne (var X = {)
            # → supprimer seulement la ligne laisserait le } de fermeture flottant.
            line_stripped_end = line.rstrip()
            if line_stripped_end.endswith('{') or line_stripped_end.endswith('['):
                continue
            # Clé = (nom, profondeur réelle) — pas de special-case COMMON_VARS
            key = (name, depth)
            if key in seen:
                to_remove.add(i)
            else:
                seen[key] = i

    if not to_remove:
        return script, 0

    filtered = [line for i, line in enumerate(lines) if i not in to_remove]
    return '\n'.join(filtered), len(to_remove)


# ─────────────────────────────────────────────────────────────
# FIX — createRadialGradient NaN/non-finite guard
# ─────────────────────────────────────────────────────────────

def _inject_gradient_safety(script: str) -> tuple[str, list[str]]:
    """
    Inject a one-time prototype patch that prevents createRadialGradient crashes
    when coordinates or radii are NaN/Infinity (common in procedural draw code).
    """
    if 'createRadialGradient' not in script:
        return script, []
    _sig = 'createRadialGradient=function('
    if _sig in script:
        return script, []
    _patch = (
        '(function(){'
        'var _rg=CanvasRenderingContext2D.prototype.createRadialGradient;'
        'CanvasRenderingContext2D.prototype.createRadialGradient=function(x1,y1,r1,x2,y2,r2){'
        'if(!isFinite(x1)||!isFinite(y1)||!isFinite(r1)'
        '||!isFinite(x2)||!isFinite(y2)||!isFinite(r2))'
        'return _rg.call(this,0,0,0,0,0,1);'
        'return _rg.call(this,x1,y1,Math.max(0,r1),x2,y2,Math.max(0,r2));};})();\n'
    )
    return _patch + script, ['[AUTO-FIX] createRadialGradient safety wrapper injected']


# ─────────────────────────────────────────────────────────────
# FIX 6 — eval/debug en production
# ─────────────────────────────────────────────────────────────

def _fix_external_resources(script: str) -> tuple[str, list[str]]:
    """
    Neutralise les chargements de ressources externes (new Image() avec src fichier,
    fetch(), XMLHttpRequest, new Audio() avec src fichier) → cause des 404 et exec 3.0.
    """
    fixes: list[str] = []
    original = script

    # new Image(); img.src = 'filename.ext' → remplacer src par data URI vide
    # Neutralise: img.src = 'path/to/file.png' (toute extension image)
    count = [0]

    def _remove_img_src(m: re.Match) -> str:
        src = m.group(1)
        # Garder les data URIs (commencent par 'data:')
        if src.startswith('data:'):
            return m.group(0)
        count[0] += 1
        return "/* external img removed */"

    # Pattern: quelconque_var.src = 'non-data-uri'
    script = re.sub(
        r'''(\w+)\.src\s*=\s*['"](?!data:)([^'"]{1,200})['"]''',
        lambda m: f"/* external src '{m.group(2)}' removed */",
        script
    )
    if script != original:
        fixes.append(f'[AUTO-FIX] src externe neutralisé (→ images/audio manquants supprimés)')

    # fetch() avec URL non-data - remplacer par Promise.resolve vide
    if re.search(r'\bfetch\s*\(\s*[\'"][^\'"]*[\'"]\s*\)', script):
        script = re.sub(
            r'\bfetch\s*\(\s*[\'"](?!data:)([^\'"]*)[\'"](\s*\))',
            r"Promise.resolve(new Response('{}'))\2",
            script
        )
        fixes.append('[AUTO-FIX] fetch() externe → Promise.resolve vide')

    return script, fixes


def _fix_arrow_key_mapping(script: str) -> tuple[str, list[str]]:
    """
    Corrige les handlers keydown/keyup qui font `keys[e.key.toLowerCase()] = true/false`
    sans mapper ArrowLeft/Right/Up/Down vers keys.left/right/up/down.

    Symptôme : le joueur ne peut pas se déplacer avec les flèches car updatePlayer vérifie
    keys.left/right/up/down mais le handler stocke keys["arrowleft"] etc.
    """
    fixes = []
    _ARROW_KEYDOWN = (
        "  if (e.key === \"ArrowLeft\")  { keys.left = true;  e.preventDefault(); }\n"
        "  if (e.key === \"ArrowRight\") { keys.right = true; e.preventDefault(); }\n"
        "  if (e.key === \"ArrowUp\")    { keys.up = true;    e.preventDefault(); }\n"
        "  if (e.key === \"ArrowDown\")  { keys.down = true;  e.preventDefault(); }\n"
        "  if (e.key === \" \")          { keys.space = true; e.preventDefault(); }\n"
    )
    _ARROW_KEYUP = (
        "  if (e.key === \"ArrowLeft\")  keys.left = false;\n"
        "  if (e.key === \"ArrowRight\") keys.right = false;\n"
        "  if (e.key === \"ArrowUp\")    keys.up = false;\n"
        "  if (e.key === \"ArrowDown\")  keys.down = false;\n"
        "  if (e.key === \" \")          keys.space = false;\n"
    )

    # Patch le premier keydown handler qui utilise keys[e.key.toLowerCase()]
    kd_pat = re.compile(
        r'(addEventListener\(["\']keydown["\'][^)]*\)\s*\{[^\n]*\n)'
        r'(\s*keys\[e\.key\.toLowerCase\(\)\]\s*=\s*true;)'
    )
    def _patch_kd(m):
        if 'ArrowLeft' in m.group(0):
            return m.group(0)  # déjà patché
        fixes.append('[AUTO-FIX] keydown handler: mapping ArrowLeft/Right/Up/Down → keys.left/right/up/down ajouté')
        return m.group(1) + m.group(2) + '\n' + _ARROW_KEYDOWN
    script, n = re.subn(kd_pat, _patch_kd, script, count=1)

    # Patch le premier keyup handler
    ku_pat = re.compile(
        r'(addEventListener\(["\']keyup["\'][^)]*\)\s*\{[^\n]*\n)'
        r'(\s*keys\[e\.key\.toLowerCase\(\)\]\s*=\s*false;)'
    )
    def _patch_ku(m):
        if 'ArrowLeft' in m.group(0):
            return m.group(0)
        return m.group(1) + m.group(2) + '\n' + _ARROW_KEYUP
    script = re.sub(ku_pat, _patch_ku, script, count=1)

    return script, fixes


def _fix_spawnplayer_missing_dimensions(script: str) -> tuple[str, list[str]]:
    """
    Corrige spawnPlayer() qui crée l'objet player sans w/h/r.
    Symptômes :
      - Balles spawent à player.y - undefined = NaN → invisibles
      - aabbCollide(player, e) → NaN → jamais de collision → ennemis ne font pas de dégâts
    Fix : injecte w:24, h:24, r:12 dans l'objet créé si absent.
    """
    fixes = []

    spawnplayer_pat = re.compile(
        r'(function\s+spawnPlayer\s*\([^)]*\)\s*\{)(.*?)(\n\})',
        re.DOTALL
    )
    def _find_player_obj(body):
        """Find player = { ... } with balanced braces to avoid matching nested sub-objects."""
        start_pat = re.compile(r'player\s*=\s*\{')
        m_start = start_pat.search(body)
        if not m_start:
            return None
        depth = 0
        start = m_start.end() - 1  # position of '{'
        i = start
        while i < len(body):
            if body[i] == '{':
                depth += 1
            elif body[i] == '}':
                depth -= 1
                if depth == 0:
                    return (m_start.start(), start, i)  # (match_start, content_start, content_end_incl)
            i += 1
        return None

    def _patch(m):
        body = m.group(2)
        result = _find_player_obj(body)
        if not result:
            return m.group(0)
        match_start, content_start, closing_brace = result
        obj_content = body[content_start + 1:closing_brace]  # between { and }
        changed = False
        if not re.search(r'\bw\s*:', obj_content):
            obj_content += '\n        w: 24,'
            changed = True
        if not re.search(r'\bh\s*:', obj_content):
            obj_content += '\n        h: 24,'
            changed = True
        if not re.search(r'\br\s*:', obj_content):
            obj_content += '\n        r: 12,'
            changed = True
        if changed:
            new_body = body[:content_start + 1] + obj_content + body[closing_brace:]
            fixes.append('[AUTO-FIX] spawnPlayer(): w/h/r ajoutés à player (évite balles NaN + collisions cassées)')
            return m.group(1) + new_body + m.group(3)
        return m.group(0)

    script = spawnplayer_pat.sub(_patch, script)
    return script, fixes


def _fix_spawn_missing_typeindex(script: str) -> tuple[str, list[str]]:
    """
    Corrige le pattern spawnEnemy(typeIndex) où typeIndex n'est pas stocké sur l'objet ennemi.
    Symptôme : ENEMY_TYPES[e.typeIndex] → undefined → 'Cannot read properties of undefined (reading type)'
    Fix : injecte 'typeIndex: typeIndex,' dans l'objet ennemi retourné par spawnEnemy.
    S'applique aussi à spawnPowerUp / spawnItem avec powerUpIndex / itemIndex.
    """
    fixes = []

    def _inject_field_if_missing(m_func):
        fname = m_func.group(1)       # ex: spawnEnemy
        param = m_func.group(2)       # ex: typeIndex
        body = m_func.group(3)
        field = param                  # on stocke le param tel quel

        # Cherche l'objet littéral créé dans la fonction (var xxx = { ... })
        obj_pat = re.compile(
            r'(var\s+\w+\s*=\s*\{)([^}]*?\})',
            re.DOTALL
        )
        m_obj = obj_pat.search(body)
        if not m_obj:
            return m_func.group(0)

        obj_content = m_obj.group(2)
        # Si le champ est déjà là, rien à faire
        if re.search(r'\b' + re.escape(field) + r'\s*:', obj_content):
            return m_func.group(0)

        # Injecte le champ juste après l'accolade ouvrante
        new_obj = m_obj.group(1) + f'\n        {field}: {field},' + obj_content
        new_body = body[:m_obj.start()] + new_obj + body[m_obj.end():]
        fixes.append(f'[AUTO-FIX] {fname}: champ "{field}" ajouté dans l\'objet créé (evite ENEMY_TYPES[undefined])')
        full = m_func.group(0)
        return full.replace(body, new_body)

    # Applique sur spawnEnemy(typeIndex), spawnItem(itemIndex), etc.
    pattern = re.compile(
        r'(function\s+spawn(?:Enemy|PowerUp|Item|Obstacle))\s*\((\w*[Ii]ndex\w*)\)\s*\{(.*?)\n\}',
        re.DOTALL
    )
    script = pattern.sub(_inject_field_if_missing, script)
    return script, fixes


def _fix_type_vs_name_property(script: str) -> tuple[str, list[str]]:
    """
    Corrige la confusion type.name / type.type sur les objets de tableaux de définition
    (ENEMY_TYPES, POWERUP_TYPES, WAVE_DEFS, etc.) dont la propriété d'identité s'appelle 'type'.

    Pattern: quand les définitions utilisent { type: "..." } mais que le code lit .name sur
    un élément issu de ces tableaux — last-def-wins entre L6 (génère les arrays) et L7/L9
    (réécrit les fonctions update en utilisant .name).

    Stratégie : si le script contient au moins un tableau de définition avec { type: "..." }
    et qu'il contient des accès .name sur des variables typiquement issues de ces tableaux
    (typeDef, enemyType, powerupDef, waveDef, etc.) → remplacer .name par .type.
    """
    fixes = []
    # Vérifie si le script utilise le pattern { type: "..." } dans des arrays de defs
    has_type_arrays = bool(re.search(
        r'(?:ENEMY_TYPES|POWERUP_TYPES|WAVE_DEFS|ITEM_TYPES|WEAPON_TYPES|UPGRADE_TYPES|OBSTACLE_TYPES)\s*=\s*\[',
        script
    ))
    if not has_type_arrays:
        return script, fixes

    # Remplace typeDef.name, enemyType.name, etc. → .type
    _TYPE_VAR_PATTERN = r'\b(typeDef|enemyType|enemyDef|powerupDef|powerupType|waveDef|itemDef|itemType|weaponDef|weaponType|upgradeDef|upgradeType|obstacleDef|obstacleType|type)\s*\.\s*name\b'

    def _replace_name(m):
        var = m.group(1)
        fixes.append(f'[AUTO-FIX] {var}.name → {var}.type (propriété identité = "type" dans les arrays de définition)')
        return var + '.type'

    new_script = re.sub(_TYPE_VAR_PATTERN, _replace_name, script)
    return new_script, fixes


def _fix_no_args_handlers_in_gameloop(script: str) -> tuple[str, list[str]]:
    """
    Supprime les appels sans arguments à des handlers de collision/événement dans la gameLoop.
    Ex: handleBulletEnemyHit() → supprimé (déjà appelé avec args dans checkCollisions())
    Cause: le Patcher injecte parfois ces appels dans la gameLoop sans passer les paramètres,
    ce qui provoque 'Cannot read properties of undefined' au runtime.
    """
    fixes = []
    # Handlers qui sont TOUJOURS appelés via checkCollisions() avec des args — jamais directement
    _HANDLER_PREFIXES = (
        'handleBulletEnemyHit', 'handleEnemyBulletHit', 'handlePlayerEnemyHit',
        'handleBossBulletHit', 'handlePlayerBossHit', 'handlePowerUpCollect',
        'handleBulletBossHit', 'handleBulletHit', 'handleEnemyHit',
    )
    # Trouver la gameLoop pour limiter la recherche (éviter de toucher checkCollisions lui-même)
    gameloop_m = re.search(r'function\s+gameLoop\b', script)
    if not gameloop_m:
        return script, fixes

    gameloop_start = gameloop_m.start()
    # Chercher uniquement dans le corps de la gameLoop (heuristique : ~200 lignes après)
    gameloop_body_end = min(len(script), gameloop_start + 8000)
    prefix = script[:gameloop_start]
    body = script[gameloop_start:gameloop_body_end]
    suffix = script[gameloop_body_end:]

    for handler in _HANDLER_PREFIXES:
        # Appel sans arguments : handler(); ou handler() ; (avec espaces éventuels)
        pattern = re.compile(r'\b' + re.escape(handler) + r'\s*\(\s*\)\s*;[^\n]*\n?')
        new_body, n = re.subn(pattern, '', body)
        if n:
            body = new_body
            fixes.append(f'[AUTO-FIX] {handler}() sans args supprimé de gameLoop (géré par checkCollisions)')

    return prefix + body + suffix, fixes


def _fix_boss_defs_access(script: str) -> tuple[str, list[str]]:
    """
    Corrige BOSS_DEFS['level' + level] quand BOSS_DEFS est un objet plat (non indexé par niveau).
    Symptôme : spawnBoss() fait BOSS_DEFS['level1'] → undefined → guard if (!bossDef) return → boss jamais spawné.
    Fix : remplace par BOSS_DEFS['level' + level] || BOSS_DEFS pour le fallback sur l'objet plat.
    Ajoute aussi vx/shootTimer/spawnDroneTimer/invTimer si absents dans l'objet boss créé.
    """
    fixes = []

    # Fix 1 : fallback sur l'objet plat
    pat = re.compile(r"BOSS_DEFS\s*\[\s*['\"]level['\"]?\s*\+\s*\w+\s*\](?!\s*\|\|)")
    if pat.search(script):
        script = pat.sub(lambda m: m.group(0) + ' || BOSS_DEFS', script)
        fixes.append('[AUTO-FIX] BOSS_DEFS[\'level\' + level] → || BOSS_DEFS (fallback objet plat)')

    # Fix 2 : BOSS_DEFS[boss.type] (aussi incorrect pour objet plat) → BOSS_DEFS
    pat2 = re.compile(r"BOSS_DEFS\s*\[\s*boss\s*\.\s*type\s*\]")
    if pat2.search(script):
        script = pat2.sub('BOSS_DEFS', script)
        fixes.append('[AUTO-FIX] BOSS_DEFS[boss.type] → BOSS_DEFS (objet plat)')

    # Fix 3 : injecter vx/shootTimer/invTimer dans l'objet boss si absents
    spawn_boss_pat = re.compile(r'(function\s+spawnBoss\s*\([^)]*\)\s*\{.*?boss\s*=\s*\{)(.*?)(\})', re.DOTALL)
    def _patch_boss_obj(m):
        content = m.group(2)
        changed = False
        for prop, val in [('vx', '40'), ('shootTimer', '1.0'), ('invTimer', '0'), ('spawnDroneTimer', '5.0')]:
            if not re.search(r'\b' + prop + r'\s*:', content):
                content += f'\n        {prop}: {val},'
                changed = True
        if changed:
            fixes.append('[AUTO-FIX] spawnBoss(): vx/shootTimer/invTimer/spawnDroneTimer ajoutés')
            return m.group(1) + content + m.group(3)
        return m.group(0)
    script = spawn_boss_pat.sub(_patch_boss_obj, script)

    return script, fixes


def _fix_eval_in_production(script: str) -> tuple[str, bool]:
    """
    Supprime les patches de débogage window.__devPatch / window.__debug etc.
    """
    original = script
    script = re.sub(
        r'window\.__(?:devPatch|debug|patch|eval|test)\s*=\s*function.*?\}\s*;',
        '/* debug removed */',
        script,
        flags=re.DOTALL
    )
    return script, script != original


# ─────────────────────────────────────────────────────────────
# CHECKS DIAGNOSTIQUES (sans fix)
# ─────────────────────────────────────────────────────────────

def _diagnostic_checks(script: str) -> list[str]:
    """
    Vérifie les conditions critiques qui empêchent le jeu de fonctionner.
    Retourne des messages 'CRITIQUE: ...' pour les problèmes non corrigés.
    """
    issues: list[str] = []

    # Boucle de jeu manquante
    if not any(s in script for s in ['requestAnimationFrame', 'setInterval', 'setTimeout']):
        issues.append(
            'CRITIQUE: boucle de jeu manquante — requestAnimationFrame/setInterval absent'
        )

    # getContext manquant (seulement si pas Three.js)
    if 'getContext' not in script and 'THREE.' not in script:
        issues.append(
            'CRITIQUE: getContext manquant — canvas.getContext(\'2d\') jamais appelé'
        )

    # Stubs vides : update() ou draw() sans corps significatif
    _stub_issues = _check_empty_stubs(script)
    issues.extend(_stub_issues)

    return issues


def _check_empty_stubs(script: str) -> list[str]:
    """
    Détecte les fonctions critiques (update, draw, render, gameLoop) avec un corps vide
    ou quasi-vide (uniquement commentaires/return vide). Ces stubs donnent l'impression
    que le jeu fonctionne mais l'écran reste noir.
    """
    issues = []
    CRITICAL_FUNS = ['update', 'draw', 'render', 'gameLoop', 'loop', 'tick', 'animate']

    for fn_name in CRITICAL_FUNS:
        # Chercher la définition de la fonction
        m = re.search(
            rf'\bfunction\s+{re.escape(fn_name)}\s*\([^)]*\)\s*\{{',
            script
        )
        if not m:
            continue
        # Extraire le corps (jusqu'à l'accolade fermante correspondante)
        depth, start = 0, m.end() - 1
        body_start = m.end()
        i = start
        while i < min(start + 3000, len(script)):
            if script[i] == '{':
                depth += 1
            elif script[i] == '}':
                depth -= 1
                if depth == 0:
                    body = script[body_start:i]
                    break
            i += 1
        else:
            continue

        # Corps significatif = au moins 3 lignes non vides non commentaires
        # OU corps minifié sur 1 ligne mais substantiel (> 120 chars) — fonctions ENGINE
        meaningful_lines = [
            ln.strip() for ln in body.split('\n')
            if ln.strip() and not ln.strip().startswith('//')
            and ln.strip() not in ('{', '}', 'return;', 'return')
        ]
        body_chars = len(body.strip())
        if len(meaningful_lines) < 3 and body_chars < 120:
            issues.append(
                f'CRITIQUE: fonction {fn_name}() quasi-vide ({len(meaningful_lines)} ligne(s) — stub) '
                f'— le jeu ne peut pas fonctionner'
            )

    return issues


# ─────────────────────────────────────────────────────────────
# UTILITAIRES INTERNES
# ─────────────────────────────────────────────────────────────

def _collect_declarations(script: str) -> set[str]:
    """
    Collecte tous les noms de variables déclarées dans le script.
    Gère :
      - `let x = ...`  /  `const x = ...`  /  `var x = ...`
      - `let a, b, c;`  (déclarations multiples sans initialisation)
      - `let a = 0, b, c = [];`  (déclarations multiples avec init mélangée)
      - paramètres de fonctions  function f(a, b, c)
      - variables de boucle for (let i = ...)
    """
    declared: set[str] = set()

    # Scan let/const/var → lire jusqu'au ; ou { ou } qui termine la déclaration
    for m in re.finditer(r'\b(?:let|const|var)\b', script):
        seg_start = m.end()
        seg_end = min(len(script), seg_start + 400)
        # Chercher la fin du statement (';', '{', '}' ou saut de ligne double)
        seg = script[seg_start:seg_end]
        end_match = re.search(r'[;{}]', seg)
        if end_match:
            seg = seg[:end_match.start()]
        # Séparer par virgule et extraire le premier identifiant de chaque partie
        for part in seg.split(','):
            part = part.strip()
            id_match = re.match(r'([a-zA-Z_$][a-zA-Z0-9_$]*)', part)
            if id_match:
                name = id_match.group(1)
                # Exclure les mots-clés JS qui ne sont pas des vars
                if name not in ('function', 'if', 'else', 'for', 'while', 'do',
                                'return', 'new', 'class', 'this', 'typeof',
                                'instanceof', 'in', 'of', 'async', 'await'):
                    declared.add(name)

    # Paramètres de fonctions
    for params_str in re.findall(r'\bfunction\s*\w*\s*\(([^)]*)\)', script):
        for p in params_str.split(','):
            p = p.strip().lstrip('...')
            id_match = re.match(r'([a-zA-Z_$][a-zA-Z0-9_$]*)', p)
            if id_match:
                declared.add(id_match.group(1))

    return declared


def _strip_strings_comments(s: str) -> str:
    """Supprime les chaînes littérales et commentaires pour éviter les faux positifs."""
    # Chaînes double quotes
    s = re.sub(r'"(?:[^"\\]|\\.)*"', '""', s)
    # Chaînes simple quotes
    s = re.sub(r"'(?:[^'\\]|\\.)*'", "''", s)
    # Template literals (approximation — pas de regex parfaite pour les imbriqués)
    s = re.sub(r'`[^`]*`', '``', s)
    # Commentaires // et /* */
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
    return s


def _count_braces_precise(script: str) -> int:
    """
    Compte la balance des accolades en parcourant char par char.
    Ignore les accolades dans les chaînes et les commentaires.
    Retourne le delta (>0 = trop d'ouvertures, <0 = trop de fermetures).
    """
    depth = 0
    in_single = False
    in_double = False
    in_template = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    n = len(script)

    while i < n:
        ch = script[i]
        next_ch = script[i + 1] if i + 1 < n else ''

        # Gestion des commentaires ligne
        if in_line_comment:
            if ch == '\n':
                in_line_comment = False
            i += 1
            continue

        # Gestion des commentaires bloc
        if in_block_comment:
            if ch == '*' and next_ch == '/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Début commentaires
        if not in_single and not in_double and not in_template:
            if ch == '/' and next_ch == '/':
                in_line_comment = True
                i += 2
                continue
            if ch == '/' and next_ch == '*':
                in_block_comment = True
                i += 2
                continue

        # Gestion des chaînes
        if ch == '\\' and (in_single or in_double or in_template):
            i += 2  # skip escaped char
            continue

        if ch == "'" and not in_double and not in_template:
            in_single = not in_single
            i += 1
            continue

        if ch == '"' and not in_single and not in_template:
            in_double = not in_double
            i += 1
            continue

        if ch == '`' and not in_single and not in_double:
            in_template = not in_template
            i += 1
            continue

        # Compter les accolades (hors chaînes)
        if not in_single and not in_double and not in_template:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1

        i += 1

    return depth


def _fix_missing_gameloop_calls(script: str) -> tuple[str, list[str]]:
    """
    Detects zero-arg update*/draw* functions defined but never called from the game loop.
    Injects the missing calls at the top of gameLoop()/update() body.
    Conservative: only touches zero-param functions, verifies syntax after injection.
    """
    fixes: list[str] = []
    # Only inject if there is a clear game loop entry point
    gameloop_m = re.search(r'function\s+(gameLoop|update)\s*\(\s*\)\s*\{', script)
    if not gameloop_m:
        return script, fixes

    # Collect zero-param update*/draw* definitions (not draw() itself — too generic)
    defined = re.findall(r'\bfunction\s+((?:update|draw)[A-Z]\w*)\s*\(\s*\)', script)
    if not defined:
        return script, fixes

    missing = []
    for fn in defined:
        # Check if the function is called (an occurrence NOT preceded by 'function' on same line)
        _call_found = False
        for _m in re.finditer(r'\b' + re.escape(fn) + r'\s*\(', script):
            _line_start = script.rfind('\n', 0, _m.start()) + 1
            _before = script[_line_start:_m.start()]
            if not re.search(r'\bfunction\s*$', _before):
                _call_found = True
                break
        if not _call_found:
            missing.append(fn)

    if not missing:
        return script, fixes

    # Inject calls at the start of the game loop body (limit to 4 injections max)
    missing = missing[:4]
    inject_pos = gameloop_m.end()  # right after the opening {
    injection = '\n    ' + '\n    '.join(f'{fn}();  // B4b: auto-injected' for fn in missing)
    new_script = script[:inject_pos] + injection + script[inject_pos:]

    # Validate the injection doesn't break syntax
    try:
        from js_syntax_checker import check_syntax as _chk_b4b
        _tmp_html = f'<script>{new_script}</script>'
        if _chk_b4b(_tmp_html):
            return script, fixes  # injection broke syntax — skip
    except Exception:
        return script, fixes  # can't validate — skip

    for fn in missing:
        fixes.append(f'[AUTO-FIX B4b] {fn}() missing from game loop — injected call')
    return new_script, fixes


def _log_results(issues: list[str]) -> None:
    """Logue le bilan de la validation."""
    if not issues:
        return
    n_auto = sum(1 for i in issues if '[AUTO-FIX]' in i)
    n_total = len(issues)
    coordinateur_log.info(f'Validation code : {n_total} problème(s), {n_auto} auto-corrigé(s)')
    for issue in issues:
        coordinateur_log.info(f'  {issue}')

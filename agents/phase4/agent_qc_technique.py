"""
Agent QC Technique — Phase 4
Evaluates code on adaptive technical criteria based on genre.
Criteria come from the GenreProfile (generated in Phase 1).
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, EvaluationResult
from logger import phase4_log

SYSTEM_2D = """You are an expert in HTML5 Canvas/JavaScript game development. You analyze code
with precision and objectivity. You identify technical strengths and weaknesses.
You respond ONLY in valid JSON."""

SYSTEM_3D = """You are an expert in 3D web game development with Three.js. You analyze
Three.js/WebGL code with precision. You know Three.js patterns: Scene, Camera, Renderer, Clock,
geometries, materials, lighting, 3D collisions. You respond ONLY in valid JSON."""

CRITERES_UNIVERSELS_2D = """SCORING RUBRIC (guide your evaluation — be precise and strict):
- 0-3 : Non-functional game (crash, black screen, empty stub, no game logic)
- 4-5 : Basic game that runs but lacks depth (1 enemy type, no boss, no particles)
- 6   : Correct — functional core loop, some features but lacks rich systems
- 7   : Good — clean code, 2-3 enemy types, boss or wave system, working collisions
- 8   : Very good — boss with phases, combo/power-ups/particles implemented, clean restart, highscore
- 9   : Excellent — all genre systems present, visible polish (shake, glow, floatTexts, transitions)
- 10  : Exceptional (reserve for a truly remarkable game — rare)

BLOCKING criteria — severe penalty if absent (non-functional game):
- DOMContentLoaded wrapping ALL code (canvas retrieved after DOM)
- requestAnimationFrame for the game loop (not setInterval or setTimeout)
- Delta time calculated and used in movement (no fixed speeds)
- Canvas retrieved via getElementById INSIDE the DOMContentLoaded callback
- No .clear() on arrays (TypeError) — use .length = 0
- LOOP VAR INIT: `for (let i = arr.length-1; i >= 0; i--)` → body starts with `const X = arr[i]`
- FOR-OF SPLICE: `for (const x of arr)` must NEVER contain `arr.splice()`
- CONST REASSIGNMENT: `const score = 0` then `score += 10` → TypeError — mutable scalars = `let`
- DT PASSING: functions that use `dt` MUST have it as a parameter (updateEnemies, updateBoss, etc.)
- `dist` calculated BEFORE being used in if(dist < ...) — no variable appearing out of thin air
- NO eval(), window.__devPatch, new Function() in production
- Key functions NON-STUB: updatePlayer(), updateEnemies(), checkCollisions() with real body (not just comments)
- Startable menu: SPACE or Enter → gameState = 'playing'
- Initialization at start: initGame() calls spawnEnemies()/generateLevel() — no empty arrays

BASIC QUALITY criteria (fundamentals — penalty if absent):
- Clean state machine: gameState ∈ {menu, playing, paused, gameover} used everywhere
- Complete restart without location.reload() — all variables reset to zero
- Working collisions (AABB or distance) — no ghost or missed collisions
- Score + highscore in localStorage — displayed on menu AND in game
- Responsive canvas (window.innerWidth/innerHeight)
- Consistent keys{} object with same names everywhere (avoid keys['ArrowLeft'] vs keys.left)

GAMEPLAY DEPTH criteria (major impact on score — what distinguishes a good game):
- ENEMY VARIETY: ≥ 3 distinct enemy types (different behaviors, not just recolors) → +1pt
- BOSS SYSTEM: boss with high HP, distinct attack pattern, AND ≥ 2 phases (HP% thresholds) → +1pt
- WAVE SYSTEM: progressive difficulty (speed/count/types per wave) → +0.5pt
- POWER-UPS: ≥ 2 collectable types with distinct effects (duration, activation, visual) → +0.5pt
- COMBO/MULTIPLIER: combo system (consecutive kills → multiplied score) → +0.5pt
- PARTICLES: spawnExplosion/spawnParticles + updateParticles() actually called → +0.5pt
- RICH VISUAL FEEDBACK: screen shake (triggerShake), floating texts (spawnFloatText), flash overlay → +0.5pt
- PLAYER PROGRESSION: XP/level OR upgrade OR ability unlock during gameplay → +0.5pt

DUNGEON/RPG criteria (if genre is RPG, dungeon, adventure — check imperatively):
- Enemy knockback: enemies receive an impulse when hit AND do not pass through walls (knockbackVX/VY with wall stop)
- Visual contrast: light floor vs dark wall (perceptible difference), enemies a different color from the floor
- Boss room made visible: BOSS_WALL not pure black, boss room floor distinct
- Corridors ≥ 3 tiles wide: verify in procedural generation that corridors have width ≥ 3
- Varied loot: chests use a loot table with ≥ 4 different item types (rollLoot / LOOT_TABLE)
- Impactful level up: checkLevelUp() increases max HP by at least 15% + full heal + floating text with gains
- Speed balance: normal enemy speed ≤ 90% player speed — check numeric values
- Readable texts: font ≥ 7px in pixel art, ≥ 13px in full-screen canvas
- Registry callbacks with optional chaining: ENEMY_TYPES[x].onAttack?.() not onAttack() — check all method calls on type objects
- Timers initialized: any xyzTimer used in updateBoss/updateEnemy must be initialized in createEnemy/spawnBoss (e.g. cloneTimer, summonTimer, teleportTimer)
- No double const/let in same function: look for two declarations of the same name in generateDungeon, update, draw...
- Boss spawns in generateDungeon(): no lazy conditional spawn that can fail
- No heavy computation in draw()/update(): drawMap() iterates only over visible tiles (frustum culling)
- Screen shake dosed: triggerShake mag ≤ 2 on normal damage, ≥ 6 only on death/boss transition
- Attack animations: hero.attackFlash or visible sweep arc during an attack
- Skill cooldown displayed: visible bar or timer in HUD for each skill with cooldown
- UNIQUE boss damage source: boss damage comes either from collision check or onAttack — NOT both (double damage = instant death)
- Balanced boss stats: boss.attack ≤ 15% player maxHP, boss.attackRadius ≤ TILE_SIZE, boss.speed phase1 ≤ player speed * 0.5
- Post-attack boss recoil: boss._recoilTimer > 0 → boss retreats 0.6–1.0s after each hit (evasion window for player)
- Distinctive boss visuals: pulsing aura (animated semi-transparent arc), ★ BOSS ★ indicator above, mini health bar on sprite, sizeFactor ≥ 2.0"""

CRITERES_UNIVERSELS_3D = """BLOCKING criteria (error = non-functional game):
- DOMContentLoaded wrapping all Three.js code (NEVER THREE.* at top-level)
- THREE.WebGLRenderer created and added to body (document.body.appendChild(renderer.domElement))
- AmbientLight present (otherwise all black)
- DirectionalLight present (otherwise no shadows/relief)
- THREE.Clock used for delta time (clock.getDelta(), capped at 0.05)
- requestAnimationFrame for the game loop — gameLoop() launched immediately in DOMContentLoaded
- scene.background defined (Color or Texture) — otherwise transparent background
- No .clear() on arrays — use .length = 0
- scene.remove(mesh) called when removing entities (otherwise memory leak)

QUALITY criteria (impact on score):
- 3D collisions via THREE.Box3.setFromObject() + intersectsBox() (not just distance-based)
- HTML overlay HUD (fixed divs over canvas — not a 2D canvas)
- Clean restart: scene.remove() for all meshes + arrays.length = 0 + reset vars
- Responsive canvas: window.addEventListener('resize') with camera.aspect + renderer.setSize
- Best score in localStorage
- At least 3 distinct Three.js geometries (BoxGeometry, SphereGeometry, CylinderGeometry...)
- MeshPhongMaterial or MeshStandardMaterial (not only MeshBasicMaterial)
- Three.js particles (THREE.Points) or at least one dynamic visual effect
- renderer.shadowMap.enabled + castShadow/receiveShadow on main objects"""


def _detect_orphan_functions(code: str) -> list[str]:
    """
    F1: Detects functions defined but never called ANYWHERE in the code.
    Searches for fn( throughout the entire code — covers forEach/map/for loops, callbacks, etc.
    Returns a list of orphan function names.
    """
    import re
    # Extract all defined function names
    defined = set(re.findall(r'function\s+([a-zA-Z_$][\w$]*)\s*\(', code))
    # Ignore built-in and structural functions (M3: extended list)
    ignore = {
        'init', 'gameLoop', 'animate', 'loop', 'tick', 'render', 'main',
        'DOMContentLoaded', 'onload', 'onclick', 'onkeydown', 'onkeyup',
        'addEventListener', 'removeEventListener',
        # Standard canvas/web functions
        'requestAnimationFrame', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        # Common event handlers
        'onmousedown', 'onmouseup', 'onmousemove', 'ontouchstart', 'ontouchmove', 'ontouchend',
        'onresize', 'onblur', 'onfocus', 'oncontextmenu',
        # Common structural functions (may be called indirectly)
        'update', 'draw', 'start', 'stop', 'pause', 'resume', 'reset', 'restart',
        'setup', 'preload', 'create', 'destroy',
    }
    candidates = defined - ignore
    orphans = []
    for fn in candidates:
        # M3: Search for fn( in ALL code (not just gameLoop)
        # — covers forEach, map, for-loops, callbacks, nested calls
        call_pattern = re.compile(r'\b' + re.escape(fn) + r'\s*\(')
        def_pattern = re.compile(r'function\s+' + re.escape(fn) + r'\s*\(')
        all_occurrences = len(call_pattern.findall(code))
        definitions = len(def_pattern.findall(code))
        calls = all_occurrences - definitions
        if calls == 0:
            orphans.append(fn)
    return orphans


def run(code: str, genre_profile: GenreProfile) -> EvaluationResult:
    est_3d = genre_profile.technologie_rendu == "threejs"
    phase4_log.agent_start("QC Technique", f"Technical analysis {'Three.js 3D' if est_3d else 'Canvas 2D'}")

    criteres = genre_profile.criteres_qc_technique
    criteres_str = json.dumps(criteres, ensure_ascii=False) if criteres else "standard criteria"
    criteres_universels = CRITERES_UNIVERSELS_3D if est_3d else CRITERES_UNIVERSELS_2D
    system = SYSTEM_3D if est_3d else SYSTEM_2D
    techno_label = "Three.js (3D)" if est_3d else "Canvas 2D"

    # F4: Full code extraction 40KB (instead of 24KB truncated)
    from utils import extract_js_sample
    code_extrait = extract_js_sample(code, 40000)

    # F1: Detect orphan functions before LLM call
    _orphans = _detect_orphan_functions(code)
    _orphan_hint = ""
    if _orphans:
        phase4_log.warning(f"F1: {len(_orphans)} orphan function(s): {', '.join(_orphans[:6])}")
        _orphan_hint = (
            f"\n\nORPHAN FUNCTIONS DETECTED (defined but never called — flag as critical issues):\n"
            + "\n".join(f"  - {fn}()" for fn in _orphans[:10])
            + "\nThese functions NEVER contribute to the game. Add a critical issue for each one."
        )

    prompt = f"""Technically analyze this HTML5 game code ({techno_label}) for a {genre_profile.genre_principal}.

CODE (excerpt):
```html
{code_extrait}
```

CRITERIA SPECIFIC TO GENRE {genre_profile.genre_principal.upper()}:
{criteres_str}

TECHNICAL CRITERIA {techno_label.upper()} to check:
{criteres_universels}{_orphan_hint}

For each criterion, give a score from 0.0 to its maximum weight and a comment.

Respond in JSON:
{{
  "criteres_evalues": [
    {{
      "nom": "...",
      "score_obtenu": 1.5,
      "score_max": 1.5,
      "present": true,
      "commentaire": "..."
    }}
  ],
  "issues": [
    {{
      "severite": "critique / majeur / mineur",
      "description": "Precise description: which variable/pattern is broken",
      "fonction_concernee": "exact name of the concerned JS function (e.g. updateEnemies, loadGame, checkCollisions)",
      "pattern_a_chercher": "exact code excerpt to find (e.g. 'for (let i = 0; i < enemies.length' or 'localStorage.getItem')",
      "suggestion": "concrete fix in 1-2 lines"
    }}
  ],
  "points_forts": ["...", "..."],
  "score_total": 8.5,
  "commentaire_global": "..."
}}"""

    result = _call(prompt, system)
    ev = _parse(result, "QC Technique")

    # F1: Inject orphan functions as automatic critical issues
    if _orphans:
        for _fn in _orphans[:5]:
            ev.issues.insert(0, {
                "severite": "critique",
                "description": f"F1: orphan function '{_fn}()' — defined but never called from gameLoop/update/draw",
                "fonction_concernee": _fn,
                "pattern_a_chercher": f"function {_fn}(",
                "suggestion": f"Call {_fn}() in gameLoop() or in the appropriate update/draw function"
            })

    return ev


def _parse(result: dict, agent_name: str) -> EvaluationResult:
    ev = EvaluationResult(agent_name=agent_name)
    ev.criteres = result.get("criteres_evalues", [])
    ev.issues = result.get("issues", [])
    ev.points_forts = result.get("points_forts", [])
    ev.score = float(result.get("score_total", 5.0))
    ev.commentaire_global = result.get("commentaire_global", "")
    ev.score = max(0.0, min(10.0, ev.score))

    phase4_log.score("QC Technique", ev.score)
    critiques = [i for i in ev.issues if i.get("severite") == "critique"]
    if critiques:
        phase4_log.warning(f"{len(critiques)} critical issue(s) detected")
    return ev


# _sample_code replaced by utils.extract_js_sample (JS extraction + sampling)

@with_fallback({
    "criteres_evalues": [],
    "issues": [{"severite": "majeur", "description": "Technical QC analysis failed", "suggestion": "Retry"}],
    "points_forts": [],
    "score_total": 5.0,
    "commentaire_global": "Analysis unavailable"
})
def _call(prompt: str, system: str = SYSTEM_2D) -> dict:
    return call_gemini_json(prompt, temperature=0.2, system_instruction=system)

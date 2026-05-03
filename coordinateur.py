"""
Coordinator — Main entry point of the system.
Orchestrates the 5 phases and the ReAct loop.

Usage:
    python coordinateur.py "un jeu de plateforme avec des ennemis robots"
    python coordinateur.py  (interactive mode)
"""

import sys
import os
import re
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Core imports
from logger import coordinateur_log, init_session, get_thread_event_queue, set_thread_event_queue, get_session_log, push_event
from genre_profile import GenreProfile, ConceptionContext, EvaluationBundle, EvaluationResult
import memory



def _export_failure_log(
    genre: str, titre: str, score: float, exec_score: float,
    issues: list, log_content: str = "", label: str = "failed"
) -> None:
    """
    Task P — Exports a structured failure log to failures_log.json.
    Used by auto_learner and for the /api/stats dashboard.
    """
    import json, os
    failures_path = os.path.join(os.path.dirname(__file__), "failures_log.json")
    try:
        if os.path.exists(failures_path):
            with open(failures_path, "r", encoding="utf-8") as f:
                failures = json.load(f)
        else:
            failures = []
    except Exception:
        failures = []

    failures.append({
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "genre": genre,
        "titre": titre,
        "score_global": round(score, 2),
        "exec_score": round(exec_score, 2),
        "label": label,
        "top_issues": [
            i.get("description", str(i)) if isinstance(i, dict) else str(i)
            for i in issues[:10]
        ],
    })
    # Keep the last 100 failures
    failures = failures[-100:]
    with open(failures_path, "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)


def _make_minimal_fallback_game(titre: str, genre: str) -> str:
    """
    Session 14 — Generates a minimal guaranteed-functional game in pure Python.
    Used when ALL iterations have failed with exec < 4.5 AND syntactically invalid code.
    It's a simple game but it WORKS 100%.
    """
    import html as _html_mod
    titre_safe = _html_mod.escape(titre[:40])
    genre_safe = _html_mod.escape(genre[:20])
    return f"""<!DOCTYPE html>
<html><head><title>{titre_safe}</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0a1a;overflow:hidden;font-family:'Courier New',monospace;}}
canvas{{display:block;}}
</style></head><body>
<canvas id="gameCanvas"></canvas>
<script>
var canvas = document.getElementById('gameCanvas');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
var ctx = canvas.getContext('2d');
var W = canvas.width, H = canvas.height;

var score = 0, lives = 3, gameState = 'menu';
var player = {{ x: W/2, y: H/2, r: 20, vx: 0, vy: 0, speed: 200 }};
var enemies = [], bullets = [], lastTime = 0, spawnTimer = 0;
var keys = {{}};

document.addEventListener('keydown', function(e) {{
    keys[e.code] = true;
    if (e.code === 'Space') e.preventDefault();
}});
document.addEventListener('keyup', function(e) {{ keys[e.code] = false; }});
canvas.addEventListener('click', function(e) {{
    if (gameState === 'menu') {{ gameState = 'playing'; initGame(); }}
    else if (gameState === 'gameover') {{ gameState = 'menu'; }}
}});

function initGame() {{
    score = 0; lives = 3; enemies = []; bullets = [];
    player.x = W/2; player.y = H/2; player.vx = 0; player.vy = 0;
    spawnTimer = 0;
}}

function spawnEnemy() {{
    var angle = Math.random() * Math.PI * 2;
    var dist = Math.max(W, H) * 0.6;
    enemies.push({{
        x: W/2 + Math.cos(angle) * dist,
        y: H/2 + Math.sin(angle) * dist,
        r: 14, speed: 60 + Math.random() * 40 + score * 0.05,
        hp: 2, color: '#F44'
    }});
}}

function update(dt) {{
    if (gameState !== 'playing') return;
    var dx = 0, dy = 0;
    if (keys['ArrowLeft'] || keys['KeyA']) dx -= 1;
    if (keys['ArrowRight'] || keys['KeyD']) dx += 1;
    if (keys['ArrowUp'] || keys['KeyW']) dy -= 1;
    if (keys['ArrowDown'] || keys['KeyS']) dy += 1;
    var len = Math.sqrt(dx*dx + dy*dy) || 1;
    if (dx !== 0 || dy !== 0) {{ player.x += dx/len * player.speed * dt; player.y += dy/len * player.speed * dt; }}
    player.x = Math.max(player.r, Math.min(W-player.r, player.x));
    player.y = Math.max(player.r, Math.min(H-player.r, player.y));

    if (keys['Space'] && bullets.length < 8) {{
        keys['Space'] = false;
        var nearest = null, nd = Infinity;
        enemies.forEach(function(en) {{ var d = Math.hypot(en.x-player.x, en.y-player.y); if(d < nd){{ nd = d; nearest = en; }} }});
        var bdir = nearest ? {{ x:(nearest.x-player.x)/nd, y:(nearest.y-player.y)/nd }} : {{ x:0, y:-1 }};
        bullets.push({{ x:player.x, y:player.y, vx:bdir.x*350, vy:bdir.y*350, r:6 }});
    }}

    for (var i = bullets.length-1; i >= 0; i--) {{
        var b = bullets[i]; b.x += b.vx*dt; b.y += b.vy*dt;
        if (b.x<0||b.x>W||b.y<0||b.y>H) {{ bullets.splice(i,1); continue; }}
        var hit = false;
        for (var j = enemies.length-1; j >= 0; j--) {{
            var en = enemies[j];
            if (Math.hypot(b.x-en.x, b.y-en.y) < b.r+en.r) {{
                en.hp--; hit = true;
                if (en.hp <= 0) {{ score += 10; enemies.splice(j,1); }}
                break;
            }}
        }}
        if (hit) bullets.splice(i,1);
    }}

    for (var i = enemies.length-1; i >= 0; i--) {{
        var en = enemies[i];
        var edx = player.x-en.x, edy = player.y-en.y, ed = Math.hypot(edx,edy)||1;
        en.x += edx/ed*en.speed*dt; en.y += edy/ed*en.speed*dt;
        if (Math.hypot(en.x-player.x, en.y-player.y) < en.r+player.r) {{
            lives--; enemies.splice(i,1);
            if (lives <= 0) gameState = 'gameover';
        }}
    }}

    spawnTimer -= dt;
    if (spawnTimer <= 0) {{ spawnEnemy(); spawnTimer = Math.max(0.5, 2.0 - score*0.005); }}
}}

function draw() {{
    ctx.fillStyle = '#0a0a1a'; ctx.fillRect(0,0,W,H);
    if (gameState === 'menu') {{
        ctx.fillStyle = '#0AF'; ctx.font = 'bold 36px Courier New'; ctx.textAlign = 'center';
        ctx.fillText('{titre_safe}', W/2, H/2-40);
        ctx.fillStyle = '#888'; ctx.font = '18px Courier New';
        ctx.fillText('Genre: {genre_safe}', W/2, H/2);
        ctx.fillStyle = '#FFF'; ctx.fillText('Clic pour jouer | WASD = mouvement | ESPACE = tir', W/2, H/2+40);
        ctx.textAlign = 'left'; return;
    }}
    if (gameState === 'gameover') {{
        ctx.fillStyle = '#F44'; ctx.font = 'bold 40px Courier New'; ctx.textAlign = 'center';
        ctx.fillText('GAME OVER', W/2, H/2-20);
        ctx.fillStyle = '#FFF'; ctx.font = '20px Courier New';
        ctx.fillText('Score: ' + score, W/2, H/2+20);
        ctx.fillText('Clic pour recommencer', W/2, H/2+55);
        ctx.textAlign = 'left'; return;
    }}
    // Draw enemies
    enemies.forEach(function(en) {{
        ctx.fillStyle = en.color; ctx.beginPath(); ctx.arc(en.x,en.y,en.r,0,Math.PI*2); ctx.fill();
    }});
    // Draw bullets
    ctx.fillStyle = '#FF0';
    bullets.forEach(function(b) {{ ctx.beginPath(); ctx.arc(b.x,b.y,b.r,0,Math.PI*2); ctx.fill(); }});
    // Draw player
    ctx.fillStyle = '#0AF'; ctx.beginPath(); ctx.arc(player.x,player.y,player.r,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = '#000'; ctx.beginPath(); ctx.arc(player.x,player.y,player.r*0.4,0,Math.PI*2); ctx.fill();
    // HUD
    ctx.fillStyle = '#FFF'; ctx.font = '16px Courier New';
    ctx.fillText('Score: ' + score + '   Vies: ' + lives, 16, 30);
}}

function gameLoop(ts) {{
    var dt = Math.min((ts - lastTime) / 1000, 0.05); lastTime = ts;
    update(dt); draw();
    requestAnimationFrame(gameLoop);
}}

requestAnimationFrame(gameLoop);
</script></body></html>"""


def _parallel(tasks: list, max_workers: int = 4, stagger_seconds: float = 1.0) -> dict:
    """
    Runs tasks in parallel, propagating the SSE queue to sub-threads.
    tasks = [(name, fn, [args...]), ...]
    stagger_seconds: delay between each submission to avoid RPM spikes.
    Returns {name: result}.
    """
    import time as _time
    current_queue = get_thread_event_queue()
    results = {}

    def _run(name, fn, args):
        if current_queue:
            set_thread_event_queue(current_queue)
        return name, fn(*args)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as ex:
        futures = {}
        for i, (name, fn, args) in enumerate(tasks):
            if i > 0 and stagger_seconds > 0:
                _time.sleep(stagger_seconds)
            futures[ex.submit(_run, name, fn, args)] = name
        for future in as_completed(futures):
            try:
                name, result = future.result()
                results[name] = result
            except Exception as e:
                name = futures[future]
                coordinateur_log.error(f"Parallel task '{name}' failed: {e}")
                results[name] = None
    return results

# Phase 1 — Intelligence
from agents.phase1 import (
    agent_intelligence_genre,   # merged researcher + watcher
    agent_enrichisseur,
    agent_architecte,
    agent_moderateur_classificateur,
)

# Phase 2 — Design
from agents.phase2 import (
    agent_game_designer,
    agent_tech_architect,
    agent_ux_designer,
    agent_level_designer,
    agent_game_logics,
    agent_scenariste,
)

# Phase 3 — Generation
from agents.phase3 import agent_createur, agent_assembleur, agent_js_linter

# Phase 4 — Evaluation
from agents.phase4 import (
    agent_qc_technique,
    agent_qc_gameplay,   # now includes anti_pattern
    agent_qc_visuel,
    agent_executeur,
    agent_playtester,
    agent_testeur_modules,
)

# Phase 5 — Iteration
from agents.phase5 import agent_diagnosticien, agent_patcher, agent_pre_patcher

# Support
from agents.support import agent_verdict_final, agent_sauvegarde, agent_auto_learner  # verdict_final = benchmark + neutral

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MAX_ITERATIONS = 4          # 4 iterations: generation + 3 patch/fix passes
SCORE_SEUIL_SAUVEGARDE = 7.5   # Minimum score to mark as "approved"
SCORE_SORTIE_ANTICIPEE = 8.5   # Score to exit early without iterating
SCORE_STAGNATION_DELTA = 0.2   # If score improves by less than this → stagnation
SCORE_MIN_VIABLE_SAVE  = 2.0   # Below this, no point saving (empty code)
# Number of consecutive iterations without progress before stagnation is declared
MAX_ITERATIONS_SANS_PROGRES = 2  # tolerate 1 "stuck" iteration — A2 fix can unblock
# E4: threshold to allow passes 3 and 4 (quota savings)
SCORE_SEUIL_ITERATIONS_SUP = 7.5  # Above this → 2 passes are enough
# C1: minimum scores per dimension (block save if not reached)
SCORE_MIN_EXECUTION = 5.0   # C1: execution must be >= 5.0
SCORE_MIN_TECHNIQUE = 5.5   # C1: technique must be >= 5.5
# I7: limit past_errors
MAX_ERREURS_PASSEES = 20


def _js_check_quick(html: str) -> tuple:
    """Quick JS syntax check to validate a patch before applying it."""
    try:
        from js_syntax_checker import check_and_report as _chk
        issues, broken = _chk(html)
        return issues, broken
    except ImportError:
        return [], False  # checker not installed — accept by default
    except Exception as e:
        coordinateur_log.warning(f"_js_check_quick unexpected error: {e} — patch accepted by default")
        return [], False


STYLE_GRAPHIQUE_MAP = {
    "pixel_art_gameboy":   "pixel art Game Boy 4 couleurs (style Pokémon Rouge/Bleu, résolution 160×144, palette : #0f380f #306230 #8bac0f #9bbc0f)",
    "pixel_art_nes_mario": "pixel art NES style Mario Bros (résolution 256×240, palette vive NES : rouges #D82800, bleus #0058F8, jaunes #F8B800, verts #00A800, blancs #FCFCFC, noirs #000000 — jusqu'à 16 couleurs simultanées)",
    "pixel_art_nes_zelda": "pixel art NES style Zelda (résolution 256×240, palette NES colorée et variée : herbe #70C848, eau #3CBCFC, doré #F8B800, rouge #D82800, violet #A800A8, gris #BCBCBC, skin #FCBCB0 — sprites 16×16, tuiles 8×8, fond sombre avec accents vifs)",
    "pixel_art_16bit":     "pixel art 16-bit SNES (résolution 320×240, palette très riche jusqu'à 256 couleurs, sprites détaillés 32×32, dégradés subtils, ombres portées pixel art)",
    "cartoon_2d":          "cartoon 2D coloré et expressif",
    "minimaliste":         "minimaliste géométrique épuré",
    "3d_lowpoly":          "3D low-poly",
}

def run(user_prompt: str, style_graphique: str = "", stop_event=None,
        _max_iterations: int | None = None) -> dict:
    """
    Main pipeline. Takes a prompt as input and returns a dict with:
    - genre_profile, gdd, code, scores, verdict, html_path
    style_graphique: optional key (e.g. "pixel_art_gameboy") — overrides auto-detection.
    stop_event: optional threading.Event — if triggered, the pipeline stops cleanly.
    _max_iterations: internal override for run_quick() (1 pass without remediation).
    """
    def _check_stop():
        if stop_event and stop_event.is_set():
            raise RuntimeError("Generation cancelled (SSE timeout)")
    init_session()
    memory.init_memory()
    start_time = time.time()

    coordinateur_log.section(f"ARCADE AI -- Game Generation")
    coordinateur_log.info(f"Prompt: '{user_prompt}'")
    coordinateur_log.info(f"Started at: {datetime.datetime.now().strftime('%H:%M:%S')}")
    push_event("timer_start", {"timestamp": start_time})

    # ─────────────────────────────────────────────
    # PHASE 1: MODERATION
    # ─────────────────────────────────────────────
    coordinateur_log.section("PHASE 1 — Intelligence & Enrichment")

    # Round 1: moderation + classification in ONE SINGLE call (optimization)
    mod_class = agent_moderateur_classificateur.run(user_prompt) or {}

    if not mod_class.get("valide", True):
        coordinateur_log.error(f"Prompt rejected: {mod_class.get('raison_rejet', '?')}")
        return {"erreur": mod_class.get("raison_rejet"), "code": None}

    cleaned_prompt = mod_class.get("prompt_nettoye", user_prompt) or user_prompt

    for avert in mod_class.get("avertissements", []):
        coordinateur_log.warning(f"Warning: {avert}")

    # If the classifier failed (fallback), detect genre by keywords
    _genre_raw = mod_class.get("genre_principal", "arcade")
    if _genre_raw == "arcade":
        import re as _re
        _p = cleaned_prompt.lower()
        # Whole-word matching to avoid false positives ("xp" in "explosions", etc.)
        def _kw_match(kw, text):
            if len(kw) <= 3:  # short words → check word boundaries
                return bool(_re.search(r'\b' + _re.escape(kw) + r'\b', text))
            return kw in text
        # Order: most specific genres first
        _genre_kw = {
            "shooter":       ["shooter", "shoot them up", "shmup", "bullet hell", "vaisseau", "tir automatique", "shoot"],
            "platformer":    ["platformer", "plateforme", "saut", "jump", "mario"],
            "tower defense": ["tower defense", "tourelle", "défense de base"],
            "puzzle":        ["puzzle", "réflexion", "casse-tête", "logique", "blocs"],
            "racing":        ["racing", "course automobile", "voiture", "kart"],
            "survival":      ["survival", "survie", "crafting", "zombie"],
            "roguelite":     ["roguelite", "roguelike", "procédural", "aléatoire"],
            "rpg":           ["rpg", "rôle", "quête", "donjon", "dungeon", "héros", "level up", "inventaire"],
            "aventure":      ["aventure", "exploration", "zelda"],
        }
        for genre, kws in _genre_kw.items():
            if any(_kw_match(kw, _p) for kw in kws):
                _genre_raw = genre
                coordinateur_log.info(f"Genre detected by keywords (classifier fallback): {_genre_raw}")
                break

    # Build a compatible Classification object from the merged response
    from genre_profile import Classification

    # Graphic style: forced by the user or auto-detected
    _style_force = STYLE_GRAPHIQUE_MAP.get(style_graphique, "") if style_graphique else ""
    if _style_force:
        # Style explicitly chosen — ignore auto-detection
        est_3d = style_graphique == "3d_lowpoly"
        style_visuel = _style_force
        coordinateur_log.info(f"Graphic style forced: {style_visuel}")
    else:
        # Auto-detection from the prompt
        est_3d = mod_class.get("technologie", "canvas2d") == "threejs"
        _kw_pixel = ["pixel art", "pixel-art", "rétro", "retro", "zelda", "pokemon",
                     "nes", "game boy", "gameboy", "8-bit", "16-bit", "8bit", "16bit"]
        _prompt_lower = cleaned_prompt.lower()
        est_pixel = any(kw in _prompt_lower for kw in _kw_pixel)
        if est_3d:
            style_visuel = "3D low-poly"
        elif est_pixel:
            style_visuel = "pixel art rétro"
        else:
            style_visuel = "cartoon 2D"
    classification = Classification(
        genre_principal=_genre_raw,
        sous_genre=mod_class.get("sous_genre", "action"),
        ton="casual",
        public_cible="tous publics",
        style_visuel_attendu=style_visuel,
        type_gameplay="arcade",
        confiance=0.7,
        raisonnement="",
    )

    # Round 2: genre intelligence (merged researcher + watcher in 1 call)
    research, trends = agent_intelligence_genre.run(classification)
    trends = trends or ""

    if trends:
        coordinateur_log.info(f"Genre intelligence: {len(trends)} chars of context")

    # Retrieve successful patterns + past errors for this genre
    successful_patterns = memory.get_patterns_for_genre(classification.genre_principal)
    if successful_patterns:
        coordinateur_log.info(f"{len(successful_patterns)} successful pattern(s) found in memory")

    past_errors = memory.get_errors_for_genre(classification.genre_principal)
    # Add known structural errors (from the validator)
    validator_errors = memory.get_validator_errors_for_genre(classification.genre_principal, n=3)
    if validator_errors:
        past_errors = list(past_errors) + [f"[STRUCTUREL] {e}" for e in validator_errors]
    # B3: immediate deduplication to avoid prompt pollution between iterations
    past_errors = list(dict.fromkeys(past_errors))
    if past_errors:
        coordinateur_log.info(f"{len(past_errors)} past error(s) retrieved for '{classification.genre_principal}'")

    # Q13 — Tracking fixed vs recurring errors
    # Each error is either a str or a dict {msg, fixed, iteration}
    # Normalize to a list of str with [FIXED] / [RECURRING] prefixes for prompts
    _erreurs_tracker: dict = {}  # msg_lower → {count, fixed}

    def _mark_error_fixed(issue_desc: str):
        """Marks an error as fixed in the tracker."""
        key = issue_desc[:80].lower()
        if key in _erreurs_tracker:
            _erreurs_tracker[key]['fixed'] = True

    def _record_error(issue_desc: str, iteration: int):
        """Records a newly encountered error."""
        key = issue_desc[:80].lower()
        if key not in _erreurs_tracker:
            _erreurs_tracker[key] = {'msg': issue_desc, 'count': 1, 'fixed': False, 'iter': iteration}
        else:
            _erreurs_tracker[key]['count'] += 1
            _erreurs_tracker[key]['fixed'] = False

    # Enrichment — create the GenreProfile
    genre_profile = agent_enrichisseur.run(cleaned_prompt, classification, research)

    # Propagate 3D detection from classifier to GenreProfile
    if est_3d:
        genre_profile.technologie_rendu = "threejs"
    else:
        genre_profile.technologie_rendu = "canvas2d"

    # Propagate narrative detection
    _is_narrative_raw = mod_class.get("is_narrative", False)
    genre_profile.is_narrative = bool(_is_narrative_raw)

    coordinateur_log.success(f"Phase 1 complete: {genre_profile.summary()}")

    # ─────────────────────────────────────────────
    # PHASE 2: DESIGN
    # ─────────────────────────────────────────────
    _check_stop()
    coordinateur_log.section("PHASE 2 — Design")

    # I14: Phase 2 fully in parallel — GDD + tech + ux + game_logics + level_designer
    # Game Designer runs in parallel with others on genre_profile only
    # then tech/ux/level/logics receive the GDD via result
    p2_gdd = _parallel([
        ("gdd", agent_game_designer.run, [genre_profile]),
    ], max_workers=1)
    gdd = p2_gdd["gdd"] or {}
    coordinateur_log.info(f"Game: '{gdd.get('titre', '?')}'")

    # G5 + B9: minimal GDD structure validation — retry if empty (timeout/malformed JSON)
    _gdd_title = (gdd.get('titre') or gdd.get('title') or gdd.get('nom') or '')
    _gdd_mechanics = (gdd.get('mecaniques_principales') or gdd.get('core_mechanics')
                      or gdd.get('mecaniques') or gdd.get('mechanics') or [])
    _gdd_systems = (gdd.get('systemes_jeu') or gdd.get('systemes_principaux')
                    or gdd.get('systems') or gdd.get('systemes') or gdd.get('game_systems') or {})
    if not _gdd_title:
        coordinateur_log.warning("B9/G5: GDD without title — retry agent_game_designer")
        _gdd_retry = agent_game_designer.run(genre_profile)
        if _gdd_retry and (_gdd_retry.get('titre') or _gdd_retry.get('title') or _gdd_retry.get('nom')):
            gdd = _gdd_retry
            _gdd_title = gdd.get('titre') or gdd.get('title') or gdd.get('nom') or ''
            coordinateur_log.success(f"B9: GDD retry OK — '{_gdd_title}'")
        else:
            coordinateur_log.warning("B9: GDD retry also empty — continuing with generic title")
    elif not _gdd_mechanics and not _gdd_systems:
        coordinateur_log.warning("G5: GDD without mechanics or systems detected (unexpected key?)")

    # I14: the 4 other Phase 2 agents in parallel (max_workers=4)
    p2 = _parallel([
        ("tech",         agent_tech_architect.run, [genre_profile, gdd]),
        ("ux",           agent_ux_designer.run,    [genre_profile, gdd]),
        ("game_logics",  agent_game_logics.run,    [genre_profile, gdd]),
        ("level_design", agent_level_designer.run, [genre_profile, gdd, {}]),
    ], max_workers=4)
    tech_specs    = p2["tech"]         or {}
    ux_specs      = p2["ux"]           or {}
    game_logics   = p2["game_logics"]  or ""
    level_design  = p2["level_design"] or {}

    # Narrative agent (optional — if narrative game)
    narrative_context = None
    if genre_profile.is_narrative:
        coordinateur_log.info("Narrative mode detected — calling narrative agent")
        push_event("agent_start", {"agent": "Scénariste", "phase": "PHASE2", "description": "Création histoire, quêtes et personnages"})
        narrative_context = agent_scenariste.run(genre_profile)
        push_event("agent_done", {"agent": "Scénariste", "phase": "PHASE2", "result": f"Histoire : {narrative_context.titre}"})

    # Assemble the design context
    context = ConceptionContext(
        genre_profile=genre_profile,
        gdd=gdd,
        tech_specs=tech_specs,
        ux_specs=ux_specs,
        level_design=level_design,
        narrative_context=narrative_context,
    )

    coordinateur_log.success("Phase 2 complete — full context assembled")

    # ─────────────────────────────────────────────
    # PHASE 3: GENERATION (modular)
    # ─────────────────────────────────────────────
    _check_stop()
    coordinateur_log.section("PHASE 3 — Game Generation")

    genre_principal_lower = (genre_profile.genre_principal or "").lower()
    sous_genre_lower = (genre_profile.sous_genre or "").lower()
    est_3d_genre = genre_profile.technologie_rendu == "threejs"

    # Generation strategy:
    # - Monolithic for ALL 2D games (more reliable, fewer failure points)
    # - Modular ONLY for 3D games (Three.js) where complexity justifies it
    use_modular = est_3d_genre

    CODE_MIN_VIABLE = 15000  # a real playable 2D game is >15K chars minimum

    # ─────────────────────────────────────────────
    # CODE GENERATION
    # ─────────────────────────────────────────────
    if use_modular:
        # 3D games — modular Three.js architecture
        coordinateur_log.info("3D route: modular Three.js generation")
        architecture = agent_architecte.run(context)

        from agents.phase3.agent_createur import run_modulaire
        generated = run_modulaire(
            context,
            architecture,
            patterns_reussis=successful_patterns,
            tendances=trends,
            erreurs_passees=past_errors,
            game_logics=game_logics,
        )

        # Module testing then assembly
        generated = agent_testeur_modules.run(generated)
        code = agent_assembleur.run(generated, context)
        coordinateur_log.success(f"3D code assembled: {len(code)} characters")
    else:
        # 2D games — ALWAYS via the 5-layer system (never monolithic)
        coordinateur_log.info("2D route: 5-layer generation (layered)")
        from agents.phase3._layer_gen import run_layered
        code = run_layered(
            context,
            patterns_reussis=successful_patterns,
            erreurs_passees=past_errors,
            game_logics=game_logics,        # A — detailed mechanics
            level_design=level_design,       # 4 — level structure
        )
        coordinateur_log.success(f"2D layered code: {len(code)} characters")

    # Basic sanity check: verify we have viable code
    game_title = context.gdd.get("titre", "Arcade Game")
    game_genre = genre_profile.genre_principal

    if not code or len(code) < 1000:
        coordinateur_log.warning("Code too short — guaranteed minimal fallback")
        if not use_modular:
            from agents.phase3._layer_gen import _run_compact_fallback
            code = _run_compact_fallback(context, erreurs_passees=past_errors)
        if not code or len(code) < 1000:
            code = _make_minimal_fallback_game(game_title, game_genre)

    coordinateur_log.success(f"Phase 3 complete: {len(code)} characters")

    # K4 — Factored coherence_check + A1_linter into a reusable function
    def _post_generation_cleanup(html_code: str, ep: list) -> tuple[str, list]:
        """Coherence check + A1 JS linter — applied after any generation (init + E1)."""
        _ep = list(ep or [])
        if not use_modular:
            from agents.phase3._layer_gen import coherence_check as _coh_check
            _coh_issues = _coh_check(html_code)
            if _coh_issues:
                coordinateur_log.warning(f"Coherence check: {len(_coh_issues)} problem(s) detected")
                for _ci in _coh_issues[:5]:
                    coordinateur_log.warning(f"  → {_ci}")
                _coh_patched = agent_pre_patcher.run(html_code, _coh_issues)
                _, _coh_broken = _js_check_quick(_coh_patched)
                if _coh_broken:
                    coordinateur_log.warning("Coherence pre-patch invalid — ignored (broken syntax)")
                else:
                    html_code = _coh_patched
                _ep = (_ep + _coh_issues[:3])[-MAX_ERREURS_PASSEES:]
            else:
                coordinateur_log.success("Coherence check OK — game is structurally sound")

        _lint_issues = agent_js_linter.run(html_code)
        if _lint_issues:
            coordinateur_log.warning(f"A1 JS Linter: {len(_lint_issues)} problem(s) — automatic pre-patch")
            _lint_patched = agent_pre_patcher.run(html_code, _lint_issues)
            _, _lint_broken = _js_check_quick(_lint_patched)
            if _lint_broken:
                coordinateur_log.warning("A1: lint pre-patch invalid — ignored (broken syntax)")
            else:
                html_code = _lint_patched
                coordinateur_log.success(f"A1: {len(_lint_issues)} lint issue(s) pre-fixed before Phase 4")
        else:
            coordinateur_log.info("A1 JS Linter: no runtime bugs detected")
        return html_code, _ep

    code, past_errors = _post_generation_cleanup(code, past_errors)

    # E1 — Live preview: store generated code for /api/preview
    try:
        from logger import store_code_preview
        store_code_preview(code)
    except Exception as e:
        coordinateur_log.warning(f"Code preview not stored: {e}")

    # G2: technologie_rendu consistency — if code contains THREE but genre_profile says canvas2d
    _code_has_three = 'THREE.' in code or 'new THREE.' in code
    if _code_has_three and genre_profile.technologie_rendu != "threejs":
        coordinateur_log.warning("G2: Three.js code detected but genre_profile.technologie_rendu=canvas2d — auto-correction")
        genre_profile.technologie_rendu = "threejs"
    elif not _code_has_three and genre_profile.technologie_rendu == "threejs":
        coordinateur_log.warning("G2: genre_profile says threejs but code has no THREE — correcting to canvas2d")
        genre_profile.technologie_rendu = "canvas2d"

    # ─────────────────────────────────────────────
    # REACT LOOP (Phases 4 + 5)
    # ─────────────────────────────────────────────
    coordinateur_log.section("PHASES 4-5 — Evaluation & Iteration")

    previous_score = 0.0
    bundle = None
    stagnation_count = 0

    def _safe_result(r, name: str) -> EvaluationResult:
        """Extracts an EvaluationResult from a raw value (dict or object)."""
        if isinstance(r, EvaluationResult):
            return r
        if isinstance(r, dict):
            # Some agents return {"gameplay": EvaluationResult, ...}
            for key in r:
                if isinstance(r[key], EvaluationResult):
                    return r[key]
        # B1: score 1.5 (not 5.0) — agent crashed → low visible score, not artificially inflated
        coordinateur_log.error(f"Agent '{name}' crashed or returned None — fallback score 1.5")
        return EvaluationResult(agent_name=name, score=1.5,
                                commentaire_global=f"Agent {name} non disponible (crash ou timeout)")

    _iters = _max_iterations if _max_iterations is not None else MAX_ITERATIONS
    for iteration in range(1, _iters + 1):
        _check_stop()
        coordinateur_log.section(f"Iteration {iteration}/{_iters}")

        # ── PHASE 4: EVALUATION (5 agents in parallel) ──
        coordinateur_log.section("PHASE 4 — Multi-dimensional evaluation")

        # I10: max_workers=5 — all QC in parallel (~30s instead of 90s)
        p4 = _parallel([
            ("qc_technique", agent_qc_technique.run, [code, genre_profile]),
            ("qc_gameplay",  agent_qc_gameplay.run,  [code, genre_profile, context.gdd]),
            ("qc_visuel",    agent_qc_visuel.run,     [code, genre_profile]),
            ("executeur",    agent_executeur.run,     [code, genre_profile]),
            ("playtester",   agent_playtester.run,    [code, genre_profile, context.gdd]),
        ], max_workers=5)

        # qc_gameplay returns {"gameplay": ..., "anti_pattern": ...}
        _gp_raw = p4.get("qc_gameplay", {})
        _gp_result = _gp_raw if isinstance(_gp_raw, dict) else {}

        bundle = EvaluationBundle(
            qc_technique = _safe_result(p4["qc_technique"], "QC Technique"),
            qc_gameplay  = _safe_result(_gp_result.get("gameplay", _gp_raw), "QC Gameplay"),
            qc_visuel    = _safe_result(p4["qc_visuel"],    "QC Visuel"),
            execution    = _safe_result(p4["executeur"],    "Executeur"),
            playtester   = _safe_result(p4["playtester"],  "Playtester"),
            anti_pattern = _safe_result(_gp_result.get("anti_pattern", {}), "Anti-Pattern"),
        )

        score = bundle.score_global()
        exec_score = bundle.execution.score

        # C1: minimum thresholds per dimension — block if not reached
        # (note: exec < 4.5 is always covered here since 4.5 < SCORE_MIN_EXECUTION=5.0)
        _tech_score = bundle.qc_technique.score
        if exec_score < SCORE_MIN_EXECUTION or _tech_score < SCORE_MIN_TECHNIQUE:
            _blocking_reasons = []
            if exec_score < SCORE_MIN_EXECUTION:
                _blocking_reasons.append(f"execution={exec_score:.1f} < {SCORE_MIN_EXECUTION}")
            if _tech_score < SCORE_MIN_TECHNIQUE:
                _blocking_reasons.append(f"technique={_tech_score:.1f} < {SCORE_MIN_TECHNIQUE}")
            coordinateur_log.warning(f"C1 thresholds not met: {', '.join(_blocking_reasons)} — score capped at 4.5")
            score = min(score, 4.5)

        # E1: full regeneration if execution < 4.0 on the first iteration
        # (the patcher cannot repair an architecturally broken game)
        if iteration == 1 and exec_score < 4.0:
            coordinateur_log.warning(f"E1: execution={exec_score:.1f} < 4.0 — full regeneration before patch")
            _err_from_exec = [c.get("commentaire", "") for c in bundle.execution.criteres if c.get("score", 1) == 0]
            past_errors = list(past_errors or []) + _err_from_exec[:3]
            # Limit past_errors (I7)
            past_errors = past_errors[-MAX_ERREURS_PASSEES:]
            if not use_modular:
                from agents.phase3._layer_gen import run_layered as _rl_e1
                _regen_code = _rl_e1(context, patterns_reussis=successful_patterns,
                                     erreurs_passees=past_errors, game_logics=game_logics,
                                     level_design=level_design)
                if _regen_code and len(_regen_code) >= CODE_MIN_VIABLE:
                    code = _regen_code
                    coordinateur_log.success(f"E1 regeneration complete: {len(code)} chars")
                    # K4 — apply coherence+linter on E1 code (bypasses main loop)
                    code, past_errors = _post_generation_cleanup(code, past_errors)
                    continue  # restart Phase 4 with the new code

        # Log scores
        coordinateur_log.score("Score global", score)
        coordinateur_log.score("Technique",    bundle.qc_technique.score)
        coordinateur_log.score("Gameplay",     bundle.qc_gameplay.score)
        coordinateur_log.score("Visuel",       bundle.qc_visuel.score)
        coordinateur_log.score("Execution",    exec_score)
        coordinateur_log.score("Playtester",   bundle.playtester.score)
        coordinateur_log.score("Anti-pattern", bundle.anti_pattern.score)

        push_event("score", {"label": "Score global", "value": round(score, 2)})
        push_event("score", {"label": "Execution",    "value": round(exec_score, 2)})

        # A2 — Reactive auto-fix: extract "X is not defined" from Playwright errors
        # and inject var X = <default>; to unblock the next iteration.
        # _a2_fixed_vars persists until all_issues_str is built
        # so the Diagnostician does not receive already-fixed issues.
        _a2_fixed_vars = set()
        if exec_score < SCORE_MIN_EXECUTION and iteration < _iters:
            _exec_criteres = bundle.execution.criteres if bundle.execution else []
            _undef_vars = set()
            _undef_re = re.compile(r'\b(\w+) is not defined', re.IGNORECASE)
            for _c in _exec_criteres:
                for _m in _undef_re.finditer(_c.get('commentaire', '')):
                    _undef_vars.add(_m.group(1))
            if _undef_vars:
                from js_syntax_checker import fix_undefined_runtime_vars as _fix_undef
                code, _a2_fixed, _a2_descs = _fix_undef(code, _undef_vars)
                if _a2_fixed:
                    _a2_fixed_vars = _undef_vars
                    coordinateur_log.success(
                        f"A2 auto-fix {len(_undef_vars)} undef var(s) post-Playwright: "
                        f"{', '.join(sorted(_undef_vars)[:6])}"
                    )
                    stagnation_count = max(0, stagnation_count - 1)

        # P4 — Playability gate: check if player is responsive (Playwright test)
        _joueur_reactif_ok = not any(
            c.get("nom") == "Joueur réactif" and c.get("score", 1) == 0
            for c in (bundle.execution.criteres if bundle.execution else [])
        )

        # Early exit if score is excellent AND player is responsive
        if score >= SCORE_SORTIE_ANTICIPEE:
            if _joueur_reactif_ok:
                coordinateur_log.success(f"Score {score:.2f} >= {SCORE_SORTIE_ANTICIPEE} -> early exit")
                break
            else:
                coordinateur_log.warning(
                    f"Score {score:.2f} >= {SCORE_SORTIE_ANTICIPEE} but 'Joueur réactif' failed — continuing"
                )

        # Stagnation?
        delta = score - previous_score
        if iteration > 1:
            if delta < SCORE_STAGNATION_DELTA:
                stagnation_count += 1
                coordinateur_log.warning(f"Stagnation ({delta:+.2f}) [{stagnation_count}]")
                if stagnation_count >= MAX_ITERATIONS_SANS_PROGRES:
                    coordinateur_log.warning("Persistent stagnation -> stopping iterations")
                    break
            else:
                stagnation_count = 0
        previous_score = score

        # E4: quota savings — passes 3+ only if score is high AND player is responsive
        if iteration >= 2 and score >= SCORE_SEUIL_ITERATIONS_SUP and _joueur_reactif_ok:
            coordinateur_log.info(f"E4: score {score:.2f} >= {SCORE_SEUIL_ITERATIONS_SUP} after {iteration} passes — stopping")
            break

        # Last iteration → no new patch
        if iteration == _iters:
            coordinateur_log.info("Last iteration — no new patch")
            break

        # ── PHASE 5: PATCH ──
        coordinateur_log.section(f"PHASE 5 — Patch iteration {iteration}")

        all_issues = bundle.all_issues()
        # Only pass critical + major issues to the pre-patcher.
        # Minor issues are not worth an LLM call — they are ignored here
        # (they remain visible in the diagnostic for the main patcher).
        _issues_for_prepatch = [
            i for i in all_issues
            if (i.get("severite", "mineur") if isinstance(i, dict) else "mineur") in ("critique", "majeur")
        ]
        _issues_mineurs_count = len(all_issues) - len(_issues_for_prepatch)
        if _issues_mineurs_count:
            coordinateur_log.info(
                f"Pre-patcher: {_issues_mineurs_count} minor issue(s) ignored "
                f"(keeping {len(_issues_for_prepatch)} critical+major)"
            )
        # B4: all_issues_str deduplication — same issue must not be handled twice
        all_issues_str = list(dict.fromkeys(
            i.get("description", str(i)) if isinstance(i, dict) else str(i)
            for i in _issues_for_prepatch
        ))

        # A2-filter: exclude from Diagnostician issues already fixed by A2 (injected variables)
        # Prevents the Patcher from rewriting drawBackground to "fix" gridSize already declared by A2
        if _a2_fixed_vars:
            _before_filter = len(all_issues_str)
            all_issues_str = [
                issue for issue in all_issues_str
                if not any(
                    re.search(r'\b' + re.escape(v) + r'\b', issue, re.IGNORECASE)
                    for v in _a2_fixed_vars
                )
            ]
            _filtered_count = _before_filter - len(all_issues_str)
            if _filtered_count:
                coordinateur_log.info(
                    f"[A2-filter] {_filtered_count} issue(s) excluded from Diagnostician "
                    f"(already fixed: {', '.join(sorted(_a2_fixed_vars)[:4])})"
                )

        # B5: deterministic rules first — resolve 30-40% of issues without LLM
        try:
            from agents.phase5._auto_fix_rules import apply_all_rules as _auto_rules
            from agents.phase3._layer_gen import _extract_js_from_html as _b5_extract
            _js_before_rules = _b5_extract(code) if '<script' in code else code
            _js_after_rules, _rules_applied = _auto_rules(_js_before_rules)
            if _rules_applied:
                import re as _re_b5
                code = _re_b5.sub(
                    r'(<script[^>]*>)(.*?)(</script>)',
                    lambda m: m.group(1) + _js_after_rules + m.group(3),
                    code, flags=_re_b5.DOTALL
                )
                coordinateur_log.info(f"B5 pre-LLM auto-fix: {len(_rules_applied)} rule(s) — {', '.join(_rules_applied[:3])}")
        except Exception as _e_b5:
            coordinateur_log.warning(f"B5 auto-fix non-critical: {_e_b5}")

        # LLM pre-patcher: corrections on remaining issues
        # Save BEFORE pre_patcher — rollback here if patcher fails (not post-pre_patch)
        code_before_prepatch = code
        code_prepatch = agent_pre_patcher.run(code, all_issues_str)
        # Validate that the pre_patcher has not introduced broken syntax
        _prepatch_issues, _prepatch_broken = _js_check_quick(code_prepatch)
        if _prepatch_broken:
            coordinateur_log.warning("Pre-patcher output invalid — pre_patch ignored (broken syntax)")
            code_prepatch = code_before_prepatch
        code = code_prepatch

        # Diagnostician → correction plan
        diagnostic = agent_diagnosticien.run(
            code, genre_profile, bundle, iteration,
            corrections_deja_tentees=past_errors,
        )

        # If diagnostician found nothing useful (fallback or API failure), skip patching
        _diag_corrections = diagnostic.get("corrections_prioritaires", []) if diagnostic else []
        _diag_indispo = "indisponible" in diagnostic.get("probleme_principal", "").lower() if diagnostic else True
        if not _diag_corrections or _diag_indispo:
            coordinateur_log.warning("Diagnostician has no useful corrections — patch skipped to preserve code")
            patched_code = None
        else:
            # Patcher: targeted LLM corrections
            patched_code = agent_patcher.run(code, diagnostic, genre_profile, iteration)

        if patched_code and len(patched_code) >= CODE_MIN_VIABLE:
            # Quick check: the patch must not introduce a syntax error
            _patch_issues, _patch_broken = _js_check_quick(patched_code)
            if _patch_broken:
                coordinateur_log.warning("Patch rejected — invalid syntax (rollback to PRE-pre_patcher code)")
                code = code_before_prepatch  # full rollback, not post-pre_patch
            else:
                code = patched_code
                coordinateur_log.success(f"Patched code: {len(code)} characters")
                # H3 — Mark patched issues as fixed in the Q13 tracker
                for _pi in _issues_for_prepatch:
                    _mark_error_fixed(_pi.get("description", "") if isinstance(_pi, dict) else str(_pi))
                # P4 — Re-run pre-patcher after agent_patcher
                # agent_patcher (LLM over the full code) can introduce new syntax errors
                _p4_issues, _p4_broken = _js_check_quick(code)
                if not _p4_broken and _p4_issues:
                    coordinateur_log.info(f"P4: {len(_p4_issues)} post-patch issue(s) — re-run pre-patcher")
                    _p4_patched = agent_pre_patcher.run(code, _p4_issues)
                    _p4_recheck, _p4_rebroken = _js_check_quick(_p4_patched)
                    if not _p4_rebroken:
                        code = _p4_patched
                        coordinateur_log.info("P4: post-patch pre-patcher OK")
                # P4b — ESLint no-undef post-patcher: catches undeclared variables
                # introduced by the LLM Patcher, before Phase 4 sees them
                from js_syntax_checker import fix_all_auto as _fix_all_post_patch
                code, _p4b_fixed, _p4b_descs = _fix_all_post_patch(code)
                if _p4b_fixed:
                    coordinateur_log.success(f"P4b post-patch auto-fix: {len(_p4b_descs)} correction(s)")
        else:
            # C — Targeted patch by error type before full regeneration
            issue_descs = [
                i.get("description", str(i)) if isinstance(i, dict) else str(i)
                for i in all_issues[:8]
            ]
            _logic_keywords = ("undefined", "NaN", "not a function", "collision", "spawn", "update")
            _render_keywords = ("draw", "canvas", "render", "visual", "color", "display")
            has_logic_errors = any(
                any(kw in d.lower() for kw in _logic_keywords) for d in issue_descs
            )
            has_render_errors = any(
                any(kw in d.lower() for kw in _render_keywords) for d in issue_descs
            )

            # Q13 — Record errors with fixed/recurring tracking
            for _ed in issue_descs[:5]:
                _record_error(_ed, iteration)
            # Build enriched past_errors with [RECURRING] / [FIXED] prefixes
            _enriched = []
            for _info in list(_erreurs_tracker.values())[-15:]:
                _prefix = "[CORRIGÉ] " if _info['fixed'] else (f"[RÉCURRENT x{_info['count']}] " if _info['count'] > 1 else "")
                _enriched.append(_prefix + _info['msg'])
            past_errors = _enriched
            # I7: limit past_errors to 20 max to avoid prompt pollution
            past_errors = past_errors[-MAX_ERREURS_PASSEES:]

            if not use_modular:
                from agents.phase3._layer_gen import run_layered as _rl
                if has_logic_errors and not has_render_errors:
                    # Logic errors → targeted L2 hint in the errors
                    coordinateur_log.warning("Patch insufficient — targeted regeneration (L2 logic errors)")
                    past_errors.append("[L2-CIBLE] Regenère la logique avec ces corrections : " + "; ".join(issue_descs[:3]))
                    import memory as _mem
                    _mem.save_layer_errors(game_genre, 2, issue_descs[:3])
                else:
                    coordinateur_log.warning("Patch insufficient — full layered regeneration")
                new_code = _rl(
                    context,
                    patterns_reussis=successful_patterns,
                    erreurs_passees=past_errors,
                    game_logics=game_logics,
                    level_design=level_design,
                )
                if new_code and len(new_code) >= CODE_MIN_VIABLE:
                    code = new_code
                    coordinateur_log.success(f"Layered regeneration: {len(code)} characters")
                    code, past_errors = _post_generation_cleanup(code, past_errors)

    # ─────────────────────────────────────────────
    # PHASE 5 : FINALISATION
    # ─────────────────────────────────────────────
    coordinateur_log.section("PHASE 5 — Finalisation")

    duration = time.time() - start_time
    final_exec_score = bundle.execution.score if bundle else 0.0
    final_issues = bundle.all_issues() if bundle else []

    # Verdict final — must run before final_score so that bundle.benchmark is populated
    full_verdict = agent_verdict_final.run(genre_profile, context.gdd, bundle) if bundle else {}
    # full_verdict = {"evaluation": EvaluationResult, "verdict": dict}
    if bundle and full_verdict:
        bundle.benchmark = full_verdict.get("evaluation", bundle.benchmark)
    verdict = full_verdict.get("verdict", {}) if full_verdict else {}

    # H1 — final_score computed AFTER benchmark injection (otherwise benchmark=0 → underestimated score)
    final_score = bundle.score_global() if bundle else 0.0
    approved = final_score >= SCORE_SEUIL_SAUVEGARDE

    # C2 : Veto si le verdict final déclare le jeu "non jouable" ou "ne se lance pas"
    _veto_kws = ["non jouable", "injouable", "ne se lance pas", "écran noir", "crash au démarrage",
                 "unplayable", "black screen", "doesn't launch", "does not launch", "broken game", "crashes on"]
    _vd_text = ((verdict.get("justification", "") or "") + " " + (verdict.get("recommandation", "") or "")).lower()
    if approved and any(kw in _vd_text for kw in _veto_kws):
        approved = False
        coordinateur_log.warning("C2 : veto agent neutre — jeu déclaré non jouable malgré score suffisant")

    # C3 : Hard playability gate — execution < 5.0 AND player not responsive → block save
    _final_joueur_reactif_failed = any(
        c.get("nom") == "Joueur réactif" and c.get("score", 1) == 0
        for c in (bundle.execution.criteres if bundle and bundle.execution else [])
    )
    if approved and final_exec_score < 5.0 and _final_joueur_reactif_failed:
        approved = False
        coordinateur_log.warning(
            f"C3 : hard playability gate — execution={final_exec_score:.1f} < 5.0 AND "
            f"'Joueur réactif' failed → game blocked regardless of score"
        )

    coordinateur_log.info(f"Final score: {final_score:.2f} | Approved: {approved}")

    # 5 — Extract and memorize snippets from highly successful games
    if final_score >= 8.0 and not use_modular:
        try:
            import re as _re
            js_match = _re.search(r'<script[^>]*>(.*?)</script>', code, _re.DOTALL)
            if js_match:
                js_body = js_match.group(1)
                # Extraire les fonctions de logique (update*, check*, spawn*) comme snippets
                fn_matches = _re.finditer(
                    r'(function\s+(?:update|check|spawn|init)\w*\s*\([^)]*\)\s*\{)',
                    js_body
                )
                snippets = []
                for fm in fn_matches:
                    start = fm.start()
                    depth, end = 0, start
                    for ci in range(start, min(start + 2000, len(js_body))):
                        if js_body[ci] == '{':
                            depth += 1
                        elif js_body[ci] == '}':
                            depth -= 1
                            if depth == 0:
                                end = ci + 1
                                break
                    snippets.append(js_body[start:end])
                if snippets:
                    combined = '\n\n'.join(snippets[:3])[:3000]
                    memory.save_pattern(genre_profile, final_score, combined, notes="auto-extrait score>=8")
                    coordinateur_log.success(f"Snippet réussi mémorisé ({len(snippets)} fonctions extraites)")
        except Exception as e:
            coordinateur_log.warning(f"Extraction snippet non critique : {e}")

    # Export failure log if exec < 4.5 (execution problem)
    if final_exec_score < 4.5:
        _export_failure_log(
            genre=game_genre,
            titre=game_title,
            score=final_score,
            exec_score=final_exec_score,
            issues=final_issues,
            label="exec_failure",
        )

    # Save
    log_content = "\n".join(get_session_log())
    html_path = ""
    if final_score >= SCORE_MIN_VIABLE_SAVE:
        html_path = agent_sauvegarde.run(
            code=code,
            genre_profile=genre_profile,
            gdd=context.gdd,
            bundle=bundle,
            verdict=verdict,
            duree_secondes=duration,
            log_content=log_content,
            approuve=approved,
        )
        if html_path:
            coordinateur_log.success(f"Game saved: {html_path}")
            html_basename = os.path.basename(html_path)
        else:
            html_basename = ""
    else:
        coordinateur_log.warning(f"Score {final_score:.2f} < {SCORE_MIN_VIABLE_SAVE} — game not saved")
        html_basename = ""

    # Auto-learner (async)
    try:
        agent_auto_learner.run(
            html=code,
            score=final_score,
            approuve=approved,
            genre=game_genre,
            titre=game_title,
            logs=log_content,
        )
    except Exception as e:
        coordinateur_log.warning(f"Auto-learner non-critical: {e}")

    push_event("complete", {
        "score": round(final_score, 2),
        "approuve": approved,
        "html_basename": html_basename,
        "titre": game_title,
    })

    coordinateur_log.section(f"Done in {duration:.1f}s — Score: {final_score:.2f}/10")

    return {
        "genre_profile": genre_profile,
        "gdd": context.gdd,
        "code": code,
        "bundle": bundle,
        "verdict": verdict,
        "score": final_score,
        "approved": approved,
        "html_path": html_path,
        "html_basename": html_basename,
        "duration": duration,
    }


def run_quick(user_prompt: str, style_graphique: str = "", stop_event=None) -> dict:
    """
    Lightweight pipeline: Phase 1 + 2 + 3 complete + Phase 4 single pass,
    no diagnostician/patcher loop. Returns the same format as run().
    Key 'duree_secondes' included for compatibility with /api/quick-generate.
    """
    result = run(user_prompt, style_graphique=style_graphique,
                 stop_event=stop_event, _max_iterations=1)
    if "duration" in result and "duree_secondes" not in result:
        result["duree_secondes"] = result["duration"]
    return result


# ─────────────────────────────────────────────
# POINT D'ENTRÉE CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = input("Prompt: ").strip()
        if not prompt:
            print("Empty prompt — aborting.")
            sys.exit(1)

    result = run(prompt)
    if result.get("erreur"):
        print(f"\nError: {result['erreur']}")
        sys.exit(1)

    print(f"\nFinal score: {result['score']:.2f}/10")
    print(f"Approved    : {result['approved']}")
    if result.get("html_path"):
        print(f"File        : {result['html_path']}")

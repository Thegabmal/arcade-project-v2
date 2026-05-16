"""
Arcade AI — Flask Web Interface
Game generation with real-time SSE streaming.
"""

import os
import sys
import json
import uuid
import queue
import glob
import time
import datetime
import threading
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

SAVE_DIR = "jeux_sauvegardes"
GENERATION_TIMEOUT = 900   # 15 minutes in seconds
MAX_PROMPT_LENGTH = 500
SESSION_TTL = 1800         # 30 minutes — purge completed sessions after this delay
MAX_CONCURRENT_GENERATIONS = 3  # F3: limit concurrent generations (API cost)

# ─────────────────────────────────────────────
# SESSION MANAGEMENT
# ─────────────────────────────────────────────
_sessions: dict = {}
_sessions_lock = threading.Lock()
_generation_semaphore = threading.Semaphore(MAX_CONCURRENT_GENERATIONS)


def _new_session(session_id: str) -> dict:
    return {
        "queue": queue.Queue(),
        "status": "running",
        "result": None,
        "created_at": time.time(),
    }


def _session_cleanup_loop():
    """Daemon thread: purge completed sessions older than SESSION_TTL."""
    while True:
        time.sleep(300)  # Check every 5 minutes
        now = time.time()
        to_delete = []
        with _sessions_lock:
            for sid, sess in _sessions.items():
                age = now - sess.get("created_at", now)
                if sess["status"] in ("done", "error") and age > SESSION_TTL:
                    to_delete.append(sid)
            for sid in to_delete:
                del _sessions[sid]
        if to_delete:
            print(f"  [Sessions] {len(to_delete)} expired session(s) purged")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _build_recommendations(scores: dict, issues: list) -> list:
    """Generate concrete prompt recommendations from scores and issues."""
    recs = []

    tech = scores.get("technique", 10)
    gameplay = scores.get("gameplay", 10)
    visuel = scores.get("visuel", 10)
    execution = scores.get("execution", 10)

    # Low technical score → mechanics too vague
    if tech < 6:
        recs.append({
            "label": "Specify the mechanics",
            "texte": "Describe each mechanic explicitly: 'the player can jump, shoot, collect coins, and die on enemy contact'",
            "icone": "⚙️",
        })

    # Low gameplay score → unclear core loop
    if gameplay < 6:
        recs.append({
            "label": "Describe the core loop",
            "texte": "Describe the objective and game loop: 'dodge obstacles, collect bonuses, survive as long as possible'",
            "icone": "🎯",
        })

    # Low visual score → style not specified
    if visuel < 6:
        recs.append({
            "label": "Specify the visual style",
            "texte": "Add an explicit visual style: 'retro 8-bit pixel art with vivid neon colors'",
            "icone": "🎨",
        })

    # Low execution score → technical complexity issue
    if execution < 5:
        recs.append({
            "label": "Simplify the request",
            "texte": "This game type is very complex. Try a simpler version: '2D game' instead of '3D FPS'",
            "icone": "🔧",
        })

    # Critical issues → generation blocked
    has_critical = any(i.get("severite") == "critique" for i in issues)
    if has_critical:
        recs.append({
            "label": "Try a different genre",
            "texte": "Critical errors blocked generation. Try a simpler genre: platformer, puzzle, or 2D shooter",
            "icone": "🔄",
        })

    # Very low global score → full reorientation needed
    global_score = sum(scores.values()) / len(scores) if scores else 0
    if global_score < 4 and not recs:
        recs.append({
            "label": "Rephrase more simply",
            "texte": "Describe your game in one clear sentence with genre + action + context: 'a platformer where a robot avoids traps in a factory'",
            "icone": "✏️",
        })

    # Always add a general tip if few recommendations
    if len(recs) < 2:
        recs.append({
            "label": "Add more details",
            "texte": "The more precise your prompt, the better the game. Add: enemies, power-ups, atmosphere, difficulty, visual theme",
            "icone": "💡",
        })

    return recs[:4]  # max 4 recommendations


# ─────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/play/<path:filename>")
def play_game(filename):
    return render_template("game.html", filename=filename)


@app.route("/game-file/<path:filename>")
def serve_game_file(filename):
    return send_from_directory(os.path.abspath(SAVE_DIR), filename)


@app.route("/debug/<path:filename>")
def debug_game(filename):
    """Debug page — detailed scores, per-agent issues, game analysis."""
    base = filename.replace(".html", "")
    json_path = os.path.join(SAVE_DIR, f"{base}.json")
    log_path = os.path.join(SAVE_DIR, f"{base}_log.txt")

    if not os.path.exists(json_path):
        return f"<h1>Metadata not found for {filename}</h1>", 404

    with open(json_path, encoding="utf-8") as f:
        meta = json.load(f)

    log_content = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            log_content = f.read()

    # Detailed per-agent scores with weights
    AGENT_WEIGHTS = {
        "technique": ("QC Technique", 20),
        "gameplay": ("QC Gameplay", 25),
        "visuel": ("QC Visuel", 15),
        "execution": ("Exécuteur", 20),
        "playtester": ("Playtester", 15),
        "anti_pattern": ("Anti-Pattern", 3),
        "benchmark": ("Benchmark", 2),
    }
    scores = meta.get("scores", {})
    score_details = []
    for key, (label, weight) in AGENT_WEIGHTS.items():
        val = scores.get(key)
        score_details.append({
            "key": key,
            "label": label,
            "weight": weight,
            "score": round(val, 2) if val is not None else None,
            "color": "#2ecc71" if (val or 0) >= 7 else ("#f39c12" if (val or 0) >= 5 else "#e74c3c"),
        })

    return render_template(
        "debug.html",
        filename=filename,
        meta=meta,
        score_details=score_details,
        log_content=log_content,
    )


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True, silent=True) or {}

    # Validate prompt
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "Prompt is empty."}), 400
    if len(prompt) > MAX_PROMPT_LENGTH:
        prompt = prompt[:MAX_PROMPT_LENGTH]

    # Minimal sanitization: strip tags and injection vectors
    # F2: include quotes to prevent injections in LLM prompts
    prompt = prompt.replace("<", "").replace(">", "").replace("`", "").replace('"', "'").replace("\\", "")

    # Optional game type
    game_type = str(data.get("game_type", "")).strip()
    if game_type and game_type != "tout type":
        full_prompt = f"Jeu de type {game_type} : {prompt}"
    else:
        full_prompt = prompt

    # Optional graphic style (e.g. "pixel_art_gameboy", "3d_lowpoly", ...)
    graphic_style = str(data.get("graphic_style", "")).strip()

    session_id = str(uuid.uuid4())
    session = _new_session(session_id)
    stop_event = threading.Event()

    with _sessions_lock:
        _sessions[session_id] = session

    def run_pipeline():
        from logger import set_thread_event_queue, clear_thread_event_queue, clear_code_preview, set_preview_session_id
        set_thread_event_queue(session["queue"])
        set_preview_session_id(session_id)
        # F3: semaphore — block if MAX_CONCURRENT_GENERATIONS reached
        if not _generation_semaphore.acquire(blocking=True, timeout=5):
            session["queue"].put({"type": "error", "data": {
                "message": f"Server busy ({MAX_CONCURRENT_GENERATIONS} generations running). Please retry in a few minutes."
            }})
            session["queue"].put(None)
            return
        try:
            import coordinateur
            result = coordinateur.run(full_prompt, style_graphique=graphic_style, stop_event=stop_event)

            gdd = result.get("gdd") or {}
            html_path = result.get("html_path")
            html_basename = None
            if html_path:
                html_basename = os.path.basename(html_path)

            bundle = result.get("bundle")
            issues_top = []
            scores_detail = {}
            if bundle:
                issues_top = bundle.all_issues()[:5]
                scores_detail = {
                    "technique": round(bundle.qc_technique.score, 1),
                    "gameplay": round(bundle.qc_gameplay.score, 1),
                    "visuel": round(bundle.qc_visuel.score, 1),
                    "execution": round(bundle.execution.score, 1),
                    "playtester": round(bundle.playtester.score, 1),
                    "anti_pattern": round(bundle.anti_pattern.score, 1),
                    "benchmark": round(bundle.benchmark.score, 1),
                }

            result_data = {
                "score": round(result.get("score", 0), 2),
                "html_path": html_path,
                "html_basename": html_basename,
                "titre": gdd.get("titre", "Jeu généré") if isinstance(gdd, dict) else "Jeu généré",
                "approuve": result.get("approved", result.get("approuve", False)),
                "erreur": result.get("erreur"),
                "duree": int(result.get("duree_secondes", 0)),
                "scores_detail": scores_detail,
                "issues": issues_top,
                "recommandations": _build_recommendations(scores_detail, issues_top),
            }

            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["status"] = "done"
                    _sessions[session_id]["result"] = result_data

            session["queue"].put({"type": "complete", "data": result_data})

        except Exception as exc:
            err_msg = str(exc)
            # E4: clear message when Gemini quotas are exhausted
            _exc_lower = err_msg.lower()
            if "allfreekeysexhausted" in type(exc).__name__.lower() or \
               "allfreekeysexhausted" in _exc_lower or \
               ("quota" in _exc_lower and ("épuisé" in _exc_lower or "exhausted" in _exc_lower)):
                err_msg = ("API quotas exhausted — all free keys have hit their daily limit. "
                           "Retry tomorrow or configure a paid key (GEMINI_RPD_LIMIT=9999).")
            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["status"] = "error"
            session["queue"].put({"type": "error", "data": {"message": err_msg}})
        finally:
            _generation_semaphore.release()
            clear_thread_event_queue()
            clear_code_preview()
            session["queue"].put(None)  # sentinelle de fin

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    with _sessions_lock:
        _sessions[session_id]["thread"] = thread
        _sessions[session_id]["stop_event"] = stop_event

    return jsonify({"session_id": session_id})


@app.route("/api/stream/<session_id>")
def api_stream(session_id):
    with _sessions_lock:
        session = _sessions.get(session_id)

    if not session:
        return jsonify({"error": "Unknown session"}), 404

    def generate():
        yield "data: {\"type\": \"connected\"}\n\n"
        event_queue = session["queue"]

        while True:
            try:
                event = event_queue.get(timeout=GENERATION_TIMEOUT)
                if event is None:
                    yield "data: {\"type\": \"end\"}\n\n"
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except queue.Empty:
                # Signal the generation thread to stop
                with _sessions_lock:
                    sess = _sessions.get(session_id, {})
                    se = sess.get("stop_event")
                    if se:
                        se.set()
                    if session_id in _sessions:
                        _sessions[session_id]["status"] = "error"
                print(f"  [Timeout] Session {session_id[:8]} — stop_event triggered", flush=True)
                yield "data: {\"type\": \"timeout\", \"data\": {\"message\": \"Timeout 15 minutes\"}}\n\n"
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/history")
def api_history():
    games = []
    if os.path.exists(SAVE_DIR):
        json_files = sorted(
            glob.glob(os.path.join(SAVE_DIR, "*.json")),
            key=os.path.getmtime,
            reverse=True,
        )
        for jf in json_files:
            try:
                with open(jf, encoding="utf-8") as f:
                    meta = json.load(f)
                meta["json_file"] = os.path.basename(jf)
                base = os.path.basename(jf).replace(".json", ".html")
                meta["html_basename"] = base
                games.append(meta)
            except Exception:
                pass
    return jsonify(games)


@app.route("/api/game-log/<path:filename>")
def api_game_log(filename):
    """Return the pipeline text log for a saved game."""
    # filename can be "title_20240101_120000.html" → look for "_log.txt"
    base = filename.replace(".html", "")
    log_path = os.path.join(SAVE_DIR, f"{base}_log.txt")
    if not os.path.exists(log_path):
        return jsonify({"error": "Log not available for this game."}), 404
    try:
        with open(log_path, encoding="utf-8") as f:
            content = f.read()
        return Response(content, mimetype="text/plain; charset=utf-8")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reevaluate", methods=["POST"])
def api_reevaluate():
    """Re-evaluate a saved game with Phase 4 agents and update its metadata."""
    data = request.get_json(force=True, silent=True) or {}
    filename = str(data.get("filename", "")).strip()

    # Security: no directory traversal
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.endswith(".html"):
        return jsonify({"error": "File must be a .html"}), 400

    html_path = os.path.join(SAVE_DIR, filename)
    json_path = html_path.replace(".html", ".json")

    if not os.path.exists(html_path):
        return jsonify({"error": "HTML file not found"}), 404

    session_id = str(uuid.uuid4())
    session = _new_session(session_id)
    with _sessions_lock:
        _sessions[session_id] = session

    def run_reevaluation():
        from logger import set_thread_event_queue, clear_thread_event_queue, push_event
        set_thread_event_queue(session["queue"])
        try:
            # Load the HTML
            with open(html_path, encoding="utf-8") as f:
                code = f.read()

            # Load existing metadata
            meta = {}
            if os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as f:
                    meta = json.load(f)

            # Rebuild a GenreProfile from metadata
            from genre_profile import GenreProfile, EvaluationBundle, EvaluationResult
            is_3d = "THREE." in code and "WebGLRenderer" in code
            genre_profile = GenreProfile(
                genre_principal=meta.get("genre", "arcade"),
                sous_genre=meta.get("sous_genre", ""),
                ton=meta.get("ton", "casual"),
                type_gameplay=meta.get("type_gameplay", "arcade"),
                technologie_rendu="threejs" if is_3d else "canvas2d",
            )
            gdd = {
                "titre": meta.get("titre", "Jeu"),
                "concept": meta.get("concept", ""),
            }

            push_event("phase_start", {"phase": "REEVALUATION", "title": "Re-evaluation — Phase 4"})

            # Run the 5 evaluation agents in parallel
            from coordinateur import _parallel
            from agents.phase4 import (
                agent_qc_technique, agent_qc_gameplay, agent_qc_visuel,
                agent_executeur, agent_playtester,
            )
            from agents.support import agent_verdict_final

            p4 = _parallel([
                ("qc_tech",    agent_qc_technique.run, [code, genre_profile]),
                ("qc_gameplay", agent_qc_gameplay.run, [code, genre_profile, gdd]),
                ("qc_visuel",  agent_qc_visuel.run,   [code, genre_profile]),
                ("execution",  agent_executeur.run,   [code, genre_profile]),
                ("playtester", agent_playtester.run,  [code, genre_profile, gdd]),
            ], max_workers=3)

            qc_gp_bundle = p4["qc_gameplay"] or {}
            if isinstance(qc_gp_bundle, dict) and "gameplay" in qc_gp_bundle:
                qc_gameplay_result  = qc_gp_bundle["gameplay"]   or EvaluationResult(agent_name="QC Gameplay")
                anti_pattern_result = qc_gp_bundle["anti_pattern"] or EvaluationResult(agent_name="Anti-Pattern")
            else:
                qc_gameplay_result  = qc_gp_bundle if isinstance(qc_gp_bundle, EvaluationResult) else EvaluationResult(agent_name="QC Gameplay")
                anti_pattern_result = EvaluationResult(agent_name="Anti-Pattern")

            bundle = EvaluationBundle(
                qc_technique= p4["qc_tech"]   or EvaluationResult(agent_name="QC Technique"),
                qc_gameplay=  qc_gameplay_result,
                qc_visuel=    p4["qc_visuel"] or EvaluationResult(agent_name="QC Visuel"),
                execution=    p4["execution"] or EvaluationResult(agent_name="Exécuteur"),
                playtester=   p4["playtester"] or EvaluationResult(agent_name="Playtester"),
                anti_pattern= anti_pattern_result,
                benchmark=    EvaluationResult(agent_name="Benchmark"),
            )

            verdict_result = agent_verdict_final.run(genre_profile, gdd, bundle)
            bundle.benchmark = verdict_result.get("evaluation", {})

            score_global = bundle.score_global()

            # Update the JSON metadata
            new_scores = {
                "technique":   round(bundle.qc_technique.score, 1),
                "gameplay":    round(bundle.qc_gameplay.score, 1),
                "visuel":      round(bundle.qc_visuel.score, 1),
                "execution":   round(bundle.execution.score, 1),
                "playtester":  round(bundle.playtester.score, 1),
                "anti_pattern": round(bundle.anti_pattern.score, 1),
                "benchmark":   round(bundle.benchmark.score, 1),
                "global":      round(score_global, 2),
            }
            meta["scores"] = new_scores
            meta["date"] = datetime.datetime.now().isoformat()
            meta["verdict"] = verdict_result.get("verdict", meta.get("verdict", {}))
            meta["approuve"] = score_global >= 7.5

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            scores_detail = {k: v for k, v in new_scores.items() if k != "global"}
            issues_top = bundle.all_issues()[:5]

            result_data = {
                "score": round(score_global, 2),
                "html_basename": filename,
                "titre": meta.get("titre", "Jeu"),
                "approuve": meta["approuve"],
                "scores_detail": scores_detail,
                "issues": issues_top,
                "recommandations": _build_recommendations(scores_detail, issues_top),
            }

            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["status"] = "done"
                    _sessions[session_id]["result"] = result_data

            session["queue"].put({"type": "complete", "data": result_data})

        except Exception as exc:
            err_msg = str(exc)
            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["status"] = "error"
            session["queue"].put({"type": "error", "data": {"message": err_msg}})
        finally:
            clear_thread_event_queue()
            session["queue"].put(None)

    thread = threading.Thread(target=run_reevaluation, daemon=True)
    thread.start()

    return jsonify({"session_id": session_id})


def _extract_game_context(html: str) -> str:
    """
    Extract key JS state variables for Gemini context.
    Strategy: find `let` declarations (mutable variables = game state),
    then summarize constant registries (HERO_CLASSES, ENEMY_TYPES...).
    Also extracts: 2D function signatures (name + params), arrays,
    and auto-detects the game type.
    """
    import re

    # Trouver le script principal (le plus long sans attribut src)
    js = ""
    for m in re.finditer(r'<script(?:\s(?!src)[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE):
        if len(m.group(1)) > len(js):
            js = m.group(1)
    if not js:
        return ""

    sections = []

    # ── 1. Mutable `let` variables (game state: score, lives, gameState, inventory...) ──
    let_decls = []
    seen_names = set()
    for m in re.finditer(
        r'^\s*(let\s+(\w+)\s*=\s*(?:\{[^}]{0,300}\}|[^\n;]{0,80}))',
        js, re.MULTILINE
    ):
        name = m.group(2)
        if name not in seen_names:
            seen_names.add(name)
            let_decls.append(m.group(1).strip())
    if let_decls:
        sections.append("// State variables (let — mutable):\n" + '\n'.join(let_decls[:40]))

    # ── 2. Registry summaries (HERO_CLASSES, ENEMY_TYPES, LOOT_TYPES...) ──
    for pattern, label in [
        (r'const\s+(HERO_CLASSES)\s*=\s*\[.*?\]', "HERO_CLASSES"),
        (r'const\s+(ENEMY_TYPES)\s*=\s*\{.*?\}', "ENEMY_TYPES"),
        (r'const\s+(LOOT_TYPES)\s*=\s*\{.*?\}', "LOOT_TYPES"),
        (r'const\s+(HERO_SPRITES)\s*=\s*\{.*?\}', "HERO_SPRITES"),
    ]:
        m = re.search(pattern, js, re.DOTALL)
        if m:
            snippet = m.group(0)[:300]  # First 300 chars are enough to capture key names
            sections.append(f"// {label} (extrait) :\n{snippet}\n...")

    # ── 3. For Three.js games — extract game-specific API ──
    is_threejs = bool(re.search(r'THREE\.|WebGLRenderer', js))
    if is_threejs:
        threejs_info = []

        # Signature de createProjectile
        m = re.search(r'function createProjectile\s*\([^)]+\)\s*\{.{0,600}return\s*\{[^}]+\}', js, re.DOTALL)
        if m:
            threejs_info.append("// createProjectile signature :\n" + m.group(0)[:500])

        # GAME_SETTINGS (premières clés)
        m = re.search(r'const\s+GAME_SETTINGS\s*=\s*\{([^}]{0,800})\}', js, re.DOTALL)
        if m:
            threejs_info.append("// GAME_SETTINGS (extrait) :\nconst GAME_SETTINGS = {" + m.group(1)[:400] + "\n...}")

        # createEnemy signature
        m = re.search(r'function createEnemy\s*\([^)]+\)\s*\{.{0,400}', js, re.DOTALL)
        if m:
            threejs_info.append("// createEnemy signature :\n" + m.group(0)[:400])

        # Types d'ennemis disponibles (availableEnemyTypes ou switch/case)
        m = re.search(r'availableEnemyTypes[^;]{0,500}', js, re.DOTALL)
        if m:
            threejs_info.append("// Types d'ennemis :\n" + m.group(0)[:300])
        else:
            cases = re.findall(r"case\s+'([^']+)'", js)
            if cases:
                threejs_info.append("// Types ennemis (case) : " + str(list(set(cases))[:10]))

        # Variable de temps (runTime, clock, etc.)
        for t_pattern in [r'\brunTime\b', r'\bgameTime\b', r'\belapsedTime\b']:
            if re.search(t_pattern, js):
                threejs_info.append(f"// Variable temps : {t_pattern.strip(r'\\b')}")
                break

        # Tableau de projectiles
        for arr in ['bullets', 'projectiles', 'shots']:
            if re.search(rf'\b{arr}\s*=\s*\[\]', js):
                threejs_info.append(f"// Tableau projectiles : {arr}[]")
                break

        if threejs_info:
            sections.append('\n\n'.join(threejs_info))

    # ── 4. For 2D games — available functions, arrays, game type ──
    if not is_threejs:
        # Named functions (not arrow functions)
        _skip_fns = {
            'gameLoop', 'draw', 'update', 'animate', 'init', 'requestAnimationFrame',
            'cancelAnimationFrame', 'setTimeout', 'setInterval', 'clearInterval',
            'addEventListener', 'removeEventListener',
        }
        fn_sigs = []
        seen_fn_names = set()
        for m in re.finditer(r'\bfunction\s+(\w+)\s*\(([^)]{0,120})\)', js):
            fname = m.group(1)
            fparams = m.group(2).strip()
            if fname not in _skip_fns and fname not in seen_fn_names:
                seen_fn_names.add(fname)
                fn_sigs.append(f"// {fname}({fparams})")
                if len(fn_sigs) >= 20:
                    break

        # Declared arrays
        arr_names = []
        seen_arr_names = set()
        for m in re.finditer(r'\b(?:let|const)\s+(\w+)\s*=\s*(?:\[\]|new\s+Array)', js):
            aname = m.group(1)
            if aname not in seen_arr_names:
                seen_arr_names.add(aname)
                arr_names.append(aname)
                if len(arr_names) >= 15:
                    break

        # Game type detection
        js_lower = js.lower()
        if 'towers' in js_lower:
            game_type_detected = 'tower_defense'
        elif 'platforms' in js_lower:
            game_type_detected = 'platformer'
        elif 'hero' in js_lower and 'dungeon' in js_lower:
            game_type_detected = 'rpg_dungeon'
        elif 'hero' in js_lower:
            game_type_detected = 'rpg'
        elif 'player' in js_lower:
            game_type_detected = 'action'
        elif 'pieces' in js_lower or 'tetris' in js_lower:
            game_type_detected = 'puzzle'
        else:
            game_type_detected = 'unknown'

        if fn_sigs or arr_names:
            fn_block_lines = ["// Available functions in this game:"]
            fn_block_lines.extend(fn_sigs)
            if arr_names:
                fn_block_lines.append("// Arrays: " + ", ".join(f"{a}[]" for a in arr_names))
            fn_block_lines.append(f"// Detected game type: {game_type_detected}")
            sections.append('\n'.join(fn_block_lines))

    return '\n\n'.join(sections)[:8000]


def _detect_game_type(js_snippet: str) -> str:
    """Detect the game type from the extracted context snippet."""
    import re as _re_dgt
    m = _re_dgt.search(r'// Detected game type: (\w+)', js_snippet)
    if m:
        return m.group(1)
    # Fallback : détecter depuis le texte brut du snippet
    s = js_snippet.lower()
    if 'towers' in s:
        return 'tower_defense'
    elif 'platforms' in s:
        return 'platformer'
    elif 'hero' in s and 'dungeon' in s:
        return 'rpg_dungeon'
    elif 'hero' in s:
        return 'rpg'
    elif 'player' in s:
        return 'action'
    elif 'pieces' in s or 'tetris' in s:
        return 'puzzle'
    return 'unknown'


def _extract_full_js_code(html: str, max_chars: int = 50000) -> str:
    """Extract the full JS code (not a summary) from the game HTML file."""
    import re
    js = ""
    for m in re.finditer(r'<script(?:\s(?!src)[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE):
        if len(m.group(1)) > len(js):
            js = m.group(1)
    return js[:max_chars]


def _is_complex_request(prompt: str) -> bool:
    """
    Detect if the request requires the full game code (new system/mechanic/type).
    Simple requests (modify a stat, spawn an enemy) don't need it.
    """
    import re
    p = prompt.lower()
    complex_patterns = [
        # Nouveau type / nouvelle entité
        r'\b(nouveau|nouvelle|new)\s+\b(type|classe|class|système|systeme|mécanique|mecanique|arme|boss|ennemi|enemy|wave|vague|objet|item|power.?up|powerup|capacité|capacite|sort|skill|effet)\b',
        # Boss / wave / vague comme objet direct de création
        r'\b(ajoute[rz]?|créer?)\s+(?:un[e]?\s+)?(?:nouveau|nouvelle)?\s*\b(boss|wave|vague|level|niveau)\b.*?\b(avec|qui|type|de)\b',
        # Ajouter un système complet
        r'\bajoute[rz]?\s+une?\s+\b(système|systeme|mécanique|mecanique|mini.?map|minimap|inventaire|sauvegarde|barre|jauge|compteur|timer|chrono)\b',
        r'\bajoute[rz]?\s+\b(une?\s+)?(mini.?map|minimap|inventaire|sauvegarde|leaderboard)\b',
        # Implémenter
        r'\bimplémente[rz]?\b|\bimplemente[rz]?\b',
        # Système de X
        r'\b(système|systeme|mechanic|mécanique|mécanisme|mecanisme)\s+de\b',
        # Créer un système/mécanique
        r'\bcré[eé][rz]?\s+une?\s+\b(système|systeme|mécanique|mecanique|ennemi|arme|power|objet|classe|type)\b',
        # Comportement IA / nouveau comportement
        r'\b(comportement|behavior|ia\b|intelligence\s+artificielle|pathfinding|ia\s+ennem)\b',
        # Refonte / réécriture
        r'\brefonte\b|\brewrite\b|\brefaire\b',
        # Modes de jeu
        r'\bmode\s+(survie|coop|multijoueur|endurance|boss.?rush|time\s*trial)\b',
    ]
    for pat in complex_patterns:
        if re.search(pat, p, re.IGNORECASE):
            return True
    return False


@app.route("/api/quick-generate", methods=["POST"])
def api_quick_generate():
    """Lightweight pipeline ~2min: Phase 1 + partial Phase 2 + Phase 3 + 3-agent eval."""
    data = request.get_json(force=True, silent=True) or {}
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "Prompt is empty."}), 400
    if len(prompt) > MAX_PROMPT_LENGTH:
        prompt = prompt[:MAX_PROMPT_LENGTH]
    # F2: include quotes to prevent injections in LLM prompts
    prompt = prompt.replace("<", "").replace(">", "").replace("`", "").replace('"', "'").replace("\\", "")

    game_type = str(data.get("game_type", "")).strip()
    if game_type and game_type != "tout type":
        full_prompt = f"Jeu de type {game_type} : {prompt}"
    else:
        full_prompt = prompt

    graphic_style = str(data.get("graphic_style", "")).strip()
    session_id = str(uuid.uuid4())
    session = _new_session(session_id)
    with _sessions_lock:
        _sessions[session_id] = session

    def run_quick_pipeline():
        from logger import set_thread_event_queue, clear_thread_event_queue, clear_code_preview, set_preview_session_id
        set_thread_event_queue(session["queue"])
        set_preview_session_id(session_id)
        try:
            import coordinateur
            result = coordinateur.run_quick(full_prompt, style_graphique=graphic_style)

            gdd = result.get("gdd") or {}
            html_path = result.get("html_path")
            html_basename = os.path.basename(html_path) if html_path else None
            bundle = result.get("bundle")
            scores_detail = {}
            issues_top = []
            if bundle:
                issues_top = bundle.all_issues()[:5]
                scores_detail = {
                    "technique": round(bundle.qc_technique.score, 1),
                    "gameplay": round(bundle.qc_gameplay.score, 1),
                    "visuel": round(bundle.qc_visuel.score, 1),
                    "execution": round(bundle.execution.score, 1),
                    "playtester": round(bundle.playtester.score, 1),
                    "anti_pattern": round(bundle.anti_pattern.score, 1),
                    "benchmark": round(bundle.benchmark.score, 1),
                }

            result_data = {
                "score": round(result.get("score", 0), 2),
                "html_path": html_path, "html_basename": html_basename,
                "titre": gdd.get("titre", "Jeu généré") if isinstance(gdd, dict) else "Jeu généré",
                "approuve": result.get("approved", result.get("approuve", False)),
                "erreur": result.get("erreur"),
                "duree": int(result.get("duree_secondes", 0)),
                "scores_detail": scores_detail, "issues": issues_top,
                "recommandations": _build_recommendations(scores_detail, issues_top),
                "quick_mode": True,
            }

            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["status"] = "done"
                    _sessions[session_id]["result"] = result_data
            session["queue"].put({"type": "complete", "data": result_data})

        except Exception as e:
            err_msg = str(e)
            with _sessions_lock:
                if session_id in _sessions:
                    _sessions[session_id]["status"] = "error"
            session["queue"].put({"type": "error", "data": {"message": err_msg}})
        finally:
            clear_thread_event_queue()
            clear_code_preview()
            session["queue"].put(None)

    threading.Thread(target=run_quick_pipeline, daemon=True).start()
    return jsonify({"session_id": session_id, "quick_mode": True})


@app.route("/api/preview/<session_id>")
def api_preview(session_id):
    """
    Return the HTML game code generated in Phase 3, before evaluation.
    Enables live preview while the pipeline continues running.
    """
    with _sessions_lock:
        session = _sessions.get(session_id)
    if not session:
        return "Unknown session", 404
    from logger import get_preview_by_session
    html = get_preview_by_session(session_id)
    if not html:
        return "Preview not yet available — Phase 3 is not complete.", 202
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/game-patch", methods=["POST"])
def api_game_patch():
    """
    Modify a game in real time via a natural language prompt.
    Receives {filename, prompt, context} and returns {code: "JS snippet"}.
    The game calls eval(code) to apply the modification without reload.
    """
    data = request.get_json(force=True, silent=True) or {}
    filename = str(data.get("filename", "")).strip()
    user_prompt = str(data.get("prompt", "")).strip()
    context = data.get("context", {})

    # Security
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.endswith(".html"):
        return jsonify({"error": "File must be a .html"}), 400
    if not user_prompt:
        return jsonify({"error": "Empty prompt"}), 400
    if len(user_prompt) > 500:
        user_prompt = user_prompt[:500]

    html_path = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(html_path):
        return jsonify({"error": "File not found"}), 404

    # Extract a code snippet for Gemini context
    try:
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        return jsonify({"error": f"Cannot read file: {e}"}), 500

    # Extract key JS variables/structures to give Gemini proper context
    import re as _re
    js_snippet = _extract_game_context(html)

    # Runtime context passed from the game (optional)
    context_str = ""
    if context:
        context_str = f"\nCURRENT GAME STATE (runtime):\n{json.dumps(context, ensure_ascii=False, indent=2)}"

    # ── Detect game type to choose the right API doc ────────────────────────────
    _is_threejs = bool(_re.search(r'three\.js|THREE\.|WebGLRenderer|new THREE\b', html, _re.IGNORECASE))

    if _is_threejs:
        # ── API doc pour jeux Three.js 3D ──────────────────────────────────────
        GAME_API_DOC = """=== JEU THREE.JS 3D — VARIABLES ET API ===
IMPORTANT : ce jeu utilise Three.js. Les variables sont dans le scope du DOMContentLoaded.
Toutes les modifications passent par window.__devPatch (bridge injecté).

=== VARIABLES D'ÉTAT ===
player          — { mesh: THREE.Mesh, hp, maxHp, speed, active, box: THREE.Box3,
                    currentVelocity: THREE.Vector3, fireRate, lastFireTime, activeBuffs[] }
enemies[]       — ennemis actifs [{ mesh, hp, maxHp, speed, active, box }]
boss            — boss actuel (même structure) ou null
bullets[]       — projectiles actifs [{ mesh, vx, vy, vz, damage, active, box }]  (ou projectiles[])
score, gameState  — 'playing'|'menu'|'gameover'|'paused'
scene           — THREE.Scene (pour add/remove meshes)
camera          — THREE.PerspectiveCamera

=== FONCTIONS DISPONIBLES (selon le jeu) ===
createExplosion(position, color, count)     — explosion de particules Three.js
triggerShake(mag, dur)                      — screen shake (si défini)
spawnFloatingText(x, y, text, color, size)  — texte flottant (si défini)

=== RECETTES 3D (utiliser THREE. directement) ===
// Changer la couleur du vaisseau joueur :
player.mesh.traverse(child => { if(child.isMesh) child.material = child.material.clone(); });
player.mesh.traverse(child => { if(child.isMesh) child.material.color.set(0xFF0000); });

// Augmenter la vitesse du joueur :
player.speed = player.speed * 2;

// Rendre le joueur invincible :
player.invincible = true; player.invincibilityTime = 99999;

// Max HP :
player.hp = 9999; player.maxHp = 9999;

// Tuer tous les ennemis :
enemies.forEach(e => { e.hp = 0; e.active = false; scene.remove(e.mesh); }); enemies.length = 0;

// Freeze tous les ennemis :
enemies.forEach(e => e.speed = 0);

// Modifier le taux de tir (cadence doublée) :
player.fireRate = (player.fireRate || 0.3) * 0.5;

// Modifier les projectiles visuellement (laser cyan) SANS CASSER le tir :
// ⚠️ RÈGLE ABSOLUE : ne JAMAIS remplacer createProjectile — modifier seulement le mesh APRÈS création.
// ⚠️ L'objet retourné DOIT conserver : mesh, direction, speed, damage, active, shooter, box, distanceTraveled, range
// Recette laser — override sûr via wrapper :
(function(){
  var _orig = createProjectile;
  createProjectile = function(shooter, position, direction, speed, damage, color, range) {
    var p = _orig(shooter, position, direction, speed, damage, color, range);
    if (shooter === player) {
      scene.remove(p.mesh);
      var geo = new THREE.CylinderGeometry(0.05, 0.05, 2.5, 6);
      geo.rotateX(Math.PI/2);
      var mat = new THREE.MeshPhongMaterial({color:0x00FFFF, emissive:0x00FFFF, emissiveIntensity:1.0});
      p.mesh = new THREE.Mesh(geo, mat);
      p.mesh.position.copy(position);
      p.mesh.lookAt(position.clone().add(direction));
      scene.add(p.mesh);
      p.speed *= 1.5; p.damage *= 1.2;
    }
    return p;
  };
})();

// Double canon (2 projectiles décalés latéralement) :
(function(){
  var _orig = createProjectile;
  var _right = new THREE.Vector3();
  createProjectile = function(shooter, position, direction, speed, damage, color, range) {
    if (shooter !== player) return _orig(shooter, position, direction, speed, damage, color, range);
    _right.crossVectors(direction, new THREE.Vector3(0,1,0)).normalize().multiplyScalar(0.8);
    var p1 = _orig(shooter, position.clone().add(_right), direction, speed, damage, color, range);
    var p2 = _orig(shooter, position.clone().sub(_right), direction, speed, damage, color, range);
    bullets.push(p2); // p1 sera push par le code principal
    return p1;
  };
})();

// Spawner un ennemi (utilise les types réels du jeu) :
(function(){ var p=player.mesh.position; enemies.push(createEnemy(p.x+20, p.y, p.z-30, 'Asteroid_Classic')); })();
(function(){ var p=player.mesh.position; enemies.push(createEnemy(p.x, p.y, p.z-40, 'Drone_Hunter')); })();

// Tuer tous les ennemis :
enemies.forEach(e => { e.hp = 0; e.active = false; scene.remove(e.mesh); }); enemies.length = 0;

// Freeze tous les ennemis :
enemies.forEach(e => e.speed = 0);

// Ajouter des HP :
player.hp = Math.min(player.maxHp, player.hp + 50);

// Changer la couleur de fond de la scène :
scene.background = new THREE.Color(0x001133);

// Lire les propriétés actuelles (debug) :
console.log(JSON.stringify({hp:player.hp,speed:player.speed,fireRate:player.fireRate,lastFireTime:player.lastFireTime}));"""

    else:
        # ── API doc pour jeux 2D Canvas (RPG, platformer, tower defense, etc.) ──
        GAME_API_DOC = """=== VARIABLES D'ÉTAT (accessibles et modifiables) ===
hero            — {x, y, hp, mp, speed, facing, classId, level, xp, xpToNext, attack, defense, maxHp, maxMp, invincibilityTimer}
enemies[]       — ennemis actifs [{x, y, hp, maxHp, attack, speed, type, knockbackX, knockbackY, ...}]
boss            — boss actuel (même structure) ou null
loot[]          — objets au sol [{x, y, type, collected, ...}]
interactables[] — leviers/coffres/portes [{x, y, type, used, open, nearPlayer, ...}]
minions[]       — alliés invoqués (même structure qu'enemies)
playerStats     — {maxHp, hp, maxMp, mp, attack, defense, speed, invincibilityTimer, atkCooldown, skillCooldown}
playerInventory — {keys:N, potions:N, weapon:null|{}, armor:null|{}, accessory:null|{}}
activeBuffs[]   — [{type:'speed_boost'|'defense_boost'|'invincibility', value:N, duration:N}]
gameState       — 'PLAYING'|'PAUSED'|'MENU'|'CLASS_SELECT'|'GAMEOVER'|'VICTORY'
currentDungeonFloor — étage actuel (1-9)
score, gold, soulFragments
HERO_CLASSES[]  — tableau des classes jouables (modifiable en live)
CUSTOM_SKILLS   — {classId: function(){...}} — compétences custom
CUSTOM_ATTACKS  — {classId: function(baseDamage, attackRange){...}} — attaques custom
ENEMY_TYPES     — dictionnaire des types d'ennemis (lecture)
TILE_SIZE=16, ENEMY_SIZE=12, MAP_W=40, MAP_H=30

=== FONCTIONS DISPONIBLES ===
createEnemy(x, y, type)                     — crée un ennemi (retourne l'objet, à push dans enemies[])
spawnBoss(floor)                            — invoque le boss de l'étage N (1-9), le place dans boss
generateDungeon(floor)                      — régénère TOUT le donjon à l'étage N (reset enemies/loot/map!)
checkLevelUp(hero)                          — applique level-up si hero.xp >= hero.xpToNext
handleEnemyDefeat(enemy, idx)               — finalise la mort d'un ennemi (loot, XP, effets)
onBossDefeat()                              — finalise la victoire contre le boss (accès étage suivant)
applyKnockback(entity, fromX, fromY, force) — repousse une entité (knockbackX/Y)
spawnParticles(x, y, color, count)          — effet visuel de particules
spawnFloatingText(x, y, text, color, size)  — texte flottant animé
triggerShake(magnitude, duration)           — tremblement d'écran
createProjectile(x, y, vx, vy, damage, type, owner) — crée un projectile ('arrow','magic','fire','spirit')

=== RECETTES ADMIN (copier-adapter directement) ===
// Spawner un ennemi devant le héros :
enemies.push(createEnemy(hero.x + 48, hero.y, 'goblin'));

// Spawner un boss de l'étage actuel :
spawnBoss(currentDungeonFloor);

// Spawner un coffre devant le héros :
loot.push({ x: hero.x + 32, y: hero.y, type: 'chest_magic', collected: false, size: 12 });

// Level up immédiat :
hero.xp = hero.xpToNext; checkLevelUp(hero);

// Téléporter à l'étage 5 :
currentDungeonFloor = 5; generateDungeon(5);

// Activer tous les leviers + ouvrir la porte du boss :
interactables.filter(o => o.type === 'lever').forEach(l => { l.activated = true; l.used = true; });
if (bossGate) bossGate.open = true;

// Invincibilité JOUEUR :
hero.invincibilityTimer = 9999;

// Max stats joueur :
hero.attack = 999; playerStats.attack = 999; hero.defense = 99; playerStats.defense = 99;

// Tuer tous les ennemis :
[...enemies].forEach((e, i) => { e.hp = -1; handleEnemyDefeat(e, enemies.indexOf(e)); });
if (boss) { boss.hp = -1; onBossDefeat(); }

// Freezer tous les ennemis :
enemies.forEach(e => e.speed = 0); if (boss) boss.speed = 0;

// Créer une classe admin :
HERO_CLASSES.push({ id:'admin', name:'Admin GOD', color:'#FF0000', baseHp:9999, baseMp:9999, baseAtk:999, baseDef:999, baseSpd:150, atkName:'Frappe Divine', skillName:'Activer Leviers', atkCost:0, atkCooldown:0.05, skillCost:0, skillCooldown:2, skillDuration:1 });
CUSTOM_SKILLS['admin'] = function() { interactables.filter(o=>o.type==='lever').forEach(l=>{l.activated=true;l.used=true;}); if(bossGate){bossGate.open=true;} hero.invincibilityTimer=9999; triggerShake(6,0.4); };"""

    # ── Intent detection ─────────────────────────────────────────────────────
    import re as _re2

    _creation_words  = r'\b(cr[ée]{1,2}r?|ajouter?|nouveau|nouvelle|faire|invente[rz]?|fais|génère[rz]?|conçois?|construis?)\b'
    _modif_words     = r'\b(modifie[rz]?|changer?|augmenter?|diminuer?|r[ée]duire?|am[ée]liore[rz]?|baisser?|mettre|rendre|rends?|augmente?|booster?|nerfe[rz]?|up(?:grade)?|buff|nerf|monte[rz]?|hausse[rz]?)\b'
    _class_words     = r'\b(classe|class|h[ée]ros?|personnage|perso|character)\b'

    # Creation: creation word + class word, without modification word
    # Special case: "nouvelle classe" or "créer un perso" without ambiguity
    has_class_word    = bool(_re2.search(_class_words, user_prompt, _re2.IGNORECASE))
    has_creation_word = bool(_re2.search(_creation_words, user_prompt, _re2.IGNORECASE))
    has_modif_word    = bool(_re2.search(_modif_words, user_prompt, _re2.IGNORECASE))
    # "nouvelle classe" / "un nouveau perso" suffit même sans verbe explicite
    has_new_class     = bool(_re2.search(r'\b(nouveau|nouvelle|new)\b.*\b(classe|class|h[ée]ros?|perso)\b', user_prompt, _re2.IGNORECASE))

    # Three.js games don't have HERO_CLASSES — disable class detection
    is_class_creation = (not _is_threejs) and (
        (has_class_word and has_creation_word and not has_modif_word)
        or has_new_class
    )

    # Modification of an existing class
    _class_stat_words = r'\b(classe|class|h[ée]ros?|personnage|perso|vitesse|speed|d[ée]g[aâ]ts?|attaque?|d[ée]fense?|hp|vie|mana|mp|comp[ée]tence|skill|rapide|lent|fort|puissant|faible|lente?)\b'
    is_class_modification = (
        not _is_threejs
        and not is_class_creation
        and has_modif_word
        and bool(_re2.search(_class_stat_words, user_prompt, _re2.IGNORECASE))
    )

    # ── Common rules ─────────────────────────────────────────────────────────
    RULES = """RÈGLES ABSOLUES :
- Retourne UNIQUEMENT du code JavaScript pur, sans markdown, sans backticks, sans commentaires
- Le code DOIT être syntaxiquement COMPLET — toutes accolades/parenthèses/crochets fermés
- Ne redéclare pas les variables existantes (pas de let/const/var devant hero, enemies, etc.)
- WRAPPER OBLIGATOIRE : tout snippet complexe (> 3 lignes) DOIT être encapsulé dans :
  (function(){ try { /* ton code ici */ } catch(e){ console.error('[PATCH]', e.message); } })();
- DÉFENSE OBLIGATOIRE contre les undefined/null :
  * Toujours vérifier typeof avant d'accéder : if(typeof hero !== 'undefined' && hero)
  * boss peut être null → toujours if(boss) avant d'y accéder
  * bossGate peut être null → toujours if(bossGate)
  * enemies peut être vide → vérifier enemies.length avant d'indexer
  * Utiliser l'opérateur ?. (optional chaining) pour les accès chaînés incertains
  * Ne jamais appeler une fonction sans vérifier qu'elle existe : if(typeof fn==='function') fn()
- Si une variable n'est PAS confirmée dans le contexte, NE PAS l'utiliser — adapter la logique"""

    if is_class_creation:
        system = f"""Tu es un expert JavaScript spécialisé dans les jeux HTML5 dungeon crawler.
Tu génères du code JavaScript à exécuter via eval() dans le jeu pour créer une nouvelle classe jouable.

{RULES}
- Génère EXACTEMENT 3 ou 4 blocs sur des lignes séparées, ULTRA-COMPACTS (tout sur une seule ligne par bloc) :
  1. HERO_CLASSES.push({{id, name, description, color, baseHp, baseMp, baseAtk, baseDef, baseSpd, atkName, skillName, atkCost, atkCooldown, skillCost, skillCooldown, skillDuration}});
  2. CUSTOM_SKILLS['id'] = function() {{ /* mécanique courte */ }};
  3. (optionnel) CUSTOM_ATTACKS['id'] = function(baseDmg, atkRange) {{ /* attaque courte */ }};
  4. window.__customSkillDescs = window.__customSkillDescs||{{}}; window.__customSkillDescs['id'] = 'NomSkill (X) : Description. Coût: NMP. CD: Ns.';
- Chaque ligne DOIT être syntaxiquement COMPLÈTE et fermée — JAMAIS couper une fonction en cours

STATS — valeurs cohérentes avec les classes de base :
  baseHp   : 80-150  (warrior=150, rogue=80)
  baseMp   : 60-120  (mage=120, warrior=60)
  baseAtk  : 8-15    (warrior=15, mage=10)
  baseDef  : 2-8     (warrior=8, rogue=3)
  baseSpd  : 60-90   (rogue=80, warrior=60) — JAMAIS 1 ni 0 ni >100
  atkCooldown : 0.5-1.5s
  skillCost   : 15-30 MP
  skillCooldown: 5-10s
  skillDuration: 2-5s

API disponible dans CUSTOM_SKILLS / CUSTOM_ATTACKS :
  hero (x,y,hp,mp,speed,invincibilityTimer,skillActiveTimer), enemies[], boss, playerStats, activeBuffs[]
  interactables[], bossGate, minions[]
  applyKnockback(e,fromX,fromY,force), spawnParticles(x,y,color,count)
  spawnFloatingText(x,y,text,color,size), triggerShake(mag,dur)
  handleEnemyDefeat(enemy,idx), onBossDefeat()
  createEnemy(x,y,type), createProjectile(x,y,vx,vy,dmg,type,owner)

BUFFS disponibles (via activeBuffs.push) :
  {{type:'speed_boost_custom', _baseSpeed:hero.speed, duration:N}}  → restaure la vitesse après N secondes
  {{type:'defense_boost', value:N, duration:N}}                      → +N défense pendant N secondes

EXEMPLES DE MÉCANIQUES de compétence (créer quelque chose de NOUVEAU et thématiquement cohérent) :
  - Boost de vitesse temporaire : var s=hero.speed; hero.speed=s*2; playerStats.speed=s*2; activeBuffs.push({{type:'speed_boost_custom',_baseSpeed:s,duration:4}});
  - Soins + particules : hero.hp=Math.min(hero.maxHp,hero.hp+40); spawnParticles(hero.x,hero.y,'#00ff88',15);
  - AOE dégâts proches : enemies.filter(e=>Math.hypot(e.x-hero.x,e.y-hero.y)<100).forEach(e=>{{e.hp-=30;applyKnockback(e,hero.x,hero.y,20);}});
  - Invincibilité courte : hero.invincibilityTimer=hero.skillActiveTimer||3;

RÈGLES DÉFENSIVES OBLIGATOIRES dans CUSTOM_SKILLS et CUSTOM_ATTACKS :
  - Toujours vérifier : if(boss) avant d'accéder à boss
  - Toujours vérifier : if(bossGate) avant d'accéder à bossGate
  - Toujours vérifier : if(enemies.length) avant forEach sur enemies
  - Ne JAMAIS accéder à enemies[0] sans vérifier enemies.length > 0
  - Utiliser Math.min/Math.max pour les stats (ex: hero.hp=Math.min(hero.maxHp,hero.hp+40))
  - Wrapper le corps entier dans try{{...}}catch(e){{console.error(e);}} si la logique est complexe

RÈGLE DESCRIPTION : le champ 'description' de HERO_CLASSES doit expliquer le thème du personnage ET sa compétence (max 60 chars).
IMPÉRATIF : chaque ligne doit tenir en moins de 300 caractères. Fonctions ultra-compactes, pas d'espaces superflus."""

        # For creation we only need the IDs/names of existing classes
        known_ids = context.get("heroClassIds", []) if context else []
        existing_summary = "Classes existantes : " + ", ".join(known_ids) if known_ids else js_snippet[:300]
        prompt = f"""{existing_summary}

DEMANDE : {user_prompt}

Génère exactement 3 ou 4 lignes JS (HERO_CLASSES.push / CUSTOM_SKILLS / optionnel CUSTOM_ATTACKS / window.__customSkillDescs).
Chaque ligne syntaxiquement COMPLÈTE, baseSpd entre 60 et 90, mécanique de compétence réelle."""
        max_tok = 12000

    elif is_class_modification:
        # Existing classes known via runtime context
        known_ids = context.get("heroClassIds", []) if context else []
        known_ids_str = ", ".join(f"'{i}'" for i in known_ids) if known_ids else "voir HERO_CLASSES"

        system = f"""Tu es un expert JavaScript spécialisé dans les jeux HTML5 dungeon crawler.
Tu génères du code JavaScript pour MODIFIER une classe existante dans HERO_CLASSES via eval().

{RULES}
- NE JAMAIS faire HERO_CLASSES.push() — modifier UNIQUEMENT la classe existante
- Utilise HERO_CLASSES.find(c => c.id === 'ID') pour trouver la classe
- Après avoir modifié la classe, TOUJOURS mettre à jour les stats live du héros si c'est sa classe :
    if (hero && hero.classId === cls.id) {{ hero.speed = cls.baseSpd; playerStats.speed = cls.baseSpd; }}
- Pour chaque stat modifiée, mettre à jour la prop correspondante sur hero ET playerStats :
    baseSpd   → hero.speed + playerStats.speed
    baseAtk   → hero.attack + playerStats.attack
    baseDef   → hero.defense + playerStats.defense
    baseHp    → hero.maxHp + playerStats.maxHp (ne pas réduire hero.hp en dessous de 1)
    baseMp    → hero.maxMp + playerStats.maxMp
- Pour CUSTOM_SKILLS / CUSTOM_ATTACKS : remplacer la fonction existante, pas en ajouter une nouvelle
- Classes disponibles : {known_ids_str}"""

        prompt = f"""HERO_CLASSES et classes custom actuelles :
{js_snippet[:1000]}
{context_str}

DEMANDE : {user_prompt}

Génère le code JS qui MODIFIE la classe existante (pas de push) et applique les changements en temps réel."""
        max_tok = 4000

    else:
        # ── Dynamic API doc for 2D Canvas games ────────────────────────────────
        _game_type = _detect_game_type(js_snippet)

        # Variables section (extract let lines from js_snippet)
        import re as _re_eb
        _let_lines = [l for l in js_snippet.splitlines() if l.strip().startswith('let ')][:30]
        _let_block = '\n'.join(_let_lines) if _let_lines else "(voir contexte ci-dessus)"

        # Functions section
        _fn_lines = [l for l in js_snippet.splitlines() if l.strip().startswith('// ') and '(' in l and 'Type de jeu' not in l and 'Tableaux' not in l and 'Variables' not in l][:20]
        _fn_block = '\n'.join(_fn_lines) if _fn_lines else "(voir contexte ci-dessus)"

        # Arrays section
        _arr_match = _re_eb.search(r'// Tableaux \(arrays\) : (.+)', js_snippet)
        _arr_block = _arr_match.group(1) if _arr_match else "(aucun détecté)"

        # Recipes adapted to the game type
        if _game_type == 'tower_defense':
            _recettes = """=== RECETTES TOWER DEFENSE ===
// Ajouter une tour :
if(typeof towers !== 'undefined') towers.push({x: 200, y: 200, type: 'arrow', level: 1, hp: 100, maxHp: 100});

// Ajouter de l'or :
if(typeof gold !== 'undefined') gold += 500;

// Passer à la vague suivante :
if(typeof wave !== 'undefined') wave++;

// Tuer tous les ennemis :
if(typeof enemies !== 'undefined') enemies.forEach(function(e){ e.hp = -1; });"""
        elif _game_type == 'platformer':
            _recettes = """=== RECETTES PLATFORMER ===
// Téléporter le joueur :
if(typeof player !== 'undefined'){ player.x = 200; player.y = 100; }

// Ajouter des vies :
if(typeof lives !== 'undefined') lives += 3;

// Ajouter des points :
if(typeof score !== 'undefined') score += 1000;

// Rendre invincible :
if(typeof player !== 'undefined') player.invincible = true;"""
        elif _game_type in ('rpg', 'rpg_dungeon'):
            _recettes = """=== RECETTES RPG / DUNGEON ===
// Spawner un ennemi :
if(typeof enemies !== 'undefined' && typeof createEnemy === 'function') enemies.push(createEnemy(hero.x + 48, hero.y, 'goblin'));

// Level up immédiat :
if(typeof hero !== 'undefined' && typeof checkLevelUp === 'function'){ hero.xp = hero.xpToNext; checkLevelUp(hero); }

// Max stats :
if(typeof hero !== 'undefined'){ hero.attack = 999; hero.defense = 99; }

// Téléporter étage :
if(typeof generateDungeon === 'function') generateDungeon(5);"""
        elif _game_type == 'puzzle':
            _recettes = """=== RECETTES PUZZLE ===
// Ajouter des points :
if(typeof score !== 'undefined') score += 1000;

// Passer au niveau suivant :
if(typeof level !== 'undefined') level++;

// Vider la grille :
if(typeof pieces !== 'undefined') pieces.length = 0;"""
        else:
            _recettes = """=== RECETTES GÉNÉRIQUES ===
// Modifier le score :
if(typeof score !== 'undefined') score += 1000;

// Modifier les vies :
if(typeof lives !== 'undefined') lives = 99;

// Modifier la vitesse du joueur :
var _p = typeof player !== 'undefined' ? player : (typeof hero !== 'undefined' ? hero : null);
if(_p) _p.speed = (_p.speed || 5) * 2;"""

        GAME_API_DOC = f"""=== VARIABLES DÉTECTÉES DANS CE JEU ===
{_let_block}

=== FONCTIONS DISPONIBLES ===
{_fn_block}

=== ARRAYS/TABLEAUX ===
{_arr_block}

=== RÈGLES DE SÉCURITÉ ABSOLUES ===
- TOUJOURS wrapper tout le code généré dans : (function(){{ try {{ ... votre_code ... }} catch(e){{ console.error('[PATCH]',e); }} }})();
- TOUJOURS vérifier typeof avant d'accéder à une variable : if(typeof hero !== 'undefined' && hero)
- Ne JAMAIS utiliser de variables non confirmées dans le contexte ci-dessus
- Si une variable n'existe pas dans le jeu, ne pas l'utiliser — adapter la recette
- Pour chaque tableau (array) : vérifier arr.length > 0 avant d'accéder à arr[0]

{_recettes}"""

        # ── Complex request → full code + function wrapping ─────────────────
        is_complex = _is_complex_request(user_prompt)

        if is_complex:
            _full_js = _extract_full_js_code(html, max_chars=40000)
            system = f"""Tu es un expert JavaScript spécialisé dans les jeux HTML5 ({_game_type}).
Tu implémentes une modification COMPLEXE (nouveau système/mécanique/type) dans un jeu en temps réel via eval().

{RULES}
- Utilise la technique de FUNCTION WRAPPING pour étendre les fonctions existantes sans les casser :
  (function(){{
    var _orig = nomFonction;
    nomFonction = function(/* params */) {{
      var result = _orig.apply(this, arguments);
      // Tes ajouts ici
      return result;
    }};
  }})();
- Utilise un flag d'installation pour éviter les doublons :
  if (window.__nom_systeme_installed) return; window.__nom_systeme_installed = true;
- Injecte les nouveaux systèmes dans la boucle de jeu existante via wrapping ou setInterval en dernier recours
- Si tu ajoutes des types (ennemis, items, tours...) : utilise la même structure que les types existants
- Documente brièvement ce que tu fais avec des commentaires courts

Réponds UNIQUEMENT en JSON valide (sans markdown, sans backticks) :
{{
  "explanation": "Ce que tu as implémenté (2-3 phrases max)",
  "code": "// tout le code JS sur une seule chaîne avec \\n pour les retours à la ligne"
}}"""

            prompt = f"""CODE COMPLET DU JEU ({_game_type}) :
```javascript
{_full_js}
```

CONTEXTE RUNTIME :
{context_str or "(non fourni)"}

DEMANDE COMPLEXE : {user_prompt}

Analyse le code, identifie les structures existantes, puis génère le code JS qui implémente cette modification.
Utilise function wrapping pour les modifications de fonctions existantes.
Réponds en JSON : {{"explanation": "...", "code": "..."}}"""
            max_tok = 20000
        else:
            system = f"""Tu es un expert JavaScript spécialisé dans les jeux HTML5 ({_game_type}).
Tu génères UN SNIPPET JavaScript minimal exécuté via eval() pour modifier le jeu EN TEMPS RÉEL.

{RULES}
- Snippets courts (< 20 lignes), chirurgicaux, utilise exactement les noms détectés dans le contexte
- Si impossible sans rechargement : throw new Error("Nécessite un rechargement")

{GAME_API_DOC}"""

            prompt = f"""CONTEXTE DU JEU :
{js_snippet}
{context_str}

DEMANDE : {user_prompt}

Génère le snippet JS minimal et syntaxiquement complet."""
            max_tok = 6000

    def _is_truncated(code):
        opens    = code.count('{') - code.count('}')
        parens   = code.count('(') - code.count(')')
        brackets = code.count('[') - code.count(']')
        # Seuil strict : tout déséquilibre = tronqué
        return abs(opens) > 0 or abs(parens) > 0 or abs(brackets) > 0

    def _clean(code):
        import re as _re3
        return _re3.sub(r'```[a-z]*\n?', '', code).strip()


    # _expects_json est mis à True dans le bloc complex ci-dessus via is_complex

    try:
        from config import call_gemini, call_gemini_json

        if locals().get('is_complex', False):
            # Demande complexe → JSON {"explanation": "...", "code": "..."}
            result_dict = call_gemini_json(prompt, temperature=0.2, system_instruction=system, max_tokens=max_tok)
            code = _clean(result_dict.get("code", ""))
            explanation = result_dict.get("explanation", f"Modification appliquée : {user_prompt[:120]}")

            if not code:
                return jsonify({"error": "Gemini n'a pas retourné de code dans le JSON"}), 500

            if _is_truncated(code):
                return jsonify({"error": "Code tronqué — essaie de décomposer la demande en étapes plus simples."}), 422

            return jsonify({"code": code, "explanation": explanation})

        else:
            # Demande simple → code brut
            code = call_gemini(prompt, temperature=0.15, system_instruction=system, max_tokens=max_tok)
            if not code:
                return jsonify({"error": "Gemini n'a pas retourné de code"}), 500
            code = _clean(code)

            # Si tronqué → retry avec prompt ultra-minimaliste
            if _is_truncated(code):
                retry_system = system + "\n\nCRITIQUE : le code précédent était tronqué. Écris des fonctions ULTRA-COURTES (1 seule instruction par fonction max). Chaque ligne < 150 chars."
                code2 = call_gemini(prompt, temperature=0.1, system_instruction=retry_system, max_tokens=max_tok)
                if code2:
                    code2 = _clean(code2)
                    if not _is_truncated(code2):
                        code = code2
                    else:
                        return jsonify({"error": "Code tronqué après retry — simplifie la demande."}), 422

            return jsonify({"code": code, "explanation": f"Appliqué : {user_prompt[:120]}"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    """Pipeline health dashboard."""
    import subprocess, shutil, os as _os
    health = {"status": "ok", "checks": {}}

    # Check Node.js (required for js_syntax_checker)
    node_ok = shutil.which("node") is not None
    if node_ok:
        try:
            r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            health["checks"]["node"] = {"ok": r.returncode == 0, "version": r.stdout.strip()}
        except Exception:
            health["checks"]["node"] = {"ok": False, "version": None}
    else:
        health["checks"]["node"] = {"ok": False, "version": None}

    # Check Playwright (required for agent_executeur)
    try:
        from playwright.sync_api import sync_playwright
        health["checks"]["playwright"] = {"ok": True}
    except Exception as e:
        health["checks"]["playwright"] = {"ok": False, "error": str(e)}

    # Check ChromaDB (RAG vector database)
    try:
        import rag
        rag_stats = rag.get_stats()
        health["checks"]["chromadb"] = {"ok": True, "patterns": rag_stats.get("total_patterns", 0)}
    except Exception as e:
        health["checks"]["chromadb"] = {"ok": False, "error": str(e)}

    # Check Gemini API key
    api_key_set = bool(_os.environ.get("GEMINI_API_KEY") or _os.environ.get("GOOGLE_API_KEY") or _os.environ.get("GEMINI_PAID_KEY"))
    health["checks"]["gemini_api_key"] = {"ok": api_key_set}

    # Check memory.json state file
    try:
        import memory
        stats = memory.get_stats()
        health["checks"]["memory"] = {
            "ok": True,
            "total_generated": stats.get("total_games_generated", 0),
            "total_saved": stats.get("total_games_saved", 0),
        }
    except Exception as e:
        health["checks"]["memory"] = {"ok": False, "error": str(e)}

    # Check saved games directory
    save_dir = _os.path.join(_os.path.dirname(__file__), "jeux_sauvegardes")
    game_count = len([f for f in _os.listdir(save_dir) if f.endswith(".html")]) if _os.path.isdir(save_dir) else 0
    health["checks"]["save_dir"] = {"ok": True, "game_files": game_count}

    # Check active session count
    health["checks"]["active_sessions"] = {"count": len(_sessions)}

    # Global status
    critical_failed = [k for k, v in health["checks"].items() if not v.get("ok") and k in ("gemini_api_key", "playwright")]
    health["status"] = "degraded" if critical_failed else "ok"
    health["critical_issues"] = critical_failed

    return jsonify(health)


@app.route("/api/stats")
def api_stats():
    try:
        import memory
        stats = memory.get_stats()
        import rag
        stats["rag"] = rag.get_stats()
        # Dashboard genre profiler — taux d'approbation, scores par dimension, patch_bank
        try:
            import genre_profiler
            stats["genre_dashboard"] = genre_profiler.get_dashboard()
        except Exception:
            pass
        # Derniers échecs pour observabilité
        try:
            import json as _json, os as _os
            failures_path = _os.path.join(_os.path.dirname(__file__), "failures_log.json")
            if _os.path.exists(failures_path):
                with open(failures_path, "r", encoding="utf-8") as _f:
                    stats["recent_failures"] = _json.load(_f)[-10:]  # 10 derniers
        except Exception:
            pass
        return jsonify(stats)
    except Exception:
        return jsonify({})


@app.route("/api/quota")
def api_quota():
    """Return RPD quota status per key — no API call made."""
    try:
        from config import get_quota_status
        return jsonify(get_quota_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def _build_mechanics_kb_async():
    """Populate the mechanics knowledge base in the background at startup (if empty)."""
    try:
        import build_mechanics_kb
        n = build_mechanics_kb.build(force=False)
        if n > 0:
            print(f"  [MechanicsKB] {n} entries indexed in ChromaDB.")
    except Exception as e:
        print(f"  [MechanicsKB] Build skipped: {e}")


# Background threads (run under both `python app.py` and gunicorn/WSGI)
# Placed here (outside __main__) so they also run when Flask is started by a WSGI server
threading.Thread(target=_build_mechanics_kb_async, daemon=True, name="mechanics-kb-build").start()
threading.Thread(target=_session_cleanup_loop, daemon=True, name="session-cleanup").start()

if __name__ == "__main__":
    os.makedirs(SAVE_DIR, exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    print("\n" + "=" * 60)
    print("  ARCADE AI — Web Interface")
    print("  http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=False, port=5000, threaded=True, use_reloader=False)

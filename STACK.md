# Arcade Project v2 — Full Stack Reference

> Authoritative reference for every technology in this project.
> Use this to prepare for technical interviews — each section covers what the technology is,
> what role it plays here specifically, where it appears in the code, and how it connects to everything else.

---

## Table of Contents

1. [Python](#1-python)
2. [Gemini 2.5-Flash (google-genai)](#2-gemini-25-flash-google-genai)
3. [Claude (Anthropic SDK)](#3-claude-anthropic-sdk)
4. [Flask](#4-flask)
5. [Server-Sent Events (SSE)](#5-server-sent-events-sse)
6. [Playwright](#6-playwright)
7. [ChromaDB (RAG)](#7-chromadb-rag)
8. [Three.js](#8-threejs)
9. [Canvas 2D API](#9-canvas-2d-api)
10. [WebAudio API](#10-webaudio-api)
11. [Node.js](#11-nodejs)
12. [Threading / concurrent.futures](#12-threading--concurrentfutures)
13. [httpx](#13-httpx)
14. [python-dotenv](#14-python-dotenv)
15. [sentence-transformers (optional)](#15-sentence-transformers-optional)
16. [How everything connects](#16-how-everything-connects)

---

## 1. Python

**What it is:** The main programming language of the entire backend.

**What it does in this project:**
Every agent, every pipeline phase, the web server, the validation logic, the RAG system — all written in Python. It is the glue that connects all other technologies together. Python 3.10+ is used (with `match/case`, walrus operator, `|` union types).

**Where it appears:**
- Every `.py` file in the project
- Entry points: `app.py` (web server), `coordinateur.py` (pipeline runner), `coordinateur.py::run()` (main generation function)
- Key pattern: `@dataclass` in `genre_profile.py` for all data structures passed between agents

**How it connects to the rest:**
Python calls Gemini via `google-genai`, launches Playwright via `playwright.async_api`, queries ChromaDB via `chromadb`, and serves the web UI via Flask. All inter-agent communication is just Python function calls passing dataclasses.

---

## 2. Gemini 2.5-Flash (google-genai)

**What it is:** Google's large language model, accessed through the `google-genai` Python SDK. The brain of the pipeline.

**What it does in this project:**
Gemini generates everything that requires creative or analytical intelligence: genre profiling, game design documents, full HTML5/JavaScript game code, quality evaluations, and code patches. It is called 20-40 times per game generation.

Two tiers are used:
- **Free tier** (`gemini-2.5-flash`): multi-key rotation across up to 20 API keys (`GEMINI_API_KEY`, `GEMINI_API_KEY_1`...`GEMINI_API_KEY_20`), rate-limited to 4 RPM / 19 RPD per key
- **Paid tier** (`gemini-2.5-flash` via `GEMINI_PAID_KEY`): used for the critical generation and patching agents (no rate limit concerns)

**Where it appears:**
- `config.py` — all Gemini wrappers:
  - `call_gemini()` (lines ~365-460): free tier with key rotation and RPM/RPD tracking
  - `call_gemini_paid()` (lines ~309-362): paid key for game code generation
  - `call_gemini_json()` / `call_gemini_paid_json()`: same but forces JSON output and parses it
- `config.py::_rotate_key()`: picks the next free key that hasn't hit its rate limit
- `.quota_rpd.json`: file that persists daily usage counts, reset at UTC midnight

**How it connects to the rest:**
Every agent (`agent_game_designer`, `agent_qc_technique`, `agent_patcher`, etc.) calls `call_gemini_json()` or `call_gemini_paid_json()`. The result (a Python dict) is parsed into dataclasses (`GenreProfile`, `EvaluationResult`, etc.) and passed to the next phase.

---

## 3. Claude (Anthropic SDK)

**What it is:** Anthropic's Claude model (`claude-sonnet-4-6`), used as a fallback for one specific agent.

**What it does in this project:**
Claude handles `agent_game_logics` in Phase 2 — the agent that writes concrete, implementable game mechanics formulas. Claude tends to produce more precise mathematical/logical game rules than Gemini for this task.

**Where it appears:**
- `config.py::call_claude()` (lines ~577-610): wraps `anthropic.Anthropic().messages.create()`
- `agents/phase2/agent_game_logics.py`: imports and calls `call_claude()`
- Rate limit: 1 second minimum between calls (`CLAUDE_API_DELAY = 1.0` in `config.py`)

**How it connects to the rest:**
`agent_game_logics` produces a `game_logics` dict that is passed into Phase 3 (game generation) as additional context. Claude only runs once per pipeline execution.

---

## 4. Flask

**What it is:** A lightweight Python web framework. It powers the entire web interface of the project.

**What it does in this project:**
Flask serves the 3-page web UI (generation page, game viewer, history), exposes a REST API for triggering generation and retrieving results, and handles the SSE stream that sends real-time progress to the browser.

**Where it appears:**
- `app.py` — the entire web server
- Key routes:
  - `GET /` → `index.html` (generation UI)
  - `GET /play/<filename>` → `game.html` (game viewer with scores)
  - `POST /api/generate` → launches `coordinateur.run()` in a background thread, returns `{session_id}`
  - `GET /api/stream/<session_id>` → SSE stream (see section 5)
  - `GET /api/history` → JSON list of all saved games
  - `GET /api/preview/<session_id>` → returns the HTML being generated mid-Phase 3
  - `GET /debug/<filename>` → per-agent score breakdown and full pipeline log

**How it connects to the rest:**
Flask receives the user prompt, passes it to `coordinateur.run()` in a daemon thread, and exposes the event queue as an SSE stream. After generation, it serves the HTML game file directly from `jeux_sauvegardes/`.

---

## 5. Server-Sent Events (SSE)

**What it is:** A browser standard for one-way real-time data streaming from server to client over HTTP.

**What it does in this project:**
Every log line, agent result, and score produced during generation is pushed to the browser in real time. The user sees the pipeline progress live (Phase 1 → Phase 2 → ... → Final score) without polling.

**Where it appears:**
- `logger.py`: each Logger method (`info`, `success`, `score`, `agent_start`, etc.) calls `push_event()` which puts a JSON dict into a `queue.Queue`
- `logger.py::set_thread_event_queue(q)`: called by Flask before launching `coordinateur.run()` to bind the queue to the generation thread
- `logger.py`: uses `threading.local()` so each concurrent generation has its own isolated queue
- `app.py::stream_events()` (`GET /api/stream/<session_id>`): reads from the queue and yields SSE-formatted lines: `data: {"type": "score", "data": {...}}\n\n`
- `templates/index.html`: JavaScript `EventSource` receives events and updates the UI

**How it connects to the rest:**
The queue is the communication channel between the pipeline (running in a background thread) and the browser. Every agent in every phase logs to the same Logger, which transparently routes to the right queue.

---

## 6. Playwright

**What it is:** A browser automation library that can control a real browser (Chromium) in headless mode from Python.

**What it does in this project:**
Playwright is the only way to know if a generated game actually *works*. It opens the HTML file in a real browser, waits for the game to initialize, checks for JavaScript errors, measures canvas activity (is the screen black?), simulates player inputs, and returns an execution score (0-10).

**Where it appears:**
- `agents/phase4/agent_executeur.py::run()`: main evaluation function
  - Opens the game HTML with `page.goto(f"file://{path}")`
  - Waits 7 seconds for 3D games (WebGL shader compile time), 3s for 2D
  - `page.on('pageerror', ...)`: captures JavaScript runtime errors
  - `page.evaluate("document.querySelector('canvas')?.toDataURL()")`: screenshots canvas to detect black screen
  - `page.keyboard.press('Space')` / `page.keyboard.press('ArrowLeft')`: simulates player input
- `preflight_check.py`: same Playwright logic but used in Phase 3.5 (before the main eval loop) for an early crash check with up to 2 LLM fix rounds
- Both use `async_playwright()` context manager

**How it connects to the rest:**
The execution score (0-10) from Playwright is the most important single metric. If execution < 4.0, the QC Technique score is capped to 6.0. If execution < 5.0, the global score is capped to 4.5. This forces the pipeline to prioritize fixing runtime crashes over everything else.

---

## 7. ChromaDB (RAG)

**What it is:** An open-source vector database that stores and retrieves text snippets by semantic similarity.

**What it does in this project:**
ChromaDB is the project's long-term memory. Every time a game scores ≥ 7.5, its code patterns are saved to ChromaDB. When a new game of the same genre is being generated, the pipeline retrieves the most similar past patterns and injects them into the generation prompt — so the LLM learns from its own past successes.

**Where it appears:**
- `rag.py`: the RAG interface
  - `store_pattern(genre, code, score, metadata)`: saves a successful game pattern
  - `search_patterns(genre, n=3)`: retrieves the top-n most similar patterns for a genre
  - `PersistentClient(path="rag_database/")`: ChromaDB stores data on disk in `rag_database/`
  - Collection: `game_patterns` with cosine similarity
- `agent_sauvegarde.py`: calls `rag.store_pattern()` after each approved game
- `coordinateur.py` Phase 3: calls `rag.search_patterns()` to inject past patterns into the generator prompt
- `seed_rag_models.py`: one-time script that seeds 25 hand-crafted model games into ChromaDB

**How it connects to the rest:**
ChromaDB acts as a feedback loop: good games → stored in ChromaDB → retrieved next generation → better games. Without it (or with an empty database), every run starts from zero. The embeddings are created by `sentence-transformers` if available, or ChromaDB's built-in fallback.

---

## 8. Three.js

**What it is:** A JavaScript 3D rendering library that wraps WebGL (the browser's GPU-accelerated graphics API) into a usable API.

**What it does in this project:**
Three.js powers all 3D games generated by the pipeline. Every 3D game (FPS, 3D platformer, tower defense 3D, space shooter 3D, etc.) includes Three.js via CDN and uses it to render the 3D scene, manage the camera, handle collisions, and create visual effects.

**Where it appears:**
- All `templates/game_templates/genres/*_3d.html` files
- CDN: `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js` (r160, standardized across all templates)
- Core objects in every 3D game:
  ```javascript
  const scene    = new THREE.Scene();
  const camera   = new THREE.PerspectiveCamera(75, W/H, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  const clock    = new THREE.Clock();  // delta time source
  ```
- Collision detection: `new THREE.Box3().setFromObject(mesh)` + `.intersectsBox()`
- Geometries: `BoxGeometry`, `SphereGeometry`, `CylinderGeometry`, `PlaneGeometry`
- Materials: `MeshPhongMaterial`, `MeshStandardMaterial`
- Lighting: `AmbientLight` + `DirectionalLight` (both required — missing either = black screen)

**How it connects to the rest:**
`agent_moderateur_classificateur.py` detects keywords like "3D", "FPS", "first-person" and sets `GenreProfile.technologie_rendu = "threejs"`. This flag routes Phase 3 to use 3D templates and triggers Three.js-specific evaluation criteria in all QC agents.

---

## 9. Canvas 2D API

**What it is:** The browser's built-in 2D drawing API, accessed through an HTML `<canvas>` element. No external library needed.

**What it does in this project:**
Canvas 2D powers all 2D games (platformers, match-3, shoot-em-ups, runners, etc.). The ENGINE in every 2D template sets up the canvas, handles DPR scaling, and provides a fixed-timestep game loop. The LLM fills in the game-specific drawing code.

**Where it appears:**
- All `templates/game_templates/genres/*.html` 2D templates
- ENGINE setup (same in every template):
  ```javascript
  const canvas = document.getElementById('gameCanvas');
  const ctx    = canvas.getContext('2d');
  const DPR    = Math.min(window.devicePixelRatio || 1, 2);
  let W = 480, H = 640;
  ```
- Key drawing commands used: `ctx.fillRect`, `ctx.strokeRect`, `ctx.arc`, `ctx.fillText`, `ctx.save/restore`, `ctx.translate`, `ctx.shadowBlur`

**How it connects to the rest:**
The canvas is the output surface that Playwright screenshots to detect black screens. The `code_validator.py` has Canvas 2D-specific auto-fixes (missing `ctx.clearRect`, wrong canvas ID, etc.). QC Visuel specifically checks for canvas drawing richness (particles, glow, background detail).

---

## 10. WebAudio API

**What it is:** The browser's built-in synthesized audio API. It generates sounds from scratch using oscillators — no audio files needed.

**What it does in this project:**
Every generated game has sound effects (menu clicks, hits, deaths, level up) without any external audio file. The ENGINE in every template provides an `sfx` object that wraps WebAudio.

**Where it appears:**
- Every game template — the `sfx` object is in the ENGINE section:
  ```javascript
  const sfx = {
    _ctx: null,
    play(freq, dur, type, vol) {
      // Creates AudioContext oscillator on demand
      const osc = this._ctx.createOscillator();
      osc.type = type;           // 'sine', 'square', 'sawtooth', 'triangle'
      osc.frequency.value = freq; // pitch in Hz
      // gain.exponentialRampToValueAtTime(...) for fade-out
    }
  };
  ```
- Usage examples in generated games: `sfx.play(440, 0.08, 'sine', 0.1)` (menu tap), `sfx.play(110, 0.25, 'sawtooth', 0.15)` (explosion)

**How it connects to the rest:**
The sfx object is ENGINE-provided. QC Gameplay and the diagnosticien are configured to treat any `sfx.play()` call as "audio present" — they do not penalize for missing external audio files.

---

## 11. Node.js

**What it is:** A JavaScript runtime that can execute JavaScript outside of a browser, from the command line.

**What it does in this project:**
Node.js is used exclusively for one purpose: syntax-checking the generated JavaScript before it goes into the browser. `node --check file.js` parses the JS and returns exact syntax error messages with line numbers — much faster and more precise than trying to catch JS syntax errors in Playwright.

**Where it appears:**
- `js_syntax_checker.py::check_syntax(code)`:
  - Writes the JS to a temp file
  - Runs `subprocess.run(["node", "--check", tmpfile])`
  - Parses the error output to extract line number and message
  - Returns `(is_valid: bool, errors: list[str])`
- `js_syntax_checker.py::fix_exact_syntax_error()`: uses the exact line number from `node --check` to apply a targeted fix (add missing `}`, `;`, or `)` at the exact reported line)
- Called in `coordinateur.py` before and after every patch

**How it connects to the rest:**
Node.js is the first gate before Playwright. If `node --check` fails, there's no point running Playwright — the browser would just throw a parse error. The syntax check also triggers `fix_exact_syntax_error()` which can auto-repair simple errors without an LLM call.

---

## 12. Threading / concurrent.futures

**What it is:** Python's standard library modules for running code in parallel threads.

**What it does in this project:**
Two different uses:

1. **Parallel agent execution**: Phase 4's 5 QC agents (technique, gameplay, visual, execution, playtester) all run simultaneously using `ThreadPoolExecutor`. This reduces Phase 4 from ~5 minutes to ~1 minute.

2. **Concurrent generation sessions**: Flask uses daemon threads so multiple users can generate games at the same time without blocking each other. Each session gets its own `queue.Queue` via `threading.local()`.

**Where it appears:**
- `coordinateur.py::_parallel(tasks, max_workers=4)` (line ~265): `ThreadPoolExecutor` + `as_completed()` for Phase 4
- `app.py`: `threading.Thread(target=run_pipeline, daemon=True)` for each generation request
- `logger.py`: `threading.local()` for per-thread SSE queue
- `config.py`: `threading.Lock()` for API key rotation (`_key_lock`, `_paid_key_lock`)

**How it connects to the rest:**
The `threading.local()` pattern in `logger.py` is what makes the SSE streaming work correctly under concurrent load — each generation thread writes to its own isolated event queue, which Flask reads on the HTTP request thread.

---

## 13. httpx

**What it is:** A modern Python HTTP client library with support for async and custom timeouts.

**What it does in this project:**
Used only to configure custom timeout settings for the Gemini SDK's underlying HTTP client. The default Gemini SDK timeout is too short for long generation calls (which can take 60-90 seconds).

**Where it appears:**
- `config.py` (lines ~24-29):
  ```python
  import httpx as _httpx
  _http_timeout = _httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
  # Passed to genai.Client(http_options=types.HttpOptions(httpxClient=...))
  ```

**How it connects to the rest:**
Transparent — the Gemini SDK uses it internally. Without this, long game generation calls (the LLM taking 60+ seconds to generate 30KB of HTML/JS) would time out.

---

## 14. python-dotenv

**What it is:** A library that loads environment variables from a `.env` file into `os.environ`.

**What it does in this project:**
All API keys (`GEMINI_API_KEY`, `GEMINI_API_PAID_KEY`, `ANTHROPIC_API_KEY`) and configuration values are stored in a `.env` file and loaded at startup. This keeps secrets out of the code.

**Where it appears:**
- `config.py` (top of file): `from dotenv import load_dotenv; load_dotenv()`
- `.env` (not committed to git): contains all API keys
- Values read via `os.getenv("GEMINI_API_KEY")`, `os.getenv("GEMINI_API_KEY_1")`, etc.

**How it connects to the rest:**
It runs once at import time. Everything else just reads `os.getenv()` — they don't know or care about dotenv.

---

## 15. sentence-transformers (optional)

**What it is:** A Python library for generating text embeddings (dense vector representations of text) using pre-trained transformer models.

**What it does in this project:**
Used by ChromaDB to convert game code snippets into embedding vectors for similarity search. If not installed, ChromaDB falls back to its own default embedding function.

**Where it appears:**
- `rag.py`: ChromaDB is initialized with `embedding_functions.SentenceTransformerEmbeddingFunction()` if `sentence-transformers` is installed, otherwise `embedding_functions.DefaultEmbeddingFunction()`
- The fallback is silent — the pipeline works either way

**How it connects to the rest:**
Better embeddings = more accurate RAG retrieval = more relevant past-game patterns injected into generation prompts. The difference is noticeable for niche genres (e.g. "bullet hell 3D" finds closer matches with a real embedding model).

---

## 16. How everything connects

```
USER PROMPT (browser)
        │
        ▼ POST /api/generate (Flask)
COORDINATEUR.run()  ←──────────────── ChromaDB (past patterns retrieved)
        │
        ├─ Phase 1: Gemini (free) ── classifies genre, enriches prompt
        ├─ Phase 2: Gemini (free, parallel) ── GDD, UX, levels, tech specs
        │           + Claude ── game mechanics formulas
        │
        ├─ Phase 3: Gemini (PAID) ── generates HTML5 game
        │           ├─ Template ENGINE (Canvas 2D or Three.js) pre-wired
        │           ├─ LLM fills [FILL] zones only
        │           ├─ Node.js ── syntax check
        │           └─ Playwright ── preflight crash check
        │
        ├─ Phase 4: (5 agents in parallel via ThreadPoolExecutor)
        │           ├─ Gemini × 4 (QC agents: technique, gameplay, visual, playtester)
        │           └─ Playwright ── real browser test (execution score)
        │
        ├─ Phase 5: Gemini (PAID) ── patch failures
        │           └─ Node.js ── verify patch syntax
        │
        └─ Save: HTML + JSON + ChromaDB (if score ≥ 7.5)

BROWSER ←──────────────────────────── SSE stream (logger → queue → Flask)
         receives live events throughout all phases
```

**The critical path:** Gemini generates → Node.js validates syntax → Playwright runs in browser → score determines if we patch or save.

**The learning loop:** Game approved (≥7.5) → saved to ChromaDB → retrieved next run → better generation.

---

---

## 17. Node.js in context

Already covered in section 11. Key interview point: Node.js is used **only as a static analysis tool** — it never runs any game code in production. The pipeline calls `node --check file.js` which parses JavaScript syntax without executing it. This gives exact line numbers and error messages faster than any Python-based JS parser, and is more reliable than Playwright for catching parse errors before runtime.

---

*Last updated: 2026-05-25*

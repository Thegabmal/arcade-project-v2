# Arcade AI — Autonomous HTML5 Game Generation Pipeline

> Type a prompt. Get a fully playable HTML5 game in under 10 minutes.

**Best score: 8.4/10** &nbsp;|&nbsp; **23 specialized agents** &nbsp;|&nbsp; **5-phase ReAct pipeline** &nbsp;|&nbsp; **Gemini 2.5-Flash + Claude Sonnet**

---

## What It Does

This pipeline turns a natural language prompt into a complete, standalone HTML5 arcade game — no human in the loop, no build step, no dependencies. The output is a single self-contained HTML file, playable directly in any browser. The system orchestrates 23 AI agents across 5 phases: it designs the game, generates the code, evaluates it against a scientific benchmark grounded in Flow Theory and Self-Determination Theory, and iteratively patches the result until the score meets the approval threshold — or until it determines that further iteration won't help. The core technical innovation is a template engine that pre-wires all boilerplate (game loop, input handling, physics, meta-progression) into locked ENGINE sections, leaving the LLM to fill only genre-specific creative logic — reducing hallucinations, guaranteeing the game runs, and cutting token usage by approximately 4× compared to single-shot generation.

```bash
python coordinateur.py "a bullet-hell space shooter with shield mechanics and a final boss"
# → jeux_sauvegardes/galactic_fury_20260425.html  (score: 8.4/10, approved)
```

---

## Architecture — 5-Phase ReAct Pipeline

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — Intelligence & Enrichment                                │
│                                                                     │
│  Moderator/Classifier ──► validates prompt, detects genre & 2D/3D  │
│  Genre Intelligence   ──► trends, reference games, known pitfalls  │
│  Enricher             ──► synthesizes into a full GenreProfile      │
│  Code Architect       ──► module decomposition (3D games only)      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  GenreProfile
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — Game Design   (agents run in parallel)                   │
│                                                                     │
│  Game Designer  ──► GDD: title, systems, progression               │
│  Tech Architect ──► Canvas 2D vs Three.js routing                  │
│  UX Designer    ──► controls, HUD, game feel guidelines            │
│  Game Logics    ──► concrete mechanics & numeric balance (Claude)   │
│  Level Designer ──► level structure, difficulty curve              │
│  Narrator       ──► story & characters (narrative games only)      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  ConceptionContext
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3 — Code Generation                                          │
│                                                                     │
│  Template route (primary) ──► ENGINE pre-wired, LLM fills [FILL:]  │
│     2D: Canvas 2D ENGINE + genre-specific creative logic            │
│     3D: Three.js ENGINE + genre-specific creative logic             │
│  Layered route (fallback) ──► 8-layer generation for 2D            │
│  Modular route (3D only)  ──► architect → modules → assembler      │
│                                                                     │
│  JS Linter ──► static analysis, catches LLM hallucination patterns │
│  Preflight ──► Playwright headless crash check before eval loop     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  Complete HTML5 game (~20–60 KB)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4 — Multi-Dimensional Evaluation   (5 agents in parallel)   │
│                                                                     │
│  QC Technical  [20%] ──► code quality, error handling, patterns    │
│  QC Gameplay   [25%] ──► mechanics depth, balance, anti-patterns   │
│  QC Visual     [15%] ──► coherence, animations, polish             │
│  Executor      [20%] ──► headless browser test (Playwright)        │
│  Playtester    [15%] ──► fun factor, engagement, replayability     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  EvaluationBundle + global score
                                │
                   score ≥ 8.5 ─┴─► save & exit (early exit)
                                │
                   score < 8.5  ▼  (up to 4 iterations)
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 5 — Iterative Patching                                       │
│                                                                     │
│  Auto-Fixer    ──► 40+ deterministic rule-based fixes  (~35%)      │
│  Pre-Patcher   ──► lightweight LLM quick fixes (critical issues)   │
│  Diagnostician ──► root cause analysis, priority fix plan          │
│  Patcher       ──► targeted LLM surgery with rollback guard        │
│                    └─► loops back to Phase 4                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SUPPORT — Finalization                                             │
│                                                                     │
│  Verdict Agent   ──► neutral benchmark comparison (genre standard) │
│  Save Agent      ──► HTML + JSON metadata + ChromaDB RAG           │
│  Auto-Learner    ──► extract & store patterns (score ≥ 8.0)        │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
              jeux_sauvegardes/<game-title>.html   ✓ playable
```

---

## Core Innovation — Template ENGINE + [FILL] Architecture

The central engineering challenge with LLM-generated game code is **hallucination**: the model invents function names, references undefined variables, or generates syntactically valid code that crashes at runtime. Single-shot generation approaches (one big prompt → full game) produce a 20–40% runtime failure rate before any fixes.

This pipeline solves it with a **crash-proof template architecture**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  TEMPLATE = ENGINE (locked) + [FILL:] zones (LLM-editable)         │
│                                                                     │
│  // ═══ ENGINE — DO NOT MODIFY ═══                                  │
│  const canvas = document.getElementById('gameCanvas');              │
│  const ctx = canvas.getContext('2d');                               │
│  // ... 300–600 lines of pre-wired boilerplate ...                  │
│  // Game loop, input handling, physics helpers, meta-progression,   │
│  // WebAudio SFX engine, particle system, localStorage saves        │
│  // ═══ END ENGINE ═══                                              │
│                                                                     │
│  // [FILL: EntityDefinitions]                                       │
│  // LLM fills: enemy types, player stats, item definitions          │
│                                                                     │
│  // [FILL: CoreGameLogic]                                           │
│  // LLM fills: spawn logic, collision callbacks, level progression  │
│                                                                     │
│  // [FILL: RenderLoop]                                              │
│  // LLM fills: drawing code, visual effects, HUD elements           │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this works:**
- The LLM generates **only creative logic** — not infrastructure
- ENGINE variables (`canvas`, `ctx`, `Keys`, `Particles`, `sfx`, etc.) are guaranteed to exist
- All [FILL:] zones are validated post-fill: unfilled markers are detected and flagged
- The patcher respects ENGINE boundaries — it cannot accidentally break working infrastructure
- **~4× fewer tokens generated** compared to single-shot approaches, with higher quality and lower cost

**15 templates** cover the full genre matrix:
- 10 Canvas 2D templates: Platformer, Shoot-em-up, Match-3, Runner, Breakout, Tower Defense, Dungeon Crawler, Roguelite, RPG/Narrative, Visual Novel
- 5 Three.js templates: FPS Shooter, 3D Platformer, Space Shooter, Racing, Tower Defense 3D

---

## Agent Roster

### Phase 1 — Intelligence & Enrichment

| Agent | Model | Role |
|-------|-------|------|
| Moderator/Classifier | Gemini 2.5-Flash | Validates prompt, detects genre, 2D/3D, narrative flag — single optimized call |
| Genre Intelligence | Gemini 2.5-Flash | Genre trends, reference games, known pitfalls |
| Enricher | Gemini 2.5-Flash | Synthesizes Phase 1 data into a typed `GenreProfile` |
| Code Architect | Gemini 2.5-Flash | Module decomposition for 3D games (Three.js) |

### Phase 2 — Game Design (parallel)

| Agent | Model | Role |
|-------|-------|------|
| Game Designer | Gemini 2.5-Flash | Full GDD: title, systems, characters, progression |
| Tech Architect | Gemini 2.5-Flash | Canvas 2D vs Three.js decision + tech constraints |
| UX Designer | Gemini 2.5-Flash | Controls, HUD layout, game feel, accessibility |
| **Game Logics** | **Claude Sonnet 4.6** | Concrete mechanics formulas, numeric balancing, edge cases |
| Level Designer | Gemini 2.5-Flash | Level structure, difficulty scaling, pacing |
| Narrator | Gemini 2.5-Flash | Story, quests, dialogue (narrative games only) |

### Phase 3 — Code Generation

| Agent | Model | Role |
|-------|-------|------|
| Template Engine (2D) | Gemini 2.5-Flash | Fills [FILL:] zones in Canvas 2D templates |
| Template Engine (3D) | Gemini 2.5-Flash | Fills [FILL:] zones in Three.js templates |
| 8-Layer Generator | Gemini 2.5-Flash (paid) | Fallback: scaffold → state → logic → rendering → polish |
| Module Creator (3D) | Gemini 2.5-Flash (paid) | Modular Three.js generation per architectural module |
| Assembler | deterministic | Combines 3D modules into final game (no LLM call) |
| JS Linter | Gemini 2.5-Flash | Detects runtime error patterns before evaluation |
| Pre-Patcher | Gemini 2.5-Flash | Lightweight quick fixes (syntax, undefined vars) |

### Phase 4 — Evaluation (parallel)

| Agent | Model | Weight | Criteria |
|-------|-------|--------|----------|
| QC Technical | Gemini 2.5-Flash | 20% | Code architecture, patterns, performance, error handling |
| QC Gameplay | Gemini 2.5-Flash | 25% | Core loop depth, mechanics balance, anti-pattern detection |
| QC Visual | Gemini 2.5-Flash | 15% | Visual coherence, animation quality, readability |
| Executor | Playwright | 20% | Headless browser test — does it actually run? |
| Playtester | Gemini 2.5-Flash | 15% | Simulated player session — fun, engagement, replayability |
| Verdict | Gemini 2.5-Flash | 2% | Genre benchmark comparison |

### Phase 5 — Patching & Iteration

| Agent | Model | Role |
|-------|-------|------|
| Auto-Fixer | Rules engine | 40+ deterministic fixes: missing vars, scoping, event listeners |
| Pre-Patcher | Gemini 2.5-Flash | Lightweight syntax + critical issue fixes |
| Diagnostician | Gemini 2.5-Flash (paid) | Root cause analysis, priority fix plan |
| Patcher | Gemini 2.5-Flash (paid) | Targeted code surgery with syntax validation & rollback |

### Support Agents

| Agent | Model | Role |
|-------|-------|------|
| Save | I/O | Writes HTML + JSON metadata + log, stores patterns in ChromaDB |
| Auto-Learner | analysis | Extracts reusable patterns from games scoring ≥ 8.0 |

---

## Benchmark Methodology — Flow Theory & SDT

The evaluation system is grounded in two established frameworks from game psychology.

### Flow Theory (Csikszentmihalyi, 1990)

A game is most engaging when challenge matches player skill. The **QC Gameplay agent** evaluates:
- Does difficulty scale progressively with player advancement?
- Is there a tight feedback loop — immediate visible response to every action?
- Are objectives clear and achievable within the session?
- Is the core loop sustainable over 10+ minutes without feeling repetitive?

### Self-Determination Theory (Ryan & Deci, 2000)

The **Playtester agent** simulates a human player's three fundamental psychological needs:

| SDT Dimension | In-Game Expression | Agent Criterion |
|---------------|-------------------|-----------------|
| **Autonomy** | Meaningful player choices, multiple valid strategies | Mechanics depth score |
| **Competence** | Clear skill curve, satisfying progression, rewards | Playtester engagement score |
| **Relatedness** | World coherence, narrative investment, aesthetic identity | QC Visual + Narrator output |

### Score Formula

```
Final Score =  0.25 × Gameplay
             + 0.20 × Technical
             + 0.20 × Execution   ← headless Playwright test
             + 0.15 × Visual
             + 0.15 × Fun Factor
             + 0.03 × Anti-Pattern
             + 0.02 × Benchmark
```

**Hard blocks:** if `Execution < 5.0` or `Technical < 5.5`, the global score is capped at 4.5 regardless of other dimensions — a game that doesn't run cannot be approved.

---

## Generated Game Example

**Galactic Fury** — bullet-hell space shooter, generated from:
> *"a retro space shooter with multiple enemy types, power-ups, and a screen-shaking boss fight"*

| Dimension | Score | Notes |
|-----------|-------|-------|
| Gameplay | 8.8/10 | Satisfying bullet patterns, well-paced wave escalation |
| Technical | 8.5/10 | Clean game loop, delta-time physics, localStorage hi-score |
| Execution | 9.0/10 | Playwright: canvas renders, no JS errors, input responsive |
| Visual | 8.0/10 | Neon palette, particle explosions, smooth scrolling stars |
| Fun Factor | 8.2/10 | Strong replayability, tight controls, boss creates tension |
| Anti-Pattern | 9.0/10 | No global state leaks, no infinite loops detected |
| Benchmark | 8.0/10 | Competitive with genre standards (R-Type, Galaga) |
| **Global** | **8.4/10** | **Approved — saved to library** |

Generation time: 7m 42s — 2 patch iterations.

---

## Getting Started

### Requirements

- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/apikey) (free tier works)
- Node.js (for JS syntax checking — `node --check`)
- Optional: Anthropic API key (Claude Sonnet for the Game Logics agent)

### Installation

```bash
git clone https://github.com/your-username/arcade-project-v2.git
cd arcade-project-v2

pip install -r requirements.txt
playwright install chromium
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` with your API key(s):

```env
# Required — at least one Gemini key
GEMINI_API_KEY=your_gemini_key_here

# Optional — dedicated paid key for the creator agent (faster, no daily quota)
GEMINI_PAID_KEY=your_paid_key_here

# Optional — multi-key free-tier rotation (up to 20 keys)
GEMINI_API_KEY_1=key_1
GEMINI_API_KEY_2=key_2

# Optional — Claude Sonnet for the Game Logics agent
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### Run

**Web interface (recommended):**
```bash
python app.py
# Open http://localhost:5000
```

**CLI — direct generation:**
```bash
python coordinateur.py "a top-down dungeon crawler with traps and keys"
```

The generated `.html` file is saved to `jeux_sauvegardes/` and immediately playable in any browser.

---

## Project Structure

```
arcade-project-v2/
│
├── coordinateur.py         # Main orchestrator — 5-phase ReAct pipeline (1,600 lines)
├── app.py                  # Flask web server + SSE real-time streaming
├── config.py               # API wrappers, key rotation, RPM/RPD rate limiting
├── genre_profile.py        # Core data structures (GenreProfile, EvaluationBundle, ...)
├── logger.py               # Thread-local SSE event logger
├── rag.py                  # ChromaDB vector search for pattern retrieval
├── code_validator.py       # 170+ auto-injectable variable defaults + auto-fix rules
├── js_syntax_checker.py    # Node.js-based syntax validation + targeted auto-fixes
│
├── agents/
│   ├── phase1/             # Intelligence: Moderator, Genre Intel, Enricher, Architect
│   ├── phase2/             # Design: GameDesigner, TechArchitect, UX, Logics, Level, Narrator
│   ├── phase3/             # Generation: LayerGen, TemplateEngine, Assembler, Linter, Preflight
│   ├── phase4/             # Evaluation: QC×3, Executor (Playwright), Playtester
│   ├── phase5/             # Patching: AutoFixer, PrePatcher, Diagnostician, Patcher
│   └── support/            # Finalization: Verdict, Save, AutoLearner
│
├── templates/
│   └── game_templates/
│       └── genres/         # 15 crash-proof ENGINE+[FILL:] templates (10 2D + 5 3D)
│
├── jeux_modeles/           # 25 hand-crafted reference HTML5 games (10 2D + 15 3D)
│
├── static/                 # CSS + JS for the web interface
├── templates/              # Flask HTML pages (index, viewer, history, debug)
│
├── requirements.txt
├── .env.example
├── README.md
└── STACK.md                # Interview-ready technology reference
```

---

## Reference Game Library

`jeux_modeles/` contains 25 hand-crafted standalone HTML5 games covering the full genre matrix. These are **not generated** — they are clean reference implementations written to demonstrate best practices, and are stored in ChromaDB so the pipeline retrieves real code patterns at generation time.

### 2D Games (Canvas API)

| # | File | Genre | Key patterns demonstrated |
|---|------|-------|--------------------------|
| 1 | `shoot_em_up.html` | Shoot-em-up | Wave spawning, 3-phase boss, 5 weapon types, combo ×10, screen shake |
| 2 | `platformer.html` | Platformer | Coyote time, jump buffer, double jump, dash, 4 enemy types, 5 levels |
| 3 | `rpg_narratif.html` | Narrative RPG | Smooth tile movement, turn-based combat, XP/leveling, NPC dialogue |
| 4 | `puzzle_match3.html` | Match-3 | 8×8 grid, cascade resolver, chain combos, special gems |
| 5 | `endless_runner.html` | Runner | Procedural obstacles, 3-layer parallax, speed ramp, hi-score |
| 6 | `breakout.html` | Breakout | Brick HP types, angle physics, multi-ball, 6 power-ups |
| 7 | `tower_defense.html` | Tower Defense | Grid placement, 4 tower types, synergies, wave economy |
| 8 | `visual_novel.html` | Visual Novel | Branching dialogue tree, flag tracking, 3 endings |
| 9 | `dungeon_crawler.html` | Dungeon Crawler | BSP room generation, 3 classes, 3 loot rarities, boss phases |
| 10 | `roguelite.html` | Roguelite | Run structure, meta-progression, passive synergies, permadeath |

### 3D Games (Three.js r160)

| # | File | Genre |
|---|------|-------|
| 11 | `fps_shooter_3d.html` | FPS — pointer lock, wave enemies, weapon reload, boss, shop |
| 12 | `platformer_3d.html` | 3D Platformer — TPS camera, AABB collision, moving platforms |
| 13 | `space_shooter_3d.html` | Space Shooter — mouse aim, shield regen, asteroid field |
| 14 | `racing_3d.html` | Racing — CatmullRomCurve3 track, checkpoints, AI racers |
| 15 | `tower_defense_3d.html` | Tower Defense 3D — isometric raycasting, grid placement |
| 16 | `dungeon_rpg_3d.html` | Dungeon RPG 3D — room-based exploration, turn-based combat |
| 17 | `zombie_survival_3d.html` | Zombie Survival — wave defense, stamina, crafting |
| 18 | `flight_shooter_3d.html` | Flight Shooter — free-flight physics, missile lock-on |
| 19 | `arena_fighter_3d.html` | Arena Fighter — combo system, stamina, multiple opponents |
| 20 | `puzzle_3d.html` | 3D Puzzle — physics-based object manipulation |
| 21–25 | `polypulse_arena_reference.html` + 4 variants | FPS reference implementation with all balance values documented |

---

## Current State & Roadmap

### Why This Is Published Now

This project is intentionally published before completion — and that is a deliberate architectural choice, not an unfinished product.

**The pipeline is self-improving by design.** Each generation run produces structured data — scores, issue categories, recurring bug patterns — that directly feeds back into template improvements, linter rules, and agent prompts. The current workflow is:

```
Run a game → Gap analysis → Fix template/linter/agent → Rerun → Better scores
```

This cycle has been applied to 4 genres so far (Shoot-em-up, Tower Defense, Match-3, FPS 3D), with documented improvements at each iteration:

| Genre | Before fixes | After fixes | Rules added |
|-------|-------------|-------------|-------------|
| Shoot-em-up | ~6.0/10 | ~8.0/10 | R1–R6 anti-hallucination |
| Tower Defense | 6.83/10 | ~7.5/10 | TD-1→TD-7 |
| Match-3 | 6.65/10 | ~7.5/10 | M3-1→M3-11 |
| FPS 3D | baseline | 8.4/10 | FPS-1→FPS-10 |

**The constraint is cost, not architecture.**

Reaching production-ready quality across all 15 genre templates requires hundreds of generation iterations — each costing approximately $1 in API calls (Gemini paid tier for the creator agent). The architecture is designed for exactly this: the ChromaDB RAG, the auto-learner, the gap analysis workflow, the template ENGINE system — all of it exists to make this iteration process systematic and efficient.

At student scale, running 200–300 iterations across all genres isn't financially realistic. With proper resources, it is entirely feasible and the engineering is already in place to do it.

### What's Already Complete

- 5-phase pipeline with 23 specialized agents — fully operational
- 15 crash-proof templates (10 Canvas 2D + 5 Three.js) with ENGINE+[FILL:] architecture
- 25 hand-crafted reference games seeded into ChromaDB
- Multi-dimensional evaluation benchmark (6 agents, Flow Theory + SDT)
- Iterative patching loop with 40+ deterministic auto-fix rules
- Anti-hallucination system (symbol tables, linter, auto-stub injection)
- Real-time web interface with SSE streaming
- ChromaDB RAG for learning from past successful games

### Next Steps With Proper Resources

1. **Genre completion** — apply the gap analysis cycle to the remaining 11 templates
2. **Volume runs** — 10–20 generations per genre to extract robust statistical patterns
3. **Multi-key scaling** — parallel generations using free-tier key pools
4. **Automated regression** — CI pipeline to detect score regressions when templates change
5. **Extended 3D coverage** — Bullet Hell 3D, Vehicle Combat 3D, Stealth 3D templates

---

## Key Design Decisions

**Why 5 phases instead of one big prompt?**
Each phase has a single clear responsibility, reducing hallucination and making failures debuggable. Phase 2 and Phase 4 run all their agents concurrently via `ThreadPoolExecutor`.

**Why a patching loop instead of regenerating from scratch?**
Regeneration wastes ~3 minutes of API calls on a game that is 80% correct. The Diagnostician + Patcher combo surgically fixes the specific issues identified by Phase 4, typically improving scores by 0.5–1.5 points per iteration.

**Why Playwright for evaluation?**
An LLM cannot tell if JavaScript actually runs. The Executor agent opens the game in a real headless Chromium browser, checks for JS errors, verifies the canvas renders, and simulates keyboard input. This is the most reliable quality gate in the pipeline.

**Why ChromaDB RAG?**
Every approved game (score ≥ 7.5) is stored as vector embeddings. When generating a new game in the same genre, the pipeline retrieves the most relevant past patterns — mechanics that worked, visual approaches that scored well, common bugs to avoid. This is the core mechanism by which the pipeline improves over time.

---

## Anti-Hallucination System

LLMs writing game code tend to "invent" variable names or function signatures that don't exist. Three independent layers address this:

1. **Symbol Table** (Phase 3 pre-generation): A manifest of all ENGINE variables, helper functions, and callback signatures is injected into the creator's context — the LLM knows exactly what exists.
2. **JS Linter** (post Phase 3): Statically detects undefined references, missing function definitions, and scope leaks before any evaluation.
3. **A2 Auto-Stub Injection** (Phase 4→5): Any variable named in a Playwright `"X is not defined"` runtime error is automatically injected as `var X = safeDefault;` — no LLM call needed, resolves ~35% of runtime failures instantly.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM — primary (20–40 calls/game) | Google Gemini 2.5-Flash |
| LLM — mechanics design | Anthropic Claude Sonnet 4.6 |
| Browser testing & evaluation | Playwright (headless Chromium) |
| JS syntax validation | Node.js (`node --check`) |
| Vector memory (RAG) | ChromaDB with cosine similarity |
| Web interface | Flask + Server-Sent Events |
| Game runtime — 2D | HTML5 Canvas 2D API |
| Game runtime — 3D | Three.js r160 via CDN |
| Language | Python 3.10+ |

See [STACK.md](STACK.md) for a detailed breakdown of every technology — what it does, where it appears in the code, and how it connects to the rest of the pipeline.

---

*Built with Gemini 2.5-Flash + Claude Sonnet 4.6 · Python 3.10+ · Flask · Playwright · ChromaDB · Three.js*

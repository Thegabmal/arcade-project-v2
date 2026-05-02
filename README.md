# Arcade AI — Multi-Agent HTML5 Game Generation Pipeline

> Transform a natural language prompt into a fully playable HTML5 game in under 10 minutes.

**Best score achieved: 8.4/10** &nbsp;|&nbsp; **20+ specialized agents** &nbsp;|&nbsp; **5-phase ReAct pipeline** &nbsp;|&nbsp; **Gemini 2.5-Flash + Claude Sonnet**

---

## What It Does

You type a prompt. The pipeline designs, codes, evaluates, and iteratively patches a complete standalone HTML5 arcade game — no human in the loop.

```bash
python coordinateur.py "a bullet-hell space shooter with shield mechanics and a final boss"
# → jeux_sauvegardes/galactic_fury_20260425.html  (score: 8.4/10)
```

The output is a **single self-contained HTML file** playable directly in any browser — no server, no build step, no dependencies.

---

## Architecture — 5-Phase ReAct Pipeline

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — Intelligence & Enrichment                                │
│                                                                     │
│  Moderator/Classifier ──► validates prompt, detects genre & style   │
│  Genre Intelligence   ──► trends, reference games, known pitfalls   │
│  Enricher             ──► builds a full GenreProfile object          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  GenreProfile
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — Game Design   (6 agents in parallel)                     │
│                                                                     │
│  Game Designer  ──► GDD: title, systems, progression               │
│  Tech Architect ──► Canvas 2D vs Three.js routing                   │
│  UX Designer    ──► controls, HUD, game feel guidelines             │
│  Game Logics    ──► detailed mechanics (Claude Sonnet API)           │
│  Level Designer ──► level structure, difficulty curve               │
│  Narrator       ──► story & characters (optional, if narrative)     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  ConceptionContext
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3 — Code Generation                                          │
│                                                                     │
│  2D route ──► 5-layer generator (structure → logic → rendering)     │
│  3D route ──► modular Three.js (architect → modules → assembler)    │
│  JS Linter + Pre-Patcher ──► syntax validation before evaluation    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  Complete HTML5 game (~20–40 KB)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4 — Multi-Dimensional Evaluation   (5 agents in parallel)    │
│                                                                     │
│  QC Technical  [20%] ──► code quality, error handling, patterns     │
│  QC Gameplay   [25%] ──► mechanics depth, balance, anti-patterns    │
│  QC Visual     [15%] ──► coherence, animations, polish              │
│  Executor      [20%] ──► headless browser test (Playwright)         │
│  Playtester    [15%] ──► fun factor, engagement, replayability      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  EvaluationBundle + global score
                                │
                   score ≥ 8.0 ─┴─► save & exit (early exit)
                                │
                   score < 8.0  ▼  (up to 3 iterations)
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 5 — Iterative Patching                                       │
│                                                                     │
│  Auto-Fixer    ──► deterministic rule-based fixes  (no LLM, ~35%)  │
│  Diagnostician ──► analyze issues, build priority fix plan          │
│  Patcher       ──► targeted LLM corrections with rollback guard     │
│                    └─► loops back to Phase 4                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SUPPORT — Finalization                                             │
│                                                                     │
│  Verdict Agent   ──► neutral benchmark comparison                   │
│  Save Agent      ──► HTML + JSON metadata + ChromaDB RAG            │
│  Auto-Learner    ──► extract & memorize patterns (score ≥ 8.0)      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
              saved_games/<game-title>.html   ✓ playable
```

---

## Agent Roster

### Phase 1 — Intelligence & Enrichment

| Agent | Model | Role |
|-------|-------|------|
| Moderator/Classifier | Gemini Flash | Validates prompt, detects genre, 2D/3D, narrative flag |
| Genre Intelligence | Gemini Flash | Scrapes genre trends, reference games, common pitfalls |
| Enricher | Gemini Flash | Synthesizes all Phase 1 data into a `GenreProfile` |
| Code Architect | Gemini Flash | Module decomposition for 3D games (Three.js) |

### Phase 2 — Game Design (parallel)

| Agent | Model | Role |
|-------|-------|------|
| Game Designer | Gemini Flash | Full GDD: title, systems, characters, progression |
| Tech Architect | Gemini Flash | Canvas 2D vs Three.js decision + tech constraints |
| UX Designer | Gemini Flash | Controls, HUD layout, game feel, accessibility |
| **Game Logics** | **Claude Sonnet** | Detailed mechanics, edge cases, numeric balancing |
| Level Designer | Gemini Flash | Level structure, difficulty scaling, pacing |
| Narrator | Gemini Flash | Story, quests, dialogue (narrative games only) |

### Phase 3 — Code Generation

| Agent | Model | Role |
|-------|-------|------|
| 2D Creator (5-layer) | Gemini Flash (paid) | Layered generation: scaffold → state → logic → rendering → polish |
| 3D Creator | Gemini Flash (paid) | Modular Three.js generation per architectural module |
| Module Tester | Gemini Flash | Tests each 3D module independently before assembly |
| Assembler | Gemini Flash | Combines tested 3D modules into a final game |
| JS Linter | Gemini Flash | Detects runtime errors pre-evaluation |
| Pre-Patcher | Gemini Flash | Lightweight quick fixes (syntax, undefined vars) |

### Phase 4 — Evaluation (parallel)

| Agent | Model | Weight | Criteria |
|-------|-------|--------|----------|
| QC Technical | Gemini Flash | 20% | Code architecture, patterns, performance, error handling |
| QC Gameplay | Gemini Flash | 25% | Core loop depth, mechanics balance, anti-pattern detection |
| QC Visual | Gemini Flash | 15% | Visual coherence, animation quality, readability |
| Executor | Playwright | 20% | Headless browser test — does it actually run? |
| Playtester | Gemini Flash | 15% | Simulated player session — fun, engagement, replayability |

### Phase 5 — Patching & Iteration

| Agent | Model | Role |
|-------|-------|------|
| Auto-Fixer | Rules engine | Deterministic fixes: missing vars, scoping, event listeners |
| Diagnostician | Gemini Flash (paid) | Root cause analysis, priority fix plan |
| Patcher | Gemini Flash (paid) | Targeted code surgery with syntax validation & rollback |

### Support Agents

| Agent | Model | Role |
|-------|-------|------|
| Verdict | Gemini Flash | Neutral benchmark comparison vs genre standards |
| Save | I/O | Writes HTML + JSON metadata + log, stores in ChromaDB |
| Auto-Learner | Analysis | Extracts reusable patterns from games scoring ≥ 8.0 |

---

## Benchmark Methodology — Flow Theory & SDT

The evaluation system is grounded in two established frameworks from game psychology.

### Flow Theory (Csikszentmihalyi, 1990)

A game is most engaging when challenge matches player skill — too easy produces boredom, too hard produces anxiety. The **QC Gameplay agent** specifically evaluates:

- Does difficulty scale progressively with player advancement?
- Is there a tight feedback loop — immediate visible response to every action?
- Are objectives clear and achievable within the session?
- Is the core loop sustainable over 10+ minutes without feeling repetitive?

### Self-Determination Theory (Ryan & Deci, 2000)

The **Playtester agent** simulates a human player's three fundamental psychological needs:

| SDT Dimension | In-Game Expression | Agent Criterion |
|---------------|-------------------|-----------------|
| **Autonomy** | Meaningful player choices, multiple strategies | Mechanics depth score |
| **Competence** | Clear skill curve, satisfying progression, rewards | Playtester engagement score |
| **Relatedness** | World coherence, narrative investment, aesthetic identity | QC Visual + Narrator output |

### Score Formula

```
Final Score =  0.25 × Gameplay
             + 0.20 × Technical
             + 0.20 × Execution   ← headless browser test
             + 0.15 × Visual
             + 0.15 × Fun Factor
             + 0.03 × Anti-Pattern
             + 0.02 × Benchmark
```

Hard blocks: if `Execution < 5.0` or `Technical < 5.5`, the score is capped at 4.5 regardless of other dimensions (a game that doesn't run cannot be approved).

---

## Generated Game Example

**Galactic Fury** — bullet-hell space shooter, generated from the prompt:
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

Edit `.env` and add your API key(s):

```env
# Required — at least one Gemini key
GEMINI_API_KEY=your_gemini_key_here

# Optional — for multiple free-tier key rotation
GEMINI_API_KEY_1=key_1
GEMINI_API_KEY_2=key_2

# Optional — dedicated paid key for the creator agent (faster generation)
GEMINI_PAID_KEY=your_paid_key_here

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

The generated `.html` file is saved to `saved_games/` and immediately playable in any browser.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM — primary | Google Gemini 2.5-Flash (free + paid tiers) |
| LLM — mechanics | Anthropic Claude Sonnet 4.6 |
| Browser testing | Playwright (headless Chromium) |
| Vector memory | ChromaDB (semantic pattern retrieval) |
| Web interface | Flask + Server-Sent Events (real-time streaming) |
| Game runtime | HTML5 Canvas 2D + Three.js r128 (3D) |
| Language | Python 3.10+ |

---

## Project Structure

```
arcade-project-v2/
│
├── coordinateur.py         # Main orchestrator — 5-phase ReAct pipeline
├── app.py                  # Flask web server + SSE real-time streaming
├── config.py               # API config, key rotation, rate limiting
├── genre_profile.py        # Core data structures (GenreProfile, EvaluationBundle...)
├── logger.py               # Thread-local SSE event logger
├── rag.py                  # ChromaDB vector search for pattern retrieval
├── memory.py               # JSON-based persistent memory (patterns, errors)
│
├── agents/
│   ├── phase1/             # Intelligence: Moderator, Genre Intel, Enricher
│   ├── phase2/             # Design: GameDesigner, TechArchitect, UX, Logics, Level, Narrator
│   ├── phase3/             # Generation: Creator (5-layer), Assembler, Linter, PrePatcher
│   ├── phase4/             # Evaluation: QC×3, Executor (Playwright), Playtester
│   ├── phase5/             # Patching: AutoFixer, Diagnostician, Patcher
│   └── support/            # Finalization: Verdict, Save, AutoLearner
│
├── jeux_modeles/           # Reference HTML5 games injected as LLM context
│   ├── platformer.html     # 2D platformer with coyote time, enemies, power-ups
│   ├── shoot_em_up.html    # Bullet-hell shmup with boss fights and weapon combos
│   └── rpg_narratif.html   # Tile-based RPG with combat, inventory, dialogue
│
├── templates/              # Flask HTML templates (index, history, viewer)
├── static/                 # CSS + JS assets for the web interface
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## Key Design Decisions

**Why 5 separate phases instead of one big prompt?**
Each phase has a single clear responsibility. This reduces hallucination, makes failures debuggable, and allows parallel execution within phases (Phase 2 and Phase 4 run all their agents concurrently).

**Why a patching loop instead of regenerating from scratch?**
Regeneration wastes ~3 minutes of API calls on a game that's 80% correct. The Diagnostician + Patcher combo surgically fixes the specific issues identified by Phase 4, typically improving scores by 0.5–1.5 points per iteration.

**Why Playwright for evaluation?**
An LLM cannot tell if JavaScript actually runs. The Executor agent launches the game in a headless Chromium browser, checks for runtime errors, verifies the canvas renders, and simulates keyboard input. This is the most reliable quality gate in the pipeline.

**Why ChromaDB RAG?**
Successful past games are stored as vector embeddings. When generating a new game in the same genre, the creator agent retrieves the most relevant patterns — mechanics that worked, visual approaches that scored well, common bugs to avoid. Over time, the system gets measurably better at each genre.

---

## Anti-Hallucination System

A recurring challenge with LLM-generated code is that agents "invent" variable names or function signatures that don't exist in context. This pipeline addresses it with three layers:

1. **Symbol Table** (Phase 3): Before generation, a manifest of expected variable names, function signatures, and event handlers is injected into the creator's context.
2. **JS Linter** (post Phase 3): Detects undefined references before evaluation.
3. **A2 Auto-Fix** (Phase 4→5 boundary): Automatically injects `var X = defaultValue;` for any variable named in a Playwright `"X is not defined"` error — no LLM call needed, resolves ~35% of runtime failures instantly.

---

*Built with Gemini 2.5-Flash + Claude Sonnet 4.6 · Python 3.10+ · Flask · Playwright · ChromaDB*

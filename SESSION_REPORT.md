# Arcade Project v2 — Rapport de Session

> **Usage :** Ce fichier est lu en début de chaque conversation et mis à jour en fin de session.
> Il reflète l'état ACTUEL du projet après toutes les modifications apportées.

---

## Last session: 2026-05-19 (session 6) — FPS 3D gap analysis + template-aware evaluation

### What to do FIRST next session
1. Open the FPS 3D game in `needs_review/` — find the file from the last run
2. Fix it manually until it is perfectly playable (same process as TD and M3 gap analyses)
3. Document every bug with root cause → extract FPS-specific pipeline rules
4. Commit rules to linter / auto-fix / template as appropriate
5. After rules are extracted → re-run FPS 3D to validate, then continue genre cycle (3D Platformer, Bullet Hell 3D)

### All fixes applied this session

#### Template-aware evaluation (Phase 4-5 agents)
| Item | File | Fix |
|------|------|-----|
| `est_template` flag | `genre_profile.py` | New `est_template: bool = False` field, set True after successful `run_from_template`/`run_from_template_3d` |
| `est_template` propagation | `coordinateur.py` | Set `genre_profile.est_template = True` on template success paths |
| QC Technique template criteria | `agents/phase4/agent_qc_technique.py` | `CRITERES_BLOCKING_TEMPLATE_2D` + `ENGINE_CONTEXT_TEMPLATE` injected when `est_template=True and not est_3d` — removes 4 false-positive BLOCKING checks |
| QC Gameplay ENGINE credit | `agents/phase4/agent_qc_gameplay.py` | `_engine_features_note` injected when `est_template=True` — credits spawnParticles, sfx.play, triggerShake, etc. as present |
| Diagnosticien devPatch false positive | `agents/phase5/agent_diagnosticien.py` | Strip ENGINE's `window.__devPatch` def before eval check |
| Diagnosticien spawnFloatText false positive | `agents/phase5/agent_diagnosticien.py` | Add `spawnPopup` to spawnFloatText detection regex |
| Diagnosticien DOMContentLoaded rule | `agents/phase5/agent_diagnosticien.py` | `_template_guard` block added to prompt — prevents wrong DOMContentLoaded/initGame() recommendations |

#### M3 scope contracts (6 uncovered bugs)
| Item | File | Fix |
|------|------|-----|
| 6-rule SCOPE CONTRACTS block | `templates/game_templates/genres/puzzle_match3.html` | Prevents gem/matches/r-c/end/nr-nc/dr silent failures on next M3 run |

#### FPS 3D gap analysis — 2 structural bugs fixed
| Item | File | Fix |
|------|------|-----|
| FPS-2: ENGINE marker mismatch | `templates/game_templates/genres/fps_shooter_3d.html` | Changed 3-line header to `// ═══ ENGINE — DO NOT MODIFY ═══` + `// ═══ END ENGINE ═══` — matches what `_validate_template_integrity_3d` expects |
| FPS-1: `core` namespace collision | `js_syntax_checker.py` | `fix_undefined_runtime_vars` now skips injection for variables with existing `let`/`const` declaration anywhere in script — prevents `var core` + `let core` SyntaxError |

#### Other
| Item | Fix |
|------|-----|
| RAG seeded | 25 model games seeded into ChromaDB via `seed_rag_models.py` |
| `STACK.md` created | Full technology reference (15 techs, connectivity diagram) |

### FPS-3 still open
Cross-module weapon/reload/wave state coordination in modular fallback path — not fixed yet.
If FPS template path now works (FPS-2 fixed), this should not be needed for most runs.

---

## Last session: 2026-05-17 (session 5) — Zero défaut plan COMPLETE (all 4 sessions A-D)

### What to do FIRST next session
1. Start Flask: `python app.py`
2. Run 8-genre test sequence — all 12 zero-défaut fixes are live
3. Expected: save rate moves from ~10% toward 60-70%; no more "4.9 forever" stagnation

### All fixes applied this session (commit a56a4ba — Session D)

| Item | File | Fix |
|------|------|-----|
| 1.4 `__devPatch` contradiction | `agent_createur.py` | RULE N°7 updated: ENGINE's `__devPatch` must not be removed; LLM's [FILL] must never add eval/new Function/`__devPatch(...)` calls |
| 3.3 ENGINE-aware extraction | `agent_patcher.py` | New `_engine_end_line()` helper; `_extract_function_window` now clamps `fn_start` to after ENGINE block — patcher can never rewrite canvas/ctx/W/H |

---

## Last session: 2026-05-17 (session 4) — Zero défaut Sessions A+B+C complete

### What to do FIRST next session
1. Start Flask: `python app.py`
2. Run 8-genre test sequence — pipeline has 10 major fixes across Sessions A-C
3. Watch for: pre-flight catching startup errors, E1-tardif triggering on stagnating games, linter catching more undefined vars

### All fixes applied this session (commits a30bd31 + c87a3bf + 0ef5e4c)

**Session A** — startup crash prevention
| Item | File | Fix |
|------|------|-----|
| 1.2 Self-review rule | `agent_createur.py` | RULE 22: 4-point checklist (double RAF, undefined vars, gamestates, missing functions) |
| 2.3 A2 smart stubs | `js_syntax_checker.py` | scale/radius/speed default to 1/10/1 — never 0 for rendering vars |
| 3.1 Runtime errors → patcher | `coordinateur.py` | Playwright JS errors bypass Diagnosticien, go directly to patcher |
| 2.1 Pre-flight check | `preflight_check.py` (NEW) | Phase 3.5: Playwright run before eval loop, up to 2 LLM fix rounds |

**Session B** — context and rescue
| Item | File | Fix |
|------|------|-----|
| 1.1 Scope contracts | 6 templates | `[FILL]` sections now have MODULE-LEVEL vs ENGINE ownership comments |
| 3.2 Full function extraction | `agent_patcher.py` | `_extract_function_window`: finds enclosing function, falls back to ±125-line window |
| 4.1 needs_review folder | `coordinateur.py` | Saves games with score≥5.0 + exec≥5.0 to `needs_review/` instead of dropping |

**Session C** — quality and stagnation recovery
| Item | File | Fix |
|------|------|-----|
| 2.2 Linter full-file | `agent_js_linter.py` | `_quick_checks` runs on FULL script (was 28K sample); LLM analysis stays 28K |
| 4.2 E1-tardif | `coordinateur.py` | Stagnation + exec<6.0 → full regen instead of stop; resets stagnation counter |
| 1.3 Few-shot examples | `agent_createur.py` | ~80-line correct shooter added at end of SYSTEM_2D as positive reference |

---

## Last session: 2026-05-17 (session 3) — Full pipeline audit + 14 critical/high fixes

### What to do FIRST next session
1. Start Flask: `python app.py`
2. Run 8 autonomous games covering all genre types (platformer, puzzle, runner, dungeon 3D, RPG, roguelite, shoot-em-up, breakout)
3. Monitor for regressions — all fixes below should prevent the most common failures

### All fixes applied this session (commits 455b0f0 + ae59fa6)

| Bug | File | Fix |
|-----|------|-----|
| `THREE` not in browser globals → ESLint injects `var THREE=0` → all 3D games crash | `js_syntax_checker.py` | Added THREE to `_BROWSER_AND_TEMPLATE_GLOBALS` |
| ctx alias TDZ crash: `var cx=ctx` injected before `const ctx` → ReferenceError | `js_syntax_checker.py` | Guard: `(typeof ctx!=="undefined"?ctx:null)` |
| `_CTX_METHODS` too broad: `scale/rotate/translate` matched physics/3D code → false positives | `js_syntax_checker.py` | Removed non-canvas-exclusive methods from detection |
| Simple syntax errors (missing `}`, `;`) cause patcher to rewrite 200 lines → new bugs | `js_syntax_checker.py` | Added `fix_exact_syntax_error`: reads exact `node --check` output, applies minimal targeted fix (brace count / line removal / semicolon insert), verifies with another `node --check` before accepting; loops 5× in `fix_all_auto` |
| ENGINE utility functions (lerp, createPool, triggerShake…) flagged as orphans by qc_technique | `agent_qc_technique.py` | Added all ENGINE helpers + state-machine callbacks to orphan-function ignore list |
| Brace-balance check killed Cas 2 (surgical) patch path | `agent_patcher.py` | Moved check inside Cas 1 block only |
| Declarations context only shown for script-only patches (not full HTML) | `agent_patcher.py` | Always compute and include `decls_context` |
| `_HTML_TEMPLATE_GLOBALS` included 28 names not in `_HTML_TEMPLATE` wrapper | `_layer_gen.py` | Split into `_LAYER_GEN_GLOBALS` (8 names) + full list |
| `[FILL]` validation missed malformed tokens like `[FILL]` or `[FILL ...]` | `_layer_gen.py` | Changed to `re.findall(r'\[FILL[:\]]?', html)` |
| 3D CDN validation checked `'three.min.js'` — accepted wrong cdnjs URL | `_layer_gen.py` | Now checks full jsdelivr URL |
| 3D Playwright init 5s → black screen on WebGL + shader compile | `agent_executeur.py` | 3D init delay: 5s → 7s |
| Three.js CDN inconsistent: 5 files still using cdnjs URL | all 3D agents | All → `cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js` |
| RAG stored broken games (no score threshold) → pollutes future retrieval | `rag.py` | Reject patterns with score < 7.5 |
| Chest in dungeon_rpg_3d spawns at (0,0,0) → instant auto-loot on hero spawn | `dungeon_rpg_3d.html` | Random position 3–6 units from origin |

### Audit source
5 parallel audit agents covered the full pipeline (90+ bugs found total).
Ultrareview (master~5) confirmed 3 bugs with detailed proof.
Fixes prioritized by: severity × frequency × ease of fix.

### Remaining audit items (not yet fixed — lower priority)
- agent_patcher: _find_keyword() may extract wrong function (anchors on first occurrence)
- agent_patcher: executeur called after each patch (5× overhead per iteration)
- agent_diagnosticien: runtime error detection heuristics too weak
- code_validator: Three.js detection missing in _fix_missing_canvas_setup

---

## Last session: 2026-05-16 (session 2) — Model game bugfixes + B2 dedup fix

### What to do FIRST next session
1. Start Flask: `python app.py`
2. Trigger autonomous run sequence (all genres): platformer, puzzle match-3, endless runner, dungeon crawler, RPG narratif, roguelite, breakout, 3D game
3. All model game bugs below are fixed — RAG re-seeded with corrected versions

### All fixes applied this session (committed b3148cd)

#### Dead enemy pool bug (roguelite, shoot-em-up, tower defense, dungeon crawler)
| File | Bug | Fix |
|------|-----|-----|
| `roguelite.html`, `roguelite_2.html` | `enemyPool.update` callback returned `true` unconditionally — dead enemies stayed active, kept shooting; room-clear `active.length===0` fired too early | Added `if(!e.alive)return false;` at start of callback; changed to `.filter(x=>x.alive).length===0` |
| `shoot_em_up.html`, `shoot_em_up_2.html` | `return e.y<H+90` didn't check `e.alive` — dead enemies visible and shooting; wave advance used `active.length===0` | `return e.alive && e.y<H+90`; wave advance uses `.filter(x=>x.alive)` |
| `tower_defense.html`, `tower_defense_2.html` | Same alive check + wave-clear issue | Same fixes |
| `dungeon_crawler.html`, `dungeon_crawler_2.html` | Room-clear `active.length===0` fires before dead enemy removed from pool | Changed to `.filter(x=>x.alive).length===0` |

#### Difficulty scaling
| File | Fix |
|------|-----|
| `rpg_narratif.html` | Malachar atk 26→18; hero potions 2→3 (fight 3 was impossible) |
| `rpg_narratif_2.html` | NEXUS atk 25→18, hp 230→190; Aegis hp 145→110, atk 19→15; Drone atk 15→12; hero potions 2→3 |
| `tower_defense.html` | Archer cost 80→60 (wave 1 now winnable with 150 start gold — can buy 2 archers) |

#### Visual novel content (was too short)
- `visual_novel.html`: Added 5 new scenes to all 3 paths
  - Common path: `pattern_depth` (extra observation between anomaly and choice)
  - Good ending: `signal_reveals` + `mira_accepts` (2 scenes before ending_good)
  - Neutral ending: `containment` (containment team scene before ending_neutral)
  - Bad ending: `regret_morning` + `signal_gone` (leave_early path was 2 scenes → 5)

#### 3D games — START button fix
- All 10 3D model games: added `onclick="startGame()"` HTML attribute on `btn-play`
- Root cause: `document.getElementById('btn-play').onclick=startGame` was set at END of script; if any JS error before that line, onclick was never set

#### B2 dedup cycle — js_syntax_checker.py
- `fix_identifier_already_declared`: now removes LLM's FIRST declaration of template globals (before ENGINE line), not ENGINE's authoritative declaration
- Added `TILE_SIZE` to `_TEMPLATE_GLOBALS` frozenset
- This fixes the platformer run cycle: `[SKIPPED] 2 redéclaration(s) — rollback` on every iteration

### State after this session
- All 25 model games are bug-free and balanced
- RAG re-seeded with corrected model games (`python seed_rag_models.py`)
- B2 dedup cycle fixed — template global redeclarations now correctly resolved
- Ready to run full autonomous genre sequence

---

## Last session: 2026-05-16 — All pipeline bugs fixed, ready to run

### What to do FIRST next session
1. Start Flask: `python app.py`
2. Trigger a run: `curl -X POST http://127.0.0.1:5000/api/generate -H "Content-Type: application/json" -d "{\"prompt\": \"a space shoot-em-up with 4 enemy types, boss waves, shield power-up and triple shot\"}"`
3. Watch the SSE stream — all bugs below are fixed and should no longer appear

### All fixes applied this session (all committed to disk, Flask NOT yet restarted)
| Bug | Status |
|-----|--------|
| `disable_thinking=True` in enrichisseur — JSON truncated at char 18600 | ✅ Fixed |
| `game_logics` crash: `name 'titre' is not defined` | ✅ Fixed |
| `game_logics[:1500]` — only 10% of content passed to template LLM | ✅ Fixed |
| 9 arbitrary truncations (`[:300]`…`[:3000]`) → `[:100_000]` | ✅ Fixed |
| game_logics now outputs JS constants block first (ENEMY_TYPES, POWERUP_TYPES, WAVE_PLAN) | ✅ Fixed |
| `<canvas>` inside `<script>` → `SyntaxError: Unexpected token '<'` | ✅ Fixed: `_strip_html_from_script_blocks()` + system prompt rule |
| 6 `[FILL:]` not replaced — LLM fills code but keeps `// [FILL:]` comment lines | ✅ Fixed: same function strips `[FILL:]` from comment lines; rule 3 updated |
| `gameLoop()/init() missing` false positive on template-route games | ✅ Fixed: `coherence_check()` now accepts `loop/initGame` (template) and `gameLoop/init` (layered) |
| Model game reference dropped into prompt without context label | ✅ Fixed: wrapped in `REFERENCE DATA STRUCTURES` label |
| Patcher 3D awareness — only had 2D engine contract | ✅ Fixed: 3D engine contract injected when `THREE.` found |

### Note on previous run (d19afda0)
Flask process (PID 37396) was using OLD cached code. All bugs still appeared.
Flask was killed. Needs restart before next run.

---

## Last session: 2026-05-15 — Pipeline truncation fixes + game_logics improvements

### What was built
Identified and fixed all arbitrary content truncations that were silently discarding pipeline data.

#### Root causes fixed
| Bug | File | Fix |
|-----|------|-----|
| `disable_thinking=False` in enrichisseur | `agent_enrichisseur.py` | → `disable_thinking=True` — JSON was cut at char 18600 (thinking tokens consumed output budget), leaving GenreProfile empty |
| `game_logics[:1500]` in both template routes | `_layer_gen.py` | Removed truncation — LLM was receiving only 10% of game_logics context |
| `titre` not in scope of `_build_sections_list()` | `agent_game_logics.py` | Added `titre: str` parameter + updated call site |
| `game_logics_entities[:2000]` L3 | `_layer_gen.py` | → `[:100_000]` |
| `game_logics_entities[:1500]` L4 | `_layer_gen.py` | → `[:100_000]` |
| `game_logics_update[:1500]` L5 | `_layer_gen.py` | → `[:100_000]` |
| `enrichment_targets[:600]` L5 | `_layer_gen.py` | → `[:100_000]` |
| `enrichment_targets[:500]` L6 | `_layer_gen.py` | → `[:100_000]` |
| `draw_code_l6[:3000]` L7 | `_layer_gen.py` | → `[:100_000]` |
| `gdd_desc[:300]` | `_layer_gen.py` | → `[:100_000]` |
| `gdd_concept[:300]` | `_layer_gen.py` | → `[:100_000]` |
| `snippets[:3000]` (memory save) | `coordinateur.py` | → `[:100_000]` |

#### game_logics improvements
- Shooter, tower defense, puzzle sections now output JS constants block FIRST (copy-paste ready: `ENEMY_TYPES`, `POWERUP_TYPES`, `WAVE_PLAN`, `TOWER_TYPES`, `GEM_TYPES`) before prose explanations
- Reduces translation work for template LLM — LLM can copy exact values into `[FILL:]` sections

#### Patcher 3D improvements
- Added 3D engine contract injected into patcher prompt when `THREE.` found in code: `scene`, `camera`, `renderer`, `clock` — prevent redeclaration
- Added 7 3D genre entries to patcher model game reference mapping

#### Template route improvements (`run_from_template`)
- RAG patterns now injected into prompt (was received but never used)
- Model game reference now fetched in template route (was only in layered route)

#### Additional fixes (same session, round 2)
| Bug | Root cause | Fix |
|-----|-----------|-----|
| `SyntaxError: Unexpected token '<'` at line 14/21 | LLM puts `<canvas id="gameCanvas"></canvas>` INSIDE the `<script>` block | `_strip_html_from_script_blocks()` strips bare HTML elements from script blocks; `_TEMPLATE_ADAPT_SYSTEM` rule 11 warns LLM not to do this |
| 6 `[FILL:]` sections not replaced | LLM fills code content but leaves `// [FILL: SectionName]` comment lines unchanged | Post-processing in `_strip_html_from_script_blocks()` strips `[FILL:]` from comment lines; rule 3 updated to explicitly mention comment lines |
| `gameLoop() manquant` / `init() manquant` false positive | `coherence_check()` only looked for `function gameLoop` / `function init`, but template uses `function loop` / `function initGame` | Updated check to accept both naming conventions; prevents pre-patcher from adding spurious `gameLoop`/`init` stubs |
| Model game reference injected without label | `_get_model_game_reference()` returned raw JS without any context in the prompt | Wrapped in `REFERENCE DATA STRUCTURES` label in `run_from_template()` |

### State after this session
- All major content truncations eliminated from the pipeline
- game_logics produces structured constants blocks ready for template fill
- Patcher is 3D-aware

---

## Last session: 2026-05-15 — All 25 model games + 5 new 3D templates complete

### What was built (continued same session)
Wrote all 5 core 3D genre templates in `templates/game_templates/genres/`. Each follows the exact same ENGINE + [FILL:] convention as the 10 existing 2D templates.

| File | Paradigm | Covers genres |
|------|----------|---------------|
| `fps_shooter_3d.html` | FPS (pointer lock, WASD) | FPS shooter, zombie survival |
| `platformer_3d.html` | TPS follow-cam, gravity+AABB | Platformer 3D, collectathon |
| `space_shooter_3d.html` | Mouse aim, no floor | Space shooter, flight shooter |
| `racing_3d.html` | CatmullRomCurve3 + car physics | Racing, circuit games |
| `tower_defense_3d.html` | Fixed isometric + raycasting | Tower defense 3D, top-down strategy |

Key design decisions:
- All templates: ENGINE handles the hard wiring (Three.js core, input, physics, meta, loop); [FILL:] sections cover creative content only
- `platformer_3d.html`: `makePlatform()` + `makeGem()` helpers exposed in FILL zone; moving platforms wired in ENGINE
- `space_shooter_3d.html`: dual-cannon `fireBullet()`, shield regen timer, star-scroll background all in ENGINE
- `racing_3d.html`: `buildTrack()` uses `TRACK_POINTS` const; AI car helper `buildAICar()` in ENGINE; checkpoint system fully wired
- `tower_defense_3d.html`: `placeTower()`, `killEnemy()`, `spawnEnemy()`, raycasting on `gridTiles[]`, tower fire — all ENGINE; LLM fills grid layout, path, tower types, enemy types

### State after this session
- **25/25 model games complete** — all in `jeux_modeles/`
- **5/5 new 3D templates complete** — in `templates/game_templates/genres/`
- Total templates: 10 (2D) + 5 (3D) = 15 templates
- Next: run `python seed_rag_models.py` to reinject all 25 into ChromaDB; then wire `agent_createur.py` to select 3D templates
- All 3D games and templates use Three.js r160 via CDN, no external dependencies

---

## Last session: 2026-05-15 — All 25 model games complete (15 2D + 10 3D)

### What was built
Wrote all remaining `jeux_modeles/*.html` model games. Every game is standalone HTML5, meta-progression enabled (loadMeta/saveMeta/shop/4 upgrades), unique META_KEY, correct typography (system-ui for HUD/shop, decorative font for title only).

#### 2D games completed this session (continued from 11/25)
| File | Title | Genre | Notes |
|------|-------|-------|-------|
| `rpg_narratif.html` | SHARDS OF ETERNITY | RPG narrative | 3 battles, 9 scenes, branching, custom enemy sprites |
| `rpg_narratif_2.html` | ECHOES OF THE VOID | RPG narrative | Sci-fi, 10 scenes, holographic UI, NEXUS boss |
| `visual_novel.html` | LAST TRANSMISSION | Visual novel | 20 nodes, 3 endings, The Signal alien character |
| `breakout.html` | PRISM BREAKER | Breakout | Already complete, verified no [FILL:] markers |
| `shoot_em_up_2.html` | DRAGON VEIL | Shooter 2D | Fantasy vertical shmup, 5 enemy types, dragon boss |

#### 3D games written from scratch (Three.js r160)
| File | Title | Genre | Key technique |
|------|-------|-------|---------------|
| `fps_shooter_3d.html` | IRON COMPOUND | FPS | Pointer lock, WASD+mouse, wave enemies, reload system |
| `platformer_3d.html` | SKYRIFT | Platformer 3D | TPS follow-cam, AABB platforms, moving platforms, gems |
| `space_shooter_3d.html` | NEBULA BREACH | Space shooter | Mouse aim, ship banking, sector waves, shield regen |
| `racing_3d.html` | APEX CIRCUIT | Racing | CatmullRomCurve3 oval track, checkpoints, AI racers, nitro |
| `dungeon_rpg_3d.html` | CRYPT OF IRON | Dungeon RPG | First-person dungeon, turn rooms, XP/level-up, magic orbs |
| `zombie_survival_3d.html` | DEAD COMPOUND | Zombie survival | Pointer lock FPS, 4 zombie types, wave system, blood particles |
| `flight_shooter_3d.html` | IRON SKIES | Dogfight | Full 6-DOF flight, barrel roll (Q/E), afterburner (Shift) |
| `tower_defense_3d.html` | LAST BASTION | Tower defense | Raycasting grid placement, 4 tower types, path-following enemies |
| `arena_fighter_3d.html` | GLADIATOR PRIME | Arena fighter | TPS melee, block/dodge/combo, AI opponent, escalating rounds |
| `puzzle_3d.html` | CHROMATIC | Puzzle 3D | Orbital camera, color-matching block puzzle, ghost targets, undo |

### State after this session
- **25/25 model games complete** — all in `jeux_modeles/`
- Next: run `python seed_rag_models.py` to reinject all 25 into ChromaDB
- All 3D games use Three.js r160 via CDN, no external dependencies

---

## Last session: 2026-05-14 (continued 4) — Meta-progression all templates + QC checklists

### What was built
Completed the meta-progression rollout across all 10 templates and hardened QC enforcement.

#### Changes implemented
| ID | Change | File | Effect |
|----|--------|------|--------|
| A1 | `check_fill_placeholders()` | `code_validator.py` | Detects remaining `[FILL: …]` in JS before execution; emits CRITIQUE if unfilled |
| A2 | Patcher SYSTEM prompt fixes | `agent_patcher.py` | W/H no longer assumed 480×640; gameState includes `'shop'`; meta-persistence API documented |
| B1 | Runner QC checklist item 6 | `agent_qc_gameplay.py` | Meta-progression scored as (−1.0 pt) deduction if absent |
| B2 | 7 remaining genre checklists | `agent_qc_gameplay.py` | Shooter, platformer, RPG/dungeon/roguelite, tower_defense, match3, breakout, visual_novel each get item 6 META-PROGRESSION (−1.0 pt) |
| C1 | Meta-progression in 9 templates | 9 HTML files | `shooter_2d`, `platformer_2d`, `breakout`, `puzzle_match3`, `tower_defense`, `dungeon_crawler`, `roguelite`, `rpg_narrative`, `visual_novel` all have full meta block |

### Meta-progression: all 10 templates now complete
Each template has:
- `_META_KEY` unique per genre (e.g. `'meta_shooter'`, `'meta_platformer'`, …)
- Fixed infrastructure: `loadMeta/saveMeta/addRunCoins/buyUpgrade/updateShop/renderShop`
- LLM-fillable: `[FILL: UPGRADE_DEFS]` + `[FILL: APPLY_UPGRADES]`
- State machine: `menu → playing → gameover → shop → playing`
- All menus/HUD/shop use `system-ui, sans-serif` (pixel font only for title)

### QC enforcement
All 8 active genre checklists (shooter, platformer, rpg+dungeon+roguelite, tower_defense, match3, runner, breakout, visual_novel) now have:
- Item 6: `META-PROGRESSION (−1.0 pt)` — deducted if persistent coins + shop with ≥ 2 upgrades absent

### Next step
Run end-to-end test with a shooter or platformer prompt to validate meta-progression in a generated game.

---

## Previous session: 2026-05-14 (continued 3) — Meta-progression + ENGINE hardening

### What was built
Four fixes and one major feature added this session.

#### Changes implemented
| ID | Change | File | Effect |
|----|--------|------|--------|
| E1 | `_ensure_engine_intact()` + `_extract_engine_section()` | `_layer_gen.py` | Detects and surgically restores ENGINE section if LLM modifies or drops it |
| E2 | `_ENGINE_MARKER` / `_ENGINE_SEP` constants | `_layer_gen.py` | Precise boundary detection using 3-separator structure (Sep1→Sep2→Sep3) |
| B1 | `_strip_js_comments()` helper | `code_validator.py` | Prevents `_is_used_standalone()` false positives from JS comments/strings |
| B2 | Strip comments before usage scan | `code_validator.py` | Fixes AUTO-FIX noise: `state`, `body`, `collision`, `direction`, `center` no longer injected |
| F1 | **Meta-progression in `endless_runner.html`** | template | Persistent coins + shop + 4 upgrades (magnet, shield, headstart, multiplier) |
| F2 | `ph` bug fixed in `endless_runner.html` | template | `const playerH` → `const ph` — ground collision variable was undefined in callbacks |
| F3 | `aabb()`, `randChoice()`, `drawBar()` added to ENGINE | template | All engine math helpers now available; `aabb()` used for cleaner collision checks |
| F4 | `Mouse.x` / `Mouse.y` tracking added to ENGINE | template | Shop card click detection works correctly |
| F5 | Typography rule enforced | template | All menus/HUD/shop use `system-ui, sans-serif`; pixel font only for title |

#### Meta-progression architecture (endless_runner template)
State machine: `menu → playing → gameover → shop → playing`

**Fixed infrastructure** (do not modify):
- `loadMeta()` / `saveMeta()` — localStorage with key `meta_runner`
- `addRunCoins(n)` — called on gameover transition, adds floor(coins) to persistent bank
- `getUpgradeLevel(id)` / `buyUpgrade(id)` — level gating + coin deduction
- `updateGameover(dt)` — 1.5s auto-transition to shop (or on any action)
- `updateShop(dt)` / `renderShop()` — clickable card grid + Play button

**LLM-fillable sections**:
- `[FILL: UPGRADE_DEFS]` — UPGRADES array: 4 examples provided (magnet, shield, headstart, multiplier)
- `[FILL: APPLY_UPGRADES]` — `applyUpgrades()` function reading levels → sets `_magnetRange`, `_scoreMultiplier`, `player.maxHp`, `worldSpeed`

**Runtime vars**: `_magnetRange`, `_scoreMultiplier`, `_runCoins`, `_gameoverTimer`, `_shopIdx`

#### Test run: Cyber-Sprint (endless runner)
- Execution score improved: 1.8 (Cosmic Cascade) → **6.47** (Cyber-Sprint)
- `_sanitize_engine_globals()` confirmed working (no ctx=null crash)
- Remaining issues: `ph` bug (now fixed in template), false-positive AUTO-FIX injections (now fixed)

### Next step
Implement meta-progression in the remaining 9 templates:
`shooter_2d`, `platformer_2d`, `breakout`, `puzzle_match3`, `tower_defense`,
`dungeon_crawler` (+ skill tree), `roguelite`, `rpg_narrative`, `visual_novel`

---

## Previous session: 2026-05-14 (continued 2) — Full pipeline consolidation: Sacred Engine Contract

### What was built
Complete system overhaul to guarantee 100% launch reliability. Six simultaneous fixes targeting the root causes of the Cosmic Cascade failure (execution=1.8, ctx=null crash).

#### Changes implemented
| ID | Change | File | Effect |
|----|--------|------|--------|
| T1-A | `_sanitize_engine_globals()` | `code_validator.py` | Removes `var canvas=null / ctx=null / W=0` — the kill switch is permanently closed |
| T1-B | Canonical contract in `_LAYER_SYSTEM` | `_layer_gen.py` | Every layer LLM told: "NEVER redeclare canvas/ctx/W/H" |
| T2-A | Dev console extracted from templates | all 10 templates | Templates back to 23-37KB (was 39-50KB); console injected post-generation by Python |
| T2-B | `max_tokens=65536` for template adaptation | `_layer_gen.py` | LLM has enough budget to complete large templates |
| T3-A | ENGINE manifest in patcher SYSTEM prompt | `agent_patcher.py` | Patcher diagnoses canvas=null in 1 shot using reference model |
| T4-A | `_validate_template_integrity()` (10-point check) | `_layer_gen.py` | Replaces unreliable `_js_check` false-positive — falls back only when score < 7/10 |
| T4-B | `_inject_dev_console()` post-generation | `_layer_gen.py` | Console always injected from `templates/game_templates/consoles/` after both routes |
| T4-C | SYSTEM INSTRUCTIONS prefix on all 10 templates | all 10 templates | LLM reads full ENGINE contract before touching any code |
| FIX | `_fix_spawnplayer_whr()` balanced brace | `code_validator.py` | Fixed nested-object regex crash that introduced `r: 12}` syntax error |
| FIX | ENGINE check instead of `_js_check` in template route | `_layer_gen.py` | Template route no longer false-positives on large files |

#### Architecture: The Sacred Engine Contract
Templates now have a 100-line USAGE GUIDE HTML comment at the top explaining:
- Which variables are sacred (canvas, ctx, W, H — never redeclare)
- Which functions to implement (startGame, updatePlaying, renderPlaying)
- What is absolutely forbidden (setInterval, new Image(), fetch(), location.reload())
- Quality checklist the LLM must satisfy

Console code is now split:
- `templates/game_templates/genres/*.html` — game engine + [FILL] sections + bridge (23-37KB)
- `templates/game_templates/consoles/*.html` — 10 genre-specific console files (~15KB each)
- `_inject_dev_console(html, genre)` in `_layer_gen.py` — injects console post-generation

#### Root cause of Cosmic Cascade failure (diagnosed and fixed)
Failure chain: template _js_check false-positive → layered fallback → L1 generated `var canvas=null` → dedup rollback → `code_validator` injected `r:12}` into nested `hitbox` object → execution=1.8
All 4 root causes are now patched.

---

## Previous session: 2026-05-14 — Dev console added to all 10 templates

### What was built
In-game developer console (toggled via `²` key) integrated into every template.

#### Console features (all 10 templates)
- **`²` toggle**: shows/hides a bottom panel without pausing the game
- **Quick actions bar**: 6 genre-specific one-click buttons (no API call)
- **🔍 ctx button**: reads live game variables and displays them in a collapsible panel
- **AI text input**: natural language → `/api/game-patch` → generated JS executed in game scope
- **Snapshot/undo**: captures state before each patch; up to 15 undo levels
- **Syntax validator**: checks braces/parens/brackets before executing
- **Action log**: last 30 operations with timestamps and success/failure indicator
- **History navigation**: ↑/↓ arrows to browse previous commands
- **`__devPatch` bridge**: defined INSIDE game `<script>` scope so `eval(code)` has full variable access

#### Genre-specific quick actions
| Template | Quick actions |
|----------|--------------|
| `shooter_2d.html` | ♾ Invincible, ❤ Full HP×9, ⚡ Rapid Fire, 💥 Nuke, ↩ Skip Wave, ⭐ Max Score |
| `platformer_2d.html` | ♾ Invincible, ∞ Jump, ⚡ Speed×2, 💰 +100 Coins, ☠ Kill All, 🏆 Next Level |
| `breakout.html` | 3× Multi-Ball, 🔲 Wide Paddle, 🔫 Laser, ⚡ Boost Ball, 💥 Clear Row, ❤ +1 Life |
| `endless_runner.html` | ♾ Invincible, ⚡ Speed×2, 🐢 Slow×0.5, 💰 +100 Coins, ☠ Clear Obstacles, ∞ Jump |
| `puzzle_match3.html` | ∞ Shuffle, 📎 +20 Moves, ⭐ Max Score, 💥 Cascade All, ✨ Make Special, 🌈 All Same Color |
| `tower_defense.html` | 💰 +500 Gold, 👑 Inf Lives, ⚡ Next Wave, ☠ Kill All, 🛡 Tower×2 DMG, ⭐ +1000 Score |
| `dungeon_crawler.html` | ♾ Invincible, ⚔ ATK×5, 💊 Full HP, 💰 +500 Gold, ⭐ +1000 XP, 🚭 Clear Room |
| `roguelite.html` | ♾ Invincible, 💎 +100 Crystals, ⬆ Next Floor, 💊 Full HP, ⚔ ATK×3, ☠ Kill All |
| `rpg_narrative.html` | ⚔ Win Battle, 💊 Full HP/MP, ⭐ Level Up, 💰 +500 Gold, 🚀 Max Stats, 🎭 Clear Flags |
| `visual_novel.html` | ▶ Next Node, ⏭ Skip Text, 🔄 Auto Mode, ⏩ Fast Skip, 🏁 Clear Flags, 📜 History |

#### collectContext() variables tracked per genre
- shooter: `gameState, score, wave, enemiesLeft, player{hp,speed,fireRate,lives}, bullets, enemies`
- platformer: `gameState, score, level, player{hp,x,y,speed,jumpsMax,coins}, enemies`
- breakout: `gameState, balls, paddle, bricks, lives, level, score`
- endless_runner: `gameState, player{hp,y,vy,invincible}, worldSpeed, dist, obstacles, coins`
- puzzle_match3: `gameState, score, movesLeft, level, objective, gridSize, gemTypes, selected`
- tower_defense: `gameState, gold, lives, wave, score, towers, enemies, spawnerActive`
- dungeon_crawler: `gameState, score, player{hp,xp,level,gold,atk,invincible}, room, enemies`
- roguelite: `gameState, floor, room, runScore, meta{crystals}, player{hp,atk,level,relics}`
- rpg_narrative: `gameState, hero{hp,mp,atk,def,level,xp,gold}, scene, flags, lineIndex`
- visual_novel: `gameState, node{id,bg,speaker}, textComplete, autoMode, skipMode, flags, historyLen`

### Next step
Run a generation to test the template system end-to-end. Suggested prompt: "un shoot-em-up spatial avec des boss de phases".

---

## Last session: 2026-05-14 — Template system complete (10 templates + agent_template.py + pipeline integration)

### What was built
Full template system for the arcade pipeline — the single largest quality improvement possible.

#### 10 HTML5 game templates written (`templates/game_templates/genres/`)
| Template | Genre | Size | [FILL] sections |
|----------|-------|------|-----------------|
| `shooter_2d.html` | Shoot-em-up | 23 KB | 18 |
| `platformer_2d.html` | Platformer | 26 KB | 16 |
| `breakout.html` | Breakout/Arkanoid | 25 KB | 10 |
| `endless_runner.html` | Endless Runner | 24 KB | 13 |
| `puzzle_match3.html` | Match-3 Puzzle | 23 KB | 9 |
| `tower_defense.html` | Tower Defense | 26 KB | 12 |
| `dungeon_crawler.html` | Dungeon Crawler | 27 KB | 12 |
| `roguelite.html` | Roguelite | 30 KB | 10 |
| `rpg_narrative.html` | RPG Narrative | 27 KB | 15 |
| `visual_novel.html` | Visual Novel | 27 KB | 15 |

#### Architecture of each template
- **ENGINE section** (marked `// DO NOT MODIFY`): complete, crash-proof boilerplate — object pools, fixed-step game loop, input system, audio helper, particles, screen shake
- **[FILL] sections**: clearly marked creative areas — game title, color palette, entity stats, level data, enemy types, story content
- All 10 genre-specific mechanics pre-built and tested: AABB collision, coyote time, wave system, meta-progression, scene graph, etc.

#### New files
- `agents/phase3/agent_template.py` — selects the right template via keyword matching on `genre_principal + sous_genre + prompt_enrichi`; tested: all 10 genres match correctly
- `run_from_template()` in `agents/phase3/_layer_gen.py` — single LLM call to fill [FILL] sections; falls back to `run_layered()` if output < 5 KB or syntax-broken

#### Pipeline wiring (`coordinateur.py`)
- Phase 2.5 added (after design, before generation): calls `agent_template.run()` for 2D games
- Phase 3: template route used when matched, layered generation used as fallback
- E1 regen path: also uses template when available
- Patch-insufficient regen path: also uses template re-adaptation

### Next step
Run a generation to test the template system end-to-end. Suggested prompt: "un shoot-em-up spatial avec des boss de phases".

---

## Last session: 2026-05-13 (late) — Run 9 diagnosed, variance reduction system implemented

### Run 9 result: 5.57/10 — NOT approved
- **Root cause**: `let JumpyJolt.gameState = 'loading';` at line 14 — dot-notation with `let` is a SyntaxError
- exec=0.88 all 4 iterations (script never loaded). Patcher couldn't fix it — LLM snippets all rejected.

### Fixes implemented (variance reduction — 6 changes)
| Fix | File | Impact |
|-----|------|--------|
| `fix_let_dot_notation()` step -6 | `js_syntax_checker.py` | Deterministic: removes `let/const/var` before `X.Y=` |
| SYSTEM_MODULE_3D rule 7 | `agent_createur.py` | Prohibits `let X.Y = value;` in LLM prompt |
| Temperature 3D modules: 0.5→0.2 | `agent_createur.py` | Less LLM variance = less hallucinated patterns |
| Temperature 2D: 0.6→0.3 | `agent_createur.py` | Same |
| Full working skeleton example in SYSTEM_MODULE_3D | `agent_createur.py` | Few-shot: model follows concrete example not rules |
| `bug_fixes` RAG collection (10 patterns seeded) | `rag.py` | Pre-patcher queries on each LLM fix attempt |
| RAG query integrated in `_llm_fix_snippet` | `agent_pre_patcher.py` | Known fix example injected into prompt |
| RAG anti-patterns injected in module generation | `agent_createur.py` | Creator sees top-3 known bugs to avoid |

### Both approved 2D games fully fixed (blue screen → playable)
- `neon_strike_20260512_125032.html`: 9 bugs fixed (ctx-before-init crash, drawBackground undefined vars, 5 loop variable bugs, drawCombo alpha)
- `royal_rampart_20260512_132439.html`: 11 bugs fixed (dt parameter NaN crash, gameLoop dt passing, loop variables, drawHUD undefined vars, touchmove handler)

### Bug pattern knowledge base
- `memory/project_bug_patterns.md`: 8 categories of known LLM game bugs
- `rag_database/bug_fixes` ChromaDB collection: 10 patterns, queryable by pre-patcher and creator

### Next step
Run 10 — 3D platformer. All variance reduction fixes active.

---

## Last session: 2026-05-13 (continued) — 3D platformer deep-debug: 4 more fixes (runs 8, 9 in progress)

### Session summary
Run 8 = 5.97/10 (not approved). Diagnosed exec=3.8 root causes. Implemented 4 deterministic fixes. Run 9 ready to launch.

### Root causes found and fixed (run 8 debug)

| Fix | File(s) | Root cause |
|-----|---------|-----------|
| Pre-patcher targets longest game script block | `agents/phase5/agent_pre_patcher.py` | Pre-patcher's `re.search` matched the 3D polyfill (first non-CDN block) instead of game code. Injected `let player=null` into polyfill, which was then concatenated with game code by Node.js checker → "Identifier already declared" → pre-patch rejected → code entered Phase 4 with undeclared vars |
| Code validator targets longest game script block | `code_validator.py` | Same bug — code_validator evaluated polyfill as game code → false "boucle de jeu manquante" CRITIQUE → injected `requestAnimationFrame(gameLoop)` into polyfill → gameLoop not yet defined → ReferenceError in polyfill block |
| 3D startup: pre-init UI + startGame() fallback | `agents/phase3/agent_assembleur.py` | `core.init()` called `setState('MENU')` → `ui.showMenu()` before `ui.initUI()` was ever called → `hudElement` undefined → "Cannot read properties of undefined (reading 'style')" crash. Also: HTML template button calls `startGame()` but LLM doesn't define it → Playwright can't start game |
| SYSTEM_3D: explicit initUI() order rule | `agents/phase3/agent_createur.py` | LLM generated ui.showMenu() call in init() before ui.initUI() — added RÈGLE ABSOLUE rule to enforce ui.initUI() first |

### Current state
- All syntax checks pass
- Run 9 ready to launch

---

## Previous session: 2026-05-13 (continued) — 3D platformer deep-debug (5 new fixes)

### Session summary
Re-ran 3D platformer validation (runs 2–4). Each run revealed a new root cause. Found and fixed 5 issues blocking exec on 3D games. Run 4 in progress at session end.

### Root causes found and fixed this session

| Fix | File(s) | Root cause | Effect |
|-----|---------|-----------|--------|
| `fix_cdn_script_content` (step -4 in fix_all_auto) | `js_syntax_checker.py` | LLM module code contained HTML boilerplate (`</script>` + `<script src="...">`) — when substituted into assembler template via `{js_code}`, game code ended up INSIDE the CDN `<script src="three.min.js">` tag. Browsers ignore inline content when `src=` is present → THREE loads, game never runs → exec=2.6 | Detects `<script src="...">code</script>` with >50 chars, extracts code into separate `<script>` block. Also drops duplicate Three.js CDN tag if clean one already exists (prevents r128 overwriting r160). |
| `extract_js_from_html` fix | `js_syntax_checker.py` | After fix_cdn_script_content creates empty `<script src="..."></script>`, the non-greedy regex matched across the empty CDN tag, extracting `</script>\n<script>\n[game_code]\n` as "content" → line 1 was `</script>` → "Unexpected token '<'" | Now skips `src=` tags entirely when extracting JS for node --check |
| `fix_markdown_code_fences` (step -5 in fix_all_auto) | `js_syntax_checker.py` | LLM leaked Markdown code fences (` ```javascript`, ` ``` `) into game code — triple backticks are parsed as template literal delimiters in JS, corrupting all syntax after the first ` ``` ` (line 239) | Removes all lines matching `^\s*\`\`\`` from inside `<script>` blocks |
| Three.js CDN r128 → r160 | `agent_assembleur.py`, `agent_executeur.py`, `agent_createur.py`, `agent_tech_architect.py`, `agent_game_logics.py`, `agent_js_linter.py`, `CLAUDE.md` | `THREE.CapsuleGeometry is not a constructor` — added in r142, not in r128. LLM generates r160-era APIs. Permanently breaks game init → exec stuck at 4.5 despite CDN fix | CDN URL updated from `r128` to `0.160.0` across all 6 files. Cache `rag_database/three.min.js` deleted to force re-download. |
| Duplicate CDN drop in `fix_cdn_script_content` | `js_syntax_checker.py` | Even after fix, the extracted LLM-injected r128 CDN tag remained as `<script src="r128"></script>` — loaded after r160 template tag, overwriting `THREE` global with r128 version → CapsuleGeometry still fails | If a clean Three.js CDN tag already exists (r160 from template), the LLM's CDN tag is dropped entirely, not just emptied |

### Runs executed this session

| # | Result | Key finding |
|---|--------|-------------|
| Run 2 | exec=2.6 all 4 iters | fix_cdn ran but code_validator introduced `Unexpected identifier 'Item'` — traced to unclosed template literal from Markdown fence leak |
| Run 3 | exec=4.5 (E1 regen), stagnation | CapsuleGeometry not in r128 — game crashes at init every iteration |
| Run 4 | In progress at session end | CDN r160 + cache cleared + duplicate CDN drop. Expected to clear CapsuleGeometry |

### Current state
- 23/23 fixes total (18 from previous + 5 today)  
- 20/20 regression tests passing
- Run 4 in progress — expected to finally get exec ≥ 5.0

---

## Previous session: 2026-05-13 — Full fix batch implementation (18 fixes across all phases)

### Session summary
Continued from previous session. Implemented the complete master improvement plan: 3D pipeline fixes (3D-A through 3D-D), Phase 2a loop fixes (B1–B6), Phase 3 quality fixes (Q1–Q6). All 9 modified files pass syntax check. Regression tests running.

### Fixes implemented this session

| Fix | File(s) | What |
|-----|---------|------|
| 3D-A | `js_syntax_checker.py` | `fix_stray_script_close()`: removes `</script>` inside game script block — now first step in `fix_all_auto` cascade |
| 3D-B | `agent_qc_visuel.py` | `_apply_visual_code_checks(est_3d=)`: 2D canvas penalties (fillStyle/HUD/draw*/shadowBlur/arc) skipped for Three.js; 3D-specific checks (scene.background, lighting, DOM HUD) added |
| 3D-C | `coordinateur.py` | E1 regen for modular 3D: if exec<4.0 on iteration 1, re-run `run_modulaire` + `agent_testeur_modules` + `agent_assembleur` with past errors injected |
| 3D-D | `js_syntax_checker.py` | ESLint skip for Three.js: early return in `check_undefined_vars_eslint` if CDN three.js detected |
| B1 | `agent_pre_patcher.py` | Snippet-level syntax check: allow LLM calls even when full script is broken, if the extracted snippet is itself valid |
| B2 | `coordinateur.py` | `fix_all_auto` loop ×3 in `_post_generation_cleanup` — runs for both 2D and 3D post-generation |
| B3 | `agent_executeur.py` | Error persistence tracker: `[PERSISTS×N]` prefix added to repeated error messages for the AI mini-patcher |
| B4a | `agent_executeur.py` | `validate_and_fix` (includes `_fix_arrow_key_mapping`) now runs on EVERY repair pass (not just `cannot_read_props`) |
| B4b | `code_validator.py` | `_fix_missing_gameloop_calls()`: detects zero-arg `update*/draw*` functions never called from game loop, injects calls |
| B5 | `agent_executeur.py` | Diff ratio check: rollback mini-patcher AI result if diff > 35% (prevents LLM rewriting entire game) |
| B6 | `agents/phase3/_layer_gen.py` | Genre-specific recurring error hints injected into every generation prompt (8 genres covered) |
| Q1 | `agent_createur.py` | RÈGLE ABSOLUE N°19: gradient/rich background mandatory — no solid black (#000) |
| Q2 | `agent_createur.py` | RÈGLE ABSOLUE N°20: screen shake + flash effect mandatory for impact games |
| Q3 | `agent_createur.py` | RÈGLE ABSOLUE N°21: full Web Audio sfx object mandatory (not stub) |
| Q4 | `coordinateur.py` | GDD depth enforcement: retry `agent_game_designer` if systems < 3 |
| Q5 | `agent_createur.py` | Mandatory arc()/bezierCurveTo() sprites with examples per genre — -2.0 penalty documented |
| Q6 | `agent_qc_gameplay.py` | Added racing and 3D platformer genre checklists |

---

## Previous session: 2026-05-12 — 4-run validation + 8 robustness fixes

### Session summary
4 validation runs (2D shooter, 2D tower defense, RPG narratif, 3D platformer). Runs 1–2 approved. Runs 3–4 stuck at exec=2.6 due to distinct root causes. 8 fixes implemented during the session. Full root-cause analysis on 3D pipeline completed.

### Runs executed

| # | Prompt | Game | Score | Approved | Root cause failure |
|---|--------|------|-------|----------|--------------------|
| 1 | shoot-em-up néon | neon_strike | ~7+ | ✅ | — |
| 2 | tower defense royal | royal_rampart | ~7+ | ✅ | — |
| 3 | RPG narratif dialogues | chroniques_des_gribo | 4.5 | ❌ | Mini-patcher injected `Unexpected token ':'`; 503 on layer 9 (fixed mid-run) |
| 4 | platformer 3D Three.js | jump_n_joy | 4.89 | ❌ | `SyntaxError: Unexpected token '<'` in assembled HTML blocked ALL fixes; QC Visuel 2D penalties applied to 3D (6.3→1.0) |

### Fixes implemented

| Fix | File | What |
|-----|------|------|
| Fix 1A | `agent_executeur.py` | Mini-patcher IA: syntax check before returning patched section — reject if broken |
| Fix 1C | `agent_executeur.py` | Repair loop: syntax check before Playwright run — skip run if code has errors |
| Fix 3 | `coordinateur.py` | Best-version keeper: track highest-scoring (code, bundle) across iterations, restore before Phase 5 if later iterations regressed |
| Fix 4 | `js_syntax_checker.py` | `fix_unexpected_identifier()`: detect `Unexpected identifier X` via Node.js, insert semicolon at end of previous line |
| Fix 5 | `agent_executeur.py` | Mini-patcher context enrichment: include declaration snippets for each target variable |
| Fix 6 | `agent_executeur.py` | Mini-patcher fallback: inject `var X = null;` if `X is not defined` target absent from patched section |
| Fix 7 | `js_syntax_checker.py` | ESLint truncated retry: on timeout, retry on first 60K chars with 15s timeout |
| Fix 8 | `coordinateur.py` | Enrichisseur output validation: if mechanics < 3 or prompt_enrichi < 200 chars, backfill from classification |
| Fix A | `config.py` | 503 backoff: `15*(2**attempt)` capped at 120s (was max 30s) |
| Fix layer | `agents/phase3/_layer_gen.py` | Layer-level 503 retry: wait 3 min after exhausting retries, retry layer once |

### New root causes found (run 4 — 3D platformer)

**Root cause 1 — Stray `</script>` inside game script block**
The 3D modular assembler occasionally includes `</script>` inside the game `<script>` tag. This causes `SyntaxError: Unexpected token '<'` at line 1 (via Node.js). Consequence: ALL JS fixes (`fix_all_auto`, pre-patcher LLM snippets, `fix_unexpected_identifier`) are blocked. The pre-patcher detects "code cassé" and skips every LLM call.
→ **Fix needed**: scan assembled 3D HTML for `</script>` inside the game script block, remove it before any QC.

**Root cause 2 — QC Visuel 2D penalties on 3D games**
QC Visuel scored the 3D game at 6.3, then penalized it to 1.0 for: "no non-black fillStyle background" and "no HUD detected". These are 2D Canvas checks. Three.js games use `scene.background` / `renderer.setClearColor` — not `fillStyle`. The 5 visual penalties killed a 6.3 → 1.0, dragging global score below the C1 execution cap.
→ **Fix needed**: in `agent_qc_visuel.py`, detect 3D (Three.js CDN present or `technologie_rendu==threejs`) and skip 2D canvas penalties.

**Root cause 3 — E1 regeneration skipped for modular 3D games**
E1 (full regen when exec<4.0) only triggers `if not use_modular`. For 3D games, `use_modular=True` → E1 logs the warning but never regenerates. Execution stayed at 2.6 across all 3 iterations.
→ **Fix needed**: implement E1 for modular 3D path — trigger modular re-generation with past errors if exec<4.0 on iteration 1.

**Root cause 4 — ESLint double timeout on 3D games**
ESLint timed out on both the full file AND the 60K truncated retry (the file was already <60K, so both timeouts were on the same content). No undef detection for 3D games.
→ **Fix needed**: skip ESLint for 3D games (files too large + Three.js globals confuse it).

### Next session — priority fix list

1. **[CRITICAL] Fix stray `</script>` in 3D assembler** — in `agents/phase3/agent_createur.py` modular assembler or `js_syntax_checker.py`, strip `</script>` from inside game script block
2. **[HIGH] Fix QC Visuel for 3D** — skip `fillStyle`/canvas HUD penalties when Three.js CDN detected in HTML
3. **[HIGH] E1 regeneration for 3D** — re-run modular generation if exec<4.0 on iteration 1
4. **[MEDIUM] ESLint 3D skip** — if `technologie_rendu==threejs`, skip ESLint entirely
5. **Then re-run 3D platformer** to verify fixes work

---

## Previous session: 2026-05-11 — Token cost optimization (disable_thinking on 3 agents)

### Session summary
Analyzed full pipeline token costs. Identified 3 agents silently using `call_gemini` with default `disable_thinking=False` when they have no need for reasoning. Fixed all 3.

### What was fixed

| File | Change | Why |
|------|--------|-----|
| `agents/phase2/agent_game_logics.py` | `_call_section`: added `disable_thinking=True` | 4 calls/gen × thinking budget = biggest silent cost. Section specs are mechanical (numeric values, state machines) — no reasoning needed. |
| `agents/phase5/agent_pre_patcher.py` | `_call_llm`: added `disable_thinking=True` | Up to 3 calls/gen. Pre-patcher does pattern-based text injection, not creative reasoning. |
| `agents/phase4/agent_executeur.py` | `_mini_patcher_gemini`: added `disable_thinking=True` | Conditional call. Mini-patcher rewrites one targeted function — focused code fix, not creative. |

### Why the original plan was wrong (and was corrected)
- Plan A (merge game_logics 4→1): would have caused lost-in-the-middle on sections 2-3, which were deliberately separated for that reason.
- Plan B (disable game_designer thinking): Phase 2 structural agents already had `disable_thinking=True` via `call_gemini_json` defaults. Game designer thinking is intentional (quality cascades through 8 layers).
- Plan C (strip HTML from QC): HTML boilerplate is <2% of game file size — negligible.
- Plan D (skip playtester): distorts weighted score used by stagnation detection and E4 early-exit.

### Estimated savings
25–40% reduction in token cost per generation, concentrated in game_logics (4 calls) and pre_patcher (3 calls per full run).

---

## Previous session: 2026-05-08 — Full code review + 31 fixes + next session plan

### Session summary
First systematic full-codebase review (all 40+ Python files). Identified and fixed 31 issues across 20 files in 9 commits. Then built and validated a 4-phase improvement plan for the next sessions.

### What was fixed (9 commits)

| Commit | Category | Key fixes |
|--------|----------|-----------|
| `bc977b1` | CRITICAL | `config.py` retry loop (Gemini fallback fired after 1st retry not last), `logger.py` `get_session_log()` returned `str` not `list[str]` → malformed saved logs, fallback game French strings |
| `b31ba62` | HIGH | `app.py` re-eval threshold 6.5→7.5, `agent_verdict_final` SEUIL 7.0→7.5, French `[CORRIGÉ]/[RÉCURRENT]` strings in LLM prompts → English, STYLE_GRAPHIQUE_MAP translated, `snapshot.py` hardcoded path fixed |
| `efc3c21` | i18n | phase1 agents (enrichisseur, architecte) SYSTEM → English |
| `946d2dc` | i18n | phase2 agents (game_designer full 7 rules, tech_architect 3D constraints, game_logics) SYSTEM → English |
| `7c47ac2` | i18n | phase4 agents (qc_gameplay, qc_visuel 2D+3D, playtester) SYSTEM → English |
| `b041853` | i18n | phase5 agents (diagnosticien full with JSON example, patcher full with all bug patterns) SYSTEM → English |
| `c8b6617` | MEDIUM | `_extract_js_from_html` → longest-match (was first-match, broke Three.js CDN), B5 `str.replace()` instead of `re.sub` on all script tags, `agent_enrichisseur_code.py` deleted (dead code) |
| *(in b31ba62)* | LOW | `agent_auto_learner.run()` → daemon thread (was blocking), debug page weights corrected (playtester 10→15, anti_pattern 5→3, benchmark 5→2) |

### Why these bugs existed
All were reactive fixes from previous sessions (fix what crashed, not everything). This was the first full audit of every file. Previously all sweeps were targeted and reactive.

### Next session plan (saved in memory: project_next_session_plan.md)

**4 phases — in order:**

**Phase A — Validation (START HERE)**
1. A0: Curate existing 58 saved games — identify which are already demo-ready (score ≥ 7.5, manually playable)
2. A1: Run `python test_regression.py` — all tests must pass
3. A2: 4 validation runs: shoot-em-up (baseline vs 7.70), tower defense (RAG test), narrative RPG (scenariste test), 3D game (JS extraction fix test)
4. A3: Post-run checklist per game: glow present, no rectangle sprites, executor ≥ 5.0, RAG hit in logs, manually playable
5. A4: Contingency if < 7.0 — targeted log diagnosis → fix → re-run

**Phase B — Score ceiling push (after A confirms ≥ 7.5 avg)**
- B1: GDD depth enforcement (check `systemes_principaux` ≥ 3, retry once if not)
- B2: Working audio via Web Audio API boilerplate (test Playwright compatibility first)
- B3: Iteration delta logging (`[ITER-DELTA]` per evaluation round — reveals if patching helps)
- B4: 3D-specific fixes based on Phase A Run 4 results

**Phase C — Demo library (2–3 sessions)**
- 10–15 games covering all 10 genres, all ≥ 7.5 + manually verified
- Run in genre order to build RAG progressively (each good game seeds the next)
- Final 1-hour manual curation session to pick the best 10 for Arcade AI demo

**Phase D — Demo polish (last)**
- README + screenshots + GitHub push
- Stats page visual overhaul
- Stretch: gallery with thumbnails, demo mode

### First command next session
```bash
python test_regression.py
```
Then launch Run 1 at localhost:5000: "un shoot-em-up spatial néon avec des boss et power-ups"

---

## Previous session: 2026-04-30 — DQ11-style rpg_narratif + combat bug fixes

### Résumé session
Réécriture complète de `jeux_modeles/rpg_narratif.html` en style Dragon Quest 11 2D lisse.
Abandon du pipeline pixel-art offscreen (160×120 × 4). Rendu direct 640×480 avec formes composites et dégradés.

### Bugs corrigés (session précédente + cette session)
- Actions combat incliquables : `kjp={}` vidé AVANT `update()` → fix : déplacé APRÈS `update()` dans la boucle
- Menus illisibles : textes passaient par l'offscreen 160×120 (police 5px) → fix : rendu direct sur ctx
- Fuite soigne l'ennemi : `combat.enemy` est une copie `{...}`, les dégâts ne se synchronisent pas → fix : `combat.enemy.ref.hp = Math.max(1, combat.enemy.hp)` avant d'appliquer la fuite
- Probabilité de fuite trop faible : 50% → 70%

### rpg_narratif.html — Réécriture DQ11 2D
**Abandon total du pixel art offscreen. Tout dessiné directement sur ctx 640×480.**

Architecture graphique :
- `TILE=48px` — tuiles procédurales avec `createLinearGradient` / `createRadialGradient`, lames d'herbe, arbres détaillés, eau animée, bâtiments avec fenêtres lumineuses
- `drawHero(cx,cy,dir,frame,sc)` — ombre ellipse, tunique bleue gradient, tête gradient radial peau, cheveux arc, yeux par direction, épée argentée
- `drawNPCShape(cx,cy,type,sc)` — 5 types (sage+staff orb, forgeron tablier, garde casque, marchand grand chapeau, prisonnier)
- `drawEnemyShape(cx,cy,type,shake,sc)` — loup (gris/bleu, yeux rouges brillants, crocs), bandit (armure rouge, bandana), boss (armure sombre, couronne dorée, grande épée), gardien (violet, aura magique, orbe)
- `drawPanel(x,y,w,h,title)` — panneaux avec fond dégradé sombre + bordure or double
- `drawHPBar(x,y,w,h,val,max,col)` — barre avec dégradé lumineux
- Combat : fond ciel de bataille gradient, sol texture, étoiles animées, ennemi centré-droit (scale 1.3×), héros bas-gauche (scale 0.85×), secousse pendant animation tour

**Logique préservée à l'identique :**
- Carte 20×15, système caméra, collision tuiles, zones bloquées (citadelle sans drapeau)
- 5 PNJs + 5 ennemis monde (2 loups, bandit, boss, gardien corrompu)
- Tous les dialogues, arbres de choix, flags, quêtes
- Combat tour par tour : attaque, magie (-10 MP), potion, fuite (70%)
- Gains XP, level-up stats, or, condition victoire narrative (gardien corrompu vaincu)

---

## Session précédente : 2026-04-26 (suite) — Pipeline améliorations majeures (5 axes)

### Résumé session
Suite de la session précédente. Star Blaster Blitz stabilisé (boss, barre de vie, blinkAlpha). 5 axes d'amélioration pipeline implémentés.

### Fixes Star Blaster Blitz (star_blaster_blitz_20260426_005117.html)
- Boss ne spawne jamais : `BOSS_DEFS['level'+level]` = undefined → guard retourne tôt → `|| BOSS_DEFS` fallback
- Boss scroll hors écran : `boss.y += scrollSpeed * dt` dans update + pas de clamp → entrée animée + clamp Y dans 3 bossPattern functions
- Barre de vie boss invisible : `barX=0, barY=0, barWidth=0` → `barX=40, barY=12, barWidth=W-80, barHeight=14`
- `blinkAlpha is not defined` dans drawGameOver : var déclarée dans drawMenu mais utilisée dans drawGameOver → déclarée locale dans drawGameOver
- boss.vx/shootTimer/invTimer/waveActive=false manquants dans spawnBoss → ajoutés

### 5 axes d'amélioration implémentés

| Axe | Statut | Fichiers |
|-----|--------|---------|
| 0. Mini-patcher IA executor | ✅ FAIT | `agent_executeur.py` : `_mini_patcher_gemini()` extrait fonction cible + globals (~200 lignes), évite "lost in the middle" |
| 1. Executor amélioré | ✅ FAIT | Test "Score progresse" (Space×10 → attente → check score), hard cap 4.5 si JS errors + joueur immobile |
| 2. Support jeux narratifs | ✅ FAIT (complet) | `genre_profile.py` NarrativeContext, `agent_scenariste.py` NOUVEAU, `agent_createur.py` narrative_info, `agent_qc_gameplay.py` critères narratifs |
| 3. Jeux modèles | ⏳ EN COURS (3/9) | `jeux_modeles/` : shoot_em_up.html, platformer.html, rpg_narratif.html codés à la main |
| 4. Playability gate | ✅ PARTIEL | SCORE_MIN_EXECUTION=5.0, hard cap 4.5, veto agent neutre |
| 5. Feedback erreurs JS → patcher | ✅ PARTIEL | commentaire_global inclut 3 premières erreurs JS |

### Jeux modèles créés (jeux_modeles/)
- `shoot_em_up.html` : ~400 lignes, 4 types ennemis, power-ups, boss par vague, highscore localStorage
- `platformer.html` : ~500 lignes, coyote time + jump buffer, 3 niveaux, 2 types ennemis
- `rpg_narratif.html` : ~600 lignes, map tuiles 20×15, dialogues typewriter, 5 PNJs, système quêtes, combat tour par tour, boss final

### Ce qui reste à faire (Point 3)
- 6 jeux modèles restants : puzzle match-3, endless runner, breakout, tower defense, visual novel, dungeon crawler
- Script injection ChromaDB : extraire patterns → `rag.store_pattern()`

---

## Session précédente : 2026-04-26 (matin) — Run 7 Star Blaster Blitz + fixes pipeline

### Résumé session
Run 7 (shoot em up spatial) lancé → score 7.70 sauvegardé. Jeu injouable → débogage complet + 12 fixes pipeline.

### Bugs jeu corrigés (star_blaster_blitz_20260426)
| Bug | Cause | Fix jeu | Fix pipeline |
|-----|-------|---------|-------------|
| Écran noir (SyntaxError) | Literal `\n` dans string Python | `split('\\n')` dans utils_dev_console | `fix_literal_newlines_in_strings` dans js_syntax_checker |
| Stubs vides écrasent implémentations | `_stub_orphan_calls` injecte stubs pour fonctions déjà définies | Stubs supprimés du jeu | Guard `re.search('function fn(', accumulated)` avant injection |
| `handleBulletEnemyHit()` sans args crash | Patcher injecte appels sans args dans gameLoop | Appels supprimés | `_fix_no_args_handlers_in_gameloop` dans code_validator |
| `multiplierTimer is not defined` | Patcher utilise var sans la déclarer | Déclaré global | Ajout à COMMON_VARS |
| PALETTE dupliquée → undefined | Second `var PALETTE={}` écrase L1 | `Object.assign` | `fix_duplicate_palette` dans js_syntax_checker |
| `gridSize is not defined` | Var locale L6 utilisée dans L9 sans redéclaration | Déclarée | `_fix_undeclared_draw_locals` dans code_validator |
| `hpRatio is not defined` (9 fonctions) | Idem L6→L9 | Injectées | `_fix_undeclared_draw_locals` dans code_validator |
| Joueur non réactif (updatePlayer/etc. vides) | Stubs orphelins écrasent vraies implémentations (last-def-wins) | Stubs retirés | `_stub_orphan_calls` skip si `function fn(` déjà présent |
| `typeDef.name` → undefined | ENEMY_TYPES utilise `type:` mais code lit `.name` | `.name` → `.type` | `_fix_type_vs_name_property` dans code_validator |
| `e.typeIndex` → undefined | `spawnEnemy(typeIndex)` ne stocke pas typeIndex sur l'objet | `typeIndex: typeIndex` ajouté | `_fix_spawn_missing_typeindex` dans code_validator |
| `e is not defined` dans drawEnemies | L9 réécrit drawEnemies sans `var e = enemies[i]` | `var e` injecté | `_fix_draw_loop_missing_element_var` dans code_validator |
| `b is not defined` dans drawBullets | Idem pour drawBullets | `var b` injecté | Couvert par même fonction |
| `p is not defined` dans updateParticles | Idem pour updateParticles | `var p` injecté | Table étendue aux update* |
| ArrowLeft/Right ne bougent pas le joueur | Handler stocke `keys["arrowleft"]` mais updatePlayer lit `keys.left` | Mapping ajouté | `_fix_arrow_key_mapping` dans code_validator |
| Ennemis spawent à gauche seulement | `spawnEnemy` hardcode `400` au lieu de `W` | `W` utilisé | Bug connu |
| Balles ne supprimées pas après hit | `handleBulletEnemyHit` L9 ne splice pas | `bullets.splice(bi,1)` ajouté | Fix dans jeu |
| Écran vide après vague 1 | `drawUpgradeSelect` inexistant | Fonction créée | Bug connu |

### Amélioration agent_executeur
- Lit `window.__ARCADE_ERROR__` (erreur gameLoop catch) → repair loop max 3 itérations
- Lit `player.x` avant/après ArrowRight — détecte joueur figé (avant : fallback canvas diff → faux positif car fond animé)
- Test `enemies.length > 0` après démarrage → détecte spawn cassé

### Tests
20/20 après chaque fix.

---

## Session précédente : 2026-04-20 — Audit 33/33 COMPLET + Symbol Table A+B+C (stable/v8)

### Résumé session
Continuation audit. 7 items restants implémentés + refonte anti-hallucination majeure (Symbol Table A+B+C).
Commit : stable/v8 (`8b60c99`).

### Nouveau système anti-hallucination — Symbol Table A+B+C

**Problème résolu :** LLM hallucine des constantes ALLCAPS (`ENEMY_SPEED_DRONE`, `ENEMY_HP_BOMBER`) inexistantes
parce qu'il pattern-complete depuis ses données d'entraînement sans vérifier L1.

**Implémentation dans `_layer_gen.py` :**
- `_build_symbol_table(l1_js)` : extrait toutes les constantes ALLCAPS et type arrays de L1
- `_format_global_contract(table)` : formate un "contrat global" injecté en tête de chaque prompt L2-L9
- `_resolve_undeclared_symbols(fragment, table, accumulated)` : scan post-génération, inject `var NAME=heuristic;` pour tout ALLCAPS non déclaré
- `_derive_constant_value(name)` : heuristiques (speed→150, rate→0.5, hp→3, dmg→1, etc.)
- `_build_layer_context()` : nouveau param `global_contract=` utilisé sur toutes les 8 couches
- L1 prompt : instruction `// @GLOBALS:` pour que L1 liste ses constantes

### Fixes audit items 7/7 restants

| ID | Fichier | Fix |
|----|---------|-----|
| **C1** | `_layer_gen.py` post-assemblage | Injection déterministe `score += e.points\|\|10` dans `handleBulletEnemyHit` si score absent |
| **C2** | `agent_executeur.py` | Test Playwright : `player.hp > 0` (santé accessible et positive) |
| **C5** | `agent_executeur.py` | Test Playwright : zone HUD (top 10% canvas) non noire |
| **D2** | `utils.py` | `strip_js_comments(js)` → appelé automatiquement dans `extract_js_sample()` (~25% tokens économisés) |
| **E1** | `coordinateur.py` | `store_code_preview(code)` après Phase 3 (live preview via `/api/preview`) |
| **G1/G2/G4** | — | SKIP (dette mineure, ROI faible, pas de démo impact) |

### État audit complet
- **33/33 items traités** (B2/B8/B10 : déjà OK ou SKIP justifié, G1/G2/G4 : SKIP dette mineure)
- Snapshot : stable/v8 (2026-04-20)

### À faire maintenant
1. Lancer 3-4 générations (shooter, platformer, tower defense, puzzle)
2. Surveiller logs `[symbol-table]` → vérifier que les constantes hallucinées sont résolues
3. Vérifier manuellement chaque jeu sauvegardé dans le navigateur

---

## Session précédente : 2026-04-15 (suite) — P5 + fixes jeu star_blaster_blitz

### Fixes pipeline supplémentaires

| Fichier | Fix |
|---------|-----|
| `agents/phase3/_layer_gen.py` | **P5** : après réparation, injection auto des fonctions `update*/draw*/check*` non appelées via `_patch_gameloop_calls` |
| `jeux_sauvegardes/star_blaster_blitz_20260415_151938.html` | `gradient1/2/3` locale → recréées inline dans `drawBackground` (cause écran bleu flou) |
| `jeux_sauvegardes/star_blaster_blitz_20260415_151938.html` | `gridSize` non déclaré dans `drawBackground` → `var gridSize = 50` ajouté |
| `jeux_sauvegardes/star_blaster_blitz_20260415_151938.html` | `drawEnemies` (v2) : `e` non déclaré → `const e = enemies[i]` ; `hpRatio` → déclaré local ; `angle` hex → `let angle = (j/6)*Math.PI*2` |
| `jeux_sauvegardes/star_blaster_blitz_20260415_151938.html` | `drawBoss` (v2) : `hpRatio`, `barX`, `barY` non déclarés → déclarés locaux |
| `jeux_sauvegardes/star_blaster_blitz_20260415_151938.html` | `drawHUD` (v2) : `hpRatio` non déclaré → `const hpRatio = player.hp / player.maxHp` |

### État des 6 priorités — TOUTES IMPLÉMENTÉES ✅

P1 double RAF | P2 playtester fallback score | P3 playSound stub → WebAudio | P4 COMMON_VARS | P5 injection post-réparation | P6 timeout 20s

### À ne PAS oublier
- `.quota_rpd.json` à supprimer avant chaque run si clé payante changée
- Clé payante dans `.env` avec `GEMINI_RPD_LIMIT=9999`, `GEMINI_RPM_LIMIT=50`, `GEMINI_RPM_LIMIT_PAID=200`
- Le jeu star_blaster_blitz a eu de nombreux bugs de variables non déclarées dans ses fonctions draw* v2 (layer 7) — signe que le layer 7 génère parfois des fonctions qui référencent des vars locales d'autres fonctions comme si elles étaient globales

---

## Session 2026-04-15 (run Star Blaster Blitz + analyse logs + 15 fixes pipeline)

### Résultat run Star Blaster Blitz
- Score : 7.64/10 — **sauvegardé** ✓
- exec : 8.5/10 stable (root cause `Unexpected token ']'` corrigé)
- Durée : 34m41s (2 itérations)
- Bug post-run : `star is not defined` dans drawStars — patché manuellement dans le HTML sauvegardé

### Fixes appliqués

| Fichier | Fix |
|---------|-----|
| `code_validator.py` `_dedup_declarations` | Skip `var X = {` → fix root cause `Unexpected token ']'` |
| `code_validator.py` `_fix_orphan_closing_braces` | Rollback si opens > closes après suppression |
| `agent_pre_patcher.py` `_dedup_declarations` | Même fix (copie distincte) |
| `agent_pre_patcher.py` `_dedup_functions` | Garde le PLUS LONG (pas le dernier) + garde DOMContentLoaded/RAF |
| `agent_pre_patcher.py` `run()` | `_quick_syntax_ok` par snippet + déplacé en haut (fix NameError) |
| `agent_pre_patcher.py` stopwords | `Canvas` ajouté ; check taille snippet supprimé |
| `agent_executeur.py` | `type not found`, `not found:` dans critical_errors |
| `agent_createur.py` | Règles 22/23 + patterns I/J dans `_FORBIDDEN_JS_SYNTAX` |
| `coordinateur.py` | `MAX_ITERATIONS` 3→2 |
| `config.py` | `MAX_CALLS_PER_MINUTE_PAID=200` |
| `code_validator.py` | `_fix_forindex_missing_element` + `_fix_empty_playsound_stub` + COMMON_VARS |
| `genre_profile.py` `score_global()` | Playtester fallback exclu du calcul pondéré |
| `js_syntax_checker.py` | Timeout 10s → 20s |
| `agents/phase3/_layer_gen.py` | Déduplication `requestAnimationFrame(gameLoop)` |

---

## Session précédente : 2026-04-15 (fix root cause Unexpected token ']' + repasse Pro)

### Contexte
Continuation de la session précédente (run Galactic Fury, exec=2.2/10).
Root cause identifiée et fixée. Agent créateur repassé en Gemini Pro.

### Coût session
0€ (pas de run lancé — uniquement fixes code)

### Bug root cause corrigé — `Unexpected token ']'`

**Root cause réelle** : `_dedup_declarations` supprimait la ligne `var X = {` mais laissait le `}` de fermeture flottant → `_fix_orphan_closing_braces` le supprimait (profondeur < 0) → si ce `}` fermait un objet dans un tableau, le `]` du tableau devenait invalide.

**Fixes appliqués**

| Fichier | Fix |
|---------|-----|
| `code_validator.py` `_dedup_declarations` | Skip les déclarations qui se terminent par `{` ou `[` (bloc multi-ligne) → ne jamais supprimer une ligne qui ouvre un bloc |
| `agents/phase5/agent_pre_patcher.py` `_dedup_declarations` | Même fix (copie de la fonction dans pre_patcher) |
| `code_validator.py` `_fix_orphan_closing_braces` | Rollback si après suppression `opens > closes` (garde de sécurité secondaire) — s'applique au chemin principal ET au fallback |
| `agents/phase3/agent_createur.py` | Repasse en Gemini Pro (`MODEL_NAME_PRO` dans `_call` et `_call_module`) |

**Tests** : 18/18 régression passés après les fixes.

### Ce qui reste à faire

1. **Valider** : relancer le shooter spatial et vérifier exec > 4.5
2. **Observer** : est-ce que `Unexpected token ']'` disparaît ? Si oui, fix confirmé.
3. **Surveiller** : exec moyen sur les prochains runs

### À ne PAS oublier
- `.quota_rpd.json` à supprimer avant chaque run si clé payante changée
- Clé payante dans `.env` avec `GEMINI_RPD_LIMIT=9999`
- Run Galactic Fury durait 38min → normal pour 3 itérations avec Pre-Patcher

---

## Session précédente : 2026-04-14 (run diagnostique + fixes pipeline + passage Pro)

### Contexte
Premier run avec nouvelles clés gratuites → quota 171/171 brûlé sur une seule génération cassée.
Diagnostic complet des causes + 6 fixes appliqués + migration vers Gemini 2.5 Pro sur agent_createur.

### Bugs découverts et fixes appliqués

**Bug 1 — `_dedup_functions` supprimait les versions améliorées des couches (82K → 46K)**
- Cause : garde la PREMIÈRE occurrence → layer 9 (graphisme enrichi) écrasait layer 6 (rendu basique) → 1052 lignes supprimées
- Fix : `agent_pre_patcher.py` → `_dedup_functions` garde maintenant la DERNIÈRE occurrence

**Bug 2 — Quota journalier traité comme erreur transiente → 18 retries par agent**
- Cause : `"quota"` dans le message d'erreur matché par le handler 429 → 18 tentatives × N agents = 171 appels brûlés
- Fix : `config.py` → détection `"quota journalier"` → `raise` immédiat sans retry

**Bug 3 — `SyntaxError: Unexpected token ':'` non comptée comme erreur critique**
- Cause : filtre `critical_errors` dans l'exécuteur ne catchait que TypeError/ReferenceError
- Fix : `agent_executeur.py` → ajout `syntaxerror` et `unexpected token` dans le filtre

**Bug 4 — `extract_js_from_html` ne vérifiait que le plus grand bloc script**
- Cause : si le HTML a plusieurs `<script>`, les erreurs dans les blocs secondaires passaient
- Fix : `js_syntax_checker.py` → concatène tous les blocs > 50 chars avant check Node.js

**Bug 5 — `GEMINI_API_KEY_1` jamais chargée**
- Cause : boucle `range(2, 20)` → sautait le `_1`
- Fix : `config.py` → `range(1, 20)`

### Migration vers Gemini 2.5 Pro (agent_createur uniquement)

- `config.py` : ajout `MODEL_NAME_PRO = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")`
- `config.py` : paramètre `model=None` dans `call_gemini()`, utilisé si fourni
- `agent_createur.py` : `_call` et `_call_module` passent `model=MODEL_NAME_PRO`
- Tous les autres agents restent sur Flash

### Configuration clés payantes

- `config.py` : `MAX_CALLS_PER_DAY = int(os.getenv("GEMINI_RPD_LIMIT", "19"))`
- `config.py` : `MAX_CALLS_PER_MINUTE = int(os.getenv("GEMINI_RPM_LIMIT", "4"))`
- `.env` à configurer : `GEMINI_RPD_LIMIT=9999`, `GEMINI_RPM_LIMIT=50`
- Clé payante = `GEMINI_API_KEY`, clés gratuites = `GEMINI_API_KEY_1` à `GEMINI_API_KEY_N`
- Supprimer `.quota_rpd.json` + redémarrer l'app après changement de clés

### Fichiers modifiés cette session

| Fichier | Changement |
|---------|-----------|
| `agents/phase5/agent_pre_patcher.py` | `_dedup_functions` garde DERNIÈRE occurrence |
| `agents/phase4/agent_executeur.py` | `critical_errors` inclut SyntaxError/Unexpected token |
| `agents/phase3/agent_createur.py` | `_call` + `_call_module` utilisent `MODEL_NAME_PRO` |
| `js_syntax_checker.py` | `extract_js_from_html` concatène tous les blocs script |
| `config.py` | quota journalier fatal + MODEL_NAME_PRO + RPD/RPM via env + range(1,20) |

### État au moment de clore la session

- Run de test pas encore complété (quota gratuit épuisé en cours de session)
- Prochaine run : clé payante active + `.quota_rpd.json` supprimé + app redémarrée
- `Unexpected token ':'` root cause toujours inconnue — Pro devrait réduire la fréquence

### Ce qui reste à faire

1. **Valider le premier run complet** avec clé payante + Pro sur créateur
2. **Observer si `Unexpected token ':'` disparaît** avec Pro — si persiste, investiguer le code généré
3. **Vérifier les layer stats** (chercher `95%` ou `98%`) — si tronqué, monter `max_tokens` sur les couches concernées

### À ne PAS faire
- Ne pas save agent_createur.py depuis Cursor sans recharger depuis le disque d'abord
- Ne pas supprimer `.quota_rpd.json` pendant un run en cours

---

## Session précédente : 2026-04-04 (analyse 3 jeux échoués + fixes ciblés)

### Bugs découverts sur le run "Astro Blitz" et fixes appliqués

**Bug 1 — `dt is not defined` (23 erreurs runtime)**
- Cause : `dt` déclaré LOCAL dans `gameLoop` (`const dt = ...`) → inaccessible depuis les fonctions helper (`updateEnemies`, `spawnBoss`, etc.)
- Fix : `SYSTEM_2D` squelette : `var dt = 0, lastTime = 0;` déclarés GLOBALEMENT avant DOMContentLoaded. `gameLoop` fait maintenant `dt = Math.min(...)` (UPDATE, pas déclaration). Règle ⚠️ ajoutée dans `⛔ SYNTAXE JS INTERDITE` et dans le patcher SYSTEM.

**Bug 2 — Pre-patcher injecte `let enemies = []` en doublon**
- Cause : `agent_pre_patcher.py` cherchait `enemies` avec regex `\b(?:let|const|var)\s+enemies\b` mais ne trouvait pas l'assignment nu `enemies = []` ni les multi-déclarations `const enemies = [], bullets = []`
- Fix : Vérification étendue (bare assignment + `window.X`) + `fix_all_auto` appliqué sur le patch AVANT le check syntaxe dans `coordinateur.py`

**Bug 3 — Patcher introduit `Unexpected token ':'` dans WAVE_DEFS**
- Cause : snippet inséré au mauvais endroit casse la structure array
- Mitigation : circuit breaker existant (2 patches invalides → stop). Pas de fix programmatique possible, le circuit breaker est la bonne réponse.

### Fixes post-run "Astro Blitz" (6 patterns d'erreurs)

| # | Erreur | Fix |
|---|--------|-----|
| 1 | `Unexpected token ':'` — patcher corrompt WAVE_DEFS en cherchant BOSS_DEFS | `_find_keyword` bloque ALL_CAPS + `gameloop/update/draw/init` → jamais de snippet autour des data structures |
| 2 | `BOSS_DEFS`/`spawnPatterns` undeclared | Injection programmatique dans pre-patcher (`_ALLCAPS_STUBS`) : var BOSS_DEFS={}, spawnPatterns=[], etc. |
| 3 | `sfx.init is not a function` | `sfx.init(){}` dans SYSTEM_2D + `_fix_sfx_missing_methods()` dans code_validator (auto-inject méthodes no-op) |
| 4 | `chargeTimer`/`shootTimer` undefined | `_fix_enemy_timer_init()` dans code_validator : injecte `xTimer: 0` dans chaque `enemies.push({...})` |
| 5 | `dt is not defined` (23 erreurs) | `var dt=0, lastTime=0;` globaux dans SYSTEM_2D + règle ⚠️ E-G dans `_FORBIDDEN_JS_SYNTAX` |
| 6 | `enemies` redéclaré par pre-patcher | Vérification robuste (bare assignment) + `fix_all_auto` avant rejet lint |

### Fixes post-analyse 3 jeux échoués (Neon Cyber Assault, Crystal Keepers, Grid Guardians)

| # | Erreur | Fix |
|---|--------|-----|
| 7 | `player: '#0AF'` dans PALETTE → pre-patcher injecte `let player = null;` → `Unexpected token ':'` | Détection faux positif : si `cv_name` apparaît UNIQUEMENT comme clé d'objet (`player:`) et jamais en usage standalone (`player.x`, `player =`), skip injection |
| 8 | `getContext manquant` persist quand canvas nommé `c`/`gameCanvas` (pas `canvas`) | `_fix_missing_getcontext` : regex capte n'importe quel nom de variable canvas + fallback getElementById sur pattern `canvas` |
| 9 | `PATH_NODES`/`WAVE_DEFS`/`TOWER_DEFS`/`ENEMY_DEFS` undeclared (Tower Defense) | Ajout dans `_ALLCAPS_STUBS` du pre-patcher |
| 10 | `Unexpected token 'const'` persistant (Neon Cyber Assault — 5 patches, jamais résolus) | `fix_all_auto` boucle maintenant jusqu'à 10× sur `fix_const_syntax_errors` (chaque appel ne voit qu'UNE SyntaxError à la fois) |

### Fichiers modifiés dans cette mise à jour

| Fichier | Changement |
|---------|-----------|
| `agents/phase3/agent_createur.py` | `var dt=0, lastTime=0;` global + `sfx.init(){}` + règles E-G dans `_FORBIDDEN_JS_SYNTAX` |
| `agents/phase5/agent_patcher.py` | `_find_keyword` bloque ALL_CAPS et gameloop/update/draw/init/reset/start + règle dt dans SYSTEM |
| `agents/phase5/agent_pre_patcher.py` | `_ALLCAPS_STUBS` étendu (PATH_NODES, WAVE_DEFS, TOWER_DEFS, ENEMY_DEFS, MAP_DATA, TILE_DEFS) + faux positif objet-clé + `_fix_missing_getcontext` robuste |
| `coordinateur.py` | `fix_all_auto` appliqué au patch lint avant rejet |
| `code_validator.py` | `_fix_enemy_timer_init()` + `_fix_sfx_missing_methods()` + `_SFX_MISSING_METHODS` |
| `js_syntax_checker.py` | `fix_all_auto` boucle jusqu'à 10× sur `fix_const_syntax_errors` |

---

## Session principale : 2026-04-04

### Ce qui a été fait cette session

#### Plan 18 sessions — Reconstruction complète de la pipeline

Les 18 sessions ont été conçues pour résoudre le problème racine : `exec = 3.0/10` permanent sur tous les jeux, causé par des `SyntaxError: Unexpected token 'const'`. Ce problème bloquait la boucle d'apprentissage (RAG vide, aucun jeu sauvegardé après 53 générations).

**Sessions A–D (prompt hardening + fixes immédiats)**
- `_FORBIDDEN_JS_SYNTAX` injecté dans tous les prompts générateurs
- `_fix_const_in_switch_cases` + `_fix_for_const_loop` dans `code_validator.py`
- `fix_const_syntax_errors()` dans `js_syntax_checker.py` (Node.js line-precise fix)
- RAG threshold abaissé : 5.0+exec5 → basique, 6.0+approuvé → référence (était 7.5)

**Session 1 — Fix declared_str truncation**
- `agent_createur.py` passe 2 : `{declared_str[:400]}` → `{declared_str}` (évite redéclarations)

**Session 2 — Pre-eval gate (économie API)**
- `coordinateur.py` : run `agent_executeur` seul en premier, skip 4 agents LLM si exec < 4.5
- Économie ~60% des appels API sur les jeux cassés

**Session 3 — Régénération sur syntaxe persistante**
- Si syntaxe invalide après pre-patcher → régénération complète (max 2 fois)

**Session 4 — COMMON_VARS étendu**
- ~50 nouvelles variables auto-injectées : Tower Defense (`grid`, `towers`, `waveEnemies`, `path`...), RPG (`npcs`, `quests`, `dialogueActive`...), timers (`slowTimer`, `fireTimer`, `shootTimer`...), etc.

**Session 5 — Patcher prompt hardening**
- `agent_patcher.py` : `⛔ SYNTAXE JS INTERDITE` ajouté au SYSTEM

**Session 6 — Circuit breaker patcher**
- Arrêt après 2 patches consécutifs syntaxiquement invalides

**Session 7 — Smart stagnation**
- Stagnation + exec < 4.5 → régénération au lieu de stop

**Session 8 — Template Tower Defense** ✓
- `_TEMPLATE_TOWER_DEFENSE` ajouté dans `agent_createur.py`
- Grille, chemin, placement tours, vagues ennemis, économie, HUD
- `_TEMPLATES["tower"]` → Tower Defense (était Survival)

**Session 9 — _ensure_complete (déjà bien implémenté)**
- Déjà couvert : `_is_js_truncated`, retry genre complexe, fermeture manuelle accolades

**Session 10 — JS Linter auto-fix** ✓
- `fix_identifier_already_declared()` dans `js_syntax_checker.py`
- `fix_all_auto()` — cascade : const/let + identifiants redéclarés
- Toutes les utilisations de `fix_const_syntax_errors` → `fix_all_auto` dans `coordinateur.py` et `agent_createur.py`

**Session 11 — _fix_gamestateflow** ✓
- Fonction implémentée dans `code_validator.py` (l'appel existait mais la fonction était absente → NameError)
- Injecte transition `menu → playing` quand absente

**Session 12 — seed_rag.py** ✓
- Script standalone : lit tous les JSON de `jeux_sauvegardes/` → ChromaDB
- Usage : `python seed_rag.py --min-score 5.0`

**Session 13 — Error memory par genre (déjà implémenté)**
- `memory.save_validator_errors()` + `get_validator_errors_for_genre()` existaient déjà
- Utilisés dans `coordinateur.py` pour alimenter `erreurs_passees`

**Session 14 — Fallback minimal** ✓
- `_make_minimal_fallback_game(titre, genre)` dans `coordinateur.py`
- Shooter WASD + tir auto-visant, syntaxe garantie valide
- Exec score mesuré : **8.3/10**
- Déclenché quand toutes les itérations échouent avec code syntaxiquement invalide

**Session 15 — Health endpoint** ✓
- `GET /api/health` dans `app.py`
- Vérifie : Node.js, Playwright, ChromaDB, clé API Gemini, memory.json, save dir, sessions actives

**Session 16 — Regression tests** ✓
- `test_regression.py` — 16 tests sans appels API Gemini
- **16/16 passés** (dont exec fallback = 8.3/10 via Playwright)
- Usage : `python test_regression.py --fast` (rapide) ou sans flag (Playwright inclus)

---

### État de la pipeline après ces sessions

```
Avant les 18 sessions :
  exec moyen   : 3.0/10 (SyntaxError permanent)
  RAG          : 0 patterns (threshold trop haut)
  Jeux sauvés  : 0 (53 générations, 0 approuvé)
  Coût API     : 100% des appels même sur jeux cassés

Après les 18 sessions :
  exec moyen   : ???/10 (à valider via test_quick.py)
  RAG          : 0 patterns (seed_rag.py peut amorcer depuis jeux_sauvegardes/)
  Auto-fix     : const/let, for-const, redéclarations, gamestate flow
  Économie API : ~60% sur jeux cassés (pre-eval gate)
  Fallback     : jeu minimal garanti exec=8.3/10 si tout échoue
```

---

### Fichiers modifiés cette session

| Fichier | Changement |
|---------|-----------|
| `code_validator.py` | `_fix_gamestateflow()` implémentée (Session 11) |
| `js_syntax_checker.py` | `fix_identifier_already_declared()` + `fix_all_auto()` (Session 10) |
| `agents/phase3/agent_createur.py` | `_TEMPLATE_TOWER_DEFENSE` + `_TEMPLATES` mis à jour + `fix_all_auto` (Sessions 8, 10) |
| `coordinateur.py` | `_make_minimal_fallback_game()` + fallback trigger + `fix_all_auto` (Sessions 10, 14) |
| `app.py` | `GET /api/health` (Session 15) |
| `seed_rag.py` | Créé (Session 12) |
| `test_regression.py` | Créé (Session 16) |

---

### Ce qui reste à faire / surveiller

1. **Valider sur un vrai run** : lancer `python test_quick.py` pour mesurer l'exec moyen réel après toutes les sessions
2. **Amorcer le RAG** : `python seed_rag.py` si des jeux ont été sauvegardés
3. **Surveiller le fallback** : le jeu minimal est un shooter générique, pas adapté au genre demandé — éventuellement faire un fallback par genre

### À ne PAS faire

- Ne pas baisser `MAX_ITERATIONS` (actuellement 3) — les itérations sont utiles
- Ne pas modifier le threshold `SCORE_SEUIL_SAUVEGARDE = 6.0` sans raison
- Ne pas toucher `_make_minimal_fallback_game` sans re-runner `test_regression.py`

---

### Commandes utiles

```bash
# Tests de régression (sans API)
python test_regression.py --fast    # ~30s
python test_regression.py           # ~90s (avec Playwright)

# Test de la pipeline complète (appels Gemini)
python test_quick.py
python test_quick.py --genres tower shooter

# Amorcer le RAG depuis les jeux existants
python seed_rag.py --min-score 5.0

# Interface web
python app.py  → http://localhost:5000
python app.py  → http://localhost:5000/api/health   # santé pipeline

# CLI direct
python coordinateur.py "un shoot'em up spatial néon avec des boss"
```

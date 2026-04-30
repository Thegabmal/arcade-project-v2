# Arcade Project v2 — Rapport de Session

> **Usage :** Ce fichier est lu en début de chaque conversation et mis à jour en fin de session.
> Il reflète l'état ACTUEL du projet après toutes les modifications apportées.

---

## Dernière session : 2026-04-30 — DQ11-style rpg_narratif + fixes bugs combat

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

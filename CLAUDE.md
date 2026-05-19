# Arcade Project v2 — Référence Claude

## Vue d'ensemble

Système de génération de jeux HTML5/3D arcade via une pipeline multi-agents IA.
**Input :** prompt en langage naturel
**Output :** fichier HTML5 standalone (2D Canvas ou 3D Three.js), jouable dans un navigateur
**Modèle :** Google Gemini 2.5-Flash (+ Gemini Pro optionnel + Claude pour certains agents)
**Stack :** Python 3.14, google-genai, Flask, Playwright, ChromaDB

---

## Lancer le projet

```bash
# Interface web (recommandé)
python app.py
# → http://localhost:5000

# CLI direct
python coordinateur.py "un jeu de plateforme avec des robots"
```

---

## Architecture : Pipeline 5 phases

```
Prompt utilisateur
      ↓
[Phase 1] Modérat+Class → Intelligence Genre → Enrichissement → Architecte Modules
      ↓ GenreProfile + ModuleArchitecture
[Phase 2] Game Designer → Tech Architect → UX Designer → Level Designer → Game Logics → Scénariste
      ↓ ConceptionContext
[Phase 3] _layer_gen (template) | agent_createur (modulaire) → preflight_check → js_linter
      ↓ HTML5 validé
[Phase 4] Évaluation (6 agents) ←────────────────────────────────────────┐
      ↓ EvaluationBundle                                                   │
   score ≥ 8.5 ? → Succès anticipé                                        │
   stagnation ?  → Stop                                                    │
   sinon         → Diagnosticien → Pre-Patcher → Patcher (+ auto_fix_rules)┘
      ↓ (max 4 itérations)
[Phase 5] Agent Verdict Final (benchmark + neutre) → Agent Sauvegarde
      ↓
jeux_sauvegardes/<nom>.html + metadata.json  |  needs_review/<nom>.html
```

---

## Support 3D (Three.js)

**Détection automatique** dans `agent_moderateur_classificateur.py` via mots-clés :
- "3D", "three.js", "fps", "first-person", "third-person", "monde 3d", "en 3d"

**Propagation** :
- `GenreProfile.technologie_rendu` = `"threejs"` ou `"canvas2d"`
- `agent_tech_architect.py` : force `technologie_rendu: threejs` si 3D détecté
- Phase 3 : appelle `_layer_gen.run_from_template_3d` ou `agent_createur.run_modulaire`

**Dans l'interface**, le sélecteur "🎮 Jeu 3D (Three.js)" force le type.

---

## Agents par phase

### Phase 1 — Intelligence
| Agent | Rôle |
|-------|------|
| `agent_moderateur_classificateur` | Fusion modération + classification en un seul appel (valide prompt + identifie genre/tech) |
| `agent_intelligence_genre` | Fusion chercheur + veilleur — mécaniques, références, pièges, tendances |
| `agent_enrichisseur` | Synthèse → `GenreProfile` complet avec critères QC adaptatifs |
| `agent_architecte` | Décompose le jeu en modules JS indépendants → `ModuleArchitecture` |

### Phase 2 — Conception
| Agent | Rôle |
|-------|------|
| `agent_game_designer` | GDD (systèmes, personnages, progression) |
| `agent_tech_architect` | Specs techniques + choix Canvas2D/Three.js |
| `agent_ux_designer` | UI/UX, game feel, feedback visuel |
| `agent_level_designer` | Progression, difficulté, structure des niveaux |
| `agent_game_logics` | Mécaniques concrètes et implémentables (utilise Claude) |
| `agent_scenariste` | Contexte narratif optionnel (`NarrativeContext`) |

### Phase 3 — Génération
| Agent / Fichier | Rôle |
|-----------------|------|
| `_layer_gen.py` | **Chemin principal** — génération par couches depuis template. `run_from_template` (2D), `run_from_template_3d` (3D), `run_layered`, `_run_compact_fallback` |
| `agent_createur.py` | Chemin modulaire (`run_modulaire`) — fallback ou 3D complexe |
| `agent_assembleur.py` | Assemble les modules JS en un seul HTML (déterministe, sans LLM) |
| `agent_template.py` | Chargement et sélection du template selon genre |
| `preflight_check.py` | Vérification rapide (Playwright headless) avant la boucle d'évaluation |
| `agent_js_linter.py` | Lint statique du JS — détecte patterns d'erreurs LLM fréquents |

### Phase 4 — Évaluation (6 agents, poids dans le score global)
| Agent | Poids | Rôle |
|-------|-------|------|
| `agent_qc_technique` | 20% | Code, performance, architecture |
| `agent_qc_gameplay` | 25% | Mécaniques, équilibre, fun (inclut détection anti-patterns) |
| `agent_qc_visuel` | 15% | Cohérence visuelle, animations |
| `agent_executeur` | 20% | Test navigateur headless (Playwright) |
| `agent_playtester` | 15% | Simulation expérience joueur |
| `agent_testeur_modules` | — | Valide chaque module JS avant assemblage (statique + Playwright) |
| _(anti_pattern)_ | 3% | **Fusionné dans qc_gameplay** — pas d'agent séparé |
| _(benchmark)_ | 2% | **Fusionné dans agent_verdict_final** — pas d'agent séparé |

### Phase 5 — Itération + Finalisation
| Agent / Fichier | Rôle |
|-----------------|------|
| `agent_diagnosticien` | Analyse les issues du bundle → plan de correction ciblé |
| `agent_pre_patcher` | Applique les auto-fix rules avant le patch LLM |
| `agent_patcher` | Patch LLM ciblé sur les issues diagnostiquées |
| `_auto_fix_rules.py` | Règles de fix déterministes (appliquer avant chaque itération) |

### Support
| Agent | Rôle |
|-------|------|
| `agent_verdict_final` | Fusion benchmark + neutre — verdict final + score de comparaison genre |
| `agent_sauvegarde` | Sauvegarde HTML + metadata + patterns (ChromaDB) |
| `agent_auto_learner` | Apprend des échecs → `auto_learnings.json` |

---

## Modules de validation (hors agents)

| Fichier | Rôle |
|---------|------|
| `code_validator.py` | ~40 auto-fix déterministes sur le JS généré (pools, scopes, timers, etc.) |
| `js_syntax_checker.py` | Vérifie la syntaxe JS via Node.js + injecte des defaults pour vars indéfinies (A2) |
| `snippet_bank.py` | Banque de snippets réutilisables par genre |
| `patch_bank.py` | Banque de patches connus pour bugs récurrents |

---

## Interface Flask (app.py)

### Routes
| Route | Description |
|-------|-------------|
| `GET /` | Page principale (génération) |
| `GET /history` | Historique des jeux sauvegardés |
| `GET /play/<filename>` | Viewer du jeu (iframe + scores) |
| `GET /game-file/<filename>` | Sert le fichier HTML du jeu |
| `POST /api/generate` | Lance la génération → `{session_id}` |
| `GET /api/stream/<session_id>` | SSE — flux d'événements en temps réel |
| `GET /api/history` | JSON — liste des jeux sauvegardés |
| `GET /api/stats` | JSON — statistiques globales + RAG |

### SSE Events
```json
{"type": "connected"}
{"type": "phase_start", "data": {"phase": "PHASE1", "title": "..."}}
{"type": "agent_start", "data": {"agent": "Classificateur", "phase": "PHASE1", "description": "..."}}
{"type": "agent_done",  "data": {"agent": "Classificateur", "phase": "PHASE1", "result": "..."}}
{"type": "score",       "data": {"label": "QC Technique", "value": 8.5}}
{"type": "warning",     "data": {"message": "..."}}
{"type": "complete",    "data": {"score": 7.96, "approuve": true, "html_basename": "...", "titre": "..."}}
{"type": "end"}
```

### Sécurité
- Prompt limité à **500 caractères** (tronqué côté serveur)
- Nettoyage `<`, `>`, backticks avant passage à la pipeline
- Timeout **15 minutes** par génération (SSE queue.Empty)
- Threads daemon — pas de fuite de processus

---

## ChromaDB RAG (rag.py)

- **Stockage** : `rag_database/` (PersistentClient)
- **Collection** : `game_patterns` (similarité cosine)
- **Écriture** : `agent_sauvegarde.py` appelle `rag.store_pattern()` si score ≥ 7.5
- **Lecture** : Phase 3 appelle `rag.search_patterns()` pour enrichir les patterns
- **Fallback silencieux** : si ChromaDB indisponible, la pipeline continue sans RAG

---

## Streaming SSE — Logger

`logger.py` utilise `threading.local()` pour associer une `queue.Queue` à chaque thread de génération.
- `set_thread_event_queue(q)` — appelé par Flask avant de lancer `coordinateur.run()`
- `clear_thread_event_queue()` — appelé dans le `finally` du thread
- Chaque méthode Logger (`info`, `success`, `warning`, `error`, `score`, `section`, `agent_start`, `agent_done`) pousse un événement dans la queue

---

## Structures de données clés

**`GenreProfile`** — sortie Phase 1
- `technologie_rendu: str` — `"canvas2d"` ou `"threejs"`
- genre, sous-genre, mécaniques, style visuel, critères QC adaptatifs

**`ModuleArchitecture`** — sortie `agent_architecte` (Phase 1)
- Décomposition du jeu en modules JS nommés avec interfaces définies

**`ConceptionContext`** — sortie Phase 2
- Agrège GenreProfile + GDD + specs tech + UX + level design + logics + narratif

**`EvaluationBundle`** — sortie Phase 4
- Scores pondérés de 6 agents + anti_pattern + benchmark, issues par sévérité

---

## Configuration importante

**`coordinateur.py`**
```python
MAX_ITERATIONS = 4               # génération + 3 passes patch/fix
SCORE_SEUIL_SAUVEGARDE = 7.5    # minimum pour approuver
SCORE_SORTIE_ANTICIPEE = 8.5    # exit early sans itérer
SCORE_STAGNATION_DELTA = 0.2    # progrès < ceci → stagnation
SCORE_MIN_VIABLE_SAVE  = 2.0    # en-dessous, pas de sauvegarde
SCORE_NEEDS_REVIEW     = 5.0    # entre 5.0 et 7.5 → needs_review/
MAX_ITERATIONS_SANS_PROGRES = 2 # tolérance stagnation avant stop
SCORE_SEUIL_ITERATIONS_SUP = 7.5
```

**`config.py`**
```python
MODEL_NAME = "gemini-2.5-flash"
MODEL_NAME_PRO = "gemini-2.5-pro"  # optionnel via env GEMINI_PRO_MODEL
MAX_RETRIES = 2
CLAUDE_API_DELAY = 1.0  # pour les agents utilisant Claude
```

**`app.py`**
```python
MAX_PROMPT_LENGTH = 500
GENERATION_TIMEOUT = 900  # 15 minutes
```

---

## Standards des jeux générés

### Jeux 2D (Canvas)
- Fichier HTML unique sans dépendances
- Canvas 2D + requestAnimationFrame + delta time
- Machine à états, score, localStorage, responsive
- Basé sur templates dans `templates/game_templates/genres/`

### Jeux 3D (Three.js)
- Three.js via CDN (r160 / 0.160.0)
- WebGLRenderer plein écran responsive
- THREE.Clock pour delta time
- Caméra PerspectiveCamera (FPS/TPS/fixe selon genre)
- HUD HTML2D overlay sur le canvas 3D
- Pointer lock pour FPS

---

## État du projet

**Ce qui fonctionne :**
- Pipeline complète bout en bout sans crash
- Support 3D via Three.js (détection auto + génération)
- Évaluation multi-dimensionnelle adaptative (6 agents)
- Test navigateur headless Playwright
- `@with_fallback()` sur chaque agent
- ChromaDB RAG intégré (stockage + retrieval)
- Interface Flask avec SSE temps réel
- 3 pages : génération, viewer jeu, historique avec Chart.js
- Dark arcade theme (Press Start 2P + Orbitron)
- Auto-fix pipeline : ~40 règles déterministes dans `code_validator.py`
- JS linter : détection patterns LLM (orphan state functions, helpers manquants, etc.)
- Auto-learner : apprentissage des patterns d'échec → `auto_learnings.json`
- Sprint 1 anti-hallucination rules : R1–R6 implémentées (2026-05-18)

**Ce qui reste à améliorer :**
- ChromaDB a besoin d'embeddings : si `sentence-transformers` non installé, fallback auto
- Pas de concurrence limitée (plusieurs générations simultanées possibles)
- French → English sweep sur tous les fichiers Python (strings de prompt encore en français)
- Cycle runs genres (Tower Defense → Match-3 → FPS 3D → 3D Platformer → Bullet Hell 3D) pour extraire de nouvelles règles

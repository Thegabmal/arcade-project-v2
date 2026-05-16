# Arcade Project v2 — Référence Claude

## Vue d'ensemble

Système de génération de jeux HTML5/3D arcade via une pipeline multi-agents IA.
**Input :** prompt en langage naturel
**Output :** fichier HTML5 standalone (2D Canvas ou 3D Three.js), jouable dans un navigateur
**Modèle :** Google Gemini 2.5-Flash
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
[Phase 1] Modération → Classification (2D/3D détecté) → Recherche → Enrichissement
      ↓ GenreProfile (avec technologie_rendu: canvas2d | threejs)
[Phase 2] Game Designer → Tech Architect (Three.js si 3D) → UX Designer → Level Designer
      ↓ ConceptionContext
[Phase 3] Agent Créateur → HTML5 Game Code (Canvas 2D ou Three.js 3D)
      ↓
[Phase 4] Évaluation (7 agents) ←──────────────────────┐
      ↓ EvaluationBundle                                │
   score ≥ 8.5 ? → Succès anticipé                     │
   stagnation ?  → Stop                                 │
   sinon         → Diagnosticien → Patcher ─────────────┘
      ↓ (max 3 itérations)
[Phase 5] Agent Neutre → Agent Sauvegarde (→ ChromaDB + memory.json)
      ↓
jeux_sauvegardes/<nom>.html + metadata.json
```

---

## Support 3D (Three.js)

**Détection automatique** dans `agent_classificateur.py` via mots-clés :
- "3D", "three.js", "fps", "first-person", "third-person", "monde 3d", "en 3d"

**Propagation** :
- `GenreProfile.technologie_rendu` = `"threejs"` ou `"canvas2d"`
- `agent_tech_architect.py` : force `technologie_rendu: threejs` si 3D détecté, autorise Three.js dans les contraintes
- `agent_createur.py` : utilise `SYSTEM_3D` + exigences Three.js (CDN r160 / 0.160.0, WebGLRenderer, THREE.Clock, etc.)

**Dans l'interface**, le sélecteur "🎮 Jeu 3D (Three.js)" force le type.

---

## Agents par phase

### Phase 1 — Intelligence
| Agent | Rôle |
|-------|------|
| `agent_moderateur` | Valide le prompt (contenu, faisabilité) |
| `agent_classificateur` | Identifie genre + détecte si 3D |
| `agent_chercheur` | Recherche mécaniques, références, pièges du genre |
| `agent_enrichisseur` | Synthèse → `GenreProfile` complet |

### Phase 2 — Conception
| Agent | Rôle |
|-------|------|
| `agent_game_designer` | GDD (systèmes, personnages, progression) |
| `agent_tech_architect` | Specs techniques + choix Canvas2D/Three.js |
| `agent_ux_designer` | UI/UX, game feel, feedback visuel |
| `agent_level_designer` | Progression, difficulté, structure des niveaux |

### Phase 3 — Génération
| Agent | Rôle |
|-------|------|
| `agent_createur` | Génère HTML5 Canvas 2D ou Three.js 3D complet |

### Phase 4 — Évaluation (7 agents, poids dans le score global)
| Agent | Poids | Rôle |
|-------|-------|------|
| `agent_qc_technique` | 20% | Code, performance, architecture |
| `agent_qc_gameplay` | 25% | Mécaniques, équilibre, fun |
| `agent_qc_visuel` | 15% | Cohérence visuelle, animations |
| `agent_executeur` | 20% | Test navigateur headless (Playwright) |
| `agent_playtester` | 15% | Simulation expérience joueur |
| `agent_anti_pattern` | 3% | Détection anti-patterns (fusionné dans qc_gameplay) |
| `agent_benchmark` | 2% | Comparaison standards du genre (via agent_verdict_final) |

### Phase 5 — Finalisation
| Agent | Rôle |
|-------|------|
| `agent_neutre` | Verdict indépendant final |
| `agent_sauvegarde` | Sauvegarde HTML + metadata + patterns (memory.json + ChromaDB) |

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
- **Lecture** : `agent_createur.py` appelle `rag.search_patterns()` pour enrichir les patterns
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
- `technologie_rendu: str` — `"canvas2d"` ou `"threejs"` ← nouveau
- genre, sous-genre, mécaniques, style visuel, critères QC adaptatifs

**`ConceptionContext`** — sortie Phase 2
- Agrège GenreProfile + GDD + specs tech + UX + level design

**`EvaluationBundle`** — sortie Phase 4
- Scores pondérés de 7 agents, issues par sévérité

---

## Configuration importante

**`coordinateur.py`**
```python
MAX_ITERATIONS = 4
SCORE_SEUIL_SAUVEGARDE = 7.5
SCORE_SORTIE_ANTICIPEE = 8.5
SCORE_SEUIL_ITERATIONS_SUP = 7.5
SCORE_STAGNATION_DELTA = 0.2
```

**`config.py`**
```python
MODEL_NAME = "gemini-2.5-flash"
API_DELAY = 3.0       # secondes entre appels
MAX_RETRIES = 5
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
- Évaluation multi-dimensionnelle adaptative
- Test navigateur headless Playwright
- `@with_fallback()` sur chaque agent
- ChromaDB RAG intégré (stockage + retrieval)
- Interface Flask avec SSE temps réel
- 3 pages : génération, viewer jeu, historique avec Chart.js
- Dark arcade theme (Press Start 2P + Orbitron)

**Ce qui reste à améliorer :**
- ChromaDB a besoin d'embeddings : si `sentence-transformers` non installé, fallback auto
- `patterns_reussis.json` vide (se remplit après premier run ≥ 7.5)
- Pas de concurrence limitée (plusieurs générations simultanées possibles)
- Test runs à faire pour valider le pipeline complet (graphics overhaul + gates + genre checklist)
- French → English sweep sur tous les fichiers Python (strings de prompt encore en français)

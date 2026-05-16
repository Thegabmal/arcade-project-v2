"""
RAG — ChromaDB integration.
Stores and retrieves patterns from successful games to improve generation.
Silent fallback if ChromaDB is unavailable.
"""

import os
import json
import datetime

RAG_DIR = "rag_database"

_client = None
_collection = None
_available = None  # None = non testé, True/False = résultat du test

# ── Collection mechanics_kb ──────────────────────────────────────────────────
_mech_client = None
_mech_collection = None
_mech_available = None


def _get_mechanics_collection():
    global _mech_client, _mech_collection, _mech_available

    if _mech_available is False:
        return None
    if _mech_collection is not None:
        return _mech_collection

    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        _mech_client = chromadb.PersistentClient(path=RAG_DIR)
        _mech_collection = _mech_client.get_or_create_collection(
            name="mechanics_kb",
            metadata={"hnsw:space": "cosine"},
        )
        _mech_available = True
        return _mech_collection
    except Exception as e:
        _mech_available = False
        print(f"  [MechanicsKB] ChromaDB indisponible : {e}")
        return None


def store_mechanic(game_name: str, genre: str, document: str, publisher: str = "", year: int = 0) -> bool:
    """Stocke les mécaniques d'un jeu dans la collection mechanics_kb. Retourne True si succès."""
    collection = _get_mechanics_collection()
    if collection is None:
        return False

    try:
        doc_id = f"mech_{genre}_{game_name.replace(' ', '_').replace('/', '_')[:40]}"
        metadata = {
            "genre": genre,
            "game_name": game_name,
            "publisher": publisher,
            "year": year,
        }
        collection.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])
        return True
    except Exception as e:
        print(f"  [MechanicsKB] Erreur stockage {game_name} : {e}")
        return False


def search_mechanics(genre: str, query: str, n: int = 3) -> list:
    """
    Cherche les mécaniques pertinentes dans la collection mechanics_kb par similarité sémantique.
    Filtre d'abord par genre, puis fallback sans filtre si vide.
    Retourne une liste de dicts {game_name, genre, publisher, year, document}.
    """
    collection = _get_mechanics_collection()
    if collection is None:
        return []

    try:
        count = collection.count()
        if count == 0:
            return []

        where = {"genre": {"$eq": genre}} if genre else None
        actual_n = n

        if where:
            genre_items = collection.get(where=where)
            genre_count = len(genre_items["ids"])
            if genre_count == 0:
                where = None
            else:
                actual_n = min(n, genre_count)

        actual_n = min(actual_n, count)
        if actual_n == 0:
            return []

        results = collection.query(
            query_texts=[f"{genre} {query}"],
            n_results=actual_n,
            where=where,
        )

        mechanics = []
        if results and results.get("metadatas") and results.get("documents"):
            for meta, doc in zip(results["metadatas"][0], results["documents"][0]):
                entry = dict(meta)
                entry["document"] = doc
                mechanics.append(entry)

        return mechanics

    except Exception as e:
        print(f"  [MechanicsKB] Erreur recherche : {e}")
        return []


def _get_collection():
    global _client, _collection, _available

    if _available is False:
        return None
    if _collection is not None:
        return _collection

    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=RAG_DIR)
        _collection = _client.get_or_create_collection(
            name="game_patterns",
            metadata={"hnsw:space": "cosine"},
        )
        _available = True
        return _collection
    except Exception as e:
        _available = False
        print(f"  [RAG] ChromaDB indisponible : {e}")
        return None


def store_pattern(
    genre: str,
    sous_genre: str,
    description: str,
    score: float,
    mecaniques: list,
    style_visuel: str,
    boucle_core: str,
    code_snippet: str = "",
    notes: str = "",
) -> bool:
    """Stocke un pattern réussi dans ChromaDB. Retourne True si succès."""
    if score < 7.5:
        print(f"  [RAG] Pattern rejeté — score {score:.2f} < 7.5 (seuil qualité)")
        return False

    collection = _get_collection()
    if collection is None:
        return False

    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        doc_id = f"{genre}_{sous_genre}_{ts}"[:64]

        document = (
            f"{genre} {sous_genre}: {boucle_core} {description} "
            f"Mécaniques: {', '.join(mecaniques[:5])} Style: {style_visuel}"
        )
        metadata = {
            "genre": genre,
            "sous_genre": sous_genre,
            "score": float(score),
            "style_visuel": style_visuel,
            "boucle_core": boucle_core[:200],
            "notes": notes[:200],
            "mecaniques": json.dumps(mecaniques[:10]),
            "code_snippet": code_snippet[:300],
        }

        collection.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])
        return True

    except Exception as e:
        print(f"  [RAG] Erreur stockage : {e}")
        return False


def search_patterns(query: str, genre: str = "", n_results: int = 5) -> list:
    """Cherche les patterns pertinents par similarité sémantique."""
    collection = _get_collection()
    if collection is None:
        return []

    try:
        count = collection.count()
        if count == 0:
            return []

        actual_n = min(n_results, count)
        where = {"genre": {"$eq": genre}} if genre else None

        # Si filtre genre mais pas de résultats, retomber sans filtre
        if where:
            genre_count = len(collection.get(where=where)["ids"])
            if genre_count == 0:
                where = None
            else:
                actual_n = min(actual_n, genre_count)

        results = collection.query(
            query_texts=[query],
            n_results=actual_n,
            where=where,
        )

        patterns = []
        if results and results.get("metadatas"):
            for meta in results["metadatas"][0]:
                # Filter out low-quality patterns at retrieval time
                if float(meta.get("score", 0)) < 7.5:
                    continue
                p = dict(meta)
                if "mecaniques" in p:
                    try:
                        p["mecaniques"] = json.loads(p["mecaniques"])
                    except Exception:
                        p["mecaniques"] = []
                patterns.append(p)
        return patterns

    except Exception as e:
        print(f"  [RAG] Erreur recherche : {e}")
        return []


# ── Collection code_snippets ──────────────────────────────────────────────────
_snippets_client = None
_snippets_collection = None
_snippets_available = None


def _get_snippets_collection():
    global _snippets_client, _snippets_collection, _snippets_available
    if _snippets_available is False:
        return None
    if _snippets_collection is not None:
        return _snippets_collection
    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        _snippets_client = chromadb.PersistentClient(path=RAG_DIR)
        _snippets_collection = _snippets_client.get_or_create_collection(
            name="code_snippets",
            metadata={"hnsw:space": "cosine"},
        )
        _snippets_available = True
        return _snippets_collection
    except Exception as e:
        _snippets_available = False
        return None


def store_code_snippet(game_name: str, genre: str, snippet_type: str, code: str, score: float = 0.0) -> bool:
    """
    Stocke un extrait de code fonctionnel d'un jeu réussi.
    snippet_type: 'gameloop', 'collision', 'enemy_ai', 'draw', 'full_update', etc.
    """
    collection = _get_snippets_collection()
    if collection is None:
        return False
    if not code or len(code) < 50:
        return False
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:17]
        doc_id = f"snip_{genre}_{snippet_type}_{game_name.replace(' ', '_')[:20]}_{ts}"
        metadata = {
            "genre": genre,
            "game_name": game_name,
            "snippet_type": snippet_type,
            "score": score,
            "char_count": len(code),
        }
        # Truncate code to 3000 chars for embedding efficiency
        collection.upsert(ids=[doc_id], documents=[code[:3000]], metadatas=[metadata])
        return True
    except Exception:
        return False


def search_code_snippets(genre: str, snippet_type: str, n: int = 2) -> list[dict]:
    """
    Récupère des extraits de code similaires pour un genre/type donné.
    Retourne liste de dicts {game_name, genre, snippet_type, score, code}.
    """
    collection = _get_snippets_collection()
    if collection is None:
        return []
    try:
        count = collection.count()
        if count == 0:
            return []
        query = f"{genre} {snippet_type} game javascript canvas"
        where = {"genre": {"$eq": genre}}
        try:
            results = collection.query(query_texts=[query], n_results=min(n, count), where=where)
        except Exception:
            results = collection.query(query_texts=[query], n_results=min(n, count))

        snippets = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            snippets.append({
                "game_name": meta.get("game_name", ""),
                "genre": meta.get("genre", ""),
                "snippet_type": meta.get("snippet_type", ""),
                "score": meta.get("score", 0),
                "code": doc,
            })
        return snippets
    except Exception:
        return []


def get_stats() -> dict:
    """Retourne les stats de la base RAG (game_patterns + mechanics_kb)."""
    collection = _get_collection()
    mech_collection = _get_mechanics_collection()
    snippets_collection = _get_snippets_collection()
    bug_fixes_collection = _get_bug_fixes_collection()

    patterns_count = 0
    mechanics_count = 0
    snippets_count = 0
    bug_fixes_count = 0
    available = False

    try:
        if collection is not None:
            patterns_count = collection.count()
            available = True
    except Exception:
        pass

    try:
        if mech_collection is not None:
            mechanics_count = mech_collection.count()
            available = True
    except Exception:
        pass

    try:
        if snippets_collection is not None:
            snippets_count = snippets_collection.count()
            available = True
    except Exception:
        pass

    try:
        if bug_fixes_collection is not None:
            bug_fixes_count = bug_fixes_collection.count()
            available = True
    except Exception:
        pass

    return {
        "available": available,
        "total_patterns": patterns_count,
        "total_mechanics": mechanics_count,
        "total_snippets": snippets_count,
        "total_bug_fixes": bug_fixes_count,
    }


# ── Collection bug_fixes ──────────────────────────────────────────────────────
_bf_client = None
_bf_collection = None
_bf_available = None

# Seed data: known LLM game bug patterns with fixes.
# Indexed by semantic similarity — pre-patcher queries this before calling LLM.
_BUG_FIX_SEEDS = [
    {
        "id": "bug_loop_variable_b",
        "document": "ReferenceError b is not defined bullets loop for loop variable missing declaration",
        "category": "loop_variable_missing",
        "symptom": "ReferenceError: b is not defined",
        "buggy_pattern": "for (let i = bullets.length - 1; i >= 0; i--) { if (b.active) {",
        "fix_pattern": "for (let i = bullets.length - 1; i >= 0; i--) { const b = bullets[i]; if (b.active) {",
        "explanation": "Loop body uses 'b' without declaring it. Add 'const b = array[i];' as first line of loop body.",
        "game_type": "both",
    },
    {
        "id": "bug_loop_variable_e",
        "document": "ReferenceError e is not defined enemies loop for loop variable missing declaration",
        "category": "loop_variable_missing",
        "symptom": "ReferenceError: e is not defined",
        "buggy_pattern": "for (let i = enemies.length - 1; i >= 0; i--) { if (e.active) {",
        "fix_pattern": "for (let i = enemies.length - 1; i >= 0; i--) { const e = enemies[i]; if (e.active) {",
        "explanation": "Loop body uses 'e' without declaring it. Add 'const e = array[i];' as first line of loop body.",
        "game_type": "both",
    },
    {
        "id": "bug_loop_variable_p",
        "document": "ReferenceError p is not defined particles powerUps loop for loop variable missing declaration",
        "category": "loop_variable_missing",
        "symptom": "ReferenceError: p is not defined",
        "buggy_pattern": "for (let i = particles.length - 1; i >= 0; i--) { p.life -= dt;",
        "fix_pattern": "for (let i = particles.length - 1; i >= 0; i--) { const p = particles[i]; p.life -= dt;",
        "explanation": "Loop body uses 'p' without declaring it. Add 'const p = array[i];' as first line.",
        "game_type": "both",
    },
    {
        "id": "bug_let_dot_notation",
        "document": "SyntaxError Unexpected token . let const var dot notation namespace property assignment",
        "category": "let_dot_notation",
        "symptom": "SyntaxError: Unexpected token '.'",
        "buggy_pattern": "let GameName.gameState = 'menu'; const GameName.score = 0;",
        "fix_pattern": "GameName.gameState = 'menu'; GameName.score = 0;",
        "explanation": "JavaScript does not allow let/const/var before dot-notation. Remove the keyword: 'let X.Y = v' → 'X.Y = v'",
        "game_type": "3d",
    },
    {
        "id": "bug_dt_parameter_nan",
        "document": "canvas blue screen invisible nothing renders globalAlpha 0.08 drawBackground dt undefined NaN createRadialGradient",
        "category": "dt_parameter_missing",
        "symptom": "Canvas shows body background only (blue screen), globalAlpha stuck at 0.08",
        "buggy_pattern": "function gameLoop(timestamp) { ... drawBackground(); drawMenu(); }",
        "fix_pattern": "function gameLoop(timestamp) { ... drawBackground(dt); drawMenu(dt); }",
        "explanation": "Drawing functions declare 'dt' as parameter but callers omit it. dt=undefined → _bgTimer=NaN → createRadialGradient(NaN) throws inside ctx.save() → ctx.restore() skipped → globalAlpha=0.08 forever.",
        "game_type": "2d",
    },
    {
        "id": "bug_ctx_before_init",
        "document": "TypeError Cannot read properties of undefined reading createLinearGradient ctx undefined canvas before initialization DOMContentLoaded",
        "category": "ctx_before_init",
        "symptom": "TypeError: Cannot read properties of undefined (reading 'createLinearGradient')",
        "buggy_pattern": "document.addEventListener('DOMContentLoaded', () => { var gradient = ctx.createLinearGradient(0,0,W,H); var canvas = ...; var ctx = canvas.getContext('2d');",
        "fix_pattern": "Remove the ctx.createLinearGradient line — ctx is not yet defined at that point.",
        "explanation": "ctx is used before canvas is initialized. Remove or move any ctx usage to after 'var ctx = canvas.getContext(\"2d\")'.",
        "game_type": "2d",
    },
    {
        "id": "bug_iife_module_3d",
        "document": "ReferenceError init is not defined gameLoop is not defined IIFE module pattern functions not global three.js 3D",
        "category": "iife_module_3d",
        "symptom": "ReferenceError: init is not defined / gameLoop is not defined",
        "buggy_pattern": "let core = (() => { function init() { ... } return { init }; })();",
        "fix_pattern": "function init() { ... } // declared globally, NOT inside IIFE",
        "explanation": "LLM wraps 3D modules as IIFE. Functions inside IIFE are not global. Use plain function declarations at top level.",
        "game_type": "3d",
    },
    {
        "id": "bug_ui_initui_before_setstate",
        "document": "TypeError Cannot read properties of undefined reading style hudElement undefined ui.showMenu setState before initUI three.js 3D",
        "category": "ui_init_order",
        "symptom": "TypeError: Cannot read properties of undefined (reading 'style')",
        "buggy_pattern": "function init() { setState('MENU'); } // ui.initUI() never called first",
        "fix_pattern": "function init() { if (typeof ui !== 'undefined' && ui.initUI) ui.initUI(); setState('MENU'); }",
        "explanation": "ui.initUI() must be called before any setState(). setState triggers ui.showMenu() which accesses DOM elements only created by ui.initUI().",
        "game_type": "3d",
    },
    {
        "id": "bug_undefined_hud_vars",
        "document": "ReferenceError hpBarX hpBarY hpBarWidth hpFillWidth hpGradient undefined drawHUD function",
        "category": "undefined_draw_vars",
        "symptom": "ReferenceError: hpBarX is not defined (or similar HUD variable)",
        "buggy_pattern": "function drawHUD() { ctx.fillRect(hpBarX, hpBarY, hpFillWidth, 20); }",
        "fix_pattern": "function drawHUD() { var hpBarX = W/2-75; var hpBarY = 20; var hpBarWidth = 150; var hpRatio = Math.min(1, player.hp / player.maxHp); var hpFillWidth = hpBarWidth * hpRatio; ctx.fillRect(hpBarX, hpBarY, hpFillWidth, 20); }",
        "explanation": "HUD drawing variables must be declared inside the function that uses them, not assumed to exist globally.",
        "game_type": "2d",
    },
    {
        "id": "bug_wrong_loop_alias",
        "document": "ReferenceError e is not defined enemy declared but e used variable name mismatch drawEnemies",
        "category": "loop_variable_alias_mismatch",
        "symptom": "ReferenceError: e is not defined (despite 'enemy' being declared)",
        "buggy_pattern": "for (let i = 0; i < enemies.length; i++) { const enemy = enemies[i]; ctx.fillRect(e.x, e.y);",
        "fix_pattern": "for (let i = 0; i < enemies.length; i++) { const e = enemies[i]; ctx.fillRect(e.x, e.y);",
        "explanation": "Declaration uses 'enemy' but code uses 'e'. Change declaration alias to match usage.",
        "game_type": "both",
    },
]


def _get_bug_fixes_collection():
    global _bf_client, _bf_collection, _bf_available
    if _bf_available is False:
        return None
    if _bf_collection is not None:
        return _bf_collection
    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        _bf_client = chromadb.PersistentClient(path=RAG_DIR)
        _bf_collection = _bf_client.get_or_create_collection(
            name="bug_fixes",
            metadata={"hnsw:space": "cosine"},
        )
        _bf_available = True
        # Auto-seed on first creation
        if _bf_collection.count() == 0:
            seed_bug_fixes()
        return _bf_collection
    except Exception as e:
        _bf_available = False
        return None


def seed_bug_fixes(force: bool = False) -> int:
    """Seeds the bug_fixes collection with known LLM game bug patterns.
    Returns number of patterns seeded. Skips if already seeded (unless force=True).
    """
    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        client = chromadb.PersistentClient(path=RAG_DIR)
        collection = client.get_or_create_collection(
            name="bug_fixes",
            metadata={"hnsw:space": "cosine"},
        )
        if collection.count() > 0 and not force:
            return 0

        ids, documents, metadatas = [], [], []
        for seed in _BUG_FIX_SEEDS:
            ids.append(seed["id"])
            documents.append(seed["document"])
            metadatas.append({
                "category": seed["category"],
                "symptom": seed["symptom"],
                "buggy_pattern": seed["buggy_pattern"][:300],
                "fix_pattern": seed["fix_pattern"][:500],
                "explanation": seed["explanation"][:400],
                "game_type": seed["game_type"],
            })

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)
    except Exception as e:
        print(f"  [BugFixes] Seed failed: {e}")
        return 0


def search_bug_fixes(error_message: str, n: int = 2) -> list[dict]:
    """Query bug_fixes collection for relevant fix examples.
    Returns list of dicts with category, symptom, buggy_pattern, fix_pattern, explanation.
    """
    collection = _get_bug_fixes_collection()
    if collection is None:
        return []
    try:
        count = collection.count()
        if count == 0:
            return []
        results = collection.query(
            query_texts=[error_message],
            n_results=min(n, count),
        )
        fixes = []
        if results and results.get("metadatas"):
            for meta in results["metadatas"][0]:
                fixes.append(dict(meta))
        return fixes
    except Exception:
        return []


def store_bug_fix(
    category: str,
    symptom: str,
    buggy_pattern: str,
    fix_pattern: str,
    explanation: str,
    game_type: str = "both",
) -> bool:
    """Store a new discovered bug fix pattern in the bug_fixes collection."""
    collection = _get_bug_fixes_collection()
    if collection is None:
        return False
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:17]
        doc_id = f"bug_{category}_{ts}"
        document = f"{symptom} {explanation} {category} {game_type}"
        metadata = {
            "category": category,
            "symptom": symptom,
            "buggy_pattern": buggy_pattern[:300],
            "fix_pattern": fix_pattern[:500],
            "explanation": explanation[:400],
            "game_type": game_type,
        }
        collection.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])
        return True
    except Exception:
        return False

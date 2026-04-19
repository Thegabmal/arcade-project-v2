"""
RAG — ChromaDB integration.
Stocke et récupère les patterns de jeux réussis pour améliorer la génération.
Fallback silencieux si ChromaDB est indisponible.
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

    patterns_count = 0
    mechanics_count = 0
    snippets_count = 0
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

    return {
        "available": available,
        "total_patterns": patterns_count,
        "total_mechanics": mechanics_count,
        "total_snippets": snippets_count,
    }

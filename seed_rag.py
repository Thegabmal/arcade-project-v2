"""
Session 12 — Seed RAG manuel
Lit tous les jeux sauvegardés dans jeux_sauvegardes/ et injecte les patterns
dans ChromaDB pour amorcer la boucle d'apprentissage sans attendre de nouveaux runs.

Usage :
    python seed_rag.py                 # All saved games
    python seed_rag.py --min-score 6.0 # Only games with score >= 6.0
    python seed_rag.py --dry-run       # Show what would be seeded without writing
"""

import os
import json
import argparse
import sys

SAVE_DIR = "jeux_sauvegardes"


def seed_rag(min_score: float = 5.0, dry_run: bool = False) -> int:
    try:
        import rag
    except ImportError:
        print("[ERROR] Cannot import rag.py — run from the project root")
        sys.exit(1)

    json_files = sorted(
        [f for f in os.listdir(SAVE_DIR) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(SAVE_DIR, f))
    )
    if not json_files:
        print(f"[seed_rag] No JSON metadata files in {SAVE_DIR}/")
        return 0

    seeded = 0
    skipped = 0
    for fname in json_files:
        fpath = os.path.join(SAVE_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            print(f"[SKIP] {fname}: JSON read error — {e}")
            continue

        score = meta.get("scores", {}).get("global", 0.0)
        if score < min_score:
            skipped += 1
            continue

        genre = meta.get("genre", "unknown")
        sous_genre = meta.get("sous_genre", "")
        description = meta.get("concept", "") or meta.get("prompt_original", "")[:200]
        notes = ""
        verdict = meta.get("verdict", {})
        if isinstance(verdict, dict):
            pts = verdict.get("points_forts", [])
            notes = pts[0] if pts else ""
        approuve = meta.get("approuve", False)
        tag = "approuve" if (approuve and score >= 6.0) else "basique"

        # Lire le code HTML du jeu
        html_file = meta.get("html_file", "")
        code_snippet = ""
        if html_file and os.path.exists(html_file):
            try:
                with open(html_file, encoding="utf-8") as hf:
                    code_snippet = hf.read()[:300]
            except Exception:
                pass
        elif not html_file:
            # Chercher le fichier HTML correspondant
            html_candidate = fpath.replace(".json", ".html")
            if os.path.exists(html_candidate):
                try:
                    with open(html_candidate, encoding="utf-8") as hf:
                        code_snippet = hf.read()[:300]
                except Exception:
                    pass

        if dry_run:
            print(f"[DRY-RUN] Would seed: {genre} — {meta.get('titre','?')} (score {score:.1f}) [{tag}]")
            seeded += 1
            continue

        try:
            rag.store_pattern(
                genre=genre,
                sous_genre=sous_genre,
                description=description,
                score=score,
                mecaniques=[],  # not stored in metadata
                style_visuel=meta.get("genre_profile_summary", {}).get("style_visuel", "") if isinstance(meta.get("genre_profile_summary"), dict) else "",
                boucle_core=meta.get("genre_profile_summary", {}).get("boucle_core", "") if isinstance(meta.get("genre_profile_summary"), dict) else "",
                code_snippet=code_snippet,
                notes=f"[{tag}] {notes}",
            )
            seeded += 1
            print(f"  ✓ {genre} — {meta.get('titre','?')} (score {score:.1f}) [{tag}]")
        except Exception as e:
            print(f"[WARN] {fname}: RAG store failed — {e}")

    if not dry_run:
        print(f"\n[seed_rag] Done — {seeded} games seeded, {skipped} skipped (score < {min_score})")
    else:
        print(f"\n[seed_rag] Dry-run — {seeded} games would be seeded, {skipped} skipped (score < {min_score})")
    return seeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed ChromaDB RAG from saved games")
    parser.add_argument("--min-score", type=float, default=5.0, help="Minimum score to seed (default: 5.0)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be seeded without writing")
    args = parser.parse_args()
    seed_rag(min_score=args.min_score, dry_run=args.dry_run)

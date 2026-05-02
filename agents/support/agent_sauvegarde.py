"""
Save Agent — Support
Saves the final game and its metadata.
Extracts successful patterns to improve future generations.
"""

import os
import re
import re as _re_snip
import json
import datetime
from genre_profile import GenreProfile, EvaluationBundle
import memory
import rag
import snippet_bank
import genre_profiler

SAVE_DIR = "jeux_sauvegardes"


def run(
    code: str,
    genre_profile: GenreProfile,
    gdd: dict,
    bundle: EvaluationBundle,
    verdict: dict,
    duree_secondes: float = 0.0,
    log_content: str = "",
    approuve: bool = True,
) -> str:
    """Sauvegarde le jeu et retourne le chemin du fichier HTML."""
    os.makedirs(SAVE_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    import unicodedata
    titre_raw = gdd.get("titre", "jeu")
    # Normaliser les accents (é→e, ç→c…) puis ne garder que les alphanumériques et underscores
    titre_normalized = unicodedata.normalize("NFD", titre_raw)
    titre_normalized = "".join(c for c in titre_normalized if unicodedata.category(c) != "Mn")
    titre_safe = re.sub(r"[^\w]", "_", titre_normalized.lower())[:20].strip("_")
    titre_safe = titre_safe or "jeu"
    filename_base = f"{titre_safe}_{timestamp}"

    # Injecter la dev console si absente (obligatoire pour tout jeu sauvegardé)
    import utils_dev_console
    code = utils_dev_console.inject(code)

    # Nettoyage post-injection : corrige les éventuels sauts de ligne littéraux dans strings JS
    from js_syntax_checker import fix_literal_newlines_in_strings as _fix_nl
    code, _nl_fixed, _ = _fix_nl(code)

    # Sauvegarder le HTML
    html_path = os.path.join(SAVE_DIR, f"{filename_base}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(code)

    # Sauvegarder le log de la pipeline
    if log_content:
        log_path = os.path.join(SAVE_DIR, f"{filename_base}_log.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_content)

    # Sauvegarder les métadonnées
    duree_int = int(duree_secondes)
    metadata = {
        "titre": gdd.get("titre", "?"),
        "date": datetime.datetime.now().isoformat(),
        "prompt_original": genre_profile.prompt_utilisateur_original,
        "genre": genre_profile.genre_principal,
        "sous_genre": genre_profile.sous_genre,
        "ton": genre_profile.ton,
        "concept": gdd.get("concept", ""),
        "duree_secondes": duree_int,
        "approuve": approuve,
        "scores": {
            "technique": bundle.qc_technique.score,
            "gameplay": bundle.qc_gameplay.score,
            "visuel": bundle.qc_visuel.score,
            "execution": bundle.execution.score,
            "playtester": bundle.playtester.score,
            "anti_pattern": bundle.anti_pattern.score,
            "benchmark": bundle.benchmark.score,
            "global": bundle.score_global(),
        },
        "verdict": verdict,
        "html_file": html_path,
        "genre_profile_summary": genre_profile.summary(),
    }

    json_path = os.path.join(SAVE_DIR, f"{filename_base}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        # Ne pas laisser un bug JSON bloquer la sauvegarde du HTML
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"error": str(e), "titre": metadata.get("titre", "?"),
                       "scores": metadata.get("scores", {}), "approuve": metadata.get("approuve")},
                      f, ensure_ascii=False, indent=2)

    # Sauvegarder en mémoire
    memory.save_session(
        prompt=genre_profile.prompt_utilisateur_original,
        genre_profile=genre_profile,
        score_global=bundle.score_global(),
        saved=approuve,
        filename=html_path,
    )

    score_global = bundle.score_global()
    scores_dict = {
        "technique":  bundle.qc_technique.score,
        "gameplay":   bundle.qc_gameplay.score,
        "visuel":     bundle.qc_visuel.score,
        "execution":  bundle.execution.score,
        "playtester": bundle.playtester.score,
    }

    # Genre Profiler — enregistré pour TOUTE génération (approuvée ou non)
    # pour avoir un signal complet sur les dimensions faibles du genre
    try:
        genre_profiler.record(genre_profile.genre_principal, scores_dict)
    except Exception:
        pass

    # Snippet Bank — alimentée uniquement pour les bons jeux
    if score_global >= 8.0 and approuve:
        try:
            titre = gdd.get("titre", genre_profile.genre_principal)
            nb_slots = snippet_bank.store(code, genre_profile.genre_principal, titre, score_global)
            if nb_slots:
                print(f"  ✓ Snippet Bank  : {nb_slots} slot(s) mis à jour")
        except Exception:
            pass

    # Extraire et sauvegarder le pattern
    # — Seuil abaissé à 6.0 (approuvé) ou 5.0 (basique, pour amorcer le RAG)
    _execution_score = getattr(bundle, 'execution', None)
    _exec_ok = (_execution_score.score >= 5.0) if _execution_score else False
    _save_as_reference = score_global >= 6.0 and approuve
    _save_as_basique = (not _save_as_reference) and score_global >= 5.0 and _exec_ok

    if _save_as_reference or _save_as_basique:
        _tag = "approuve" if _save_as_reference else "basique"
        notes = verdict.get("points_forts", [""])[0] if verdict.get("points_forts") else ""
        if _save_as_reference:
            memory.save_pattern(
                genre_profile=genre_profile,
                score=score_global,
                code_snippet=code[:500],
                notes=notes,
            )
        # Stocker dans ChromaDB RAG (game_patterns) pour la recherche sémantique
        rag.store_pattern(
            genre=genre_profile.genre_principal,
            sous_genre=genre_profile.sous_genre,
            description=gdd.get("concept", ""),
            score=score_global,
            mecaniques=genre_profile.mecaniques_obligatoires,
            style_visuel=genre_profile.style_visuel,
            boucle_core=genre_profile.boucle_core,
            code_snippet=code[:300],
            notes=f"[{_tag}] {notes}",
        )
        print(f"  ✓ RAG enrichi ({_tag}) : {genre_profile.genre_principal} — score {score_global:.1f}")
        # Alimenter aussi la mechanics_kb avec ce jeu réussi (feedback loop)
        # Construire un document structuré à partir des données du jeu
        _mech_doc = (
            f"{genre_profile.genre_principal.upper()} — {gdd.get('titre','?')} (score {score_global:.1f}/10)\n"
            f"CORE LOOP : {genre_profile.boucle_core}\n"
            f"MÉCANIQUES : {', '.join(genre_profile.mecaniques_obligatoires[:8])}\n"
            f"STYLE : {genre_profile.style_visuel}\n"
            f"CONCEPT : {gdd.get('concept','')[:200]}\n"
            f"POINTS FORTS : {notes[:200] if notes else 'N/A'}"
        )
        rag.store_mechanic(
            game_name=gdd.get("titre", genre_profile.genre_principal),
            genre=genre_profile.genre_principal,
            document=_mech_doc,
            publisher="ArcadeAI",
            year=int(datetime.datetime.now().year),
        )
        # Stocker les extraits de code clés pour le RAG code snippets
        try:
            import rag as _rag_snip
            _html_code = html_path and open(html_path, encoding='utf-8').read() or ""
            if _html_code:
                _scripts = _re_snip.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', _html_code, _re_snip.DOTALL)
                _js = max(_scripts, key=len) if _scripts else ""
                if _js and len(_js) > 1000:
                    _genre = genre_profile.genre_principal if genre_profile else "unknown"
                    _title = gdd.get('titre', 'unknown') if isinstance(gdd, dict) else "unknown"
                    # Extract gameLoop
                    _m = _re_snip.search(r'function\s+gameLoop\s*\([^)]*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', _js)
                    if _m:
                        _rag_snip.store_code_snippet(_title, _genre, 'gameloop', _m.group(), score_global)
                    # Extract update function
                    _m = _re_snip.search(r'function\s+update\s*\([^)]*\)\s*\{', _js)
                    if _m:
                        _end = _m.start()
                        _depth = 0
                        for _i, _c in enumerate(_js[_m.start():_m.start()+3000]):
                            if _c == '{': _depth += 1
                            elif _c == '}':
                                _depth -= 1
                                if _depth == 0:
                                    _end = _m.start() + _i + 1
                                    break
                        _rag_snip.store_code_snippet(_title, _genre, 'update', _js[_m.start():_end], score_global)
                    # Extract collision detection
                    _m = _re_snip.search(r'function\s+(?:checkCollisions?|detectCollisions?|handleCollisions?)\s*\(', _js)
                    if _m:
                        _rag_snip.store_code_snippet(_title, _genre, 'collision', _js[_m.start():_m.start()+1500], score_global)
        except Exception:
            pass  # Never crash the pipeline

    mins, secs = divmod(duree_int, 60)
    duree_str = f"{mins}m{secs:02d}s" if mins else f"{secs}s"
    print(f"\n  ✓ Jeu sauvegardé : {html_path}")
    print(f"  ✓ Métadonnées    : {json_path}")
    print(f"  ✓ Durée pipeline : {duree_str}")
    return html_path

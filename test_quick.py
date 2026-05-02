"""
test_quick.py — Lightweight test script: 3 simple genres in sequence.

Validates the pipeline baseline before testing complex genres.
Uses run_quick() to minimize API calls.

Usage :
    python test_quick.py
    python test_quick.py --genres platformer shooter    # genres ciblés
    python test_quick.py --stop-on-fail 2               # arrêt si N échecs
"""

import sys
import time
import argparse
import os

# Assure que le répertoire du projet est dans le path
sys.path.insert(0, os.path.dirname(__file__))

# Prompts de test par genre (simples, formulés clairement)
DEFAULT_TESTS = [
    {
        "label": "Platformer",
        "prompt": "un jeu de plateforme 2D avec un personnage qui saute sur des plateformes et évite des ennemis",
        "min_exec": 4.5,
        "min_score": 6.0,
    },
    {
        "label": "Shooter",
        "prompt": "un shoot'em up spatial 2D avec un vaisseau qui tire sur des vaisseaux ennemis et collecte des bonus",
        "min_exec": 4.5,
        "min_score": 6.0,
    },
    {
        "label": "Puzzle",
        "prompt": "un jeu de puzzle avec des blocs colorés à faire correspondre, un score et un timer",
        "min_exec": 4.5,
        "min_score": 6.0,
    },
]

EXTRA_TESTS = {
    "rpg": {
        "label": "RPG simple",
        "prompt": "un mini RPG 2D avec un héros qui combat des monstres et monte de niveau",
        "min_exec": 4.0,
        "min_score": 5.5,
    },
    "tower": {
        "label": "Tower Defense",
        "prompt": "un tower defense 2D avec des tours qui tirent sur des ennemis qui suivent un chemin",
        "min_exec": 4.0,
        "min_score": 5.5,
    },
    "survival": {
        "label": "Survival",
        "prompt": "un jeu de survie 2D avec des vagues d'ennemis et un système d'upgrade",
        "min_exec": 4.0,
        "min_score": 5.5,
    },
}


def _color(text: str, code: str) -> str:
    """Couleur ANSI si terminal le supporte."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(t): return _color(t, "92")
def _red(t):   return _color(t, "91")
def _yellow(t): return _color(t, "93")
def _bold(t):  return _color(t, "1")
def _cyan(t):  return _color(t, "96")


def run_test(test: dict) -> dict:
    """Lance une génération et retourne les métriques clés."""
    from coordinateur import run_quick

    label = test["label"]
    prompt = test["prompt"]
    print(f"\n{'─'*60}")
    print(f"  {_bold(_cyan(label))} : {prompt[:80]}")
    print(f"{'─'*60}")

    t0 = time.time()
    try:
        result = run_quick(prompt)
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  {_red('ERREUR')} : {e}")
        return {
            "label": label, "prompt": prompt,
            "score": 0.0, "exec": 0.0,
            "approuve": False, "elapsed": elapsed,
            "error": str(e),
            "passed": False,
        }

    elapsed = time.time() - t0
    bundle = result.get("bundle")
    score = result.get("score", 0.0)
    exec_score = bundle.execution.score if bundle else 0.0
    approuve = result.get("approved", result.get("approuve", False))
    titre = result.get("gdd", {}).get("titre", "?") if result.get("gdd") else "?"

    # Scores par agent
    scores_detail = {}
    if bundle:
        scores_detail = {
            "technique": getattr(bundle.technique, "score", None),
            "gameplay": getattr(bundle.gameplay, "score", None),
            "visuel":   getattr(bundle.visuel, "score", None),
            "exec":     exec_score,
        }

    passed = exec_score >= test["min_exec"] and score >= test["min_score"]

    # Affichage
    status_icon = _green("✓ PASS") if passed else _red("✗ FAIL")
    exec_color  = _green(f"{exec_score:.1f}") if exec_score >= 4.5 else _red(f"{exec_score:.1f}")
    score_color = _green(f"{score:.2f}") if score >= 6.0 else _yellow(f"{score:.2f}") if score >= 5.0 else _red(f"{score:.2f}")

    print(f"  Titre     : {titre}")
    print(f"  Statut    : {status_icon}")
    print(f"  Score     : {score_color}/10  |  Exec: {exec_color}/10  |  Approuvé: {'oui' if approuve else 'non'}")
    if scores_detail:
        parts = [f"Tech={scores_detail.get('technique','?'):.1f}" if scores_detail.get('technique') else "",
                 f"Play={scores_detail.get('gameplay','?'):.1f}" if scores_detail.get('gameplay') else "",
                 f"Visual={scores_detail.get('visuel','?'):.1f}"  if scores_detail.get('visuel') else ""]
        print(f"  Détail    : {' | '.join(p for p in parts if p)}")
    print(f"  Durée     : {elapsed:.0f}s")

    if not passed:
        # Afficher les issues critiques
        if bundle:
            blocking = [i for i in bundle.all_issues() if i.get("severite") in ("critique", "critical")][:3]
            if blocking:
                print(f"  Issues critiques :")
                for iss in blocking:
                    print(f"    · {iss.get('description','')[:100]}")

    return {
        "label": label, "prompt": prompt,
        "score": score, "exec": exec_score,
        "approuve": approuve, "elapsed": elapsed,
        "passed": passed,
        "titre": titre,
    }


def main():
    parser = argparse.ArgumentParser(description="Test rapide pipeline arcade — 3 genres simples")
    parser.add_argument(
        "--genres", nargs="*",
        choices=list(EXTRA_TESTS.keys()) + ["platformer", "shooter", "puzzle"],
        help="Genres à tester (défaut: platformer, shooter, puzzle)"
    )
    parser.add_argument(
        "--stop-on-fail", type=int, default=3, metavar="N",
        help="Arrêt si N échecs (défaut: 3 = ne s'arrête jamais)"
    )
    parser.add_argument(
        "--delay", type=int, default=5,
        help="Délai en secondes entre chaque test (défaut: 5)"
    )
    args = parser.parse_args()

    # Construire la liste de tests
    if args.genres:
        tests = []
        for g in args.genres:
            if g in EXTRA_TESTS:
                tests.append(EXTRA_TESTS[g])
            elif g == "platformer":
                tests.append(DEFAULT_TESTS[0])
            elif g == "shooter":
                tests.append(DEFAULT_TESTS[1])
            elif g == "puzzle":
                tests.append(DEFAULT_TESTS[2])
    else:
        tests = DEFAULT_TESTS

    print(_bold(f"\n{'='*60}"))
    print(_bold(f"  ARCADE PIPELINE — Test rapide ({len(tests)} genre(s))"))
    print(_bold(f"{'='*60}"))
    print(f"  Stop-on-fail : {args.stop_on_fail}")
    print(f"  Délai inter-test : {args.delay}s")

    results = []
    failures = 0

    for i, test in enumerate(tests):
        if i > 0 and args.delay > 0:
            print(f"\n  Pause {args.delay}s avant le prochain test...")
            time.sleep(args.delay)

        result = run_test(test)
        results.append(result)

        if not result.get("passed"):
            failures += 1
            if failures >= args.stop_on_fail:
                print(f"\n  {_red(f'{failures} échec(s) — arrêt (--stop-on-fail {args.stop_on_fail})')}")
                break

    # Résumé final
    print(f"\n{'='*60}")
    print(_bold("  RÉSUMÉ"))
    print(f"{'='*60}")

    passed_count = sum(1 for r in results if r.get("passed"))
    total = len(results)
    rate = passed_count / total * 100 if total else 0

    for r in results:
        icon = _green("✓") if r.get("passed") else _red("✗")
        score_str = f"{r['score']:.2f}" if r.get('score') is not None else "—"
        exec_str  = f"{r['exec']:.1f}"  if r.get('exec') is not None else "—"
        err = f"  [{r.get('error','')}]" if r.get('error') else ""
        print(f"  {icon} {r['label']:<15} score={score_str}  exec={exec_str}{err}")

    overall = _green(f"{passed_count}/{total} PASS ({rate:.0f}%)") if passed_count == total \
              else _yellow(f"{passed_count}/{total} PASS ({rate:.0f}%)") if passed_count > 0 \
              else _red(f"{passed_count}/{total} PASS ({rate:.0f}%)")
    print(f"\n  Résultat global : {overall}")

    avg_score = sum(r["score"] for r in results if r.get("score")) / total if total else 0
    avg_exec  = sum(r["exec"]  for r in results if r.get("exec"))  / total if total else 0
    print(f"  Score moyen    : {avg_score:.2f}/10")
    print(f"  Exec moyen     : {avg_exec:.1f}/10")

    if passed_count < total:
        print(f"\n  {_yellow('→ Investiguer les échecs avant de tester des genres complexes.')}")
    else:
        print(f"\n  {_green('→ Baseline validée — tu peux tester des genres complexes (tower defense, RPG...).')}")

    print()
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())

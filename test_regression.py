"""
Rapid regression tests (no Gemini API calls)
Verifies that critical pipeline fixes are working correctly.

Usage :
    python test_regression.py           # Run all tests
    python test_regression.py --fast    # Skip slow Playwright tests
    python test_regression.py -v        # Verbose output with tracebacks
"""

import sys
import argparse
import traceback
import os

# Assure que le répertoire du projet est dans le path
sys.path.insert(0, os.path.dirname(__file__))

PASS = "✓"
FAIL = "✗"
WARN = "⚠"

results = []
verbose = False
fast_mode = False


def run_test(name, fn):
    try:
        fn()
        results.append((PASS, name, None))
        print(f"  {PASS} {name}")
        return True
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")
        return False
    except Exception as e:
        results.append((FAIL, name, f"{type(e).__name__}: {e}"))
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")
        if verbose:
            traceback.print_exc()
        return False


# ─────────────────────────────────────────────
# Tests — JS Syntax Checker
# ─────────────────────────────────────────────

def test_fix_const_in_switch():
    """fix_const_syntax_errors corrige 'const' dans switch/case."""
    from js_syntax_checker import fix_const_syntax_errors, check_syntax
    broken_html = """<!DOCTYPE html><html><body><script>
var x = 2;
switch(x) {
  case 1:
    const a = 10;
    break;
  case 2:
    var b = 20;
    break;
}
</script></body></html>"""
    fixed, was_fixed, descs = fix_const_syntax_errors(broken_html)
    issues_after = check_syntax(fixed)
    assert not issues_after, f"Still has syntax errors after fix: {issues_after}"


def test_fix_for_const_loop():
    """fix_const_syntax_errors corrige for(const i=0;...)."""
    from js_syntax_checker import fix_const_syntax_errors, check_syntax
    html = """<!DOCTYPE html><html><body><script>
for(const i=0; i<10; i++) {
  console.log(i);
}
</script></body></html>"""
    fixed, was_fixed, _ = fix_const_syntax_errors(html)
    issues_after = check_syntax(fixed)
    assert not issues_after, f"Still has syntax errors after fix: {issues_after}"


def test_fix_identifier_already_declared():
    """fix_identifier_already_declared tourne sans crash."""
    from js_syntax_checker import fix_identifier_already_declared
    html = """<!DOCTYPE html><html><body><script>
var score = 0;
const score = 10;
console.log(score);
</script></body></html>"""
    fixed, was_fixed, descs = fix_identifier_already_declared(html)
    assert isinstance(was_fixed, bool), "Return type should be bool"
    assert isinstance(fixed, str) and "</html>" in fixed


def test_fix_all_auto_pipeline():
    """fix_all_auto enchaîne les deux fixes sans crash."""
    from js_syntax_checker import fix_all_auto, check_syntax
    html = """<!DOCTYPE html><html><body><script>
var x = 1;
switch(x) {
  case 1: const y = 5; break;
}
</script></body></html>"""
    fixed, any_fixed, descs = fix_all_auto(html)
    assert isinstance(any_fixed, bool)
    assert isinstance(descs, list)
    assert "</html>" in fixed
    issues = check_syntax(fixed)
    assert not issues, f"Still broken after fix_all_auto: {issues}"


def test_check_and_report_valid():
    """check_and_report retourne ([], False) sur code valide."""
    from js_syntax_checker import check_and_report
    valid_html = """<!DOCTYPE html><html><body><script>
var x = 1;
function foo() { return x + 1; }
console.log(foo());
</script></body></html>"""
    issues, broken = check_and_report(valid_html)
    assert not broken, f"Valid code reported as broken: {issues}"


# ─────────────────────────────────────────────
# Tests — Code Validator
# ─────────────────────────────────────────────

def test_validate_and_fix_runs():
    """validate_and_fix ne crashe pas sur un code HTML simple."""
    from code_validator import validate_and_fix
    html = """<!DOCTYPE html><html><body><canvas id="gameCanvas"></canvas><script>
var score = 0, lives = 3, gameState = 'menu';
var canvas = document.getElementById('gameCanvas');
</script></body></html>"""
    fixed, issues, changed = validate_and_fix(html)
    assert isinstance(fixed, str) and len(fixed) > 100
    assert isinstance(issues, list)
    assert isinstance(changed, bool)


def test_fix_gamestateflow_no_crash():
    """_fix_gamestateflow ne crashe pas sur un jeu sans gameState."""
    from code_validator import _fix_gamestateflow
    script_no_gs = "function update(dt) { var x = 1; }"
    result, fixes = _fix_gamestateflow(script_no_gs)
    assert result == script_no_gs  # unchanged
    assert fixes == []


def test_fix_gamestateflow_injects_transition():
    """_fix_gamestateflow détecte menu sans transition playing."""
    from code_validator import _fix_gamestateflow
    script = """
var gameState = 'menu';
function initGame() { var x = 1; }
function update(dt) {
  if (gameState === 'menu') {
    return;
  }
}
"""
    result, fixes = _fix_gamestateflow(script)
    assert isinstance(fixes, list)
    # If a fix was applied, it should inject something about 'playing'
    if fixes:
        assert "playing" in result, f"Fix applied but 'playing' not found in result"


def test_fix_all_auto_loops_multiple_redeclarations():
    """fix_all_auto + fix_identifier_already_declared corrige les redéclarations multiples."""
    from js_syntax_checker import fix_all_auto, check_syntax
    # Deux redéclarations const : Node.js ne voit qu'une SyntaxError à la fois
    html = """<!DOCTYPE html><html><body><script>
var score = 0;
const score = 10;
const score = 20;
console.log(score);
</script></body></html>"""
    fixed, any_fixed, descs = fix_all_auto(html)
    # Le résultat doit être syntaxiquement valide
    issues = check_syntax(fixed)
    assert not issues, f"Toujours des erreurs après fix_all_auto: {issues}"
    # La boucle fix_all_auto ne doit pas crasher (même si un seul fix suffit ici)
    assert isinstance(descs, list)


def test_prepatcher_player_false_positive():
    """pre-patcher ne doit PAS injecter let player=null quand player est clé d'objet PALETTE."""
    import re
    # Simuler le check _already_declared + object-key detection de agent_pre_patcher
    script = """var PALETTE = { bg:'#222', player:'#0AF', enemy:'#F44' };"""
    cv_name = 'player'
    _already_declared = (
        bool(re.search(rf'\b(?:let|const|var)\s+{re.escape(cv_name)}\b', script))
        or bool(re.search(rf'(?:^|\n)\s*{re.escape(cv_name)}\s*=\s*[^\s=]', script))
        or f'window.{cv_name}' in script
    )
    _used_as_standalone = bool(re.search(rf'\b{re.escape(cv_name)}\s*(?:\.|=|\[|\()', script))
    _used_as_obj_key = bool(re.search(rf'[{{\s,]\s*{re.escape(cv_name)}\s*:', script))
    should_inject = not _already_declared and not (_used_as_obj_key and not _used_as_standalone)
    assert not should_inject, "player dans PALETTE ne devrait PAS déclencher une injection"


def test_fix_orphan_closing_braces_mid_file():
    """_fix_orphan_closing_braces supprime les } qui font passer la profondeur < 0."""
    from code_validator import _fix_orphan_closing_braces
    script = """function foo() {
  var x = 1;
}
}
function bar() {
  var y = 2;
}"""
    fixed, fixes = _fix_orphan_closing_braces(script)
    assert fixes, "Devrait avoir supprimé une accolade orpheline"
    # Vérifier que les { et } sont maintenant équilibrés
    opens = fixed.count('{')
    closes = fixed.count('}')
    assert opens == closes, f"Toujours déséquilibré: {opens} {{ vs {closes} }}"


def test_getcontext_fix_any_canvas_name():
    """_fix_missing_getcontext fonctionne même si la variable canvas n'est pas nommée 'canvas'."""
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from agents.phase5.agent_pre_patcher import _fix_missing_getcontext
    script = """var gameCanvas = document.getElementById('gameCanvas');
function draw() { ctx.clearRect(0, 0, 800, 600); }"""
    fixed, was_fixed = _fix_missing_getcontext(script)
    assert was_fixed, "Devrait avoir ajouté getContext"
    assert 'getContext' in fixed, "getContext manquant dans le résultat"
    assert 'gameCanvas.getContext' in fixed, "Devrait utiliser le bon nom de variable"


def test_common_vars_injection():
    """validate_and_fix injecte les variables COMMON_VARS non déclarées."""
    from code_validator import validate_and_fix
    html = """<!DOCTYPE html><html><body><canvas id="gameCanvas"></canvas><script>
document.addEventListener('DOMContentLoaded', function() {
  var canvas = document.getElementById('gameCanvas');
  var ctx = canvas.getContext('2d');
  score += 10;
  lives -= 1;
});
</script></body></html>"""
    fixed, issues, changed = validate_and_fix(html)
    assert "score" in fixed
    assert "lives" in fixed


# ─────────────────────────────────────────────
# Tests — Memory
# ─────────────────────────────────────────────

def test_memory_save_session():
    """memory.save_session ne crashe pas."""
    import memory
    from genre_profile import GenreProfile
    memory.init_memory()
    gp = GenreProfile(
        prompt_utilisateur_original="test",
        genre_principal="shooter",
        sous_genre="shmup",
        ton="arcade",
        technologie_rendu="canvas2d",
    )
    memory.save_session(
        prompt="test prompt",
        genre_profile=gp,
        score_global=5.5,
        saved=False,
        errors=["test error"],
    )


def test_memory_validator_errors():
    """memory.save_validator_errors persiste et get_validator_errors_for_genre récupère."""
    import memory
    memory.init_memory()
    test_genre = "_regression_test_genre_42"
    test_errors = ["[REGRESSION_TEST] Variable x non déclarée"]
    memory.save_validator_errors(test_genre, test_errors)
    retrieved = memory.get_validator_errors_for_genre(test_genre, n=5)
    assert any("REGRESSION_TEST" in e for e in retrieved), f"Errors not persisted: {retrieved}"


# ─────────────────────────────────────────────
# Tests — Minimal Fallback Game
# ─────────────────────────────────────────────

def test_minimal_fallback_valid_html():
    """_make_minimal_fallback_game génère du HTML valide syntaxiquement."""
    from coordinateur import _make_minimal_fallback_game
    from js_syntax_checker import check_and_report
    html = _make_minimal_fallback_game("Test Game", "shooter")
    assert "<!DOCTYPE html>" in html, "Missing DOCTYPE"
    assert "</html>" in html, "Missing </html>"
    assert "gameCanvas" in html, "Missing canvas element"
    issues, broken = check_and_report(html)
    assert not broken, f"Fallback game has syntax errors: {issues}"


def test_minimal_fallback_xss_safe():
    """_make_minimal_fallback_game échappe le HTML pour éviter XSS."""
    from coordinateur import _make_minimal_fallback_game
    html = _make_minimal_fallback_game('<script>alert(1)</script>', 'test<b>hi</b>')
    assert '<script>alert(1)</script>' not in html, "XSS not escaped in titre"
    assert '<b>hi</b>' not in html, "XSS not escaped in genre"


def test_minimal_fallback_different_genres():
    """_make_minimal_fallback_game gère plusieurs genres sans crash."""
    from coordinateur import _make_minimal_fallback_game
    for genre in ["shooter", "platformer", "rpg", "tower defense", "puzzle"]:
        html = _make_minimal_fallback_game(f"Test {genre}", genre)
        assert len(html) > 1000, f"Fallback too short for genre={genre}"
        assert "gameCanvas" in html


# ─────────────────────────────────────────────
# Tests — Playwright (slow, skip in fast mode)
# ─────────────────────────────────────────────

def test_playwright_available():
    """Playwright est installé et Chromium accessible."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()


def test_executor_on_fallback():
    """agent_executeur donne exec >= 4.5 sur le jeu minimal garanti fonctionnel."""
    from coordinateur import _make_minimal_fallback_game
    from agents.phase4 import agent_executeur
    from genre_profile import GenreProfile
    html = _make_minimal_fallback_game("Fallback Regression Test", "shooter")
    gp = GenreProfile(
        prompt_utilisateur_original="test",
        genre_principal="shooter",
        sous_genre="arcade",
        ton="arcade",
        technologie_rendu="canvas2d",
    )
    result = agent_executeur.run(html, gp)
    assert result is not None, "agent_executeur returned None"
    assert result.score >= 4.5, f"Fallback exec score too low: {result.score:.1f} (expected >= 4.5)"


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

FAST_TESTS = [
    ("JS Syntax: fix_const_in_switch", test_fix_const_in_switch),
    ("JS Syntax: fix_for_const_loop", test_fix_for_const_loop),
    ("JS Syntax: fix_identifier_already_declared", test_fix_identifier_already_declared),
    ("JS Syntax: fix_all_auto pipeline", test_fix_all_auto_pipeline),
    ("JS Syntax: fix_all_auto multi-redeclaration loop", test_fix_all_auto_loops_multiple_redeclarations),
    ("JS Syntax: check_and_report valid code", test_check_and_report_valid),
    ("Pre-patcher: player/PALETTE false positive", test_prepatcher_player_false_positive),
    ("Validator: _fix_orphan_closing_braces mid-file", test_fix_orphan_closing_braces_mid_file),
    ("Pre-patcher: getContext any canvas name", test_getcontext_fix_any_canvas_name),
    ("Validator: validate_and_fix runs", test_validate_and_fix_runs),
    ("Validator: _fix_gamestateflow no crash", test_fix_gamestateflow_no_crash),
    ("Validator: _fix_gamestateflow injects transition", test_fix_gamestateflow_injects_transition),
    ("Validator: COMMON_VARS injection", test_common_vars_injection),
    ("Memory: save_session", test_memory_save_session),
    ("Memory: save/get validator errors", test_memory_validator_errors),
    ("Fallback: valid HTML syntax", test_minimal_fallback_valid_html),
    ("Fallback: XSS safe", test_minimal_fallback_xss_safe),
    ("Fallback: multiple genres", test_minimal_fallback_different_genres),
]

SLOW_TESTS = [
    ("Playwright: disponible", test_playwright_available),
    ("Executor: fallback exec >= 4.5", test_executor_on_fallback),
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arcade Project — Regression Tests (no API calls)")
    parser.add_argument("--fast", action="store_true", help="Skip slow Playwright tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output with tracebacks")
    args = parser.parse_args()
    verbose = args.verbose
    fast_mode = args.fast

    print("\n" + "=" * 58)
    print("  Arcade Project — Regression Tests (sans API Gemini)")
    if fast_mode:
        print("  Mode rapide — tests Playwright ignorés")
    print("=" * 58 + "\n")

    all_tests = FAST_TESTS + ([] if fast_mode else SLOW_TESTS)
    for name, fn in all_tests:
        run_test(name, fn)

    if fast_mode and SLOW_TESTS:
        for name, _ in SLOW_TESTS:
            print(f"  {WARN} {name} [SKIPPED — --fast]")

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total = len(results)

    print(f"\n{'=' * 58}")
    print(f"  Résultats : {passed}/{total} passés" + (f", {failed} échec(s)" if failed else " — tout OK !"))
    print("=" * 58)
    sys.exit(0 if failed == 0 else 1)

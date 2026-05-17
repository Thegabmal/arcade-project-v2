"""
Phase 3.5 — Pre-flight JS check (Session A, item 2.1)

Lightweight Playwright run between Phase 3 (generation) and Phase 4 (full evaluation).
Catches startup JS errors before they enter the evaluation loop, saving API credits
and avoiding the "4.9 forever" pattern caused by undefined variable stubs.

Returns (html, n_fixed, errors_found).
"""

import os
import re
import time
import tempfile
import logging

preflight_log = logging.getLogger("preflight")

MAX_FIX_ROUNDS = 2


def _run_quick_playwright(html_code: str, genre: str) -> list[str]:
    """
    Runs Playwright for genre-appropriate delay, returns critical JS errors only.
    Returns [] if Playwright unavailable or no critical errors found.
    """
    try:
        from playwright.sync_api import sync_playwright
        from agents.phase4.agent_executeur import _get_threejs_local, _init_delay_for_genre
    except ImportError:
        return []

    is_threejs = "three.min.js" in html_code or "three.js" in html_code.lower()
    js_errors: list[str] = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_code)
        tmp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=angle",
                    "--no-sandbox", "--disable-dev-shm-usage",
                ],
            )
            page = browser.new_page()
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            page.on("console", lambda msg: js_errors.append(f"[{msg.type}] {msg.text}")
                    if msg.type == "error" else None)

            if is_threejs:
                threejs_local = _get_threejs_local()
                if threejs_local:
                    def _route_three(route):
                        try:
                            with open(threejs_local, "rb") as fh:
                                route.fulfill(status=200, content_type="application/javascript", body=fh.read())
                        except Exception:
                            route.continue_()
                    page.route("**/*three*", _route_three)
                    page.route("**/*jsdelivr.net*three*", _route_three)

            page.goto(f"file://{tmp_path}")
            time.sleep(_init_delay_for_genre(genre))

            try:
                _arcade_err = page.evaluate(
                    "typeof window.__ARCADE_ERROR__ !== 'undefined' ? window.__ARCADE_ERROR__ : ''"
                )
                if _arcade_err:
                    js_errors.append(f"ARCADE_ERROR: {_arcade_err}")
            except Exception:
                pass

            browser.close()

    except Exception as e:
        preflight_log.warning(f"Pre-flight Playwright error: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Filter — keep only errors that indicate broken code (same filter as agent_executeur)
    threejs_noise = {"webgl context", "gl_", "shader compilation", "context lost", "webglrenderer", "three.webgl"}
    critical = [
        e for e in js_errors
        if any(kw in e.lower() for kw in (
            "is not defined", "typeerror", "referenceerror", "is not a function",
            "cannot read", "syntaxerror", "unexpected token", "arcade_error",
        ))
        and (not is_threejs or not any(n in e.lower() for n in threejs_noise))
    ]
    return critical


def _fix_js_errors(html_code: str, errors: list[str]) -> str | None:
    """
    Calls Gemini Paid to surgically fix the listed JS errors.
    Returns fixed HTML or None if the fix was invalid or empty.
    """
    from config import call_gemini_paid
    from js_syntax_checker import check_and_report as _chk_report

    # Extract the game's main script block (longest <script>…</script> — skips CDN tags)
    matches = list(re.finditer(r'(<script[^>]*>)(.*?)(</script>)', html_code, re.DOTALL | re.IGNORECASE))
    if not matches:
        return None
    target = max(matches, key=lambda m: len(m.group(2)))
    open_tag  = target.group(1)
    script    = target.group(2)
    close_tag = target.group(3)

    if len(script) < 200:
        return None

    error_list = "\n".join(f"  - {e}" for e in errors[:3])

    prompt = (
        "You are a JavaScript expert. Fix ONLY the JS errors listed below in this HTML5 game script.\n"
        "Make the minimal surgical change — do NOT rewrite game logic.\n\n"
        f"ERRORS TO FIX:\n{error_list}\n\n"
        "RULES:\n"
        "1. Return ONLY the corrected JavaScript (no HTML wrapper, no explanation, no markdown fences)\n"
        "2. Fix ONLY what causes the listed errors\n"
        "3. Keep ALL existing game logic intact\n"
        "4. Declare missing variables at the top of their scope with a safe default\n"
        "5. Do NOT add a second requestAnimationFrame loop\n\n"
        f"FULL SCRIPT:\n{script[:60000]}"
    )

    try:
        raw = call_gemini_paid(prompt, temperature=0.15, max_tokens=65536, disable_thinking=True)
    except Exception as e:
        preflight_log.warning(f"Pre-flight LLM call failed: {e}")
        return None

    # Strip markdown fences the model sometimes adds
    fixed_script = raw.strip()
    if fixed_script.startswith("```"):
        lines = fixed_script.split("\n", 1)
        fixed_script = lines[1] if len(lines) > 1 else ""
        if fixed_script.rstrip().endswith("```"):
            fixed_script = fixed_script.rstrip()[:-3]
    fixed_script = fixed_script.strip()

    if len(fixed_script) < 500:
        preflight_log.warning("Pre-flight LLM response too short — discarding")
        return None

    # Reconstruct full HTML with only the target script replaced
    fixed_html = (
        html_code[: target.start(2)]
        + fixed_script
        + html_code[target.end(2):]
    )

    try:
        _, broken = _chk_report(fixed_html)
    except Exception:
        broken = False
    if broken:
        preflight_log.warning("Pre-flight LLM fix introduced syntax errors — discarding")
        return None

    return fixed_html


def run(html_code: str, genre: str) -> tuple[str, int, list[str]]:
    """
    Phase 3.5 — Pre-flight JS check.

    Args:
        html_code : Generated HTML game code (after A1 linter)
        genre     : Genre principal (used for Playwright init delay)

    Returns:
        (html_code, n_fixed, errors_found)
        - html_code    : Potentially patched version (or original if fix failed)
        - n_fixed      : Number of successful fix rounds applied (0–2)
        - errors_found : Critical JS errors still present after last attempt
    """
    try:
        from logger import coordinateur_log as _log
    except Exception:
        _log = preflight_log

    _log.info("Phase 3.5 — Pre-flight JS check (Playwright)")

    n_fixed = 0
    errors_found: list[str] = []

    for attempt in range(MAX_FIX_ROUNDS + 1):
        errors = _run_quick_playwright(html_code, genre)

        if not errors:
            if n_fixed > 0:
                _log.success(f"Pre-flight: all JS errors resolved ({n_fixed} fix round(s))")
            else:
                _log.success("Pre-flight: clean — no JS errors at startup")
            return html_code, n_fixed, []

        errors_found = errors
        first_err = errors[0][:80]
        _log.warning(f"Pre-flight [{attempt + 1}/{MAX_FIX_ROUNDS + 1}]: {len(errors)} error(s) — {first_err}")

        if attempt >= MAX_FIX_ROUNDS:
            _log.warning(
                f"Pre-flight: {len(errors)} error(s) remain after {MAX_FIX_ROUNDS} fix attempt(s) "
                "— forwarding raw errors to Phase 4"
            )
            break

        fixed = _fix_js_errors(html_code, errors)
        if fixed and fixed != html_code:
            html_code = fixed
            n_fixed += 1
            _log.info(f"Pre-flight: LLM fix applied (round {n_fixed}/{MAX_FIX_ROUNDS})")
        else:
            _log.warning("Pre-flight: LLM fix failed or produced no change — stopping pre-flight")
            break

    return html_code, n_fixed, errors_found

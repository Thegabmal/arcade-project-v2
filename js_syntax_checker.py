"""
JS Syntax Checker — Node.js based
Uses `node --check` to detect precise JS syntax errors
(Unexpected token, SyntaxError, etc.) with exact line numbers.

Advantage over regex: a real JS parser, 100% reliable on missing commas,
unbalanced braces, unclosed template literals, etc.
"""

import re
import json as _json
import subprocess
import tempfile
import os
from logger import coordinateur_log

# Variables du template HTML et globals browser — jamais à déclarer auto
_BROWSER_AND_TEMPLATE_GLOBALS = frozenset({
    # Browser
    'window', 'document', 'Math', 'Date', 'JSON', 'console', 'Array', 'Object',
    'String', 'Number', 'Boolean', 'RegExp', 'Error', 'Promise', 'Map', 'Set',
    'WeakMap', 'WeakSet', 'Symbol', 'Proxy', 'Reflect',
    'undefined', 'null', 'NaN', 'Infinity', 'void',
    'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
    'requestAnimationFrame', 'cancelAnimationFrame',
    'localStorage', 'sessionStorage', 'performance',
    'AudioContext', 'webkitAudioContext', 'AudioBuffer', 'GainNode',
    'navigator', 'location', 'history', 'screen',
    'parseFloat', 'parseInt', 'isNaN', 'isFinite', 'encodeURIComponent',
    'decodeURIComponent', 'escape', 'unescape', 'eval',
    'Uint8Array', 'Float32Array', 'Int16Array', 'Int32Array', 'Uint16Array',
    'Uint32Array', 'Float64Array', 'ArrayBuffer', 'DataView',
    'Image', 'Audio', 'XMLHttpRequest', 'fetch',
    'Event', 'KeyboardEvent', 'MouseEvent', 'TouchEvent', 'PointerEvent',
    'addEventListener', 'removeEventListener', 'dispatchEvent',
    'alert', 'confirm', 'prompt',
    # HTML template globals
    'canvas', 'ctx', 'W', 'H', 'dt', 'lastTime', 'gameState', '_AC', '_dpr',
    # 2D template ENGINE objects — never inject wrong defaults for these
    'Keys', 'Touch', 'Mouse', 'Shake', 'Particles', 'Popups', 'sfx',
    'FIXED_DT', 'MAX_DT', 'accumulator', 'GAME_W', 'GAME_H', 'DPR',
    'TILE_SIZE', 'GAME_SCORE', 'GAME_TITLE',
    'cam', 'coinPool', 'tileMap', 'platforms', 'mapCols', 'mapRows',
    # ENGINE utility functions — LLM must not redeclare or stub these
    'dist', 'aabb', 'lerp', 'clamp', 'createPool', 'rand', 'randInt',
    # Three.js global namespace — never inject var THREE = 0
    'THREE',
})


def extract_js_from_html(html: str) -> str:
    """Extract and concatenate all inline <script> blocks (skips external src= scripts)."""
    matches = []
    for m in re.finditer(r'(<script(?:\s[^>]*)?>)(.*?)(</script>)', html, re.DOTALL | re.IGNORECASE):
        open_tag = m.group(1)
        content = m.group(2)
        # Skip external/CDN scripts — browsers ignore inline content when src= is present
        if re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            continue
        matches.append(content)
    if not matches:
        return ""
    blocks = [m for m in matches if len(m.strip()) > 50]
    if not blocks:
        return max(matches, key=len)
    return "\n;\n".join(blocks)


def check_syntax(html: str) -> list[str]:
    """
    Vérifie la syntaxe JS via `node --check`.
    Retourne une liste d'issues formatées pour le pre-patcher.
    Liste vide = syntaxe OK.
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return []

    # Écrire le JS dans un fichier temporaire
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f:
            f.write(js)
            tmp = f.name

        result = subprocess.run(
            ['node', '--check', tmp],
            capture_output=True, text=True, timeout=20
        )

        if result.returncode == 0:
            return []  # Syntaxe OK

        # Parser la sortie d'erreur Node.js
        # Format: /path/to/file.js:42
        #         const x = { a: 1  b: 2 }
        #                            ^
        # SyntaxError: Unexpected token 'b'
        stderr = result.stderr or result.stdout
        issues = _parse_node_error(stderr, js)
        return issues

    except subprocess.TimeoutExpired:
        coordinateur_log.warning("JS syntax check timeout (>10s)")
        return []
    except FileNotFoundError:
        coordinateur_log.warning("node non trouvé — syntaxe JS non vérifiée")
        return []
    except Exception as e:
        coordinateur_log.warning(f"JS syntax check échoué : {e}")
        return []
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def _parse_node_error(stderr: str, js: str) -> list[str]:
    """
    Parse la sortie d'erreur de Node.js et retourne des issues
    formatées pour le pre-patcher (avec contexte de ligne).
    """
    issues = []
    lines = js.splitlines()

    # Pattern principal : file.js:LINE\nCODE\nARROW\nSyntaxError: MSG
    # Node v24 format: file.js:42\n    ctx.something\n    ^\nSyntaxError: ...
    error_blocks = re.finditer(
        r'(?:.*?):(\d+)\n(.*?)\n\s*\^[\n\s]*(SyntaxError[^\n]+)',
        stderr, re.MULTILINE
    )

    found = False
    for m in error_blocks:
        line_num = int(m.group(1))
        code_line = m.group(2).strip()
        error_msg = m.group(3).strip()
        found = True

        # Extraire contexte (lignes autour de l'erreur)
        ctx_start = max(0, line_num - 3)
        ctx_end = min(len(lines), line_num + 2)
        context = '\n'.join(
            f"  {'→' if i == line_num-1 else ' '} {i+1}: {lines[i]}"
            for i in range(ctx_start, ctx_end)
        )

        issue = (
            f"SYNTAXE JS — {error_msg} à la ligne {line_num}. "
            f"Code problématique : `{code_line}`. "
            f"Contexte :\n{context}\n"
            f"Corrige cette erreur de syntaxe pour que le script puisse s'exécuter."
        )
        issues.append(issue)
        coordinateur_log.warning(f"Syntax error ligne {line_num}: {error_msg}")

    if not found:
        # Fallback : chercher juste le message SyntaxError
        syntax_err = re.search(r'SyntaxError[^\n]+', stderr)
        if syntax_err:
            issues.append(
                f"SYNTAXE JS — {syntax_err.group(0)}. "
                f"Corrige cette erreur de syntaxe pour que le script puisse s'exécuter."
            )

    return issues


def _count_brace_depth(js: str) -> int:
    """Count net unclosed { braces in JS, ignoring strings and comments."""
    depth = 0
    i, n = 0, len(js)
    in_line = in_block = in_str = False
    str_ch = ''
    while i < n:
        c = js[i]
        if in_line:
            if c == '\n': in_line = False
            i += 1; continue
        if in_block:
            if c == '*' and i + 1 < n and js[i+1] == '/': in_block = False; i += 2
            else: i += 1
            continue
        if in_str:
            if c == '\\': i += 2; continue
            if c == str_ch: in_str = False
            i += 1; continue
        if c == '/' and i + 1 < n:
            if js[i+1] == '/': in_line = True; i += 2; continue
            if js[i+1] == '*': in_block = True; i += 2; continue
        if c in ('"', "'"):
            in_str = True; str_ch = c; i += 1; continue
        if c == '`':
            i += 1
            while i < n:
                if js[i] == '\\': i += 2; continue
                if js[i] == '`': i += 1; break
                i += 1
            continue
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        i += 1
    return depth


def _find_game_script_block(html: str):
    """Find the main (non-CDN) script block. Returns re.Match or None."""
    for sm in re.finditer(r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
                          html, re.DOTALL | re.IGNORECASE):
        if 'src=' not in sm.group(1).lower():
            return sm
    return None


def fix_exact_syntax_error(html: str) -> tuple[str, bool, list[str]]:
    """
    Surgical syntax fixer: reads the exact node --check error (line + message)
    and applies the MINIMAL targeted fix without touching anything else.

    Handles:
    - 'Unexpected end of input' → append missing } (counted from brace depth)
    - "Unexpected token '}'" at line N → remove orphan } on that line
    - 'Unexpected token' / 'Missing ;' at line N → add ; at end of that line
    - Brace imbalance (depth < 0) → remove trailing orphan }

    Falls back silently if the fix doesn't resolve the error.
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return html, False, []

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f:
            f.write(js)
            tmp = f.name

        result = subprocess.run(
            ['node', '--check', tmp],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return html, False, []

        stderr = result.stderr or result.stdout
        sm = _find_game_script_block(html)
        if not sm:
            return html, False, []

        # ── Parse the error from node stderr ─────────────────────────────────
        line_match = re.search(r'\.js:(\d+)', stderr)
        line_num = int(line_match.group(1)) - 1 if line_match else None  # 0-indexed
        err_msg = ''
        em = re.search(r'SyntaxError[^\n]+', stderr)
        if em:
            err_msg = em.group(0)

        js_lines = js.split('\n')
        new_js = None
        fix_desc = None

        # ── Case 1: Unexpected end of input → add missing closing braces ─────
        if 'Unexpected end' in err_msg or 'end of input' in stderr.lower():
            depth = _count_brace_depth(js)
            if depth > 0:
                new_js = js.rstrip() + '\n' + '\n'.join(['}'] * depth)
                fix_desc = f'Added {depth} missing closing brace(s) (Unexpected end of input)'

        # ── Case 2: Extra } at known line → remove it ────────────────────────
        elif ("Unexpected token '}'" in err_msg or "Unexpected token }" in err_msg) \
                and line_num is not None and line_num < len(js_lines):
            target = js_lines[line_num]
            # Remove the } only if the line is essentially just a closing brace
            stripped = target.strip()
            if stripped in ('}', '};', '},'):
                js_lines.pop(line_num)
                new_js = '\n'.join(js_lines)
                fix_desc = f'Removed orphan }} at line {line_num + 1}'
            else:
                # Try removing one } from that line (might be extra })
                new_line = target.replace('}', '', 1)
                js_lines[line_num] = new_line
                new_js = '\n'.join(js_lines)
                fix_desc = f'Removed extra }} from line {line_num + 1}'

        # ── Case 3: Missing semicolon / unexpected identifier → add ; ─────────
        elif ('Missing' in err_msg or 'missing' in err_msg or
              ('Unexpected' in err_msg and 'identifier' in err_msg.lower())) \
                and line_num is not None and line_num > 0:
            # Add ; to end of PREVIOUS line (node reports line AFTER the problem)
            target_line_idx = max(0, line_num - 1)
            prev_line = js_lines[target_line_idx]
            if prev_line.rstrip() and not prev_line.rstrip().endswith((';', '{', '}', ',')):
                js_lines[target_line_idx] = prev_line.rstrip() + ';'
                new_js = '\n'.join(js_lines)
                fix_desc = f'Added ; at end of line {target_line_idx + 1}'

        # ── Case 4: Brace imbalance (depth < 0) → trim trailing orphan } ─────
        if new_js is None:
            depth = _count_brace_depth(js)
            if depth < 0:
                to_remove = abs(depth)
                removed = 0
                lines_copy = js_lines[:]
                for i in range(len(lines_copy) - 1, -1, -1):
                    if removed >= to_remove:
                        break
                    if lines_copy[i].strip() in ('}', '};', '},'):
                        lines_copy.pop(i)
                        removed += 1
                if removed > 0:
                    new_js = '\n'.join(lines_copy)
                    fix_desc = f'Removed {removed} trailing orphan closing brace(s)'

        if new_js is None or new_js == js:
            return html, False, []

        # Apply fix to HTML
        new_html = html[:sm.start(2)] + new_js + html[sm.end(2):]

        # Verify: the fix must actually resolve the syntax error
        if not check_syntax(new_html):
            coordinateur_log.info(f'[AUTO-FIX] {fix_desc}')
            return new_html, True, [f'[AUTO-FIX] {fix_desc}']

        return html, False, []

    except Exception as e:
        coordinateur_log.warning(f'fix_exact_syntax_error failed: {e}')
        return html, False, []
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def fix_const_syntax_errors(html: str) -> tuple[str, bool, list[str]]:
    """
    Correction ciblée de 'SyntaxError: Unexpected token const/let'.
    Node.js fournit le numéro de ligne exact → on convertit le const/let fautif en var.
    Vérifie que la syntaxe est valide après correction.
    Retourne (html_corrigé, was_fixed, fix_descriptions).
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return html, False, []

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f:
            f.write(js)
            tmp = f.name

        result = subprocess.run(
            ['node', '--check', tmp],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            return html, False, []

        stderr = result.stderr or result.stdout
        if 'Unexpected token' not in stderr:
            return html, False, []
        if "'const'" not in stderr and "'let'" not in stderr:
            return html, False, []

        # Extraire le numéro de ligne — Node.js : "file.js:LINE"
        m = re.search(r'\.js:(\d+)', stderr)
        if not m:
            return html, False, []

        line_num = int(m.group(1)) - 1  # 0-indexed
        lines = js.split('\n')
        if line_num >= len(lines):
            return html, False, []

        original_line = lines[line_num]
        fix_desc = None

        # Priorité 1 : for(const X = …) → for(let X = …)
        new_line = re.sub(r'\bfor\s*\(\s*const\s+(\w+)\s*=',
                          lambda mm: f'for (let {mm.group(1)} =', original_line)
        if new_line != original_line:
            fix_desc = f'for(const...) → for(let...) ligne {line_num + 1}'
        else:
            # Priorité 2 : const/let → var sur cette ligne précise
            new_line = re.sub(r'\b(const|let)\b', 'var', original_line, count=1)
            if new_line != original_line:
                kw = 'const' if 'const' in original_line else 'let'
                fix_desc = f'{kw} → var ligne {line_num + 1} (SyntaxError fix)'

        if fix_desc is None:
            return html, False, []

        lines[line_num] = new_line
        new_js = '\n'.join(lines)

        # Reconstruire le HTML
        script_match = re.search(
            r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
            html, re.DOTALL | re.IGNORECASE
        )
        if not script_match:
            return html, False, []
        new_html = (
            html[:script_match.start(2)]
            + new_js
            + html[script_match.end(2):]
        )

        # Vérifier que la syntaxe est maintenant valide
        verify_issues = check_syntax(new_html)
        if not verify_issues:
            coordinateur_log.info(f"[AUTO-FIX] SyntaxError const/let corrigé : {fix_desc}")
            return new_html, True, [f'[AUTO-FIX] {fix_desc}']

        # La correction a pu révéler une autre erreur — on retente une fois de plus
        js2 = extract_js_from_html(new_html)
        for vi in verify_issues:
            m2 = re.search(r'ligne (\d+)', vi)
            if not m2:
                continue
            ln2 = int(m2.group(1)) - 1
            lines2 = js2.split('\n') if js2 else []
            if ln2 >= len(lines2):
                continue
            if "'const'" in vi or "'let'" in vi:
                lines2[ln2] = re.sub(r'\b(const|let)\b', 'var', lines2[ln2], count=1)
                js2 = '\n'.join(lines2)
                new_html = (
                    new_html[:script_match.start(2)]
                    + js2
                    + new_html[script_match.end(2):]
                )
        final_issues = check_syntax(new_html)
        if not final_issues:
            return new_html, True, [f'[AUTO-FIX] {fix_desc} (+ passes supplémentaires)']

        return html, False, []

    except Exception as e:
        coordinateur_log.warning(f"fix_const_syntax_errors échoué : {e}")
        return html, False, []
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def _remove_single_var_from_line(line: str, ident: str) -> str:
    """
    Remove one variable declarator from a multi-declaration JS line, keeping the rest.
    Handles semicolon-separated statements and comma-separated declarators.
    Example:
      'const FIXED_DT=1/60,MAX_DT=0.1;let lastTime=0,accumulator=0;'
      remove 'lastTime' → 'const FIXED_DT=1/60,MAX_DT=0.1;let accumulator=0;'
    Returns empty string if the declarator was the only one on the line.
    """
    import re as _re
    statements = line.split(';')
    new_statements = []
    for stmt in statements:
        s = stmt.strip()
        if not s:
            new_statements.append('')
            continue
        kw_m = _re.match(r'^(\s*)(let|const|var)\s+(.*)', s, _re.DOTALL)
        if not kw_m:
            new_statements.append(stmt)
            continue
        indent, kw, rest = kw_m.group(1), kw_m.group(2), kw_m.group(3)
        declarators = [d.strip() for d in rest.split(',') if d.strip()]
        kept = [d for d in declarators
                if not _re.match(_re.escape(ident) + r'\s*=', d) and d != ident]
        if not kept:
            new_statements.append('')
        else:
            new_statements.append(indent + kw + ' ' + ', '.join(kept))
    result = ';'.join(new_statements)
    result = _re.sub(r';{2,}', ';', result).strip()
    return result


def fix_identifier_already_declared(html: str) -> tuple[str, bool, list[str]]:
    """
    Correction automatique de 'SyntaxError: Identifier X has already been declared'.
    Stratégie : convertir le const/let redéclaré en var (qui tolère les redéclarations).
    Retourne (html_corrigé, was_fixed, fix_descriptions).
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return html, False, []

    tmp = None
    fixes = []
    max_iterations = 5  # éviter les boucles infinies

    for _ in range(max_iterations):
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.js', encoding='utf-8', delete=False
            ) as f:
                f.write(js)
                tmp = f.name

            result = subprocess.run(
                ['node', '--check', tmp],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0:
                break  # syntaxe OK

            stderr = result.stderr or result.stdout
            if 'already been declared' not in stderr and 'already declared' not in stderr:
                break  # autre type d'erreur — ne pas toucher

            # Extraire le nom de l'identifiant et la ligne
            m_ident = re.search(r"Identifier '(\w+)' has already been declared", stderr)
            m_line = re.search(r'\.js:(\d+)', stderr)
            if not m_ident or not m_line:
                break

            ident = m_ident.group(1)
            line_num = int(m_line.group(1)) - 1  # 0-indexed
            lines = js.split('\n')
            if line_num >= len(lines):
                break

            original = lines[line_num]

            # Variables du template HTML — retirer seulement la variable en conflit
            # (jamais convertir en var, jamais effacer toute la ligne si multi-déclaration)
            _TEMPLATE_GLOBALS = frozenset({
                'canvas', 'ctx', 'W', 'H', 'dt', 'lastTime', 'gameState',
                # Timing ENGINE
                'FIXED_DT', 'MAX_DT', 'accumulator',
                # Dimensions
                'DPR', 'GAME_W', 'GAME_H',
                # Constantes template
                'TILE', 'TILE_SIZE', 'GAME_TITLE',
            })
            if ident in _TEMPLATE_GLOBALS:
                # Strategy: use ENGINE section boundaries to avoid removing ENGINE declarations.
                # The ENGINE section starts at '// ENGINE' and ends at the second '// ══' separator.
                # If line_num is OUTSIDE ENGINE → the reported line IS the LLM/patcher's duplicate → remove directly.
                # If line_num is INSIDE ENGINE → the reported line is ENGINE's own declaration → find duplicate after ENGINE.
                _eng_start = next((j for j, l in enumerate(lines) if '// ENGINE' in l), -1)
                _eng_end = next(
                    (j for j, l in enumerate(lines) if '// ══' in l and j > _eng_start + 2),
                    len(lines)
                )
                _decl_pat = re.compile(r'\b(?:const|let|var)\s+' + re.escape(ident) + r'\b')
                _removed = False
                if _eng_start >= 0 and _eng_start <= line_num <= _eng_end:
                    # Reported line is the ENGINE's own declaration → find LLM/patcher duplicate after ENGINE
                    for _j in range(_eng_end + 1, len(lines)):
                        if _decl_pat.search(lines[_j]):
                            _new = _remove_single_var_from_line(lines[_j], ident)
                            if not _new.strip():
                                lines.pop(_j)
                            else:
                                lines[_j] = _new
                            js = '\n'.join(lines)
                            fixes.append(f'[AUTO-FIX] Suppression redéclaration variable template : {ident} ligne {_j + 1}')
                            _removed = True
                            break
                    if not _removed:
                        # Also check BEFORE ENGINE — handles _HTML_TEMPLATE preamble conflicts
                        # (e.g. _HTML_TEMPLATE declares `var canvas` before ENGINE which has `const canvas`)
                        for _j in range(_eng_start):
                            if _decl_pat.search(lines[_j]):
                                _new = _remove_single_var_from_line(lines[_j], ident)
                                if not _new.strip():
                                    lines.pop(_j)
                                else:
                                    lines[_j] = _new
                                js = '\n'.join(lines)
                                fixes.append(f'[AUTO-FIX] Suppression redéclaration variable template (pre-ENGINE) : {ident} ligne {_j + 1}')
                                _removed = True
                                break
                else:
                    # Reported line is outside ENGINE → remove ident from reported line directly
                    _new = _remove_single_var_from_line(lines[line_num], ident)
                    if not _new.strip():
                        lines.pop(line_num)
                    else:
                        lines[line_num] = _new
                    js = '\n'.join(lines)
                    fixes.append(f'[AUTO-FIX] Suppression redéclaration variable template : {ident} ligne {line_num + 1}')
                    _removed = True
                if not _removed:
                    # Fallback: search everywhere except ENGINE section
                    for _j in range(len(lines)):
                        if _eng_start <= _j <= _eng_end:
                            continue
                        if _decl_pat.search(lines[_j]):
                            _new = _remove_single_var_from_line(lines[_j], ident)
                            if not _new.strip():
                                lines.pop(_j)
                            else:
                                lines[_j] = _new
                            js = '\n'.join(lines)
                            fixes.append(f'[AUTO-FIX] Suppression redéclaration variable template : {ident} ligne {_j + 1}')
                            break
                continue

            # Convertir const X = ... ou let X = ... en var X = ... sur cette ligne
            new_line = re.sub(r'\b(const|let)\s+' + re.escape(ident) + r'\b', f'var {ident}', original, count=1)
            if new_line == original:
                # Déjà un var — convertir en assignation (supprimer 'var') pour préserver le RHS multi-ligne
                if re.match(r'^\s*var\s+' + re.escape(ident) + r'\b', original):
                    new_line = re.sub(r'^(\s*)var\s+', r'\1', original)
                    lines[line_num] = new_line
                    js = '\n'.join(lines)
                    fixes.append(f'[AUTO-FIX] Suppression var dupliqué : {ident} ligne {line_num + 1}')
                else:
                    break  # impossible de corriger automatiquement
                continue

            lines[line_num] = new_line
            js = '\n'.join(lines)
            fixes.append(f'[AUTO-FIX] Identifier déjà déclaré : {ident} → var ligne {line_num + 1}')

        except Exception:
            break
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
                tmp = None

    if not fixes:
        return html, False, []

    # Reconstruire le HTML avec le JS corrigé
    script_match = re.search(
        r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not script_match:
        return html, False, []

    new_html = html[:script_match.start(2)] + js + html[script_match.end(2):]
    # Vérification finale
    final_issues = check_syntax(new_html)
    if not final_issues:
        for fix in fixes:
            coordinateur_log.info(fix)
        return new_html, True, fixes

    # Syntaxe toujours invalide mais peut-être une autre erreur — retourner quand même les fixes partiels
    return new_html, bool(fixes), fixes


def fix_missing_comma_before_brace(html: str) -> tuple[str, bool, list[str]]:
    """
    Corrige 'SyntaxError: Unexpected token {' causé par une virgule manquante
    entre deux éléments consécutifs d'un tableau d'objets.

    Pattern typique (LLM oublie la virgule sur les longs tableaux) :
        const EVENTS = [
          { id: 'foo', ... }       ← manque ","
          { id: 'bar', ... }       ← Unexpected token '{'
        ];

    Fix : si la ligne précédant l'erreur se termine par } (sans virgule),
    on insère une virgule.
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return html, False, []

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f:
            f.write(js)
            tmp = f.name

        result = subprocess.run(
            ['node', '--check', tmp],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            return html, False, []

        stderr = result.stderr or result.stdout
        if "Unexpected token '{'" not in stderr and "Unexpected token '{'" not in stderr:
            # Normalise les guillemets typographiques Node.js
            stderr_norm = stderr.replace('\u2018', "'").replace('\u2019', "'")
            if "Unexpected token '{'" not in stderr_norm:
                return html, False, []

        # Trouver la ligne de l'erreur
        m = re.search(r'\.js:(\d+)', stderr)
        if not m:
            return html, False, []

        line_num = int(m.group(1)) - 1  # 0-indexed
        lines = js.split('\n')
        if line_num == 0 or line_num >= len(lines):
            return html, False, []

        # Vérifier si la ligne d'erreur commence bien par `{` (élément tableau)
        err_line_stripped = lines[line_num].lstrip()
        if not err_line_stripped.startswith('{'):
            return html, False, []

        # Vérifier si la ligne précédente se termine par `}` sans virgule
        prev_line = lines[line_num - 1].rstrip()
        if not (prev_line.endswith('}') or prev_line.endswith('},')):
            return html, False, []
        if prev_line.endswith(','):
            return html, False, []  # virgule déjà présente

        # Insérer la virgule manquante
        lines[line_num - 1] = prev_line + ','
        new_js = '\n'.join(lines)

        # Reconstruire le HTML
        script_match = re.search(
            r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
            html, re.DOTALL | re.IGNORECASE
        )
        if not script_match:
            return html, False, []
        new_html = (
            html[:script_match.start(2)]
            + new_js
            + html[script_match.end(2):]
        )
        coordinateur_log.info(
            f"[AUTO-FIX] virgule manquante insérée avant ligne {line_num + 1} (Unexpected token '{{' corrigé)"
        )
        return new_html, True, [f"[AUTO-FIX] virgule manquante entre éléments tableau ligne {line_num}"]

    except Exception as e:
        coordinateur_log.warning(f"fix_missing_comma_before_brace échoué : {e}")
        return html, False, []
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def fix_literal_newlines_in_strings(html: str) -> tuple[str, bool, list[str]]:
    """
    Remplace les sauts de ligne littéraux dans les string literals JS (quotes simples ou doubles)
    par l'escape \\n. Ignore les template literals (backticks) qui supportent le multiline.
    Cause typique : utils_dev_console.py _CONSOLE_JS avec split('\\n') où \\n était un vrai newline.
    """
    fixes: list[str] = []
    any_fixed = False

    def fix_in_js(js: str) -> tuple[str, bool]:
        result = []
        i = 0
        fixed = False
        while i < len(js):
            ch = js[i]
            if ch in ('"', "'"):
                quote = ch
                result.append(ch)
                i += 1
                while i < len(js):
                    c = js[i]
                    if c == '\\':
                        result.append(c)
                        i += 1
                        if i < len(js):
                            result.append(js[i])
                            i += 1
                    elif c == '\n':
                        result.append('\\n')
                        i += 1
                        fixed = True
                    elif c == quote:
                        result.append(c)
                        i += 1
                        break
                    else:
                        result.append(c)
                        i += 1
            elif ch == '`':
                result.append(ch)
                i += 1
                while i < len(js):
                    c = js[i]
                    if c == '\\':
                        result.append(c)
                        i += 1
                        if i < len(js):
                            result.append(js[i])
                            i += 1
                    elif c == '`':
                        result.append(c)
                        i += 1
                        break
                    else:
                        result.append(c)
                        i += 1
            elif ch == '/' and i + 1 < len(js):
                if js[i+1] == '/':
                    end = js.find('\n', i)
                    if end == -1:
                        result.append(js[i:])
                        i = len(js)
                    else:
                        result.append(js[i:end+1])
                        i = end + 1
                elif js[i+1] == '*':
                    end = js.find('*/', i + 2)
                    if end == -1:
                        result.append(js[i:])
                        i = len(js)
                    else:
                        result.append(js[i:end+2])
                        i = end + 2
                else:
                    result.append(ch)
                    i += 1
            else:
                result.append(ch)
                i += 1
        return ''.join(result), fixed

    def replace_script(m):
        nonlocal any_fixed
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        new_body, fixed = fix_in_js(body)
        if fixed:
            any_fixed = True
            fixes.append('[AUTO-FIX] Saut de ligne littéral dans string JS → \\n escape')
            return open_tag + new_body + close_tag
        return m.group(0)

    html = re.sub(
        r'(<script(?:\s(?!src)[^>]*)?>)(.*?)(</script>)',
        replace_script,
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    return html, any_fixed, fixes


def fix_illegal_return_statements(html: str) -> tuple[str, bool, list[str]]:
    """
    Supprime les `return` au niveau 0 de portée (hors de toute fonction).
    Node.js CommonJS ne les détecte pas mais le navigateur lève
    'Uncaught SyntaxError: Illegal return statement' au runtime.
    Stratégie : parcourir le JS char-par-char pour compter la profondeur
    d'accolades ; toute ligne `return …;` à profondeur 0 est supprimée.
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return html, False, []

    lines = js.splitlines(keepends=True)
    depth = 0
    in_single = False   # inside //
    in_multi = False    # inside /* */
    in_str_s = False    # inside '
    in_str_d = False    # inside "
    in_tpl = False      # inside `
    removed = []

    new_lines = []
    for lineno, raw in enumerate(lines):
        # Track brace depth char-by-char (naïve: ignore regex literals)
        line_start_depth = depth
        i = 0
        while i < len(raw):
            c = raw[i]
            # Multi-line comment toggle
            if in_multi:
                if c == '*' and i + 1 < len(raw) and raw[i+1] == '/':
                    in_multi = False
                    i += 2
                    continue
                i += 1
                continue
            # Single-line comment — rest of line is comment
            if in_single:
                if c == '\n':
                    in_single = False
                i += 1
                continue
            # String/template tracking
            if in_str_s:
                if c == '\\':
                    i += 2
                    continue
                if c == "'":
                    in_str_s = False
                i += 1
                continue
            if in_str_d:
                if c == '\\':
                    i += 2
                    continue
                if c == '"':
                    in_str_d = False
                i += 1
                continue
            if in_tpl:
                if c == '\\':
                    i += 2
                    continue
                if c == '`':
                    in_tpl = False
                i += 1
                continue
            # Start of comment or string
            if c == '/' and i + 1 < len(raw):
                if raw[i+1] == '/':
                    in_single = True
                    i += 2
                    continue
                if raw[i+1] == '*':
                    in_multi = True
                    i += 2
                    continue
            if c == "'":
                in_str_s = True
            elif c == '"':
                in_str_d = True
            elif c == '`':
                in_tpl = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth = max(0, depth - 1)
            i += 1

        # If this line was entirely at depth 0 and is a bare `return`
        if line_start_depth == 0 and depth == 0:
            stripped = raw.strip()
            if re.match(r'^return\b', stripped):
                removed.append(lineno + 1)
                continue  # skip this line

        new_lines.append(raw)

    if not removed:
        return html, False, []

    new_js = ''.join(new_lines)
    script_match = re.search(
        r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not script_match:
        return html, False, []

    new_html = html[:script_match.start(2)] + new_js + html[script_match.end(2):]
    descs = [f'[AUTO-FIX] return hors fonction supprimé ligne {ln}' for ln in removed]
    for d in descs:
        coordinateur_log.info(d)
    return new_html, True, descs


_PALETTE_COLOR_HINTS = [
    ('neon', '#00ffcc'), ('cyan', '#00ffff'), ('teal', '#00ffcc'),
    ('magenta', '#ff00ff'), ('purple', '#8800ff'), ('violet', '#8800ff'),
    ('orange', '#ff6600'), ('gold', '#ffd700'), ('yellow', '#ffff00'),
    ('green', '#00ff44'), ('lime', '#aaff00'),
    ('pink', '#ff0088'), ('red', '#ff2200'), ('fire', '#ff4400'),
    ('blue', '#0088ff'), ('ice', '#88ddff'), ('shield', '#00aaff'),
    ('white', '#ffffff'), ('dark', '#0a0a1a'), ('gray', '#888888'),
    ('bg', '#0a0a1a'), ('back', '#0a0a1a'),
    ('player', '#00ffcc'), ('enemy', '#ff4444'), ('boss', '#ff00ff'),
    ('bullet', '#ffff00'), ('ui', '#ffffff'), ('hud', '#ffffff'),
    ('particle', '#ffaa00'), ('hit', '#ff8800'), ('damage', '#ff0000'),
]


def _guess_palette_color(key: str) -> str:
    kl = key.lower()
    for hint, col in _PALETTE_COLOR_HINTS:
        if hint in kl:
            return col
    return '#ffffff'


def fix_duplicate_palette(html: str) -> tuple[str, bool, list[str]]:
    """
    Détecte les redéclarations de PALETTE (var PALETTE = {...}) dans un même script.
    Remplace les déclarations dupliquées (2e, 3e...) par Object.assign(PALETTE, {...})
    pour fusionner les clés sans écraser la définition complète de L1.
    """
    fixes: list[str] = []

    def fix_in_script(js: str) -> tuple[str, bool]:
        decls = list(re.finditer(r'\bvar\s+PALETTE\s*=\s*\{', js))
        if len(decls) < 2:
            return js, False
        changed = False
        # Traiter de la fin vers le début pour ne pas décaler les offsets
        for decl in reversed(decls[1:]):
            brace_start = decl.end() - 1
            depth = 0
            i = brace_start
            while i < len(js):
                if js[i] == '{':
                    depth += 1
                elif js[i] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            obj_body = js[decl.end():i]
            old_text = js[decl.start():i + 1]
            new_text = f'Object.assign(PALETTE, {{{obj_body}}})'
            js = js[:decl.start()] + new_text + js[i + 1:]
            changed = True
        return js, changed

    def replace_script(m):
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        new_body, changed = fix_in_script(body)
        if changed:
            fixes.append('[AUTO-FIX] PALETTE redéclaré → Object.assign (fusion sans perte des clés)')
            return open_tag + new_body + close_tag
        return m.group(0)

    new_html = re.sub(
        r'(<script(?:\s(?!src)[^>]*)?>)(.*?)(</script>)',
        replace_script,
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    if fixes:
        for f in fixes:
            coordinateur_log.info(f)
    return new_html, bool(fixes), fixes


def fix_palette_missing_keys(html: str) -> tuple[str, bool, list[str]]:
    """
    Détecte les références PALETTE.xxx utilisées dans le JS mais absentes de l'objet PALETTE.
    Injecte les clés manquantes directement dans l'objet PALETTE avec une couleur déduite du nom.
    Couvre le cas où le Patcher ou L9 invente une clé que L1 n'a pas déclarée.
    """
    js = extract_js_from_html(html)
    if not js:
        return html, False, []

    palette_m = re.search(r'\bvar\s+PALETTE\s*=\s*\{([^}]+)\}', js, re.DOTALL)
    if not palette_m:
        return html, False, []

    declared = set(re.findall(r'(\w+)\s*:', palette_m.group(1)))
    used = set(re.findall(r'\bPALETTE\.(\w+)\b', js))
    missing = used - declared
    if not missing:
        return html, False, []

    new_entries = ', '.join(
        f"{k}: '{_guess_palette_color(k)}'"
        for k in sorted(missing)
    )
    new_js = re.sub(
        r'(\bvar\s+PALETTE\s*=\s*\{)([^}]+)(\})',
        lambda m: m.group(1) + m.group(2).rstrip().rstrip(',') + ', ' + new_entries + m.group(3),
        js, count=1, flags=re.DOTALL
    )

    script_m = re.search(
        r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not script_m:
        return html, False, []

    new_html = html[:script_m.start(2)] + new_js + html[script_m.end(2):]
    descs = [f'[AUTO-FIX] PALETTE.{k} = {_guess_palette_color(k)} (clé manquante)' for k in sorted(missing)]
    for d in descs:
        coordinateur_log.info(d)
    return new_html, True, descs


def _guess_var_default(name: str) -> str:
    """Infer a safe JS default value for an auto-declared variable."""
    n = name.lower()
    if any(n.endswith(s) for s in ('active', 'visible', 'enabled', 'started', 'ready', 'open', 'alive')):
        return 'false'
    if any(n.endswith(s) for s in ('list', 'arr', 'items', 'tiles', 'nodes', 'enemies', 'bullets', 'particles', 'texts', 'stars', 'effects')):
        return '[]'
    if any(n.endswith(s) for s in ('color', 'col', 'style', 'bg', 'fill', 'stroke')):
        return '"#ffffff"'
    if any(n.endswith(s) for s in ('size', 'width', 'height', 'radius', 'len', 'length', 'gap', 'spacing')):
        return '32'
    if any(n.endswith(s) for s in ('speed', 'rate', 'scale', 'factor', 'mult')):
        return '1'
    if n.endswith('pool'):
        return '{get:function(){return{};},release:function(){},items:[]}'
    return '0'


def check_undefined_vars_eslint(html: str) -> list[str]:
    """
    Option B — Détection PRÉVENTIVE des variables non déclarées via ESLint no-undef.
    Retourne la liste des noms de variables undefined (filtrés des globals connus).
    Retourne [] si eslint indisponible ou aucune erreur.
    Three.js files are skipped — ESLint times out on them and THREE.* globals
    produce noise that obscures real errors.
    """
    # Fix 3D-D: skip ESLint for Three.js games (timeouts + THREE.* global noise)
    if re.search(r'three(?:\.min)?\.js|cdn.*three|three.*cdn', html, re.IGNORECASE):
        return []

    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return []

    # Injecter un commentaire de globals connus pour éviter les faux-positifs
    _known = sorted(_BROWSER_AND_TEMPLATE_GLOBALS)
    preamble = '/* global ' + ', '.join(_known) + ' */\n'
    full_js = preamble + js

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f:
            f.write(full_js)
            tmp = f.name

        # shell=True requis sur Windows pour résoudre npx.cmd via PATH
        _eslint_cmd = f'npx --yes eslint --no-eslintrc --rule \'{{"no-undef":["error"]}}\' --env browser --format json "{tmp}"'
        result = subprocess.run(
            _eslint_cmd,
            shell=True,
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return []

        try:
            data = _json.loads(result.stdout or '[]')
        except Exception:
            return []

        undef_vars = []
        for file_result in data:
            for msg in file_result.get('messages', []):
                if msg.get('ruleId') == 'no-undef':
                    m = re.search(r"'(\w+)' is not defined", msg.get('message', ''))
                    if m and m.group(1) not in _BROWSER_AND_TEMPLATE_GLOBALS:
                        undef_vars.append(m.group(1))

        return list(dict.fromkeys(undef_vars))  # dédupliqué, ordre préservé

    except FileNotFoundError:
        coordinateur_log.warning("eslint/npx non trouvé — check no-undef ignoré")
        return []
    except subprocess.TimeoutExpired:
        coordinateur_log.warning("eslint timeout on full file — retrying on first 60K chars")
        # Truncate to 60K and retry with shorter timeout
        tmp2 = None
        try:
            truncated = preamble + js[:60000]
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.js', encoding='utf-8', delete=False
            ) as f2:
                f2.write(truncated)
                tmp2 = f2.name
            _cmd2 = f'npx --yes eslint --no-eslintrc --rule \'{{"no-undef":["error"]}}\' --env browser --format json "{tmp2}"'
            result2 = subprocess.run(_cmd2, shell=True, capture_output=True, text=True, timeout=20)
            if result2.returncode == 0:
                return []
            try:
                data2 = _json.loads(result2.stdout or '[]')
            except Exception:
                return []
            undef2 = []
            for fr in data2:
                for msg in fr.get('messages', []):
                    if msg.get('ruleId') == 'no-undef':
                        m2 = re.search(r"'(\w+)' is not defined", msg.get('message', ''))
                        if m2 and m2.group(1) not in _BROWSER_AND_TEMPLATE_GLOBALS:
                            undef2.append(m2.group(1))
            return list(dict.fromkeys(undef2))
        except subprocess.TimeoutExpired:
            coordinateur_log.warning("eslint timeout on truncated file too — check no-undef ignoré")
            return []
        except Exception as e2:
            coordinateur_log.warning(f"eslint truncated retry failed: {e2}")
            return []
        finally:
            if tmp2 and os.path.exists(tmp2):
                os.unlink(tmp2)
    except Exception as e:
        coordinateur_log.warning(f"eslint check échoué : {e}")
        return []
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def fix_undefined_runtime_vars(html: str, var_names: set) -> tuple[str, bool, list[str]]:
    """
    Option A — Injection de déclarations pour les variables runtime undefined.
    Utilisé de façon RÉACTIVE (post-Playwright) et PRÉVENTIVE (post-eslint).
    - Identifiant appelé comme fonction (updateShake(dt)) → stub function(){}
    - Identifiant utilisé comme valeur → var X = <default déduit du nom>
    """
    js = extract_js_from_html(html)
    # Skip variables that are computed distances/angles — stubbing them to 0 creates gameplay bugs
    _SKIP_STUB_PREFIXES = ('dist', 'Dist', 'angle', 'Angle', 'dx', 'dy', 'dz')
    to_declare = sorted(
        v for v in var_names
        if v and v.isidentifier()
        and v not in _BROWSER_AND_TEMPLATE_GLOBALS
        and not any(v.startswith(p) for p in _SKIP_STUB_PREFIXES)
    )
    if not to_declare:
        return html, False, []

    # Canvas-exclusive method patterns — only these prove v is a ctx alias (not physics coords)
    # Excludes transform/scale/rotate/translate which appear in Three.js and physics libs
    _CTX_METHODS = r'\.(beginPath|fillRect|strokeRect|clearRect|fill|stroke|save|restore|clip|arc|moveTo|lineTo|bezierCurveTo|fillText|strokeText|drawImage|createLinearGradient|createRadialGradient)\s*\('

    inject_lines = []
    descs = []
    for v in to_declare:
        is_fn_call = bool(js and re.search(r'\b' + re.escape(v) + r'\s*\(', js))
        is_ctx_alias = bool(js and re.search(r'\b' + re.escape(v) + _CTX_METHODS, js))
        if is_ctx_alias:
            # Guard ctx reference with typeof to avoid TDZ crash when const ctx is declared later
            inject_lines.append(
                f'var {v}=(typeof {v}!=="undefined")?{v}:(typeof ctx!=="undefined"?ctx:null);'
            )
            descs.append(f'[AUTO-FIX] var {v} = ctx (canvas context alias détecté)')
        elif is_fn_call:
            inject_lines.append(
                f'if(typeof {v}==="undefined")var {v}=function(){{}};'
            )
            descs.append(f'[AUTO-FIX] function stub {v}() (appel détecté)')
        else:
            default = _guess_var_default(v)
            inject_lines.append(
                f'var {v}=(typeof {v}!=="undefined")?{v}:{default};'
            )
            descs.append(f'[AUTO-FIX] var {v} = {default} (undefined détecté)')

    inject_block = '\n'.join(inject_lines) + '\n'

    script_m = re.search(r'(<script(?:\s[^>]*)?>)', html, re.IGNORECASE)
    if not script_m:
        return html, False, []

    new_html = html[:script_m.end()] + '\n' + inject_block + html[script_m.end():]
    for d in descs:
        coordinateur_log.info(d)
    return new_html, True, descs


def fix_let_dot_notation(html: str) -> tuple[str, bool, list[str]]:
    """Fix `let/const/var X.Y = value;` — dot-notation with a declaration keyword is a SyntaxError.

    LLMs sometimes generate `let GameName.property = value;` trying to use a namespace pattern.
    JavaScript does not allow `let` with dot-notation. The fix: remove the `let/const/var` keyword.
    """
    fixes: list[str] = []

    def fix_block(m: re.Match) -> str:
        open_tag, content, close_tag = m.group(1), m.group(2), m.group(3)
        if re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            return m.group(0)
        fixed, count = re.subn(
            r'\b(let|const|var)\s+(\w+\.\w[\w.]*)\s*=',
            r'\2 =',
            content,
        )
        if count:
            fixes.append(f"fix_let_dot_notation: {count} `let/const/var X.Y=` → `X.Y=` (SyntaxError removed)")
        return f"{open_tag}{fixed}{close_tag}"

    new_html = re.sub(
        r'(<script(?:\s[^>]*)?>)(.*?)(</script>)',
        fix_block,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return new_html, bool(fixes), fixes


def fix_markdown_code_fences(html: str) -> tuple[str, bool, list[str]]:
    """Remove Markdown code fence lines (```javascript, ```) from inside <script> blocks.

    LLMs sometimes wrap generated code in Markdown fences. Inside a <script> tag
    these triple-backtick lines are parsed as template literals, breaking all
    syntax after them.
    """
    fixes: list[str] = []

    def clean_block(m: re.Match) -> str:
        open_tag = m.group(1)
        content = m.group(2)
        # Skip CDN/external scripts
        if re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            return m.group(0)
        cleaned_lines = []
        removed = 0
        for line in content.split('\n'):
            if re.match(r'^\s*```', line):
                removed += 1
            else:
                cleaned_lines.append(line)
        if removed:
            fixes.append(f'[AUTO-FIX] {removed} Markdown code fence line(s) removed from script block')
            return f'{open_tag}{chr(10).join(cleaned_lines)}</script>'
        return m.group(0)

    new_html = re.sub(
        r'(<script(?:\s[^>]*)?>)(.*?)(</script>)',
        clean_block,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fixes:
        for f in fixes:
            coordinateur_log.info(f)
    return new_html, bool(fixes), fixes


def fix_cdn_script_content(html: str) -> tuple[str, bool, list[str]]:
    """Move inline content out of <script src="..."> tags into a separate <script> block.

    Browsers ignore inline content when src is present, so game code placed
    inside CDN script tags (e.g. three.js) never executes.

    For Three.js CDN tags specifically: if a clean Three.js CDN tag already exists
    elsewhere in the HTML, the duplicate LLM-injected CDN tag is dropped entirely
    (keeping only its content) to avoid loading an older Three.js version that would
    overwrite the correct one.
    """
    fixes: list[str] = []

    # Count existing clean Three.js CDN tags (src= present, no substantial inline content)
    _clean_threejs = re.findall(
        r'<script\b[^>]*\bsrc\s*=[^>]*three(?:\.min)?\.js[^>]*>\s*</script>',
        html, re.IGNORECASE
    )
    has_clean_threejs_cdn = len(_clean_threejs) > 0

    def replacer(m: re.Match) -> str:
        open_tag: str = m.group(1)
        content: str = m.group(2)
        stripped = content.strip()
        if not re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            return m.group(0)
        if len(stripped) < 50:
            return m.group(0)
        is_threejs = bool(re.search(r'three(?:\.min)?\.js', open_tag, re.IGNORECASE))
        if is_threejs and has_clean_threejs_cdn:
            # Assembler template already has the correct CDN tag — drop this duplicate
            fixes.append(
                f"[AUTO-FIX] {len(stripped)} chars of game code extracted; duplicate Three.js CDN tag dropped"
            )
            return f'<script>\n{content}\n</script>'
        fixes.append(
            f"[AUTO-FIX] {len(stripped)} chars of game code moved out of CDN script tag"
        )
        return f'{open_tag}</script>\n<script>\n{content}\n</script>'

    new_html = re.sub(
        r'(<script(?:\s[^>]*)?>)(.*?)(</script>)',
        replacer,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fixes:
        for f in fixes:
            coordinateur_log.info(f)
    return new_html, bool(fixes), fixes


def fix_stray_script_close(html: str) -> tuple[str, bool, list[str]]:
    """
    Removes accidental </script> occurrences inside the game <script> block.
    Caused by LLM generating strings/comments containing '</script>', which
    prematurely closes the HTML script tag and makes the entire JS invalid.
    Strategy: find the last </script> (real end), find the last <script> before
    it (real open), then escape any </script> found inside that range.
    """
    html_lower = html.lower()
    # Find the real closing tag: the LAST </script> in the document
    last_close = html_lower.rfind('</script>')
    if last_close == -1:
        return html, False, []

    # Find the last <script> opening tag before that closing tag
    prefix = html[:last_close]
    open_tags = list(re.finditer(r'<script(?:\s[^>]*)?>', prefix, re.IGNORECASE))
    if not open_tags:
        return html, False, []
    last_open = open_tags[-1]
    open_end = last_open.end()  # position right after the opening <script> tag

    # The "inner" is everything between the opening tag and the last </script>
    inner = html[open_end:last_close]

    # Escape any </script> found inside (these are the strays)
    cleaned = re.sub(r'<\s*/\s*script\s*>', r'<\\/script>', inner, flags=re.IGNORECASE)
    if cleaned == inner:
        return html, False, []

    count = inner.lower().count('</script>') + inner.lower().count('</ script>')
    new_html = html[:open_end] + cleaned + html[last_close:]
    desc = f"[AUTO-FIX] {count} stray </script> inside game script block — escaped to <\\/script>"
    coordinateur_log.info(desc)
    return new_html, True, [desc]


def fix_unexpected_identifier(html: str) -> tuple[str, bool, list[str]]:
    """
    Fix 'SyntaxError: Unexpected identifier X' — caused by a missing semicolon
    between two consecutive statements (ASI failure). Node.js reports the LINE
    of the unexpected identifier; we insert a semicolon at the end of the
    PREVIOUS non-blank line.
    Retourne (html_corrigé, was_fixed, fix_descriptions).
    """
    js = extract_js_from_html(html)
    if not js or len(js) < 200:
        return html, False, []

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f:
            f.write(js)
            tmp = f.name

        result = subprocess.run(
            ['node', '--check', tmp],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            return html, False, []

        stderr = result.stderr or result.stdout
        # Match "Unexpected identifier 'SOMETHING'"
        m_err = re.search(r"Unexpected identifier '?(\w+)'?", stderr)
        if not m_err:
            return html, False, []

        identifier = m_err.group(1)

        # Extract line number from Node output
        m_line = re.search(r'\.js:(\d+)', stderr)
        if not m_line:
            return html, False, []

        line_num = int(m_line.group(1)) - 1  # 0-indexed
        lines = js.split('\n')
        if line_num <= 0 or line_num >= len(lines):
            return html, False, []

        # Find the previous non-blank line
        prev_idx = line_num - 1
        while prev_idx >= 0 and not lines[prev_idx].strip():
            prev_idx -= 1
        if prev_idx < 0:
            return html, False, []

        prev_line = lines[prev_idx]
        # Only add semicolon if the line doesn't already end with one
        stripped = prev_line.rstrip()
        if stripped.endswith((';', '{', '}', ',')):
            return html, False, []

        lines[prev_idx] = stripped + ';'
        new_js = '\n'.join(lines)

        # Verify the fix didn't break things further
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', encoding='utf-8', delete=False
        ) as f2:
            f2.write(new_js)
            tmp2 = f2.name
        try:
            r2 = subprocess.run(['node', '--check', tmp2],
                                capture_output=True, text=True, timeout=20)
            # Only accept if errors reduced or gone
            if r2.returncode != 0:
                stderr2 = r2.stderr or r2.stdout
                # If same error still present, not worth applying
                if m_err.group(0) in stderr2:
                    return html, False, []
        finally:
            if os.path.exists(tmp2):
                os.unlink(tmp2)

        # Replace JS in HTML
        if js in html:
            new_html = html.replace(js, new_js, 1)
        else:
            return html, False, []

        fix_desc = f"[AUTO-FIX] Unexpected identifier '{identifier}' — semicolon inserted line {prev_idx + 1}"
        coordinateur_log.info(fix_desc)
        return new_html, True, [fix_desc]

    except Exception:
        return html, False, []
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


_THREEJS_POLYFILL_MARKER = 'THREE.Capsule=function'

_THREEJS_POLYFILL_BLOCK = """\
<script>
// Polyfill: classes from Three.js examples/jsm — not included in the main bundle
if(typeof THREE!=='undefined'){
  if(!THREE.Capsule){THREE.Capsule=function(s,e,r){this.start=s?s.clone():new THREE.Vector3(0,0,0);this.end=e?e.clone():new THREE.Vector3(0,1,0);this.radius=r!==undefined?r:0.5;this.getCenter=function(t){return t.addVectors(this.start,this.end).multiplyScalar(0.5);};this.translate=function(v){this.start.add(v);this.end.add(v);return this;};this.copy=function(c){this.start.copy(c.start);this.end.copy(c.end);this.radius=c.radius;return this;};this.set=function(a,b,r){this.start.copy(a);this.end.copy(b);this.radius=r;return this;};this.clone=function(){return new THREE.Capsule(this.start,this.end,this.radius);};};};
  if(!THREE.Octree){THREE.Octree=function(){this.fromGraphNode=function(){};this.capsuleIntersect=function(){return false;};this.rayIntersect=function(){return false;};};};
  if(!THREE.OctreeHelper){THREE.OctreeHelper=function(){THREE.Object3D.call(this);};THREE.OctreeHelper.prototype=Object.create(THREE.Object3D.prototype);THREE.OctreeHelper.prototype.update=function(){};};
}
</script>"""


def inject_threejs_polyfills(html: str) -> tuple[str, bool, list[str]]:
    """
    If the HTML loads Three.js from CDN and uses THREE.Capsule/Octree (jsm-only classes),
    inject a polyfill <script> block right after the Three.js CDN tag so those constructors exist.
    """
    threejs_cdn = re.search(
        r'<script\b[^>]*\bsrc\s*=[^>]*three(?:\.min)?\.js[^>]*>\s*</script>',
        html, re.IGNORECASE
    )
    if not threejs_cdn:
        return html, False, []
    if _THREEJS_POLYFILL_MARKER in html:
        return html, False, []
    uses_jsm = bool(re.search(r'\bTHREE\.(Capsule|Octree|OctreeHelper)\b', html))
    if not uses_jsm:
        return html, False, []
    insert_pos = threejs_cdn.end()
    new_html = html[:insert_pos] + '\n  ' + _THREEJS_POLYFILL_BLOCK + html[insert_pos:]
    msg = '[AUTO-FIX] THREE.js polyfill injected (Capsule/Octree used but not in main bundle)'
    coordinateur_log.info(msg)
    return new_html, True, [msg]


def fix_threejs_duplicate_renderer(html: str) -> tuple[str, bool, list[str]]:
    """
    In modular Three.js code, multiple modules may each declare `new THREE.WebGLRenderer()`.
    The second+ renderer fails to get a WebGL context (already used), making domElement invalid
    → 'Failed to execute appendChild on Node: parameter 1 is not of type Node'.
    Fix: keep only the first WebGLRenderer instantiation per script block.
    """
    if html.count('THREE.WebGLRenderer') < 2:
        return html, False, []
    fixes: list[str] = []

    def fix_in_script(js: str) -> str:
        occurrences = list(re.finditer(r'[^\n]*\bnew\s+THREE\.WebGLRenderer\s*\([^\n]*\n', js))
        if len(occurrences) < 2:
            return js
        changed = js
        for m in reversed(occurrences[1:]):
            changed = changed[:m.start()] + changed[m.end():]
            fixes.append('[AUTO-FIX] Duplicate THREE.WebGLRenderer instantiation removed (only first kept)')
        return changed

    def process_script(m):
        open_tag = m.group(1)
        content = m.group(2)
        if re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            return m.group(0)
        new_content = fix_in_script(content)
        if new_content != content:
            return f'{open_tag}{new_content}</script>'
        return m.group(0)

    new_html = re.sub(r'(<script(?:\s[^>]*)?>)(.*?)(</script>)', process_script, html, flags=re.DOTALL | re.IGNORECASE)
    if fixes:
        for f in fixes:
            coordinateur_log.info(f)
    return new_html, bool(fixes), fixes


def fix_threejs_canvas_context_conflict(html: str) -> tuple[str, bool, list[str]]:
    """
    In Three.js games, the renderer creates its own WebGL canvas.
    If the game code also calls canvas.getContext('2d') on the same canvas,
    WebGL and 2D contexts conflict → 'Canvas has an existing context of a different type'.
    Fix: remove any .getContext('2d') calls inside <script> blocks that also use THREE.WebGLRenderer.
    """
    if 'THREE.WebGLRenderer' not in html:
        return html, False, []
    fixes: list[str] = []

    def fix_in_script(js: str) -> str:
        if 'THREE.WebGLRenderer' not in js:
            return js
        changed = js
        # Pattern 1: canvas.getContext('2d') or .getContext("2d") — line with assignment
        # e.g.: const ctx = canvas.getContext('2d');
        pattern = re.compile(
            r"[^\n]*\.getContext\s*\(\s*['\"]2d['\"]\s*\)[^\n]*\n",
            re.IGNORECASE
        )
        new_js = pattern.sub('', changed)
        if new_js != changed:
            fixes.append("[AUTO-FIX] Removed canvas.getContext('2d') conflicting with THREE.WebGLRenderer WebGL context")
            changed = new_js
        return changed

    def process_script(m):
        open_tag = m.group(1)
        content = m.group(2)
        if re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            return m.group(0)
        new_content = fix_in_script(content)
        if new_content != content:
            return f'{open_tag}{new_content}</script>'
        return m.group(0)

    new_html = re.sub(r'(<script(?:\s[^>]*)?>)(.*?)(</script>)', process_script, html, flags=re.DOTALL | re.IGNORECASE)
    if fixes:
        for f in fixes:
            coordinateur_log.info(f)
    return new_html, bool(fixes), fixes


def fix_all_auto(html: str) -> tuple[str, bool, list[str]]:
    """
    Applique toutes les corrections automatiques disponibles en cascade :
    -1. fix_literal_newlines_in_strings (\\n littéral dans string JS → \\\\n)
    0. fix_illegal_return_statements (return hors fonction — invisible à Node.js CJS)
    1. fix_missing_comma_before_brace (virgule manquante entre éléments tableau)
    2. fix_const_syntax_errors (const/let en switch/for) — boucle jusqu'à 10×
    2b. fix_unexpected_identifier (missing semicolon between statements)
    2c. fix_exact_syntax_error (surgical: missing/extra brace or ; from exact node error) — boucle jusqu'à 5×
    3. fix_identifier_already_declared (redéclarations) — boucle jusqu'à 5×
    4. fix_palette_missing_keys (clés PALETTE manquantes)
    5. check_undefined_vars_eslint + fix_undefined_runtime_vars
    Retourne (html_final, any_fixed, toutes_les_descriptions).
    """
    all_fixes = []
    any_fixed = False

    # Étape -6 : `let/const/var X.Y = value;` — dot-notation with declaration keyword is SyntaxError
    html, fixed_ldn, descs_ldn = fix_let_dot_notation(html)
    if fixed_ldn:
        any_fixed = True
        all_fixes.extend(descs_ldn)

    # Étape -5 : Markdown code fences inside <script> blocks (``` or ```javascript)
    html, fixed_md, descs_md = fix_markdown_code_fences(html)
    if fixed_md:
        any_fixed = True
        all_fixes.extend(descs_md)

    # Étape -4 : game code inside CDN <script src="..."> tag — browsers ignore inline content
    html, fixed_cdn, descs_cdn = fix_cdn_script_content(html)
    if fixed_cdn:
        any_fixed = True
        all_fixes.extend(descs_cdn)

    # Étape -3.5 : inject Three.js polyfills (Capsule/Octree not in main bundle) when needed
    html, fixed_poly, descs_poly = inject_threejs_polyfills(html)
    if fixed_poly:
        any_fixed = True
        all_fixes.extend(descs_poly)

    # Étape -3.4 : remove duplicate THREE.WebGLRenderer instantiations (second fails to get context)
    html, fixed_dup, descs_dup = fix_threejs_duplicate_renderer(html)
    if fixed_dup:
        any_fixed = True
        all_fixes.extend(descs_dup)

    # Étape -3.3 : remove canvas.getContext('2d') that conflicts with THREE.WebGLRenderer WebGL context
    html, fixed_ctx, descs_ctx = fix_threejs_canvas_context_conflict(html)
    if fixed_ctx:
        any_fixed = True
        all_fixes.extend(descs_ctx)

    # Étape -3 : stray </script> inside game script block (highest priority — unblocks all 3D fixes)
    html, fixed_sc, descs_sc = fix_stray_script_close(html)
    if fixed_sc:
        any_fixed = True
        all_fixes.extend(descs_sc)

    # Étape -2 : PALETTE redéclaré (var PALETTE = {...} en double → écrase les clés)
    html, fixed_dp, descs_dp = fix_duplicate_palette(html)
    if fixed_dp:
        any_fixed = True
        all_fixes.extend(descs_dp)

    # Étape -1 : sauts de ligne littéraux dans strings JS (SyntaxError: Invalid token)
    html, fixed_nl, descs_nl = fix_literal_newlines_in_strings(html)
    if fixed_nl:
        any_fixed = True
        all_fixes.extend(descs_nl)

    # Étape 0 : return hors fonction (browser crash, invisible à Node.js CJS)
    html, fixed_r, descs_r = fix_illegal_return_statements(html)
    if fixed_r:
        any_fixed = True
        all_fixes.extend(descs_r)

    # Boucle sur fix_missing_comma_before_brace : un seul `{` inattendu visible à la fois
    for _ in range(10):
        html, fixed0, descs0 = fix_missing_comma_before_brace(html)
        if not fixed0:
            break
        any_fixed = True
        all_fixes.extend(descs0)

    # Boucle sur fix_const_syntax_errors : une seule SyntaxError visible à la fois
    for _ in range(10):
        html, fixed1, descs1 = fix_const_syntax_errors(html)
        if not fixed1:
            break
        any_fixed = True
        all_fixes.extend(descs1)

    # Boucle sur fix_unexpected_identifier (missing semicolons) — boucle jusqu'à 10×
    for _ in range(10):
        html, fixed_ui, descs_ui = fix_unexpected_identifier(html)
        if not fixed_ui:
            break
        any_fixed = True
        all_fixes.extend(descs_ui)

    # Surgical catch-all: read exact node --check error and apply minimal fix (missing/extra brace, ;)
    for _ in range(5):
        html, fixed_syn, descs_syn = fix_exact_syntax_error(html)
        if not fixed_syn:
            break
        any_fixed = True
        all_fixes.extend(descs_syn)

    html, fixed2, descs2 = fix_identifier_already_declared(html)
    if fixed2:
        any_fixed = True
        all_fixes.extend(descs2)

    # Étape 4 — PALETTE clés manquantes (ex: PALETTE.neonCyan inventé par L9 absent de L1)
    html, fixed3, descs3 = fix_palette_missing_keys(html)
    if fixed3:
        any_fixed = True
        all_fixes.extend(descs3)

    # Étape 5 — Option B : ESLint no-undef — détection préventive des variables non déclarées
    # (après PALETTE fix pour éviter les faux-positifs sur les clés fraîchement ajoutées)
    _eslint_undefs = check_undefined_vars_eslint(html)
    if _eslint_undefs:
        coordinateur_log.info(f"[B6-eslint] {len(_eslint_undefs)} var(s) non déclarée(s) : {', '.join(_eslint_undefs[:8])}")
        html, fixed4, descs4 = fix_undefined_runtime_vars(html, set(_eslint_undefs))
        if fixed4:
            any_fixed = True
            all_fixes.extend(descs4)

    return html, any_fixed, all_fixes


def check_and_report(html: str) -> tuple[list[str], bool]:
    """
    Vérifie la syntaxe et logue le résultat.
    Retourne (issues, has_syntax_error).
    """
    issues = check_syntax(html)
    if issues:
        coordinateur_log.warning(f"Node.js syntax check : {len(issues)} erreur(s) de syntaxe détectée(s)")
        for issue in issues:
            first_line = issue.split('\n')[0]
            coordinateur_log.info(f"  → {first_line}")
        return issues, True
    else:
        coordinateur_log.info("Node.js syntax check : OK ✓")
        return [], False

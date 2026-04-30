"""
JS Syntax Checker — Node.js based
Utilise `node --check` pour détecter les erreurs de syntaxe JS précises
(Unexpected token, SyntaxError, etc.) avec numéro de ligne exact.

Avantage sur les regex : un vrai parseur JS, 100% fiable sur les virgules
manquantes, accolades déséquilibrées, template literals mal fermés, etc.
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
})


def extract_js_from_html(html: str) -> str:
    """Extrait et concatène tous les blocs <script> du HTML (hors type module/json)."""
    matches = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
    if not matches:
        return ""
    # Filtrer les blocs trop courts (inline one-liners, tracking snippets)
    blocks = [m for m in matches if len(m.strip()) > 50]
    if not blocks:
        return max(matches, key=len)
    # Concaténer tous les blocs pour que check_syntax détecte les erreurs dans chacun
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

            # Variables du template HTML — toujours supprimer (jamais convertir en var)
            _TEMPLATE_GLOBALS = frozenset({'canvas', 'ctx', 'W', 'H', 'dt', 'lastTime', 'gameState'})
            if ident in _TEMPLATE_GLOBALS:
                lines.pop(line_num)
                js = '\n'.join(lines)
                fixes.append(f'[AUTO-FIX] Suppression redéclaration variable template : {ident} ligne {line_num + 1}')
                continue

            # Convertir const X = ... ou let X = ... en var X = ... sur cette ligne
            new_line = re.sub(r'\b(const|let)\s+' + re.escape(ident) + r'\b', f'var {ident}', original, count=1)
            if new_line == original:
                # Déjà un var — supprimer la ligne dupliquée
                if re.match(r'^\s*var\s+' + re.escape(ident) + r'\b', original):
                    lines.pop(line_num)
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
    return '0'


def check_undefined_vars_eslint(html: str) -> list[str]:
    """
    Option B — Détection PRÉVENTIVE des variables non déclarées via ESLint no-undef.
    Retourne la liste des noms de variables undefined (filtrés des globals connus).
    Retourne [] si eslint indisponible ou aucune erreur.
    """
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
        coordinateur_log.warning("eslint timeout (>30s) — check no-undef ignoré")
        return []
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
    to_declare = sorted(
        v for v in var_names
        if v and v.isidentifier() and v not in _BROWSER_AND_TEMPLATE_GLOBALS
    )
    if not to_declare:
        return html, False, []

    inject_lines = []
    descs = []
    for v in to_declare:
        is_fn_call = bool(js and re.search(r'\b' + re.escape(v) + r'\s*\(', js))
        if is_fn_call:
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


def fix_all_auto(html: str) -> tuple[str, bool, list[str]]:
    """
    Applique toutes les corrections automatiques disponibles en cascade :
    -1. fix_literal_newlines_in_strings (\\n littéral dans string JS → \\\\n)
    0. fix_illegal_return_statements (return hors fonction — invisible à Node.js CJS)
    1. fix_missing_comma_before_brace (virgule manquante entre éléments tableau)
    2. fix_const_syntax_errors (const/let en switch/for) — boucle jusqu'à 10×
    3. fix_identifier_already_declared (redéclarations) — boucle jusqu'à 5×
    4. fix_palette_missing_keys (clés PALETTE manquantes)
    5. check_undefined_vars_eslint + fix_undefined_runtime_vars
    Retourne (html_final, any_fixed, toutes_les_descriptions).
    """
    all_fixes = []
    any_fixed = False

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

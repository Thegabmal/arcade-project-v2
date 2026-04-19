"""
JS Syntax Checker — Node.js based
Utilise `node --check` pour détecter les erreurs de syntaxe JS précises
(Unexpected token, SyntaxError, etc.) avec numéro de ligne exact.

Avantage sur les regex : un vrai parseur JS, 100% fiable sur les virgules
manquantes, accolades déséquilibrées, template literals mal fermés, etc.
"""

import re
import subprocess
import tempfile
import os
from logger import coordinateur_log


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


def fix_all_auto(html: str) -> tuple[str, bool, list[str]]:
    """
    Applique toutes les corrections automatiques disponibles en cascade :
    1. fix_missing_comma_before_brace (virgule manquante entre éléments tableau)
    2. fix_const_syntax_errors (const/let en switch/for) — boucle jusqu'à 10×
    3. fix_identifier_already_declared (redéclarations) — boucle jusqu'à 5×
    Retourne (html_final, any_fixed, toutes_les_descriptions).
    """
    all_fixes = []
    any_fixed = False

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

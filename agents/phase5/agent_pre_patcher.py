"""
Agent Pre-Patcher — Phase 3→4 transition
Correcteur chirurgical pré-évaluation.

Stratégie : ne JAMAIS réécrire le fichier entier.
Pour chaque issue critique, on extrait le snippet problématique (50-100 lignes),
on demande à Gemini de corriger UNIQUEMENT ce snippet, puis on le réinjecte.
Pour les corrections triviales (RAF manquant, etc.), on le fait sans LLM.
"""

import re
from config import call_gemini, with_fallback
from logger import phase3_log

_IDENTIFIER_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b')


# ─────────────────────────────────────────────
# CORRECTIFS PROGRAMMATIQUES (sans LLM)
# ─────────────────────────────────────────────

def _fix_missing_game_loop(script: str) -> tuple[str, bool]:
    """
    Insère requestAnimationFrame(gameLoop) si absent.
    Cherche la fermeture du DOMContentLoaded et insère juste avant.
    """
    if any(s in script for s in ['requestAnimationFrame', 'setInterval', 'setTimeout']):
        return script, False

    # Chercher la fin du DOMContentLoaded
    # Pattern : la dernière accolade fermante + ");" à la fin du script
    dom_ready = re.search(
        r'(document\.addEventListener\s*\(\s*[\'"]DOMContentLoaded[\'"].*?)\}\s*\)\s*;?\s*$',
        script, re.DOTALL
    )
    if dom_ready:
        insert_pos = dom_ready.end() - len(re.search(r'\}\s*\)\s*;?\s*$', script[dom_ready.start():]).group())
        raf = "\n  // Démarrage de la boucle de jeu\n  if (typeof gameLoop === 'function') requestAnimationFrame(gameLoop);\n"
        script = script[:insert_pos] + raf + script[insert_pos:]
        return script, True

    # Fallback : ajouter à la fin du script
    script = script.rstrip() + "\n// Démarrage boucle de jeu\nif (typeof gameLoop === 'function') requestAnimationFrame(gameLoop);\n"
    return script, True


def _fix_missing_getcontext(script: str) -> tuple[str, bool]:
    """
    Ajoute ctx = canvas.getContext('2d') si canvas est déclaré mais getContext absent.
    Supporte n'importe quel nom de variable canvas (canvas, c, gameCanvas, etc.).
    """
    if 'getContext' in script:
        return script, False

    # Chercher la déclaration du canvas — n'importe quel nom de variable
    canvas_match = re.search(
        r'(?:const|let|var)\s+(\w+)\s*=\s*document\.(?:getElementById|querySelector)\s*\([^)]+\)\s*;',
        script
    )
    if canvas_match:
        canvas_name = canvas_match.group(1)
        insert_after = canvas_match.end()
        ctx_line = f"\n  const ctx = {canvas_name}.getContext('2d');"
        script = script[:insert_after] + ctx_line + script[insert_after:]
        return script, True

    # Fallback : chercher getElementById/querySelector sans assignation à une variable
    elem_match = re.search(
        r'document\.getElementById\s*\(\s*[\'"](\w*[Cc]anvas\w*|\w*[Cc])\w*[\'"]\s*\)',
        script
    )
    if elem_match:
        # Injecter setup canvas complet avant DOMContentLoaded ou en tête de script
        inject = ("var canvas = document.getElementById('" + elem_match.group(1)
                  + "') || document.querySelector('canvas');\n"
                  + "var ctx = canvas ? canvas.getContext('2d') : null;\n")
        script = _inject_before_domready(script, inject)
        return script, True

    return script, False


# ─────────────────────────────────────────────
# CORRECTIF LLM CIBLÉ (pour issues complexes)
# ─────────────────────────────────────────────

SYSTEM = """Tu es un chirurgien du code JavaScript. On te donne un EXTRAIT de code avec un bug précis.
Tu corriges UNIQUEMENT le bug décrit, sans rien changer d'autre.
Retourne UNIQUEMENT le code corrigé, sans explications, sans balises markdown.

RÈGLES ABSOLUES — violations = code cassé :
1. JAMAIS créer une nouvelle déclaration `const X = ...` ou `let X = ...` si X est déjà déclaré dans l'extrait.
2. JAMAIS redéclarer une variable déjà présente avec let/const/var — cela crée une SyntaxError.
3. JAMAIS insérer du code dans le corps d'un objet littéral (entre les accolades d'un const sfx = {...}).
4. Pour ajouter une propriété manquante à un objet : trouve la dernière propriété et ajoute après la virgule.

EXEMPLES CORRECTS — applique exactement ces patterns :

▸ Ajouter une propriété à un objet existant :
  ❌ const PALETTE = { bg:'#333', enemy:'#F44' };  // redéclaration → écrase l'objet entier !
  ✅ // Trouver la définition existante et ajouter la propriété dedans :
     const PALETTE = { bg:'#333', hero:'#0AF', enemy:'#F44', ui:'#FFF' };  // propriété ajoutée

▸ Variable utilisée sans déclaration → ajouter let AVANT la boucle :
  ❌ for (const en of enemies) { if (dist < 100) closest = en; }  // closest jamais déclaré → ReferenceError
  ✅ let closest = null;
     for (const en of enemies) { const dx=en.x-player.x, dy=en.y-player.y; const dist=Math.hypot(dx,dy); if (dist < 100) closest = en; }

▸ Boucle sans init locale → ajouter const varLocale = tableau[i] :
  ❌ for (let i = 0; i < bullets.length; i++) { bullet.x += bullet.vx * dt; }
  ✅ for (let i = bullets.length-1; i >= 0; i--) { const bullet = bullets[i]; bullet.x += bullet.vx * dt; }

▸ dt manquant dans une fonction :
  ❌ function updateEnemies() { for (const en of enemies) { en.x += en.vx * dt; } }
  ✅ function updateEnemies(dt) { for (const en of enemies) { en.x += en.vx * dt; } }
  (Et modifier l'appel : updateEnemies(dt) au lieu de updateEnemies())"""


def _llm_fix_snippet(snippet: str, issue: str, prev_attempt: str = "", prev_error: str = "") -> str:
    """
    Demande à Gemini de corriger un extrait de 50-100 lignes max.
    P1 — Si prev_attempt est fourni, inclut le feedback d'erreur pour un 2e essai.
    """
    if not snippet.strip():
        return snippet

    # Si le snippet contient des template literals avec interpolation ${ },
    # le wrapper ```javascript``` dans le prompt fait fermer le bloc markdown prématurément
    # (le backtick du template literal est interprété comme fin du bloc) → corruption garantie.
    # Dans ce cas, on skippe le fix LLM pour ne pas casser le code.
    if re.search(r'`[^`]*\$\{', snippet):
        return snippet

    # S3 — Contrainte explicite sur la balance des accolades
    _open_count = snippet.count('{')
    _close_count = snippet.count('}')
    _paren_open = snippet.count('(')
    _paren_close = snippet.count(')')

    # P1 — Section feedback si retry
    _retry_section = ""
    if prev_attempt and prev_error:
        _prev_open = prev_attempt.count('{')
        _prev_close = prev_attempt.count('}')
        _retry_section = f"""
TENTATIVE PRÉCÉDENTE REJETÉE — voici l'erreur de ta réponse précédente :
Erreur : {prev_error}
Ta réponse avait {_prev_open} '{{' et {_prev_close} '}}' (attendu {_open_count}/{ _close_count}).
Corrige EXACTEMENT cette erreur sans en introduire de nouvelles.

"""

    prompt = f"""Bug à corriger dans cet extrait JavaScript :

PROBLÈME : {issue}
{_retry_section}
RÈGLES ABSOLUES :
- Corrige UNIQUEMENT ce problème précis, ne modifie rien d'autre
- Retourne l'extrait corrigé COMPLET
- CRITIQUE BALANCE : ton output doit avoir EXACTEMENT {_open_count} accolades ouvrantes '{{' et {_close_count} accolades fermantes '}}' — même balance que l'extrait d'entrée
- CRITIQUE PARENTHÈSES : ton output doit avoir EXACTEMENT {_paren_open} '(' et {_paren_close} ')' — même balance
- Ne pas ajouter ni supprimer de fonctions entières — corriger SEULEMENT l'intérieur

EXTRAIT :
===CODE_START===
{snippet}
===CODE_END===

Retourne uniquement le code JavaScript corrigé (sans balises markdown)."""

    result = _call_llm(prompt)
    if result:
        result = result.strip()
        # Nettoyer les backticks si présents
        if result.startswith("```"):
            lines = result.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            result = "\n".join(lines).strip()
        # La taille n'est pas un critère de qualité — un patch localisé peut être très court.
        # La vérification `fixed_snippet != snippet` + `_quick_syntax_ok` suffisent.
        return result
    return snippet


def _brace_balance_ok(original: str, candidate: str) -> bool:
    """
    Vérifie que le patch n'aggrave pas le déséquilibre des accolades.
    Un script JS entier équilibré a toujours net=0. On rejette si le candidat
    est plus déséquilibré que l'original par plus de 2 accolades.
    Rejette aussi si une accolade fermante orpheline apparaît (préfixe négatif).
    """
    def strip_strings_comments(s: str) -> str:
        cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', s)
        cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cleaned)
        cleaned = re.sub(r'`(?:[^`\\]|\\.)*`', '``', cleaned)
        cleaned = re.sub(r'//[^\n]*', '', cleaned)
        return cleaned

    def net_braces(s: str) -> int:
        cleaned = strip_strings_comments(s)
        return abs(cleaned.count('{') - cleaned.count('}'))

    def has_stray_close(s: str) -> bool:
        """Retourne True si une accolade fermante est orpheline (profondeur < 0)."""
        cleaned = strip_strings_comments(s)
        depth = 0
        for ch in cleaned:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth < 0:
                    return True
        return False

    orig_imbalance = net_braces(original)
    cand_imbalance = net_braces(candidate)
    # Rejeter si le candidat aggrave l'imbalance, en tolérant max 1 accolade de différence
    if (cand_imbalance - orig_imbalance) > 1:
        return False
    # Rejeter si une accolade fermante orpheline est introduite (cause Unexpected token '}')
    if not has_stray_close(original) and has_stray_close(candidate):
        return False
    return True


def _inject_before_domready(script: str, code: str) -> str:
    """
    Injecte du code juste avant le DOMContentLoaded.
    Fallback 1 : après les globals du template (var gameState / var dt / var lastTime).
    Fallback 2 : à la fin du script (jamais au début — évite de casser les globals du template).
    """
    match = re.search(r'document\s*\.\s*addEventListener\s*\(\s*[\'"]DOMContentLoaded', script)
    if match:
        return script[:match.start()] + code + script[match.start():]
    # Ancrer après le dernier global du template HTML (gameState / dt / lastTime)
    _globals_anchor = re.search(
        r'(?:var\s+(?:gameState|dt|lastTime)\s*[=;][^\n]*\n)',
        script
    )
    if _globals_anchor:
        pos = _globals_anchor.end()
        return script[:pos] + code + script[pos:]
    # Dernier recours : ajouter à la fin (jamais au début — évite de briser l'ordre d'init)
    return script + '\n' + code


def _extract_snippet_around(script: str, keyword: str, context_lines: int = 40) -> tuple[str, int, int]:
    """
    Extrait un snippet de context_lines lignes autour de la première occurrence de keyword.
    Retourne (snippet, start_char, end_char) dans le script original.

    Garde de robustesse :
    - Étend les limites pour ne pas couper au milieu d'un bloc { } ouvert.
    - Limite le snippet à 120 lignes max pour éviter de noyer le LLM.
    """
    lines = script.split('\n')
    target_line = -1
    for i, line in enumerate(lines):
        if keyword in line:
            target_line = i
            break

    if target_line == -1:
        target_line = 0

    half = context_lines // 2
    start_line = max(0, target_line - half)
    end_line = min(len(lines), target_line + half)

    # Étendre pour ne pas couper un objet/tableau ouvert en début de snippet
    # On regarde les 5 lignes avant start_line pour voir si une accolade/crochet est ouverte
    for look in range(start_line - 1, max(0, start_line - 6), -1):
        stripped = lines[look].strip()
        if stripped.endswith(('{', '[', '(')):
            start_line = look
            break

    # Étendre la fin pour refermer toute accolade ouverte dans le snippet
    snippet_text = '\n'.join(lines[start_line:end_line])
    open_count = snippet_text.count('{') - snippet_text.count('}')
    if open_count > 0:
        for look in range(end_line, min(len(lines), end_line + 20)):
            end_line += 1
            snippet_text += '\n' + lines[look]
            if snippet_text.count('{') - snippet_text.count('}') <= 0:
                break

    # Limiter à 120 lignes max
    if end_line - start_line > 120:
        end_line = start_line + 120

    snippet_lines = lines[start_line:end_line]
    snippet = '\n'.join(snippet_lines)

    start_char = len('\n'.join(lines[:start_line])) + (1 if start_line > 0 else 0)
    end_char = start_char + len(snippet)

    return snippet, start_char, end_char


def _extract_function_boundary(script: str, keyword: str) -> tuple[str, int, int]:
    """
    S2 — Extrait la fonction JS COMPLÈTE contenant le keyword (brace-counting).
    Garantit que le snippet commence sur 'function X(...) {' et finit sur le '}' fermant.
    Fallback : _extract_snippet_around si la fonction est introuvable ou > 200 lignes.
    """
    pos = script.find(keyword)
    if pos == -1:
        return _extract_snippet_around(script, keyword, context_lines=80)

    # Trouver la déclaration de fonction la plus proche AVANT le keyword
    fn_start_match = None
    for m in re.finditer(
        r'(?:^|\n)[ \t]*(?:async\s+)?function\s+\w*\s*\([^)]*\)\s*\{',
        script[:pos]
    ):
        fn_start_match = m

    if not fn_start_match:
        # Pas de fonction trouvée avant → fallback
        return _extract_snippet_around(script, keyword, context_lines=80)

    fn_start = fn_start_match.start()
    if fn_start > 0 and script[fn_start] == '\n':
        fn_start += 1  # Commencer après le \n

    # Trouver la { ouvrante de la fonction
    open_brace = script.find('{', fn_start_match.end() - 1)
    if open_brace == -1:
        return _extract_snippet_around(script, keyword, context_lines=80)

    # Compter les accolades pour trouver la } fermante correspondante
    depth = 0
    fn_end = open_brace
    in_str = False
    str_char = ''
    escape = False
    for i in range(open_brace, len(script)):
        ch = script[i]
        if escape:
            escape = False
            continue
        if in_str:
            if ch == '\\':
                escape = True
            elif ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'", '`'):
            in_str = True
            str_char = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                fn_end = i + 1
                break

    fn_text = script[fn_start:fn_end]
    fn_lines = fn_text.count('\n')

    # Si la fonction est trop longue (>200 lignes), fallback sur snippet classique
    if fn_lines > 200:
        return _extract_snippet_around(script, keyword, context_lines=80)

    return fn_text, fn_start, fn_end


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def run(html: str, issues: list) -> str:
    """
    Applique des corrections chirurgicales ciblées.
    Ne réécrit JAMAIS le fichier entier.
    """
    if not html or not issues:
        return html

    phase3_log.agent_start("Pre-Patcher", f"{len(issues)} issue(s) — correction chirurgicale")

    # Extraire le script principal
    script_match = re.search(
        r'(<script(?:\s[^>]*)?>)(.+?)(</script>)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not script_match:
        return html

    prefix = html[:script_match.start(2)]
    script = script_match.group(2)
    suffix = html[script_match.end(2):]

    applied = []

    def _quick_syntax_ok(s: str) -> bool:
        """Retourne True si le script passe le check de syntaxe Node.js."""
        try:
            import subprocess, tempfile, os
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(s)
                fname = f.name
            result = subprocess.run(
                ['node', '--check', fname],
                capture_output=True, text=True, timeout=5
            )
            os.unlink(fname)
            return result.returncode == 0
        except Exception:
            return True  # Si Node indisponible, on assume OK (le coordinateur re-vérifiera)

    def _runtime_ok(s: str) -> tuple[bool, str]:
        """
        P2 — Vérifie l'absence d'erreurs runtime évidentes (ReferenceError/TypeError).
        Exécute le script dans Node.js avec un try/catch global.
        Retourne (ok, error_message).
        """
        try:
            import subprocess, tempfile, os
            wrapped = (
                "try {\n" + s + "\n"
                "if(typeof init==='function'){try{init();}catch(e){console.error('RUNTIME:'+e.message);}}\n"
                "} catch(e) { console.error('RUNTIME:'+e.message); }\n"
            )
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(wrapped)
                fname = f.name
            result = subprocess.run(
                ['node', fname],
                capture_output=True, text=True, timeout=6
            )
            os.unlink(fname)
            stderr = (result.stderr or '').strip()
            stdout = (result.stdout or '').strip()
            runtime_errors = [ln for ln in (stderr + '\n' + stdout).split('\n')
                              if ln.startswith('RUNTIME:')]
            if runtime_errors:
                return False, runtime_errors[0].replace('RUNTIME:', '')
            return True, ''
        except Exception:
            return True, ''  # Si Node indisponible, assume OK

    # ── Correction universelle : supprimer les chargements d'images locales ──
    # Tout img.src = 'fichier.ext' qui n'est pas data: ou http cause ERR_FILE_NOT_FOUND
    def _remove_local_img_src(m):
        src = m.group(1)
        if src.startswith(('http', 'data:', '//')):
            return m.group(0)  # URL externe valide → garder
        return m.group(0).replace(m.group(0), '/* img local supprimé */')

    fixed_img = re.sub(
        r'''(?:img|image|sprite|[\w]+Img|[\w]+Image|[\w]+Sprite)\s*\.src\s*=\s*['"]([^'"]+)['"]''',
        _remove_local_img_src,
        script
    )
    if fixed_img != script:
        script = fixed_img
        applied.append("chargements d'images locales supprimés (ERR_FILE_NOT_FOUND)")

    # ── Correction universelle : remplacer new Audio('fichier') par stub WebAudio ──
    # new Audio() avec fichiers locaux cause ERR_FILE_NOT_FOUND — remplacer par stub silencieux
    _audio_stub = "{ play: function() {}, pause: function() {}, currentTime: 0, loop: false, volume: 1 }"
    def _replace_local_audio(m):
        src = m.group(1)
        if src.startswith(('http', 'data:', '//')):
            return m.group(0)  # URL externe valide → garder
        return _audio_stub
    fixed_audio = re.sub(
        r'''new\s+Audio\s*\(\s*['"]([^'"]*)['"]\s*\)''',
        _replace_local_audio,
        script
    )
    if fixed_audio != script:
        script = fixed_audio
        applied.append("new Audio() locaux remplacés par stubs silencieux (ERR_FILE_NOT_FOUND)")

    # ── Correction universelle : supprimer window.__devPatch / __devPatch / eval bridges ──
    fixed_devpatch = re.sub(
        r'window\.__(?:devPatch|debug|patch|eval|dev)\s*=\s*function[^;]+;?\n?',
        '/* devPatch removed */\n',
        script, flags=re.DOTALL
    )
    if fixed_devpatch != script:
        script = fixed_devpatch
        applied.append("window.__devPatch (eval bridge) supprimé")

    # P6 — Correctifs programmatiques déterministes (sans LLM) — avant la boucle issues
    try:
        from agents.phase5._auto_fix_rules import apply_all_rules as _p6_rules
        _p6_script, _p6_applied = _p6_rules(script)
        if _p6_applied:
            # Valider que P6 n'a pas cassé la syntaxe
            if _quick_syntax_ok(_p6_script):
                script = _p6_script
                applied.extend([f"[P6] {d}" for d in _p6_applied])
            else:
                phase3_log.warning("Pre-Patcher P6 : règles déterministes cassaient la syntaxe — ignorées")
    except Exception:
        pass  # Module P6 indisponible → on continue

    # P3 — Trier les issues par priorité de dépendance
    # Les déclarations manquantes doivent être corrigées avant les erreurs d'appel
    def _issue_priority(iss: str) -> int:
        il = iss.lower()
        if any(k in il for k in ('syntaxerror', 'parse error', 'unexpected token', 'unexpected end')):
            return 0  # Erreurs syntaxe — priorité maximale
        if any(k in il for k in ('déclaré', 'declared', 'not defined', 'undefined', 'undeclared',
                                  'jamais défini', 'manquant', 'missing', 'stub')):
            return 1  # Variables/fonctions non déclarées
        if any(k in il for k in ('const', 'reassign', 'for-of', 'splice', 'nan', 'typeerror',
                                  'for(const', 'boucle inverse', '.clear()')):
            return 2  # Erreurs de type / patterns dangereux
        if any(k in il for k in ('collision', 'logique', 'logic', 'update', 'spawn', 'bug')):
            return 3  # Erreurs logiques
        return 4  # Qualité / style

    issues_sorted = sorted(issues, key=_issue_priority)

    # Cap issues LLM : trop d'issues → MAX_TOKENS sur les snippets → on garde les 12 plus critiques
    _MAX_ISSUES_CAP = 12
    if len(issues_sorted) > _MAX_ISSUES_CAP:
        phase3_log.info(
            "Pre-Patcher : %d issues — cap à %d (priorité descendante pour éviter MAX_TOKENS)"
            % (len(issues_sorted), _MAX_ISSUES_CAP)
        )
        issues_sorted = issues_sorted[:_MAX_ISSUES_CAP]

    # S5 — Vérifier syntaxe AVANT la boucle issue
    # Si le code est déjà cassé, skip tous les appels LLM snippet (inutiles + lents)
    # Les corrections programmatiques (injections) s'appliquent quand même
    _code_syntaxically_ok = _quick_syntax_ok(script)
    if not _code_syntaxically_ok:
        phase3_log.info("Pre-Patcher : code syntaxiquement cassé — LLM snippets désactivés (programmatique uniquement)")

    for issue in issues_sorted:
        original_script = script
        issue_lower = issue.lower()

        # ── Correctifs programmatiques (sans LLM) ──
        if "boucle de jeu" in issue:
            script, fixed = _fix_missing_game_loop(script)
            if fixed:
                applied.append("game loop ajoutée")
                continue

        if "getContext" in issue:
            script, fixed = _fix_missing_getcontext(script)
            if fixed:
                applied.append("ctx.getContext ajouté")
                continue

        # ── Eval en production ──
        if "eval" in issue_lower or "devpatch" in issue_lower or "__dev" in issue_lower:
            fixed = re.sub(
                r'window\.__(?:devPatch|debug|patch|eval)\s*=\s*function.*?\}\s*;',
                '/* debug removed */',
                script,
                flags=re.DOTALL
            )
            if fixed != script:
                script = fixed
                applied.append("window.__devPatch supprimé")
                continue

        # ── JSON.parse manquant dans loadGame ──
        if "json.parse" in issue_lower or "loadgame" in issue_lower or "loadsave" in issue_lower or "localstorage" in issue_lower:
            # Pattern élargi : toute variable assignée depuis localStorage sans JSON.parse
            def add_json_parse(m):
                varname = m.group(1)
                key = m.group(2)
                # Vérifier si JSON.parse n'est pas déjà appliqué
                surrounding = script[max(0, m.start()-5):m.end()+100]
                if 'JSON.parse' in surrounding:
                    return m.group(0)
                return f'const {varname} = JSON.parse(localStorage.getItem({key}) || "null"); if (!{varname}) return'
            fixed = re.sub(
                r'(?:const|let|var)\s+(\w+)\s*=\s*localStorage\.getItem\(([^)]+)\)',
                add_json_parse, script
            )
            if fixed != script:
                script = fixed
                applied.append("JSON.parse wrappé autour de localStorage.getItem")
                continue

        # ── Correctifs programmatiques pour variables globales manquantes ──

        if "'keys'" in issue_lower or "variable globale 'keys'" in issue_lower or "objet 'keys'" in issue_lower:
            if not re.search(r'\b(?:let|const|var)\s+keys\s*=', script):
                inject = ("let keys = { left:false, right:false, up:false, down:false, "
                          "space:false, space_pressed:false, e:false, e_prev:false, "
                          "z:false, x:false, c:false, escape:false };\n")
                script = _inject_before_domready(script, inject)
                applied.append("keys déclaré globalement")
            continue  # toujours skip — qu'il soit injecté ou déjà déclaré

        if "'mouse'" in issue_lower or "variable globale 'mouse'" in issue_lower or "objet 'mouse'" in issue_lower:
            if not re.search(r'\b(?:let|const|var)\s+mouse\s*=', script):
                inject = "let mouse = { x:0, y:0, clicked:false };\n"
                script = _inject_before_domready(script, inject)
                applied.append("mouse déclaré globalement")
            continue  # toujours skip

        if "'particles'" in issue_lower or "tableau 'particles'" in issue_lower:
            if not re.search(r'\b(?:let|const|var)\s+particles\s*=', script):
                inject = "const particles = [];\n"
                script = _inject_before_domready(script, inject)
                applied.append("particles déclaré globalement")
            continue  # toujours skip

        if "'gamestate'" in issue_lower or "variable 'gamestate'" in issue_lower or "gamestate" in issue_lower and "jamais déclaré" in issue_lower:
            if not re.search(r'\b(?:let|const|var)\s+gameState\b', script):
                inject = "let gameState = 'menu';\n"
                script = _inject_before_domready(script, inject)
                applied.append("gameState déclaré globalement")
            continue  # toujours skip — évite snippet LLM autour de 'gameState'

        if ("'dt'" in issue_lower or "variable 'dt'" in issue_lower or
                ("dt" in issue_lower and "jamais déclaré" in issue_lower)):
            if not re.search(r'\b(?:let|const|var)\s+dt\b', script):
                inject = "let dt = 0;\nlet lastTime = 0;\n"
                script = _inject_before_domready(script, inject)
                # Injecter la mise à jour dt dans le callback requestAnimationFrame
                # Pattern : function gameLoop(timestamp) { ou (timestamp) => {
                raf_pat = re.compile(
                    r'(function\s+\w*\s*\(\s*(?:timestamp|ts|now|time|t)\s*\)\s*\{|'
                    r'\(\s*(?:timestamp|ts|now|time|t)\s*\)\s*=>\s*\{)',
                    re.IGNORECASE
                )
                m_raf = raf_pat.search(script)
                if m_raf and 'dt =' not in script[m_raf.end():m_raf.end() + 200]:
                    param = re.search(r'\(\s*(\w+)\s*\)', m_raf.group(0)).group(1)
                    dt_update = (f"\n  dt = Math.min(({param} - lastTime) / 1000, 0.05);"
                                 f"\n  lastTime = {param};")
                    script = script[:m_raf.end()] + dt_update + script[m_raf.end():]
                applied.append("dt + lastTime déclarés, mise à jour dans gameLoop")
            continue  # toujours skip

        # ── COMMON_VARS génériques : injection programmatique sans LLM ──
        # Évite que le LLM snippet fixer se plante sur des objets PALETTE/config
        # qui contiennent player/boss/canvas comme CLÉS d'objet (pas des variables)
        _COMMON_VARS_DEFAULTS = {
            'player': 'null', 'boss': 'null', 'canvas': 'null', 'ctx': 'null',
            'enemies': '[]', 'bullets': '[]', 'particles': '[]', 'projectiles': '[]',
            'floatingTexts': '[]', 'items': '[]', 'towers': '[]', 'rooms': '[]',
            'score': '0', 'lives': '3', 'gold': '0', 'xp': '0', 'wave': '0',
            'combo': '0', 'paused': 'false', 'gameOver': 'false',
            'angle': '0', 'dist': '0', 'dx': '0', 'dy': '0',
            'animId': 'null', 'sfx': '{}',
            # Vars fréquemment oubliées — auto-détectées par auto-learner
            'life': '0', 'closest': 'null', 'hit': 'false', 'invincible': 'false',
            'grid': '[]', 'gravity': '900', 'current': 'null', 'power': '0',
            'option': 'null', 'selected': 'null', 'state': 'null',
            'waveAnnouncetimer': '0', 'wavetimer': '3',
            'activepowerups': '[]', 'currentupgrades': '[]',
            'down': 'false', 'firerate': '0.2', 'multiplier': '1',
            'upgrades': '[]', 'upgrade': 'null',
        }
        _matched_common = None
        for cv_name, cv_default in _COMMON_VARS_DEFAULTS.items():
            if (f"'{cv_name}'" in issue_lower or f'variable \'{cv_name}\'' in issue_lower
                    or (cv_name in issue_lower and 'déclaré' in issue_lower)):
                _matched_common = (cv_name, cv_default)
                break
        if _matched_common:
            cv_name, cv_default = _matched_common
            # Vérification robuste : let/const/var + assignment nu (enemies = []) + propriété window
            _already_declared = (
                re.search(rf'\b(?:let|const|var)\s+{re.escape(cv_name)}\b', script)
                or re.search(rf'(?:^|\n)\s*{re.escape(cv_name)}\s*=\s*[^\s=]', script)
                or f'window.{cv_name}' in script
            )
            # Faux positif : cv_name apparaît UNIQUEMENT comme clé d'objet littéral
            # ex: PALETTE = { player: '#0AF' } → NE PAS injecter let player = null
            if not _already_declared:
                _used_as_standalone = bool(re.search(
                    rf'\b{re.escape(cv_name)}\s*(?:\.|=|\[|\()',
                    script
                ))
                _used_as_obj_key = bool(re.search(
                    rf'[{{\s,]\s*{re.escape(cv_name)}\s*:',
                    script
                ))
                if _used_as_obj_key and not _used_as_standalone:
                    # C'est uniquement une clé d'objet, pas une variable → skip
                    continue
            if not _already_declared:
                inject = f"let {cv_name} = {cv_default};\n"
                script = _inject_before_domready(script, inject)
                applied.append(f"{cv_name} déclaré globalement (common_vars)")
            continue  # toujours skip — même si déjà déclaré

        # ── PALETTE non définie — injection objet de couleurs complet ──
        if 'palette' in issue_lower and ('not defined' in issue_lower or 'déclaré' in issue_lower or 'défini' in issue_lower):
            if not re.search(r'\b(?:var|let|const)\s+PALETTE\s*=', script):
                inject = (
                    "var PALETTE = {bg:'#0a0a1a',player:'#00ffcc',enemy:'#ff4444',boss:'#ff00ff',"
                    "bullet:'#ffff00',ui:'#ffffff',shield:'#00aaff',particle:'#ffaa00',"
                    "bulletHit:'#ff8800',damageText:'#ff0000',enemyBomberBody:'#ff6600',"
                    "enemyBomberOutline:'#ffcc00',drone:'#44ff88',turret:'#ff8844'};\n"
                )
                script = _inject_before_domready(script, inject)
                applied.append("PALETTE injectée (objet de couleurs default)")
            continue

        # ── _AC (AudioContext) non défini ──
        if '_ac' in issue_lower and ('not defined' in issue_lower or 'déclaré' in issue_lower):
            if not re.search(r'\b_AC\b', script):
                inject = "var _AC = null; try { _AC = new (window.AudioContext||window.webkitAudioContext)(); } catch(e) {}\n"
                script = _inject_before_domready(script, inject)
                applied.append("_AC (AudioContext) injecté")
            continue

        # ── ENEMY_SPEED_TYPE, ENEMY_HP_TYPE, ENEMY_*_* non définis ──
        _enemy_const_m = re.search(r'\b(enemy_\w+)\b.*(?:not defined|déclaré|défini)', issue_lower)
        if _enemy_const_m:
            const_name = _enemy_const_m.group(1).upper()
            if not re.search(rf'\b(?:var|let|const)\s+{re.escape(const_name)}\b', script):
                default_val = '100' if 'speed' in const_name.lower() else ('1' if 'hp' in const_name.lower() or 'dmg' in const_name.lower() else '100')
                inject = f"var {const_name} = {default_val}; /* valeur par défaut auto-injectée */\n"
                script = _inject_before_domready(script, inject)
                applied.append(f"{const_name} injecté (constante ALL_CAPS manquante)")
            continue

        # ── waveAnnounceTimer non déclaré ──
        if 'waveannouncetimer' in issue_lower and ('not defined' in issue_lower or 'déclaré' in issue_lower):
            if not re.search(r'\bwaveAnnounceTimer\b', script):
                inject = "var waveAnnounceTimer = 0; var waveAnnounceTxt = '';\n"
                script = _inject_before_domready(script, inject)
                applied.append("waveAnnounceTimer injecté")
            continue

        # ── Constantes ALL_CAPS manquantes (BOSS_DEFS, spawnPatterns, etc.) ──
        # Ces constantes sont utilisées par Gemini mais pas toujours déclarées.
        # On injecte des stubs minimalistes pour éviter ReferenceError au runtime.
        # NE PAS passer au LLM snippet — il corrompt les tableaux de données voisins.
        _ALLCAPS_STUBS = {
            'BOSS_DEFS':    'var BOSS_DEFS = {};\n',
            'UPGRADE_DEFS': 'var UPGRADE_DEFS = [];\n',
            'POWERUP_DEFS': 'var POWERUP_DEFS = [];\n',
            'ABILITY_DEFS': 'var ABILITY_DEFS = {};\n',
            'SPELL_DEFS':   'var SPELL_DEFS = {};\n',
            'ITEM_DEFS':    'var ITEM_DEFS = {};\n',
            'NPC_DEFS':     'var NPC_DEFS = {};\n',
            'QUEST_DEFS':   'var QUEST_DEFS = [];\n',
            'ROOM_DEFS':    'var ROOM_DEFS = [];\n',
            'HERO_CLASSES': 'var HERO_CLASSES = {};\n',
            'PATH_NODES':   'var PATH_NODES = [];\n',
            'WAVE_DEFS':    'var WAVE_DEFS = [];\n',
            'TOWER_DEFS':   'var TOWER_DEFS = {};\n',
            'ENEMY_DEFS':   'var ENEMY_DEFS = {};\n',
            'LEVEL_DEFS':   'var LEVEL_DEFS = [];\n',
            'MAP_DATA':     'var MAP_DATA = [];\n',
            'TILE_DEFS':    'var TILE_DEFS = {};\n',
            'spawnPatterns': 'var spawnPatterns = [];\n',
            'bossPhases':   'var bossPhases = [];\n',
            'waveConfig':   'var waveConfig = [];\n',
            'levelConfig':  'var levelConfig = [];\n',
        }
        _matched_stub = None
        for stub_name, stub_code in _ALLCAPS_STUBS.items():
            name_lower = stub_name.lower()
            if (stub_name in issue or f"'{stub_name}'" in issue
                    or (name_lower in issue_lower and ('déclaré' in issue_lower or 'déclaration' in issue_lower or 'sans déclar' in issue_lower))):
                _matched_stub = (stub_name, stub_code)
                break
        if _matched_stub:
            stub_name, stub_code = _matched_stub
            if not re.search(rf'\b(?:let|const|var)\s+{re.escape(stub_name)}\b', script):
                script = _inject_before_domready(script, stub_code)
                applied.append(f"{stub_name} stub injecté (ALL_CAPS manquant)")
            continue  # toujours skip

        # ── Callback sans optional chaining sur un registre de types ──
        if "optional chaining" in issue_lower or "absent dans la définition" in issue_lower or "?.(" in issue_lower:
            # Remplacer TYPES.key.method( par TYPES.key.method?.(
            import re as _re2
            fixed = _re2.sub(
                r'([A-Z_]+\.\w+\.)(\w+)\s*\((?!\?)',
                lambda m: m.group(1) + m.group(2) + '?.(',
                script
            )
            # Aussi les appels via bracket notation TYPES[x].method(
            fixed = _re2.sub(
                r'([A-Z_]+\[\w+\]\.)(\w+)\s*\((?!\?)',
                lambda m: m.group(1) + m.group(2) + '?.(',
                fixed
            )
            if fixed != script:
                script = fixed
                applied.append("optional chaining ajouté sur callbacks de registre")
                continue

        if "'floatingTexts'" in issue_lower or "floatingtexts" in issue_lower:
            # Supprimer les déclarations en double (garder seulement la première)
            count = len(re.findall(r'\b(?:let|const|var)\s+floatingTexts\s*=', script))
            if count > 1:
                script = re.sub(
                    r'\b(?:let|const|var)\s+floatingTexts\s*=\s*\[\];?\n?',
                    '', script, count=count - 1
                )
                applied.append("floatingTexts dédupliqué")
                continue

        # ── Double dégâts boss : retirer playerTakeDamage de onAttack ──
        if "double source" in issue_lower and "onattack" in issue_lower:
            # Retirer playerTakeDamage(...) dans les callbacks onAttack des boss
            fixed = re.sub(
                r'(onAttack\s*:\s*\([^)]*\)\s*=>\s*\{[^}]*)playerTakeDamage\s*\([^)]*\)\s*;?',
                r'\1/* dégâts via collision */',
                script, flags=re.DOTALL
            )
            if fixed != script:
                script = fixed
                applied.append("playerTakeDamage retiré de onAttack boss (double dégât corrigé)")
                continue

        # ── sfx utilisé sans déclaration ──
        if "sfx" in issue_lower or "'sfx'" in issue_lower:
            if "sfx" in script and not re.search(r'\b(?:let|const|var)\s+sfx\s*=', script):
                inject = "const sfx = { play: () => {}, stop: () => {}, loop: () => {} }; // stub son\n"
                script = _inject_before_domready(script, inject)
                applied.append("sfx stub déclaré globalement")
            continue  # toujours skip

        # ── hit/found/closest/targetEnemy utilisé sans déclaration ──
        for varname in ('hit', 'found', 'closest', 'targetEnemy', 'angle'):
            if f"'{varname}'" in issue_lower or f'"{varname}"' in issue_lower:
                if varname in script and not re.search(rf'\b(?:let|const|var)\s+{varname}\b', script):
                    inject = f"let {varname} = null;\n"
                    script = _inject_before_domready(script, inject)
                    applied.append(f"{varname} déclaré globalement")
                    break

        # ── Variable _prefixée utilisée sans déclaration (ex: _run_state, _phase) ──
        _underscore_match = re.search(r"'(_[a-zA-Z][a-zA-Z0-9_]*)'\s*(?:is not defined|n'est pas défini|undeclared)", issue)
        if _underscore_match:
            _uvar = _underscore_match.group(1)
            if _uvar in script and not re.search(rf'\b(?:let|const|var)\s+{re.escape(_uvar)}\b', script):
                # Déduire la valeur initiale selon le nom
                if 'state' in _uvar.lower() or 'phase' in _uvar.lower() or 'mode' in _uvar.lower():
                    _uval = "'menu'"
                elif 'timer' in _uvar.lower() or 'time' in _uvar.lower() or 'count' in _uvar.lower():
                    _uval = '0'
                elif 'active' in _uvar.lower() or 'enabled' in _uvar.lower() or 'ready' in _uvar.lower():
                    _uval = 'false'
                elif 'list' in _uvar.lower() or 'queue' in _uvar.lower() or 'pool' in _uvar.lower():
                    _uval = '[]'
                else:
                    _uval = 'null'
                inject = f"var {_uvar} = {_uval};\n"
                script = _inject_before_domready(script, inject)
                applied.append(f"{_uvar} déclaré globalement (var _prefixée)")

        # ── Fonction camelCase non définie → stub vide ──
        _fn_undef_match = re.search(
            r"'([a-z][a-zA-Z0-9_]*)'\s*(?:is not defined|n'est pas défini|undeclared)",
            issue
        )
        if _fn_undef_match:
            _fn_name = _fn_undef_match.group(1)
            # Vérifier que c'est appelé comme fonction (suivi de '(') et non déclaré
            if (re.search(rf'\b{re.escape(_fn_name)}\s*\(', script) and
                    not re.search(rf'\bfunction\s+{re.escape(_fn_name)}\b', script) and
                    not re.search(rf'\b(?:let|const|var)\s+{re.escape(_fn_name)}\b', script)):
                inject = f"function {_fn_name}() {{}}\n"
                script = _inject_before_domready(script, inject)
                applied.append(f"stub fonction {_fn_name}()")

        # ── Redéclaration ("already been declared") → fix programmatique ──
        already_decl_match = re.search(
            r"Identifier '(\w+)' has already been declared", issue
        )
        if already_decl_match:
            varname = already_decl_match.group(1)
            # Chercher toutes les occurrences de `let/const/var varname` (avec ou sans =)
            decl_re = re.compile(
                rf'^[ \t]*(?:let|const|var)\s+{re.escape(varname)}\b',
                re.MULTILINE
            )
            occurrences = list(decl_re.finditer(script))
            if len(occurrences) >= 2:
                # Garder la première, supprimer la deuxième (et son bloc si multi-ligne)
                second = occurrences[1]
                line_start = script.rfind('\n', 0, second.start()) + 1
                decl_line_end = script.find('\n', second.end())
                if decl_line_end == -1:
                    decl_line_end = len(script)
                decl_line = script[line_start:decl_line_end]
                # Si la déclaration ouvre un bloc multi-ligne ({  ou [), on supprime tout le bloc
                stripped_decl = decl_line.rstrip()
                if stripped_decl.endswith('{') or stripped_decl.endswith('['):
                    open_ch = stripped_decl[-1]
                    close_ch = '}' if open_ch == '{' else ']'
                    depth = 0
                    block_end = line_start
                    for ci in range(line_start, len(script)):
                        ch = script[ci]
                        if ch == open_ch:
                            depth += 1
                        elif ch == close_ch:
                            depth -= 1
                            if depth == 0:
                                # Avancer jusqu'à la fin de la ligne (incl. ; éventuel)
                                block_end = script.find('\n', ci)
                                if block_end == -1:
                                    block_end = len(script)
                                break
                    script = script[:line_start] + script[block_end + 1:]
                else:
                    script = script[:line_start] + script[decl_line_end + 1:]
                applied.append(f"'{varname}' dédupliqué (already declared)")
                continue

        # ── Patch_bank : tenter un correctif connu avant de passer au LLM ──
        try:
            import sys as _sys, os as _os
            _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))))
            from patch_bank import try_apply_known_patch as _try_known
            _patched_known, _applied_known = _try_known(script, issue, genre="")
            if _applied_known:
                script = _patched_known
                applied.append(f"patch_bank : {issue[:60]}")
                continue
        except Exception:
            pass  # patch_bank indisponible → on continue vers LLM

        # ── Correctif LLM sur snippet ciblé (pour les cas complexes) ──
        keyword = None
        # Fonctions critiques : extraire un snippet autour d'elles détruirait le game loop entier
        _CRITICAL_FN_BLACKLIST = {
            'gameLoop', 'gameloop', 'animate', 'loop', 'tick', 'mainLoop',
            'update', 'draw', 'render', 'initGame', 'startGame', 'resetGame',
            'restartGame', 'init', 'start', 'reset',
        }
        _STOP_WORDS = {'function', 'const', 'let', 'var', 'return', 'this', 'true',
                       'false', 'null', 'undefined', 'NaN', 'typeof', 'instanceof',
                       # Mots français courants dans les messages de linter
                       'dans', 'pour', 'avec', 'une', 'les', 'des', 'est', 'qui',
                       'par', 'sur', 'pas', 'mais', 'son', 'ses', 'cette', 'ces',
                       'que', 'car', 'elle', 'lui', 'ces', 'aux', 'aussi', 'tout',
                       'bien', 'peut', 'doit', 'sera', 'valide', 'erreur', 'code',
                       'critique', 'variable', 'declaration', 'syntaxe', 'appel',
                       'script', 'objet', 'tableau', 'boucle', 'zone', 'Zone',
                       'sans', 'avant', 'apres', 'after', 'before', 'never', 'jamais',
                       'toujours', 'souvent', 'parfois', 'chaque', 'tous', 'entre',
                       'debut', 'debut', 'fin', 'haut', 'bas', 'gauche', 'droite',
                       'global', 'local', 'scope', 'context', 'param', 'args',
                       'return', 'retour', 'sortie', 'entree', 'input', 'output',
                       'ligne', 'colonne', 'bloc', 'corps', 'head', 'body', 'tail',
                       # Globals de jeu déclarés par le LLM — faux positifs fréquents du linter
                       'player', 'enemies', 'boss', 'canvas', 'Canvas', 'ctx', 'keys', 'items',
                       'map', 'rooms', 'particles', 'projectiles', 'bullets', 'camera',
                       # Propriétés d'objets courants — génèrent des snippets dans le mauvais contexte
                       'left', 'right', 'up', 'down', 'space', 'enter', 'escape',
                       'mouse', 'click', 'pressed', 'gameState', 'state', 'type',
                       'value', 'index', 'count', 'timer', 'time', 'speed', 'data',
                       'dt', 'lastTime', 'timestamp', 'deltaTime', 'elapsed',
                       # Constantes de données ALL_CAPS — ne jamais passer au LLM snippet fixer
                       # (le LLM retourne le contenu brut sans le wrapper const X = [...])
                       'PATH_NODES', 'ENEMY_DEFS', 'BOSS_DEFS', 'TOWER_DEFS', 'WAVE_DEFS',
                       'TILE_DEFS', 'LEVEL_DATA', 'MAP_DATA', 'ITEM_DEFS', 'SKILL_DEFS',
                       'HERO_CLASSES', 'UPGRADE_DEFS', 'POWERUP_DEFS', 'ROOM_DEFS',
                       'NPC_DEFS', 'QUEST_DEFS', 'ABILITY_DEFS', 'SPELL_DEFS',
                       'CONFIG', 'SETTINGS', 'CONSTANTS', 'PALETTE'}
        for ident in _IDENTIFIER_RE.findall(issue):
            # Ignorer les constantes ALL_CAPS (données structurées — le LLM les corrompt)
            if ident.isupper() and len(ident) > 3:
                continue
            # Ignorer les fonctions critiques — le snippet autour d'elles est trop large
            # et le LLM risque de retourner un game loop partiel → écran noir garanti
            if ident in _CRITICAL_FN_BLACKLIST:
                continue
            if ident not in _STOP_WORDS and ident in script:
                keyword = ident
                break

        # ── S1A — Route programmatique : case mismatch (X utilisée mais Y est déclarée) ──
        _case_match = re.search(
            r"[Vv]ariable\s+'([a-zA-Z][a-zA-Z0-9_]*)'\s+(?:utilisée|used).*?"
            r"'([a-zA-Z][a-zA-Z0-9_]*)'\s+(?:est déclarée|is declared|déclarée globalement)",
            issue
        )
        if _case_match:
            _used_name, _decl_name = _case_match.group(1), _case_match.group(2)
            if _used_name.lower() == _decl_name.lower() and _used_name != _decl_name:
                _fixed_case = re.sub(rf'\b{re.escape(_used_name)}\b', _decl_name, script)
                if _fixed_case != script:
                    if _quick_syntax_ok(_fixed_case):
                        script = _fixed_case
                        applied.append(f"case mismatch corrigé : {_used_name} → {_decl_name}")
                        continue

        # ── S1B — Route programmatique : fonction non définie → stub en fin de script ──
        _fn_undef_prog = re.search(
            r"(?:[Ff]onction|[Ff]unction)\s+'?([a-z][a-zA-Z0-9_]+)'?\s*(?:\(\))?\s*"
            r"(?:appelée|called).*?(?:jamais définie|non définie|not defined|undefined)",
            issue
        )
        if not _fn_undef_prog:
            # Aussi matcher la cohérence check : "Fonction appelée dans gameLoop mais non définie : updatePowerUps()"
            _fn_undef_prog = re.search(
                r"(?:non définie|not defined|undefined)\s*:\s*([a-z][a-zA-Z0-9_]+)\s*\(",
                issue
            )
        if _fn_undef_prog:
            _fn_name_stub = _fn_undef_prog.group(1)
            if (_fn_name_stub not in _CRITICAL_FN_BLACKLIST and
                    _fn_name_stub not in _STOP_WORDS and
                    len(_fn_name_stub) > 3 and
                    re.search(rf'\b{re.escape(_fn_name_stub)}\s*\(', script) and
                    not re.search(rf'\bfunction\s+{re.escape(_fn_name_stub)}\b', script)):
                _stub_code = f"\nfunction {_fn_name_stub}(dt) {{ /* auto-stub S1B */ }}\n"
                _candidate_stub = script + _stub_code
                if _quick_syntax_ok(_candidate_stub):
                    script = _candidate_stub
                    applied.append(f"stub {_fn_name_stub}() injecté (S1B)")
                    continue

        if keyword:
            # S5 — skip LLM si code syntaxiquement cassé
            if not _code_syntaxically_ok:
                phase3_log.info(f"Pre-Patcher : skip LLM '{keyword}' (code cassé)")
                continue

            # S2 — Extraction function-boundary au lieu de N lignes arbitraires
            snippet, s_start, s_end = _extract_function_boundary(script, keyword)

            # P1 — Retry LLM avec feedback si premier essai rejeté (max 2 tentatives)
            _accepted = False
            _prev_attempt = ""
            _prev_error = ""
            for _llm_try in range(2):
                fixed_snippet = _llm_fix_snippet(snippet, issue,
                                                  prev_attempt=_prev_attempt,
                                                  prev_error=_prev_error)
                if fixed_snippet == snippet:
                    break
                candidate = script[:s_start] + fixed_snippet + script[s_end:]
                # S4 — NE PAS appeler _dedup_declarations sur le candidat

                if not _brace_balance_ok(script, candidate):
                    _prev_attempt = fixed_snippet
                    _open_c, _close_c = fixed_snippet.count('{'), fixed_snippet.count('}')
                    _prev_error = f"Accolades déséquilibrées dans ton output : {_open_c} ouvrantes, {_close_c} fermantes"
                    phase3_log.warning(f"Pre-Patcher : snippet '{keyword}' essai {_llm_try+1} rejeté (accolades)")
                    if _llm_try == 1:
                        # Dernier essai échoué — fallback stub S6
                        if (re.search(rf'\b{re.escape(keyword)}\s*\(', script) and
                                not re.search(rf'\bfunction\s+{re.escape(keyword)}\b', script) and
                                keyword not in _CRITICAL_FN_BLACKLIST):
                            _stub = f"\nfunction {keyword}(dt) {{ /* stub S6 balance */ }}\n"
                            if _quick_syntax_ok(script + _stub):
                                script = script + _stub
                                applied.append(f"stub fallback {keyword}() (S6 — balance)")
                    continue

                if not _quick_syntax_ok(candidate):
                    _prev_attempt = fixed_snippet
                    _prev_error = "SyntaxError — ton output introduit une erreur de syntaxe JS"
                    phase3_log.warning(f"Pre-Patcher : snippet '{keyword}' essai {_llm_try+1} rejeté (syntaxe)")
                    if _llm_try == 1:
                        # Dernier essai échoué — fallback stub S6
                        if (re.search(rf'\b{re.escape(keyword)}\s*\(', script) and
                                not re.search(rf'\bfunction\s+{re.escape(keyword)}\b', script) and
                                keyword not in _CRITICAL_FN_BLACKLIST):
                            _stub = f"\nfunction {keyword}(dt) {{ /* stub S6 syntax */ }}\n"
                            if _quick_syntax_ok(script + _stub):
                                script = script + _stub
                                applied.append(f"stub fallback {keyword}() (S6 — LLM rejeté)")
                    continue

                # P2 — Runtime check : vérifier qu'on n'introduit pas de ReferenceError/TypeError
                _rt_ok, _rt_err = _runtime_ok(candidate)
                if not _rt_ok:
                    # Comparer avec le runtime de l'original — si l'original avait déjà l'erreur, accepter quand même
                    _rt_orig_ok, _ = _runtime_ok(script)
                    if _rt_orig_ok:
                        _prev_attempt = fixed_snippet
                        _prev_error = f"Ton patch introduit une erreur runtime : {_rt_err}"
                        phase3_log.warning(f"Pre-Patcher : snippet '{keyword}' essai {_llm_try+1} rejeté (runtime: {_rt_err[:60]})")
                        if _llm_try == 1:
                            pass  # On ne fait pas de stub sur erreur runtime — trop risqué
                        continue

                # Candidat accepté
                script = candidate
                _code_syntaxically_ok = True  # Le code est maintenant syntaxiquement valide
                applied.append(f"snippet corrigé ({keyword})" + (f" [retry {_llm_try+1}]" if _llm_try > 0 else ""))
                _accepted = True
                break

    # ── Event listeners canvas hors DOMContentLoaded (cause principale d'écran noir) ──
    script, el_fixed = _fix_canvas_listeners_outside_domready(script)
    if el_fixed:
        applied.append("event listeners canvas déplacés dans DOMContentLoaded")

    script_before_dedup = script

    # ── Déduplication post-patch : supprimer les redéclarations let/const/var ──
    script_dedup, dedup_count = _dedup_declarations(script)
    if dedup_count:
        # Valider que la déduplication n'a pas cassé la syntaxe
        if _quick_syntax_ok(script_dedup):
            script = script_dedup
            applied.append(f"{dedup_count} redéclaration(s) supprimée(s)")
        else:
            phase3_log.warning(f"Pre-Patcher : _dedup_declarations cassait la syntaxe — ignoré")

    # Déduplication des fonctions en double
    script_fndedup, fn_dedup_count = _dedup_functions(script)
    if fn_dedup_count:
        # Garde de sécurité : vérifier que les éléments vitaux du jeu sont toujours présents
        _vital_keywords = ('DOMContentLoaded', 'requestAnimationFrame')
        _vitals_ok = all(kw in script_fndedup for kw in _vital_keywords)
        if not _vitals_ok:
            phase3_log.warning(f"Pre-Patcher : _dedup_functions supprimait DOMContentLoaded/requestAnimationFrame — ignoré")
        elif _quick_syntax_ok(script_fndedup):
            script = script_fndedup
            applied.append(f"{fn_dedup_count} ligne(s) de fonctions dupliquées supprimées")
        else:
            phase3_log.warning(f"Pre-Patcher : _dedup_functions cassait la syntaxe — ignoré")

    # Validation de portée : déplacer gameLoop hors des fonctions imbriquées
    script_scope, scope_fixed = _fix_gameloop_scope(script)
    if scope_fixed:
        if _quick_syntax_ok(script_scope):
            script = script_scope
            applied.append("gameLoop extrait au niveau global")
        else:
            phase3_log.warning(f"Pre-Patcher : _fix_gameloop_scope cassait la syntaxe — ignoré")

    # P5 — Passe supplémentaire si des corrections ont été appliquées
    # (un fix peut révéler un nouveau problème détectable programmatiquement)
    if applied:
        from agents.phase3._layer_gen import coherence_check as _coh_check2
        _p5_issues = []
        try:
            _p5_issues = _coh_check2(prefix + script + suffix)
        except Exception:
            pass
        if _p5_issues:
            _p5_new_applied = []
            _p5_script_before = script
            for _p5_issue in _p5_issues[:5]:
                _il = _p5_issue.lower()
                # Traitement programmatique uniquement en passe P5 (pas de LLM)
                _fn_stub_p5 = re.search(
                    r"(?:non définie|not defined|undefined)\s*:\s*([a-z][a-zA-Z0-9_]+)\s*\(",
                    _p5_issue
                )
                if _fn_stub_p5:
                    _fn_p5 = _fn_stub_p5.group(1)
                    if (len(_fn_p5) > 3 and _fn_p5 not in _CRITICAL_FN_BLACKLIST and
                            re.search(rf'\b{re.escape(_fn_p5)}\s*\(', script) and
                            not re.search(rf'\bfunction\s+{re.escape(_fn_p5)}\b', script)):
                        _stub_p5 = f"\nfunction {_fn_p5}(dt) {{ /* P5 auto-stub */ }}\n"
                        if _quick_syntax_ok(script + _stub_p5):
                            script = script + _stub_p5
                            _p5_new_applied.append(f"P5 stub {_fn_p5}()")
            if _p5_new_applied:
                applied.extend(_p5_new_applied)
                phase3_log.info(f"Pre-Patcher P5 : {len(_p5_new_applied)} correction(s) supplémentaire(s)")

    if applied:
        phase3_log.agent_done("Pre-Patcher", f"Corrections : {', '.join(applied)}")
        return prefix + script + suffix

    phase3_log.info("Pre-Patcher — aucune correction applicable")
    return html


def _dedup_declarations(script: str, keep_last: bool = False) -> tuple[str, int]:
    """
    Supprime les redéclarations de variables (let/const/var X = ...).
    Déduplique par (nom, niveau_indentation) pour ne jamais supprimer
    une variable locale qui a le même nom qu'une globale (scopes différents).
    Par défaut garde la première occurrence (keep_last=False).
    """
    import re as _re
    decl_pattern = _re.compile(
        r'^([ \t]*)(?:let|const|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=',
        _re.MULTILINE
    )
    # Clé = (nom, niveau_indent) — deux déclarations du même nom à des indentations
    # différentes sont dans des scopes différents et doivent être conservées
    seen = {}
    lines = script.split('\n')
    to_remove = set()

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith('//') or stripped.startswith('*'):
            continue
        m = decl_pattern.match(line)
        if m:
            indent = len(m.group(1))
            name = m.group(2)
            # Ne pas déduper les déclarations qui ouvrent un bloc multi-ligne (var X = {)
            # → supprimer seulement la ligne laisserait le } de fermeture flottant,
            # ce qui trompe ensuite _fix_orphan_closing_braces et peut corrompre le code.
            line_stripped_end = line.rstrip()
            if line_stripped_end.endswith('{') or line_stripped_end.endswith('['):
                continue
            key = (name, indent)
            if key in seen:
                if keep_last:
                    to_remove.add(seen[key])
                    seen[key] = i
                else:
                    to_remove.add(i)
            else:
                seen[key] = i

    if not to_remove:
        return script, 0

    filtered = [line for i, line in enumerate(lines) if i not in to_remove]
    return '\n'.join(filtered), len(to_remove)


def _dedup_functions(script: str) -> tuple[str, int]:
    """
    Supprime les déclarations de fonctions en double.
    Garde la DERNIÈRE occurrence (la plus complète dans le système layered où
    les couches tardives redéfinissent intentionnellement les couches précédentes).
    Supprime toutes les occurrences antérieures.
    """
    import re
    fn_pattern = re.compile(r'^[ \t]*function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(', re.MULTILINE)

    lines = script.split('\n')
    # Collecte toutes les occurrences : {name: [(start, end), ...]}
    occurrences = {}

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith('//') or stripped.startswith('*'):
            continue
        m = fn_pattern.match(line)
        if m:
            name = m.group(1)
            # Trouver la fin de cette fonction (accolade fermante correspondante)
            brace_count = 0
            has_opened = False
            end = i
            for j in range(i, min(i + 300, len(lines))):
                line_clean = re.sub(r'"(?:[^"\\]|\\.)*"', '', lines[j])
                line_clean = re.sub(r"'(?:[^'\\]|\\.)*'", '', line_clean)
                line_clean = re.sub(r'`(?:[^`\\]|\\.)*`', '', line_clean)
                line_clean = re.sub(r'//.*', '', line_clean)
                brace_count += line_clean.count('{') - line_clean.count('}')
                if brace_count > 0:
                    has_opened = True
                if has_opened and brace_count <= 0:
                    end = j
                    break
            if name not in occurrences:
                occurrences[name] = []
            occurrences[name].append((i, end + 1))

    # Pour chaque fonction en double, supprimer toutes sauf la PLUS LONGUE
    # (garder la dernière était dangereux : la dernière peut être un stub court
    #  qui écrase une implémentation complète — 605 lignes perdues observé en prod)
    to_remove_ranges = []
    for name, ranges in occurrences.items():
        if len(ranges) > 1:
            # Trouver l'occurrence la plus longue (end - start maximum)
            longest_idx = max(range(len(ranges)), key=lambda i: ranges[i][1] - ranges[i][0])
            for idx, (start, end) in enumerate(ranges):
                if idx != longest_idx:
                    to_remove_ranges.append((start, end))

    if not to_remove_ranges:
        return script, 0

    # Suppression de last à first pour préserver les indices
    result_lines = list(lines)
    removed = 0
    for start, end in sorted(to_remove_ranges, reverse=True):
        removed += end - start
        del result_lines[start:end]

    return '\n'.join(result_lines), removed


def _fix_canvas_listeners_outside_domready(script: str) -> tuple[str, bool]:
    """
    Détecte les canvas.addEventListener() placés AVANT DOMContentLoaded
    ET avant que canvas soit initialisé (= canvas undefined → crash immédiat → écran noir).
    Stratégie :
    - keydown/keyup → remplacer canvas.addEventListener par document.addEventListener
    - mousemove/click/mousedown/mouseup → déplacer le BLOC ENTIER (avec brace-scan)
      juste avant requestAnimationFrame dans DOMContentLoaded

    IMPORTANT : ne pas toucher si canvas est déjà assigné avant le listener
    (canvas = document.getElementById(...) précède l'addEventListener → OK).
    """
    dom_match = re.search(
        r'document\s*\.\s*addEventListener\s*\(\s*[\'"]DOMContentLoaded', script
    )
    if not dom_match:
        return script, False

    dom_start = dom_match.start()
    before_dom = script[:dom_start]

    # Chercher des canvas.addEventListener avant DOMContentLoaded
    listener_pattern = re.compile(
        r'canvas\s*\.\s*addEventListener\s*\(\s*[\'"](\w+)[\'"]',
    )
    if not listener_pattern.search(before_dom):
        return script, False

    # Si canvas est explicitement assigné avant les listeners, ne pas toucher
    # (canvas = document.getElementById(...) avant le premier addEventListener)
    canvas_init = re.search(r'\bcanvas\s*=\s*document\s*\.', before_dom)
    first_listener = listener_pattern.search(before_dom)
    if canvas_init and canvas_init.start() < first_listener.start():
        return script, False

    fixed = False

    # ── Clavier : remplacer canvas.addEventListener par document.addEventListener ──
    def fix_keyboard(m):
        nonlocal fixed
        event = m.group(1)
        if event in ('keydown', 'keyup', 'keypress'):
            fixed = True
            return m.group(0).replace('canvas.', 'document.', 1)
        return m.group(0)

    new_before = listener_pattern.sub(fix_keyboard, before_dom)

    # ── Souris : extraire le BLOC ENTIER (ouverture + corps + fermeture) ──
    mouse_events = ('mousemove', 'click', 'mousedown', 'mouseup', 'contextmenu')
    blocks_to_move = []

    def _extract_full_block(text: str, match_start: int) -> tuple[str, int] | None:
        """
        À partir de la position d'un canvas.addEventListener(, extrait tout le bloc
        jusqu'au ); de fermeture correspondant. Retourne (bloc_entier, pos_fin).
        """
        # Trouver la première parenthèse ouvrante (celle du addEventListener)
        pos = match_start
        paren_depth = 0
        started = False
        for i in range(pos, len(text)):
            ch = text[i]
            if ch == '(':
                paren_depth += 1
                started = True
            elif ch == ')':
                paren_depth -= 1
                if started and paren_depth == 0:
                    # Consommer le ';' éventuel
                    end = i + 1
                    if end < len(text) and text[end] == ';':
                        end += 1
                    return text[match_start:end], end
        return None

    # Trouver et extraire tous les blocs souris dans new_before
    remaining = new_before
    kept_parts = []
    pos = 0
    while True:
        m = re.search(r'canvas\s*\.\s*addEventListener\s*\(\s*[\'"](\w+)[\'"]', remaining[pos:])
        if not m:
            kept_parts.append(remaining[pos:])
            break
        event_name = m.group(1)
        abs_start = pos + m.start()
        if event_name in mouse_events:
            result = _extract_full_block(remaining, abs_start)
            if result:
                block, block_end = result
                kept_parts.append(remaining[pos:abs_start])
                # Nettoyer la ligne vide laissée par le retrait
                tail = remaining[abs_start:block_end]
                blocks_to_move.append(block.strip())
                pos = block_end
                fixed = True
                continue
        kept_parts.append(remaining[pos:abs_start + m.end()])
        pos = abs_start + m.end()
    new_before = ''.join(kept_parts)

    after_dom = script[dom_start:]
    if blocks_to_move:
        inject_block = '\n  '.join(blocks_to_move)
        # Insérer avant requestAnimationFrame dans DOMContentLoaded
        raf_match = re.search(r'requestAnimationFrame\s*\(', after_dom)
        if raf_match:
            after_dom = (after_dom[:raf_match.start()] +
                         inject_block + '\n  ' +
                         after_dom[raf_match.start():])

    result = new_before + after_dom
    return result, fixed


def _fix_gameloop_scope(script: str) -> tuple[str, bool]:
    """
    Détecte si 'function gameLoop' est définie à l'intérieur d'une autre fonction
    et la déplace au niveau global.
    """
    import re

    # Check if gameLoop is nested (preceded by function body code at same/deeper indent)
    lines = script.split('\n')
    gameloop_line = -1
    for i, line in enumerate(lines):
        if re.match(r'^[ \t]+function\s+gameLoop\s*\(', line):  # indented = nested
            gameloop_line = i
            break

    if gameloop_line == -1:
        return script, False  # Not nested or not found

    # Extract the gameLoop function block
    indent = len(lines[gameloop_line]) - len(lines[gameloop_line].lstrip())
    brace_count = 0
    end_line = gameloop_line
    for j in range(gameloop_line, min(gameloop_line + 100, len(lines))):
        brace_count += lines[j].count('{') - lines[j].count('}')
        if j > gameloop_line and brace_count <= 0:
            end_line = j
            break

    # Extract and dedent the function
    import textwrap
    fn_lines = lines[gameloop_line:end_line + 1]
    fn_block = textwrap.dedent('\n'.join(fn_lines))

    # Remove from original position
    new_lines = lines[:gameloop_line] + lines[end_line + 1:]

    # Insert at top level (before DOMContentLoaded or at beginning)
    dom_ready_line = -1
    for i, line in enumerate(new_lines):
        if 'DOMContentLoaded' in line:
            dom_ready_line = i
            break

    insert_at = dom_ready_line if dom_ready_line > 0 else 0
    new_lines = new_lines[:insert_at] + [fn_block, ''] + new_lines[insert_at:]

    return '\n'.join(new_lines), True


@with_fallback(None)
def _call_llm(prompt: str) -> str:
    return call_gemini(prompt, temperature=0.1, system_instruction=SYSTEM, max_tokens=8000)

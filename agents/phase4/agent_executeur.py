"""
Executor Agent — Phase 4
Launches the game in a headless browser (Playwright) and verifies
it actually works: canvas, game loop, inputs, absence of JS errors.
"""

import os
import time
import tempfile
from genre_profile import GenreProfile, EvaluationResult
from logger import phase4_log

EXECUTION_TIMEOUT = 8000  # ms (défaut)
INTERACTION_DELAY = 1.0   # secondes entre interactions

# Timeout d'init par genre (secondes) — les jeux complexes ont besoin de plus de temps
_GENRE_INIT_DELAY = {
    # Genres rapides à initialiser
    "arcade": 2.0, "runner": 2.0, "shooter": 2.0, "snake": 2.0, "breakout": 2.0, "tetris": 2.0,
    "platformer": 2.5, "action": 2.5,
    # Genres avec génération procédurale ou chargement plus long
    "rpg": 4.0, "dungeon": 4.0, "dungeon crawler": 4.0, "tower defense": 3.5,
    "strategy": 3.5, "simulation": 3.5, "metroidvania": 3.5, "roguelite": 4.0, "roguelike": 4.0,
    "survival": 3.5,
    # 3D : Three.js prend du temps à init WebGL
    "fps": 5.0, "3d": 5.0,
}

def _init_delay_for_genre(genre: str) -> float:
    """Retourne le délai d'initialisation adapté au genre du jeu."""
    genre_lower = genre.lower()
    for key, delay in _GENRE_INIT_DELAY.items():
        if key in genre_lower:
            return delay
    return 2.5  # défaut

# Cache local pour Three.js (évite de re-télécharger à chaque test)
_THREEJS_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "rag_database", "three.min.js")
_THREEJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"


def _get_threejs_local() -> str | None:
    """Télécharge Three.js une fois et le met en cache. Retourne le chemin local."""
    if os.path.exists(_THREEJS_CACHE_PATH) and os.path.getsize(_THREEJS_CACHE_PATH) > 100000:
        return _THREEJS_CACHE_PATH
    try:
        import urllib.request
        os.makedirs(os.path.dirname(_THREEJS_CACHE_PATH), exist_ok=True)
        phase4_log.info("Téléchargement Three.js pour les tests headless...")
        urllib.request.urlretrieve(_THREEJS_CDN, _THREEJS_CACHE_PATH)
        return _THREEJS_CACHE_PATH
    except Exception as e:
        phase4_log.warning(f"Impossible de télécharger Three.js : {e}")
        return None


def run(code: str, genre_profile: GenreProfile) -> EvaluationResult:
    phase4_log.agent_start("Exécuteur", "Test en navigateur headless")

    ev = EvaluationResult(agent_name="Exécuteur")

    try:
        ev = _run_playwright(code, genre_profile)
    except ImportError:
        phase4_log.warning("Playwright non installé — exécution simulée")
        ev = _run_simulated(code)
    except Exception as e:
        phase4_log.error(f"Erreur d'exécution : {e}")
        ev.score = 4.0
        ev.issues = [{"severite": "majeur", "description": str(e), "suggestion": "Vérifier le code"}]
        ev.commentaire_global = f"Erreur lors de l'exécution : {e}"

    # ─── BOUCLE DE REPAIR AUTOMATIQUE ────────────────────────────────────────────
    # Reproduction du process de debug manuel :
    #   1. Playwright détecte une erreur JS à l'écran
    #   2. On extrait le message exact
    #   3. On essaie des fixes déterministes (rapides, sans API)
    #   4. Si ça échoue → mini-patcher IA (Gemini ciblé sur l'erreur précise)
    #   5. On relance Playwright pour vérifier
    #   6. Répéter jusqu'à MAX_REPAIR fois
    _MAX_REPAIR = 4   # 2 passes dumb + 2 passes IA si besoin
    _MAX_AI_REPAIRS = 2   # max appels Gemini dans cette boucle
    _ai_repairs_done = 0
    _repair_code = code
    # B3: error type tracker — counts how many iterations each error fingerprint has persisted
    _error_persist: dict[str, int] = {}
    import re as _re_repair
    _undef_pattern     = _re_repair.compile(r"'?(\w+)'? is not defined", _re_repair.IGNORECASE)
    _arcade_pattern    = _re_repair.compile(r'ARCADE_ERROR:\s*(.+)', _re_repair.IGNORECASE)
    _cannot_read_pat   = _re_repair.compile(r"Cannot read propert\w+ of (?:undefined|null) \(reading '(\w+)'\)", _re_repair.IGNORECASE)
    _typeerr_pattern   = _re_repair.compile(r"TypeError:\s*(.+?)(?:\s+at\s+|$)", _re_repair.IGNORECASE)
    _not_func_pattern  = _re_repair.compile(r"(\w+) is not a function", _re_repair.IGNORECASE)

    for _repair_i in range(_MAX_REPAIR):
        if ev.score >= 7.0:
            break

        # ── Collecter TOUTES les erreurs JS : chargement + gameplay ──────────────
        _undef_vars = set()
        _has_arcade_error = False
        _has_screen_issue = False
        _error_msgs = []    # messages d'erreur bruts pour le mini-patcher IA
        _cannot_read_props = set()
        _not_func_names = set()

        for _c in ev.criteres:
            _txt = _c.get('commentaire', '')
            nom = _c.get('nom', '')

            # Variables non définies (chargement ET gameplay)
            for _m in _undef_pattern.finditer(_txt):
                _v = _m.group(1)
                # Filtrer les faux positifs (variables navigateur)
                if _v not in ('undefined', 'null', 'true', 'false', 'NaN', 'Infinity'):
                    _undef_vars.add(_v)

            # Erreur gameLoop visible (écran d'erreur affiché dans le jeu)
            for _m in _arcade_pattern.finditer(_txt):
                _has_arcade_error = True
                _err_text = _m.group(1).strip()
                _error_msgs.append(_err_text)
                for _m2 in _undef_pattern.finditer(_err_text):
                    _undef_vars.add(_m2.group(1))

            # Cannot read property (crash objet undefined)
            for _m in _cannot_read_pat.finditer(_txt):
                _cannot_read_props.add(_m.group(1))
                _error_msgs.append(_txt[:120])

            # X is not a function
            for _m in _not_func_pattern.finditer(_txt):
                _not_func_names.add(_m.group(1))
                _error_msgs.append(_txt[:120])

            # TypeError générique
            for _m in _typeerr_pattern.finditer(_txt):
                if _m.group(1) not in _error_msgs:
                    _error_msgs.append('TypeError: ' + _m.group(1)[:100])

            # Erreurs JS brutes (critère B3 — inclut les crashs gameplay)
            if nom == 'Erreurs JS brutes':
                raw_errors = [e.strip() for e in _txt.split('|') if e.strip()]
                for _re_raw in raw_errors:
                    _error_msgs.append(_re_raw[:150])
                    for _m in _undef_pattern.finditer(_re_raw):
                        _undef_vars.add(_m.group(1))
                    for _m in _cannot_read_pat.finditer(_re_raw):
                        _cannot_read_props.add(_m.group(1))

            # Crashes pendant inputs (gameplay)
            if nom in ('Inputs sans crash', 'Joueur réactif', 'Score progresse') and _c.get('score', 1) == 0:
                if 'crash' in _txt.lower() or 'erreur' in _txt.lower() or 'undefined' in _txt.lower():
                    _error_msgs.append(f'[GAMEPLAY] {_txt[:120]}')
                    for _m in _undef_pattern.finditer(_txt):
                        _undef_vars.add(_m.group(1))

            # Écran noir
            if 'ÉCRAN NOIR' in _txt or 'ecran noir' in _txt.lower() or 'canvas figé' in _txt.lower():
                _has_screen_issue = True

        # Dédupliquer
        _error_msgs = list(dict.fromkeys(_error_msgs))[:6]

        # B3: update persistence counter and flag recurring errors for the AI
        _new_persist: dict[str, int] = {}
        _flagged_msgs = []
        for _em in _error_msgs:
            _fp = _em[:60]  # fingerprint: first 60 chars
            _cnt = _error_persist.get(_fp, 0) + 1
            _new_persist[_fp] = _cnt
            _flagged_msgs.append(f"[PERSISTS×{_cnt}] {_em}" if _cnt > 1 else _em)
        _error_persist.update(_new_persist)
        _error_msgs = _flagged_msgs  # AI sees persistence count

        has_any_error = bool(_undef_vars or _has_arcade_error or _has_screen_issue
                             or _cannot_read_props or _not_func_names or _error_msgs)
        if not has_any_error:
            break

        # ── ÉTAPE 1 : Fixes déterministes (rapides, sans API) ────────────────────
        try:
            from js_syntax_checker import fix_all_auto as _fix_all, fix_undefined_runtime_vars as _fix_undef_vars
        except ImportError:
            break

        _fixed = _repair_code
        _did_any_fix = False
        _fix_reasons = []

        # Fix ciblé : variables non définies
        if _undef_vars:
            _fixed, _did, _descs = _fix_undef_vars(_fixed, _undef_vars)
            if _did:
                _did_any_fix = True
                _fix_reasons.append(f"vars: {', '.join(sorted(_undef_vars)[:4])}")

        # Fix générique : ESLint + syntax
        _fixed2, _did2, _ = _fix_all(_fixed)
        if _did2:
            _fixed = _fixed2
            _did_any_fix = True
            _fix_reasons.append("fix_all_auto")

        # B4a: code_validator on every pass — includes _fix_arrow_key_mapping for
        # key-mapping bugs that cause "Joueur réactif" failures
        try:
            from code_validator import validate_and_fix as _cv_fix
            _cv_result, _cv_issues, _ = _cv_fix(_fixed)
            if _cv_issues:
                _fixed = _cv_result
                _did_any_fix = True
                _fix_reasons.append(f"code_validator ({len(_cv_issues)} fix(es))")
        except Exception:
            pass

        # ── ÉTAPE 2 : Mini-patcher IA si les fixes déterministes n'ont pas suffi ─
        if not _did_any_fix and _ai_repairs_done < _MAX_AI_REPAIRS and _error_msgs:
            phase4_log.info(f"[Repair {_repair_i+1}] Fixes déterministes insuffisants — mini-patcher IA ({_ai_repairs_done+1}/{_MAX_AI_REPAIRS})")
            _ai_fixed = _mini_patcher_gemini(_repair_code, _error_msgs, genre_profile)
            if _ai_fixed:
                # B5: diff ratio check — rollback if AI patch modified >35% of chars
                # (protects against LLM rewriting the whole game instead of targeting the fix)
                _orig_len = max(len(_repair_code), 1)
                _changed = sum(1 for a, b in zip(_repair_code, _ai_fixed) if a != b)
                _changed += abs(len(_ai_fixed) - len(_repair_code))
                _diff_ratio = _changed / _orig_len
                if _diff_ratio > 0.35:
                    phase4_log.warning(
                        f"[Repair {_repair_i+1}] B5: mini-patcher diff ratio {_diff_ratio:.0%} > 35% — rollback"
                    )
                    break
                _fixed = _ai_fixed
                _did_any_fix = True
                _ai_repairs_done += 1
                _fix_reasons.append(f"mini-patcher IA [{_error_msgs[0][:40]}...]")
            else:
                phase4_log.warning(f"[Repair {_repair_i+1}] Mini-patcher IA sans résultat — arrêt")
                break

        if not _did_any_fix:
            phase4_log.warning(f"[Repair {_repair_i+1}] Aucun fix applicable — arrêt")
            break

        _reason_str = " | ".join(_fix_reasons)
        phase4_log.info(f"[Repair {_repair_i+1}/{_MAX_REPAIR}] {_reason_str} — relance Playwright")

        # Fix 2: syntax check before Playwright — don't waste a run on broken code
        try:
            from js_syntax_checker import check_and_report as _pre_chk
            _, _pre_broken = _pre_chk(_fixed)
            if _pre_broken:
                phase4_log.warning(f"[Repair {_repair_i+1}] Fixed code has syntax error — skipping Playwright run")
                break
        except Exception:
            pass

        try:
            _ev_retry = _run_playwright(_fixed, genre_profile)
            if _ev_retry.score > ev.score:
                phase4_log.info(f"[Repair {_repair_i+1}] score amélioré : {ev.score:.1f} → {_ev_retry.score:.1f}")
                _ev_retry.commentaire_global = (
                    f"[REPAIR×{_repair_i+1} +{_ev_retry.score - ev.score:.1f}] "
                    + _ev_retry.commentaire_global
                )
                ev = _ev_retry
                _repair_code = _fixed
            else:
                phase4_log.info(f"[Repair {_repair_i+1}] score non amélioré ({_ev_retry.score:.1f}) — arrêt")
                break
        except Exception as _e_retry:
            phase4_log.warning(f"[Repair {_repair_i+1}] Playwright retry échoué : {_e_retry}")
            break

    phase4_log.score("Exécution", ev.score)
    return ev


def _extract_function_section(js_code: str, targets: set) -> tuple[str, int, int] | None:
    """
    Extrait la fonction JS qui contient l'une des variables/noms cibles.
    Remonte au 'function' précédent, suit les accolades jusqu'à la fermeture.
    Retourne (section_code, start_in_js, end_in_js) ou None si introuvable.
    """
    import re

    # Trouver la première occurrence d'une cible dans le code
    best_pos = len(js_code) + 1
    for target in targets:
        # Chercher le nom comme token JS (pas dans un commentaire)
        for m in re.finditer(r'\b' + re.escape(target) + r'\b', js_code):
            if m.start() < best_pos:
                best_pos = m.start()
                break

    if best_pos > len(js_code):
        return None

    # Remonter pour trouver le début de la fonction englobante
    func_start = -1
    # Chercher le dernier "function " avant best_pos
    for m in re.finditer(r'\bfunction\s+\w*\s*\(', js_code[:best_pos]):
        func_start = m.start()
    # Aussi chercher les fonctions fléchées / méthodes d'objets
    if func_start < 0:
        func_start = max(0, best_pos - 300)

    # Trouver la fin de la fonction par comptage d'accolades
    depth = 0
    func_end = best_pos
    in_string = False
    string_char = ''
    for i in range(func_start, min(func_start + 5000, len(js_code))):
        c = js_code[i]
        if in_string:
            if c == string_char and (i == 0 or js_code[i-1] != '\\'):
                in_string = False
        elif c in ('"', "'", '`'):
            in_string = True
            string_char = c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                func_end = i + 1
                break

    # Ajouter contexte : 3 lignes avant la fonction (pour les commentaires)
    section_start = max(0, js_code.rfind('\n', 0, func_start - 1) + 1 if func_start > 0 else 0)
    # Aller 2 lignes en arrière depuis func_start
    for _ in range(2):
        prev = js_code.rfind('\n', 0, section_start - 1)
        if prev >= 0:
            section_start = prev + 1

    section_end = min(len(js_code), func_end)
    return js_code[section_start:section_end], section_start, section_end


def _extract_globals(js_code: str, max_chars: int = 1500) -> str:
    """
    Extrait les déclarations de variables globales du début du JS.
    Ces vars sont nécessaires pour que Gemini comprenne le contexte sans lire tout le code.
    """
    import re
    lines = js_code.split('\n')
    global_lines = []
    chars = 0
    for line in lines:
        stripped = line.strip()
        # Lignes de déclarations de variables globales
        if (stripped.startswith('var ') or stripped.startswith('const ') or
                stripped.startswith('let ') or stripped.startswith('// ') or
                stripped.startswith('/* ') or (stripped.startswith('function ') and len(stripped) < 80)):
            global_lines.append(line)
            chars += len(line)
            if chars > max_chars:
                break
        elif stripped and not stripped.startswith('var ') and chars > 200:
            # On a passé la zone de déclarations
            break
    return '\n'.join(global_lines)


def _mini_patcher_gemini(html_code: str, error_msgs: list, genre_profile) -> str | None:
    """
    Mini-patcher IA anti-lost-in-the-middle.

    Au lieu de passer tout le code (22K chars → modèle perd le fil),
    on extrait UNIQUEMENT :
    1. Les déclarations de variables globales (~30 lignes — contexte suffisant)
    2. La fonction spécifique où l'erreur se produit (~50-150 lignes)

    Gemini corrige ces ~200 lignes ciblées → on réinjecte dans le code original.
    C'est l'équivalent du debug manuel : "voilà la fonction qui crash, corrige-la."
    """
    if not error_msgs or not html_code:
        return None
    try:
        from config import call_gemini
        import re

        # ── Extraire le JS du HTML ──────────────────────────────────────────────
        js_match = re.search(r'(<script[^>]*>)(.*?)(</script>)', html_code, re.DOTALL)
        if not js_match:
            return None
        js_prefix   = js_match.group(1)
        js_code     = js_match.group(2)
        js_suffix   = js_match.group(3)
        html_before = html_code[:js_match.start()]
        html_after  = html_code[js_match.end():]

        # ── Extraire les cibles depuis les messages d'erreur ───────────────────
        def _is_only_obj_key(ident: str) -> bool:
            used_standalone = bool(re.search(rf'\b{re.escape(ident)}\s*(?:\(|\.|\[|=(?!=))', js_code))
            used_as_key = bool(re.search(rf'[{{\s,]\s*{re.escape(ident)}\s*:', js_code))
            return used_as_key and not used_standalone

        targets = set()
        for err in error_msgs:
            # "X is not defined"
            for m in re.finditer(r"'?(\w+)'? is not defined", err, re.IGNORECASE):
                v = m.group(1)
                if v not in ('undefined', 'null', 'true', 'false', 'window', 'document') and not _is_only_obj_key(v):
                    targets.add(v)
            # "Cannot read properties of undefined (reading 'X')"
            for m in re.finditer(r"reading '(\w+)'", err):
                targets.add(m.group(1))
            # "X is not a function"
            for m in re.finditer(r"(\w+) is not a function", err, re.IGNORECASE):
                targets.add(m.group(1))
            # "[GAMEPLAY] ... X is not defined"
            for m in re.finditer(r'\b([A-Za-z_]\w+)\s+(?:is not defined|is not a function)', err):
                targets.add(m.group(1))

        if not targets and not error_msgs:
            return None

        # ── Extraire le contexte global (variables déclarées en haut) ──────────
        globals_ctx = _extract_globals(js_code, max_chars=1200)

        # ── Extraire la/les fonction(s) concernée(s) ───────────────────────────
        sections_to_fix = []   # [(section_text, start, end)]

        # Pour chaque cible, extraire sa fonction
        already_covered = set()  # éviter de passer la même fonction deux fois
        for target in list(targets)[:4]:
            result = _extract_function_section(js_code, {target})
            if result:
                section_text, sec_start, sec_end = result
                # Vérifier qu'on n'a pas déjà une section qui couvre cet intervalle
                overlap = any(
                    not (sec_end <= s or sec_start >= e)
                    for (_, s, e) in sections_to_fix
                )
                if not overlap and section_text not in already_covered:
                    sections_to_fix.append((section_text, sec_start, sec_end))
                    already_covered.add(section_text)

        if not sections_to_fix:
            # Fallback : prendre les 2000 premiers chars (zone init souvent problématique)
            sections_to_fix = [(js_code[:2000], 0, 2000)]

        # ── Fix 5: collect declaration context for each target ────────────────
        decl_ctx_lines = []
        for _tgt in list(targets)[:4]:
            # Search for assignments/declarations of the target variable
            _decl_pat = re.compile(
                r'^[^\n]*\b(?:var|let|const)\s+' + re.escape(_tgt) + r'\b[^\n]*$'
                r'|^[^\n]*\b' + re.escape(_tgt) + r'\s*=[^\n]{0,80}$',
                re.MULTILINE
            )
            _decl_matches = _decl_pat.findall(js_code)
            if _decl_matches:
                for _dm in _decl_matches[:2]:
                    decl_ctx_lines.append(f'  // Déclaration de {_tgt}: {_dm.strip()[:120]}')

        decl_ctx_text = '\n'.join(decl_ctx_lines) if decl_ctx_lines else '  // (aucune déclaration trouvée)'

        # ── Construire le prompt focalisé ──────────────────────────────────────
        errors_text = '\n'.join(f'  {i+1}. {e}' for i, e in enumerate(error_msgs[:4]))
        sections_text = '\n\n---\n\n'.join(
            f'// SECTION {i+1} (à corriger) :\n{s[0]}'
            for i, s in enumerate(sections_to_fix)
        )
        total_section_chars = sum(len(s[0]) for s in sections_to_fix)

        prompt = f"""Tu es un debugger JavaScript expert en jeux HTML5 Canvas.
Playwright a détecté ces erreurs runtime :

ERREURS :
{errors_text}

DÉCLARATIONS DES VARIABLES CIBLES (où elles sont définies dans le code) :
{decl_ctx_text}

VARIABLES GLOBALES DU JEU (contexte — ne pas modifier) :
```javascript
{globals_ctx}
```

SECTION(S) DE CODE À CORRIGER ({total_section_chars} chars — c'est là que l'erreur se produit) :
```javascript
{sections_text}
```

CAUSES FRÉQUENTES :
- "X is not defined" dans une boucle → `var e = arr[i];` manquant avant `e.x`
- "Cannot read ... undefined" → objet null, ajouter `if (!obj) return;`
- "X is not a function" → X écrasé par une var du même nom
- Crash ArrowLeft/Right → `keys["arrowleft"]` vs `keys.left` (mapping incohérent)
- `blinkAlpha` non défini dans drawGameOver → le déclarer localement dans la fonction

RÈGLES :
1. Corrige UNIQUEMENT les erreurs listées dans les sections fournies
2. Retourne UNIQUEMENT le code corrigé pour chaque section, dans le même ordre
3. Sépare chaque section corrigée par la ligne exacte : // SECTION_FIXED_N
4. Ne réécris rien d'autre

SECTIONS CORRIGÉES :"""

        response = call_gemini(prompt, temperature=0.05, max_tokens=8000, disable_thinking=True)

        if not response or len(response) < 50:
            phase4_log.warning("Mini-patcher IA : réponse vide")
            return None

        # ── Parser la réponse et réinjecter chaque section ──────────────────────
        # Nettoyer les backticks markdown
        response = re.sub(r'^```(?:javascript|js)?\s*\n?', '', response.strip())
        response = re.sub(r'\n?```\s*$', '', response.strip())

        # Tenter de séparer les sections par le marqueur // SECTION_FIXED_N
        fixed_sections_raw = re.split(r'//\s*SECTION_FIXED_\d+\s*\n?', response)
        # Filtrer les segments vides
        fixed_sections_raw = [s.strip() for s in fixed_sections_raw if s.strip()]

        # Si une seule section (pas de marqueur), utiliser pour la première section
        if len(fixed_sections_raw) == 0:
            phase4_log.warning("Mini-patcher IA : réponse sans contenu utilisable")
            return None

        # Réinjecter dans le JS original, en remplaçant section par section
        # On trie par position décroissante pour ne pas décaler les indices
        fixed_js = js_code
        replacements = []
        for i, (orig_section, sec_start, sec_end) in enumerate(sections_to_fix):
            if i < len(fixed_sections_raw):
                fixed_section = fixed_sections_raw[i]
            else:
                fixed_section = fixed_sections_raw[-1]  # réutiliser le dernier
            # Vérifier que le fix est raisonnable (pas plus de 3x plus court)
            if len(fixed_section) < len(orig_section) * 0.3:
                phase4_log.warning(f"Mini-patcher IA : section {i+1} réponse trop courte — ignorée")
                continue
            replacements.append((sec_start, sec_end, fixed_section))

        # Fix 6: if "X is not defined" target is missing from the fixed section, inject fallback
        undef_targets = set()
        for err in error_msgs[:4]:
            for m in re.finditer(r"'?(\w+)'? is not defined", err, re.IGNORECASE):
                undef_targets.add(m.group(1))

        if undef_targets:
            for i, (s_start, s_end, fixed_section) in enumerate(replacements):
                for _uv in list(undef_targets):
                    _decl_pat_check = re.compile(
                        r'\b(?:var|let|const)\s+' + re.escape(_uv) + r'\b'
                        r'|\b' + re.escape(_uv) + r'\s*='
                    )
                    if not _decl_pat_check.search(fixed_section):
                        _fallback = f'var {_uv} = null; // fallback injected\n'
                        replacements[i] = (s_start, s_end, _fallback + fixed_section)
                        phase4_log.info(f"Fix 6: injected fallback declaration for '{_uv}'")

        if not replacements:
            return None

        # Appliquer les remplacements du dernier au premier (positions stables)
        replacements.sort(key=lambda x: x[0], reverse=True)
        for sec_start, sec_end, fixed_section in replacements:
            fixed_js = fixed_js[:sec_start] + fixed_section + fixed_js[sec_end:]

        # Réinjecter dans le HTML
        fixed_html = html_before + js_prefix + '\n' + fixed_js + '\n' + js_suffix + html_after

        # Sanity check — length
        if len(fixed_html) < len(html_code) * 0.65:
            phase4_log.warning(f"Mini-patcher IA : HTML résultant trop court — rejeté")
            return None

        # Syntax check — reject if the patch introduced a new syntax error
        try:
            from js_syntax_checker import check_and_report as _js_chk
            _issues, _broken = _js_chk(fixed_html)
            if _broken:
                phase4_log.warning(
                    f"Mini-patcher IA : syntaxe cassée après injection "
                    f"({_issues[0][:80] if _issues else '?'}) — rejeté"
                )
                return None
        except Exception:
            pass  # If checker unavailable, accept and let Playwright decide

        phase4_log.info(
            f"Mini-patcher IA : {len(replacements)} section(s) corrigée(s) "
            f"(cibles: {', '.join(list(targets)[:3])})"
        )
        return fixed_html

    except Exception as e:
        phase4_log.warning(f"Mini-patcher IA exception : {e}")
        return None


def _run_playwright(code: str, genre_profile: GenreProfile) -> EvaluationResult:
    from playwright.sync_api import sync_playwright
    ev = EvaluationResult(agent_name="Exécuteur")
    tests_passes = []
    tests_echoues = []
    js_errors = []
    _hooks_available = False  # B1/B4 : initialisé avant try/finally
    _hooks_penalty = False    # B4

    # Écrire le HTML dans un fichier temporaire
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    is_threejs = "three.min.js" in code or "three.js" in code.lower()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--enable-webgl",
                    "--ignore-gpu-blocklist",
                    "--use-gl=angle",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            page = browser.new_page()

            # Capture des erreurs JS
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            page.on("console", lambda msg: js_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

            # Pour les jeux Three.js : intercepter le CDN et servir en local
            if is_threejs:
                threejs_local = _get_threejs_local()
                if threejs_local:
                    def handle_threejs_route(route):
                        try:
                            with open(threejs_local, "rb") as f:
                                route.fulfill(status=200, content_type="application/javascript", body=f.read())
                        except Exception:
                            route.continue_()
                    page.route("**/*three*", handle_threejs_route)
                    page.route("**/*cdnjs.cloudflare.com*three*", handle_threejs_route)

            # Charger le jeu
            page.goto(f"file://{tmp_path}")
            time.sleep(_init_delay_for_genre(genre_profile.genre_principal))

            # Lire l'erreur gameLoop capturée par le try/catch (invisible à page.on('pageerror'))
            try:
                _arcade_err = page.evaluate("typeof window.__ARCADE_ERROR__ !== 'undefined' ? window.__ARCADE_ERROR__ : ''")
                if _arcade_err:
                    js_errors.append(f"ARCADE_ERROR: {_arcade_err}")
                    phase4_log.warning(f"Erreur gameLoop (écran d'erreur) : {_arcade_err}")
            except Exception:
                pass

            # Test 1 : Canvas présent (Three.js crée son propre canvas via WebGLRenderer)
            canvas = page.query_selector("canvas")
            if canvas:
                tests_passes.append({"nom": "Canvas présent", "score": 1.5, "commentaire": "Canvas HTML5 détecté"})
            else:
                # Pour Three.js, attendre que le renderer crée le canvas
                if is_threejs:
                    time.sleep(1.5)
                    canvas = page.query_selector("canvas")
                if canvas:
                    tests_passes.append({"nom": "Canvas présent", "score": 1.5, "commentaire": "Canvas Three.js détecté"})
                else:
                    tests_echoues.append({"nom": "Canvas présent", "score": 0, "commentaire": "Aucun canvas détecté"})

            # Test 2 : Pas d'erreurs JS critiques au chargement
            # Pour les jeux Three.js uniquement : filtrer les messages du renderer GPU (faux positifs)
            # Pour les jeux 2D : AUCUN filtre — tout TypeError/ReferenceError est critique
            threejs_renderer_noise = {"webgl context", "gl_", "shader compilation", "context lost", "webglrenderer", "three.webgl"}
            critical_errors = [
                e for e in js_errors
                if ("undefined" in e.lower() or "referenceerror" in e.lower()
                    or "typeerror" in e.lower() or "is not defined" in e.lower()
                    or "is not a function" in e.lower() or "cannot read" in e.lower()
                    or "syntaxerror" in e.lower() or "unexpected token" in e.lower()
                    or "type not found" in e.lower() or "not found:" in e.lower())
                and (not is_threejs or not any(n in e.lower() for n in threejs_renderer_noise))
            ]
            errors_count_at_load = len(critical_errors)
            if not critical_errors:
                tests_passes.append({"nom": "Pas d'erreurs JS", "score": 1.5, "commentaire": "Aucune erreur critique au chargement"})
            else:
                tests_echoues.append({
                    "nom": "Pas d'erreurs JS", "score": 0,
                    "commentaire": f"Erreurs au chargement: {critical_errors[:2]}"
                })

            # Test 3a : Contenu visible — le canvas n'est pas un écran noir
            if canvas:
                bright_pct = page.evaluate("""() => {
                    const canvas = document.querySelector('canvas');
                    if (!canvas || canvas.width === 0 || canvas.height === 0) return 0;
                    // Canvas 2D
                    try {
                        const ctx = canvas.getContext('2d');
                        if (ctx) {
                            const w = Math.min(canvas.width, 120), h = Math.min(canvas.height, 120);
                            const d = ctx.getImageData(0, 0, w, h).data;
                            let bright = 0;
                            for (let i = 0; i < d.length; i += 4) {
                                if (d[i] > 25 || d[i+1] > 25 || d[i+2] > 25) bright++;
                            }
                            return bright / (d.length / 4);
                        }
                    } catch(e) {}
                    // WebGL (Three.js) — readPixels fonctionne si preserveDrawingBuffer=true
                    try {
                        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                        if (gl) {
                            const w = Math.min(canvas.width, 120), h = Math.min(canvas.height, 120);
                            const pixels = new Uint8Array(w * h * 4);
                            gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
                            let bright = 0;
                            for (let i = 0; i < pixels.length; i += 4) {
                                if (pixels[i] > 25 || pixels[i+1] > 25 || pixels[i+2] > 25) bright++;
                            }
                            return bright / (w * h);
                        }
                    } catch(e) {}
                    return -1;  // indéterminé
                }""")

                if bright_pct < 0:
                    # Indéterminé (WebGL sans preserveDrawingBuffer) — score partiel, max_score ajusté
                    tests_passes.append({"nom": "Contenu visible", "score": 1.0,
                                         "commentaire": "Pixels non lisibles (WebGL sans preserveDrawingBuffer) — score partiel"})
                elif bright_pct < 0.02:
                    # Écran noir (< 2% de pixels non-noirs)
                    tests_echoues.append({"nom": "Contenu visible", "score": 0,
                                          "commentaire": f"ÉCRAN NOIR — {bright_pct*100:.2f}% pixels visibles seulement"})
                    js_errors.append(f"ÉCRAN NOIR DÉTECTÉ : {bright_pct*100:.2f}% de pixels non-noirs")
                elif bright_pct < 0.10:
                    # Très sombre (2–10%)
                    tests_echoues.append({"nom": "Contenu visible", "score": 0,
                                          "commentaire": f"Canvas très sombre ({bright_pct*100:.1f}% pixels visibles) — rendu partiel"})
                    js_errors.append(f"ÉCRAN QUASI-NOIR : {bright_pct*100:.1f}% des pixels ont de la couleur")
                else:
                    tests_passes.append({"nom": "Contenu visible", "score": 2.5,
                                         "commentaire": f"Canvas non-noir ({bright_pct*100:.0f}% pixels visibles)"})

            # Test 3b : Vérifier que le jeu tourne (game loop active)
            if canvas:
                screenshot1 = canvas.screenshot()
                time.sleep(1.5)
                screenshot2 = canvas.screenshot()
                if screenshot1 != screenshot2:
                    tests_passes.append({"nom": "Game loop active", "score": 2.0, "commentaire": "Le canvas se met à jour"})
                else:
                    tests_echoues.append({"nom": "Game loop active", "score": 0,
                                          "commentaire": "Canvas figé — game loop inactive ou bloquée"})

            # B2 : Test FPS réel via __ARCADE_TEST__._frame (mesure sur 2s)
            try:
                _fps_frame_start = page.evaluate("typeof window.__ARCADE_TEST__ !== 'undefined' ? window.__ARCADE_TEST__._frame : -1")
                if _fps_frame_start >= 0:
                    time.sleep(2.0)
                    _fps_frame_end = page.evaluate("window.__ARCADE_TEST__._frame")
                    _fps_measured = (_fps_frame_end - _fps_frame_start) / 2.0
                    if _fps_measured >= 25:
                        tests_passes.append({"nom": "FPS", "score": 1.0,
                                             "commentaire": f"FPS mesuré : {_fps_measured:.0f} fps (≥25 — fluide)"})
                    elif _fps_measured >= 10:
                        tests_passes.append({"nom": "FPS", "score": 0.5,
                                             "commentaire": f"FPS mesuré : {_fps_measured:.0f} fps (lent mais fonctionnel)"})
                    else:
                        tests_echoues.append({"nom": "FPS", "score": 0,
                                              "commentaire": f"FPS mesuré : {_fps_measured:.0f} fps (< 10 — probablement bloqué)"})
                        js_errors.append(f"B2: FPS très bas : {_fps_measured:.0f} fps")
            except Exception:
                pass  # B2 non bloquant

            # ─── Test 4a : DÉMARRAGE DU JEU (Space/Enter → canvas change) ───────────
            # Valide que le menu répond et que la transition menu→jeu se produit
            screenshot_menu = canvas.screenshot() if canvas else None
            input_crash = False
            try:
                page.keyboard.press("Space")
                time.sleep(0.4)
                page.keyboard.press("Enter")
                time.sleep(1.2)  # laisser le jeu démarrer
            except Exception as e:
                input_crash = True
                js_errors.append(f"CRASH démarrage : {e}")

            # Inspection JS : lire gameState pour confirmer la transition
            game_started_js = False
            game_state_val = "?"
            try:
                gs = page.evaluate("typeof gameState !== 'undefined' ? String(gameState) : '__undef__'")
                if gs != "__undef__":
                    game_state_val = gs
                    # Si gameState n'est plus 'menu'/'title'/'start' → jeu démarré
                    if gs.lower() not in ('menu', 'title', 'start', 'intro', 'loading'):
                        game_started_js = True
            except Exception:
                pass

            screenshot_post_start = canvas.screenshot() if canvas else None
            canvas_changed_start = (screenshot_menu and screenshot_post_start
                                    and screenshot_menu != screenshot_post_start)

            if (canvas_changed_start or game_started_js) and not input_crash:
                details = []
                if canvas_changed_start: details.append("canvas changé")
                if game_started_js: details.append(f"gameState={game_state_val}")
                tests_passes.append({"nom": "Démarrage jeu", "score": 1.5,
                                     "commentaire": f"Menu → jeu confirmé ({', '.join(details)})"})
            elif input_crash:
                tests_echoues.append({"nom": "Démarrage jeu", "score": 0,
                                      "commentaire": "Crash JS lors de Space/Enter"})
            else:
                tests_echoues.append({"nom": "Démarrage jeu", "score": 0,
                                      "commentaire": f"Canvas inchangé après Space/Enter — menu non réactif (gameState={game_state_val})"})

            # ─── B1 : Lire état hooks avant interactions ──────────────────────────────
            _hooks_available = False
            _state_before = None
            try:
                _hooks_available = page.evaluate("typeof window.__ARCADE_TEST__ !== 'undefined' && typeof window.__ARCADE_TEST__.getState === 'function'")
                if _hooks_available:
                    _state_before = page.evaluate("window.__ARCADE_TEST__.getState()")
            except Exception:
                pass

            # ─── B2 : FPS via frame counter ──────────────────────────────────────────
            _frame_before = None
            try:
                if _hooks_available:
                    _frame_before = page.evaluate("window.__ARCADE_TEST__._frame")
            except Exception:
                pass

            # ─── Test 4b : GAMEPLAY RÉACTIF via hooks logiques (B1) ──────────────────
            # Lire player.x AVANT les inputs (fallback direct sans hooks)
            _player_x_before = -1
            _lives_before = -1
            try:
                _player_x_before = page.evaluate(
                    "typeof player !== 'undefined' && player ? Number(player.x) : "
                    "(typeof playerX !== 'undefined' ? Number(playerX) : -1)"
                )
                _lives_before = page.evaluate("typeof lives !== 'undefined' ? Number(lives) : -1")
            except Exception:
                pass

            try:
                page.keyboard.down("ArrowRight")
                time.sleep(0.6)
                page.keyboard.press("Space")   # tir / action
                time.sleep(0.4)
                page.keyboard.up("ArrowRight")
                page.keyboard.down("ArrowLeft")
                time.sleep(0.5)
                page.keyboard.up("ArrowLeft")
                page.keyboard.press("z")       # certains jeux utilisent z/x
                time.sleep(0.3)
            except Exception as e:
                input_crash = True
                js_errors.append(f"CRASH gameplay inputs : {e}")

            # Lire état après interactions — player.x direct + hooks
            _state_after = None
            _hooks_penalty = False
            _player_x_after = -1
            _lives_after = -1
            try:
                score_val = page.evaluate("typeof score !== 'undefined' ? Number(score) : -1")
                lives_val = page.evaluate("typeof lives !== 'undefined' ? Number(lives) : -1")
                game_state_now = page.evaluate("typeof gameState !== 'undefined' ? String(gameState) : '?'")
                _player_x_after = page.evaluate(
                    "typeof player !== 'undefined' && player ? Number(player.x) : "
                    "(typeof playerX !== 'undefined' ? Number(playerX) : -1)"
                )
                _lives_after = page.evaluate("typeof lives !== 'undefined' ? Number(lives) : -1")
                if _hooks_available:
                    _state_after = page.evaluate("window.__ARCADE_TEST__.getState()")
            except Exception:
                score_val, lives_val, game_state_now = -1, -1, "?"

            # B4 : pénalité si tous les hooks retournent null (architecture cassée)
            if _hooks_available and _state_after:
                _all_null = (_state_after.get('score') is None and
                             _state_after.get('playerX') is None and
                             _state_after.get('gameState') is None)
                if _all_null:
                    _hooks_penalty = True
                    js_errors.append("B4: __ARCADE_TEST__ retourne tout null — variables de jeu non exposées")

            # Évaluer réactivité via hooks ou fallback canvas diff
            screenshot_gameplay = canvas.screenshot() if canvas else None
            canvas_moved = (screenshot_post_start and screenshot_gameplay
                            and screenshot_post_start != screenshot_gameplay)

            if _hooks_available and _state_before and _state_after and not _hooks_penalty:
                # B1 : tester avec les vraies variables de jeu
                _player_moved = (
                    _state_before.get('playerX') is not None and
                    _state_after.get('playerX') is not None and
                    abs((_state_after.get('playerX') or 0) - (_state_before.get('playerX') or 0)) > 5
                )
                _score_changed = (
                    _state_before.get('score') is not None and
                    _state_after.get('score') is not None and
                    _state_after.get('score') != _state_before.get('score')
                )
                _gs_playing = _state_after.get('gameState') not in ('menu', 'title', 'start', None)

                if _player_moved:
                    tests_passes.append({"nom": "Joueur réactif", "score": 1.5,
                                         "commentaire": f"playerX changé de {_state_before.get('playerX'):.0f} → {_state_after.get('playerX'):.0f} (hooks)"})
                elif canvas_moved:
                    tests_passes.append({"nom": "Joueur réactif", "score": 1.0,
                                         "commentaire": "Canvas change (hooks non conclusifs — fallback visuel)"})
                else:
                    tests_echoues.append({"nom": "Joueur réactif", "score": 0,
                                          "commentaire": f"playerX immobile après inputs (hooks: playerX={_state_after.get('playerX')})"})

                if _score_changed:
                    tests_passes.append({"nom": "Score s'incrémente", "score": 2.0,
                                         "commentaire": f"score {_state_before.get('score')} → {_state_after.get('score')} (hooks)"})
                else:
                    tests_echoues.append({"nom": "Score s'incrémente", "score": 0,
                                          "commentaire": f"score inchangé après inputs (hooks: score={_state_after.get('score')})"})
            else:
                # Fallback : player.x direct + canvas diff si hooks absents
                _fallback_comment = " [hooks absents]" if not _hooks_available else " [hooks null — B4]"
                _direct_moved = (_player_x_before >= 0 and _player_x_after >= 0
                                 and abs(_player_x_after - _player_x_before) > 5)
                if _direct_moved:
                    tests_passes.append({"nom": "Joueur réactif", "score": 1.5,
                                         "commentaire": f"player.x : {_player_x_before:.0f} → {_player_x_after:.0f} (direct){_fallback_comment}"})
                elif canvas_moved and not _hooks_penalty and _player_x_before < 0:
                    # Canvas change mais player.x illisible (variable pas globale) — score partiel
                    tests_passes.append({"nom": "Gameplay réactif", "score": 0.8,
                                         "commentaire": f"Canvas change (player.x non lisible){_fallback_comment}"
                                                        + (f" (score={score_val})" if score_val >= 0 else "")})
                else:
                    _detail = f"player.x avant={_player_x_before:.0f} après={_player_x_after:.0f}" if _player_x_before >= 0 else "player.x non lisible"
                    tests_echoues.append({"nom": "Joueur réactif", "score": 0,
                                          "commentaire": f"Joueur immobile après ArrowRight/Left ({_detail}){_fallback_comment}"})

            # ─── Test 4b2 : Ennemis présents et actifs après démarrage ───────────────
            _enemies_before = -1
            try:
                time.sleep(1.5)  # laisser le temps aux ennemis de spawner
                enemies_count = page.evaluate(
                    "typeof enemies !== 'undefined' ? enemies.length : "
                    "(typeof ENEMIES !== 'undefined' ? ENEMIES.length : -1)"
                )
                _enemies_before = enemies_count
                if enemies_count > 0:
                    tests_passes.append({"nom": "Ennemis présents", "score": 1.0,
                                         "commentaire": f"{enemies_count} ennemi(s) actif(s) dans le jeu"})
                elif enemies_count == 0:
                    tests_echoues.append({"nom": "Ennemis présents", "score": 0,
                                          "commentaire": "Tableau enemies vide après démarrage — spawn cassé"})
                # enemies_count == -1 → variable non globale, on ne pénalise pas
            except Exception:
                pass

            # ─── Test 4b3 : Score progresse (tirs + attente, sans hooks) ─────────────
            # Lire score, tirer 10x, attendre, relire — si score augmente = gameplay fonctionnel
            try:
                _score_before_shoot = page.evaluate("typeof score !== 'undefined' ? Number(score) : -1")
                for _ in range(10):
                    page.keyboard.press("Space")
                    time.sleep(0.1)
                time.sleep(2.0)  # attendre impacts + dégâts
                _score_after_shoot = page.evaluate("typeof score !== 'undefined' ? Number(score) : -1")
                _enemies_after_shoot = page.evaluate(
                    "typeof enemies !== 'undefined' ? enemies.length : -1"
                )
                if _score_before_shoot >= 0 and _score_after_shoot > _score_before_shoot:
                    tests_passes.append({"nom": "Score progresse", "score": 1.5,
                                         "commentaire": f"score {_score_before_shoot:.0f} → {_score_after_shoot:.0f} après tirs"})
                elif _score_before_shoot >= 0:
                    # Score n'a pas bougé — vérifier si ennemis diminuent (peut-être score différé)
                    if _enemies_before > 0 and _enemies_after_shoot >= 0 and _enemies_after_shoot < _enemies_before:
                        tests_passes.append({"nom": "Score progresse", "score": 0.8,
                                             "commentaire": f"Ennemis tués ({_enemies_before}→{_enemies_after_shoot}) mais score inchangé — score non incrémenté"})
                    else:
                        tests_echoues.append({"nom": "Score progresse", "score": 0,
                                              "commentaire": f"Score inchangé après 10 tirs ({_score_before_shoot}) — balles inefficaces ou ennemis intouchables"})
            except Exception:
                pass

            # ─── Test 4c : Interactions souris + absence de crash ─────────────────────
            errors_before_mouse = list(js_errors)
            try:
                if canvas:
                    box = canvas.bounding_box()
                    if box and box["width"] > 0 and box["height"] > 0:
                        cx = box["x"] + box["width"] / 2
                        cy = box["y"] + box["height"] / 2
                        page.mouse.click(cx, cy)
                        time.sleep(0.3)
                        page.mouse.click(box["x"] + box["width"] * 0.25,
                                         box["y"] + box["height"] * 0.25)
                        time.sleep(0.2)
                        page.mouse.click(box["x"] + box["width"] * 0.75,
                                         box["y"] + box["height"] * 0.65)
                        time.sleep(0.2)
            except Exception as e:
                js_errors.append(f"CRASH souris : {e}")

            # Vérifier les erreurs JS apparues PENDANT les interactions (critiques)
            all_critical_now = [
                e for e in js_errors
                if ("undefined" in e.lower() or "referenceerror" in e.lower()
                    or "typeerror" in e.lower() or "is not defined" in e.lower()
                    or "is not a function" in e.lower() or "cannot read" in e.lower())
                and (not is_threejs or not any(n in e.lower() for n in threejs_renderer_noise))
            ]
            new_errors_after_input = [e for e in all_critical_now if e not in critical_errors]

            if input_crash or new_errors_after_input:
                tests_echoues.append({
                    "nom": "Inputs sans crash",
                    "score": 0,
                    "commentaire": f"Crash ou erreur JS : {(new_errors_after_input or ['crash'])[:2]}"
                })
                for err in new_errors_after_input:
                    js_errors.append(f"[POST-INTERACTION] {err}")
            else:
                tests_passes.append({"nom": "Inputs sans crash", "score": 1.0,
                                     "commentaire": "Aucune erreur JS pendant les interactions clavier+souris"})

            # Test 5 : localStorage disponible
            try:
                has_local_storage = page.evaluate("typeof localStorage !== 'undefined'")
                if has_local_storage:
                    tests_passes.append({"nom": "localStorage", "score": 0.5, "commentaire": "localStorage disponible"})
            except Exception:
                pass

            # Test 6 : Stabilité globale — aucune nouvelle erreur critique post-interactions
            final_critical = [
                e for e in js_errors
                if ("undefined" in e.lower() or "referenceerror" in e.lower()
                    or "typeerror" in e.lower() or "is not defined" in e.lower()
                    or "is not a function" in e.lower() or "cannot read" in e.lower())
                and (not is_threejs or not any(n in e.lower() for n in threejs_renderer_noise))
            ]
            if len(final_critical) == errors_count_at_load:
                tests_passes.append({"nom": "Stabilité", "score": 1.5, "commentaire": "Aucune nouvelle erreur critique après interactions"})
            else:
                new_count = len(final_critical) - errors_count_at_load
                tests_echoues.append({"nom": "Stabilité", "score": 0,
                                      "commentaire": f"{new_count} nouvelle(s) erreur(s) critique(s) après interactions"})

            # C2 — Test player.hp accessible et positif
            try:
                _hp_val = page.evaluate("""() => {
                    if (typeof player !== 'undefined' && player !== null) {
                        if (typeof player.hp === 'number') return player.hp;
                        if (typeof player.lives === 'number') return player.lives;
                        if (typeof player.health === 'number') return player.health;
                    }
                    if (typeof lives !== 'undefined' && typeof lives === 'number') return lives;
                    return -1;
                }""")
                if _hp_val > 0:
                    tests_passes.append({"nom": "Santé joueur", "score": 0.5,
                                         "commentaire": f"player hp/lives = {_hp_val} (positif et accessible)"})
                elif _hp_val == 0:
                    tests_echoues.append({"nom": "Santé joueur", "score": 0,
                                          "commentaire": "player.hp = 0 dès le début (game over immédiat ou init incorrecte)"})
            except Exception:
                pass

            # C5 — Test HUD : score visible dans la zone haute du canvas
            try:
                _hud_ok = page.evaluate("""() => {
                    const canvas = document.querySelector('canvas');
                    if (!canvas || canvas.width === 0) return -1;
                    try {
                        const ctx = canvas.getContext('2d');
                        if (!ctx) return -1;
                        // Échantillonner la zone HUD (top 10% du canvas)
                        const hudH = Math.max(1, Math.floor(canvas.height * 0.10));
                        const d = ctx.getImageData(0, 0, canvas.width, hudH).data;
                        let bright = 0;
                        for (let i = 0; i < d.length; i += 4) {
                            if (d[i] > 30 || d[i+1] > 30 || d[i+2] > 30) bright++;
                        }
                        return bright / (d.length / 4);
                    } catch(e) { return -1; }
                }""")
                if _hud_ok > 0.01:
                    tests_passes.append({"nom": "HUD visible", "score": 0.5,
                                         "commentaire": f"Zone HUD (top 10%) non vide ({_hud_ok*100:.0f}% pixels)"})
                elif _hud_ok >= 0:
                    tests_echoues.append({"nom": "HUD visible", "score": 0,
                                          "commentaire": "Zone HUD noire — score/vies probablement non affichés"})
            except Exception:
                pass

            browser.close()

    finally:
        os.unlink(tmp_path)

    # Calcul du score (normalisé sur max_score ajusté)
    # max_score : 1.5 (canvas) + 1.5 (JS load) + 2.5 (visible) + 2.0 (loop) + 1.0 (FPS)
    #           + 1.5 (démarrage jeu) + 1.5 (joueur réactif) + 2.0 (score s'incrémente)
    #           + 1.5 (score progresse) + 1.0 (ennemis présents)
    #           + 1.0 (inputs sans crash) + 0.5 (localStorage) + 1.5 (stabilité)
    #           + 0.5 (santé joueur C2) + 0.5 (HUD visible C5) = 18.5 avec hooks / 16.5 sans
    score_brut = sum(t["score"] for t in tests_passes)
    webgl_partial = any("score partiel" in t.get("commentaire", "") for t in tests_passes if t.get("nom") == "Contenu visible")
    _with_hooks_tests = any(t.get("nom") in ("Joueur réactif", "Score s'incrémente") for t in tests_passes + tests_echoues)
    _has_score_progresse = any(t.get("nom") == "Score progresse" for t in tests_passes + tests_echoues)
    _has_enemies_test = any(t.get("nom") == "Ennemis présents" for t in tests_passes + tests_echoues)
    if webgl_partial:
        max_score = 13.0 if _with_hooks_tests else 12.5
    else:
        max_score = 17.0 if _with_hooks_tests else 15.0
    if _has_score_progresse:
        max_score += 1.5
    if _has_enemies_test:
        max_score += 1.0
    ev.score = min(10.0, (score_brut / max_score) * 10)

    # Pénalité dure : écran noir = score plafonné à 3.0 quel que soit le reste
    ecran_noir = any("ÉCRAN NOIR" in t["commentaire"] for t in tests_echoues)
    if ecran_noir:
        ev.score = min(ev.score, 3.0)

    # Pénalité dure : crash lors des interactions = score plafonné à 4.0
    crash_interaction = any("Crash ou erreur" in t.get("commentaire", "") for t in tests_echoues if t.get("nom") == "Inputs sans crash")
    if crash_interaction:
        ev.score = min(ev.score, 4.0)

    # Pénalité dure : erreurs JS au chargement + joueur immobile = jeu injouable → cap 4.5
    _player_immobile = any(
        t.get("nom") == "Joueur réactif" and t.get("score", 1) == 0
        for t in tests_echoues
    )
    if errors_count_at_load > 0 and _player_immobile:
        ev.score = min(ev.score, 4.5)
        ev.issues.append({
            "severite": "critique",
            "description": f"INJOUABLE : {errors_count_at_load} erreur(s) JS au chargement + joueur immobile après inputs",
            "suggestion": "Corriger les erreurs JavaScript — le joueur ne peut pas interagir avec le jeu"
        })

    ev.criteres = tests_passes + tests_echoues

    # B3 : Exporter erreurs JS brutes comme critère dédié (Patcher recevra les stack traces)
    if js_errors:
        ev.criteres.append({
            "nom": "Erreurs JS brutes",
            "score": 0,
            "commentaire": " | ".join(js_errors[:5])
        })

    ev.issues = [
        {
            "severite": "critique" if any(k in t["nom"] for k in ["JS", "loop", "Contenu", "Canvas"]) else "majeur",
            "description": t["commentaire"],
            "suggestion": "Corriger le problème identifié"
        }
        for t in tests_echoues
    ]

    if js_errors:
        ev.issues.append({
            "severite": "critique",
            "description": f"Erreurs JS détectées : {js_errors[:3]}",
            "suggestion": "Déboguer les erreurs JavaScript"
        })

    # B4 : pénalité dure si hooks retournent tout null
    if _hooks_penalty:
        ev.score = min(ev.score if hasattr(ev, 'score') else 10.0, 3.5)
        ev.issues.append({
            "severite": "critique",
            "description": "B4: __ARCADE_TEST__ retourne uniquement des null — architecture de jeu probablement cassée",
            "suggestion": "Vérifier que score, gameState et player sont correctement déclarés globalement"
        })

    _hooks_status = "hooks OK" if _hooks_available else "sans hooks"
    ev.points_forts = [t["commentaire"] for t in tests_passes]
    ev.commentaire_global = f"{len(tests_passes)}/{len(tests_passes) + len(tests_echoues)} tests réussis [{_hooks_status}]"
    if js_errors:
        # Inclure les 3 premières erreurs JS dans le commentaire global pour le patcher
        _err_summary = " | ".join(js_errors[:3])
        ev.commentaire_global += f" | ERREURS JS: {_err_summary[:200]}"
        phase4_log.warning(f"{len(js_errors)} erreur(s) JS : {js_errors[0]}")
    if _player_immobile:
        ev.commentaire_global += " | JOUEUR IMMOBILE"

    return ev


def _run_simulated(code: str) -> EvaluationResult:
    """Analyse statique du code quand Playwright n'est pas disponible."""
    ev = EvaluationResult(agent_name="Exécuteur (simulé)")
    score = 0.0
    criteres = []
    issues = []

    is_threejs = "three.min.js" in code or "THREE." in code
    code_lower = code.lower()

    # (keyword, label, poids, severite_si_absent)
    # severite: "critique" = jeu probablement non fonctionnel, "majeur" = problème sérieux, "mineur" = manque
    if is_threejs:
        checks = [
            ("requestAnimationFrame",         "Game loop RAF",            2.5, "critique"),
            ("DOMContentLoaded",              "DOMContentLoaded wrap",    1.5, "critique"),
            ("WebGLRenderer",                 "Renderer WebGL",           2.0, "critique"),
            ("AmbientLight",                  "Éclairage ambient",        1.0, "majeur"),
            ("DirectionalLight",              "Éclairage directionnel",   0.5, "majeur"),
            ("THREE.Clock",                   "Delta time (Clock)",       1.0, "majeur"),
            ("scene.background",              "Fond scène défini",        0.5, "majeur"),
            ("document.body.appendChild",     "Renderer ajouté au DOM",  1.0, "critique"),
            ("addEventListener",              "Event listeners",          1.0, "majeur"),
            ("gameState",                     "Machine à états",          1.0, "majeur"),
            ("localStorage",                  "localStorage",             0.5, "mineur"),
            ("scene.remove",                  "Cleanup entités",          0.5, "majeur"),
        ]
    else:
        checks = [
            ("requestAnimationFrame",   "Game loop RAF",          2.5, "critique"),
            ("DOMContentLoaded",        "DOMContentLoaded wrap",  1.5, "critique"),
            ("<canvas",                 "Canvas présent",         1.5, "critique"),
            ("ctx.clearRect",           "Nettoyage canvas",       1.0, "majeur"),
            ("deltaTime",               "Delta time",             1.0, "majeur"),
            ("addEventListener",        "Event listeners",        1.0, "majeur"),
            ("gameState",               "Machine à états",        0.5, "majeur"),
            ("collision",               "Détection collision",    0.5, "majeur"),
            ("localStorage",            "localStorage",           0.5, "mineur"),
            ("gameover",                "Game over / restart",    0.5, "mineur"),
        ]

    for keyword, nom, poids, severite in checks:
        # Recherche case-insensitive pour les chaînes non-techniques
        if keyword.startswith("THREE.") or keyword.startswith("<"):
            present = keyword in code
        else:
            present = keyword.lower() in code_lower

        score += poids if present else 0
        criteres.append({
            "nom": nom,
            "score_obtenu": poids if present else 0,
            "score_max": poids,
            "present": present,
            "commentaire": "✓ Présent" if present else f"✗ Absent ({severite})"
        })
        if not present:
            issues.append({
                "severite": severite,
                "description": f"{nom} non trouvé dans le code",
                "suggestion": "Ajouter cette fonctionnalité"
            })

    max_possible = sum(c[2] for c in checks)
    ev.score = min(10.0, (score / max_possible) * 10)

    # Pénalité si critères critiques absents
    critiques_absents = sum(1 for c in checks if c[3] == "critique" and c[0].lower() not in code_lower)
    if critiques_absents >= 2:
        ev.score = min(ev.score, 4.0)  # jeu probablement non fonctionnel

    ev.criteres = criteres
    ev.issues = issues
    ev.points_forts = [c["nom"] for c in criteres if c["present"]]
    ev.commentaire_global = (
        f"Analyse statique (Playwright non disponible) — "
        f"{sum(1 for c in criteres if c['present'])}/{len(criteres)} critères présents — "
        f"score: {ev.score:.1f}/10"
    )
    return ev

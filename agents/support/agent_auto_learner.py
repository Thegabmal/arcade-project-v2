"""
Agent Auto-Learner — Post-génération
Analyse le HTML final + les logs pour identifier :
- Les bugs résiduels non couverts par code_validator
- Les nouvelles variables non déclarées (candidats COMMON_VARS)
- Les patterns récurrents à traiter

Écrit dans auto_learnings.json sans jamais modifier code_validator.py directement.
La prochaine session avec Claude incorporera les learnings manuellement.
"""

import json
import re
import os
from datetime import datetime
from logger import coordinateur_log

LEARNINGS_FILE  = "auto_learnings.json"
LEARNED_VARS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "learned_vars.json")

# Seuil : nb de jeux distincts pour promouvoir une var dans learned_vars.json
# et la rendre disponible dans code_validator au run suivant
PROMOTE_THRESHOLD = 2

# ─────────────────────────────────────────────
# Fixes déjà couverts (ne pas re-signaler)
# ─────────────────────────────────────────────
ALREADY_COVERED = {
    "markdown_fence",
    "keyup_missing_k",
    "mouse_missing_r",
    "localStorage_no_parse",
    "localStorage_data_alias",
    "loop_missing_var_init",
    "double_declaration",
    "trailing_comma",
    "eval_devpatch",
    "inputstate_missing_props",
    "canvas_missing",
    "canvas_id_mismatch",
    "unclosed_brace",
    "dt_missing_param",         # couvert par agent_diagnosticien
    "canvas_listener_before_dom",  # couvert par _fix_canvas_listeners_outside_domready
}

# Variables déjà dans COMMON_VARS (ne pas re-signaler)
KNOWN_COMMON_VARS = {
    "hovered", "hit", "found", "gameTime", "bossActive", "bossSpawned",
    "waveNumber", "combo", "comboTimer", "cost", "stellarCrystals", "gold",
    "coins", "gems", "currentLevel", "upgrade", "moveX", "moveY", "angle",
    "dx", "dy", "dist", "scaleX", "scaleY", "result", "data", "buff",
    "choice", "numRooms", "POWERUP_DEFS", "healTimer", "roomHistory",
    "isSolid", "timeInRunMinutes", "dmg", "bw", "bh", "by", "cx", "cy",
    "lastTime",
    # Ajoutés suite à l'analyse des 19 premiers jeux
    "attackCooldown", "attackTimer", "attackDamage", "atkCooldown", "atkTimer",
    "cooldown", "defense", "baseDamage", "baseSpeed",
    "aiState", "aiTimer", "aiTarget", "aoeTimer", "bleedTimer",
    "currentPhase", "alpha", "duration", "charIndex",
}

# Globals JS standards
JS_GLOBALS = {
    "window", "document", "console", "Math", "Date", "JSON", "Array",
    "Object", "String", "Number", "Boolean", "parseInt", "parseFloat",
    "isNaN", "isFinite", "setTimeout", "setInterval", "clearTimeout",
    "clearInterval", "requestAnimationFrame", "cancelAnimationFrame",
    "AudioContext", "localStorage", "sessionStorage", "navigator",
    "performance", "screen", "alert", "confirm", "prompt", "fetch",
    "XMLHttpRequest", "Error", "TypeError", "RangeError", "Promise",
    "Symbol", "Map", "Set", "WeakMap", "WeakSet", "Proxy", "Reflect",
    "undefined", "null", "true", "false", "NaN", "Infinity",
    "THREE", "PIXI",
    # Globals jeux standards
    "canvas", "ctx", "offscreen", "gctx", "player", "enemies", "boss",
    "keys", "mouse", "items", "map", "rooms", "particles", "projectiles",
    "bullets", "score", "gameState", "camera", "world", "level", "wave",
    "input", "sfx", "GW", "GH", "W", "H", "TILE", "SCALE",
    # Vars courtes ignorées
    "i", "j", "k", "x", "y", "z", "n", "m", "t", "v", "p", "e", "r",
    "dt", "el", "fn", "cb", "id", "to",
}


def _extract_script(html: str) -> str:
    """Extrait le script JS principal du HTML."""
    matches = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
    if not matches:
        matches = re.findall(r'<script(?:\s[^>]*)?>(.+)</script>', html, re.DOTALL | re.IGNORECASE)
    return max(matches, key=len) if matches else ""


def _check_undeclared_vars(script: str) -> list[dict]:
    """
    Trouve les variables utilisées dans if(x) / while(x) sans être déclarées.
    Retourne les candidats pour COMMON_VARS.
    """
    findings = []

    all_declared = set(re.findall(r'\b(?:const|let|var)\s+(\w+)', script))
    all_declared |= set(re.findall(r'\bfunction\s+(\w+)\s*\(', script))
    for params in re.findall(r'function\s*\w*\s*\(([^)]+)\)', script):
        all_declared |= {p.strip().lstrip('...') for p in params.split(',') if p.strip()}
    all_declared |= set(re.findall(r'\bfor\s*\(\s*(?:const|let|var)\s+(\w+)', script))
    # Multi-declarator
    for m in re.finditer(r'\b(?:const|let|var)\s+\w+[^;,\n]*(?:,\s*(\w+)[^;,\n]*)+', script):
        for extra in re.findall(r',\s*(\w+)\s*(?:=|,|;|\n|$)', m.group(0)):
            all_declared.add(extra)

    # Variables utilisées dans des conditions
    used_in_conditions = set(re.findall(r'\bif\s*\(\s*!?(\w+)\b', script))
    used_in_conditions |= set(re.findall(r'\bwhile\s*\(\s*!?(\w+)\b', script))

    # Usages généraux (pour détecter les vars utilisées mais pas déclarées)
    # On cherche les patterns X.something ou X += ou X -= utilisés sans déclaration
    used_with_dot = set(re.findall(r'\b([a-z][a-zA-Z0-9_]{3,})\s*\.', script))
    used_assigned = set(re.findall(r'\b([a-z][a-zA-Z0-9_]{3,})\s*[+\-*]?=(?!=)', script))

    candidates = (used_in_conditions | used_with_dot | used_assigned) - all_declared

    for varname in sorted(candidates):
        if (len(varname) >= 4
                and varname not in KNOWN_COMMON_VARS
                and varname not in JS_GLOBALS
                and not varname[0].isupper()
                and not varname.startswith('_')
                and re.search(rf'\b{re.escape(varname)}\b', script)):
            # Compter les occurrences
            count = len(re.findall(rf'\b{re.escape(varname)}\b', script))
            if count >= 3:  # au moins 3 usages pour être significatif
                findings.append({
                    "varname": varname,
                    "occurrences": count,
                    "suggested_default": _guess_default(varname, script),
                })

    return findings[:15]  # cap à 15 candidats


def _guess_default(varname: str, script: str) -> str:
    """Devine la valeur par défaut d'une variable selon son nom/usage."""
    vl = varname.lower()
    if any(k in vl for k in ('timer', 'time', 'delay', 'cooldown', 'tick', 'elapsed')):
        return '0'
    if any(k in vl for k in ('active', 'visible', 'enabled', 'open', 'show', 'dead', 'alive', 'paused')):
        return 'false'
    if any(k in vl for k in ('count', 'num', 'total', 'score', 'level', 'wave', 'hp', 'health', 'speed', 'dmg', 'damage', 'rate')):
        return '0'
    if any(k in vl for k in ('list', 'items', 'array', 'queue', 'stack', 'pool')):
        return '[]'
    if any(k in vl for k in ('map', 'dict', 'table', 'config', 'data', 'state', 'info')):
        return '{}'
    # Vérifier si utilisé dans une comparaison booléenne
    if re.search(rf'\b{re.escape(varname)}\s*===\s*(?:true|false)\b', script):
        return 'false'
    if re.search(rf'\b{re.escape(varname)}\s*[+\-*/]=', script):
        return '0'
    return 'null'


def _check_missing_functions(script: str) -> list[dict]:
    """Trouve les fonctions appelées mais jamais définies."""
    defined = set(re.findall(r'function\s+(\w+)\s*\(', script))
    defined |= set(re.findall(r'\b(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>)', script))

    # Appels de fonctions (nom suivi de '(')
    called = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\s*\(', script))

    missing = []
    ignore = JS_GLOBALS | KNOWN_COMMON_VARS | {
        'if', 'for', 'while', 'switch', 'catch', 'return', 'typeof',
        'instanceof', 'new', 'delete', 'void', 'throw', 'case', 'default',
        'class', 'extends', 'super', 'import', 'export', 'async', 'await',
        'Math', 'JSON', 'Object', 'Array', 'String', 'Number', 'Boolean',
        'parseInt', 'parseFloat', 'setTimeout', 'setInterval',
        'requestAnimationFrame', 'cancelAnimationFrame',
        'addEventListener', 'removeEventListener', 'getElementById',
        'querySelector', 'querySelectorAll', 'getElementsByTagName',
        'getBoundingClientRect', 'appendChild', 'removeChild',
        'createElement', 'createElementNS', 'setAttribute', 'getAttribute',
        'getContext', 'clearRect', 'fillRect', 'strokeRect', 'beginPath',
        'moveTo', 'lineTo', 'arc', 'fill', 'stroke', 'save', 'restore',
        'translate', 'rotate', 'scale', 'drawImage', 'fillText', 'strokeText',
        'measureText', 'createLinearGradient', 'createRadialGradient',
        'addColorStop', 'getImageData', 'putImageData', 'createImageData',
        'toDataURL', 'play', 'pause', 'start', 'stop', 'connect', 'disconnect',
        'setValueAtTime', 'exponentialRampToValueAtTime', 'linearRampToValueAtTime',
        'log', 'warn', 'error', 'info', 'debug', 'max', 'min', 'abs', 'floor',
        'ceil', 'round', 'sqrt', 'pow', 'sin', 'cos', 'tan', 'atan2', 'random',
        'sign', 'trunc', 'hypot', 'PI', 'stringify', 'parse', 'keys', 'values',
        'entries', 'assign', 'freeze', 'create', 'defineProperty', 'hasOwnProperty',
        'push', 'pop', 'shift', 'unshift', 'splice', 'slice', 'indexOf', 'findIndex',
        'find', 'filter', 'map', 'reduce', 'forEach', 'some', 'every', 'includes',
        'join', 'split', 'replace', 'trim', 'toLowerCase', 'toUpperCase',
        'toString', 'valueOf', 'toFixed', 'isNaN', 'isFinite', 'bind', 'call', 'apply',
        'then', 'catch', 'finally', 'resolve', 'reject', 'all', 'race',
        'set', 'get', 'has', 'delete', 'clear', 'size', 'add',
        'setItem', 'getItem', 'removeItem',
        'requestPointerLock', 'exitPointerLock',
        # CSS / canvas color functions
        'rgba', 'rgb', 'hsl', 'hsla',
        # String/Array methods (appelés comme méthodes, pas fonctions libres)
        'startsWith', 'endsWith', 'padStart', 'padEnd', 'repeat', 'at',
        'flatMap', 'flat', 'from', 'of', 'isArray', 'fill', 'copyWithin',
        'sort', 'reverse', 'concat', 'toSorted', 'toReversed',
        'substring', 'substr', 'trimEnd', 'trimStart', 'trimLeft', 'trimRight',
        'charCodeAt', 'codePointAt', 'normalize', 'localeCompare',
        # Date / performance
        'now', 'getTime', 'getFullYear', 'getMonth', 'getDate',
        # Canvas spécifiques
        'beginPath', 'closePath', 'clip', 'stroke', 'fill', 'save', 'restore',
        'ellipse', 'rect', 'roundRect', 'quadraticCurveTo', 'bezierCurveTo',
        'setLineDash', 'createPattern', 'isPointInPath', 'isPointInStroke',
        # Audio
        'createOscillator', 'createGain', 'createBuffer', 'createBufferSource',
        'createDynamicsCompressor', 'createAnalyser', 'decodeAudioData',
        # DOM
        'preventDefault', 'stopPropagation', 'stopImmediatePropagation',
        'classList', 'style', 'textContent', 'innerHTML', 'innerText',
        # Misc courants
        'effect', 'update', 'draw', 'render', 'init', 'reset', 'spawn',
        'emit', 'trigger', 'fire', 'dispatch',
        # Faux positifs regex
        'function', 'eval',
    }
    for fn in called:
        if fn not in defined and fn not in ignore and not fn[0].isupper():
            count = len(re.findall(rf'\b{re.escape(fn)}\s*\(', script))
            if count >= 2:
                missing.append({"function": fn, "call_count": count})

    return sorted(missing, key=lambda x: -x["call_count"])[:10]


def _check_residual_patterns(script: str) -> list[dict]:
    """Vérifie les patterns résiduels après tous les fixes."""
    findings = []

    # Double RAF
    raf_count = len(re.findall(r'\brequestAnimationFrame\s*\(', script))
    if raf_count >= 3:
        findings.append({
            "type": "double_raf",
            "description": f"requestAnimationFrame appelé {raf_count}× — possible double game loop",
            "severity": "medium",
        })

    # gameState référencé mais switch/if incomplet
    states_set = set(re.findall(r"gameState\s*=\s*['\"]([^'\"]+)['\"]", script))
    states_checked = set(re.findall(r"gameState\s*===?\s*['\"]([^'\"]+)['\"]", script))
    unhandled = states_set - states_checked
    if unhandled:
        findings.append({
            "type": "unhandled_gamestate",
            "description": f"États gameState assignés mais jamais vérifiés : {sorted(unhandled)}",
            "severity": "medium",
        })

    # ctx non initialisé avant usage (utilisé HORS FONCTION avant getContext)
    # Faux positif fréquent si ctx est utilisé dans une fonction définie avant DOMContentLoaded
    ctx_init_pos = min((m.start() for m in re.finditer(r'getContext\s*\(', script)), default=None)
    if ctx_init_pos is not None:
        # Chercher ctx.X en dehors des corps de fonctions (indentation 0 ou dans const/let)
        # Heuristique : ligne qui commence par ctx (pas indentée)
        ctx_global_usage = [m.start() for m in re.finditer(r'^\s{0,2}ctx\s*\.', script, re.MULTILINE)]
        if ctx_global_usage and min(ctx_global_usage) < ctx_init_pos:
            findings.append({
                "type": "ctx_before_init",
                "description": "ctx utilisé au niveau global avant canvas.getContext() — possible undefined",
                "severity": "high",
            })

    # Fonction draw() sans ctx.clearRect ou ctx.fillRect au début
    draw_match = re.search(r'function\s+draw\s*\([^)]*\)\s*\{(.{0,300})', script, re.DOTALL)
    if draw_match:
        draw_body = draw_match.group(1)
        if not re.search(r'ctx\s*\.\s*(?:clearRect|fillRect)\s*\(', draw_body[:200]):
            findings.append({
                "type": "draw_no_clear",
                "description": "draw() ne commence pas par clearRect/fillRect → ghosting ou écran noir",
                "severity": "medium",
            })

    # Listener keydown utilise e.key directement sans toLowerCase (inconsistant)
    keydown_body_match = re.search(
        r"addEventListener\s*\(\s*['\"]keydown['\"]\s*,.*?\{(.{0,500})\}",
        script, re.DOTALL
    )
    if keydown_body_match:
        body = keydown_body_match.group(1)
        has_lower = bool(re.search(r'toLowerCase\(\)', body))
        has_arrowleft = bool(re.search(r"'ArrowLeft'|\"ArrowLeft\"", body))
        if has_arrowleft and not has_lower:
            # Fine — uses raw e.key with capital letters
            pass
        elif has_lower and re.search(r"'ArrowLeft'|\"ArrowLeft\"", body):
            findings.append({
                "type": "key_case_mismatch",
                "description": "keydown mélange toLowerCase() et 'ArrowLeft' (capital) — touches non détectées",
                "severity": "high",
            })

    return findings


def run(html: str, score: float, approuve: bool, genre: str, titre: str, logs: str = "") -> dict:
    """
    Analyse le HTML généré et les logs post-génération.
    Écrit les findings dans auto_learnings.json.
    Retourne le résumé des findings.
    """
    if not html or len(html) < 1000:
        return {}

    script = _extract_script(html)
    if not script or len(script) < 500:
        return {}

    # Analyses
    new_vars = _check_undeclared_vars(script)
    missing_fns = _check_missing_functions(script)
    residual = _check_residual_patterns(script)

    # Résumé
    findings = {
        "timestamp": datetime.now().isoformat(),
        "titre": titre,
        "genre": genre,
        "score": round(score, 2),
        "approuve": approuve,
        "html_size": len(html),
        "new_common_vars_candidates": new_vars,
        "missing_functions": missing_fns,
        "residual_patterns": residual,
        "has_new_findings": bool(new_vars or missing_fns or residual),
    }

    # Écriture dans auto_learnings.json
    learnings = []
    if os.path.exists(LEARNINGS_FILE):
        try:
            with open(LEARNINGS_FILE, encoding="utf-8") as f:
                learnings = json.load(f)
        except Exception:
            learnings = []

    learnings.append(findings)

    # Garder max 50 entrées
    if len(learnings) > 50:
        learnings = learnings[-50:]

    with open(LEARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(learnings, f, ensure_ascii=False, indent=2)

    # ── Mise à jour incrémentale de learned_vars.json ──────────────────────────
    # Compte combien de jeux distincts ont signalé chaque var candidate.
    # Quand une var atteint PROMOTE_THRESHOLD jeux distincts, elle entre dans
    # learned_vars.json → code_validator.py la charge au run suivant.
    if new_vars:
        try:
            learned: dict = {}
            lv_path = os.path.normpath(LEARNED_VARS_FILE)
            if os.path.exists(lv_path):
                with open(lv_path, "r", encoding="utf-8") as lf:
                    learned = json.load(lf)

            promoted = []
            for candidate in new_vars:
                varname = candidate["varname"]
                init    = candidate["suggested_default"]
                entry   = learned.setdefault(varname, {"games": [], "count": 0, "init": init})
                if titre not in entry["games"]:
                    entry["games"].append(titre)
                    entry["count"] = len(entry["games"])
                if entry["count"] >= PROMOTE_THRESHOLD and varname not in KNOWN_COMMON_VARS:
                    promoted.append(varname)

            with open(lv_path, "w", encoding="utf-8") as lf:
                json.dump(learned, lf, ensure_ascii=False, indent=2)

            if promoted:
                coordinateur_log.info(
                    f"Auto-learner : {len(promoted)} var(s) promue(s) dans learned_vars.json"
                    f" (seuil {PROMOTE_THRESHOLD} jeux) : {promoted}"
                )
        except Exception as _e:
            coordinateur_log.warning(f"Auto-learner : échec mise à jour learned_vars.json : {_e}")

    # Log dans la pipeline
    n_new = len(new_vars) + len(missing_fns) + len(residual)
    if n_new:
        coordinateur_log.info(
            f"Auto-learner : {n_new} finding(s) enregistré(s) → auto_learnings.json"
        )
        if new_vars:
            names = [v["varname"] for v in new_vars[:5]]
            coordinateur_log.info(f"  Nouvelles vars candidates COMMON_VARS : {names}")
        if missing_fns:
            names = [f["function"] for f in missing_fns[:3]]
            coordinateur_log.info(f"  Fonctions manquantes : {names}")
        if residual:
            for r in residual[:2]:
                coordinateur_log.info(f"  Pattern résiduel [{r['severity']}] : {r['description'][:80]}")
    else:
        coordinateur_log.info("Auto-learner : aucun nouveau pattern détecté — pipeline optimale pour ce jeu")

    return findings

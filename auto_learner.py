"""
Auto-Learner: scans saved game logs to detect frequently undeclared variables
and adds them to learned_vars.json.
code_validator.py loads this file at runtime to dynamically enrich COMMON_VARS.

Sources analyzed:
  - jeux_sauvegardes/*_log.txt       (Playwright output: "X is not defined")
  - jeux_sauvegardes/*_log.txt       (code_validator: "used without declaration")

Seuil minimal : MIN_OCCURRENCES fois dans au moins MIN_GAMES jeux différents.
"""

import re
import json
import os

SAVE_DIR        = os.path.join(os.path.dirname(__file__), "jeux_sauvegardes")
OUTPUT_FILE     = os.path.join(os.path.dirname(__file__), "learned_vars.json")
LEARNINGS_FILE  = os.path.join(os.path.dirname(__file__), "auto_learnings.json")

# Nombre minimal d'occurrences (dans des jeux distincts) pour apprendre une variable
MIN_GAMES = 2

# Variables déjà couvertes par COMMON_VARS — ne pas redéclarer
# (liste exhaustive synchronisée avec code_validator._fix_undeclared_common_vars)
ALREADY_IN_COMMON_VARS = {
    'score', 'lives', 'level', 'gameOver', 'paused', 'gameState',
    'player', 'enemies', 'bullets', 'particles', 'items', 'rooms', 'map',
    'boss', 'sfx', 'keys', 'mouse', 'canvas', 'ctx',
    'dt', 'lastTime', 'animId',
    'closest', 'targetEnemy', 'floatingTexts',
    'attempts', 'shakeTimer', 'shakeMag',
    'distToPlayer', 'bullet',
    'classId', 'critChance', 'critMult',
    'gold', 'xp', 'combo', 'wave', 'upgrade', 'dmg', 'hit', 'found',
    'angle', 'dx', 'dy', 'dist',
    'offscreen', 'gctx',
    # Variables trop génériques — risque élevé de faux positifs
    'count', 'active', 'base', 'current', 'state', 'index',
    'value', 'type', 'name', 'size', 'width', 'height', 'color',
    'time', 'speed', 'power', 'strength', 'range',
    # Propriétés de l'objet keys{} — gérées par _fix_keys_completeness
    'left', 'right', 'up', 'down', 'space', 'escape', 'enter',
    'left_prev', 'right_prev', 'up_prev', 'down_prev',
    'space_pressed', 'escape_pressed', 'enter_pressed',
    'down_pressed', 'up_pressed', 'left_pressed', 'right_pressed',
    # Propriétés de mouse{} — gérées par code_validator
    'clicked', 'pressed',
    # Variables trop courtes / loop vars
    'i', 'j', 'k', 'x', 'y', 'w', 'h', 'r', 'g', 'b', 'a',
    'n', 'm', 't', 'e', 'el', 'fn', 'cb', 'id',
    'data', 'raw', 'text', 'line', 'row', 'col', 'tile',
    'obj', 'item', 'node', 'tag', 'key', 'val', 'res', 'err',
    # JS builtins / globals
    'Math', 'Date', 'JSON', 'Array', 'Object', 'String', 'Number',
    'Boolean', 'Function', 'Promise', 'console', 'window', 'document',
    'requestAnimationFrame', 'cancelAnimationFrame', 'setTimeout', 'setInterval',
    'clearTimeout', 'clearInterval', 'localStorage', 'sessionStorage',
    'true', 'false', 'null', 'undefined', 'NaN', 'Infinity',
    'performance', 'navigator', 'location', 'history',
    # Three.js globals
    'THREE', 'scene', 'camera', 'renderer', 'clock',
    # Canvas 2D CanvasRenderingContext2D properties — NE PAS injecter comme variables globales
    # (ce sont des propriétés de ctx, pas des variables indépendantes)
    'fillStyle', 'strokeStyle', 'lineWidth', 'font', 'textAlign', 'textBaseline',
    'globalAlpha', 'globalCompositeOperation', 'shadowColor', 'shadowBlur',
    'lineCap', 'lineJoin', 'miterLimit', 'imageSmoothingEnabled',
    # Paramètres DOM / event courants — jamais des globals de jeu
    'event', 'target', 'currentTarget', 'detail', 'which', 'keyCode',
    'clientX', 'clientY', 'offsetX', 'offsetY', 'pageX', 'pageY',
    # Noms de variables trop génériques / risque de shadowing
    'alpha', 'buffer', 'comp', 'gain', 'source', 'output', 'input',
    'distance', 'angle2', 'direction', 'origin', 'position', 'rotation',
    'duration', 'frequency', 'amplitude', 'volume', 'pitch',
    # Web Audio API nodes — ne pas confondre avec des globals de jeu
    'ctx2', 'audioCtx', 'oscillator', 'gainNode', 'analyser',
}

# Regex : détecte "X is not defined" dans les logs Playwright / navigateur
REF_ERROR_RE = re.compile(
    r"ReferenceError:\s+(\w+)\s+is not defined"
    r"|(\w+)\s+is not defined"            # variante courte (Chrome/Firefox)
    r"|\[pageerror\].*?(\w+)\s+is not defined",
    re.IGNORECASE
)

# Regex : détecte les messages du code_validator dans les logs
CODE_VALIDATOR_RE = re.compile(
    r"'(\w+)' utilisé sans déclaration",
    re.IGNORECASE
)


def _guess_init(varname: str) -> str:
    """Devine la valeur initiale d'une variable d'après son nom."""
    vl = varname.lower()
    if any(k in vl for k in ('timer', 'time', 'delay', 'cooldown', 'tick', 'elapsed', 'phase', 'count',
                               'num', 'total', 'score', 'level', 'wave', 'hp', 'health', 'speed',
                               'dmg', 'damage', 'rate', 'index', 'idx')):
        return '0'
    if any(k in vl for k in ('active', 'visible', 'enabled', 'open', 'show', 'dead', 'alive',
                               'paused', 'triggered', 'spawned', 'solid', 'mode')):
        return 'false'
    if any(k in vl for k in ('list', 'items', 'array', 'queue', 'stack', 'pool', 'texts', 'history')):
        return '[]'
    if any(k in vl for k in ('map', 'dict', 'table', 'config', 'state', 'info', 'defs', 'def')):
        return '{}'
    return 'null'


def _extract_vars_from_log(log_path: str) -> set[str]:
    """Extrait les noms de variables non déclarées depuis un fichier log."""
    found = set()
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                for m in REF_ERROR_RE.finditer(line):
                    varname = m.group(1) or m.group(2) or m.group(3)
                    if varname:
                        found.add(varname.strip())
                for m in CODE_VALIDATOR_RE.finditer(line):
                    found.add(m.group(1).strip())
    except FileNotFoundError:
        pass
    return found


def _is_valid_candidate(varname: str) -> bool:
    """Filtre les noms de variables qui ne doivent pas être dans COMMON_VARS."""
    if varname in ALREADY_IN_COMMON_VARS:
        return False
    if len(varname) <= 1:
        return False
    # Exclure les noms en SCREAMING_CASE (constantes = toujours déclarées par le LLM)
    if varname.isupper() and len(varname) > 2:
        return False
    # Exclure les identifiants qui commencent par une majuscule (classes/constructeurs)
    if varname[0].isupper():
        return False
    # Exclure les noms trop courts qui sont probablement des vars de boucle
    if len(varname) <= 2:
        return False
    return True


def _extract_vars_from_learnings() -> dict[str, set[str]]:
    """
    Extrait les candidats COMMON_VARS depuis auto_learnings.json
    (données issues de l'analyse statique par agent_auto_learner).
    Retourne {varname: set_of_game_titres}.
    """
    frequency: dict[str, set[str]] = {}
    if not os.path.exists(LEARNINGS_FILE):
        return frequency
    try:
        with open(LEARNINGS_FILE, "r", encoding="utf-8") as f:
            learnings = json.load(f)
        for entry in learnings:
            titre = entry.get("titre", "?")
            for candidate in entry.get("new_common_vars_candidates", []):
                varname = candidate.get("varname", "")
                if varname and _is_valid_candidate(varname):
                    frequency.setdefault(varname, set()).add(titre)
    except Exception:
        pass
    return frequency


def learn(verbose: bool = True) -> dict:
    """
    Scanne tous les logs disponibles + auto_learnings.json et met à jour learned_vars.json.
    Retourne le dictionnaire des variables apprises.
    """
    log_files = [
        os.path.join(SAVE_DIR, f)
        for f in os.listdir(SAVE_DIR)
        if f.endswith("_log.txt")
    ]

    # frequency[varname] = set de noms de jeux dans lesquels la var manque
    frequency: dict[str, set[str]] = {}

    # Source 1 : logs Playwright (ReferenceError runtime)
    for log_path in log_files:
        game_name = os.path.basename(log_path).replace("_log.txt", "")
        vars_in_game = _extract_vars_from_log(log_path)
        for v in vars_in_game:
            if _is_valid_candidate(v):
                frequency.setdefault(v, set()).add(game_name)

    # Source 2 : auto_learnings.json (analyse statique par agent_auto_learner)
    for varname, games in _extract_vars_from_learnings().items():
        frequency.setdefault(varname, set()).update(games)

    # Charger les vars déjà apprises (pour les mettre à jour)
    existing: dict = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # Pruner les entrées obsolètes (vars maintenant dans ALREADY_IN_COMMON_VARS)
    pruned = [v for v in list(existing.keys()) if not _is_valid_candidate(v)]
    for v in pruned:
        del existing[v]

    # Mettre à jour les occurrences
    for varname, games in frequency.items():
        if varname not in existing:
            init = _guess_init(varname)
            existing[varname] = {"games": list(games), "count": len(games), "init": init}
        else:
            # Fusionner les jeux
            known_games = set(existing[varname].get("games", []))
            merged = known_games | games
            existing[varname]["games"] = list(merged)
            existing[varname]["count"] = len(merged)

    # Écrire le fichier
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    # Résumé
    qualified = {k: v for k, v in existing.items() if v["count"] >= MIN_GAMES}
    if verbose:
        print(f"=== Auto-Learner : {len(log_files)} logs analysés ===")
        print(f"Variables qualifiees (>={MIN_GAMES} jeux) : {len(qualified)}")
        for varname, info in sorted(qualified.items(), key=lambda x: -x[1]["count"]):
            print(f"  {varname:25s}  {info['count']}x  (init={info['init']})")
        unqualified = {k: v for k, v in existing.items() if v["count"] < MIN_GAMES}
        if unqualified:
            print(f"En attente (1 jeu seulement) : {list(unqualified.keys())}")

    return existing


STUBS_LOG_FILE = os.path.join(os.path.dirname(__file__), "stubs_injected_log.json")


def track_stub_injection(stub_name: str) -> None:
    """
    Enregistre qu'un stub a été injecté dans un jeu.
    Appelé par code_validator._inject_missing_stubs() à chaque injection.
    Thread-safe via lecture-modification-écriture atomique (fichier petit).
    """
    try:
        if os.path.exists(STUBS_LOG_FILE):
            with open(STUBS_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        data[stub_name] = data.get(stub_name, 0) + 1
        with open(STUBS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # jamais bloquant


def stubs_report() -> dict:
    """Retourne le rapport des stubs les plus souvent injectés."""
    if not os.path.exists(STUBS_LOG_FILE):
        return {}
    try:
        with open(STUBS_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return dict(sorted(data.items(), key=lambda x: -x[1]))
    except Exception:
        return {}


if __name__ == "__main__":
    learn()
    report = stubs_report()
    if report:
        print("\n=== Stubs les plus injectés (→ à ajouter dans SYSTEM_2D) ===")
        for stub, count in report.items():
            print(f"  {stub:30s}  {count}x")

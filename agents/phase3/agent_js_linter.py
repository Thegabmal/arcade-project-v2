"""
Agent JS Linter — Phase 3.5
Analyse statique du JavaScript généré AVANT l'évaluation complète.

Rôle : détecter les bugs runtime évidents que le code_validator (regex) ne peut pas voir :
  - Variables/fonctions utilisées sans être déclarées
  - Propriétés d'objets inexistantes (ex: ball.speedMultiplier sans déclaration)
  - Fonctions appelées avant d'être définies (hors hoisting)
  - Incohérences dans la state machine (états référencés mais non gérés)
  - Patterns connus cassés (ex: canvas.width dans la boucle RAF sans caching)

Cet agent retourne une liste d'issues CIBLÉES pour le pre_patcher.
Il ne réécrit JAMAIS de code — il diagnostique seulement.
"""

import re
from config import call_gemini_json, with_fallback
from logger import phase3_log
from utils import extract_js_sample

SYSTEM = """Tu es un expert JavaScript spécialisé dans l'analyse statique de code de jeux HTML5.
Tu identifies uniquement les bugs RUNTIME qui empêcheront le jeu de se lancer ou de fonctionner.
Tu ignores complètement le style, la performance, et les bonnes pratiques.

BUGS À CHERCHER (par ordre de dangerosité) :
1. Variable utilisée dans if(X), boucle ou opération arithmétique sans avoir été déclarée (let/const/var) → ReferenceError → écran noir
   Ex: if (closest) attack(); sans let closest = null avant → crash garanti
   Ex: const dist = Math.sqrt(dx * dx + dy * dy); sans const dx = ...; const dy = ...; avant → ReferenceError

2. Constante de clé localStorage non déclarée → ReferenceError → crash au premier save/load
   Ex: localStorage.setItem(SAVE_KEY, JSON.stringify(data)); sans const SAVE_KEY = 'myGame_v1'; → crash garanti
   Ex: localStorage.getItem(STORAGE_KEY); sans const STORAGE_KEY = ... → ReferenceError

3. Résultat de lookup dans un dictionnaire utilisé sans vérification d'existence → TypeError
   Ex: const upgrades = def.upgrades.length; sans const def = TOWER_DEFS[tower.type]; avant → TypeError: Cannot read property 'upgrades' of undefined
   Ex: WAVE_CONFIG[currentWave].enemies.forEach(...); sans vérifier que WAVE_CONFIG[currentWave] existe

4. Fonction utilise `dt` dans son corps mais n'a pas `dt` comme paramètre → NaN partout
   Ex: function updateBullets() { b.x += b.vx * dt; } → dt=undefined

5. Propriété accédée sur un objet mais absente de sa définition
   Ex: ENEMY_DEFS.boss.onPhaseChange() mais onPhaseChange absent de la def boss

6. État gameState comparé (=== 'boss_fight') mais jamais géré dans update() → jeu bloqué
7. localStorage.getItem() sans JSON.parse() → data.property TypeError

EXEMPLES D'ISSUES BIEN FORMULÉES :
- "Variable 'closest' utilisée dans 'if (closest) attack(closest)' mais jamais déclarée — ajouter 'let closest = null;' avant la boucle enemies"
- "Constante 'SAVE_KEY' utilisée dans localStorage.setItem(SAVE_KEY, ...) mais jamais déclarée — ajouter 'const SAVE_KEY = \"myGame_v1\";' en tête de script"
- "Variable 'dx' utilisée dans 'Math.sqrt(dx * dx + dy * dy)' sans être calculée avant — ajouter 'const dx = enemy.x - player.x; const dy = enemy.y - player.y;' avant cette ligne"
- "Résultat de lookup 'def' utilisé via 'def.upgrades' sans vérifier que TOWER_DEFS[tower.type] existe — ajouter 'const def = TOWER_DEFS[tower.type]; if (!def) return;'"
- "Fonction 'updateBullets()' utilise 'dt' dans son corps sans l'avoir en paramètre — changer en 'updateBullets(dt)' et mettre à jour l'appel"
- "BOSS_DEFS.titan.onPhaseChange appelé à la ligne ~80 mais 'onPhaseChange' absent de la définition 'titan'"

Tu réponds UNIQUEMENT en JSON valide."""


def run(html: str) -> list[str]:
    """
    Analyse statique du JS généré.
    Retourne une liste d'issues critiques à corriger (strings décrivant précisément le problème).
    Retourne [] si aucun problème détecté ou si l'analyse échoue.
    """
    if not html or len(html) < 500:
        return []

    # Extraire le JS — deux échantillons :
    # - grand (28k) pour les checks programmatiques (regex, pas de LLM)
    # - petit (14k) pour l'analyse LLM (éviter les dépassements de tokens)
    # - déclarations collectées depuis le script COMPLET (pas d'échantillon)
    js_full = extract_js_sample(html, 28000)   # Zone 1 = ~9800 chars → couvre les déclarations globales
    js_sample = extract_js_sample(html, 14000)  # Pour LLM seulement
    if not js_full or len(js_full) < 200:
        return []

    # Construire all_declared depuis le script entier (évite les faux positifs pour vars hors Zone 1)
    js_complete = extract_js_sample(html, 10_000_000)  # Pas de troncature → script entier
    declared_from_full = _collect_all_declared(js_complete)

    # Checks programmatiques rapides d'abord (sans LLM) — utilise le grand échantillon
    quick_issues = _quick_checks(js_full, declared_from_full)

    # Analyse LLM uniquement si le code est de taille raisonnable
    llm_issues = []
    if len(js_sample) <= 20000:
        llm_issues = _llm_analysis(js_sample) or []

    all_issues = quick_issues + [i for i in llm_issues if i not in quick_issues]

    if all_issues:
        phase3_log.warning(f"JS Linter : {len(all_issues)} problème(s) détecté(s)")
        for issue in all_issues[:5]:
            phase3_log.info(f"  → {issue}")
    else:
        phase3_log.info("JS Linter : aucun problème critique détecté")

    return all_issues


def _collect_all_declared(js: str) -> set[str]:
    """Collecte toutes les déclarations du script complet (const/let/var/function/params/for)."""
    declared = set(re.findall(r'\b(?:const|let|var)\s+(\w+)', js))
    for m in re.finditer(r'\b(?:const|let|var)\s+\w+[^;,\n]*(?:,\s*(\w+)[^;,\n]*)+', js):
        for extra in re.findall(r',\s*(\w+)\s*(?:=|,|;|\n|$)', m.group(0)):
            declared.add(extra)
    declared |= set(re.findall(r'\bfunction\s+(\w+)\s*\(', js))
    for params in re.findall(r'function\s*\w*\s*\(([^)]+)\)', js):
        declared |= {p.strip().lstrip('...') for p in params.split(',') if p.strip()}
    declared |= set(re.findall(r'\bfor\s*\(\s*(?:const|let|var)\s+(\w+)', js))
    return declared


def _quick_checks(js: str, extra_declared: set | None = None) -> list[str]:
    """
    Vérifications rapides sans LLM.
    Détecte les patterns les plus fréquemment cassés.
    """
    issues = []

    # 1. Propriétés accédées via `.` mais jamais déclarées dans l'objet
    # Exemple : ball.speedMultiplier utilisé sans déclaration
    obj_declarations = {}
    for match in re.finditer(
        r'(?:const|let|var)\s+(\w+)\s*=\s*\{([^}]{0,500})\}',
        js
    ):
        obj_name = match.group(1)
        body = match.group(2)
        declared_props = set(re.findall(r'(\w+)\s*:', body))
        obj_declarations[obj_name] = declared_props

    for obj_name, declared_props in obj_declarations.items():
        if not declared_props:
            continue
        # Propriétés accédées sur cet objet
        accessed = set(re.findall(rf'\b{re.escape(obj_name)}\.(\w+)\b', js))
        # Exclure les méthodes built-in JS communes
        builtins = {'length', 'push', 'pop', 'shift', 'splice', 'forEach',
                    'map', 'filter', 'find', 'indexOf', 'join', 'slice',
                    'toString', 'valueOf', 'constructor'}
        undefined_props = accessed - declared_props - builtins
        # Filtrer les faux positifs : si le nom ressemble à une méthode (maj après .)
        undefined_props = {p for p in undefined_props if p[0].islower()}
        if len(undefined_props) >= 2:
            issues.append(
                f"Propriétés non déclarées sur '{obj_name}': {sorted(undefined_props)[:4]} "
                f"(déclarer ces propriétés dans l'objet '{obj_name}')"
            )

    # 2. .clear() sur des tableaux (erreur runtime fréquente)
    array_clears = re.findall(r'(\w+)\.clear\(\)', js)
    if array_clears:
        # Vérifier que ce ne sont pas des Map/Set
        for name in array_clears:
            if not re.search(rf'\b{re.escape(name)}\s*=\s*new\s+(?:Map|Set)\b', js):
                issues.append(
                    f"'{name}.clear()' : les tableaux n'ont pas de méthode .clear() "
                    f"— remplacer par '{name}.length = 0'"
                )
                break  # Signaler une seule fois

    # 3. Callbacks appelés sur un objet-type sans optional chaining ni définition
    # Ex: ENEMY_TYPES.boss_X.onAttack(e) alors que boss_X n'a pas de onAttack
    type_obj_calls = re.findall(
        r'([A-Z_]+)\[?[\'"]?(\w+)[\'"]?\]?\.(\w+)\s*\((?!\?)',  # appel direct sans ?.
        js
    )
    # Aussi les appels directs style ENEMY_TYPES.boss_slime_alpha.onAttack(
    direct_calls = re.findall(
        r'([A-Z_]+)\.(\w+)\.(\w+)\s*\([^?]',
        js
    )
    for registry, type_key, method in direct_calls:
        # Vérifier que ce type existe dans le registre et a cette méthode
        # Chercher la définition: 'type_key': { ... method: ...}
        type_def = re.search(
            rf"['\"]?{re.escape(type_key)}['\"]?\s*:\s*\{{([^}}]{{0,800}})\}}",
            js
        )
        if type_def and method not in type_def.group(1):
            issues.append(
                f"'{registry}.{type_key}.{method}()' appelé mais '{method}' absent "
                f"dans la définition de '{type_key}' — ajouter {method} ou utiliser ?.() "
            )

    # 4. Timers utilisés dans update() sans être initialisés à la création de l'entité
    # Pattern : e.xTimer -= dt  mais pas e.xTimer = ... dans la fonction de création
    timer_used = set(re.findall(r'\b\w+\.(\w+Timer)\s*[<>=-]', js))
    timer_inited = set(re.findall(r'(?:boss|enemy|e)\.\s*(\w+Timer)\s*=\s*[\d(]', js))
    # Chercher aussi dans les fonctions de création (createEnemy, spawnBoss...)
    create_blocks = re.findall(
        r'function\s+(?:createEnemy|spawnBoss|createEntity)\s*\([^)]*\)\s*\{([^}]{0,2000})\}',
        js, re.DOTALL
    )
    for block in create_blocks:
        for t in re.findall(r'(\w+Timer)\s*:', block):
            timer_inited.add(t)
    orphan_timers = timer_used - timer_inited - {'attackTimer', 'invincibilityTimer', 'stunTimer'}
    if orphan_timers:
        issues.append(
            f"Timers utilisés mais jamais initialisés à la création : {sorted(orphan_timers)} "
            f"— les initialiser à 0 dans createEnemy() ou spawnBoss()"
        )

    # 5. const/let déclarés deux fois dans la même fonction (même scope)
    # Analyse par fonction : extraire les déclarations top-level de chaque bloc
    func_bodies = re.findall(
        r'function\s+\w+\s*\([^)]*\)\s*\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}',
        js
    )
    for body in func_bodies:
        seen_in_func = {}
        for m2 in re.finditer(r'\b(?:const|let)\s+(\w+)\s*=', body):
            name = m2.group(1)
            # Ignorer les variables de boucle courantes
            if name in ('i', 'j', 'k', 'x', 'y', 'dx', 'dy', 'dt'):
                continue
            if name in seen_in_func:
                issues.append(
                    f"Variable '{name}' déclarée deux fois (const/let) dans la même fonction "
                    f"— SyntaxError potentielle → écran noir"
                )
                break  # Une seule issue par fonction
            seen_in_func[name] = True

    # 6. Double source de dégâts boss : playerTakeDamage dans onAttack ET dans le check de collision
    # Si onAttack contient playerTakeDamage ET qu'il y a aussi isColliding(hero, boss) → playerTakeDamage
    # → le joueur prend des dégâts deux fois à chaque contact
    has_onattack_damage = bool(re.search(
        r'onAttack\s*:\s*\([^)]*\)\s*=>\s*\{[^}]*playerTakeDamage',
        js, re.DOTALL
    ))
    has_collision_damage = bool(re.search(
        r'isColliding\s*\(\s*hero\s*,\s*boss\s*\)[^;]*playerTakeDamage',
        js, re.DOTALL
    ))
    if has_onattack_damage and has_collision_damage:
        issues.append(
            "Double source de dégâts boss : playerTakeDamage appelé dans onAttack ET dans le "
            "check isColliding(hero, boss) — choisir UNE seule source, retirer playerTakeDamage "
            "de onAttack (garder uniquement effets visuels/sonores)"
        )

    # 3b (old 3). gameState déclaré mais des états référencés non gérés dans update()
    state_decl = re.search(r"(?:let|var|const)\s+gameState\s*=\s*['\"](\w+)['\"]", js)
    if state_decl:
        all_states_set = set(re.findall(r"gameState\s*[=!]=\s*['\"](\w+)['\"]", js))
        handled_states = set(re.findall(
            r"(?:if|else if|case)\s*[\(]?\s*gameState\s*[=!]=\s*['\"](\w+)['\"]",
            js
        ))
        unhandled = all_states_set - handled_states
        unhandled.discard('playing')  # 'playing' peut être implicite
        if len(unhandled) >= 2:
            issues.append(
                f"États gameState référencés mais jamais gérés : {sorted(unhandled)} "
                f"(ajouter des branches if/else ou case pour ces états)"
            )

    # 7. Paramètre `dt` manquant dans les fonctions qui l'utilisent
    # Chercher les fonctions qui utilisent `dt` sans l'avoir en paramètre
    func_definitions = re.finditer(
        r'function\s+(\w+)\s*\(([^)]*)\)\s*\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}',
        js
    )
    dt_issue_reported = False
    for fn_match in func_definitions:
        fn_name = fn_match.group(1)
        params = fn_match.group(2)
        body = fn_match.group(3)
        # Ignorer gameLoop, update, animate — ils reçoivent naturellement le timestamp
        if fn_name in ('gameLoop', 'animate', 'loop', 'tick', 'render', 'update', 'main'):
            continue
        # Le body utilise dt comme variable (pas juste dans un commentaire)
        uses_dt = bool(re.search(r'\*\s*dt\b|\bdt\s*[*\-+<>]|\bdt\)', body))
        has_dt_param = 'dt' in re.split(r'\s*,\s*', params)
        if uses_dt and not has_dt_param and not dt_issue_reported:
            issues.append(
                f"Fonction '{fn_name}' utilise `dt` mais ne l'a pas en paramètre — "
                f"ajouter `dt` dans les paramètres et passer `dt` à l'appel"
            )
            dt_issue_reported = True  # Signaler une seule fois

    # A5 : Boucles while(true) sans break/return visible → blocage garanti du thread principal
    while_true_matches = list(re.finditer(r'while\s*\(\s*(?:true|1)\s*\)\s*\{', js))
    for wm in while_true_matches:
        zone = js[wm.end():wm.end() + 500]
        if not re.search(r'\b(?:break|return)\b', zone):
            issues.append(
                "while(true) sans break/return visible — risque de blocage du thread UI (freeze navigateur). "
                "Convertir en requestAnimationFrame ou ajouter un compteur de sécurité."
            )
            break  # Signaler une seule fois

    # I8 : THREE.js — classes hallucinées absentes de Three.js r128
    _THREE_FAKE = [
        'THREE.FogExp3D', 'THREE.LineCurve3D', 'THREE.CatmullRomCurve2',
        'THREE.PlaneHelper3D', 'THREE.ObjectHelper', 'THREE.GridHelper3D',
        'THREE.AxisHelper', 'THREE.BoundingBoxHelper',
        'THREE.MeshFaceMaterial', 'THREE.MultiMaterial',
        'THREE.BoxHelper2', 'THREE.TransformGizmo',
    ]
    for _fake in _THREE_FAKE:
        if _fake in js:
            issues.append(
                f"THREE.js halluciné : '{_fake}' n'existe pas dans Three.js r128 — "
                f"supprimer ou remplacer par l'API correcte."
            )
            break  # Signaler une seule fois

    # 0. gameLoop défini AVANT DOMContentLoaded qui appelle update()/draw() définis DANS le callback
    # → "update is not defined" au premier RAF → écran noir garanti
    dom_match = re.search(
        r"document\.addEventListener\s*\(\s*['\"]DOMContentLoaded['\"]",
        js
    )
    if dom_match:
        code_before_dom = js[:dom_match.start()]
        code_in_dom = js[dom_match.start():]
        for raf_fn in ('gameLoop', 'animate', 'mainLoop', 'gameRender'):
            if re.search(rf'\bfunction\s+{re.escape(raf_fn)}\s*\(', code_before_dom):
                # La fonction est définie avant DOMContentLoaded
                # Vérifier qu'elle appelle update()/draw() qui sont dans DOMContentLoaded
                fn_m = re.search(rf'\bfunction\s+{re.escape(raf_fn)}\s*\(', code_before_dom)
                brace_s = code_before_dom.find('{', fn_m.end())
                if brace_s >= 0:
                    snippet = code_before_dom[brace_s:brace_s + 500]
                    calls_update_draw = bool(re.search(r'\b(?:update|draw)\s*\(', snippet))
                    update_in_dom = bool(re.search(r'\bfunction\s+(?:update|draw)\s*\(', code_in_dom))
                    if calls_update_draw and update_in_dom:
                        issues.append(
                            f"Fonction '{raf_fn}' définie AVANT DOMContentLoaded appelle update()/draw() "
                            f"qui ne seront définis QU'À L'INTÉRIEUR du callback — "
                            f"ReferenceError garanti au premier requestAnimationFrame. "
                            f"Déplacer '{raf_fn}' DANS DOMContentLoaded, après update() et draw()."
                        )
                break

    # 6a. Boucle for-of qui spliceait le tableau itéré (comportement indéfini)
    for_of_splice = re.findall(
        r'for\s*\(\s*(?:const|let)\s+(\w+)\s+of\s+(\w+)\s*\)',
        js
    )
    for var_name, arr_name in for_of_splice:
        if len(arr_name) < 3:
            continue
        # Chercher splice du même tableau dans une zone de 2000 chars après la boucle
        loop_match = re.search(
            rf'for\s*\(\s*(?:const|let)\s+{re.escape(var_name)}\s+of\s+{re.escape(arr_name)}\s*\)',
            js
        )
        if loop_match:
            zone = js[loop_match.start():loop_match.start() + 2000]
            if re.search(rf'\b{re.escape(arr_name)}\.splice\s*\(', zone):
                issues.append(
                    f"Boucle 'for ({var_name} of {arr_name})' splice le tableau itéré "
                    f"— comportement indéfini (éléments sautés/dupliqués). "
                    f"Remplacer par : for (let i = {arr_name}.length-1; i >= 0; i--) "
                    f"{{ const {var_name} = {arr_name}[i]; ... {arr_name}.splice(i,1); }}"
                )

    # 6b. Anti-pattern location.reload() pour restart
    reload_matches = re.findall(r'(?:window\.)?location\.reload\(\)', js)
    if reload_matches:
        # Chercher une fonction de reset dans le code
        reset_fn = next(
            (fn for fn in ('restartGame', 'resetGame', 'restart', 'reset', 'init', 'startGame', 'newGame')
             if re.search(rf'function\s+{fn}\s*\(', js)),
            None
        )
        if reset_fn:
            issues.append(
                f"location.reload() détecté ({len(reload_matches)} occurrence(s)) — "
                f"remplacer par {reset_fn}() pour éviter le rechargement de page"
            )
        else:
            issues.append(
                f"location.reload() détecté ({len(reload_matches)} occurrence(s)) — "
                f"créer une fonction resetGame() qui réinitialise les variables et appeler resetGame() à la place"
            )

    # 7. Expression-statements sans effet : résultat d'un appel ignoré (oubli d'affectation)
    # Pattern : ligne standalone = expression booléenne/objet qui devrait être assignée
    # Ex: !towers.some(t => ...);  au lieu de  const isValid = !towers.some(t => ...);
    orphan_exprs = re.findall(
        r'^\s*(!?\w[\w.]*(?:\[.*?\])?\s*\.\s*\w+\s*\([^)]*\))\s*;',
        js, re.MULTILINE
    )
    # Garder seulement les cas suspects : résultat d'un .some/.every/.find ignoré
    suspicious_methods = {'some', 'every', 'find', 'findIndex', 'filter', 'map', 'includes'}
    for expr in orphan_exprs:
        method_match = re.search(r'\.(\w+)\s*\(', expr)
        if method_match and method_match.group(1) in suspicious_methods:
            if expr.strip().startswith('!') or not expr.strip().startswith('//'):
                issues.append(
                    f"Expression sans affectation : '{expr.strip()[:60]}' — "
                    f"le résultat est ignoré. Probablement manque 'const isValid = ...' "
                    f"— la variable utilisée ensuite dans if(isValid) sera undefined"
                )
                break  # Signaler une seule fois

    # 8a. Constantes de clé localStorage utilisées sans être déclarées
    # Pattern : localStorage.setItem(SAVE_KEY, ...) ou localStorage.getItem(STORAGE_KEY)
    # mais const SAVE_KEY = ... absent
    ls_key_usages = re.findall(
        r'localStorage\.(?:setItem|getItem|removeItem)\s*\(\s*([A-Z_][A-Z0-9_]{2,})\b',
        js
    )
    for key_name in set(ls_key_usages):
        if not re.search(
            rf'\b(?:const|let|var)\s+{re.escape(key_name)}\s*=',
            js
        ):
            issues.append(
                f"Constante '{key_name}' utilisée dans localStorage mais jamais déclarée "
                f"— ReferenceError au premier save/load. "
                f"Ajouter 'const {key_name} = \"{key_name.lower()}_v1\";' en tête de script."
            )

    # 8b. Résultat de lookup dans un dictionnaire *_DEFS/*_CONFIG utilisé directement
    # sans vérification d'existence → TypeError: Cannot read property X of undefined
    # Pattern : const def = TOWER_DEFS[tower.type]; (ok) vs TOWER_DEFS[x].prop (sans guard)
    # Détecte : DICT_NAME[varExpr].property sans un if(DICT_NAME[varExpr]) ou const x = ... if (!x)
    dict_direct_access = re.finditer(
        r'\b([A-Z][A-Z0-9_]*(?:DEFS?|CONFIG|DATA|TYPES?|MAP|TABLE))\s*\[\s*(\w+(?:\.\w+)?)\s*\]\s*\.\s*(\w+)',
        js
    )
    reported_dicts: set[str] = set()
    for m in dict_direct_access:
        dict_name = m.group(1)
        key_expr = m.group(2)
        prop = m.group(3)
        report_key = f"{dict_name}[{key_expr}]"
        if report_key in reported_dicts:
            continue
        # Vérifier qu'il y a un guard : if (!DICT[key]) ou const def = DICT[key]; (sans .prop chaîné)
        # Chercher dans les 300 chars précédant l'accès
        pos = m.start()
        code_before = js[max(0, pos - 300):pos]
        # Guard valide : if(!DICT[x]) ou if(DICT[x]) dans le contexte précédent
        has_if_guard = bool(re.search(
            rf'if\s*\(\s*!?\s*{re.escape(dict_name)}\s*\[',
            code_before
        ))
        # Guard valide : const x = DICT[key]; (semicolon ou newline AVANT un éventuel .prop)
        # = stockage intermédiaire sans accès chaîné direct
        stored_lookup = re.search(
            rf'(?:const|let|var)\s+(\w+)\s*=\s*{re.escape(dict_name)}\s*\[[^\]]+\]\s*[;\n]',
            code_before
        )
        has_guard = has_if_guard or bool(stored_lookup)
        if not has_guard:
            reported_dicts.add(report_key)
            issues.append(
                f"Accès direct '{dict_name}[{key_expr}].{prop}' sans vérifier que "
                f"'{dict_name}[{key_expr}]' existe → TypeError si la clé est absente. "
                f"Ajouter 'const def = {dict_name}[{key_expr}]; if (!def) return;' avant l'accès."
            )
        if len(reported_dicts) >= 2:
            break  # Signaler max 2 cas

    # 8. Variables utilisées dans des conditions if() sans jamais être déclarées
    # Collecte depuis l'échantillon js (pour cohérence locale)
    all_declared = set(re.findall(r'\b(?:const|let|var)\s+(\w+)', js))
    # Multi-declarator: const a = [], b = [], c = [] — capture b, c, ...
    for m in re.finditer(r'\b(?:const|let|var)\s+\w+[^;,\n]*(?:,\s*(\w+)[^;,\n]*)+', js):
        for extra in re.findall(r',\s*(\w+)\s*(?:=|,|;|\n|$)', m.group(0)):
            all_declared.add(extra)
    all_declared |= set(re.findall(r'\bfunction\s+(\w+)\s*\(', js))
    # Paramètres de fonctions
    for params in re.findall(r'function\s*\w*\s*\(([^)]+)\)', js):
        all_declared |= {p.strip().lstrip('...') for p in params.split(',') if p.strip()}
    # Variables de boucle for
    all_declared |= set(re.findall(r'\bfor\s*\(\s*(?:const|let|var)\s+(\w+)', js))
    # Enrichissement depuis le script complet (évite les faux positifs hors-échantillon)
    if extra_declared:
        all_declared |= extra_declared

    # Variables utilisées dans if(cond) — on cherche les identifiers simples dans les conditions
    if_conditions = re.findall(r'\bif\s*\(\s*!?(\w+)\b', js)
    js_globals = {
        # Mots-clés JS — JAMAIS des variables à déclarer
        'true', 'false', 'null', 'undefined', 'this', 'typeof', 'instanceof',
        'void', 'delete', 'in', 'of', 'new', 'class', 'super', 'extends',
        'return', 'throw', 'catch', 'finally', 'async', 'await', 'yield',
        # Globals navigateur
        'window', 'document', 'navigator', 'location', 'history',
        'performance', 'screen', 'event', 'self', 'globalThis',
        # Constructeurs et builtins JS
        'Math', 'Date', 'Array', 'Object', 'String', 'Number', 'Boolean',
        'Function', 'Symbol', 'BigInt', 'RegExp', 'Error', 'Promise',
        'Map', 'Set', 'WeakMap', 'WeakSet', 'Proxy', 'Reflect',
        'Int8Array', 'Uint8Array', 'Float32Array', 'Float64Array',
        'console', 'JSON', 'Intl',
        # Web APIs
        'localStorage', 'sessionStorage', 'IndexedDB',
        'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
        'requestAnimationFrame', 'cancelAnimationFrame',
        'fetch', 'XMLHttpRequest', 'WebSocket', 'Worker',
        'AudioContext', 'webkitAudioContext',
        # Valeurs numériques spéciales
        'NaN', 'Infinity', 'parseInt', 'parseFloat', 'isNaN', 'isFinite',
        'encodeURIComponent', 'decodeURIComponent',
        # Three.js
        'THREE',
        # Globals communs aux jeux HTML5 générés (déclarés hors de la zone 1 du sample)
        # Ces vars sont déclarées en dehors de la fenêtre analysée par le linter
        'player', 'enemies', 'boss', 'canvas', 'ctx', 'keys', 'items', 'map',
        'rooms', 'particles', 'projectiles', 'bullets', 'score', 'gameState',
        'offscreen', 'gctx', 'camera', 'world', 'level', 'wave', 'input',
        'floatingTexts', 'platforms', 'lootItems', 'mouse', 'sfx',
        'dt', 'lastTime', 'W', 'H', 'WIDTH', 'HEIGHT',
        # Propriétés destructurées fréquentes
        'left', 'right', 'up', 'down', 'space', 'enter', 'escape',
    }
    undeclared_in_if = []
    for varname in if_conditions:
        if (len(varname) >= 4  # Ignorer les noms très courts (i, j, x, y, dt...)
                and varname not in all_declared
                and varname not in js_globals
                and not varname[0].isupper()  # Ignorer les constantes/classes
                and varname not in undeclared_in_if):
            undeclared_in_if.append(varname)

    if undeclared_in_if:
        # Vérifier qu'ils ne sont pas déclarés ailleurs (affectation simple)
        truly_undeclared = [
            v for v in undeclared_in_if
            if not re.search(rf'\b{re.escape(v)}\s*[=](?!=)', js)  # pas d'affectation
            and not re.search(rf'\bfor\s*\([^)]*\b{re.escape(v)}\b', js)  # pas dans for
        ]
        if truly_undeclared:
            issues.append(
                f"Variables utilisées dans if() mais jamais déclarées : {truly_undeclared[:4]} "
                f"— ReferenceError au runtime lors de l'interaction"
            )

    return issues


@with_fallback(None)
def _llm_analysis(js: str) -> list[str]:
    """
    Analyse LLM ciblée pour détecter les bugs runtime non évidents.
    Retourne une liste de descriptions de bugs précis.
    """
    result = _call(js)
    if not result:
        return []

    bugs = result.get("bugs_runtime", [])
    issues = []
    for bug in bugs:
        desc = bug.get("description", "")
        fix = bug.get("correction_suggeree", "")
        if desc:
            issues.append(f"{desc}{' — ' + fix if fix else ''}")

    return issues


@with_fallback(None)
def _call(js: str) -> dict:
    prompt = f"""Analyse ce code JavaScript de jeu HTML5. Cherche UNIQUEMENT les bugs runtime qui cassent le jeu.

CODE :
```javascript
{js}
```

Réponds en JSON avec exactement ce format :
{{
  "bugs_runtime": [
    {{
      "type": "undefined_variable | missing_param | missing_property | logic_error | type_error",
      "description": "Nom exact de la variable/fonction concernée + ce qui est cassé",
      "correction_suggeree": "Correction concrète en 1 ligne : quoi ajouter/modifier où"
    }}
  ],
  "code_semble_fonctionnel": true
}}

EXEMPLES de bugs_runtime bien formatés :
- {{"type":"undefined_variable","description":"Variable 'closest' utilisée dans if(closest) sans déclaration préalable","correction_suggeree":"Ajouter 'let closest = null;' avant la boucle enemies"}}
- {{"type":"undefined_variable","description":"Constante 'SAVE_KEY' utilisée dans localStorage.setItem(SAVE_KEY,...) mais jamais déclarée","correction_suggeree":"Ajouter 'const SAVE_KEY = \"myGame_v1\";' en tête de script"}}
- {{"type":"undefined_variable","description":"Variable 'dx' utilisée dans Math.sqrt(dx*dx+dy*dy) sans être calculée avant","correction_suggeree":"Ajouter 'const dx = target.x - src.x; const dy = target.y - src.y;' avant la ligne"}}
- {{"type":"missing_param","description":"Fonction 'updateTowers()' utilise dt sans l'avoir en paramètre","correction_suggeree":"Changer en 'function updateTowers(dt)' et l'appeler updateTowers(dt)"}}
- {{"type":"missing_property","description":"WAVE_DEFS.boss_wave.spawnPattern appelé mais spawnPattern absent de la définition","correction_suggeree":"Ajouter spawnPattern:'line' dans WAVE_DEFS.boss_wave ou utiliser ?.()  "}}
- {{"type":"type_error","description":"TOWER_DEFS[tower.type].upgrades accédé sans vérifier que la clé existe","correction_suggeree":"Ajouter 'const def = TOWER_DEFS[tower.type]; if (!def) return;' avant l'accès"}}

Limite : 5 bugs max, seulement ceux qui causent un crash ou un écran noir. Si rien de critique : bugs_runtime vide."""

    return call_gemini_json(prompt, temperature=0.1, system_instruction=SYSTEM, max_tokens=12000)

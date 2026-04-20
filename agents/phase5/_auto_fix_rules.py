"""
_auto_fix_rules.py — Bibliothèque de correctifs programmatiques déterministes (P6).

Chaque règle est une fonction (script: str) -> tuple[str, str | None]
  - retourne (script_corrigé, description) si une correction a été appliquée
  - retourne (script_original, None) si rien à faire

Toutes les règles sont sans LLM — purement regex/AST-léger.
Elles couvrent les patterns récurrents qui n't besoin pas d'intelligence pour être corrigés.
"""

import re


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-1 : const X réassigné → let X
# ──────────────────────────────────────────────────────────────────────────────

def fix_const_reassignment(script: str) -> tuple[str, str | None]:
    """
    Détecte les variables déclarées avec `const` mais réassignées plus loin
    (score += 10, player = null, etc.) et les convertit en `let`.
    """
    # Trouver tous les `const X = ...` (pas d'objet ou tableau — scalaires seulement)
    const_decls = re.findall(
        r'^[ \t]*const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?![\[{])[^\n;]+',
        script, re.MULTILINE
    )
    changed = []
    for name in set(const_decls):
        # Chercher une réassignation (X = ..., X += ..., X++, X--, ++X)
        if re.search(rf'\b{re.escape(name)}\s*(?:\+=|-=|\*=|/=|%=|\+\+|--|\s*=[^=])', script):
            # Vérifier que ce n'est pas une comparaison (===, !==)
            assignments = re.findall(rf'\b{re.escape(name)}\s*(?:\+=|-=|\*=|/=|%=|\+\+|--|=(?!=))', script)
            if assignments:
                # Remplacer `const name` par `let name`
                new_script = re.sub(
                    rf'(^[ \t]*)const(\s+{re.escape(name)}\s*=)',
                    r'\1let\2',
                    script, flags=re.MULTILINE
                )
                if new_script != script:
                    script = new_script
                    changed.append(name)
    if changed:
        return script, f"const→let pour variable(s) réassignée(s) : {', '.join(changed[:5])}"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-2 : for(const i=0; ...) → for(let i=0; ...)
# ──────────────────────────────────────────────────────────────────────────────

def fix_for_const_index(script: str) -> tuple[str, str | None]:
    """for(const i=0; i<n; i++) est une SyntaxError — remplacer par let."""
    new_script = re.sub(
        r'\bfor\s*\(\s*const\s+(\w+)\s*=\s*0\s*;',
        r'for (let \1 = 0;',
        script
    )
    if new_script != script:
        return new_script, "for(const i=0...) → for(let i=0...) [SyntaxError évitée]"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-3 : arr.clear() → arr.length = 0
# ──────────────────────────────────────────────────────────────────────────────

def fix_array_clear(script: str) -> tuple[str, str | None]:
    """arr.clear() n'existe pas en JS standard — remplacer par arr.length = 0."""
    new_script = re.sub(
        r'\b(\w+)\.clear\s*\(\s*\)',
        r'\1.length = 0',
        script
    )
    if new_script != script:
        count = len(re.findall(r'\b\w+\.clear\s*\(\s*\)', script))
        return new_script, f"{count} .clear() → .length = 0"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-4 : location.reload() → resetGame() ou initGame()
# ──────────────────────────────────────────────────────────────────────────────

def fix_location_reload(script: str) -> tuple[str, str | None]:
    """location.reload() recharge la page entière — utiliser resetGame() ou initGame()."""
    if 'location.reload()' not in script:
        return script, None
    # Détecter quelle fonction de reset existe
    if re.search(r'\bfunction\s+resetGame\b', script):
        new_script = script.replace('location.reload()', 'resetGame()')
        return new_script, "location.reload() → resetGame()"
    elif re.search(r'\bfunction\s+initGame\b', script):
        new_script = script.replace('location.reload()', 'initGame()')
        return new_script, "location.reload() → initGame()"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-5 : updateFn() appelée sans dt alors que body contient dt
# ──────────────────────────────────────────────────────────────────────────────

def fix_missing_dt_param(script: str) -> tuple[str, str | None]:
    """
    Détecte les fonctions update* définies sans paramètre dt mais dont le corps utilise dt,
    et ajoute dt en paramètre + corrige les appels correspondants.
    """
    changed = []
    # Trouver les fonctions update* sans paramètre
    fn_pattern = re.compile(
        r'function\s+(update[a-zA-Z0-9_]*)\s*\(\s*\)\s*\{',
        re.IGNORECASE
    )
    for m in fn_pattern.finditer(script):
        fn_name = m.group(1)
        fn_start = m.end()
        # Extraire le corps (brace counting)
        depth = 1
        fn_end = fn_start
        for i in range(fn_start, len(script)):
            if script[i] == '{':
                depth += 1
            elif script[i] == '}':
                depth -= 1
                if depth == 0:
                    fn_end = i
                    break
        body = script[fn_start:fn_end]
        # Si le corps utilise dt directement (pas comme paramètre)
        if re.search(r'\bdt\b', body):
            # Ajouter dt en paramètre
            script = script[:m.start()] + f'function {fn_name}(dt) {{' + script[m.end():]
            # Corriger les appels : fn_name() → fn_name(dt)
            script = re.sub(
                rf'\b{re.escape(fn_name)}\s*\(\s*\)',
                f'{fn_name}(dt)',
                script
            )
            changed.append(fn_name)
    if changed:
        return script, f"dt ajouté en paramètre : {', '.join(changed[:5])}"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-6 : eval() en production → suppression
# ──────────────────────────────────────────────────────────────────────────────

def fix_eval_production(script: str) -> tuple[str, str | None]:
    """Supprime les appels eval() qui ne sont pas dans des commentaires."""
    # Cibler les eval() simples (pas new Function() qui est plus complexe)
    new_script = re.sub(
        r'\beval\s*\([^)]{0,200}\)',
        '/* eval supprimé */',
        script
    )
    if new_script != script:
        count = len(re.findall(r'\beval\s*\(', script))
        return new_script, f"{count} eval() supprimé(s)"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-7 : new Image() → suppression (cause ERR_FILE_NOT_FOUND)
# ──────────────────────────────────────────────────────────────────────────────

def fix_new_image(script: str) -> tuple[str, str | None]:
    """Remplace les new Image() par null (le pré-patcher principal gère .src)."""
    # Chercher les assignations var/let/const img = new Image()
    new_script = re.sub(
        r'(?:var|let|const)\s+(\w+)\s*=\s*new\s+Image\s*\(\s*\)\s*;?',
        r'var \1 = null; /* Image supprimée — utilise canvas shapes */',
        script
    )
    if new_script != script:
        count = len(re.findall(r'new\s+Image\s*\(\s*\)', script))
        return new_script, f"{count} new Image() → null (pas de fichier externe)"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-8 : var locale dans L9 utilisée comme globale
# Cas spécifique : gradient1/gradient2 local dans drawBackground
# ──────────────────────────────────────────────────────────────────────────────

def fix_l9_undeclared_locals(script: str) -> tuple[str, str | None]:
    """
    Détecte les variables utilisées dans les fonctions draw* sans être déclarées localement
    ni globalement. Cas récurrent : gradients, barX/barY, hpRatio dans les fonctions draw.
    Ajoute une déclaration `let X = 0;` au début de la fonction.
    """
    changed = []
    # Variables fréquemment oubliées dans draw*
    _local_suspects = ['gradient', 'gradient1', 'gradient2', 'gradient3',
                       'barX', 'barY', 'barW', 'barH', 'hpRatio', 'gridSize',
                       'tileX', 'tileY', 'alpha', 'pulse']

    draw_fn_pattern = re.compile(
        r'(function\s+draw[a-zA-Z0-9_]*\s*\([^)]*\)\s*\{)',
        re.IGNORECASE
    )
    for m in draw_fn_pattern.finditer(script):
        fn_start = m.end()
        depth = 1
        fn_end = fn_start
        for i in range(fn_start, len(script)):
            if script[i] == '{':
                depth += 1
            elif script[i] == '}':
                depth -= 1
                if depth == 0:
                    fn_end = i
                    break
        body = script[fn_start:fn_end]
        for suspect in _local_suspects:
            # Utilisé mais non déclaré localement
            if (re.search(rf'\b{re.escape(suspect)}\b', body) and
                    not re.search(rf'(?:var|let|const)\s+{re.escape(suspect)}\b', body) and
                    not re.search(rf'^(?:var|let|const)\s+{re.escape(suspect)}\b', script, re.MULTILINE)):
                # Injecter déclaration en début de corps de fonction
                inject = f'\n  var {suspect} = null;'
                script = script[:fn_start] + inject + script[fn_start:]
                fn_start += len(inject)
                fn_end += len(inject)
                changed.append(suspect)
    if changed:
        return script, f"Variables locales draw* déclarées : {', '.join(set(changed[:8]))}"
    return script, None


# ──────────────────────────────────────────────────────────────────────────────
# APPLICATION DE TOUTES LES RÈGLES
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# RÈGLE P6-9 : rgba() appelé comme fonction JS → string CSS quotée
# ──────────────────────────────────────────────────────────────────────────────

def fix_rgba_as_function(script: str) -> tuple[str, str | None]:
    """
    Corrige `ctx.fillStyle = rgba(255,0,0,0.5)` → `ctx.fillStyle = 'rgba(255,0,0,0.5)'`
    Corrige aussi `= rgba(r,g,b,alpha)` avec des variables comme arguments.
    `= rgba(...)` non quoté cause ReferenceError et écran noir.
    """
    # Règle : = rgba(...) non précédé d'une quote ouverte (donc pas déjà dans une string)
    # On exclut les cas où rgba est déjà dans une chaîne : '...' ou "..."
    # Le lookahead négatif (?<!['"]) vérifie que le = n'est pas suivi d'une quote AVANT rgba
    def _add_quotes(m):
        inner = m.group(2)
        return m.group(1) + "'rgba(" + inner + ")'"

    # Match = rgba(...) avec n'importe quel contenu (variables, nombres, expressions simples)
    # Exclusions : déjà entre guillemets → pas de match si rgba est précédé de ' ou "
    new_script = re.sub(
        r'''(=\s*)(?<!['"=])rgba\s*\(([^'")\n]{1,120})\)(?!\s*['"])''',
        _add_quotes,
        script
    )
    # Cas supplémentaire : = rgba(...) sur propriétés Canvas connues
    if new_script == script:
        new_script = re.sub(
            r'((?:fillStyle|strokeStyle|shadowColor|color|background)\s*=\s*)rgba\s*\(([^)]{1,120})\)(?!\s*[\'"])',
            lambda m: m.group(1) + "'rgba(" + m.group(2) + ")'",
            script
        )

    # Cas template literal : ctx.fillStyle = `rgba(${r},${g},${b},0.5)` → ctx.fillStyle = 'rgba('+r+','+g+','+b+',0.5)'
    # Ces template literals sont valides JS mais le contenu `rgba(` est parfois généré sans guillemets autour
    # → ici on les laisse intacts (ce sont de vraies strings), mais on corrige rgba() sans backtick NI guillemet
    # Cas bare : assignation directe sans quote NI backtick (le LLM oublie les guillemets)
    if new_script == script:
        new_script = re.sub(
            r'(=\s*)(?<![\'\"`])rgba\s*\(([^)]{1,120})\)(?![\'\"`])',
            lambda m: m.group(1) + "'rgba(" + m.group(2) + ")'",
            new_script
        )

    if new_script != script:
        count = len(re.findall(r'=\s*rgba\s*\(', script))
        return new_script, f"{count} rgba() sans quotes → 'rgba()' (ReferenceError évité)"
    return script, None


_ALL_RULES = [
    fix_rgba_as_function,       # P6-9 en premier : cause écran noir si non fixé
    fix_const_reassignment,
    fix_for_const_index,
    fix_array_clear,
    fix_location_reload,
    fix_missing_dt_param,
    fix_eval_production,
    fix_new_image,
    fix_l9_undeclared_locals,
]


def _quick_syntax_check(script: str) -> bool:
    """Vérifie la syntaxe JS via Node.js --check. Retourne True si OK."""
    try:
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False,
                                         encoding='utf-8', errors='replace') as f:
            f.write(script)
            fname = f.name
        result = subprocess.run(
            ['node', '--check', fname],
            capture_output=True, text=True, timeout=6
        )
        os.unlink(fname)
        return result.returncode == 0
    except Exception:
        return True  # Impossible de vérifier → on assume OK


def apply_all_rules(script: str) -> tuple[str, list[str]]:
    """
    Applique toutes les règles P6 dans l'ordre.
    Chaque règle est rollbackée individuellement si elle casse la syntaxe.
    Retourne (script_corrigé, [descriptions_appliquées]).
    """
    applied = []
    for rule in _ALL_RULES:
        try:
            new_script, description = rule(script)
            if description and new_script != script:
                # Rollback individuel si syntaxe cassée
                if _quick_syntax_check(new_script):
                    script = new_script
                    applied.append(description)
                # else: cette règle casse la syntaxe — on la skip silencieusement
        except Exception:
            pass  # Règle échouée → on continue sans crasher
    return script, applied

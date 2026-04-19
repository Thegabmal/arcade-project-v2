"""
Agent Testeur de Modules — Phase 4
Valide chaque module JavaScript avant assemblage.
Détecte les problèmes par analyse statique (+ Playwright si disponible).
Retourne la liste des modules valides et des modules qui doivent être régénérés.
"""

import re
from genre_profile import GeneratedModules, ModuleArchitecture
from logger import phase4_log


def run(generated: GeneratedModules) -> GeneratedModules:
    """
    Valide chaque module. Met à jour modules_valides et modules_echoues.
    Retourne le GeneratedModules annoté.
    """
    phase4_log.agent_start("Testeur Modules", f"Validation de {len(generated.modules)} modules")

    arch = generated.architecture
    modules_valides = []
    modules_echoues = []

    for nom, code in generated.modules.items():
        issues = _validate_module(nom, code, arch)
        if issues:
            modules_echoues.append(nom)
            phase4_log.warning(f"  ✗ Module '{nom}' : {'; '.join(issues)}")
        else:
            modules_valides.append(nom)
            phase4_log.info(f"  ✓ Module '{nom}' OK ({len(code)} chars)")

    generated.modules_valides = modules_valides
    generated.modules_echoues = modules_echoues

    phase4_log.agent_done(
        "Testeur Modules",
        f"{len(modules_valides)}/{len(generated.modules)} modules valides"
    )
    return generated


def _validate_module(nom: str, code: str, arch: ModuleArchitecture) -> list:
    """Retourne une liste d'issues pour un module. Liste vide = module valide."""
    issues = []
    est_3d = arch.technologie == "threejs"

    # 1. Code non vide
    if not code or len(code.strip()) < 50:
        issues.append("code trop court ou vide")
        return issues

    # 2. Pas de balises HTML dans un module JS
    if "<html" in code.lower() or "<!doctype" in code.lower():
        issues.append("contient des balises HTML (doit être JS pur)")

    # 3. Pas de redéclaration de variables globales
    global_vars = set(arch.variables_globales)
    for var in global_vars:
        pattern = rf'\b(?:let|const|var)\s+{re.escape(var)}\b'
        if re.search(pattern, code):
            issues.append(f"redéclare la variable globale '{var}'")

    # 4. Les fonctions exposées sont bien définies
    module_def = arch.get_module(nom)
    fonctions_attendues = module_def.get("fonctions_exposees", []) if module_def else []
    for fn in fonctions_attendues:
        pattern_fn = rf'\bfunction\s+{re.escape(fn)}\s*\('
        pattern_arrow = rf'\b{re.escape(fn)}\s*=\s*(?:function|\()'
        if not re.search(pattern_fn, code) and not re.search(pattern_arrow, code):
            issues.append(f"fonction '{fn}' manquante")

    # 5. Pas d'erreurs de syntaxe évidentes (accolades non équilibrées)
    open_braces = code.count("{")
    close_braces = code.count("}")
    if abs(open_braces - close_braces) > 2:
        issues.append(f"accolades déséquilibrées ({open_braces}{{ vs {close_braces}}})")

    # 6. Taille raisonnable
    taille_max = module_def.get("taille_max", 8000) if module_def else 8000
    if len(code) > taille_max * 1.5:
        issues.append(f"module trop long ({len(code)} > {int(taille_max * 1.5)} chars)")

    # 7. Gates spécifiques 3D (Three.js)
    if est_3d:
        issues.extend(_validate_3d_specifics(nom, code))

    return issues


def _validate_3d_specifics(nom: str, code: str) -> list:
    """Gates de validation spécifiques aux modules Three.js."""
    issues = []

    # 7a. Hallucination propriétés 2D : obj.x au lieu de obj.position.x
    #     On cherche des patterns typiques : player.x =, enemy.x +, .x += dt
    #     mais on exclut les cas légitimes comme position.x, uv.x, color.r
    _2d_prop_patterns = [
        r'\bplayer\.(x|y)\s*[+\-*/=]',
        r'\benemy\.(x|y)\s*[+\-*/=]',
        r'\bbullet\.(x|y)\s*[+\-*/=]',
        r'\.\s*(x|y)\s*\+=\s*\w+\s*\*\s*dt',  # .x += speed * dt hors position
    ]
    for pat in _2d_prop_patterns:
        if re.search(pat, code):
            # Exclut si adjacent à "position" ou "uv" ou "rotation"
            match = re.search(pat, code)
            if match:
                start = max(0, match.start() - 20)
                context_snippet = code[start:match.end()]
                if not re.search(r'position\.|uv\.|rotation\.|scale\.', context_snippet):
                    issues.append(f"hallucination 2D détectée : '{match.group(0).strip()}' — utilise .position.x/.position.y")
                    break

    # 7b. Création de geometry dans la boucle de jeu (très coûteux)
    loop_body_match = re.search(
        r'function\s+(?:animate|gameLoop|update)\s*\([^)]*\)\s*\{([\s\S]*?)(?=\nfunction |\Z)',
        code
    )
    if loop_body_match:
        loop_body = loop_body_match.group(1)
        if re.search(r'new\s+THREE\.\w*Geometry\s*\(', loop_body):
            issues.append("geometry créée dans la boucle de jeu (coûteux — crée hors loop et réutilise)")

    # 7c. Pour les modules avec entités (splice), scene.remove() doit être présent
    if re.search(r'\.splice\s*\(', code):
        if 'THREE' in code and not re.search(r'scene\.remove\s*\(', code):
            issues.append("splice() utilisé sans scene.remove() — les meshs fuient dans la scène")

    # 7d. Module core doit avoir scene, camera, renderer, clock
    if nom == "core":
        required_3d = ["scene", "camera", "renderer", "clock"]
        missing = [r for r in required_3d if r not in code]
        if missing:
            issues.append(f"module core manque : {', '.join(missing)}")

    return issues


def get_modules_to_regenerate(generated: GeneratedModules) -> list:
    """Retourne les noms des modules qui nécessitent une régénération."""
    return generated.modules_echoues.copy()


def score_modules(generated: GeneratedModules) -> float:
    """Score 0-10 basé sur le ratio modules valides."""
    total = len(generated.modules)
    if total == 0:
        return 0.0
    valid = len(generated.modules_valides)
    return round((valid / total) * 10, 1)

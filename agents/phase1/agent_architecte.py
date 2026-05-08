"""
Code Architect Agent — Phase 1 (end)
Decomposes the game into independent JavaScript modules.
Each module is < 8000 chars, with clear interfaces.
Produces a ModuleArchitecture used by the modular Creator.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import ConceptionContext, ModuleArchitecture
from logger import phase1_log

SYSTEM = """You are a software architect expert in HTML5 games. You decompose games into
independent, coherent JavaScript modules. Each module exposes functions and uses clearly
defined global variables. You respond ONLY in valid JSON."""


def run(context: ConceptionContext) -> ModuleArchitecture:
    phase1_log.agent_start("Architecte", "Décomposition du jeu en modules")

    gp = context.genre_profile
    gdd = context.gdd
    tech = context.tech_specs
    est_3d = tech.get("technologie_rendu", "canvas2d") == "threejs"

    technologie = "threejs" if est_3d else "canvas2d"
    states = tech.get("state_machine", {}).get("etats", ["menu", "playing", "gameover"])

    prompt = f"""Décompose ce jeu HTML5 en modules JavaScript indépendants.

JEU : {gdd.get('titre', 'Arcade Game')}
GENRE : {gp.genre_principal} / {gp.sous_genre}
TECHNOLOGIE : {"Three.js (3D)" if est_3d else "Canvas 2D"}
ÉTATS : {', '.join(states)}
CORE LOOP : {gp.boucle_core}
SYSTÈMES : {json.dumps([s.get('nom', '') for s in gdd.get('systemes_principaux', [])], ensure_ascii=False)}

RÈGLES DE DÉCOMPOSITION :
1. Chaque module fait entre 3000 et 8000 caractères de JavaScript
2. Chaque module a une responsabilité unique et CONTIENT TOUT LE CODE nécessaire à cette responsabilité
3. Les modules communiquent uniquement via les variables globales listées
4. L'ordre d'exécution est critique — un module n'utilise que des variables déjà définies
5. Le module "core" contient DOMContentLoaded, le canvas, la game loop et la machine à états
6. Pas de module "utils" sauf si vraiment nécessaire — fusionne-le dans "core"
7. IMPORTANT : un petit jeu 3D doit avoir 3-4 modules, un jeu complexe au maximum 5

ARCHITECTURE RECOMMANDÉE (3 à 5 modules) :
Pour un jeu d'action/shooter/platformer :
  - core    : DOMContentLoaded, canvas, game loop, états, inputs
  - entities: joueur + ennemis + projectiles (groupés)
  - ui      : HUD, menus, game over
  [optionnel] fx : particules, effets visuels

Pour un RPG/dungeon/aventure :
  - core    : setup, game loop, états
  - player  : joueur, stats, inventaire
  - world   : niveau, ennemis, IA
  - ui      : HUD, dialogues, menus

Réponds avec ce JSON :
{{
  "modules": [
    {{
      "nom": "core",
      "description": "DOMContentLoaded, canvas, game loop, machine à états, inputs",
      "taille_max": 7000,
      "fonctions_exposees": ["init", "gameLoop", "setState"],
      "variables_requises": [],
      "variables_ecrites": ["gameState", "score", "canvas", "ctx", "lastTime", "keys"]
    }},
    ...
  ],
  "variables_globales": ["gameState", "score", "canvas", "ctx", "player", "enemies", "lastTime", "keys"],
  "variables_init": {{
    "gameState": "'menu'",
    "score": "0",
    "enemies": "[]"
  }},
  "ordre_execution": ["core", "entities", "ui"],
  "startup_code": "init();"
}}

IMPORTANT : Génère EXACTEMENT 3 modules pour un jeu simple, 4 pour un jeu moyen, 5 maximum pour un jeu complexe."""

    raw = _call(prompt)
    arch = _parse_architecture(raw, technologie)

    phase1_log.agent_done("Architecte", f"{len(arch.modules)} modules définis : {arch.module_names()}")
    return arch


def _parse_architecture(raw: dict, technologie: str) -> ModuleArchitecture:
    if not raw or not isinstance(raw, dict):
        return _fallback_architecture(technologie)

    modules = raw.get("modules", [])
    if not modules or not isinstance(modules, list):
        return _fallback_architecture(technologie)

    # Validation et nettoyage des modules
    modules_valides = []
    for m in modules:
        if not isinstance(m, dict) or not m.get("nom"):
            continue
        modules_valides.append({
            "nom": m.get("nom", ""),
            "description": m.get("description", ""),
            "taille_max": min(int(m.get("taille_max", 7000)), 8000),
            "fonctions_exposees": m.get("fonctions_exposees", []),
            "variables_requises": m.get("variables_requises", []),
            "variables_ecrites": m.get("variables_ecrites", []),
        })

    if not modules_valides:
        return _fallback_architecture(technologie)

    arch = ModuleArchitecture(
        modules=modules_valides,
        variables_globales=raw.get("variables_globales", []),
        variables_init=raw.get("variables_init", {}),
        ordre_execution=raw.get("ordre_execution", [m["nom"] for m in modules_valides]),
        startup_code=raw.get("startup_code", "init(); requestAnimationFrame(gameLoop);"),
        technologie=technologie,
    )

    # S'assurer que l'ordre d'exécution couvre tous les modules
    noms = {m["nom"] for m in modules_valides}
    manquants = noms - set(arch.ordre_execution)
    arch.ordre_execution.extend(list(manquants))

    return arch


def _fallback_architecture(technologie: str) -> ModuleArchitecture:
    """Architecture minimale de fallback si l'agent échoue."""
    phase1_log.warning("Architecte fallback — architecture minimale utilisée")
    if technologie == "threejs":
        modules = [
            {"nom": "core", "description": "Variables globales, Three.js setup, game loop", "taille_max": 8000,
             "fonctions_exposees": ["init", "gameLoop"], "variables_requises": [],
             "variables_ecrites": ["scene", "camera", "renderer", "gameState", "score", "clock"]},
            {"nom": "player", "description": "Entité joueur 3D", "taille_max": 7000,
             "fonctions_exposees": ["createPlayer", "updatePlayer"], "variables_requises": ["scene", "camera"],
             "variables_ecrites": ["player", "playerVelocity"]},
            {"nom": "world", "description": "Monde 3D, obstacles, environnement", "taille_max": 7000,
             "fonctions_exposees": ["createWorld", "updateWorld"], "variables_requises": ["scene"],
             "variables_ecrites": ["obstacles", "collectibles"]},
            {"nom": "ui", "description": "HUD HTML overlay, menus, game over", "taille_max": 5000,
             "fonctions_exposees": ["showMenu", "showHUD", "showGameOver", "updateScore"],
             "variables_requises": ["score", "gameState"], "variables_ecrites": []},
        ]
        return ModuleArchitecture(
            modules=modules,
            variables_globales=["scene", "camera", "renderer", "gameState", "score", "clock", "player", "obstacles"],
            variables_init={"gameState": "'menu'", "score": "0", "obstacles": "[]"},
            ordre_execution=["core", "player", "world", "ui"],
            startup_code="init(); requestAnimationFrame(gameLoop);",
            technologie="threejs",
        )
    else:
        modules = [
            {"nom": "core", "description": "Variables globales, canvas, game loop, machine à états", "taille_max": 7000,
             "fonctions_exposees": ["init", "gameLoop", "setState"], "variables_requises": [],
             "variables_ecrites": ["canvas", "ctx", "gameState", "score", "lastTime", "keys"]},
            {"nom": "player", "description": "Entité joueur, mouvements, inputs", "taille_max": 7000,
             "fonctions_exposees": ["createPlayer", "updatePlayer", "drawPlayer"],
             "variables_requises": ["canvas", "ctx", "keys"], "variables_ecrites": ["player"]},
            {"nom": "enemies", "description": "Entités ennemies, spawning, IA", "taille_max": 7000,
             "fonctions_exposees": ["spawnEnemy", "updateEnemies", "drawEnemies"],
             "variables_requises": ["canvas", "ctx"], "variables_ecrites": ["enemies"]},
            {"nom": "physics", "description": "Détection de collisions, physique", "taille_max": 5000,
             "fonctions_exposees": ["checkCollisions", "rectIntersect"],
             "variables_requises": ["player", "enemies"], "variables_ecrites": []},
            {"nom": "ui", "description": "HUD, menus, écrans, score", "taille_max": 5000,
             "fonctions_exposees": ["drawHUD", "drawMenu", "drawGameOver"],
             "variables_requises": ["ctx", "score", "gameState"], "variables_ecrites": []},
        ]
        return ModuleArchitecture(
            modules=modules,
            variables_globales=["canvas", "ctx", "gameState", "score", "lastTime", "keys", "player", "enemies"],
            variables_init={"gameState": "'menu'", "score": "0", "enemies": "[]", "particles": "[]"},
            ordre_execution=["core", "player", "enemies", "physics", "ui"],
            startup_code="init(); requestAnimationFrame(gameLoop);",
            technologie="canvas2d",
        )


@with_fallback(None)
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.3, system_instruction=SYSTEM)

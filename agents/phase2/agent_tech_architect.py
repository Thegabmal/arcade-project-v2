"""
Agent Tech Architect — Phase 2
Defines the technical architecture of the game:
physics, rendering, state management, inputs, optimizations.
Adapts technical choices to the genre and complexity of the game.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile
from logger import phase2_log

SYSTEM = """You are an engineer specialized in HTML5 JavaScript game development.
You define precise technical architectures, adapted to the genre and achievable in a single HTML file.
For 2D games you use Canvas 2D API. For 3D games you use Three.js r160 via CDN.

3D TECHNICAL CONSTRAINTS (Three.js r160):
- All code inside document.addEventListener('DOMContentLoaded', function() { ... })
- THREE.WebGLRenderer + renderer.shadowMap.enabled = true
- THREE.Clock for delta time (clock.getDelta(), capped at 0.05)
- AmbientLight (intensity 0.4-0.5) + DirectionalLight (intensity 0.8-1.0) mandatory
- Collisions via THREE.Box3.setFromObject() + box.intersectsBox()
- Entities = { mesh: THREE.Mesh, hp, speed, active, box: new THREE.Box3() }
- HUD = HTML divs positioned fixed over the Three.js canvas (never canvas 2D overlay)
- Restart = scene.remove() for each mesh + reset arrays (.length = 0)
- Particles = THREE.Points with BufferGeometry and PointsMaterial
- NEVER data:URI for textures

CAMERA TYPES by genre:
- FPS: PerspectiveCamera(75, ...) + pointer lock + pitch/yaw
- TPS/3D platformer: camera follows player with lerp, lookAt(player.position)
- Top-down: camera.position.set(0, 20, 0); camera.lookAt(sceneCenter)
- Fixed/isometric: fixed angled camera, no movement

You respond ONLY in valid JSON."""


def run(genre_profile: GenreProfile, gdd: dict) -> dict:
    phase2_log.agent_start("Tech Architect", f"Architecture pour {genre_profile.genre_principal}")

    # Détecter si le jeu doit être en 3D
    _sg = (genre_profile.sous_genre or "").lower()
    _sv = (genre_profile.style_visuel or "").lower()
    _pu = (genre_profile.prompt_utilisateur_original or "").lower()
    est_3d = (
        genre_profile.technologie_rendu == "threejs"
        or "3d" in _sv
        or "3d" in _sg
        or "3d" in _pu
        or "three" in _pu
        or "fps" in _sg
        or "first-person" in _sg
    )
    techno_hint = (
        "three.js via CDN (https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js)"
        if est_3d else "HTML5 Canvas 2D API, JavaScript vanilla"
    )

    prompt = f"""Définis l'architecture technique complète pour ce jeu HTML5.

GENRE : {genre_profile.genre_principal} / {genre_profile.sous_genre}
TITRE : {gdd.get('titre', '?')}
CONCEPT : {gdd.get('concept', '')}
NOTES TECHNIQUES DU GENRE : {genre_profile.notes_techniques}
PROMPT TECHNIQUE : {genre_profile.prompt_technique}
MODE 3D : {"OUI — utiliser Three.js" if est_3d else "NON — Canvas 2D"}

SYSTÈMES DU JEU :
{json.dumps(gdd.get('systemes_principaux', []), ensure_ascii=False)}

CONTRAINTES :
- Un seul fichier HTML (tout inline)
- Technologie de rendu : {techno_hint}
- Doit fonctionner dans un navigateur moderne sans serveur
- {"Three.js r160 via CDN obligatoire — tout le code dans DOMContentLoaded" if est_3d else "Canvas 2D API vanilla — pas de bibliothèques externes"}

Définis précisément :

1. GAME LOOP : comment structurer la boucle de jeu (requestAnimationFrame, delta time, etc.)
2. STATE MACHINE : les états du jeu et transitions
3. PHYSIQUE : gravité, collisions, vélocité — adapté au genre
4. RENDU : layers de rendu, caméra, effets, optimisations
5. INPUTS : clavier, souris, mobile (touch) selon le genre
6. ENTITÉS : structure des objets de jeu (joueur, ennemis, etc.)
7. PERFORMANCE : optimisations importantes pour ce genre
8. ARCHITECTURE GLOBALE : organisation du code JS recommandée

Réponds en JSON :
{{
  "game_loop": {{
    "pattern": "requestAnimationFrame avec delta time",
    "target_fps": 60,
    "delta_time": true,
    "description": "..."
  }},
  "state_machine": {{
    "etats": ["menu", "playing", "paused", "gameover", "..."],
    "transitions": [{{"de": "menu", "vers": "playing", "trigger": "appui touche"}}],
    "gestion": "variable globale gameState"
  }},
  "physique": {{
    "gravite": true,
    "valeur_gravite": 0.5,
    "collisions": "AABB / cercle / pixel-perfect",
    "velocite": true,
    "friction": false,
    "description": "..."
  }},
  "rendu": {{
    "layers": ["background", "entities", "ui"],
    "camera": "statique / suivante / libre",
    "effets": ["parallax", "particles", "screen shake", "..."],
    "canvas_size": {{"width": 800, "height": 600}},
    "responsive": true
  }},
  "inputs": {{
    "clavier": {{"fleches": true, "wasd": true, "espace": true, "autres": []}},
    "souris": false,
    "touch": true,
    "description": "..."
  }},
  "entites": [
    {{
      "nom": "Player",
      "proprietes": ["x", "y", "width", "height", "vitesse", "vie"],
      "methodes": ["update(dt)", "draw(ctx)", "handleInput()"]
    }}
  ],
  "performance": {{
    "object_pooling": false,
    "culling": false,
    "optimisations": ["...", "..."]
  }},
  "architecture_code": {{
    "organisation": "description de l'organisation du code",
    "variables_globales": ["gameState", "score", "..."],
    "fonctions_cles": ["init()", "gameLoop()", "update(dt)", "draw()", "handleInput()"],
    "patterns": ["game loop pattern", "object pooling si nécessaire", "..."]
  }},
  "technologie_rendu": "canvas2d",
  "recommandations_specifiques": "Conseils techniques spécifiques à ce genre",
  "camera_type": "fps | tps | top-down | fixed | isometrique (3D seulement)",
  "collision_strategy": "AABB/Box3 (3D), cercle ou rect (2D)",
  "entity_pattern": "description du pattern objet+mesh ou objet+coords pour les entités"
}}"""

    result = _call(prompt)
    # Forcer la technologie si 3D détecté
    if est_3d:
        result["technologie_rendu"] = "threejs"
    elif "technologie_rendu" not in result:
        result["technologie_rendu"] = "canvas2d"
    phase2_log.agent_done("Tech Architect", f"Rendu: {result.get('technologie_rendu', 'canvas2d')}, Camera: {result.get('rendu', {}).get('camera', '?')}")
    return result


@with_fallback({
    "game_loop": {"pattern": "requestAnimationFrame", "target_fps": 60, "delta_time": True},
    "state_machine": {"etats": ["menu", "playing", "gameover"]},
    "physique": {"gravite": False, "collisions": "AABB"},
    "rendu": {"layers": ["background", "entities", "ui"], "camera": "statique"},
    "inputs": {"clavier": {"fleches": True, "wasd": True, "espace": True}},
    "entites": [],
    "performance": {"optimisations": []},
    "architecture_code": {"fonctions_cles": ["init", "gameLoop", "update", "draw"]},
})
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.3, system_instruction=SYSTEM, max_tokens=32000)

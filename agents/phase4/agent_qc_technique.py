"""
Agent QC Technique — Phase 4
Évalue le code sur des critères techniques adaptatifs au genre.
Les critères viennent du GenreProfile (générés en Phase 1).
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, EvaluationResult
from logger import phase4_log

SYSTEM_2D = """Tu es un expert en développement de jeux HTML5 Canvas/JavaScript. Tu analyses du code
avec précision et objectivité. Tu identifies les forces et faiblesses techniques.
Tu réponds UNIQUEMENT en JSON valide."""

SYSTEM_3D = """Tu es un expert en développement de jeux 3D web avec Three.js. Tu analyses du code
Three.js/WebGL avec précision. Tu connais les patterns Three.js : Scene, Camera, Renderer, Clock,
géométries, matériaux, éclairage, collisions 3D. Tu réponds UNIQUEMENT en JSON valide."""

CRITERES_UNIVERSELS_2D = """RUBRIQUE DE SCORE (guide ton évaluation — sois précis et sévère) :
- 0-3 : Jeu non fonctionnel (crash, écran noir, stub vide, aucune logique de jeu)
- 4-5 : Jeu basique qui tourne mais sans profondeur (1 type d'ennemi, pas de boss, pas de particules)
- 6   : Correct — core loop fonctionnelle, quelques features mais manque de systèmes riches
- 7   : Bon — code propre, 2-3 types d'ennemis, boss ou système de vagues, collisions correctes
- 8   : Très bon — boss avec phases, combo/power-ups/particules implémentés, restart propre, highscore
- 9   : Excellent — tous les systèmes du genre présents, polish visible (shake, glow, floatTexts, transitions)
- 10  : Exceptionnel (réserve pour un jeu vraiment remarquable — rare)

Critères BLOQUANTS — pénalité sévère si absent (jeu non fonctionnel) :
- DOMContentLoaded wrappant TOUT le code (canvas récupéré après le DOM)
- requestAnimationFrame pour la game loop (pas setInterval ni setTimeout)
- Delta time calculé et utilisé dans les mouvements (pas de vitesses fixes)
- Canvas récupéré via getElementById DANS le callback DOMContentLoaded
- Pas de .clear() sur des tableaux (TypeError) — utiliser .length = 0
- LOOP VAR INIT : `for (let i = arr.length-1; i >= 0; i--)` → corps commence par `const X = arr[i]`
- FOR-OF SPLICE : `for (const x of arr)` ne doit JAMAIS contenir `arr.splice()`
- CONST REASSIGNMENT : `const score = 0` puis `score += 10` → TypeError — scalaires mutables = `let`
- DT PASSING : fonctions qui utilisent `dt` DOIVENT l'avoir en paramètre (updateEnemies, updateBoss, etc.)
- `dist` calculée AVANT d'être utilisée dans if(dist < ...) — pas de variable tombée du ciel
- PAS d'eval(), window.__devPatch, new Function() en production
- Fonctions clés NON-STUB : updatePlayer(), updateEnemies(), checkCollisions() avec corps réel (pas juste des commentaires)
- Menu démarrable : SPACE ou Enter → gameState = 'playing'
- Initialisation au démarrage : initGame() appelle spawnEnemies()/generateLevel() — pas d'arrays vides

Critères QUALITÉ DE BASE (fondamentaux — pénalité si absent) :
- Machine à états propre : gameState ∈ {menu, playing, paused, gameover} utilisé partout
- Restart complet sans location.reload() — toutes les variables remises à zéro
- Collisions fonctionnelles (AABB ou distance) — pas de collisions fantômes ni manquées
- Score + highscore en localStorage — affiché sur menu ET en jeu
- Canvas responsive (window.innerWidth/innerHeight)
- Objet keys{} cohérent avec les mêmes noms partout (eviter keys['ArrowLeft'] vs keys.left)

Critères PROFONDEUR GAMEPLAY (impact majeur sur le score — ce qui distingue un bon jeu) :
- VARIÉTÉ ENNEMIS : ≥ 3 types d'ennemis distincts (comportements différents, pas juste des recolors) → +1pt
- BOSS SYSTEM : boss avec HP élevé, pattern d'attaque distinct, ET ≥ 2 phases (HP% seuils) → +1pt
- SYSTÈME DE VAGUES : difficulté progressive (vitesse/count/types selon wave) → +0.5pt
- POWER-UPS : ≥ 2 types collectables avec effets distincts (durée, activation, visuel) → +0.5pt
- COMBO/MULTIPLICATEUR : système combo (kills consecutifs → score multiplié) → +0.5pt
- PARTICULES : spawnExplosion/spawnParticles + updateParticles() réellement appelé → +0.5pt
- FEEDBACK VISUEL RICHE : screen shake (triggerShake), floating texts (spawnFloatText), flash overlay → +0.5pt
- PROGRESSION JOUEUR : XP/niveau OU upgrade OU déblocage de capacité au fil du jeu → +0.5pt

Critères DUNGEON/RPG (si le genre est RPG, dungeon, aventure — vérifier impérativement) :
- Knockback ennemi : les ennemis reçoivent une impulsion quand frappés ET ne traversent pas les murs (knockbackVX/VY avec stop mural)
- Contraste visuel : sol clair vs mur sombre (différence perceptible), ennemis de couleur différente du sol
- Salle du boss rendue visible : BOSS_WALL pas noir pur, sol de la salle boss distinct
- Couloirs ≥ 3 tuiles de large : vérifier dans la génération procédurale que les corridors ont une largeur ≥ 3
- Loot varié : les coffres utilisent une loot table avec ≥ 4 types d'items différents (rollLoot / LOOT_TABLE)
- Level up impactant : checkLevelUp() augmente HP max d'au moins 15% + soin complet + floating text avec les gains
- Balance vitesses : speed ennemi normal ≤ 90% vitesse joueur — vérifier les valeurs numériques
- Textes lisibles : font ≥ 7px en pixel art, ≥ 13px en canvas plein écran
- Callbacks de registre avec optional chaining : ENEMY_TYPES[x].onAttack?.() pas onAttack() — vérifier tous les appels de méthodes sur des objets-type
- Timers initialisés : tout xyzTimer utilisé dans updateBoss/updateEnemy doit être initialisé dans createEnemy/spawnBoss (ex: cloneTimer, summonTimer, teleportTimer)
- Pas de double const/let dans la même fonction : chercher deux déclarations du même nom dans generateDungeon, update, draw...
- Boss spawn dans generateDungeon() : pas de spawn lazy conditionnel qui peut rater
- Pas de calcul lourd dans draw()/update() : drawMap() itère seulement sur tuiles visibles (frustum culling)
- Screen shake dosé : triggerShake mag ≤ 2 sur dégâts normaux, ≥ 6 seulement sur mort/boss transition
- Animations d'attaque : hero.attackFlash ou arc de balayage visible lors d'une attaque
- Cooldown compétence affiché : barre ou timer visible dans le HUD pour chaque compétence à cooldown
- Source de dégâts boss UNIQUE : les dégâts du boss viennent soit du check de collision soit de onAttack — PAS des deux (double dégât = mort instantanée)
- Stats boss équilibrées : boss.attack ≤ 15% maxHP joueur, boss.attackRadius ≤ TILE_SIZE, boss.speed phase1 ≤ vitesse joueur * 0.5
- Recul boss post-attaque : boss._recoilTimer > 0 → boss s'éloigne 0.6–1.0s après chaque hit (fenêtre d'évasion pour le joueur)
- Visuel boss distinctif : aura pulsante (arc semi-transparent animé), indicateur ★ BOSS ★ au-dessus, mini barre de vie sur le sprite, sizeFactor ≥ 2.0"""

CRITERES_UNIVERSELS_3D = """Critères BLOQUANTS (erreur = jeu non fonctionnel) :
- DOMContentLoaded wrappant tout le code Three.js (JAMAIS THREE.* au top-level)
- THREE.WebGLRenderer créé et ajouté au body (document.body.appendChild(renderer.domElement))
- AmbientLight présent (sinon tout noir)
- DirectionalLight présent (sinon pas d'ombres/relief)
- THREE.Clock utilisé pour le delta time (clock.getDelta(), capped à 0.05)
- requestAnimationFrame pour la game loop — gameLoop() lancé immédiatement dans DOMContentLoaded
- scene.background défini (Color ou Texture) — sinon fond transparent
- Pas de .clear() sur des tableaux — utiliser .length = 0
- scene.remove(mesh) appelé à la suppression d'entités (sinon memory leak)

Critères QUALITÉ (impact sur le score) :
- Collisions 3D via THREE.Box3.setFromObject() + intersectsBox() (pas juste distance-based)
- HUD HTML overlay (divs fixed par-dessus le canvas — pas de canvas 2D)
- Restart propre : scene.remove() pour tous les meshes + arrays.length = 0 + reset vars
- Canvas responsive : window.addEventListener('resize') avec camera.aspect + renderer.setSize
- Meilleur score en localStorage
- Au moins 3 géométries Three.js distinctes (BoxGeometry, SphereGeometry, CylinderGeometry...)
- MeshPhongMaterial ou MeshStandardMaterial (pas uniquement MeshBasicMaterial)
- Particules Three.js (THREE.Points) ou au moins un effet visuel dynamique
- renderer.shadowMap.enabled + castShadow/receiveShadow sur les objets principaux"""


def _detect_orphan_functions(code: str) -> list[str]:
    """
    F1 : Détecte les fonctions définies mais jamais appelées NULLE PART dans le code.
    Recherche fn( dans l'intégralité du code — couvre forEach/map/for loops, callbacks, etc.
    Retourne une liste de noms de fonctions orphelines.
    """
    import re
    # Extraire tous les noms de fonctions définies
    defined = set(re.findall(r'function\s+([a-zA-Z_$][\w$]*)\s*\(', code))
    # Ignorer les fonctions built-in et de structure (M3 : liste étendue)
    ignore = {
        'init', 'gameLoop', 'animate', 'loop', 'tick', 'render', 'main',
        'DOMContentLoaded', 'onload', 'onclick', 'onkeydown', 'onkeyup',
        'addEventListener', 'removeEventListener',
        # Fonctions canvas/web standard
        'requestAnimationFrame', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        # Handlers événements courants
        'onmousedown', 'onmouseup', 'onmousemove', 'ontouchstart', 'ontouchmove', 'ontouchend',
        'onresize', 'onblur', 'onfocus', 'oncontextmenu',
        # Fonctions de structure communes (peuvent être appelées indirectement)
        'update', 'draw', 'start', 'stop', 'pause', 'resume', 'reset', 'restart',
        'setup', 'preload', 'create', 'destroy',
    }
    candidates = defined - ignore
    orphans = []
    for fn in candidates:
        # M3 : Recherche fn( dans TOUT le code (pas seulement gameLoop)
        # — couvre forEach, map, for-loops, callbacks, appels imbriqués
        call_pattern = re.compile(r'\b' + re.escape(fn) + r'\s*\(')
        def_pattern = re.compile(r'function\s+' + re.escape(fn) + r'\s*\(')
        all_occurrences = len(call_pattern.findall(code))
        definitions = len(def_pattern.findall(code))
        calls = all_occurrences - definitions
        if calls == 0:
            orphans.append(fn)
    return orphans


def run(code: str, genre_profile: GenreProfile) -> EvaluationResult:
    est_3d = genre_profile.technologie_rendu == "threejs"
    phase4_log.agent_start("QC Technique", f"Analyse technique {'Three.js 3D' if est_3d else 'Canvas 2D'}")

    criteres = genre_profile.criteres_qc_technique
    criteres_str = json.dumps(criteres, ensure_ascii=False) if criteres else "critères standards"
    criteres_universels = CRITERES_UNIVERSELS_3D if est_3d else CRITERES_UNIVERSELS_2D
    system = SYSTEM_3D if est_3d else SYSTEM_2D
    techno_label = "Three.js (3D)" if est_3d else "Canvas 2D"

    # F4 : Extraction code complète 40KB (au lieu de 24KB tronqué)
    from utils import extract_js_sample
    code_extrait = extract_js_sample(code, 40000)

    # F1 : Détecter les fonctions orphelines avant appel LLM
    _orphans = _detect_orphan_functions(code)
    _orphan_hint = ""
    if _orphans:
        phase4_log.warning(f"F1 : {len(_orphans)} fonction(s) orpheline(s) : {', '.join(_orphans[:6])}")
        _orphan_hint = (
            f"\n\nFONCTIONS ORPHELINES DÉTECTÉES (définies mais jamais appelées — à signaler comme issues critiques) :\n"
            + "\n".join(f"  - {fn}()" for fn in _orphans[:10])
            + "\nCes fonctions ne contribuent JAMAIS au jeu. Ajouter une issue critique pour chacune."
        )

    prompt = f"""Analyse technique ce code de jeu HTML5 ({techno_label}) pour un {genre_profile.genre_principal}.

CODE (extrait) :
```html
{code_extrait}
```

CRITÈRES SPÉCIFIQUES AU GENRE {genre_profile.genre_principal.upper()} :
{criteres_str}

CRITÈRES TECHNIQUES {techno_label.upper()} à vérifier :
{criteres_universels}{_orphan_hint}

Pour chaque critère, donne un score de 0.0 à son poids max et un commentaire.

Réponds en JSON :
{{
  "criteres_evalues": [
    {{
      "nom": "...",
      "score_obtenu": 1.5,
      "score_max": 1.5,
      "present": true,
      "commentaire": "..."
    }}
  ],
  "issues": [
    {{
      "severite": "critique / majeur / mineur",
      "description": "Description précise : quelle variable/pattern est cassé",
      "fonction_concernee": "nom exact de la fonction JS concernée (ex: updateEnemies, loadGame, checkCollisions)",
      "pattern_a_chercher": "extrait de code exact à trouver (ex: 'for (let i = 0; i < enemies.length' ou 'localStorage.getItem')",
      "suggestion": "correction concrète en 1-2 lignes"
    }}
  ],
  "points_forts": ["...", "..."],
  "score_total": 8.5,
  "commentaire_global": "..."
}}"""

    result = _call(prompt, system)
    ev = _parse(result, "QC Technique")

    # F1 : Injecter les fonctions orphelines comme issues critiques automatiques
    if _orphans:
        for _fn in _orphans[:5]:
            ev.issues.insert(0, {
                "severite": "critique",
                "description": f"F1 : fonction orpheline '{_fn}()' — définie mais jamais appelée depuis gameLoop/update/draw",
                "fonction_concernee": _fn,
                "pattern_a_chercher": f"function {_fn}(",
                "suggestion": f"Appeler {_fn}() dans gameLoop() ou dans la fonction update/draw appropriée"
            })

    return ev


def _parse(result: dict, agent_name: str) -> EvaluationResult:
    ev = EvaluationResult(agent_name=agent_name)
    ev.criteres = result.get("criteres_evalues", [])
    ev.issues = result.get("issues", [])
    ev.points_forts = result.get("points_forts", [])
    ev.score = float(result.get("score_total", 5.0))
    ev.commentaire_global = result.get("commentaire_global", "")
    ev.score = max(0.0, min(10.0, ev.score))

    phase4_log.score("QC Technique", ev.score)
    critiques = [i for i in ev.issues if i.get("severite") == "critique"]
    if critiques:
        phase4_log.warning(f"{len(critiques)} issue(s) critique(s) détectée(s)")
    return ev


# _sample_code remplacé par utils.extract_js_sample (extraction JS + échantillonnage)

@with_fallback({
    "criteres_evalues": [],
    "issues": [{"severite": "majeur", "description": "Analyse QC technique échouée", "suggestion": "Réessayer"}],
    "points_forts": [],
    "score_total": 5.0,
    "commentaire_global": "Analyse indisponible"
})
def _call(prompt: str, system: str = SYSTEM_2D) -> dict:
    return call_gemini_json(prompt, temperature=0.2, system_instruction=system)

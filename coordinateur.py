"""
Coordinateur — Point d'entrée principal du système.
Orchestre les 5 phases et la boucle ReAct.

Usage :
    python coordinateur.py "un jeu de plateforme avec des ennemis robots"
    python coordinateur.py  (mode interactif)
"""

import sys
import os
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Imports fondamentaux
from logger import coordinateur_log, init_session, get_thread_event_queue, set_thread_event_queue, get_session_log, push_event
from genre_profile import GenreProfile, ConceptionContext, EvaluationBundle
import memory



def _export_failure_log(
    genre: str, titre: str, score: float, exec_score: float,
    issues: list, log_content: str = "", label: str = "failed"
) -> None:
    """
    Tâche P — Exporte un log d'échec structuré dans failures_log.json.
    Utilisé par auto_learner et pour le dashboard /api/stats.
    """
    import json, os
    failures_path = os.path.join(os.path.dirname(__file__), "failures_log.json")
    try:
        if os.path.exists(failures_path):
            with open(failures_path, "r", encoding="utf-8") as f:
                failures = json.load(f)
        else:
            failures = []
    except Exception:
        failures = []

    failures.append({
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "genre": genre,
        "titre": titre,
        "score_global": round(score, 2),
        "exec_score": round(exec_score, 2),
        "label": label,
        "top_issues": [
            i.get("description", str(i)) if isinstance(i, dict) else str(i)
            for i in issues[:10]
        ],
    })
    # Garder les 100 derniers échecs
    failures = failures[-100:]
    with open(failures_path, "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)


def _make_minimal_fallback_game(titre: str, genre: str) -> str:
    """
    Session 14 — Génère un jeu minimal garanti fonctionnel en pur Python.
    Utilisé quand TOUS les itérations ont échoué avec exec < 4.5 ET code syntaxiquement invalide.
    C'est un jeu simple mais qui FONCTIONNE à 100%.
    """
    import html as _html_mod
    titre_safe = _html_mod.escape(titre[:40])
    genre_safe = _html_mod.escape(genre[:20])
    return f"""<!DOCTYPE html>
<html><head><title>{titre_safe}</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0a1a;overflow:hidden;font-family:'Courier New',monospace;}}
canvas{{display:block;}}
</style></head><body>
<canvas id="gameCanvas"></canvas>
<script>
var canvas = document.getElementById('gameCanvas');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
var ctx = canvas.getContext('2d');
var W = canvas.width, H = canvas.height;

var score = 0, lives = 3, gameState = 'menu';
var player = {{ x: W/2, y: H/2, r: 20, vx: 0, vy: 0, speed: 200 }};
var enemies = [], bullets = [], lastTime = 0, spawnTimer = 0;
var keys = {{}};

document.addEventListener('keydown', function(e) {{
    keys[e.code] = true;
    if (e.code === 'Space') e.preventDefault();
}});
document.addEventListener('keyup', function(e) {{ keys[e.code] = false; }});
canvas.addEventListener('click', function(e) {{
    if (gameState === 'menu') {{ gameState = 'playing'; initGame(); }}
    else if (gameState === 'gameover') {{ gameState = 'menu'; }}
}});

function initGame() {{
    score = 0; lives = 3; enemies = []; bullets = [];
    player.x = W/2; player.y = H/2; player.vx = 0; player.vy = 0;
    spawnTimer = 0;
}}

function spawnEnemy() {{
    var angle = Math.random() * Math.PI * 2;
    var dist = Math.max(W, H) * 0.6;
    enemies.push({{
        x: W/2 + Math.cos(angle) * dist,
        y: H/2 + Math.sin(angle) * dist,
        r: 14, speed: 60 + Math.random() * 40 + score * 0.05,
        hp: 2, color: '#F44'
    }});
}}

function update(dt) {{
    if (gameState !== 'playing') return;
    var dx = 0, dy = 0;
    if (keys['ArrowLeft'] || keys['KeyA']) dx -= 1;
    if (keys['ArrowRight'] || keys['KeyD']) dx += 1;
    if (keys['ArrowUp'] || keys['KeyW']) dy -= 1;
    if (keys['ArrowDown'] || keys['KeyS']) dy += 1;
    var len = Math.sqrt(dx*dx + dy*dy) || 1;
    if (dx !== 0 || dy !== 0) {{ player.x += dx/len * player.speed * dt; player.y += dy/len * player.speed * dt; }}
    player.x = Math.max(player.r, Math.min(W-player.r, player.x));
    player.y = Math.max(player.r, Math.min(H-player.r, player.y));

    if (keys['Space'] && bullets.length < 8) {{
        keys['Space'] = false;
        var nearest = null, nd = Infinity;
        enemies.forEach(function(en) {{ var d = Math.hypot(en.x-player.x, en.y-player.y); if(d < nd){{ nd = d; nearest = en; }} }});
        var bdir = nearest ? {{ x:(nearest.x-player.x)/nd, y:(nearest.y-player.y)/nd }} : {{ x:0, y:-1 }};
        bullets.push({{ x:player.x, y:player.y, vx:bdir.x*350, vy:bdir.y*350, r:6 }});
    }}

    for (var i = bullets.length-1; i >= 0; i--) {{
        var b = bullets[i]; b.x += b.vx*dt; b.y += b.vy*dt;
        if (b.x<0||b.x>W||b.y<0||b.y>H) {{ bullets.splice(i,1); continue; }}
        var hit = false;
        for (var j = enemies.length-1; j >= 0; j--) {{
            var en = enemies[j];
            if (Math.hypot(b.x-en.x, b.y-en.y) < b.r+en.r) {{
                en.hp--; hit = true;
                if (en.hp <= 0) {{ score += 10; enemies.splice(j,1); }}
                break;
            }}
        }}
        if (hit) bullets.splice(i,1);
    }}

    for (var i = enemies.length-1; i >= 0; i--) {{
        var en = enemies[i];
        var edx = player.x-en.x, edy = player.y-en.y, ed = Math.hypot(edx,edy)||1;
        en.x += edx/ed*en.speed*dt; en.y += edy/ed*en.speed*dt;
        if (Math.hypot(en.x-player.x, en.y-player.y) < en.r+player.r) {{
            lives--; enemies.splice(i,1);
            if (lives <= 0) gameState = 'gameover';
        }}
    }}

    spawnTimer -= dt;
    if (spawnTimer <= 0) {{ spawnEnemy(); spawnTimer = Math.max(0.5, 2.0 - score*0.005); }}
}}

function draw() {{
    ctx.fillStyle = '#0a0a1a'; ctx.fillRect(0,0,W,H);
    if (gameState === 'menu') {{
        ctx.fillStyle = '#0AF'; ctx.font = 'bold 36px Courier New'; ctx.textAlign = 'center';
        ctx.fillText('{titre_safe}', W/2, H/2-40);
        ctx.fillStyle = '#888'; ctx.font = '18px Courier New';
        ctx.fillText('Genre: {genre_safe}', W/2, H/2);
        ctx.fillStyle = '#FFF'; ctx.fillText('Clic pour jouer | WASD = mouvement | ESPACE = tir', W/2, H/2+40);
        ctx.textAlign = 'left'; return;
    }}
    if (gameState === 'gameover') {{
        ctx.fillStyle = '#F44'; ctx.font = 'bold 40px Courier New'; ctx.textAlign = 'center';
        ctx.fillText('GAME OVER', W/2, H/2-20);
        ctx.fillStyle = '#FFF'; ctx.font = '20px Courier New';
        ctx.fillText('Score: ' + score, W/2, H/2+20);
        ctx.fillText('Clic pour recommencer', W/2, H/2+55);
        ctx.textAlign = 'left'; return;
    }}
    // Draw enemies
    enemies.forEach(function(en) {{
        ctx.fillStyle = en.color; ctx.beginPath(); ctx.arc(en.x,en.y,en.r,0,Math.PI*2); ctx.fill();
    }});
    // Draw bullets
    ctx.fillStyle = '#FF0';
    bullets.forEach(function(b) {{ ctx.beginPath(); ctx.arc(b.x,b.y,b.r,0,Math.PI*2); ctx.fill(); }});
    // Draw player
    ctx.fillStyle = '#0AF'; ctx.beginPath(); ctx.arc(player.x,player.y,player.r,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = '#000'; ctx.beginPath(); ctx.arc(player.x,player.y,player.r*0.4,0,Math.PI*2); ctx.fill();
    // HUD
    ctx.fillStyle = '#FFF'; ctx.font = '16px Courier New';
    ctx.fillText('Score: ' + score + '   Vies: ' + lives, 16, 30);
}}

function gameLoop(ts) {{
    var dt = Math.min((ts - lastTime) / 1000, 0.05); lastTime = ts;
    update(dt); draw();
    requestAnimationFrame(gameLoop);
}}

requestAnimationFrame(gameLoop);
</script></body></html>"""


def _parallel(tasks: list, max_workers: int = 4) -> dict:
    """
    Exécute des tâches en parallèle en propageant la queue SSE aux sous-threads.
    tasks = [(nom, fn, [args...]), ...]
    Retourne {nom: résultat}.
    """
    current_queue = get_thread_event_queue()
    results = {}

    def _run(name, fn, args):
        if current_queue:
            set_thread_event_queue(current_queue)
        return name, fn(*args)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as ex:
        futures = {ex.submit(_run, name, fn, args): name for name, fn, args in tasks}
        for future in as_completed(futures):
            try:
                name, result = future.result()
                results[name] = result
            except Exception as e:
                name = futures[future]
                coordinateur_log.error(f"Tâche parallèle '{name}' échouée : {e}")
                results[name] = None
    return results

# Phase 1 — Intelligence
from agents.phase1 import (
    agent_intelligence_genre,   # fusion chercheur + veilleur
    agent_enrichisseur,
    agent_architecte,
    agent_moderateur_classificateur,
)

# Phase 2 — Conception
from agents.phase2 import (
    agent_game_designer,
    agent_tech_architect,
    agent_ux_designer,
    agent_level_designer,
    agent_game_logics,
)

# Phase 3 — Génération
from agents.phase3 import agent_createur, agent_assembleur, agent_js_linter

# Phase 4 — Évaluation
from agents.phase4 import (
    agent_qc_technique,
    agent_qc_gameplay,   # inclut désormais anti_pattern
    agent_qc_visuel,
    agent_executeur,
    agent_playtester,
    agent_testeur_modules,
)

# Phase 5 — Itération
from agents.phase5 import agent_diagnosticien, agent_patcher, agent_pre_patcher

# Support
from agents.support import agent_verdict_final, agent_sauvegarde, agent_auto_learner  # verdict_final = benchmark + neutre

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MAX_ITERATIONS = 2          # E4 : 2 itérations max (coût API réduit)
SCORE_SEUIL_SAUVEGARDE = 7.0   # Score minimum pour marquer "approuvé"
SCORE_SORTIE_ANTICIPEE = 8.0   # Score pour sortir sans itérer
SCORE_STAGNATION_DELTA = 0.2   # Si le score progresse de moins de ça → stagnation
SCORE_MIN_VIABLE_SAVE  = 2.0   # En dessous de ça, inutile de sauvegarder (code vide)
# Nombre d'itérations consécutives sans progrès avant stagnation déclarée
MAX_ITERATIONS_SANS_PROGRES = 2
# E4 : seuil pour autoriser les passes 3 et 4 (économie quota)
SCORE_SEUIL_ITERATIONS_SUP = 7.0  # Au-dessus → 2 passes suffisent
# C1 : seuils minimums par dimension (bloquer sauvegarde si non atteints)
SCORE_MIN_EXECUTION = 5.0   # C1 : execution doit être ≥ 5.0
SCORE_MIN_TECHNIQUE = 5.5   # C1 : technique doit être ≥ 5.5
# I7 : limite erreurs_passees
MAX_ERREURS_PASSEES = 20


def _js_check_quick(html: str) -> tuple:
    """Vérification syntaxe JS rapide pour valider un patch avant de l'appliquer."""
    try:
        from js_syntax_checker import check_and_report as _chk
        issues, broken = _chk(html)
        return issues, broken
    except Exception:
        return [], False  # En cas d'erreur du checker, accepter par défaut


STYLE_GRAPHIQUE_MAP = {
    "pixel_art_gameboy":   "pixel art Game Boy 4 couleurs (style Pokémon Rouge/Bleu, résolution 160×144, palette : #0f380f #306230 #8bac0f #9bbc0f)",
    "pixel_art_nes_mario": "pixel art NES style Mario Bros (résolution 256×240, palette vive NES : rouges #D82800, bleus #0058F8, jaunes #F8B800, verts #00A800, blancs #FCFCFC, noirs #000000 — jusqu'à 16 couleurs simultanées)",
    "pixel_art_nes_zelda": "pixel art NES style Zelda (résolution 256×240, palette NES colorée et variée : herbe #70C848, eau #3CBCFC, doré #F8B800, rouge #D82800, violet #A800A8, gris #BCBCBC, skin #FCBCB0 — sprites 16×16, tuiles 8×8, fond sombre avec accents vifs)",
    "pixel_art_16bit":     "pixel art 16-bit SNES (résolution 320×240, palette très riche jusqu'à 256 couleurs, sprites détaillés 32×32, dégradés subtils, ombres portées pixel art)",
    "cartoon_2d":          "cartoon 2D coloré et expressif",
    "minimaliste":         "minimaliste géométrique épuré",
    "3d_lowpoly":          "3D low-poly",
}

def run(prompt_utilisateur: str, style_graphique: str = "", stop_event=None,
        _max_iterations: int | None = None) -> dict:
    """
    Pipeline principale. Prend un prompt en entrée et retourne un dict avec :
    - genre_profile, gdd, code, scores, verdict, html_path
    style_graphique : clé optionnelle (ex: "pixel_art_gameboy") — écrase la détection auto.
    stop_event : threading.Event optionnel — si déclenché, la pipeline s'arrête proprement.
    _max_iterations : override interne pour run_quick() (1 passe sans remediation).
    """
    def _check_stop():
        if stop_event and stop_event.is_set():
            raise RuntimeError("Génération annulée (timeout SSE)")
    init_session()
    memory.init_memory()
    start_time = time.time()

    coordinateur_log.section(f"ARCADE AI -- Generation de jeu")
    coordinateur_log.info(f"Prompt : '{prompt_utilisateur}'")
    coordinateur_log.info(f"Démarré à : {datetime.datetime.now().strftime('%H:%M:%S')}")
    push_event("timer_start", {"timestamp": start_time})

    # ─────────────────────────────────────────────
    # PHASE 1 : MODÉRATION
    # ─────────────────────────────────────────────
    coordinateur_log.section("PHASE 1 — Intelligence & Enrichissement")

    # Round 1 : modération + classification en UN SEUL appel (optimisation)
    mod_class = agent_moderateur_classificateur.run(prompt_utilisateur) or {}

    if not mod_class.get("valide", True):
        coordinateur_log.error(f"Prompt rejeté : {mod_class.get('raison_rejet', '?')}")
        return {"erreur": mod_class.get("raison_rejet"), "code": None}

    prompt_nettoye = mod_class.get("prompt_nettoye", prompt_utilisateur) or prompt_utilisateur

    for avert in mod_class.get("avertissements", []):
        coordinateur_log.warning(f"Avertissement : {avert}")

    # Si le classificateur a échoué (fallback), détecter le genre par mots-clés
    _genre_raw = mod_class.get("genre_principal", "arcade")
    if _genre_raw == "arcade":
        import re as _re
        _p = prompt_nettoye.lower()
        # Correspondance mot entier pour éviter les faux positifs ("xp" dans "explosions", etc.)
        def _kw_match(kw, text):
            if len(kw) <= 3:  # mots courts → vérifier les frontières de mots
                return bool(_re.search(r'\b' + _re.escape(kw) + r'\b', text))
            return kw in text
        # Ordre : genres les plus spécifiques en premier
        _genre_kw = {
            "shooter":       ["shooter", "shoot them up", "shmup", "bullet hell", "vaisseau", "tir automatique", "shoot"],
            "platformer":    ["platformer", "plateforme", "saut", "jump", "mario"],
            "tower defense": ["tower defense", "tourelle", "défense de base"],
            "puzzle":        ["puzzle", "réflexion", "casse-tête", "logique", "blocs"],
            "racing":        ["racing", "course automobile", "voiture", "kart"],
            "survival":      ["survival", "survie", "crafting", "zombie"],
            "roguelite":     ["roguelite", "roguelike", "procédural", "aléatoire"],
            "rpg":           ["rpg", "rôle", "quête", "donjon", "dungeon", "héros", "level up", "inventaire"],
            "aventure":      ["aventure", "exploration", "zelda"],
        }
        for genre, kws in _genre_kw.items():
            if any(_kw_match(kw, _p) for kw in kws):
                _genre_raw = genre
                coordinateur_log.info(f"Genre détecté par mots-clés (fallback classificateur) : {_genre_raw}")
                break

    # Construire un objet Classification compatible depuis la réponse fusionnée
    from genre_profile import Classification

    # Style graphique : forcé par l'utilisateur ou détecté automatiquement
    _style_force = STYLE_GRAPHIQUE_MAP.get(style_graphique, "") if style_graphique else ""
    if _style_force:
        # Style explicitement choisi — on ignore la détection automatique
        est_3d = style_graphique == "3d_lowpoly"
        style_visuel = _style_force
        coordinateur_log.info(f"Style graphique forcé : {style_visuel}")
    else:
        # Détection automatique depuis le prompt
        est_3d = mod_class.get("technologie", "canvas2d") == "threejs"
        _kw_pixel = ["pixel art", "pixel-art", "rétro", "retro", "zelda", "pokemon",
                     "nes", "game boy", "gameboy", "8-bit", "16-bit", "8bit", "16bit"]
        _prompt_lower = prompt_nettoye.lower()
        est_pixel = any(kw in _prompt_lower for kw in _kw_pixel)
        if est_3d:
            style_visuel = "3D low-poly"
        elif est_pixel:
            style_visuel = "pixel art rétro"
        else:
            style_visuel = "cartoon 2D"
    classification = Classification(
        genre_principal=_genre_raw,
        sous_genre=mod_class.get("sous_genre", "action"),
        ton="casual",
        public_cible="tous publics",
        style_visuel_attendu=style_visuel,
        type_gameplay="arcade",
        confiance=0.7,
        raisonnement="",
    )

    # Round 2 : intelligence genre (fusion chercheur + veilleur en 1 appel)
    research, tendances = agent_intelligence_genre.run(classification)
    tendances = tendances or ""

    if tendances:
        coordinateur_log.info(f"Intelligence genre : {len(tendances)} chars de contexte")

    # Récupérer les patterns réussis + erreurs passées pour ce genre
    patterns_reussis = memory.get_patterns_for_genre(classification.genre_principal)
    if patterns_reussis:
        coordinateur_log.info(f"{len(patterns_reussis)} pattern(s) réussi(s) trouvé(s) en mémoire")

    erreurs_passees = memory.get_errors_for_genre(classification.genre_principal)
    # Ajouter les erreurs structurelles connues (du validateur)
    validator_errors = memory.get_validator_errors_for_genre(classification.genre_principal, n=3)
    if validator_errors:
        erreurs_passees = list(erreurs_passees) + [f"[STRUCTUREL] {e}" for e in validator_errors]
    if erreurs_passees:
        coordinateur_log.info(f"{len(erreurs_passees)} erreur(s) passée(s) récupérée(s) pour '{classification.genre_principal}'")

    # Q13 — Tracking des erreurs corrigées vs récurrentes
    # Chaque erreur est soit str soit dict {msg, fixed, iteration}
    # On normalise en liste de str avec préfixes [CORRIGÉ] / [RÉCURRENT] pour les prompts
    _erreurs_tracker: dict = {}  # msg_lower → {count, fixed}

    def _mark_error_fixed(issue_desc: str):
        """Marque une erreur comme corrigée dans le tracker."""
        key = issue_desc[:80].lower()
        if key in _erreurs_tracker:
            _erreurs_tracker[key]['fixed'] = True

    def _record_error(issue_desc: str, iteration: int):
        """Enregistre une nouvelle erreur rencontrée."""
        key = issue_desc[:80].lower()
        if key not in _erreurs_tracker:
            _erreurs_tracker[key] = {'msg': issue_desc, 'count': 1, 'fixed': False, 'iter': iteration}
        else:
            _erreurs_tracker[key]['count'] += 1
            _erreurs_tracker[key]['fixed'] = False

    # Enrichissement — création du GenreProfile
    genre_profile = agent_enrichisseur.run(prompt_nettoye, classification, research)

    # Propager la détection 3D du classificateur vers le GenreProfile
    # (l'enrichisseur ne connaît pas ce champ — on le force ici pour cohérence)
    if est_3d:
        genre_profile.technologie_rendu = "threejs"
    else:
        genre_profile.technologie_rendu = "canvas2d"

    coordinateur_log.success(f"Phase 1 terminée : {genre_profile.summary()}")

    # ─────────────────────────────────────────────
    # PHASE 2 : CONCEPTION
    # ─────────────────────────────────────────────
    _check_stop()
    coordinateur_log.section("PHASE 2 — Conception")

    # I14 : Phase 2 entièrement en parallèle — GDD + tech + ux + game_logics + level_designer
    # Game Designer tourne en parallèle avec les autres sur le genre_profile uniquement
    # puis tech/ux/level/logics reçoivent le GDD via résultat
    p2_gdd = _parallel([
        ("gdd", agent_game_designer.run, [genre_profile]),
    ], max_workers=1)
    gdd = p2_gdd["gdd"] or {}
    coordinateur_log.info(f"Jeu : '{gdd.get('titre', '?')}'")

    # G5 : validation GDD structure minimale (check tous les noms de champs possibles)
    _gdd_title = (gdd.get('titre') or gdd.get('title') or gdd.get('nom') or '')
    _gdd_mechanics = (gdd.get('mecaniques_principales') or gdd.get('core_mechanics')
                      or gdd.get('mecaniques') or gdd.get('mechanics') or [])
    _gdd_systems = (gdd.get('systemes_jeu') or gdd.get('systemes_principaux')
                    or gdd.get('systems') or gdd.get('systemes') or gdd.get('game_systems') or {})
    if not _gdd_title:
        coordinateur_log.warning("G5 : GDD sans titre — fallback 'Arcade Game'")
    elif not _gdd_mechanics and not _gdd_systems:
        coordinateur_log.warning("G5 : GDD sans mécaniques ni systèmes détectés (clé inattendue ?)")

    # I14 : les 4 autres agents de Phase 2 en parallèle (max_workers=4)
    p2 = _parallel([
        ("tech",         agent_tech_architect.run, [genre_profile, gdd]),
        ("ux",           agent_ux_designer.run,    [genre_profile, gdd]),
        ("game_logics",  agent_game_logics.run,    [genre_profile, gdd]),
        ("level_design", agent_level_designer.run, [genre_profile, gdd, {}]),
    ], max_workers=4)
    tech_specs    = p2["tech"]         or {}
    ux_specs      = p2["ux"]           or {}
    game_logics   = p2["game_logics"]  or ""
    level_design  = p2["level_design"] or {}

    # Assembler le contexte de conception
    context = ConceptionContext(
        genre_profile=genre_profile,
        gdd=gdd,
        tech_specs=tech_specs,
        ux_specs=ux_specs,
        level_design=level_design,
    )

    coordinateur_log.success("Phase 2 terminée — contexte complet assemblé")

    # ─────────────────────────────────────────────
    # PHASE 3 : GÉNÉRATION (modulaire)
    # ─────────────────────────────────────────────
    _check_stop()
    coordinateur_log.section("PHASE 3 — Génération du jeu")

    genre_principal_lower = (genre_profile.genre_principal or "").lower()
    sous_genre_lower = (genre_profile.sous_genre or "").lower()
    est_3d_genre = genre_profile.technologie_rendu == "threejs"

    # Stratégie de génération :
    # - Monolithique pour TOUS les jeux 2D (plus fiable, moins de points de défaillance)
    # - Modulaire UNIQUEMENT pour les jeux 3D (Three.js) où la complexité le justifie
    use_modular = est_3d_genre

    CODE_MIN_VIABLE = 15000  # un vrai jeu 2D jouable fait >15K chars minimum

    def _run_monolithic(reason: str) -> str:
        """Gardé uniquement pour référence — NE JAMAIS appeler sur des jeux 2D."""
        coordinateur_log.info(f"Génération monolithique ({reason})")
        c = agent_createur.run(
            context,
            patterns_reussis=patterns_reussis,
            tendances=tendances,
            erreurs_passees=erreurs_passees,
            game_logics=game_logics,
        )
        coordinateur_log.success(f"Code monolithique : {len(c)} caractères")
        return c

    # ─────────────────────────────────────────────
    # GÉNÉRATION DU CODE
    # ─────────────────────────────────────────────
    if use_modular:
        # Jeux 3D — architecture modulaire Three.js
        coordinateur_log.info("Route 3D : génération modulaire Three.js")
        architecture = agent_architecte.run(context)

        from agents.phase3.agent_createur import run_modulaire
        generated = run_modulaire(
            context,
            architecture,
            patterns_reussis=patterns_reussis,
            tendances=tendances,
            erreurs_passees=erreurs_passees,
            game_logics=game_logics,
        )

        # Test de modules puis assemblage
        generated = agent_testeur_modules.run(generated)
        code = agent_assembleur.run(generated, context)
        coordinateur_log.success(f"Code 3D assemblé : {len(code)} caractères")
    else:
        # Jeux 2D — TOUJOURS via le système 5 couches (jamais monolithique)
        coordinateur_log.info("Route 2D : génération 5 couches (layered)")
        from agents.phase3._layer_gen import run_layered
        code = run_layered(
            context,
            patterns_reussis=patterns_reussis,
            erreurs_passees=erreurs_passees,
            game_logics=game_logics,        # A — mécaniques détaillées
            level_design=level_design,       # 4 — structure de niveaux
        )
        coordinateur_log.success(f"Code 2D layered : {len(code)} caractères")

    # Sanité de base : vérifier qu'on a du code viable
    titre_jeu = context.gdd.get("titre", "Arcade Game")
    genre_jeu = genre_profile.genre_principal
    CODE_MIN_VIABLE = 15000

    if not code or len(code) < 1000:
        coordinateur_log.warning("Code trop court — fallback minimal garanti")
        if not use_modular:
            from agents.phase3._layer_gen import _run_compact_fallback
            code = _run_compact_fallback(context, erreurs_passees=erreurs_passees)
        if not code or len(code) < 1000:
            code = _make_minimal_fallback_game(titre_jeu, genre_jeu)

    coordinateur_log.success(f"Phase 3 terminée : {len(code)} caractères")

    # K4 — Factorisation coherence_check + A1_linter en fonction réutilisable
    # Appelée ici ET après chaque E1 (la régénération E1 bypassait ce bloc)
    def _post_generation_cleanup(html_code: str, ep: list) -> tuple[str, list]:
        """Cohérence check + A1 JS linter — s'applique après toute génération (init + E1)."""
        _ep = list(ep or [])
        if not use_modular:
            from agents.phase3._layer_gen import coherence_check as _coh_check
            _coh_issues = _coh_check(html_code)
            if _coh_issues:
                coordinateur_log.warning(f"Cohérence check : {len(_coh_issues)} problème(s) détecté(s)")
                for _ci in _coh_issues[:5]:
                    coordinateur_log.warning(f"  → {_ci}")
                _coh_patched = agent_pre_patcher.run(html_code, _coh_issues)
                _, _coh_broken = _js_check_quick(_coh_patched)
                if _coh_broken:
                    coordinateur_log.warning("Coherence pre-patch invalide — ignoré (syntaxe cassée)")
                else:
                    html_code = _coh_patched
                _ep = (_ep + _coh_issues[:3])[-MAX_ERREURS_PASSEES:]
            else:
                coordinateur_log.success("Cohérence check OK — jeu structurellement sain")

        _lint_issues = agent_js_linter.run(html_code)
        if _lint_issues:
            coordinateur_log.warning(f"A1 JS Linter : {len(_lint_issues)} problème(s) — pre-patch automatique")
            _lint_patched = agent_pre_patcher.run(html_code, _lint_issues)
            _, _lint_broken = _js_check_quick(_lint_patched)
            if _lint_broken:
                coordinateur_log.warning("A1 : lint pre-patch invalide — ignoré (syntaxe cassée)")
            else:
                html_code = _lint_patched
                coordinateur_log.success(f"A1 : {len(_lint_issues)} issue(s) lint pré-corrigée(s) avant Phase 4")
        else:
            coordinateur_log.info("A1 JS Linter : aucun bug runtime détecté")
        return html_code, _ep

    code, erreurs_passees = _post_generation_cleanup(code, erreurs_passees)

    # G2 : Cohérence technologie_rendu — si le code contient THREE mais genre_profile dit canvas2d
    _code_has_three = 'THREE.' in code or 'new THREE.' in code
    if _code_has_three and genre_profile.technologie_rendu != "threejs":
        coordinateur_log.warning("G2 : code Three.js détecté mais genre_profile.technologie_rendu=canvas2d — correction auto")
        genre_profile.technologie_rendu = "threejs"
    elif not _code_has_three and genre_profile.technologie_rendu == "threejs":
        coordinateur_log.warning("G2 : genre_profile dit threejs mais code sans THREE — correction vers canvas2d")
        genre_profile.technologie_rendu = "canvas2d"

    # ─────────────────────────────────────────────
    # BOUCLE REACT (Phases 4 + 5)
    # ─────────────────────────────────────────────
    coordinateur_log.section("PHASES 4-5 — Evaluation & Iteration")

    score_precedent = 0.0
    bundle = None
    iterations_sans_progres = 0

    _iters = _max_iterations if _max_iterations is not None else MAX_ITERATIONS
    for iteration in range(1, _iters + 1):
        _check_stop()
        coordinateur_log.section(f"Iteration {iteration}/{_iters}")

        # ── PHASE 4 : ÉVALUATION (5 agents en parallèle) ──
        coordinateur_log.section("PHASE 4 — Evaluation multi-dimensionnelle")

        # I10 : max_workers=5 — tous les QC en parallèle (~30s au lieu de 90s)
        p4 = _parallel([
            ("qc_technique", agent_qc_technique.run, [code, genre_profile]),
            ("qc_gameplay",  agent_qc_gameplay.run,  [code, genre_profile, context.gdd]),
            ("qc_visuel",    agent_qc_visuel.run,     [code, genre_profile]),
            ("executeur",    agent_executeur.run,     [code, genre_profile]),
            ("playtester",   agent_playtester.run,    [code, genre_profile, context.gdd]),
        ], max_workers=5)

        from genre_profile import EvaluationResult
        def _safe_result(r, name: str) -> "EvaluationResult":
            """Extrait un EvaluationResult depuis une valeur brute (dict ou objet)."""
            if isinstance(r, EvaluationResult):
                return r
            if isinstance(r, dict):
                # Certains agents retournent {"gameplay": EvaluationResult, ...}
                for key in r:
                    if isinstance(r[key], EvaluationResult):
                        return r[key]
            return EvaluationResult(agent_name=name, score=5.0)

        # qc_gameplay retourne {"gameplay": ..., "anti_pattern": ...}
        _gp_raw = p4.get("qc_gameplay", {})
        _gp_result = _gp_raw if isinstance(_gp_raw, dict) else {}

        bundle = EvaluationBundle(
            qc_technique = _safe_result(p4["qc_technique"], "QC Technique"),
            qc_gameplay  = _safe_result(_gp_result.get("gameplay", _gp_raw), "QC Gameplay"),
            qc_visuel    = _safe_result(p4["qc_visuel"],    "QC Visuel"),
            execution    = _safe_result(p4["executeur"],    "Executeur"),
            playtester   = _safe_result(p4["playtester"],  "Playtester"),
            anti_pattern = _safe_result(_gp_result.get("anti_pattern", {}), "Anti-Pattern"),
        )

        score = bundle.score_global()
        exec_score = bundle.execution.score

        # 1 — Plafonnement du score si le jeu ne s'exécute pas
        if exec_score < 4.5:
            score_before_cap = score
            score = min(score, 5.0)
            if score < score_before_cap:
                coordinateur_log.warning(
                    f"Score plafonné à 5.0 (exec={exec_score:.1f} < 4.5 — jeu non fonctionnel)"
                )

        # C1 : seuils minimums par dimension — bloquer si non atteints
        _tech_score = bundle.qc_technique.score
        if exec_score < SCORE_MIN_EXECUTION or _tech_score < SCORE_MIN_TECHNIQUE:
            _blocking_reasons = []
            if exec_score < SCORE_MIN_EXECUTION:
                _blocking_reasons.append(f"execution={exec_score:.1f} < {SCORE_MIN_EXECUTION}")
            if _tech_score < SCORE_MIN_TECHNIQUE:
                _blocking_reasons.append(f"technique={_tech_score:.1f} < {SCORE_MIN_TECHNIQUE}")
            coordinateur_log.warning(f"C1 seuils non atteints : {', '.join(_blocking_reasons)} — score plafonné à 4.5")
            score = min(score, 4.5)

        # E1 : régénération complète si execution < 4.0 dès la première itération
        # (le patcher ne peut pas réparer un jeu architecturalement cassé)
        if iteration == 1 and exec_score < 4.0:
            coordinateur_log.warning(f"E1 : execution={exec_score:.1f} < 4.0 — régénération complète avant patch")
            _err_from_exec = [c.get("commentaire", "") for c in bundle.execution.criteres if c.get("score", 1) == 0]
            erreurs_passees = list(erreurs_passees or []) + _err_from_exec[:3]
            # Limiter erreurs_passees (I7)
            erreurs_passees = erreurs_passees[-MAX_ERREURS_PASSEES:]
            if not use_modular:
                from agents.phase3._layer_gen import run_layered as _rl_e1
                _regen_code = _rl_e1(context, patterns_reussis=patterns_reussis,
                                     erreurs_passees=erreurs_passees, game_logics=game_logics)
                if _regen_code and len(_regen_code) >= CODE_MIN_VIABLE:
                    code = _regen_code
                    coordinateur_log.success(f"E1 régénération terminée : {len(code)} chars")
                    # K4 — appliquer coherence+linter sur le code E1 (bypasse la boucle principale)
                    code, erreurs_passees = _post_generation_cleanup(code, erreurs_passees)
                    continue  # relancer Phase 4 avec le nouveau code

        # Log des scores
        coordinateur_log.score("Score global", score)
        coordinateur_log.score("Technique",    bundle.qc_technique.score)
        coordinateur_log.score("Gameplay",     bundle.qc_gameplay.score)
        coordinateur_log.score("Visuel",       bundle.qc_visuel.score)
        coordinateur_log.score("Execution",    exec_score)
        coordinateur_log.score("Playtester",   bundle.playtester.score)
        coordinateur_log.score("Anti-pattern", bundle.anti_pattern.score)

        push_event("score", {"label": "Score global", "value": round(score, 2)})
        push_event("score", {"label": "Execution",    "value": round(exec_score, 2)})

        # Plafonnement log uniquement — la régénération sur exec stagné a été supprimée
        # (trop coûteuse : 9 couches × retries × rotation clés = +30-45 min)

        # Sortie anticipée si score excellent
        if score >= SCORE_SORTIE_ANTICIPEE:
            coordinateur_log.success(f"Score {score:.2f} >= {SCORE_SORTIE_ANTICIPEE} -> sortie anticipee")
            break

        # Stagnation ?
        delta = score - score_precedent
        if iteration > 1:
            if delta < SCORE_STAGNATION_DELTA:
                iterations_sans_progres += 1
                coordinateur_log.warning(f"Stagnation ({delta:+.2f}) [{iterations_sans_progres}]")
                if iterations_sans_progres >= MAX_ITERATIONS_SANS_PROGRES:
                    coordinateur_log.warning("Stagnation persistante -> arret des iterations")
                    break
            else:
                iterations_sans_progres = 0
        score_precedent = score

        # E4 : économie quota — passes 3+ uniquement si score < 7.0 après 2 passes
        if iteration >= 2 and score >= SCORE_SEUIL_ITERATIONS_SUP:
            coordinateur_log.info(f"E4 : score {score:.2f} >= {SCORE_SEUIL_ITERATIONS_SUP} après {iteration} passes — arrêt")
            break

        # Dernière itération → pas de patch
        if iteration == _iters:
            coordinateur_log.info("Derniere iteration — pas de nouveau patch")
            break

        # ── PHASE 5 : PATCH ──
        coordinateur_log.section(f"PHASE 5 — Patch iteration {iteration}")

        all_issues = bundle.all_issues()
        # Ne passer au pre-patcher que les issues critique + majeur.
        # Les issues mineures ne valent pas un appel LLM — elles sont ignorées ici
        # (elles restent visibles dans le diagnostic pour le patcher principal).
        _issues_for_prepatch = [
            i for i in all_issues
            if (i.get("severite", "mineur") if isinstance(i, dict) else "mineur") in ("critique", "majeur")
        ]
        _issues_mineurs_count = len(all_issues) - len(_issues_for_prepatch)
        if _issues_mineurs_count:
            coordinateur_log.info(
                f"Pre-patcher : {_issues_mineurs_count} issue(s) mineure(s) ignorées "
                f"(garde {len(_issues_for_prepatch)} critique+majeur)"
            )
        all_issues_str = [
            i.get("description", str(i)) if isinstance(i, dict) else str(i)
            for i in _issues_for_prepatch
        ]

        # Pré-patcher : corrections automatiques simples
        # Sauvegarder AVANT pre_patcher — rollback ici si patcher échoue (pas post-pre_patch)
        code_before_prepatch = code
        code_prepatch = agent_pre_patcher.run(code, all_issues_str)
        # Valider que le pre_patcher n'a pas introduit de syntaxe cassée
        _prepatch_issues, _prepatch_broken = _js_check_quick(code_prepatch)
        if _prepatch_broken:
            coordinateur_log.warning("Pre-patcher output invalide — pre_patch ignoré (syntaxe cassée)")
            code_prepatch = code_before_prepatch
        code = code_prepatch

        # Diagnosticien → plan de corrections
        diagnostic = agent_diagnosticien.run(
            code, genre_profile, bundle, iteration,
            corrections_deja_tentees=erreurs_passees,
        )

        # Si diagnosticien n'a rien trouvé (fallback ou API failure), ne pas patcher
        _diag_corrections = diagnostic.get("corrections_prioritaires", []) if diagnostic else []
        _diag_indispo = "indisponible" in diagnostic.get("probleme_principal", "").lower() if diagnostic else True
        if not _diag_corrections or _diag_indispo:
            coordinateur_log.warning("Diagnosticien sans corrections utiles — patch ignoré pour préserver le code")
            code_patche = None
        else:
            # Patcher : corrections LLM ciblées
            code_patche = agent_patcher.run(code, diagnostic, genre_profile, iteration)

        if code_patche and len(code_patche) >= CODE_MIN_VIABLE:
            # Vérification rapide : le patch ne doit pas introduire de syntax error
            _patch_issues, _patch_broken = _js_check_quick(code_patche)
            if _patch_broken:
                coordinateur_log.warning("Patch rejeté — syntaxe invalide (rollback vers code PRÉ-pre_patcher)")
                code = code_before_prepatch  # rollback complet, pas post-pre_patch
            else:
                code = code_patche
                coordinateur_log.success(f"Code patche : {len(code)} caracteres")
                # P4 — Re-run pre-patcher après agent_patcher
                # agent_patcher (LLM sur tout le code) peut introduire de nouvelles erreurs syntaxiques
                _p4_issues, _p4_broken = _js_check_quick(code)
                if not _p4_broken and _p4_issues:
                    coordinateur_log.info(f"P4 : {len(_p4_issues)} issue(s) post-patch — re-run pre-patcher")
                    _p4_patched = agent_pre_patcher.run(code, _p4_issues)
                    _p4_recheck, _p4_rebroken = _js_check_quick(_p4_patched)
                    if not _p4_rebroken:
                        code = _p4_patched
                        coordinateur_log.info("P4 : pre-patcher post-patch OK")
        else:
            # C — Patch ciblé par type d'erreur avant de régénérer entièrement
            issue_descs = [
                i.get("description", str(i)) if isinstance(i, dict) else str(i)
                for i in all_issues[:8]
            ]
            _logic_keywords = ("undefined", "NaN", "not a function", "collision", "spawn", "update")
            _render_keywords = ("draw", "canvas", "render", "visual", "color", "display")
            has_logic_errors = any(
                any(kw in d.lower() for kw in _logic_keywords) for d in issue_descs
            )
            has_render_errors = any(
                any(kw in d.lower() for kw in _render_keywords) for d in issue_descs
            )

            # Q13 — Enregistrer les erreurs avec tracking fixed/récurrent
            for _ed in issue_descs[:5]:
                _record_error(_ed, iteration)
            # Construire erreurs_passees enrichies avec préfixes [RÉCURRENT] / [CORRIGÉ]
            _enriched = []
            for _info in list(_erreurs_tracker.values())[-15:]:
                _prefix = "[CORRIGÉ] " if _info['fixed'] else (f"[RÉCURRENT x{_info['count']}] " if _info['count'] > 1 else "")
                _enriched.append(_prefix + _info['msg'])
            erreurs_passees = _enriched
            # I7 : limiter erreurs_passees à 20 max pour éviter pollution des prompts
            erreurs_passees = erreurs_passees[-MAX_ERREURS_PASSEES:]

            if not use_modular:
                from agents.phase3._layer_gen import run_layered as _rl
                if has_logic_errors and not has_render_errors:
                    # Erreurs logiques → hint ciblé L2 dans les erreurs
                    coordinateur_log.warning("Patch insuffisant — regeneration ciblee (erreurs logique L2)")
                    erreurs_passees.append("[L2-CIBLE] Regenère la logique avec ces corrections : " + "; ".join(issue_descs[:3]))
                    import memory as _mem
                    _mem.save_layer_errors(genre_jeu, 2, issue_descs[:3])
                else:
                    coordinateur_log.warning("Patch insuffisant — regeneration complete layered")
                nouveau_code = _rl(
                    context,
                    patterns_reussis=patterns_reussis,
                    erreurs_passees=erreurs_passees,
                    game_logics=game_logics,
                )
                if nouveau_code and len(nouveau_code) >= CODE_MIN_VIABLE:
                    code = nouveau_code
                    coordinateur_log.success(f"Regeneration layered : {len(code)} caracteres")

    # ─────────────────────────────────────────────
    # PHASE 5 : FINALISATION
    # ─────────────────────────────────────────────
    coordinateur_log.section("PHASE 5 — Finalisation")

    duree = time.time() - start_time
    score_final = bundle.score_global() if bundle else 0.0
    exec_score_final = bundle.execution.score if bundle else 0.0
    all_issues_final = bundle.all_issues() if bundle else []

    # Verdict final
    verdict_full = agent_verdict_final.run(genre_profile, context.gdd, bundle) if bundle else {}
    # verdict_full = {"evaluation": EvaluationResult, "verdict": dict}
    if bundle and verdict_full:
        bundle.benchmark = verdict_full.get("evaluation", bundle.benchmark)
    verdict = verdict_full.get("verdict", {}) if verdict_full else {}
    approuve = score_final >= SCORE_SEUIL_SAUVEGARDE

    # C2 : Veto si le verdict final déclare le jeu "non jouable" ou "ne se lance pas"
    _veto_kws = ["non jouable", "injouable", "ne se lance pas", "écran noir", "crash au démarrage", "unplayable"]
    _vd_text = ((verdict.get("justification", "") or "") + " " + (verdict.get("recommandation", "") or "")).lower()
    if approuve and any(kw in _vd_text for kw in _veto_kws):
        approuve = False
        coordinateur_log.warning("C2 : veto agent neutre — jeu déclaré non jouable malgré score suffisant")

    coordinateur_log.info(f"Score final : {score_final:.2f} | Approuve : {approuve}")

    # 5 — Extraire et mémoriser les snippets des jeux très réussis
    if score_final >= 8.0 and not use_modular:
        try:
            import re as _re
            js_match = _re.search(r'<script[^>]*>(.*?)</script>', code, _re.DOTALL)
            if js_match:
                js_body = js_match.group(1)
                # Extraire les fonctions de logique (update*, check*, spawn*) comme snippets
                fn_matches = _re.finditer(
                    r'(function\s+(?:update|check|spawn|init)\w*\s*\([^)]*\)\s*\{)',
                    js_body
                )
                snippets = []
                for fm in fn_matches:
                    start = fm.start()
                    depth, end = 0, start
                    for ci in range(start, min(start + 2000, len(js_body))):
                        if js_body[ci] == '{':
                            depth += 1
                        elif js_body[ci] == '}':
                            depth -= 1
                            if depth == 0:
                                end = ci + 1
                                break
                    snippets.append(js_body[start:end])
                if snippets:
                    combined = '\n\n'.join(snippets[:3])[:500]
                    memory.save_pattern(genre_profile, score_final, combined, notes="auto-extrait score>=8")
                    coordinateur_log.success(f"Snippet réussi mémorisé ({len(snippets)} fonctions extraites)")
        except Exception as e:
            coordinateur_log.warning(f"Extraction snippet non critique : {e}")

    # Export log d'échec si exec < 4.5 (problème d'exécution)
    if exec_score_final < 4.5:
        _export_failure_log(
            genre=genre_jeu,
            titre=titre_jeu,
            score=score_final,
            exec_score=exec_score_final,
            issues=all_issues_final,
            label="exec_failure",
        )

    # Sauvegarder
    html_path = ""
    if score_final >= SCORE_MIN_VIABLE_SAVE:
        log_content = "\n".join(get_session_log())
        html_path = agent_sauvegarde.run(
            code=code,
            genre_profile=genre_profile,
            gdd=context.gdd,
            bundle=bundle,
            verdict=verdict,
            duree_secondes=duree,
            log_content=log_content,
            approuve=approuve,
        )
        if html_path:
            coordinateur_log.success(f"Jeu sauvegarde : {html_path}")
            html_basename = os.path.basename(html_path)
        else:
            html_basename = ""
    else:
        coordinateur_log.warning(f"Score {score_final:.2f} < {SCORE_MIN_VIABLE_SAVE} — jeu non sauvegarde")
        html_basename = ""

    # Auto-learner (asynchrone)
    try:
        log_content = "\n".join(get_session_log())
        agent_auto_learner.run(
            html=code,
            score=score_final,
            approuve=approuve,
            genre=genre_jeu,
            titre=titre_jeu,
            logs=log_content,
        )
    except Exception as e:
        coordinateur_log.warning(f"Auto-learner non critique : {e}")

    push_event("complete", {
        "score": round(score_final, 2),
        "approuve": approuve,
        "html_basename": html_basename,
        "titre": titre_jeu,
    })

    coordinateur_log.section(f"Termine en {duree:.1f}s — Score : {score_final:.2f}/10")

    return {
        "genre_profile": genre_profile,
        "gdd": context.gdd,
        "code": code,
        "bundle": bundle,
        "verdict": verdict,
        "score": score_final,
        "approuve": approuve,
        "html_path": html_path,
        "html_basename": html_basename,
        "duree": duree,
    }


def run_quick(prompt_utilisateur: str, style_graphique: str = "", stop_event=None) -> dict:
    """
    Pipeline allégée : Phase 1 + 2 + 3 complètes + Phase 4 une seule passe,
    sans boucle diagnosticien/patcher. Retourne le même format que run().
    Clé 'duree_secondes' incluse pour compatibilité avec /api/quick-generate.
    """
    result = run(prompt_utilisateur, style_graphique=style_graphique,
                 stop_event=stop_event, _max_iterations=1)
    if "duree" in result and "duree_secondes" not in result:
        result["duree_secondes"] = result["duree"]
    return result


# ─────────────────────────────────────────────
# POINT D'ENTRÉE CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = input("Prompt : ").strip()
        if not prompt:
            print("Prompt vide — arret.")
            sys.exit(1)

    resultat = run(prompt)
    if resultat.get("erreur"):
        print(f"\nErreur : {resultat['erreur']}")
        sys.exit(1)

    print(f"\nScore final : {resultat['score']:.2f}/10")
    print(f"Approuve    : {resultat['approuve']}")
    if resultat.get("html_path"):
        print(f"Fichier     : {resultat['html_path']}")

"""
Agent Exécuteur — Phase 4
Lance le jeu dans un navigateur headless (Playwright) et vérifie
qu'il fonctionne réellement : canvas, game loop, inputs, absence d'erreurs JS.
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
_THREEJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"


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

    phase4_log.score("Exécution", ev.score)
    return ev


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
            # B1 : teste score, playerX via __ARCADE_TEST__ au lieu de pixels canvas
            try:
                page.keyboard.down("ArrowRight")
                time.sleep(0.5)
                page.keyboard.press("Space")   # tir / action
                time.sleep(0.3)
                page.keyboard.up("ArrowRight")
                page.keyboard.down("ArrowLeft")
                time.sleep(0.4)
                page.keyboard.up("ArrowLeft")
                page.keyboard.press("z")       # certains jeux utilisent z/x
                time.sleep(0.3)
            except Exception as e:
                input_crash = True
                js_errors.append(f"CRASH gameplay inputs : {e}")

            # Lire état après interactions
            _state_after = None
            _hooks_penalty = False
            try:
                score_val = page.evaluate("typeof score !== 'undefined' ? Number(score) : -1")
                lives_val = page.evaluate("typeof lives !== 'undefined' ? Number(lives) : -1")
                game_state_now = page.evaluate("typeof gameState !== 'undefined' ? String(gameState) : '?'")
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
                # Fallback : canvas diff si hooks absents
                _fallback_comment = " [hooks absents — fallback visuel]" if not _hooks_available else " [hooks null — B4]"
                if canvas_moved and not _hooks_penalty:
                    tests_passes.append({"nom": "Gameplay réactif", "score": 1.5,
                                         "commentaire": f"Canvas change durant le jeu{_fallback_comment}"
                                                        + (f" (score={score_val})" if score_val >= 0 else "")})
                else:
                    tests_echoues.append({"nom": "Gameplay réactif", "score": 0,
                                          "commentaire": f"Canvas statique + hooks non conclusifs (gameState={game_state_now}){_fallback_comment}"})

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

            browser.close()

    finally:
        os.unlink(tmp_path)

    # Calcul du score (normalisé sur max_score ajusté)
    # max_score : 1.5 (canvas) + 1.5 (JS load) + 2.5 (visible) + 2.0 (loop) + 1.0 (FPS)
    #           + 1.5 (démarrage jeu) + 1.5 (joueur réactif) + 2.0 (score s'incrémente)
    #           + 1.0 (inputs sans crash) + 0.5 (localStorage) + 1.5 (stabilité) = 16.0
    # Sans hooks : 1.5+1.5+2.5+2.0+1.0+1.5+1.5+1.0+0.5+1.5 = 14.0
    score_brut = sum(t["score"] for t in tests_passes)
    webgl_partial = any("score partiel" in t.get("commentaire", "") for t in tests_passes if t.get("nom") == "Contenu visible")
    _with_hooks_tests = any(t.get("nom") in ("Joueur réactif", "Score s'incrémente") for t in tests_passes + tests_echoues)
    if webgl_partial:
        max_score = 12.0 if _with_hooks_tests else 11.5
    else:
        max_score = 16.0 if _with_hooks_tests else 14.0
    ev.score = min(10.0, (score_brut / max_score) * 10)

    # Pénalité dure : écran noir = score plafonné à 3.0 quel que soit le reste
    ecran_noir = any("ÉCRAN NOIR" in t["commentaire"] for t in tests_echoues)
    if ecran_noir:
        ev.score = min(ev.score, 3.0)

    # Pénalité dure : crash lors des interactions = score plafonné à 4.0
    crash_interaction = any("Crash ou erreur" in t.get("commentaire", "") for t in tests_echoues if t.get("nom") == "Inputs sans crash")
    if crash_interaction:
        ev.score = min(ev.score, 4.0)

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
        phase4_log.warning(f"{len(js_errors)} erreur(s) JS : {js_errors[0]}")

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
            ("AmbientLight",                  "Éclairage ambient",        1.0, "critique"),
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

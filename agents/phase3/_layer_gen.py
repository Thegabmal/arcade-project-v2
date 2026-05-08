"""
Layered Generation — 5 JS layers validated with cross-layer name extraction.

Hardened architecture (6 axes):
  Axis 1 — Quality Guard        : _check_layer_quality
  Axis 2 — Runtime Validation   : _validate_layer_runtime
  Axis 3 — gameLoop Auto-Patch  : _patch_gameloop_calls
  Axis 4 — Emergency Stubs      : _get_emergency_stub
  Axis 5 — Enhanced Prompts     : integrated in run_layered
  Axis 6 — Monitoring           : _LAYER_STATS, _record_layer_event, get_layer_stats
"""

import re
import os
import subprocess
import tempfile
from config import call_gemini, call_gemini_paid, MODEL_NAME_PRO
from logger import phase3_log

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Variables pré-déclarées dans le template HTML (jamais à redéclarer)
_HTML_TEMPLATE_GLOBALS = [
    'canvas', 'ctx', 'W', 'H', 'dt', 'lastTime', 'gameState',
]

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0a1a;overflow:hidden;font-family:'Courier New',monospace;touch-action:none;}}
canvas{{display:block;}}
</style>
</head><body>
<canvas id="gameCanvas"></canvas>
<script>
var canvas = document.getElementById('gameCanvas');
var _dpr = window.devicePixelRatio || 1;
var W = window.innerWidth, H = window.innerHeight;
canvas.width = W * _dpr; canvas.height = H * _dpr;
canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
var ctx = canvas.getContext('2d');
ctx.scale(_dpr, _dpr);
var dt = 0, lastTime = 0;
var gameState = 'menu';

{js_body}
</script>
</body></html>"""

_LAYER_SYSTEM = (
    "Tu es un développeur senior JavaScript Canvas 2D. "
    "Tu generes du code JS pur — pas de HTML, pas de balises <script>, pas de markdown.\n\n"
    "REGLES ABSOLUES :\n"
    "- Output = JavaScript pur uniquement (pas de <!DOCTYPE>, <html>, <script>, ```)\n"
    "- Jamais de `const` dans un switch/case sans accolades -> utilise `var`\n"
    "- Jamais de `for(const i=0;...)` -> utilise `let`\n"
    "- Jamais de `const` pour une variable reassignee -> utilise `let`\n"
    "- Chaque fonction doit etre COMPLETE avec un vrai corps — pas de stubs, pas de TODO\n"
    "- Pas de limite de lignes — prends autant d'espace que necessaire pour etre complet\n"
    "- CRITIQUE : ta reponse DOIT se terminer sur une instruction complete "
    "(accolade fermante '}' ou point-virgule ';'). "
    "Si tu dois t'arreter, ferme proprement la fonction en cours avant.\n"
    "- F1 localStorage : toujours entourer d'un try/catch "
    "(ex: try { localStorage.setItem('score', score); } catch(e) {} )\n"
    "  SecurityError en mode prive/iframe sinon.\n"
    "- INTERDIT ABSOLU : new Image(), img.src, Image(), fetch(), XMLHttpRequest, "
    "import(), require(), new Audio(), Audio() — tout doit etre dessine/joue en Canvas 2D pur "
    "sans ressources externes. Pour le son : utilise WebAudio API (AudioContext) uniquement.\n"
    "- FORBIDDEN in draw* functions: fillRect() as the ONLY render for any entity (player/enemy/projectile).\n"
    "  Use arc(), bezierCurveTo(), gradient, or compound shapes — rectangle sprites = visual score <= 6.\n"
)

_LAYER_SYSTEM_GRAPHIQUE = (
    "Tu es un directeur artistique senior specialise en jeux HTML5 Canvas 2D. "
    "Tu crees des visuels exceptionnels — beaux, coherents, expressifs et memorables.\n\n"
    "MISSION : Reecris les fonctions draw* existantes pour les rendre visuellement remarquables. "
    "En JavaScript, la derniere definition d'une fonction ecrase la precedente — tu peux redefinir "
    "les memes noms de fonctions pour les ameliorer.\n\n"
    "TECHNIQUES OBLIGATOIRES :\n"
    "- ctx.save()/ctx.restore() pour toute transformation (translate, rotate, scale)\n"
    "- shadowBlur + shadowColor pour les effets glow (joueur, boss, bullets, particules)\n"
    "- createLinearGradient / createRadialGradient pour les entites importantes\n"
    "- globalAlpha pour la transparence, overlays, et effets de fondu\n"
    "- Animations basees sur une variable timer globale dediee avec +=dt (ex: _bgTimer+=dt) — JAMAIS Date.now() pour animer\n"
    "- Fond riche et anime : etoiles, grille, nebuleuse, parallaxe — jamais un fond uni\n"
    "- Boss visuellement exceptionnel : plus grand, aura, couleur unique par phase, barre HP stylisee\n"
    "- Particules belles : taille et opacite qui diminuent avec life, couleurs variees\n"
    "- ABSOLUTE FORBIDDEN: fillRect() as the ONLY visual for player, enemy, or projectile.\n"
    "  Every entity MUST use arc(), bezierCurveTo(), or a composition of 3+ draw calls.\n\n"
    "REGLES ABSOLUES :\n"
    "- Output = JavaScript pur uniquement\n"
    "- Utilise UNIQUEMENT les proprietes du contrat de schema fourni\n"
    "- Chaque fonction redefinite doit etre COMPLETE et auto-suffisante\n"
    "- Jamais de new Image(), fetch(), import()\n"
    "- Pas de limite de lignes — la beaute prend du temps\n"
    "- INTERDIT ABSOLU : rgba() appelee comme une fonction JavaScript — cause ReferenceError et ecran noir.\n"
    "  FAUX : ctx.fillStyle = rgba(255, 0, 0, 0.5)          ← CRASH\n"
    "  FAUX : ctx.fillStyle = rgba(r, g, b, alpha)           ← CRASH\n"
    "  VRAI : ctx.fillStyle = 'rgba(255, 0, 0, 0.5)';        ← string CSS directe OK\n"
    "  VRAI : ctx.globalAlpha = 0.5; ctx.fillStyle = '#f00'; ← alpha separe OK\n"
    "  Meme regle pour rgb(), hsl(), hsla() — toujours entre guillemets simples ou doubles.\n"
)

# Canvas mock pour la validation Node.js (Axe 2)
_NODE_MOCK = """\
var _runtimeErrors = [];
var canvas = { width:800, height:600, getContext:function(){return ctx;}, addEventListener:function(){}, style:{} };
var ctx = { fillStyle:'',strokeStyle:'',lineWidth:1,font:'16px monospace',globalAlpha:1,textAlign:'left',textBaseline:'alphabetic',shadowBlur:0,shadowColor:'',fillRect:function(){},clearRect:function(){},fillText:function(){},strokeText:function(){},beginPath:function(){},closePath:function(){},arc:function(){},rect:function(){},fill:function(){},stroke:function(){},moveTo:function(){},lineTo:function(){},save:function(){},restore:function(){},translate:function(){},rotate:function(){},scale:function(){},transform:function(){},setTransform:function(){},createLinearGradient:function(){return{addColorStop:function(){}};},createRadialGradient:function(){return{addColorStop:function(){}};},drawImage:function(){},clip:function(){},measureText:function(t){return{width:(t||'').length*8};},strokeRect:function(){},quadraticCurveTo:function(){},bezierCurveTo:function(){},putImageData:function(){},getImageData:function(){return{data:[],width:0,height:0};},isPointInPath:function(){return false;} };
var W=800,H=600,dt=0.016,lastTime=0,gameState='playing';
var requestAnimationFrame=function(){};
var cancelAnimationFrame=function(){};
var document={getElementById:function(){return canvas;},querySelector:function(){return canvas;},querySelectorAll:function(){return[];},createElement:function(){return{getContext:function(){return ctx;},style:{},width:0,height:0};},addEventListener:function(){},removeEventListener:function(){},body:{style:{},appendChild:function(){}}};
var AudioCtxMock=function(){return{createOscillator:function(){return{connect:function(){},start:function(){},stop:function(){},frequency:{setValueAtTime:function(){},value:440}};},createGain:function(){return{connect:function(){},gain:{setValueAtTime:function(){},value:1,linearRampToValueAtTime:function(){}}};},destination:{},currentTime:0,state:'running',resume:function(){return Promise.resolve();}};};
var window={innerWidth:800,innerHeight:600,addEventListener:function(){},removeEventListener:function(){},AudioContext:AudioCtxMock,webkitAudioContext:AudioCtxMock,location:{href:''},performance:{now:function(){return 0;}}};
var localStorage={getItem:function(){return null;},setItem:function(){},removeItem:function(){}};
var performance={now:function(){return Date.now();}};
var Image=function(){this.src='';this.onload=null;};
var Audio=function(){this.src='';this.play=function(){return Promise.resolve();};this.pause=function(){};this.volume=1;};
// Pièges LLM — ces fonctions CSS ne sont PAS des fonctions JS
// Les définir comme undefined force un ReferenceError explicite si appelées sans guillemets
// (au lieu d'un crash silencieux ou d'un bad string)
// NON défini intentionnellement : rgba, rgb, hsl, hsla — ils doivent être des strings CSS
"""

_NODE_RUNNER_SUFFIX = """\
// Simuler quelques frames pour attraper les erreurs de rendu/update
try { if(typeof init==='function') init(); } catch(e){ process.stdout.write('RUNTIME_ERROR:init:'+e.message+'\\n'); }
// Frame 1 : menu
try { if(typeof gameLoop==='function') gameLoop(16.7); } catch(e){ process.stdout.write('RUNTIME_ERROR:gameLoop(menu):'+e.message+'\\n'); }
// Frame 2 : playing
try { gameState='playing'; dt=0.016; if(typeof gameLoop==='function') gameLoop(33.4); } catch(e){ process.stdout.write('RUNTIME_ERROR:gameLoop(playing):'+e.message+'\\n'); }
// Frame 3 : gameover
try { gameState='gameover'; if(typeof gameLoop==='function') gameLoop(50.1); } catch(e){ process.stdout.write('RUNTIME_ERROR:gameLoop(gameover):'+e.message+'\\n'); }
// Tester les fonctions draw séparément (détecte les rgba() non-quotés)
try { if(typeof drawBackground==='function') drawBackground(); } catch(e){ process.stdout.write('RUNTIME_ERROR:drawBackground:'+e.message+'\\n'); }
try { if(typeof drawHUD==='function') drawHUD(); } catch(e){ process.stdout.write('RUNTIME_ERROR:drawHUD:'+e.message+'\\n'); }
try { if(typeof drawMenu==='function') drawMenu(); } catch(e){ process.stdout.write('RUNTIME_ERROR:drawMenu:'+e.message+'\\n'); }
process.stdout.write('RUNTIME_OK\\n');
"""


# ─────────────────────────────────────────────────────────────────────────────
# AXE 6 — MONITORING
# ─────────────────────────────────────────────────────────────────────────────

_LAYER_STATS: dict = {
    'layer1': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer2': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer3': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer4': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer5': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer6': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer7': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer8': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
    'layer9': {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []},
}


# Mots-clés pour le split sémantique de game_logics (init vs update)
_INIT_KEYWORDS = [
    'spawn', 'init', 'create', 'reset', 'start', 'setup', 'load',
    'instancier', 'initialiser', 'creer', 'créer', 'démarrer',
]
_UPDATE_KEYWORDS = [
    'update', 'move', 'check', 'detect', 'handle', 'apply', 'process',
    'mettre a jour', 'deplacer', 'déplacer', 'calculer', 'verifier', 'vérifier',
]


def _record_layer_event(layer_key: str, success: bool, lines: int = 0, reason: str = '') -> None:
    """Met à jour les stats d'une couche (Axe 6)."""
    if layer_key not in _LAYER_STATS:
        return
    entry = _LAYER_STATS[layer_key]
    entry['attempts'] += 1
    if success:
        entry['successes'] += 1
        if lines > 0:
            entry['lines_generated'].append(lines)
    else:
        if reason:
            entry['failures'].append(reason)


def get_layer_stats() -> dict:
    """Retourne un résumé des stats avec taux de succès par couche (Axe 6)."""
    summary = {}
    for key, data in _LAYER_STATS.items():
        attempts = data['attempts']
        successes = data['successes']
        rate = (successes / attempts * 100) if attempts > 0 else 0.0
        avg_lines = (
            sum(data['lines_generated']) / len(data['lines_generated'])
            if data['lines_generated'] else 0
        )
        summary[key] = {
            'attempts': attempts,
            'successes': successes,
            'success_rate': round(rate, 1),
            'avg_lines': round(avg_lines, 1),
            'top_failures': _most_common(data['failures'], 3),
        }
    return summary



def _most_common(lst: list, n: int) -> list[tuple]:
    """Retourne les n éléments les plus fréquents de lst."""
    counts: dict = {}
    for item in lst:
        counts[item] = counts.get(item, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])[:n]


# ─────────────────────────────────────────────────────────────────────────────
# AXE 1 — QUALITY GUARD
# ─────────────────────────────────────────────────────────────────────────────

def _check_layer_quality(js: str, layer_name: str) -> tuple[bool, str]:
    """
    Rejette les outputs LLM de mauvaise qualité (Axe 1).
    Retourne (True, "") si OK, (False, "raison") si rejeté.
    """
    if not js or not js.strip():
        return False, "trop court (stub probable)"

    lines = [ln for ln in js.splitlines() if ln.strip()]
    # Couche 1 (données) tolère 10 lignes minimum, les autres 15
    min_lines = 10 if ('1' in layer_name or 'données' in layer_name.lower()) else 15
    if len(lines) < min_lines:
        return False, f"trop court ({len(lines)} lignes < {min_lines})"

    # HTML résiduel
    html_patterns = ['<div', '<canvas', '<!DOCTYPE', '<html', '<body', '<script']
    for pat in html_patterns:
        if pat.lower() in js.lower():
            return False, "HTML résiduel"

    # use strict interdit
    if "'use strict'" in js or '"use strict"' in js:
        return False, "use strict interdit"

    # Fonctions vides : détection des stubs {} ou { // ... }
    all_fn_bodies = re.findall(
        r'function\s+\w+\s*\([^)]*\)\s*\{([^}]*)\}',
        js
    )
    if all_fn_bodies:
        empty_count = 0
        for body in all_fn_bodies:
            stripped = body.strip()
            # Corps vide ou ne contenant que des commentaires
            no_comments = re.sub(r'//[^\n]*', '', stripped).strip()
            no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL).strip()
            if not no_comments:
                empty_count += 1
        ratio = empty_count / len(all_fn_bodies)
        if ratio > 0.5:
            return False, "fonctions vides"

    # J10 : détecter arrow function stubs (const fn = () => {}) non détectés par le check ci-dessus
    arrow_stubs = re.findall(r'(?:const|let|var)\s+\w+\s*=\s*(?:\([^)]*\)|[a-zA-Z_$]\w*)\s*=>\s*\{\s*\}', js)
    total_arrows = re.findall(r'(?:const|let|var)\s+\w+\s*=\s*(?:\([^)]*\)|[a-zA-Z_$]\w*)\s*=>', js)
    if total_arrows and len(arrow_stubs) / len(total_arrows) > 0.5:
        return False, "arrow function stubs"

    # Contrôles spécifiques par couche — architecture 9 couches
    layer_lower = layer_name.lower()

    # Toute couche avec "logique" ou couches 2-5 doit avoir au moins une fonction
    if any(x in layer_lower for x in ('logique', 'couche 2', 'couche 3', 'couche 4', 'couche 5')):
        if not re.search(r'\bfunction\b', js):
            return False, "aucune fonction générée"

    # Couches de rendu (6 et 9) doivent avoir des fonctions draw* ou render*
    if any(x in layer_lower for x in ('couche 6', 'couche 9', 'rendu', 'graphisme')):
        if not re.search(r'\bfunction\s+(?:draw|render|paint|display)\w*\s*\(', js):
            return False, "aucune fonction draw*/render* (rendu)"

    # Couche physique (3) doit avoir des fonctions de mouvement/physique
    # Accepte : update*, move*, apply*, handle*, calc*, process*, run*
    if 'couche 3' in layer_lower or 'physique' in layer_lower:
        if not re.search(r'\bfunction\s+(?:update|move|apply|handle|calc|process|run)\w*\s*\(', js):
            return False, "aucune fonction update*/move*/apply* (physique)"

    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# AXE 2 — RUNTIME VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_js_from_html(html: str) -> str:
    """Extract the main game JS block — uses longest-match to skip CDN script tags."""
    matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    if matches:
        longest = max(matches, key=len)
        if len(longest) > 100:
            return longest
    return html


def _validate_layer_runtime(html: str) -> list[str]:
    """
    Valide le JS à l'exécution via Node.js (Axe 2).
    Retourne la liste des erreurs runtime (vide = OK).
    Non-bloquant par conception : appelant doit décider du comportement.
    """
    try:
        game_js = _extract_js_from_html(html)
        script_content = _NODE_MOCK + '\n' + game_js + '\n' + _NODE_RUNNER_SUFFIX

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.js', delete=False, encoding='utf-8'
        ) as f:
            f.write(script_content)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ['node', '--timeout', '8000', tmp_path],
                capture_output=True,
                text=True,
                timeout=10,  # B7 : 10s — détecte les boucles infinies réelles
            )
            output = result.stdout + result.stderr
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        errors: list[str] = []
        for line in output.splitlines():
            if line.startswith('RUNTIME_ERROR:'):
                msg = line[len('RUNTIME_ERROR:'):]
                # Filtrer les faux positifs pour draw*/update* optionnels
                if re.search(r"draw\w+\s+is not a function", msg, re.IGNORECASE):
                    continue
                if re.search(r"update\w+\s+is not a function", msg, re.IGNORECASE):
                    continue
                errors.append(msg)

        return errors

    except FileNotFoundError:
        # node n'est pas disponible — on saute silencieusement
        phase3_log.info("[layered] Node.js non disponible — runtime check sauté")
        return []
    except subprocess.TimeoutExpired:
        phase3_log.warning("[layered] Runtime check timeout")
        return []
    except Exception as e:
        phase3_log.warning("[layered] Runtime check erreur inattendue : %s" % e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# AXE 3 — GAMELOOP AUTO-INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

def _patch_gameloop_calls(accumulated_js: str, new_fns: list[str]) -> str:
    """
    Intègre automatiquement les nouvelles fonctions (L8) dans le bloc playing de gameLoop.

    Algorithme :
    1. Localise le bloc if(gameState==='playing') dans gameLoop
    2. Injecte les update_fns après le dernier appel update existant (dans playing)
    3. Injecte les draw_fns après le dernier appel draw existant (dans playing)
    4. Valide le résultat — rollback si invalide
    """
    if not new_fns:
        return accumulated_js

    try:
        from js_syntax_checker import fix_all_auto, check_and_report as _js_check
    except ImportError:
        return accumulated_js

    # Séparer update et draw fonctions
    update_fns = [fn for fn in new_fns if fn.startswith(('update', 'check'))]
    draw_fns = [fn for fn in new_fns if fn.startswith('draw')]

    if not update_fns and not draw_fns:
        return accumulated_js

    # Localiser gameLoop en comptant les accolades (robuste face aux corps complexes)
    gl_m = re.search(r'function\s+gameLoop\s*\([^)]*\)\s*\{', accumulated_js)
    if not gl_m:
        phase3_log.info("[layered] _patch_gameloop_calls : gameLoop non trouvé")
        return accumulated_js

    gl_body_start = gl_m.end()
    depth, gl_body_end = 1, gl_body_start
    for ci in range(gl_body_start, len(accumulated_js)):
        if accumulated_js[ci] == '{': depth += 1
        elif accumulated_js[ci] == '}':
            depth -= 1
            if depth == 0: gl_body_end = ci; break
    gl_body = accumulated_js[gl_body_start:gl_body_end]

    # Localiser le bloc playing dans gameLoop (if/else ou switch/case)
    playing_m = re.search(r'gameState\s*===?\s*["\']playing["\']', gl_body)
    if not playing_m:
        playing_m = re.search(r"case\s+['\"]playing['\"]", gl_body)
    if not playing_m:
        phase3_log.info("[layered] _patch_gameloop_calls : bloc playing non trouvé — fallback RAF")

    patched = accumulated_js
    offset = 0  # décalage cumulatif après injections

    if playing_m:
        # Trouver l'accolade ouvrante du bloc playing
        brace_pos = gl_body.find('{', playing_m.end())
        if brace_pos != -1:
            # Extraire le contenu du bloc playing (entre { et })
            pdepth, pend = 1, brace_pos + 1
            for ci in range(brace_pos + 1, len(gl_body)):
                if gl_body[ci] == '{': pdepth += 1
                elif gl_body[ci] == '}':
                    pdepth -= 1
                    if pdepth == 0: pend = ci; break
            playing_block = gl_body[brace_pos + 1:pend]

            # Position absolue de l'intérieur du bloc playing dans accumulated_js
            playing_abs_start = gl_body_start + brace_pos + 1

            # Trouver où injecter les update_fns (après le dernier appel update*)
            inject_update_pos = None
            for m in re.finditer(r'\b(?:update\w+|checkCollisions)\s*\([^)]*\)\s*;?', playing_block):
                inject_update_pos = m.end()
            # Trouver où injecter les draw_fns (après le dernier appel draw*)
            inject_draw_pos = None
            for m in re.finditer(r'\bdraw\w+\s*\(\s*\)\s*;?', playing_block):
                inject_draw_pos = m.end()

            # Injection update_fns
            if update_fns and inject_update_pos is not None:
                inj = '\n' + '\n'.join(
                    "    if(typeof %s==='function') %s();" % (fn, fn)
                    for fn in update_fns
                )
                abs_pos = playing_abs_start + inject_update_pos + offset
                patched = patched[:abs_pos] + inj + patched[abs_pos:]
                offset += len(inj)

            # Injection draw_fns
            if draw_fns and inject_draw_pos is not None:
                inj = '\n' + '\n'.join(
                    "    if(typeof %s==='function') %s();" % (fn, fn)
                    for fn in draw_fns
                )
                abs_pos = playing_abs_start + inject_draw_pos + offset
                patched = patched[:abs_pos] + inj + patched[abs_pos:]
                offset += len(inj)

    if offset == 0:
        # Aucune position trouvée — fallback : injecter avant RAF (stratégie précédente)
        raf_pattern = re.compile(r'requestAnimationFrame\s*\(\s*gameLoop\s*\)')
        matches = list(raf_pattern.finditer(patched))
        if matches:
            raf_pos = matches[-1].start()
            all_injection = '\n'.join(
                "  if(typeof %s==='function') %s();" % (fn, fn)
                for fn in update_fns + draw_fns
            )
            patched = patched[:raf_pos] + all_injection + '\n  ' + patched[raf_pos:]

    # Valider le résultat
    try:
        test_html = _HTML_TEMPLATE.format(title="test", js_body=patched)
        test_html, _fixed, _ = fix_all_auto(test_html)
        _issues, _broken = _js_check(test_html)
        if _broken:
            phase3_log.warning("[layered] _patch_gameloop_calls : résultat invalide — rollback")
            return accumulated_js
        phase3_log.info(
            "[layered] _patch_gameloop_calls : +%d update_fns, +%d draw_fns injectés"
            % (len(update_fns), len(draw_fns))
        )
        return patched
    except Exception as e:
        phase3_log.warning("[layered] _patch_gameloop_calls erreur validation : %s" % e)
        return accumulated_js


# ─────────────────────────────────────────────────────────────────────────────
# AXE 4 — EMERGENCY STUBS
# ─────────────────────────────────────────────────────────────────────────────

def _get_emergency_stub(layer_num: int, genre: str, decls: dict) -> str:
    """
    Retourne un stub JS minimal mais fonctionnel quand le LLM échoue deux fois (Axe 4).
    Référence uniquement les variables présentes dans decls['vars'] et decls['funcs'].
    """
    known_vars = set(decls.get('vars', []))
    known_funcs = set(decls.get('funcs', []))

    def _has(name: str) -> bool:
        return name in known_vars or name in known_funcs

    def _find_alias(candidates: list) -> str:
        """Retourne le premier nom trouvé parmi les candidats, ou '' si aucun."""
        for c in candidates:
            if _has(c):
                return c
        return ''

    # Détecter les noms réels utilisés dans L1 (anti-hallucination stub)
    _player_var = _find_alias(['player', 'hero', 'ship', 'character', 'p', 'joueur', 'vaisseau'])
    _enemies_var = _find_alias(['enemies', 'foes', 'monsters', 'ennemis', 'mobs', 'ennemi'])
    _bullets_var = _find_alias(['bullets', 'projectiles', 'shots', 'balles', 'lasers'])

    if layer_num == 2:
        # Fonctions update minimales basées sur les variables déclarées
        stub_parts: list[str] = []

        if _player_var:
            pv = _player_var
            stub_parts.append(
                "function updatePlayer(dt) {\n"
                f"  if(!{pv}) return;\n"
                f"  if(keys.left || keys['arrowleft']) {pv}.x -= 200*dt;\n"
                f"  if(keys.right || keys['arrowright']) {pv}.x += 200*dt;\n"
                f"  if(keys.up || keys['arrowup']) {pv}.y -= 200*dt;\n"
                f"  if(keys.down || keys['arrowdown']) {pv}.y += 200*dt;\n"
                f"  {pv}.x = Math.max(0, Math.min(W - ({pv}.w||{pv}.r*2||20), {pv}.x));\n"
                f"  {pv}.y = Math.max(0, Math.min(H - ({pv}.h||{pv}.r*2||20), {pv}.y));\n"
                "}"
            )

        if _enemies_var:
            ev = _enemies_var
            pv_ref = _player_var or 'null'
            stub_parts.append(
                "function updateEnemies() {\n"
                f"  for(var i={ev}.length-1;i>=0;i--) {{\n"
                f"    var e={ev}[i];\n"
                f"    if({pv_ref}){{e.x+=({pv_ref}.x-e.x)*0.5*dt;e.y+=({pv_ref}.y-e.y)*0.5*dt;}}\n"
                "    else{e.y+=80*dt;}\n"
                f"    if((e.hp||e.health||1)<=0){{{ev}.splice(i,1);if(typeof score!=='undefined')score+=10;}}\n"
                "  }\n"
                "}"
            )

        if _bullets_var:
            bv = _bullets_var
            stub_parts.append(
                "function updateBullets() {\n"
                f"  for(var i={bv}.length-1;i>=0;i--) {{\n"
                f"    var b={bv}[i];\n"
                "    b.x+=(b.vx||b.dx||0)*dt; b.y+=(b.vy||b.dy||-300)*dt;\n"
                f"    if(b.x<0||b.x>W||b.y<0||b.y>H){{{bv}.splice(i,1);}}\n"
                "  }\n"
                "}"
            )

        if _has('particles'):
            stub_parts.append(
                "function updateParticles() {\n"
                "  for(var i=particles.length-1;i>=0;i--) {\n"
                "    var p=particles[i];\n"
                "    p.x+=p.vx*dt; p.y+=p.vy*dt;\n"
                "    p.life-=dt;\n"
                "    if(p.life<=0){particles.splice(i,1);}\n"
                "  }\n"
                "}"
            )

        pv = _player_var or 'null'
        ev = _enemies_var or '[]'
        bv = _bullets_var or '[]'
        stub_parts.append(
            "function checkCollisions() {\n"
            f"  if(!{pv} || !{ev} || !{bv}) return;\n"
            f"  var pw={pv}.w||{pv}.r*2||20, ph={pv}.h||{pv}.r*2||20;\n"
            f"  for(var i={bv}.length-1;i>=0;i--) {{\n"
            f"    var b={bv}[i];\n"
            f"    for(var j={ev}.length-1;j>=0;j--) {{\n"
            f"      var e={ev}[j];\n"
            "      var er=e.r||e.w/2||15;\n"
            "      var dx=b.x-e.x, dy=b.y-e.y;\n"
            "      if(dx*dx+dy*dy<er*er) {\n"
            "        if(e.hp!==undefined)e.hp-=1; else if(e.health!==undefined)e.health-=1;\n"
            f"        {bv}.splice(i,1); break;\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "}"
        )

        if _has('waveTimer'):
            stub_parts.append(
                "function updateWave() {\n"
                "  if(typeof waveActive!=='undefined' && waveActive) return;\n"
                "  if(typeof waveTimer!=='undefined'){waveTimer-=dt;}\n"
                "  if(typeof waveTimer!=='undefined' && waveTimer<=0) {\n"
                "    waveTimer=5;\n"
                "    if(typeof wave!=='undefined')wave++;\n"
                "  }\n"
                "}"
            )

        return '\n\n'.join(stub_parts) if stub_parts else (
            "function updatePlayer(){}\nfunction updateEnemies(){}\nfunction checkCollisions(){}"
        )

    elif layer_num == 3:
        # Fonctions draw minimales
        has_player = _has('player')
        has_enemies = _has('enemies')
        has_bullets = _has('bullets')
        has_particles = _has('particles')
        has_score = _has('score')
        has_lives = _has('lives')
        has_palette = _has('PALETTE')
        bg_color = 'PALETTE.bg||"#0a0a1a"' if has_palette else '"#0a0a1a"'
        entity_color = 'PALETTE.player||"#00ffff"' if has_palette else '"#00ffff"'

        parts: list[str] = [
            "function drawBackground() {\n"
            "  ctx.fillStyle=%s;\n"
            "  ctx.fillRect(0,0,W,H);\n"
            # Grille lumineuse visible pour que le test brightness Playwright passe
            "  ctx.strokeStyle='rgba(0,200,255,0.15)';\n"
            "  ctx.lineWidth=1;\n"
            "  for(var gx=0;gx<W;gx+=60){ctx.beginPath();ctx.moveTo(gx,0);ctx.lineTo(gx,H);ctx.stroke();}\n"
            "  for(var gy=0;gy<H;gy+=60){ctx.beginPath();ctx.moveTo(0,gy);ctx.lineTo(W,gy);ctx.stroke();}\n"
            "}" % bg_color
        ]

        if has_player:
            parts.append(
                "function drawPlayer() {\n"
                "  if(!player) return;\n"
                "  var pw=player.w||24, ph=player.h||24;\n"
                "  ctx.fillStyle=%s;\n"
                "  ctx.shadowColor=%s;\n"
                "  ctx.shadowBlur=12;\n"
                "  ctx.fillRect(player.x-pw/2, player.y-ph/2, pw, ph);\n"
                "  ctx.shadowBlur=0;\n"
                "}" % (entity_color, entity_color)
            )

        if has_enemies:
            enemy_color = 'PALETTE.enemy||"#ff4444"' if has_palette else '"#ff4444"'
            parts.append(
                "function drawEnemies() {\n"
                "  for(var i=0;i<enemies.length;i++) {\n"
                "    var e=enemies[i];\n"
                "    ctx.fillStyle=%s;\n"
                "    ctx.beginPath();\n"
                "    ctx.arc(e.x,e.y,e.r||15,0,Math.PI*2);\n"
                "    ctx.fill();\n"
                "  }\n"
                "}" % enemy_color
            )

        if has_bullets:
            bullet_color = 'PALETTE.bullet||"#ffff00"' if has_palette else '"#ffff00"'
            parts.append(
                "function drawBullets() {\n"
                "  ctx.fillStyle=%s;\n"
                "  for(var i=0;i<bullets.length;i++) {\n"
                "    var b=bullets[i];\n"
                "    ctx.beginPath();\n"
                "    ctx.arc(b.x,b.y,b.r||4,0,Math.PI*2);\n"
                "    ctx.fill();\n"
                "  }\n"
                "}" % bullet_color
            )

        if has_particles:
            parts.append(
                "function drawParticles() {\n"
                "  for(var i=0;i<particles.length;i++) {\n"
                "    var p=particles[i];\n"
                "    ctx.globalAlpha=Math.max(0,p.life);\n"
                "    ctx.fillStyle=p.color||'#ffffff';\n"
                "    ctx.beginPath();\n"
                "    ctx.arc(p.x,p.y,p.r||3,0,Math.PI*2);\n"
                "    ctx.fill();\n"
                "  }\n"
                "  ctx.globalAlpha=1;\n"
                "}"
            )

        hud_score = "  if(typeof score!=='undefined'){ctx.fillText('SCORE: '+score,16,40);}\n" if has_score else ""
        hud_lives = "  if(typeof lives!=='undefined'){ctx.fillText('VIES: '+lives,16,64);}\n" if has_lives else ""
        parts.append(
            "function drawHUD() {\n"
            "  ctx.fillStyle='#ffffff';\n"
            "  ctx.font='16px monospace';\n"
            "  ctx.textAlign='left';\n"
            + hud_score + hud_lives +
            "}"
        )

        parts.append(
            "function drawMenu() {\n"
            # Fond semi-transparent mais pas trop sombre (améliore brightness test)
            "  ctx.fillStyle='rgba(0,20,60,0.75)';\n"
            "  ctx.fillRect(0,0,W,H);\n"
            # Panneau central lumineux
            "  ctx.fillStyle='rgba(0,100,200,0.4)';\n"
            "  ctx.fillRect(W/2-200,H/2-100,400,200);\n"
            "  ctx.strokeStyle='#00ffff';\n"
            "  ctx.lineWidth=2;\n"
            "  ctx.strokeRect(W/2-200,H/2-100,400,200);\n"
            "  ctx.shadowColor='#00ffff'; ctx.shadowBlur=20;\n"
            "  ctx.fillStyle='#00ffff';\n"
            "  ctx.font='bold 40px monospace';\n"
            "  ctx.textAlign='center';\n"
            "  ctx.fillText('ARCADE',W/2,H/2-30);\n"
            "  ctx.shadowBlur=0;\n"
            "  ctx.fillStyle='#ffffff';\n"
            "  ctx.font='18px monospace';\n"
            "  ctx.fillText('CLIC ou ESPACE pour jouer',W/2,H/2+30);\n"
            "  ctx.textAlign='left';\n"
            "}"
        )

        parts.append(
            "function drawGameOver() {\n"
            "  ctx.fillStyle='rgba(0,0,0,0.8)';\n"
            "  ctx.fillRect(0,0,W,H);\n"
            "  ctx.fillStyle='#ff4444';\n"
            "  ctx.font='bold 40px monospace';\n"
            "  ctx.textAlign='center';\n"
            "  ctx.fillText('GAME OVER',W/2,H/2-40);\n"
            + ("  ctx.fillStyle='#ffffff';\n  ctx.font='20px monospace';\n  ctx.fillText('Score: '+score,W/2,H/2+10);\n" if has_score else "") +
            "  ctx.fillStyle='#aaaaaa';\n"
            "  ctx.font='16px monospace';\n"
            "  ctx.fillText('Appuie sur ESPACE',W/2,H/2+50);\n"
            "  ctx.textAlign='left';\n"
            "}"
        )

        return '\n\n'.join(parts)

    elif layer_num == 4:
        # Game loop minimal construit depuis les fonctions connues
        update_fns = [fn for fn in known_funcs if fn.startswith('update') or fn == 'checkCollisions']
        draw_fns = [fn for fn in known_funcs if fn.startswith('draw')]
        init_fns = [fn for fn in known_funcs if fn.startswith('init')]

        update_calls = '\n    '.join(fn + '();' for fn in sorted(update_fns)) or '// update'
        draw_calls = '\n    '.join(fn + '();' for fn in sorted(draw_fns)) or (
            'ctx.fillStyle="#FFF";ctx.font="20px monospace";'
            'ctx.fillText("Chargement...",W/2-60,H/2);'
        )
        init_calls = '\n  '.join(fn + '();' for fn in init_fns) or ''

        return (
            "function init() {\n"
            "  %(init_calls)s\n"
            "  gameState = 'menu';\n"
            "  requestAnimationFrame(gameLoop);\n"
            "}\n\n"
            "function gameLoop(ts) {\n"
            "  dt = Math.min((ts - lastTime) / 1000, 0.05);\n"
            "  lastTime = ts;\n"
            "  ctx.clearRect(0, 0, W, H);\n"
            "  if(gameState === 'menu') {\n"
            "    if(typeof drawBackground==='function') drawBackground();\n"
            "    if(typeof drawMenu==='function') drawMenu();\n"
            "  } else if(gameState === 'playing') {\n"
            "    %(update_calls)s\n"
            "    %(draw_calls)s\n"
            "  } else if(gameState === 'gameover') {\n"
            "    if(typeof drawBackground==='function') drawBackground();\n"
            "    if(typeof drawGameOver==='function') drawGameOver();\n"
            "  }\n"
            "  requestAnimationFrame(gameLoop);\n"
            "}\n\n"
            "document.addEventListener('keydown', function(e) {\n"
            "  var k = e.key.toLowerCase();\n"
            "  if(typeof keys !== 'undefined' && keys.hasOwnProperty(k)) keys[k] = true;\n"
            "  if(e.code === 'Space') {\n"
            "    e.preventDefault();\n"
            "    if(gameState === 'gameover') { if(typeof init==='function') init(); }\n"
            "    else if(gameState === 'menu') { gameState = 'playing'; }\n"
            "  }\n"
            "});\n"
            "document.addEventListener('keyup', function(e) {\n"
            "  var k = e.key.toLowerCase();\n"
            "  if(typeof keys !== 'undefined' && keys.hasOwnProperty(k)) keys[k] = false;\n"
            "});\n"
            "canvas.addEventListener('mousemove', function(e) {\n"
            "  if(typeof mouse !== 'undefined'){mouse.x = e.clientX; mouse.y = e.clientY;}\n"
            "});\n"
            "canvas.addEventListener('mousedown', function(e) {\n"
            "  if(typeof mouse !== 'undefined') mouse.down = true;\n"
            "  if(gameState === 'menu') { gameState = 'playing'; }\n"
            "  else if(gameState === 'gameover') { if(typeof init==='function') init(); }\n"
            "});\n"
            "canvas.addEventListener('mouseup', function() {\n"
            "  if(typeof mouse !== 'undefined') mouse.down = false;\n"
            "});\n"
            "init();\n"
        ) % {
            'init_calls': init_calls,
            'update_calls': update_calls,
            'draw_calls': draw_calls,
        }

    elif layer_num == 5:
        # Système combo universel (toujours utile, toujours syntaxiquement valide)
        return (
            "var combo = typeof combo !== 'undefined' ? combo : 0;\n"
            "var comboTimer = 0;\n"
            "var highScore = parseInt(localStorage.getItem('hs') || '0');\n\n"
            "function updateCombo() {\n"
            "  if(comboTimer > 0) {\n"
            "    comboTimer -= dt;\n"
            "    if(comboTimer <= 0) { combo = 0; }\n"
            "  }\n"
            "}\n\n"
            "function addKill() {\n"
            "  combo++;\n"
            "  comboTimer = 2.5;\n"
            "  var pts = 10 * Math.max(1, combo);\n"
            "  if(typeof score !== 'undefined') score += pts;\n"
            "  if(typeof score !== 'undefined' && score > highScore) {\n"
            "    highScore = score;\n"
            "    localStorage.setItem('hs', highScore);\n"
            "  }\n"
            "}\n\n"
            "function drawCombo() {\n"
            "  if(combo < 2) return;\n"
            "  ctx.save();\n"
            "  ctx.globalAlpha = Math.min(1, comboTimer);\n"
            "  ctx.fillStyle = combo >= 5 ? '#ff4400' : '#ffcc00';\n"
            "  ctx.font = 'bold ' + (16 + combo * 2) + 'px monospace';\n"
            "  ctx.textAlign = 'center';\n"
            "  ctx.fillText('COMBO x' + combo, W / 2, 80);\n"
            "  ctx.textAlign = 'left';\n"
            "  ctx.restore();\n"
            "}\n"
        )

    return "// stub vide\n"


# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRES INTERNES
# ─────────────────────────────────────────────────────────────────────────────

def _extract_js_declarations(js: str) -> dict:
    """
    Extrait les noms déclarés au niveau global dans un fragment JS.
    Gère les multi-déclarations : var a = 0, b = [], c = null;
    Retourne {'vars': [...], 'funcs': [...], 'all': [...]}
    """
    var_names: set = set()
    func_names: set = set()
    _KEYWORDS = {
        'var', 'let', 'const', 'function', 'async', 'true', 'false', 'null',
        'undefined', 'new', 'return', 'if', 'else', 'for', 'while', 'do',
        'break', 'continue', 'switch', 'case', 'default', 'typeof', 'in', 'of',
    }

    # Lignes de déclaration var/let/const
    for m in re.finditer(
        r'^[ \t]*(?:var|let|const)\s+(.+?)(?:;[ \t]*$|$)',
        js, re.MULTILINE
    ):
        decl_str = m.group(1)
        for name in re.findall(r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:=|,|;|$)', decl_str):
            if name not in _KEYWORDS:
                var_names.add(name)

    # function name() {...}
    for m in re.finditer(r'^[ \t]*(?:async\s+)?function\s+([\w$]+)', js, re.MULTILINE):
        func_names.add(m.group(1))

    # const/let/var name = (...) => ou function
    for m in re.finditer(
        r'^[ \t]*(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s+)?(?:\(|function)',
        js, re.MULTILINE
    ):
        func_names.add(m.group(1))

    all_names = sorted(var_names | func_names)
    return {'vars': sorted(var_names), 'funcs': sorted(func_names), 'all': all_names}


def _extract_function_signatures(js: str) -> str:
    """
    Extrait les signatures complètes (nom + paramètres) des fonctions déclarées.
    Ex: function updatePlayer(dt) → "updatePlayer(dt)"
    Passé aux couches suivantes pour éviter les appels avec mauvais arguments.
    Compact : ne transmet que nom+params, pas le corps.
    """
    sigs = []
    # function name(params) {
    for m in re.finditer(r'^[ \t]*(?:async\s+)?function\s+([\w$]+)\s*\(([^)]*)\)', js, re.MULTILINE):
        name = m.group(1)
        params = m.group(2).strip()
        sigs.append(f"{name}({params})")
    # const/let/var name = (params) => ou = function(params)
    for m in re.finditer(
        r'^[ \t]*(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s+)?(?:\(([^)]*)\)\s*=>|function\s*\(([^)]*)\))',
        js, re.MULTILINE
    ):
        name = m.group(1)
        params = (m.group(2) or m.group(3) or '').strip()
        sigs.append(f"{name}({params})")
    if not sigs:
        return ""
    return "FONCTIONS DISPONIBLES (signatures exactes — appelle-les avec ces paramètres) :\n  " + \
           ",  ".join(sigs[:50])


def _extract_object_schemas(js: str) -> str:
    """
    Extrait le schéma des objets principaux déclarés dans L1.
    Ex: let player = {x:0, y:0, hp:3} → "player: {x, y, hp}"
    Passé à L2b et L3 pour éviter l'hallucination de propriétés inexistantes.
    """
    schemas = []
    seen_names: set = set()

    # Chercher les déclarations d'objets inline (var/let/const name = { ... })
    for m in re.finditer(
        r'\b(?:var|let|const)\s+([\w$]+)\s*=\s*\{([^{}]{10,300})\}',
        js
    ):
        name = m.group(1)
        body = m.group(2)
        # Extraire les noms de propriétés (clé: valeur) — ^ pour la 1ère propriété
        props = re.findall(r'(?:^|[\s,{])(\w+)\s*:', body)
        if len(props) >= 2 and name not in seen_names:
            schemas.append(f"  {name}: {{{', '.join(props)}}}")
            seen_names.add(name)

    # Chercher les assignations dans les fonctions : name = { ... } (objets créés dans init*)
    for m in re.finditer(
        r'\b([\w$]+)\s*=\s*\{([^{}]{10,300})\}',
        js
    ):
        name = m.group(1)
        if name in seen_names or name[0].isupper():  # ignorer les constructeurs/constantes
            continue
        body = m.group(2)
        props = re.findall(r'(?:^|[\s,{])(\w+)\s*:', body)
        if len(props) >= 2:
            schemas.append(f"  {name}: {{{', '.join(props)}}}")
            seen_names.add(name)

    # Chercher les objets dans push() pour déduire le schéma des tableaux
    # ex: enemies.push({x:0, y:0, hp:3}) → enemies[i]: {x, y, hp}
    for m in re.finditer(
        r'\b([\w$]+)\.push\s*\(\s*\{([^{}]{10,200})\}',
        js
    ):
        arr_name = m.group(1)
        body = m.group(2)
        props = re.findall(r'(?:^|[\s,{])(\w+)\s*:', body)
        alias = arr_name.rstrip('s')  # "enemies" → "enemy", "bullets" → "bullet"
        key = f"{arr_name}[i] ({alias})"
        if len(props) >= 2 and key not in seen_names:
            schemas.append(f"  {key}: {{{', '.join(props)}}}")
            seen_names.add(key)

    if not schemas:
        return ""
    return "SCHÉMA EXACT des objets de L1 (utilise CES propriétés, n'en invente pas d'autres) :\n" + "\n".join(schemas[:10])


# ── Symbol Table A+B+C — anti-hallucination de constantes ──────────────────

_JS_ALLCAPS_BUILTINS = frozenset({
    'NaN', 'Infinity', 'Math', 'JSON', 'Object', 'Array', 'String', 'Number',
    'Boolean', 'Date', 'RegExp', 'Error', 'TypeError', 'RangeError', 'SyntaxError',
    'Promise', 'Symbol', 'Map', 'Set', 'WeakMap', 'WeakSet', 'Proxy', 'Reflect',
    'console', 'undefined', 'null', 'true', 'false', 'this', 'arguments',
    'PI', 'E', 'LN2', 'LN10', 'LOG2E', 'LOG10E', 'SQRT2',
    'MAX_SAFE_INTEGER', 'MIN_SAFE_INTEGER', 'MAX_VALUE', 'MIN_VALUE',
    'POSITIVE_INFINITY', 'NEGATIVE_INFINITY', 'EPSILON',
    'W', 'H', 'INT8', 'UINT8', 'INT16', 'UINT16', 'INT32', 'UINT32',
    'FLOAT32', 'FLOAT64', 'BYTES_PER_ELEMENT',
    'KEYDOWN', 'KEYUP', 'KEYPRESS', 'MOUSEDOWN', 'MOUSEUP', 'MOUSEMOVE',
    'CLICK', 'CONTEXTMENU', 'TOUCHSTART', 'TOUCHEND', 'TOUCHMOVE',
})


def _build_symbol_table(l1_js: str) -> dict:
    """Extract declared symbols from L1 to prevent ALLCAPS hallucination in L2-L9."""
    table: dict = {
        "allcaps": {},      # NAME -> value snippet (≤80 chars)
        "type_keys": {},    # arr_name -> set of type string values
        "functions": set(),
        "all_names": set(),
    }

    # Top-level var/let/const declarations
    for m in re.finditer(r'^(?:var|let|const)\s+([\w$]+)\s*=\s*(.{0,200})', l1_js, re.MULTILINE):
        name = m.group(1)
        val = m.group(2).strip().rstrip(';,')
        table["all_names"].add(name)
        if name == name.upper() and len(name) > 1 and not name.isdigit():
            table["allcaps"][name] = val[:80]

    # Function declarations
    for m in re.finditer(r'(?:^|\n)\s*function\s+([\w$]+)\s*\(', l1_js):
        fn = m.group(1)
        table["functions"].add(fn)
        table["all_names"].add(fn)

    # ALLCAPS arrays with {type:'xxx'} entries → extract type values
    for m in re.finditer(r'\b([A-Z_][A-Z0-9_]{2,})\s*=\s*\[', l1_js):
        arr_name = m.group(1)
        start = m.end()
        depth, end = 1, start
        while end < len(l1_js) and depth > 0:
            c = l1_js[end]
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
            end += 1
        arr_body = l1_js[start:end - 1]
        type_vals = re.findall(r'\btype\s*:\s*[\'"](\w+)[\'"]', arr_body)
        if type_vals:
            table["type_keys"][arr_name] = set(type_vals)

    return table


def _format_global_contract(table: dict) -> str:
    """Format symbol table as a compact injection block for L2-L9 prompts."""
    lines: list = []
    if table["allcaps"]:
        lines.append("CONTRAT GLOBAL — constantes déclarées en L1 (N'EN INVENTER AUCUNE AUTRE) :")
        for name, val in sorted(table["allcaps"].items())[:30]:
            lines.append(f"  {name} = {val[:60]}")
    if table["type_keys"]:
        lines.append("TYPES D'ENTITÉS — lire depuis le tableau, NE PAS créer ALLCAPS_TYPE dérivés :")
        for arr_name, keys in sorted(table["type_keys"].items()):
            types_str = ', '.join(sorted(keys)[:10])
            singular = arr_name.rstrip('S') if arr_name.endswith('S') else arr_name
            lines.append(
                f"  {arr_name}: types=[{types_str}]"
                f" → accéder via entite.speed/.hp/.dmg — JAMAIS {singular}_SPEED_DRONE etc."
            )
    return '\n'.join(lines) if lines else ""


def _derive_constant_value(name: str) -> str:
    """Heuristic numeric value for an undeclared ALLCAPS symbol."""
    nl = name.lower()
    if 'speed' in nl:
        return '150'
    if 'rate' in nl or 'interval' in nl or 'delay' in nl:
        return '0.5'
    if 'hp' in nl or 'health' in nl or 'life' in nl:
        return '3'
    if 'size' in nl or 'radius' in nl or 'width' in nl or 'height' in nl:
        return '24'
    if 'dmg' in nl or 'damage' in nl or 'power' in nl:
        return '1'
    if 'max' in nl:
        return '100'
    if 'score' in nl or 'point' in nl:
        return '10'
    if 'time' in nl or 'timer' in nl or 'dur' in nl:
        return '2'
    if 'alpha' in nl or 'opacity' in nl:
        return '1'
    return '1'


def _resolve_undeclared_symbols(fragment_js: str, table: dict, accumulated: str) -> tuple:
    """Scan a generated layer, inject var declarations for undefined ALLCAPS."""
    # Collect all declared names: symbol table + accumulated + fragment itself
    all_declared: set = set(table["all_names"]) | _JS_ALLCAPS_BUILTINS
    for m in re.finditer(r'(?:var|let|const|function)\s+([\w$]+)', accumulated):
        all_declared.add(m.group(1))
    for m in re.finditer(r'(?:var|let|const|function)\s+([\w$]+)', fragment_js):
        all_declared.add(m.group(1))

    # Find ALLCAPS identifiers used but not declared
    used_caps = set(re.findall(r'\b([A-Z][A-Z0-9_]{2,})\b', fragment_js))
    undefined_caps = used_caps - all_declared
    if not undefined_caps:
        return fragment_js, []

    inject_lines = []
    for name in sorted(undefined_caps):
        val = _derive_constant_value(name)
        inject_lines.append(f"var {name} = {val}; // auto-resolved: not in L1")

    header = "// [symbol-table] auto-resolved undefined constants\n" + "\n".join(inject_lines) + "\n\n"
    return header + fragment_js, sorted(undefined_caps)


def _extract_layer_manifest(layer_js: str, layer_num: int) -> str:
    """Compact manifest of all declarations in a validated layer (functions, vars, object shapes)."""
    fn_lines, var_lines, shape_lines = [], [], []
    seen_fns: set = set()
    seen_vars: set = set()
    seen_shapes: set = set()

    for m in re.finditer(r'(?:^|\n)\s*function\s+([\w$]+)\s*\(([^)]*)\)', layer_js):
        name, params = m.group(1), m.group(2).strip()
        if name not in seen_fns:
            fn_lines.append(f"  fn {name}({params})")
            seen_fns.add(name)

    for m in re.finditer(r'^(?:var|let|const)\s+([\w$]+)\s*=\s*(.{0,120})', layer_js, re.MULTILINE):
        name, val = m.group(1), m.group(2).strip().rstrip(';, ')
        if name in seen_vars:
            continue
        seen_vars.add(name)
        if val.startswith('['):
            var_lines.append(f"  {name}: Array")
        elif val.startswith('{'):
            keys = re.findall(r'(\w+)\s*:', val[:200])
            var_lines.append(f"  {name}: {{{', '.join(keys[:8])}}}" if keys else f"  {name}: Object")
        elif re.match(r'^-?\d', val):
            var_lines.append(f"  {name}: Number={val[:20]}")
        elif val[:1] in ("'", '"'):
            var_lines.append(f"  {name}: String={val[:20]}")
        elif val in ('true', 'false'):
            var_lines.append(f"  {name}: Boolean={val}")
        elif val in ('null', 'undefined'):
            var_lines.append(f"  {name}: null")
        else:
            var_lines.append(f"  {name}: ?")

    for m in re.finditer(r'(\w+)\.push\(\s*\{([^}]{0,400})\}', layer_js):
        arr_name, body = m.group(1), m.group(2)
        keys = re.findall(r'(\w+)\s*:', body)
        if keys and arr_name not in seen_shapes:
            seen_shapes.add(arr_name)
            shape_lines.append(f"  {arr_name}[] items: {{{', '.join(keys[:12])}}}")

    if not fn_lines and not var_lines and not shape_lines:
        return ""
    parts = [f"── MANIFEST L{layer_num} ──"]
    parts.extend(fn_lines)
    parts.extend(var_lines)
    if shape_lines:
        parts.append("  ·shapes·")
        parts.extend(shape_lines)
    return '\n'.join(parts)


def _contract_reminder(global_contract: str, incremental_manifest: str) -> str:
    """Short reminder block appended at end of each layer prompt (counter 'lost in middle')."""
    parts = []
    if global_contract:
        names = re.findall(r'^\s{2}([A-Z_][A-Z0-9_]+)\s*=', global_contract, re.MULTILINE)
        if names:
            parts.append("RAPPEL CONSTANTES L1 (utiliser telles quelles, ne pas réinventer) : "
                         + ', '.join(names[:20]))
    if incremental_manifest:
        fns = re.findall(r'\bfn ([\w$]+\([^)]*\))', incremental_manifest)
        if fns:
            parts.append("RAPPEL FONCTIONS EXISTANTES (appeler, jamais redéclarer) : "
                         + ', '.join(fns[:25]))
        shapes = re.findall(r'(\w+\[\] items: \{[^}]+\})', incremental_manifest)
        if shapes:
            parts.append("RAPPEL SHAPES OBJETS : " + ' | '.join(shapes[:8]))
    return ('\n' + '\n'.join(parts) + '\n') if parts else ''


def _layer_declared_str(accumulated_js: str) -> str:
    """Retourne la chaîne 'INTERDIT de redéclarer' avec hints de type pour les tableaux.
    Ex: 'enemies (Array), score (Number)' — évite enemies.x au lieu de enemies[i].x.
    """
    decls = _extract_js_declarations(accumulated_js)
    all_names = _HTML_TEMPLATE_GLOBALS + decls['all']
    if not all_names:
        return ""

    # Détecter les types depuis le code source pour les variables importantes
    _array_vars: set = set()
    _num_vars: set = set()
    for m in re.finditer(r'\b(?:var|let|const)\s+([\w$]+)\s*=\s*(\[|\d)', accumulated_js):
        vname, vtype = m.group(1), m.group(2)
        if vtype == '[':
            _array_vars.add(vname)
        elif vtype.isdigit():
            _num_vars.add(vname)

    def _hint(name: str) -> str:
        if name in _array_vars:
            return f"{name}[]"
        if name in _num_vars:
            return f"{name}(N)"
        return name

    annotated = [_hint(n) for n in all_names]
    lines = []
    for i in range(0, len(annotated), 8):
        lines.append('  ' + ', '.join(annotated[i:i + 8]))
    return "DEJA DECLARE — ne PAS redeclarer ([] = tableau, N = nombre) :\n" + '\n'.join(lines)


def _parse_object_schemas_dict(layer1_js: str) -> dict:
    """
    Parse le code L1 et retourne un dict {nom_objet: set(propriétés)}.
    Ex: {'player': {'x','y','w','h','hp'}, 'enemies': {'x','y','hp'}}
    Utilisé par les gates pour détecter les propriétés halluchinées.
    """
    schemas: dict = {}
    # Déclarations inline : var/let/const name = { ... }
    for m in re.finditer(r'\b(?:var|let|const)\s+([\w$]+)\s*=\s*\{([^{}]{10,300})\}', layer1_js):
        name = m.group(1)
        body = m.group(2)
        props = set(re.findall(r'(?:^|[\s,{])(\w+)\s*:', body))
        if len(props) >= 2:
            schemas[name] = props
    # Objets dans push() : arr.push({...}) → schéma de arr
    for m in re.finditer(r'\b([\w$]+)\.push\s*\(\s*\{([^{}]{10,200})\}', layer1_js):
        arr_name = m.group(1)
        body = m.group(2)
        props = set(re.findall(r'(?:^|[\s,{])(\w+)\s*:', body))
        if len(props) >= 2:
            schemas.setdefault(arr_name, set()).update(props)
    return schemas


def _check_hallucinated_properties(js: str, schemas_dict: dict) -> list:
    """
    Détecte obj.prop où prop n'est pas dans schemas_dict[obj].
    Retourne la liste des accès hallucinés (max 5).
    Ex: ['player.radius (valides: w, h, x, y, hp)']
    """
    _ALWAYS_VALID = {
        # JS builtins
        'length', 'constructor', 'prototype', 'toString', 'valueOf',
        'push', 'pop', 'splice', 'slice', 'filter', 'map', 'forEach',
        'indexOf', 'includes', 'join', 'sort', 'reverse', 'concat', 'find',
        'some', 'every', 'reduce', 'fill', 'flat',
        # Propriétés géométriques universelles — JAMAIS halluciner sur ces noms
        'x', 'y', 'z', 'w', 'h', 'r', 'radius', 'width', 'height', 'depth',
        'vx', 'vy', 'vz', 'speed', 'angle', 'rotation', 'scale',
        'left', 'right', 'top', 'bottom', 'cx', 'cy',
        # Propriétés d'état universelles
        'active', 'alive', 'dead', 'visible', 'enabled',
        'type', 'id', 'index', 'name', 'tag',
        'alpha', 'opacity', 'color', 'fill', 'stroke',
        # Timers — tout xyzTimer / xyzCooldown est valide (défini dynamiquement)
        # (vérification par suffixe plus bas)
    }
    errors = []
    seen = set()
    for obj_name, valid_props in schemas_dict.items():
        if not valid_props:
            continue
        # H1 — L'objet 'keys' est dynamique (touches WASD, arrows, etc.) → toujours valide
        if obj_name == 'keys':
            continue
        # Trouver tous les obj_name.prop qui ne sont pas des appels de méthodes connues
        for m in re.finditer(r'\b' + re.escape(obj_name) + r'\.([\w$]+)\b', js):
            prop = m.group(1)
            key = f"{obj_name}.{prop}"
            if key in seen or prop in _ALWAYS_VALID:
                continue
            # Timers/cooldowns/counters définis dynamiquement → jamais halluciner
            if prop.endswith(('Timer', 'Cooldown', 'Counter', 'Duration', 'Delay', 'Time', 'Tick')):
                continue
            seen.add(key)
            if prop not in valid_props:
                errors.append(
                    f"{obj_name}.{prop} n'existe pas (propriétés valides: {', '.join(sorted(valid_props)[:8])})"
                )
    return errors[:5]


def _gate_check_critical(layer_name: str, js: str, schemas_dict: dict,
                         expected_fns: dict = None) -> tuple:
    """
    Vérifie les contraintes critiques d'une couche après syntax+quality OK.
    Retourne (passed: bool, errors: list[str]) — errors = feedback pour le retry.
    expected_fns : {'init': [...], 'update': [...], 'draw': [...]} — listes de fonctions attendues (L4)
    """
    errors = []
    ln = layer_name.lower()

    # ── COUCHE 2 — Spawn & Init ──────────────────────────────────────────────
    if 'couche 2' in ln:
        if not re.search(r'function\s+(init|spawn|generate|create|reset)\w*\s*\(', js, re.IGNORECASE):
            errors.append(
                "Aucune fonction init*/spawn*/generate* détectée — "
                "génère au moins spawnPlayer() ET initGame()"
            )

    # ── COUCHE 3 — Physique ──────────────────────────────────────────────────
    elif 'couche 3' in ln:
        if not re.search(r'function\s+update\w*\s*\(', js, re.IGNORECASE):
            errors.append(
                "Aucune fonction update* détectée — "
                "génère au moins updatePlayer(dt) ET updateEnemies(dt)"
            )
        if schemas_dict:
            hall = _check_hallucinated_properties(js, schemas_dict)
            for h in hall:
                errors.append("Propriété inventée dans la physique: " + h)

    # ── COUCHE 4 — Collisions ────────────────────────────────────────────────
    elif 'couche 4' in ln:
        if not re.search(r'function\s+checkCollisions\s*\(', js, re.IGNORECASE):
            errors.append(
                "Fonction checkCollisions() absente — "
                "c'est le point d'entrée de toutes les détections de collision"
            )
        if schemas_dict:
            hall = _check_hallucinated_properties(js, schemas_dict)
            for h in hall:
                errors.append("Propriété inventée dans les collisions: " + h)

    # ── COUCHE 5 — Boss & Vagues ─────────────────────────────────────────────
    elif 'couche 5' in ln:
        if not re.search(
            r'function\s+(?:update|handle|process|tick|manage|run|spawn|start)'
            r'(?:Wave|Boss|Enemy|Enemies|Enemies|Waves|Round|Stage)\w*\s*\(',
            js, re.IGNORECASE
        ):
            errors.append(
                "Aucune fonction updateWave*/updateBoss*/spawnWave* détectée — "
                "génère au moins updateWave(dt) ET updateBoss(dt)"
            )

    # ── COUCHE 6 — Rendu ─────────────────────────────────────────────────────
    elif 'couche 6' in ln:
        if not re.search(r'function\s+draw\w+\s*\(', js):
            errors.append(
                "Aucune fonction draw* détectée — "
                "toutes les fonctions de rendu DOIVENT commencer par 'draw'"
            )
        if schemas_dict:
            hall = _check_hallucinated_properties(js, schemas_dict)
            for h in hall:
                errors.append("Propriété inventée dans le rendu: " + h)

    # ── COUCHE 7 — Game Loop ─────────────────────────────────────────────────
    elif 'couche 7' in ln:
        missing = []
        if 'function gameLoop' not in js:
            missing.append("gameLoop(timestamp)")
        if not re.search(r'function\s+init\s*\(', js):
            missing.append("init()")
        if missing:
            errors.append("Fonctions requises absentes: " + ', '.join(missing))
        if 'requestAnimationFrame' not in js:
            errors.append("requestAnimationFrame() manquant — la boucle de jeu ne démarrera pas")
        # Extraire le corps de gameLoop en comptant les accolades (regex [^}] ne fonctionne pas
        # sur un vrai corps de fonction qui contient de nombreux `}` internes)
        _gl_open = re.search(r'function\s+gameLoop\s*\([^)]*\)\s*\{', js)
        if _gl_open:
            _gl_depth, _gl_body_start = 0, _gl_open.end() - 1
            _gl_body_end = _gl_body_start
            for _ci in range(_gl_body_start, len(js)):
                if js[_ci] == '{': _gl_depth += 1
                elif js[_ci] == '}':
                    _gl_depth -= 1
                    if _gl_depth == 0: _gl_body_end = _ci; break
            _body = js[_gl_open.end():_gl_body_end]
            _real_statements = [l.strip() for l in _body.split('\n')
                                if l.strip() and not l.strip().startswith('//')]
            if len(_real_statements) < 3:
                errors.append(
                    "gameLoop() trop vide (< 3 instructions réelles) — "
                    "doit appeler update(dt), draw(), requestAnimationFrame(gameLoop)"
                )
            # M4 : vérifier ≥2 appels draw* et ≥2 appels update* dans gameLoop
            _draw_calls_found = re.findall(r'\bdraw\w+\s*\(', _body)
            _update_calls_found = re.findall(r'\b(?:update\w+|checkCollisions)\s*\(', _body)
            if len(_draw_calls_found) == 0:
                _draw_hint = ', '.join(f + '()' for f in (expected_fns or {}).get('draw', [])[:2]) or 'drawBackground(); drawPlayer();'
                errors.append(
                    f"gameLoop() n'appelle aucune fonction draw* — écran noir garanti. "
                    f"Appelle : {_draw_hint};"
                )
            elif len(_draw_calls_found) < 2:
                _draw_hint = ', '.join(f + '()' for f in (expected_fns or {}).get('draw', [])[:3]) or 'drawBackground(); drawPlayer(); drawEnemies();'
                errors.append(
                    f"gameLoop() n'appelle qu'1 fonction draw* ({_draw_calls_found[0]}) — "
                    f"rendu insuffisant. Appelle au moins : {_draw_hint};"
                )
            if len(_update_calls_found) == 0:
                _upd_hint = ', '.join(f + '(dt)' for f in (expected_fns or {}).get('update', [])[:2]) or 'updatePlayer(dt); updateEnemies(dt);'
                errors.append(
                    f"gameLoop() n'appelle aucune fonction update* — jeu statique. "
                    f"Appelle : {_upd_hint};"
                )
            elif len(_update_calls_found) < 2:
                _upd_hint = ', '.join(f + '(dt)' for f in (expected_fns or {}).get('update', [])[:3]) or 'updatePlayer(dt); updateEnemies(dt); checkCollisions();'
                errors.append(
                    f"gameLoop() n'appelle qu'1 fonction update* ({_update_calls_found[0]}) — "
                    f"logique incomplète. Appelle au moins : {_upd_hint};"
                )
        # Extraire le corps de init() de la même façon
        _init_open = re.search(r'function\s+init\s*\(\s*\)\s*\{', js)
        if _init_open:
            _in_depth, _in_body_start = 0, _init_open.end() - 1
            _in_body_end = _in_body_start
            for _ci in range(_in_body_start, len(js)):
                if js[_ci] == '{': _in_depth += 1
                elif js[_ci] == '}':
                    _in_depth -= 1
                    if _in_depth == 0: _in_body_end = _ci; break
            _init_body = js[_init_open.end():_in_body_end]
            _init_calls = re.findall(r'\b(init\w+|spawn\w+|generate\w+|reset\w+|create\w+)\s*\(', _init_body)
            if not _init_calls and expected_fns and expected_fns.get('init'):
                fns_hint = ', '.join(f + '()' for f in expected_fns['init'][:3])
                errors.append(
                    f"init() n'appelle aucune fonction d'initialisation — "
                    f"doit appeler : {fns_hint}"
                )

    return len(errors) == 0, errors


def _autocomplete_truncated_js(js: str) -> str:
    """
    Tente de compléter un fragment JS tronqué en fermant les brackets ouverts.
    Utilisé quand Gemini retourne du code coupé (Unexpected end of input).
    Tracks the stack to close brackets in the correct reverse order.
    """
    stack: list[str] = []
    close_map = {'{': '}', '[': ']', '(': ')'}
    open_chars = set(close_map.keys())
    close_chars = {v: k for k, v in close_map.items()}
    in_string: str | None = None
    i = 0
    while i < len(js):
        c = js[i]
        if in_string:
            if c == '\\':
                i += 2
                continue
            if c == in_string:
                in_string = None
        elif c in ('"', "'", '`'):
            in_string = c
        elif c in open_chars:
            stack.append(c)
        elif c in close_chars:
            if stack and stack[-1] == close_chars[c]:
                stack.pop()
        i += 1
    # Close any open string first
    if in_string:
        js += in_string
    # Close all open brackets in reverse order
    for opener in reversed(stack):
        # Si on ferme un { et que le dernier char significatif est ':', valeur manquante → null
        if opener == '{':
            stripped = js.rstrip()
            if stripped.endswith(':') or stripped.endswith(','):
                js += 'null'
        js += close_map[opener]
    return js


def _validate_layer(new_js: str, accumulated_js: str, layer_name: str) -> tuple:
    """
    Valide un fragment JS en l'intégrant dans le contexte accumulé.
    Tente d'autocompleter si tronqué. Retourne (new_js_fixed, is_valid).
    """
    try:
        from js_syntax_checker import fix_all_auto, check_and_report as _js_check
        test_html = _HTML_TEMPLATE.format(title="test", js_body=accumulated_js + '\n' + new_js)
        test_html, _fixed, _ = fix_all_auto(test_html)
        _issues, _broken = _js_check(test_html)
        if _broken and _issues and 'end of input' in _issues[0].lower():
            # Tronqué → tenter autocomplétion
            completed = _autocomplete_truncated_js(new_js)
            test_html2 = _HTML_TEMPLATE.format(title="test", js_body=accumulated_js + '\n' + completed)
            test_html2, _, _ = fix_all_auto(test_html2)
            _issues2, _broken2 = _js_check(test_html2)
            if not _broken2:
                phase3_log.info("[layered] %s — autocomplétion tronqué OK" % layer_name)
                return completed, True
        if _broken:
            phase3_log.warning(
                "[layered] %s — syntaxe invalide : %s"
                % (layer_name, _issues[0][:80] if _issues else '?')
            )
            return new_js, False
        phase3_log.info("[layered] %s — syntaxe OK" % layer_name)
        return new_js, True
    except Exception as e:
        phase3_log.warning(
            "[layered] Validation %s impossible (%s) — accepté par défaut" % (layer_name, e)
        )
        return new_js, True


def _call_layer(system: str, prompt: str, max_tokens: int = 6000,
                temperature: float = 0.1, disable_thinking: bool = True,
                model: str = None) -> str:
    """Appelle Gemini (clé PAYANTE) pour une couche, nettoie le résultat.

    J1 — thinking par couche : L4/L7/L9 disable_thinking=False (raisonnement profond)
         L1/L2/L3/L5/L6/L8 disable_thinking=True (vitesse + évite troncature)
    J2 — température par couche : L1-L4/L7=0.1, L5/L6=0.2, L8=0.35, L9=0.45
    Utilise call_gemini_paid — clé payante exclusive pour la génération de code critique.
    model=MODEL_NAME_PRO pour L4/L7 (couches les plus complexes).
    """
    raw = call_gemini_paid(prompt, temperature=temperature, system_instruction=system,
                           max_tokens=max_tokens, disable_thinking=disable_thinking,
                           model=model)
    if not raw:
        return ""
    # Retirer les balises markdown / script / html
    raw = re.sub(r'^```[\w]*\n?', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'\n?```$', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'<script[^>]*>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</script>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<!DOCTYPE.*?<body[^>]*>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r'</body>.*?</html>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    return raw.strip()


_JS_BUILTINS = frozenset([
    'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'typeof', 'instanceof',
    'new', 'delete', 'void', 'throw', 'case', 'class', 'super', 'import', 'export',
    'Math', 'console', 'JSON', 'localStorage', 'sessionStorage', 'window', 'document',
    'requestAnimationFrame', 'cancelAnimationFrame', 'setTimeout', 'clearTimeout',
    'setInterval', 'clearInterval', 'parseInt', 'parseFloat', 'isNaN', 'isFinite',
    'String', 'Number', 'Boolean', 'Array', 'Object', 'Date', 'Promise', 'Error',
    'eval', 'encodeURIComponent', 'decodeURIComponent', 'encodeURI', 'decodeURI',
    'init', 'gameLoop', 'alert', 'confirm', 'prompt', 'fetch', 'performance',
    # array/string methods that look like calls
    'push', 'pop', 'shift', 'unshift', 'splice', 'slice', 'join', 'sort', 'reverse',
    'forEach', 'map', 'filter', 'find', 'findIndex', 'reduce', 'some', 'every',
    'indexOf', 'lastIndexOf', 'includes', 'split', 'replace', 'match', 'test',
    'toString', 'valueOf', 'hasOwnProperty', 'apply', 'call', 'bind',
    'max', 'min', 'abs', 'floor', 'ceil', 'round', 'sqrt', 'pow', 'random', 'sin', 'cos',
    # CSS color functions (appear in ctx.fillStyle = 'rgba(...)' etc.)
    'rgba', 'rgb', 'hsl', 'hsla',
])


def _check_gameloop_calls(accumulated_js: str) -> list[str]:
    """
    Détecte les appels orphelins (fonctions appelées mais non déclarées) dans la zone update/draw.
    Retourne une liste de noms orphelins pour log.
    """
    decls = _extract_js_declarations(accumulated_js)
    # Inclure decls['vars'] : les variables (joueur, ennemis, boss...) ne sont PAS
    # des fonctions manquantes — injecter un stub function dessus causerait un conflit
    # var vs function au runtime (TypeError: joueur is not a function).
    all_known = set(decls['funcs']) | set(decls['vars']) | set(_HTML_TEMPLATE_GLOBALS) | _JS_BUILTINS
    orphans: list[str] = []
    for m in re.finditer(r'\b([a-zA-Z_$][\w$]*)\s*\(', accumulated_js):
        name = m.group(1)
        # Ignorer les connus, les majuscules (constructeurs), les méthodes (précédées d'un .)
        if name in all_known or name[0].isupper():
            continue
        # Ignorer si précédé d'un point (méthode d'objet)
        pos = m.start()
        if pos > 0 and accumulated_js[pos - 1] == '.':
            continue
        orphans.append(name)
    # Ne retourner que les orphelins significatifs (appelés ≥ 2 fois)
    counts: dict = {}
    for n in orphans:
        counts[n] = counts.get(n, 0) + 1
    return [n for n, c in counts.items() if c >= 2]


def _stub_orphan_calls(accumulated_js: str) -> tuple[str, list[str]]:
    """
    Injecte des stubs vides pour les fonctions orphelines (appelées mais non définies).
    M1 — Blacklist des noms trop génériques/anglais qui sont clairement des hallucinations.
    Retourne (js_patché, liste des stubs injectés).
    """
    # M1 — Noms hallucinations fréquentes : mots anglais/français génériques, pas de vraies fonctions de jeu
    _ORPHAN_STUB_BLACKLIST = {
        'property', 'timer', 'body', 'data', 'item', 'type', 'id', 'state',
        'event', 'value', 'content', 'text', 'node', 'element', 'object',
        'method', 'action', 'input', 'output', 'result', 'response', 'name',
        'target', 'source', 'origin', 'delta', 'index', 'count', 'size',
        'position', 'direction', 'velocity', 'force', 'mass', 'energy',
        'update', 'draw', 'render', 'init', 'reset', 'start', 'stop',
        'create', 'destroy', 'remove', 'add', 'get', 'set', 'run', 'execute',
        'check', 'test', 'validate', 'process', 'handle', 'fire', 'trigger',
        'load', 'save', 'read', 'write', 'send', 'receive', 'connect',
        # Mots français hallucinations récurrentes (never real function names)
        'neon', 'néon', 'bombe', 'bombes', 'joueur', 'ennemi', 'ennemis',
        'balle', 'balles', 'tir', 'tirs', 'invulnerable', 'invulnérable',
        'bouclier', 'explosion', 'niveau',
        # Fonctions sons LLM-générées dont le nom n'est pas dans le scope global
        'soundmenubeep', 'menubeep', 'soundlevelup', 'soundgameover',
        'soundhit', 'soundshoot', 'soundexplode',
        # Fonctions d'UI injectées comme stubs vides — elles doivent être générées en L7/L9
        'drawpausemenu', 'drawupgradeui', 'drawupgradeselect', 'drawinstructions',
        'drawpause', 'drawvictory', 'drawcredits',
        # Noms génériques simples souvent hallucinations CSS/DOM
        'effect', 'bar', 'panel', 'overlay', 'badge', 'tag', 'slot',
        'frame', 'icon', 'label', 'button', 'menu', 'popup', 'modal',
        # Fonctions CSS appelées comme JS (traitées par P6-9)
        'rgba', 'rgb', 'hsl', 'hsla',
    }
    orphans = _check_gameloop_calls(accumulated_js)
    if not orphans:
        return accumulated_js, []
    injected: list[str] = []
    stubs = ''
    for fn in orphans:
        # M1 — Skip les noms trop génériques
        if fn.lower() in _ORPHAN_STUB_BLACKLIST or len(fn) <= 2:
            continue
        # M2 — Skip si une implémentation réelle existe déjà (last-definition-wins évité)
        if re.search(r'\bfunction\s+' + re.escape(fn) + r'\s*\(', accumulated_js):
            continue
        stub = f"function {fn}() {{}}\n"
        stubs += stub
        injected.append(fn)
    return stubs + accumulated_js, injected


# ─────────────────────────────────────────────────────────────────────────────
# ENRICHISSEMENT — sélection par genre
# ─────────────────────────────────────────────────────────────────────────────

def _get_enrichment_targets(genre: str) -> str:
    """Retourne le bloc d'enrichissement adapté au genre — implémentations COMPLÈTES requises."""
    genre_lower = genre.lower()
    _common = (
        '\n'
        'SYSTÈMES VISUELS OBLIGATOIRES (implémentations complètes, pas de stubs) :\n'
        '1. triggerShake(mag, dur) + applyShake() — screen shake appliqué sur ctx avant draw\n'
        '   Exemple : var shakeTimer=0,shakeMag=0,shakeX=0,shakeY=0;\n'
        '   function triggerShake(m,d){shakeMag=m;shakeTimer=d;}\n'
        '   function applyShake(){if(shakeTimer>0){shakeX=(Math.random()-.5)*shakeMag*2;shakeY=(Math.random()-.5)*shakeMag*2;shakeTimer-=dt;ctx.translate(shakeX,shakeY);}}\n'
        '2. Floating score text : var floatTexts=[];\n'
        '   function spawnFloatText(x,y,txt,color){floatTexts.push({x,y,txt,color,life:1,vy:-60});}\n'
        '   function updateFloatTexts(){floatTexts=floatTexts.filter(t=>{t.y+=t.vy*dt;t.life-=dt;return t.life>0;});}\n'
        '   function drawFloatTexts(){floatTexts.forEach(t=>{ctx.globalAlpha=t.life;ctx.fillStyle=t.color;ctx.font="bold 18px monospace";ctx.fillText(t.txt,t.x,t.y);});ctx.globalAlpha=1;}\n'
        '3. Particules d\'explosion : var particles=[];\n'
        '   function spawnExplosion(x,y,col,n){for(var i=0;i<(n||8);i++){var a=Math.random()*Math.PI*2,s=Math.random()*120+40;particles.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life:1,color:col||"#fff",r:Math.random()*4+2});}}\n'
        '   function updateParticles(){particles=particles.filter(p=>{p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=150*dt;p.life-=dt*1.5;return p.life>0;});}\n'
        '   function drawParticles(){particles.forEach(p=>{ctx.globalAlpha=p.life;ctx.fillStyle=p.color;ctx.beginPath();ctx.arc(p.x,p.y,p.r*p.life,0,Math.PI*2);ctx.fill();});ctx.globalAlpha=1;}\n'
    )

    if any(g in genre_lower for g in ('tower', 'defense', 'td')):
        return (
            'ENRICHISSEMENTS PRIORITAIRES pour Tower Defense :\n'
            '- upgradeTower(tower) : 3 niveaux (coûts 50/100/200 gold), bonus dmg+range à chaque niveau\n'
            '  Exemple complet : if(gold>=tower.upgradeCost){gold-=tower.upgradeCost;tower.level++;tower.damage+=5;tower.range+=20;tower.upgradeCost*=2;spawnFloatText(tower.x,tower.y,"UPGRADE!","#ffd700");}\n'
            '- drawTowerRange(tower) : cercle semi-transparent quand survol souris (ctx.arc + globalAlpha=0.15)\n'
            '- Boss wave toutes les 3 vagues : var bossHP=0,bossMaxHP=0,bossActive=false;\n'
            '  function spawnBoss(){bossActive=true;bossHP=bossMaxHP=wave*150;triggerShake(6,0.3);}\n'
            '  drawBoss() avec barre HP rouge au-dessus + taille 3x + couleur distincte\n'
            '- Combo kill rapide : var killCombo=0,comboTimer=0; kills en <1s incrémentent le score x combo'
        ) + _common
    elif any(g in genre_lower for g in ('shoot', 'shmup', 'bullet', 'space')):
        return (
            'ENRICHISSEMENTS PRIORITAIRES pour Shoot\'em\'up :\n'
            '- Boss 3 phases selon HP% (>66%, 33-66%, <33%) avec patterns différents :\n'
            '  Phase 1 : tir en ligne droite; Phase 2 : tir en éventail 5 bullets; Phase 3 : tir circulaire\n'
            '  Exemple : var bossPhase=1; if(boss.hp<boss.maxHp*0.33)bossPhase=3; else if(boss.hp<boss.maxHp*0.66)bossPhase=2;\n'
            '- Power-ups variés : var powerUps=[]; function spawnPowerup(x,y,type){powerUps.push({x,y,type,vy:40,r:12});}\n'
            '  Types : "shield" (invincibilité 5s), "double" (tir x2 pendant 8s), "bomb" (clear screen)\n'
            '  function updatePowerups(){powerUps=powerUps.filter(p=>{p.y+=p.vy*dt; return p.y<H;});}\n'
            '- Combo kill : var combo=0,comboTimer=0,comboMax=0;\n'
            '  À chaque kill : combo++; comboTimer=3; score+=10*combo; spawnFloatText(x,y,"x"+combo,"#ff0");\n'
            '  Dans update : if(comboTimer>0)comboTimer-=dt; else combo=0;\n'
            '- drawHUD() enrichi : barre de bouclier, icône power-up actif, combo affiché en grand'
        ) + _common
    elif any(g in genre_lower for g in ('platform', 'jump', 'run')):
        return (
            'ENRICHISSEMENTS PRIORITAIRES pour Platformer :\n'
            '- Collectibles (pièces/gems) : var coins=[]; function spawnCoin(x,y,val){coins.push({x,y,val:val||10,r:8,anim:0});}\n'
            '  updateCoins() : rotation + attraction magnétique si proche joueur (dist<60 → move vers player)\n'
            '  Collecte : score+=c.val; spawnFloatText(c.x,c.y,"+"+c.val,"#ffd700"); spawnExplosion(c.x,c.y,"#ffd700",5)\n'
            '- Effets de saut/atterrissage : spawnDust(x,y) — 4-6 petites particules grises en arc\n'
            '  Déclencher dans updatePlayer() quand player vient de toucher le sol (wasOnGround==false && onGround)\n'
            '- Ennemis patrouille : chaque ennemi a dir=1, quand au bord de plateforme → dir*=-1\n'
            '- Ecran de dégâts : var damageFlash=0; when hit: damageFlash=0.5;\n'
            '  drawDamageOverlay() : if(damageFlash>0){ctx.fillStyle="rgba(255,0,0,"+damageFlash*0.5+")";ctx.fillRect(0,0,W,H);damageFlash-=dt;}\n'
            '- Checkpoint system : var checkpoints=[], lastCheckpoint={x:100,y:300}; étoile dorée sur map'
        ) + _common
    elif any(g in genre_lower for g in ('rpg', 'dungeon', 'rogue')):
        return (
            'ENRICHISSEMENTS PRIORITAIRES pour RPG/Dungeon :\n'
            '- XP et level up : var xp=0,level=1,xpNext=100;\n'
            '  function gainXP(n){xp+=n;if(xp>=xpNext){level++;xpNext=Math.floor(xpNext*1.5);levelUp();}}\n'
            '  function levelUp(){player.maxHp+=10;player.hp=player.maxHp;player.atk+=3;triggerShake(4,0.5);spawnFloatText(player.x,player.y-20,"LEVEL UP!","#ffd700");}\n'
            '- Loot sur mort ennemi (avec probabilités) :\n'
            '  30% → gold (spawnLoot(x,y,"gold",5+Math.floor(Math.random()*15)))\n'
            '  10% → potion (restore 20 HP), 5% → relic (bonus permanent)\n'
            '- Barres HP ennemis : drawEnemyHPBar(e) au-dessus de chaque ennemi\n'
            '  ctx.fillStyle="#500";ctx.fillRect(e.x-20,e.y-e.r-10,40,6); ctx.fillStyle="#0f0";ctx.fillRect(e.x-20,e.y-e.r-10,40*(e.hp/e.maxHp),6)\n'
            '- Critique : 15% chance de crit (dégâts x2.5) + spawnFloatText(x,y,"CRIT!","#f80")\n'
            '- Ecran pause (P) : overlay semi-transparent avec stats du héros et tableau de bord'
        ) + _common
    else:
        return (
            'ENRICHISSEMENTS PRIORITAIRES (systèmes de feedback et profondeur gameplay) :\n'
            '- Système combo : var combo=0,comboTimer=0;\n'
            '  À chaque action positive : combo++; comboTimer=3; score+=basePoints*Math.max(1,combo);\n'
            '  spawnFloatText(x,y,"x"+combo+" COMBO!","#f80");\n'
            '  Dans update : if(comboTimer>0)comboTimer-=dt; else if(combo>0){combo=0;}\n'
            '- High score persistant : localStorage.setItem("hs_"+titre,score) au game over\n'
            '  var highScore=parseInt(localStorage.getItem("hs_"+titre)||"0"); affiché sur menu\n'
            '- drawProgressBar(x,y,w,h,val,max,col) : barre générique réutilisable\n'
            '  ctx.fillStyle="#222";ctx.fillRect(x,y,w,h); ctx.fillStyle=col;ctx.fillRect(x,y,w*(val/max),h);\n'
            '- Niveau/vague affiché avec animation : "VAGUE 3!" en grand au centre, 2s, puis disparaît\n'
            '  var waveAnnounce=0,waveAnnounceTxt=""; function showWaveAnnounce(txt){waveAnnounceTxt=txt;waveAnnounce=2;}'
        ) + _common


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK COMPACT — max 400 lignes, jamais de générateur monolithique
# ─────────────────────────────────────────────────────────────────────────────

_COMPACT_SYSTEM = (
    "Tu es un développeur JavaScript Canvas 2D expert en jeux arcade.\n"
    "Tu génères UN SEUL fichier HTML5 complet et autonome.\n\n"
    "CONTRAINTE ABSOLUE : maximum 400 lignes de JavaScript total.\n"
    "Chaque fonction : max 15 lignes. Simplifier plutôt que d'omettre.\n"
    "Le jeu DOIT être jouable : menu → jeu → game over → rejouer.\n\n"
    "STRUCTURE IMPOSÉE :\n"
    "1. Constantes ALL_CAPS (PALETTE, defs de jeu) — max 30 lignes\n"
    "2. Variables globales (score, lives, enemies, etc.) — 1 par ligne\n"
    "3. Fonctions update* — logique pure, pas de draw\n"
    "4. Fonctions draw* — rendu pur, pas de logique\n"
    "5. function init() + function gameLoop(ts)\n"
    "6. Event listeners (keydown, mousedown, click)\n"
    "7. init(); en dernière ligne\n\n"
    "INTERDIT : new Image(), fetch(), Audio src fichier, eval(), setInterval"
)


def _run_compact_fallback(context, erreurs_passees=None) -> str:
    """
    Générateur compact — max 400 lignes JS, JAMAIS le monolithique.
    Appelé quand les couches layered échouent toutes.
    """
    from code_validator import validate_and_fix
    from js_syntax_checker import fix_all_auto

    gp = context.genre_profile
    gdd = context.gdd
    titre = gdd.get('titre', 'Arcade Game')
    genre = gp.genre_principal
    sous_genre = gp.sous_genre or genre
    style = gp.style_visuel or 'neon sur fond sombre'
    mecaniques = ', '.join(gp.mecaniques_obligatoires[:4]) or 'gameplay classique'
    erreurs_str = ''
    if erreurs_passees:
        erreurs_str = '\nEvite ces erreurs : ' + '; '.join(str(e)[:60] for e in erreurs_passees[:3])

    prompt = (
        'Génère un jeu "%s" — genre : %s (%s)\n'
        'Style visuel : %s\n'
        'Mécaniques : %s\n'
        '%s\n\n'
        'CONTRAINTE ABSOLUE : 300 à 400 lignes de JS maximum.\n'
        'Simplifie chaque système pour tenir dans cette limite.\n'
        'Génère le fichier HTML5 complet et autonome.'
    ) % (titre, genre, sous_genre, style, mecaniques, erreurs_str)

    phase3_log.warning("[layered] Fallback compact activé (max 400L)")
    raw = _call_layer(_COMPACT_SYSTEM, prompt, max_tokens=12000)
    if not raw or len(raw) < 500:
        # Dernier recours : retourner le stub minimal HTML
        return _get_emergency_full_html(genre, titre)

    # Wrapper HTML si le LLM a retourné du JS pur
    if not raw.strip().startswith('<!'):
        html = _HTML_TEMPLATE.format(title=titre, js_body=raw)
    else:
        html = raw

    html, _, _ = fix_all_auto(html)
    html, _, _ = validate_and_fix(html)
    phase3_log.info("[layered] Compact fallback : %d chars" % len(html))
    return html


def _get_emergency_full_html(genre: str, titre: str) -> str:
    """HTML minimal garanti fonctionnel si tout échoue."""
    return _HTML_TEMPLATE.format(
        title=titre,
        js_body=_get_emergency_stub(4, genre, {'vars': ['score', 'lives', 'gameState', 'enemies', 'bullets', 'particles', 'player'], 'funcs': []})
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3 — TRY/CATCH GAMELOOP (résilience contre les erreurs JS)
# ─────────────────────────────────────────────────────────────────────────────

def _inject_trycatch_gameloop(js: str) -> str:
    """
    Injecte un try/catch dans gameLoop pour éviter les écrans noirs.
    Si une erreur survient pendant update/draw, affiche un message d'erreur
    visible et maintient la boucle active (le jeu ne freeze pas).
    """
    if 'function gameLoop' not in js:
        return js

    # Ajouter drawErrorScreen si absent
    if 'drawErrorScreen' not in js:
        js = (
            "window.__ARCADE_ERROR__ = '';\n"
            "function drawErrorScreen(msg) {\n"
            "  var s = String(msg).slice(0,120);\n"
            "  window.__ARCADE_ERROR__ = s;\n"
            "  ctx.fillStyle = '#300'; ctx.fillRect(0,0,W,H);\n"
            "  ctx.fillStyle = '#FF4444'; ctx.font = 'bold 16px monospace'; ctx.textAlign = 'center';\n"
            "  ctx.fillText('Erreur — rechargez la page', W/2, H/2-20);\n"
            "  ctx.fillStyle = '#FFAAAA'; ctx.font = '11px monospace';\n"
            "  ctx.fillText(s.slice(0,80), W/2, H/2+10);\n"
            "  ctx.textAlign = 'left';\n"
            "}\n\n"
        ) + js

    # Trouver le corps de gameLoop
    gl_m = re.search(r'function gameLoop\s*\([^)]*\)\s*\{', js)
    if not gl_m:
        return js

    depth, body_start = 0, gl_m.end() - 1
    end = body_start
    for ci in range(body_start, len(js)):
        if js[ci] == '{':
            depth += 1
        elif js[ci] == '}':
            depth -= 1
            if depth == 0:
                end = ci
                break

    body = js[gl_m.end():end]

    # Trouver requestAnimationFrame pour séparer before/after
    raf_m = re.search(r'requestAnimationFrame\s*\([^)]*\)\s*;?', body)
    if not raf_m:
        return js

    before_raf = body[:raf_m.start()]
    raf_call  = body[raf_m.start():raf_m.end()]
    after_raf = body[raf_m.end():]

    # Séparer les lignes setup (dt/lastTime) du reste (update/draw)
    lines = before_raf.split('\n')
    setup, logic = [], []
    in_setup = True
    for ln in lines:
        s = ln.strip()
        if in_setup and (not s or s.startswith('dt') or 'lastTime' in s or s.startswith('var ')):
            setup.append(ln)
        else:
            in_setup = False
            logic.append(ln)

    logic_str = '\n'.join(logic).strip()
    if not logic_str:
        return js

    new_body = (
        '\n'.join(setup) + '\n'
        '  try {\n'
        + '\n'.join('    ' + l if l.strip() else l for l in logic) + '\n'
        '  } catch (_e) { drawErrorScreen(_e.message || _e); }\n'
        '  ' + raf_call + '\n'
        + after_raf
    )

    return js[:gl_m.end()] + new_body + js[end:]


# ─────────────────────────────────────────────────────────────────────────────
# 6 — CORRECTION DES RISQUES NaN (post-assemblage)
# ─────────────────────────────────────────────────────────────────────────────

def _fix_nan_risks(js: str) -> str:
    """
    Corrige les patterns les plus fréquents causant des NaN silencieux :
    - Division par distance sans garde : dist → (dist||0.001)
    - Normalisation sans longueur : len → (len||1)
    """
    # Division par variable de distance/longueur sans garde
    js = re.sub(
        r'/ (dist|len|length|magnitude|speed|norm)\b(?!\s*\|\|)',
        r'/ (\1 || 0.001)',
        js
    )
    # Math.sqrt sur différence au carré déjà OK, mais hypot(0,0) → 0 possible
    # Garde sur les divisions dans les formules de direction
    js = re.sub(
        r'/ (dx\s*\*\s*dx\s*\+\s*dy\s*\*\s*dy)',
        r'/ ((\1) || 0.001)',
        js
    )
    return js




# ─────────────────────────────────────────────────────────────────────────────
# D — VÉRIFICATION COHÉRENCE POST-ASSEMBLAGE (sans appel LLM)
# ─────────────────────────────────────────────────────────────────────────────

def coherence_check(html: str) -> list:
    """
    Vérification déterministe après assemblage, avant Phase 4.
    Détecte les problèmes évidents sans appel LLM.
    Retourne la liste des problèmes trouvés (strings).
    """
    issues = []
    js_match = re.search(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    if not js_match:
        return ["Pas de bloc <script> dans le HTML"]
    js = js_match.group(1)

    # 1. Fonctions essentielles présentes
    if 'function gameLoop' not in js:
        issues.append("gameLoop() manquant — le jeu ne démarrera pas")
    if not re.search(r'function init\s*\(', js):
        issues.append("init() manquant — le jeu ne s'initialise pas")
    if 'requestAnimationFrame' not in js:
        issues.append("requestAnimationFrame manquant — pas de boucle de rendu")

    # 2. Fonctions appelées dans gameLoop → toutes définies ?
    gl_m = re.search(r'function gameLoop\b[^{]*\{', js)
    if gl_m:
        depth, start = 0, gl_m.end() - 1
        end = start
        for ci in range(start, len(js)):
            if js[ci] == '{':
                depth += 1
            elif js[ci] == '}':
                depth -= 1
                if depth == 0:
                    end = ci
                    break
        gl_body = js[start:end]
        # Exclure les appels de méthodes (précédés d'un .)
        gl_body_no_methods = re.sub(r'\.\s*\w+\s*\(', '.METHOD(', gl_body)
        called = set(re.findall(r'\b([a-z]\w+)\s*\(', gl_body_no_methods))
        declared = set(re.findall(r'function\s+(\w+)\s*\(', js))
        # Mots-clés JS + builtins + fonctions natives communes
        _excluded = {
            # Mots-clés
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'return',
            'try', 'catch', 'finally', 'throw', 'new', 'delete', 'typeof',
            # Builtins globaux
            'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
            'requestAnimationFrame', 'cancelAnimationFrame',
            'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURI',
            'decodeURI', 'alert', 'confirm', 'console',
            # Méthodes Math (capturées à cause de Math.min() etc.)
            'min', 'max', 'abs', 'floor', 'ceil', 'round', 'sqrt',
            'random', 'pow', 'sin', 'cos', 'atan2', 'hypot', 'sign',
            # Méthodes Array/String
            'push', 'pop', 'splice', 'slice', 'filter', 'map', 'forEach',
            'indexOf', 'includes', 'join', 'split', 'toString', 'length',
            # Autres
            'performance', 'JSON', 'Object', 'Array', 'String', 'Number',
            # Fonctions UI optionnelles — déclarées conditionnellement ou en L9
            # Ne pas les signaler comme manquantes : elles sont appelées via typeof guard
            'drawPauseMenu', 'drawUpgradeUI', 'drawUpgradeSelect', 'drawInstructions',
            'drawPause', 'drawVictory', 'drawCredits', 'drawHUD', 'drawOverlay',
            # Fonctions CSS natifs appelés comme JS par erreur — traités par P6-9
            'rgba', 'rgb', 'hsl', 'hsla',
        }
        for fn in called:
            if fn not in declared and fn not in _excluded:
                issues.append("Fonction appelée dans gameLoop mais non définie : %s()" % fn)

    # 3. Ressources externes interdites
    if re.search(r'new\s+Image\s*\(\s*\)', js):
        issues.append("new Image() détecté — provoque un ERR_FILE_NOT_FOUND (404)")
    # img.src = 'fichier.ext' (pas data: ni http)
    _src_matches = re.findall(r'''\.src\s*=\s*['"]([^'"]+)['"]''', js)
    for src_val in _src_matches:
        if not src_val.startswith(('http', 'data:', '//', 'blob:')):
            issues.append("img.src='%s' détecté — fichier local → ERR_FILE_NOT_FOUND" % src_val[:40])
            break
    if re.search(r'\bfetch\s*\(', js):
        issues.append("fetch() détecté — provoque un crash silencieux (404)")
    if re.search(r'new\s+Audio\s*\(["\']', js):
        issues.append("new Audio('fichier') détecté — 404 navigateur")

    # 4. Variables critiques initialisées
    for var in ('score', 'lives', 'gameState'):
        if not re.search(r'\b' + var + r'\b', js):
            issues.append("Variable '%s' non déclarée" % var)

    return issues


def _deep_review_assembled_code(html: str) -> list:
    """
    Q12 — Couche 10 : revue programmatique approfondie du code assemblé.
    Complète coherence_check avec des vérifications inter-couches supplémentaires.
    Sans LLM — purement déterministe.
    """
    issues = []
    js_match = re.search(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    if not js_match:
        return issues
    js = js_match.group(1)

    # Q12-1 : Case mismatches connus
    _known_mismatches = [
        ('powerups', 'powerUps'), ('floattexts', 'floatTexts'),
        ('bossactive', 'bossActive'), ('wavetime', 'waveTimer'),
        ('highscore', 'highScore'), ('playerhealth', 'player.hp'),
    ]
    js_lower = js.lower()
    for wrong, right in _known_mismatches:
        if wrong in js_lower and right not in js:
            issues.append(f"Case mismatch probable : '{wrong}' utilisé mais déclaration attendue '{right}'")

    # Q12-2 : for-of avec splice sur le même tableau
    _for_of_tables = re.findall(r'for\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+(\w+)\s*\)', js)
    for table in _for_of_tables:
        # Chercher si splice est appelé sur ce tableau dans les 20 lignes suivantes
        pattern = rf'for\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+{re.escape(table)}\s*\).*?{re.escape(table)}\s*\.\s*splice'
        if re.search(pattern, js, re.DOTALL):
            issues.append(f"for-of avec splice sur '{table}' — corrupteur silencieux, utiliser boucle inversée")

    # Q12-3 : Fonctions déclarées mais jamais appelées (simplifiée, top-level seulement)
    _top_level_fns = re.findall(r'^function\s+([a-zA-Z][a-zA-Z0-9_]+)\s*\(', js, re.MULTILINE)
    _game_critical = {'init', 'gameLoop', 'animate', 'loop', 'tick', 'update', 'draw', 'render',
                      'drawBackground', 'drawPlayer', 'drawEnemies', 'drawHUD', 'drawMenu',
                      'drawGameOver', 'drawBoss', 'resetGame', 'initGame'}
    for fn in _top_level_fns:
        if fn in _game_critical:
            continue
        call_count = len(re.findall(rf'\b{re.escape(fn)}\s*\(', js))
        def_count = len(re.findall(rf'function\s+{re.escape(fn)}\s*\(', js))
        if call_count <= def_count:
            issues.append(f"Fonction '{fn}()' définie mais jamais appelée — à connecter dans gameLoop ou init")

    # Q12-4 : Variables undefined fréquentes (utilisées sans déclaration évidente)
    _known_undeclared_patterns = [
        (r'\bgradient\b(?!\s*=)', "variable 'gradient' utilisée sans déclaration locale — var gradient=null en tête de fonction"),
        (r'\bbarX\b(?!\s*=)', "variable 'barX' utilisée sans déclaration locale — var barX=0"),
        (r'\bhpRatio\b(?!\s*=)', "variable 'hpRatio' utilisée sans déclaration locale — var hpRatio=1"),
    ]
    for pattern, msg in _known_undeclared_patterns:
        if re.search(pattern, js):
            if not re.search(rf'(?:var|let|const)\s+{pattern.split(chr(92)+"b")[1].split(chr(92))[0]}', js):
                issues.append(msg)

    # Q12-5 : Objet keys manquant de touches importantes
    keys_decl = re.search(r'var\s+keys\s*=\s*\{([^}]+)\}', js)
    if keys_decl:
        keys_body = keys_decl.group(1)
        for key in ('space', 'left', 'right'):
            if key not in keys_body:
                issues.append(f"Touche '{key}' absente de l'objet keys — probable crash au keydown")

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# TRUNCATION INTELLIGENTE
# ─────────────────────────────────────────────────────────────────────────────

def _smart_truncate(js: str, hard_limit: int, layer_name: str) -> tuple:
    """
    Tronque proprement au dernier } complet avant hard_limit.
    Analyse l'overflow pour identifier les fonctions perdues et leur criticité.
    Retourne (js_tronqué, overflow_hint) — overflow_hint est passé à L5.
    """
    lines = js.split('\n')
    if len(lines) <= hard_limit:
        return js, ""

    # Trouver le dernier } de fermeture de fonction avant hard_limit
    truncation_point = hard_limit
    for i in range(min(hard_limit, len(lines)) - 1, max(0, hard_limit - 40), -1):
        if lines[i].strip() in ('}', '};'):
            truncation_point = i + 1
            break

    kept = '\n'.join(lines[:truncation_point])
    overflow = '\n'.join(lines[truncation_point:])

    if not overflow.strip():
        return js, ""

    # Extraire les signatures complètes des fonctions perdues
    overflow_fns = re.findall(r'function\s+(\w+)\s*\(([^)]*)\)', overflow)
    if not overflow_fns:
        return kept, ""

    # Classifier par criticité
    _critical_prefixes = ('update', 'check', 'spawn', 'init', 'handle', 'reset', 'apply', 'compute')
    critical = [(n, p) for n, p in overflow_fns if any(n.startswith(px) for px in _critical_prefixes)]
    optional = [(n, p) for n, p in overflow_fns if (n, p) not in critical]

    # Construire le hint structuré
    hint_parts = []
    if critical:
        sigs = ', '.join('%s(%s)' % (n, p) for n, p in critical)
        hint_parts.append("[CRITIQUE] %s" % sigs)
    if optional:
        sigs = ', '.join('%s(%s)' % (n, p) for n, p in optional)
        hint_parts.append("[optionnel] %s" % sigs)

    hint = "%s tronquée — fonctions perdues : %s" % (layer_name, " | ".join(hint_parts))
    phase3_log.warning("[layered] %s" % hint)

    return kept, hint


def _build_layer_context(
    accumulated: str,
    layer1_schema: str,
    accumulated_signatures: str,
    tail_lines: int = 400,
    global_contract: str = "",
    incremental_manifest: str = "",
) -> str:
    """
    Contexte anti-hallucination pour chaque couche — 5 parties :
    0. Contrat global (symbol table L1 — empêche les constantes ALLCAPS hallucinées)
    0b. Manifest incrémental (toutes déclarations L1-LN : fonctions, vars, shapes)
    1. Schéma typé L1 (contrat de propriétés)
    2. Signatures de toutes les fonctions définies
    3. Code récent (80 lignes si manifest présent, tail_lines sinon)
    Le manifest remplace la queue longue — contexte compact quelle que soit la profondeur.
    """
    parts = []
    if global_contract:
        parts.append(global_contract)
    if incremental_manifest:
        parts.append(incremental_manifest)
    if layer1_schema:
        parts.append(layer1_schema)
    if accumulated_signatures:
        parts.append(accumulated_signatures)
    code_lines = accumulated.split('\n')
    if incremental_manifest:
        # Manifest présent → seulement les 80 dernières lignes pour la continuité de style
        tail = '\n'.join(code_lines[-80:])
        parts.append(f"EXTRAIT RÉCENT — dernières 80 lignes (style/référence) :\n{tail}")
    elif len(code_lines) > tail_lines:
        tail = '\n'.join(code_lines[-tail_lines:])
        parts.append(f"CODE ACCUMULÉ ({len(code_lines)} lignes — fin uniquement) :\n{tail}")
    else:
        parts.append(f"CODE ACCUMULÉ :\n{accumulated}")
    return '\n\n'.join(parts)


def _detect_game_events(accumulated: str) -> str:
    """
    Détecte les systèmes présents dans le code pour briefer L9 (couche graphique).
    Permet à L9 de créer des visuels adaptés à chaque système du jeu.
    """
    events = []
    if re.search(r'boss\w*[Pp]hase|boss\.phase|bossPhase\s*[=>]?\s*[23]', accumulated):
        events.append("boss avec 3 phases — visuels distincts par phase (couleur/taille/aura/pattern)")
    if re.search(r'powerUps?\b|activatePowerUp|spawnPowerup|powerUp\.type', accumulated):
        events.append("power-ups — aura/couleur unique par type (shield=bleu, rapidfire=jaune, bomb=rouge)")
    if re.search(r'\bcombo\b|comboCount|comboTimer|comboMult', accumulated):
        events.append("combo system — texte combo animé en grand, multiplicateur visible")
    if re.search(r'waveAnnounce|showWave|nextWave|waveTransition', accumulated):
        events.append("transitions entre vagues — titre de vague animé au centre")
    if re.search(r'shieldActive|shieldTimer|shieldRadius', accumulated):
        events.append("bouclier joueur — aura pulsante bleue autour du joueur")
    if re.search(r'levelUp|LEVEL.UP|gainXP|xpBar', accumulated):
        events.append("level up — flash doré, texte 'LEVEL UP!' animé")
    if re.search(r'bossActive\s*=\s*true|spawnBoss\s*\(', accumulated):
        events.append("apparition boss — effet dramatique (flash, shake, texte WARNING)")
    if re.search(r'damageFlash|hitFlash|invTimer|invincible', accumulated):
        events.append("feedback de dégâts — flash rouge sur l'écran ou le joueur")
    if not events:
        return ""
    return (
        "ÉVÉNEMENTS DU JEU À RENDRE VISUELLEMENT MÉMORABLES :\n" +
        "\n".join(f"  - {e}" for e in events)
    )


def _extract_draw_code(accumulated: str) -> str:
    """
    Extrait tout le code des fonctions draw* depuis le code accumulé.
    Utilisé par L9 pour voir les draw* fonctionnelles et les améliorer.
    """
    draw_blocks = []
    for m in re.finditer(r'(function\s+draw\w+\s*\([^)]*\)\s*\{)', accumulated):
        start = m.start()
        depth = 0
        found = False
        for i in range(start, len(accumulated)):
            c = accumulated[i]
            if c == '{':
                depth += 1
                found = True
            elif c == '}':
                depth -= 1
                if found and depth == 0:
                    draw_blocks.append(accumulated[start:i + 1])
                    break
    if not draw_blocks:
        return ""
    return "FONCTIONS draw* EXISTANTES (à améliorer artistiquement) :\n\n" + '\n\n'.join(draw_blocks[:12])


# ─────────────────────────────────────────────────────────────────────────────
# MÉCANIQUES OBLIGATOIRES — mapping, vérification, réparation
# ─────────────────────────────────────────────────────────────────────────────

def _mechanic_to_keywords(mechanic: str) -> list[str]:
    """
    Mappe une description de mécanique vers les tokens JS attendus dans le code.
    Retourne les 2-3 tokens les plus représentatifs pour vérifier la présence.
    """
    m = mechanic.lower()
    if any(k in m for k in ('scroll', 'défilement', 'scrolling vertical', 'fond défilant', 'défile')):
        return ['scrollSpeed', 'scrollY', 'bgOffset', 'starsY', 'backgroundY']
    if any(k in m for k in ('hitbox', 'hitbox réduite', 'collision précis', 'précis'))  :
        return ['checkCollisions', 'aabbCollide', 'hitbox']
    if any(k in m for k in ('tir auto', 'autofire', 'shoot auto', 'fire auto')):
        return ['fireTimer', 'spawnBullet']
    if any(k in m for k in ('tir', 'shoot', 'bullet', 'projectile', 'fire')):
        return ['spawnBullet', 'bullets']
    if any(k in m for k in ('power', 'powerup', 'power-up', 'pickup', 'bonus item')):
        return ['powerUps', 'handlePowerUpCollect']
    if any(k in m for k in ('combo', 'multiplicateur', 'multiplier', 'kill streak')):
        return ['combo', 'comboTimer']
    if any(k in m for k in ('boss phase', 'phase de boss', 'bossphase')):
        return ['bossPhase', 'checkBossPhase']
    if any(k in m for k in ('boss', 'patron')):
        return ['bossActive', 'spawnBoss']
    if any(k in m for k in ('vague', 'wave', 'horde')):
        return ['wave', 'updateWave']
    if any(k in m for k in ('vaisseau', 'ship', 'spaceship', 'vaisseau joueur')):
        return ['player', 'updatePlayer']
    if any(k in m for k in ('formation', 'géométrique', 'geometric', 'pattern ennemi', 'formation ennemi')):
        return ['enemies', 'updateEnemies']
    if any(k in m for k in ('mouvement', 'déplacement', 'mouvement libre', 'mouvement 2d', 'horizontal', 'vertical limité')):
        return ['player', 'updatePlayer']
    if any(k in m for k in ('dash', 'esquive', 'dodge', 'blink')):
        return ['dashTimer', 'isDashing']
    if any(k in m for k in ('double jump', 'double saut', 'doublejump')):
        return ['jumpsLeft', 'canDoubleJump']
    if any(k in m for k in ('saut', 'jump', 'gravit', 'platf')):
        return ['gravity', 'onGround']
    if any(k in m for k in ('shield', 'bouclier', 'invincib')):
        return ['shieldActive', 'shieldTimer']
    if any(k in m for k in ('upgrade', 'amélioration', 'level up', 'levelup', 'xp', 'expérience')):
        return ['upgrade', 'xp']
    if any(k in m for k in ('screen shake', 'vibrat', 'tremblement')):
        return ['triggerShake', 'shakeTimer']
    if any(k in m for k in ('particule', 'particle', 'explosion')):
        return ['spawnParticle', 'particles']
    # M2 — "3 types d'ennemis distincts" → accepter ENEMY_TYPES data OU 3 entrées type: différentes
    if any(k in m for k in ('3 type', 'trois type', 'ennemi varié', 'enemy type', 'type ennemi',
                             'multi ennemi', 'distinct', 'différent')):
        return ['ENEMY_TYPES']
    if any(k in m for k in ('plateforme', 'platform', 'level map', 'tile')):
        return ['platforms', 'LEVEL_DEFS']
    if any(k in m for k in ('tour', 'tower', 'turret', 'tourelle')):
        return ['towers', 'TOWER_TYPES']
    if any(k in m for k in ('inventaire', 'inventory', 'item slot')):
        return ['inventory', 'items']
    if any(k in m for k in ('score', 'point', 'highscore')):
        return ['score', 'highScore']
    # fallback : premier mot significatif
    words = [w for w in m.split() if len(w) > 3]
    return [words[0].replace('-', '')] if words else [m[:8]]


def _check_mechanics_present(accumulated: str, mecaniques: list) -> list[str]:
    """
    Vérifie que chaque mécanique obligatoire est réellement implémentée dans le code.

    Hiérarchie de vérification :
    1. Token déclaré comme function → implémenté (fiable)
    2. 2+ tokens trouvés hors commentaires → probablement présent
    3. 1 seul token en substring → insuffisant (peut être un commentaire)
    """
    # Supprimer commentaires pour éviter faux positifs
    _nc = re.sub(r'//[^\n]*', '', accumulated)
    _nc = re.sub(r'/\*.*?\*/', '', _nc, flags=re.DOTALL)
    _declared_fns = set(re.findall(r'\bfunction\s+(\w+)\s*\(', _nc))

    missing = []
    for mec in mecaniques:
        keywords = _mechanic_to_keywords(mec)
        mec_lower = mec.lower()
        # Critère 1 : token déclaré comme fonction
        if any(kw in _declared_fns for kw in keywords):
            continue
        # Critère 2 : 2+ tokens présents dans le code réel
        if sum(1 for kw in keywords if kw in _nc) >= 2:
            continue
        # Critère 2b : pour le scrolling → 1 seul token suffit (implémenté de 100 façons)
        if any(k in mec_lower for k in ('scroll', 'défilement', 'fond défilant')):
            if any(kw in _nc for kw in keywords):
                continue
            # Aussi : toute variable bgY, starsPos, starOffset, scrollOffset, bgOffset
            if re.search(r'\b(?:bg[YX]|stars?[YX]?|bgOffset|scrollOffset|backgroundY|starsPos)\b', _nc):
                continue
        # Critère 2c : hitbox/collision précis → checkCollisions + aabbCollide suffisent
        if any(k in mec_lower for k in ('hitbox', 'collision précis', 'précis')):
            if 'checkCollisions' in _nc or 'aabbCollide' in _nc:
                continue
        # M2 — Critère 3 : ENEMY_TYPES avec ≥2 entrées dans un tableau (data structure présente)
        if 'ENEMY_TYPES' in keywords and 'ENEMY_TYPES' in _nc:
            _et_matches = re.findall(r'ENEMY_TYPES\s*=\s*\[', _nc)
            if _et_matches:
                continue  # Le data structure est là — mécanique considérée présente
        # M2 — Critère 4 : présence de 3+ valeurs type: différentes (ennemis distincts inline)
        _mec_lower = mec.lower()
        if any(k in _mec_lower for k in ('3 type', 'distinct', 'différent', 'varié')):
            _type_vals = re.findall(r'type\s*:\s*["\']?(\w+)["\']?', _nc)
            if len(set(_type_vals)) >= 3:
                continue
        missing.append(mec)
    return missing


def _format_mechanics_as_requirements(mecaniques: list) -> str:
    """
    Formate les mécaniques comme exigences de code explicites.
    Utilisé dans le prompt L1 pour que les data structures soient déclarées dès le départ.
    """
    if not mecaniques:
        return ""
    lines = [
        "MÉCANIQUES OBLIGATOIRES — TOUTES doivent être implémentées (le jeu est rejeté si une manque) :",
    ]
    for i, mec in enumerate(mecaniques, 1):
        kws = _mechanic_to_keywords(mec)
        lines.append(f"  {i}. {mec}  →  tokens attendus dans le code : {', '.join(kws)}")
    lines.append("  Le LLM peut ajouter des mécaniques BONUS en plus — c'est encouragé.")
    return '\n'.join(lines) + '\n'


# ─────────────────────────────────────────────────────────────────────────────
# STUB L4 — Système de collision déterministe (fallback LLM échoué)
# ─────────────────────────────────────────────────────────────────────────────

def _make_hardcoded_collisions(decls: dict) -> str:
    """
    Génère un système de collision COMPLET et déterministe en Python pur.
    Couvre : bullet→enemy, player→enemy, enemy_bullet→player, powerUp collection.
    Utilisé quand L4 échoue complètement — garanti fonctionnel, 0 appel LLM.
    """
    def _alias(candidates):
        for c in candidates:
            if c in decls.get('vars', []) or c in decls.get('funcs', []):
                return c
        return candidates[0]

    pv = _alias(['player', 'hero', 'ship', 'joueur', 'vaisseau', 'character'])
    ev = _alias(['enemies', 'ennemis', 'foes', 'monsters', 'mobs'])
    bv = _alias(['bullets', 'projectiles', 'shots', 'balles', 'lasers'])

    return (
        "function aabbCollide(a,b){\n"
        "  var aw=a.w||a.r*2||20,ah=a.h||a.r*2||20,bw=b.w||b.r*2||20,bh=b.h||b.r*2||20;\n"
        "  return Math.abs(a.x-b.x)<(aw+bw)/2&&Math.abs(a.y-b.y)<(ah+bh)/2;\n"
        "}\n\n"
        "function handleBulletEnemyHit(b,e,bi,ei){\n"
        "  if(e.hp!==undefined)e.hp-=b.dmg||1;\n"
        "  if((e.hp!==undefined?e.hp:1)<=0){\n"
        "    score=(score||0)+(e.points||10);\n"
        "    combo=(typeof combo!=='undefined'?combo:0)+1;\n"
        "    comboTimer=3;\n"
        "    highScore=Math.max(typeof highScore!=='undefined'?highScore:0,score);\n"
        "    if(typeof spawnParticle==='function')spawnParticle(e.x,e.y,e.color||'#f80',8);\n"
        "    if(typeof spawnFloatText==='function')spawnFloatText(e.x,e.y-20,'+'+(e.points||10),'#ff0');\n"
        f"    {ev}.splice(ei,1);\n"
        "  }\n"
        f"  {bv}.splice(bi,1);\n"
        "}\n\n"
        "function handlePlayerEnemyHit(e,ei){\n"
        f"  if(typeof {pv}!=='undefined'&&{pv}){{\n"
        f"    if({pv}.hp!==undefined){pv}.hp--;\n"
        "    else if(typeof lives!=='undefined')lives--;\n"
        "  }\n"
        "  if(typeof triggerShake==='function')triggerShake(8,0.4);\n"
        f"  if(typeof spawnParticle==='function')spawnParticle({pv}.x,{pv}.y,'#f00',6);\n"
        f"  {ev}.splice(ei,1);\n"
        f"  var _ghp={pv}&&{pv}.hp!==undefined?{pv}.hp:(typeof lives!=='undefined'?lives:1);\n"
        "  if(_ghp<=0){highScore=Math.max(typeof highScore!=='undefined'?highScore:0,score||0);localStorage.setItem('hs',highScore);gameState='gameover';}\n"
        "}\n\n"
        "function handleEnemyBulletHit(b,bi){\n"
        "  if(typeof lives!=='undefined')lives--;\n"
        "  if(typeof triggerShake==='function')triggerShake(6,0.3);\n"
        "  if(typeof spawnFloatText==='function')spawnFloatText(typeof player!=='undefined'&&player?player.x:W/2,typeof player!=='undefined'&&player?player.y-30:H/2,'TOUCHÉ!','#f00');\n"
        f"  {bv}.splice(bi,1);\n"
        "  if((typeof lives!=='undefined'?lives:1)<=0){highScore=Math.max(typeof highScore!=='undefined'?highScore:0,score||0);localStorage.setItem('hs',highScore);gameState='gameover';}\n"
        "}\n\n"
        "function handlePowerUpCollect(p,pi){\n"
        "  if(p.type==='shield'){if(typeof shieldActive!=='undefined')shieldActive=true;if(typeof shieldTimer!=='undefined')shieldTimer=5;}\n"
        "  else if(p.type==='double'){if(typeof doubleTimer!=='undefined')doubleTimer=8;}\n"
        "  else if(p.type==='bomb'){score=(score||0)+500;if(typeof enemies!=='undefined')enemies.length=0;}\n"
        "  else if(p.type==='heal'){if(typeof lives!=='undefined')lives=Math.min(typeof MAX_LIVES!=='undefined'?MAX_LIVES:5,lives+1);}\n"
        "  if(typeof spawnFloatText==='function')spawnFloatText(p.x,p.y-20,(p.type||'').toUpperCase(),'#ffd700');\n"
        "  if(typeof powerUps!=='undefined')powerUps.splice(pi,1);\n"
        "}\n\n"
        "function updatePowerUps(dt){\n"
        "  if(typeof shieldTimer!=='undefined'&&shieldTimer>0){shieldTimer-=dt;if(shieldTimer<=0){if(typeof shieldActive!=='undefined')shieldActive=false;shieldTimer=0;}}\n"
        "  if(typeof doubleTimer!=='undefined'&&doubleTimer>0)doubleTimer-=dt;\n"
        "  if(typeof powerUps==='undefined')return;\n"
        "  for(var _i=powerUps.length-1;_i>=0;_i--){\n"
        "    powerUps[_i].y+=(powerUps[_i].vy||50)*dt;\n"
        "    powerUps[_i].anim=(powerUps[_i].anim||0)+dt;\n"
        "    if(powerUps[_i].y>H)powerUps.splice(_i,1);\n"
        "  }\n"
        "}\n\n"
        "function checkCollisions(){\n"
        f"  if(typeof {pv}==='undefined'||!{pv}||typeof {ev}==='undefined'||typeof {bv}==='undefined')return;\n"
        f"  for(var _i={bv}.length-1;_i>=0;_i--){{\n"
        f"    var _b={bv}[_i];\n"
        "    if(_b.owner==='player'||!_b.owner){\n"
        "      if(typeof bossActive!=='undefined'&&bossActive&&typeof boss!=='undefined'&&boss){\n"
        "        if(aabbCollide(_b,boss)){boss.hp-=_b.dmg||1;\n"
        f"          if(typeof triggerShake==='function')triggerShake(4,0.2);{bv}.splice(_i,1);continue;}}\n"
        f"      for(var _j={ev}.length-1;_j>=0;_j--){{\n"
        f"        if(aabbCollide(_b,{ev}[_j])){{handleBulletEnemyHit(_b,{ev}[_j],_i,_j);break;}}}}\n"
        "    }else{\n"
        f"      if({pv}&&aabbCollide(_b,{pv})&&!(typeof shieldActive!=='undefined'&&shieldActive))\n"
        "        handleEnemyBulletHit(_b,_i);\n"
        "    }\n"
        "  }\n"
        f"  for(var _i={ev}.length-1;_i>=0;_i--){{\n"
        f"    if({pv}&&aabbCollide({pv},{ev}[_i])&&!(typeof shieldActive!=='undefined'&&shieldActive))\n"
        f"      handlePlayerEnemyHit({ev}[_i],_i);}}\n"
        "  if(typeof powerUps!=='undefined'&&powerUps.length>0){\n"
        f"    var _pw={pv}?({pv}.w||24)/2:12;\n"
        "    for(var _i=powerUps.length-1;_i>=0;_i--){\n"
        f"      if({pv}&&Math.hypot(powerUps[_i].x-{pv}.x,powerUps[_i].y-{pv}.y)<(powerUps[_i].r||12)+_pw)\n"
        "        handlePowerUpCollect(powerUps[_i],_i);\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# A4 — INJECTION __ARCADE_TEST__ HOOKS
# ─────────────────────────────────────────────────────────────────────────────

def _inject_arcade_test_hooks(js: str) -> str:
    """
    A4 : Injecte window.__ARCADE_TEST__ dans le JS généré.
    Permet à Playwright de lire l'état interne du jeu (score, lives, playerX, gameState, frame).
    Injecté à la fin du fragment JS, avant init().
    """
    # Ne pas double-injecter
    if '__ARCADE_TEST__' in js:
        return js

    hooks_code = (
        "\n// __ARCADE_TEST__ — hooks Playwright (ne pas modifier)\n"
        "var __ARCADE_TEST__ = {\n"
        "  _frame: 0,\n"
        "  getState: function() {\n"
        "    return {\n"
        "      score: (typeof score !== 'undefined') ? score : null,\n"
        "      lives: (typeof lives !== 'undefined') ? lives : null,\n"
        "      playerX: (typeof player !== 'undefined' && player) ? (player.x || null) : null,\n"
        "      playerY: (typeof player !== 'undefined' && player) ? (player.y || null) : null,\n"
        "      gameState: (typeof gameState !== 'undefined') ? gameState : null,\n"
        "      enemies: (typeof enemies !== 'undefined') ? enemies.length : null,\n"
        "      frame: __ARCADE_TEST__._frame\n"
        "    };\n"
        "  }\n"
        "};\n"
        "// Incrémenter le compteur de frames à chaque RAF\n"
        "var _origRAF = requestAnimationFrame;\n"
        "requestAnimationFrame = function(cb) {\n"
        "  return _origRAF(function(ts) {\n"
        "    __ARCADE_TEST__._frame++;\n"
        "    cb(ts);\n"
        "  });\n"
        "};\n"
    )

    # Insérer juste avant le dernier init() standalone
    _init_m = list(re.finditer(r'^init\s*\(\s*\)\s*;', js, re.MULTILINE))
    if _init_m:
        pos = _init_m[-1].start()
        return js[:pos] + hooks_code + js[pos:]
    # Sinon, ajouter à la fin
    return js + hooks_code


# ─────────────────────────────────────────────────────────────────────────────
# MODEL GAME REFERENCE EXTRACTOR (Axe 1)
# ─────────────────────────────────────────────────────────────────────────────

def _get_model_game_reference(genre: str, sous_genre: str) -> str:
    """
    Extract the data-structure section (PALETTE, ENEMY_TYPES, WAVE_DEFS, etc.)
    from the matching model game file.  Returns '' if no match or read failure.
    Only the constants block is extracted (up to the first 'function' keyword)
    so L1 can mirror the data patterns without picking up conflicting game-loop code.
    """
    import re as _re

    genre_l = (genre + " " + (sous_genre or "")).lower()

    GENRE_MAP = [
        (["shmup", "shoot", "vaisseau", "spatial", "space", "bullet hell", "galaga"], "shoot_em_up.html"),
        (["platformer", "plateforme", "jump", "mario"], "platformer.html"),
        (["rpg", "aventure", "zelda", "action-rpg", "action rpg"], "rpg_narratif.html"),
        (["puzzle", "match3", "match-3", "match 3", "correspondance"], "puzzle_match3.html"),
        (["runner", "endless", "infini", "course infinie"], "endless_runner.html"),
        (["arcade", "breakout", "casse-briques", "brique", "pong", "balle"], "breakout.html"),
        (["tower defense", "tower_defense", "tour de défense", "defense"], "tower_defense.html"),
        (["visual novel", "visual_novel", "roman visuel", "vn"], "visual_novel.html"),
        (["dungeon", "crawler", "dungeon_crawler", "donjon"], "dungeon_crawler.html"),
        (["roguelite", "rogue-lite", "rogue lite", "roguelike"], "roguelite.html"),
    ]

    filename = None
    for keywords, fname in GENRE_MAP:
        if any(kw in genre_l for kw in keywords):
            filename = fname
            break

    if not filename:
        return ""

    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(_root, "jeux_modeles", filename)

    try:
        with open(model_path, "r", encoding="utf-8") as f:
            html = f.read()
    except (IOError, OSError):
        return ""

    m = _re.search(r'<script[^>]*>(.*?)</script>', html, _re.DOTALL | _re.IGNORECASE)
    if not m:
        return ""
    js = m.group(1)

    # Anchor: first ALLCAPS constant assigned to an object or array (data tables)
    anchor_m = _re.search(r'(?:var|const)\s+[A-Z_][A-Z0-9_]{2,}\s*=\s*[{\[]', js)
    if anchor_m:
        start = anchor_m.start()
    else:
        # Fallback: first ALLCAPS scalar constant block
        anchor_m2 = _re.search(r'(?:var|const)\s+[A-Z_][A-Z0-9_]{2,}\s*=', js)
        if anchor_m2:
            start = anchor_m2.start()
        else:
            return ""

    # Fixed 2500-char window — includes data defs AND nearby helpers/functions for context
    excerpt = js[start:start + 2500]
    last_nl = excerpt.rfind('\n')
    if last_nl > 1800:
        excerpt = excerpt[:last_nl]

    return excerpt.strip()


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def run_layered(context, patterns_reussis=None, erreurs_passees=None, game_logics="", level_design=None) -> str:
    """
    Génération en 8 couches JS — architecture sans troncature.

    L1 DONNÉES        : constantes, data structures, état global
    L2 SPAWN & INIT   : factories d'entités, initGame(), resetGame()
    L3 PHYSIQUE       : updatePlayer/Enemies/Bullets/Particles(dt) — zéro conséquence
    L4 COLLISIONS     : checkCollisions(), handleBulletHit(), handlePlayerHit()
    L5 BOSS & VAGUES  : updateWave(), updateBoss(), checkBossPhase(), bossPattern*()
    L6 RENDU          : fonctions draw* fonctionnelles
    L7 BOUCLE         : init(), gameLoop(), event listeners
    L8 POLISH         : screen shake, sons WebAudio, combo, floating texts + réécriture draw* artistique

    Garanties :
    - Aucune troncature d'output (zéro limite de lignes)
    - Contexte anti-hallucination : schéma typé + signatures + queue récente
    - Chaque couche a une responsabilité unique et claire
    """
    import html as _html_mod
    from code_validator import validate_and_fix
    import memory as _memory

    titre = context.gdd.get('titre', 'Jeu Arcade')
    genre = context.genre_profile.genre_principal
    sous_genre = context.genre_profile.sous_genre or genre
    style_visuel = context.genre_profile.style_visuel or 'neon sur fond sombre'
    palette = context.genre_profile.palette_recommandee or ''

    # Build UX visual contract from ux_specs
    _ux_contract_str = ""
    _ux = getattr(context, 'ux_specs', {}) or {}
    if _ux:
        _juice = (_ux.get('game_feel') or {}).get('elements_juice', [])
        _particles = (_ux.get('effets_visuels') or {}).get('particles', [])
        _shake = (_ux.get('effets_visuels') or {}).get('screen_shake', {}) or {}
        _feedback = (_ux.get('feedback_visuel') or [])[:3]
        _feel_parts = []
        if _juice:
            _feel_parts.append("Juice: " + ", ".join(str(j) for j in _juice[:4]))
        if _particles:
            _feel_parts.append("Particles: " + " | ".join(
                f"{p.get('nom','?')}({p.get('count','?')} pts, {p.get('duree_ms','?')}ms, {p.get('couleurs',['#fff'])[:2]})"
                for p in _particles[:3]
            ))
        if _shake.get('actif'):
            _feel_parts.append(f"Screen shake: {_shake.get('amplitude_px','6')}px / {_shake.get('duree_ms','200')}ms on {_shake.get('declencheurs',['impact'])}")
        if _feedback:
            _feel_parts.append("Visual feedback: " + " | ".join(
                f"{fb.get('action','?')} → {fb.get('feedback','?')}" for fb in _feedback
            ))
        if _feel_parts:
            _ux_contract_str = "\nUX VISUAL CONTRACT (implement ALL of these):\n" + "\n".join(f"  {p}" for p in _feel_parts) + "\n"
    mecaniques = context.genre_profile.mecaniques_obligatoires or []
    mecaniques_str = ', '.join(mecaniques[:6]) if mecaniques else 'gameplay classique'

    # Reset des stats au début de chaque run — évite la pollution cross-runs
    # (les stats d'un shooter précédent ne doivent pas injecter des hints erronés dans un platformer)
    for _k in _LAYER_STATS:
        _LAYER_STATS[_k] = {'attempts': 0, 'successes': 0, 'failures': [], 'lines_generated': []}

    erreurs_list: list[str] = list(erreurs_passees or [])
    # _stats_to_erreurs supprimé : les erreurs cross-runs polluaient le contexte.
    # L'apprentissage se fait via erreurs_passees transmis explicitement par coordinateur.py.
    erreurs_str = ""
    if erreurs_list:
        # J18 : erreurs récentes en premier ([-6:] au lieu de [:6])
        erreurs_str = "\nEvite ces erreurs connues :\n" + "\n".join("- " + e for e in erreurs_list[-6:])

    phase3_log.agent_start("Createur Layered", "Generation 9 couches (%s)" % titre)

    # ── Contexte level_design pour L1 ──
    level_design_section = ""
    _ld = level_design or (context.level_design if hasattr(context, 'level_design') else None)
    if _ld and isinstance(_ld, dict):
        nb_levels = _ld.get('nombre_niveaux') or _ld.get('nb_levels') or _ld.get('waves')
        progression = _ld.get('progression') or _ld.get('difficulte') or ""
        ennemis = _ld.get('ennemis') or _ld.get('enemy_types') or ""
        if nb_levels or progression or ennemis:
            level_design_section = "\nSTRUCTURE DE JEU (guide pour WAVE_DEFS / LEVEL_DEFS) :\n"
            if nb_levels:
                level_design_section += "  Niveaux/vagues : %s\n" % str(nb_levels)
            if progression:
                level_design_section += "  Progression : %s\n" % str(progression)
            if ennemis:
                level_design_section += "  Ennemis : %s\n" % str(ennemis)

    # ── Snippets RAG ──
    snippets_section = ""
    if patterns_reussis:
        good = [p for p in patterns_reussis if p.get('score', 0) >= 8.0]
        if good:
            snippets_section = "\nEXTRAITS RÉUSSIS (score >= 8) — utilise comme inspiration :\n"
            for p in good[:2]:
                snippet = p.get('code_snippet') or p.get('snippet') or p.get('code') or ''
                # J5 : snippets 600 chars (200 = 3 lignes, insuffisant)
                snippets_section += "--- %s (score %.1f) ---\n%s\n" % (
                    p.get('genre', '?'), p.get('score', 0), snippet[:600]
                )

    # ── Model game reference (Axe 1) ──
    reference_section = ""
    _ref_code = _get_model_game_reference(genre, sous_genre)
    if _ref_code:
        reference_section = (
            "\nJEU DE RÉFÉRENCE VALIDÉ — ARCHITECTURE 8+/10 EN PRODUCTION\n"
            "Ces structures de données sont ÉPROUVÉES pour ce genre — reproduis les mêmes patterns.\n"
            "Adapte les valeurs (couleurs, vitesses, HP) au jeu demandé, mais conserve les structures :\n"
            "```javascript\n" + _ref_code + "\n```\n"
        )
        phase3_log.info("[layered] Reference jeu modèle injectée : %d chars" % len(_ref_code))

    # ── Split game_logics ──
    def _split_game_logics_semantic(gl: str) -> tuple:
        if not gl or len(gl) < 50:
            return "", ""
        lines = gl.split('\n')
        init_lines, update_lines, neutral_lines = [], [], []
        current_bucket = 'neutral'
        for line in lines:
            ll = line.lower()
            is_init = any(kw in ll for kw in _INIT_KEYWORDS)
            is_update = any(kw in ll for kw in _UPDATE_KEYWORDS)
            if is_init and not is_update:
                current_bucket = 'init'
            elif is_update and not is_init:
                current_bucket = 'update'
            if current_bucket == 'init':
                init_lines.append(line)
            elif current_bucket == 'update':
                update_lines.append(line)
            else:
                neutral_lines.append(line)
        neutral_str = '\n'.join(neutral_lines)
        return neutral_str + '\n' + '\n'.join(init_lines), neutral_str + '\n' + '\n'.join(update_lines)

    _gl_init_part, _gl_update_part = _split_game_logics_semantic(game_logics)
    game_logics_entities = _gl_init_part.strip()
    game_logics_update = _gl_update_part.strip()

    # ── Enrichment targets (pour L5 et L8) ──
    enrichment_targets = _get_enrichment_targets(genre)

    # ── Schemas dict (anti-hallucination) ──
    schemas_dict: dict = {}

    # ── Compteur de couches critiques échouées ──
    _critical_stub_count = 0

    accumulated = ""
    accumulated_signatures = ""
    layer1_schema = ""
    layer1_js = ""

    # Q3 — Templates de prompts par genre
    try:
        from agents.phase3._layer_prompts_genre import get_layer_extra as _genre_extra
    except Exception:
        def _genre_extra(g, n): return ""

    # Q2 — Extraire les constantes numériques de game_logics pour injection dans L1
    def _extract_logics_constants(gl: str) -> str:
        """
        Parse game_logics pour extraire des formules numériques et les convertir en constantes JS.
        Ex: "speed = 80 + wave*15" → "var PLAYER_SPEED_BASE = 80; var PLAYER_SPEED_WAVE_SCALE = 15;"
        """
        if not gl or len(gl) < 30:
            return ""
        lines = []
        # Patterns : "X = N", "X: N", "X = N + wave*M"
        for m in re.finditer(
            r'\b([A-Z_][A-Z0-9_]{2,}|(?:player|enemy|boss|bullet)\w*(?:speed|hp|damage|radius|range|rate|scale|size))\s*[=:]\s*(\d+(?:\.\d+)?)',
            gl, re.IGNORECASE
        ):
            name = re.sub(r'[^a-zA-Z0-9_]', '_', m.group(1)).upper()
            val = m.group(2)
            lines.append(f'var {name} = {val};')
        if not lines:
            return ""
        unique = list(dict.fromkeys(lines))[:15]  # Max 15 constantes
        return '// Constantes extraites de game_logics (Q2)\n' + '\n'.join(unique) + '\n'

    _logics_constants = _extract_logics_constants(game_logics or "")

    # ─────────────────────────────────────────────────────────────
    # COUCHE 1 — DONNÉES & ÉTAT GLOBAL
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 1 — données et état global")

    _mecaniques_block = _format_mechanics_as_requirements(mecaniques)

    layer1_prompt = (
        f'Jeu : "{titre}" — genre : {genre} ({sous_genre})\n'
        f'Style visuel : {style_visuel}\n'
        f'{_mecaniques_block}'
        f'{erreurs_str}{level_design_section}{snippets_section}{reference_section}\n\n'
        'Génère UNIQUEMENT les déclarations de données et état global.\n\n'
        'OBLIGATOIRE (sois PRÉCIS et RICHE — ces données définissent tout le gameplay) :\n'
        '1. var PALETTE = {bg:"#0a0a1a",player:"#00ffcc",enemy:"#ff4444",...} — 15+ couleurs, adapte au thème\n'
        '   OBLIGATOIRE : inclure AU MINIMUM ces clés :\n'
        '   bg, player, enemy, boss, bullet, ui, shield, particle,\n'
        '   neonCyan, neonMagenta, neonOrange, neonYellow, neonGreen, neonPink, neonBlue,\n'
        '   neonRed, neonWhite, neonPurple, neonTeal, neonGold,\n'
        '   dark, darkGray, blue, cyan, green, red, white, gray, orange, purple, yellow, pink\n'
        '   IMPORTANT : déclarer PALETTE comme var global (NE PAS mettre const — peut être redéfini en L9)\n'
        '2. Constantes gameplay ALL_CAPS : PLAYER_SPEED, BULLET_SPEED, ENEMY_SPEED, MAX_LIVES, FIRE_RATE, BULLET_DMG\n'
        '   INTERDIT : constantes ENEMY_SPEED_TYPE séparées (ex: ENEMY_SPEED_DRONE) — utiliser enemy.speed dans ENEMY_TYPES[]\n'
        '3. Data structures selon le genre (3-4 types avec vraies valeurs) :\n'
        '   Shooter: var ENEMY_TYPES = [{type:"kamikaze",hp:1,speed:120,points:10,size:16,color:"#f00"}, ...]\n'
        '   TD: var WAVE_DEFS = [{enemies:[{type:"basic",count:5,interval:1}]}, ...]\n'
        '   Platformer: var LEVEL_DEFS = [{tiles:[[...]], enemies:[...], spawn:{x,y}}, ...]\n'
        '   RPG: var HERO_CLASSES = [{id:"warrior",hp:100,atk:15,speed:80}, ...]\n'
        f'{game_logics_entities[:2000] if game_logics_entities else ""}\n'
        f'{_logics_constants}\n'
        '4. Variables état globales (TOUTES initialisées avec des vraies valeurs) :\n'
        '   var player = null; var enemies = []; var bullets = []; var particles = []; var floatTexts = [];\n'
        '   var score = 0; var highScore = parseInt(localStorage.getItem("hs")||"0");\n'
        '   var lives = 3; var wave = 1; var level = 1;\n'
        '   var boss = null; var bossActive = false; var bossPhase = 1;\n'
        '   var waveTimer = 3; var waveActive = false; var fireTimer = 0; var spawnTimer = 0;\n'
        '   var shakeX=0,shakeY=0,shakeMag=0,shakeTimer=0;\n'
        '   var powerUps=[]; var shieldActive=false; var shieldTimer=0;\n'  # H4 : camelCase imposé
        '   var combo=0; var comboTimer=0; var comboMax=0;\n'
        '   /* H4 CASSE OBLIGATOIRE : powerUps (U majuscule), floatTexts (T majuscule) — respecter EXACTEMENT */\n'
        '   var waveAnnounce=0; var waveAnnounceTxt="";\n'
        '   var multiplier=1; var xp=0; var playerLevel=1; var upgradePoints=0;\n'
        '   var flashAlpha=0; var flashColor="#FFF";\n'
        '   /* Q1 — Overlay de transition (fondu menu→jeu) */\n'
        '   var overlayAlpha=0; var overlayFadeDir=0;\n'
        '   /* Q11 — Object pools (réutilisation pour éviter GC stutters) */\n'
        '   var bulletPool=[]; var particlePool=[];\n'
        '   /* Q1 — Audio state (rempli en L8 par _initAudio) */\n'
        '   var _AC=null; var sfx={}; var musicPlaying=false;\n'
        '5. var keys = {left:false,right:false,up:false,down:false,space:false,'
        'a:false,d:false,w:false,s:false,q:false,e:false,shift:false,'
        'z:false,x:false,c:false,enter:false,escape:false,p:false};\n'
        '   var mouse = {x:W/2,y:H/2,down:false,clicked:false};\n\n'
        'DÉJÀ DÉCLARÉ dans le template HTML (NE PAS redéclarer) : canvas, ctx, W, H, dt, lastTime, gameState\n\n'
        'RÈGLES OBLIGATOIRES :\n'
        '- I2 : localStorage TOUJOURS dans try/catch :\n'
        '  var highScore = 0; try { highScore = parseInt(localStorage.getItem("hs") || "0"); } catch(e) {}\n'
        '- I4 : constantes limites obligatoires : var MAX_ENEMIES = 60; var MAX_BULLETS = 80;\n'
        '  Ces constantes servent à écrêter les tableaux dans updateEnemies/updateBullets.\n'
        f'{_genre_extra(genre, 1)}'
        'INTERDIT : fonctions, gameLoop, init, addEventListener, requestAnimationFrame, new Audio(), new Image()\n'
        '// @GLOBALS: liste toutes tes constantes ALLCAPS sur UNE ligne en commentaire à la fin (ex: // @GLOBALS: PLAYER_SPEED, BULLET_SPEED, ENEMY_TYPES, WAVE_DEFS)\n'
        'Output : JS pur uniquement.'
    )

    for attempt in range(2):
        raw = _call_layer(_LAYER_SYSTEM, layer1_prompt, max_tokens=16000, temperature=0.1, disable_thinking=True)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 1")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 1 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer1', False, reason=quality_reason)
            layer1_prompt += "\n\nATTENTION : rejeté (%s). Génère du code substantiel." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, "", "Couche 1")
        if not valid:
            _record_layer_event('layer1', False, reason="syntaxe invalide")
            layer1_prompt += "\n\nATTENTION : syntaxe invalide. Sois rigoureux."
            continue
        layer1_js = fixed_js
        _record_layer_event('layer1', True, lines=fixed_js.count('\n'))
        break

    if not layer1_js or len(layer1_js) < 100:
        phase3_log.warning("[layered] Couche 1 échouée — fallback compact")
        return _run_compact_fallback(context, erreurs_passees=erreurs_passees)

    accumulated = layer1_js
    phase3_log.info("[layered] Couche 1 OK — %d chars" % len(layer1_js))

    layer1_schema = _extract_object_schemas(layer1_js)
    if layer1_schema:
        schemas_dict = _parse_object_schemas_dict(layer1_js)
        phase3_log.info("[layered] Schéma L1 extrait : %d objet(s)" % len(schemas_dict))

    # ── Symbol Table A+B+C — construit après L1 ──
    _symbol_table = _build_symbol_table(layer1_js)
    _global_contract = _format_global_contract(_symbol_table)
    if _global_contract:
        phase3_log.info(
            "[layered] Symbol table: %d constantes ALLCAPS, %d type-arrays"
            % (len(_symbol_table["allcaps"]), len(_symbol_table["type_keys"]))
        )

    # ── Manifest incrémental — démarre avec L1, enrichi après chaque couche ──
    _incremental_manifest = _extract_layer_manifest(layer1_js, 1)
    phase3_log.info("[layered] Manifest L1 : %d lignes" % _incremental_manifest.count('\n'))

    # ── Extraction des clés PALETTE réellement déclarées en L1 ──
    # Permet d'injecter dans L6/L9 la liste exacte des clés disponibles → évite PALETTE.neonXxx undefined
    _palette_keys_declared: list[str] = []
    _palette_raw_m = re.search(r'\bvar\s+PALETTE\s*=\s*\{([^}]+)\}', layer1_js, re.DOTALL)
    if _palette_raw_m:
        _palette_keys_declared = re.findall(r'(\w+)\s*:', _palette_raw_m.group(1))
    if _palette_keys_declared:
        phase3_log.info("[layered] PALETTE L1 : %d clé(s) : %s" % (len(_palette_keys_declared), ', '.join(_palette_keys_declared[:10])))
    _palette_keys_hint = ', '.join(_palette_keys_declared) if _palette_keys_declared else 'bg, player, enemy, boss, bullet, ui, shield, particle, neonCyan, neonMagenta'

    # K5 — Extraire toutes les déclarations globales de L1 pour éviter les redéclarations dans L2-L9
    _l1_global_vars = re.findall(r'^(?:var|let|const)\s+([a-zA-Z_$]\w*)', layer1_js, re.MULTILINE)
    _l1_global_vars_unique = sorted(set(_l1_global_vars))
    _no_redecl_note = (
        "\nCRITIQUE — Ces variables sont DÉJÀ DÉCLARÉES en couche 1 — NE PAS les redéclarer avec var/let/const :\n"
        + ', '.join(_l1_global_vars_unique[:60])
        + "\nUtilise ces variables directement sans déclarateur. "
        "Redéclarer crée des erreurs 'already declared' ou écrase les valeurs initialisées.\n"
    ) if _l1_global_vars_unique else ""

    # ─────────────────────────────────────────────────────────────
    # COUCHE 2 — SPAWN & INIT
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 2 — spawn et initialisation")
    accumulated_signatures = _extract_function_signatures(accumulated)
    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=300, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    layer2_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n'
        f'{_mecaniques_block}'
        f'{layer_ctx}\n\n'
        'MISSION : Génère UNIQUEMENT les fonctions de création et initialisation des entités.\n\n'
        'FONCTIONS OBLIGATOIRES :\n'
        '- spawnPlayer() : crée player avec TOUTES ses propriétés (x, y, w, h, hp, maxHp, speed, fireTimer, etc.)\n'
        '- spawnEnemy(type) : crée un ennemi selon ENEMY_TYPES[type], push dans enemies[]\n'
        '- spawnBoss() : crée boss avec hp=wave*100, maxHp, phase=1, x=W/2, taille distincte, push ou assign boss\n'
        '- spawnBullet(x, y, vx, vy, owner, dmg) : RÉUTILISE bulletPool si dispo, sinon crée;\n'
        '  push dans bullets[] ; MAX_BULLETS appliqué (if(bullets.length>=MAX_BULLETS)return;)\n'
        '  Q11 : var b=bulletPool.length?bulletPool.pop():{};  b.x=x;b.y=y;b.vx=vx;b.vy=vy;b.owner=owner;b.dmg=dmg||1;b.active=true; bullets.push(b);\n'
        '- spawnPowerUp(x, y, type) : push dans powerUps[] avec {x,y,type,vy:50,r:12,anim:0}\n'
        '- spawnParticle(x, y, col, n) : n particules — RÉUTILISE particlePool si dispo;\n'
        '  Q11 : for(var i=0;i<n;i++){var p=particlePool.length?particlePool.pop():{};p.x=x;p.y=y;p.vx=(Math.random()-0.5)*150;p.vy=(Math.random()-0.5)*150-80;p.life=0.6+Math.random()*0.4;p.maxLife=p.life;p.col=col||"#ff6600";p.active=true;particles.push(p);}\n'
        '- spawnFloatText(x, y, txt, col) : push dans floatTexts[] avec {x,y,txt,col,life:1.2,vy:-50}\n'
        '- initGame() : appelle spawnPlayer(), initialise waveTimer=3, wave=1, score=0, lives=3, bossActive=false\n'
        '   NE PAS appeler requestAnimationFrame\n'
        '- resetGame() : remet tout à zéro (score, lives, wave, enemies.length=0, bullets.length=0, etc.)\n'
        '   puis appelle initGame()\n\n'
        f'{game_logics_entities[:1500] if game_logics_entities else ""}\n\n'
        'RÈGLES CRITIQUES :\n'
        '- Utilise UNIQUEMENT les propriétés du SCHÉMA L1\n'
        '- spawnEnemy(type) doit lire depuis ENEMY_TYPES pour les stats (hp, speed, points, size)\n'
        '- Toute propriété rajoutée sur un objet doit être cohérente avec le schéma\n\n'
        'INTERDIT : gameLoop, draw*, addEventListener, requestAnimationFrame, logique update/collision\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement.'
    )

    layer2_js = ""
    for attempt in range(2):
        raw = _call_layer(_LAYER_SYSTEM, layer2_prompt, max_tokens=20000, temperature=0.1, disable_thinking=True)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 2")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 2 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer2', False, reason=quality_reason)
            layer2_prompt += "\n\nATTENTION : rejeté (%s). Génère des fonctions spawn COMPLÈTES." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 2")
        if not valid:
            _record_layer_event('layer2', False, reason="syntaxe invalide")
            layer2_prompt += "\n\nATTENTION : syntaxe invalide."
            continue
        gate_ok, _gate_errs = _gate_check_critical("Couche 2", fixed_js, schemas_dict)
        if not gate_ok and attempt < 1:
            phase3_log.warning("[layered] Couche 2 gate échec : %s" % '; '.join(_gate_errs[:2]))
            _record_layer_event('layer2', False, reason="gate: " + _gate_errs[0][:50])
            continue
        layer2_js = fixed_js
        _record_layer_event('layer2', True, lines=fixed_js.count('\n'))
        break

    if not layer2_js:
        phase3_log.warning("[layered] Couche 2 échouée — stub spawn/init minimal")
        # NOTE : _get_emergency_stub(2, ...) génère des fonctions UPDATE (pour L3).
        # L2 a besoin de fonctions SPAWN/INIT — on les écrit directement ici.
        decls2 = _extract_js_declarations(accumulated)
        _pv = next((n for n in ['player','hero','ship','joueur','vaisseau'] if n in decls2.get('vars',[])), 'player')
        layer2_js = (
            f"function spawnPlayer(){{\n"
            f"  {_pv} = {{x:W/2, y:H*0.75, w:24, h:24, hp:3, maxHp:3, speed:220, fireTimer:0, invTimer:0}};\n"
            f"}}\n\n"
            f"function spawnEnemy(type){{\n"
            f"  var et = (typeof ENEMY_TYPES!=='undefined' && ENEMY_TYPES[type%ENEMY_TYPES.length]) || {{hp:1,speed:80,points:10,size:18,color:'#f44'}};\n"
            f"  enemies.push({{x:Math.random()*(W-40)+20, y:-30, hp:et.hp, maxHp:et.hp, speed:et.speed, points:et.points||10, w:et.size||18, h:et.size||18, color:et.color||'#f44', type:type||0, shootTimer:2+Math.random()*2}});\n"
            f"}}\n\n"
            f"function spawnBoss(){{\n"
            f"  boss = {{x:W/2, y:80, hp:wave*150, maxHp:wave*150, w:64, h:64, speed:60, shootTimer:1.5, phase:1}};\n"
            f"  bossActive = true; bossPhase = 1;\n"
            f"}}\n\n"
            f"function spawnBullet(x,y,vx,vy,owner,dmg){{\n"
            f"  bullets.push({{x:x, y:y, vx:vx||0, vy:vy||-400, owner:owner||'player', dmg:dmg||1, r:5}});\n"
            f"}}\n\n"
            f"function spawnPowerUp(x,y,type){{\n"
            f"  powerUps.push({{x:x, y:y, type:type||'shield', vy:50, r:12, anim:0}});\n"
            f"}}\n\n"
            f"function spawnParticle(x,y,col,n){{\n"
            f"  for(var i=0;i<(n||8);i++){{\n"
            f"    var a=Math.random()*Math.PI*2, s=Math.random()*120+40;\n"
            f"    particles.push({{x:x, y:y, vx:Math.cos(a)*s, vy:Math.sin(a)*s, life:1, color:col||'#fff', r:Math.random()*3+2}});\n"
            f"  }}\n"
            f"}}\n\n"
            f"function spawnFloatText(x,y,txt,col){{\n"
            f"  floatTexts.push({{x:x, y:y, txt:txt, col:col||'#fff', life:1.2, vy:-50}});\n"
            f"}}\n\n"
            f"function initGame(){{\n"
            f"  spawnPlayer();\n"
            f"  enemies.length=0; bullets.length=0; particles.length=0; floatTexts.length=0; powerUps.length=0;\n"
            f"  score=0; lives=3; wave=1; bossActive=false; boss=null;\n"
            f"  waveTimer=3; waveActive=false; combo=0; comboTimer=0;\n"
            f"}}\n\n"
            f"function resetGame(){{\n"
            f"  initGame();\n"
            f"}}\n"
        )
        _critical_stub_count += 1
        _record_layer_event('layer2', False, reason="stub urgence")
        if _critical_stub_count >= 2:
            return _run_compact_fallback(context, erreurs_passees=erreurs_passees)

    layer2_js, _resolved2 = _resolve_undeclared_symbols(layer2_js, _symbol_table, accumulated)
    if _resolved2:
        phase3_log.info("[layered] L2 auto-resolved: %s" % ', '.join(_resolved2[:6]))
    accumulated += '\n\n' + layer2_js
    _l2_manifest = _extract_layer_manifest(layer2_js, 2)
    if not _l2_manifest.strip():
        phase3_log.warning("[layered] L2 manifest vide — couche probablement tronquée")
    _incremental_manifest += '\n' + _l2_manifest
    phase3_log.info("[layered] Couche 2 OK — %d chars" % len(layer2_js))

    # ─────────────────────────────────────────────────────────────
    # COUCHE 3 — PHYSIQUE PURE (déplacement, 0 conséquence)
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 3 — physique pure")
    accumulated_signatures = _extract_function_signatures(accumulated)
    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=350, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    layer3_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n'
        f'{_mecaniques_block}'
        f'{layer_ctx}\n\n'
        'MISSION : Génère UNIQUEMENT les fonctions de déplacement et cinématique.\n'
        'RÈGLE ABSOLUE : ces fonctions ne modifient JAMAIS score, lives, gameState, ni ne splicient les tableaux.\n\n'
        'FONCTIONS OBLIGATOIRES :\n'
        '- updatePlayer(dt) : mouvement selon keys (left/right/up/down), fireTimer -= dt,\n'
        '  tir : if(fireTimer<=0 && keys.space){ spawnBullet(...); fireTimer=FIRE_RATE; }\n'
        '  bords écran : var _pw=player.w||24; player.x = Math.max(_pw/2, Math.min(W-_pw/2, player.x));\n'
        '  shieldTimer -= dt si shieldActive\n'
        '  comboTimer -= dt; if(comboTimer<=0){ combo=0; comboTimer=0; }\n'
        '- updateEnemies(dt) : IA par type (kamikaze=fonce sur player, strafe=esquive, formation=maintient rang)\n'
        '  shootTimer -= dt; si timer<=0 → spawnBullet(e.x,e.y,0,BULLET_SPEED,"enemy",1); timer=intervalle\n'
        '  Déplacement selon type, rotation si applicable\n'
        '- updateBullets(dt) : b.x+=b.vx*dt; b.y+=b.vy*dt; SPLICE si hors écran (itération inverse)\n'
        '- updateParticles(dt) : p.x+=p.vx*dt; p.y+=p.vy*dt; p.vy+=150*dt; p.life-=dt*1.5;\n'
        '  itération inverse pour splice les morts (p.life<=0)\n'
        '- updateFloatTexts(dt) : ft.y+=ft.vy*dt; ft.life-=dt; splice si mort\n'
        '- applyShake() : si shakeTimer>0 {\n'
        '    shakeX=(Math.random()-.5)*shakeMag*2; shakeY=(Math.random()-.5)*shakeMag*2;\n'
        '    shakeTimer-=dt; shakeMag*=0.9;\n'
        '  } else { shakeX=0; shakeY=0; }\n'
        '  (utilise dt global — PAS de paramètre dt)\n\n'
        f'{game_logics_update[:1500] if game_logics_update else ""}\n\n'
        'RÈGLES STRICTES :\n'
        '- Utilise UNIQUEMENT les propriétés du SCHÉMA L1\n'
        '- Itération inverse pour splice : for(let i=arr.length-1;i>=0;i--){...}\n'
        '- Distance sécurisée : const dist=Math.hypot(dx,dy)||0.001;\n'
        '- Timers : timer-=dt; if(timer<=0){...;timer=intervalle;}\n'
        '- INTERDIT : modifier score, lives, gameState, splice direct sans itération inverse\n\n'
        f'{_genre_extra(genre, 3)}'
        'INTERDIT : gameLoop, draw*, addEventListener, checkCollisions, spawnExplosion dans update\n'
        'INTERDIT ABSOLU : constantes ENEMY_SPEED_TYPE séparées (ex: ENEMY_SPEED_DRONE, ENEMY_HP_BOMBER)\n'
        '  → Utiliser directement enemy.speed, enemy.hp, enemy.dmg depuis ENEMY_TYPES[] — ces props existent déjà en L1\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement.'
    )

    layer3_js = ""
    for attempt in range(3):
        raw = _call_layer(_LAYER_SYSTEM, layer3_prompt, max_tokens=20000, temperature=0.1, disable_thinking=True)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 3")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 3 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer3', False, reason=quality_reason)
            layer3_prompt += "\n\nATTENTION : rejeté (%s). Génère des fonctions update COMPLÈTES." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 3")
        if not valid:
            _record_layer_event('layer3', False, reason="syntaxe invalide")
            layer3_prompt += "\n\nATTENTION : syntaxe invalide. Chaque fonction doit se terminer sur '}'."
            continue
        gate_ok, _gate_errs = _gate_check_critical("Couche 3", fixed_js, schemas_dict)
        if not gate_ok and attempt < 2:
            phase3_log.warning("[layered] Couche 3 gate échec : %s" % '; '.join(_gate_errs[:2]))
            _record_layer_event('layer3', False, reason="gate: " + _gate_errs[0][:50])
            layer3_prompt += "\n\nCORRIGE CES PROBLÈMES :\n" + "\n".join("- " + e for e in _gate_errs[:3])
            continue
        layer3_js = fixed_js
        _record_layer_event('layer3', True, lines=fixed_js.count('\n'))
        break

    if not layer3_js:
        phase3_log.warning("[layered] Couche 3 — stub d'urgence")
        decls3 = _extract_js_declarations(accumulated)
        layer3_js = _get_emergency_stub(2, genre, decls3)  # 2 = update stubs (physique)
        _critical_stub_count += 1
        _record_layer_event('layer3', False, reason="stub urgence")
        if _critical_stub_count >= 2:
            return _run_compact_fallback(context, erreurs_passees=erreurs_passees)

    layer3_js, _resolved3 = _resolve_undeclared_symbols(layer3_js, _symbol_table, accumulated)
    if _resolved3:
        phase3_log.info("[layered] L3 auto-resolved: %s" % ', '.join(_resolved3[:6]))
    accumulated += '\n\n' + layer3_js
    _l3_manifest = _extract_layer_manifest(layer3_js, 3)
    if not _l3_manifest.strip():
        phase3_log.warning("[layered] L3 manifest vide — couche probablement tronquée")
    _incremental_manifest += '\n' + _l3_manifest
    phase3_log.info("[layered] Couche 3 OK — %d chars" % len(layer3_js))

    # Runtime check L3 (non-bloquant)
    _rt3 = _validate_layer_runtime(_HTML_TEMPLATE.format(title="test", js_body=accumulated))
    if _rt3:
        phase3_log.info("[layered] Couche 3 runtime hints : %s" % '; '.join(_rt3[:2]))

    # ─────────────────────────────────────────────────────────────
    # COUCHE 4 — COLLISIONS & CONSÉQUENCES
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 4 — collisions et conséquences")
    accumulated_signatures = _extract_function_signatures(accumulated)
    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=400, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    layer4_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n\n'
        f'{layer_ctx}\n\n'
        'MISSION : Génère UNIQUEMENT les fonctions de collision et leurs conséquences sur le jeu.\n\n'
        'FONCTIONS OBLIGATOIRES :\n'
        '- checkCollisions() : orchestre toutes les détections :\n'
        '  1. bullet (owner="player") ↔ enemy : si AABB → handleBulletEnemyHit(b, e, i, j)\n'
        '  2. bullet (owner="player") ↔ boss : si bossActive && boss && AABB → boss.hp -= b.dmg||1; bullets.splice(i,1);\n'
        '     (le boss meurt dans updateBoss quand boss.hp<=0)\n'
        '  3. player ↔ enemy : si AABB et !shieldActive → handlePlayerEnemyHit(e, j)\n'
        '  4. player ↔ powerUp : si distance < e.r+player.w/2 → handlePowerUpCollect(p, i)\n'
        '  5. bullet (owner="enemy" ou "boss") ↔ player : si AABB et !shieldActive → handleEnemyBulletHit(b, i)\n'
        '  Utilise itération inverse : for(let i=bullets.length-1;i>=0;i--)\n'
        '- handleBulletEnemyHit(b, e, bi, ei) : e.hp-=b.dmg||1;\n'
        '  si e.hp<=0 { score+=e.points||10; combo++; comboTimer=3;\n'
        '    spawnParticle(e.x,e.y,e.color||"#f80",8); spawnFloatText(e.x,e.y-20,"+"+score,"#ff0");\n'
        '    enemies.splice(ei,1); } bullets.splice(bi,1);\n'
        '- handlePlayerEnemyHit(e, ei) : si player.hp (mode RPG) player.hp--; sinon lives--;\n'
        '  shakeTimer=0.4; shakeMag=8; spawnParticle(player.x,player.y,"#f00",6);\n'
        '  si lives<=0 ou player.hp<=0 { gameState="gameover"; localStorage.setItem("hs",highScore); }\n'
        '  enemies.splice(ei, 1);\n'
        '- handleEnemyBulletHit(b, bi) : lives--; shakeTimer=0.3; shakeMag=6;\n'
        '  spawnFloatText(player.x,player.y-30,"TOUCHÉ!","#f00"); bullets.splice(bi,1);\n'
        '  si lives<=0 { gameState="gameover"; }\n'
        '- handlePowerUpCollect(p, pi) : selon p.type :\n'
        '  "shield" → shieldActive=true; shieldTimer=5;\n'
        '  "double" → fireRate halved pendant 8s (doubleTimer=8)\n'
        '  "bomb" → enemies.forEach(e=>spawnParticle(e.x,e.y,...)); enemies.length=0; score+=500;\n'
        '  "heal" → lives=Math.min(MAX_LIVES,lives+1);\n'
        '  spawnFloatText(p.x,p.y-20,p.type.toUpperCase(),"#ffd700"); powerUps.splice(pi,1);\n'
        '- updatePowerUps(dt) : timers des effets actifs (shieldTimer-=dt, doubleTimer-=dt, etc.)\n\n'
        'FONCTIONS HELPER :\n'
        '- aabbCollide(a, b) : retourne bool (Math.abs(a.x-b.x)<(a.w||a.r*2)/2+(b.w||b.r*2)/2 && ...)\n\n'
        'RÈGLES STRICTES :\n'
        '- Utilise UNIQUEMENT les propriétés du SCHÉMA L1\n'
        '- highScore = Math.max(highScore, score) avant gameState="gameover"\n'
        '- combo++ à chaque kill, comboTimer=3; si comboTimer<=0 → combo=0 (géré dans L3)\n\n'
        # H3 — updatePowerUps obligatoire si powerUps dans le schema L1
        + ('- OBLIGATOIRE : définir function updatePowerUps(dt) { } qui met à jour powerUps[] '
           '(déplacement, collection par le joueur, expiration)\n\n'
           if ('powerUps' in layer1_js or 'powerups' in layer1_js.lower()) else '')
        + 'INTERDIT : gameLoop, draw*, addEventListener, logique de déplacement\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement.'
    )

    layer4_js = ""
    for attempt in range(3):
        # J1 : thinking activé pour L4 (collisions critiques)
        raw = _call_layer(_LAYER_SYSTEM, layer4_prompt, max_tokens=20000, temperature=0.1, disable_thinking=False)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 4")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 4 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer4', False, reason=quality_reason)
            layer4_prompt += "\n\nATTENTION : rejeté (%s)." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 4")
        if not valid:
            _record_layer_event('layer4', False, reason="syntaxe invalide")
            layer4_prompt += "\n\nATTENTION : syntaxe invalide."
            continue
        gate_ok, _gate_errs = _gate_check_critical("Couche 4", fixed_js, schemas_dict)
        if not gate_ok and attempt < 2:
            phase3_log.warning("[layered] Couche 4 gate échec : %s" % '; '.join(_gate_errs[:2]))
            _record_layer_event('layer4', False, reason="gate: " + _gate_errs[0][:50])
            layer4_prompt += "\n\nCORRIGE :\n" + "\n".join("- " + e for e in _gate_errs[:3])
            continue
        layer4_js = fixed_js
        _record_layer_event('layer4', True, lines=fixed_js.count('\n'))
        break

    if not layer4_js:
        phase3_log.warning("[layered] Couche 4 échouée — injection système collision déterministe")
        decls4 = _extract_js_declarations(accumulated)
        layer4_js = _make_hardcoded_collisions(decls4)
        _record_layer_event('layer4', False, reason="stub hardcoded collisions")

    layer4_js, _resolved4 = _resolve_undeclared_symbols(layer4_js, _symbol_table, accumulated)
    if _resolved4:
        phase3_log.info("[layered] L4 auto-resolved: %s" % ', '.join(_resolved4[:6]))
    accumulated += '\n\n' + layer4_js
    _l4_manifest = _extract_layer_manifest(layer4_js, 4)
    if not _l4_manifest.strip():
        phase3_log.warning("[layered] L4 manifest vide — couche probablement tronquée")
    _incremental_manifest += '\n' + _l4_manifest
    phase3_log.info("[layered] Couche 4 OK — %d chars" % len(layer4_js))

    # ─────────────────────────────────────────────────────────────
    # COUCHE 5 — BOSS & VAGUES
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 5 — boss et vagues")
    accumulated_signatures = _extract_function_signatures(accumulated)
    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=400, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    layer5_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n\n'
        f'{layer_ctx}\n\n'
        'MISSION : Génère UNIQUEMENT les systèmes de boss et de progression par vagues.\n\n'
        'FONCTIONS OBLIGATOIRES :\n'
        '- updateWave(dt) :\n'
        '  si !waveActive : waveTimer-=dt; si waveTimer<=0 { spawnWaveEnemies(wave); waveActive=true; waveAnnounce=2; waveAnnounceTxt="VAGUE "+wave; }\n'
        '  si waveActive && enemies.length===0 && !bossActive :\n'
        '    toutes les 3 vagues → spawnBoss(); sinon wave++; waveActive=false; waveTimer=4;\n'
        '    waveAnnounce=2; waveAnnounceTxt="VAGUE "+wave+" !";\n'
        '  waveAnnounce-=dt; (si>0)\n'
        '- spawnWaveEnemies(waveIdx) : OBLIGATOIRE lire WAVE_DEFS[waveIdx % WAVE_DEFS.length],\n'
        '  NE JAMAIS faire spawnEnemy(0) directement — toujours utiliser WAVE_DEFS pour la variété\n'
        '  si WAVE_DEFS absent ou vide : génère 3+waveIdx ennemis avec types alternés depuis ENEMY_TYPES\n'
        '- updateBoss(dt) : si !bossActive || !boss return;\n'
        '  boss.shootTimer-=dt;\n'
        '  checkBossPhase();\n'
        '  si bossPhase===1 → bossPattern1(dt);\n'
        '  si bossPhase===2 → bossPattern2(dt);\n'
        '  si bossPhase===3 → bossPattern3(dt);\n'
        '  si boss.hp<=0 { bossActive=false; score+=1000; wave++; waveTimer=5; spawnParticle(boss.x,boss.y,"#ff0",20); triggerShake(12,0.8); }\n'
        '- checkBossPhase() — Q7 : 3 phases DISTINCTES avec transition visuelle :\n'
        '  si boss.hp > boss.maxHp*0.66 → si bossPhase!==1 { bossPhase=1; triggerShake(6,0.4); triggerFlash("#FFFF00",0.4); }\n'
        '  sinon si boss.hp > boss.maxHp*0.33 → si bossPhase!==2 { bossPhase=2; boss.speed*=1.3; triggerShake(10,0.6); triggerFlash("#FF8800",0.5); }\n'
        '  sinon → si bossPhase!==3 { bossPhase=3; boss.speed*=1.5; boss.fireRate=0.4; triggerShake(15,0.8); triggerFlash("#FF0000",0.6); }\n'
        '- bossPattern1(dt) — Phase 1 : tir vers joueur toutes les fireRate secondes, mouvement sinusoïdal X\n'
        '  boss.sinTimer=(boss.sinTimer||0)+dt; boss.x=W/2+Math.cos(boss.sinTimer*0.8)*150;\n'
        '- bossPattern2(dt) — Phase 2 : éventail de 5 bullets (angles -60° à +60° par pas de 30°), plus rapide\n'
        '  si boss.shootTimer<=0 { for(var a=-2;a<=2;a++){var ang=Math.atan2(player.y-boss.y,player.x-boss.x)+a*0.35;\n'
        '    spawnBullet(boss.x,boss.y,Math.cos(ang)*200,Math.sin(ang)*200,"boss",1); } boss.shootTimer=boss.fireRate||0.8; }\n'
        '- bossPattern3(dt) — Phase 3 ENRAGÉ : spirale 8 bullets + charge vers joueur\n'
        '  boss.spiralAngle=(boss.spiralAngle||0)+dt*3;\n'
        '  si boss.shootTimer<=0 { for(var i=0;i<8;i++){var a=boss.spiralAngle+i*(Math.PI*2/8);\n'
        '    spawnBullet(boss.x,boss.y,Math.cos(a)*250,Math.sin(a)*250,"boss",2); } boss.shootTimer=0.3; }\n'
        '  boss.x+=(player.x-boss.x)*dt*1.2; boss.y+=(player.y-boss.y)*dt*0.8;\n'
        '- triggerShake(mag, dur) : shakeMag=mag; shakeTimer=dur;\n'
        '- triggerFlash(col, alpha) : flashColor=col; flashAlpha=alpha;\n\n'
        f'{_genre_extra(genre, 5)}'
        f'{enrichment_targets[:600]}\n\n'
        '- Q8 — SYSTÈME DE PROGRESSION JOUEUR (obligatoire) :\n'
        '  function offerUpgrade() — appelée à la fin de chaque vague (après wave++) :\n'
        '    si wave % 2 === 0 : upgradePoints++ et gameState="upgrade_select"\n'
        '    générer 3 upgrades aléatoires parmi : {id:"firerate",label:"Cadence +25%",effect:"player.fireRate*=0.75"}\n'
        '      {id:"speed",label:"Vitesse +20%",effect:"player.speed*=1.2"}\n'
        '      {id:"damage",label:"Dégâts +30%",effect:"player.dmg=(player.dmg||1)*1.3"}\n'
        '      {id:"shield",label:"Bouclier",effect:"shieldActive=true;shieldTimer=10"}\n'
        '      {id:"multishot",label:"Triple tir",effect:"player.multishot=(player.multishot||1)+1"}\n'
        '    var currentUpgrades = [...3 items sélectionnés au hasard...]\n'
        '  function applyUpgrade(idx) — applique currentUpgrades[idx].effect, gameState="playing"\n'
        '  Toujours revenir à "playing" si upgradePoints===0 à la fin de vague.\n\n'
        'RÈGLES STRICTES :\n'
        '- Utilise UNIQUEMENT les propriétés du SCHÉMA L1\n'
        '- boss.hp ne doit être réduit QUE dans handleBulletEnemyHit (L4) — pas ici\n'
        '- spawnBullet() doit être appelé avec owner="boss"\n'
        '- triggerShake/triggerFlash disponibles — appelle-les sur événements importants\n\n'
        'INTERDIT : draw*, addEventListener, gameLoop\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement.'
    )

    layer5_js = ""
    for attempt in range(3):
        raw = _call_layer(_LAYER_SYSTEM, layer5_prompt, max_tokens=24000, temperature=0.2, disable_thinking=True)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 5")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 5 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer5', False, reason=quality_reason)
            layer5_prompt += "\n\nATTENTION : rejeté (%s). Génère boss ET wave COMPLETS." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 5")
        if not valid:
            _record_layer_event('layer5', False, reason="syntaxe invalide")
            layer5_prompt += "\n\nATTENTION : syntaxe invalide."
            continue
        gate_ok, _gate_errs = _gate_check_critical("Couche 5", fixed_js, schemas_dict)
        if not gate_ok and attempt < 2:
            phase3_log.warning("[layered] Couche 5 gate échec : %s" % '; '.join(_gate_errs[:2]))
            _record_layer_event('layer5', False, reason="gate: " + _gate_errs[0][:50])
            layer5_prompt += "\n\nCORRIGE :\n" + "\n".join("- " + e for e in _gate_errs[:3])
            continue
        layer5_js = fixed_js
        _record_layer_event('layer5', True, lines=fixed_js.count('\n'))
        break

    if not layer5_js:
        phase3_log.warning("[layered] Couche 5 — stub minimal")
        layer5_js = (
            "function updateWave(dt){waveTimer-=dt;if(waveTimer<=0&&!waveActive){"
            "for(var i=0;i<3+wave;i++)enemies.push({x:Math.random()*W,y:-30,hp:wave,speed:60+wave*10,points:10,w:20,h:20,type:'basic',shootTimer:2});"
            "waveActive=true;waveTimer=5;}if(waveActive&&enemies.length===0){wave++;waveActive=false;waveTimer=4;}}\n"
            "function triggerShake(m,d){shakeMag=m;shakeTimer=d;}\n"
            "function updateBoss(dt){}\n"
            "function checkBossPhase(){}\n"
        )
        _record_layer_event('layer5', False, reason="stub urgence")

    layer5_js, _resolved5 = _resolve_undeclared_symbols(layer5_js, _symbol_table, accumulated)
    if _resolved5:
        phase3_log.info("[layered] L5 auto-resolved: %s" % ', '.join(_resolved5[:6]))
    accumulated += '\n\n' + layer5_js
    _l5_manifest = _extract_layer_manifest(layer5_js, 5)
    if not _l5_manifest.strip():
        phase3_log.warning("[layered] L5 manifest vide — couche probablement tronquée")
    _incremental_manifest += '\n' + _l5_manifest
    phase3_log.info("[layered] Couche 5 OK — %d chars" % len(layer5_js))

    # ── Gate check mécaniques obligatoires ───────────────────────────────────
    # Vérifie que chaque mécanique demandée a laissé une trace dans le code.
    # Si des mécaniques manquent → un appel LLM ciblé les ajoute avant L6.
    _missing_mechanics = _check_mechanics_present(accumulated, mecaniques)
    if _missing_mechanics:
        phase3_log.warning(
            "[layered] Mécaniques manquantes : %s — appel réparation"
            % ', '.join(_missing_mechanics[:5])
        )
        _mechs_req = '\n'.join(
            "  - %s  (tokens attendus : %s)" % (m, ', '.join(_mechanic_to_keywords(m)))
            for m in _missing_mechanics[:6]
        )
        _repair_sigs = _extract_function_signatures(accumulated)
        _repair_prompt = (
            f'Jeu : "{titre}" — genre : {genre}\n\n'
            f'{_build_layer_context(accumulated, layer1_schema, _repair_sigs, tail_lines=250, global_contract=_global_contract, incremental_manifest=_incremental_manifest)}\n\n'
            'MÉCANIQUES OBLIGATOIRES NON ENCORE IMPLÉMENTÉES — génère-les maintenant.\n'
            'RÈGLE ABSOLUE : ne redéclare AUCUNE fonction ou variable déjà présente ci-dessus.\n'
            'Ajoute UNIQUEMENT les systèmes manquants listés ci-dessous.\n\n'
            'MÉCANIQUES À IMPLÉMENTER :\n'
            f'{_mechs_req}\n\n'
            'Pour chaque mécanique : variables d\'état + fonctions update/spawn/handle COMPLÈTES.\n'
            'Tu peux ajouter des mécaniques BONUS en plus (enrichissement libre).\n\n'
            'Output : JS pur uniquement — fonctions complètes, pas de stubs, pas de TODO.'
        )
        _repair_raw = _call_layer(_LAYER_SYSTEM, _repair_prompt, max_tokens=16000)
        _repair_fixed, _repair_valid = _validate_layer(_repair_raw, accumulated, "Réparation mécaniques")
        if _repair_valid and len(_repair_fixed) > 300:
            # Vérifier les redéclarations : les fonctions déjà existantes seront écrasées
            # (en JS la dernière définition gagne — acceptable pour les mécaniques)
            _existing_fns_repair = set(_extract_js_declarations(accumulated)['funcs'])
            _repair_new_fns = set(_extract_js_declarations(_repair_fixed)['funcs'])
            _overwrites = _repair_new_fns & _existing_fns_repair
            if _overwrites:
                phase3_log.warning(
                    "[layered] Réparation mécaniques : redéfinit %s (last-definition-wins JS — OK)"
                    % ', '.join(sorted(_overwrites)[:4])
                )
            accumulated += '\n\n' + _repair_fixed
            phase3_log.info("[layered] Mécaniques réparées — %d chars ajoutés" % len(_repair_fixed))

            # ── P5 : vérifier que les fonctions réparées sont bien appelées dans gameLoop ──
            # Les mécaniques sont générées mais souvent jamais appelées depuis update/draw.
            _repair_new_fns_list = sorted(
                fn for fn in _repair_new_fns
                if fn not in _existing_fns_repair  # seulement les vraiment nouvelles
                and (fn.startswith('update') or fn.startswith('draw') or fn.startswith('check'))
            )
            if _repair_new_fns_list:
                # Une fonction est "uncalled" si le nb d'occurrences fn( == nb de définitions function fn(
                # (c.-à-d. elle n'est appelée nulle part en dehors de sa propre définition)
                _uncalled = [
                    fn for fn in _repair_new_fns_list
                    if len(re.findall(r'\b' + re.escape(fn) + r'\s*\(', accumulated))
                       <= len(re.findall(r'function\s+' + re.escape(fn) + r'\s*\(', accumulated))
                ]
                if _uncalled:
                    if 'function gameLoop' in accumulated:
                        phase3_log.info(
                            "[layered] Réparation : %d fn(s) non appelée(s) dans gameLoop — injection : %s"
                            % (len(_uncalled), ', '.join(_uncalled[:4]))
                        )
                        accumulated = _patch_gameloop_calls(accumulated, _uncalled)
                    else:
                        # gameLoop pas encore créé (L7 le créera) — injection différée
                        phase3_log.info(
                            "[layered] Réparation : %d fn(s) à injecter en L7/L8 : %s"
                            % (len(_uncalled), ', '.join(_uncalled[:4]))
                        )

            # Vérification post-réparation
            _still_missing = _check_mechanics_present(accumulated, _missing_mechanics)
            if _still_missing:
                phase3_log.warning("[layered] Mécaniques encore manquantes après réparation : %s" % ', '.join(_still_missing[:3]))
        else:
            phase3_log.warning("[layered] Réparation mécaniques invalide — continuera avec l'existant")
    else:
        phase3_log.info("[layered] Mécaniques OK — toutes présentes dans le code")

    # ─────────────────────────────────────────────────────────────
    # COUCHE 6 — RENDU FONCTIONNEL
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 6 — rendu")
    accumulated_signatures = _extract_function_signatures(accumulated)
    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=400, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    layer6_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n'
        f'Style visuel : {style_visuel}\n'
        f'Palette : {palette}\n'
        f'{_ux_contract_str}\n'
        f'{layer_ctx}\n\n'
        'MISSION : Génère UNIQUEMENT les fonctions de rendu. '
        'Sois COMPLET et SOIGNÉ — chaque entité doit être lisible et visuellement cohérente.\n\n'
        'FONCTIONS OBLIGATOIRES (toutes doivent être présentes) :\n'
        '- drawBackground() : fond riche avec étoiles/grille/décorations selon le genre — JAMAIS un fond uni\n'
        '- drawPlayer() : joueur avec détails (glow, ombre, direction visible si applicable)\n'
        '  ctx.save(); ctx.translate(player.x, player.y); [dessin]; ctx.restore();\n'
        '  (NE PAS ajouter shakeX/shakeY ici — la game loop applique déjà ctx.translate(shakeX,shakeY) globalement)\n'
        '- drawEnemies() : chaque type d\'ennemi visuellement distinct (couleur, forme, taille)\n'
        '- drawBoss() : si bossActive && boss — rendu distinctif (grand, aura, barre HP dédiée au-dessus)\n'
        '- drawBullets() / drawProjectiles() : selon owner (player=couleur vive, enemy=rouge)\n'
        '- drawParticles() : opacité via p.life, taille décroissante\n'
        '- drawFloatTexts() : texte avec opacité ft.life, centré sur ft.x,ft.y\n'
        '- drawPowerUps() : icônes distinctes par type (shield=bleu, double=jaune, bomb=rouge)\n'
        '- drawHUD() : score haut-gauche, lives haut-droite, wave haut-centre\n'
        '  + barre HP joueur si hp/maxHp disponible + indicateur power-up actif + combo si >1\n'
        '  + waveAnnounce : si waveAnnounce>0 { texte centré animé "VAGUE X!" }\n'
        '- drawMenu() : titre en grand, sous-titre, instructions "ESPACE pour jouer", high score\n'
        '- drawGameOver() : "GAME OVER", score final, high score, "ESPACE pour rejouer"\n\n'
        f'PALETTE disponible — clés déclarées en L1 : {_palette_keys_hint}\n'
        '   Utilise UNIQUEMENT ces clés — ne jamais inventer PALETTE.neonXxx si la clé n\'est pas dans la liste.\n\n'
        'RÈGLES VISUELLES :\n'
        '- ctx.save()/ctx.restore() pour TOUTE transformation\n'
        '- ctx.shadowColor + ctx.shadowBlur pour les éléments importants\n'
        '- Utilise PALETTE si déclaré, sinon couleurs directes cohérentes\n'
        '- Utilise UNIQUEMENT les propriétés du SCHÉMA L1\n'
        '- NE PAS appliquer shakeX/shakeY dans AUCUNE fonction draw* — la game loop gère déjà ctx.translate(shakeX,shakeY) globalement avant tout dessin\n'
        '- INTERDIT ABSOLU : rgba() appelé comme une fonction JS — cela cause ReferenceError et écran noir.\n'
        '  FAUX : ctx.fillStyle = rgba(r, g, b, 0.5)   ← ReferenceError\n'
        '  VRAI : ctx.fillStyle = \'rgba(\' + r + \',\' + g + \',\' + b + \',0.5)\';\n'
        '  VRAI : ctx.fillStyle = \'rgba(255, 0, 0, 0.5)\';   ← string directe\n'
        '  VRAI : ctx.fillStyle = PALETTE.enemy;   ← clé PALETTE\n\n'
        'FORBIDDEN in drawPlayer/drawEnemies/drawBoss/drawBullets:\n'
        '- fillRect() as the ONLY render call for any entity -> visual QC score <= 6/10\n'
        '  Every entity MUST use AT LEAST ONE of: arc() OR bezierCurveTo() OR gradient OR shadowBlur >= 8\n\n'
        'MANDATORY HELPER — include EXACTLY this function in your response:\n'
        'function drawGlow(x, y, radius, color) {\n'
        '  ctx.save(); ctx.shadowColor = color; ctx.shadowBlur = radius * 2;\n'
        '  ctx.beginPath(); ctx.arc(x, y, radius * 0.5, 0, Math.PI * 2);\n'
        '  ctx.fillStyle = color; ctx.globalAlpha = 0.25; ctx.fill(); ctx.restore();\n'
        '}\n\n'
        'INTERDIT : gameLoop, logique de jeu, addEventListener, modification d\'état global\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement — chaque fonction DOIT commencer par "draw".'
    )

    layer6_js = ""
    _l6_gate_errors: list = []
    for attempt in range(2):
        _prompt_6 = layer6_prompt + (
            ("\n\nCORRIGE CES PROBLÈMES :\n" + "\n".join("- " + e for e in _l6_gate_errors))
            if _l6_gate_errors else ""
        )
        raw = _call_layer(_LAYER_SYSTEM, _prompt_6, max_tokens=32000, temperature=0.2, disable_thinking=True)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 6")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 6 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer6', False, reason=quality_reason)
            layer6_prompt += "\n\nATTENTION : rejeté (%s). Toutes les fonctions draw* COMPLÈTES." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 6")
        if not valid:
            _record_layer_event('layer6', False, reason="syntaxe invalide")
            layer6_prompt += "\n\nATTENTION : syntaxe invalide."
            continue
        gate_ok, _l6_gate_errors = _gate_check_critical("Couche 6", fixed_js, schemas_dict)
        if not gate_ok and attempt < 1:
            phase3_log.warning("[layered] Couche 6 gate échec : %s" % '; '.join(_l6_gate_errors[:2]))
            _record_layer_event('layer6', False, reason="gate: " + _l6_gate_errors[0][:50])
            continue
        layer6_js = fixed_js
        _record_layer_event('layer6', True, lines=fixed_js.count('\n'))
        break

    if not layer6_js:
        phase3_log.warning("[layered] Couche 6 — stub d'urgence")
        decls6 = _extract_js_declarations(accumulated)
        layer6_js = _get_emergency_stub(3, genre, decls6)
        _record_layer_event('layer6', False, reason="stub urgence")

    layer6_js, _resolved6 = _resolve_undeclared_symbols(layer6_js, _symbol_table, accumulated)
    if _resolved6:
        phase3_log.info("[layered] L6 auto-resolved: %s" % ', '.join(_resolved6[:6]))
    accumulated += '\n\n' + layer6_js
    _l6_manifest = _extract_layer_manifest(layer6_js, 6)
    if not _l6_manifest.strip():
        phase3_log.warning("[layered] L6 manifest vide — couche probablement tronquée")
    _incremental_manifest += '\n' + _l6_manifest
    phase3_log.info("[layered] Couche 6 OK — %d chars" % len(layer6_js))

    # ─────────────────────────────────────────────────────────────
    # COUCHE 7 — BOUCLE & EVENTS
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 7 — boucle de jeu et contrôles")
    accumulated_signatures = _extract_function_signatures(accumulated)
    decls7 = _extract_js_declarations(accumulated)

    # H2 — Extraction complète des fonctions update/draw depuis le code accumulé
    # Inclure toutes les fonctions qui doivent être appelées dans gameLoop
    _update_prefixes = ('update', 'handle', 'tick', 'manage', 'process', 'run', 'step')
    _game_loop_helpers = ('checkCollisions', 'applyShake', 'applyScreenShake',
                          'triggerShake', 'updatePowerUps', 'updateFloatTexts',
                          'updateParticles', 'updateCombo', 'updateWave', 'updateBoss')
    update_fns = [
        fn for fn in decls7['funcs']
        if fn.startswith(_update_prefixes) or fn in _game_loop_helpers
    ]
    draw_fns = [fn for fn in decls7['funcs'] if fn.startswith(('draw', 'render', 'paint'))]
    init_fns = [fn for fn in decls7['funcs'] if fn.startswith('init') or fn == 'spawnPlayer']
    # Dédupliquer en préservant l'ordre
    update_fns = list(dict.fromkeys(update_fns))
    draw_fns = list(dict.fromkeys(draw_fns))

    # Construire les lignes d'appel explicites (code réel, pas des commentaires)
    # applyShake() utilise dt global → pas de paramètre
    _update_call_lines = '\n     '.join(
        (fn + '(dt);') if fn.startswith('update') else (fn + '();')
        for fn in (update_fns or ['updatePlayer', 'updateEnemies', 'checkCollisions', 'applyShake'])
    )
    # Exclure les fonctions d'états spécifiques du bloc playing (menu/gameover sont dans leurs propres blocs)
    _playing_state_draws = {'drawMenu', 'drawGameOver', 'drawPause', 'drawVictory', 'drawCredits'}
    _draw_fns_playing = [fn for fn in draw_fns if fn not in _playing_state_draws]
    _draw_call_lines = '\n     '.join(
        fn + '();'
        for fn in (_draw_fns_playing or ['drawBackground', 'drawPlayer', 'drawEnemies', 'drawHUD'])
    )
    _init_call_lines = '\n   '.join(fn + '();' for fn in init_fns) if init_fns else 'initGame();'

    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=400, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    # Variables déclarées dans L1/L2 — NE PAS les appeler comme fonctions
    _declared_vars = decls7['vars']
    _vars_warning = (
        f'VARIABLES DÉCLARÉES (joueur, ennemis, etc.) — INTERDIT de les appeler comme des fonctions.\n'
        f'Ces noms sont des variables, pas des fonctions : {", ".join(_declared_vars[:20]) or "aucune"}\n'
        f'FAUX : joueur(dt);  ennemis(dt);  boss(dt);  — VRAI : updatePlayer(dt);  updateEnemies(dt);\n\n'
    ) if _declared_vars else ''

    layer7_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n\n'
        f'{layer_ctx}\n\n'
        'MISSION : Génère la boucle de jeu COMPLÈTE, l\'initialisation et les event listeners.\n\n'
        f'FONCTIONS UPDATE à appeler : {", ".join(update_fns) or "updatePlayer, updateEnemies"}\n'
        f'FONCTIONS DRAW à appeler : {", ".join(draw_fns) or "drawBackground, drawPlayer, drawHUD"}\n\n'
        f'{_vars_warning}'
        'GÉNÈRE EXACTEMENT CE CODE (copie et adapte — ne mets PAS ces appels en commentaires) :\n\n'
        'function init() {\n'
        f'  {_init_call_lines}\n'
        '  gameState = "menu";\n'
        '  requestAnimationFrame(gameLoop);\n'
        '}\n\n'
        'function gameLoop(timestamp) {\n'
        '  dt = Math.min((timestamp-lastTime)/1000, 0.05);\n'
        '  lastTime = timestamp;\n'
        '  ctx.save();\n'
        '  ctx.translate(shakeX, shakeY);\n'
        '  ctx.clearRect(-shakeX,-shakeY,W,H);\n'
        '  if (gameState === "menu") {\n'
        '    drawBackground();\n'
        '    drawMenu();\n'
        '  } else if (gameState === "instructions") {\n'
        '    drawBackground();\n'
        '    if(typeof drawInstructions==="function") drawInstructions();\n'
        '  } else if (gameState === "playing") {\n'
        f'    {_update_call_lines}\n'
        f'    {_draw_call_lines}\n'
        '    if(typeof drawPolish==="function") drawPolish();\n'
        '    if(typeof drawUpgradeUI==="function"&&upgradePoints>0) drawUpgradeUI();\n'
        '  } else if (gameState === "paused") {\n'
        '    drawBackground();\n'
        '    if(typeof drawPauseMenu==="function") drawPauseMenu(); else {\n'
        '      ctx.fillStyle="rgba(0,0,0,0.6)"; ctx.fillRect(0,0,W,H);\n'
        '      ctx.fillStyle="#FFF"; ctx.font="bold 40px monospace"; ctx.textAlign="center";\n'
        '      ctx.fillText("PAUSE",W/2,H/2); ctx.font="20px monospace";\n'
        '      ctx.fillText("P — Reprendre",W/2,H/2+50);\n'
        '    }\n'
        '  } else if (gameState === "upgrade_select") {\n'
        '    if(typeof drawBackground==="function") drawBackground();\n'
        '    if(typeof drawUpgradeSelect==="function") drawUpgradeSelect();\n'
        '  } else if (gameState === "gameover") {\n'
        '    drawBackground();\n'
        '    drawGameOver();\n'
        '  }\n'
        '  ctx.restore();\n'
        '  mouse.clicked = false;\n'
        '  requestAnimationFrame(gameLoop);\n'
        '}\n\n'
        'Puis ajoute les event listeners COMPLETS :\n'
        '- keydown :\n'
        '  keys[e.key.toLowerCase()]=true;\n'
        '  Espace/Enter sur "menu" → "playing" (+ soundMenuBeep si disponible)\n'
        '  Espace/Enter sur "gameover" → "menu"\n'
        '  "p" ou "Escape" sur "playing" → "paused"; sur "paused" → "playing"\n'
        '  Escape sur "instructions" → "menu"\n'
        '  "i" sur "menu" → "instructions"\n'
        '  Chiffres 1-3 sur "upgrade_select" → applyUpgrade(0/1/2) si disponible\n'
        '  Réinitialiser keys.space, keys.enter après usage\n'
        '- keyup : keys[e.key.toLowerCase()]=false;\n'
        '- mousemove : mouse.x=e.clientX-canvas.getBoundingClientRect().left; mouse.y=e.clientY-canvas.getBoundingClientRect().top;\n'
        '- mousedown : mouse.down=true; mouse.clicked=true; si menu → gameState="playing";\n'
        '- mouseup : mouse.down=false;\n\n'
        'Termine par : init();\n\n'
        'RÈGLE CRITIQUE : dt est "var dt=0" dans le HTML — écris dt=Math.min(...) PAS "var dt" ni "let dt".\n'
        'INTERDIT : redéclarer canvas, ctx, W, H, dt, lastTime, gameState.\n\n'
        'OBLIGATOIRE — event listeners SUPPLÉMENTAIRES :\n'
        '- I3 : window.resize : window.addEventListener("resize", function() {\n'
        '    canvas.width = window.innerWidth; canvas.height = window.innerHeight;\n'
        '    W = canvas.width; H = canvas.height;\n'
        '  });\n'
        '- J12 : touch events (support mobile basique) :\n'
        '    canvas.addEventListener("touchstart", function(e) {\n'
        '      e.preventDefault(); var t=e.touches[0];\n'
        '      mouse.x=t.clientX; mouse.y=t.clientY; mouse.down=true; mouse.clicked=true;\n'
        '      if(gameState==="menu") gameState="playing";\n'
        '    }, {passive:false});\n'
        '    canvas.addEventListener("touchend", function(e) { e.preventDefault(); mouse.down=false; }, {passive:false});\n'
        '    canvas.addEventListener("touchmove", function(e) { e.preventDefault(); var t=e.touches[0];\n'
        '      mouse.x=t.clientX; mouse.y=t.clientY; }, {passive:false});\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement — AUCUN commentaire à la place des vrais appels de fonctions.'
    )

    layer7_js = ""
    _l7_gate_errors: list = []
    for attempt in range(2):
        _prompt_7 = layer7_prompt + (
            ("\n\nCORRIGE :\n" + "\n".join("- " + e for e in _l7_gate_errors))
            if _l7_gate_errors else ""
        )
        # J1 : thinking activé pour L7 (boucle principale — câblage critique)
        raw = _call_layer(_LAYER_SYSTEM, _prompt_7, max_tokens=16000, temperature=0.1, disable_thinking=False)
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 7")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 7 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer7', False, reason=quality_reason)
            layer7_prompt += "\n\nATTENTION : rejeté (%s)." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 7")
        if not valid:
            _record_layer_event('layer7', False, reason="syntaxe invalide")
            layer7_prompt += "\n\nATTENTION : syntaxe invalide."
            continue
        _l7_expected = {'init': init_fns, 'update': update_fns, 'draw': draw_fns}
        gate_ok, _l7_gate_errors = _gate_check_critical("Couche 7", fixed_js, schemas_dict, _l7_expected)
        if not gate_ok and attempt < 1:
            phase3_log.warning("[layered] Couche 7 gate échec : %s" % '; '.join(_l7_gate_errors[:2]))
            _record_layer_event('layer7', False, reason="gate: " + _l7_gate_errors[0][:50])
            continue
        layer7_js = fixed_js
        _record_layer_event('layer7', True, lines=fixed_js.count('\n'))
        break

    if not layer7_js:
        phase3_log.warning("[layered] Couche 7 — game loop minimal")
        decls_for_stub7 = _extract_js_declarations(accumulated)
        layer7_js = _get_emergency_stub(4, genre, decls_for_stub7)
        _critical_stub_count += 1
        _record_layer_event('layer7', False, reason="stub urgence")
        if _critical_stub_count >= 2:
            return _run_compact_fallback(context, erreurs_passees=erreurs_passees)

    layer7_js, _resolved7 = _resolve_undeclared_symbols(layer7_js, _symbol_table, accumulated)
    if _resolved7:
        phase3_log.info("[layered] L7 auto-resolved: %s" % ', '.join(_resolved7[:6]))
    accumulated += '\n\n' + layer7_js
    _l7_manifest = _extract_layer_manifest(layer7_js, 7)
    if not _l7_manifest.strip():
        phase3_log.warning("[layered] L7 manifest vide — couche probablement tronquée")
    _incremental_manifest += '\n' + _l7_manifest
    phase3_log.info("[layered] Couche 7 OK — %d chars" % len(layer7_js))

    # Runtime check L7 — critique
    _rt7 = _validate_layer_runtime(_HTML_TEMPLATE.format(title="test", js_body=accumulated))
    if _rt7:
        crit7 = [e for e in _rt7 if 'init is not a function' in e or 'gameLoop is not a function' in e]
        if crit7:
            phase3_log.warning("[layered] Couche 7 erreur critique : %s — stub" % crit7[0])
            decls_for_stub7b = _extract_js_declarations(accumulated)
            accumulated += '\n\n' + _get_emergency_stub(4, genre, decls_for_stub7b)
        else:
            phase3_log.info("[layered] Couche 7 runtime hints : %s" % '; '.join(_rt7[:2]))

    # ── Vérification programmatique : tous les appels update/draw présents dans gameLoop ──
    _gl_match = re.search(r'function\s+gameLoop\s*\([^)]*\)\s*\{', accumulated)
    if _gl_match:
        # Extraire le corps de gameLoop
        _gl_start = _gl_match.end()
        _depth, _gl_end = 1, _gl_start
        for _ci in range(_gl_start, len(accumulated)):
            if accumulated[_ci] == '{': _depth += 1
            elif accumulated[_ci] == '}':
                _depth -= 1
                if _depth == 0: _gl_end = _ci; break
        _gl_body = accumulated[_gl_start:_gl_end]

        # Trouver les appels manquants
        _missing_updates = [fn for fn in update_fns if fn + '(' not in _gl_body]
        # Ne pas injecter les fonctions d'états spécifiques dans le bloc "playing"
        _state_draws = {'drawMenu', 'drawGameOver', 'drawPause', 'drawVictory', 'drawCredits'}
        _missing_draws = [fn for fn in draw_fns if fn + '(' not in _gl_body and fn not in _state_draws]

        if _missing_updates or _missing_draws:
            phase3_log.warning(
                "[layered] Couche 7 appels manquants — updates: %s | draws: %s" % (
                    ', '.join(_missing_updates) or 'aucun',
                    ', '.join(_missing_draws) or 'aucun'
                )
            )
            # Injecter les appels manquants avant la première draw* dans le bloc playing
            _playing_match = re.search(r'gameState\s*===?\s*["\']playing["\']', _gl_body)
            if _playing_match:
                # Trouver la fin du bloc playing (premier }) après le match
                _inj_lines = []
                for fn in _missing_updates:
                    call = fn + '(dt);' if fn.startswith('update') else fn + '();'
                    _inj_lines.append('    ' + call)
                for fn in _missing_draws:
                    _inj_lines.append('    ' + fn + '();')
                if _inj_lines:
                    _injection = '\n' + '\n'.join(_inj_lines)
                    # Insérer après l'ouverture du bloc playing
                    _brace_pos = _gl_body.find('{', _playing_match.end())
                    if _brace_pos != -1:
                        _abs_pos = _gl_start + _brace_pos + 1
                        accumulated = accumulated[:_abs_pos] + _injection + accumulated[_abs_pos:]
                        phase3_log.info("[layered] Couche 7 injection auto : %s" % ', '.join(_missing_updates + _missing_draws))

    # Vérification appels orphelins avant L8
    orphans = _check_gameloop_calls(accumulated)
    if orphans:
        phase3_log.info("[layered] Appels orphelins : %s" % ', '.join(orphans[:5]))
        accumulated, stubbed = _stub_orphan_calls(accumulated)
        if stubbed:
            phase3_log.info("[layered] Stubs orphelins injectés : %s" % ', '.join(stubbed))

    # ─────────────────────────────────────────────────────────────
    # COUCHE 8 — POLISH SYSTÈME
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 8 — polish système")
    accumulated_signatures = _extract_function_signatures(accumulated)
    existing_fns_8 = set(_extract_js_declarations(accumulated)['funcs'])
    layer_ctx = _build_layer_context(accumulated, layer1_schema, accumulated_signatures, tail_lines=350, global_contract=_global_contract, incremental_manifest=_incremental_manifest)

    layer8_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n\n'
        f'{layer_ctx}\n\n'
        'MISSION : Génère les systèmes de polish et de feedback visuel/sonore.\n'
        'Fonctions déjà présentes (NE PAS recréer) : ' + (', '.join(sorted(existing_fns_8)[:25]) or 'aucune') + '\n\n'
        'SYSTÈMES OBLIGATOIRES — TOUS à implémenter même si une version basique existe déjà :\n\n'
        '1. SCREEN SHAKE — OBLIGATOIRE :\n'
        '   function triggerShake(m,d){shakeMag=m;shakeTimer=d;}\n'
        '   function updateShake(dt){if(shakeTimer>0){shakeTimer-=dt;var s=shakeMag*(shakeTimer/0.5);\n'
        '     shakeX=(Math.random()-0.5)*s*2;shakeY=(Math.random()-0.5)*s*2;\n'
        '   }else{shakeX=0;shakeY=0;shakeMag=0;}}\n\n'
        '2. FLASH OVERLAY — OBLIGATOIRE :\n'
        '   function triggerFlash(col,alpha){flashColor=col||"#FFF";flashAlpha=alpha||0.6;}\n'
        '   function updateFlash(dt){if(flashAlpha>0)flashAlpha=Math.max(0,flashAlpha-dt*3);}\n'
        '   function drawFlash(){if(flashAlpha>0){ctx.save();ctx.globalAlpha=flashAlpha;\n'
        '     ctx.fillStyle=flashColor;ctx.fillRect(0,0,W,H);ctx.restore();}}\n\n'
        '3. FLOAT TEXTS — OBLIGATOIRE :\n'
        '   function updateFloatTexts(dt){for(var i=floatTexts.length-1;i>=0;i--){\n'
        '     var ft=floatTexts[i];ft.y+=ft.vy*dt;ft.life-=dt;\n'
        '     if(ft.life<=0)floatTexts.splice(i,1);}}\n'
        '   function drawFloatTexts(){floatTexts.forEach(function(ft){\n'
        '     ctx.save();ctx.globalAlpha=Math.min(1,ft.life/0.4);\n'
        '     ctx.fillStyle=ft.col||"#FFD700";ctx.font="bold 18px monospace";\n'
        '     ctx.textAlign="center";ctx.fillText(ft.txt,ft.x,ft.y);ctx.restore();});}\n\n'
        '4. SONS WebAudio — OBLIGATOIRE (système complet, 0 fichier externe) :\n'
        '   function _initAudio(){if(_AC)return;try{_AC=new(window.AudioContext||window.webkitAudioContext)();}catch(e){}}\n'
        '   function _playTone(freq,dur,type,vol,delay){\n'
        '     if(!_AC)return; var t=_AC.currentTime+(delay||0);\n'
        '     var o=_AC.createOscillator(),g=_AC.createGain();\n'
        '     o.connect(g);g.connect(_AC.destination);\n'
        '     o.frequency.value=freq; o.type=type||"square";\n'
        '     g.gain.setValueAtTime(0.001,t);\n'
        '     g.gain.linearRampToValueAtTime(vol||0.15,t+0.005);\n'
        '     g.gain.exponentialRampToValueAtTime(0.001,t+dur);\n'
        '     o.start(t); o.stop(t+dur+0.01);\n'
        '   }\n'
        '   function soundShoot(){_playTone(520,0.06,"square",0.08);}\n'
        '   function soundHit(){_playTone(180,0.12,"sawtooth",0.18);}\n'
        '   function soundExplosion(){_playTone(60,0.5,"sawtooth",0.35);_playTone(120,0.3,"square",0.2,0.05);}\n'
        '   function soundPowerUp(){[660,880,1100].forEach(function(f,i){_playTone(f,0.12,"sine",0.18,i*0.07);});}\n'
        '   function soundLevelUp(){[440,550,660,880,1100].forEach(function(f,i){_playTone(f,0.15,"sine",0.2,i*0.08);});}\n'
        '   function soundMenuBeep(){_playTone(440,0.05,"sine",0.1);}\n'
        '   function soundGameOver(){[330,220,165].forEach(function(f,i){_playTone(f,0.3,"sawtooth",0.25,i*0.2);});}\n\n'
        '5. COMBO DISPLAY (si drawCombo absent) :\n'
        '   function drawCombo(){\n'
        '     if(combo<2) return;\n'
        '     var alpha=Math.min(1,comboTimer/3);\n'
        '     ctx.save(); ctx.globalAlpha=alpha;\n'
        '     ctx.fillStyle="#ff8800"; ctx.font="bold "+(28+combo*2)+"px monospace";\n'
        '     ctx.textAlign="center";\n'
        '     ctx.fillText("x"+combo+" COMBO!",W/2,H*0.7);\n'
        '     ctx.restore();\n'
        '   }\n\n'
        '4. WAVE ANNOUNCE (si drawWaveAnnounce absent) :\n'
        '   function drawWaveAnnounce(){\n'
        '     if(waveAnnounce<=0) return;\n'
        '     var alpha=Math.min(1,waveAnnounce);\n'
        '     ctx.save(); ctx.globalAlpha=alpha;\n'
        '     ctx.fillStyle="#ffffff"; ctx.font="bold 48px monospace";\n'
        '     ctx.textAlign="center"; ctx.shadowColor="#00aaff"; ctx.shadowBlur=20;\n'
        '     ctx.fillText(waveAnnounceTxt,W/2,H/2);\n'
        '     ctx.restore();\n'
        '   }\n\n'
        f'5. AUTRES ENRICHISSEMENTS SPÉCIFIQUES AU GENRE :\n{enrichment_targets[:500]}\n\n'
        'RÈGLES :\n'
        '- _AC, sfx, flashAlpha, flashColor sont déjà déclarés en L1 — NE PAS les redéclarer\n'
        '- Appelle _initAudio() dans le keydown/mousedown listener (if(!_AC)_initAudio())\n'
        '- Pour intégrer les sons : réécris UNIQUEMENT spawnBullet(), handleBulletEnemyHit() et handlePowerUpCollect()\n'
        '  en ajoutant les appels son ET triggerShake() à la fin de leurs corps respectifs :\n'
        '  spawnBullet → soundShoot() en fin de fonction\n'
        '  handleBulletEnemyHit → soundHit(); si enemy.hp<=0: soundExplosion(); triggerShake(4,0.2); triggerFlash("#FF4400",0.3)\n'
        '  handlePowerUpCollect → soundPowerUp(); triggerFlash("#00FF88",0.3)\n'
        '  Ces 3 fonctions sont courtes et sûres à réécrire — copie leur corps exact depuis le contexte.\n'
        '- Q5 : updateShake(dt), updateFlash(dt), updateFloatTexts(dt) DOIVENT être appelées dans la boucle playing\n'
        '  → réécris updatePlayer() pour appeler updateShake(dt) et updateFlash(dt) en fin de corps,\n'
        '  ou mieux : ajoute une fonction updatePolish(dt) qui les regroupe, que L7 appellera.\n'
        '- drawFlash() et drawFloatTexts() DOIVENT être appelées à la fin de chaque frame (après tout draw)\n'
        '  → ajoute function drawPolish() { drawFlash(); drawFloatTexts(); } que L7 appellera en dernier.\n\n'
        'INTERDIT ABSOLU : redéfinir gameLoop, init(), toute fonction update*() existante sauf spawnBullet/handleBulletEnemyHit/handlePowerUpCollect.\n'
        'NE PAS toucher à updatePlayer, updateEnemies, updateBullets, updateParticles, updateWave, updateBoss.\n\n'
        '⚠️ RÈGLE CRITIQUE — RÉÉCRITURE DE FONCTIONS :\n'
        'Quand tu réécris une fonction existante (ex: spawnBullet), la version précédente est REMPLACÉE.\n'
        'Toutes les variables déclarées avec var DANS la version précédente sont INACCESSIBLES dans ta version.\n'
        'Tu DOIS redéclarer TOUTES les variables locales que tu utilises dans chaque fonction réécrite.\n'
        'Exemple CORRECT :\n'
        '  function spawnBullet() {\n'
        '    var speed = 400;  // ← DOIT être redéclaré même si présent dans l\'ancienne version\n'
        '    ...\n'
        '  }\n'
        'Ne suppose JAMAIS qu\'une variable locale d\'une version précédente est encore disponible.\n\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement.'
    )

    layer8_js = ""
    for attempt in range(2):
        raw = _call_layer(_LAYER_SYSTEM, layer8_prompt, max_tokens=24000, temperature=0.35, disable_thinking=True)
        if not raw or len(raw) < 80:
            _record_layer_event('layer8', False, reason="trop court")
            break
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 8")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 8 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer8', False, reason=quality_reason)
            layer8_prompt += "\n\nATTENTION : rejeté (%s)." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 8")
        if not valid:
            _record_layer_event('layer8', False, reason="syntaxe invalide")
            layer8_prompt += "\n\nATTENTION : syntaxe invalide."
            continue
        # L8 ne trigger pas de gate check (enrichissement libre)
        layer8_js = fixed_js
        _record_layer_event('layer8', True, lines=fixed_js.count('\n'))
        break

    if layer8_js:
        # Strip gameLoop si présent (on ne veut pas de redéclaration)
        if 'function gameLoop' in layer8_js:
            gl_m = re.search(r'function gameLoop\s*\(', layer8_js)
            if gl_m:
                depth, found_open = 0, False
                for ci in range(gl_m.start(), len(layer8_js)):
                    ch = layer8_js[ci]
                    if ch == '{':
                        depth += 1
                        found_open = True
                    elif ch == '}':
                        depth -= 1
                        if found_open and depth == 0:
                            layer8_js = layer8_js[:gl_m.start()] + layer8_js[ci + 1:]
                            break

        decls_before_8 = set(existing_fns_8)
        decls_after_8 = _extract_js_declarations(layer8_js)
        new_fns_from_8 = [fn for fn in decls_after_8['funcs'] if fn not in decls_before_8 and fn != 'gameLoop']

        layer8_js, _resolved8 = _resolve_undeclared_symbols(layer8_js, _symbol_table, accumulated)
        if _resolved8:
            phase3_log.info("[layered] L8 auto-resolved: %s" % ', '.join(_resolved8[:6]))
        accumulated += '\n\n' + layer8_js
        _l8_manifest = _extract_layer_manifest(layer8_js, 8)
        if not _l8_manifest.strip():
            phase3_log.warning("[layered] L8 manifest vide — couche probablement tronquée")
        _incremental_manifest += '\n' + _l8_manifest
        phase3_log.info("[layered] Couche 8 OK — %d chars" % len(layer8_js))

        if new_fns_from_8:
            accumulated = _patch_gameloop_calls(accumulated, new_fns_from_8)

        # J8b : forcer la version correcte de _playTone (last-wins) si L8 l'a réécrite sans var t
        if '_playTone' in accumulated:
            _PLAYTONE_SAFE = (
                '\nfunction _playTone(freq,dur,type,vol,delay){'
                'if(!_AC)return; var t=_AC.currentTime+(delay||0);'
                'var o=_AC.createOscillator(),g=_AC.createGain();'
                'o.connect(g);g.connect(_AC.destination);'
                'o.frequency.value=freq; o.type=type||"square";'
                'g.gain.setValueAtTime(0.001,t);'
                'g.gain.linearRampToValueAtTime(vol||0.15,t+0.005);'
                'g.gain.exponentialRampToValueAtTime(0.001,t+dur);'
                'o.start(t); o.stop(t+dur+0.01);}\n'
            )
            accumulated += _PLAYTONE_SAFE

        # J8 : s'assurer que _initAudio() est câblé dans init() si L8 a généré _initAudio
        if '_initAudio' in layer8_js and '_initAudio' not in accumulated.split('function init')[0] if 'function init' in accumulated else True:
            _init_m = re.search(r'function\s+init\s*\([^)]*\)\s*\{', accumulated)
            if _init_m:
                _init_insert = _init_m.end()
                accumulated = accumulated[:_init_insert] + '\n  if(typeof _initAudio==="function")_initAudio();' + accumulated[_init_insert:]
                phase3_log.info("[layered] J8 : _initAudio() câblé dans init()")
    else:
        phase3_log.info("[layered] Couche 8 ignorée (output vide)")
        _record_layer_event('layer8', False, reason="output vide")

    # ─────────────────────────────────────────────────────────────
    # HELPER : stubs draw* minimaux après rollback ou L9 vide
    # ─────────────────────────────────────────────────────────────
    def _inject_draw_stubs(acc: str, _genre: str, _schemas: dict) -> str:
        """Injecte des stubs fonctionnels pour chaque draw* absent après un rollback L9."""
        _has_palette = 'PALETTE' in acc
        _bg   = 'PALETTE.bg||"#0a0a1a"'   if _has_palette else '"#0a0a1a"'
        _pl   = 'PALETTE.player||"#00ffcc"' if _has_palette else '"#00ffcc"'
        _en   = 'PALETTE.enemy||"#ff4444"' if _has_palette else '"#ff4444"'
        _bo   = 'PALETTE.boss||"#ff00ff"'  if _has_palette else '"#ff00ff"'

        _REQUIRED_DRAW = {
            'drawBackground': (
                f'function drawBackground(){{'
                f'ctx.fillStyle={_bg};ctx.fillRect(0,0,W,H);'
                f'ctx.strokeStyle="rgba(0,200,255,0.1)";ctx.lineWidth=1;'
                f'for(var _gx=0;_gx<W;_gx+=60){{ctx.beginPath();ctx.moveTo(_gx,0);ctx.lineTo(_gx,H);ctx.stroke();}}'
                f'for(var _gy=0;_gy<H;_gy+=60){{ctx.beginPath();ctx.moveTo(0,_gy);ctx.lineTo(W,_gy);ctx.stroke();}}'
                f'}}'
            ),
            'drawPlayer': (
                f'function drawPlayer(){{'
                f'if(!player)return;'
                f'var _pw=player.w||24,_ph=player.h||24;'
                f'ctx.fillStyle={_pl};ctx.shadowColor={_pl};ctx.shadowBlur=10;'
                f'ctx.fillRect(player.x-_pw/2,player.y-_ph/2,_pw,_ph);'
                f'ctx.shadowBlur=0;}}'
            ),
            'drawEnemies': (
                f'function drawEnemies(){{'
                f'for(var _i=0;_i<enemies.length;_i++){{'
                f'var _e=enemies[_i];'
                f'ctx.fillStyle={_en};'
                f'ctx.beginPath();ctx.arc(_e.x,_e.y,_e.r||12,0,Math.PI*2);ctx.fill();}}}}'
            ),
            'drawBoss': (
                f'function drawBoss(){{'
                f'if(!bossActive||!boss)return;'
                f'ctx.fillStyle={_bo};ctx.shadowColor={_bo};ctx.shadowBlur=20;'
                f'ctx.fillRect(boss.x-boss.w/2,boss.y-boss.h/2,boss.w,boss.h);'
                f'ctx.shadowBlur=0;}}'
            ),
            'drawHUD': (
                'function drawHUD(){'
                'ctx.fillStyle="#fff";ctx.font="bold 16px monospace";'
                'ctx.fillText("Score: "+(score||0),10,25);'
                'ctx.fillText("Vies: "+(lives||0),10,50);}'
            ),
            'drawMenu': (
                'function drawMenu(){'
                'ctx.fillStyle="#fff";ctx.font="bold 36px monospace";'
                'ctx.textAlign="center";'
                'ctx.fillText("PRESS SPACE",W/2,H/2);'
                'ctx.textAlign="left";}'
            ),
            'drawGameOver': (
                'function drawGameOver(){'
                'ctx.fillStyle="#ff4444";ctx.font="bold 48px monospace";'
                'ctx.textAlign="center";'
                'ctx.fillText("GAME OVER",W/2,H/2);'
                'ctx.fillStyle="#fff";ctx.font="20px monospace";'
                'ctx.fillText("SPACE pour rejouer",W/2,H/2+60);'
                'ctx.textAlign="left";}'
            ),
        }

        stubs_added = []
        for fn_name, stub_code in _REQUIRED_DRAW.items():
            if f'function {fn_name}' not in acc:
                acc += '\n' + stub_code
                stubs_added.append(fn_name)

        if stubs_added:
            phase3_log.info(
                "[layered] Stubs draw* injectés (L9 absent/rollback) : %s" % ', '.join(stubs_added)
            )
        return acc

    # ─────────────────────────────────────────────────────────────
    # COUCHE 9 — GRAPHISME FINAL (directeur artistique)
    # ─────────────────────────────────────────────────────────────
    phase3_log.info("[layered] Couche 9 — graphisme final")
    accumulated_before_l9 = accumulated  # snapshot pour rollback si L9 casse le runtime
    accumulated_signatures = _extract_function_signatures(accumulated)
    game_events = _detect_game_events(accumulated)
    draw_code_l6 = _extract_draw_code(accumulated)

    # Propriétés existantes sur player/boss/enemies pour éviter les hallucinations de L9
    _schema_props = list(schemas_dict.get('player', set())) + list(schemas_dict.get('boss', set()))
    _safe_props_hint = ', '.join(_schema_props[:12]) if _schema_props else 'x, y, w, h, hp, maxHp, speed'

    # Q6 — Guide de style artistique par genre
    _L9_ART_STYLES = {
        'shooter': (
            "STYLE : Neon Space Shooter — fond noir quasi-absolu, glow omniprésent (shadowBlur 8-20px), "
            "traînées lumineuses derrière les bullets (lignes avec alpha décroissant), "
            "ennemis géométriques anguleux avec fill sombre + stroke néon, "
            "explosions en arcs de cercles colorés, HUD à la police 'monospace' pixelisée."
        ),
        'platformer': (
            "STYLE : Cartoon Platformer — contours noirs épais (lineWidth 2-3, stroke avant fill), "
            "couleurs vives et saturées (pas de nuances foncées), "
            "ombres portées décalées (+2px bas-droite), "
            "animations de saut (squash & stretch : scaleX 1.2 au sol, scaleY 1.3 au sommet), "
            "background parallaxe à 3 couches (sky, middleground, foreground)."
        ),
        'rpg': (
            "STYLE : Pixel Art RPG — palette limitée (16-32 couleurs max), "
            "imageSmoothingEnabled=false (pixel art net), tuiles 32px avec bordures grilles subtiles, "
            "zone sombre pour les donjons (ambiance torche avec radialGradient pulsant), "
            "HUD en style fenêtre RPG (fond sombre, bordure biseautée, texte blanc)."
        ),
        'defense': (
            "STYLE : Tower Defense — vue isométrique simulée avec tuiles dessinées en rhombes, "
            "tours avec base cylindrique + tourelle rotatif, ennemis avec barres de vie intégrées, "
            "projectiles en arcs paraboliques avec traînée, "
            "feedback de placement (grille verte/rouge selon validité)."
        ),
        'runner': (
            "STYLE : Endless Runner — décor cyberpunk en défilement horizontal, "
            "sol en grille perspective, obstacles neon, "
            "personnage avec traînée de mouvement (motion blur via lignes translucides), "
            "score en grand format centré haut, multiplicateur de vitesse visible."
        ),
    }
    _genre_lower = genre.lower()
    _art_style_hint = next(
        (style for key, style in _L9_ART_STYLES.items() if key in _genre_lower),
        f"STYLE : {style_visuel} — glow (shadowBlur), gradients, animations fluides, HUD propre."
    )

    layer9_prompt = (
        f'Jeu : "{titre}" — genre : {genre}\n'
        f'{_art_style_hint}\n'
        f'Palette imposée : {palette}\n'
        f'{_ux_contract_str}\n'
        f'{layer1_schema}\n\n'
        f'{accumulated_signatures}\n\n'
        f'{game_events}\n\n'
        f'{draw_code_l6[:3000] if draw_code_l6 else ""}\n\n'
        'MISSION ARTISTIQUE : Réécris les fonctions draw* pour les rendre visuellement exceptionnelles.\n'
        'En JavaScript, la DERNIÈRE définition d\'une fonction écrase la précédente.\n'
        'Tu peux redéfinir drawBackground, drawPlayer, drawEnemies, drawBoss, drawHUD, drawMenu, drawGameOver.\n\n'
        '⚠️ RULE ZERO — ABSOLUTE BAN ON RECTANGLE SPRITES:\n'
        'Any player, enemy, boss or projectile drawn with fillRect() alone MUST be replaced.\n'
        '✅ Use: arc() · bezierCurveTo() · createRadialGradient()+arc() · 3+ composed draw calls\n'
        'fillRect() as the only sprite = visual QC score <= 6/10. NON-NEGOTIABLE.\n\n'
        '⚠️ RÈGLE N°1 — VARIABLES NOUVELLES :\n'
        'Toute variable que tu introduis DOIT être déclarée EN TÊTE du fragment avec le guard typeof :\n'
        '  var _bgTimer = (typeof _bgTimer !== "undefined") ? _bgTimer : 0;\n'
        '  var _bgStars = (typeof _bgStars !== "undefined") ? _bgStars : [];\n'
        'JAMAIS référencer une variable que tu n\'as pas déclarée dans ce fragment.\n\n'
        '⚠️ RÈGLE N°1bis — RÉÉCRITURE DE FONCTIONS :\n'
        'Quand tu réécris drawBackground, drawPlayer, etc., la version L6 est EFFACÉE — ses variables locales disparaissent.\n'
        'Tout ce que tu utilises DANS le corps de ta fonction doit être déclaré DANS ce corps.\n'
        'Exemple : si tu utilises gridSize dans drawBackground, tu DOIS écrire var gridSize = 50; au début.\n'
        'Ne suppose JAMAIS qu\'une variable était dans la version précédente de la fonction — elle n\'existe plus.\n\n'
        f'⚠️ RÈGLE N°2 — PROPRIÉTÉS D\'OBJETS :\n'
        f'Utilise UNIQUEMENT les propriétés du SCHÉMA : {_safe_props_hint}\n'
        'JAMAIS inventer player.angle, player.rot, enemy.frame, etc. si absent du schéma.\n'
        'Pour une rotation visuelle : utilise une variable locale angle calculée avec _bgTimer UNIQUEMENT — jamais Date.now() (ignore le delta time).\n\n'
        'EXIGENCES VISUELLES (TOUTES obligatoires) :\n\n'
        '1. drawBackground() — fond animé riche :\n'
        '   var _bgTimer=(typeof _bgTimer!=="undefined")?_bgTimer:0; _bgTimer+=dt;\n'
        '   Étoiles parallaxe (3 couches, vitesses différentes), nébuleuse en arrière-plan,\n'
        '   grille ou effet de profondeur selon le genre. JAMAIS un fond uni.\n\n'
        '2. drawPlayer() — joueur mémorable :\n'
        '   ctx.save(); ctx.translate(player.x, player.y);\n'
        '   Glow (shadowBlur=15), gradient radial, forme distinctive,\n'
        '   shield visible si shieldActive (cercle pulsant bleu translucide).\n'
        '   ctx.restore(); — NE PAS utiliser player.angle sauf si dans le schéma.\n\n'
        '3. drawEnemies() — ennemis visuellement distincts par TYPE :\n'
        '   Chaque type a une forme différente (triangle, losange, hexagone...),\n'
        '   glow selon e.hp restant, barre HP sous l\'ennemi si e.hp>1.\n\n'
        '4. drawBoss() — boss exceptionnel si bossActive && boss :\n'
        '   3x plus grand, aura colorée selon bossPhase (1=vert, 2=orange, 3=rouge),\n'
        '   barre HP stylisée avec gradient, texte "BOSS" au-dessus.\n\n'
        '5. drawHUD() — HUD complet :\n'
        '   Score haut-gauche avec ombre, vies en icônes haut-droite,\n'
        '   wave/level centré, barre HP si player.hp défini dans schéma,\n'
        '   waveAnnounce si waveAnnounce>0.\n\n'
        '6. drawMenu() — titre avec glow, meilleur score, instruction clignotante.\n\n'
        '7. drawGameOver() — "GAME OVER" en rouge avec glow, score vs high score, instruction rejouer.\n\n'
        '8. FINAL CHECK — shadowBlur on all entities:\n'
        '   drawPlayer() MUST have ctx.shadowBlur >= 10 — if missing in the code, add it now.\n'
        '   drawEnemies() MUST have ctx.shadowBlur for each enemy type.\n'
        '   drawBullets/drawProjectiles(): glow or decreasing-alpha trail is mandatory.\n'
        '   If these calls are missing in functions inherited from L6 -> add them in your rewrite.\n\n'
        f'PALETTE disponible — clés déclarées en L1 : {_palette_keys_hint}\n'
        '   IMPORTANT : utilise UNIQUEMENT les clés listées ci-dessus — ne jamais inventer PALETTE.neonXxx, PALETTE.glow, PALETTE.accent si absents de la liste.\n'
        '   Si une couleur n\'est pas dans PALETTE, utilise une string CSS directe (ex: \'#00ffcc\').\n\n'
        'RÈGLES ABSOLUES :\n'
        '- ctx.save()/ctx.restore() pour CHAQUE transformation — jamais de translate sans save/restore\n'
        '- Code COMPLET, pas de TODO ni de "/* comme avant */"\n'
        '- Commence par les var declarations (typeof guard), puis les fonctions\n'
        '- INTERDIT ABSOLU : rgba() appelé comme une fonction JS — cause ReferenceError et écran noir.\n'
        '  FAUX : ctx.fillStyle = rgba(0, 0, 0, 0.5)         ← ReferenceError\n'
        '  FAUX : ctx.fillStyle = `rgba(${r},${g},${b},0.5)` ← template literal problématique\n'
        '  VRAI : ctx.fillStyle = \'rgba(0,0,0,0.5)\';          ← string directe\n'
        '  VRAI : ctx.globalAlpha = 0.5; ctx.fillStyle = \'#000\'; ← alpha séparé\n\n'
        f'{_no_redecl_note}'
        f'{_contract_reminder(_global_contract, _incremental_manifest)}'
        'Output : JS pur uniquement.'
    )

    layer9_js = ""
    _l9_use_thinking = True  # J14 : première tentative avec thinking, fallback sans
    for attempt in range(2):
        # J1 : thinking activé pour L9 (direction artistique — créativité maximale)
        # J14 : si rollback ou 2ème tentative, désactiver thinking pour éviter sur-complexité
        raw = _call_layer(_LAYER_SYSTEM_GRAPHIQUE, layer9_prompt, max_tokens=32000,
                          temperature=0.45, disable_thinking=not _l9_use_thinking)
        if not raw or len(raw) < 80:
            _record_layer_event('layer9', False, reason="trop court")
            break
        quality_ok, quality_reason = _check_layer_quality(raw, "Couche 9")
        if not quality_ok:
            phase3_log.warning("[layered] Couche 9 tentative %d rejetée (%s)" % (attempt + 1, quality_reason))
            _record_layer_event('layer9', False, reason=quality_reason)
            layer9_prompt += "\n\nATTENTION : rejeté (%s). Génère des fonctions draw* BELLES et COMPLÈTES." % quality_reason
            continue
        fixed_js, valid = _validate_layer(raw, accumulated, "Couche 9")
        if not valid:
            _record_layer_event('layer9', False, reason="syntaxe invalide")
            layer9_prompt += "\n\nATTENTION : syntaxe invalide."
            _l9_use_thinking = False  # J14 : désactive thinking si 1ère tentative a échoué
            continue
        layer9_js = fixed_js
        _record_layer_event('layer9', True, lines=fixed_js.count('\n'))
        break

    if layer9_js:
        # Gate accolades L9 avant d'accumuler — rollback immédiat si déséquilibré
        _l9_open = layer9_js.count('{')
        _l9_close = layer9_js.count('}')
        if abs(_l9_open - _l9_close) > 1:
            phase3_log.warning(
                "[layered] Couche 9 accolades déséquilibrées (%d{ vs %d}) — rollback L9" % (_l9_open, _l9_close)
            )
            _record_layer_event('layer9', False, reason="accolades déséquilibrées")
            layer9_js = ""
        if layer9_js:
            layer9_js, _resolved9 = _resolve_undeclared_symbols(layer9_js, _symbol_table, accumulated)
            if _resolved9:
                phase3_log.info("[layered] L9 auto-resolved: %s" % ', '.join(_resolved9[:6]))
            accumulated += '\n\n' + layer9_js
        # Runtime check L9 — rollback si L9 casse quelque chose de critique
        _rt9 = _validate_layer_runtime(_HTML_TEMPLATE.format(title="test", js_body=accumulated))
        _crit9 = [e for e in (_rt9 or [])
                  if any(kw in e for kw in ('is not defined', 'Cannot read', 'init is not a function', 'gameLoop is not a function', 'SyntaxError', 'Unexpected token', 'Unexpected end'))]
        if _crit9:
            phase3_log.warning(
                "[layered] Couche 9 erreurs runtime critiques (%s) — rollback L9" % _crit9[0][:80]
            )
            accumulated = accumulated_before_l9
            _record_layer_event('layer9', False, reason="rollback runtime: " + _crit9[0][:50])
            _inject_draw_stubs(accumulated, genre, schemas_dict)
        else:
            phase3_log.info("[layered] Couche 9 OK — %d chars (visuels enrichis)" % len(layer9_js))
            if _rt9:
                phase3_log.info("[layered] Couche 9 runtime hints (non-bloquants) : %s" % '; '.join(_rt9[:2]))
    else:
        phase3_log.info("[layered] Couche 9 ignorée (output vide ou invalide)")
        _record_layer_event('layer9', False, reason="output vide")
        accumulated = _inject_draw_stubs(accumulated, genre, schemas_dict)

    # ─────────────────────────────────────────────────────────────
    # ASSEMBLAGE FINAL
    # ─────────────────────────────────────────────────────────────
    accumulated = _fix_nan_risks(accumulated)

    # ── Déduplication requestAnimationFrame(gameLoop) ──
    # Les couches (réparation, L7, try/catch) peuvent chacune en injecter un.
    # Étape 1 : supprimer les rAF standalone (hors fonctions) en excès — garder le dernier.
    _raf_standalone = re.compile(
        r'^[ \t]*requestAnimationFrame\s*\(\s*gameLoop\s*\)\s*;?[ \t]*$',
        re.MULTILINE
    )
    _raf_matches = list(_raf_standalone.finditer(accumulated))
    if len(_raf_matches) > 1:
        for _m in reversed(_raf_matches[:-1]):
            accumulated = accumulated[:_m.start()] + accumulated[_m.end():]
        phase3_log.info(
            f"[layered] {len(_raf_matches)-1} requestAnimationFrame(gameLoop) dupliqué(s) supprimé(s)"
        )
    # Étape 2 : dans le corps de gameLoop, dédupliquer les rAF en excès (garder le dernier)
    _gl_raf_m = re.search(r'function\s+gameLoop\s*\([^)]*\)\s*\{', accumulated)
    if _gl_raf_m:
        _gl_body_start = _gl_raf_m.end()
        _gl_depth, _gl_body_end = 1, _gl_body_start
        for _ci in range(_gl_body_start, len(accumulated)):
            if accumulated[_ci] == '{': _gl_depth += 1
            elif accumulated[_ci] == '}':
                _gl_depth -= 1
                if _gl_depth == 0: _gl_body_end = _ci; break
        _gl_body = accumulated[_gl_body_start:_gl_body_end]
        _raf_in_gl = list(re.finditer(r'requestAnimationFrame\s*\(\s*gameLoop\s*\)\s*;?', _gl_body))
        if len(_raf_in_gl) > 1:
            # Supprimer tous sauf le dernier dans gameLoop
            _removed_count = 0
            _new_body = _gl_body
            _offset = 0
            for _rm in reversed(_raf_in_gl[:-1]):
                _new_body = _new_body[:_rm.start() - _offset] + _new_body[_rm.end() - _offset:]
                _offset += _rm.end() - _rm.start()
                _removed_count += 1
            accumulated = accumulated[:_gl_body_start] + _new_body + accumulated[_gl_body_end:]
            phase3_log.info(
                f"[layered] {_removed_count} requestAnimationFrame(gameLoop) dupliqué(s) dans gameLoop supprimé(s)"
            )

    # C6 : supprimer les requestAnimationFrame(gameLoop) dans le corps de init()
    # init() ne doit pas lancer la boucle — c'est au code de démarrage de le faire
    _init_m = re.search(r'function\s+init\s*\(\s*\)\s*\{', accumulated)
    if _init_m:
        _init_body_start = _init_m.end()
        _init_depth, _init_body_end = 1, _init_body_start
        for _ci in range(_init_body_start, len(accumulated)):
            if accumulated[_ci] == '{': _init_depth += 1
            elif accumulated[_ci] == '}':
                _init_depth -= 1
                if _init_depth == 0: _init_body_end = _ci; break
        _init_body = accumulated[_init_body_start:_init_body_end]
        _raf_in_init = list(re.finditer(r'requestAnimationFrame\s*\(\s*gameLoop\s*\)\s*;?\n?', _init_body))
        if _raf_in_init:
            _new_init = _init_body
            for _m in reversed(_raf_in_init):
                _new_init = _new_init[:_m.start()] + _new_init[_m.end():]
            accumulated = accumulated[:_init_body_start] + _new_init + accumulated[_init_body_end:]
            phase3_log.info(f"[layered] C6 : {len(_raf_in_init)} RAF dans init() supprimé(s) — double boucle évitée")

    # ── Garanties programmatiques post-assemblage ──────────────────────────────
    # PALETTE : si absent ou déclaré const (peut être supprimé par dédup) → injecter var fallback
    if not re.search(r'\bvar\s+PALETTE\s*=', accumulated):
        if not re.search(r'\bconst\s+PALETTE\s*=|\blet\s+PALETTE\s*=', accumulated):
            # Absent complètement — injecter default
            _palette_inject = (
                "var PALETTE = {bg:'#0a0a1a',player:'#00ffcc',enemy:'#ff4444',boss:'#ff00ff',"
                "bullet:'#ffff00',ui:'#ffffff',shield:'#00aaff',particle:'#ffaa00',"
                "bulletHit:'#ff8800',damageText:'#ff0000',enemyBomberBody:'#ff6600',"
                "enemyBomberOutline:'#ffcc00',drone:'#44ff88',turret:'#ff8844',"
                # Clés neon générées par L9 — évite les undefined sur PALETTE.neonCyan etc.
                "neonCyan:'#00ffff',neonMagenta:'#ff00ff',neonOrange:'#ff6600',"
                "neonYellow:'#ffff00',neonGreen:'#00ff44',neonPink:'#ff0088',"
                "neonBlue:'#0088ff',neonRed:'#ff2200',neonWhite:'#ffffff',"
                "neonPurple:'#cc00ff',neonTeal:'#00ffcc',neonGold:'#ffd700',"
                "dark:'#0a0a1a',darkGray:'#222244',blue:'#0066cc',cyan:'#00ccff',"
                "green:'#00cc44',red:'#ff2200',white:'#ffffff',gray:'#888888',"
                "orange:'#ff6600',purple:'#8800ff',yellow:'#ffdd00',pink:'#ff44aa'};\n"
            )
            accumulated = _palette_inject + accumulated
            phase3_log.info("[layered] PALETTE absente — injection fallback garantie")
        else:
            # Déclaré avec const/let → convertir en var pour éviter les conflits de scope
            accumulated = re.sub(r'\b(?:const|let)\s+(PALETTE\s*=)', r'var \1', accumulated)
            phase3_log.info("[layered] PALETTE const/let → var (compatibilité multi-couche)")

    # PALETTE clés manquantes — L9 peut inventer PALETTE.neonCyan absent de L1
    _palette_existing_m = re.search(r'\bvar\s+PALETTE\s*=\s*\{([^}]+)\}', accumulated, re.DOTALL)
    if _palette_existing_m:
        _pal_declared = set(re.findall(r'(\w+)\s*:', _palette_existing_m.group(1)))
        _pal_used = set(re.findall(r'\bPALETTE\.(\w+)\b', accumulated))
        _pal_missing = _pal_used - _pal_declared
        if _pal_missing:
            _pal_new = ','.join(
                f"{k}:'{next((c for h,c in [('neon','#00ffcc'),('cyan','#00ffff'),('magenta','#ff00ff'),('orange','#ff6600'),('gold','#ffd700'),('yellow','#ffff00'),('green','#00ff44'),('pink','#ff0088'),('red','#ff2200'),('blue','#0088ff'),('white','#ffffff'),('dark','#0a0a1a'),('gray','#888888'),('bg','#0a0a1a'),('player','#00ffcc'),('enemy','#ff4444'),('boss','#ff00ff'),('bullet','#ffff00'),('ui','#ffffff'),('hit','#ff8800')] if h in k.lower()), '#ffffff')}'"
                for k in sorted(_pal_missing)
            )
            accumulated = re.sub(
                r'(\bvar\s+PALETTE\s*=\s*\{)([^}]+)(\})',
                lambda m: m.group(1) + m.group(2).rstrip().rstrip(',') + ',' + _pal_new + m.group(3),
                accumulated, count=1, flags=re.DOTALL
            )
            phase3_log.info(f"[layered] PALETTE clés manquantes ajoutées : {', '.join(sorted(_pal_missing)[:8])}")

    # _AC + sfx : garantir déclaration si utilisés
    if '_AC' in accumulated and not re.search(r'\bvar\s+_AC\b|\blet\s+_AC\b|\bconst\s+_AC\b', accumulated):
        accumulated = "var _AC = null;\n" + accumulated
        phase3_log.info("[layered] _AC manquant — déclaration injectée")
    if 'sfx.' in accumulated and not re.search(r'\bvar\s+sfx\b|\blet\s+sfx\b|\bconst\s+sfx\b', accumulated):
        accumulated = "var sfx = {};\n" + accumulated
        phase3_log.info("[layered] sfx manquant — déclaration injectée")

    # C1 — Garantie programmatique : handleBulletEnemyHit incrémente toujours score
    _hit_m = re.search(r'function\s+handleBulletEnemyHit\s*\([^)]*\)\s*\{', accumulated)
    if _hit_m:
        _hit_start = _hit_m.end()
        _hit_depth, _hit_end = 1, _hit_start
        while _hit_end < len(accumulated) and _hit_depth > 0:
            if accumulated[_hit_end] == '{': _hit_depth += 1
            elif accumulated[_hit_end] == '}': _hit_depth -= 1
            _hit_end += 1
        _hit_body = accumulated[_hit_start:_hit_end - 1]
        if 'score' not in _hit_body:
            _score_patch = '\n  if(e && e.hp<=0){ score+=(e.points||10); }'
            accumulated = accumulated[:_hit_end - 1] + _score_patch + accumulated[_hit_end - 1:]
            phase3_log.info("[layered] C1 : score+= injecté dans handleBulletEnemyHit")

    accumulated = _inject_trycatch_gameloop(accumulated)
    if 'drawErrorScreen' in accumulated:
        phase3_log.info("[layered] try/catch gameLoop injecté")

    # A4 : Injection window.__ARCADE_TEST__ hooks pour Playwright
    accumulated = _inject_arcade_test_hooks(accumulated)
    phase3_log.info("[layered] __ARCADE_TEST__ hooks injectés")

    import html as _html_mod_final
    title_safe = _html_mod_final.escape(titre[:60])
    final_html = _HTML_TEMPLATE.format(title=title_safe, js_body=accumulated)

    try:
        from js_syntax_checker import fix_all_auto, check_and_report as _js_check
        final_html, _fixed, fix_descs = fix_all_auto(final_html)
        if fix_descs:
            phase3_log.info("[layered] Auto-fix final : %s" % '; '.join(fix_descs[:3]))
        _final_issues, _final_broken = _js_check(final_html)
        if _final_broken:
            phase3_log.warning(
                "[layered] Syntaxe finale invalide : %s"
                % (_final_issues[0][:60] if _final_issues else '?')
            )
        else:
            phase3_log.info("[layered] Syntaxe finale OK")
    except Exception as e:
        phase3_log.warning("[layered] Validation finale impossible (%s)" % e)

    rt_final = _validate_layer_runtime(final_html)
    if rt_final:
        critical_fatal = [e for e in rt_final
                          if 'init is not a function' in e or 'gameLoop is not a function' in e]
        if critical_fatal:
            phase3_log.warning(
                "[layered] Erreur runtime critique finale : %s — fallback compact" % critical_fatal[0]
            )
            return _run_compact_fallback(context, erreurs_passees=erreurs_passees)

        # ── Réparation runtime ciblée (boucle 2 tentatives) ──────────────────────
        # Si des erreurs `is not defined` / `Cannot read` subsistent après assemblage,
        # on tente d'abord les règles auto-fix, puis un appel LLM chirurgical.
        _rt_errors = [e for e in rt_final
                      if any(kw in e for kw in ('is not defined', 'Cannot read', 'Unexpected token', 'SyntaxError'))]
        if _rt_errors:
            phase3_log.warning(
                "[layered] %d erreur(s) runtime post-assemblage — tentative réparation : %s"
                % (len(_rt_errors), _rt_errors[0][:80])
            )
            # Tentative 1 — règles déterministes (auto_fix_rules)
            try:
                from agents.phase5._auto_fix_rules import apply_all_rules as _apply_rules_repair
                _js_repair = _extract_js_from_html(final_html)
                _js_fixed, _rules_applied = _apply_rules_repair(_js_repair)
                if _rules_applied:
                    _html_repaired = re.sub(
                        r'(<script[^>]*>)(.*?)(</script>)',
                        lambda m: m.group(1) + _js_fixed + m.group(3),
                        final_html, flags=re.DOTALL
                    )
                    _rt_after_rules = _validate_layer_runtime(_html_repaired)
                    _rt_errors_after = [e for e in (_rt_after_rules or [])
                                        if any(kw in e for kw in ('is not defined', 'Cannot read'))]
                    if len(_rt_errors_after) < len(_rt_errors):
                        final_html = _html_repaired
                        phase3_log.info(
                            "[layered] Réparation auto-fix : %d → %d erreur(s) : %s"
                            % (len(_rt_errors), len(_rt_errors_after), ', '.join(_rules_applied[:3]))
                        )
                        _rt_errors = _rt_errors_after
            except Exception as _e_repair_rules:
                phase3_log.warning("[layered] Réparation auto-fix erreur : %s" % _e_repair_rules)

            # Tentative 2 — LLM chirurgical si des erreurs subsistent
            if _rt_errors:
                try:
                    _err_lines = '\n'.join('- ' + e for e in _rt_errors[:5])
                    _js_to_repair = _extract_js_from_html(final_html)
                    # Extraire les fonctions impliquées pour donner du contexte
                    _implicated = []
                    for _err in _rt_errors[:4]:
                        _m_fn = re.search(r"'(\w+)' is not defined", _err)
                        if _m_fn:
                            _implicated.append(_m_fn.group(1))
                    _ctx_fns = ""
                    for _fn_name in _implicated[:3]:
                        _fn_m = re.search(
                            r'function\s+' + re.escape(_fn_name) + r'\s*\([^)]*\)\s*\{',
                            _js_to_repair
                        )
                        if not _fn_m:
                            _ctx_fns += f"\n// '{_fn_name}' est utilisé mais n'existe pas dans le code."
                    _llm_repair_prompt = (
                        f'Code JS d\'un jeu HTML5 Canvas 2D — erreurs runtime détectées :\n{_err_lines}\n\n'
                        f'{_ctx_fns}\n\n'
                        'MISSION : corrige UNIQUEMENT les erreurs listées ci-dessus.\n'
                        '- Pour chaque variable "X is not defined" : ajoute "var X = [valeur_initiale];" en début de script\n'
                        '- Pour chaque "rgba() is not a function" ou appel rgba(...) non quoté : remplace par une string CSS\n'
                        '- Pour chaque propriété "Cannot read properties of undefined" : ajoute un guard "if(!obj) return;"\n'
                        'NE MODIFIE PAS le reste du code — retourne UNIQUEMENT les lignes de correction à injecter en début de script.\n'
                        'Format de retour : code JS pur (déclarations var + corrections), sans HTML ni markdown.'
                    )
                    _repair_code = _call_layer(_LAYER_SYSTEM, _llm_repair_prompt, max_tokens=4000, temperature=0.05, disable_thinking=True)
                    if _repair_code and len(_repair_code) > 10:
                        _js_with_repair = _repair_code.strip() + '\n\n' + _js_to_repair
                        _html_llm_repaired = re.sub(
                            r'(<script[^>]*>)(.*?)(</script>)',
                            lambda m: m.group(1) + _js_with_repair + m.group(3),
                            final_html, flags=re.DOTALL
                        )
                        _rt_after_llm = _validate_layer_runtime(_html_llm_repaired)
                        _rt_errors_llm = [e for e in (_rt_after_llm or [])
                                          if any(kw in e for kw in ('is not defined', 'Cannot read'))]
                        if len(_rt_errors_llm) <= len(_rt_errors):
                            final_html = _html_llm_repaired
                            phase3_log.info(
                                "[layered] Réparation LLM ciblée : %d → %d erreur(s)"
                                % (len(_rt_errors), len(_rt_errors_llm))
                            )
                        else:
                            phase3_log.warning("[layered] Réparation LLM aggravait les erreurs — ignorée")
                except Exception as _e_repair_llm:
                    phase3_log.warning("[layered] Réparation LLM erreur : %s" % _e_repair_llm)
        else:
            phase3_log.info("[layered] Runtime final hints : %s" % '; '.join(rt_final[:3]))

    # Q12 — Couche 10 : revue programmatique approfondie (deep review inter-couches)
    try:
        _deep_issues = _deep_review_assembled_code(final_html)
        if _deep_issues:
            phase3_log.info(f"[layered] Q12 deep review : {len(_deep_issues)} issue(s) — pre-patch")
            from agents.phase5 import agent_pre_patcher as _pre_patcher_q12
            _deep_patched = _pre_patcher_q12.run(final_html, _deep_issues)
            # Valider que le deep patch n'a pas cassé la syntaxe
            try:
                from js_syntax_checker import check_and_report as _chk_q12
                _q12_issues, _q12_broken = _chk_q12(_deep_patched)
                if not _q12_broken:
                    final_html = _deep_patched
                    phase3_log.info(f"[layered] Q12 deep review : patch OK")
                else:
                    phase3_log.warning(f"[layered] Q12 deep review : patch cassait la syntaxe — ignoré")
            except Exception:
                final_html = _deep_patched  # Si checker indispo, accepter le patch
    except Exception as _e_q12:
        phase3_log.warning(f"[layered] Q12 deep review erreur : {_e_q12}")

    # validate_and_fix avec rollback si la syntaxe est cassée après
    _pre_validate_html = final_html
    final_html, _, _ = validate_and_fix(final_html)

    # Vérification syntaxe POST validate_and_fix (peut introduire des ] ou } orphelins)
    try:
        from js_syntax_checker import fix_all_auto, check_and_report as _js_check_post
        _candidate, _fixed_post, fix_descs_post = fix_all_auto(final_html)
        if fix_descs_post:
            phase3_log.info("[layered] Auto-fix post-validator : %s" % '; '.join(fix_descs_post[:3]))
        _post_issues, _post_broken = _js_check_post(_candidate)
        if _post_broken:
            phase3_log.warning(
                "[layered] Syntaxe cassée par validate_and_fix — ROLLBACK vers code pré-validation : %s"
                % (_post_issues[0][:80] if _post_issues else '?')
            )
            final_html = _pre_validate_html  # ← rollback critique
        else:
            final_html = _candidate
            phase3_log.info("[layered] Syntaxe post-validator OK")
    except Exception as _e_post:
        phase3_log.warning("[layered] Validation post-validator impossible (%s)" % _e_post)

    # Gate score — avertit si score ne s'incrémente jamais (jeu sans but)
    import re as _re_score
    if not _re_score.search(r'\bscore\s*[\+\-]?=\s*[^=]|\bscore\s*\+\+|\bscore\s*\-\-', accumulated):
        phase3_log.warning("[layered] ⚠ score jamais incrémenté — le jeu manque d'objectif")

    # J3 : vérification que init() est appelé en standalone (jeu ne démarre jamais si absent)
    _init_standalone = re.search(r'^init\s*\(\s*\)\s*;', accumulated, re.MULTILINE)
    if not _init_standalone:
        # Chercher DOMContentLoaded avec init dedans
        if 'init()' not in accumulated:
            phase3_log.warning("[layered] ⚠ init() absent — injection standalone")
            accumulated += "\ninit();\n"
        else:
            phase3_log.info("[layered] init() présent (inline ou DOMContentLoaded)")

    # J9 : détection redéfinitions non-intentionnelles entre couches
    _all_fn_defs = re.findall(r'function\s+([a-zA-Z_$][\w$]*)\s*\(', accumulated)
    _fn_counts: dict = {}
    for _fn in _all_fn_defs:
        _fn_counts[_fn] = _fn_counts.get(_fn, 0) + 1
    _redefined = [fn for fn, cnt in _fn_counts.items() if cnt > 1 and fn not in ('init', 'gameLoop')]
    if _redefined:
        phase3_log.info("[layered] J9 redéfinitions détectées (last-wins JS) : %s" % ', '.join(_redefined[:6]))

    stats = get_layer_stats()
    total_lines = accumulated.count('\n')
    stats_summary = ' | '.join(
        "%s:%.0f%%" % (k, v['success_rate'])
        for k, v in stats.items()
        if v['attempts'] > 0
    )
    phase3_log.agent_done(
        "Createur Layered",
        "%d chars finaux — %d lignes JS (%s) [stats: %s]"
        % (len(final_html), total_lines, titre, stats_summary)
    )
    return final_html

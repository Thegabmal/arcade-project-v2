"""
Assembler Agent — Phase 3
Assembles the generated JavaScript modules into a complete standalone HTML file.
Each module is surrounded by markers to allow targeted patching.
Pure algorithm (no LLM call) — deterministic and reliable.
"""

from genre_profile import GeneratedModules, ModuleArchitecture, ConceptionContext
from logger import phase3_log

# Marqueurs de module pour extraction/remplacement ciblé
MODULE_START = "// ═══ MODULE: {nom} ═══"
MODULE_END = "// ═══ END MODULE: {nom} ═══"


def _extract_js_from_module(code: str, is_3d: bool) -> str:
    """
    Strip any HTML wrapper from a module's code, keeping only pure JavaScript.
    LLMs sometimes generate full HTML pages (with <script src="...">game_code</script>)
    instead of raw JS. This causes nested script tags after assembly → exec=2.6.
    """
    import re
    stripped = code.strip()
    # Fast path: if no HTML indicators, return as-is
    if not is_3d:
        return stripped
    if '<script' not in stripped.lower() and '<!doctype' not in stripped.lower():
        return stripped
    # Extract content from inline script blocks (skip src= tags)
    matches = []
    for m in re.finditer(r'<script(?:\s[^>]*)?>(.+?)</script>', stripped, re.DOTALL | re.IGNORECASE):
        open_tag = m.group(0)[:m.group(0).index('>') + 1]
        if re.search(r'\bsrc\s*=', open_tag, re.IGNORECASE):
            continue
        content = m.group(1).strip()
        if len(content) > 50:
            matches.append(content)
    if matches:
        return '\n\n'.join(matches)
    return stripped


def run(
    generated: GeneratedModules,
    context: ConceptionContext,
) -> str:
    """Assemble les modules en un fichier HTML complet."""
    phase3_log.agent_start("Assembleur", f"Assemblage de {len(generated.modules)} modules")

    arch = generated.architecture
    gp = context.genre_profile
    gdd = context.gdd
    tech = context.tech_specs
    est_3d = arch.technologie == "threejs"

    titre = gdd.get("titre", "Arcade Game")
    palette = gp.palette_recommandee or "#1a1a2e"
    bg_color = _extract_first_color(palette) or "#1a1a2e"

    # Construire le JS assemblé dans l'ordre d'exécution
    js_parts = []
    ordre = arch.ordre_execution or arch.module_names()

    # Modules dans l'ordre
    for nom in ordre:
        if nom in generated.modules:
            code = _extract_js_from_module(generated.modules[nom], est_3d)
            js_parts.append(f"{MODULE_START.format(nom=nom)}")
            js_parts.append(code)
            js_parts.append(f"{MODULE_END.format(nom=nom)}")
            js_parts.append("")

    # Modules hors ordre (si oubliés)
    for nom, code in generated.modules.items():
        if nom not in ordre:
            code = _extract_js_from_module(code, est_3d)
            js_parts.append(f"{MODULE_START.format(nom=nom)}")
            js_parts.append(code)
            js_parts.append(f"{MODULE_END.format(nom=nom)}")
            js_parts.append("")

    js_code = "\n".join(js_parts)

    # Déclarer les variables globales
    globals_decl = _build_globals_declaration(arch)

    # Code de démarrage
    startup = arch.startup_code or "init(); requestAnimationFrame(gameLoop);"

    if est_3d:
        js_code = _inject_trycatch_animate_3d(js_code)
        html = _build_3d_html(titre, bg_color, js_code, globals_decl, startup)
        _coherence_check_3d(html)
        _check_startup_functions(html, startup)
    else:
        canvas_w = tech.get("rendu", {}).get("canvas_size", {}).get("width", 800)
        canvas_h = tech.get("rendu", {}).get("canvas_size", {}).get("height", 600)
        html = _build_2d_html(titre, bg_color, canvas_w, canvas_h, js_code, globals_decl, startup)

    phase3_log.agent_done("Assembleur", f"HTML assemblé : {len(html)} chars")
    return html


def _build_globals_declaration(arch: ModuleArchitecture) -> str:
    """Génère les déclarations de variables globales."""
    lines = ["// ═══ VARIABLES GLOBALES ═══"]
    for var in arch.variables_globales:
        init_val = arch.variables_init.get(var, "null")
        lines.append(f"let {var} = {init_val};")
    lines.append("// ═══ END VARIABLES GLOBALES ═══")
    return "\n".join(lines)


def _build_2d_html(
    titre: str,
    bg_color: str,
    canvas_w: int,
    canvas_h: int,
    js_code: str,
    globals_decl: str,
    startup: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{titre}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: {bg_color};
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      overflow: hidden;
    }}
    canvas {{
      display: block;
      max-width: 100%;
      max-height: 100vh;
    }}
  </style>
</head>
<body>
  <canvas id="gameCanvas" width="{canvas_w}" height="{canvas_h}"></canvas>
  <script>
    "use strict";

    {globals_decl}

    {js_code}

    // ═══ STARTUP ═══
    window.addEventListener('load', function() {{
      {startup}
    }});
    // ═══ END STARTUP ═══
  </script>
</body>
</html>"""


_THREEJS_POLYFILL_HTML = """  <script>
// Polyfill: Three.js examples/jsm classes — not in the main bundle
if(typeof THREE!=='undefined'){
  if(!THREE.Capsule){THREE.Capsule=function(s,e,r){this.start=s?s.clone():new THREE.Vector3(0,0,0);this.end=e?e.clone():new THREE.Vector3(0,1,0);this.radius=r!==undefined?r:0.5;this.getCenter=function(t){return t.addVectors(this.start,this.end).multiplyScalar(0.5);};this.translate=function(v){this.start.add(v);this.end.add(v);return this;};this.copy=function(c){this.start.copy(c.start);this.end.copy(c.end);this.radius=c.radius;return this;};this.set=function(a,b,r){this.start.copy(a);this.end.copy(b);this.radius=r;return this;};this.clone=function(){return new THREE.Capsule(this.start,this.end,this.radius);};};};
  if(!THREE.Octree){THREE.Octree=function(){this.fromGraphNode=function(){};this.capsuleIntersect=function(){return false;};this.rayIntersect=function(){return false;};};};
  if(!THREE.OctreeHelper){THREE.OctreeHelper=function(){THREE.Object3D.call(this);};THREE.OctreeHelper.prototype=Object.create(THREE.Object3D.prototype);THREE.OctreeHelper.prototype.update=function(){};};
}
  </script>"""


def _build_3d_html(
    titre: str,
    bg_color: str,
    js_code: str,
    globals_decl: str,
    startup: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{titre}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: {bg_color};
      overflow: hidden;
    }}
    canvas {{
      display: block;
    }}
    #hud {{
      position: fixed;
      top: 20px;
      left: 20px;
      color: white;
      font-family: Arial, sans-serif;
      font-size: 20px;
      pointer-events: none;
      z-index: 10;
    }}
    #overlay {{
      position: fixed;
      top: 0; left: 0;
      width: 100%; height: 100%;
      background: rgba(0,0,0,0.85);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      color: white;
      font-family: Arial, sans-serif;
      z-index: 100;
    }}
    #overlay h1 {{ font-size: 3em; margin-bottom: 20px; }}
    #overlay p {{ font-size: 1.2em; margin-bottom: 10px; opacity: 0.8; }}
    #overlay button {{
      margin-top: 20px;
      padding: 15px 40px;
      font-size: 1.2em;
      background: #4444ff;
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
    }}
    #overlay button:hover {{ background: #6666ff; }}
  </style>
</head>
<body>
  <div id="hud"></div>
  <div id="overlay">
    <h1>{titre}</h1>
    <p>Appuie sur DÉMARRER pour jouer</p>
    <button onclick="startGame()">DÉMARRER</button>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
{_THREEJS_POLYFILL_HTML}
  <script>
    // ═══ NOTE: pas de "use strict" — les modules partagent des globaux cross-script ═══

    {globals_decl}

    {js_code}

    // ═══ STARTUP ═══
    window.addEventListener('load', function() {{
      // Pre-initialize UI module before core setup to avoid undefined DOM refs
      if (typeof ui !== 'undefined' && typeof ui.initUI === 'function') {{ ui.initUI(); }}
      // Bridge: expose core.init / core.gameLoop as globals in case startup_code uses plain init()
      if (typeof init === 'undefined' && typeof core !== 'undefined') {{
        if (typeof core.init === 'function') window.init = function() {{ return core.init(); }};
        if (typeof core.gameLoop === 'function') window.gameLoop = function(ts) {{ return core.gameLoop(ts); }};
      }}
      {startup}
      // Ensure startGame() is defined — generated code may use core.setState() instead
      if (typeof startGame !== 'function') {{
        window.startGame = function() {{
          var _ovl = document.getElementById('overlay');
          if (_ovl) _ovl.style.display = 'none';
          if (typeof core !== 'undefined' && typeof core.setState === 'function') {{ core.setState('PLAYING'); }}
          else if (typeof setState === 'function') {{ setState('PLAYING'); }}
        }};
      }}
    }});
    // ═══ END STARTUP ═══
  </script>
</body>
</html>"""


def _inject_trycatch_animate_3d(js_code: str) -> str:
    """
    Wrappe le body de la fonction animate/gameLoop Three.js dans un try/catch.
    Affiche l'erreur dans le HUD au lieu de freezer silencieusement.
    Si la fonction n'est pas trouvée, retourne le code inchangé.
    """
    import re
    # Cherche : function animate() { ... } ou function gameLoop() { ... }
    pattern = r'(function\s+(?:animate|gameLoop)\s*\([^)]*\)\s*\{)'
    match = re.search(pattern, js_code)
    if not match:
        return js_code
    insert_pos = match.end()
    trycatch_open = (
        "\n  try {"
    )
    # Trouver la fermeture de la fonction pour insérer } catch
    # Approche simple : trouver le requestAnimationFrame final et insérer après
    raf_pattern = r'requestAnimationFrame\s*\(\s*(?:animate|gameLoop)\s*\)'
    raf_matches = list(re.finditer(raf_pattern, js_code[insert_pos:]))
    if not raf_matches:
        return js_code
    last_raf = raf_matches[-1]
    raf_end = insert_pos + last_raf.end()
    trycatch_close = (
        "\n  } catch(e) {"
        "\n    var hud = document.getElementById('hud');"
        "\n    if (hud) hud.innerHTML = '<span style=\"color:#f55;font-size:12px\">ERR: ' + e.message + '</span>';"
        "\n    window.__ARCADE_ERROR__ = e.message + (e.stack ? ' | ' + e.stack.split('\\n').slice(1,3).join(' ') : '');"
        "\n    console.error('3D game error:', e.message, e.stack);"
        "\n  }"
    )
    return js_code[:insert_pos] + trycatch_open + js_code[insert_pos:raf_end] + trycatch_close + js_code[raf_end:]


def _check_startup_functions(html: str, startup: str) -> None:
    """
    Vérifie que les fonctions appelées dans startup_code existent dans le HTML assemblé.
    Log un warning pour chaque fonction manquante.
    """
    import re
    calls = re.findall(r'\b([a-zA-Z_]\w*)\s*\(', startup)
    # Filtre les mots-clés JS et les patterns connus non-fonctions
    skip = {'if', 'for', 'while', 'function', 'return', 'requestAnimationFrame', 'setTimeout', 'setInterval'}
    for fn in calls:
        if fn in skip:
            continue
        pattern_fn = rf'\bfunction\s+{re.escape(fn)}\s*\('
        pattern_arrow = rf'\b{re.escape(fn)}\s*=\s*(?:function|\()'
        if not re.search(pattern_fn, html) and not re.search(pattern_arrow, html):
            phase3_log.warning(f"  ⚠ startup_code appelle '{fn}()' mais cette fonction n'existe pas dans les modules")


def _coherence_check_3d(html: str) -> None:
    """
    Vérifie la cohérence du HTML 3D assemblé.
    Log des warnings si des éléments Three.js critiques sont manquants.
    Ne lève pas d'exception — le jeu est quand même retourné.
    """
    import re
    checks = [
        ("THREE.WebGLRenderer",     "renderer non créé — écran noir garanti"),
        ("THREE.Scene",             "scene non créée"),
        ("THREE.PerspectiveCamera", "caméra perspective absente"),
        ("THREE.Clock",             "clock absente — delta time impossible"),
        ("renderer.render",         "render() non appelé — rien ne s'affiche"),
        ("requestAnimationFrame",   "boucle de jeu absente"),
        ("DOMContentLoaded",        "DOMContentLoaded absent — init peut être trop tôt"),
    ]
    issues = []
    for keyword, msg in checks:
        if keyword not in html:
            issues.append(msg)

    if issues:
        phase3_log.warning(f"  ⚠ Cohérence 3D : {len(issues)} problème(s) détectés")
        for issue in issues:
            phase3_log.warning(f"    - {issue}")
    else:
        phase3_log.info("  ✓ Cohérence 3D : tous les éléments Three.js critiques présents")


def _extract_first_color(palette: str) -> str:
    """Extrait la première couleur hexadécimale d'une palette."""
    import re
    match = re.search(r'#[0-9a-fA-F]{6}', palette)
    return match.group(0) if match else "#1a1a2e"


# ─────────────────────────────────────────────
# Utilitaires d'extraction / remplacement
# (utilisés par agent_patcher en mode modulaire)
# ─────────────────────────────────────────────

def extract_module(html: str, nom: str) -> str | None:
    """Extrait le code JS d'un module depuis le HTML assemblé."""
    import re
    start_marker = re.escape(MODULE_START.format(nom=nom))
    end_marker = re.escape(MODULE_END.format(nom=nom))
    pattern = rf"{start_marker}\n(.*?)\n{end_marker}"
    match = re.search(pattern, html, re.DOTALL)
    return match.group(1).strip() if match else None


def replace_module(html: str, nom: str, new_code: str) -> str:
    """Remplace le code d'un module dans le HTML assemblé."""
    import re
    start_marker = re.escape(MODULE_START.format(nom=nom))
    end_marker = re.escape(MODULE_END.format(nom=nom))
    pattern = rf"({start_marker}\n).*?(\n{end_marker})"
    replacement = rf"\g<1>{new_code}\g<2>"
    new_html = re.sub(pattern, replacement, html, flags=re.DOTALL)
    if new_html == html:
        # Module non trouvé — injecter avant END STARTUP
        injection = f"\n{MODULE_START.format(nom=nom)}\n{new_code}\n{MODULE_END.format(nom=nom)}\n"
        new_html = html.replace("// ═══ STARTUP ═══", injection + "// ═══ STARTUP ═══")
    return new_html


def list_modules(html: str) -> list:
    """Liste les noms des modules présents dans le HTML."""
    import re
    pattern = r"// ═══ MODULE: (.+?) ═══"
    return re.findall(pattern, html)

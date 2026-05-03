"""
Patcher Agent — Phase 5
Fixes the game code based on the Diagnostician's diagnosis.
Does NOT rewrite the entire game — makes targeted surgical corrections.
Preserves what is working well.
"""

import json
from config import call_gemini_paid, with_fallback
from genre_profile import GenreProfile
from logger import phase5_log

SYSTEM = """Tu es un développeur senior en débogage de jeux HTML5 (Canvas 2D et Three.js). Tu fais des corrections chirurgicales.

RÈGLES UNIVERSELLES :
- Tu ne réécrits JAMAIS tout le jeu — tu patches uniquement ce qui est cassé
- Pour vider un tableau : arr.length = 0 (JAMAIS arr.clear())
- Tout objet utilisé DOIT être déclaré dans le code avant son premier appel
- Noms d'inputs cohérents : remplace TOUS les noms incohérents dans le fichier entier
- Tout accès DOM dans DOMContentLoaded ou window.onload — jamais au top-level
- JAMAIS location.reload() pour restart — réinitialise les variables en JS pur
- JAMAIS data:URI — utilise des couleurs et formes géométriques

⛔ SYNTAXE JS INTERDITE — ces patterns dans ton patch causeront SyntaxError :
  A. const dans switch/case sans {} → utilise var ou { const x=...; break; }
  B. for(const i=0; i<n; i++) → TOUJOURS for(let i=0; ...)
  C. const pour variable réassignée → TOUJOURS let
  D. const/let après if sans accolades → if(ok) { const x=5; }
  → Vérifie que ton patch est syntaxiquement valide avant de le retourner.

RÈGLE CRITIQUE — DÉCLARATIONS DE VARIABLES :
- NE SUPPRIME JAMAIS une déclaration (var/let/const/function) qui existait dans l'original
- Si tu vois "DÉCLARATIONS EXISTANTES" dans le prompt, TOUTES ces variables doivent rester déclarées dans ton output
- Une variable utilisée DOIT être déclarée dans le même fichier — si elle manque, ajoute sa déclaration

RÈGLE dt — "dt is not defined" est causé par un dt local dans gameLoop :
- ❌ INTERDIT dans gameLoop : const dt = ...; ou let dt = ...;
- ✅ OBLIGATOIRE : dt doit être une variable GLOBALE (var dt = 0; avant DOMContentLoaded)
  et gameLoop doit faire dt = Math.min(...) sans const/let pour METTRE À JOUR le global
- Si tu vois "dt is not defined", ajoute var dt = 0; en scope global et corrige gameLoop

BUGS FRÉQUENTS — EXEMPLES AVANT/APRÈS (applique exactement ces patterns) :

▸ BUG 1 — BOUCLE SANS INIT LOCALE → ReferenceError garanti :
  ❌ for (let i = 0; i < enemies.length; i++) { enemy.vx *= 0.9; if (enemy.hp<=0) enemies.splice(i,1); }
  ✅ for (let i = enemies.length-1; i >= 0; i--) { const enemy = enemies[i]; enemy.vx *= 0.9; if (enemy.hp<=0) enemies.splice(i,1); }
  Règle : const varLocale = tableau[i]; OBLIGATOIRE ligne 1 du corps. Boucle inversée si splice().

▸ BUG 2 — dt NON PASSÉ EN PARAMÈTRE → valeurs NaN partout :
  ❌ function updateBullets() { for (const b of bullets) { b.x += b.vx * dt; } }
     update(dt) { updateBullets(); }
  ✅ function updateBullets(dt) { for (const b of bullets) { b.x += b.vx * dt; } }
     update(dt) { updateBullets(dt); }
  Règle : si le corps utilise dt → dt dans les params ET dans l'appel.

▸ BUG 3 — JSON.parse MANQUANT → TypeError: cannot read property of string :
  ❌ function loadGame() { const data = localStorage.getItem('save'); if (data.score) score = data.score; }
  ✅ function loadGame() { const raw = localStorage.getItem('save'); const data = JSON.parse(raw || 'null'); if (!data) return; score = data.score || 0; }

▸ BUG 4 — VARIABLE INTERMÉDIAIRE NON DÉCLARÉE → ReferenceError :
  ❌ for (const en of enemies) { if (dist < 100) closest = en; } if (closest) attack(closest);
  ✅ let closest = null; let minDist = Infinity;
     for (const en of enemies) { const dx=en.x-player.x, dy=en.y-player.y; const dist=Math.hypot(dx,dy); if (dist<minDist) { minDist=dist; closest=en; } }
     if (closest) attack(closest);
  Règle : let closest=null, let angle=0, let hit=false → DÉCLARER avec let AVANT la boucle/if.

▸ BUG 5 — EVENT LISTENERS HORS DOMContentLoaded → canvas=null → crash immédiat :
  ❌ canvas.addEventListener('mousemove', e => { mouse.x=e.clientX; });
     document.addEventListener('DOMContentLoaded', () => { const canvas = ...; });
  ✅ document.addEventListener('DOMContentLoaded', () => {
       const canvas = document.getElementById('gameCanvas');
       canvas.addEventListener('mousemove', e => { mouse.x=e.clientX; });  // DANS le callback
     });
  Règle clavier : document.addEventListener('keydown') peut être PARTOUT (pas besoin de canvas).
  Règle souris/clic : canvas.addEventListener() DOIT être dans DOMContentLoaded.

▸ BUG 6 — FOR-OF + SPLICE → éléments sautés / tableau corrompu silencieusement :
  ❌ for (const enemy of enemies) { ... enemies.splice(idx, 1); }
  ✅ for (let i = enemies.length - 1; i >= 0; i--) { const enemy = enemies[i]; ... enemies.splice(i, 1); }
  Règle : for-of ne permet JAMAIS de splice le tableau qu'il itère. Toujours boucle inversée + const X = arr[i].

▸ BUG 7 — CONST REASSIGNMENT → TypeError: Assignment to constant variable (crash silencieux) :
  ❌ const score = 0; ... score += 10;      // TypeError crash
     const lives = 3; ... lives--;          // TypeError crash
     const player = null; ... player = {};  // TypeError crash
  ✅ let score = 0; let lives = 3; let player = null;  // let pour tout game state mutable
  Règle : SCREAMING_CASE (PALETTE, TILE_SIZE, MAX_ENEMIES) et tableaux sans réassignation → const.
          Tout scalaire mutable, state, HP, compteur → let.

RÈGLES CANVAS 2D :
- draw() : ctx.fillStyle=BG; ctx.fillRect(0,0,W,H) DOIT être la toute première opération (avant save/translate)
- Null guard : if (!player) return; au début de draw() si player peut être null
- Particles : spawnParticles(x,y,color,count) → push({x,y,vx,vy,life:1,size,color}) + updateParticles(dt) + drawParticles()

RÈGLES THREE.JS 3D :
- JAMAIS THREE.* hors du DOMContentLoaded
- renderer : document.body.appendChild(renderer.domElement) — OBLIGATOIRE
- Lumières : scene.add(new THREE.AmbientLight(0xffffff,0.6)); scene.add(new THREE.DirectionalLight(0xffffff,0.8));
- Suppression : scene.remove(entity.mesh) AVANT entities.splice(i,1)
- HUD : divs HTML (getElementById + textContent), jamais canvas 2D par-dessus Three.js

Tu produis UNIQUEMENT le code HTML corrigé complet, sans explication ni backticks."""


def _get_model_snippet_for_missing(genre: str, sous_genre: str, missing_musts: list[str]) -> str:
    """
    For each missing genre must-have, extract a ~500-char reference snippet from
    the matching model game file.  Returns a formatted block or '' if nothing found.
    """
    import re as _re, os as _os

    g = (genre + " " + (sous_genre or "")).lower()

    GENRE_FILE = [
        (["shmup", "shoot", "vaisseau", "spatial", "space", "galaga"], "shoot_em_up.html"),
        (["platformer", "plateforme", "jump", "mario"], "platformer.html"),
        (["rpg", "aventure", "dungeon", "roguelite", "rogue"], "rpg_narratif.html"),
        (["puzzle", "match3", "match-3"], "puzzle_match3.html"),
        (["runner", "endless"], "endless_runner.html"),
        (["arcade", "breakout", "brique"], "breakout.html"),
        (["tower defense", "tower_defense", "defense"], "tower_defense.html"),
        (["visual novel", "visual_novel", "vn"], "visual_novel.html"),
        (["dungeon_crawler", "crawler"], "dungeon_crawler.html"),
    ]

    filename = None
    for keywords, fname in GENRE_FILE:
        if any(k in g for k in keywords):
            filename = fname
            break
    if not filename:
        return ""

    _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    model_path = _os.path.join(_root, "jeux_modeles", filename)
    try:
        with open(model_path, "r", encoding="utf-8") as f:
            html = f.read()
    except (IOError, OSError):
        return ""

    m = _re.search(r'<script[^>]*>(.*?)</script>', html, _re.DOTALL | _re.IGNORECASE)
    if not m:
        return ""
    js = m.group(1)

    # Criterion keyword → anchor strings to search for in the model game
    CRITERION_ANCHORS = [
        ("PHASE",      ["bossPhase", "boss.phase", "phase === 2", "phase >= 2"]),
        ("POWER",      ["PU_DEFS", "powerUp", "powerups", "spawnPowerup"]),
        ("VAGUE",      ["WAVE_DEFS", "updateWave", "waveActive"]),
        ("ENNEMI",     ["ENEMY_DEFS", "ENEMY_TYPES", "createEnemy"]),
        ("COMBO",      ["combo", "comboTimer", "comboMult"]),
        ("XP",         ["checkLevelUp", "addXP", "gainXP", "xp +="]),
        ("LEVEL",      ["LEVEL_DEFS", "LEVELS =", "currentLevel"]),
        ("UPGRADE",    ["upgradeTower", "tower.level", "TOWER_TYPES"]),
        ("GOLD",       ["addGold", "gold +=", "gainGold"]),
        ("CASCADE",    ["applyGravity", "cascade", "dropTiles"]),
        ("MATCH",      ["checkMatch", "findMatch"]),
        ("CHOICE",     ["showChoiceDialog", "choices :"]),
        ("FLAG",       ["setFlag", "flags["]),
        ("COYOTE",     ["coyoteTime", "COYOTE_TIME", "jumpBuffer"]),
        ("OBSTACLE",   ["OBSTACLE_TYPES", "spawnObstacle"]),
        ("SPEED",      ["SPEED_RAMP", "gameSpeed", "speed *="]),
        ("BOSS",       ["spawnBoss", "bossActive", "drawBoss"]),
    ]

    blocks = []
    for must in missing_musts[:3]:  # max 3 snippets to keep prompt size reasonable
        must_upper = must.upper()
        anchors = next(
            (anch for kw, anch in CRITERION_ANCHORS if kw in must_upper),
            None
        )
        if not anchors:
            continue
        for anchor in anchors:
            idx = js.find(anchor)
            if idx != -1:
                # Find the start of the line
                line_start = js.rfind('\n', 0, idx) + 1
                # Extract ~500 chars from that line
                snippet = js[line_start:line_start + 500].strip()
                last_nl = snippet.rfind('\n')
                if last_nl > 350:
                    snippet = snippet[:last_nl]
                if snippet:
                    blocks.append(f"-- Reference for '{must}' (from {filename}) --\n{snippet}")
                break

    if not blocks:
        return ""
    return "\n\nREFERENCE IMPLEMENTATIONS — mirror these patterns in the game:\n" + "\n\n".join(blocks) + "\n"


def run(code: str, diagnostic: dict, genre_profile: GenreProfile, iteration: int) -> str:
    phase5_log.agent_start("Patcher", f"Application des corrections (itération {iteration})")

    corrections = diagnostic.get("corrections_prioritaires", [])
    a_preserver = diagnostic.get("a_absolument_preserver", [])
    instructions = diagnostic.get("instructions_patcher", "")

    corrections_str = json.dumps(corrections[:5], ensure_ascii=False)
    preserver_str = json.dumps(a_preserver, ensure_ascii=False)

    # Jeux complexes ou longs : augmenter la limite de tokens
    genres_complexes = {"fps", "shooter", "rpg", "simulation", "strategy"}
    is_complexe = (
        "THREE." in code or "three.min.js" in code
        or any(g in (genre_profile.genre_principal or "").lower() for g in genres_complexes)
        or len(code) > 20000
    )
    max_tokens = 48000 if is_complexe else 32000

    # Si le script est trop grand pour être réécrit entièrement en un seul appel,
    # utiliser un patch ciblé sur un snippet autour du bug (comme le pre-patcher)
    # IMPORTANT : max_tokens est en tokens, le script est en chars. ~3 chars/token en moyenne.
    # On réserve ~30% pour le prompt système + instructions → budget script = max_tokens * 3 * 0.7
    script_content = _extract_script(code)
    MAX_PATCH_CHARS = int(max_tokens * 2.5)  # ex: 48000 tokens → ~120000 chars max pour le script
    # Pour les jeux complexes, le full-rewrite perd souvent des déclarations.
    # Multi-snippet dès 50k chars sur un genre complexe (RPG/FPS/etc.).
    script_trop_grand = script_content and (
        len(script_content) > MAX_PATCH_CHARS
        or (is_complexe and len(script_content) > 50000)
    )

    if script_trop_grand:
        # Mode multi-snippet : patch indépendant par issue, ~200 lignes chacun
        reason = (f"Script trop grand ({len(script_content)} chars > {MAX_PATCH_CHARS})"
                  if script_content and len(script_content) > MAX_PATCH_CHARS
                  else f"Jeu complexe ({genre_profile.genre_principal}, {len(script_content)} chars)")
        phase5_log.warning(f"{reason} — patch multi-snippet par issue")
        return _run_multi_snippet_patch(code, script_content, diagnostic, genre_profile, iteration)

    code_pour_patch = script_content if script_content and len(script_content) > 500 else code
    est_script_only = script_content and len(script_content) > 500 and code_pour_patch != code

    if est_script_only:
        format_instructions = "Génère UNIQUEMENT le contenu JavaScript corrigé (sans balises <script>). Commence directement par le code JS."
        format_sortie = "Retourne uniquement le JavaScript corrigé, sans balises HTML."
        # Inclure la liste des déclarations pour éviter que le LLM en perde
        decls = _extract_declarations(script_content)
        decls_context = f"\nDÉCLARATIONS EXISTANTES (à ABSOLUMENT conserver dans l'output) :\n{', '.join(decls)}\n" if decls else ""
    else:
        format_instructions = "Génère le code HTML corrigé complet. Commence par <!DOCTYPE html> et termine par </html>."
        format_sortie = "Ne mets AUCUN texte avant ou après le code."
        decls_context = ""

    # Inject model game snippets for any missing genre must-haves
    try:
        from agents.phase5.agent_diagnosticien import _detect_missing_genre_musts
        _missing = _detect_missing_genre_musts(
            code_pour_patch, genre_profile.genre_principal, genre_profile.sous_genre or ""
        )
        _reference_snippets = _get_model_snippet_for_missing(
            genre_profile.genre_principal, genre_profile.sous_genre or "", _missing
        ) if _missing else ""
    except Exception:
        _reference_snippets = ""

    prompt = f"""Corrige ce code de jeu HTML5 ({genre_profile.genre_principal}).
{decls_context}

PROBLÈME PRINCIPAL : {diagnostic.get('probleme_principal', '')}

CORRECTIONS À APPORTER (par ordre de priorité) :
{corrections_str}

ÉLÉMENTS À ABSOLUMENT PRÉSERVER (ne pas modifier) :
{preserver_str}

INSTRUCTIONS GÉNÉRALES :
{instructions}
{_reference_snippets}
RÈGLES IMPORTANTES :
1. Ne réécris PAS tout le jeu — fais des corrections ciblées
2. Préserve TOUT ce qui est dans "à absolument préserver"
3. Si un système fonctionne bien, ne le touche pas
4. Applique les corrections dans l'ordre de priorité
5. Chaque correction doit améliorer concrètement un aspect du jeu
6. Ne réduis pas les fonctionnalités existantes
7. Si une correction est trop risquée, saute-la et passe à la suivante

CODE À CORRIGER :
```
{code_pour_patch}
```

{format_instructions}
{format_sortie}"""

    raw_patch = _call(prompt, max_tokens)
    if not raw_patch:
        phase5_log.warning("Patcher — réponse vide, conservation du code original")
        return code
    raw_patch = _clean_html(raw_patch)

    # Si on a patché seulement le script, réinjecter dans le HTML original
    if est_script_only and raw_patch and not raw_patch.strip().startswith("<!DOCTYPE"):
        # Vérifier que les déclarations importantes sont préservées avant injection
        if script_content:
            missing = _check_missing_declarations(script_content, raw_patch)
            if missing:
                phase5_log.warning(f"Patch perd {len(missing)} déclaration(s) ({', '.join(missing[:5])}) — conservation du code original")
                return code
        new_code = _inject_script(code, raw_patch)
    else:
        new_code = raw_patch

    # Post-patch cleanup: remove duplicate declarations and functions
    if new_code != code:
        from agents.phase5.agent_pre_patcher import _dedup_declarations, _dedup_functions, _fix_gameloop_scope
        import re
        # Extract and clean the main script
        script_match = re.search(r'(<script(?:\s[^>]*)?>)(.+?)(</script>)', new_code, re.DOTALL | re.IGNORECASE)
        if script_match:
            prefix_h = new_code[:script_match.start(2)]
            cleaned = script_match.group(2)
            suffix_h = new_code[script_match.end(2):]
            cleaned, n1 = _dedup_declarations(cleaned, keep_last=True)
            cleaned, n2 = _dedup_functions(cleaned)
            cleaned, fixed = _fix_gameloop_scope(cleaned)
            if n1 or n2 or fixed:
                phase5_log.info(f"Post-patch cleanup: {n1} décl. + {n2} fn. dupliquées supprimées" + (" + gameLoop scope fixé" if fixed else ""))
                new_code = prefix_h + cleaned + suffix_h

    # Vérification de base : le code ne doit pas être vide ou tronqué
    if len(new_code) < len(code) * 0.5:
        phase5_log.warning("Code patché trop court — conservation du code original")
        return code

    if not new_code.strip().startswith("<!DOCTYPE") and not new_code.strip().startswith("<html"):
        phase5_log.warning("Code patché invalide — conservation du code original")
        return code

    # E3 : validation syntaxe post-patch avant retour
    try:
        from js_syntax_checker import check_and_report as _js_check
        _patch_issues, _patch_broken = _js_check(new_code)
        if _patch_broken:
            phase5_log.warning(f"E3 : syntaxe cassée après patch ({_patch_issues[0][:80] if _patch_issues else '?'}) — rollback")
            return code
        else:
            phase5_log.info("E3 : syntaxe post-patch OK")
    except Exception as _e3:
        phase5_log.warning(f"E3 : validation post-patch impossible ({_e3}) — accepté par défaut")

    diff_size = len(new_code) - len(code)
    phase5_log.agent_done(
        "Patcher",
        f"Code corrigé : {len(new_code)} chars (delta: {'+' if diff_size > 0 else ''}{diff_size})"
    )
    return new_code


def _extract_declarations(script: str) -> list[str]:
    """Extrait tous les noms de variables/fonctions déclarés au top-level du script."""
    import re
    names = set()
    # var/let/const (peut y avoir plusieurs déclarations sur une ligne)
    for m in re.finditer(r'\b(?:var|let|const)\s+(\w+)', script):
        names.add(m.group(1))
    # function declarations
    for m in re.finditer(r'\bfunction\s+(\w+)\s*\(', script):
        names.add(m.group(1))
    # class declarations
    for m in re.finditer(r'\bclass\s+(\w+)', script):
        names.add(m.group(1))
    return sorted(names)


def _check_missing_declarations(original: str, patched: str) -> list[str]:
    """
    Retourne la liste des identifiants déclarés dans l'original mais
    utilisés dans le patch sans être re-déclarés.
    """
    import re
    original_decls = set(_extract_declarations(original))
    patched_decls = set(_extract_declarations(patched))
    # Identifiants présents dans l'original, absents du patch mais utilisés dans le patch
    missing = []
    for name in original_decls - patched_decls:
        # Vérifier que le nom est effectivement utilisé dans le patch (pas juste un artefact)
        if re.search(r'\b' + re.escape(name) + r'\b', patched):
            missing.append(name)
    return missing


def _extract_script(html: str) -> str | None:
    """Extrait le contenu du dernier bloc <script> (le code du jeu)."""
    import re
    matches = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
    # Prendre le plus long bloc script (= le code du jeu, pas les petits scripts CDN)
    if not matches:
        return None
    biggest = max(matches, key=len)
    return biggest.strip() if len(biggest.strip()) > 200 else None


def _inject_script(html: str, new_script: str) -> str:
    """Remplace le contenu du plus grand bloc <script> par new_script."""
    import re
    # Trouver tous les blocs script avec leur position
    pattern = re.compile(r'(<script(?:\s[^>]*)?>)(.+?)(</script>)', re.DOTALL | re.IGNORECASE)
    matches = list(pattern.finditer(html))
    if not matches:
        return html
    # Remplacer le plus long
    target = max(matches, key=lambda m: len(m.group(2)))
    return html[:target.start(2)] + "\n" + new_script + "\n" + html[target.end(2):]


def _clean_html(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)
    return code.strip()


@with_fallback(None)  # None = on rendra le code original
def _call(prompt: str, max_tokens: int = 16000) -> str:
    return call_gemini_paid(prompt, temperature=0.2, system_instruction=SYSTEM,
                            max_tokens=max_tokens, disable_thinking=True)


# ─────────────────────────────────────────────
# PATCH MULTI-SNIPPET (une issue = un snippet)
# ─────────────────────────────────────────────

_STOP_WORDS = {"function", "const", "let", "var", "return", "this", "true",
               "false", "null", "undefined", "typeof",
               # Mots français courants dans les diagnostics — pas des identifiants JS
               "critique", "erreur", "variable", "declaration", "probleme",
               "syntaxe", "appel", "code", "jeu", "script", "dans", "par",
               "avec", "pour", "depuis", "lors", "mais", "aussi", "non",
               "pas", "les", "des", "une", "qui", "que", "sans", "plus",
               "sont", "lors", "tout", "bien", "peut", "doit", "sera",
               "Correction", "Erreur", "Probleme", "Variables", "Tableau"}


def _find_keyword(correction: dict | str, probleme: str, script: str) -> str | None:
    """Trouve le mot-clé JS le plus pertinent pour localiser le snippet à patcher."""
    import re as _re

    issue_code = correction.get("code_a_modifier", "") if isinstance(correction, dict) else ""
    issue_desc = correction.get("description", "") if isinstance(correction, dict) else str(correction)

    def _is_safe_keyword(ident: str) -> bool:
        """Rejette les identifiants dangereux pour le snippet LLM."""
        if ident in _STOP_WORDS:
            return False
        # Bloquer les constantes ALL_CAPS (BOSS_DEFS, WAVE_DEFS, ENEMY_DEFS…)
        # → le LLM corrompt les tableaux de données qui les entourent
        if ident.replace('_', '').isupper() and len(ident) > 3:
            return False
        # Bloquer les noms de fonctions gameLoop/update/draw — trop larges, trop risqués
        if ident.lower() in {'gameloop', 'update', 'draw', 'init', 'reset', 'start'}:
            return False
        return ident in script

    # Priorité 1 : code_a_modifier exact
    if issue_code:
        candidate = issue_code.strip()
        if candidate and _is_safe_keyword(candidate):
            return candidate

    # Priorité 2 : identifiants JS dans la description de la correction
    for ident in _re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b', issue_desc):
        if _is_safe_keyword(ident):
            return ident

    # Priorité 3 : identifiants JS dans le problème principal
    for ident in _re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b', probleme):
        if _is_safe_keyword(ident):
            return ident

    return None


def _extract_snippet(script: str, keyword: str) -> tuple[str, int, int]:
    """Extrait ~200 lignes autour du keyword, en respectant les template literals."""
    lines = script.split("\n")
    half = 125 if len(lines) > 400 else 100
    target_line = next((i for i, ln in enumerate(lines) if keyword in ln), 0)
    start_line = max(0, target_line - half)
    end_line = min(len(lines), target_line + half)

    # Reculer start_line si on coupe au milieu d'un template literal
    pre_backticks = "\n".join(lines[:start_line]).count('`')
    if pre_backticks % 2 == 1:
        for sl in range(start_line - 1, max(0, start_line - 30), -1):
            if '`' in lines[sl]:
                start_line = sl
                if "\n".join(lines[:start_line]).count('`') % 2 == 0:
                    break

    return "\n".join(lines[start_line:end_line]), start_line, end_line


def _patch_single_issue(code: str, script: str, correction: dict | str,
                        probleme: str, genre_profile: GenreProfile) -> str:
    """
    Patch ciblé sur ~200 lignes autour d'une seule issue.
    Retourne le code patché, ou le code original si le patch échoue/régresse.
    """
    keyword = _find_keyword(correction, probleme, script)
    if not keyword:
        return code

    snippet, start_line, end_line = _extract_snippet(script, keyword)
    issue_desc = correction.get("description", "") if isinstance(correction, dict) else str(correction)
    correction_str = json.dumps(correction, ensure_ascii=False)

    snippet_lines = snippet.count('\n') + 1
    prompt = f"""Corrige ce snippet JavaScript (extrait d'un jeu {genre_profile.genre_principal}).

PROBLÈME : {issue_desc}

CORRECTION :
{correction_str}

⚠️ RÈGLE ABSOLUE : Tu DOIS retourner les {snippet_lines} lignes COMPLÈTES du snippet ci-dessous,
avec ta correction intégrée. NE retourne PAS uniquement les lignes modifiées — retourne TOUT
le snippet du début à la fin, même les lignes non touchées. Si tu ne retournes que le diff,
le code sera corrompu.

SNIPPET COMPLET À CORRIGER ET RETOURNER (lignes {start_line}–{end_line}) :
{snippet}

Retourne uniquement le JavaScript corrigé (les {snippet_lines} lignes complètes)."""

    fixed_snippet = _call(prompt, max(8000, snippet_lines * 60))
    if not fixed_snippet:
        phase5_log.info(f"    → snippet vide, ignoré")
        return code

    fixed_snippet = _clean_html(fixed_snippet)
    fixed_lines = fixed_snippet.count('\n') + 1

    # Cas 1 : snippet complet retourné (≥ 50% des lignes originales) → injection directe
    # Cas 2 : correction chirurgicale (LLM n'a retourné que les lignes changées) →
    #          chercher dans le snippet original où ce bloc s'insère et patcher uniquement cette zone
    lines = script.split("\n")
    if fixed_lines >= snippet_lines * 0.5:
        # Injection normale : remplace la fenêtre start_line..end_line
        new_script = "\n".join(lines[:start_line]) + "\n" + fixed_snippet + "\n" + "\n".join(lines[end_line:])
    else:
        # Injection chirurgicale : le LLM a retourné seulement les lignes modifiées
        # On tente de repérer dans le snippet les fonctions touchées et de les remplacer
        phase5_log.info(f"    → correction courte ({fixed_lines} lignes vs {snippet_lines}) — injection chirurgicale")
        import re as _re
        fn_names = _re.findall(r'\bfunction\s+(\w+)', fixed_snippet)
        if fn_names:
            patched_script = "\n".join(lines)
            for fn_name in fn_names:
                # Trouver la fonction dans le script original et la remplacer
                fn_pattern = _re.compile(
                    r'(function\s+' + _re.escape(fn_name) + r'\s*\([^)]*\)\s*\{)',
                )
                fn_match = fn_pattern.search(patched_script)
                if not fn_match:
                    continue
                fn_start = fn_match.start()
                # Trouver la fermeture de la fonction en comptant les accolades
                depth, i = 0, fn_start
                while i < len(patched_script):
                    if patched_script[i] == '{':
                        depth += 1
                    elif patched_script[i] == '}':
                        depth -= 1
                        if depth == 0:
                            fn_end = i + 1
                            break
                    i += 1
                else:
                    continue
                # Trouver la version corrigée de cette fonction dans fixed_snippet
                fn_fixed_match = fn_pattern.search(fixed_snippet)
                if not fn_fixed_match:
                    continue
                fn_fixed_start = fn_fixed_match.start()
                depth2, j = 0, fn_fixed_start
                while j < len(fixed_snippet):
                    if fixed_snippet[j] == '{':
                        depth2 += 1
                    elif fixed_snippet[j] == '}':
                        depth2 -= 1
                        if depth2 == 0:
                            fn_fixed_end = j + 1
                            break
                    j += 1
                else:
                    continue
                fixed_fn = fixed_snippet[fn_fixed_start:fn_fixed_end]
                patched_script = patched_script[:fn_start] + fixed_fn + patched_script[fn_end:]
            new_script = patched_script
        else:
            # Pas de fonction identifiable → injection directe dans la fenêtre quand même
            new_script = "\n".join(lines[:start_line]) + "\n" + fixed_snippet + "\n" + "\n".join(lines[end_line:])

    # Vérification taille globale (>75% de l'original)
    new_code_pre = _inject_script(code, new_script)
    if len(new_code_pre) < len(code) * 0.75:
        phase5_log.warning(f"    → code résultant trop court ({len(new_code_pre)} < {int(len(code)*0.75)}) — ignoré")
        return code

    # Déduplication post-snippet
    try:
        from agents.phase5.agent_pre_patcher import _dedup_declarations
        new_script, dedup_n = _dedup_declarations(new_script)
        if dedup_n:
            phase5_log.info(f"    → {dedup_n} redéclaration(s) supprimée(s)")
    except ImportError:
        pass

    return _inject_script(code, new_script)


def _run_multi_snippet_patch(code: str, script: str, diagnostic: dict,
                             genre_profile: GenreProfile, iteration: int) -> str:
    """
    Patch par issue : chaque correction est appliquée indépendamment sur son propre snippet.
    Quelle que soit la taille du script, chaque appel LLM ne traite que ~200 lignes.
    Les patches sont appliqués séquentiellement : si l'un échoue ou casse la syntaxe, il est ignoré.
    """
    corrections = diagnostic.get("corrections_prioritaires", [])
    probleme = diagnostic.get("probleme_principal", "")

    if not corrections:
        phase5_log.warning("Patcher multi-snippet — aucune correction à appliquer")
        return code

    try:
        from js_syntax_checker import check_and_report as js_syntax_check
        has_syntax_checker = True
    except ImportError:
        has_syntax_checker = False

    # Guard anti-régression exec : score de référence avant patches
    try:
        from agents.phase4 import agent_executeur as _exec_agent
        baseline_exec = _exec_agent.run(code, genre_profile).score
        has_exec_guard = True
        phase5_log.info(f"  [exec guard] score baseline = {baseline_exec:.1f}")
    except Exception:
        has_exec_guard = False
        baseline_exec = 0.0

    current_code = code
    patches_applied = 0
    patches_skipped = 0
    consecutive_syntax_failures = 0  # Session 6 — circuit breaker
    max_issues = min(len(corrections), 5)

    for i, correction in enumerate(corrections[:max_issues]):
        issue_desc = (correction.get("description", "") if isinstance(correction, dict) else str(correction))[:80]
        phase5_log.info(f"  [Issue {i+1}/{max_issues}] {issue_desc}")

        # Extraire le script courant (mis à jour après chaque patch accepté)
        current_script = _extract_script(current_code)
        if not current_script:
            break

        patched = _patch_single_issue(current_code, current_script, correction, probleme, genre_profile)

        if patched == current_code:
            phase5_log.info(f"    → aucun changement")
            patches_skipped += 1
            consecutive_syntax_failures = 0
            continue

        # Vérifier la syntaxe après le patch
        if has_syntax_checker:
            _, broken = js_syntax_check(patched)
            if broken:
                consecutive_syntax_failures += 1
                phase5_log.warning(
                    f"    → patch brise la syntaxe — ignoré "
                    f"({consecutive_syntax_failures} échec(s) consécutif(s))"
                )
                patches_skipped += 1
                if consecutive_syntax_failures >= 2:
                    phase5_log.warning(
                        "  [circuit breaker] 2 patches syntaxiquement invalides consécutifs "
                        "— arrêt anticipé du patcher (code inchangé vaut mieux que code dégradé)"
                    )
                    break
                continue
        consecutive_syntax_failures = 0  # reset sur succès syntaxique

        # Guard anti-régression exec : rejeter si le score exec descend > 0.5 pts
        patched_exec = None
        if has_exec_guard:
            try:
                patched_exec = _exec_agent.run(patched, genre_profile).score
                if patched_exec < baseline_exec - 0.5:
                    phase5_log.warning(
                        f"    → patch régresse exec {baseline_exec:.1f}→{patched_exec:.1f} — ignoré"
                    )
                    patches_skipped += 1
                    continue
                phase5_log.info(f"    → exec OK ({patched_exec:.1f})")
            except Exception:
                patched_exec = None  # guard indisponible → on accepte le patch quand même

        current_code = patched
        patches_applied += 1
        phase5_log.info(f"    → patch appliqué ✓")

        # Stocker le patch validé dans la patch_bank pour réutilisation future
        try:
            import sys as _sys, os as _os, difflib as _diff
            _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))))
            from patch_bank import store_patch as _store_patch
            exec_delta = (patched_exec - baseline_exec) if patched_exec is not None else 0.0
            # Extraire uniquement le bloc modifié (lignes - et + du diff unifié)
            old_lines = current_script.splitlines()
            new_script = _extract_script(patched) or ""
            new_lines = new_script.splitlines()
            removed, added = [], []
            for line in _diff.unified_diff(old_lines, new_lines, lineterm="", n=0):
                if line.startswith("-") and not line.startswith("---"):
                    removed.append(line[1:])
                elif line.startswith("+") and not line.startswith("+++"):
                    added.append(line[1:])
            if removed and added and len(removed) <= 20:
                _store_patch(
                    issue_desc=issue_desc,
                    search="\n".join(removed),
                    replace="\n".join(added),
                    genre=genre_profile.genre_principal,
                    exec_delta=exec_delta,
                )
        except Exception:
            pass  # patch_bank indisponible → pas bloquant

    if patches_applied == 0:
        phase5_log.warning("Patcher multi-snippet — aucun patch valide, conservation")
        return code

    delta = len(current_code) - len(code)
    phase5_log.agent_done(
        "Patcher",
        f"Multi-snippet : {patches_applied}/{max_issues} issue(s) corrigée(s) "
        f"(delta: {'+' if delta >= 0 else ''}{delta} chars)"
    )
    return current_code


# ─────────────────────────────────────────────
# PATCH MODULAIRE
# ─────────────────────────────────────────────

SYSTEM_MODULE_PATCH = """Tu es un développeur expert en jeux HTML5. Tu corriges un module JavaScript
spécifique d'un jeu. Tu ne modifies QUE ce module, sans toucher les autres.
Tu produis UNIQUEMENT le code JavaScript corrigé du module, sans balises HTML, sans explication,
sans backticks."""


def run_module_patch(html: str, module_nom: str, diagnostic: dict, genre_profile: GenreProfile, iteration: int) -> str:
    """
    Patche un seul module dans le HTML assemblé.
    Extrait le module, le corrige, le réinjecte.
    """
    from agents.phase3.agent_assembleur import extract_module, replace_module

    phase5_log.agent_start("Patcher Modulaire", f"Patch du module '{module_nom}' (itération {iteration})")

    # Extraire le code du module
    module_code = extract_module(html, module_nom)
    if not module_code:
        phase5_log.warning(f"Module '{module_nom}' introuvable dans le HTML — patch complet")
        return run(html, diagnostic, genre_profile, iteration)

    # Filtrer les corrections pour ce module
    corrections_module = [
        c for c in diagnostic.get("corrections_prioritaires", [])
        if c.get("module_concerne") == module_nom or not c.get("module_concerne")
    ][:3]

    corrections_str = json.dumps(corrections_module, ensure_ascii=False)

    prompt = f"""Corrige ce module JavaScript "{module_nom}" pour le jeu {genre_profile.genre_principal}.

PROBLÈME PRINCIPAL : {diagnostic.get('probleme_principal', '')}

CORRECTIONS À APPORTER :
{corrections_str}

INSTRUCTIONS :
{diagnostic.get('instructions_patcher', '')}

CODE ACTUEL DU MODULE "{module_nom}" :
{module_code}

Génère le code JavaScript corrigé du module. Ne génère QUE le code JS, sans balises HTML."""

    new_module_code = _call_module_patch(prompt)

    if not new_module_code or len(new_module_code) < len(module_code) * 0.4:
        phase5_log.warning(f"Patch module '{module_nom}' invalide — conservation")
        return html

    new_html = replace_module(html, module_nom, new_module_code)
    delta = len(new_html) - len(html)
    phase5_log.agent_done(
        "Patcher Modulaire",
        f"Module '{module_nom}' patché (delta: {'+' if delta >= 0 else ''}{delta} chars)"
    )
    return new_html


@with_fallback(None)
def _call_module_patch(prompt: str) -> str:
    return call_gemini_paid(prompt, temperature=0.2, system_instruction=SYSTEM_MODULE_PATCH,
                            max_tokens=16000, disable_thinking=True)

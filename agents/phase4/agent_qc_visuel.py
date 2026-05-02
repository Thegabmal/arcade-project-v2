"""
Visual QC Agent — Phase 4
Evaluates the visual and artistic quality of the game by reading the code.
Criteria adapt to the expected visual style for the genre.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, EvaluationResult
from logger import phase4_log

SYSTEM_2D = """Tu es un artiste et directeur artistique spécialisé dans les jeux HTML5 Canvas 2D.
Tu évalues la qualité visuelle d'un jeu en analysant son code de rendu Canvas.
Tu réponds UNIQUEMENT en JSON valide."""

SYSTEM_3D = """Tu es un artiste et directeur artistique spécialisé dans les jeux 3D web avec Three.js.
Tu évalues la qualité visuelle d'un jeu Three.js en analysant son code : géométries, matériaux,
éclairage, caméra, effets, HUD HTML overlay. Tu réponds UNIQUEMENT en JSON valide."""

CRITERES_VISUELS_2D = """RUBRIQUE DE SCORE VISUEL :
- 0-3 : Écran noir ou quasi-vide, aucun effort visuel
- 4-5 : Formes basiques, couleurs plates, aucun effet (pas de particules, pas de glow)
- 6   : Correct — fond visible, éléments distincts, HUD lisible, quelques couleurs cohérentes
- 7   : Bon — palette cohérente, animations présentes, fond avec détails, HUD complet
- 8   : Très bon — effets de juice (shake, particules, glow), transitions soignées, style cohérent
- 9   : Excellent — direction artistique affirmée, polish visible sur tous les éléments, très beau

Critères BLOQUANTS (score ≤ 4 si absent) :
- Canvas non vide : ctx.clearRect + appels draw réels → sinon écran noir
- Fond dessiné avec une couleur distincte de #000 (fond noir = pénalité -2pts)
- Joueur visuellement distinct des ennemis (couleur ET forme différentes si possible)
- HUD lisible : score + vies/HP affichés via ctx.fillText avec couleur contrastée

Critères QUALITÉ (impact direct sur le score) :
- Cohérence palette : 5-8 couleurs harmonieuses dans tout le jeu (pas de mélange aléatoire)
- Animations ennemis : les ennemis ont un visuel distinct par TYPE (pas juste un cercle identique recolorisé)
- Effets de juice — évaluer chacun individuellement :
  • Screen shake : ctx.translate avec shakeX/shakeY → feedback d'impact
  • Particules : tableau particles[] avec updateParticles() et drawParticles() → explosions, mort
  • Floating texts : spawnFloatText() → score flottant, "CRIT!", "x2 COMBO!"
  • Flash overlay : overlay rouge/blanc alpha sur damage ou événement important
  • Glow / shadowBlur : effets lumineux sur joueur, boss, projectiles
- Fond riche : éléments de background (étoiles, grille, nuages, tuiles) — pas canvas uni
- Boss visuellement distinctif : plus grand, couleur unique, barre HP dédiée, aura/glow
- Écrans de menu et game over soignés : titre stylisé, sous-titre, instructions, best score
- Transitions fluides : fade ou animation entre états (menu → jeu → gameover)
- Police adaptée au genre : ctx.font taille ≥ 16px, police cohérente avec le style visuel"""

CRITERES_VISUELS_PIXEL_ART = """⚠️ MODE PIXEL ART DÉTECTÉ — critères adaptés (NE PAS pénaliser l'absence d'effets CSS modernes).

Critères BLOQUANTS (score 0 si absent) :
- Canvas basse résolution scalée : off-canvas (160×144 ou 256×240) + ctx.drawImage(off, 0, 0, W*SCALE, H*SCALE)
- imageSmoothingEnabled = false OBLIGATOIRE (sinon pixels flous = raté)
- Fond non-noir : tuiles de sol dessinées (au moins une couleur de fond autre que #000)
- Joueur visible avec sprite ou forme distincte

Critères QUALITÉ pixel art (impact score) :
- PALETTE COHÉRENTE : 8-16 couleurs max issues d'une palette NES/GB réelle (ex: #70C848, #D82800, #3CBCFC, #F8B800)
  → NE PAS pénaliser une palette "simple" si elle est cohérente et NES-authentique
- SPRITES par tableaux fillRect 1×1 : présence de tableaux 2D (const HERO_SPRITE = [[...],...]) → bonne pratique pixel art
- TILEMAP : tableau 2D map[][] + fonction drawTile() → monde structuré
- ANIMATION frames : frameIndex + frameTick → sprites animés (walk/idle)
- HUD pixel art : cœurs dessinés en fillRect (pas texte "HP:"), barres colorées
- BOÎTE DE DIALOGUE : bordure pixel art (double bord fillRect) + typewriter effect
- FLOATING TEXT : spawnFloatingText() pour dégâts et collectibles
- FADE TRANSITION : fadeOut/fadeIn entre zones (pas de coupure sèche)
- CAMÉRA SCROLLING : cam.x/cam.y pour monde plus grand qu'un écran

⚠️ RÈGLES D'ÉVALUATION PIXEL ART :
- Un jeu pixel art avec palette cohérente NES + sprites array + tilemap MÉRITE 7+ même sans effets modernes
- NE PAS pénaliser : absence de dégradés CSS, absence de shadowBlur, formes simples (c'est voulu)
- PÉNALISER : pixels flous (imageSmoothingEnabled manquant), couleurs aléatoires non-palette, sprites statiques dans un jeu d'action, monde d'un seul écran sans scrolling"""

CRITERES_VISUELS_3D = """Critères BLOQUANTS (score 0 si absent) :
- Au moins 1 lumière (AmbientLight ou DirectionalLight) → sinon tout noir
- WebGLRenderer.setClearColor() défini → sinon fond transparent ou noir par défaut
- Joueur/avatar visible et distinct des ennemis (couleur ou géométrie différente)
- HUD HTML (div overlay) avec score visible

Critères QUALITÉ (impact score) :
- Variété géométries : au moins 3 types différents (BoxGeometry, SphereGeometry, CylinderGeometry...)
- Matériaux appropriés : MeshStandardMaterial ou MeshPhongMaterial (pas MeshBasicMaterial partout)
- Éclairage multicouche : AmbientLight (0.4-0.6 intensity) + DirectionalLight ou PointLight
- Caméra adaptée au genre : FOV correct (60-90°), position cohérente avec le gameplay
- Fluidité animations 3D : lerp/slerp pour transitions douces (pas de téléportation brusque)
- Effets 3D : particules (Points ou sprites), trails, ou explosions procédurales
- Fond cohérent : setClearColor avec couleur d'ambiance ou skybox
- Lisibilité 3D : joueur, ennemis, obstacles clairement différenciés"""


_KW_PIXEL = ["pixel", "rétro", "retro", "zelda", "pokemon", "nes", "game boy",
             "gameboy", "8-bit", "16-bit", "8bit", "16bit"]


def _extract_palette(code: str) -> list[str]:
    """F5 : Extraction automatique de la palette de couleurs via regex hex/rgb."""
    import re
    # Hex couleurs (#RGB ou #RRGGBB)
    hex_colors = re.findall(r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b', code)
    # rgb/rgba
    rgb_colors = re.findall(r'rgba?\([^)]+\)', code)
    # hsl/hsla
    hsl_colors = re.findall(r'hsla?\([^)]+\)', code)
    all_colors = list(dict.fromkeys(hex_colors[:15] + rgb_colors[:5] + hsl_colors[:5]))
    return all_colors[:20]  # max 20 couleurs


def run(code: str, genre_profile: GenreProfile) -> EvaluationResult:
    est_3d = genre_profile.technologie_rendu == "threejs"
    style_lower = (genre_profile.style_visuel or "").lower()
    est_pixel = any(kw in style_lower for kw in _KW_PIXEL)
    phase4_log.agent_start("QC Visuel", f"Style attendu: {genre_profile.style_visuel} ({'3D' if est_3d else ('pixel art' if est_pixel else '2D')})")

    criteres = genre_profile.criteres_qc_visuel
    criteres_str = json.dumps(criteres, ensure_ascii=False) if criteres else ""
    if est_3d:
        criteres_universels = CRITERES_VISUELS_3D
    elif est_pixel:
        criteres_universels = CRITERES_VISUELS_PIXEL_ART
    else:
        criteres_universels = CRITERES_VISUELS_2D
    system = SYSTEM_3D if est_3d else SYSTEM_2D
    techno_label = "Three.js (3D)" if est_3d else "Canvas 2D"

    from utils import extract_js_sample
    code_extrait = extract_js_sample(code, 20000)

    # F5 : Extraction automatique de la palette de couleurs
    _palette_detected = _extract_palette(code)
    _palette_hint = ""
    if _palette_detected:
        _palette_hint = f"\nPALETTE DÉTECTÉE AUTOMATIQUEMENT : {', '.join(_palette_detected[:12])}\n"

    prompt = f"""Analyse la qualité visuelle de ce jeu HTML5 {techno_label} en cherchant des preuves CONCRÈTES dans le code.

CODE :
```html
{code_extrait}
```

ATTENTES VISUELLES :
- Style visuel demandé : {genre_profile.style_visuel}
- Palette recommandée : {genre_profile.palette_recommandee}
{_palette_hint}
- Animations clés attendues : {json.dumps(genre_profile.animations_cles, ensure_ascii=False)}
- Effets importants attendus : {json.dumps(genre_profile.effets_importants, ensure_ascii=False)}
- Genre : {genre_profile.genre_principal} / {genre_profile.sous_genre}
- Ton : {genre_profile.ton}

CRITÈRES VISUELS SPÉCIFIQUES AU GENRE :
{criteres_str}

CRITÈRES VISUELS {techno_label.upper()} :
{criteres_universels}

INSTRUCTIONS D'ÉVALUATION :
- Cherche les preuves dans le CODE (ex: "ctx.fillRect" trouvé, "screen_shake" trouvé)
- Ne donne PAS de score élevé si le critère est absent du code
- Un jeu avec écran noir (pas de ctx.clearRect ou pas de fond) = score ≤ 4.0
- Sois honnête : un score moyen sur le visuel = 5-6, bon = 7-8, excellent = 9-10

Réponds en JSON :
{{
  "criteres_evalues": [
    {{
      "nom": "...",
      "score_obtenu": 1.5,
      "score_max": 2.0,
      "commentaire": "..."
    }}
  ],
  "effets_trouves": ["effets visuels présents dans le code", "..."],
  "effets_manquants": ["effets attendus mais absents", "..."],
  "issues": [
    {{
      "severite": "critique / majeur / mineur",
      "description": "...",
      "suggestion": "..."
    }}
  ],
  "points_forts": ["...", "..."],
  "score_total": 7.0,
  "commentaire_global": "..."
}}"""

    result = _call(prompt, system)
    ev = _parse(result, "QC Visuel")

    # Checks programmatiques — plafonnent le score LLM si réalité du code dit autre chose
    ev = _apply_visual_code_checks(code, ev)
    return ev


def _parse(result: dict, agent_name: str) -> EvaluationResult:
    ev = EvaluationResult(agent_name=agent_name)
    ev.criteres = result.get("criteres_evalues", [])
    ev.issues = result.get("issues", [])
    ev.points_forts = result.get("points_forts", [])
    ev.score = float(result.get("score_total", 5.0))
    ev.commentaire_global = result.get("commentaire_global", "")
    ev.score = max(0.0, min(10.0, ev.score))

    phase4_log.score("QC Visuel", ev.score)
    return ev


def _apply_visual_code_checks(code: str, ev: EvaluationResult) -> EvaluationResult:
    """
    Checks programmatiques sur le code source — pénalités ET bonus.
    Le LLM peut être trop généreux ou trop sévère — le code ne ment pas.
    """
    import re
    penalties = []
    bonuses = []

    # ── PÉNALITÉS ──────────────────────────────────────────────────────────────

    # 1. Fond noir : pas de couleur de fond définie autre que noir/transparent
    has_bg_color = bool(re.search(
        r'fillStyle\s*=\s*[\'"](?!(?:#000(?:000)?|black|rgb\(0,\s*0,\s*0\))[\'"])',
        code, re.IGNORECASE
    ))
    has_clearrect = 'clearRect' in code
    if not has_bg_color and not has_clearrect:
        penalties.append(("fond potentiellement noir — aucun fillStyle de fond non-noir détecté", 2.0))
    elif not has_bg_color and has_clearrect:
        penalties.append(("fond effacé mais sans couleur de fond définie → fond noir probable", 1.0))

    # 2. Palette trop réduite
    hex_colors = set(re.findall(r'#[0-9A-Fa-f]{3,6}\b', code))
    rgba_colors = set(re.findall(r'rgba?\([^)]+\)', code))
    total_colors = len(hex_colors) + len(rgba_colors)
    if total_colors < 4:
        penalties.append((f"palette très réduite ({total_colors} couleur(s)) — visuel pauvre", 2.0))
    elif total_colors < 8:
        penalties.append((f"palette limitée ({total_colors} couleurs) — manque de richesse visuelle", 0.8))

    # 3. HUD absent
    has_hud = bool(re.search(
        r'drawHUD|fillText.*(?:score|Score|vie|HP|hp|wave|Wave|combo|Combo)',
        code, re.IGNORECASE
    ))
    if not has_hud:
        penalties.append(("aucun HUD détecté — score/vies non affichés", 1.5))

    # 4. requestAnimationFrame absent
    if 'requestAnimationFrame' not in code:
        penalties.append(("requestAnimationFrame absent — pas d'animation", 2.0))

    # 5. Aucune fonction draw* → le jeu ne dessine rien
    draw_fn_count = len(re.findall(r'function\s+draw\w+\s*\(', code))
    if draw_fn_count < 2:
        penalties.append((f"très peu de fonctions draw* ({draw_fn_count}) — rendu probablement minimal", 1.5))

    # ── BONUS (effets de juice — valident que le LLM n'a pas surestimé) ────────

    # Screen shake
    has_shake = bool(re.search(r'shakeX|shakeY|shakeMag|shakeTimer|triggerShake', code))
    if has_shake:
        bonuses.append(("screen shake implémenté", 0.5))

    # Particules
    has_particles = bool(re.search(r'particles\s*=\s*\[\]|spawnExplosion|spawnParticle|drawParticles', code))
    if has_particles:
        bonuses.append(("système de particules présent", 0.5))

    # Floating texts
    has_float = bool(re.search(r'floatTexts|spawnFloatText|floatingText', code))
    if has_float:
        bonuses.append(("floating score texts présents", 0.3))

    # Glow / shadowBlur
    has_glow = 'shadowBlur' in code and 'shadowColor' in code
    if has_glow:
        bonuses.append(("effets glow (shadowBlur/shadowColor) présents", 0.3))

    # globalAlpha (transparence / fade)
    has_alpha = 'globalAlpha' in code
    if has_alpha:
        bonuses.append(("effets de transparence (globalAlpha) présents", 0.2))

    # Appliquer pénalités
    total_penalty = sum(p for _, p in penalties)
    if total_penalty > 0:
        old_score = ev.score
        ev.score = max(1.0, ev.score - total_penalty)
        for desc, pen in penalties:
            ev.issues.append({
                "severite": "critique" if pen >= 1.5 else "majeur",
                "description": f"[VISUEL-CHECK] {desc} (−{pen:.1f} pts)",
                "suggestion": "Ajouter fond coloré, palette ≥ 8 couleurs hex, fonctions draw* complètes, HUD"
            })
        phase4_log.warning(
            f"QC Visuel pénalités : {old_score:.1f} → {ev.score:.1f} ({len(penalties)} pénalité(s))"
        )

    # Appliquer bonus (plafonné à +2.0 total et score max 9.5)
    total_bonus = min(2.0, sum(b for _, b in bonuses))
    if total_bonus > 0:
        old_score = ev.score
        ev.score = min(9.5, ev.score + total_bonus)
        juice_list = ", ".join(desc for desc, _ in bonuses)
        ev.points_forts.append(f"Effets de juice détectés : {juice_list}")
        phase4_log.info(f"QC Visuel bonus juice : {old_score:.1f} → {ev.score:.1f} ({juice_list})")

    if total_penalty > 0 or total_bonus > 0:
        phase4_log.score("QC Visuel (ajusté)", ev.score)

    return ev


@with_fallback({
    "criteres_evalues": [], "issues": [], "points_forts": [],
    "score_total": 5.0, "commentaire_global": "Analyse indisponible",
    "effets_trouves": [], "effets_manquants": []
})
def _call(prompt: str, system: str = SYSTEM_2D) -> dict:
    return call_gemini_json(prompt, temperature=0.3, system_instruction=system)

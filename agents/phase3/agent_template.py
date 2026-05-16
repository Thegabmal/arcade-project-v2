"""
Template Agent — Phase 2.5
Selects the appropriate HTML5 game template based on the detected genre.
Returns the complete template content so run_from_template() can use it as
the mandatory LLM foundation — the LLM fills [FILL] sections rather than
generating the entire engine from scratch.
"""

import os
from genre_profile import GenreProfile
from logger import phase3_log

_TEMPLATES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'game_templates', 'genres')
)

# Ordered most-specific → most-generic; first match wins.
# Keywords are checked against: genre_principal + sous_genre + first 200 chars of prompt_enrichi.
_GENRE_TO_FILE = [
    # Visual novel — before RPG (RPG keywords appear in VN descriptions too)
    (['visual novel', 'visual_novel', 'roman visuel', 'dating sim', 'kinetic novel', 'rencontres'], 'visual_novel.html'),
    # Roguelite — before dungeon/RPG
    (['roguelite', 'roguelike', 'rogue-lite', 'rogue lite', 'rogue-like', 'rogue like'], 'roguelite.html'),
    # Dungeon crawler — before generic RPG
    (['dungeon crawler', 'dungeon_crawler', 'hack and slash', 'hack-and-slash', 'action rpg', 'arpg'], 'dungeon_crawler.html'),
    # RPG narrative
    (['rpg narrative', 'rpg_narrative', 'jrpg', 'role playing', 'role-playing', 'rpg'], 'rpg_narrative.html'),
    # Shoot-em-up
    (['shoot em up', 'shoot-em-up', 'shmup', 'bullet hell', 'space shooter', 'shoot them up',
      'shoot\'em up', 'vaisseau spatial', 'galaga', 'space invaders'], 'shooter_2d.html'),
    # Tower defense
    (['tower defense', 'tower_defense', 'tower defence', 'défense de tour', 'defense de base',
      'tourelles', 'td game', 'plants vs'], 'tower_defense.html'),
    # Match-3 / Puzzle-match
    (['match 3', 'match-3', 'match3', 'puzzle match', 'bejeweled', 'candy crush', 'gem match',
      'three in a row', 'trois en ligne'], 'puzzle_match3.html'),
    # Breakout / Arkanoid
    (['breakout', 'arkanoid', 'brick breaker', 'casse-briques', 'casse briques',
      'brique', 'paddle ball', 'raquette balle'], 'breakout.html'),
    # Endless runner
    (['endless runner', 'endless_runner', 'auto runner', 'infinite runner',
      'auto-runner', 'runner infini', 'défilement automatique'], 'endless_runner.html'),
    # Platformer
    (['platformer', 'platform game', 'plateforme', 'side scroller', 'side-scroller',
      'mario', 'jump and run', 'metroidvania'], 'platformer_2d.html'),
    # Generic fallbacks (broad terms, matched after all specifics)
    (['puzzle', 'réflexion', 'reflexion', 'casse-tête', 'logic game', 'combinaison'], 'puzzle_match3.html'),
    (['dungeon', 'donjon', 'crawler', 'labyrinthe combat'], 'dungeon_crawler.html'),
    (['rogue', 'procédural', 'procedural', 'permadeath'], 'roguelite.html'),
    (['runner', 'course infinie'], 'endless_runner.html'),
    (['shoot', 'shooter', 'tir', 'bullet', 'vaisseau'], 'shooter_2d.html'),
    (['platform', 'saut', 'jump', 'plateforme'], 'platformer_2d.html'),
]


def select_template(genre_profile: GenreProfile) -> tuple:
    """
    Returns (template_filename, template_content) or (None, None) if no match.
    """
    genre = (genre_profile.genre_principal or '').lower().strip()
    sous_genre = (genre_profile.sous_genre or '').lower().strip()
    prompt_snippet = (genre_profile.prompt_enrichi or '').lower()[:200]

    search_text = f"{genre} {sous_genre} {prompt_snippet}"

    for keywords, filename in _GENRE_TO_FILE:
        if any(kw in search_text for kw in keywords):
            path = os.path.join(_TEMPLATES_DIR, filename)
            if not os.path.exists(path):
                phase3_log.warning(f"[template] File missing: {path}")
                continue
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            fill_count = content.count('[FILL')
            phase3_log.info(
                f"[template] '{filename}' selected for genre='{genre}/{sous_genre}' "
                f"({len(content)} chars, {fill_count} [FILL] sections)"
            )
            return filename, content

    phase3_log.info(
        f"[template] No match for genre='{genre}' sous_genre='{sous_genre}' — layered generation used"
    )
    return None, None


# ─── 3D template mapping ──────────────────────────────────────────────────────
# Ordered most-specific → most-generic; matched against genre + sous_genre + prompt.
_GENRE_TO_3D_FILE = [
    # FPS & zombie survival (pointer lock)
    (['fps', 'first person', 'first-person', 'zombie survival', 'zombie fps',
      'horde survival', 'zombie horde', 'dead compound', 'iron compound'], 'fps_shooter_3d.html'),
    # Racing & circuit
    (['racing', 'race game', 'circuit', 'kart', 'car race', 'drift', 'formula',
      'track racing', 'apex circuit'], 'racing_3d.html'),
    # Space & flight shooters (mouse aim, no floor)
    (['space shooter', 'space_shooter', 'nebula', 'flight shooter', 'flight_shooter',
      'dogfight', 'aerial combat', 'iron skies', 'nebula breach'], 'space_shooter_3d.html'),
    # Tower defense 3D (fixed isometric camera + raycasting)
    (['tower defense 3d', 'tower_defense_3d', 'isometric tower', 'last bastion',
      'defense isometric'], 'tower_defense_3d.html'),
    # 3D platformer & collectathon (TPS follow-cam)
    (['3d platformer', 'platformer 3d', 'platform 3d', 'tps platformer',
      'skyrift', '3d platform', 'collect gems 3d'], 'platformer_3d.html'),
    # Generic 3D fallbacks
    (['3d', 'three.js', 'threejs', '3d game', 'three js'], 'fps_shooter_3d.html'),
]


def select_3d_template(genre_profile: GenreProfile) -> tuple:
    """
    Returns (template_filename, template_content) for a 3D game, or (None, None).
    Called before the modular Three.js pipeline as a faster, more reliable alternative.
    """
    genre = (genre_profile.genre_principal or '').lower().strip()
    sous_genre = (genre_profile.sous_genre or '').lower().strip()
    prompt_snippet = (genre_profile.prompt_enrichi or genre_profile.prompt_utilisateur_original or '').lower()[:300]

    search_text = f"{genre} {sous_genre} {prompt_snippet}"

    for keywords, filename in _GENRE_TO_3D_FILE:
        if any(kw in search_text for kw in keywords):
            path = os.path.join(_TEMPLATES_DIR, filename)
            if not os.path.exists(path):
                phase3_log.warning(f"[template3d] File missing: {path}")
                continue
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            fill_count = content.count('[FILL')
            phase3_log.info(
                f"[template3d] '{filename}' selected for genre='{genre}/{sous_genre}' "
                f"({len(content)} chars, {fill_count} [FILL] sections)"
            )
            return filename, content

    phase3_log.info(
        f"[template3d] No 3D template match for genre='{genre}' sous_genre='{sous_genre}'"
    )
    return None, None


def run(genre_profile: GenreProfile) -> tuple:
    """Public interface for 2D templates. Returns (template_filename, template_content) or (None, None)."""
    try:
        return select_template(genre_profile)
    except Exception as e:
        phase3_log.warning(f"[template] Selection error: {e}")
        return None, None


def run_3d(genre_profile: GenreProfile) -> tuple:
    """Public interface for 3D templates. Returns (template_filename, template_content) or (None, None)."""
    try:
        return select_3d_template(genre_profile)
    except Exception as e:
        phase3_log.warning(f"[template3d] Selection error: {e}")
        return None, None

"""
Seed RAG with jeux_modeles/ reference games.
These are hand-crafted reference games with known quality — inject directly
into game_patterns + code_snippets without needing metadata JSON files.

Usage:
    python seed_rag_models.py           # Seed all 10 model games
    python seed_rag_models.py --dry-run # Preview without writing
"""

import os
import re
import sys
import argparse

MODELS_DIR = "jeux_modeles"

# Hand-curated metadata for each model game
GAME_META = {
    "shoot_em_up.html": {
        "genre": "shmup",
        "sous_genre": "vertical_shmup",
        "titre": "Shoot Em Up - Modèle",
        "description": "Shoot 'em up vertical, bullet hell, vagues ennemis, boss fights, power-ups tir",
        "mecaniques": ["bullet_pattern", "vague_ennemis", "boss_fight", "power_up_tir", "bombes", "lives"],
        "style_visuel": "espace néon, effets explosions, étoiles défilantes",
        "boucle_core": "esquiver balles, tirer ennemis, collecter power-ups, boss final par niveau",
        "score": 8.6,
        "notes": "[modele_reference] Jeu modèle vertical shmup — bullet patterns variés, boss multi-phases",
    },
    "platformer.html": {
        "genre": "platformer",
        "sous_genre": "2d_platformer",
        "titre": "Platformer - Modèle",
        "description": "Platformer 2D avec double saut, wall slide, coyote time, ennemis, collectibles",
        "mecaniques": ["double_jump", "wall_slide", "coyote_time", "ennemi_patrol", "collectibles", "level_progression"],
        "style_visuel": "coloré pixel art, plateformes variées",
        "boucle_core": "sauter courir, éviter ennemis, collecter pièces, atteindre sortie par niveau",
        "score": 8.6,
        "notes": "[modele_reference] Jeu modèle platformer — coyote time, wall slide, game feel soigné",
    },
    "rpg_narratif.html": {
        "genre": "rpg",
        "sous_genre": "jrpg_narratif",
        "titre": "RPG Narratif - Modèle",
        "description": "RPG narratif JRPG avec combat ATB, dialogue narratif, inventaire, XP/niveaux",
        "mecaniques": ["combat_atb", "dialogue_narratif", "inventaire", "experience_niveaux", "magie", "quetes"],
        "style_visuel": "pixel art RPG classique, portraits personnages",
        "boucle_core": "exploration, dialogues à choix, combat ATB tour-par-tour, progression RPG",
        "score": 8.5,
        "notes": "[modele_reference] Jeu modèle RPG narratif — ATB, arbres dialogue, montée en niveau",
    },
    "puzzle_match3.html": {
        "genre": "puzzle",
        "sous_genre": "match3",
        "titre": "Puzzle Match-3 - Modèle",
        "description": "Match-3 avec 5 types de gemmes, combos en cascade, multiplicateurs de score, objectifs par niveau",
        "mecaniques": ["gem_swap", "cascade_combo", "5_gem_types", "score_multiplier", "level_objectives", "hint_system"],
        "style_visuel": "gemmes colorées néon, effets particules cascade",
        "boucle_core": "aligner 3+ gemmes en swappant, déclencher cascades, remplir objectifs avant fin de moves",
        "score": 8.9,
        "notes": "[modele_reference] Jeu modèle match3 — cascade physics, combos, objectifs par niveau",
    },
    "endless_runner.html": {
        "genre": "runner",
        "sous_genre": "endless_runner",
        "titre": "Endless Runner - Modèle",
        "description": "Runner infini cyberpunk avec coyote time, parallaxe 3 couches, 6 types d'obstacles, power-ups",
        "mecaniques": ["coyote_time", "parallax_3layer", "6_obstacle_types", "power_ups", "speed_ramp", "coin_magnet"],
        "style_visuel": "cyberpunk néon, parallaxe 3 couches vitesses différentes",
        "boucle_core": "courir automatiquement, sauter obstacles, collecter pièces, vitesse accélère progressivement",
        "score": 8.8,
        "notes": "[modele_reference] Jeu modèle runner — coyote time 0.1s, parallaxe ×0.12/0.30/0.62, 6 obstacles",
    },
    "breakout.html": {
        "genre": "arcade",
        "sous_genre": "breakout_casse_briques",
        "titre": "Breakout - Modèle",
        "description": "Casse-briques avec système HP briques, 5 niveaux, 6 power-ups, briques explosives, collisions SAT",
        "mecaniques": ["sat_collision", "brick_hp_system", "explosive_bricks", "power_ups_6", "laser_beams", "5_levels"],
        "style_visuel": "néon sombre, 5 types de briques colorées avec glow",
        "boucle_core": "contrôler raquette, faire rebondir balle, casser briques HP, collecter power-ups, finir 5 niveaux",
        "score": 8.7,
        "notes": "[modele_reference] Jeu modèle breakout — SAT collision, briques HP 1-3, explosives, 6 power-ups",
    },
    "tower_defense.html": {
        "genre": "tower_defense",
        "sous_genre": "grid_tower_defense",
        "titre": "Tower Defense - Modèle",
        "description": "Tower defense grille 20×14, 6 types de tours, 10 vagues, système upgrade niveau 2, synergie Ice+Cannon",
        "mecaniques": ["6_tower_types", "10_waves", "upgrade_level2", "ice_cannon_synergy", "gold_interest_5pct", "waypoints_path"],
        "style_visuel": "grille top-down, chemins colorés, tours avec portée visible",
        "boucle_core": "placer tours sur grille, défendre chemin waypoints, améliorer tours, survivre 10 vagues croissantes",
        "score": 8.7,
        "notes": "[modele_reference] Jeu modèle tower defense — synergie Ice+Cannon, intérêt or 5%, upgrade niveau 2",
    },
    "visual_novel.html": {
        "genre": "visual_novel",
        "sous_genre": "sci_fi_vn_choix",
        "titre": "Visual Novel - Modèle",
        "description": "Visual novel sci-fi avec arbre de dialogue, 3 personnages canvas, 3 fins alternatives selon score de choix",
        "mecaniques": ["branching_dialogue", "3_characters_canvas", "3_endings", "choice_score", "typewriter", "history_panel"],
        "style_visuel": "sci-fi, portraits géométriques dessinés sur canvas, décors procéduraux",
        "boucle_core": "lire dialogue typewriter, faire choix narratifs, accumuler score choix, débloquer une des 3 fins",
        "score": 8.5,
        "notes": "[modele_reference] Jeu modèle VN — portraits canvas géométriques, flags narratifs, 3 fins",
    },
    "dungeon_crawler.html": {
        "genre": "rpg",
        "sous_genre": "dungeon_crawler_action",
        "titre": "Dungeon Crawler - Modèle",
        "description": "Dungeon crawler action avec génération BSP, brouillard de guerre, 3 classes, auto-attaque, 3 étages",
        "mecaniques": ["bsp_generation", "fog_of_war", "3_classes_warrior_rogue_mage", "auto_attack_cooldown", "item_drops", "minimap"],
        "style_visuel": "donjon sombre tuiles 32×32, minimap top-right, fog révélé progressivement",
        "boucle_core": "explorer donjon BSP généré, combattre ennemis auto, collecter items, descendre 3 étages, boss final",
        "score": 8.5,
        "notes": "[modele_reference] Jeu modèle dungeon crawler — BSP, fog-of-war Uint8Array, 3 classes spécialisées",
    },
    "roguelite.html": {
        "genre": "roguelite",
        "sous_genre": "action_roguelite_meta",
        "titre": "Roguelite - Modèle",
        "description": "Roguelite action avec seed RNG, méta-progression localStorage, 5 armes, 20 passifs, 10 upgrades méta",
        "mecaniques": ["seeded_rng_mulberry32", "meta_progression", "5_weapons", "20_passives_pool", "10_meta_upgrades", "dash_cooldown", "card_selection"],
        "style_visuel": "sombre avec effets néon, 3 biomes différents, arènes procédurales",
        "boucle_core": "run procédural depuis seed, sélectionner passifs après chaque salle, dépenser or en méta-upgrades",
        "score": 8.9,
        "notes": "[modele_reference] Jeu modèle roguelite — seeded RNG, meta gold economy, card selection 1-3",
    },
}

# Snippet extraction patterns: look for key functions per game type
SNIPPET_PATTERNS = {
    "shoot_em_up.html": [
        (r"function (shoot|spawnEnemy|updateBullets|spawnWave)\b.*?\n(?:.*\n){5,40}?\}", "gameloop"),
    ],
    "endless_runner.html": [
        (r"function (spawnObstacle|updatePlayer|drawParallax)\b.*?\n(?:.*\n){5,40}?\}", "gameloop"),
    ],
    "breakout.html": [
        (r"function (resolveBounceBrick|ballBrickCollide|spawnPowerUp)\b.*?\n(?:.*\n){5,40}?\}", "collision"),
    ],
    "tower_defense.html": [
        (r"function (towerShoot|spawnEnemy|updateEnemies)\b.*?\n(?:.*\n){5,40}?\}", "enemy_ai"),
    ],
    "dungeon_crawler.html": [
        (r"function (revealAround|generateBSP|rollItem)\b.*?\n(?:.*\n){5,40}?\}", "collision"),
    ],
    "roguelite.html": [
        (r"function (generateRunSeq|dealDamage|seededRnd)\b.*?\n(?:.*\n){3,30}?\}", "gameloop"),
    ],
}


def extract_script_body(html: str) -> str:
    """Extract the main <script> tag content (no src=)."""
    scripts = re.findall(r'<script(?!\s[^>]*\bsrc\b)[^>]*>([\s\S]*?)</script>', html)
    if not scripts:
        return ""
    return max(scripts, key=len)


def extract_snippets(fname: str, html: str) -> list[tuple[str, str]]:
    """Extract (code, snippet_type) tuples from an HTML game file."""
    script = extract_script_body(html)
    results = []

    patterns = SNIPPET_PATTERNS.get(fname, [])
    for pattern, stype in patterns:
        m = re.search(pattern, script, re.DOTALL)
        if m:
            snippet = m.group(0)[:3000]
            results.append((snippet, stype))

    # Fallback: grab a large middle section of the script as generic gameloop
    if not results and len(script) > 2000:
        mid = len(script) // 3
        results.append((script[mid:mid+2500], "gameloop"))

    return results


def seed_models(dry_run: bool = False) -> int:
    try:
        import rag
    except ImportError:
        print("[ERROR] Cannot import rag.py — run from the project root")
        sys.exit(1)

    files = sorted(f for f in os.listdir(MODELS_DIR) if f.endswith(".html"))
    seeded = 0

    for fname in files:
        meta = GAME_META.get(fname)
        if not meta:
            print(f"  SKIP (no metadata): {fname}")
            continue

        path = os.path.join(MODELS_DIR, fname)
        with open(path, encoding="utf-8") as f:
            html = f.read()

        code_snippet = html[:300]  # Standard snippet for game_patterns

        if dry_run:
            print(f"  DRY-RUN  {meta['genre']:18s}  {meta['titre']}  (score {meta['score']})")
            snippets = extract_snippets(fname, html)
            for s, t in snippets:
                print(f"           code_snippet [{t}] {len(s)} chars")
            seeded += 1
            continue

        # Store in game_patterns
        ok = rag.store_pattern(
            genre=meta["genre"],
            sous_genre=meta["sous_genre"],
            description=meta["description"],
            score=meta["score"],
            mecaniques=meta["mecaniques"],
            style_visuel=meta["style_visuel"],
            boucle_core=meta["boucle_core"],
            code_snippet=code_snippet,
            notes=meta["notes"],
        )
        if ok:
            print(f"  pattern  {meta['genre']:18s}  {fname}")
        else:
            print(f"  FAIL pattern  {fname}")

        # Store code snippets
        snippets = extract_snippets(fname, html)
        for snippet_code, snippet_type in snippets:
            rag.store_code_snippet(
                game_name=meta["titre"],
                genre=meta["genre"],
                snippet_type=snippet_type,
                code=snippet_code,
                score=meta["score"],
            )
            print(f"  snippet  {meta['genre']:18s}  [{snippet_type}] {len(snippet_code)} chars")

        seeded += 1

    action = "DRY-RUN" if dry_run else "Done"
    print(f"\n[seed_rag_models] {action} — {seeded}/{len(files)} model games seeded")
    return seeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed ChromaDB RAG from jeux_modeles/ reference games")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    seed_models(dry_run=args.dry_run)

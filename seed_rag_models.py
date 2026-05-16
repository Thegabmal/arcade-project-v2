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
    # ── v2 2D games (second instances + extras) ──────────────────────────────
    "shoot_em_up_2.html": {
        "genre": "shmup",
        "sous_genre": "vertical_shmup",
        "titre": "DRAGON VEIL — Fantasy Shmup",
        "description": "Vertical shoot 'em up fantasy, 5 enemy types (imp/gargoyle/wyvern/necromancer/dragon boss), spread powerup, meta-progression",
        "mecaniques": ["vertical_scrolling", "5_enemy_types", "3phase_boss", "spread_powerup", "meta_progression", "wave_system"],
        "style_visuel": "fantasy dark, pixel art enemies, dragon boss multi-phase",
        "boucle_core": "dodge enemy bullets, shoot fantasy enemies, collect power-ups, defeat dragon boss",
        "score": 8.7,
        "notes": "[modele_reference] Fantasy shmup variant — dragon boss 3 phases, 5 enemy types, spread shot",
    },
    "tower_defense_2.html": {
        "genre": "tower_defense",
        "sous_genre": "grid_tower_defense",
        "titre": "CYBER GRID — Sci-Fi Tower Defense",
        "description": "Sci-fi tower defense with drone enemies, 4 tower types, gold economy, waypoints path, meta-progression",
        "mecaniques": ["4_tower_types", "drone_enemies", "gold_economy", "waypoints_path", "meta_progression", "wave_system"],
        "style_visuel": "sci-fi neon grid, drone enemy units, laser towers",
        "boucle_core": "place towers on sci-fi grid, defend path from drone waves, upgrade towers, survive escalating waves",
        "score": 8.6,
        "notes": "[modele_reference] Sci-fi tower defense variant — drone enemies, different economy from fantasy version",
    },
    "dungeon_crawler_2.html": {
        "genre": "rpg",
        "sous_genre": "dungeon_crawler_action",
        "titre": "SECTOR ZERO — Sci-Fi Dungeon",
        "description": "Sci-fi dungeon crawler with rogue class, laser weapons, fog-of-war, BSP generation, 3 floors",
        "mecaniques": ["bsp_generation", "fog_of_war", "rogue_class", "laser_weapons", "item_drops", "3_floors"],
        "style_visuel": "sci-fi corridor aesthetic, metal tiles, neon laser effects",
        "boucle_core": "explore sci-fi dungeon, fight with laser weapons, collect gear, descend 3 floors",
        "score": 8.5,
        "notes": "[modele_reference] Sci-fi dungeon variant — rogue class, laser combat, same BSP as fantasy version",
    },
    "roguelite_2.html": {
        "genre": "roguelite",
        "sous_genre": "bullet_hell_roguelite",
        "titre": "VOID PROTOCOL — Bullet Hell Roguelite",
        "description": "Bullet-hell roguelite with different passive pool, complex bullet patterns, void biome, meta-progression",
        "mecaniques": ["bullet_hell_patterns", "different_passive_pool", "void_biome", "dash_cooldown", "meta_progression", "card_selection"],
        "style_visuel": "void/space aesthetic, complex bullet patterns, purple/black color palette",
        "boucle_core": "dodge dense bullet patterns, select passives after rooms, unlock meta upgrades between runs",
        "score": 8.8,
        "notes": "[modele_reference] Bullet-hell roguelite variant — denser patterns, void biome, different passive pool",
    },
    "rpg_narratif_2.html": {
        "genre": "rpg",
        "sous_genre": "jrpg_narratif",
        "titre": "ECHOES OF THE VOID — Sci-Fi Narrative RPG",
        "description": "Sci-fi narrative RPG with Kael/ARIA/Voss vs NEXUS, 10+ scenes, holographic UI, ATB combat",
        "mecaniques": ["combat_atb", "branching_dialogue", "10_scenes", "3_party_members", "boss_nexus", "meta_progression"],
        "style_visuel": "sci-fi holographic UI, space station aesthetic, portrait art",
        "boucle_core": "navigate sci-fi narrative, make dialogue choices, ATB combat vs NEXUS, reach ending",
        "score": 8.5,
        "notes": "[modele_reference] Sci-fi narrative RPG — Kael/ARIA/Voss party, NEXUS boss, holographic UI",
    },
    # ── v2 3D games (Three.js r160) ─────────────────────────────────────────
    "fps_shooter_3d.html": {
        "genre": "fps",
        "sous_genre": "fps_arena_shooter",
        "titre": "IRON COMPOUND — FPS Shooter 3D",
        "description": "First-person arena shooter with pointer lock, WASD+mouse, wave enemies (grunt/heavy/runner/boss), reload system, meta-progression",
        "mecaniques": ["pointer_lock", "wasd_mouse_fps", "wave_system", "4_enemy_types", "reload_mechanic", "meta_progression", "threejs_r160"],
        "style_visuel": "3D arena militaire, pillars and crates cover, point lights, Three.js WebGL",
        "boucle_core": "lock pointer, WASD move, aim mouse, shoot wave enemies, survive escalating waves",
        "score": 8.7,
        "notes": "[modele_reference] 3D FPS — pointer lock, WASD+yaw/pitch, circleBlocked() collision, spawnBullet() shared player+enemy",
    },
    "platformer_3d.html": {
        "genre": "platformer",
        "sous_genre": "tps_platformer_3d",
        "titre": "SKYRIFT — 3D Platformer",
        "description": "Third-person 3D platformer with TPS follow-cam (mouse drag orbit), AABB platform collision, moving platforms, gem collect, meta-progression",
        "mecaniques": ["tps_follow_cam", "aabb_platform_collision", "moving_platforms", "gem_collect", "double_jump", "meta_progression", "threejs_r160"],
        "style_visuel": "floating islands, 3D gems, TPS camera orbit, Three.js WebGL",
        "boucle_core": "WASD run, jump on platforms, collect all gems to clear level, avoid falling",
        "score": 8.6,
        "notes": "[modele_reference] 3D TPS platformer — mouse-drag camYaw/camPhi, resolveGround() AABB, moving platform ride",
    },
    "space_shooter_3d.html": {
        "genre": "shmup",
        "sous_genre": "space_shooter_3d",
        "titre": "NEBULA BREACH — Space Shooter 3D",
        "description": "3D space shooter with mouse aim (no pointer lock), dual cannons, ship banking, shield regen, sector waves, star field, meta-progression",
        "mecaniques": ["mouse_aim_3d", "dual_cannons", "ship_banking", "shield_regen", "sector_waves", "star_field", "meta_progression", "threejs_r160"],
        "style_visuel": "space nebula, star particle field, ship banking roll, neon projectiles",
        "boucle_core": "move ship with mouse/WASD in bounded space, auto-fire dual cannons, kill wave enemies, protect shield+hull",
        "score": 8.7,
        "notes": "[modele_reference] 3D space shooter — mouseX/mouseY aim, BOUNDS clamped arena, shield regen after 3s no damage",
    },
    "racing_3d.html": {
        "genre": "racing",
        "sous_genre": "circuit_racing_3d",
        "titre": "APEX CIRCUIT — Racing 3D",
        "description": "3D circuit racing with CatmullRomCurve3 oval track, checkpoints, 3 AI racers, nitro boost, TPS follow-cam, meta-progression",
        "mecaniques": ["catmullrom_track", "checkpoint_system", "ai_racers", "nitro_boost", "tps_follow_cam", "lap_system", "meta_progression", "threejs_r160"],
        "style_visuel": "outdoor circuit track, TubeGeometry road, cone barriers, grass ground, TPS camera",
        "boucle_core": "accelerate WASD, steer around circuit, use nitro on straights, beat AI to finish N laps",
        "score": 8.7,
        "notes": "[modele_reference] 3D racing — CatmullRomCurve3 closed loop, car.dir.applyAxisAngle(UP, steer), AI follows t parameter",
    },
    "dungeon_rpg_3d.html": {
        "genre": "rpg",
        "sous_genre": "dungeon_rpg_3d_firstperson",
        "titre": "CRYPT OF IRON — 3D Dungeon RPG",
        "description": "First-person 3D dungeon RPG with pointer lock, melee+magic combat, XP/level-up, magic orbs, stairs progression, meta-progression",
        "mecaniques": ["first_person_dungeon", "pointer_lock", "melee_magic_combat", "xp_level_up", "magic_orbs", "stairs_progression", "meta_progression", "threejs_r160"],
        "style_visuel": "dark 3D dungeon, hero point light, stone geometry, first-person perspective",
        "boucle_core": "explore first-person dungeon, fight enemies (melee or magic), gain XP, find stairs when floor cleared",
        "score": 8.6,
        "notes": "[modele_reference] 3D first-person dungeon — gainXP() level-up cascade, heroLight follows camera, buildDungeon() per floor",
    },
    "zombie_survival_3d.html": {
        "genre": "fps",
        "sous_genre": "zombie_survival_fps_3d",
        "titre": "DEAD COMPOUND — Zombie Survival 3D",
        "description": "FPS zombie survival with pointer lock, 4 zombie types (walker/runner/brute/special), wave system, blood particles, barricades, meta-progression",
        "mecaniques": ["pointer_lock", "4_zombie_types", "horde_waves", "blood_particles", "barricade_cover", "ammo_management", "meta_progression", "threejs_r160"],
        "style_visuel": "post-apocalyptic compound, barricades as cover, red blood particle bursts",
        "boucle_core": "lock pointer, WASD+shoot waves of zombies, manage ammo, survive escalating hordes",
        "score": 8.7,
        "notes": "[modele_reference] 3D zombie FPS — same pointer lock as iron_compound but horde waves, spawnBlood() 6 red particles",
    },
    "flight_shooter_3d.html": {
        "genre": "shmup",
        "sous_genre": "flight_shooter_dogfight_3d",
        "titre": "IRON SKIES — Flight Shooter 3D",
        "description": "6-DOF dogfight flight shooter with Quaternion orientation, barrel roll (Q/E), afterburner (Shift), TPS camera, enemy AI, meta-progression",
        "mecaniques": ["6dof_flight", "quaternion_orientation", "barrel_roll", "afterburner", "tps_flight_cam", "enemy_ai_dogfight", "meta_progression", "threejs_r160"],
        "style_visuel": "sky + clouds + ground plane, TPS camera behind plane, afterburner trail effect",
        "boucle_core": "WASD pitch/yaw, Q/E barrel roll, Shift afterburner, shoot enemy planes, survive waves",
        "score": 8.7,
        "notes": "[modele_reference] 3D dogfight — plane.grp.quaternion.slerp(q,0.15), barrel roll timer 0.5s, back vector for TPS cam",
    },
    "tower_defense_3d.html": {
        "genre": "tower_defense",
        "sous_genre": "tower_defense_3d_isometric",
        "titre": "LAST BASTION — Tower Defense 3D",
        "description": "3D tower defense with fixed top-down camera, THREE.Raycaster grid placement, 4 tower types, path-following enemies, meta-progression",
        "mecaniques": ["raycasting_grid_click", "4_tower_types", "path_following_enemies", "fixed_isometric_cam", "wave_system", "gold_economy", "meta_progression", "threejs_r160"],
        "style_visuel": "3D isometric grid, tower turrets, path arrows, base marker, top-down perspective",
        "boucle_core": "click grid tiles to place towers, send enemy waves manually, towers auto-target, protect base HP",
        "score": 8.7,
        "notes": "[modele_reference] 3D tower defense — raycaster.intersectObjects(gridTiles), PATH[] waypoints, tower.grp.lookAt(nearest)",
    },
    "arena_fighter_3d.html": {
        "genre": "fighting",
        "sous_genre": "arena_fighter_tps_3d",
        "titre": "GLADIATOR PRIME — Arena Fighter 3D",
        "description": "TPS arena melee fighter with mouse-orbit camera, block/dodge/combo system, stamina, AI opponent, escalating rounds, meta-progression",
        "mecaniques": ["tps_melee_combat", "mouse_orbit_cam", "block_dodge_combo", "stamina_system", "ai_opponent", "round_escalation", "meta_progression", "threejs_r160"],
        "style_visuel": "gladiator arena, cylinder floor+wall, pillar torches, crowd boxes",
        "boucle_core": "attack/block/dodge enemy, build combos, deplete enemy HP, survive escalating rounds",
        "score": 8.7,
        "notes": "[modele_reference] 3D arena fighter — doPlayerAttack() dist<2.8, enemyAI blockTimer, comboCount++ on hit",
    },
    "puzzle_3d.html": {
        "genre": "puzzle",
        "sous_genre": "spatial_puzzle_3d",
        "titre": "CHROMATIC — 3D Spatial Puzzle",
        "description": "3D color-match puzzle with orbital camera (right-click drag), raycasting piece selection, ghost targets, undo stack, meta-progression",
        "mecaniques": ["orbital_camera", "raycasting_piece_select", "color_match_puzzle", "ghost_target", "undo_stack", "swap_mechanic", "meta_progression", "threejs_r160"],
        "style_visuel": "3D platform arena, color-coded pieces, ghost opacity pulse, orbital camera rotation",
        "boucle_core": "click to select piece, click slot to move/swap, match all pieces to ghost targets, no mistakes",
        "score": 8.6,
        "notes": "[modele_reference] 3D puzzle — raycaster on pieceMeshes, movePiece() push/pop undoStack, checkSolved() every(p=>targets[p.slotIdx]===p.colorIdx)",
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

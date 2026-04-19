"""
_layer_prompts_genre.py — Templates de prompts spécifiques par genre pour chaque couche (Q3).

Chaque entrée : genre_key → {layer_num: "extra instructions"}
Les extras sont injectés APRÈS les instructions génériques de la couche.
"""

# Clés de genre (sous-chaînes lowercase — la première qui matche est utilisée)
GENRE_LAYER_EXTRAS: dict[str, dict[int, str]] = {

    # ─── SHOOTER / SHOOT'EM UP ───────────────────────────────────────────────
    'shooter': {
        3: (  # L3 — Physics / Movement
            "\nSHOOTER SPÉCIFIQUE (L3) :\n"
            "- Auto-fire : player.fireTimer-=dt; si <=0 { spawnBullet(...); player.fireTimer=player.fireRate||0.2; }\n"
            "- Bullet patterns : droit, légèrement écarté (shotgun), sinusoïdal pour les ennemis erratiques\n"
            "- Homing bullets pour drone type : calcule angle vers joueur, ajuste vx/vy de 8% par frame\n"
            "- Ennemis formation : drones en V, bombardiers en ligne, tourelles fixes (rotation seule)\n"
            "- Screen scroll optionnel : si scrollY défini, tous les ennemis descendent de scrollSpeed*dt\n"
        ),
        5: (  # L5 — Boss & Waves
            "\nSHOOTER SPÉCIFIQUE (L5) :\n"
            "- WAVE_DEFS varie la composition : vague 1=drones, vague 2=mix, vague 3=bombardiers+tourelles\n"
            "- Boss pattern spiral : 12 bullets en cercle toutes les 0.3s en phase 3\n"
            "- Boss invulnérable pendant 1s après transition de phase (boss.invTimer)\n"
            "- Tirs du boss owner='boss' avec dmg=2 (double dégâts par rapport aux ennemis normaux)\n"
        ),
        6: (  # L6 — Render
            "\nSHOOTER SPÉCIFIQUE (L6) :\n"
            "- Bullets : lignes épaisses avec glow (shadowBlur=8), couleur selon owner (player=cyan, boss=rouge)\n"
            "- Traînée bullet : dessine 3 lignes décroissantes derrière la position précédente\n"
            "- Ennemis : forme géométrique anguleuse par type (triangle=kamikaze, carré=bombardier, cercle=tourelle)\n"
            "- Fond étoilé animé : 3 couches de points, vitesse parallaxe (0.2, 0.5, 1.0)\n"
        ),
    },

    # ─── PLATFORMER ──────────────────────────────────────────────────────────
    'platformer': {
        3: (  # L3 — Physics
            "\nPLATFORMER SPÉCIFIQUE (L3) :\n"
            "- Coyote time : player.coyoteTimer — reste sauteable 0.12s après avoir quitté une plateforme\n"
            "- Jump buffering : player.jumpBuffer — si saut appuyé 0.1s avant d'atterrir → saut immédiat\n"
            "- Variable jump height : si touches.space relâché avant apogée → player.vy *= 0.45\n"
            "- Gravité différente ascendante vs descendante : vy<0 → gravity*0.8, vy>0 → gravity*1.4\n"
            "- Wall slide : si contre mur et vy>0 → vy=Math.min(vy,60) (glissement lent)\n"
            "- Double jump : player.jumpsLeft=2, décrémenté à chaque saut, reset au sol\n"
        ),
        4: (  # L4 — Collisions
            "\nPLATFORMER SPÉCIFIQUE (L4) :\n"
            "- Slope detection : AABB mais avec tolérance 4px pour monter les pentes\n"
            "- Ceiling detection : si collision haut → vy=0 (stoppe le saut)\n"
            "- One-way platforms : collision uniquement si player descend (vy>0) ET feet sur la plateforme\n"
            "- Knockback : ennemis touchés poussent le joueur (player.vx ±150, player.vy=-200)\n"
            "- Invincibility frames : player.invTimer=1.5s après dégâts, clignote toutes les 0.1s\n"
        ),
        5: (  # L5 — Levels/Waves
            "\nPLATFORMER SPÉCIFIQUE (L5) :\n"
            "- Progression par niveaux (level), pas par vagues\n"
            "- nextLevel() : level++, charger LEVEL_DEFS[level-1], respawn player spawn point\n"
            "- Checkpoints : si player atteint checkpoint → lastCheckpoint={x,y}\n"
            "- Respawn au checkpoint si player.hp<=0 (pas de game over immédiat)\n"
        ),
    },

    # ─── RPG / DUNGEON ───────────────────────────────────────────────────────
    'rpg': {
        1: (  # L1 — Data
            "\nRPG SPÉCIFIQUE (L1) :\n"
            "- TILE_DEFS : {FLOOR:0, WALL:1, DOOR:2, CHEST:3, BOSS_FLOOR:4}\n"
            "- var map=[], mapW=0, mapH=0, TILE_SIZE=32;\n"
            "- var fogOfWar=[]; (tableau 2D de bool — révélé/non révélé)\n"
            "- player doit avoir : x,y,w,h,hp,maxHp,atk,def,speed,xp,level,gold\n"
            "- var LOOT_TABLE=[{type:'gold',min:5,max:20},{type:'hp_potion',chance:0.3},...]\n"
        ),
        3: (  # L3 — Physics
            "\nRPG SPÉCIFIQUE (L3) :\n"
            "- Mouvement 4-directionnels (haut/bas/gauche/droite), pas de vecteur libre\n"
            "- Collision avec TILE_DEFS.WALL (tile-based AABB)\n"
            "- Aggro radius : ennemis poursuivent si dist < aggro_radius (150px), retournent sinon\n"
            "- Patrol : ennemis sans aggro suivent un chemin patrol prédéfini\n"
            "- Knockback : enemy.vx/vy += direction * 200 quand frappé, décélération rapide\n"
        ),
        6: (  # L6 — Render
            "\nRPG SPÉCIFIQUE (L6) :\n"
            "- Tilemap rendu par chunks (seules les tiles visibles dans le viewport)\n"
            "- Fog of war : cases non révélées en noir, cases révélées mais hors vue en gris 50%\n"
            "- Lumière de torche : radialGradient centré sur joueur, rayon 200px, pulsation sin()\n"
            "- Minimap dans le HUD (coin bas-droite, 80x80px, tuiles colorées)\n"
        ),
    },

    # ─── TOWER DEFENSE ───────────────────────────────────────────────────────
    'defense': {
        3: (  # L3 — Physics
            "\nTOWER DEFENSE SPÉCIFIQUE (L3) :\n"
            "- Ennemis suivent un PATH (tableau de waypoints), pas de pathfinding libre\n"
            "- Interpolation sur le path : en.pathIdx, en.pathT, avance sur segment\n"
            "- Tours : rotation vers ennemi le plus proche dans range, tir si shootTimer<=0\n"
            "- Projectiles tours : owner='tower', ciblent un ennemi spécifique (en.id stocké)\n"
        ),
        5: (  # L5 — Waves
            "\nTOWER DEFENSE SPÉCIFIQUE (L5) :\n"
            "- WAVE_DEFS : chaque vague = [{type:'basic',count:5,interval:0.8},{type:'fast',count:3,interval:0.4}]\n"
            "- spawnQueue : liste d'ennemis à spawner avec délais\n"
            "- lives décrémente si ennemi atteint la fin du path\n"
            "- gold += enemy.reward quand ennemi tué (économie pour acheter des tours)\n"
        ),
    },

    # ─── RUNNER ──────────────────────────────────────────────────────────────
    'runner': {
        3: (  # L3 — Physics
            "\nRUNNER SPÉCIFIQUE (L3) :\n"
            "- Vitesse de défilement augmente avec le temps : scrollSpeed += dt * 5 (cap à 800)\n"
            "- Saut avec gravité : player.vy += gravity*dt; player.y += player.vy*dt\n"
            "- Double jump disponible une fois en l'air\n"
            "- Obstacles générés procéduralement avec espacement minimum garanti (200px)\n"
            "- Score basé sur la distance parcourue : score += scrollSpeed * dt\n"
        ),
        1: (  # L1 — Data
            "\nRUNNER SPÉCIFIQUE (L1) :\n"
            "- var scrollSpeed = 300; var obstacleSpawnTimer = 0;\n"
            "- var obstacles = []; (type, x, y, w, h)\n"
            "- player.lane ou player.y pour position verticale\n"
            "- var distance = 0; (distance parcourue — base du score)\n"
        ),
    },
}


def get_layer_extra(genre: str, layer_num: int) -> str:
    """
    Retourne les instructions supplémentaires pour une couche selon le genre.
    Retourne "" si pas d'extras pour ce couple (genre, couche).
    """
    genre_lower = genre.lower()
    for key, layers in GENRE_LAYER_EXTRAS.items():
        if key in genre_lower:
            return layers.get(layer_num, "")
    return ""

"""
Agent Game Logics — Phase 2
Expert en mécaniques de jeu concrètes basées sur des jeux réels.
Interroge Claude pour produire des game logics précises et implémentables.
Adapte selon le genre : boss, ennemis, power-ups, classes, quêtes, PNJ, formules.
"""

import json
from config import call_claude, with_fallback
from genre_profile import GenreProfile
from logger import phase2_log

SYSTEM = """Tu es un game designer expert avec 20 ans d'expérience sur des jeux AAA et indie.
Tu connais parfaitement les mécaniques des jeux les plus réussis de chaque genre.
Ta spécialité : les game logics concrètes et implémentables en JavaScript/HTML5.
Tu fournis des spécifications précises avec des valeurs numériques, des comportements détaillés
et des références directes aux jeux qui ont prouvé leur efficacité.
Tu n'expliques pas la théorie — tu donnes des specs directement utilisables par un développeur."""


def run(genre_profile: GenreProfile, gdd: dict) -> str:
    """
    Produit les game logics en plusieurs appels parallèles focalisés (1 section = 1 appel).
    Évite les prompts gigantesques et les réponses tronquées.
    """
    phase2_log.agent_start("Game Logics", f"Analyse des mécaniques pour '{genre_profile.genre_principal}'")

    titre   = gdd.get("titre", "Arcade Game")
    context = (
        f'Jeu : "{titre}" — {genre_profile.genre_principal} / {genre_profile.sous_genre}\n'
        f'Mécaniques : {", ".join(genre_profile.mecaniques_obligatoires[:5])}\n'
        f'Références : {", ".join(genre_profile.jeux_reference[:4])}\n'
        f'Core loop : {genre_profile.boucle_core}'
    )

    # Construire les sections individuelles
    sections = _build_sections_list(
        (genre_profile.genre_principal or "").lower(),
        (genre_profile.sous_genre or "").lower(),
        genre_profile,
        context,
    )

    # Appels parallèles — 1 prompt focalisé par section
    results = _call_sections_parallel(sections)

    # Assembler dans l'ordre
    parts = []
    for title, result in results:
        if result and result.strip():
            parts.append(f"━━━ {title} ━━━\n{result.strip()}")

    if parts:
        combined = "\n\n".join(parts)
        phase2_log.agent_done("Game Logics", f"{len(combined)} chars ({len(parts)} sections)")
        return combined

    phase2_log.agent_done("Game Logics", "Fallback utilisé")
    return _fallback_logics(genre_profile)


def _call_sections_parallel(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Exécute les appels API séquentiellement.
    Anciennement parallèle (ThreadPoolExecutor(4)) — supprimé car provoquait des cascades
    de 429 : game_logics était déjà dans un thread du coordinateur, les 4 sous-threads
    multipliaient les appels simultanés et saturaient le quota Gemini free tier.
    """
    results = []
    for title, prompt in sections:
        result = _call_section(prompt)
        results.append((title, result or ""))
    return results


def _build_sections_list(genre: str, sous_genre: str, gp: GenreProfile, context: str) -> list[tuple[str, str]]:
    """
    Retourne une liste de (titre_section, prompt_focalisé) à appeler en parallèle.
    Chaque prompt est court et ciblé sur UNE seule responsabilité.
    """
    sections = []
    instr = "Sois TRÈS concret : valeurs numériques précises, state machines, références à des jeux connus. Pas de généralités."

    # ── Détection famille de genre ──
    is_shooter   = any(g in genre for g in ["shooter","shoot","spatial","space","bullet","shmup"])
    is_platformer= any(g in genre for g in ["platform","plateform","jump","run"])
    is_rpg       = any(g in genre for g in ["rpg","role","adventure","aventure","dungeon"])
    is_puzzle    = any(g in genre for g in ["puzzle","match","tetris","block"])
    is_tower     = any(g in genre for g in ["tower","defense","défense","td"])
    is_fighting  = any(g in genre for g in ["fight","combat","beat","brawl"])
    is_racing    = any(g in genre for g in ["racing","race","car","drive","kart"])
    is_survival  = any(g in genre for g in ["survival","survie","roguelike","rogue"])
    is_3d        = gp.technologie_rendu == "threejs"

    # ── Section 1 — Ennemis & IA (universelle) ──
    sections.append(("ENNEMIS & IA", f"""{context}

Décris 4 à 5 types d'ennemis VISUELLEMENT ET COMPORTEMENTALEMENT DISTINCTS.
Pour chaque ennemi (valeurs numériques obligatoires) :
- Nom + couleur unique (JAMAIS la même que le sol ou les autres ennemis)
- HP précis, vitesse en px/s (max 65 px/s pour les normaux), dégâts par coup
- State machine complète (idle → patrol → chase → attack → stunned → death)
- Pattern de déplacement PRÉCIS (ex: "patrouille sur 64px, se retourne aux bords ; dès que le joueur est à < 100px, charge en ligne droite")
- Type d'attaque : mêlée / projectile / zone / saut (ne pas mettre tous en mêlée)
- Comportement post-knockback : l'ennemi se relève après 0.2s et reprend son état

DIVERSITÉ OBLIGATOIRE :
- 1 ennemi lent et robuste (HP élevés, dégâts forts)
- 1 ennemi rapide et fragile (HP faibles, dégâts modérés, speed 60–65 px/s)
- 1 ennemi à distance (tire des projectiles, maintient une distance de 80–120px)
- 1 ennemi spécial (invocateur, kamikaze, invisible, bouclier…)
- Chacun apparaît à des étages/zones différents (pas tous dès le départ)

BOSS OBLIGATOIRE — précise TOUS ces points :
- Nom du boss + couleur distinctive (≠ tout ennemi normal, ≠ sol de la salle)
- HP total (300–600), taille sizeFactor = 1.8–2.0, sprite plus grand que les ennemis normaux
- Emplacement : salle de boss dédiée en bas-droite de la map (dernière salle de la grille)
- SPAWN dans generateDungeon() — pas de spawn lazy — boss = createBoss() lors de la génération
- Condition de déverrouillage : nombre de clés (floor/3) OU leviers activés
- 3 phases avec HP seuils ET comportements différents :
  Phase 1 (100%→50%) : déplacement lent 40 px/s, attaque mêlée cooldown 2s
  Phase 2  (50%→25%) : vitesse 65 px/s + tir projectile directionnel cooldown 1.5s
  Phase 3   (<25%)   : vitesse 75 px/s + téléportation aléatoire toutes les 1.2s + salve en étoile 8 directions
- Après défaite : placer TILE.STAIR au centre de la salle + afficher dialog + accès étage suivant
{instr}"""))

    # ── Section 2 — Mécaniques core du genre ──
    if is_rpg:
        sections.append(("CLASSES & COMBAT", f"""{context}

Définis 3 classes de personnages jouables TRÈS DISTINCTES. Pour chacune :
- Nom + description de style de jeu en 2 phrases (comment elle se joue concrètement)
- Stats de base : HP, ATK, DEF, SPD (valeurs numériques précises en px/s et points)
- Forme visuelle distinctive : cercle / carré / triangle / losange + couleur unique
- Passive unique (ex: "le guerrier regagne 2 HP en tuant un ennemi")
- 3 compétences actives avec : nom, description en 1 ligne, coût MP, cooldown en secondes, effet chiffré
  ex: "Bouclier Divin — bloque tout dégât pendant 2s — coût: 20 MP — CD: 8s"
- Scénario de victoire : dans quel cas cette classe est-elle supérieure aux autres ?

BALANCE OBLIGATOIRE (valeurs numériques) :
- Vitesse joueur de base : 75 px/s (résolution 256×240)
- Vitesse ennemis normaux : 45–65 px/s (JAMAIS > 70 px/s = jamais plus rapide que le joueur)
- Vitesse ennemis élites : 60–72 px/s (max 95% vitesse joueur)
- Boss phase 1 : 40 px/s — phase 2 : 60 px/s — phase 3 : 75 px/s (égale le joueur)
- Dégâts ennemi normal : 8–15 HP/coup — boss : 25–35 HP/coup
- HP ennemi normal : 30–80 — élite : 100–200 — boss : 300–600

LEVEL UP — progression impactante (à implémenter dans checkLevelUp) :
- Niveau 1→2 : +15 HP max, +4 ATK, +2 DEF → soin complet
- Niveau 2→3 : +18 HP max, +5 ATK, +2 DEF → soin complet
- Formule générale : hpGain = 10 + niveau * 5, atkGain = 2 + floor(niveau/3)
- Tous les 3 niveaux : débloquer ou améliorer une compétence
- XP requis : niveau * 100 (ex: lvl1→lvl2 : 100 XP, lvl2→lvl3 : 200 XP)
{instr} Inspire-toi de Final Fantasy, Diablo, Zelda."""))

        sections.append(("QUÊTES & PROGRESSION", f"""{context}

Décris le système de quêtes : 1 quête principale (3 étapes), 3 quêtes secondaires (type, objectif, récompense).
Système de progression : courbe XP par niveau (formule ou tableau niveaux 1-10), types d'équipement (arme/armure/accessoire),
rareté (commun/rare/épique avec couleurs et bonus), économie (prix marchands, revenus typiques).
{instr}"""))

        sections.append(("MARCHAND & ÉCONOMIE", f"""{context}

SYSTÈME DE BOUTIQUE — PNJ Marchand dans le donjon :
Décris un écran de boutique complet accessible en interagissant avec le PNJ Marchand :

INTERFACE BOUTIQUE :
- Fond sombre semi-transparent sur tout l'écran (rgba(0,0,0,0.85))
- Titre "BOUTIQUE" en gros + nom du marchand + dialogue d'accueil court
- Liste de 4-6 articles avec : icône (forme géométrique colorée), nom, description courte, prix en or
- Sélection par clavier (↑↓) ET clic souris — les deux toujours actifs
- Boutons : [ACHETER] [QUITTER] — feedback visuel sur hover

INVENTAIRE DU MARCHAND (4-6 articles avec prix) :
1. Potion de Soin — restaure 40 HP — 30 or
2. Potion Mana — restaure 30 MP — 25 or
3. Amulette de Force — +5 ATK permanent — 80 or (one-shot, disparaît après achat)
4. Bouclier en Cuir — +3 DEF permanent — 60 or
5. Clé Spéciale — ouvre les coffres épiques — 50 or
6. Elixir de Vitesse — +20 SPD pendant 60s — 40 or

LOGIQUE D'ACHAT :
- Vérifier or suffisant AVANT d'autoriser l'achat
- Feedback d'erreur si pas assez d'or : texte rouge "Or insuffisant !" pendant 1.5s
- Feedback succès : texte vert "Acheté !" + son (sfx.play...) + particules dorées
- Les articles "one-shot" (stat permanente) sont grisés et non-achetables une 2ème fois

IMPLÉMENTATION (noms obligatoires pour la dev console) :
let shopOpen = false;
let shopSelectedItem = 0;
const SHOP_ITEMS = [... liste des articles ...];
function openShop() {{ shopOpen = true; shopSelectedItem = 0; gameState = 'shop'; }}
function closeShop() {{ shopOpen = false; gameState = 'playing'; }}
function buyItem(index) {{ ... vérifier or, appliquer effet, déduire or ... }}
Dans draw() : if (shopOpen) drawShop();
Dans update() : if (gameState === 'shop') {{ updateShop(); return; }}
{instr}"""))

    elif is_shooter:
        sections.append(("SYSTÈMES DE TIR & POWER-UPS", f"""{context}

JOUEUR — ARME DE BASE :
- Tir de base : cadence 0.25s (4 tirs/s), vitesse projectile 250 px/s, dégâts 10/tir
- Direction : toujours vers le haut (vertical scroller) OU 8 directions (top-down)
- Hitbox projectile : 4×12px (vertical) ou 6×6px (circulaire)

4 POWER-UPS collectables (dropés par ennemis élites, durée 12s sauf bouclier) :
1. TRIPLE SHOT — 3 projectiles en éventail (angles -15°, 0°, +15°), dégâts 8/tir
2. LASER — rayon continu (damage 3/frame, range GH), cooldown interne 0.08s
3. BOMBE — explosion AOE (rayon 60px, dégâts 60, knockback 80px), cooldown 3s
4. BOUCLIER — absorbe 2 coups avant de disparaître, pulse bleu animé autour du joueur

PATTERNS D'ATTAQUE ENNEMIS (valeurs pour résolution 256×240) :
1. TIRS CIRCULAIRES — 8 projectiles à 45° chacun, vitesse 80 px/s, cooldown 2.5s
   code: for(let a=0;a<8;a++){{spawnBullet(e.x,e.y,Math.cos(a*Math.PI/4)*80,Math.sin(a*Math.PI/4)*80)}}
2. ÉVENTAIL 5 BALLES — spread 60° autour de la direction joueur, vitesse 100 px/s, cooldown 1.8s
3. TIR VISÉ — projectile unique qui trace vers la position du joueur, vitesse 120 px/s, cooldown 1.2s
4. SPIRALE — 1 projectile/frame pendant 3s, angle +15° par tir, vitesse 90 px/s
5. SALVE RAPIDE — 5 tirs en 0.5s (burst), pause 3s

BOSS PATTERN (3 phases) :
Phase 1 (100%→60%) : tir circulaire 6 balles toutes les 2s
Phase 2 (60%→30%) : alterne tir visé + éventail, invocateur (2 minions toutes les 5s)
Phase 3 (<30%) : spirale continue + déplacement aléatoire rapide, rage mode

VAGUES (si vertical/horizontal scroller) :
Vague 1-3 : ennemis formation V, déplacement simple
Vague 4-6 : ennemis kamikazes + tirs simples
Vague 7-9 : ennemis élites avec tirs complexes + mid-boss toutes les 3 vagues
Vague 10+ : boss complet
{instr} Inspire-toi de Galaga, Ikaruga, Touhou, Gradius."""))

    elif is_platformer:
        sections.append(("PHYSIQUE & POWER-UPS PLATFORMER", f"""{context}

VALEURS PHYSIQUES (pour canvas 320×240, TILE_SIZE=16) :
- Vitesse course : 160 px/s (accélération en 0.1s depuis l'arrêt)
- Vitesse saut initial : -320 px/s (impulsion vers le haut)
- Gravité : +900 px/s² (chute rapide et réactive)
- Saut maintenu : si keys.jump tenu, réduire la gravité à 450 px/s² pendant 0.3s max (saut variable)
- Coyote time : 6 frames après le bord d'une plateforme (peut encore sauter)
- Jump buffering : mémoriser l'input saut 8 frames à l'avance (si atterrissage imminent)
- Double saut : hauteur = 80% du saut simple, une seule charge (rechargée au sol)
- Dash : 200 px en 0.15s, cooldown 0.8s, invincibilité pendant le dash (4 frames)
- Knockback reçu : vx = ±120 px/s, vy = -200 px/s, durée 0.25s (bloque le contrôle)

5 POWER-UPS (placés dans le niveau, effet au contact) :
1. SUPER SAUT — hauteur ×1.8 pendant 10s (effet particules dorées)
2. VITESSE — vitesse course ×1.5 pendant 8s (traînée de particules bleues)
3. DASH AMÉLIORÉ — distance ×2, cooldown réduit à 0.3s, pendant 12s
4. INVINCIBILITÉ — 5s d'invincibilité totale (clignotement blanc)
5. MEGA SAUT — saut infini pendant 6s (re-sauter en l'air sans limite)

TYPES DE PLATEFORMES :
- Normale : statique, solide
- Mouvante : aller-retour sur 80-120px, vitesse 60 px/s (le joueur se déplace avec)
- Fragile : se brise en 0.5s après contact (shaking animation), disparaît 2s
- Rebondissante : vy = -500 px/s au contact (super rebond, particules jaunes)
- Passable : peut sauter à travers du bas (appuyer Bas+Saut pour tomber)

ENNEMIS TYPIQUES (en plus de la section ENNEMIS) :
- Marcheur : patrouille sur la plateforme, se retourne aux bords
- Sauteur : saute vers le joueur si <100px (vy=-280, vx=signé vers joueur)
- Tireur : statique, tire un projectile lent (80 px/s) vers le joueur toutes les 2s
- Épineux au sol : décor mortel, pas d'IA (contact = mort instantanée)
{instr} Inspire-toi de Celeste, Hollow Knight, Super Mario Bros, Shovel Knight."""))

    elif is_puzzle:
        sections.append(("MÉCANIQUES PUZZLE & PROGRESSION", f"""{context}

Mécanique fondamentale avec règles précises. Progression de difficulté sur 10 niveaux.
5 boosters avec effets immédiats. Système de score avec multiplicateurs de combo.
{instr}"""))

    elif is_tower:
        sections.append(("TOURS & VAGUES", f"""{context}

4-5 types de tours (coût, portée px, cadence tirs/s, dégâts, 2 niveaux d'upgrade).
Structure de 10 vagues (composition, timing, boss toutes les 5 vagues).
Économie : or de départ, revenus par kill/vague, coûts placement.
{instr}"""))

    elif is_survival:
        sections.append(("RESSOURCES & GÉNÉRATION PROCÉDURALE", f"""{context}

Ressources clés avec équilibrage (HP, stamina, munitions). Règles de génération procédurale des salles.
5-8 upgrades permanents entre les runs. Ennemis élite et boss par zone avec mécaniques uniques.
{instr} Inspire-toi de Hades, Dead Cells, The Binding of Isaac."""))

    elif is_fighting:
        sections.append(("SYSTÈME DE COMBAT", f"""{context}

Attaques légère/lourde/combo avec dégâts, frames, portée. Système de blocage/parry.
Archétypes ennemis avec move sets. 3 boss avec phases et tells visuels.
{instr}"""))

    elif is_racing:
        sections.append(("PHYSIQUE VÉHICULE & CIRCUITS", f"""{context}

Physique véhicule : accélération, vitesse max, friction, dérapage. 3 types de véhicules.
5 circuits avec caractéristiques (virages, raccourcis, obstacles). Items/power-ups style Mario Kart.
{instr}"""))

    else:
        sections.append(("MÉCANIQUES CORE", f"""{context}

Décris les mécaniques fondamentales propres à ce genre : action principale joueur, obstacles/défis,
système de progression, 5 power-ups avec valeurs précises.
{instr}"""))

    # ── Section 3 — Interactions environnementales (universelle, adaptée au genre) ──
    genre_label = gp.genre_principal
    sections.append(("INTERACTIONS ENVIRONNEMENTALES", f"""{context}

Définis 3 à 4 interactions environnementales adaptées à ce jeu {genre_label}.
Pour chaque interaction : nom adapté à l'univers, description visuelle (couleur/animation),
condition d'activation (touche E / contact / automatique), effet précis avec valeurs numériques,
feedback (particules couleur+nombre, sfx fréquence), position dans le niveau (optionnel/obligatoire).
Types disponibles : levier/switch, plaque de pression, coffre/conteneur, zone verrouillée+condition,
téléporteur, bouton temporisé, PNJ interactif, objet physique déplaçable, zone d'effet passif.

RÈGLE CRITIQUE — LES INTERACTIONS DOIVENT AVOIR UN OBJECTIF CONCRET :
JAMAIS de levier décoratif. Chaque interaction doit changer quelque chose dans le monde :
- Levier / Switch → ouvre une porte, déverrouille la salle du boss, active un pont, désactive des pièges
- Plaque de pression → déclenche un mécanisme temporaire (pont rétractable, plateforme, ouverture timed)
- Coffre → loot varié (loot table avec poids, ≥ 4 types différents)
- Porte boss → ne s'ouvre QUE si N clés collectées OU M leviers activés (pas les deux à la fois)

Pour les jeux RPG/Dungeon — LIENS LEVIERS → BOSS OBLIGATOIRES :
Spécifie : combien de leviers par étage (ex: 2 leviers sur étage 1, 3 sur étage 2) et que
tous doivent être activés pour ouvrir la bossGate. Le HUD doit afficher "Leviers : X/N".
Position des leviers : dispersés dans des salles différentes (pas tous au même endroit).
{instr}"""))

    # ── Section 4 — Juice & Game Feel (universelle) ──
    sections.append(("JUICE & GAME FEEL", f"""{context}

5 recommandations concrètes pour rendre ce jeu {genre_label} satisfaisant :
1. Feedback visuel sur actions clés (durée ms, amplitude px)
2. Screen shake : quand, intensité (px), durée (frames)
3. Hit pause/hitstop : durée en frames sur les coups importants
4. Particules : nombre, vitesse, couleurs recommandées
5. Floating text : quand l'afficher, couleurs, taille
Toutes les valeurs doivent être directement implémentables en JavaScript Canvas 2D.
{instr}"""))

    # ── Section 3D si applicable ──
    if is_3d:
        sections.insert(0, ("ARCHITECTURE 3D", f"""{context}

Architecture Three.js r128 pour ce jeu :
Caméra : type exact (FPS/TPS/top-down), FOV, position initiale, lerp factor.
Mouvements joueur : vitesse (units/s), saut impulsion Y, gravité, friction.
Collisions : THREE.Box3 ou sphère (rayon), sol detection.
Performance : max ennemis simultanés, réutilisation géométries/matériaux, pixel ratio.
{instr}"""))

    return sections


def _build_genre_sections(genre: str, sous_genre: str, gp: GenreProfile) -> str:
    """Conservé pour compatibilité — redirige vers _build_sections_list."""
    sections = _build_sections_list(genre, sous_genre, gp, f"Jeu : {gp.genre_principal} / {gp.sous_genre}")
    return "\n\n".join(f"=== {t} ===\n{p}" for t, p in sections)
    """Construit les sections de demande adaptées au genre."""

    # Détecter la famille de genre
    is_shooter = any(g in genre for g in ["shooter", "shoot", "spatial", "space", "bullet", "shmup"])
    is_platformer = any(g in genre for g in ["platform", "plateform", "jump", "run"])
    is_rpg = any(g in genre for g in ["rpg", "role", "adventure", "aventure", "dungeon"])
    is_puzzle = any(g in genre for g in ["puzzle", "match", "tetris", "block"])
    is_tower = any(g in genre for g in ["tower", "defense", "défense", "td"])
    is_fighting = any(g in genre for g in ["fight", "combat", "beat", "brawl"])
    is_racing = any(g in genre for g in ["racing", "race", "car", "drive", "kart"])
    is_survival = any(g in genre for g in ["survival", "survie", "roguelike", "rogue"])
    is_stealth = any(g in genre for g in ["stealth", "infiltration", "espion"])
    is_3d = gp.technologie_rendu == "threejs" or any(g in genre+sous_genre for g in ["3d", "fps", "first-person", "third-person"])

    sections = []

    # ── Section 3D spécifique ──
    if is_3d:
        sections.append("""SECTION 0 — ARCHITECTURE 3D (Three.js r128)
Précise l'architecture 3D adaptée au genre :

CAMÉRA :
- Type exact : FPS (pointer lock) / TPS (suit joueur avec lerp) / Top-down fixe / Isométrique
- FOV recommandé (60-90°), position initiale (x,y,z)
- Pour FPS : pitch/yaw avec clamp à ±Math.PI*0.4
- Pour TPS : camera.lerp vers (player.x, player.y+5, player.z+10) avec factor 0.08, lookAt(player)

MOUVEMENTS JOUEUR 3D (valeurs numériques précises) :
- Vitesse de déplacement : unités Three.js/seconde
- Pour FPS : vecteur directionnel calculé depuis camera.rotation (forward/right)
- Pour TPS : WASD déplace en world space, le mesh player oriente selon la direction
- Saut : impulsion Y (ex: 8 units/s), gravité (ex: -20 units/s²)
- Friction sol : multiplicateur de vélocité par frame (ex: 0.88)

SPAWN ENNEMIS 3D :
- Position spawn : hors du frustum caméra (ex: cercle de rayon 15 units autour du joueur)
- Object pooling : créer N meshes au départ, réutiliser avec mesh.visible = false/true
- Max ennemis simultanés recommandé : 8-15 (performance WebGL mobile)

COLLISIONS (THREE.Box3) :
- playerBox.setFromObject(player.mesh) — mettre à jour chaque frame
- Pour les balles/projectiles : sphère (rayon 0.3) + distance check (< 0.5 units) plus performant
- Sol : player.position.y >= groundLevel, sinon appliquer gravité

PERFORMANCE THREE.JS :
- Réutiliser les géométries/matériaux (une instance par type, pas une par entité)
- Limiter les lights dynamiques (max 2-3 PointLights)
- Éviter scene.remove/add en boucle — utiliser mesh.visible
- renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)) pour mobile""")

    # ── Section universelle : Ennemis & IA ──
    sections.append("""SECTION 1 — ENNEMIS & COMPORTEMENTS IA
Décris 4 à 6 types d'ennemis distincts avec :
- Nom, HP, vitesse, dégâts de contact
- State machine (états: idle, patrol, chase, attack, flee, death)
- Comportement de déplacement précis (ex: "patrouille sur X pixels, se retourne aux bords")
- Condition d'attaque et pattern d'attaque
- Valeur en points au kill
- Moment d'apparition dans la progression (début / milieu / fin)""")

    # ── Shooter ──
    if is_shooter:
        sections.append("""SECTION 2 — SYSTÈME DE TIR & BULLET PATTERNS
Décris le système de tir du joueur ET des ennemis :
JOUEUR :
- Tir de base : cadence (balles/sec), vitesse balle, dégâts
- Power-up tir double : écartement en degrés
- Power-up tir triple : angles précis
- Power-up laser : largeur px, dégâts/frame, durée
- Power-up bombe : rayon d'explosion, dégâts

ENNEMIS :
- Pattern circulaire : nombre de balles, angle entre chaque
- Pattern en éventail : nombre de balles, angle total
- Pattern visé (aimed) : délai de calcul, vitesse balle
- Pattern spirale : rotation deg/frame, vitesse

SECTION 3 — BOSS & PHASES
Décris 3 boss distincts avec leurs patterns d'attaque :
Boss 1 (boss de mi-parcours) :
- HP, taille, vitesse de déplacement
- Phase 1 (100%-60% HP) : pattern d'attaque A + déplacement
- Phase 2 (60%-30% HP) : pattern d'attaque B (plus intense) + comportement
- Phase 3 (<30% HP) : rage mode, tous les patterns en simultané
- Récompense à la mort (score bonus, power-up spécial)

Boss 2 et Boss 3 avec la même structure mais des mécaniques différentes.
Inspire-toi de : Galaga, R-Type, Ikaruga, Touhou, Jamestown.

SECTION 4 — POWER-UPS
Définis 5 à 7 power-ups avec :
- Nom, apparence (couleur/icône), fréquence d'apparition (%)
- Effet précis avec valeurs numériques
- Durée (si temporaire) en secondes
- Sont-ils cumulables ? Lequel remplace lequel ?
- Exemple : "Triple Shot : 3 balles à -15°, 0°, +15°, durée 8s, non cumulable avec Laser"

SECTION 5 — FORMATIONS D'ENNEMIS
Décris 5 formations de vagues :
- Formation en V (classic Galaga)
- Grid attack (Space Invaders)
- Flanking (attaque des deux côtés)
- Suicide rush (kamikaze en ligne droite)
- Boss escort (ennemis protègent un ennemi central)
Pour chaque : nombre d'ennemis, espacement en pixels, ordre d'apparition, comportement""")

    # ── Platformer ──
    elif is_platformer:
        sections.append("""SECTION 2 — MÉCANIQUES DE MOUVEMENT JOUEUR
Valeurs précises pour le mouvement :
- Vitesse course : px/s
- Vitesse saut : px/s initial (vertical)
- Gravité : px/s² d'accélération vers le bas
- Coyote time : frames de grâce après le bord d'une plateforme
- Double saut : hauteur relative au saut normal (ex: 70%)
- Dash : distance en px, durée en ms, cooldown en ms
- Wall jump : angle de déviation en degrés

SECTION 3 — BOSS & PATTERNS
3 boss avec :
- Pattern de déplacement (saut, rush, patrouille)
- Attaques (projectiles, zone, corps-à-corps)
- Phases selon % HP restants
- Tells visuels (signal avant attaque)
Inspire-toi de : Super Mario, Hollow Knight, Celeste, Mega Man.

SECTION 4 — POWER-UPS & COLLECTIBLES
5 power-ups avec valeurs et durées précises.
Types de plateformes : normale, mouvante (vitesse, amplitude), fragile (délai avant chute), rebondissante (coefficient), dangereuse (spikes).

SECTION 5 — SPAWNING & LEVEL PATTERNS
Règles de spawn d'ennemis selon distance parcourue.
Patterns de niveau : gaps, élévations, sections d'ennemis, mini-boss toutes les X secondes.""")

    # ── RPG ──
    elif is_rpg:
        sections.append("""SECTION 2 — CLASSES DE PERSONNAGES
Définis 3 classes jouables :
Pour chaque classe :
- Nom, archétype, style de jeu
- Stats de base : HP, attaque, défense, vitesse, magie
- Compétence passive unique
- 3 compétences actives avec cooldown et effets précis
- Style visuel suggéré (couleur, forme)
Inspire-toi de : Diablo, Path of Exile, Final Fantasy, Stardew Valley.

SECTION 3 — SYSTÈME DE COMBAT
Mécaniques de combat détaillées :
- Tour par tour ou temps réel ? Précise les timings si temps réel.
- Formule de calcul des dégâts (ex: dégâts = (attaque - défense) * multiplicateur)
- Types de dégâts : physique, magique, élémentaire (feu, glace, foudre)
- États de statut : empoisonné (dégâts/tour), étourdi (skip tour), brûlé, gelé
- Système de critique (chance %, multiplicateur de dégâts)
- Effets de résistance et faiblesses élémentaires

SECTION 4 — QUÊTES & PNJ
Types de quêtes avec structure narrative :
- Quête principale : arc narratif en 3 actes
- Quêtes secondaires : 3 types (élimination, collecte, escort, exploration)
- PNJ types : marchand (liste d'articles avec prix), guide (dialogues), quêteur (déclencheur)
- Système de dialogue : arbres de décision simples
- Récompenses : XP, or, objets, informations

SECTION 5 — PROGRESSION & LOOT
- Courbe d'XP pour passer les niveaux (formule ou tableau)
- Types d'équipement : arme, armure, accessoire, consommable
- Rareté : commun, rare, épique (couleurs et stat bonus)
- Système d'inventaire : slots, empilage
- Économie : or, prix des objets, revenus typiques par quête""")

    # ── Tower Defense ──
    elif is_tower:
        sections.append("""SECTION 2 — TOURS (TOWERS)
4 à 5 types de tours avec specs précises :
- Nom, coût en or, portée en px, cadence tirs/sec, dégâts/tir
- Type de dégâts : single target, splash (rayon), slow, poison
- Upgrades : 2 niveaux d'upgrade avec coût et amélioration de stats
- Priorité ciblage : premier ennemi, dernier ennemi, plus de HP, plus proche

SECTION 3 — VAGUES D'ENNEMIS
Structure de 10 vagues avec :
- Composition par vague (types, nombre, espacement en frames)
- Vague boss (toutes les 5 vagues) : HP x5, reward x3
- Accélération : vitesse des ennemis +5% par vague
- Ennemis blindés (résistance physique), rapides (vitesse x2), volants (ignorent certaines tours)

SECTION 4 — ÉCONOMIE
- Or de départ
- Revenus : or par ennemi tué (par type), or par vague complète
- Coût de placement et upgrade des tours
- Système d'intérêt (bonus or selon or non dépensé)

SECTION 5 — CHEMIN & CARTE
- Structure du chemin (entrée → sortie)
- Zones de placement valides
- Effets du terrain""")

    # ── Puzzle ──
    elif is_puzzle:
        sections.append("""SECTION 2 — MÉCANIQUES CORE DU PUZZLE
Décris la mécanique fondamentale avec précision :
- Règle de base (ex: "aligner 3 éléments identiques pour les éliminer")
- Types d'éléments et leurs propriétés
- Conditions de victoire et d'échec
- Combos et chaînes : définition, multiplicateur de score

SECTION 3 — PROGRESSION DE DIFFICULTÉ
Niveau par niveau sur 10 niveaux :
- Vitesse de jeu (augmentation %)
- Nouveaux éléments introduits (quel niveau, pourquoi)
- Contraintes ajoutées (grille plus petite, éléments bloquants)
- Objectifs spéciaux (compléter en moins de X secondes)

SECTION 4 — POWER-UPS & BOOSTERS
5 boosters avec effets précis :
- Effet immédiat (ex: "explose toute une ligne")
- Conditions d'activation
- Cooldown ou consommable ?

SECTION 5 — SCORING
Système de score détaillé :
- Points par élément éliminé
- Multiplicateurs de combo (x2, x3, x5...)
- Bonus de temps
- Étoiles (1, 2, 3) selon performance""")

    # ── Fighting / Beat'em Up ──
    elif is_fighting:
        sections.append("""SECTION 2 — SYSTÈME DE COMBAT
Mécaniques de combat avec valeurs précises :
- Attaque légère : dégâts, frames d'animation, portée
- Attaque lourde : dégâts x2, frames plus lentes, knockback
- Combo : séquences de touches et multiplicateurs (ex: L+L+H = x1.5 dégâts)
- Blocage : réduction dégâts %, timing de parfait blocage (parry)
- Esquive : invincibility frames, distance de roll

SECTION 3 — ENNEMIS & BOSS
Archétypes avec move sets :
- Grunttype rapide, tank lent, mage à distance, boss avec 3 phases
- Pour chaque boss : patterns, tells visuels, fenêtres de punition

SECTION 4 — PROGRESSION
- Système de XP et déblocage de compétences
- Améliorations permanentes entre les niveaux
- Difficulté adaptative selon les performances du joueur""")

    # ── Survival / Roguelike ──
    elif is_survival:
        sections.append("""SECTION 2 — GESTION DES RESSOURCES
Ressources clés avec équilibrage :
- Santé : régénération, max HP, sources de heal
- Énergie/Stamina : consommation par action, régénération
- Munitions ou ressources d'attaque
- Nourriture ou timer de survie (si applicable)

SECTION 3 — GÉNÉRATION PROCÉDURALE
Règles de génération :
- Structure des salles/zones (dimensions, connexions)
- Densité d'ennemis par zone selon la profondeur
- Distribution du loot (rareté vs profondeur)
- Événements spéciaux (salle trésor, salle piège, mini-boss)

SECTION 4 — MÉTA-PROGRESSION (Roguelike)
Améliorations permanentes entre les runs :
- 5 à 8 upgrades débloquables avec coût et effet
- Personnages/builds alternatifs
- Malédictions et bénédictions (risque/récompense)
- Synergies d'items à découvrir

SECTION 5 — BOSS & ÉLITE ENNEMIS
- Boss par zone avec phases et mécaniques uniques
- Ennemis élite (version améliorée avec icône/couleur) : stats x2, drop garantis
- Patterns d'attaque inspirés de : The Binding of Isaac, Dead Cells, Hades""")

    # ── Default (genre non reconnu) ──
    else:
        sections.append(f"""SECTION 2 — MÉCANIQUES SPÉCIFIQUES AU GENRE "{gp.genre_principal.upper()}"
Décris les mécaniques fondamentales propres à ce type de jeu :
- Système d'action principal du joueur
- Obstacles et défis principaux
- Système de progression
- Interactions clés entre les éléments du jeu

SECTION 3 — ENNEMIS & BOSS
3 types d'ennemis + 1 boss avec comportements détaillés et valeurs numériques.

SECTION 4 — POWER-UPS & RÉCOMPENSES
5 power-ups ou collectibles avec effets et valeurs précis.

SECTION 5 — ÉQUILIBRAGE
Valeurs de départ et courbe de progression sur la durée de jeu.""")

    # ── Section interactions environnementales — s'applique à TOUS les genres ──
    sections.append(f"""SECTION INTERACTIONS — MÉCANIQUES ENVIRONNEMENTALES
Cette section s'applique à TOUS les genres. Chaque type de jeu peut et doit intégrer
des interactions environnementales adaptées à son univers. Sélectionne 3 à 5 types parmi
le catalogue ci-dessous en les adaptant au genre "{gp.genre_principal} / {gp.sous_genre}".

CATALOGUE UNIVERSEL — interprète chaque type selon ton genre :

A) LEVIER / SWITCH (interaction E ou proximité automatique)
   Concept : activer/désactiver un mécanisme du monde
   → Platformer : levier ouvre une porte, active un pont, coupe des piques
   → Shooter spatial : bouton lance une tourelle alliée, ouvre un passage entre astéroïdes
   → RPG : levier actionne un ascenseur, ouvre une trappe secrète
   → Tower defense : switch redirige les ennemis vers un autre chemin
   → Racing : bouton active un raccourci, déclenche un boost pad
   → Puzzle : switch inverse la gravité d'une zone, change la couleur des blocs

B) PLAQUE DE PRESSION (activation au contact du joueur ou d'un objet)
   Concept : déclencheur persistant ou momentané lié à la position physique
   → Platformer : déclenche l'apparition de pièces, ouvre une porte temporaire
   → Shooter : zone d'activation d'un bouclier, beacon qui régénère les munitions
   → RPG : piège (fléchettes, chute de blocs), ou déclencheur de loot caché
   → Puzzle : les plaques doivent toutes être activées simultanément pour progresser
   → Arcade/runner : boost de vitesse, zone de multiplication de score
   → Tower defense : ralentisseur d'ennemis, zone d'amplification des dégâts

C) COFFRE / CONTENEUR / RAVITAILLEMENT (interaction E)
   Concept : récompense cachée à découvrir, encourage l'exploration
   → Platformer / RPG / Dungeon : coffre trésor, coffre piégé (ennemi sort)
   → Shooter spatial : épave de vaisseau qui contient des munitions ou un power-up
   → Tower defense : caisse de ressources cachée, bonus d'or
   → Survival : caisses de ravitaillement (nourriture, armes, matériaux)
   → Racing : boîte mystère qui donne un item spécial (comme Mario Kart)
   → Puzzle : boîte qui révèle un indice ou une pièce manquante

D) ZONE VERROUILLÉE + CONDITION DE DÉVERROUILLAGE
   Concept : un passage bloqué qui nécessite de remplir une condition d'abord
   → Platformer : porte + clé colorée, portail + X ennemis à tuer pour l'ouvrir
   → Shooter : bouclier ennemi désactivé en détruisant ses générateurs
   → RPG : zone dont l'accès nécessite un badge, un niveau min, ou un PNJ particulier
   → Tower defense : vague bonus débloquée en construisant X tours d'un type
   → Puzzle : zone débloquée quand toutes les plaques sont activées dans l'ordre
   → Survival : zone sécurisée débloquée après avoir tué tous les ennemis alentour

E) TÉLÉPORTEUR / WARP / PORTAIL
   Concept : déplacement instantané vers un autre point — crée de la verticalité/shortcuts
   → Platformer / Adventure : portail menant à une zone bonus ou un raccourci
   → Shooter spatial : warp gate entre zones, portail d'urgence vers la base
   → RPG : pierre de téléportation vers les villes déjà visitées
   → Survival / Roguelike : escalier/portail vers le niveau suivant
   → Racing : portail raccourci avec risque associé (narrow passage)
   → Tower defense : portail d'entrée alternatif des ennemis (surprise)

F) BOUTON / INTERRUPTEUR TEMPORISÉ
   Concept : l'effet est limité dans le temps, crée de l'urgence et du skill
   → Platformer : pont apparu pendant 5s, plateforme mouvante activée
   → Shooter : bouclier temporaire, ralenti (bullet time) de 3s
   → Puzzle : portes qui restent ouvertes le temps que le joueur traverse
   → RPG : mécanisme d'une salle à activer avant le boss
   → Racing : boost pad qui dure 2s, nitro station
   → Tower defense : buff d'attaque de 10s pour toutes les tours

G) PNJ INTERACTIF (marchand, guide, allié, ennemi neutre)
   Concept : personnage qui enrichit l'univers, donne des ressources ou des infos
   → RPG / Adventure : marchand (acheter/vendre), guide (hint sur le niveau), quêteur
   → Platformer : personnage piégé à sauver (bonus de score), marchand caché
   → Shooter : station de réparation habitée, pilote allié qui améliore le vaisseau
   → Tower defense : "architecte" qui vend des tours spéciales entre les vagues
   → Survival : survivant à rescaper, commerçant ambulant
   → Puzzle : personnage qui donne des indices payants

H) OBJET INTERACTIF PHYSIQUE (pousser, tirer, lancer)
   Concept : un objet du décor que le joueur peut déplacer — enrichit les puzzles
   → Platformer / Puzzle : caisse à pousser sur une plaque de pression
   → Shooter : barils explosifs à pousser vers les ennemis (ou à éviter)
   → RPG / Adventure : rocher à déplacer pour révéler un passage secret
   → Tower defense : barricade repositionnable par le joueur
   → Survival : meuble à déplacer pour bloquer une porte
   → Arcade : boule à diriger dans un objectif (pong-like inversé)

I) ZONE D'EFFET ENVIRONNEMENTALE (passif, pas de touche requise)
   Concept : une zone du niveau qui modifie constamment le joueur ou les entités
   → Platformer : vent (pousse le joueur), eau (ralentit), feu (dégâts/s), glace (glisse)
   → Shooter : nébuleuse (réduit la visée), champ de gravité (attire les balles)
   → RPG : zone de malédiction (stats réduites), zone de régénération (heal/s)
   → Tower defense : terrain difficile (ennemis ralentis), marécage, lave
   → Racing : route glissante, zone de boue, asphalte sec (boost naturel)
   → Survival : zone radioactive (dégâts continus), abri (protection des ennemis)

INSTRUCTIONS POUR CHAQUE INTERACTION CHOISIE :
Fournis, pour chacune des 3 à 5 interactions sélectionnées :
1. Nom adapté à l'univers du jeu (ex: "Réacteur d'urgence" plutôt que "levier" dans un space shooter)
2. Description visuelle : couleur, forme, animation d'état actif/inactif
3. Condition d'activation : touche E (si proximity), contact automatique, ou condition externe
4. Effet précis avec valeurs : ce qui change, quelles variables, durée si temporisé
5. Feedback : particules (couleur, nombre), sfx.play(fréquence, durée, type), animation
6. Position dans le niveau : optionnel (exploration récompensée) ou obligatoire (progression)
7. Lien avec d'autres systèmes du jeu (score, vies, ennemis, portes, etc.)

RÈGLE FONDAMENTALE : chaque interaction doit enrichir le gameplay de ce genre précis.
Une interaction qui ne fait que décorer sans impact sur les décisions du joueur ne sert à rien.
Préfère 3 interactions profondes et bien reliées au reste du jeu à 5 interactions superficielles.""")

    # ── Section universelle finale : Juice & Game Feel ──
    sections.append("""SECTION FINALE — JUICE & GAME FEEL
Donne 5 recommandations concrètes pour rendre le jeu fun et satisfaisant :
1. Feedback visuel sur les actions clés (avec valeurs : durée en ms, amplitude en px)
2. Screen shake : quand, intensité (amplitude en px), durée (frames)
3. Hit pause / hitstop : durée en frames sur les coups importants
4. Particules : nombre, vitesse, couleurs recommandées pour ce genre
5. Progression du score : multiplicateur, combo, affichage flottant

Ces recommandations doivent être directement implémentables en JavaScript Canvas.""")

    return "\n\n".join(sections)


def _fallback_logics(genre_profile: GenreProfile) -> str:
    """Fallback minimal si l'appel API échoue."""
    genre = (genre_profile.genre_principal or "").lower()
    mecaniques = "\n".join(f"- {m}" for m in genre_profile.mecaniques_obligatoires[:5])

    # Interactions adaptées au genre pour le fallback
    is_shooter  = any(g in genre for g in ["shoot", "space", "bullet", "shmup"])
    is_rpg      = any(g in genre for g in ["rpg", "role", "adventure", "dungeon"])
    is_puzzle   = any(g in genre for g in ["puzzle", "match", "tetris"])
    is_td       = any(g in genre for g in ["tower", "defense"])
    is_survival = any(g in genre for g in ["survival", "survie", "rogue"])

    if is_shooter:
        interactions = """INTERACTIONS ENVIRONNEMENTALES :
- Station de réparation : zone verte, contact automatique, restaure 1 HP, cooldown 15s
- Beacon de puissance : plaque bleue clignotante, active x2 dégâts pendant 8s
- Warp gate : portail animé, téléporte le vaisseau vers un point de sortie du niveau
- Épave : objet E, révèle des munitions ou un power-up caché"""
    elif is_rpg:
        interactions = """INTERACTIONS ENVIRONNEMENTALES :
- Coffre : objet E, 80% loot normal / 15% rare / 5% piégé (ennemi)
- Levier : objet E, ouvre une porte verrouillée ou active un ascenseur
- Marchand PNJ : objet E, ouvre un menu d'achat (3 items aléatoires)
- Plaque secrète : contact, révèle un passage menant à une zone bonus"""
    elif is_puzzle:
        interactions = """INTERACTIONS ENVIRONNEMENTALES :
- Plaque de pression : contact, doit être maintenue pour garder une porte ouverte
- Switch : objet E ou contact, inverse un état (blocs apparaissent/disparaissent)
- Bouton temporisé : activer puis traverser le passage avant qu'il se referme (5s)
- Zone d'effet : ralentit le temps (bullet-time) pour résoudre une séquence"""
    elif is_td:
        interactions = """INTERACTIONS ENVIRONNEMENTALES :
- Switch de chemin : objet E, redirige les ennemis vers un couloir alternatif
- Caisse de ressources : objet E, +50 or bonus (1 fois par vague)
- Zone de buff : plaque jaune, amplifie les tours dans un rayon de 80px (+25% dégâts)
- Barricade : objet E, bloque un passage pendant 10s (cooldown 30s)"""
    elif is_survival:
        interactions = """INTERACTIONS ENVIRONNEMENTALES :
- Caisses de ravitaillement : objet E, contient soin + munitions + matériau aléatoire
- Porte barricadable : objet E, bloque l'entrée ennemie pendant 20s
- Zone sécurisée : contour bleu, régénère 1HP/s tant que le joueur y reste
- Levier d'alarme : objet E, déclenche une vague ennemie bonus en échange d'un gros loot"""
    else:
        interactions = """INTERACTIONS ENVIRONNEMENTALES :
- Levier : objet E, active/désactive un mécanisme (porte, piège, plateforme)
- Plaque de pression : contact, fait apparaître des pièces ou ouvre un passage temporaire
- Coffre : objet E, révèle un power-up ou un bonus de score (utilisable une fois)
- Zone d'effet : zone colorée au sol, applique un effet passif (boost vitesse, regen, dégâts)"""

    return f"""GAME LOGICS — {genre_profile.genre_principal.upper()}

ENNEMIS DE BASE :
- Ennemi basique : 1 HP, vitesse 80px/s, 10 points au kill
- Ennemi rapide : 1 HP, vitesse 150px/s, 20 points au kill
- Ennemi tank : 3 HP, vitesse 40px/s, 50 points au kill
- Elite : 5 HP, vitesse 100px/s, tire des projectiles, 100 points au kill
- Boss : 20 HP, 3 phases (100%, 60%, 30% HP), 1000 points au kill

MÉCANIQUES CLÉS :
{mecaniques}

POWER-UPS :
- Bouclier : invincibilité 5 secondes
- Vitesse : vitesse joueur +50% pendant 8 secondes
- Multiplicateur x2 : double les points pendant 10 secondes

{interactions}

ÉQUILIBRAGE :
- Score : +10 points par seconde de survie
- Difficulté : vitesse ennemis +10% toutes les 30 secondes
- Spawn : 1 ennemi/s au départ, +0.5/s toutes les 30s

GAME FEEL :
- Screen shake sur hit : 3px pendant 200ms
- Particules mort ennemi : 8 particules, vitesse aléatoire 50-150px/s
- Flash joueur sur dommage : 500ms clignotement rouge"""


@with_fallback(None)
def _call_section(prompt: str) -> str:
    """Appel focalisé sur une seule section — prompt court, réponse ciblée."""
    return call_claude(prompt, system=SYSTEM, max_tokens=4000, temperature=0.5)

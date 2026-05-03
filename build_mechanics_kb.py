"""
build_mechanics_kb.py — Populates the ChromaDB "mechanics_kb" collection
with mechanics from classic games by genre.

Usage:
    python build_mechanics_kb.py

The search_mechanics(genre, query, n=3) function is exportable and used
by agent_intelligence_genre.py to enrich the analysis.
"""

import os
import sys

# ─── Base de connaissance statique des jeux par genre ────────────────────────

GAMES_KB = [
    # ─── PLATFORMER ───────────────────────────────────────────────────────────
    {
        "genre": "platformer",
        "game_name": "Super Mario 64",
        "publisher": "Nintendo",
        "year": 1996,
        "document": """SUPER MARIO 64 — Platformer 3D de référence
CORE LOOP : Explorer → Trouver étoile → Étoile collectée → Nouvelle zone débloquée
MÉCANIQUES CORE :
- Triple saut, long jump, wall jump : combinaisons de mouvements fluides
- Momentum conservé : vitesse accumulée pour les sauts longs
- Hub central (Château Peach) avec portails vers les mondes
- 120 étoiles à collecter, progression non-linéaire
- Caméra libre contrôlée séparément (révolutionnaire à l'époque)
GAME FEEL :
- Son distinct pour chaque type de saut (audio feedback immédiat)
- Écrasement visuel du personnage à l'atterrissage (squash & stretch)
- Animations de transition fluides entre états
LEVEL DESIGN :
- Chaque niveau = sandbox avec 6-7 étoiles à obtenir différemment
- Progression ouverte : pas besoin de tout compléter pour avancer
- Secrets cachés récompensant l'exploration
FUN FACTOR : Liberté totale de mouvement, maîtrise progressive du mouvement
PIÈGES D'IMPLÉMENTATION :
- Caméra 3D complexe à gérer (frustration si mal orientée)
- Hitbox de plateforme imprécise = frustration joueur
- Trop de collectibles = dilution de la récompense""",
    },
    {
        "genre": "platformer",
        "game_name": "Celeste",
        "publisher": "Maddy Makes Games",
        "year": 2018,
        "document": """CELESTE — Platformer de précision moderne
CORE LOOP : Tenter salle → Mourir → Réapparaître instantanément → Comprendre le pattern → Réussir
MÉCANIQUES CORE :
- Dash directionnel (8 directions) rechargeable sur le sol ou certains objets
- Escalade de mur (grip limité)
- Coyote time : sauter une fraction de seconde après le bord
- Jump buffering : input de saut mémorisé avant l'atterrissage
- Fraises optionnelles pour les joueurs cherchant le défi
GAME FEEL :
- Réapparition instantanée (< 0.5s) : élimine la frustration de la mort
- Particules abondantes sur dash et atterrissage
- Musique qui s'adapte au succès (layers additifs)
- Screen shake calibré : impactant sans être nauséeux
LEVEL DESIGN :
- Progression de difficulté courbe: normal → difficile → extrême (B-sides)
- Chaque salle enseigne une nouvelle mécanique avant de la combiner
- Checkpoints généreux dans la progression principale
FUN FACTOR : Flow parfait grâce au cycle mort/réapparition rapide, maîtrise du dash
PIÈGES D'IMPLÉMENTATION :
- Coyote time mal calibré = sensation de "vol" ou de rigidité
- Pas de jump buffer = inputs ratés perçus comme des bugs
- Dash trop lent = frustration, trop rapide = perte de contrôle""",
    },
    {
        "genre": "platformer",
        "game_name": "Crash Bandicoot",
        "publisher": "Naughty Dog / Sony",
        "year": 1996,
        "document": """CRASH BANDICOOT — Platformer linéaire avec couloir 3D
CORE LOOP : Avancer → Éviter obstacles → Casser caisses → Atteindre la fin du niveau
MÉCANIQUES CORE :
- Spin attack (attaque latérale circulaire)
- Corps-à-corps ou saut sur les ennemis
- Aku Aku : masque protecteur (3 masques = invincibilité temporaire)
- Caisses TNT (timing) vs caisses normales (spin/saut)
- Wumpa fruits : 100 = vie supplémentaire
GAME FEEL :
- Death animation exagérée et comique (renforce l'arcade feel)
- Sons distincts pour chaque type de caisse
- Vibration du contrôleur calibrée
LEVEL DESIGN :
- Couloir 3D semi-linéaire : illusion de 3D avec gameplay 2D
- Bonus stages pour les gemmes cachées
- Niveaux thématiques variés (jungle, usine, ruines, glace)
FUN FACTOR : Satisfaction de casser des caisses, humour visuel, challenge progressif
PIÈGES D'IMPLÉMENTATION :
- Profondeur 3D difficile à lire pour les sauts (caisses en profondeur)
- Niveaux trop longs sans checkpoint = frustration""",
    },
    {
        "genre": "platformer",
        "game_name": "Hollow Knight",
        "publisher": "Team Cherry",
        "year": 2017,
        "document": """HOLLOW KNIGHT — Metroidvania atmosphérique
CORE LOOP : Explorer → Mourir → Récupérer son âme (geo) → Débloquer compétence → Explorer plus loin
MÉCANIQUES CORE :
- Nail (épée) : attaques dans 4 directions + pogo sur ennemis/sols
- Soul system : tuer des ennemis charge la jauge, dépensée pour soins ou sorts
- Charms : système de personnalisation avec slots et combinaisons
- Fast travel limité (via cartes à acheter)
- Shade : fantôme laissé à la mort, récupérer = regagner sa monnaie
GAME FEEL :
- Impact du nail accompagné de freeze frame (2-3 frames)
- Particules et effets de lumière sur les sorts
- Ambiance sonore oppressante mais cohérente
LEVEL DESIGN :
- Monde interconnecté sans chargement visible
- Backtracking récompensé par nouvelles compétences
- Boss fights avec phases distinctes et patterns apprenables
FUN FACTOR : Exploration récompensante, lore mystérieux, combat technique satisfaisant
PIÈGES D'IMPLÉMENTATION :
- Monde trop grand sans map = joueur perdu (frustration)
- Hitbox imprécise du nail = frustration en combat
- Difficulté des boss incompatible avec la progression narrative""",
    },
    {
        "genre": "platformer",
        "game_name": "Mega Man X",
        "publisher": "Capcom",
        "year": 1993,
        "document": """MEGA MAN X — Platformer d'action avec boss et armes volées
CORE LOOP : Sélectionner stage → Traverser niveau → Battre boss → Récupérer son arme → Exploiter faiblesse suivante
MÉCANIQUES CORE :
- Wall slide et wall jump : mobilité verticale
- Dash horizontal : traverser rapidement, éviter projectiles
- Armes acquises sur les boss (8 armes distinctes)
- Capsules de vie : upgrades collectibles cachés dans les niveaux
- Charge shot : maintenir feu pour projectile puissant
GAME FEEL :
- Dash ultra-réactif (frame 1)
- Hit stop sur les touches importantes
- Musique mémorable par stage (renforce l'identité)
LEVEL DESIGN :
- 8 stages sélectionnables librement, ordre optimal suggéré par les faiblesses
- Secrets encouragent le backtracking avec nouvelles compétences
- Intro stage = tutoriel implicite de toutes les mécaniques
FUN FACTOR : Expression du skill via le dash, satisfaction de trouver les faiblesses, rejouabilité
PIÈGES D'IMPLÉMENTATION :
- Projectiles ennemis trop nombreux = wallhack impossible
- Charge shot trop dominant supprime la variété des armes""",
    },

    # ─── RPG ──────────────────────────────────────────────────────────────────
    {
        "genre": "rpg",
        "game_name": "Diablo II",
        "publisher": "Blizzard",
        "year": 2000,
        "document": """DIABLO II — Action-RPG dungeon crawler fondateur
CORE LOOP : Tuer → Looter → Améliorer build → Tuer plus vite → Rejouer en difficulté supérieure
MÉCANIQUES CORE :
- Point-and-click : déplacement et attaque sur la même touche
- 5 classes avec arbres de compétences distincts
- Item drops randomisés : rareté (Normal/Magic/Rare/Set/Unique)
- Affixes sur les items : combinaisons aléatoires de stats
- Respawn des monstres à chaque session
GAME FEEL :
- Satisfying kill feedback : son, flash, corpse pile
- Tintement distinct selon la rareté du loot
- Gore exagéré renforçant l'impact des coups
LEVEL DESIGN :
- Donjons procéduraux semi-aléatoires à chaque partie
- Acts progressifs avec boss gardant le portail vers le suivant
- Rune Words et crafting pour les vétérans
FUN FACTOR : Boucle de loot addictive, personnalisation du build, rejouabilité infinie
PIÈGES D'IMPLÉMENTATION :
- Loot trop rare = frustration, trop fréquent = dévaluation
- Classes déséquilibrées brisent la diversité des builds
- Inventaire limité obligeant des choix frustrants""",
    },
    {
        "genre": "rpg",
        "game_name": "The Legend of Zelda: Breath of the Wild",
        "publisher": "Nintendo",
        "year": 2017,
        "document": """ZELDA BREATH OF THE WILD — Action-adventure open world
CORE LOOP : Explorer → Résoudre puzzle → Obtenir ressource → Craft équipement → Explorer davantage
MÉCANIQUES CORE :
- Physique sandbox : objets interagissent, feu se propage, métal conduit
- Armes cassables : forçant renouvellement de l'équipement
- 4 runes : magnèse, cryonis, bombe, Stasis — outils polyvalents
- Cuisine : recettes avec effets gameplay (endurance, résistance, attaque)
- Parapente : traversée des zones et descente des hauteurs
GAME FEEL :
- Physique convaincante donnant vie au monde
- Sons environnementaux réactifs (pluie, vent, feu)
- Découverte récompensée à chaque sommet
LEVEL DESIGN :
- 900 Korogus secrets, 120 sanctuaires : densité d'activités
- Monde ouvert sans ordre imposé (liberté totale dès le début)
FUN FACTOR : Liberté totale, solutions multiples à chaque problème, discovery constant
PIÈGES D'IMPLÉMENTATION :
- Durabilité des armes mal calibrée = frustration constante
- Monde trop grand sans objectifs clairs = errance""",
    },
    {
        "genre": "rpg",
        "game_name": "Dark Souls",
        "publisher": "FromSoftware",
        "year": 2011,
        "document": """DARK SOULS — Action-RPG hardcore avec apprentissage par l'échec
CORE LOOP : Mourir → Réapprendre pattern ennemi → Maîtriser combat → Progresser → Boss → Nouveau territoire
MÉCANIQUES CORE :
- Stamina bar : limite les attaques, esquives et blocages
- Roulade d'esquive (invincibility frames au début)
- Estus Flask : soins limités, rechargés aux feux de camp
- Âmes : monnaie/XP perdue à la mort, récupérable une fois
- Deux mains : augmente les stats d'arme, change les movesets
GAME FEEL :
- Hit stop appuyé : chaque coup semble peser
- Parry/riposte : reward du skill avec animation spectaculaire
- Ambiance sonore minimaliste renforçant la tension
LEVEL DESIGN :
- Monde interconnecté sans fast travel initial
- Raccourcis révélés progressivement (sentiment de maîtrise)
- Boss fights = tests des compétences accumulées
FUN FACTOR : Satisfaction profonde de surmonter un challenge difficile, exploration dense
PIÈGES D'IMPLÉMENTATION :
- Difficulté sans fairness = frustration pure (pas de fun)
- Controls lourds sans apprentissage guidé = abandon""",
    },
    {
        "genre": "rpg",
        "game_name": "Stardew Valley",
        "publisher": "ConcernedApe",
        "year": 2016,
        "document": """STARDEW VALLEY — RPG farming/social
CORE LOOP : Planter → Arroser → Récolter → Vendre → Améliorer ferme → Approfondir relations sociales
MÉCANIQUES CORE :
- Gestion de l'énergie journalière (limite les actions par jour)
- Cycle saisonnier : certaines cultures seulement en certaines saisons
- Relations avec PNJ : cadeaux, dialogues → déblocages de contenu
- Mine : combat basique, descente d'étages, ressources craft
- Crafting : outils améliorés, machines de traitement
GAME FEEL :
- Sons apaisants (sons de récolte, musique douce)
- Progression visible de la ferme (satisfaction visuelle)
- Fêtes saisonnières : récompenses sociales
LEVEL DESIGN :
- Pas de game over, progression très permissive
- Contenu infini via mariage, amitié, collection
FUN FACTOR : Relaxation, progression constante, attachement aux PNJ
PIÈGES D'IMPLÉMENTATION :
- Journée trop courte = frustration (pas le temps de tout faire)
- Min-maxing détruit le côté détendu si trop optimisé""",
    },
    {
        "genre": "rpg",
        "game_name": "Final Fantasy VII",
        "publisher": "Square",
        "year": 1997,
        "document": """FINAL FANTASY VII — JRPG au tour par tour narratif
CORE LOOP : Progresser dans l'histoire → Combats aléatoires → Farmer XP/Gil → Équiper Matérias → Boss
MÉCANIQUES CORE :
- ATB (Active Time Battle) : jauge se remplit, action dès qu'elle est pleine
- Matéria system : gemmes équipables sur armes/armures pour sorts et compétences
- Limit Breaks : attaque dévastatrice chargée par les dégâts reçus
- 3 personnages par combat parmi un roster de 9
- Invocations : summons visuellement impressionnants
GAME FEEL :
- Animations de combat et d'invocation spectaculaires
- Musique iconique de Nobuo Uematsu renforçant l'émotion
- Narration forte portée par les personnages
LEVEL DESIGN :
- Monde 3D pré-rendu avec points d'intérêt
- Donjons thématiques alignés avec la narration
FUN FACTOR : Narration émotionnelle, personnalisation via matérias, boss mémorables
PIÈGES D'IMPLÉMENTATION :
- Combat trop lent sans option de vitesse = ennui
- Grinding obligatoire si progression sous-optimale""",
    },

    # ─── SHOOTER ──────────────────────────────────────────────────────────────
    {
        "genre": "shooter",
        "game_name": "Space Invaders",
        "publisher": "Taito",
        "year": 1978,
        "document": """SPACE INVADERS — Shoot'em up arcade fondateur
CORE LOOP : Tirer → Éliminer ligne ennemie → Ennemis s'accélèrent → Survivre → Score maximum
MÉCANIQUES CORE :
- Tir unique : un seul projectile en vol à la fois (limitation = challenge)
- Bunkers destructibles : abris qui s'érodent sous les tirs
- Ennemis descendent progressivement : pression temporelle
- Vaisseau UFO bonus : apparaît aléatoirement pour score bonus
- Accélération des ennemis : moins il en reste, plus ils sont rapides
GAME FEEL :
- Son qui s'accélère avec la descente ennemie (tension musicale)
- Tir unique = décisions tactiques sur le timing
LEVEL DESIGN :
- Vagues identiques avec difficulté croissante (vitesse + motifs)
- Pas de fin : score infini jusqu'à la mort
FUN FACTOR : Tension croissante, score beating, pattern recognition
PIÈGES D'IMPLÉMENTATION :
- Trop de projectiles ennemis = impossible à esquiver
- Absence de scoring lisible démotive""",
    },
    {
        "genre": "shooter",
        "game_name": "Galaga",
        "publisher": "Namco",
        "year": 1981,
        "document": """GALAGA — Shoot'em up avec capture et double vaisseau
CORE LOOP : Esquiver formation → Tirer ennemis → Gérer double vaisseau → Bonus stages → Score
MÉCANIQUES CORE :
- Ennemis arrivent en formation choreographiée avant de se mettre en place
- Boss Galaga : peut capturer le vaisseau avec un rayon (gimmick unique)
- Double vaisseau : se laisser capturer puis libérer = double canon
- Bonus stages : tuer 40 ennemis sans mourir pour bonus score
- Motifs de piqués variés selon le type d'ennemi
GAME FEEL :
- Formations ennemies visuellement lisibles (couleurs distinctes)
- Son de capture dramatique
LEVEL DESIGN :
- Stages 1-∞ avec difficulté croissante
- Alternance stages normaux / bonus stages
FUN FACTOR : Risque/récompense du double vaisseau, formation lisible, pattern recognition
PIÈGES D'IMPLÉMENTATION :
- Double canon trop fort supprime le challenge
- Formation peu lisible = confus pour le joueur""",
    },
    {
        "genre": "shooter",
        "game_name": "Ikaruga",
        "publisher": "Treasure",
        "year": 2001,
        "document": """IKARUGA — Shoot'em up avec système de polarité
CORE LOOP : Analyser couleurs → Switcher polarité → Absorber balles alliées → Tirer ennemi opposé → Chaînes
MÉCANIQUES CORE :
- Polarité noir/blanc : absorber les balles de même couleur = recharge la barre spéciale
- Tirer sur ennemi de couleur opposée = double dégâts
- Chaînes : tuer 3 ennemis de même couleur consécutivement = multiplicateur de score
- Homing laser chargé : attaque tous les ennemis
GAME FEEL :
- Contraste visuel fort noir/blanc (lisibilité maximale)
- Son d'absorption satisfaisant
LEVEL DESIGN :
- Niveaux mémorisables (bullet hell prévisible, pas aléatoire)
- Boss fights requérant alternance rapide de polarité
FUN FACTOR : Gameplay cérébral unique, sentiment de maîtrise des patterns, scoring profond
PIÈGES D'IMPLÉMENTATION :
- Trop de balles à l'écran = illisible même avec la polarité
- Système de polarité mal expliqué = confusion totale""",
    },
    {
        "genre": "shooter",
        "game_name": "Geometry Wars",
        "publisher": "Bizarre Creations",
        "year": 2003,
        "document": """GEOMETRY WARS — Twin-stick shooter arena
CORE LOOP : Survivre → Tuer ennemis → Multiplier score → Exploser bombe quand submergé → Recommencer
MÉCANIQUES CORE :
- Twin-stick : stick gauche = déplacement, stick droit = direction de tir (360°)
- Bombes en nombre limité : nettoie l'écran, utilisées stratégiquement
- Multiplicateur de score : grimpe en tuant sans mourir
- Grille déformable : les explosions créent des ondulations visuelles
- Ennemis variés avec comportements distincts (seekers, snakers, repulsors...)
GAME FEEL :
- Effets de particules explosifs et colorés sur chaque mort
- Grille déformable : feedback physique de l'action
- Musique électronique pulsante
LEVEL DESIGN :
- Arena fermée : pression spatiale croissante
- Spawn waves progressives jusqu'à saturation de l'écran
FUN FACTOR : Intensité visuelle et sonore, risk/reward du multiplicateur, sessions courtes
PIÈGES D'IMPLÉMENTATION :
- Trop d'ennemis à l'écran = illisible
- Bombe trop rare = frustration, trop commune = trivialisation""",
    },
    {
        "genre": "shooter",
        "game_name": "Enter the Gungeon",
        "publisher": "Devolver Digital",
        "year": 2016,
        "document": """ENTER THE GUNGEON — Roguelite bullet hell dungeon crawler
CORE LOOP : Explorer chambre → Éviter bullets patterns → Tuer → Loooter armes → Boss → Étage suivant → Mourir → Recommencer
MÉCANIQUES CORE :
- Dodge roll : invincibility frames pendant la roulade
- Centaines d'armes aux comportements uniques
- Tables retournables : couverture tactique
- Blanks : effacent les bullets à l'écran (ressource précieuse)
- Synergies secrètes entre armes et items
GAME FEEL :
- Impact fort de chaque arme (sons, recoil visuel)
- Bullet patterns lisibles malgré leur densité (couleurs distinctes)
- Run mémorable grâce aux armes aléatoires
LEVEL DESIGN :
- Génération procédurale des salles par étage
- Boss par étage avec patterns complexes
FUN FACTOR : Variété infinie des runs, synergies surprenantes, maîtrise du dodge roll
PIÈGES D'IMPLÉMENTATION :
- Trop d'armes inutiles dans le pool dilue les runs
- Hitbox joueur imprécise = frustration sur les bullets serrés""",
    },

    # ─── TOWER DEFENSE ────────────────────────────────────────────────────────
    {
        "genre": "tower_defense",
        "game_name": "Plants vs Zombies",
        "publisher": "PopCap",
        "year": 2009,
        "document": """PLANTS VS ZOMBIES — Tower defense accessible et stratégique
CORE LOOP : Collecter soleil → Planter défenses → Zombies arrivent en vagues → Survivre → Prochaine vague
MÉCANIQUES CORE :
- Ressource soleil : générée passivement et par plantes dédiées
- Lignes séparées : zombies avancent sur une des 5 lignes
- Plantes spécialisées : attaque (pois), ralentissement (givre), explosion (cerise)
- Carte de plantes : main limitée de plantes disponibles par niveau
- Cooldown sur chaque plante après plantation
GAME FEEL :
- Sons cartoonesques plaisants
- Feedback visuel fort quand un zombie est tué
- Humour omniprésent (noms des plantes/zombies)
LEVEL DESIGN :
- Introduction progressive de nouvelles plantes et zombies
- Environnements variés (jardin/nuit/piscine/toit) modifiant les règles
- Niveaux puzzle avec plantes pré-posées
FUN FACTOR : Accessibilité, humour, variété des stratégies, satisfaction de la défense parfaite
PIÈGES D'IMPLÉMENTATION :
- Vague trop soudaine sans warning = unfair
- Ressource soleil trop lente = jeu bloqué""",
    },
    {
        "genre": "tower_defense",
        "game_name": "Bloons TD 6",
        "publisher": "Ninja Kiwi",
        "year": 2018,
        "document": """BLOONS TD 6 — Tower defense profond avec upgrades multi-path
CORE LOOP : Placer tours → Gérer économie → Vague ennemie → Améliorer tours → Vague de boss → Victoire/défaite
MÉCANIQUES CORE :
- Arbres d'upgrades à 3 branches (top/middle/bottom), max 2 branches par tour
- Paragon : ultime d'une tour (level 100)
- Monkey Knowledge : méta-progression entre parties
- Heroes : unités uniques avec level automatique
- Eco farming : revenu passif via certaines tours
GAME FEEL :
- Effets visuels impressionnants sur les upgrades
- Satisfaction des tours qui nettoient des vagues entières
LEVEL DESIGN :
- Maps variées avec chemins multiples
- Modes de jeu distincts (difficile, impoppa, chimps)
FUN FACTOR : Profondeur du build, satisfaction du min-max, contenu très riche
PIÈGES D'IMPLÉMENTATION :
- Trop de tours = écran illisible
- Courbe de difficulté brutale en fin de partie""",
    },
    {
        "genre": "tower_defense",
        "game_name": "Kingdom Rush",
        "publisher": "Ironhide",
        "year": 2011,
        "document": """KINGDOM RUSH — Tower defense premium sur mobile
CORE LOOP : Placer 4 types de tours → Vague → Améliorer → Vague boss → Étoiles de niveau
MÉCANIQUES CORE :
- 4 types de base : archers, soldats (blocage corps-à-corps), mages, artillerie
- Upgrades visuellement distincts (tour change d'apparence)
- Pouvoirs actifs : météore, renfort de soldats (CD à gérer)
- Ennemis avec résistances : magiques, physiques, volants, blindés
- Recyclage des tours pour récupérer partiellement l'or
GAME FEEL :
- Animations de mort ennemies détaillées
- Sons de victoire satisfaisants par type de tour
LEVEL DESIGN :
- Chemins sinueux avec noeuds de placement fixes
- Ennemis avec timing de spawn calibré
FUN FACTOR : Stratégie claire, upgrade visuel satisfaisant, challenge accessible
PIÈGES D'IMPLÉMENTATION :
- Noeuds de placement mal positionnés = niveau impossible
- Un type de tour dominant rend les autres inutiles""",
    },
    {
        "genre": "tower_defense",
        "game_name": "Dungeon Defenders",
        "publisher": "Trendy Entertainment",
        "year": 2011,
        "document": """DUNGEON DEFENDERS — Tower defense avec action-RPG hybride
CORE LOOP : Phase build (placer défenses) → Phase combat (jouer en temps réel) → Loot → Améliorer → Niveau suivant
MÉCANIQUES CORE :
- Mana : ressource unique pour construire et améliorer les défenses
- 4 classes avec défenses distinctes (mage = tours magiques, soldat = barricades)
- Phase de construction vs phase de combat alternées
- Core crystal : à protéger absolument
- Coop 4 joueurs : chaque classe complète les autres
GAME FEEL :
- Hybride action/stratégie : jamais passif
- Loot feeding progression entre niveaux
LEVEL DESIGN :
- Maps avec chemins multiples forçant la diversité des défenses
FUN FACTOR : Hybridation originale action/TD, coop fun, loot addictif
PIÈGES D'IMPLÉMENTATION :
- Phase build trop lente ou trop courte rompt le rythme
- Défenses en dehors des chemins = inutiles""",
    },
    {
        "genre": "tower_defense",
        "game_name": "Orcs Must Die!",
        "publisher": "Robot Entertainment",
        "year": 2011,
        "document": """ORCS MUST DIE — Tower defense avec TPS et trappes au sol
CORE LOOP : Placer trappes (sol/mur/plafond) → Combattre en TPS → Orcs dans les pièges → Score de crânes
MÉCANIQUES CORE :
- Trappes physiques : orcs tombent dans des fosse, volent dans les escaliers
- Warlock = personnage jouable avec arme et sorts actifs
- Pièges synergiques : ralentisseur + dégâts = combo
- Système de crânes : score post-niveau pour débloquer upgrades
- Vies = nombre d'ennemis passant l'objectif (pas une barre de vie)
GAME FEEL :
- Physique des orcs : ragdoll satisfaisant
- Combos visuels spectaculaires (glace + éclair)
LEVEL DESIGN :
- Couloirs 3D avec chokepoints pour maximiser les trappes
FUN FACTOR : Action directe, physique fun, combo de pièges créatifs
PIÈGES D'IMPLÉMENTATION :
- Physique ragdoll coûteuse en performance
- Pièges invisibles depuis les angles de caméra = unfair""",
    },

    # ─── PUZZLE ───────────────────────────────────────────────────────────────
    {
        "genre": "puzzle",
        "game_name": "Tetris",
        "publisher": "Alexey Pajitnov / Nintendo",
        "year": 1989,
        "document": """TETRIS — Puzzle de tétrominos fondateur
CORE LOOP : Pièce tombe → Placer intelligemment → Compléter ligne → Ligne disparaît → Score → Vitesse augmente
MÉCANIQUES CORE :
- 7 pièces (tétrominos) avec rotations à 4 états
- T-spin : rotation en dernière seconde pour insérer dans des espaces serrés
- Hold piece : réserver une pièce pour plus tard
- Ghost piece : aperçu de la position finale
- Gravité : vitesse croissante par niveau
GAME FEEL :
- Lock delay : brève fenêtre pour repositionner avant le verrouillage
- Line clear : animation et son distincts selon 1-2-3-4 lignes
- Music qui s'accélère avec le niveau (Korobeiniki)
LEVEL DESIGN :
- Pas de niveaux : un seul espace infini qui s'accélère
- Guideline (Tetris Company) : spawn, ordre des pièces
FUN FACTOR : Accessibilité infinie, profondeur techniques avancées, tension croissante
PIÈGES D'IMPLÉMENTATION :
- RNG pièces non-pondéré = frustration (sacks O)
- Pas de ghost piece = impossible à haut niveau""",
    },
    {
        "genre": "puzzle",
        "game_name": "Portal",
        "publisher": "Valve",
        "year": 2007,
        "document": """PORTAL — Puzzle 3D avec portails interconnectés
CORE LOOP : Observer chambre → Comprendre la physique des portails → Placer orange/bleu → Traverser → Sortir
MÉCANIQUES CORE :
- Portail Gun : portails orange (entrée) et bleu (sortie), échangeables
- Conservation du momentum : vitesse entrante = vitesse sortante
- Objets lourds : activent boutons pour débloquer portes
- Cubes de compagnon : pousser, poser, transporter
- Turrets : ennemis à déjouer avec portails
GAME FEEL :
- Son de portail distinctif et satisfaisant
- Narration humoristique de GLaDOS récompense l'exploration
- "Now you're thinking with portals" = eureka moment
LEVEL DESIGN :
- Chambres isolées : une mécanique par chambre
- Progression du simple au complexe + contre-intuitif
FUN FACTOR : Eureka moments fréquents, humour, physique surprenante
PIÈGES D'IMPLÉMENTATION :
- Portail sur surface non-portable = frustration si pas expliqué
- Momentum complexe à simuler fidèlement""",
    },
    {
        "genre": "puzzle",
        "game_name": "The Witness",
        "publisher": "Thekla",
        "year": 2016,
        "document": """THE WITNESS — Puzzle d'exploration et de métaconnaissance
CORE LOOP : Découvrir panneau → Comprendre règle implicite → Tracer chemin → Réussir → Nouveau panneau → Généraliser règle
MÉCANIQUES CORE :
- Tous les puzzles = tracer un chemin sur une grille
- Règles variables par zone : jamais expliquées verbalement
- Puzzles environnementaux : la solution est dans le décor (ombre, son, lumière)
- Épiphanies : comprendre une règle = résoudre des dizaines de puzzles en chaîne
GAME FEEL :
- Silence et ambiance sonore naturelle (renforce la contemplation)
- Sentiment de découverte pure sans tutoriel
LEVEL DESIGN :
- 11 zones thématiques avec mécaniques distinctes
- Puzzles de fin = synthèse de toutes les règles apprises
FUN FACTOR : Plaisir intellectuel pur, épiphanies, exploration libre
PIÈGES D'IMPLÉMENTATION :
- Règles trop obscures sans indice = abandon
- Interface confuse dissimule la vraie mécanique""",
    },
    {
        "genre": "puzzle",
        "game_name": "Baba Is You",
        "publisher": "Hempuli",
        "year": 2019,
        "document": """BABA IS YOU — Puzzle méta avec règles manipulables
CORE LOOP : Lire les règles du niveau (blocs de texte) → Pousser les mots → Modifier les règles → Atteindre l'objectif
MÉCANIQUES CORE :
- Règles = blocs physiques : BABA IS YOU, FLAG IS WIN, WALL IS STOP
- Pousser un bloc mot = changer la règle : WALL IS WIN → toucher les murs gagne
- Multiples instances : jouer plusieurs personnages simultanément
- YOU peut devenir n'importe quel objet
- WIN peut être assigné à n'importe quel objet
GAME FEEL :
- Son de bloc poussé simple mais cohérent
- "Aha !" puissant quand la règle se comprend
LEVEL DESIGN :
- Niveaux compacts : solution souvent contre-intuitive
- Worlds thématiques introduisant des sous-ensembles de mécaniques
FUN FACTOR : Créativité illimitée, subversion totale des attentes, puzzles mémorables
PIÈGES D'IMPLÉMENTATION :
- Règles impossibles à implémenter en JS sans moteur dédié
- Logique de règles : nombreux edge cases complexes""",
    },
    {
        "genre": "puzzle",
        "game_name": "Monument Valley",
        "publisher": "ustwo",
        "year": 2014,
        "document": """MONUMENT VALLEY — Puzzle d'architecture impossible
CORE LOOP : Observer architecture → Tourner élément → Chemin impossible devient possible → Avancer → Niveau suivant
MÉCANIQUES CORE :
- Illusions d'optique : perspectives impossibles créant des chemins
- Rotation de blocs/plateformes pour aligner les niveaux
- Corbeaux : bloquent le passage, détournables
- Levier/bouton : ouvrent passages ou activent mécanismes
- Totem : compagnon que l'on positionne pour activer des éléments
GAME FEEL :
- Musique ambiante réactive aux actions
- Esthétique minimaliste pastel très soignée
- Feedback sonore doux pour chaque rotation
LEVEL DESIGN :
- Niveaux courts, narratif visuel sans dialogue
- Architecture inspirée d'Escher
FUN FACTOR : Beauté visuelle, puzzles accessibles mais satisfaisants, narration visuelle
PIÈGES D'IMPLÉMENTATION :
- Illusions d'optique 3D difficiles à rendre en 2D Canvas
- Trop court = sentiment d'inachevé""",
    },

    # ─── SURVIVAL ─────────────────────────────────────────────────────────────
    {
        "genre": "survival",
        "game_name": "Minecraft",
        "publisher": "Mojang",
        "year": 2011,
        "document": """MINECRAFT — Survival sandbox en voxels
CORE LOOP : Miner → Crafter → Construire abri → Survivre la nuit → Explorer → Progresser vers le End
MÉCANIQUES CORE :
- Crafting grid 3x3 : recettes à découvrir
- Gestion faim et vie : manger pour régénérer
- Cycle jour/nuit : danger la nuit (monstres)
- Biomes variés avec ressources uniques
- Redstone : électronique in-game
GAME FEEL :
- Sons ambiants par biome
- Feedback sonore de chaque bloc cassé/placé
- Satisfaction visuelle de construire
LEVEL DESIGN :
- Monde procédural infini
- Progression matériaux : bois → pierre → fer → or → diamant → netherite
FUN FACTOR : Liberté totale, créativité, survie accessible, progression claire
PIÈGES D'IMPLÉMENTATION :
- Génération procédurale coûteuse
- Sans objectif clair = joueur perdu""",
    },
    {
        "genre": "survival",
        "game_name": "Don't Starve",
        "publisher": "Klei Entertainment",
        "year": 2013,
        "document": """DON'T STARVE — Survival hardcore avec santé mentale
CORE LOOP : Récupérer ressources → Éviter monstres → Manger → Maintenir sanité → Survivre → Hiver
MÉCANIQUES CORE :
- 3 jauges : vie, faim, sanité (originalité)
- Sanité baisse dans le noir, près des monstres : hallucinations → ennemis invoqués
- Cycle saisonnier : ressources différentes, dangers différents
- Permadeath : mort = recommencer (roguelike)
- Artisanat découvert par crafting ou investigation
GAME FEEL :
- Esthétique Tim Burton cohérente
- Ambiance sonore angoissante renforcée par la sanité basse
LEVEL DESIGN :
- Monde semi-aléatoire avec biomes
- Bosses saisonniers : Deerclops en hiver
FUN FACTOR : Tension constante, esthétique unique, sanité originale, challenge réel
PIÈGES D'IMPLÉMENTATION :
- Jauge sanité sous-utilisée si pas de conséquences visuelles
- Permadeath sans run seed mémorisable = anti-fun""",
    },
    {
        "genre": "survival",
        "game_name": "The Long Dark",
        "publisher": "Hinterland Studio",
        "year": 2014,
        "document": """THE LONG DARK — Survival simulation dans le Grand Nord
CORE LOOP : Chercher ressources (nourriture, bois) → Gérer température → Éviter loups → Trouver abri → Dormir
MÉCANIQUES CORE :
- Température : hypothermie si trop exposé au froid
- Calories : se dépenser = brûler plus de calories
- Condition des objets : tous les items se dégradent
- Feu : indispensable, limité par le vent
- Loups : comportements réalistes (patrouille, traque, charge)
GAME FEEL :
- Sons de vent et de neige immersifs
- Visibilité réduite dans les tempêtes (tension)
LEVEL DESIGN :
- Zones ouvertes mais dangereuses
- Structures abandonnées pour se réchauffer
FUN FACTOR : Immersion extrême, tension de survie réelle, satisfaction de l'abri
PIÈGES D'IMPLÉMENTATION :
- Trop de jauges simultanées = micro-management fastidieux
- Mort aléatoire par loup = anti-fun""",
    },
    {
        "genre": "survival",
        "game_name": "Terraria",
        "publisher": "Re-Logic",
        "year": 2011,
        "document": """TERRARIA — Survival 2D action avec construction
CORE LOOP : Miner en profondeur → Trouver ressources → Forger équipement → Battre boss → Accéder nouveau biome
MÉCANIQUES CORE :
- 2D sandbox : construction libre + exploration verticale (profondeur = difficulté)
- Boss invocables : progression non-linéaire
- Hardmode : activé après Mur de Chair, double la difficulté
- Classes implicites : armes et armures orientent vers Mage/Guerrier/Ranger/Summoner
- Événements : invasions, Lune Sanguine, Eclipse
GAME FEEL :
- Feedback sonore satisfaisant pour chaque ennemi tué
- Variété visuelle des biomes (jungle, désert, enfer, espace)
LEVEL DESIGN :
- Verticale : surface → cavernes → souterrain → enfer
- Largeur : forêt → désert → toundra → jungle
FUN FACTOR : Progression très claire, boss mémorables, liberté de build
PIÈGES D'IMPLÉMENTATION :
- Monde généré trop petit = manque de variété
- Difficulté Hardmode trop brutale sans transition""",
    },
    {
        "genre": "survival",
        "game_name": "Subnautica",
        "publisher": "Unknown Worlds",
        "year": 2018,
        "document": """SUBNAUTICA — Survival sous-marin avec narration environnementale
CORE LOOP : Explorer océan → Collecter ressources → Crafter équipement → Explorer plus profond → Découvrir la lore
MÉCANIQUES CORE :
- Profondeur = pression = véhicule obligatoire pour atteindre les zones profondes
- Oxygène : jauge critique en plongée libre
- Biomes sous-marins : récif, grand récif, champignons, lave
- Bases sous-marines : construire habitat personnel
- Léviathans : monstres géants déclenchant l'horreur
GAME FEEL :
- Ambiance sonore sous-marine immersive
- Thalassophobie exploitée design de créatures
LEVEL DESIGN :
- Zone sécurisée de départ → danger progressivement croissant par profondeur
FUN FACTOR : Exploration mystérieuse, peur contrôlée, narration environnementale
PIÈGES D'IMPLÉMENTATION :
- Génération procédurale + océan = performance
- Sous l'eau : désorientation 3D sans repères""",
    },

    # ─── FIGHTING ─────────────────────────────────────────────────────────────
    {
        "genre": "fighting",
        "game_name": "Street Fighter II",
        "publisher": "Capcom",
        "year": 1991,
        "document": """STREET FIGHTER II — Fighting game fondateur du genre compétitif
CORE LOOP : Lire adversaire → Exécuter mouvement correct → Combo → Victoire de round → Match en 3 rounds
MÉCANIQUES CORE :
- 6 boutons : 3 poings (léger/moyen/fort) + 3 pieds
- Mouvements spéciaux : quarts de cercle + bouton (fireball)
- Super Meter (dans Super SF2 Turbo)
- Zones de priorité : chaque coup a startup/active/recovery
- Crouch tech, throw tech (défense)
GAME FEEL :
- Hit stop : freeze frames sur coups connectés (impact fort)
- Son distinctif par coup (punch, kick, hadouken)
- Voice acting iconique
LEVEL DESIGN :
- Arènes distinctes avec personnages associés
- Bouts contre 8-12 personnages pour atteindre le boss (Bison)
FUN FACTOR : Skill gap immense, matchmaking entre niveaux, personnages mémorables
PIÈGES D'IMPLÉMENTATION :
- Inputs précis difficiles (piano inputs)
- Frame data invisible = frustration débutants""",
    },
    {
        "genre": "fighting",
        "game_name": "Mortal Kombat II",
        "publisher": "Midway",
        "year": 1993,
        "document": """MORTAL KOMBAT II — Fighting game avec fatalities et gore
CORE LOOP : Combattre → Réduire HP → Finish Him → Fatality → Score → Personnage suivant
MÉCANIQUES CORE :
- Fatalities : finisher secret par personnage (codes cachés)
- 3 blocs : bas, milieu, haut
- Mouvements signature par personnage (Scorpion : harpoon, Sub-Zero : glace)
- Arcade Ladder : combattre 10 combattants + boss
- Friendships / Babalities : finishers humoristiques
GAME FEEL :
- Effets sanglants exagérés (gore = marketing)
- Sons d'impact gutturaux
- Voix off "FINISH HIM !"
LEVEL DESIGN :
- Arènes thématiques avec stages interactifs (pit, acid)
FUN FACTOR : Secrets, finishers, personnages iconiques, gore unique à l'époque
PIÈGES D'IMPLÉMENTATION :
- Mouvements secrets sans guide = non-découvrables
- Hit detection imprécise = unfair""",
    },
    {
        "genre": "fighting",
        "game_name": "Super Smash Bros Melee",
        "publisher": "Nintendo / HAL",
        "year": 2001,
        "document": """SUPER SMASH BROS MELEE — Platform fighter compétitif
CORE LOOP : Accumuler dégâts (%) sur adversaire → Coup de finisher éjecte en dehors de la scène → Vies → Victoire
MÉCANIQUES CORE :
- % de dommages : plus haut le %, plus on vole loin
- L-cancel : couper l'atterrissage d'une aerial attack (tech avancé)
- Wavedash : glissement au sol via airdodge
- Fastfall : descente rapide pendant le saut
- Shield, shield grab, spot dodge, roll dodge
GAME FEEL :
- Hitlag : freeze bref lors d'un coup fort
- Camera qui se dézoome lors des gros hits
- Effets de knockback visuellement lisibles
LEVEL DESIGN :
- Plateformes multiples : jeu très vertical
- Stages avec hazards ou neutres (pour tournoi)
FUN FACTOR : Liberté d'expression technique, cross-over Nintendo, casual à hardcore
PIÈGES D'IMPLÉMENTATION :
- Physique aérienne complexe à reproduire fidèlement
- Balance entre personnages très difficile""",
    },
    {
        "genre": "fighting",
        "game_name": "Tekken 3",
        "publisher": "Namco",
        "year": 1997,
        "document": """TEKKEN 3 — Fighting game 3D avec sidestep
CORE LOOP : Lire adversaire → Choisir attaque → String combo → Juggle → Baisser HP → Round gagné
MÉCANIQUES CORE :
- 4 boutons : chaque bouton = un membre (main gauche/droite, pied gauche/droite)
- Sidestep : esquive 3D (entrer/sortir du plan)
- Juggles : enchaînements en l'air (ennemi lancé = combo)
- Low/Mid/High : attaques à trois niveaux nécessitant réponses différentes
- King : chaque personnage a un moveset de 80+ mouvements
GAME FEEL :
- Impact des coups lourd et satisfaisant
- Animations fluides en 60fps
LEVEL DESIGN :
- Arène circulaire avec bords cassables
FUN FACTOR : Profondeur technique accessible, juggle satisfaisant, large roster
PIÈGES D'IMPLÉMENTATION :
- Hitboxes 3D complexes
- Animations : 60fps nécessaire pour la crédibilité""",
    },
    {
        "genre": "fighting",
        "game_name": "Guilty Gear Strive",
        "publisher": "Arc System Works",
        "year": 2021,
        "document": """GUILTY GEAR STRIVE — Fighting game moderne avec accessibilité
CORE LOOP : Gérer space → Attaque → Roman Cancel (mechanic clé) → Mix-up → Corner carry → Finish
MÉCANIQUES CORE :
- Roman Cancel : coûte 50% de gauge, annule recovery d'une attaque
- Wall Break : briser le mur = rebond et reset de position
- Overdrive : super puissant coûtant 50% de gauge
- Burst : échappatoire en cas de combo reçu
- Wild Assault : attaque améliorée qui push
GAME FEEL :
- Animations 2.5D cinématographiques
- Effets de choc spectaculaires sur gros coups
- Musique rock métal par personnage
LEVEL DESIGN :
- Stages illustrés avec lore intégré
FUN FACTOR : Accessibilité débutant + profondeur expert, esthétique unique, roman cancel créatif
PIÈGES D'IMPLÉMENTATION :
- Roman Cancel complexe à expliquer / enseigner
- Hitboxes sur animations très détaillées""",
    },

    # ─── RACING ───────────────────────────────────────────────────────────────
    {
        "genre": "racing",
        "game_name": "Mario Kart 64",
        "publisher": "Nintendo",
        "year": 1996,
        "document": """MARIO KART 64 — Racing kart avec items
CORE LOOP : Conduire → Ramasser item → Utiliser au bon moment → Prendre la tête → Finir premier
MÉCANIQUES CORE :
- Rubber banding : IA rattrape automatiquement (réduit l'écart leader/dernier)
- Items pondérés par position : dernier reçoit meilleurs items (étoile, éclair)
- Drift boost : glisser en virage puis boost en sortie
- 3 tours sur 4 circuits par coupe
- Battle mode : arènes avec 3 ballons de vie
GAME FEEL :
- Effets visuels d'items exagérés (écran plein de Blooper)
- Sons de course et de kart distinctifs
- Musique mémorable par circuit
LEVEL DESIGN :
- 4 coupes × 4 circuits avec thèmes variés (plage, neige, arc-en-ciel)
- Raccourcis cachés récompensant la connaissance du circuit
FUN FACTOR : Chaos fun des items, rubber banding = compétitif jusqu'au bout, jeu social
PIÈGES D'IMPLÉMENTATION :
- Rubber banding trop fort = sentiment de frustration "peu importe ce que je fais"
- Hitbox kart mal calibrée pour les items""",
    },
    {
        "genre": "racing",
        "game_name": "F-Zero GX",
        "publisher": "Nintendo / Sega AM2",
        "year": 2003,
        "document": """F-ZERO GX — Racing futuriste de précision extrême
CORE LOOP : Maîtriser la piste → Gérer énergie → Dépasser → Éviter la mort → Terminer premier
MÉCANIQUES CORE :
- Vitesse extrême (600km/h+) : réflexes nécessaires
- Energy bar : s'use sur les bandes de bord et lors des boost
- Side attack : tasser les adversaires pour les détruire
- Boost : coûte de l'énergie (gestion risque/bénéfice)
- Magnétisme des circuits : virages banqués à 90°
GAME FEEL :
- Sensation de vitesse via défilement de décors et flou
- Musique électronique et rock qui s'adapte à la vitesse
LEVEL DESIGN :
- Circuits très techniques avec loopings, tunnels, sauts
- 30 pilotes sur piste simultanément
FUN FACTOR : Vitesse grisante, maîtrise pure, récompense l'apprentissage
PIÈGES D'IMPLÉMENTATION :
- Vitesse extrême = hitbox minuscule = frustration si imprécis
- Checkpoint invisible = ne sait pas où était l'erreur""",
    },
    {
        "genre": "racing",
        "game_name": "Burnout 3: Takedown",
        "publisher": "Criterion / EA",
        "year": 2004,
        "document": """BURNOUT 3 TAKEDOWN — Racing arcade avec crashs spectaculaires
CORE LOOP : Conduire à contresens / près des voitures → Remplir boost → Détruire adversaires (Takedown) → Gagner
MÉCANIQUES CORE :
- Boost : rechargé en roulant sur la file opposée, près des véhicules, sous camions
- Takedown : éjecter un adversaire = gros boost bonus
- Crash mode : provoquer le plus gros accident possible (mode dédié)
- Aftertouch : diriger sa voiture après un crash pour maximiser les dégâts
- Traffic checking : slalomer entre voitures = charge le boost
GAME FEEL :
- Crashs en slow motion (Crash Cam)
- Déformations de métal spectaculaires et physiques
- Son d'impact fort lors des Takedowns
LEVEL DESIGN :
- Circuits en monde ouvert avec trafic réel
- Variante : Road Rage (détruire un maximum d'adversaires dans le temps)
FUN FACTOR : Action spectaculaire, destruction récompensée, sessions courtes intenses
PIÈGES D'IMPLÉMENTATION :
- Physique de crash convaincante = complexe (ragdoll)
- Trop peu de trafic = boost difficile à maintenir""",
    },
    {
        "genre": "racing",
        "game_name": "Trackmania Nations",
        "publisher": "Nadeo",
        "year": 2006,
        "document": """TRACKMANIA NATIONS — Racing sur pistes acrobatiques
CORE LOOP : Découvrir piste → Améliorer temps → Médaille de bronze → Argent → Or → Nadeo → World record
MÉCANIQUES CORE :
- Contrôles simples : accélérer, freiner, gauche/droite
- Restart instantané : recommencer immédiatement sans menu
- Medailles : Bronze/Argent/Or/Nadeo = difficultés croissantes
- Ramps, loopings, wallrides : piste acrobatique
- Éditeur de piste : créer et partager des circuits
GAME FEEL :
- Restart instantané = itération rapide sans friction
- Sensation de vitesse avec effets de caméra
LEVEL DESIGN :
- Pistes linéaires de 20 secondes à 3 minutes
- Checkpoint en cas d'erreur (optionnel par piste)
FUN FACTOR : Maîtrise progressive mesurable, restart sans friction, courses courtes
PIÈGES D'IMPLÉMENTATION :
- Sans checkpoint : frustration sur les longues pistes
- Physique de voiture : drift différent du grip difficile à calibrer""",
    },
    {
        "genre": "racing",
        "game_name": "Rocket League",
        "publisher": "Psyonix",
        "year": 2015,
        "document": """ROCKET LEAGUE — Racing + football avec fusées
CORE LOOP : Boost → Frapper balle → Marquer but → Défendre → Score → 5 minutes de match
MÉCANIQUES CORE :
- Boost : ramassé sur des pads éparpillés sur la map
- Vol : maintenir saut et boost = voiture volante
- Aerial : frapper la balle en l'air (technique avancée)
- Dribble : tenir la balle sur le capot de la voiture
- Démolition : éperonner ennemi à vitesse maximale = respawn
GAME FEEL :
- Ball cam vs car cam : deux perspectives avec gameplays différents
- Son de coup sur la balle récompensant l'impact
- Replay automatique sur les buts
LEVEL DESIGN :
- Arène symétrique standardisée (compétitif)
- Variantes : Snowday (palet), Hoops (basketball)
FUN FACTOR : Skill gap immense, matches en 5 minutes, casual → compétitif
PIÈGES D'IMPLÉMENTATION :
- Physique de balle très précise requise
- Netcode crucial pour le multijoueur""",
    },

    # ─── ROGUELITE ────────────────────────────────────────────────────────────
    {
        "genre": "roguelite",
        "game_name": "Hades",
        "publisher": "Supergiant Games",
        "year": 2020,
        "document": """HADES — Roguelite action avec narration integree
CORE LOOP : Run -> Mourir -> Choisir boon -> Ameliorer meta -> Nouveau run plus fort
MECANIQUES CORE :
- Boons : pouvoirs offerts par un dieu apres chaque salle (choisir 1 parmi 3)
- Synergies : combiner des boons de dieux differents = effets amplifies
- Mirror of Night : meta-progression permanente (miroir des tenebres)
- Dash infini : methode principale d'esquive, jamais penalisante
GAME FEEL :
- Mort = dialogue narratif, pas un ecran de game over
- Chaque run raccourcit : plus d'experience = runs plus rapides
- Feedback hit : ennemis se figent brievement sur les coups critiques
PROGRESSION :
- Pactes de chatiment : difficulte optionnelle augmentee pour rejouer
FUN FACTOR : Variance de build elevee, narration omniprésente, mort non-punitive
PIEGES D'IMPLEMENTATION :
- Trop peu de variance = runs repetitifs
- Salle trop longue sans recompense = perte d'elan""",
    },
    {
        "genre": "roguelite",
        "game_name": "Dead Cells",
        "publisher": "Motion Twin",
        "year": 2018,
        "document": """DEAD CELLS — Roguelite Metroidvania avec combat precis
CORE LOOP : Explorer biome -> Tuer ennemis -> Collecter cellules -> Boss -> Biome suivant -> Mourir -> Depenser cellules en meta
MECANIQUES CORE :
- Cellules : monnaie de run depensee en meta-upgrades (blueprints permanents)
- Deux armes actives + deux items de support : build sur 4 slots
- Parry : timing precis = stun ennemi + degats bonus
- Roll d'esquive : i-frames pendant le roll
- Mutations : passifs choisis en fin de biome
GAME FEEL :
- Attaques ont du poids : hitstop sur les coups connectes
- Fluidite parkour : sauts, wall-jumps, grappin
PROGRESSION :
- Boss Cell : modificateurs de difficulte debloquables progressivement
FUN FACTOR : Combat precis et satisfaisant, builds varies, mort courte
PIEGES D'IMPLEMENTATION :
- Ennemis trop telegraphes = trivial, trop rapide = injuste
- Run trop long sans checkpoint = frustration""",
    },
    {
        "genre": "roguelite",
        "game_name": "The Binding of Isaac",
        "publisher": "Nicalis",
        "year": 2014,
        "document": """THE BINDING OF ISAAC: REBIRTH — Roguelite twin-stick avec combinaisons d'items
CORE LOOP : Explorer salle -> Tirer ennemis -> Collecter item -> Boss -> Etage suivant -> 7 etages -> Fin
MECANIQUES CORE :
- Items : +500 items, chacun modifiant les stats ou donnant des effets uniques
- Synergies : certains items combines creent des effets non documentes
- Larmes : projectiles du personnage, customises par les items
- Bombes/cles/pieces : ressources limitees a gerer par etage
GAME FEEL :
- Variance extreme : un bon item des le depart = run trivial ou OP
FUN FACTOR : Variance maximale, decouverte de synergies, humour noir
PIEGES D'IMPLEMENTATION :
- Trop d'items = illisibilite des effets
- Generation doit garantir jouabilite""",
    },
    {
        "genre": "roguelite",
        "game_name": "Risk of Rain 2",
        "publisher": "Hopoo Games",
        "year": 2019,
        "document": """RISK OF RAIN 2 — Roguelite 3D avec escalade de difficulte temporelle
CORE LOOP : Arriver sur planete -> Tuer monstres (difficulte croit avec le temps) -> Teleporter -> Etage suivant -> Boss -> Repeter
MECANIQUES CORE :
- Minuterie de difficulte : rester longtemps = monstres plus forts
- Items empilables : meme item plusieurs fois = effet amplifie (stacking)
- Lunar items : tres puissants mais avec une malediction associee
GAME FEEL :
- Escalade visible : on commence faible, on finit quasi-imbattable avec les bons items
PROGRESSION :
- Artifacts : modificateurs globaux debloquables
FUN FACTOR : Progression explosive, sessions rapides, builds inattendus
PIEGES D'IMPLEMENTATION :
- Timer de difficulte invisible = joueurs ne comprennent pas pourquoi ca empire""",
    },

    # ─── VISUAL NOVEL ─────────────────────────────────────────────────────────
    {
        "genre": "visual_novel",
        "game_name": "Ace Attorney",
        "publisher": "Capcom",
        "year": 2001,
        "document": """ACE ATTORNEY — Visual novel proces/enquete
CORE LOOP : Enqueter scene de crime -> Interroger temoins -> Collecter preuves -> Proces -> Objecter -> Presenter preuve -> Demasquer mensonge
MECANIQUES CORE :
- OBJECTION! : interrompre un temoignage avec une preuve contradictoire
- Pression psychologique : forcer un temoin -> contradiction -> revelation
- Jauge de vie du tribunal : erreurs = pression sur le juge (5 vies)
- Temoignages en boucle : repeter le temoignage pour identifier la faille
GAME FEEL :
- Musique dramatique qui monte lors des confrontations
- Animations de personnages expressives (sprites 2D animes)
FUN FACTOR : Satisfaction de la resolution logique, personnages memorables, twists
PIEGES D'IMPLEMENTATION :
- Solution trop evidente = pas de tension
- Solution trop obscure = frustration (trial and error)""",
    },
    {
        "genre": "visual_novel",
        "game_name": "Doki Doki Literature Club",
        "publisher": "Team Salvato",
        "year": 2017,
        "document": """DOKI DOKI LITERATURE CLUB — Visual novel psychologique/meta
CORE LOOP : Lire dialogues -> Choisir poeme -> Evenements -> Fin de journee -> Repeter
MECANIQUES CORE :
- Choix de mots pour le poeme : systeme de points d'affinite par personnage
- Four routes initiales -> corruption narrative progressive
- Meta-gameplay : modification de fichiers sauvegarde narrative
- Flags de fin : comportements deverrouilles selon les routes precedentes
GAME FEEL :
- Rupture progressive des conventions du genre (glitches intentionnels)
- Musique qui degenere avec l'histoire
FUN FACTOR : Surprise narrative, subversion des attentes, memorabilite extreme
PIEGES D'IMPLEMENTATION :
- Twist trop previsible = impact nul
- Horreur trop explicite = perd l'ambiguite""",
    },
    {
        "genre": "visual_novel",
        "game_name": "Steins;Gate",
        "publisher": "5pb./Nitroplus",
        "year": 2009,
        "document": """STEINS;GATE — Visual novel de science-fiction avec time travel
CORE LOOP : Lire textes -> Repondre aux SMS (Phone Trigger) -> Changer le passe -> Observer les consequences -> Autre route
MECANIQUES CORE :
- Phone Trigger : repondre ou ignorer un SMS = bifurcation narrative
- D-mails : envoyer SMS dans le passe = changer une variable de l'univers
- Worldlines : chaque decision cree une ligne temporelle differente
GAME FEEL :
- Progression lente et dense -> recompense emotionnelle massive
- Terminologie scientifique (vraie physique theorique)
FUN FACTOR : Coherence interne remarquable, attachement aux personnages, revelations
PIEGES D'IMPLEMENTATION :
- Trop de texte sans choix = sensation de livre interactif
- Choix sans consequence percue = desinvestissement""",
    },

    # ─── RUNNER ───────────────────────────────────────────────────────────────
    {
        "genre": "runner",
        "game_name": "Canabalt",
        "publisher": "Adam Atomic",
        "year": 2009,
        "document": """CANABALT — Endless runner minimaliste fondateur du genre
CORE LOOP : Courir automatiquement -> Sauter au bon moment -> Atterrir sur le toit suivant -> Repeter jusqu'a la mort
MECANIQUES CORE :
- Un seul bouton : ESPACE = saut
- Vitesse croissante automatiquement : plus on survit, plus on va vite
- Obstacles varies : boites renversables (ralentissent), barres a sauter, gaps
GAME FEEL :
- Momentum : courir + sauter au bord = distance maximale
- Caméra : zoom out progressif = sensation d'acceleration
FUN FACTOR : One-more-run parfait, sessions courtes, simplicite absolue
PIEGES D'IMPLEMENTATION :
- Gaps trop larges en debut = mort injuste
- Vitesse croissante trop lente = ennui, trop rapide = mort avant d'apprecier""",
    },
    {
        "genre": "runner",
        "game_name": "Geometry Dash",
        "publisher": "RobTop Games",
        "year": 2013,
        "document": """GEOMETRY DASH — Runner de precision avec musique synchronisee
CORE LOOP : Ecouter musique -> Cliquer au bon rythme -> Franchir obstacles -> Arriver a la fin du niveau
MECANIQUES CORE :
- Un bouton (clic/espace) : saut, selon le mode actif (cube/ship/ball/wave)
- Modes multiples : cube (sauter), vaisseau (voler), bille (gravite inversee)
- Rythme musical : obstacles synchronises avec la musique
- Portails : changer de mode ou de taille (mini/normal)
GAME FEEL :
- Musique entrainante = immersion complete
- Transitions de modes : gameplay radicalement different en milieu de run
FUN FACTOR : Precision musicale, satisfaction de terminer un niveau long
PIEGES D'IMPLEMENTATION :
- Synchronisation musique/obstacles doit etre parfaite
- Difficulte trop haute en debut = abandon immediat""",
    },
    {
        "genre": "runner",
        "game_name": "Jetpack Joyride",
        "publisher": "Halfbrick",
        "year": 2011,
        "document": """JETPACK JOYRIDE — Endless runner avec gadgets et missions
CORE LOOP : Voler avec jetpack -> Eviter obstacles (lasers, zappers, missiles) -> Collecter pieces -> Acheter gadgets -> Rejouer
MECANIQUES CORE :
- Jetpack : maintenir le bouton = monter, relacher = descendre
- Vehicules speciaux : atterrir sur un vehicule = powers differents (dragon, moto)
- Missions : 3 missions actives (ex : voler 500m, collecter 50 pieces) -> XP
- S.A.M. (missiles) : survie de sequence de missiles teleguides = bonus
GAME FEEL :
- Son du jetpack : feedback immediat sur chaque action
- Vehicules visuellement distinctifs et fun
PROGRESSION :
- Gadgets : equipements permanents ameliorant les runs (aimant, bouclier)
FUN FACTOR : Accessibilite totale, missions courtes, gadgets strategiques
PIEGES D'IMPLEMENTATION :
- Obstacles trop bases = lecture difficile (hauteur vs avion)
- Missions impossibles a voir = frustration""",
    },

    # ─── ARCADE / BREAKOUT ────────────────────────────────────────────────────
    {
        "genre": "arcade",
        "game_name": "Arkanoid",
        "publisher": "Taito",
        "year": 1986,
        "document": """ARKANOID — Breakout avec power-ups et boss
CORE LOOP : Deplacer raquette -> Faire rebondir balle -> Casser briques -> Collecter capsules -> Niveau suivant -> Boss
MECANIQUES CORE :
- Raquette Vaus : deplacement horizontal uniquement
- Angle de renvoi : frappe sur le bord de la raquette = angle aigu
- Capsules (power-ups) : Slow (balle lente), Break (traverse briques), Laser, Extend (raquette large), Disrupt (3 balles)
- Briques indestructibles (argent) : rebondissent toujours
- Boss Doh : resiste a plusieurs impacts
GAME FEEL :
- Son distinct par type de brique cassee (tons musicaux)
- Acceleration balle sur certains paliers
FUN FACTOR : Satisfaction de combo, power-ups transformateurs, niveaux courts
PIEGES D'IMPLEMENTATION :
- Balle coincee dans un coin = session longue ennuyeuse
- Raquette trop petite = frustration, trop grande = trivial""",
    },
    {
        "genre": "arcade",
        "game_name": "Peggle",
        "publisher": "PopCap",
        "year": 2007,
        "document": """PEGGLE — Casse-briques casual avec trajectoires et magie
CORE LOOP : Viser -> Tirer bille -> Rebondir sur pegs orange -> Compter pegs orange restants -> Vider tous les pegs orange
MECANIQUES CORE :
- Tir de haut : angle libre en haut, bille descend par gravite
- Pegs orange (a eliminer) vs bleus (bonus) vs verts (pouvoir special)
- Maitres magiques : 10 personnages donnant un power sur les pegs verts
- Free ball : bille tombe dans le seau au bas -> bille gratuite
- Score multiplicateur : combo de pegs = multiplicateur croissant
GAME FEEL :
- Ode to Joy + slow motion + confettis lors du dernier peg orange = catharsis
- Trajectoire predite en amont (pointilles)
FUN FACTOR : Accessibilite totale, satisfaction visuellement spectaculaire, one more shot
PIEGES D'IMPLEMENTATION :
- Trop de pegs = trajectoire imprévisible = RNG frustrant""",
    },
    {
        "genre": "arcade",
        "game_name": "Breakout",
        "publisher": "Atari",
        "year": 1976,
        "document": """BREAKOUT — Arcade fondateur du casse-brique
CORE LOOP : Deplacer raquette -> Balle rebondit -> Brique cassee -> Score -> Angle change -> Repeter
MECANIQUES CORE :
- Raquette : deplacement horizontal, controle l'angle de renvoi
- Mur de briques : 8 rangees de couleurs differentes (valeur differente)
- Balle s'accelere apres X briques cassees
- Percer un trou dans le mur du haut : balle rebondit dans l'espace superieur = combo bonus
GAME FEEL :
- Son mecanique : boing sur chaque impact (feedback immediat)
- Tension : balle s'accelere progressivement
FUN FACTOR : Simplicite absolue, maitrise de l'angle, sensation de controle
PIEGES D'IMPLEMENTATION :
- Balle trop rapide des le depart = demoralisant
- Hitbox raquette floue = sentiment d'injustice""",
    },

    # ─── DUNGEON CRAWLER ──────────────────────────────────────────────────────
    {
        "genre": "dungeon_crawler",
        "game_name": "Diablo II",
        "publisher": "Blizzard",
        "year": 2000,
        "document": """DIABLO II — ARPG fondateur du loot-driven dungeon crawler
CORE LOOP : Explorer zone -> Tuer monstres -> Looter items -> Equiper meilleurs items -> Zone suivante plus difficile
MECANIQUES CORE :
- Loot : chaque monstre drop items avec rarete (normal/magic/rare/unique/set)
- Builds : arbre de competences avec 30+ skills par classe
- Acte -> Boss -> Prochain acte : structure lineaire avec 5 actes
- Difficultes : Normal -> Cauchemar -> Enfer (memes zones, ennemis plus forts)
GAME FEEL :
- Son de piece qui tombe = dopamine
- Town portal : retour ville instantane avec portail
PROGRESSION :
- 7 classes radicalement differentes en builds possibles
FUN FACTOR : Loot addiction, builds infinis, rejouabilite par classe
PIEGES D'IMPLEMENTATION :
- Loot trop rare = frustration, trop frequent = dilution""",
    },
    {
        "genre": "dungeon_crawler",
        "game_name": "Hades (Dungeon)",
        "publisher": "Supergiant Games",
        "year": 2020,
        "document": """HADES — Dungeon crawler action avec chambres de combat
CORE LOOP : Entrer chambre -> Tuer tous les ennemis -> Choisir recompense -> Chambre suivante -> Boss -> Sortie ou mort
MECANIQUES CORE :
- Chambres forcees : les ennemis apparaissent et les portes se ferment
- Recompenses variees : boon / obole / vie selon la symbolique de la porte
- Boss a phases : Megaera (3 soeurs), Thesee+Asterion (duo), Hades (multi-phases)
- Couleurs de portes : or (boon rare), argent (obole), rouge (vie)
GAME FEEL :
- Actions rapides : dash + attaque + special + lancer = 4 boutons actifs
FUN FACTOR : Fluidite d'action, variete de builds, narration dans l'action
PIEGES D'IMPLEMENTATION :
- Recompenses trop similaires = choix peu engageant""",
    },
    {
        "genre": "dungeon_crawler",
        "game_name": "Nethack",
        "publisher": "NetHack DevTeam",
        "year": 1987,
        "document": """NETHACK — Roguelike pur avec systeme de simulation profond
CORE LOOP : Explorer etage -> Combattre -> Identifier items -> Descendre escalier -> Manger -> Plus profond -> Ou mort = tout recommencer
MECANIQUES CORE :
- Tour-par-tour : chaque action du joueur = un tour ennemi
- Identification : tous les items sont non-identifies au debut (potions/parchemins/baguettes)
- Alignement : Lawful/Neutral/Chaotic affecte les interactions
- Divinite : prier pour obtenir aide ou etre puni si trop frequent
- Simulation : presque tout interagit avec tout (lancer un couteau dans l'eau = no dommage)
GAME FEEL :
- Interface ASCII = imagination du joueur comble les visuels
- Mort permanente = chaque run compte
PROGRESSION :
- Meta-knowledge du joueur (pas du personnage) = vraie progression
FUN FACTOR : Profondeur infinie, surprises permanentes, mort instructive
PIEGES D'IMPLEMENTATION :
- RNG trop punitif en debut = runs impossibles
- Trop de regles implicites = courbe apprentissage verticale""",
    },
]


# ─── Fonctions ChromaDB ────────────────────────────────────────────────────────

RAG_DIR = "rag_database"

_mech_client = None
_mech_collection = None
_mech_available = None


def _get_mechanics_collection():
    global _mech_client, _mech_collection, _mech_available

    if _mech_available is False:
        return None
    if _mech_collection is not None:
        return _mech_collection

    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        _mech_client = chromadb.PersistentClient(path=RAG_DIR)
        _mech_collection = _mech_client.get_or_create_collection(
            name="mechanics_kb",
            metadata={"hnsw:space": "cosine"},
        )
        _mech_available = True
        return _mech_collection
    except Exception as e:
        _mech_available = False
        print(f"  [MechanicsKB] ChromaDB indisponible : {e}")
        return None


def store_mechanic(game_name: str, genre: str, document: str, publisher: str = "", year: int = 0) -> bool:
    """Stocke les mécaniques d'un jeu dans la collection mechanics_kb."""
    collection = _get_mechanics_collection()
    if collection is None:
        return False

    try:
        doc_id = f"mech_{genre}_{game_name.replace(' ', '_').replace('/', '_')[:40]}"
        metadata = {
            "genre": genre,
            "game_name": game_name,
            "publisher": publisher,
            "year": year,
        }
        collection.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])
        return True
    except Exception as e:
        print(f"  [MechanicsKB] Erreur stockage {game_name} : {e}")
        return False


def search_mechanics(genre: str, query: str, n: int = 3) -> list:
    """
    Cherche les mécaniques pertinentes dans la collection mechanics_kb.
    Retourne une liste de dicts {game_name, genre, publisher, year, document}.
    Exportable et utilisé par agent_intelligence_genre.py.
    """
    collection = _get_mechanics_collection()
    if collection is None:
        return []

    try:
        count = collection.count()
        if count == 0:
            return []

        # Cherche d'abord dans le genre spécifié
        where = {"genre": {"$eq": genre}} if genre else None
        actual_n = n

        if where:
            genre_items = collection.get(where=where)
            genre_count = len(genre_items["ids"])
            if genre_count == 0:
                where = None  # Fallback sans filtre genre
            else:
                actual_n = min(n, genre_count)

        actual_n = min(actual_n, count)
        if actual_n == 0:
            return []

        results = collection.query(
            query_texts=[f"{genre} {query}"],
            n_results=actual_n,
            where=where,
        )

        mechanics = []
        if results and results.get("metadatas") and results.get("documents"):
            for meta, doc in zip(results["metadatas"][0], results["documents"][0]):
                entry = dict(meta)
                entry["document"] = doc
                mechanics.append(entry)

        return mechanics

    except Exception as e:
        print(f"  [MechanicsKB] Erreur recherche : {e}")
        return []


def _migrate_genre_keys() -> int:
    """
    One-time migration: rename stale genre keys with spaces to underscore form.
    Example: 'tower defense' -> 'tower_defense'.
    Deletes old entries and re-stores them with the corrected genre key.
    Returns the number of entries migrated.
    """
    collection = _get_mechanics_collection()
    if collection is None:
        return 0

    GENRE_RENAMES = {"tower defense": "tower_defense"}
    migrated = 0

    for old_genre, new_genre in GENRE_RENAMES.items():
        try:
            old_entries = collection.get(where={"genre": {"$eq": old_genre}})
            if not old_entries["ids"]:
                continue
            # Re-store with corrected genre
            for doc_id, doc, meta in zip(old_entries["ids"], old_entries["documents"], old_entries["metadatas"]):
                new_meta = dict(meta)
                new_meta["genre"] = new_genre
                new_id = f"mech_{new_genre}_{meta.get('game_name','').replace(' ','_')[:40]}"
                collection.upsert(ids=[new_id], documents=[doc], metadatas=[new_meta])
            # Delete old entries
            collection.delete(ids=old_entries["ids"])
            migrated += len(old_entries["ids"])
            print(f"  [MechanicsKB] Migrated {len(old_entries['ids'])} entries: '{old_genre}' -> '{new_genre}'")
        except Exception as e:
            print(f"  [MechanicsKB] Migration error for '{old_genre}': {e}")

    return migrated


def build(force: bool = False) -> int:
    """
    Peuple la collection mechanics_kb avec tous les jeux définis dans GAMES_KB.
    Retourne le nombre d'entrées stockées.
    Si force=False, skip si la collection est déjà peuplée.
    """
    collection = _get_mechanics_collection()
    if collection is None:
        print("  [MechanicsKB] ChromaDB non disponible — build annulé.")
        return 0

    # Fix any stale genre keys before adding new entries
    _migrate_genre_keys()

    existing_count = collection.count()
    if existing_count >= len(GAMES_KB) and not force:
        print(f"  [MechanicsKB] Deja peuplee ({existing_count} entrees). Utilisez force=True pour reconstruire.")
        return existing_count

    stored = 0
    genres_seen = {}
    for game in GAMES_KB:
        genre = game["genre"]
        name = game["game_name"]
        if genre not in genres_seen:
            genres_seen[genre] = 0
        ok = store_mechanic(
            game_name=name,
            genre=genre,
            document=game["document"],
            publisher=game.get("publisher", ""),
            year=game.get("year", 0),
        )
        if ok:
            stored += 1
            genres_seen[genre] += 1
            print(f"  OK {genre:15s} | {name}")
        else:
            print(f"  FAIL {genre:15s} | {name}")

    print(f"\n  [MechanicsKB] {stored}/{len(GAMES_KB)} jeux indexés.")
    for genre, count in sorted(genres_seen.items()):
        print(f"    {genre:20s} : {count} jeux")

    return stored


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    force_rebuild = "--force" in sys.argv

    print("=" * 60)
    print("  BUILD MECHANICS KB — ChromaDB")
    print("=" * 60)

    n = build(force=force_rebuild)

    if n > 0:
        print("\n  Test de recherche :")
        results = search_mechanics("platformer", "saut double dash mobilité", n=2)
        for r in results:
            print(f"    → {r['game_name']} ({r['genre']})")

        results2 = search_mechanics("rpg", "loot système de progression", n=2)
        for r in results2:
            print(f"    → {r['game_name']} ({r['genre']})")

    print("\n  Terminé.")

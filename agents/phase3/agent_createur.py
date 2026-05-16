"""
Creator Agent — Phase 3
Generates the complete HTML5 game code from all accumulated context.
Two modes:
- run(): classic monolithic generation (fallback)
- run_modulaire(): generates each module independently (recommended)
"""

import json
import re as _re
from config import call_gemini, with_fallback, MODEL_NAME_PRO
from genre_profile import GenreProfile, ConceptionContext, ModuleArchitecture, GeneratedModules
from logger import phase3_log
import rag

SYSTEM_2D = """Tu es un développeur senior spécialisé en jeux HTML5 Canvas 2D. Tu produis du code qui FONCTIONNE SANS ERREUR dès le premier chargement.

SQUELETTE OBLIGATOIRE — reproduis cette structure EXACTEMENT (adapte le contenu, pas la structure) :
```html
<!DOCTYPE html><html><head><title>NomDuJeu</title><style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#000; overflow:hidden; }
canvas { display:block; }
</style></head><body>
<canvas id="gameCanvas"></canvas>
<script>
// ── CONSTANTES GLOBALES (avant DOMContentLoaded) ──
const PALETTE = { bg:'#111', player:'#0AF', enemy:'#F44', ui:'#FFF' };
const SPEED = 200, BULLET_SPEED = 400;
let score = 0, lives = 3, gameState = 'menu';
const keys = { left:false, right:false, up:false, down:false, space:false };
const mouse = { x:0, y:0, clicked:false };
const sfx = { play(f=440,d=0.1,t='square'){try{const c=new(window.AudioContext||window.webkitAudioContext)(),o=c.createOscillator(),g=c.createGain();o.type=t;o.frequency.value=f;g.gain.setValueAtTime(0.15,c.currentTime);g.gain.exponentialRampToValueAtTime(0.001,c.currentTime+d);o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+d);}catch(e){}} };
// ── ARRAYS D'ENTITÉS (globaux) ──
const enemies = [], bullets = [], particles = [];
let player = null; // initialisé dans initGame()

document.addEventListener('DOMContentLoaded', function() {
  const canvas = document.getElementById('gameCanvas');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;

  // ── EVENT LISTENERS (tous ici, dans DOMContentLoaded) ──
  document.addEventListener('keydown', e => { const k = e.key.toLowerCase(); if (k in keys) keys[k] = true; if (e.code === 'Space') keys.space = true; });
  document.addEventListener('keyup',   e => { const k = e.key.toLowerCase(); if (k in keys) keys[k] = false; if (e.code === 'Space') keys.space = false; });
  canvas.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  canvas.addEventListener('click',     e => { mouse.clicked = true; });

  function initGame() {
    score = 0; lives = 3;
    enemies.length = 0; bullets.length = 0; particles.length = 0;
    player = { x: W/2, y: H*0.8, w:30, h:30, hp:3, speed: SPEED };
    gameState = 'playing';
  }

  let lastTime = 0;
  function gameLoop(ts) {
    const dt = Math.min((ts - lastTime) / 1000, 0.05);
    lastTime = ts;
    update(dt);
    draw();
    mouse.clicked = false;
    requestAnimationFrame(gameLoop);
  }

  function update(dt) {
    if (gameState === 'menu') { if (keys.space || mouse.clicked) { initGame(); } return; }
    if (gameState === 'gameover') { if (keys.space || mouse.clicked) { gameState = 'menu'; } return; }
    // ... logique du jeu
    for (let i = enemies.length - 1; i >= 0; i--) {
      const en = enemies[i]; // ← TOUJOURS init la variable locale en 1ère ligne
      en.x += en.vx * dt; en.y += en.vy * dt;
      if (en.hp <= 0) { spawnParticles(en.x, en.y, PALETTE.enemy, 8); enemies.splice(i, 1); score += 10; }
    }
  }

  function draw() {
    ctx.fillStyle = PALETTE.bg; ctx.fillRect(0, 0, W, H); // fond EN PREMIER
    if (gameState === 'menu') { /* draw menu */ return; }
    if (gameState === 'gameover') { /* draw gameover */ return; }
    if (!player) return; // null guard
    // ... draw entities
    drawHUD();
  }

  function drawHUD() {
    ctx.fillStyle = PALETTE.ui; ctx.font = '20px Arial';
    ctx.fillText('Score: ' + score, 10, 30);
  }

  function spawnParticles(x, y, color, count) {
    for (let i = 0; i < count; i++) {
      const a = Math.random() * Math.PI * 2, s = 50 + Math.random() * 100;
      particles.push({ x, y, vx: Math.cos(a)*s, vy: Math.sin(a)*s, life:1, size:3+Math.random()*4, color });
    }
  }

  initGame();
  requestAnimationFrame(gameLoop);
});
</script></body></html>
```

RÈGLE ABSOLUE N°1 — DÉCLARATIONS GLOBALES EN HAUT DU SCRIPT :
Toute constante ou variable utilisée dans plusieurs fonctions DOIT être déclarée au sommet du <script>,
AVANT le DOMContentLoaded. Exemples de ce qui doit TOUJOURS être déclaré globalement :
  const PALETTE = { bg: '#...', hero: '#...', enemy: '#...', ui: '#...', ... };
  const TILE = { GRASS: 0, WALL: 1, WATER: 2, ... };
  const TILE_SIZE = 16;
  const PLAYER_SIZE = 14;
  const HERO_SPRITES = { idle: {...}, walk: {...}, ... };
  const UI_SPRITES = { heart_full: [...], heart_empty: [...] };
Si une variable est référencée dans une fonction, elle DOIT être déclarée à portée globale — jamais supposée
définie ailleurs. Une ReferenceError sur une variable globale = écran noir garanti.

RÈGLE ABSOLUE N°2 — SYNTAXE JS STRICTE :
- Jamais de virgule en trop après le dernier élément d'un objet ou tableau : {a:1, b:2} pas {a:1, b:2,}
- Chaque accolade ouvrante { a une accolade fermante } correspondante
- Chaque fonction doit être complète — ne jamais laisser une fonction sans corps fermé

RÈGLE ABSOLUE N°3 — PAS DE DEV CONSOLE À GÉNÉRER :
NE génère PAS de dev console / overlay de debug dans ton code.
La dev console est injectée automatiquement par le système après génération.
Concentre-toi uniquement sur le jeu lui-même.

RÈGLE ABSOLUE N°4 — INITIALISATION VARIABLE DE BOUCLE (BUG CRITIQUE FRÉQUENT) :
Dans toute boucle for sur un tableau, la PREMIÈRE ligne du corps doit initialiser la variable locale.
CORRECT — toujours écrire comme ça :
  for (let i = enemies.length - 1; i >= 0; i--) {
    const e = enemies[i];  // ← OBLIGATOIRE, première ligne
    e.x += e.vx * dt;
    e.y += e.vy * dt;
    if (e.hp <= 0) enemies.splice(i, 1);
  }
OU utiliser for...of :
  for (const e of enemies) { e.x += e.vx * dt; }
INTERDIT — jamais accéder directement sans init :
  for (let i = 0; i < projectiles.length; i++) {
    p.x += p.vx * dt;  // CRASH : p n'est pas défini !
  }
Ce bug produit un ReferenceError immédiat. Il touche bullets, enemies, projectiles, particles, etc.

RÈGLE ABSOLUE N°5 — PASSAGE DE `dt` AUX FONCTIONS (BUG SILENCIEUX FRÉQUENT) :
Chaque fonction qui utilise delta time DOIT le recevoir en paramètre.
CORRECT :
  function checkCollisions(dt) { if (...) hero.invincibilityTimer -= dt; }
  // Dans update(dt) : checkCollisions(dt);
INTERDIT :
  function checkCollisions() { hero.invincibilityTimer -= dt; } // dt est undefined ici !
  // dt n'est accessible que dans la fonction qui l'a reçu — jamais en variable globale implicite.
Règle : si une fonction utilise dt dans son corps → dt doit être dans ses paramètres.

RÈGLE ABSOLUE N°6 — JSON.parse OBLIGATOIRE dans loadGame/loadSave :
localStorage.getItem() retourne une STRING. Toujours parser avant d'accéder aux propriétés.
CORRECT :
  function loadGame() {
    const raw = localStorage.getItem('save_key');
    if (!raw) return;
    const data = JSON.parse(raw);  // ← OBLIGATOIRE
    if (!data) return;
    score = data.score || 0;
    player.hp = data.hp || 100;
  }
INTERDIT :
  function loadGame() {
    const raw = localStorage.getItem('save_key');
    score = raw.score;  // CRASH : raw est une string, .score = undefined → NaN
  }

RÈGLE ABSOLUE N°7 — JAMAIS eval() NI window.__devPatch :
NE JAMAIS écrire eval(), new Function(), window.__devPatch, ou tout mécanisme d'exécution dynamique.
Ce sont des restes de debug qui causent des fuites mémoire et des failles de sécurité.
Si tu voulais faire du debug, ne l'écris pas du tout.

RÈGLE ABSOLUE N°8 — DÉCLARER `dist` AVANT DE L'UTILISER :
Toute variable `dist`, `distance`, `dx`, `dy` DOIT être calculée AVANT d'être testée dans un if().
CORRECT :
  const dx = enemy.x - player.x;
  const dy = enemy.y - player.y;
  const dist = Math.sqrt(dx*dx + dy*dy);
  if (dist < enemy.range) { ... }
INTERDIT :
  if (dist < enemy.range) { ... }  // CRASH : dist n'a pas été calculée !
Chaque utilisation de `dist` dans une boucle doit être précédée de son calcul dans la MÊME portée.

RÈGLE ABSOLUE N°9 — SFX / SON : TOUT OU RIEN :
Si tu veux du son, tu DOIS déclarer l'objet sfx globalement avec des méthodes réelles :
  const sfx = { play: (id) => {} };  // stub minimal si WebAudio non implémenté
INTERDIT : écrire sfx.play('boom') sans avoir déclaré sfx.
Une seule référence à sfx sans déclaration = ReferenceError au premier frame = écran noir.
Règle simple : si tu n'implémente pas WebAudio, mets CE stub global et rien d'autre.

RÈGLE ABSOLUE N°10 — VARIABLES DE BOUCLE forEach/map :
Dans `.forEach(item => ...)`, le paramètre de callback ne doit PAS s'appeler `e` (conflit avec Event),
ni `p` si une variable globale `p` existe, ni `f` si `f` est utilisé ailleurs.
CORRECT : particles.forEach(pt => { ... });  bullets.forEach(blt => { ... });
INTERDIT : particles.forEach(p => { ... });  // `p` peut déjà être une variable globale !
Utilise des noms descriptifs : `pt`, `blt`, `en`, `ft` pour particles/bullets/enemies/floatingTexts.

RÈGLE ABSOLUE N°11 — DÉCLARER avant TESTER (variables intermédiaires) :
Toute variable calculée dans une fonction (closest, targetEnemy, angle, hit, found...) DOIT être
déclarée avec `let` AVANT le if() qui la teste.
CORRECT :
  let closest = null;
  let minDist = Infinity;
  for (const en of enemies) { ... if (d < minDist) { minDist = d; closest = en; } }
  if (closest) { ... }
INTERDIT :
  if (closest) { ... }  // closest jamais déclaré → ReferenceError

RÈGLE ABSOLUE N°12 — TIMERS D'ENNEMIS : INITIALISER DANS createEnemy() :
Si ENEMY_DEFS déclare `fireRateTimer:0`, `shieldTimer:0`, `flashTimer:0`, etc.,
ces mêmes propriétés DOIVENT être dans l'objet retourné par createEnemy().
CORRECT :
  function createEnemy(type, x, y) {
    const def = ENEMY_DEFS.find(d => d.type === type);
    return { ...def, x, y, hp: def.maxHp,
      fireRateTimer: 0, shieldTimer: 0, flashTimer: 0,  // ← tous les timers
      knockbackTimer: 0, specialTimer: 0 };
  }
INTERDIT : return { type, x, y, hp }  // timers absents → undefined → NaN → comportement erratique

RÈGLE ABSOLUE N°13 — VIRGULE ENTRE PROPRIÉTÉS D'OBJET :
Chaque propriété d'un objet doit être séparée de la suivante par une virgule.
L'absence d'une virgule cause "Unexpected token ':'" au runtime → ÉCRAN NOIR.
CORRECT : { a: 1, b: 2, c: 3 }
INTERDIT : { a: 1  b: 2  c: 3 }  // manque virgules → Unexpected token ':'
MÉTHODE : après chaque valeur (sauf la dernière), toujours mettre une virgule.

RÈGLE ABSOLUE N°14 — EVENT_DEFS / UPGRADE_DEFS / BOSS_DEFS : DÉCLARER AVANT D'UTILISER :
Si le code utilise `EVENT_DEFS['elite_swarm']` ou `UPGRADE_DEFS['shield']`, ces objets
DOIVENT être déclarés AVANT leur première utilisation.
CORRECT : const EVENT_DEFS = { elite_swarm: {...}, power_surge: {...} };
INTERDIT : handleGameEvents() appelle EVENT_DEFS[x] sans déclaration → ReferenceError → crash

RÈGLE ABSOLUE N°15 — PARAMÈTRES DE FONCTION COMPLETS :
Chaque fonction doit déclarer TOUS les paramètres qu'elle utilise dans sa signature.
CORRECT : function createProjectile(x, y, vx, vy, isPlayer, damage) { ... }
INTERDIT : function createProjectile(x, y, vx, vy) { if (isPlayer) { ... } }
           // isPlayer non déclaré → ReferenceError au premier appel

RÈGLE ABSOLUE N°16 — EVENT LISTENERS : TOUS À L'INTÉRIEUR DE DOMContentLoaded :
`canvas` est une variable locale initialisée DANS DOMContentLoaded.
Tout addEventListener qui utilise `canvas` DOIT être à l'intérieur de ce callback.

RÈGLE ABSOLUE N°17 — FOR-INDEX : TOUJOURS DÉCLARER L'ÉLÉMENT DE BOUCLE :
Dans un `for (let i = 0; i < arr.length; i++)`, si tu utilises `elem.prop`, tu DOIS d'abord déclarer :
  const elem = arr[i];
CORRECT :
  for (let i = 0; i < enemies.length; i++) {
    const e = enemies[i];
    e.x += e.vx * dt;
  }
INTERDIT :
  for (let i = 0; i < enemies.length; i++) {
    e.x += e.vx * dt;  // CRASH : e is not defined
  }

RÈGLE ABSOLUE N°18 — WAVE_DEFS / ENEMY_TYPES : PASSER .type, JAMAIS L'OBJET ENTIER :
Quand tu itères un tableau de définitions pour spawner un ennemi, passe la PROPRIÉTÉ `type`, pas l'objet complet.
CORRECT :
  const def = WAVE_DEFS[Math.min(wave-1, WAVE_DEFS.length-1)];
  const type = def.types[Math.floor(Math.random() * def.types.length)];
  spawnEnemy(type, x, y);   // type est une string comme "basic"
INTERDIT :
  spawnEnemy(def, x, y);    // def est l'objet entier → enemy.type = { count:6, types:[...] } → crash

CORRECT :
  document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('gameCanvas');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const ctx = canvas.getContext('2d');
    // Clavier → sur document (pas canvas)
    document.addEventListener('keydown', e => { keys[e.code] = true; });
    document.addEventListener('keyup',   e => { keys[e.code] = false; });
    // Souris → sur canvas (à l'intérieur du callback)
    canvas.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
    canvas.addEventListener('click',     e => { mouse.clicked = true; });
    requestAnimationFrame(gameLoop);
  });
INTERDIT (cause ÉCRAN NOIR garanti) :
  canvas.addEventListener('keydown', ...);   // ← AVANT DOMContentLoaded → canvas=undefined → crash
  document.addEventListener('DOMContentLoaded', function() {
    const canvas = ...;   // trop tard, les listeners ont déjà crashé
  });
RÈGLE : les écouteurs clavier attachés à `document` fonctionnent partout et n'ont pas besoin de canvas.

RÈGLE ABSOLUE N°19 — FOND NON-NOIR OBLIGATOIRE (Q1) :
Le fond du jeu NE DOIT JAMAIS être du noir uni (#000 ou '#000000').
OBLIGATOIRE : utilise un dégradé de fond ou une couleur riche sombre (ex: '#0a0a1e', '#1a0a2e', '#0d1b2a').
CORRECT (dégradé) :
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, '#0a0a1e'); grad.addColorStop(1, '#1a0a2e');
  ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);
CORRECT (couleur riche sombre) :
  ctx.fillStyle = '#0d1b2a'; ctx.fillRect(0, 0, W, H);
INTERDIT : ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);  // noir uni → rendu mort
INTERDIT : ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, W, H);

RÈGLE ABSOLUE N°20 — GAME FEEL OBLIGATOIRE (Q2) :
Tout jeu avec impacts ou explosions DOIT implémenter :
a) Screen shake (voir Pattern 13) — déclenché sur mort joueur, explosions, boss hits
b) Flash d'impact — éclair blanc bref sur l'écran quand le joueur prend des dégâts :
   let flashTimer = 0;
   function triggerFlash(dur=0.1) { flashTimer = dur; }
   // Dans draw(), APRÈS tous les dessins :
   // if (flashTimer > 0) { ctx.fillStyle = 'rgba(255,255,255,' + (flashTimer*3) + ')'; ctx.fillRect(0,0,W,H); flashTimer -= 1/60; }
   // Usage : triggerFlash(0.08); // sur hit joueur; triggerFlash(0.15); // sur explosion
Ces deux effets coûtent 5 lignes chacun — aucune excuse de les omettre.

RÈGLE ABSOLUE N°21 — WEB AUDIO OBLIGATOIRE (Q3) :
L'objet `sfx` (Pattern 14) est OBLIGATOIRE dans tout jeu.
NE PAS utiliser un stub vide `{ play(){} }` — implémenter la vraie version WebAudio.
Appels obligatoires : sfx.play() sur tir, collecte, mort ennemi, game over, et powerup.
Un jeu sans son est immédiatement pénalisé en évaluation.

PATTERNS OBLIGATOIRES — reproduis-les exactement :

0. STRUCTURE HTML COMPLÈTE [tags: always] (modèle à suivre) :
<!DOCTYPE html>
<html><head><title>NomDuJeu</title><style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#000; overflow:hidden; }
canvas { display:block; }
/* INTERDIT : canvas { background-color: ... } */
</style></head>
<body>
<canvas id="gameCanvas"></canvas>   <!-- ← OBLIGATOIRE dans le body HTML -->
<script>
document.addEventListener('DOMContentLoaded', function() {
  const canvas = document.getElementById('gameCanvas');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const ctx = canvas.getContext('2d');
  /* ... tout le jeu ici ... */
  requestAnimationFrame(gameLoop);
});
</script>
</body></html>

1. WRAPPER DOM-READY [tags: always] (tout le code JS à l'intérieur) :
document.addEventListener('DOMContentLoaded', function() {
  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d');
  /* ... tout le jeu ici ... */
  requestAnimationFrame(gameLoop);
});

2. GAME LOOP [tags: always] avec delta time :
let lastTime = 0;
function gameLoop(timestamp) {
  const dt = Math.min((timestamp - lastTime) / 1000, 0.05);
  lastTime = timestamp;
  update(dt);
  draw();
  requestAnimationFrame(gameLoop);
}

3. INPUT [tags: always] — noms IDENTIQUES dans la déclaration, les handlers ET update() :
const keys = { left: false, right: false, up: false, down: false, space: false };
// Handler générique recommandé (utilise "key in keys", JAMAIS keys.hasOwnProperty) :
document.addEventListener('keydown', e => { const k = e.key.toLowerCase(); if (k in keys) keys[k] = true; });
document.addEventListener('keyup',   e => { const k = e.key.toLowerCase(); if (k in keys) keys[k] = false; });
// ⚠️ INTERDIT : keys.hasOwnProperty(k) → écrase la méthode native et casse tous les inputs
// ✅ CORRECT   : k in keys → vérifie l'existence de la propriété sans risque
// update() : if (keys.left) player.x -= speed * dt;  ← même nom "left"

4. TYPES D'ENTITÉS [tags: always] — ne jamais mettre "type" dans behavior, utiliser "behaviorType" :
// INTERDIT : behavior = { vx:50, type:'stompable' } puis return { type, ...behavior }
//            → behavior.type écrase le type visuel, draw() et collision() se cassent
// CORRECT  : behavior = { vx:50, behaviorType:'stompable' }
//            return { type, ...behavior }  → type = 'mouse', behaviorType = 'stompable'
// Collision : if (enemy.behaviorType === 'stompable') { ... }
// Draw      : if (this.type === 'mouse') { ... }

5. TABLEAUX [tags: always] — vider avec .length = 0 (PAS .clear() qui n'existe pas) :
bullets.length = 0;   // CORRECT
enemies.length = 0;   // CORRECT
// enemies.clear();   // INTERDIT — TypeError à l'exécution

5. MODULES [tags: always] — tout objet appelé DOIT être déclaré dans ce fichier :
const audioManager = { play(s){}, stop(){} };  // Déclaré AVANT utilisation
const particles = { list:[], emit(x,y,c){}, update(dt){}, draw(ctx){} };

6. STATE MACHINE [tags: always] :
let gameState = 'menu'; // valeurs: 'menu' | 'playing' | 'paused' | 'gameover'
function update(dt) {
  if (gameState === 'playing') { updateGame(dt); }
  else if (gameState === 'menu') { updateMenu(); }
}

7. GAME OVER + RESTART [tags: always] — obligatoire :
// Sur game over : gameState = 'gameover', afficher score final + "Appuie sur ESPACE pour rejouer"
// Sur restart : réinitialiser TOUTES les variables (score=0, lives=3, enemies.length=0, etc.)
// Ne jamais utiliser location.reload() pour recharger — tout reset doit être en JS pur.

8. MENU avec instructions [tags: always] :
// L'écran menu DOIT afficher : titre du jeu + contrôles + "Appuie sur ESPACE/ENTER pour jouer"
// ⚠️ OBLIGATOIRE : utilise drawButton() du Pattern #19 pour le bouton "Jouer" — il doit être cliquable à la souris ET activable au clavier (ESPACE/ENTER).
// Si le jeu a une sélection de personnages, chaque carte de personnage DOIT être cliquable via registerZone() + hitTest().

9. SCORE et MEILLEUR SCORE [tags: always] :
const bestScore = parseInt(localStorage.getItem('highscore') || '0');
// Sur game over : if (score > bestScore) localStorage.setItem('highscore', score);

9b. HAZARDS ET COLLISIONS [tags: always] — règles obligatoires :
// a) Tout hazard (plateforme électrifiée, piège, spike) DOIT être évitable par le joueur.
//    Ne JAMAIS placer un hazard sur le chemin obligatoire pour progresser dans le niveau.
//    Le joueur doit toujours avoir un itinéraire sans hazard pour atteindre la sortie.
// b) La collision avec un hazard DOIT être codée explicitement :
//    if (p.type === 'electrified') { player.takeDamage(1); }  ← dans la boucle de collision
//    Ne pas écrire "handled elsewhere" sans implémenter réellement le code.
// c) Utiliser 'behaviorType' (pas 'type') dans les objets behavior pour éviter les conflits :
//    behavior = { vx: 50, behaviorType: 'stompable' }  // PAS type: 'stompable'

10. NULL GUARDS [tags: always] — obligatoire pour tout objet initialisé à null :
// Si currentLevel, player, ou tout autre objet est null au départ :
// TOUJOURS vérifier avant d'accéder à ses propriétés dans draw() et update()
function draw() {
  ctx.fillStyle = BG_COLOR; ctx.fillRect(0, 0, W, H); // fond EN PREMIER
  if (!currentLevel) { drawMenu(ctx); return; }        // null guard → sortie propre
  // ... reste du dessin
}
// INTERDIT : currentLevel.width sans vérifier if (currentLevel) avant

11. DRAW() [tags: always] — ordre obligatoire (respecte cet ordre EXACTEMENT) :
function draw() {
  // ÉTAPE 1 : fond plein EN PREMIER (remplace clearRect — évite l'écran vide si erreur)
  ctx.fillStyle = BACKGROUND_COLOR;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  // ÉTAPE 2 : décors (calques arrière-plan, étoiles, nuages...)
  // ÉTAPE 3 : objets de jeu (plateformes, ennemis, joueur, projectiles...)
  // ÉTAPE 4 : HUD/UI (score, vies, timer — TOUJOURS EN DERNIER)
}
// RÈGLE CRITIQUE : NE JAMAIS faire ctx.clearRect() puis ctx.save()/translate() AVANT le fond.
// Le fond doit être la TOUTE PREMIÈRE opération de draw(), sinon une erreur JS après clearRect
// laisse un canvas transparent et le joueur voit le background-color CSS à la place.

11. CSS CANVAS [tags: always] — interdit absolu de mettre une couleur de fond CSS sur le canvas :
// INTERDIT : canvas { background-color: #87CEEB; }
// Le fond est géré uniquement par JS (fillRect en début de draw())
// Canvas CSS autorisé : display:block; width:100vw; height:100vh; object-fit:contain;

12. PARTICLE SYSTEM [tags: always] — implémenter TOUJOURS ce template exact (ne jamais le stubber) :
const particles = [];
function spawnParticles(x, y, color, count = 10) {
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 / count) * i + Math.random() * 0.5;
    const speed = 60 + Math.random() * 100;
    particles.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      life: 1.0, size: 3 + Math.random() * 4, color });
  }
}
function updateParticles(dt) {
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.x += p.vx * dt; p.y += p.vy * dt;
    p.vy += 80 * dt;  // légère gravité sur les particules
    p.life -= dt * 2.5;
    if (p.life <= 0) particles.splice(i, 1);
  }
}
function drawParticles() {
  particles.forEach(p => {
    ctx.globalAlpha = p.life;
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
  });
  ctx.globalAlpha = 1;
}
// Usage : spawnParticles(enemy.x, enemy.y, '#FFD700', 10); // à la mort d'un ennemi
// Dans draw() : appeler drawParticles() AVANT le HUD
// Dans update(dt) : appeler updateParticles(dt)

13. SCREEN SHAKE [tags: always] — implémenter TOUJOURS ce template :
let shakeTime = 0, shakeMag = 0;
function triggerShake(mag, dur) { shakeMag = mag; shakeTime = dur; }
// Dans draw(), AVANT tous les ctx.save() :
// if (shakeTime > 0) { ctx.translate((Math.random()-0.5)*shakeMag*2, (Math.random()-0.5)*shakeMag*2); shakeTime -= 1/60; }
// Usage : triggerShake(6, 0.2); // sur mort joueur ; triggerShake(3, 0.1); // sur impact

14. AUDIO [tags: always] — toujours déclarer ce stub (évite TypeError si play() appelé sans init) :
// RÈGLE CRITIQUE : NE JAMAIS appeler sfx.init() dans DOMContentLoaded — Chrome bloque AudioContext
// sans geste utilisateur et lève une DOMException qui crashe tout → écran noir garanti.
// sfx.init() est appelé AUTOMATIQUEMENT au premier sfx.play() déclenché par un input joueur.
const sfx = {
  _ctx: null,
  init() { try { if (!this._ctx) this._ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {} },
  play(freq = 440, dur = 0.1, type = 'square', vol = 0.15) {
    try {
      this.init();
      if (!this._ctx) return;
      const o = this._ctx.createOscillator(), g = this._ctx.createGain();
      o.type = type; o.frequency.value = freq;
      g.gain.setValueAtTime(vol, this._ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, this._ctx.currentTime + dur);
      o.connect(g); g.connect(this._ctx.destination);
      o.start(); o.stop(this._ctx.currentTime + dur);
    } catch(e) {}
  }
};
// Usage : sfx.play(220, 0.15, 'sawtooth'); // tir
//         sfx.play(80, 0.3, 'sine');        // explosion
//         sfx.play(660, 0.1, 'square');     // collectible

15. SYSTÈME D'INTERACTIONS ENVIRONNEMENTALES [tags: interactive, adventure, shooter, platformer] — à implémenter dès que la section GAME LOGICS
    décrit des leviers, plaques, coffres, portails, zones d'effet ou tout objet interactif.
    Ce pattern est OBLIGATOIRE si ces mécaniques sont dans le design du jeu :
// ── Touche E = interaction de proximité ──
// Ajouter 'e: false' dans l'objet keys{}
// document.addEventListener('keydown', e => { if (e.key==='e'||e.key==='E') keys.e = true; });
// document.addEventListener('keyup',   e => { if (e.key==='e'||e.key==='E') keys.e = false; });

// ── Structure universelle d'un objet interactif ──
// const interactables = [];
// function createInteractable(x, y, w, h, type, linkedId = null, data = {}) {
//   return { x, y, w, h, type, linkedId, data, nearPlayer: false, used: false, state: false };
// }
// Types possibles : 'lever', 'pressure_plate', 'chest', 'door', 'key', 'teleporter', 'button_timed'

// ── Détection de proximité + prompt [E] ──
// function checkInteractions() {
//   const INTERACT_RANGE = 55; // px
//   for (const obj of interactables) {
//     const dx = (player.x + player.w/2) - (obj.x + obj.w/2);
//     const dy = (player.y + player.h/2) - (obj.y + obj.h/2);
//     obj.nearPlayer = Math.abs(dx) < INTERACT_RANGE && Math.abs(dy) < INTERACT_RANGE;
//     if (obj.nearPlayer && keys.e && !keys.e_prev) { // edge trigger (une seule activation)
//       activateInteractable(obj);
//     }
//   }
//   keys.e_prev = keys.e; // mémoriser l'état précédent pour edge-trigger
// }

// ── Activation selon le type ──
// function activateInteractable(obj) {
//   switch (obj.type) {
//     case 'lever':
//       obj.state = !obj.state; // toggle
//       // Trouver et modifier l'objet lié (porte, mécanisme)
//       const linked = interactables.find(o => o.linkedId === obj.linkedId && o.type === 'door');
//       if (linked) linked.open = obj.state;
//       sfx.play(obj.state ? 440 : 330, 0.15, 'square');
//       spawnParticles(obj.x + obj.w/2, obj.y, '#FFD700', 6);
//       break;
//     case 'pressure_plate':
//       if (!obj.used) {
//         obj.used = true;
//         // Faire apparaître des pièces autour de la plaque
//         for (let i = 0; i < 5; i++) coins.push(createCoin(obj.x + (i-2)*20, obj.y - 30));
//         sfx.play(660, 0.12, 'sine');
//       }
//       break;
//     case 'chest':
//       if (!obj.used) {
//         obj.used = true; obj.state = true; // état ouvert
//         powerups.push(createPowerup(obj.x, obj.y - 20, obj.data.itemType || 'random'));
//         sfx.play(880, 0.2, 'sine'); spawnParticles(obj.x + obj.w/2, obj.y, '#FFD700', 12);
//       }
//       break;
//     case 'key':
//       if (!obj.used) { obj.used = true; player.keys = (player.keys || 0) + 1; sfx.play(780, 0.1, 'square'); }
//       break;
//     case 'door':
//       if (player.keys > 0 && !obj.open) {
//         obj.open = true; player.keys--;
//         sfx.play(200, 0.3, 'sine'); spawnParticles(obj.x + obj.w/2, obj.y + obj.h/2, '#88FFAA', 15);
//       }
//       break;
//     case 'teleporter':
//       player.x = obj.data.targetX; player.y = obj.data.targetY;
//       sfx.play(1000, 0.15, 'sine'); spawnParticles(player.x, player.y, '#00FFFF', 10);
//       break;
//     case 'button_timed':
//       obj.timerActive = true; obj.timer = obj.data.duration || 5.0;
//       const target = interactables.find(o => o.linkedId === obj.linkedId && o.type === 'door');
//       if (target) target.open = true;
//       sfx.play(550, 0.1, 'square');
//       break;
//   }
// }
// // Pour button_timed : dans update(dt)
// // for (const obj of interactables) {
// //   if (obj.type === 'button_timed' && obj.timerActive) {
// //     obj.timer -= dt; if (obj.timer <= 0) { obj.timerActive = false;
// //       const t = interactables.find(o => o.linkedId === obj.linkedId && o.type==='door');
// //       if (t) t.open = false; } } }

// ── Rendu des objets interactifs ──
// function drawInteractables() {
//   for (const obj of interactables) {
//     // Porte — n'existe physiquement que si fermée
//     if (obj.type === 'door' && obj.open) continue;
//     // Clé — disparaît si ramassée
//     if ((obj.type === 'key' || obj.type === 'chest') && obj.used && obj.type === 'key') continue;
//
//     // Dessin selon le type
//     if (obj.type === 'lever') {
//       ctx.fillStyle = obj.state ? '#44FF88' : '#886644';
//       ctx.fillRect(obj.x, obj.y, obj.w, obj.h);
//       ctx.fillStyle = '#FFD700'; // manette
//       const handleX = obj.state ? obj.x + obj.w - 4 : obj.x;
//       ctx.fillRect(handleX, obj.y - 6, 4, obj.h + 6);
//     } else if (obj.type === 'pressure_plate') {
//       ctx.fillStyle = obj.used ? '#556655' : '#88FF44';
//       ctx.fillRect(obj.x, obj.y, obj.w, obj.h);
//       ctx.strokeStyle = '#AAFFAA'; ctx.lineWidth = 2;
//       ctx.strokeRect(obj.x + 2, obj.y + 2, obj.w - 4, obj.h - 4);
//     } else if (obj.type === 'chest') {
//       ctx.fillStyle = obj.used ? '#554433' : '#AA8833';
//       ctx.fillRect(obj.x, obj.y, obj.w, obj.h);
//       ctx.fillStyle = '#FFD700'; ctx.fillRect(obj.x + 4, obj.y, obj.w - 8, 6); // couvercle
//       if (obj.state) { ctx.fillStyle = '#FFD700'; ctx.fillRect(obj.x, obj.y - 10, obj.w, 10); } // ouvert
//     } else if (obj.type === 'door') {
//       ctx.fillStyle = '#664422';
//       ctx.fillRect(obj.x, obj.y, obj.w, obj.h);
//       if (player.keys > 0) { ctx.strokeStyle = '#FFD700'; ctx.lineWidth = 2; ctx.strokeRect(obj.x, obj.y, obj.w, obj.h); }
//     } else if (obj.type === 'key') {
//       ctx.fillStyle = '#FFD700';
//       ctx.beginPath(); ctx.arc(obj.x + obj.w/2, obj.y + 8, 7, 0, Math.PI*2); ctx.fill();
//       ctx.fillRect(obj.x + obj.w/2 - 2, obj.y + 14, 4, 14);
//     } else if (obj.type === 'teleporter') {
//       ctx.fillStyle = `hsl(${Date.now()*0.1 % 360}, 80%, 60%)`;
//       ctx.beginPath(); ctx.ellipse(obj.x + obj.w/2, obj.y + obj.h/2, obj.w/2, obj.h/2, 0, 0, Math.PI*2); ctx.fill();
//     } else {
//       ctx.fillStyle = '#888888'; ctx.fillRect(obj.x, obj.y, obj.w, obj.h);
//     }
//
//     // Prompt [E] si le joueur est proche
//     if (obj.nearPlayer && !obj.used) {
//       ctx.fillStyle = '#FFD700'; ctx.font = 'bold 12px Arial';
//       ctx.textAlign = 'center';
//       ctx.fillText('[E]', obj.x + obj.w / 2, obj.y - 10);
//       ctx.textAlign = 'left';
//       // Halo clignotant
//       ctx.strokeStyle = `rgba(255,215,0,${0.5 + 0.5 * Math.sin(Date.now() * 0.005)})`;
//       ctx.lineWidth = 2;
//       ctx.strokeRect(obj.x - 2, obj.y - 2, obj.w + 4, obj.h + 4);
//     }
//     // Indicateur de porte verrouillée
//     if (obj.type === 'door' && !obj.open && player.keys === 0) {
//       ctx.fillStyle = '#FF4444'; ctx.font = '10px Arial'; ctx.textAlign = 'center';
//       ctx.fillText('🔒', obj.x + obj.w/2, obj.y - 6); ctx.textAlign = 'left';
//     }
//   }
// }
// IMPORTANT : appeler drawInteractables() APRÈS les plateformes, AVANT le joueur et le HUD.
// IMPORTANT : appeler checkInteractions() dans update() à chaque frame.

16. COMBAT AU TOUR PAR TOUR (RPG) [tags: rpg] — OBLIGATOIRE si le genre est RPG ou si GAME LOGICS décrit un système de tours :
// ⚠️ OBLIGATOIRE : les boutons Attaquer/Sort/Fuir/Objet DOIVENT être dessinés avec drawButton() (Pattern #19).
// Chaque bouton doit répondre AUSSI bien à la souris (clic) qu'au clavier (touches 1/2/3/4 ou Z/X/C).
// Ne jamais bloquer le jeu en attendant uniquement une touche clavier pour une action de combat.
// ── 3 règles d'or que le LLM oublie toujours ──
// RÈGLE 1 : auto-sélection du héros actif quand son tour arrive
// Dans la fonction updateCombat(), quand c'est un tour joueur :
//   selectedHeroIndex = party.indexOf(activeCombatant); // ← TOUJOURS forcer la sélection
// RÈGLE 2 : les ennemis DOIVENT agir immédiatement (pas de timer bloqué)
// Après l'action ennemie : turnTimer = 0.8; activeTurnIndex = (activeTurnIndex+1) % turnOrder.length;
// RÈGLE 3 : XP distribué à TOUS les membres survivants après la victoire
// function endCombat(victory) {
//   if (victory) {
//     const xpTotal = defeatedEnemies.reduce((s,e) => s + (e.xpValue||10), 0);
//     party.filter(h => h.hp > 0).forEach(h => { h.xp += xpTotal; checkLevelUp(h); });
//   }
// }
// function checkLevelUp(hero) {
//   while (hero.xp >= hero.xpToNext) {
//     hero.xp -= hero.xpToNext; hero.level++;
//     hero.maxHp += 10; hero.hp = hero.maxHp; // restore on level up
//     hero.attack += 2; hero.xpToNext = Math.floor(hero.xpToNext * 1.5);
//     spawnFloatingText(hero.x, hero.y, `LEVEL UP! Lvl ${hero.level}`, '#FFD700');
//   }
// }

17. VISUELS RPG [tags: rpg] — OBLIGATOIRE si genre RPG :
// Personnages : dessiner avec des formes géométriques distinctes par classe (cercle=mage, carré=guerrier, triangle=rogue)
// Couleurs par classe avec border + ombre portée pour donner de la profondeur
// Barre de vie COLORÉE sous chaque personnage : rouge quand bas, vert quand plein
// Carte/grille isométrique ou vue dessus avec tuiles de couleurs différentes (herbe, pierre, eau)
// HUD de combat avec cadres stylisés pour chaque héros (nom, HP/maxHP, icône de classe)
// Ennemis visuellement différents du joueur (couleurs vives, formes agressives)
// Animations de dégâts : shake du sprite touché + chiffre qui monte
// Minimum : ctx.shadowBlur, dégradés, ou effets de lueur sur les sorts

18. MODE PIXEL ART RÉTRO [tags: pixelart] — à utiliser si le prompt mentionne "pixel art", "rétro", "zelda", "pokemon", "nes", "game boy", "8-bit", "16-bit" :
// ── Setup canvas basse résolution scalée ──
// const SCALE = 3;         // chaque pixel jeu = 3px écran
// const GW = 160, GH = 144; // résolution Game Boy (ou 256×240 NES)
// const off = document.createElement('canvas');
// off.width = GW; off.height = GH;
// const gctx = off.getContext('2d');
// gctx.imageSmoothingEnabled = false;
// canvas.width = GW * SCALE; canvas.height = GH * SCALE;
// ctx.imageSmoothingEnabled = false; // ← OBLIGATOIRE pour pixels nets

// ── Rendu en fin de draw() — 1 seule ligne ──
// ctx.drawImage(off, 0, 0, GW * SCALE, GH * SCALE);

// ── Dessin de sprites pixel art via tableaux ──
// function drawSprite(ctx, sprite, x, y, palette) {
//   sprite.forEach((row, dy) => row.forEach((c, dx) => {
//     if (!c) return; // 0 = transparent
//     ctx.fillStyle = palette[c];
//     ctx.fillRect(x + dx, y + dy, 1, 1);
//   }));
// }
// Exemple sprite héros 8×8 (index de palette) :
// const HERO_SPRITE = [
//   [0,0,2,2,2,2,0,0],
//   [0,2,1,1,1,1,2,0],
//   [0,2,1,3,3,1,2,0],
//   [0,0,2,2,2,2,0,0],
//   [0,1,2,2,2,2,1,0],
//   [1,1,0,2,2,0,1,1],
//   [0,0,0,1,1,0,0,0],
//   [0,0,1,0,0,1,0,0],
// ];
// ── Palettes NES réalistes (la NES affichait jusqu'à 25 couleurs simultanément) ──
// Zelda NES  : ['transparent','#000000','#70C848','#3050C0','#F8B800','#D82800','#BCBCBC','#FCFCFC','#A800A8','#F8D8B0','#3CBCFC','#507800','#F87858']
// Mario NES  : ['transparent','#000000','#D82800','#FC7460','#F8B800','#0058F8','#00A800','#BCBCBC','#FCFCFC','#F8D8B0','#AC7C00','#503000']
// Mega Man   : ['transparent','#000000','#0058F8','#3CBCFC','#FCFCFC','#D82800','#F8B800','#00A800','#70C848','#A800A8','#BCBCBC']
// Pokémon GB : ['transparent','#0f380f','#306230','#8bac0f','#9bbc0f']
// RÈGLE : choisir une palette principale de 8-16 couleurs ET LA RESPECTER sur tous les sprites.
// Chaque "sous-palette" (héros, ennemis, décors, HUD) = 4 couleurs max, mais l'ensemble peut être riche.

// ── Police pixel art ──
// ctx.font = 'bold 8px monospace'; ctx.imageSmoothingEnabled = false;
// Pour les chiffres : dessiner en pixel art avec des tableaux (comme les sprites)

// ── Souris en pixel art — SCALING OBLIGATOIRE ──
// En mode pixel art (canvas interne GW×GH scalé à GW*SCALE × GH*SCALE), les coords
// souris doivent être divisées par SCALE pour correspondre à l'espace de jeu :
// canvas.addEventListener('mousemove', e => {
//   const r = canvas.getBoundingClientRect();
//   mouse.x = Math.floor((e.clientX - r.left) * (canvas.width / r.width) / SCALE);
//   mouse.y = Math.floor((e.clientY - r.top)  * (canvas.height / r.height) / SCALE);
// });
// canvas.addEventListener('click', e => {
//   const r = canvas.getBoundingClientRect();
//   mouse.x = Math.floor((e.clientX - r.left) * (canvas.width / r.width) / SCALE);
//   mouse.y = Math.floor((e.clientY - r.top)  * (canvas.height / r.height) / SCALE);
//   mouse.clicked = true;
// });
// RÈGLE : Toujours diviser par SCALE — sans ça, les clicks sont décalés d'un facteur 3.

20. ANIMATION DE SPRITES PIXEL ART [tags: pixelart] — OBLIGATOIRE si pixel art et si le jeu a un personnage
    qui se déplace ou attaque. Un sprite statique = rendu mort. Minimum : marche 4 frames + idle.

// ── Système d'animation frame-based ──
// Chaque entité a : { frameIndex: 0, frameTick: 0, frameSpeed: 8, state: 'idle', facing: 'down' }
// SPRITES organisés par état et direction :
// const HERO_FRAMES = {
//   idle:  { down: [[...8x8...]], up: [[...]], left: [[...]], right: [[...]] },
//   walk:  { down: [ frame0_8x8, frame1_8x8, frame2_8x8, frame3_8x8 ],
//             up:   [ ... ], left: [ ... ], right: [ ... ] },
//   attack:{ down: [ frame0, frame1, frame2 ], up:[...], left:[...], right:[...] },
// };
// function animateEntity(entity, dt) {
//   entity.frameTick++;
//   if (entity.frameTick >= entity.frameSpeed) {
//     entity.frameTick = 0;
//     const frames = HERO_FRAMES[entity.state]?.[entity.facing] || HERO_FRAMES.idle.down;
//     entity.frameIndex = (entity.frameIndex + 1) % frames.length;
//   }
// }
// function drawEntity(entity) {
//   const frames = HERO_FRAMES[entity.state]?.[entity.facing] || HERO_FRAMES.idle.down;
//   const sprite = frames[entity.frameIndex] || frames[0];
//   drawSprite(gctx, sprite, Math.floor(entity.screenX), Math.floor(entity.screenY), entity.palette);
// }
// Mettre à jour l'état selon le mouvement :
// if (moving) { entity.state = 'walk'; entity.facing = dx>0?'right':dx<0?'left':dy>0?'down':'up'; }
// else { entity.state = 'idle'; }
// if (attacking) { entity.state = 'attack'; }
// Appeler animateEntity(hero, dt) dans update(), drawEntity(hero) dans draw()

21. TILEMAP + CAMÉRA SCROLLING [tags: pixelart, adventure, rpg] — OBLIGATOIRE pour tout jeu d'exploration (Zelda, RPG vue dessus).
    Sans scrolling le monde est limité à 1 écran — inacceptable pour ce genre.

// ── Tilemap (tableau 2D d'indices) ──
// const TILE = { GRASS:0, STONE:1, WATER:2, WALL:3, SAND:4, TREE:5, CHEST:6, LEVER:7 };
// const TILE_SOLID = new Set([TILE.WALL, TILE.WATER, TILE.TREE]); // bloquants
// const MAP_W = 40, MAP_H = 30; // tailles en tuiles
// const TILE_SIZE = 16; // px dans l'espace jeu (avant scale)
// const map = Array.from({length: MAP_H}, () => new Array(MAP_W).fill(TILE.GRASS));
// // Remplir map[][] avec la génération procédurale ou un niveau statique

// ── Dessin d'une tuile ──
// const TILE_COLORS = {
//   [TILE.GRASS]: ['#70C848','#58A838'],  // 2 teintes alternées (damier)
//   [TILE.STONE]: ['#BCBCBC','#A0A0A0'],
//   [TILE.WATER]: ['#3CBCFC','#1890D8'],  // animé (alterner selon frame)
//   [TILE.WALL]:  ['#504030','#382818'],
//   [TILE.SAND]:  ['#F8D878','#E0C060'],
//   [TILE.TREE]:  ['#007800','#005000'],
// };
// function drawTile(tileId, tx, ty, frame) {
//   const colors = TILE_COLORS[tileId] || ['#888','#666'];
//   const alt = (tileId === TILE.WATER) ? frame % 2 : (tx + ty) % 2;
//   gctx.fillStyle = colors[alt];
//   gctx.fillRect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE);
//   // Détails supplémentaires par type :
//   if (tileId === TILE.GRASS && Math.random() < 0.05) { // brins d'herbe
//     gctx.fillStyle = '#90E050';
//     gctx.fillRect(tx*TILE_SIZE+4, ty*TILE_SIZE+10, 1, 4);
//     gctx.fillRect(tx*TILE_SIZE+10, ty*TILE_SIZE+8, 1, 6);
//   }
//   if (tileId === TILE.WALL) { // joints de pierres
//     gctx.fillStyle = '#282010';
//     gctx.fillRect(tx*TILE_SIZE, ty*TILE_SIZE, TILE_SIZE, 1);
//     gctx.fillRect(tx*TILE_SIZE, ty*TILE_SIZE, 1, TILE_SIZE);
//   }
// }

// ── Caméra centrée sur le joueur ──
// let cam = { x: 0, y: 0 }; // coin haut-gauche en px jeu
// function updateCamera() {
//   cam.x = Math.floor(hero.x - GW/2 + TILE_SIZE/2);
//   cam.y = Math.floor(hero.y - GH/2 + TILE_SIZE/2);
//   // Clamp aux bords de la map
//   cam.x = Math.max(0, Math.min(cam.x, MAP_W*TILE_SIZE - GW));
//   cam.y = Math.max(0, Math.min(cam.y, MAP_H*TILE_SIZE - GH));
// }
// ── Rendu du tilemap visible ──
// function drawMap(frame) {
//   const startX = Math.floor(cam.x / TILE_SIZE);
//   const startY = Math.floor(cam.y / TILE_SIZE);
//   const endX = Math.min(MAP_W, startX + Math.ceil(GW/TILE_SIZE) + 1);
//   const endY = Math.min(MAP_H, startY + Math.ceil(GH/TILE_SIZE) + 1);
//   for (let ty = startY; ty < endY; ty++)
//     for (let tx = startX; tx < endX; tx++)
//       drawTile(map[ty][tx], tx - startX + (startX - cam.x/TILE_SIZE|0),
//                              ty - startY + (startY - cam.y/TILE_SIZE|0), frame);
// }
// Toutes les entités : screenX = entity.x - cam.x,  screenY = entity.y - cam.y
// Collision tilemap : isSolid(x, y) → TILE_SOLID.has(map[Math.floor(y/TILE_SIZE)][Math.floor(x/TILE_SIZE)])

22. BOÎTE DE DIALOGUE RPG PIXEL ART AVANCÉE [tags: rpg, adventure] — OBLIGATOIRE si le jeu a des PNJ, des coffres,
    des quêtes ou tout événement narratif. Supporte : speaker name, portrait, choix multiples.

// ── Dialog avancé : narratif + choix + speaker + portrait ──
// let dialog = {
//   active: false, lines: [], lineIndex: 0, charIndex: 0, tick: 0, speed: 2,
//   onClose: null, speaker: '', portraitFn: null,   // speaker = nom affiché, portraitFn = fn(ctx,x,y,w,h)
//   choices: null, selectedChoice: 0, onChoice: null // choices = [{label,id}] pour le mode choix
// };
// function showDialog(lines, onClose = null, speaker = '', portraitFn = null) {
//   dialog = { active: true, lines, lineIndex: 0, charIndex: 0, tick: 0, speed: 2,
//              onClose, speaker, portraitFn, choices: null, selectedChoice: 0, onChoice: null };
//   gameState = 'dialog';
// }
// function showChoiceDialog(text, choices, onChoice, speaker = '') {
//   // choices = [{label: 'Accepter', id: 'yes'}, {label: 'Refuser', id: 'no'}]
//   dialog = { active: true, lines: [text], lineIndex: 0, charIndex: text.length, tick: 0, speed: 2,
//              onClose: null, speaker, portraitFn: null,
//              choices, selectedChoice: 0, onChoice };
//   gameState = 'dialog';
// }
// function updateDialog() {
//   if (!dialog.active) return;
//   // ── Mode choix : navigation flèches haut/bas ──
//   if (dialog.choices) {
//     if (keys.up_pressed)   { dialog.selectedChoice = (dialog.selectedChoice - 1 + dialog.choices.length) % dialog.choices.length; keys.up_pressed = false; }
//     if (keys.down_pressed) { dialog.selectedChoice = (dialog.selectedChoice + 1) % dialog.choices.length; keys.down_pressed = false; }
//     if (keys.space_pressed || mouse.clicked) {
//       const chosen = dialog.choices[dialog.selectedChoice];
//       dialog.active = false; gameState = 'playing';
//       mouse.clicked = false; keys.space_pressed = false;
//       if (dialog.onChoice) dialog.onChoice(chosen.id);
//     }
//     return;
//   }
//   // ── Mode narratif : typewriter ──
//   dialog.tick++;
//   if (dialog.tick >= dialog.speed) {
//     dialog.tick = 0;
//     if (dialog.charIndex < dialog.lines[dialog.lineIndex].length) dialog.charIndex++;
//   }
//   if (keys.space_pressed || mouse.clicked) {
//     mouse.clicked = false; keys.space_pressed = false;
//     if (dialog.charIndex < dialog.lines[dialog.lineIndex].length) {
//       dialog.charIndex = dialog.lines[dialog.lineIndex].length;
//     } else if (dialog.lineIndex < dialog.lines.length - 1) {
//       dialog.lineIndex++; dialog.charIndex = 0;
//     } else {
//       dialog.active = false; gameState = 'playing';
//       if (dialog.onClose) dialog.onClose();
//     }
//   }
// }
// function drawDialog() {
//   if (!dialog.active) return;
//   const PORTRAIT_W = dialog.portraitFn ? 36 : 0;
//   const bx = 4, by = GH - 52, bw = GW - 8, bh = 48;
//   const textX = bx + PORTRAIT_W + 6, textW = bw - PORTRAIT_W - 14;
//   // Fond sombre
//   gctx.fillStyle = 'rgba(0,0,16,0.92)'; gctx.fillRect(bx, by, bw, bh);
//   // Bordure pixel art double
//   gctx.fillStyle = '#FCFCFC';
//   gctx.fillRect(bx,by,bw,1); gctx.fillRect(bx,by+bh-1,bw,1);
//   gctx.fillRect(bx,by,1,bh); gctx.fillRect(bx+bw-1,by,1,bh);
//   gctx.fillStyle = '#404060';
//   gctx.fillRect(bx+1,by+1,bw-2,1); gctx.fillRect(bx+1,by+bh-2,bw-2,1);
//   gctx.fillRect(bx+1,by+1,1,bh-2); gctx.fillRect(bx+bw-2,by+1,1,bh-2);
//   // Portrait (optionnel)
//   if (dialog.portraitFn) {
//     gctx.fillStyle = '#101028'; gctx.fillRect(bx+3, by+3, PORTRAIT_W-2, bh-6);
//     dialog.portraitFn(gctx, bx+3, by+3, PORTRAIT_W-2, bh-6);
//   }
//   // Speaker name en or
//   let textStartY = by + 11;
//   if (dialog.speaker) {
//     gctx.fillStyle = '#FFD700'; gctx.font = 'bold 6px monospace';
//     gctx.fillText(dialog.speaker + ':', textX, by + 9);
//     textStartY = by + 20;
//   }
//   // ── Mode choix ──
//   if (dialog.choices) {
//     gctx.fillStyle = '#FCFCFC'; gctx.font = 'bold 7px monospace';
//     gctx.fillText(dialog.lines[0].substring(0, Math.min(dialog.lines[0].length, Math.floor(textW/5))), textX, textStartY);
//     dialog.choices.forEach((c, i) => {
//       const optY = textStartY + 12 + i * 10;
//       gctx.fillStyle = i === dialog.selectedChoice ? '#FFD700' : '#AAAACC';
//       gctx.fillText((i === dialog.selectedChoice ? '▶ ' : '  ') + c.label, textX + 4, optY);
//     });
//     return;
//   }
//   // ── Mode narratif ──
//   gctx.fillStyle = '#FCFCFC'; gctx.font = 'bold 7px monospace';
//   const text = dialog.lines[dialog.lineIndex].substring(0, dialog.charIndex);
//   const charsPerLine = Math.max(20, Math.floor(textW / 5));
//   const words = text.split(' '); let line = '', ly = textStartY;
//   words.forEach(w => {
//     if ((line + w).length > charsPerLine) { gctx.fillText(line.trimEnd(), textX, ly); line = w + ' '; ly += 9; }
//     else line += w + ' ';
//   });
//   gctx.fillText(line.trimEnd(), textX, ly);
//   if (dialog.charIndex >= dialog.lines[dialog.lineIndex].length) {
//     if (Math.floor(Date.now()/400)%2) gctx.fillText('▼', bx+bw-10, by+bh-4);
//   }
// }
// USAGE NARRATIF : showDialog(["Tu as trouvé un coffre !", "Contenu : Épée +5"], () => player.addItem('sword'));
// USAGE SPEAKER  : showDialog(["Bienvenue aventurier !","Le donjon est au nord."], null, 'Villageois');
// USAGE PORTRAIT : showDialog(["Je suis le roi."], null, 'Roi Aldric', (ctx,x,y,w,h) => { /* pixel art portrait */ });
// USAGE CHOIX    : showChoiceDialog("Accepter la quête ?", [{label:'Oui',id:'yes'},{label:'Non',id:'no'}], id => { if(id==='yes') startQuest(); }, 'Guide');
// RAPPEL : drawDialog() EN DERNIER dans draw() ; if (gameState==='dialog') { updateDialog(); return; } dans update()

19. SOURIS + CLAVIER [tags: always] — OBLIGATOIRE pour TOUT jeu avec un menu, une sélection de personnage,
    des boutons d'action RPG, ou tout élément cliquable sur le canvas.
    La souris et le clavier doivent TOUJOURS coexister — l'un ne désactive pas l'autre.

// ── Suivi de la souris ──
let mouse = { x: 0, y: 0, clicked: false };
canvas.addEventListener('mousemove', e => {
  const r = canvas.getBoundingClientRect();
  // Convertir les coords écran → coords canvas (tient compte du scaling CSS)
  mouse.x = (e.clientX - r.left) * (canvas.width  / r.width);
  mouse.y = (e.clientY - r.top)  * (canvas.height / r.height);
});
canvas.addEventListener('click', e => {
  const r = canvas.getBoundingClientRect();
  mouse.x = (e.clientX - r.left) * (canvas.width  / r.width);
  mouse.y = (e.clientY - r.top)  * (canvas.height / r.height);
  mouse.clicked = true; // consommé une seule fois dans update()
});

// ── Registre de zones cliquables ──
// Déclarer les zones en début de frame (dans drawMenu / drawCombat / drawCharSelect…)
// puis tester dans update() ou handleClick().
const clickZones = []; // vider en début de chaque draw() de menu/combat : clickZones.length = 0;
function registerZone(x, y, w, h, id) {
  clickZones.push({ x, y, w, h, id });
}
function hitTest(mx, my) {
  for (const z of clickZones) {
    if (mx >= z.x && mx <= z.x + z.w && my >= z.y && my <= z.y + z.h) return z.id;
  }
  return null;
}

// ── Dessin d'un bouton cliquable (avec hover) ──
function drawButton(ctx, x, y, w, h, label, id) {
  const hovered = mouse.x >= x && mouse.x <= x+w && mouse.y >= y && mouse.y <= y+h;
  ctx.fillStyle = hovered ? '#ffffff' : 'rgba(255,255,255,0.15)';
  ctx.strokeStyle = hovered ? '#ffffff' : 'rgba(255,255,255,0.4)';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.roundRect(x, y, w, h, 6); ctx.fill(); ctx.stroke();
  ctx.fillStyle = hovered ? '#000' : '#fff';
  ctx.font = 'bold 16px Arial'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(label, x + w/2, y + h/2);
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  registerZone(x, y, w, h, id); // auto-enregistrement à chaque draw
  return hovered;
}
// ── Consommation du clic dans update() ──
// if (mouse.clicked) {
//   const hit = hitTest(mouse.x, mouse.y);
//   mouse.clicked = false; // consommer le clic
//   if (hit === 'btn_start')  startGame();
//   if (hit === 'btn_attack') doAttack();
//   if (hit === 'btn_flee')   doFlee();
//   if (hit === 'char_0')     selectChar(0);
//   if (hit === 'char_1')     selectChar(1);
// }
// ← Le clavier appelle les MÊMES fonctions (startGame, doAttack, doFlee, selectChar)
//   donc les deux inputs restent actifs en permanence.

// ── Exemple : écran de sélection de personnages ──
// function drawCharSelect() {
//   clickZones.length = 0; // reset zones
//   classes.forEach((cls, i) => {
//     const x = 80 + i * 180, y = canvas.height/2 - 80, w = 150, h = 200;
//     const hovered = mouse.x >= x && mouse.x <= x+w && mouse.y >= y && mouse.y <= y+h;
//     ctx.fillStyle = (selectedClass === i) ? '#FFD700' : (hovered ? '#aaa' : '#444');
//     ctx.fillRect(x, y, w, h);
//     // ... dessiner le personnage
//     registerZone(x, y, w, h, 'char_' + i);
//   });
//   drawButton(ctx, canvas.width/2 - 80, canvas.height - 100, 160, 44, 'Commencer', 'btn_start');
// }

// ── Exemple : boutons de combat RPG ──
// function drawCombatButtons() {
//   clickZones.length = 0;
//   drawButton(ctx,  60, canvas.height-80, 140, 44, '⚔ Attaquer',  'btn_attack');
//   drawButton(ctx, 220, canvas.height-80, 140, 44, '✨ Sort',      'btn_skill');
//   drawButton(ctx, 380, canvas.height-80, 140, 44, '🏃 Fuir',      'btn_flee');
//   drawButton(ctx, 540, canvas.height-80, 140, 44, '🧪 Objet',     'btn_item');
// }
// Clavier équivalent : touches 1/2/3/4 ou Z/X/C ou Entrée/Espace appellent doAttack/doSkill/doFlee/doItem()

23. FLOATING TEXT / DAMAGE NUMBERS [tags: always] — OBLIGATOIRE pour tout jeu avec combat ou collectibles.
    Les chiffres qui montent sont l'un des feedbacks les plus satisfaisants visuellement.

// ── Template exact — copie-colle et adapte les couleurs ──
const floatingTexts = [];
function spawnFloatingText(x, y, text, color = '#FCFCFC', size = 8) {
  floatingTexts.push({ x, y, text, color, size, vy: -28, life: 1.0 });
}
function updateFloatingTexts(dt) {
  for (let i = floatingTexts.length - 1; i >= 0; i--) {
    const f = floatingTexts[i];
    f.y  += f.vy * dt;
    f.vy *= 0.92; // ralentissement progressif
    f.life -= dt * 1.8;
    if (f.life <= 0) floatingTexts.splice(i, 1);
  }
}
function drawFloatingTexts(ctx) { // ctx = gctx en mode pixel art
  floatingTexts.forEach(f => {
    ctx.globalAlpha = Math.max(0, f.life);
    ctx.fillStyle = f.color;
    ctx.font = `bold ${f.size}px monospace`;
    ctx.textAlign = 'center';
    ctx.fillText(f.text, Math.floor(f.x), Math.floor(f.y));
  });
  ctx.globalAlpha = 1; ctx.textAlign = 'left';
}
// USAGE (dans les fonctions de combat ou de collecte) :
// spawnFloatingText(enemy.x + 8, enemy.y, `-${damage}`, '#F83800');  // dégâts rouges
// spawnFloatingText(hero.x + 8, hero.y, `+${xp} XP`, '#F8B800');     // XP dorés
// spawnFloatingText(hero.x + 8, hero.y, 'LEVEL UP!', '#A0F000', 10); // level up vert
// spawnFloatingText(coin.x, coin.y, `+${coin.value}`, '#FCFC00');     // pièces jaunes
// Appeler updateFloatingTexts(dt) dans update(), drawFloatingTexts(gctx) AVANT le HUD dans draw()

24. FADE TRANSITION [tags: always] — OBLIGATOIRE entre zones/salles et sur game over/victoire.
    Coût : 5 lignes de code. Impact visuel : immense. Ne jamais faire de coupure sèche.

// ── Fade in/out universel ──
let fade = { alpha: 0, dir: 0, speed: 1.5, onDone: null };
function fadeOut(speed = 1.5, onDone = null) { fade = { alpha: 0, dir: 1, speed, onDone }; }
function fadeIn(speed = 1.5)               { fade = { alpha: 1, dir: -1, speed, onDone: null }; }
function updateFade(dt) {
  if (fade.dir === 0) return;
  fade.alpha = Math.max(0, Math.min(1, fade.alpha + fade.dir * fade.speed * dt));
  if (fade.dir === 1 && fade.alpha >= 1) { fade.dir = 0; if (fade.onDone) fade.onDone(); }
  if (fade.dir === -1 && fade.alpha <= 0) { fade.dir = 0; }
}
function drawFade(ctx, W, H) { // ctx = le vrai ctx (pas gctx) pour couvrir tout l'écran
  if (fade.alpha <= 0) return;
  ctx.fillStyle = `rgba(0,0,0,${fade.alpha})`;
  ctx.fillRect(0, 0, W, H);
}
// USAGE :
// Changer de salle : fadeOut(2.0, () => { loadRoom(nextRoom); fadeIn(2.0); });
// Game over       : fadeOut(1.0, () => { gameState = 'gameover'; fadeIn(1.5); });
// Démarrer le jeu : fadeIn(1.5); // depuis le menu
// Dans update(dt) : updateFade(dt);
// Dans draw() EN TOUT DERNIER (après le HUD, sur le vrai ctx) : drawFade(ctx, canvas.width, canvas.height);

25. HUD PIXEL ART [tags: pixelart] — OBLIGATOIRE en mode pixel art. Remplace le texte brut par des icônes pixel.

// ── Cœurs (vie) style Zelda ──
// function drawHearts(ctx, hp, maxHp, x, y) {
//   const HEART_FULL  = [[0,1,1,0,0,1,1,0],[1,1,1,1,1,1,1,1],[1,1,1,1,1,1,1,1],
//                        [0,1,1,1,1,1,1,0],[0,0,1,1,1,1,0,0],[0,0,0,1,1,0,0,0],[0,0,0,0,0,0,0,0]];
//   const HEART_EMPTY = [[0,1,1,0,0,1,1,0],[1,0,0,1,1,0,0,1],[1,0,0,0,0,0,0,1],
//                        [0,1,0,0,0,0,1,0],[0,0,1,0,0,1,0,0],[0,0,0,1,1,0,0,0],[0,0,0,0,0,0,0,0]];
//   for (let i = 0; i < maxHp; i++) {
//     const sprite = i < hp ? HEART_FULL : HEART_EMPTY;
//     const col    = i < hp ? '#D82800'  : '#504040';
//     drawSprite(ctx, sprite, x + i * 10, y, [null, col]);
//   }
// }
// Usage : drawHearts(gctx, hero.hp, hero.maxHp, 2, 2);

// ── Barre XP/stamina ──
// function drawBar(ctx, x, y, w, h, value, max, colorFill, colorBg = '#200000') {
//   ctx.fillStyle = colorBg;   ctx.fillRect(x, y, w, h);
//   ctx.fillStyle = colorFill; ctx.fillRect(x, y, Math.floor(w * value / max), h);
//   ctx.fillStyle = '#FCFCFC'; ctx.fillRect(x, y, w, 1); // reflet haut
// }
// drawBar(gctx, 2, 12, 40, 4, hero.xp, hero.xpToNext, '#A0F000'); // XP vert
// drawBar(gctx, 2, 18, 40, 4, hero.mp, hero.maxMp,    '#3CBCFC'); // MP bleu

// ── Slots d'inventaire ──
// function drawInventory(ctx, items, x, y) {
//   items.slice(0, 6).forEach((item, i) => {
//     ctx.fillStyle = '#200830'; ctx.fillRect(x + i*14, y, 12, 12);
//     ctx.fillStyle = '#BCBCBC'; ctx.fillRect(x + i*14, y, 12, 1);
//     ctx.fillRect(x + i*14, y, 1, 12); // bord L
//     if (item) drawSprite(ctx, item.sprite, x + i*14 + 2, y + 2, item.palette);
//   });
// }

26. ENNEMIS — ÉTATS IA (patrol/chase/attack) [tags: combat, enemies] — OBLIGATOIRE pour tout jeu avec des ennemis.
    Des ennemis passifs = jeu ennuyeux. Chaque ennemi doit avoir un comportement.

// ── Structure universelle d'un ennemi avec IA ──
// function createEnemy(x, y, type) {
//   return { x, y, type,
//     state: 'patrol',        // 'patrol' | 'chase' | 'attack' | 'stunned'
//     patrolX: x, patrolDir: 1, patrolRange: 48,
//     hp: 3, maxHp: 3, attackCooldown: 0,
//     frameIndex: 0, frameTick: 0, facing: 'down',
//     alertRadius: 60,   // px — distance de détection du joueur
//     attackRadius: 14,  // px — distance d'attaque
//   };
// }
// function updateEnemy(e, hero, dt) {
//   const dx = hero.x - e.x, dy = hero.y - e.y;
//   const dist = Math.sqrt(dx*dx + dy*dy);
//   e.attackCooldown = Math.max(0, e.attackCooldown - dt);
//
//   switch (e.state) {
//     case 'patrol':
//       e.x += e.patrolDir * 30 * dt;
//       if (Math.abs(e.x - e.patrolX) > e.patrolRange) e.patrolDir *= -1;
//       e.facing = e.patrolDir > 0 ? 'right' : 'left';
//       if (dist < e.alertRadius) { e.state = 'chase'; sfx.play(440, 0.05, 'square'); }
//       break;
//     case 'chase':
//       const speed = 45;
//       e.x += (dx / dist) * speed * dt;
//       e.y += (dy / dist) * speed * dt;
//       e.facing = Math.abs(dx) > Math.abs(dy) ? (dx>0?'right':'left') : (dy>0?'down':'up');
//       if (dist < e.attackRadius && e.attackCooldown <= 0) { e.state = 'attack'; }
//       if (dist > e.alertRadius * 1.5) { e.state = 'patrol'; } // perd le joueur
//       break;
//     case 'attack':
//       if (e.attackCooldown <= 0) {
//         hero.hp -= 1; e.attackCooldown = 1.2;
//         spawnFloatingText(hero.x+8, hero.y, '-1', '#F83800');
//         triggerShake(4, 0.15);
//         sfx.play(120, 0.2, 'sawtooth');
//       }
//       e.state = 'chase';
//       break;
//     case 'stunned':
//       e.stunTimer -= dt;
//       if (e.stunTimer <= 0) e.state = 'chase';
//       break;
//   }
//   animateEntity(e, dt); // utilise le Pattern #20
// }
// TYPES D'ENNEMIS possibles (varier les comportements) :
// 'slime'  → patrolRange faible, alertRadius faible, hp=2
// 'guard'  → patrolRange élevé, suit une route fixe
// 'archer' → ne s'approche pas (maintient dist ~80px), tire des projectiles
// 'boss'   → plusieurs phases (hp>50% = normal, hp<50% = enragé avec speed×2)

27. SALLE DE BOSS [tags: boss, rpg, adventure] — OBLIGATOIRE pour tout jeu d'aventure/RPG avec une progression par zones.
    Le boss NE DOIT PAS apparaître au milieu du jeu. Il attend dans une salle dédiée,
    accessible seulement après avoir rempli une condition (clés, leviers, quête complète).

// ── Structure de la salle de boss ──
// Dans la tilemap, réserver une zone distincte en bas ou à droite de la map :
// const BOSS_ROOM = { x: MAP_W - 12, y: MAP_H - 12, w: 10, h: 10 }; // zone de tuiles
// Remplir cette zone avec des tuiles spéciales (TILE.DARK_STONE ou TILE.LAVA au sol)
// et entourer de murs (TILE.WALL) sauf l'entrée.

// ── Porte de boss — verrouillée jusqu'à condition ──
// const bossGate = { x: BOSS_ROOM.x * TILE_SIZE, y: (BOSS_ROOM.y + 5) * TILE_SIZE,
//                    w: TILE_SIZE * 2, h: TILE_SIZE * 2,
//                    open: false, requiredKeys: 3 }; // ou requiredLevers: true
// // Condition de déverrouillage :
// // if (!bossGate.open && leversActivated >= 3) {
// //   bossGate.open = true;
// //   spawnFloatingText(bossGate.x, bossGate.y - 20, '⚠ BOSS AWAKENED', '#D82800', 12);
// //   sfx.play(110, 0.5, 'sawtooth'); // son grave de menace
// //   fadeOut(0.8, () => { spawnBoss(); fadeIn(0.8); }); // transition dramatique
// // }
// // Dans drawMap() : si !bossGate.open → dessiner la porte fermée (couleur rouge foncé)
// //                  si bossGate.open → ne pas dessiner (passage libre)

// ── Spawn du boss dans sa salle ──
// let boss = null;
// function spawnBoss() {
//   boss = {
//     x: (BOSS_ROOM.x + 4) * TILE_SIZE,  // centre de la salle
//     y: (BOSS_ROOM.y + 4) * TILE_SIZE,
//     hp: 30, maxHp: 30, phase: 1,        // phase 1 = normal
//     attackCooldown: 0, moveTimer: 0,
//     size: TILE_SIZE * 2,                // boss 2× plus grand que les ennemis normaux
//     color: '#D82800',                   // couleur distinctive
//   };
//   gameState = 'boss_fight';             // état spécial pour la caméra et le HUD
// }

// ── IA du boss multi-phases ──
// function updateBoss(dt) {
//   if (!boss || boss.hp <= 0) return;
//   // Transition de phase selon HP
//   if (boss.hp <= boss.maxHp * 0.5 && boss.phase === 1) {
//     boss.phase = 2;
//     boss.color = '#F83800'; // plus rouge = plus dangereux
//     triggerShake(8, 0.4);
//     spawnFloatingText(boss.x, boss.y - 20, 'PHASE 2!', '#F8B800', 12);
//     sfx.play(80, 0.6, 'sawtooth');
//   }
//   if (boss.hp <= boss.maxHp * 0.25 && boss.phase === 2) {
//     boss.phase = 3;
//     boss.color = '#A800A8'; // violet = phase finale
//     sfx.play(55, 0.8, 'sawtooth');
//   }
//   // Comportements par phase :
//   boss.attackCooldown -= dt;
//   const dx = hero.x - boss.x, dy = hero.y - boss.y;
//   const dist = Math.sqrt(dx*dx + dy*dy);
//   // Phase 1 : charge lente vers le joueur
//   if (boss.phase === 1) {
//     boss.x += (dx/dist) * 40 * dt;
//     boss.y += (dy/dist) * 40 * dt;
//   }
//   // Phase 2 : plus rapide + tire des projectiles
//   else if (boss.phase === 2) {
//     boss.x += (dx/dist) * 70 * dt;
//     boss.y += (dy/dist) * 70 * dt;
//     if (boss.attackCooldown <= 0) {
//       spawnBossProjectile(boss.x, boss.y, dx/dist, dy/dist);
//       boss.attackCooldown = 1.2;
//     }
//   }
//   // Phase 3 : téléportation aléatoire + salve de projectiles
//   else if (boss.phase === 3) {
//     boss.moveTimer -= dt;
//     if (boss.moveTimer <= 0) {
//       boss.x = (BOSS_ROOM.x + 1 + Math.random() * 7) * TILE_SIZE;
//       boss.y = (BOSS_ROOM.y + 1 + Math.random() * 7) * TILE_SIZE;
//       boss.moveTimer = 0.8;
//       // Salve en étoile (8 directions)
//       for (let a = 0; a < 8; a++)
//         spawnBossProjectile(boss.x, boss.y, Math.cos(a*Math.PI/4), Math.sin(a*Math.PI/4));
//     }
//   }
//   // Dégât de contact
//   if (dist < boss.size/2 + 8) {
//     hero.hp -= 1; triggerShake(5, 0.2);
//     spawnFloatingText(hero.x, hero.y, '-1', '#D82800');
//   }
// }

// ── Victoire sur le boss ──
// function onBossDefeat() {
//   boss = null;
//   gameState = 'victory';               // écran de victoire spécial
//   spawnParticles(boss.x, boss.y, '#F8B800', 30); // explosion de particules
//   sfx.play(880, 0.5, 'sine');
//   showDialog(["BOSS VAINCU !", "Tu as sauvé le donjon.", "Fin du jeu — Félicitations !"],
//              () => { gameState = 'gameover'; }); // ou nextLevel
// }

// ── HUD de boss (barre de vie imposante) ──
// function drawBossHud() {
//   if (!boss || gameState !== 'boss_fight') return;
//   // Barre de vie boss en bas de l'écran (pixel art)
//   const bx = 10, by = GH - 12, bw = GW - 20, bh = 6;
//   gctx.fillStyle = '#400000'; gctx.fillRect(bx, by, bw, bh);
//   const ratio = Math.max(0, boss.hp / boss.maxHp);
//   const color = boss.phase === 3 ? '#A800A8' : boss.phase === 2 ? '#F83800' : '#D82800';
//   gctx.fillStyle = color; gctx.fillRect(bx, by, Math.floor(bw * ratio), bh);
//   gctx.fillStyle = '#FCFCFC'; gctx.font = 'bold 6px monospace';
//   gctx.fillText('BOSS', bx, by - 2);
// }
// Appeler drawBossHud() dans draw() EN DERNIER (sur gctx, avant drawFade)

28. KNOCKBACK ENNEMI OBLIGATOIRE [tags: combat] — tout ennemi touché par le joueur DOIT reculer.
    Sans knockback le combat est frustrant et illisible.

// ── Impulsion de recul avec arrêt aux murs ──
// function applyKnockback(entity, fromX, fromY, force = 120) {
//   const dx = entity.x - fromX, dy = entity.y - fromY;
//   const dist = Math.sqrt(dx*dx + dy*dy) || 1;
//   entity.knockbackVX = (dx / dist) * force;
//   entity.knockbackVY = (dy / dist) * force;
//   entity.knockbackTimer = 0.18; // durée en secondes
// }
// // Dans updateEnemy(e, dt) — AVANT le mouvement normal :
// if (e.knockbackTimer > 0) {
//   e.knockbackTimer -= dt;
//   const nx = e.x + e.knockbackVX * dt;
//   const ny = e.y + e.knockbackVY * dt;
//   // Vérifier collision mur avant application
//   const tileX = Math.floor(nx / TILE_SIZE);
//   const tileY = Math.floor(ny / TILE_SIZE);
//   if (!TILE_SOLID.has(map[tileY]?.[tileX])) e.x = nx;
//   if (!TILE_SOLID.has(map[Math.floor(e.y/TILE_SIZE)]?.[Math.floor(nx/TILE_SIZE)])) e.x = nx; else e.knockbackVX = 0;
//   if (!TILE_SOLID.has(map[Math.floor(ny/TILE_SIZE)]?.[Math.floor(e.x/TILE_SIZE)])) e.y = ny; else e.knockbackVY = 0;
//   e.knockbackVX *= 0.85; e.knockbackVY *= 0.85; // friction
//   return; // pas d'IA pendant le knockback
// }
// RÈGLE : le knockback s'arrête au mur — jamais un ennemi ne traverse un mur.
// Usage : applyKnockback(enemy, hero.x, hero.y, 120); // lors du coup du joueur

29. SCREEN SHAKE DOSÉ [tags: combat] — seulement sur les événements importants, pas sur chaque dégât reçu.
    Un screen shake permanent = inconfort visuel et perte de lisibilité.

// RÈGLES DE DOSAGE OBLIGATOIRES :
// - Mort du joueur         → triggerShake(6, 0.3)
// - Coup critique reçu     → triggerShake(4, 0.15)  ← max sur dégâts normaux
// - Boss transition phase  → triggerShake(8, 0.4)
// - Explosion / boss mort  → triggerShake(10, 0.5)
// - Coup normal reçu       → triggerShake(2, 0.08)  ← subtil, à peine perceptible
// INTERDIT : triggerShake(mag > 4, dur > 0.2) sur des dégâts normaux répétés
// INTERDIT : screen shake en boucle tant que le joueur est sur de la lave/spikes
//            → utiliser à la place un flash rouge sur le HUD (alpha 0→1→0 en 0.3s)
// Dans draw() : appliquer le shake UNIQUEMENT sur le gctx (canvas interne), PAS sur le ctx (canvas écran)
//   if (shakeTime > 0) { gctx.translate(Math.round((Math.random()-0.5)*shakeMag*2), Math.round((Math.random()-0.5)*shakeMag*2)); shakeTime -= dt; }

30. CONTRASTE VISUEL DUNGEON [tags: rpg, dungeon] — lisibilité obligatoire. Le joueur DOIT pouvoir distinguer
    instantanément sol, murs, ennemis et le héros.

// RÈGLES DE PALETTE DUNGEON (à respecter STRICTEMENT) :
// Sol standard    → couleur claire  (ex: #58A838 herbe, #BCBCBC pierre, #504030 bois)
// Mur/obstacle    → couleur SOMBRE  (ex: #282010 roc, #1A1A2E noir, #3A1A00 bois foncé)
//                   différence de luminosité ≥ 40% avec le sol — JAMAIS mur = sol + 10%
// Salle du boss   → sol spécial bien contrasté : TILE.LAVA (#D82800) ou TILE.DARK_STONE (#3A3A5A)
//                   BOSS_WALL = couleur différente du sol ('#4A2A1A' ou '#1A0A0A') — JAMAIS noir pur
// Ennemis normaux → couleur VIVE et DIFFÉRENTE du sol (rouge, orange, violet...)
//                   INTERDIT : ennemi couleur identique ou proche (< 40% de différence) du sol traversé
// Joueur/héros    → couleur la plus distinctive (blanc, cyan vif, doré) sur TOUS les fonds
// Couloirs        → même sol que les salles normales — JAMAIS laisser un couloir sans sol défini
//                   (= tuile WALL en couloir → couloir invisible → joueur bloqué)
// VÉRIFICATION OBLIGATOIRE :
//   Sur fond de sol GRASS (#58A838)   : ennemis en rouge/orange/blanc — JAMAIS en vert
//   Sur fond de sol STONE (#BCBCBC)   : ennemis en rouge/bleu foncé   — JAMAIS en gris
//   Sur fond de sol LAVA  (#D82800)   : ennemis en blanc/jaune/cyan   — JAMAIS en rouge/orange

31. COULOIRS PRATICABLES [tags: rpg, dungeon] — largeur minimale 3 tuiles. En dessous, le joueur se coince.

// RÈGLE GÉNÉRATION PROCÉDURALE DUNGEON :
// Couloir horizontal : MIN 3 tuiles de hauteur libre (la tuile centrale + 1 de chaque côté)
//   for (let y = midY - 1; y <= midY + 1; y++) map[y][x] = TILE.GRASS; // ← 3 tuiles, pas 1
// Couloir vertical   : MIN 3 tuiles de largeur libre
//   for (let x = midX - 1; x <= midX + 1; x++) map[y][x] = TILE.GRASS;
// Seuil de porte/entrée boss : MIN 3 tuiles de haut (midY-1, midY, midY+1)
// Connexion salle→couloir : dégager 3 tuiles au bord de la salle pour fluidifier l'entrée
// INTERDIT : couloir de 1 tuile (le joueur de 12px = TILE_SIZE * 0.75 ne peut pas passer si marge < 2px)
// PERFORMANCE : précalculer la tilemap ENTIÈRE dans generateDungeon() — ne JAMAIS modifier map[][] dans draw() ou update()

32. LOOT TABLE VARIÉE [tags: rpg, loot] — les coffres ne donnent JAMAIS deux fois la même chose.
    Un coffre prévisible = un coffre inutile.

// ── Système de loot avec poids ──
// const LOOT_TABLE = [
//   { type: 'gold',      weight: 40, value: ()=> 10 + Math.floor(Math.random()*20) },
//   { type: 'hp_potion', weight: 25, value: ()=> 30 },
//   { type: 'mp_potion', weight: 15, value: ()=> 20 },
//   { type: 'key',       weight: 12, value: ()=> 1 },
//   { type: 'sword_up',  weight: 5,  value: ()=> Math.floor(Math.random()*3)+1 },
//   { type: 'xp_gem',   weight: 3,  value: ()=> 50 + Math.floor(Math.random()*50) },
// ];
// function rollLoot() {
//   const total = LOOT_TABLE.reduce((s,e) => s + e.weight, 0);
//   let r = Math.random() * total;
//   for (const entry of LOOT_TABLE) {
//     r -= entry.weight;
//     if (r <= 0) return { type: entry.type, value: entry.value() };
//   }
//   return LOOT_TABLE[0]; // fallback
// }
// Usage dans openChest(chest) : const loot = rollLoot(); applyLoot(loot);
// applyLoot({ type, value }) { switch(type) { case 'hp_potion': hero.hp = Math.min(hero.maxHp, hero.hp + value); ... } }

33. ANIMATIONS D'ATTAQUE + COOLDOWN VISUEL [tags: combat] — OBLIGATOIRE pour tout jeu avec du combat.
    Sans animation, le joueur ne sait pas si son attaque a porté.

// ── Flash d'attaque au corps à corps ──
// Lors de l'attaque du joueur :
//   hero.attackFlash = 0.12; // timer en secondes
//   hero.attackDir = { x: dx/dist, y: dy/dist }; // direction vers la cible
// Dans drawHero() :
//   if (hero.attackFlash > 0) {
//     // Ligne/arc de balayage dans la direction d'attaque
//     gctx.strokeStyle = '#FCFCFC'; gctx.lineWidth = 2;
//     gctx.beginPath();
//     gctx.arc(hero.x, hero.y, 14, attackAngle - 0.6, attackAngle + 0.6);
//     gctx.stroke();
//     hero.attackFlash -= dt;
//   }
//
// ── Barre de cooldown compétence ──
// Sous le bouton de compétence ou sous la barre MP, afficher la progression du cooldown :
// function drawSkillCooldown(ctx, x, y, w, h, cooldown, maxCooldown) {
//   if (cooldown <= 0) return; // pas besoin si disponible
//   ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(x, y, w, h);
//   const ratio = cooldown / maxCooldown;
//   ctx.fillStyle = '#3CBCFC'; ctx.fillRect(x, y, Math.floor(w * (1 - ratio)), h);
//   ctx.fillStyle = '#FCFCFC'; ctx.font = 'bold 6px monospace'; ctx.textAlign = 'center';
//   ctx.fillText(`${Math.ceil(cooldown)}s`, x + w/2, y + h - 1);
// }
// RÈGLE : tout état 'PRÊT' / 'EN RECHARGE' doit être visible en permanence dans le HUD.

34. LEVEL UP IMPACTANT [tags: rpg, progression] — chaque niveau doit apporter un bonus PERCEPTIBLE immédiatement.
    Un level up sans effet visible = progression invisible = jeu sans récompense.

// RÈGLES OBLIGATOIRES pour checkLevelUp(hero) :
// - HP max augmente de ≥ 15% à chaque niveau (ex: +15 HP → +20 HP → +25 HP)
// - ATK augmente d'au moins 3-5 points (impact visible sur les dégâts)
// - Soin complet au level up (hero.hp = hero.maxHp) — récompense immédiate
// - XP requis pour le prochain niveau = Math.floor(xpToNext * 1.5) — courbe exponentielle
// - Affichage obligatoire : spawnFloatingText + showDialog avec les gains exacts :
//   showDialog([`NIVEAU ${hero.level} !`, `+15 HP max, +4 ATK, +2 DEF`, 'Soins complets !'], ()=>{});
// - Si classe spéciale : débloquer une nouvelle compétence tous les 3 niveaux
//   if (hero.level % 3 === 0) unlockSkill(hero);
// FORMULE RECOMMANDÉE (inspirée de Final Fantasy) :
//   hp_gain  = 10 + hero.level * 5;
//   atk_gain = 2  + Math.floor(hero.level / 3);
//   def_gain = 1  + Math.floor(hero.level / 5);

35. BALANCE VITESSES [tags: always] — le joueur doit toujours se sentir en contrôle.
    Des ennemis plus rapides que le joueur = frustration garantie.

// RÈGLES DE VITESSE OBLIGATOIRES (en px/s sur la résolution interne) :
// Joueur de base       : 70–90 px/s (ajuster selon TILE_SIZE et SCALE)
// Ennemi normal        : 50–70 px/s (max 80% de la vitesse joueur)
// Ennemi élite/rapide  : 65–80 px/s (max 100% de la vitesse joueur — JAMAIS plus)
// Boss phase 1         : 40–55 px/s (lent et menaçant)
// Boss phase 2         : 60–75 px/s (accélère, mais reste ≤ joueur)
// Boss phase 3         : 80–90 px/s (égale le joueur — tension maximale)
// RÈGLE ABSOLUE : speed ennemi normal JAMAIS > playerSpeed * 0.9
//                 speed boss phase finale JAMAIS > playerSpeed * 1.05
// EXCEPTION permise : ennemi kamikaze (HP=1) peut aller à 110% joueur, mais meurt au contact

36. TEXTES LISIBLES [tags: always] — tailles minimales obligatoires. Un texte illisible = information perdue.

// TAILLES MINIMALES OBLIGATOIRES (en px sur la résolution interne du jeu) :
// HUD permanent (HP, score, niveau)  : font ≥ 8px  en mode pixel art (GW=256), ≥ 14px sinon
// Floating text / dégâts             : font ≥ 7px  pixel art, ≥ 12px sinon
// Dialogue / descriptifs             : font ≥ 7px  pixel art, ≥ 13px sinon
// Nom du boss (barre de vie)         : font ≥ 6px  pixel art, ≥ 11px sinon
// Instructions / tutoriel            : font ≥ 8px  pixel art, ≥ 14px sinon
// RÈGLE : en mode pixel art (canvas interne), 7px monospace = taille minimale absolue
//         en mode canvas plein écran, 13px Arial = taille minimale absolue
// Couleur recommandée pour lisibilité : texte blanc '#FCFCFC' + ombre noire '#000000' 1px offset
// Ombre : gctx.fillStyle='#000'; gctx.fillText(txt, x+1, y+1); gctx.fillStyle='#FFF'; gctx.fillText(txt, x, y);

37. SPAWN BOSS GARANTI [tags: boss] — le boss DOIT toujours apparaître dans sa salle.

// RÈGLES ANTI-BUG SPAWN BOSS :
// 1. Créer le boss dans generateDungeon() (pas dans une fonction lazy appelée plus tard)
//    boss = createBoss(bossRoom.x + bossRoom.w/2, bossRoom.y + bossRoom.h/2, bossType);
// 2. Exposer bossRoom en variable globale AVANT d'appeler generateDungeon()
//    let bossRoomRef = null; // déclaré en haut du script
//    // Dans generateDungeon() : bossRoomRef = rooms[bossRoomIdx]; boss = createBoss(...);
// 3. Spawn en pixels = coordonnée tuile × TILE_SIZE (ex: bossRoom.x * TILE_SIZE + bossRoom.w * TILE_SIZE / 2)
// 4. Ne JAMAIS vérifier 'if (hero est dans la salle boss)' pour spawner le boss — spawner à l'init
// 5. bossGate bloque l'entrée → le joueur ne voit le boss que quand il y entre
// 6. Si onBossDefeat() doit placer un escalier : map[stairTY][stairTX] = TILE.STAIR;
//    Le joueur marche dessus → fadeOut → generateDungeon(currentFloor + 1) → fadeIn

38. PERFORMANCE DUNGEON [tags: rpg, dungeon] — pas de calcul lourd dans la game loop.
    Un seul calcul coûteux par frame = 60 calculs/s = lag garanti.

// RÈGLES ANTI-LAG OBLIGATOIRES :
// - generateDungeon() : tout précalcul ICI (position ennemis, chemins, distances)
//   JAMAIS de génération de structure de données lourde dans update() ou draw()
// - drawMap() : N'itérer QUE sur les tuiles visibles (frustum culling)
//   startX = Math.floor(cam.x / TILE_SIZE); endX = startX + Math.ceil(GW / TILE_SIZE) + 2;
//   (pareil pour Y) → NE PAS itérer sur toutes les MAP_W×MAP_H tuiles à chaque frame
// - Salle du boss : NE PAS recalculer les coordonnées du boss room à chaque frame
//   Stocker bossRoomRef.x / bossRoomRef.y une fois dans generateDungeon()
// - Ennemis : limiter le nombre simultané (max 20 en vue) — éviter spawns en masse
// - Collision : tester AABB seulement si les entités sont à < 200px — pas de nested loop globale
// - INTERDIT : Array.find() / Array.filter() sur des tableaux de > 50 éléments dans draw()

39. DESCRIPTIONS CLASSES JOUABLES [tags: rpg] — chaque classe doit être clairement différenciée.
    Un écran de sélection vague = joueur qui choisit au hasard.

// RÈGLES POUR L'ÉCRAN DE SÉLECTION DE CLASSE :
// - Nom de la classe + icône visuelle distinctive (forme géométrique ou sprite unique)
// - 2 lignes de description : style de jeu + compétence signature
//   ex: "GUERRIER — Résistant et puissant. Frappe qui renvoie les projectiles (Bouclier)."
//       "MAGE — Fragile mais dévastateur. Sort de foudre à zone (AoE)."
//       "VOLEUR — Rapide et furtif. Coup de dos × 2 en sortie d'invisibilité (Backstab)."
// - Barres de stats visuelles (HP, ATK, DEF, SPD) — pas juste des chiffres
//   function drawStatBar(ctx, x, y, value, max, color, label) {
//     ctx.fillStyle = '#333'; ctx.fillRect(x, y, 80, 5);
//     ctx.fillStyle = color; ctx.fillRect(x, y, Math.floor(80 * value / max), 5);
//     ctx.fillStyle = '#FFF'; ctx.font = '7px monospace';
//     ctx.fillText(label, x - 30, y + 5);
//   }
// - Compétences : nom + cooldown + coût MP + description courte (1 ligne)
// - Curseur clavier (gauche/droite) ET clic souris — les deux toujours actifs

40. CALLBACKS ET TIMERS [tags: always] — TROIS RÈGLES ANTI-CRASH ABSOLUES.

// ── Règle 1 : Optional chaining sur TOUS les callbacks de types ──
// Si tu définis un registre d'objets (ENEMY_TYPES, INTERACTABLE_TYPES, etc.) et que tu appelles
// des méthodes dessus dans la game loop, TOUJOURS utiliser l'optional chaining :
// CORRECT  : ENEMY_TYPES[e.type].onAttack?.(e, target);   // ne crashe pas si absent
// INTERDIT : ENEMY_TYPES[e.type].onAttack(e, target);     // TypeError si absent → écran noir
// RÈGLE : tout callback (onAttack, onDeath, onHit, onSummon, onClone, onActivate...) appelé
//         dans update() ou la game loop DOIT utiliser ?.() même si tu es "sûr" qu'il existe.

// ── Règle 2 : Tout timer utilisé doit être initialisé à la création ──
// Si updateBoss() ou updateEnemy() fait : entity.xyzTimer -= dt  ou  entity.xyzTimer <= 0
// alors entity.xyzTimer DOIT être initialisé dans createEnemy() ou spawnBoss() :
// CORRECT : boss.cloneTimer = bossInfo.cloneCooldown || 0;   // dans spawnBoss()
// INTERDIT : utiliser boss.cloneTimer sans l'avoir initialisé → undefined - dt = NaN → bug silencieux
// RÈGLE : lister TOUS les timers utilisés dans updateBoss/updateEnemy et vérifier qu'ils ont
//         une valeur initiale dans la fonction de création correspondante.

// ── Règle 3 : Jamais deux const/let avec le même nom dans la même fonction ──
// CORRECT : deux const normalRooms dans deux fonctions DIFFÉRENTES → ok
// INTERDIT : deux const normalRooms dans la MÊME fonction generateDungeon → SyntaxError → écran noir
// RÈGLE : si tu as besoin d'un tableau filtré à deux endroits dans la même fonction,
//         utilise des noms différents : startRooms, populationRooms, chestRooms, leverRooms...

41. BOSS — SOURCE DE DÉGÂTS UNIQUE [tags: boss, combat] (anti double-dégât).

// Un boss NE DOIT PAS infliger des dégâts via DEUX mécanismes simultanés.
// PATTERN CORRECT : dégâts uniquement via le check de collision dans checkCollisions() :
//   if (boss && isColliding(hero, boss) && hero.invincibilityTimer <= 0) {
//     playerTakeDamage(boss.attack);
//   }
// Dans ce cas, onAttack ne fait QUE des effets visuels/sonores, PAS de playerTakeDamage :
//   onAttack: (enemy, target) => {
//     sfx.play(...); spawnParticles(...); // PAS de playerTakeDamage ici
//   }
// PATTERN ALTERNATIF : dégâts uniquement via onAttack avec cooldown explicite.
//   Dans ce cas, NE PAS appeler playerTakeDamage dans le check de collision.
// INTERDIT : appeler playerTakeDamage dans LES DEUX — le joueur mourrait en quelques secondes.

42. BOSS — STATS ÉQUILIBRÉES ET VISUEL DISTINCTIF [tags: boss, combat].

// STATS BOSS (valeurs de référence pour un joueur à 100 HP) :
// boss.attack    : 8–15 HP par hit (jamais > 15% du maxHP joueur en phase 1)
// boss.speed     : 25–35 px/s en phase 1 (inférieur au joueur), 40–55 en phase finale
// boss.attackRadius : TILE_SIZE * 0.8 max (≈ contact physique uniquement)
//                    JAMAIS > 1.5 × ENEMY_SIZE — sinon frappe à travers les murs
// boss.cooldown  : ≥ 2.0s (laisser le temps au joueur de réagir)
// Recul post-attaque : après chaque hit, le boss s'éloigne 0.6–1.0s → fenêtre d'évasion
//   if (boss._recoilTimer > 0) { boss._recoilTimer -= dt; /* reculer */ }
//   else { /* avancer vers le joueur */ }
//   if (dist < boss.attackRadius && boss.attackTimer <= 0) {
//     /* attaque */ boss._recoilTimer = 0.8;
//   }
//
// VISUEL BOSS OBLIGATOIRE — le boss doit être immédiatement reconnaissable :
// 1. Aura pulsante : cercle semi-transparent autour du boss, animé avec Math.sin(Date.now())
//    gctx.globalAlpha = 0.25 + pulse * 0.2; gctx.arc(sx, sy, b.size * 0.9 + pulse * 5, ...);
// 2. Indicateur ★ BOSS ★ ou couronne flottant AU-DESSUS du sprite (jamais en-dessous)
//    gctx.fillStyle = `rgba(255,215,0,${0.7 + pulse * 0.3})`; gctx.fillText('★ BOSS ★', sx, sy - b.size/2 - 8);
// 3. Mini barre de vie directement au-dessus du sprite (EN PLUS du HUD) :
//    gctx.fillStyle = hp>50%?'#44cc44':hp>25%?'#ccaa22':'#cc2222'; gctx.fillRect(barX, barY, barW*(hp/maxHp), 4);
// 4. sizeFactor ≥ 2.0 — le boss doit être 2× plus grand que les ennemis normaux

43. API DEV CONSOLE STANDARD [tags: rpg, combat] — OBLIGATOIRE pour tout jeu avec héros, ennemis et combat.
    La dev console injectée automatiquement utilise CES NOMS EXACTS pour ses recettes admin.
    Si tu utilises d'autres noms, les commandes admin ne fonctionneront pas.

// ── VARIABLES obligatoires (noms EXACTS) ──
// let hero = { x, y, hp, maxHp, mp, maxMp, speed, attack, defense, level, xp, xpToNext,
//              classId, invincibilityTimer, facing, state };
// let enemies = [];           // ennemis actifs sur le terrain
// let boss = null;            // boss actuel ou null
// let loot = [];              // objets au sol [{x, y, type, collected, size}]
// let interactables = [];     // leviers/coffres/portes/PNJ [{x, y, type, used, open, nearPlayer}]
// let minions = [];           // alliés invoqués (si applicable)
// let playerStats = { maxHp, hp, maxMp, mp, attack, defense, speed,
//                     atkCooldown, skillCooldown, skillTimer };
// let playerInventory = { keys: 0, potions: 0 };
// let activeBuffs = [];       // [{type:'speed_boost'|'defense_boost', value:N, duration:N}]
// let bossGate = null;        // porte du boss {x, y, w, h, open: false}
// let currentDungeonFloor = 1; // progression — ou currentFloor / floor

// ── POUR LES JEUX AVEC SÉLECTION DE CLASSE ──
// const HERO_CLASSES = [...];  // [{id, name, description, color, baseHp, baseMp, ...}]
// const CUSTOM_SKILLS  = {};   // {classId: function() { /* mécanique compétence */ }}
// const CUSTOM_ATTACKS = {};   // {classId: function(baseDmg, atkRange) { /* attaque */ }}

// ── FONCTIONS obligatoires (noms EXACTS) ──
// function createEnemy(x, y, type) { ... }              // retourne l'objet ennemi
// function handleEnemyDefeat(enemy, idx) { ... }        // mort ennemi : loot, XP, effets
// function spawnBoss(floor) { ... }                     // invoque le boss de l'étage N
// function generateDungeon(floor) { ... }               // régénère tout le donjon à l'étage N
// function checkLevelUp(hero) { ... }                   // applique level-up si xp >= xpToNext
// function applyKnockback(entity, fromX, fromY, force) { ... }
// function spawnParticles(x, y, color, count) { ... }
// function spawnFloatingText(x, y, text, color, size) { ... }
// function triggerShake(magnitude, duration) { ... }
// function createProjectile(x, y, vx, vy, damage, type, owner) { ... }

// ✅ CORRECT : let hero = {...}; enemies.push(createEnemy(x, y, 'goblin'));
// ❌ INTERDIT : let player = {...}; monsters.push(spawnMonster(x, y));
//   → les commandes admin (tuer ennemis, TP, créer classe, freeze...) ne fonctionneraient pas.

44. BOUTIQUE / SHOP SYSTEM [tags: shop] — OBLIGATOIRE si le jeu a un marchand, une boutique ou des achats.
    Noms standardisés pour que la dev console puisse accéder à la boutique.

// let shopOpen = false;
// let shopSelectedItem = 0;
// const SHOP_ITEMS = [
//   { id:'potion',  name:'Potion HP',    icon:'❤',  desc:'Soigne 40 HP',     cost:30,  effect: () => { hero.hp = Math.min(hero.maxHp, hero.hp+40); } },
//   { id:'mana',    name:'Potion MP',    icon:'🔷', desc:'Restaure 30 MP',   cost:25,  effect: () => { hero.mp = Math.min(hero.maxMp, hero.mp+30); } },
//   { id:'atk_up',  name:'Amulette ATK',icon:'⚔',  desc:'+5 ATK permanent', cost:80,  effect: () => { hero.attack += 5; }, oneShot: true },
//   { id:'def_up',  name:'Bouclier',    icon:'🛡',  desc:'+3 DEF permanent', cost:60,  effect: () => { hero.defense += 3; }, oneShot: true },
//   { id:'speed',   name:'Élixir SPD',  icon:'💨',  desc:'+20 SPD / 60s',    cost:40,  effect: () => { activeBuffs.push({type:'speed',value:20,duration:60}); } },
// ];
// const _shopBought = new Set(); // track des achats one-shot
// function openShop()  { shopOpen = true; shopSelectedItem = 0; gameState = 'shop'; }
// function closeShop() { shopOpen = false; gameState = 'playing'; }
// function buyItem(idx) {
//   const item = SHOP_ITEMS[idx];
//   if (!item || (item.oneShot && _shopBought.has(item.id))) return;
//   if (playerInventory.gold < item.cost) {
//     spawnFloatingText(hero.x, hero.y - 20, 'Or insuffisant !', '#FF4444', 10);
//     return;
//   }
//   playerInventory.gold -= item.cost;
//   item.effect();
//   if (item.oneShot) _shopBought.add(item.id);
//   spawnFloatingText(hero.x, hero.y - 20, 'Acheté !', '#FFD700', 10);
//   spawnParticles(hero.x, hero.y, '#FFD700', 12);
// }
// function updateShop() {
//   if (keys.up_pressed)    { shopSelectedItem = (shopSelectedItem - 1 + SHOP_ITEMS.length) % SHOP_ITEMS.length; keys.up_pressed = false; }
//   if (keys.down_pressed)  { shopSelectedItem = (shopSelectedItem + 1) % SHOP_ITEMS.length; keys.down_pressed = false; }
//   if (keys.space_pressed) { buyItem(shopSelectedItem); keys.space_pressed = false; }
//   if (keys.escape)        { closeShop(); }
// }
// function drawShop() {
//   if (!shopOpen) return;
//   // Fond semi-transparent
//   gctx.fillStyle = 'rgba(0,0,0,0.88)'; gctx.fillRect(0, 0, GW, GH);
//   // Cadre boutique
//   const bx=10, by=8, bw=GW-20, bh=GH-16;
//   gctx.fillStyle='#1a1a2e'; gctx.fillRect(bx,by,bw,bh);
//   gctx.strokeStyle='#FFD700'; gctx.lineWidth=1; gctx.strokeRect(bx,by,bw,bh);
//   // Titre
//   gctx.fillStyle='#FFD700'; gctx.font='bold 9px monospace'; gctx.textAlign='center';
//   gctx.fillText('⚒ BOUTIQUE', GW/2, by+14);
//   gctx.fillStyle='#aaa'; gctx.font='6px monospace';
//   gctx.fillText(`Or disponible : ${playerInventory.gold}`, GW/2, by+24);
//   gctx.textAlign='left';
//   // Liste articles
//   SHOP_ITEMS.forEach((item, i) => {
//     const iy = by+36 + i*20;
//     const isBought = item.oneShot && _shopBought.has(item.id);
//     const canBuy = !isBought && playerInventory.gold >= item.cost;
//     const selected = i === shopSelectedItem;
//     if (selected) { gctx.fillStyle='rgba(255,215,0,0.15)'; gctx.fillRect(bx+4,iy-8,bw-8,18); }
//     gctx.fillStyle = isBought ? '#555' : canBuy ? '#fff' : '#f88';
//     gctx.font = selected ? 'bold 7px monospace' : '7px monospace';
//     gctx.fillText(`${item.icon} ${item.name}`, bx+10, iy);
//     gctx.fillStyle='#888'; gctx.font='6px monospace';
//     gctx.fillText(item.desc, bx+10, iy+8);
//     gctx.fillStyle= canBuy?'#FFD700':'#666';
//     gctx.font='bold 7px monospace'; gctx.textAlign='right';
//     gctx.fillText(isBought ? 'ACHETÉ':''+item.cost+' or', bx+bw-6, iy);
//     gctx.textAlign='left';
//   });
//   // Instructions
//   gctx.fillStyle='#555'; gctx.font='5px monospace'; gctx.textAlign='center';
//   gctx.fillText('[↑↓] Naviguer  [ESPACE] Acheter  [ÉCHAP] Quitter', GW/2, by+bh-4);
//   gctx.textAlign='left';
// }
// Dans draw() : drawShop() APRÈS drawHud() et AVANT drawDialog()
// Dans update() : if (gameState === 'shop') { updateShop(); return; }
// Ouvrir : PNJ interactable type 'merchant' → onInteract: () => openShop()

45. SAVE SYSTEM [tags: save, rpg, progression] — localStorage structuré pour tout jeu avec progression persistante.

// const SAVE_KEY = 'arcade_save_v1'; // clé unique par jeu
// function saveGame() {
//   const data = {
//     score: score || 0,
//     level: currentDungeonFloor || 1,
//     heroHp: hero?.hp || 100,
//     heroClass: hero?.classId || 0,
//     gold: playerInventory?.gold || 0,
//     keys: playerInventory?.keys || 0,
//     timestamp: Date.now(),
//   };
//   try { localStorage.setItem(SAVE_KEY, JSON.stringify(data)); } catch(e) {}
// }
// function loadGame() {
//   try {
//     const raw = localStorage.getItem(SAVE_KEY);
//     if (!raw) return null;
//     return JSON.parse(raw);
//   } catch(e) { return null; }
// }
// function deleteSave() { try { localStorage.removeItem(SAVE_KEY); } catch(e) {} }
// // Appeler saveGame() : à chaque descente d'étage, après un achat important, sur game over (partial)
// // Appeler loadGame() : dans DOMContentLoaded, SI un save existe → proposer "Continuer ?"
// // Indicateur sauvegarde : pastille verte ✓ SAVE en haut à droite, visible 2s puis disparaît
// let _saveIndicatorTimer = 0;
// // Dans draw() : if(_saveIndicatorTimer>0){_saveIndicatorTimer-=dt; gctx.fillStyle='#0f0';gctx.font='6px monospace';gctx.fillText('✓ SAVE',GW-36,10);}

46. MENU PAUSE [tags: always] — OBLIGATOIRE pour tout jeu avec une durée > 2 minutes.
    Touche P ou ÉCHAP pour ouvrir/fermer la pause. Évite les frustrations du joueur.

// function togglePause() {
//   if (gameState === 'playing') { gameState = 'paused'; }
//   else if (gameState === 'paused') { gameState = 'playing'; }
// }
// keys.p_pressed = false; // déclarer dans le handler keydown
// // Dans update() en début : if (keys.p_pressed) { togglePause(); keys.p_pressed = false; }
// //                           if (gameState === 'paused') return; // tout s'arrête
// function drawPause() {
//   if (gameState !== 'paused') return;
//   gctx.fillStyle = 'rgba(0,0,0,0.6)'; gctx.fillRect(0,0,GW,GH);
//   gctx.fillStyle = '#fff'; gctx.font = 'bold 12px monospace'; gctx.textAlign='center';
//   gctx.fillText('PAUSE', GW/2, GH/2 - 10);
//   gctx.font = '7px monospace'; gctx.fillStyle = '#aaa';
//   gctx.fillText('[P] ou [ÉCHAP] pour reprendre', GW/2, GH/2 + 8);
//   gctx.textAlign='left';
// }
// Dans draw() : drawPause() EN DERNIER (au-dessus de tout)
// Dans keydown : if(e.key==='p'||e.key==='P'||e.key==='Escape') keys.p_pressed=true;
// RÈGLE : en mode 'paused', NE PAS mettre à jour physics/enemies/timers — tout s'arrête net.

47. GAME FEEL & JUICE [tags: always, action, combat, shooter, platformer, rpg, survival] — OBLIGATOIRE.
    C'est la différence entre un jeu terne et un jeu vivant. CHAQUE hit doit faire ressentir quelque chose.

// ── Screen Shake ──
// let shakeX = 0, shakeY = 0, shakeDur = 0, shakeMag = 0;
// function triggerShake(mag, dur) { if (mag > shakeMag) { shakeMag = mag; shakeDur = dur; } }
// Dans update(dt) :
//   if (shakeDur > 0) { shakeDur -= dt; shakeX = (Math.random()-0.5)*shakeMag*2; shakeY = (Math.random()-0.5)*shakeMag*2; }
//   else { shakeX = 0; shakeY = 0; }
// Dans draw() AVANT tout dessin : ctx.save(); ctx.translate(shakeX, shakeY);
// En fin de draw() : ctx.restore();
// Intensités : triggerShake(3, 0.10) hit léger; triggerShake(6, 0.18) impact fort; triggerShake(12, 0.40) boss mort

// ── Flash rouge joueur touché ──
// let playerFlash = 0; // dans vars globales
// Dans update(dt) : if (playerFlash > 0) playerFlash -= dt;
// Dans draw() APRÈS le fond, AVANT le HUD :
//   if (playerFlash > 0) { ctx.fillStyle = 'rgba(220,0,0,0.28)'; ctx.fillRect(0,0,canvas.width,canvas.height); }
// Appel : playerFlash = 0.20; // quand joueur touché

// ── Flash blanc ennemi touché ──
// Ajouter à chaque ennemi : flashTimer: 0
// Dans update(dt) : if (e.flashTimer > 0) e.flashTimer -= dt;
// Dans draw() : ctx.fillStyle = e.flashTimer > 0 ? '#FFFFFF' : e.color;
// Appel : e.flashTimer = 0.08; triggerShake(3, 0.10); // quand ennemi touché

// ── Hitstop / Freeze frames ──
// let hitstopTimer = 0;
// function triggerHitstop(dur) { hitstopTimer = Math.max(hitstopTimer, dur); }
// Dans gameLoop : if (hitstopTimer > 0) { hitstopTimer -= realDt; draw(); return; } // skip update
// Appels : triggerHitstop(0.05) coup normal; triggerHitstop(0.12) coup critique

// ── Coyote Time + Jump Buffer (platformer) ──
// let coyoteTime = 0, jumpBuffer = 0;
// const COYOTE_LIMIT = 0.10, JUMP_BUFFER_LIMIT = 0.12;
// Dans update(dt) :
//   coyoteTime += dt; jumpBuffer = Math.max(0, jumpBuffer - dt);
//   if (player.onGround) coyoteTime = 0;
//   if (keys.jump_pressed) { jumpBuffer = JUMP_BUFFER_LIMIT; keys.jump_pressed = false; }
//   if (jumpBuffer > 0 && coyoteTime < COYOTE_LIMIT) {
//     player.vy = -JUMP_FORCE; coyoteTime = 99; jumpBuffer = 0; // sauter + invalider coyote
//   }
// RÈGLE : ne PAS utiliser keys.up ou keys.space directement pour sauter — toujours passer par jumpBuffer.

// RÈGLES DE CALIBRATION — éviter la nausée et le strobe (OBLIGATOIRE) :
// ✅ flash blanc ennemi : flashTimer = 0.07 max — JAMAIS plus (sinon strobe)
// ✅ flash rouge joueur : opacity 0.25 max, durée 0.18s — jamais opaque
// ✅ shake ennemi ordinaire tué : triggerShake(2, 0.08) — subtil, peine perceptible
// ✅ shake joueur touché : triggerShake(4, 0.12) — ressenti mais pas nauséeux
// ✅ shake boss mort : triggerShake(10, 0.35) — spectaculaire mais rare
// ❌ INTERDIT : triggerShake() sur chaque tir de projectile → trop fréquent, nausée
// ❌ INTERDIT : triggerShake() dans une boucle for sur enemies → cumul violent
// ❌ INTERDIT : shakeMag > 6 sur un événement récurrent (utiliser > 8 uniquement pour les boss)
// ❌ INTERDIT : flashTimer > 0.08 sur les ennemis ordinaires
// RÈGLE : triggerShake() doit utiliser Math.max pour ne jamais cumuler plusieurs shakes simultanés
// RÈGLE JUICE : mort ennemi ordinaire → spawnParticles(e.x, e.y, e.color, 8) + triggerShake(2, 0.08)
// RÈGLE JUICE : dégât joueur → playerFlash = 0.18 + triggerShake(4, 0.12)
// RÈGLE JUICE : mort boss → triggerShake(10, 0.35) + spawnParticles(boss.x, boss.y, '#FFD700', 30)

48. VARIÉTÉ ENNEMIS — 3 TYPES MINIMUM [tags: action, combat, shooter, platformer, survival, rpg] — CRITIQUE pour l'engagement.
    Des ennemis identiques tuent le fun en 30 secondes. Chaque type = couleur + taille + comportement distincts.

// ── Types d'ennemis (modèle adaptable à tout genre) ──
// const ENEMY_DEFS = {
//   grunt:   { hp:20, speed:70, size:13, color:'#E74C3C', scoreValue:10, xpValue:5,
//              behavior:'chase', alertRadius:220, attackRadius:18, damage:10 },
//   tank:    { hp:90, speed:28, size:22, color:'#8E44AD', scoreValue:35, xpValue:15,
//              behavior:'chase', alertRadius:160, attackRadius:26, damage:20, knockbackRes:0.5 },
//   shooter: { hp:14, speed:38, size:11, color:'#F39C12', scoreValue:28, xpValue:12,
//              behavior:'ranged', alertRadius:280, retreatRadius:90, attackRadius:200,
//              fireRate:2.2, fireCooldown:0, damage:8, bulletSpeed:160 },
//   fast:    { hp:10, speed:140, size:9,  color:'#1ABC9C', scoreValue:20, xpValue:8,
//              behavior:'zigzag', alertRadius:300, attackRadius:12, damage:8, zigzagTimer:0 },
// };
// function createEnemy(x, y, type) {
//   const def = ENEMY_DEFS[type] || ENEMY_DEFS.grunt;
//   return { ...def, type, x, y, maxHp: def.hp, vx:0, vy:0, flashTimer:0, active:true,
//            knockbackX:0, knockbackY:0 };
// }
//
// ── Comportements dans updateEnemy(e, dt) ──
// 'chase'  : const dx=pl.x-e.x, dy=pl.y-e.y, d=Math.sqrt(dx*dx+dy*dy);
//            if(d<e.alertRadius){e.x+=dx/d*e.speed*dt; e.y+=dy/d*e.speed*dt;}
// 'ranged' : si dist > retreatRadius → avancer; si dist < retreatRadius → reculer.
//            si fireCooldown <= 0 && dist < attackRadius → tirer; fireCooldown = fireRate.
// 'zigzag' : e.zigzagTimer += dt; const angle = Math.atan2(pl.y-e.y,pl.x-e.x);
//            e.x += Math.cos(angle + Math.sin(e.zigzagTimer*6)*0.8)*e.speed*dt;
//            e.y += Math.sin(angle + Math.sin(e.zigzagTimer*6)*0.8)*e.speed*dt;
//
// ── Progression des types au fil du temps ──
// 0-30s : seulement 'grunt'; 30-60s : grunt + shooter; 60-120s : tout;
// if (gameTime > 60) spawnWeights = { grunt:3, tank:2, shooter:3, fast:2 };
//
// RÈGLE : les ennemis de type 'shooter' ne doivent JAMAIS entrer en contact — si dist < retreatRadius, ils fuient.
// RÈGLE : knockbackRes des tanks → appliquer e.knockbackX *= e.knockbackRes dans updateEnemy.

49. POWER-UPS & COLLECTIBLES [tags: action, shooter, platformer, combat, survival] — vitamines du gameplay.
    Les power-ups créent des moments "wow" mémorables. Sans eux, le jeu semble plat.

// const POWERUP_DEFS = {
//   health: { color:'#2ECC71', symbol:'+', label:'+ VIE',    duration:0,
//             effect:(p) => { p.hp = Math.min(p.maxHp, p.hp + 30); } },
//   speed:  { color:'#3498DB', symbol:'»', label:'VITESSE!',  duration:6,
//             effect:(p) => { p._speedBase = p._speedBase||p.speed; p.speed=p._speedBase*1.7; } },
//   damage: { color:'#E74C3C', symbol:'↑', label:'ATK x2',   duration:8,
//             effect:(p) => { p._dmgBase = p._dmgBase||p.damage; p.damage=p._dmgBase*2; } },
//   shield: { color:'#F1C40F', symbol:'◈', label:'BOUCLIER', duration:5,
//             effect:(p) => { p.shielded = true; p.shieldTimer = 5; } },
// };
// let powerups = []; // variable globale
//
// function spawnPowerup(x, y) {
//   if (Math.random() > 0.18) return; // 18% de chance
//   const types = Object.keys(POWERUP_DEFS);
//   const type = types[Math.floor(Math.random() * types.length)];
//   powerups.push({ x, y, type, bob: Math.random()*Math.PI*2, collected:false, lifetime:12 });
// }
// Appel dans handleEnemyDefeat() : spawnPowerup(enemy.x, enemy.y);
//
// Dans update(dt) :
//   for (let i = powerups.length-1; i >= 0; i--) {
//     const pu = powerups[i]; pu.bob += dt*3; pu.lifetime -= dt;
//     if (pu.lifetime <= 0) { powerups.splice(i,1); continue; }
//     const dx = player.x-pu.x, dy = player.y-pu.y, d = Math.sqrt(dx*dx+dy*dy);
//     if (d < 22) { // collecte
//       POWERUP_DEFS[pu.type].effect(player);
//       spawnFloatingText(pu.x, pu.y, POWERUP_DEFS[pu.type].label, POWERUP_DEFS[pu.type].color, 13);
//       triggerShake(3, 0.08);
//       powerups.splice(i,1);
//     }
//   }
//   // Tick buffs temporaires
//   if (player.shieldTimer > 0) { player.shieldTimer -= dt; if(player.shieldTimer<=0) player.shielded=false; }
//   const spd = POWERUP_DEFS.speed; if (player._speedBase && player.speed > player._speedBase) {
//     if (!player._speedTimer) player._speedTimer = spd.duration;
//     player._speedTimer -= dt; if (player._speedTimer <= 0) { player.speed = player._speedBase; player._speedTimer=0; }
//   }
//
// function drawPowerups() {
//   for (const pu of powerups) {
//     const cfg = POWERUP_DEFS[pu.type]; const by = pu.y + Math.sin(pu.bob)*4;
//     ctx.globalAlpha = Math.min(1, pu.lifetime); // fade out en fin de vie
//     ctx.fillStyle = cfg.color+'33'; ctx.beginPath(); ctx.arc(pu.x,by,13,0,Math.PI*2); ctx.fill();
//     ctx.strokeStyle=cfg.color; ctx.lineWidth=2; ctx.stroke();
//     ctx.fillStyle=cfg.color; ctx.font='bold 11px monospace'; ctx.textAlign='center'; ctx.textBaseline='middle';
//     ctx.fillText(cfg.symbol, pu.x, by); ctx.globalAlpha=1;
//   }
//   ctx.textAlign='left'; ctx.textBaseline='alphabetic';
// }
// HUD des buffs actifs (coin bas-gauche) :
// ctx.font='8px monospace'; let bx=6, by=canvas.height-10;
// if(player.shielded){ctx.fillStyle='#F1C40F';ctx.fillText('◈ BOUCLIER',bx,by);by-=12;}
// RÈGLE : appeler drawPowerups() dans draw() juste après les entités, avant le HUD.

INTERDIT ABSOLU : N'utilise JAMAIS data:URI (data:font, data:image, etc.) — cela consomme tout le budget de tokens.
Utilise uniquement des polices système (Arial, monospace) et des formes Canvas 2D.

Q5 — SPRITES AVEC arc() ET bezierCurveTo() OBLIGATOIRES :
Les entités (joueur, ennemis, boss) NE DOIVENT PAS être des fillRect() simples.
Utilise TOUJOURS ctx.arc(), ctx.bezierCurveTo() ou ctx.quadraticCurveTo() pour leur donner des formes.
Exemples par genre :
- Shoot-em-up : vaisseau joueur = triangle avec ctx.beginPath()/lineTo() + glow (shadowBlur=15)
  ctx.beginPath(); ctx.moveTo(x,y-r); ctx.lineTo(x+r,y+r); ctx.lineTo(x-r,y+r); ctx.closePath(); ctx.fill();
- Platformer : personnage = corps arrondi
  ctx.beginPath(); ctx.arc(x, y-h/4, r, 0, Math.PI*2); ctx.fill(); // tête
  ctx.roundRect(x-w/2, y-h/2, w, h*0.75, 4); ctx.fill();            // corps
- RPG/Dungeon : personnage = silhouette avec bras
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.fill(); // corps principal
  ctx.beginPath(); ctx.arc(x, y-r*1.5, r*0.6, 0, Math.PI*2); ctx.fill(); // tête
- Boss : formes complexes avec bezier
  ctx.beginPath(); ctx.moveTo(x, y-r); ctx.bezierCurveTo(x+r,y-r, x+r,y+r, x,y+r); ctx.closePath(); ctx.fill();
Règle : ctx.arc() pour les ennemis ronds, ctx.lineTo() pour les polygones, ctx.bezierCurveTo() pour les boss.
Un jeu avec UNIQUEMENT des fillRect() sera pénalisé -2.0 pts en évaluation visuelle.
Ajouter ctx.shadowBlur = 10; ctx.shadowColor = color; avant les arc() pour l'effet glow.

Tu produis UNIQUEMENT le code HTML complet. Commence par <!DOCTYPE html>. Aucun texte avant ou après."""

SYSTEM_3D = """Tu es un développeur senior spécialisé en jeux 3D web avec Three.js r160. Tu produis du code Three.js qui FONCTIONNE SANS ERREUR dès le premier chargement.

RÈGLE ABSOLUE — CLASSES INTERDITES (examples/jsm uniquement, absentes du bundle principal) :
NE JAMAIS utiliser : THREE.Capsule, THREE.Octree, THREE.OctreeHelper, THREE.Convex*, THREE.CSG*
Pour les collisions : utilise THREE.Sphere, THREE.Box3, THREE.Raycaster — tous disponibles dans le bundle principal.
Pour les capsule-shapes : utilise new THREE.CapsuleGeometry(radius, length) pour le mesh visuel + THREE.Box3 pour les collisions.

RÈGLE ABSOLUE — INITIALISATION UI AVANT CORE :
Si le module 'ui' expose une fonction initUI(), elle DOIT être appelée dans init()
AVANT tout setState() ou appel à ui.showMenu() / ui.updateHUD().
CORRECT :
function init() {
  // 1. Three.js setup (renderer, scene, camera...)
  // 2. UI init FIRST — crée les éléments DOM
  if (typeof ui !== 'undefined' && ui.initUI) ui.initUI();
  // 3. THEN state change
  setState('MENU');
}
INTERDIT : setState('MENU') ou ui.showMenu() avant ui.initUI() → "Cannot read properties of undefined (reading 'style')"

RÈGLE ABSOLUE — NULL GUARDS OBLIGATOIRES DANS LA GAME LOOP :
Dans toute boucle sur un tableau d'entités (enemies, platforms, collectibles, etc.),
TOUJOURS vérifier que l'entité ET son mesh existent avant d'accéder à leurs propriétés :
CORRECT :
for (const e of enemies) {
  if (!e || !e.mesh) continue;  // ← OBLIGATOIRE — crash garanti si absent
  e.mesh.position.set(x, y, z);
}
for (let i = enemies.length - 1; i >= 0; i--) {
  const e = enemies[i];
  if (!e || !e.mesh) { enemies.splice(i, 1); continue; }
  // ...
}
INTERDIT : enemies.forEach(e => e.mesh.position.set(...)) sans vérification → "Cannot read properties of undefined"

RÈGLE ABSOLUE — PAS DE DEV CONSOLE À GÉNÉRER :
NE génère PAS de dev console / overlay de debug dans ton code.
La dev console est injectée automatiquement par le système après génération.

STRUCTURE HTML OBLIGATOIRE — colle ce squelette exactement :
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Titre</title><style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#000; overflow:hidden; }
#hud { position:fixed; top:12px; left:16px; color:#fff; font:bold 20px Arial; z-index:10; pointer-events:none; }
#score-display { position:fixed; top:12px; right:16px; color:#FFD700; font:bold 24px Arial; z-index:10; pointer-events:none; }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,0.88); display:flex; flex-direction:column; align-items:center; justify-content:center; color:#fff; z-index:20; }
.overlay h1 { font-size:3em; margin-bottom:20px; text-shadow:0 0 20px #0ff; }
.overlay p  { font-size:1.1em; margin:6px 0; color:#aaa; }
.btn { margin-top:24px; padding:14px 40px; font-size:1.2em; background:#0af; border:none; border-radius:8px; color:#fff; cursor:pointer; }
.btn:hover { background:#0cf; }
#gameover { display:none; }
</style></head>
<body>
<div id="hud">Vies: <span id="lives-val">3</span></div>
<div id="score-display">Score: <span id="score-val">0</span></div>
<div id="menu" class="overlay">
  <h1>TITRE DU JEU</h1>
  <p>Flèches / WASD — se déplacer</p>
  <p>Espace — action</p>
  <button class="btn" id="btn-start">JOUER</button>
</div>
<div id="gameover" class="overlay">
  <h1>GAME OVER</h1>
  <p>Score : <span id="final-score">0</span></p>
  <p>Meilleur : <span id="best-score-display">0</span></p>
  <button class="btn" id="btn-restart">REJOUER</button>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {

// ── SCENE SETUP ────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d0d1a);
scene.fog = new THREE.Fog(0x0d0d1a, 30, 100); // optionnel, adapté au genre

const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 500);
camera.position.set(0, 5, 10);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ── ÉCLAIRAGE (OBLIGATOIRE) ────────────────────
const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
scene.add(ambientLight);
const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
dirLight.position.set(8, 15, 8);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 1024;
dirLight.shadow.mapSize.height = 1024;
scene.add(dirLight);

// ── GAME STATE ─────────────────────────────────
let gameState = 'menu'; // 'menu' | 'playing' | 'gameover'
let score = 0, lives = 3;
const bestScore = parseInt(localStorage.getItem('highscore3d') || '0');

// ── GAME LOOP ──────────────────────────────────
const clock = new THREE.Clock();
function gameLoop() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (gameState === 'playing') update(dt);
  renderer.render(scene, camera);
  requestAnimationFrame(gameLoop);
}
gameLoop();

// ── BOUTONS ────────────────────────────────────
document.getElementById('btn-start').addEventListener('click', startGame);
document.getElementById('btn-restart').addEventListener('click', restartGame);

}); // fin DOMContentLoaded
</script>
</body></html>

PATTERNS OBLIGATOIRES :

1. GAME LOOP avec THREE.Clock (tout dans DOMContentLoaded) :
const clock = new THREE.Clock();
function gameLoop() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (gameState === 'playing') update(dt);
  renderer.render(scene, camera);
  requestAnimationFrame(gameLoop);
}
gameLoop(); // ← lancer IMMÉDIATEMENT dans DOMContentLoaded

2. TABLEAUX — .length = 0 UNIQUEMENT, JAMAIS .clear() :
enemies.length = 0;   // CORRECT
bullets.length = 0;   // CORRECT

3. ENTITÉS 3D — objet JS + mesh Three.js liés :
function createEnemy(x, y, z, type) {
  const geo  = type === 'fast'
    ? new THREE.SphereGeometry(0.6, 8, 8)
    : new THREE.BoxGeometry(1, 1, 1);
  const mat  = new THREE.MeshPhongMaterial({ color: type === 'fast' ? 0xff6600 : 0xff2222 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = true;
  mesh.position.set(x, y, z);
  scene.add(mesh);
  return { mesh, hp: type === 'fast' ? 1 : 2, speed: type === 'fast' ? 4 : 2,
           type, active: true, box: new THREE.Box3() };
}

4. COLLISION 3D avec THREE.Box3 :
const playerBox = new THREE.Box3();
// Dans update() :
playerBox.setFromObject(player.mesh);
for (const enemy of enemies) {
  if (!enemy.active) continue;
  enemy.box.setFromObject(enemy.mesh);
  if (playerBox.intersectsBox(enemy.box)) {
    // collision détectée
    enemy.active = false;
    scene.remove(enemy.mesh);
  }
}

5. RESTART PROPRE sans location.reload() :
function restartGame() {
  enemies.forEach(e => scene.remove(e.mesh));
  bullets.forEach(b => scene.remove(b.mesh));
  enemies.length = 0;
  bullets.length = 0;
  score = 0; lives = 3;
  player.mesh.position.set(0, 0, 0);
  updateHUD();
  document.getElementById('gameover').style.display = 'none';
  gameState = 'playing';
}

6. HUD VIA DOM (jamais via canvas 2D en mode Three.js) :
function updateHUD() {
  document.getElementById('score-val').textContent  = score;
  document.getElementById('lives-val').textContent  = lives;
}
function showGameOver() {
  document.getElementById('final-score').textContent    = score;
  document.getElementById('best-score-display').textContent = Math.max(score, bestScore);
  document.getElementById('gameover').style.display = 'flex';
  if (score > bestScore) localStorage.setItem('highscore3d', score);
  gameState = 'gameover';
}

7. PARTICULES 3D avec THREE.Points :
const explosions = [];
function createExplosion(position, color = 0xffaa00, count = 20) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  const vel = [];
  for (let i = 0; i < count; i++) {
    pos[i*3] = position.x; pos[i*3+1] = position.y; pos[i*3+2] = position.z;
    vel.push(new THREE.Vector3(
      (Math.random()-0.5)*6, Math.random()*4+1, (Math.random()-0.5)*6
    ));
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({ color, size: 0.25, transparent: true });
  const pts = new THREE.Points(geo, mat);
  scene.add(pts);
  explosions.push({ pts, vel, life: 1.0, count });
}
function updateExplosions(dt) {
  for (let i = explosions.length - 1; i >= 0; i--) {
    const ex = explosions[i];
    ex.life -= dt * 2;
    const arr = ex.pts.geometry.attributes.position.array;
    for (let j = 0; j < ex.count; j++) {
      arr[j*3]   += ex.vel[j].x * dt;
      arr[j*3+1] += ex.vel[j].y * dt - 4 * dt; // gravité
      arr[j*3+2] += ex.vel[j].z * dt;
    }
    ex.pts.geometry.attributes.position.needsUpdate = true;
    ex.pts.material.opacity = ex.life;
    if (ex.life <= 0) { scene.remove(ex.pts); explosions.splice(i, 1); }
  }
}

8. CAMERA FPS (pointer lock) — UNIQUEMENT pour les jeux FPS :
let pitch = 0, yaw = 0, pointerLocked = false;
renderer.domElement.addEventListener('click', () => renderer.domElement.requestPointerLock());
document.addEventListener('pointerlockchange', () => {
  pointerLocked = document.pointerLockElement === renderer.domElement;
});
document.addEventListener('mousemove', e => {
  if (!pointerLocked || gameState !== 'playing') return;
  yaw   -= e.movementX * 0.002;
  pitch -= e.movementY * 0.002;
  pitch  = Math.max(-Math.PI * 0.4, Math.min(Math.PI * 0.4, pitch));
  camera.rotation.set(pitch, yaw, 0, 'YXZ');
});

9. CAMERA TPS + DÉPLACEMENTS CAMÉRA-RELATIFS — OBLIGATOIRE pour tout jeu 3D vue à la troisième personne.
   Sans ça, "avancer" pousse l'entité loin de la caméra et le joueur perd le contrôle.

// ── Caméra TPS qui suit le joueur ──
// const CAM_OFFSET = new THREE.Vector3(0, 10, 18); // hauteur + recul derrière le joueur
// Dans update() :
// const camTarget = player.mesh.position.clone().add(CAM_OFFSET);
// camera.position.lerp(camTarget, 0.08);
// camera.lookAt(player.mesh.position);

// ── Déplacements RELATIFS À LA CAMÉRA (indispensable en TPS) ──
// Sans ça : appuyer "haut" = monde+Z fixe (désorientant selon l'angle de caméra)
// Avec ça  : appuyer "haut" = toujours "vers l'avant de la caméra" (intuitif)
//
// Dans updatePlayer(dt) — REMPLACE moveDir world-space par ceci :
// const forward = new THREE.Vector3();
// camera.getWorldDirection(forward);
// forward.y = 0; forward.normalize();          // projeter sur le plan horizontal
// const right = new THREE.Vector3();
// right.crossVectors(forward, new THREE.Vector3(0,1,0)); // axe droit de la caméra
//
// let moveDir = new THREE.Vector3(0, 0, 0);
// if (keys.w || keys.arrowup)    moveDir.add(forward);
// if (keys.s || keys.arrowdown)  moveDir.sub(forward);
// if (keys.a || keys.arrowleft)  moveDir.sub(right);
// if (keys.d || keys.arrowright) moveDir.add(right);
// if (moveDir.lengthSq() > 0) moveDir.normalize();
//
// // Appliquer la vélocité
// player.velocity = player.velocity || new THREE.Vector3();
// player.velocity.add(moveDir.multiplyScalar(SPEED * dt));
// player.velocity.clampLength(0, MAX_SPEED);
// player.mesh.position.addScaledVector(player.velocity, dt);
// player.velocity.multiplyScalar(0.85); // friction
//
// // Orienter le mesh dans la direction du mouvement (rotation douce)
// if (player.velocity.lengthSq() > 0.01) {
//   const targetQ = new THREE.Quaternion().setFromUnitVectors(
//     new THREE.Vector3(0,0,1), player.velocity.clone().normalize()
//   );
//   player.mesh.quaternion.slerp(targetQ, dt * 8);
// }

10. INPUT 3D — handler générique obligatoire (WASD + Flèches) :
const keys = { w:false, a:false, s:false, d:false, arrowup:false, arrowleft:false, arrowdown:false, arrowright:false, shift:false, e:false, e_prev:false, ' ':false };
// ✅ Utiliser "key in keys" — JAMAIS keys.hasOwnProperty() (écrase la méthode native → tous les inputs cassés)
document.addEventListener('keydown', e => { const k = e.key.toLowerCase(); if (k in keys) { e.preventDefault(); keys[k] = true; } });
document.addEventListener('keyup',   e => { const k = e.key.toLowerCase(); if (k in keys) keys[k] = false; });
// Dans update() : keys.e_prev = keys.e;  ← toujours en fin de frame pour les interactions à single-press

11. AUDIO WEB (stub universel) :
const sfx = {
  _ctx: null,
  init() { if (!this._ctx) this._ctx = new (window.AudioContext||window.webkitAudioContext)(); },
  play(freq=440, dur=0.1, type='square', vol=0.1) {
    try { this.init();
      const o=this._ctx.createOscillator(), g=this._ctx.createGain();
      o.type=type; o.frequency.value=freq;
      g.gain.setValueAtTime(vol,this._ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001,this._ctx.currentTime+dur);
      o.connect(g); g.connect(this._ctx.destination);
      o.start(); o.stop(this._ctx.currentTime+dur);
    } catch(e) {}
  }
};

11. INTERACTIONS ENVIRONNEMENTALES 3D — à implémenter dès que la section GAME LOGICS décrit
    des leviers, coffres, portails, zones d'effet ou tout objet interactif :
// Détection de proximité (distance-based, plus simple qu'un raycaster pour ce contexte)
// const INTERACT_RANGE = 2.5; // unités Three.js
// function checkInteractions3D() {
//   for (const obj of interactables3d) {
//     const dist = player.mesh.position.distanceTo(obj.mesh.position);
//     obj.nearPlayer = dist < INTERACT_RANGE;
//     if (obj.nearPlayer && keys.e && !keys.e_prev) activate3DInteractable(obj);
//   }
//   keys.e_prev = keys.e;
// }
// function activate3DInteractable(obj) {
//   switch(obj.type) {
//     case 'lever':
//       obj.state = !obj.state;
//       obj.mesh.rotation.z = obj.state ? Math.PI/4 : -Math.PI/4; // animation rotation
//       const door = interactables3d.find(o => o.linkedId === obj.linkedId && o.type === 'door');
//       if (door) { door.open = obj.state; door.mesh.visible = !obj.state; }
//       sfx.play(440, 0.15, 'square');
//       break;
//     case 'chest':
//       if (!obj.used) { obj.used = true; obj.mesh.rotation.x = -Math.PI/2; // ouvrir couvercle
//         powerups.push(createPowerup3D(obj.mesh.position.clone())); sfx.play(880, 0.2, 'sine'); }
//       break;
//     case 'key':
//       if (!obj.used) { obj.used = true; scene.remove(obj.mesh); player.keys++; sfx.play(780, 0.1, 'square'); }
//       break;
//     case 'teleporter':
//       player.mesh.position.set(obj.data.targetX, obj.data.targetY, obj.data.targetZ);
//       createExplosion(player.mesh.position, 0x00ffff, 20); sfx.play(1000, 0.2, 'sine');
//       break;
//   }
// }
// // HUD pour les interactions : afficher "Appuie sur E" dans un div HTML overlay
// // if (obj.nearPlayer) document.getElementById('interact-hint').style.display = 'block';
// // else document.getElementById('interact-hint').style.display = 'none';
// // <div id="interact-hint" style="position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
// //   color:#FFD700;font:bold 18px Arial;display:none;z-index:10">[E] Interagir</div>

12. GAME FEEL 3D — OBLIGATOIRE (différence entre un jeu vide et un jeu vivant) :

// ── Screen Shake 3D (caméra) ──
// let shakeOffset = new THREE.Vector3(), shakeDur = 0, shakeMag = 0;
// function triggerShake(mag, dur) { shakeMag = mag; shakeDur = dur; }
// Dans update(dt) :
//   if (shakeDur > 0) { shakeDur -= dt;
//     shakeOffset.set((Math.random()-0.5)*shakeMag, (Math.random()-0.5)*shakeMag*0.6, 0);
//   } else { shakeOffset.set(0,0,0); }
// Dans animate() APRÈS mise à jour caméra :
//   camera.position.add(shakeOffset); // appliqué APRÈS le lerp de suivi
// Appels : triggerShake(0.3, 0.12) hit; triggerShake(0.7, 0.25) explosion; triggerShake(1.5, 0.5) boss

// ── Flash d'impact (couleur mesh ennemi) ──
// function flashEnemy(e, dur) {
//   e.mesh.traverse(c => { if (c.isMesh) { c._origColor = c._origColor || c.material.color.getHex(); c.material = c.material.clone(); c.material.color.set(0xFFFFFF); } });
//   setTimeout(() => { e.mesh.traverse(c => { if (c.isMesh && c._origColor !== undefined) c.material.color.set(c._origColor); }); }, dur * 1000);
// }
// Appel quand ennemi touché : flashEnemy(e, 0.08); triggerShake(0.3, 0.10);

// ── Vignette rouge écran joueur touché ──
// <div id="hit-vignette" style="position:fixed;inset:0;pointer-events:none;z-index:15;
//   background:radial-gradient(ellipse at center, transparent 40%, rgba(200,0,0,0.5) 100%);
//   opacity:0;transition:opacity 0.1s"></div>
// function flashHitVignette() { const v=document.getElementById('hit-vignette');
//   v.style.opacity='1'; setTimeout(()=>v.style.opacity='0',200); }
// Appel : flashHitVignette(); triggerShake(0.5, 0.15); // quand joueur touché

// ── Hitstop 3D ──
// let hitstopTimer = 0;
// function triggerHitstop(dur) { hitstopTimer = Math.max(hitstopTimer, dur); }
// Dans gameLoop : const realDt=clock.getDelta(); if(hitstopTimer>0){hitstopTimer-=realDt;renderer.render(scene,camera);return;}
// const dt = Math.min(realDt, 0.05); update(dt);

// ── Power-ups 3D (sphères colorées flottantes) ──
// let powerups3d = [];
// const POWERUP3D = { health:{color:0x2ECC71,label:'+VIE'}, speed:{color:0x3498DB,label:'SPEED'}, damage:{color:0xE74C3C,label:'ATK x2'} };
// function spawnPowerup3D(pos) {
//   if(Math.random()>0.18)return;
//   const types=Object.keys(POWERUP3D); const t=types[Math.floor(Math.random()*types.length)];
//   const geo=new THREE.SphereGeometry(0.4,8,8);
//   const mat=new THREE.MeshPhongMaterial({color:POWERUP3D[t].color,emissive:POWERUP3D[t].color,emissiveIntensity:0.4});
//   const mesh=new THREE.Mesh(geo,mat); mesh.position.copy(pos); mesh.position.y+=0.5; scene.add(mesh);
//   powerups3d.push({mesh,type:t,bob:Math.random()*Math.PI*2,lifetime:12});
// }
// Dans update(dt) : powerups3d.forEach((pu,i)=>{ pu.bob+=dt*2; pu.mesh.position.y+=Math.sin(pu.bob)*0.01;
//   pu.mesh.rotation.y+=dt*2; pu.lifetime-=dt;
//   const d=player.mesh.position.distanceTo(pu.mesh.position);
//   if(d<1.5||pu.lifetime<=0){ /* appliquer effet ou expirer */ scene.remove(pu.mesh); powerups3d.splice(i,1); }
// });

// CALIBRATION 3D — éviter la nausée :
// ✅ shake ennemi ordinaire : triggerShake(0.15, 0.08) — à peine perceptible
// ✅ shake joueur touché : triggerShake(0.4, 0.12)
// ✅ shake boss mort : triggerShake(1.0, 0.35) — spectaculaire mais rare
// ❌ INTERDIT : shake sur chaque tir/projectile, shake dans une boucle for
// ❌ INTERDIT : shakeOffset.magnitude > 0.6 sur un événement récurrent
// RÈGLE JUICE 3D : mort ennemi ordinaire → createExplosion(pos, color, 12) + triggerShake(0.15, 0.08)
// RÈGLE JUICE 3D : hit joueur → flashHitVignette() + triggerShake(0.4, 0.12)
// RÈGLE JUICE 3D : boss mort → triggerShake(1.0, 0.35) + createExplosion(pos, 0xFFD700, 35)

INTERDICTIONS ABSOLUES (erreurs fatales) :
- JAMAIS THREE.* en dehors du callback DOMContentLoaded
- JAMAIS .clear() sur des tableaux — utiliser .length = 0
- JAMAIS location.reload() pour restart — tout reset en JS pur
- JAMAIS data:URI pour textures ou polices — utiliser MeshPhongMaterial avec couleurs
- TOUJOURS scene.remove(mesh) avant de supprimer un objet du jeu
- TOUJOURS AmbientLight + DirectionalLight (sinon tout noir)
- TOUJOURS renderer.setClearColor() OU scene.background défini

Tu produis UNIQUEMENT le code HTML complet. Commence par <!DOCTYPE html>. Aucun texte avant ou après."""


def _generate_architecture_plan(gp, gdd: dict, tech: dict, game_logics: str) -> str:
    """
    Passe 1 : génère un plan d'architecture JSON avant de coder.
    Force le LLM à réfléchir à la structure avant d'écrire du code.
    Retourne une chaîne JSON (ou "" en cas d'échec).
    """
    genre = gp.genre_principal
    titre = gdd.get("titre", "Arcade Game")
    technologie = tech.get("technologie_rendu", "canvas2d")
    mecaniques = ", ".join(gp.mecaniques_obligatoires[:6]) if gp.mecaniques_obligatoires else ""
    states = tech.get("state_machine", {}).get("etats", ["menu", "playing", "gameover"])

    prompt = f"""Génère un plan d'architecture CONCRET pour ce jeu HTML5. Sois précis — les noms de variables doivent être exacts.

JEU : "{titre}" — Genre: {genre} — Technologie: {technologie}
MÉCANIQUES : {mecaniques}
ÉTATS : {', '.join(states)}

Réponds UNIQUEMENT avec ce JSON (sans markdown, sans explication) :
{{
  "declarations_js": "Les déclarations JS exactes à utiliser — ex: const PALETTE={{bg:'#111',player:'#0AF',enemy:'#F44',ui:'#FFF'}};\\nconst PLAYER_SPEED=200, GRAVITY=900;\\nlet score=0, lives=3, gameState='menu';\\nconst enemies=[], bullets=[], particles=[];",
  "fonctions_principales": ["gameLoop(ts)", "update(dt)", "draw()", "spawnEnemy(type,x,y)", "checkCollisions(dt)"],
  "ordre_draw": ["background", "enemies", "player", "projectiles", "particles", "hud"],
  "pieges_a_eviter": ["piège CONCRET spécifique à ce genre — ex: 'boucle enemies sans const en=enemies[i]'", "piège 2"]
}}"""

    try:
        raw = call_gemini(prompt, temperature=0.2, max_tokens=1600)
        if not raw:
            return ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        # Validate it's parseable JSON
        import json as _json
        _json.loads(raw.strip())
        return raw.strip()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATES PAR GENRE — squelettes structurels garantissant une base fonctionnelle
# Le LLM remplit les sections marquées [CUSTOM_...], ne touche pas au reste
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATE_SHOOTER = """\
SQUELETTE SHOOTER À REMPLIR — structure garantie fonctionnelle:

```html
<!DOCTYPE html>
<html><head><title>[CUSTOM_TITRE]</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#000;overflow:hidden;}}canvas{{display:block;}}
</style></head><body>
<canvas id="gameCanvas"></canvas>
<script>
// [CUSTOM_PALETTE] — définis ici tes couleurs: const PALETTE = {{bg:'#...', player:'#...', enemy:'#...', bullet:'#...', ui:'#...'}};
const GW = 480, GH = 640;
let canvas, ctx, lastTime = 0, gameState = 'menu';
let score = 0, lives = 3, level = 1;
const player = {{x:GW/2, y:GH-80, w:28, h:28, speed:220, shootTimer:0, shootRate:0.2, shield:false}};
const bullets = [], enemies = [], particles = [], floatingTexts = [], powerups = [];
let waveTimer = 0, waveIndex = 0, bossActive = false, boss = null;
const keys = {{left:false,right:false,up:false,down:false,space:false,space_pressed:false,z:false}};

// [CUSTOM_ENEMY_TYPES] — définis ENEMY_TYPES = {{ basic: {{...}}, fast: {{...}}, tank: {{...}} }}
// [CUSTOM_WAVE_PATTERNS] — définis WAVE_PATTERNS = [{{enemies:[...], formation:'line'}}]

function spawnEnemy(type, x, y) {{ /* [CUSTOM_SPAWN_ENEMY] */ }}
function spawnBoss() {{ /* [CUSTOM_SPAWN_BOSS] */ }}
function spawnBullet(x, y, vx, vy, isPlayer) {{ bullets.push({{x,y,vx,vy,isPlayer,w:6,h:12}}); }}
function spawnParticles(x, y, color, n) {{ for(let i=0;i<n;i++) particles.push({{x,y,vx:(Math.random()-0.5)*150,vy:(Math.random()-1)*200,life:0.6,color}}); }}
function spawnFloatingText(x, y, text, color) {{ floatingTexts.push({{x,y,text,color,life:1,vy:-40}}); }}

function update(dt) {{
  if(gameState==='menu') {{ updateMenu(dt); return; }}
  if(gameState==='paused') return;
  if(gameState==='gameover') {{ updateGameOver(dt); return; }}
  // [CUSTOM_UPDATE_PLAYER]
  // [CUSTOM_UPDATE_ENEMIES]
  // [CUSTOM_UPDATE_BULLETS]
  // [CUSTOM_UPDATE_COLLISIONS]
  // [CUSTOM_UPDATE_WAVES]
  // [CUSTOM_UPDATE_BOSS]
  updateParticles(dt); updateFloatingTexts(dt);
}}

function draw() {{
  ctx.fillStyle = PALETTE.bg; ctx.fillRect(0,0,GW,GH);
  // [CUSTOM_DRAW_BACKGROUND]
  // [CUSTOM_DRAW_ENEMIES]
  // [CUSTOM_DRAW_PLAYER]
  drawBullets(); drawParticles(); drawFloatingTexts(); drawHUD();
  if(gameState==='menu') drawMenu();
  if(gameState==='gameover') drawGameOver();
  if(gameState==='paused') drawPause();
}}

function drawBullets() {{ bullets.forEach(b => {{ ctx.fillStyle = b.isPlayer?PALETTE.bullet:'#f44'; ctx.fillRect(b.x-b.w/2,b.y-b.h/2,b.w,b.h); }}); }}
function drawParticles() {{ particles.forEach(p => {{ ctx.globalAlpha=p.life; ctx.fillStyle=p.color; ctx.fillRect(p.x-2,p.y-2,4,4); }}); ctx.globalAlpha=1; }}
function drawFloatingTexts() {{ floatingTexts.forEach(t => {{ ctx.fillStyle=t.color; ctx.font='bold 14px Arial'; ctx.textAlign='center'; ctx.fillText(t.text,t.x,t.y); }}); ctx.textAlign='left'; }}
function updateParticles(dt) {{ for(let i=particles.length-1;i>=0;i--) {{ const p=particles[i]; p.x+=p.vx*dt; p.y+=p.vy*dt; p.vy+=300*dt; p.life-=dt/0.6; if(p.life<=0) particles.splice(i,1); }} }}
function updateFloatingTexts(dt) {{ for(let i=floatingTexts.length-1;i>=0;i--) {{ const t=floatingTexts[i]; t.y+=t.vy*dt; t.life-=dt; if(t.life<=0) floatingTexts.splice(i,1); }} }}

function drawHUD() {{ /* [CUSTOM_DRAW_HUD] — score, lives, level */ }}
function drawMenu() {{ /* [CUSTOM_DRAW_MENU] */ }}
function drawGameOver() {{ /* [CUSTOM_DRAW_GAMEOVER] */ }}
function drawPause() {{ ctx.fillStyle='rgba(0,0,0,0.5)'; ctx.fillRect(0,0,GW,GH); ctx.fillStyle='#fff'; ctx.font='bold 24px Arial'; ctx.textAlign='center'; ctx.fillText('PAUSE',GW/2,GH/2); ctx.textAlign='left'; }}
function updateMenu(dt) {{ if(keys.space_pressed) {{ gameState='playing'; keys.space_pressed=false; }} }}
function updateGameOver(dt) {{ if(keys.space_pressed) {{ restartGame(); keys.space_pressed=false; }} }}

function restartGame() {{ score=0; lives=3; level=1; waveIndex=0; waveTimer=0; bossActive=false; boss=null; bullets.length=0; enemies.length=0; particles.length=0; floatingTexts.length=0; powerups.length=0; player.x=GW/2; player.y=GH-80; gameState='playing'; }}

function gameLoop(timestamp) {{
  const dt = Math.min((timestamp-lastTime)/1000, 0.05); lastTime=timestamp;
  update(dt); draw();
  requestAnimationFrame(gameLoop);
}}

document.addEventListener('keydown', e => {{ if(e.key==='ArrowLeft'||e.key==='a') keys.left=true; if(e.key==='ArrowRight'||e.key==='d') keys.right=true; if(e.key==='ArrowUp'||e.key==='w') keys.up=true; if(e.key==='ArrowDown'||e.key==='s') keys.down=true; if(e.key===' ') {{ keys.space=true; keys.space_pressed=true; e.preventDefault(); }} if(e.key==='p'||e.key==='P'||e.key==='Escape') {{ if(gameState==='playing') gameState='paused'; else if(gameState==='paused') gameState='playing'; }} }});
document.addEventListener('keyup', e => {{ if(e.key==='ArrowLeft'||e.key==='a') keys.left=false; if(e.key==='ArrowRight'||e.key==='d') keys.right=false; if(e.key==='ArrowUp'||e.key==='w') keys.up=false; if(e.key==='ArrowDown'||e.key==='s') keys.down=false; if(e.key===' ') keys.space=false; }});

document.addEventListener('DOMContentLoaded', () => {{
  canvas = document.getElementById('gameCanvas');
  canvas.width = GW; canvas.height = GH;
  ctx = canvas.getContext('2d');
  requestAnimationFrame(gameLoop);
}});
</script></body></html>
```

INSTRUCTIONS : remplace TOUS les [CUSTOM_...] par le code spécifique au jeu demandé. NE modifie PAS la structure gameLoop/DOMContentLoaded/restartGame — ils sont garantis fonctionnels.
"""

_TEMPLATE_PLATFORMER = """\
SQUELETTE PLATFORMER À REMPLIR:

```html
<!DOCTYPE html>
<html><head><title>[CUSTOM_TITRE]</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#000;overflow:hidden;}}canvas{{display:block;}}
</style></head><body>
<canvas id="gameCanvas"></canvas>
<script>
const GW=480, GH=320, TILE=16, SCALE=2;
// [CUSTOM_PALETTE]
let canvas, ctx, offscreen, gctx, lastTime=0, gameState='menu';
let score=0, level=1;
const player={{x:60,y:200,w:14,h:20,vx:0,vy:0,onGround:false,jumpsLeft:2,dashTimer:0,dashCooldown:0,coyoteTime:0,jumpBuffer:0,facing:1}};
const GRAVITY=900, JUMP_VY=-340, SPEED=160, DASH_SPEED=400, DASH_DUR=0.15;
const enemies=[], particles=[], floatingTexts=[], platforms=[];
const keys={{left:false,right:false,jump:false,jump_pressed:false,dash:false,dash_pressed:false}};

// [CUSTOM_LEVEL_DATA] — tiles[][] ou platforms[]
function loadLevel(n) {{ platforms.length=0; /* [CUSTOM_LOAD_LEVEL] */ }}
function spawnParticles(x,y,color,n){{ for(let i=0;i<n;i++) particles.push({{x,y,vx:(Math.random()-0.5)*120,vy:-Math.random()*200,life:0.5,color}}); }}
function spawnFloatingText(x,y,text,color){{ floatingTexts.push({{x,y,text,color,life:1,vy:-40}}); }}

function updatePlayer(dt){{
  // Mouvement horizontal
  if(keys.left) player.vx = Math.max(player.vx-SPEED*8*dt, -SPEED);
  else if(keys.right) player.vx = Math.min(player.vx+SPEED*8*dt, SPEED);
  else player.vx *= 0.75;
  // Coyote time & jump buffer
  if(player.onGround) {{ player.coyoteTime=0.1; player.jumpsLeft=2; }} else player.coyoteTime=Math.max(0,player.coyoteTime-dt);
  if(keys.jump_pressed) player.jumpBuffer=0.1; else player.jumpBuffer=Math.max(0,player.jumpBuffer-dt);
  if(player.jumpBuffer>0 && (player.coyoteTime>0||player.jumpsLeft>0)) {{
    player.vy=JUMP_VY; player.jumpsLeft--; player.coyoteTime=0; player.jumpBuffer=0;
    spawnParticles(player.x+player.w/2,player.y+player.h,'#fff',5);
  }}
  // Gravité
  player.vy = Math.min(player.vy+GRAVITY*dt, 600);
  player.x+=player.vx*dt; player.y+=player.vy*dt;
  player.onGround=false;
  // Collisions plateformes
  platforms.forEach(p => {{
    if(player.x+player.w>p.x && player.x<p.x+p.w && player.y+player.h>p.y && player.y+player.h<p.y+p.h+player.vy*dt+10 && player.vy>=0) {{
      player.y=p.y-player.h; player.vy=0; player.onGround=true;
    }}
  }});
  if(player.x<0) player.x=0; if(player.x+player.w>GW) player.x=GW-player.w;
  if(player.y>GH) {{ lives--; if(lives<=0) gameState='gameover'; else player.x=60; player.y=100; player.vy=0; }}
  keys.jump_pressed=false; keys.dash_pressed=false;
}}

let lives=3;
function update(dt){{
  if(gameState==='menu'){{ if(keys.jump_pressed){{ gameState='playing'; keys.jump_pressed=false; }} return; }}
  if(gameState==='paused') return;
  if(gameState==='gameover'){{ if(keys.jump_pressed){{ restartGame(); keys.jump_pressed=false; }} return; }}
  updatePlayer(dt);
  // [CUSTOM_UPDATE_ENEMIES]
  // [CUSTOM_UPDATE_COLLECTIBLES]
  for(let i=particles.length-1;i>=0;i--){{ const p=particles[i]; p.x+=p.vx*dt; p.y+=p.vy*dt; p.vy+=400*dt; p.life-=dt*2; if(p.life<=0) particles.splice(i,1); }}
  for(let i=floatingTexts.length-1;i>=0;i--){{ const t=floatingTexts[i]; t.y+=t.vy*dt; t.life-=dt; if(t.life<=0) floatingTexts.splice(i,1); }}
}}

function draw(){{
  gctx.fillStyle=PALETTE.bg; gctx.fillRect(0,0,GW,GH);
  // [CUSTOM_DRAW_BACKGROUND]
  platforms.forEach(p=>{{ gctx.fillStyle=PALETTE.ground; gctx.fillRect(p.x,p.y,p.w,p.h); }});
  // [CUSTOM_DRAW_ENEMIES]
  // [CUSTOM_DRAW_PLAYER]
  gctx.fillStyle=PALETTE.player; gctx.fillRect(player.x,player.y,player.w,player.h);
  particles.forEach(p=>{{ gctx.globalAlpha=Math.max(0,p.life*2); gctx.fillStyle=p.color; gctx.fillRect(p.x-2,p.y-2,4,4); }}); gctx.globalAlpha=1;
  floatingTexts.forEach(t=>{{ gctx.fillStyle=t.color; gctx.font='bold 8px monospace'; gctx.textAlign='center'; gctx.fillText(t.text,t.x,t.y); }}); gctx.textAlign='left';
  // [CUSTOM_DRAW_HUD]
  if(gameState==='menu') /* [CUSTOM_DRAW_MENU] */ void 0;
  if(gameState==='gameover') /* [CUSTOM_DRAW_GAMEOVER] */ void 0;
  ctx.drawImage(offscreen,0,0,canvas.width,canvas.height);
}}

function restartGame(){{ score=0; lives=3; level=1; enemies.length=0; particles.length=0; floatingTexts.length=0; player.x=60; player.y=200; player.vx=0; player.vy=0; loadLevel(1); gameState='playing'; }}

function gameLoop(timestamp){{
  const dt=Math.min((timestamp-lastTime)/1000,0.05); lastTime=timestamp;
  update(dt); draw(); requestAnimationFrame(gameLoop);
}}

document.addEventListener('keydown',e=>{{ if(e.key==='ArrowLeft'||e.key==='a') keys.left=true; if(e.key==='ArrowRight'||e.key==='d') keys.right=true; if(e.key==='ArrowUp'||e.key==='w'||e.key===' ') {{ keys.jump=true; keys.jump_pressed=true; e.preventDefault(); }} if(e.key==='ArrowDown'||e.key==='s') keys.down=true; if(e.key==='Shift') keys.dash_pressed=true; if(e.key==='p'||e.key==='Escape') {{ if(gameState==='playing') gameState='paused'; else if(gameState==='paused') gameState='playing'; }} }});
document.addEventListener('keyup',e=>{{ if(e.key==='ArrowLeft'||e.key==='a') keys.left=false; if(e.key==='ArrowRight'||e.key==='d') keys.right=false; if(e.key==='ArrowUp'||e.key==='w'||e.key===' ') keys.jump=false; if(e.key==='Shift') keys.dash=false; }});

document.addEventListener('DOMContentLoaded',()=>{{
  canvas=document.getElementById('gameCanvas');
  canvas.width=GW*SCALE; canvas.height=GH*SCALE;
  ctx=canvas.getContext('2d'); ctx.imageSmoothingEnabled=false;
  offscreen=document.createElement('canvas'); offscreen.width=GW; offscreen.height=GH;
  gctx=offscreen.getContext('2d'); gctx.imageSmoothingEnabled=false;
  loadLevel(1);
  requestAnimationFrame(gameLoop);
}});
</script></body></html>
```

INSTRUCTIONS: remplace les [CUSTOM_...] par le code spécifique. NE modifie PAS gameLoop, DOMContentLoaded, updatePlayer (physique) — garantis fonctionnels.
"""

_TEMPLATE_RPG = """\
SQUELETTE RPG/DUNGEON À REMPLIR — structure garantie fonctionnelle:

```html
<!DOCTYPE html>
<html><head><title>[CUSTOM_TITRE]</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#000;overflow:hidden;}}canvas{{display:block;}}
</style></head><body><canvas id="gameCanvas"></canvas><script>
// ── CONSTANTES TILEMAP ──
const TILE={{FLOOR:0,WALL:1,DOOR:2,STAIRS:3,CHEST:4}};
const TILE_SOLID=new Set([TILE.WALL]);
const MAP_W=40,MAP_H=30,TS=16,SCALE=2,GW=320,GH=240;
// [CUSTOM_PALETTE] : const PALETTE={{bg:'#111',floor:'#2a2a2a',wall:'#555',player:'#0AF',enemy:'#F44',ui:'#FFF'}};

let canvas,ctx,offscreen,gctx,lastTime=0,gameState='menu';
let score=0,dungeonFloor=1,shakeTime=0,shakeMag=0;
const map=Array.from({{length:MAP_H}},()=>new Array(MAP_W).fill(TILE.WALL));
const rooms=[];

// ── JOUEUR (tous les champs obligatoires — n'en omettre aucun) ──
const player={{x:GW/2,y:GH/2,w:12,h:14,vx:0,vy:0,speed:80,hp:30,maxHp:30,atk:5,def:1,level:1,xp:0,xpNext:20,gold:0,invTimer:0,attackTimer:0,attackCooldown:0.35,facing:'down',attackFlash:0}};

// ── ENEMY_DEFS — TOUS les timers déclarés ici ──
// [CUSTOM_ENEMY_DEFS]
const ENEMY_DEFS={{
  basic:{{type:'basic',hp:8, maxHp:8, atk:3,def:0,speed:45,color:'#F44',xpVal:5, goldVal:2,aggroRange:80, attackRange:14,attackCooldown:1.2}},
  fast: {{type:'fast', hp:4, maxHp:4, atk:2,def:0,speed:85,color:'#FA0',xpVal:8, goldVal:3,aggroRange:100,attackRange:12,attackCooldown:0.8}},
  tank: {{type:'tank', hp:22,maxHp:22,atk:5,def:2,speed:28,color:'#A44',xpVal:12,goldVal:5,aggroRange:60, attackRange:16,attackCooldown:1.8}},
}};
// [CUSTOM_BOSS_DEF]

const enemies=[],particles=[],floatingTexts=[],items=[];
let boss=null;
const keys={{left:false,right:false,up:false,down:false,space:false,space_pressed:false,e:false,e_prev:false}};

// ── FACTORY — COPIER TOUS LES TIMERS ──
function createEnemy(type,x,y){{
  const def=ENEMY_DEFS[type]||ENEMY_DEFS.basic;
  return {{...def,x,y,vx:0,vy:0,aiState:'patrol',aiTimer:Math.random()*2,attackTimer:0,knockVx:0,knockVy:0,knockTimer:0,hitFlash:0}};
}}

// ── UTILITAIRES ──
function isSolid(px,py){{const tx=Math.floor(px/TS),ty=Math.floor(py/TS);if(tx<0||ty<0||tx>=MAP_W||ty>=MAP_H)return true;return TILE_SOLID.has(map[ty][tx]);}}
function moveEntity(e,vx,vy,dt){{e.x+=vx*dt;if(isSolid(e.x,e.y)||isSolid(e.x+e.w,e.y)||isSolid(e.x,e.y+e.h)||isSolid(e.x+e.w,e.y+e.h))e.x-=vx*dt;e.y+=vy*dt;if(isSolid(e.x,e.y)||isSolid(e.x+e.w,e.y)||isSolid(e.x,e.y+e.h)||isSolid(e.x+e.w,e.y+e.h))e.y-=vy*dt;}}
function triggerShake(mag,dur){{shakeMag=mag;shakeTime=dur;}}
function spawnParticles(x,y,color,n){{for(let i=0;i<n;i++)particles.push({{x,y,vx:(Math.random()-0.5)*120,vy:(Math.random()-0.5)*120,life:0.6,color,size:2+Math.random()*3}});}}
function spawnFloatingText(x,y,text,color){{floatingTexts.push({{x,y,text,color,life:1.2,vy:-25}});}}

function checkLevelUp(){{
  while(player.xp>=player.xpNext){{
    player.xp-=player.xpNext;player.level++;player.maxHp+=10;player.hp=player.maxHp;player.atk+=2;player.def+=1;
    player.xpNext=Math.floor(player.xpNext*1.6);
    spawnFloatingText(player.x,player.y-20,'LEVEL '+player.level+'!','#FFD700');triggerShake(3,0.2);
  }}
}}

function generateDungeon(floorNum){{
  for(let y=0;y<MAP_H;y++)for(let x=0;x<MAP_W;x++)map[y][x]=TILE.WALL;
  rooms.length=0;enemies.length=0;items.length=0;
  // [CUSTOM_DUNGEON_GENERATION] : placeRoom(x,y,w,h) + connectRooms + placeEnemies + placeItems
  // Escalier dans dernière salle : map[stairY][stairX]=TILE.STAIRS;
  // Placer joueur dans 1ère salle : player.x=rooms[0].cx*TS; player.y=rooms[0].cy*TS;
}}

let camX=0,camY=0;
function updateCamera(){{camX=Math.max(0,Math.min(Math.floor(player.x+player.w/2-GW/2),(MAP_W*TS)-GW));camY=Math.max(0,Math.min(Math.floor(player.y+player.h/2-GH/2),(MAP_H*TS)-GH));}}

function update(dt){{
  if(gameState==='menu'){{if(keys.space_pressed){{initGame();keys.space_pressed=false;}}return;}}
  if(gameState==='gameover'){{if(keys.space_pressed){{gameState='menu';keys.space_pressed=false;}}return;}}
  // [CUSTOM_UPDATE_PLAYER] : handleInput + moveEntity(player, player.vx, player.vy, dt)
  for(let i=enemies.length-1;i>=0;i--){{
    const en=enemies[i]; // ← init locale OBLIGATOIRE en première ligne
    // [CUSTOM_ENEMY_AI]
    if(en.hp<=0){{player.xp+=en.xpVal;player.gold+=en.goldVal;score+=10;spawnParticles(en.x+6,en.y+6,en.color,8);enemies.splice(i,1);checkLevelUp();continue;}}
    en.attackTimer=Math.max(0,en.attackTimer-dt);en.knockTimer=Math.max(0,en.knockTimer-dt);en.hitFlash=Math.max(0,en.hitFlash-dt);
  }}
  // [CUSTOM_UPDATE_BOSS]
  // [CUSTOM_CHECK_PLAYER_ENEMY_COLLISIONS]
  if(player.hp<=0)gameState='gameover';
  for(let i=particles.length-1;i>=0;i--){{const p=particles[i];p.x+=p.vx*dt;p.y+=p.vy*dt;p.life-=dt*1.5;if(p.life<=0)particles.splice(i,1);}}
  for(let i=floatingTexts.length-1;i>=0;i--){{const t=floatingTexts[i];t.y+=t.vy*dt;t.life-=dt;if(t.life<=0)floatingTexts.splice(i,1);}}
  player.invTimer=Math.max(0,player.invTimer-dt);player.attackTimer=Math.max(0,player.attackTimer-dt);
  updateCamera();keys.space_pressed=false;keys.e_prev=keys.e;
}}

function draw(){{
  gctx.save();if(shakeTime>0){{gctx.translate((Math.random()-0.5)*shakeMag*2,(Math.random()-0.5)*shakeMag*2);shakeTime-=1/60;}}
  gctx.fillStyle=PALETTE.bg;gctx.fillRect(0,0,GW,GH); // fond EN PREMIER
  if(gameState==='menu'){{drawMenu();gctx.restore();ctx.drawImage(offscreen,0,0,canvas.width,canvas.height);return;}}
  // [CUSTOM_DRAW_MAP] : tuiles visibles avec offset camX/camY
  // [CUSTOM_DRAW_ITEMS]
  // [CUSTOM_DRAW_ENEMIES] : for(const en of enemies){{ drawEnemy(en); }}
  // [CUSTOM_DRAW_PLAYER]
  // [CUSTOM_DRAW_BOSS]
  particles.forEach(p=>{{gctx.globalAlpha=Math.max(0,p.life);gctx.fillStyle=p.color;gctx.fillRect(p.x-camX-p.size/2,p.y-camY-p.size/2,p.size,p.size);}});gctx.globalAlpha=1;
  floatingTexts.forEach(t=>{{gctx.fillStyle=t.color;gctx.font='bold 7px monospace';gctx.textAlign='center';gctx.fillText(t.text,t.x-camX,t.y-camY);}});gctx.textAlign='left';
  drawHUD();if(gameState==='gameover')drawGameOver();
  gctx.restore();ctx.drawImage(offscreen,0,0,canvas.width,canvas.height);
}}
function drawHUD(){{/* [CUSTOM_DRAW_HUD] : HP bar, XP bar, floor, gold */}}
function drawMenu(){{/* [CUSTOM_DRAW_MENU] */}}
function drawGameOver(){{gctx.fillStyle='rgba(0,0,0,0.7)';gctx.fillRect(0,0,GW,GH);gctx.fillStyle='#F44';gctx.font='bold 14px monospace';gctx.textAlign='center';gctx.fillText('GAME OVER',GW/2,GH/2-8);gctx.fillStyle='#FFF';gctx.font='7px monospace';gctx.fillText('ESPACE pour rejouer',GW/2,GH/2+10);gctx.textAlign='left';}}

function initGame(){{score=0;dungeonFloor=1;player.hp=player.maxHp=30;player.atk=5;player.def=1;player.level=1;player.xp=0;player.xpNext=20;player.gold=0;enemies.length=0;particles.length=0;floatingTexts.length=0;items.length=0;boss=null;generateDungeon(1);gameState='playing';}}

function gameLoop(ts){{const dt=Math.min((ts-lastTime)/1000,0.05);lastTime=ts;update(dt);draw();requestAnimationFrame(gameLoop);}}

document.addEventListener('keydown',e=>{{const k=e.key.toLowerCase();if(k==='arrowleft'||k==='a')keys.left=true;if(k==='arrowright'||k==='d')keys.right=true;if(k==='arrowup'||k==='w')keys.up=true;if(k==='arrowdown'||k==='s')keys.down=true;if(e.key===' '){{keys.space=true;keys.space_pressed=true;e.preventDefault();}}if(k==='e')keys.e=true;}});
document.addEventListener('keyup',e=>{{const k=e.key.toLowerCase();if(k==='arrowleft'||k==='a')keys.left=false;if(k==='arrowright'||k==='d')keys.right=false;if(k==='arrowup'||k==='w')keys.up=false;if(k==='arrowdown'||k==='s')keys.down=false;if(e.key===' ')keys.space=false;if(k==='e')keys.e=false;}});

document.addEventListener('DOMContentLoaded',()=>{{
  canvas=document.getElementById('gameCanvas');canvas.width=GW*SCALE;canvas.height=GH*SCALE;
  ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;
  offscreen=document.createElement('canvas');offscreen.width=GW;offscreen.height=GH;
  gctx=offscreen.getContext('2d');gctx.imageSmoothingEnabled=false;
  requestAnimationFrame(gameLoop);
}});
</script></body></html>
```

INSTRUCTIONS : remplace TOUS les [CUSTOM_...]. NE modifie PAS gameLoop, DOMContentLoaded, initGame, checkLevelUp, isSolid, moveEntity — garantis fonctionnels.
CRITIQUE : dans TOUTE boucle for-index sur enemies[], PREMIÈRE ligne = `const en = enemies[i];`
"""

_TEMPLATE_SURVIVAL = """\
SQUELETTE SURVIVAL/HORDE À REMPLIR — structure garantie fonctionnelle:

```html
<!DOCTYPE html>
<html><head><title>[CUSTOM_TITRE]</title><style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#000;overflow:hidden;}}canvas{{display:block;}}
</style></head><body><canvas id="gameCanvas"></canvas><script>
// [CUSTOM_PALETTE] : const PALETTE={{bg:'#0a0a1a',player:'#0AF',enemy:'#F44',bullet:'#FF0',ui:'#FFF',xp:'#0F0'}};
let canvas,ctx,lastTime=0,gameState='menu';
let score=0,wave=1,kills=0,combo=0,comboTimer=0,shakeTime=0,shakeMag=0;

// ── JOUEUR avec stats améliorables ──
const player={{x:0,y:0,w:24,h:24,hp:100,maxHp:100,speed:180,damage:15,fireRate:0.25,fireTimer:0,invTimer:0,xp:0,xpNext:30,level:1,piercing:false,multiShot:1}};

// ── DÉFINITIONS VAGUES (WAVE_DEFS[i] = config de la vague i+1) ──
// [CUSTOM_WAVE_DEFS]
const WAVE_DEFS=[
  {{count:6, types:['basic'],        spawnRate:1.5, bossWave:false}},
  {{count:10,types:['basic','fast'], spawnRate:1.2, bossWave:false}},
  {{count:8, types:['fast','tank'],  spawnRate:1.0, bossWave:false}},
  {{count:0, types:[],               spawnRate:0,   bossWave:true }}, // vague 4 = boss
];

// ── DÉFINITIONS ENNEMIS ──
// [CUSTOM_ENEMY_DEFS]
const ENEMY_DEFS={{
  basic:{{type:'basic',hp:20,maxHp:20,speed:60, damage:8, color:'#F44',xpVal:5, size:16,fireTimer:0,fireRate:0}},
  fast: {{type:'fast', hp:10,maxHp:10,speed:110,damage:5, color:'#FA0',xpVal:8, size:12,fireTimer:0,fireRate:0}},
  tank: {{type:'tank', hp:60,maxHp:60,speed:35, damage:15,color:'#A44',xpVal:15,size:22,fireTimer:0,fireRate:0}},
}};
// [CUSTOM_BOSS_DEF]

// ── UPGRADES disponibles (choisir 1 parmi 3 à chaque level up) ──
// [CUSTOM_UPGRADE_DEFS]
const UPGRADE_DEFS=[
  {{id:'speed',    label:'Vitesse +20%',  apply:()=>{{player.speed*=1.2;}}}},
  {{id:'damage',   label:'Dégâts +25%',   apply:()=>{{player.damage=Math.ceil(player.damage*1.25);}}}},
  {{id:'firerate', label:'Cadence +30%',  apply:()=>{{player.fireRate=Math.max(0.05,player.fireRate*0.75);}}}},
  {{id:'maxhp',    label:'HP max +40',    apply:()=>{{player.maxHp+=40;player.hp=Math.min(player.hp+40,player.maxHp);}}}},
  {{id:'piercing', label:'Tirs perçants', apply:()=>{{player.piercing=true;}}}},
  {{id:'multishot',label:'Double tir',    apply:()=>{{player.multiShot=Math.min(player.multiShot+1,3);}}}},
];
let upgradeChoices=[],pendingUpgrade=false;
function rollUpgrades(){{upgradeChoices=UPGRADE_DEFS.sort(()=>Math.random()-0.5).slice(0,3);pendingUpgrade=true;gameState='upgrade';}}

const enemies=[],bullets=[],particles=[],floatingTexts=[];
let waveEnemiesLeft=0,waveSpawnTimer=0,waveActive=false,waveClearTimer=0,boss=null;
const keys={{left:false,right:false,up:false,down:false,space:false,space_pressed:false}};
const mouse={{x:0,y:0,clicked:false}};

// ── FACTORY ENNEMIS ──
function createEnemy(type,x,y){{
  const def=ENEMY_DEFS[type]||ENEMY_DEFS.basic;
  return {{...def,x,y,vx:0,vy:0,fireTimer:def.fireRate*Math.random(),hitFlash:0,knockVx:0,knockVy:0,knockTimer:0}};
}}

function triggerShake(mag,dur){{shakeMag=mag;shakeTime=dur;}}
function spawnParticles(x,y,color,n){{for(let i=0;i<n;i++)particles.push({{x,y,vx:(Math.random()-0.5)*200,vy:(Math.random()-0.5)*200,life:0.5,color}});}}
function spawnFloatingText(x,y,text,color){{floatingTexts.push({{x,y,text,color,life:1,vy:-35}});}}

function startWave(n){{
  const def=WAVE_DEFS[Math.min(n-1,WAVE_DEFS.length-1)];
  if(def.bossWave){{/* [CUSTOM_SPAWN_BOSS] */}}
  else{{waveEnemiesLeft=def.count;waveSpawnTimer=0;}}
  waveActive=true;wave=n;
}}

function checkLevelUp(){{
  while(player.xp>=player.xpNext){{player.xp-=player.xpNext;player.level++;player.xpNext=Math.floor(player.xpNext*1.5);rollUpgrades();}}
}}

function update(dt){{
  if(gameState==='menu'){{if(keys.space_pressed||mouse.clicked){{initGame();}}return;}}
  if(gameState==='gameover'){{if(keys.space_pressed||mouse.clicked){{gameState='menu';}}return;}}
  if(gameState==='upgrade'){{/* [CUSTOM_HANDLE_UPGRADE_INPUT] */return;}}
  // [CUSTOM_UPDATE_PLAYER] : mouvement + tir
  // Vague : spawner les ennemis
  if(waveActive&&waveEnemiesLeft>0){{
    waveSpawnTimer-=dt;
    if(waveSpawnTimer<=0){{
      const def=WAVE_DEFS[Math.min(wave-1,WAVE_DEFS.length-1)];
      const type=def.types[Math.floor(Math.random()*def.types.length)];
      const side=Math.floor(Math.random()*4);
      let ex,ey;const W=canvas.width,H=canvas.height;
      if(side===0){{ex=Math.random()*W;ey=-30;}}else if(side===1){{ex=W+30;ey=Math.random()*H;}}else if(side===2){{ex=Math.random()*W;ey=H+30;}}else{{ex=-30;ey=Math.random()*H;}}
      enemies.push(createEnemy(type,ex,ey));waveEnemiesLeft--;waveSpawnTimer=def.spawnRate;
    }}
  }}
  // Mise à jour ennemis
  for(let i=enemies.length-1;i>=0;i--){{
    const en=enemies[i]; // ← init locale OBLIGATOIRE
    // [CUSTOM_ENEMY_MOVEMENT_AND_ATTACK]
    if(en.hp<=0){{player.xp+=en.xpVal;score+=10*(1+combo);spawnParticles(en.x,en.y,en.color,10);kills++;combo++;comboTimer=2.5;enemies.splice(i,1);checkLevelUp();}}
  }}
  // [CUSTOM_UPDATE_BULLETS_AND_COLLISIONS]
  // [CUSTOM_UPDATE_BOSS]
  if(player.hp<=0)gameState='gameover';
  if(waveActive&&enemies.length===0&&waveEnemiesLeft===0&&!boss){{waveActive=false;waveClearTimer=2.5;}}
  if(!waveActive&&waveClearTimer>0){{waveClearTimer-=dt;if(waveClearTimer<=0)startWave(wave+1);}}
  combo=comboTimer>0?combo:0;comboTimer=Math.max(0,comboTimer-dt);
  for(let i=particles.length-1;i>=0;i--){{const p=particles[i];p.x+=p.vx*dt;p.y+=p.vy*dt;p.life-=dt*2;if(p.life<=0)particles.splice(i,1);}}
  for(let i=floatingTexts.length-1;i>=0;i--){{const t=floatingTexts[i];t.y+=t.vy*dt;t.life-=dt;if(t.life<=0)floatingTexts.splice(i,1);}}
  player.invTimer=Math.max(0,player.invTimer-dt);player.fireTimer=Math.max(0,player.fireTimer-dt);
  if(shakeTime>0)shakeTime-=dt;mouse.clicked=false;keys.space_pressed=false;
}}

function draw(){{
  ctx.save();if(shakeTime>0)ctx.translate((Math.random()-0.5)*shakeMag*2,(Math.random()-0.5)*shakeMag*2);
  ctx.fillStyle=PALETTE.bg;ctx.fillRect(0,0,canvas.width,canvas.height); // fond EN PREMIER
  if(gameState==='menu'){{drawMenu();ctx.restore();return;}}
  if(gameState==='upgrade'){{drawUpgradeScreen();ctx.restore();return;}}
  // [CUSTOM_DRAW_BACKGROUND]
  // [CUSTOM_DRAW_ENEMIES] : for(const en of enemies){{ drawEnemy(en); }}
  // [CUSTOM_DRAW_BULLETS]
  // [CUSTOM_DRAW_PLAYER]
  // [CUSTOM_DRAW_BOSS]
  particles.forEach(p=>{{ctx.globalAlpha=Math.max(0,p.life*2);ctx.fillStyle=p.color;ctx.fillRect(p.x-3,p.y-3,6,6);}});ctx.globalAlpha=1;
  floatingTexts.forEach(t=>{{ctx.fillStyle=t.color;ctx.font='bold 13px Arial';ctx.textAlign='center';ctx.fillText(t.text,t.x,t.y);}});ctx.textAlign='left';
  drawHUD();if(gameState==='gameover')drawGameOver();
  ctx.restore();
}}
function drawHUD(){{/* [CUSTOM_DRAW_HUD] : score, wave, kills, HP bar, XP bar, combo */}}
function drawMenu(){{/* [CUSTOM_DRAW_MENU] */}}
function drawGameOver(){{ctx.fillStyle='rgba(0,0,0,0.75)';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#F44';ctx.font='bold 32px Arial';ctx.textAlign='center';ctx.fillText('GAME OVER',canvas.width/2,canvas.height/2-20);ctx.fillStyle='#FFF';ctx.font='16px Arial';ctx.fillText('Score: '+score+' | Vague: '+wave,canvas.width/2,canvas.height/2+15);ctx.fillText('Clic ou ESPACE pour rejouer',canvas.width/2,canvas.height/2+45);ctx.textAlign='left';}}
function drawUpgradeScreen(){{ctx.fillStyle='rgba(0,0,0,0.85)';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#FFD700';ctx.font='bold 24px Arial';ctx.textAlign='center';ctx.fillText('CHOISIS UNE AMÉLIORATION',canvas.width/2,80);upgradeChoices.forEach((u,i)=>{{const y=150+i*80;ctx.fillStyle='#222';ctx.fillRect(canvas.width/2-150,y-30,300,60);ctx.fillStyle='#FFF';ctx.font='16px Arial';ctx.fillText(u.label,canvas.width/2,y+8);}});ctx.textAlign='left';}}

function initGame(){{score=0;wave=1;kills=0;combo=0;comboTimer=0;player.x=canvas.width/2;player.y=canvas.height/2;player.hp=player.maxHp=100;player.speed=180;player.damage=15;player.fireRate=0.25;player.fireTimer=0;player.xp=0;player.xpNext=30;player.level=1;player.piercing=false;player.multiShot=1;enemies.length=0;bullets.length=0;particles.length=0;floatingTexts.length=0;boss=null;pendingUpgrade=false;startWave(1);gameState='playing';}}

function gameLoop(ts){{const dt=Math.min((ts-lastTime)/1000,0.05);lastTime=ts;update(dt);draw();requestAnimationFrame(gameLoop);}}

document.addEventListener('keydown',e=>{{const k=e.key.toLowerCase();if(k==='arrowleft'||k==='a')keys.left=true;if(k==='arrowright'||k==='d')keys.right=true;if(k==='arrowup'||k==='w')keys.up=true;if(k==='arrowdown'||k==='s')keys.down=true;if(e.key===' '){{keys.space=true;keys.space_pressed=true;e.preventDefault();}}}});
document.addEventListener('keyup',e=>{{const k=e.key.toLowerCase();if(k==='arrowleft'||k==='a')keys.left=false;if(k==='arrowright'||k==='d')keys.right=false;if(k==='arrowup'||k==='w')keys.up=false;if(k==='arrowdown'||k==='s')keys.down=false;if(e.key===' ')keys.space=false;}});

document.addEventListener('DOMContentLoaded',()=>{{
  canvas=document.getElementById('gameCanvas');canvas.width=window.innerWidth;canvas.height=window.innerHeight;
  ctx=canvas.getContext('2d');
  canvas.addEventListener('mousemove',e=>{{mouse.x=e.clientX;mouse.y=e.clientY;}});
  canvas.addEventListener('click',e=>{{mouse.x=e.clientX;mouse.y=e.clientY;mouse.clicked=true;}});
  requestAnimationFrame(gameLoop);
}});
</script></body></html>
```

INSTRUCTIONS : remplace TOUS les [CUSTOM_...]. NE modifie PAS gameLoop, DOMContentLoaded, initGame, checkLevelUp, startWave, createEnemy — garantis fonctionnels.
CRITIQUE : dans TOUTE boucle for-index sur enemies[], PREMIÈRE ligne = `const en = enemies[i];`
"""

_TEMPLATES = {
    "shooter": _TEMPLATE_SHOOTER,
    "shmup": _TEMPLATE_SHOOTER,
    "shoot": _TEMPLATE_SHOOTER,
    "spatial": _TEMPLATE_SHOOTER,
    "platformer": _TEMPLATE_PLATFORMER,
    "plateforme": _TEMPLATE_PLATFORMER,
    "platform": _TEMPLATE_PLATFORMER,
    "rpg": _TEMPLATE_RPG,
    "dungeon": _TEMPLATE_RPG,
    "roguelite": _TEMPLATE_RPG,
    "rogue": _TEMPLATE_RPG,
    "aventure": _TEMPLATE_RPG,
    "adventure": _TEMPLATE_RPG,
    "zelda": _TEMPLATE_RPG,
    "survival": _TEMPLATE_SURVIVAL,
    "horde": _TEMPLATE_SURVIVAL,
    "survie": _TEMPLATE_SURVIVAL,
    "vague": _TEMPLATE_SURVIVAL,
    "wave": _TEMPLATE_SURVIVAL,
    "tower": _TEMPLATE_SURVIVAL,
}


def _get_template_for_genre(gp) -> str:
    """Retourne le template structurel pour ce genre, ou '' si aucun template disponible."""
    genre = gp.genre_principal.lower()
    sous_genre = gp.sous_genre.lower()
    combined = genre + " " + sous_genre
    for key, template in _TEMPLATES.items():
        if key in combined:
            return template
    return ""


def _get_desired_tags(gp) -> set:
    """Dérive les tags pertinents depuis le GenreProfile."""
    genre = (gp.genre_principal + " " + (gp.sous_genre or "")).lower()
    style = (gp.style_visuel or "").lower()
    mec   = " ".join(gp.mecaniques_obligatoires or []).lower()
    ctx   = genre + " " + style + " " + mec

    tags = {"always"}

    # Pixel art / rétro
    if any(k in style for k in ["pixel", "retro", "rétro", "8-bit", "16-bit", "nes", "game boy", "gameboy", "snes", "pokémon", "pokemon"]):
        tags.add("pixelart")

    # Combat / ennemis / action
    if any(k in ctx for k in ["ennemi", "combat", "boss", "shoot", "attaque", "tir", "bullet", "enemy", "action", "kill", "mort", "dégât", "damage", "hp", "vie", "health"]):
        tags |= {"combat", "enemies", "action"}

    # Survival
    if any(k in ctx for k in ["survival", "survie", "horde", "wave", "vague", "zombie", "endless", "infini"]):
        tags |= {"survival", "combat", "action"}

    # Boss
    if "boss" in ctx:
        tags.add("boss")

    # Interactions environnementales
    if any(k in ctx for k in ["coffre", "levier", "porte", "clé", "interactif", "npc", "pnj", "marchand"]):
        tags.add("interactive")
    if any(k in genre for k in ["shoot", "shmup", "spatial", "space", "galaga", "bullet", "vaisseau"]):
        tags |= {"shooter", "interactive"}
    if any(k in genre for k in ["platform", "plateform", "jump"]):
        tags |= {"platformer", "interactive"}

    # RPG / aventure / dungeon
    if any(k in genre for k in ["rpg", "aventure", "adventure", "dungeon", "zelda", "rogue", "roguelite"]):
        tags |= {"rpg", "adventure", "dungeon", "interactive"}

    # Progression / level up
    if any(k in ctx for k in ["level up", "xp", "expérience", "progression", "niveaux"]):
        tags |= {"progression", "rpg"}

    # Boutique / shop
    if any(k in ctx for k in ["marchand", "boutique", "shop", "achat", "gold", " or ", "monnaie"]):
        tags.add("shop")

    # Sauvegarde
    if any(k in ctx for k in ["sauvegarde", "save", "persistant", "continuer"]):
        tags.add("save")

    # Loot
    if any(k in ctx for k in ["loot", "coffre", "trésor", "chest"]):
        tags.add("loot")

    return tags


def _build_system_2d(gp) -> str:
    """Construit SYSTEM_2D filtré par tags — plus robuste que la sélection par numéros."""
    desired = _get_desired_tags(gp)

    # Header fixe (tout avant le premier pattern numéroté)
    m0 = _re.search(r'\n0\. ', SYSTEM_2D)
    if not m0:
        return SYSTEM_2D  # fallback sécurisé

    header = SYSTEM_2D[:m0.start() + 1]
    body   = SYSTEM_2D[m0.start() + 1:]

    # Découper en blocs (chaque bloc commence par "N." ou "Nb.")
    blocks = _re.split(r'\n(?=\d+\w*\. )', body)

    parts = [header]
    included = 0
    for block in blocks:
        tag_match = _re.search(r'\[tags:\s*([^\]]+)\]', block)
        if tag_match:
            pattern_tags = {t.strip() for t in tag_match.group(1).split(',')}
            if pattern_tags & desired:   # inclusion si au moins 1 tag commun
                parts.append('\n' + block)
                included += 1
        else:
            # Pas de tags = inclure par défaut (rétrocompatibilité)
            parts.append('\n' + block)
            included += 1

    phase3_log.info(f"[Créateur] patterns 2D injectés : {included}/{len(blocks)} (genre: {gp.genre_principal}, tags: {sorted(desired)})")
    return ''.join(parts)


def run(context: ConceptionContext, patterns_reussis: list = None, tendances: str = "", erreurs_passees: list = None, game_logics: str = "") -> str:
    phase3_log.agent_start("Créateur", f"Génération du jeu '{context.gdd.get('titre', '?')}'")

    gp = context.genre_profile
    gdd = context.gdd
    tech = context.tech_specs
    ux = context.ux_specs
    levels = context.level_design

    est_3d = tech.get("technologie_rendu", "canvas2d") == "threejs"
    system_instruction = SYSTEM_3D if est_3d else _build_system_2d(gp)

    # Passe 1 : plan d'architecture (uniquement pour jeux 2D non-triviaux)
    arch_plan = ""
    if not est_3d:
        arch_plan = _generate_architecture_plan(gp, gdd, tech, game_logics)
        if arch_plan:
            phase3_log.info(f"[Créateur] Plan architecture généré ({len(arch_plan)} chars)")

    # Détecter un GDD fallback/vide et le reconstituer depuis le GenreProfile
    gdd_est_vide = (
        not gdd.get("systemes_principaux")
        and gdd.get("titre", "Arcade Game") in ("Arcade Game", "")
    )
    if gdd_est_vide:
        phase3_log.warning("GDD vide détecté (fallback) — reconstitution depuis GenreProfile")
        gdd = _build_gdd_from_genre_profile(gp)

    # Augmenter les tokens pour les jeux complexes (FPS, 3D, RPG)
    genres_complexes = {"fps", "shooter", "rpg", "simulation", "strategy", "3d"}
    is_complexe = (
        est_3d
        or any(g in gp.genre_principal.lower() for g in genres_complexes)
        or any(g in gp.sous_genre.lower() for g in genres_complexes)
    )
    max_tokens_generation = 65000 if is_complexe else 56000

    # Récupérer patterns depuis ChromaDB (complémente la mémoire fichier)
    query = f"{gp.genre_principal} {gp.sous_genre} {gp.boucle_core}"
    rag_patterns = rag.search_patterns(query, genre=gp.genre_principal, n_results=3)

    # Combiner mémoire fichier + ChromaDB
    all_patterns = list(patterns_reussis or []) + [
        p for p in rag_patterns
        if p not in (patterns_reussis or [])
    ]

    patterns_info = ""
    if all_patterns:
        patterns_info = "\nPATTERNS RÉUSSIS (s'en inspirer) :\n"
        for p in all_patterns[:4]:
            patterns_info += f"- Genre {p.get('genre')}: {p.get('boucle_core', '')} (score: {p.get('score', 0):.1f})\n"

    # Récupérer extraits de code réels depuis ChromaDB
    code_examples_info = ""
    try:
        snips = rag.search_code_snippets(gp.genre_principal, "gameloop", n=1)
        snips += rag.search_code_snippets(gp.genre_principal, "collision", n=1)
        if snips:
            code_examples_info = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nEXEMPLES DE CODE FONCTIONNEL (extraits de jeux réussis — adapte, ne copies pas)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for s in snips[:2]:
                code_examples_info += f"// Exemple {s['snippet_type']} — {s['game_name']} (score {s['score']:.1f}/10)\n"
                code_examples_info += s['code'][:800] + "\n\n"
    except Exception:
        code_examples_info = ""

    erreurs_info = ""
    if erreurs_passees:
        erreurs_info = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nERREURS À ÉVITER (sessions précédentes échouées)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for e in erreurs_passees[:5]:
            erreurs_info += f"- {e}\n"

    game_logics_info = f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nGAME LOGICS — MÉCANIQUES CONCRÈTES À IMPLÉMENTER\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{game_logics}\n" if game_logics else ""

    # ── Nouvelles données de profondeur du GDD (Game Designer v2 + Level Designer v2) ──
    depth_info = ""

    # Formules mathématiques précises
    formules = gdd.get("formules_cles", {})
    if formules:
        depth_info += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        depth_info += "FORMULES MATHÉMATIQUES — IMPLÉMENTER EXACTEMENT\n"
        depth_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for key, formula in formules.items():
            depth_info += f"  {key}: {formula}\n"

    # Contenu détaillé : stats ennemis, upgrades, power-ups, boss
    contenu = gdd.get("contenu_detaille", {})
    if contenu:
        depth_info += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        depth_info += "CONTENU DÉTAILLÉ — STATS À IMPLÉMENTER\n"
        depth_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        if contenu.get("ennemis_stats"):
            depth_info += "ENNEMIS (implémenter chaque type dans ENEMY_DEFS) :\n"
            depth_info += json.dumps(contenu["ennemis_stats"], ensure_ascii=False) + "\n"
        if contenu.get("upgrades_disponibles"):
            depth_info += "UPGRADES (implémenter chaque upgrade avec scaling) :\n"
            depth_info += json.dumps(contenu["upgrades_disponibles"], ensure_ascii=False) + "\n"
        if contenu.get("powerups"):
            depth_info += "POWER-UPS (implémenter dans POWERUP_DEFS) :\n"
            depth_info += json.dumps(contenu["powerups"], ensure_ascii=False) + "\n"
        if contenu.get("boss"):
            depth_info += "BOSS (implémenter phases et patterns) :\n"
            depth_info += json.dumps(contenu["boss"], ensure_ascii=False) + "\n"
        if contenu.get("session_arc"):
            depth_info += f"ARC DE SESSION : {contenu['session_arc']}\n"

    # Meta-loop
    meta = gdd.get("meta_loop", {})
    if meta:
        depth_info += f"\nMETA-LOOP : {meta.get('raison_rejouer', '')} | Hook: {meta.get('hook_psychologique', '')}\n"

    # Paliers de difficulté du Level Designer
    paliers = levels.get("paliers_difficulte", [])
    if paliers:
        depth_info += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        depth_info += "PALIERS DE DIFFICULTÉ — IMPLÉMENTER CES TRANSITIONS\n"
        depth_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        depth_info += json.dumps(paliers, ensure_ascii=False) + "\n"

    # Events planifiés
    events = levels.get("events_planifies", [])
    if events:
        depth_info += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        depth_info += "ÉVÉNEMENTS PLANIFIÉS — IMPLÉMENTER CHAQUE TRIGGER\n"
        depth_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        depth_info += json.dumps(events, ensure_ascii=False) + "\n"

    # Spawn patterns
    spawn_pats = levels.get("spawn_patterns", [])
    if spawn_pats:
        depth_info += "SPAWN PATTERNS :\n"
        depth_info += json.dumps(spawn_pats[:4], ensure_ascii=False) + "\n"

    # Interactions entre systèmes
    interactions = gdd.get("interactions_systemes", [])
    if interactions:
        depth_info += "\nINTERACTIONS ENTRE SYSTÈMES (implémenter ces liens) :\n"
        for inter in interactions[:4]:
            depth_info += f"  {inter.get('source', '')} → {inter.get('cible', '')} : {inter.get('description', '')}\n"
    tendances_info = f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nTENDANCES & RÉFÉRENCES DU GENRE\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{tendances}\n" if tendances else ""

    # Section narrative — injectée uniquement si le jeu est narratif
    narrative_info = ""
    nc = context.narrative_context
    if nc:
        narrative_info = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        narrative_info += "HISTOIRE & NARRATION — IMPLÉMENTER INTÉGRALEMENT\n"
        narrative_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        if nc.synopsis:
            narrative_info += f"Synopsis : {nc.synopsis}\n"
        if nc.ton_narratif:
            narrative_info += f"Ton : {nc.ton_narratif}\n"
        if nc.lore:
            narrative_info += f"Lore : {nc.lore}\n"

        # Actes
        if nc.acte1 or nc.acte2 or nc.acte3:
            narrative_info += "\nSTRUCTURE EN 3 ACTES :\n"
            if nc.acte1:
                narrative_info += f"  Acte 1 (début) : {nc.acte1}\n"
            if nc.acte2:
                narrative_info += f"  Acte 2 (milieu) : {nc.acte2}\n"
            if nc.acte3:
                narrative_info += f"  Acte 3 (fin) : {nc.acte3}\n"

        # Personnages
        if nc.personnages:
            narrative_info += "\nPERSONNAGES (chaque NPC doit être présent dans la map) :\n"
            for p in nc.personnages[:6]:
                if isinstance(p, dict):
                    nom = p.get("nom", p.get("name", "?"))
                    role = p.get("role", "")
                    motivation = p.get("motivation", "")
                    narrative_info += f"  [{nom}] {role}"
                    if motivation:
                        narrative_info += f" — {motivation}"
                    narrative_info += "\n"
                else:
                    narrative_info += f"  {p}\n"

        # Quêtes
        if nc.quetes:
            narrative_info += "\nQUÊTES (implémenter chaque quête dans quests = {}) :\n"
            for q in nc.quetes[:5]:
                if isinstance(q, dict):
                    qid = q.get("id", q.get("nom", "quest"))
                    obj = q.get("objectif", q.get("description", ""))
                    recompense = q.get("recompense", "")
                    narrative_info += f"  quests['{qid}'] = {{active: false, done: false}}\n"
                    if obj:
                        narrative_info += f"    → Objectif : {obj}\n"
                    if recompense:
                        narrative_info += f"    → Récompense : {recompense}\n"
                else:
                    narrative_info += f"  {q}\n"

        # Dialogues
        if nc.dialogues:
            narrative_info += "\nDIALOGUES (extraits — implémenter avec showDialog()/showChoiceDialog()) :\n"
            for d in nc.dialogues[:4]:
                if isinstance(d, dict):
                    speaker = d.get("personnage", d.get("speaker", "?"))
                    texte = d.get("texte", d.get("text", ""))
                    choix = d.get("choix", d.get("choices", []))
                    narrative_info += f"  [{speaker}] : \"{texte[:120]}\"\n"
                    if choix:
                        narrative_info += f"    Choix : {json.dumps(choix[:3], ensure_ascii=False)[:200]}\n"
                else:
                    narrative_info += f"  {str(d)[:150]}\n"

        narrative_info += """
⚠️ MOTEUR NARRATIF OBLIGATOIRE — implémenter ces systèmes exactement :

1. SYSTÈME DE QUÊTES :
   const quests = {};  // clés = IDs des quêtes ci-dessus, valeurs = {active, done}
   const flags = {};   // flags narratifs : flags['aldricLibere'] = true
   function checkQuestConditions() { /* vérifie flags → active/complète quêtes */ }
   function completeQuest(id) { quests[id].done = true; showDialog('Quête accomplie !', 'SYSTÈME'); }

2. MOTEUR DIALOGUE (typewriter) :
   let dialogState = null;  // null = pas de dialogue actif
   function showDialog(text, speaker) {
     dialogState = {text, speaker, displayed:'', timer:0, done:false};
   }
   function showChoiceDialog(text, choices, onChoice, speaker) {
     dialogState = {text, speaker, displayed:'', timer:0, done:true, choices, onChoice, selectedChoice:0};
   }
   // Dans update(dt) : if(dialogState) updateDialog(dt)
   // Dans draw() : if(dialogState) drawDialog()
   // drawDialog() : boîte semi-transparente en bas, typewriter, choix numérotés navigables ↑↓+ESPACE

3. INTERACTION NPC ([E] key) :
   // Dans update() si key E pressée : chercher NPC à distance < 60px
   // → déclencher dialogue + quest update selon flags

4. CONDITION DE VICTOIRE narrative :
   // Vérifier que les quêtes principales sont done → écran victoire avec résumé de l'histoire

5. ÉTATS DU JEU pour le narratif :
   states: ['menu', 'playing', 'dialogue', 'combat', 'victory', 'gameover']
   // En état 'dialogue' : mouvement bloqué, seuls les choix de dialogue sont actifs

⚠️ INTERDIT : dialogues non fonctionnels, NPCs qui ne parlent pas, quêtes sans objectif trackable
⚠️ OBLIGATOIRE : chaque personnage listé ci-dessus DOIT avoir au moins un dialogue jouable
"""

    # Template structurel pour ce genre (si disponible)
    template_info = ""
    if not est_3d:
        tmpl = _get_template_for_genre(gp)
        if tmpl:
            template_info = f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nTEMPLATE STRUCTUREL — BASE GARANTIE FONCTIONNELLE\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{tmpl}\n"

    # Construire le contexte complet
    rendu = tech.get("rendu", {})
    physique = tech.get("physique", {})
    inputs = tech.get("inputs", {})
    states = tech.get("state_machine", {}).get("etats", ["menu", "playing", "gameover"])

    # Exigences spécifiques 3D
    exigences_rendu = _build_3d_requirements(tech) if est_3d else _build_2d_requirements(rendu, states)
    canvas_w = rendu.get("canvas_size", {}).get("width", 800) if not est_3d else 0
    canvas_h = rendu.get("canvas_size", {}).get("height", 600) if not est_3d else 0

    game_feel = ux.get("game_feel", {})
    effets = ux.get("effets_visuels", {})

    valeurs = levels.get("valeurs_initiales", {})
    phases = levels.get("phases_ou_niveaux", [])
    spawn = levels.get("spawn_patterns", [])

    prompt = f"""Génère un jeu HTML5 complet et jouable.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDENTITÉ DU JEU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Titre : {gdd.get('titre', 'Arcade Game')}
Tagline : {gdd.get('tagline', '')}
Concept : {gdd.get('concept', '')}
Genre : {gp.genre_principal} / {gp.sous_genre}
Ton : {gp.ton} | Public : {gp.public_cible}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORE LOOP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('core_loop', {}), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERSONNAGE / ENTITÉ PRINCIPALE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('personnage_ou_entite', {}), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTÈMES PRINCIPAUX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('systemes_principaux', []), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBSTACLES / ENNEMIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('ennemis_ou_obstacles', []), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROGRESSION ET NIVEAUX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type : {levels.get('type_progression', 'endless')}
Valeurs initiales : {json.dumps(valeurs, ensure_ascii=False)}
Phases : {json.dumps(phases[:3], ensure_ascii=False)}
Spawn patterns : {json.dumps(spawn[:3], ensure_ascii=False)}
Courbe difficulté : {json.dumps(levels.get('courbe_difficulte', {}), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÉCONOMIE DU JEU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('economie_du_jeu', {}), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÉVÉNEMENTS ALÉATOIRES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('evenements_aleatoires', []), ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPÉCIFICATIONS TECHNIQUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Technologie : {"Three.js (CDN r160)" if est_3d else f"Canvas 2D {canvas_w}x{canvas_h}"}
États : {', '.join(states)}
Physique : gravité={physique.get('gravite', False)}, collisions={physique.get('collisions', 'AABB')}
Inputs : clavier={json.dumps(inputs.get('clavier', {}))}, touch={inputs.get('touch', True)}
⚠️ SOURIS OBLIGATOIRE (Pattern #19) : tout bouton, option de menu, carte de personnage ou action de combat DOIT être cliquable à la souris via drawButton()+hitTest(). Le clavier reste actif en parallèle — les deux inputs appellent les mêmes fonctions.
{"⚠️ TILEMAP + CAMÉRA OBLIGATOIRES (Pattern #21) : le monde doit scroller — utilise cam.x/cam.y centré sur le joueur, MAP_W×MAP_H tuiles, drawTile() pour chaque type. Un monde fixe d'un seul écran est inacceptable pour ce genre." if any(g in gp.genre_principal.lower() for g in ["rpg","zelda","aventure","exploration","platformer","action"]) else ""}
{"⚠️ ANIMATIONS DE SPRITES OBLIGATOIRES (Pattern #20) : chaque personnage doit avoir frames idle + walk (4 frames) selon la direction (up/down/left/right). Un sprite statique = rendu mort." if any(kw in (gp.style_visuel + " " + (gp.prompt_utilisateur_original or "")).lower() for kw in ["pixel","rétro","retro","zelda","pokemon","nes","game boy","8-bit","16-bit","8bit","16bit"]) else ""}
{"⚠️ DIALOGUE AVANCÉ OBLIGATOIRE (Pattern #22) : coffres, leviers, PNJ et quêtes DOIVENT utiliser showDialog() avec typewriter + speaker name. Pour les arbres de décision (quêtes, marchands), utilise showChoiceDialog(text, [{label,id}], onChoice, speaker) — les choix sont navigables au clavier (↑↓ + ESPACE). Bord pixel art, indicateur ▼ clignotant." if any(g in gp.genre_principal.lower() for g in ["rpg","aventure"]) or any(kw in (gp.prompt_utilisateur_original or "").lower() for kw in ["coffre","levier","pnj","quête","mission","dialogue","npc","marchand","quest"]) else ""}
⚠️ FLOATING TEXT OBLIGATOIRE (Pattern #23) : tout dégât, XP, collectible DOIT spawner un floating text coloré via spawnFloatingText(). Appeler updateFloatingTexts(dt) et drawFloatingTexts().
⚠️ FADE TRANSITION OBLIGATOIRE (Pattern #24) : utilise fadeOut/fadeIn entre les zones, au game over et au lancement. Jamais de coupure sèche.
{"⚠️ HUD PIXEL ART OBLIGATOIRE (Pattern #25) : dessine des cœurs pixel par pixel pour les HP, des barres colorées pour XP/MP, des slots d'inventaire. Pas de texte brut pour les stats." if any(kw in (gp.style_visuel + " " + (gp.prompt_utilisateur_original or "")).lower() for kw in ["pixel","rétro","retro","zelda","pokemon","nes","game boy","8-bit","16-bit","8bit","16bit"]) else ""}
{"⚠️ IA ENNEMIS OBLIGATOIRE (Pattern #26) : chaque ennemi DOIT avoir les états patrol/chase/attack avec alertRadius et attackRadius. Varier les types (slime, garde, archer...)." if any(g in gp.genre_principal.lower() for g in ["rpg","aventure","action","platformer","shooter","roguelite","survival"]) else ""}
{"⚠️ SALLE DE BOSS OBLIGATOIRE (Pattern #27) : le boss DOIT être dans une zone dédiée au coin de la map, accessible seulement après une condition (leviers/clés). Utilise bossGate (porte verrouillée), spawnBoss() et drawBossHud(). Le boss a 3 phases visuellement distinctes (couleur change). JAMAIS le boss en plein milieu du jeu dès le début." if any(g in gp.genre_principal.lower() for g in ["rpg","aventure","action","dungeon"]) or any(kw in (gp.prompt_utilisateur_original or "").lower() for kw in ["boss","donjon","dungeon","quête","mission"]) else ""}
{"⚠️ API DEV CONSOLE OBLIGATOIRE (Pattern #43) : utilise EXACTEMENT les noms hero, enemies[], boss, loot[], interactables[], bossGate, minions[], playerStats, playerInventory, activeBuffs[], currentDungeonFloor. Fonctions : createEnemy(), handleEnemyDefeat(), spawnBoss(), generateDungeon(), checkLevelUp(), applyKnockback(), spawnParticles(), spawnFloatingText(), triggerShake(), createProjectile(). La dev console dépend de ces noms exacts pour ses recettes admin." if any(g in gp.genre_principal.lower() for g in ["rpg","dungeon","aventure","action","roguelite","survival"]) or any(kw in (gp.prompt_utilisateur_original or "").lower() for kw in ["héros","personnage","classe","ennemi","combat","donjon","dungeon","boss"]) else ""}
{"⚠️ CLASSES JOUABLES OBLIGATOIRES (Pattern #43) : utilise HERO_CLASSES[], CUSTOM_SKILLS{id:fn()}, CUSTOM_ATTACKS{id:fn(baseDmg,atkRange)} — indispensable pour la création/modification de classe via dev console. Chaque classe : {id, name, description, color, baseHp, baseMp, baseAtk, baseDef, baseSpd, atkName, skillName, atkCost, atkCooldown, skillCost, skillCooldown, skillDuration}." if any(g in gp.genre_principal.lower() for g in ["rpg","dungeon","roguelite"]) else ""}
Caméra : {rendu.get('camera', 'statique')}
{"⚠️ DÉPLACEMENTS CAMÉRA-RELATIFS OBLIGATOIRES (Pattern #9 SYSTEM_3D) : utilise camera.getWorldDirection() projeté sur le plan Y=0 pour calculer forward/right, puis moveDir = forward*input + right*input. JAMAIS de moveDir en espace monde fixe — le joueur perdrait le contrôle dès que la caméra tourne. Voir Pattern #9 du SYSTEM pour le code complet." if est_3d and any(kw in rendu.get('camera','').lower() for kw in ['tps','troisième','third','follow','suit']) else ""}
{"Renderer : WebGLRenderer plein écran responsive" if est_3d else f"Layers : {json.dumps(rendu.get('layers', ['background', 'entities', 'ui']))}"}
Notes techniques : {gp.notes_techniques}
Recommandations : {tech.get('recommandations_specifiques', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UX / GAME FEEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Style visuel : {gp.style_visuel}
{"⚠️ PIXEL ART OBLIGATOIRE : applique le Pattern #18 — canvas basse résolution (160×144 ou 256×240) scalée ×3, sprites dessinés par tableaux de fillRect 1×1, palette de couleurs limitée (4-16 couleurs), imageSmoothingEnabled=false." if any(kw in (gp.style_visuel + " " + (gp.prompt_utilisateur_original or "")).lower() for kw in ["pixel", "rétro", "retro", "zelda", "pokemon", "nes", "game boy", "8-bit", "16-bit", "8bit", "16bit"]) else ""}
Palette : {gp.palette_recommandee}
Sensations cibles : {json.dumps(game_feel.get('sensations_cibles', []), ensure_ascii=False)}
Éléments juice : {json.dumps(game_feel.get('elements_juice', []), ensure_ascii=False)}
Effets visuels : {json.dumps(effets, ensure_ascii=False)}
HUD : {json.dumps(ux.get('hud', {}), ensure_ascii=False)}
Polish spécifique : {ux.get('polish_specifique_genre', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REJOUABILITÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(gdd.get('rejouabilite', {}), ensure_ascii=False)}
{patterns_info}{code_examples_info}{erreurs_info}{game_logics_info}{depth_info}{narrative_info}{template_info}{f'''
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PLAN D'ARCHITECTURE — NOMS À UTILISER EXACTEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UTILISE CES NOMS DE VARIABLES ET FONCTIONS EXACTEMENT — pas d'autres noms inventés.
{arch_plan}

RÈGLE CRITIQUE : les "declarations_js" ci-dessus = les déclarations que tu dois mettre en haut du script (avant DOMContentLoaded). Utilise CES noms exacts partout dans le code — jamais de variantes.
RÈGLE : les fonctions dans "fonctions_principales" DOIVENT toutes être définies au niveau global. gameLoop, update, draw = toujours au top level du script.
''' if arch_plan else ''}
{tendances_info}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXIGENCES OBLIGATOIRES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{exigences_rendu}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXIGENCES DE QUALITÉ — NIVEAU PROFESSIONNEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAME FEEL — OBLIGATOIRE (différence entre un jeu terne et un jeu vivant) :
▶ Screen shake sur chaque impact (Pattern #47) : triggerShake() sur hit joueur, mort ennemi, boss
▶ Flash blanc sur entité touchée : flashTimer = 0.08 sur tout ennemi qui reçoit un dégât
▶ Flash rouge écran quand joueur touché : playerFlash = 0.20 → ctx.fillRect rouge semi-transparent
▶ Hitstop sur coups critiques : triggerHitstop(0.05-0.12) — skips update pendant quelques frames
▶ Coyote time + jump buffer (Pattern #47) si genre platformer : coyoteTime=0.10s, jumpBuffer=0.12s
▶ Particules à chaque mort : spawnParticles(e.x, e.y, e.color, 12-20) OBLIGATOIRE
▶ Floating text sur chaque dégât et collecte (Pattern #23) : spawnFloatingText()
▶ Feedback son : implémenter AudioContext Web API même silencieux (oscillator.connect(gainNode))

VARIÉTÉ — OBLIGATOIRE (3 types d'ennemis minimum pour tout jeu avec des ennemis) :
▶ Type GRUNT : rapide, fonce vers le joueur — couleur chaude (rouge, orange)
▶ Type TANK : lent, beaucoup de HP, résistant au knockback — grande taille, couleur froide (violet)
▶ Type RANGED : reste à distance, tire des projectiles, RECULE si trop proche — couleur distincte
▶ Chaque type : scoreValue différent, xpValue différent, comportement distinct dans updateEnemy()
▶ Progression temporelle : introduire les types rares progressivement (RANGED après 45s, TANK après 30s)
▶ Utiliser ENEMY_DEFS (Pattern #48) avec createEnemy(x, y, type) systématiquement

POWER-UPS — OBLIGATOIRE pour tout jeu d'action/action-RPG/shooter (Pattern #49) :
▶ 3 types minimum : soin (vert), vitesse (bleu), dégâts (rouge)
▶ Drop sur mort ennemi : 18% de chance dans handleEnemyDefeat() → spawnPowerup(e.x, e.y)
▶ Oscillation visuelle (bobbing) : pu.y += Math.sin(pu.bob) * 0.3
▶ Floating text coloré à la collecte : "+VIE", "SPEED!", "ATK x2"
▶ Buffs temporaires avec timer visible dans le HUD (coin bas-gauche)

VISUEL — OBLIGATOIRE :
▶ Fond non-noir : dégradé ou étoiles/décors procéduraux ou couleur saturée
▶ Palette cohérente de 5+ couleurs définies dans PALETTE = {{bg, player, enemy, ui, accent}}
▶ Joueur et entités : formes reconnaissables (pas des rectangles identiques)
▶ HUD : score, vies/HP, et buffs actifs visibles et lisibles en permanence
▶ Écran de démarrage avec titre et contrôles affichés (pas d'écran noir)

GAMEPLAY — OBLIGATOIRE :
▶ Contrôles affichés dès le début : "WASD/Flèches : déplacer | ESPACE : attaquer | P : pause"
▶ Difficulté progressive : premières 30s accessibles, montée continue après
▶ Game loop jamais figée : spawn, mouvement, spawn ou timer toujours actifs
▶ Feedback immédiat à CHAQUE action joueur (animation, particule, son, shake)
▶ INTERACTIONS ENVIRONNEMENTALES (Pattern #15) : leviers/coffres/portails avec [E] + particules
▶ Restart complet sans rechargement page : resetGame() remet tout à zéro

TECHNIQUE — OBLIGATOIRE :
▶ Canvas plein écran ou min 800px — canvas.width=innerWidth; canvas.height=innerHeight
▶ Delta time sur TOUT mouvement et TOUS les timers — aucune valeur fixe par frame
▶ localStorage highscore : clé "hs_" + genre spécifique
▶ Éviter les recalculs inutiles dans RAF : précalculer les positions hors boucle
▶ Nettoyer les tableaux correctement : arr.splice(i,1) en boucle inverse, jamais arr.clear()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERDICTIONS ABSOLUES (erreurs fatales à éviter)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- N'écris JAMAIS `br` seul dans le JavaScript — utilise `break;`
- N'utilise JAMAIS d'entités HTML (&amp; &lt; &gt;) dans le code JavaScript
- N'insère JAMAIS de balises HTML (<br>, <p>, <div>) à l'intérieur des balises <script>
- La déclaration d'un objet (ex: inputState, keys) doit utiliser EXACTEMENT les mêmes noms de propriétés
  partout : déclaration, lecture dans les handlers, et lecture dans les fonctions update.
  Exemple CORRECT : déclare `keys = {{ left: false }}` ET utilise `keys.left` partout.
  Exemple INTERDIT : déclare `keys = {{ left: false }}` mais utilise `keys.moveLeft` ailleurs.
- Les tableaux JavaScript (enemies, bullets, particles, etc.) n'ont PAS de méthode `.clear()`.
  Pour vider un tableau utilise TOUJOURS `enemies.length = 0` ou `enemies = []`, JAMAIS `enemies.clear()`.
- Ne référence JAMAIS un module ou objet que tu n'as pas déclaré dans ce même fichier.
  Si tu utilises `audioManager.play()`, tu DOIS déclarer `const audioManager = {{ play() {{}} }}` dans le code.
  INTERDIT : utiliser `particleSystem.emit()` sans l'avoir défini.
- Tout accès au DOM (getElementById, querySelector, canvas) DOIT être dans un callback
  `document.addEventListener('DOMContentLoaded', ...)` ou `window.onload = ...` pour éviter les erreurs null.
- Le jeu doit DÉMARRER et afficher du contenu immédiatement (pas un écran noir vide).
  La boucle requestAnimationFrame DOIT être lancée au chargement de la page.
- N'utilise JAMAIS de data:URI (data:font/..., data:image/..., data:application/...) dans le CSS ou le HTML.
  Ces encodages base64 consomment tout le budget de tokens et ne laissent plus de place pour le code du jeu.
  INTERDIT : @font-face {{ src: url('data:font/ttf;base64,...') }}
  INTERDIT : <img src="data:image/png;base64,...">
  Utilise UNIQUEMENT des couleurs, formes Canvas 2D, et polices système (Arial, monospace, sans-serif, etc.).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORDRE DE GÉNÉRATION OBLIGATOIRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Génère le code DANS CET ORDRE EXACT — ne pas changer l'ordre :

ÉTAPE 1 — Constantes légères (palette, TILE enum, tailles) — PAS les arrays sprites
ÉTAPE 2 — Variables d'état du jeu (gameState, score, hero, enemies, etc.)
ÉTAPE 3 — Game loop + update() + collisions + game over/restart  ← CRITIQUE
ÉTAPE 4 — Fonctions draw() avec formes simples (fillRect, arc) par défaut
ÉTAPE 5 — Interactions, combat, dialogues, boss ← CRITIQUE
ÉTAPE 6 — Event handlers (keydown/up, mousemove, click)
ÉTAPE 7 — Initialisation + requestAnimationFrame ← OBLIGATOIRE
ÉTAPE 8 — Données visuelles pixel art (HERO_FRAMES, TILE_COLORS, sprites) EN DERNIER

⚠️ RÈGLE ABSOLUE : Les ÉTAPES 1-7 DOIVENT être complètes et fonctionnelles.
   L'ÉTAPE 8 (sprites) est de la présentation — si tu n'as plus assez de tokens,
   remplace les sprites par des formes colorées (PALETTE.hero = '#D82800', fillRect).
   Un jeu sans sprites pixel art détaillés mais qui FONCTIONNE vaut mieux qu'un jeu
   avec de beaux sprites mais cassé syntaxiquement.

⚠️ JAMAIS : définir des tableaux de sprites de 8×8 ou plus AU DÉBUT du script.
   Les sprites vont en ÉTAPE 8, après toute la logique.

⚠️ HERO_CLASSES / ENNEMIS — format COMPACT obligatoire (pas de descriptions textuelles) :
   // CORRECT (compact) :
   const HERO_CLASSES = [
     {{ name:'Guerrier', hp:50, mp:20, atk:12, def:8, spd:4, color:'#D82800',
       skills:[{{name:'Frappe',mult:1.5,cd:3,cost:10}},{{name:'Bouclier',mult:0,cd:5,cost:15}},{{name:'Critique',mult:2,cd:8,cost:20}}] }},
     {{ name:'Mage', hp:30, mp:60, atk:15, def:3, spd:6, color:'#3CBCFC',
       skills:[{{name:'Boule de Feu',mult:2,cd:3,cost:20}},{{name:'Gel',mult:1,cd:4,cost:25}},{{name:'Éclair',mult:2.5,cd:8,cost:35}}] }},
     {{ name:'Voleur', hp:40, mp:30, atk:10, def:5, spd:8, color:'#70C848',
       skills:[{{name:'Frappe x2',mult:0.8,cd:2,cost:10}},{{name:'Poison',mult:0.5,cd:5,cost:15}},{{name:'Backstab',mult:3,cd:10,cost:25}}] }},
   ];
   // INTERDIT (trop verbeux) : descriptions longues, lore, flavor text dans les objets de données.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CONTRAT UTILISATEUR — ÉLÉMENTS OBLIGATOIRES NON NÉGOCIABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Le joueur a demandé EXACTEMENT :
"{gp.prompt_utilisateur_original}"

RÈGLE ABSOLUE : chaque élément nommé dans ce prompt DOIT être présent dans le code.
- Chaque type d'ennemi/tour/objet mentionné → doit exister avec son propre comportement
- Chaque mécanique mentionnée (boss, vagues, upgrades...) → doit être implémentée
- Le style visuel mentionné → doit se retrouver dans la palette et les effets
Omettre un élément du prompt = livrable invalide.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Génère maintenant le code HTML complet. Commence par <!DOCTYPE html> et termine par </html>.
Ne mets AUCUN texte avant ou après le code."""

    code = _call(prompt, system_instruction, max_tokens_generation)

    # Nettoyage du code si le modèle a ajouté des backticks
    code = _clean_html(code)

    # ── Retry si génération avortée (< 15000 chars = clairement trop court) ──
    MIN_GAME_SIZE = 15000
    if not code or len(code) < MIN_GAME_SIZE:
        phase3_log.warning(f"Génération trop courte ({len(code) if code else 0} chars) — retry complet")
        code = _call(prompt, system_instruction, max_tokens_generation)
        code = _clean_html(code)

    # ── Détection de troncature ──
    code = _ensure_complete(code, system_instruction, max_tokens_generation)

    phase3_log.agent_done("Créateur", f"{len(code)} caractères générés")
    return code


def _clean_html(code: str) -> str:
    """Nettoie le code HTML si le modèle l'a encapsulé dans des backticks."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        # Retire la première ligne (```html ou ```)
        lines = lines[1:]
        # Retire la dernière ligne si c'est ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)
    code = code.strip()

    # Supprimer les data:URI géants (polices/images embarquées) qui ne laissent pas de place au JS
    import re as _re
    data_uri_count = len(_re.findall(r'data:[^;]+;base64,[A-Za-z0-9+/=]{200,}', code))
    if data_uri_count:
        code = _re.sub(r"url\(['\"]?data:[^;]+;base64,[A-Za-z0-9+/=]+['\"]?\)", "url('')", code)
        code = _re.sub(r'src="data:[^;]+;base64,[A-Za-z0-9+/=]+"', 'src=""', code)
        phase3_log.warning(f"data:URI embarqués supprimés ({data_uri_count}) — consommaient le budget tokens")

    return code


def _is_js_truncated(code: str) -> bool:
    """
    Détecte si le JS interne est tronqué même quand le HTML se ferme correctement.
    Extrait le JS et vérifie les déséquilibres d'accolades / chaînes ouvertes.
    """
    import re
    scripts = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', code, re.DOTALL | re.IGNORECASE)
    if not scripts:
        return False
    js = "\n".join(scripts)
    # Déséquilibre d'accolades > 2 = troncature probable
    open_b  = js.count("{")
    close_b = js.count("}")
    if open_b - close_b > 2:
        return True
    # Déséquilibre de parenthèses > 3
    if js.count("(") - js.count(")") > 3:
        return True
    # Chaîne de caractères ouverte en fin de script (dernier ' ou " non fermé)
    tail = js[-200:].replace("\\'", "").replace('\\"', "")
    in_single = tail.count("'") % 2 == 1
    in_double = tail.count('"') % 2 == 1
    if in_single or in_double:
        return True
    return False


def _ensure_complete(code: str, system_instruction: str, max_tokens: int) -> str:
    """
    Détecte et répare le code tronqué — y compris quand </html> est présent
    mais que le JS interne est incomplet.
    """
    code_clean = code.strip()
    ends_with_html = code_clean.endswith("</html>")
    js_truncated   = _is_js_truncated(code_clean)

    if ends_with_html and not js_truncated:
        return code  # tout va bien

    reason = "JS interne tronqué (</html> présent mais accolades déséquilibrées)" if ends_with_html else "code coupé avant </html>"
    phase3_log.warning(f"Troncature détectée ({len(code)} chars) — {reason} — tentative de complétion")

    # Pour JS interne tronqué : extraire jusqu'à </script> et travailler sur le JS seul
    if ends_with_html and js_truncated:
        import re as _re
        # Trouver la position du dernier </script> et prendre ce qui précède
        match = list(_re.finditer(r'</script>', code, _re.IGNORECASE))
        if match:
            cut_pos = match[-1].start()
            js_part = code[:cut_pos]
            html_tail = code[cut_pos:]
            tail = js_part[-3000:] if len(js_part) > 3000 else js_part
        else:
            tail = code[-3000:] if len(code) > 3000 else code
            html_tail = ""
    else:
        tail = code[-3000:] if len(code) > 3000 else code
        html_tail = ""

    completion_prompt = f"""Ce code JavaScript de jeu HTML5 est INCOMPLET — tronqué au milieu d'une fonction.
Ta SEULE tâche : le compléter exactement là où il s'est arrêté.

RÈGLES :
- Commence IMMÉDIATEMENT là où le code s'arrête (zéro texte avant)
- Ferme toutes les accolades/parenthèses ouvertes
- Si une fonction est incomplète, termine-la de façon minimale fonctionnelle
- N'ajoute PAS de nouvelles features
- Si tu dois fermer DOMContentLoaded, termine par : }});

DERNIERS 3000 CHARS DU CODE TRONQUÉ :
{tail}

Continue depuis l'endroit exact où ça s'est arrêté :"""

    try:
        continuation = _call(completion_prompt, system_instruction, 16000)
        continuation = continuation.strip()
        if continuation.startswith("```"):
            lines = continuation.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            continuation = "\n".join(lines).strip()

        if continuation and not continuation.strip().startswith("<!DOCTYPE"):
            if ends_with_html and js_truncated:
                # Reconstruire : JS original tronqué + continuation + reste HTML
                completed = (code[:code.rfind(html_tail)] if html_tail and html_tail in code else code)
                completed = completed + "\n" + continuation + "\n" + html_tail
            else:
                completed = code + "\n" + continuation
            if "</html>" in completed and not _is_js_truncated(completed):
                phase3_log.warning(f"Code complété avec succès (+{len(continuation)} chars)")
                return completed
    except Exception as e:
        phase3_log.warning(f"Échec complétion : {e}")

    # Dernier recours : fermer les balises manuellement
    import re as _re
    scripts = _re.findall(r'<script(?:\s[^>]*)?>(.+?)(?:</script>|$)', code, _re.DOTALL | _re.IGNORECASE)
    js = "\n".join(scripts)
    open_brackets = max(0, js.count("{") - js.count("}"))
    close_needed = "}" * open_brackets
    has_domready = "DOMContentLoaded" in code
    dom_close = "\n});" if has_domready else ""
    phase3_log.warning(f"Fermeture minimale : {open_brackets} accolades JS ouvertes")
    if ends_with_html and js_truncated:
        # Insérer la fermeture avant </script>
        fixed = _re.sub(r'(</script>)', close_needed + dom_close + r'\1', code, count=1, flags=re.IGNORECASE)
        return fixed
    return code + "\n" + close_needed + dom_close + "\n</script>\n</body>\n</html>"


def _build_2d_requirements(rendu: dict, states: list) -> str:
    return f"""STRUCTURE :
1. Un seul fichier HTML complet et autonome (tout inline, aucune dépendance externe)
2. Le body HTML DOIT contenir : <canvas id="gameCanvas"></canvas>  ← élément HTML obligatoire !
3. TOUT le code JS dans document.addEventListener('DOMContentLoaded', function() {{ ... }});
4. Canvas récupéré APRÈS DOMContentLoaded : const canvas = document.getElementById('gameCanvas');
5. Canvas responsive : canvas.width = window.innerWidth; canvas.height = window.innerHeight;
6. Machine à états : {', '.join(states)}

GAME LOOP :
7. requestAnimationFrame avec delta time : const dt = Math.min((ts - last) / 1000, 0.05);
8. La boucle doit démarrer IMMÉDIATEMENT au chargement (pas seulement au clic)
9. update(dt) sépare la logique de draw() — pas de logique dans draw()

GAMEPLAY :
10. Détection de collisions AABB fonctionnelle (rect vs rect, ou distance pour cercles)
11. Score + HP visible en temps réel (ctx.fillText), HUD toujours lisible
12. Au moins 3 types d'entités visuellement distincts (taille, couleur, comportement différents)
13. Progression de difficulté visible (vitesse spawn, HP ennemis, variété types)
14. Game over + restart COMPLET sans rechargement (resetGame() remet tout à zéro)
15. Meilleur score : localStorage.setItem('hs_game', JSON.stringify({{score, date}}));

GAME FEEL — OBLIGATOIRE (chaque impact doit se ressentir) :
16. Screen shake sur chaque impact : shakeX/shakeY décalés aléatoirement dans draw()
17. Flash rouge écran quand joueur touché : ctx.fillStyle='rgba(220,0,0,0.28)' overlay temporaire
18. Flash blanc sur entité touchée : e.flashTimer = 0.08 → dessiner en '#FFF' pendant ce temps
19. Particules colorées sur chaque mort d'ennemi : spawnParticles(e.x, e.y, e.color, 12)
20. Floating text sur chaque dégât et collecte : spawnFloatingText(x, y, texte, couleur, taille)
21. Animations fluides via dt — JAMAIS de valeurs fixes par frame

VARIÉTÉ ENNEMIS — OBLIGATOIRE (3 types minimum) :
22. Type 1 GRUNT (rouge) : fonce vers le joueur, vitesse modérée, HP faible
23. Type 2 TANK (violet) : lent, HP élevé, résistant, grande taille
24. Type 3 RANGED (orange/jaune) : reste à distance, tire, recule si trop proche
25. Chaque type : scoreValue et xpValue différents, introduits progressivement dans le temps

POWER-UPS — OBLIGATOIRE pour jeux d'action :
26. spawnPowerup(x, y) avec 18% de chance sur mort d'ennemi
27. 3 types : health (vert), speed (bleu), damage (rouge) — oscillation visuelle (bobbing)
28. Floating text coloré à la collecte + triggerShake(3, 0.08)
29. Buffs temporaires avec timer visible dans HUD bas-gauche

INPUTS :
30. Contrôles clavier : flèches ET WASD (les deux)
31. Objet keys {{}} avec noms cohérents partout (déclaration = handlers = update)
32. Pour vider un tableau : arr.length = 0 — JAMAIS arr.clear()
33. Interactions environnementales : keys.e ou keys.e_prev si leviers/coffres présents"""


def _build_3d_requirements(tech_specs: dict = None) -> str:
    camera_type = (tech_specs or {}).get("camera_type", "tps")
    is_fps = "fps" in str(camera_type).lower()
    camera_spec = (
        "FPS : PerspectiveCamera(75), pointer lock sur click, rotation YXZ (pitch/yaw)"
        if is_fps else
        "TPS/fixe : camera suit le joueur avec lerp 0.08, lookAt(player.mesh.position)"
    )
    return f"""STRUCTURE :
1. Un seul fichier HTML complet et autonome (tout inline)
2. Charger Three.js r160 via CDN : <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
3. TOUT le code Three.js dans document.addEventListener('DOMContentLoaded', function() {{ ... }})
4. WebGLRenderer plein écran responsive — document.body.appendChild(renderer.domElement)
5. window.addEventListener('resize', ...) pour adapter camera.aspect et renderer.setSize

RENDU & SCÈNE :
6. scene.background = new THREE.Color(0x...) — obligatoire (sinon fond transparent)
7. AmbientLight(0xffffff, 0.45) + DirectionalLight(0xffffff, 0.9) — obligatoire (sinon tout noir)
8. renderer.shadowMap.enabled = true; dirLight.castShadow = true; mesh.castShadow = true
9. Au moins 3 géométries Three.js distinctes (BoxGeometry, SphereGeometry, CylinderGeometry...)
10. MeshPhongMaterial ou MeshStandardMaterial (pas MeshBasicMaterial — trop plat)

CAMÉRA :
11. {camera_spec}

GAME LOOP :
12. THREE.Clock pour le delta time : const dt = Math.min(clock.getDelta(), 0.05)
13. La boucle gameLoop() DOIT être lancée immédiatement dans DOMContentLoaded (gameLoop() en bas)
14. update(dt) séparé de renderer.render(scene, camera)

GAMEPLAY 3D :
15. Collision : THREE.Box3.setFromObject(mesh) + box1.intersectsBox(box2) pour chaque paire
16. Entités = objet {{ mesh, hp, speed, active, box: new THREE.Box3() }}
17. Suppression : scene.remove(entity.mesh) AVANT de retirer du tableau
18. Restart : scene.remove() pour chaque mesh, arrays.length = 0, reset variables
19. Particules : THREE.Points avec BufferGeometry (pattern du SYSTEM)

GAME FEEL 3D — OBLIGATOIRE :
20. Screen shake caméra : shakeOffset THREE.Vector3 appliqué APRÈS le suivi joueur dans animate()
21. Flash mesh ennemi touché : material.color.set(0xFFFFFF) pendant 80ms, puis restaurer
22. Vignette rouge HTML sur hit joueur : div fixed radial-gradient rouge, opacity 0→1→0
23. Hitstop sur coups critiques : skipUpdate pendant 50-120ms
24. Explosion de particules sur mort ennemi : createExplosion(pos, color, 15-25 points)
25. Power-ups 3D : sphères flottantes colorées avec bobbing (18% drop sur mort ennemi)

HUD & UI :
26. HUD = divs HTML fixed par-dessus le canvas (JAMAIS canvas 2D en mode Three.js)
27. Menu overlay HTML + écran game over overlay HTML avec boutons
28. Meilleur score : localStorage.getItem/setItem('highscore3d')
29. Buffs actifs affichés dans le HUD (vitesse, dégâts, bouclier avec timer)

INPUTS :
30. WASD + Flèches pour le mouvement
31. {"Pointer lock sur clic + mousemove pour la visée FPS" if is_fps else "Clics souris pour les actions"}
32. Progression de difficulté : vitesse spawn augmente avec le score ou le temps"""


def _build_gdd_from_genre_profile(gp) -> dict:
    """Reconstruit un GDD minimal mais utilisable depuis le GenreProfile quand le Game Designer a échoué."""
    return {
        "titre": f"{gp.genre_principal.title()} Game",
        "tagline": gp.boucle_core[:80] if gp.boucle_core else "Action intense",
        "concept": gp.prompt_enrichi[:400] if gp.prompt_enrichi else gp.prompt_utilisateur_original,
        "core_loop": {"description": gp.boucle_core, "etapes": [], "duree_session": "5-10 min"},
        "personnage_ou_entite": {"description": "Le joueur", "capacites": gp.mecaniques_obligatoires[:3], "feedback_visuel": "Animations réactives"},
        "systemes_principaux": [
            {"nom": m, "description": m, "impact_gameplay": "Core mechanic"}
            for m in gp.mecaniques_obligatoires[:5]
        ],
        "ennemis_ou_obstacles": [],
        "evenements_aleatoires": [],
        "economie_du_jeu": {"ressources": ["score"], "recompenses": ["points"], "consequences_echec": "game over"},
        "rejouabilite": {"elements": ["high score", "progression"], "meta_progression": "Score croissant"},
        "ambiance": {"description_visuelle": gp.style_visuel, "palette_couleurs": gp.palette_recommandee, "style_artistique": gp.style_visuel, "atmosphere": gp.ton},
    }


@with_fallback("""<!DOCTYPE html>
<html><head><title>Erreur</title></head>
<body><p>Erreur lors de la génération du jeu.</p></body></html>""")
def _call(prompt: str, system_instruction: str = SYSTEM_2D, max_tokens: int = 16000) -> str:
    return call_gemini(prompt, temperature=0.3, system_instruction=system_instruction, max_tokens=max_tokens)


# ─────────────────────────────────────────────
# GÉNÉRATION MODULAIRE
# ─────────────────────────────────────────────

SYSTEM_MODULE = """Tu es un développeur senior en jeux HTML5 Canvas 2D. Tu génères un module JavaScript pur.

RÈGLES ABSOLUES pour ce module :
- Utilise UNIQUEMENT les variables globales listées — ne les redéclare jamais avec const/let/var
- Pour vider un tableau : arr.length = 0 (JAMAIS arr.clear())
- Noms d'inputs cohérents : si keys.left est déclaré globalement, utilise keys.left partout
- Tout objet auxiliaire utilisé (particles, audio, etc.) doit être déclaré dans LE MODULE lui-même s'il n'est pas dans les globales
- N'écris JAMAIS 'br' seul — c'est break; en JS
- N'utilise JAMAIS d'entités HTML (&amp; &lt;) dans le JS
- Le module doit fonctionner sans erreur avec le reste du jeu

Tu produis UNIQUEMENT du code JavaScript, sans balises HTML, sans explication, sans backticks."""

SYSTEM_MODULE_3D = """Tu es un développeur expert en jeux 3D web avec Three.js r160. Tu génères du code
JavaScript pour un module spécifique d'un jeu Three.js. Toutes les variables THREE.* sont
disponibles globalement (Three.js chargé via CDN). Tu utilises les variables globales déclarées.

RÈGLES ABSOLUES — STRUCTURE DU MODULE :
1. NE JAMAIS wrapper le code dans une IIFE : INTERDIT let core = (() => { ... })()
2. NE JAMAIS créer des namespace objects : INTERDIT const core = { init, gameLoop }
3. Toutes les fonctions DOIVENT être déclarées au niveau global : function init() { ... }
4. Les variables globales partagées (scene, camera, renderer, player, etc.) sont déjà déclarées dans les globals — NE PAS les redéclarer avec let/const/var au niveau module
5. Module 'core' : function init() DOIT appeler ui.initUI() si le module 'ui' existe, AVANT tout setState()
6. Si tu déclares une variable locale dans une fonction, utilise let/const — JAMAIS let au niveau global si déjà dans globals
7. SYNTAXE INTERDITE — `let X.Y = value;` est une SyntaxError en JavaScript : INTERDIT let GameName.gameState = 'loading'; — CORRECT : gameState = 'loading'; (variable globale directe)

STRUCTURE CORRECTE — EXEMPLE COMPLET (module 'core') :
// ✅ Global variables — declared with var at top level (NOT let/const)
var gameState = 'menu';
var score = 0;

// ✅ Functions declared globally — NOT inside IIFE or object
function init() {
  // 1. Three.js setup first
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  // 2. UI init BEFORE setState — prevents "Cannot read properties of undefined"
  if (typeof ui !== 'undefined' && typeof ui.initUI === 'function') ui.initUI();
  // 3. State change AFTER UI is ready
  setState('menu');
  requestAnimationFrame(gameLoop);
}

function gameLoop(timestamp) {
  var dt = Math.min(clock.getDelta(), 0.05);
  if (gameState === 'playing') {
    if (typeof updateEntities === 'function') updateEntities(dt);
  }
  renderer.render(scene, camera);
  requestAnimationFrame(gameLoop);
}

function setState(s) { gameState = s; }

Tu produis UNIQUEMENT du code JavaScript, sans balises HTML, sans explication, sans backticks."""


def run_modulaire(context: ConceptionContext, architecture: ModuleArchitecture, patterns_reussis: list = None, tendances: str = "", erreurs_passees: list = None, game_logics: str = "") -> GeneratedModules:
    """
    Génère le jeu module par module.
    Stratégie séquentielle-hybride :
    1. Le module 'core' est généré en premier (synchrone)
    2. Son code est injecté comme contexte pour les autres modules
    3. Les modules restants sont générés en parallèle
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from logger import get_thread_event_queue, set_thread_event_queue

    phase3_log.agent_start("Créateur Modulaire", f"Génération de {len(architecture.modules)} modules (core-first)")

    est_3d = architecture.technologie == "threejs"
    system = SYSTEM_MODULE_3D if est_3d else SYSTEM_MODULE
    gp = context.genre_profile
    gdd = context.gdd
    ctx_global = _build_module_context(context, architecture, tendances, erreurs_passees, game_logics)
    current_queue = get_thread_event_queue()

    result = GeneratedModules(architecture=architecture)
    all_modules = architecture.modules or []

    # ─── Étape 1 : Générer le module 'core' en premier ───
    core_module = next((m for m in all_modules if m.get("nom") == "core"), None)
    other_modules = [m for m in all_modules if m.get("nom") != "core"]
    core_code_snippet = ""

    if core_module:
        phase3_log.info("  → Module 'core' en premier (séquentiel)...")
        core_code = _generate_module(core_module, ctx_global, architecture, gp, gdd, system)
        nom = core_module.get("nom", "core")
        if core_code and len(core_code) > 100:
            result.modules[nom] = core_code
            result.modules_valides.append(nom)
            core_code_snippet = core_code[:4000]
            phase3_log.info(f"  ✓ Module 'core' : {len(core_code)} chars")
        else:
            result.modules_echoues.append(nom)
            result.modules[nom] = _minimal_module_fallback(nom, core_module, est_3d)
            phase3_log.warning("  ✗ Module 'core' échoué — fallback minimal (autres modules sans contexte core)")

    # ─── Étape 2 : Injecter le code core dans le contexte des autres modules ───
    if core_code_snippet:
        ctx_with_core = (
            ctx_global
            + f"\n\n═══ CODE DU MODULE CORE (déjà implémenté — utilise ses fonctions et variables) ═══\n"
            + f"```javascript\n{core_code_snippet}\n```\n"
            + "Les fonctions et variables déclarées dans le core sont disponibles globalement.\n"
        )
    else:
        ctx_with_core = ctx_global

    # ─── Étape 3 : Autres modules en parallèle avec contexte enrichi ───
    def generate_one(module_def):
        if current_queue:
            set_thread_event_queue(current_queue)
        nom = module_def.get("nom", "")
        code = _generate_module(module_def, ctx_with_core, architecture, gp, gdd, system)
        return nom, code

    if other_modules:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(generate_one, m): m for m in other_modules if m.get("nom")}
            for future in as_completed(futures):
                try:
                    nom, code = future.result()
                    if not nom:
                        continue
                    if code and len(code) > 100:
                        result.modules[nom] = code
                        result.modules_valides.append(nom)
                        phase3_log.info(f"  ✓ Module '{nom}' : {len(code)} chars")
                    else:
                        result.modules_echoues.append(nom)
                        result.modules[nom] = _minimal_module_fallback(nom, futures[future], est_3d)
                        phase3_log.warning(f"  ✗ Module '{nom}' échoué — fallback minimal")
                except Exception as e:
                    phase3_log.warning(f"  ✗ Génération module échouée : {e}")

    phase3_log.agent_done(
        "Créateur Modulaire",
        f"{len(result.modules_valides)}/{len(architecture.modules)} modules générés"
    )
    return result


def _generate_module(
    module_def: dict,
    ctx_global: str,
    architecture: ModuleArchitecture,
    gp,
    gdd: dict,
    system: str,
) -> str:
    nom = module_def["nom"]
    description = module_def.get("description", "")
    fonctions = module_def.get("fonctions_exposees", [])
    vars_requises = module_def.get("variables_requises", [])
    vars_ecrites = module_def.get("variables_ecrites", [])
    taille_max = module_def.get("taille_max", 7000)

    # Variables disponibles dans ce module
    vars_disponibles = list(set(architecture.variables_globales + vars_requises))

    prompt = f"""Génère le module JavaScript "{nom}" pour le jeu "{gdd.get('titre', 'Arcade Game')}".

{ctx_global}

═══ MODULE À GÉNÉRER : {nom} ═══
DESCRIPTION : {description}

FONCTIONS À EXPOSER (ces fonctions DOIVENT exister dans ton code) :
{json.dumps(fonctions, ensure_ascii=False)}

VARIABLES GLOBALES DISPONIBLES (déjà déclarées, ne pas redéclarer avec let/var/const) :
{json.dumps(vars_disponibles, ensure_ascii=False)}

VARIABLES QUE CE MODULE ÉCRIT :
{json.dumps(vars_ecrites, ensure_ascii=False)}

CONTRAINTES :
- Code JavaScript pur, sans balises HTML
- Maximum {taille_max} caractères
- Ne déclare PAS les variables globales (elles sont déjà déclarées)
- Expose bien toutes les fonctions listées dans FONCTIONS À EXPOSER
- Code fonctionnel et complet pour ce module
- Commentaires courts pour clarifier la logique
- Dans chaque boucle for, déclare la variable d'élément en première ligne : `const e = enemies[i];`

Génère uniquement le code JavaScript du module, rien d'autre."""

    # Inject RAG anti-patterns as a "bugs to avoid" hint (3D modules only)
    est_3d = architecture.technologie == "threejs"
    if est_3d:
        try:
            query = f"3D module javascript common bugs {nom} three.js"
            _hits = rag.search_bug_fixes(query, n=3)
            if _hits:
                _anti = "\n".join(
                    f"  • {h.get('symptom','')}: {h.get('explanation','')} — "
                    f"BUGGY: `{h.get('buggy_pattern','')[:80]}` → FIXED: `{h.get('fix_pattern','')[:80]}`"
                    for h in _hits
                )
                prompt = prompt.replace(
                    "Génère uniquement le code JavaScript du module, rien d'autre.",
                    f"KNOWN BUG PATTERNS TO AVOID (from fix database):\n{_anti}\n\nGénère uniquement le code JavaScript du module, rien d'autre."
                )
        except Exception:
            pass

    return _call_module(prompt, system)


def _build_module_context(context: ConceptionContext, architecture: ModuleArchitecture, tendances: str = "", erreurs_passees: list = None, game_logics: str = "") -> str:
    """Contexte partagé injecté dans chaque prompt de module."""
    gp = context.genre_profile
    gdd = context.gdd
    tech = context.tech_specs
    est_3d = architecture.technologie == "threejs"

    states = tech.get("state_machine", {}).get("etats", ["menu", "playing", "gameover"])
    physique = tech.get("physique", {})

    tendances_section = f"\nTENDANCES DU GENRE (s'en inspirer) :\n{tendances[:1500]}\n" if tendances else ""
    erreurs_section = ""
    if erreurs_passees:
        erreurs_section = "\nERREURS À ÉVITER (des générations précédentes) :\n" + "\n".join(f"- {e}" for e in erreurs_passees[:5]) + "\n"
    game_logics_section = f"\nGAME LOGICS (mécaniques et interactions à implémenter dans ce module) :\n{game_logics[:5000]}\n" if game_logics else ""

    return f"""═══ CONTEXTE DU JEU ═══
Genre : {gp.genre_principal} / {gp.sous_genre}
Titre : {gdd.get('titre', 'Arcade Game')}
Core loop : {gp.boucle_core}
Ton : {gp.ton}
Technologie : {"Three.js (3D)" if est_3d else "Canvas 2D"}
États : {', '.join(states)}
Gravité : {physique.get('gravite', False)}
Style visuel : {gp.style_visuel}
Palette : {gp.palette_recommandee}
Mécaniques : {', '.join(gp.mecaniques_obligatoires[:5])}
{tendances_section}{erreurs_section}{game_logics_section}
VARIABLES GLOBALES DU JEU :
{json.dumps(architecture.variables_globales, ensure_ascii=False)}

TOUS LES MODULES DU JEU :
{json.dumps([m.get('nom') + ' : ' + m.get('description', '') for m in architecture.modules], ensure_ascii=False)}"""


def _minimal_module_fallback(nom: str, module_def: dict, est_3d: bool) -> str:
    """Code minimal pour un module qui a échoué à la génération."""
    fonctions = module_def.get("fonctions_exposees", [])
    lines = [f"// Module {nom} — fallback minimal"]
    for fn in fonctions:
        lines.append(f"function {fn}() {{")
        lines.append(f"  // TODO: implémenter {fn}")
        lines.append("}")
    return "\n".join(lines)


@with_fallback("")
def _call_module(prompt: str, system: str) -> str:
    return call_gemini(prompt, temperature=0.2, system_instruction=system, max_tokens=24000)


# ─────────────────────────────────────────────
# GÉNÉRATION EN 2 PASSES — jeux 2D complexes
# ─────────────────────────────────────────────

SYSTEM_SKELETON = """Tu génères un SQUELETTE HTML5 Canvas 2D fonctionnel minimal.

OBJECTIF : Code qui tourne sans erreur dès le premier chargement.
Ce squelette sera complété en passe 2 — ne génère PAS les systèmes complets maintenant.

RÈGLE 1 — UNE DÉCLARATION PAR LIGNE, SANS EXCEPTION :
  let score = 0;
  let lives = 3;
  let gameState = 'menu';
  ✗ INTERDIT : let score = 0, lives = 3;   ← zéro multi-declarator

RÈGLE 2 — TOUTES LES FONCTIONS APPELÉES DOIVENT ÊTRE DÉFINIES (stubs vides OK) :
  function generateDungeon() {}
  function spawnEnemy(type, x, y) {}
  function handleCombat(player, enemy) {}

RÈGLE 3 — STRUCTURE OBLIGATOIRE :
  <variables globales avant DOMContentLoaded>
  document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('gameCanvas');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const ctx = canvas.getContext('2d');
    // event listeners
    initGame();
    requestAnimationFrame(gameLoop);
  });

RÈGLE 4 — draw() commence TOUJOURS par ctx.fillRect ou ctx.clearRect (fond avant tout)
RÈGLE 5 — delta time correct : const dt = Math.min((ts - lastTime) / 1000, 0.05);
RÈGLE 6 — Déclare TOUTES les variables dont le jeu final aura besoin (même inutilisées ici)
RÈGLE 7 — ANTICIPE la passe 2 : chaque variable globale que tes fonctions ou systèmes futurs utiliseront
  DOIT être déclarée maintenant. Exemples : boss=null, sfx={}, bullets=[], enemies=[],
  currentDifficultyTier=0, classId=null, critChance=0. Si tu omets une déclaration ici,
  la passe 2 produira une ReferenceError = écran noir."""


def _generate_skeleton(context: ConceptionContext, game_logics: str = "") -> str:
    """
    Passe 1 de la génération en 2 passes.
    Génère un squelette HTML5 fonctionnel minimal avec toutes les déclarations globales.
    Le squelette contient des stubs pour les systèmes complexes qui seront implémentés en passe 2.
    """
    gp = context.genre_profile
    gdd = context.gdd
    tech = context.tech_specs

    titre = gdd.get('titre', 'Arcade Game')
    genre = gp.genre_principal
    mecaniques = ', '.join(gp.mecaniques_obligatoires[:6])
    states = tech.get('state_machine', {}).get('etats', ['menu', 'playing', 'gameover'])

    # Architecture plan pour obtenir les noms de variables exacts
    arch_plan = _generate_architecture_plan(gp, gdd, tech, game_logics)
    arch_info = f"\nPLAN D'ARCHITECTURE (utiliser ces noms exacts) :\n{arch_plan}\n" if arch_plan else ""

    # Systèmes et contenu du GDD pour identifier les variables à pré-déclarer
    systemes = gdd.get('systemes_principaux', gdd.get('systemes_mecaniques', []))
    classes = gdd.get('classes_personnages', gdd.get('classes', []))
    contenu = gdd.get('contenu_detaille', {})

    systemes_str = json.dumps(systemes[:4], ensure_ascii=False) if systemes else "(voir mécaniques)"
    classes_str = json.dumps(classes[:3], ensure_ascii=False) if classes else ""
    ennemis_str = json.dumps(contenu.get('ennemis_stats', [])[:3], ensure_ascii=False) if contenu.get('ennemis_stats') else ""

    prompt = f"""Génère le SQUELETTE HTML5 du jeu "{titre}" (genre: {genre}).

Ce squelette sera complété en passe 2. Objectif unique : code minimal qui TOURNE SANS ERREUR.
{arch_info}
MÉCANIQUES (pour savoir quelles variables pré-déclarer) : {mecaniques}
SYSTÈMES À VENIR EN PASSE 2 : {systemes_str}
CLASSES DE PERSONNAGES : {classes_str}
ENNEMIS : {ennemis_str}
ÉTATS DU JEU : {', '.join(states)}
STYLE VISUEL : {gp.style_visuel}
PALETTE : {gp.palette_recommandee}

INSTRUCTIONS PASSE 1 :

① DÉCLARER TOUTES LES VARIABLES GLOBALES (une par ligne, avant DOMContentLoaded) :
   Arrays  : enemies, rooms, items, particles, floatingTexts, bullets, etc.
   Compteurs : score, lives, gold, xp, currentFloor, combo, etc.
   Flags   : gameState, bossActive, gameOver, isPaused, etc.
   Refs    : player, currentRoom, selectedClass, boss, etc.
   Consts  : PALETTE, PLAYER_SPEED, TILE_SIZE, GRAVITY, etc.

② IMPLÉMENTER EN MINIMAL (juste ce qui fait tourner le jeu) :
   initGame()  → réinitialise les variables, crée un player basique avec toutes ses propriétés
   update(dt)  → déplace le player selon les inputs (WASD/flèches)
   draw()      → fond + player seulement (les autres systèmes viennent en passe 2)
   Input       → clavier + souris complets (keys, mouse objects)

③ STUBS VIDES pour toutes les fonctions du jeu final :
   function generateDungeon() {{}}
   function spawnEnemy(type, x, y) {{}}
   function handleCombat(attacker, target) {{}}
   function updateHUD() {{}}
   (une stub par fonctionnalité des systèmes listés ci-dessus)

④ GAME LOOP CORRECT :
   let lastTime = 0;
   function gameLoop(ts) {{
     const dt = Math.min((ts - lastTime) / 1000, 0.05);
     lastTime = ts;
     update(dt);
     draw();
     requestAnimationFrame(gameLoop);
   }}

Génère maintenant le squelette HTML complet :"""

    phase3_log.info(f"[Créateur 2-passes] Squelette : génération ({titre})")
    code = _call(prompt, SYSTEM_SKELETON, max_tokens=28000)
    return _clean_html(code)


def _extract_declared_globals(html: str) -> str:
    """
    Extrait la liste des identifiants déclarés (let/const/var) dans le code HTML.
    Utilisé en passe 2 pour interdire les redéclarations.
    """
    script_m = _re.search(r'<script[^>]*>(.*?)</script>', html, _re.DOTALL | _re.IGNORECASE)
    if not script_m:
        return ""
    script = script_m.group(1)
    declared = _re.findall(r'\b(?:const|let|var)\s+(\w+)', script)
    return ', '.join(sorted(set(declared)))


def _extend_with_systems(
    skeleton: str,
    context: ConceptionContext,
    patterns_reussis: list = None,
    erreurs_passees: list = None,
    game_logics: str = ""
) -> str:
    """
    Passe 2 de la génération en 2 passes.
    Étend le squelette fonctionnel avec tous les systèmes de jeu complets.
    Le modèle reçoit le squelette comme contexte garanti et ne doit que l'étendre.
    """
    gp = context.genre_profile
    gdd = context.gdd
    levels = context.level_design

    titre = gdd.get('titre', 'Arcade Game')
    declared_str = _extract_declared_globals(skeleton)

    # Contenu GDD
    systemes = gdd.get('systemes_principaux', gdd.get('systemes_mecaniques', []))
    contenu = gdd.get('contenu_detaille', {})
    formules = gdd.get('formules_cles', {})
    interactions = gdd.get('interactions_systemes', [])
    paliers = levels.get('paliers_difficulte', [])

    contenu_str = ""
    if contenu:
        if contenu.get('ennemis_stats'):
            contenu_str += f"\nENNEMIS : {json.dumps(contenu['ennemis_stats'], ensure_ascii=False)}"
        if contenu.get('upgrades_disponibles'):
            contenu_str += f"\nUPGRADES : {json.dumps(contenu['upgrades_disponibles'], ensure_ascii=False)}"
        if contenu.get('boss'):
            contenu_str += f"\nBOSS : {json.dumps(contenu['boss'], ensure_ascii=False)}"

    patterns_info = ""
    if patterns_reussis:
        patterns_info = "\nPATTERNS RÉUSSIS :\n" + "".join(
            f"- {p.get('genre')}: {p.get('boucle_core', '')} (score {p.get('score',0):.1f})\n"
            for p in patterns_reussis[:3]
        )

    erreurs_info = ""
    if erreurs_passees:
        erreurs_info = "\nERREURS À ÉVITER :\n" + "\n".join(f"- {e}" for e in erreurs_passees[:5])

    game_logics_info = f"\nGAME LOGICS :\n{game_logics[:4000]}" if game_logics else ""

    # Tronquer le squelette si trop long pour le contexte (garder les 35k premiers chars)
    skeleton_excerpt = skeleton[:35000]
    if len(skeleton) > 35000:
        skeleton_excerpt += "\n// ... (squelette tronqué pour le contexte)"

    prompt = f"""Tu reçois le squelette fonctionnel du jeu "{titre}".
Étends-le avec TOUS les systèmes de jeu complets et retourne le HTML complet modifié.

{'═' * 60}
SQUELETTE (NE PAS MODIFIER LA STRUCTURE HTML, LE CANVAS SETUP, LE GAME LOOP)
{'═' * 60}
{skeleton_excerpt}
{'═' * 60}

VARIABLES DÉJÀ DÉCLARÉES — NE JAMAIS REDÉCLARER :
{declared_str}

SYSTÈMES À IMPLÉMENTER COMPLÈTEMENT :
{json.dumps(systemes, ensure_ascii=False) if systemes else '(mécaniques obligatoires du GDD)'}

FORMULES MATHÉMATIQUES (implémenter exactement) :
{json.dumps(formules, ensure_ascii=False) if formules else ''}

CONTENU DÉTAILLÉ (stats, types) :
{contenu_str}

PALIERS DE DIFFICULTÉ :
{json.dumps(paliers, ensure_ascii=False) if paliers else ''}

INTERACTIONS ENTRE SYSTÈMES :
{json.dumps(interactions[:4], ensure_ascii=False) if interactions else ''}
{patterns_info}{erreurs_info}{game_logics_info}

INSTRUCTIONS PASSE 2 :
① Remplace les fonctions stubs par leur implémentation COMPLÈTE et fonctionnelle
② Étends update(dt) et draw() avec tous les systèmes du GDD
③ Ajoute les nouvelles fonctions nécessaires après les existantes
④ NE JAMAIS redéclarer ces identifiants : {declared_str}
⑤ Conserve la structure HTML, le canvas setup et le game loop du squelette
⑥ Retourne le HTML COMPLET
⑦ CRITIQUE — NOUVEAUX GLOBALS : tout identifiant utilisé dans tes nouvelles fonctions ou dans update()/draw() et qui n'est PAS dans la liste "VARIABLES DÉJÀ DÉCLARÉES" DOIT être déclaré avec `let nomVar = valeurInitiale;` dans la zone GLOBALS du squelette (juste après les const/let existants, avant init()). Utiliser une variable sans la déclarer = ReferenceError = écran noir.

🔴 CONTRAT UTILISATEUR — le joueur a demandé : "{gp.prompt_utilisateur_original}"
Chaque élément de ce prompt (types d'entités, mécaniques, style visuel) DOIT être présent. Omettre = invalide.

Génère maintenant le jeu complet :"""

    # System prompt du genre (patterns qualité + règles canvas)
    system = _build_system_2d(gp)

    phase3_log.info(f"[Créateur 2-passes] Extension systèmes ({titre})")
    code = _call(prompt, system, max_tokens=55000)
    return _clean_html(code)


@with_fallback("")
def run_deux_passes(
    context: ConceptionContext,
    patterns_reussis: list = None,
    tendances: str = "",
    erreurs_passees: list = None,
    game_logics: str = ""
) -> str:
    """
    Génération en 2 passes pour les jeux 2D complexes (RPG, dungeon crawler, strategy, etc.).

    Passe 1 — Squelette : code minimal fonctionnel avec TOUTES les déclarations globales,
                          toutes les fonctions stubées, game loop correct.
    Passe 2 — Extension : ajout de tous les systèmes complets sur la base garantie du squelette.

    Avantages vs monolithique :
    - Passe 1 garantit que chaque variable est déclarée une seule fois
    - Passe 2 reçoit la liste exacte des déclarations → zéro redéclaration possible
    - Chaque passe est < 30k tokens → le modèle reste dans sa fenêtre optimale
    - Si passe 2 échoue → passe 1 est un jeu minimal mais jouable

    Fallback automatique vers génération monolithique si une passe produit < CODE_MIN.
    """
    from code_validator import validate_and_fix

    CODE_MIN = 3000
    titre = context.gdd.get('titre', '?')

    # ── PASSE 1 : Squelette ──────────────────────────────
    squelette = _generate_skeleton(context, game_logics)

    if not squelette or len(squelette) < CODE_MIN:
        phase3_log.warning(f"[2-passes] Squelette insuffisant ({len(squelette) if squelette else 0} chars) — fallback monolithique")
        return run(context, patterns_reussis, tendances, erreurs_passees, game_logics)

    # Correctifs non-LLM sur le squelette (redéclarations, stubs manquants, etc.)
    squelette, _, _ = validate_and_fix(squelette)
    phase3_log.info(f"[2-passes] Squelette validé : {len(squelette)} chars")

    # ── PASSE 2 : Extension ──────────────────────────────
    code_final = _extend_with_systems(
        squelette, context,
        patterns_reussis=patterns_reussis,
        erreurs_passees=erreurs_passees,
        game_logics=game_logics,
    )

    if not code_final or len(code_final) < len(squelette):
        phase3_log.warning(f"[2-passes] Extension insuffisante — retour squelette validé ({len(squelette)} chars)")
        return squelette

    phase3_log.agent_done(
        "Créateur 2-passes",
        f"{len(code_final)} chars générés "
        f"(squelette: {len(squelette)}, delta: +{len(code_final) - len(squelette)})"
    )
    return code_final

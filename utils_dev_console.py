"""
Dev Console — Overlay de modification en temps réel.
Injecté dans tous les jeux sauvegardés par agent_sauvegarde.py.

La console s'ouvre avec la touche ` (backtick) ou ² (clavier AZERTY).
Elle envoie le prompt à /api/game-patch → reçoit un snippet JS → eval() live.

Architecture d'accès aux variables du jeu :
  Les variables (hero, playerStats, gameState...) sont déclarées avec `let` à l'intérieur
  du DOMContentLoaded → invisibles depuis une IIFE externe.
  Solution : on injecte window.__devPatch = function(code){ eval(code); } DANS le
  DOMContentLoaded (via _inject_patch_bridge), puis la console appelle ce bridge.
"""

import re

# ─── Marqueur pour détecter si la console est déjà présente ──────────────────
CONSOLE_MARKER = "/* DEV_CONSOLE_INJECTED */"

# ─── Bridge injecté DANS le DOMContentLoaded pour accéder aux variables locales
_BRIDGE = "\n  // Dev console bridge — accès aux variables locales du jeu\n  window.__devPatch = function(code) { return eval(code); };\n"

# ─── Snippet HTML/CSS/JS à injecter avant </body> ────────────────────────────
_CONSOLE_CSS = """
<style id="dev-console-style">
#dev-console{display:none;position:fixed;bottom:0;left:0;right:0;background:rgba(0,0,0,.96);border-top:2px solid #00ff88;padding:10px 14px;z-index:99999;font-family:monospace;color:#00ff88;box-shadow:0 -4px 20px rgba(0,255,136,.15)}
#dev-console.open{display:flex;flex-direction:column;gap:5px}
#dev-console-title{font-size:11px;color:#555;letter-spacing:1px;display:flex;justify-content:space-between;align-items:center}
#dev-console-title span:first-child{color:#00ff88;font-size:12px;font-weight:bold}
#dev-console-ctx-bar{display:flex;gap:6px;align-items:center}
#dev-console-row{display:flex;gap:8px;align-items:flex-start}
#dev-console-input{flex:1;background:#0a0a0a;border:1px solid #00ff88;color:#00ff88;font-family:'Courier New',monospace;font-size:13px;padding:8px 10px;border-radius:4px;resize:vertical;min-height:38px;max-height:180px;line-height:1.4}
#dev-console-input::placeholder{color:#1a4a2a}
#dev-console-input:focus{outline:none;border-color:#00ffcc;box-shadow:0 0 8px rgba(0,255,204,.2)}
#dev-console-btns{display:flex;flex-direction:column;gap:5px;min-width:90px}
#dev-console-btn{background:linear-gradient(135deg,#00cc66,#00ff88);color:#000;border:none;font-family:monospace;font-size:12px;font-weight:900;padding:9px 14px;border-radius:4px;cursor:pointer;letter-spacing:.5px;transition:all .15s}
#dev-console-btn:hover{background:linear-gradient(135deg,#00ff88,#00ffcc);transform:translateY(-1px)}
#dev-console-btn:disabled{background:#222;color:#444;cursor:wait;transform:none}
#dev-console-undo{background:#1a1a1a;color:#888;border:1px solid #333;font-family:monospace;font-size:11px;padding:5px 10px;border-radius:4px;cursor:pointer;transition:all .15s}
#dev-console-undo:hover:not(:disabled){background:#2a2a2a;color:#fff;border-color:#555}
#dev-console-undo:disabled{opacity:.3;cursor:default}
#dev-console-ctx-btn{background:#0a1a0a;color:#555;border:1px solid #1a3a1a;font-size:10px;padding:3px 8px;border-radius:3px;cursor:pointer;font-family:monospace;transition:all .15s}
#dev-console-ctx-btn:hover{color:#00ff88;border-color:#00ff88;background:#0a2a0a}
#dev-console-ctx-btn.active{color:#00ff88;border-color:#00ff88;background:#051505}
#dev-console-status{font-size:11px;min-height:16px;padding:2px 0;transition:color .2s;line-height:1.5;max-height:60px;overflow-y:auto}
#dev-console-status.ok{color:#00ff88}
#dev-console-status.err{color:#ff4444}
#dev-console-status.pending{color:#ffaa00}
#dev-console-status.warn{color:#ffcc44}
#dev-console-ctx{display:none;background:#050f05;border:1px solid #0a2a0a;border-radius:4px;padding:8px 10px;font-size:10px;color:#668866;max-height:120px;overflow-y:auto;line-height:1.7;margin-top:2px}
#dev-console-ctx.open{display:block}
#dev-console-log{font-size:10px;color:#333;max-height:55px;overflow-y:auto;padding-top:3px;border-top:1px solid #111;display:none;line-height:1.6}
#dev-console-log.visible{display:block}
#dev-console-close{background:none;border:none;color:#333;font-size:16px;cursor:pointer;padding:0 3px;transition:color .15s}
#dev-console-close:hover{color:#ff4444}
#dev-console-hint{font-size:9px;color:#222;text-align:right;margin-top:1px}
#dev-console-code-wrap{display:none;margin-top:4px}
#dev-console-code-wrap.visible{display:block}
#dev-console-code-toggle{background:none;border:none;color:#1a4a2a;font-size:10px;font-family:monospace;cursor:pointer;padding:2px 0;letter-spacing:.5px;transition:color .15s}
#dev-console-code-toggle:hover{color:#00cc66}
#dev-console-code-pre{background:#050f05;border:1px solid #0a2a0a;border-radius:3px;padding:8px 10px;font-size:11px;color:#44aa44;font-family:'Courier New',monospace;white-space:pre-wrap;word-break:break-all;max-height:140px;overflow-y:auto;margin-top:3px;line-height:1.5}
</style>
"""

_CONSOLE_HTML = """
<div id="dev-console">
  <div id="dev-console-title">
    <span>&#9881; DEV CONSOLE</span>
    <div id="dev-console-ctx-bar">
      <button id="dev-console-ctx-btn" title="Afficher le contexte du jeu en temps réel">&#128269; ctx</button>
      <span style="color:#222;font-size:10px">[ ² / &#96; ]</span>
      <button id="dev-console-close" title="Fermer">&#10005;</button>
    </div>
  </div>
  <div id="dev-console-ctx"></div>
  <div id="dev-console-row">
    <textarea id="dev-console-input" placeholder="Décris la modification souhaitée... Ex: rends le joueur invincible, ajoute un type ennemi dragon avec 500 HP, double la vitesse de tir, ajoute une compétence de téléportation, modifie la génération de niveaux..."></textarea>
    <div id="dev-console-btns">
      <button id="dev-console-btn">&#9654; Appliquer</button>
      <button id="dev-console-undo" disabled title="Annuler le dernier patch">&#8617; Annuler</button>
    </div>
  </div>
  <div id="dev-console-status"></div>
  <div id="dev-console-code-wrap">
    <button id="dev-console-code-toggle">&#9654; voir le code généré</button>
    <pre id="dev-console-code-pre"></pre>
  </div>
  <div id="dev-console-log"></div>
  <div id="dev-console-hint">Shift+Entrée = nouvelle ligne &nbsp;|&nbsp; Entrée = envoyer &nbsp;|&nbsp; ↑↓ = historique</div>
</div>
"""

_CONSOLE_JS = """
<script id="dev-console-script">
/* DEV_CONSOLE_INJECTED */
(function(){
'use strict';
var FILENAME=window.location.pathname.split('/').pop();
var panel=document.getElementById('dev-console');
var input=document.getElementById('dev-console-input');
var btn=document.getElementById('dev-console-btn');
var undoBtn=document.getElementById('dev-console-undo');
var statusEl=document.getElementById('dev-console-status');
var closeBtn=document.getElementById('dev-console-close');
var ctxBtn=document.getElementById('dev-console-ctx-btn');
var ctxPanel=document.getElementById('dev-console-ctx');
var logPanel=document.getElementById('dev-console-log');
var codeWrap=document.getElementById('dev-console-code-wrap');
var codeToggle=document.getElementById('dev-console-code-toggle');
var codePre=document.getElementById('dev-console-code-pre');
if(!panel||!input||!btn||!statusEl)return;

// ── État interne ──
var _snapshots=[];
var _history=[];
var _histIdx=-1;
var _actionLog=[];
var MAX_UNDO=15;
var MAX_LOG=30;
var _lastCode='';

// ── Toggle code généré ──
if(codeToggle&&codeWrap&&codePre){
  codeToggle.addEventListener('click',function(){
    var isOpen=codePre.style.display==='block';
    codePre.style.display=isOpen?'none':'block';
    codeToggle.textContent=(isOpen?'▶ voir':'▼ masquer')+' le code généré';
  });
  codePre.style.display='none'; // fermé par défaut
}

function showGeneratedCode(code){
  if(!codeWrap||!codePre||!codeToggle)return;
  _lastCode=code||'';
  codePre.textContent=_lastCode;
  codeWrap.classList.add('visible');
  codePre.style.display='none'; // fermé par défaut, l'utilisateur ouvre s'il veut
  codeToggle.textContent='▶ voir le code généré ('+_lastCode.split('\\n').length+' lignes)';
}

function hideGeneratedCode(){
  if(!codeWrap)return;
  codeWrap.classList.remove('visible');
  _lastCode='';
}

// ── Utilitaires UI ──
closeBtn.addEventListener('click',function(){panel.classList.remove('open');input.blur();});

function setStatus(msg,cls){
  statusEl.textContent=msg;
  statusEl.className=cls||'';
}

function addLog(prompt,ok,note){
  var t=new Date().toLocaleTimeString('fr',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  var short=prompt.length>55?prompt.slice(0,55)+'…':prompt;
  _actionLog.unshift({t:t,short:short,ok:ok,note:note||''});
  if(_actionLog.length>MAX_LOG)_actionLog.pop();
  renderLog();
}

function renderLog(){
  if(!_actionLog.length){logPanel.classList.remove('visible');return;}
  logPanel.classList.add('visible');
  logPanel.innerHTML=_actionLog.map(function(e){
    return '<span style="color:#333">'+e.t+'</span> '+
      '<span style="color:'+(e.ok?'#1a6a1a':'#6a1a1a')+'">&#8226;</span> '+
      '<span style="color:'+(e.ok?'#447744':'#774444')+'">'+e.short+'</span>'+
      (e.note?'<span style="color:#333"> → '+e.note+'</span>':'');
  }).join('<br>');
}

// ── Snapshot pour undo ──
function takeSnapshot(){
  try{
    var s={_ts:Date.now()};
    // Numériques globaux
    ['score','highScore','gold','lives','level','floor','stage','currentFloor',
     'currentDungeonFloor','currentLevel','wave','waveNumber','coins','gems',
     'playerGold','energy','mana','ammo'].forEach(function(n){
      if(typeof window[n]==='number')s[n]=window[n];
    });
    // gameState
    if(typeof gameState!=='undefined')s.gameState=gameState;
    // Joueur (plusieurs conventions)
    ['hero','player','ship','character'].forEach(function(pn){
      if(typeof window[pn]!=='undefined'&&window[pn]&&typeof window[pn]==='object'){
        var p=window[pn];
        s['_p_'+pn]={hp:p.hp,maxHp:p.maxHp,speed:p.speed,attack:p.attack||p.damage,
          defense:p.defense,mp:p.mp,maxMp:p.maxMp,level:p.level,xp:p.xp,
          x:p.x,y:p.y,invincibilityTimer:p.invincibilityTimer||0,
          classId:p.classId,vx:p.vx||0,vy:p.vy||0};
      }
    });
    // Longueurs des tableaux
    ['enemies','towers','loot','minions','projectiles','bullets','interactables',
     'powerups','particles'].forEach(function(n){
      if(typeof window[n]!=='undefined'&&Array.isArray(window[n]))s['_len_'+n]=window[n].length;
    });
    // playerStats si existe
    if(typeof playerStats!=='undefined'&&playerStats)
      s._playerStats=JSON.parse(JSON.stringify(playerStats));
    if(typeof activeBuffs!=='undefined'&&Array.isArray(activeBuffs))
      s._activeBuffs=JSON.parse(JSON.stringify(activeBuffs));
    return s;
  }catch(e){return null;}
}

function applySnapshot(s){
  if(!s)return false;
  var ok=false;
  try{
    ['score','highScore','gold','lives','level','floor','stage','currentFloor',
     'currentDungeonFloor','currentLevel','wave','waveNumber','coins','gems',
     'playerGold','energy','mana','ammo'].forEach(function(n){
      if(s[n]!==undefined&&typeof window[n]==='number'){window[n]=s[n];ok=true;}
    });
    if(s.gameState!==undefined&&typeof gameState!=='undefined'){gameState=s.gameState;ok=true;}
    ['hero','player','ship','character'].forEach(function(pn){
      var pk='_p_'+pn;
      if(s[pk]&&typeof window[pn]!=='undefined'&&window[pn]){
        var p=window[pn],sd=s[pk];
        ['hp','maxHp','speed','attack','defense','mp','maxMp','level','xp',
         'invincibilityTimer','classId','vx','vy'].forEach(function(f){
          if(sd[f]!==undefined)p[f]=sd[f];
        });
        ok=true;
      }
    });
    if(s._playerStats&&typeof playerStats!=='undefined'&&playerStats){
      Object.assign(playerStats,s._playerStats);ok=true;
    }
    if(s._activeBuffs&&typeof activeBuffs!=='undefined'&&Array.isArray(activeBuffs)){
      activeBuffs.length=0;s._activeBuffs.forEach(function(b){activeBuffs.push(b);});ok=true;
    }
  }catch(e){}
  return ok;
}

function pushSnapshot(snap){
  if(!snap)return;
  _snapshots.push(snap);
  if(_snapshots.length>MAX_UNDO)_snapshots.shift();
  undoBtn.disabled=false;
}

function updateUndoBtn(){undoBtn.disabled=_snapshots.length===0;}

undoBtn.addEventListener('click',function(){
  if(!_snapshots.length)return;
  var snap=_snapshots.pop();
  updateUndoBtn();
  var ok=applySnapshot(snap);
  var dt=Math.round((Date.now()-snap._ts)/1000);
  if(ok){setStatus('↩ Annulé (il y a '+dt+'s)','ok');}
  else{setStatus('⚠ Annulation partielle — les changements complexes (nouvelles fonctions, types) ne peuvent pas être annulés automatiquement','warn');}
});

// ── Context browser ──
ctxBtn.addEventListener('click',function(){
  if(ctxPanel.classList.contains('open')){
    ctxPanel.classList.remove('open');
    ctxBtn.classList.remove('active');
    ctxPanel.innerHTML='';
    return;
  }
  ctxBtn.classList.add('active');
  var ctx=collectContext();
  var lines=['<b style="color:#226622">═══ CONTEXTE EN TEMPS RÉEL ═══</b>'];
  Object.keys(ctx).forEach(function(k){
    var v=ctx[k];
    var vs=typeof v==='object'?JSON.stringify(v).slice(0,90):String(v);
    lines.push('<span style="color:#00cc55">'+k+'</span><span style="color:#224422">:</span> <span style="color:#88aa88">'+vs+'</span>');
  });
  if(lines.length===1)lines.push('<span style="color:#1a3a1a">Aucune variable standard détectée (jeu custom)</span>');
  ctxPanel.innerHTML=lines.join('<br>');
  ctxPanel.classList.add('open');
});

// ── Collecte du contexte runtime ──
function collectContext(){
  var ctx={};
  try{
    var stateNames=['gameState','state','currentState','phase','mode','screen'];
    stateNames.forEach(function(n){if(typeof window[n]!=='undefined')ctx[n]=window[n];});
    var scoreNames=['score','highScore','bestScore','gold','lives','level','floor','stage',
                    'currentFloor','currentDungeonFloor','currentLevel','wave','waveNumber',
                    'coins','gems','playerGold','energy','mana','ammo','kills'];
    scoreNames.forEach(function(n){if(typeof window[n]!=='undefined')ctx[n]=window[n];});
    ['hero','player','ship','character','pawn','tank'].forEach(function(pn){
      if(typeof window[pn]!=='undefined'&&window[pn]&&typeof window[pn]==='object'){
        var p=window[pn];
        ctx[pn]={hp:p.hp,maxHp:p.maxHp,x:Math.round(p.x||0),y:Math.round(p.y||0),
          speed:p.speed,level:p.level,attack:p.attack||p.damage||p.atk,
          defense:p.defense||p.def,mp:p.mp,maxMp:p.maxMp,classId:p.classId,
          invincible:!!(p.invincibilityTimer>0)};
      }
    });
    var arrNames=['enemies','towers','projectiles','bullets','particles','loot','interactables',
                  'minions','platforms','coins','items','obstacles','pieces','waves','powerups',
                  'skills','traps','buildings','npcs','allies'];
    arrNames.forEach(function(n){
      if(typeof window[n]!=='undefined'&&Array.isArray(window[n]))ctx[n+'_count']=window[n].length;
    });
    if(typeof window['boss']!=='undefined')ctx.bossAlive=window['boss']!==null;
    if(typeof window['bossGate']!=='undefined')ctx.bossGateOpen=!!(window['bossGate']&&window['bossGate'].open);
    if(typeof ENEMY_TYPES!=='undefined')ctx.enemyTypes=Object.keys(ENEMY_TYPES);
    if(typeof TOWER_TYPES!=='undefined')ctx.towerTypes=Object.keys(TOWER_TYPES);
    if(typeof ITEM_TYPES!=='undefined')ctx.itemTypes=Object.keys(ITEM_TYPES);
    if(typeof WEAPON_TYPES!=='undefined')ctx.weaponTypes=Object.keys(WEAPON_TYPES);
    if(typeof UPGRADE_TYPES!=='undefined')ctx.upgradeTypes=Object.keys(UPGRADE_TYPES);
    if(typeof HERO_CLASSES!=='undefined')ctx.heroClasses=HERO_CLASSES.map(function(c){return c.id+':'+c.name;});
    if(typeof CUSTOM_SKILLS!=='undefined')ctx.customSkills=Object.keys(CUSTOM_SKILLS);
    if(typeof CUSTOM_ATTACKS!=='undefined')ctx.customAttacks=Object.keys(CUSTOM_ATTACKS);
    var fnNames=['createEnemy','spawnBoss','generateDungeon','checkLevelUp','handleEnemyDefeat',
                 'spawnParticles','spawnFloatingText','triggerShake','createProjectile',
                 'placeTower','addTower','spawnEnemy','createTower','restartGame','resetGame',
                 'spawnWave','addPowerup','unlockSkill','applyKnockback','onBossDefeat',
                 'openShop','buyItem','saveGame','loadGame','generateLevel','nextWave',
                 'addUpgrade','applyUpgrade','createItem','dropLoot'];
    var avail=fnNames.filter(function(n){return typeof window[n]==='function';});
    if(avail.length)ctx.functions=avail;
    if(typeof playerInventory!=='undefined')ctx.inventory=playerInventory;
    if(typeof activeBuffs!=='undefined'&&Array.isArray(activeBuffs))ctx.buffs=activeBuffs.length;
    if(typeof TILE_SIZE!=='undefined')ctx.TILE_SIZE=TILE_SIZE;
    if(typeof MAP_W!=='undefined')ctx.MAP_W=MAP_W;
  }catch(e){}
  return ctx;
}

// ── Validation syntaxique client ──
function validateSyntax(code){
  var o=0,c=0,po=0,pc=0,bo=0,bc=0;
  for(var i=0;i<code.length;i++){
    var ch=code[i];
    if(ch==='{')o++;else if(ch==='}')c++;
    else if(ch==='(')po++;else if(ch===')')pc++;
    else if(ch==='[')bo++;else if(ch===']')bc++;
  }
  if(o!==c)return 'Accolades: '+o+' { pour '+c+' }';
  if(po!==pc)return 'Parenthèses: '+po+' ( pour '+pc+' )';
  if(bo!==bc)return 'Crochets: '+bo+' [ pour '+bc+' ]';
  return null;
}

// ── Exécution du code patché ──
function execCode(code,explanation){
  var synErr=validateSyntax(code);
  if(synErr){
    setStatus('⚠ Syntaxe invalide côté client: '+synErr+' — Le code ne sera pas exécuté.','err');
    return false;
  }
  try{
    if(typeof window.__devPatch==='function'){
      window.__devPatch(code);
    }else{
      // Fallback: new Function (n'accède pas aux vars locales du jeu)
      (new Function(code))();
    }
    var msg=explanation||'Patch appliqué !';
    setStatus('✅ '+msg,'ok');
    input.value='';
    return true;
  }catch(e){
    var msg=e.message||String(e);
    if(msg.indexOf('not defined')!==-1){
      var vn=(msg.split(' ')[0]||'').replace(/[^a-zA-Z0-9_]/g,'');
      msg='Variable "'+vn+'" introuvable dans ce jeu. Utilisez le bouton ctx pour voir ce qui est disponible.';
    }else if(msg.indexOf('is not a function')!==-1){
      msg='Fonction non disponible dans ce jeu: '+msg+'. Vérifiez ctx → functions.';
    }else if(msg.indexOf('Cannot read')!==-1||msg.indexOf('null')!==-1){
      msg='Accès à null/undefined: '+msg+' — Ajoutez une vérification if(variable) avant.';
    }else if(msg.indexOf('Assignment to constant')!==-1){
      msg="Impossible de modifier une constante (const). Passez par l'objet: ex TYPE.xxx au lieu de TYPE=...";
    }else if(msg.indexOf('Unexpected token')!==-1){
      msg='Erreur de syntaxe JS: '+msg;
    }
    setStatus('❌ '+msg,'err');
    return false;
  }
}

// ── Application d'un patch ──
async function applyPatch(){
  var prompt=input.value.trim();
  if(!prompt)return;
  if(_history[0]!==prompt){_history.unshift(prompt);if(_history.length>50)_history.pop();}
  _histIdx=-1;
  btn.disabled=true;
  hideGeneratedCode();
  setStatus('⏳ Génération en cours...','pending');
  var snap=takeSnapshot();
  try{
    var resp=await fetch('/api/game-patch',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({filename:FILENAME,prompt:prompt,context:collectContext()})
    });
    if(!resp.ok){
      var errText=await resp.text();
      setStatus('❌ Erreur serveur '+resp.status+': '+errText.slice(0,80),'err');
      addLog(prompt,false,'HTTP '+resp.status);
      return;
    }
    var data=await resp.json();
    if(data.error){
      setStatus('❌ '+data.error,'err');
      addLog(prompt,false,data.error.slice(0,40));
    }else if(data.code){
      // Afficher le code avant l'exec (utile si l'exec plante)
      showGeneratedCode(data.code);
      var ok=execCode(data.code,data.explanation);
      if(ok){
        pushSnapshot(snap);
        addLog(prompt,true,data.explanation?data.explanation.slice(0,80):'');
      }else{
        // En cas d'erreur, garder le code visible automatiquement pour debug
        if(codePre)codePre.style.display='block';
        if(codeToggle)codeToggle.textContent='▼ masquer le code généré (erreur — vérifier la syntaxe)';
        addLog(prompt,false,'Erreur exec');
      }
    }else{
      setStatus('⚠ Réponse vide du serveur','warn');
      addLog(prompt,false,'réponse vide');
    }
  }catch(e){
    setStatus('❌ Réseau: '+e.message,'err');
    addLog(prompt,false,'réseau');
  }finally{btn.disabled=false;}
}

// ── Événements ──
btn.addEventListener('click',applyPatch);
input.addEventListener('keydown',function(e){
  if(e.code!=='Backquote'&&e.code!=='IntlBackslash')e.stopPropagation();
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();applyPatch();return;}
  if(e.key==='ArrowUp'&&!e.shiftKey&&_history.length){
    e.preventDefault();_histIdx=Math.min(_histIdx+1,_history.length-1);input.value=_history[_histIdx];
  }
  if(e.key==='ArrowDown'&&!e.shiftKey){
    e.preventDefault();_histIdx=Math.max(_histIdx-1,-1);input.value=_histIdx>=0?_history[_histIdx]:'';
  }
});
document.addEventListener('keydown',function(e){
  if(e.code==='Backquote'||e.code==='IntlBackslash'){
    e.preventDefault();
    if(panel.classList.contains('open')){
      panel.classList.remove('open');input.blur();
    }else{
      panel.classList.add('open');input.focus();
    }
  }
});
})();
</script>
"""

CONSOLE_BLOCK = _CONSOLE_CSS + _CONSOLE_HTML + _CONSOLE_JS


def _inject_patch_bridge(html: str) -> str:
    """
    Injecte window.__devPatch = function(code){ eval(code); } à l'intérieur du
    DOMContentLoaded du script principal, juste avant sa fermeture }).
    Cela permet à eval() d'accéder aux variables déclarées avec let/const dans ce scope.

    Stratégie robuste (brace counting) :
    1. Trouver document.addEventListener('DOMContentLoaded', ...)
    2. Localiser l'accolade ouvrante { du callback
    3. Compter les accolades pour trouver la fermeture exacte (depth 0)
    4. Injecter juste avant cette fermeture
    Évite les faux positifs de l'ancienne approche regex sur }); en fin de script.
    """
    # Trouver le script principal (le plus long <script> sans src=)
    script_match = None
    best_len = 0
    for m in re.finditer(
        r'(<script(?:\s(?!src)[^>]*)?>)(.*?)(</script>)',
        html, re.DOTALL | re.IGNORECASE
    ):
        if len(m.group(2)) > best_len:
            best_len = len(m.group(2))
            script_match = m

    if not script_match:
        return html

    script_body = script_match.group(2)
    script_offset = script_match.start(2)  # position dans le HTML global

    # Localiser document.addEventListener('DOMContentLoaded'
    dom_match = re.search(
        r'document\s*\.\s*addEventListener\s*\(\s*[\'"]DOMContentLoaded[\'"]',
        script_body
    )
    if not dom_match:
        # Pas de DOMContentLoaded → injecter le bridge en fin du script principal
        # (accès limité aux vars globales uniquement, mais mieux que rien)
        insert_in_script = len(script_body)
        bridge = "\n  // Dev console bridge (global scope)\n  window.__devPatch = function(code) { return eval(code); };\n"
        new_script = script_body[:insert_in_script] + bridge + script_body[insert_in_script:]
        return html[:script_offset] + new_script + html[script_offset + len(script_body):]

    # Trouver l'accolade ouvrante { du callback DOMContentLoaded
    cb_open = script_body.find('{', dom_match.end())
    if cb_open == -1:
        return html

    # Brace counting : trouver la fermeture correspondante
    depth = 0
    in_string = False
    str_char = ''
    i = cb_open

    # Nettoyer les strings/commentaires pour un counting propre
    # On fait un scan simple en tenant compte des strings et commentaires single-line
    while i < len(script_body):
        ch = script_body[i]

        # Commentaire single-line (//)
        if not in_string and ch == '/' and i + 1 < len(script_body) and script_body[i+1] == '/':
            # Sauter jusqu'à la fin de la ligne
            nl = script_body.find('\n', i)
            i = nl + 1 if nl != -1 else len(script_body)
            continue

        # Commentaire multi-ligne (/* */)
        if not in_string and ch == '/' and i + 1 < len(script_body) and script_body[i+1] == '*':
            end = script_body.find('*/', i + 2)
            i = end + 2 if end != -1 else len(script_body)
            continue

        # Début/fin de string
        if not in_string and ch in ('"', "'", '`'):
            in_string = True
            str_char = ch
            i += 1
            continue
        if in_string:
            if ch == '\\':
                i += 2  # skip escaped char
                continue
            if ch == str_char:
                in_string = False
            i += 1
            continue

        # Comptage accolades
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                # C'est la fermeture du DOMContentLoaded
                # Injecter le bridge juste avant ce '}'
                insert_pos_in_script = i
                bridge = "\n  // Dev console bridge — accès aux variables locales du jeu\n  window.__devPatch = function(code) { return eval(code); };\n"
                new_script = script_body[:insert_pos_in_script] + bridge + script_body[insert_pos_in_script:]
                return html[:script_offset] + new_script + html[script_offset + len(script_body):]
        i += 1

    # Fermeture non trouvée → fallback : fin du script
    bridge = "\n// Dev console bridge (fallback)\nwindow.__devPatch = function(code) { return eval(code); };\n"
    new_script = script_body + bridge
    return html[:script_offset] + new_script + html[script_offset + len(script_body):]


def inject(html: str) -> str:
    """
    Injecte la dev console dans le HTML si elle n'est pas déjà présente.
    1. Ajoute <meta charset="utf-8"> si absent (sinon les caractères JS sont mal lus)
    2. Injecte le bridge __devPatch dans le DOMContentLoaded (accès aux vars locales)
    3. Injecte le panneau CSS+HTML+JS avant </body>
    """
    if CONSOLE_MARKER in html:
        return html  # Déjà présente

    # Étape 0 : garantir que le charset UTF-8 est déclaré
    if 'charset' not in html[:1000].lower():
        html = re.sub(r'(<head\b[^>]*>)', r'\1\n<meta charset="utf-8">', html, count=1, flags=re.IGNORECASE)

    # Étape 1 : bridge dans le scope du jeu
    html = _inject_patch_bridge(html)

    # Étape 2 : panneau console avant </body>
    body_close = re.search(r'</body\s*>', html, re.IGNORECASE)
    if body_close:
        return html[:body_close.start()] + CONSOLE_BLOCK + html[body_close.start():]

    # Fallback : ajouter à la fin
    return html + CONSOLE_BLOCK


def is_present(html: str) -> bool:
    """Retourne True si la dev console est déjà dans le HTML."""
    return CONSOLE_MARKER in html

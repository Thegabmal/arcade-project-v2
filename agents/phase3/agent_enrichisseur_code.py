"""
Agent Enrichisseur Code — Phase 3 (enrichissement progressif)
Prend un jeu HTML5 existant et y ajoute des systèmes en profondeur via JSON patches.

Passe 2 : systèmes de profondeur (boss phases, quêtes, shop, power-ups, inventaire)
Passe 3 : polish visuel (particules avancées, WebAudio, animations, secrets)

Format de patch JSON :
{
  "systemes_ajoutes": ["boss phase 2", "shop", "quêtes"],
  "global_vars": ["const LOOT_TABLE = [...];", "let questProgress = 0;"],
  "replaced_functions": [{"name": "updateBoss", "code": "function updateBoss(dt) { ... }"}],
  "new_functions": ["function openShop() { ... }", "function checkQuests() { ... }"],
  "commentaire": "..."
}
"""

import re as _re
import json as _json
from config import call_gemini, call_gemini_json, with_fallback
from genre_profile import ConceptionContext
from logger import phase3_log

# Seuil minimum de chars de passe 1 pour déclencher l'enrichissement
SEUIL_PROGRESSIF = 50000

SYSTEM_ENRICHISSEUR = """Tu es un développeur senior spécialisé en HTML5/JavaScript Canvas 2D.
Tu reçois le code source d'un jeu HTML5 fonctionnel et tu y AJOUTES des systèmes manquants.

FORMAT DE RÉPONSE OBLIGATOIRE — JSON uniquement :
{
  "systemes_ajoutes": ["nom système 1", "nom système 2"],
  "global_vars": ["const LOOT_TABLE = [...];", "let questProgress = 0;"],
  "replaced_functions": [
    {"name": "updateBoss", "code": "function updateBoss(dt) { /* corps complet */ }"},
    {"name": "generateLevel", "code": "function generateLevel() { /* corps complet */ }"}
  ],
  "new_functions": [
    "function openShop() { /* corps complet */ }",
    "function checkQuests(dt) { /* corps complet */ }"
  ],
  "commentaire": "Systèmes ajoutés : boss phase 2/3, shop, quêtes"
}

RÈGLES CRITIQUES :
- N'invente JAMAIS de variables : n'utilise que celles existant dans le code fourni
- Les fonctions dans "replaced_functions" REMPLACENT entièrement la version actuelle
- Les fonctions dans "new_functions" sont AJOUTÉES sans duplication — vérifie qu'elles n'existent pas déjà
- Les "global_vars" sont injectées AVANT le DOMContentLoaded (tableau/objet uniquement)
- Chaque fonction DOIT être 100% complète avec accolades équilibrées — jamais de "// suite..."
- JAMAIS eval(), window.__devPatch, new Function()
- `let` pour scalaires mutables, `const` pour tableaux/objets dont la référence ne change pas
- Si tu remplaces updateBoss, inclure TOUTES les phases dans la nouvelle version
- Les replaced_functions doivent être au moins 3× plus longues que les stubs qu'elles remplacent

INTERDITS ABSOLUS — ces patterns crashent le jeu :
- JAMAIS .clear() sur un tableau → utiliser TOUJOURS .length = 0 (Array.clear() n'existe pas en JS)
- JAMAIS utiliser une variable dans une fonction sans la déclarer dans sa portée (const/let avant utilisation)
- JAMAIS omettre un timer dans createEnemy() si ce timer est utilisé dans updateEnemies() ou updateBoss()
  → Tout `enemy.flashTimer`, `enemy.invTimer`, `enemy.knockTimer` utilisé DOIT être initialisé à 0 dans createEnemy()
- JAMAIS shadow une variable globale (ne pas redéclarer avec const/let une variable déjà déclarée globalement)
- JAMAIS utiliser des propriétés sur un objet-type (ENEMY_TYPES, CUSTOM_ATTACKS) sans les déclarer dans cet objet
  → Si CUSTOM_ATTACKS.archer est une fonction, déclarer `const baseDmg = attacker.atk;` DANS cette fonction
- JAMAIS for...of avec splice → utiliser boucle inversée `for (let i = arr.length-1; i>=0; i--)`

Tu réponds UNIQUEMENT en JSON valide"""


def _detect_existing_systems(html: str) -> dict:
    """Détecte les systèmes déjà implémentés dans le code HTML."""
    patterns = {
        'has_shop':           r'(function\s+openShop|shopItems|shopState|function\s+drawShop|SHOP_ITEMS)',
        'has_quest':          r'(quests\s*=\s*\[|questProgress|function\s+checkQuests|QUEST_DEFS|activeQuest)',
        'has_boss_phases':    r'(boss\.phase\s*[=>]|bossPhase\s*[=>]|boss\.maxPhase|phase\s*===\s*[23])',
        'has_powerups':       r'(powerups\s*=\s*\[|POWERUP_TYPES|activePowerup|function\s+spawnPowerup)',
        'has_particles_adv':  r'(particleEmitter|PARTICLE_TYPES|function\s+emitParticles|particles\.type)',
        'has_screen_shake':   r'(screenShake|shakeMag|function\s+triggerShake|shakeTimer\s*[=>])',
        'has_sound_system':   r'(new\s+AudioContext|new\s+\(window\.AudioContext|audioCtx\s*=|sfx\.init)',
        'has_floating_text':  r'(floatingTexts\s*=\s*\[|function\s+addFloatingText|function\s+spawnFloatingText)',
        'has_secrets':        r'(secretRoom|SECRETS|konami|easterEgg|cheatCode)',
        'has_inventory':      r'(player\.inventory\s*=|inventorySlots|function\s+openInventory)',
        'has_minimap':        r'(function\s+drawMinimap|minimapCanvas|drawMiniMap)',
        'has_level_up':       r'(function\s+checkLevelUp|player\.xp\s*[+>]=|player\.level\s*\+\+)',
        'has_dialogue':       r'(dialogueBox|activeDialogue|function\s+showDialogue|NPC_DIALOGUES)',
        'has_knockback':      r'(knockbackVX|knockbackTimer|function\s+applyKnockback)',
        'has_loot_table':     r'(LOOT_TABLE\s*=|function\s+rollLoot|lootItems\s*=\s*\[)',
    }
    detected = {}
    for system, pattern in patterns.items():
        detected[system] = bool(_re.search(pattern, html, _re.IGNORECASE))
    return detected


def _apply_enrichment_patch(html: str, patch: dict) -> str:
    """
    Applique un JSON patch à un code HTML existant.
    - global_vars    → injectés avant DOMContentLoaded
    - replaced_functions → remplacent les fonctions existantes
    - new_functions  → ajoutés à la fin du bloc <script>
    Retourne le HTML enrichi.
    """
    if not patch:
        return html

    # Import circulaire évité : importer seulement quand nécessaire
    from agents.phase3.agent_createur import _extract_func_with_braces

    # Extraire le bloc <script>
    script_m = _re.search(r'(<script(?:\s[^>]*)?>)(.*?)(</script>)', html, _re.DOTALL | _re.IGNORECASE)
    if not script_m:
        phase3_log.warning("[Enrichisseur] Aucun bloc <script> trouvé — patch annulé")
        return html

    pre_script   = html[:script_m.start(2)]
    script_content = script_m.group(2)
    post_script  = html[script_m.end(2):]

    # ── 1. Injecter global_vars avant DOMContentLoaded ────────────────────
    global_vars = patch.get('global_vars', [])
    if global_vars:
        dom_m = _re.search(
            r'document\.addEventListener\s*\(\s*[\'"]DOMContentLoaded',
            script_content
        )
        if dom_m:
            insert_pos = dom_m.start()
            vars_str = '\n'.join(str(v) for v in global_vars) + '\n\n'
            script_content = script_content[:insert_pos] + vars_str + script_content[insert_pos:]
            phase3_log.info(f"  → {len(global_vars)} global_var(s) injectée(s)")
        else:
            # Aucun DOMContentLoaded trouvé → injecter en tête du script
            vars_str = '\n'.join(str(v) for v in global_vars) + '\n\n'
            script_content = vars_str + script_content

    # ── 2. Remplacer les fonctions existantes ─────────────────────────────
    replaced_count = 0
    for rf in patch.get('replaced_functions', []):
        name = rf.get('name', '') if isinstance(rf, dict) else ''
        new_code = rf.get('code', '') if isinstance(rf, dict) else ''
        if not name or not new_code:
            continue
        old_body, old_s, old_e = _extract_func_with_braces(script_content, name)
        if old_body:
            # Garde anti-régression : si la nouvelle version est < 40% de l'originale,
            # le LLM a probablement tronqué la fonction — on ignore ce remplacement
            if len(new_code) < len(old_body) * 0.4:
                phase3_log.warning(
                    f"  → Remplacement de {name} rejeté — régression trop forte "
                    f"({len(old_body)} → {len(new_code)} chars, < 40%)"
                )
                continue
            script_content = script_content[:old_s] + new_code + script_content[old_e:]
            replaced_count += 1
            phase3_log.info(f"  → Remplacement de {name} ({len(old_body)} → {len(new_code)} chars)")
        else:
            # Fonction absente : l'ajouter comme nouvelle fonction
            phase3_log.info(f"  → {name} absente du code — ajout en tant que nouvelle fonction")
            script_content = script_content + '\n\n' + new_code

    if replaced_count:
        phase3_log.info(f"  → {replaced_count} fonction(s) remplacée(s)")

    # ── 3. Ajouter les nouvelles fonctions à la fin du script ─────────────
    new_funcs = patch.get('new_functions', [])
    valid_new = []
    for fn_code in new_funcs:
        if not fn_code:
            continue
        # Vérifier que la fonction n'existe pas déjà
        fn_name_m = _re.match(r'\s*function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)', str(fn_code))
        if fn_name_m:
            fn_name = fn_name_m.group(1)
            if _re.search(r'function\s+' + _re.escape(fn_name) + r'\s*\(', script_content):
                phase3_log.info(f"  → {fn_name} déjà présente — ignorée")
                continue
        valid_new.append(str(fn_code))

    if valid_new:
        script_content = script_content + '\n\n' + '\n\n'.join(valid_new)
        phase3_log.info(f"  → {len(valid_new)} nouvelle(s) fonction(s) ajoutée(s)")

    return pre_script + script_content + post_script


def _extract_code_sample(html: str, max_chars: int = 20000) -> str:
    """Extrait un échantillon du code JS pour le prompt (début + fin du script)."""
    try:
        from utils import extract_js_sample
        return extract_js_sample(html, max_chars)
    except Exception:
        return html[:max_chars]


def enrich_pass2(html: str, context: ConceptionContext, game_logics: str = "") -> str:
    """
    Passe 2 — Enrichissement profondeur.
    Ajoute : boss phases, quêtes, shop, power-ups, loot table, knockback, dialogue
    """
    gp = context.genre_profile
    gdd = context.gdd
    titre = gdd.get('titre', '?')

    phase3_log.agent_start("Enrichisseur P2", f"Profondeur systèmes ({titre})")

    detected = _detect_existing_systems(html)
    detected_str = ", ".join(k.replace('has_', '') for k, v in detected.items() if v) or "aucun détecté"

    # Systèmes manquants prioritaires pour profondeur
    depth_systems = {
        'has_boss_phases':  "Boss multi-phases (au moins 2 phases distinctes avec comportements différents, indicateur visuel de transition)",
        'has_powerups':     "Power-ups temporaires collectables (3+ types : vitesse, invincibilité, attaque renforcée) avec timer visuel dans le HUD",
        'has_loot_table':   "Loot table variée pour les coffres/ennemis (4+ types d'items : potions, équipements, or, parchemins)",
        'has_quest':        "Système de quêtes simples (3 quêtes actives max, tracker visible dans HUD, récompenses XP/gold)",
        'has_knockback':    "Knockback des ennemis (impulsion + rebond mural, timer 0.3s d'invincibilité post-knockback)",
        'has_floating_text': "Floating texts (+10, CRITIQUE!, LEVEL UP) avec couleur et durée de vie",
        'has_level_up':     "Level up impactant (HP max +15%, soin complet, stats affichées, floating text LEVEL UP)",
        'has_dialogue':     "Dialogues NPC simples (boîte de dialogue cliquable avec options et récompenses quête)",
    }

    missing = {k: v for k, v in depth_systems.items() if not detected.get(k)}
    if not missing:
        phase3_log.info("[Enrichisseur P2] Tous les systèmes de profondeur déjà présents — skip")
        return html

    missing_str = "\n".join(f"- {v}" for v in missing.values())

    genre = gp.genre_principal
    code_sample = _extract_code_sample(html, 18000)
    game_logics_str = f"\nGAME LOGICS (formules, équilibrage) :\n{game_logics[:6000]}" if game_logics else ""

    prompt = f"""Tu enrichis le code d'un jeu HTML5 {genre} : "{titre}".
Code actuel : {len(html)} caractères.

SYSTÈMES DÉJÀ PRÉSENTS : {detected_str}

SYSTÈMES À AJOUTER (priorité haute) :
{missing_str}

EXTRAIT DU CODE ACTUEL :
```javascript
{code_sample}
```
{game_logics_str}

CONSIGNES :
1. Analyse quelles fonctions existantes doivent être étendues (ex: updateBoss, generateLevel, checkCollisions)
2. Génère un patch JSON avec UNIQUEMENT les systèmes réellement manquants
3. Pour les replaced_functions : inclure la logique COMPLÈTE (ancienne + nouvelle)
4. Priorité absolue : boss multi-phases et power-ups si absents
5. Chaque nouvelle fonction doit être COMPLÈTE (pas de stubs)

Réponds en JSON valide :
{{
  "systemes_ajoutes": ["..."],
  "global_vars": ["const POWERUP_TYPES = [{{type:'speed', color:'#0FF', duration:5, label:'VITESSE'}},...];"],
  "replaced_functions": [{{"name": "updateBoss", "code": "function updateBoss(dt) {{ ... }}"}}],
  "new_functions": ["function spawnPowerup(x, y) {{ ... }}", "function updatePowerups(dt) {{ ... }}"],
  "commentaire": "..."
}}"""

    result = _call_enrichment(prompt, SYSTEM_ENRICHISSEUR)
    if not result or not isinstance(result, dict):
        phase3_log.warning("[Enrichisseur P2] Réponse invalide — code inchangé")
        return html

    added = result.get('systemes_ajoutes', [])
    phase3_log.info(f"[Enrichisseur P2] Systèmes identifiés : {added}")

    enriched = _apply_enrichment_patch(html, result)
    if len(enriched) <= len(html):
        phase3_log.warning(f"[Enrichisseur P2] Patch sans gain ({len(enriched)} chars) — code inchangé")
        return html

    phase3_log.agent_done("Enrichisseur P2", f"{len(enriched)} chars (delta: +{len(enriched) - len(html)})")
    return enriched


def enrich_pass3(html: str, context: ConceptionContext) -> str:
    """
    Passe 3 — Polish visuel et audio.
    Ajoute : screen shake, sons WebAudio, particules avancées, minimap, secrets
    """
    gp = context.genre_profile
    gdd = context.gdd
    titre = gdd.get('titre', '?')

    phase3_log.agent_start("Enrichisseur P3", f"Polish visuel/audio ({titre})")

    detected = _detect_existing_systems(html)
    detected_str = ", ".join(k.replace('has_', '') for k, v in detected.items() if v) or "aucun"

    # Systèmes de polish
    polish_systems = {
        'has_screen_shake':  "Screen shake (triggerShake(mag, dur) — mag 2 normal, mag 6 boss/mort)",
        'has_sound_system':  "Sons WebAudio (WebAudio API : attaque, dégâts, collecte, level_up, game_over — sfx.play enrichi)",
        'has_particles_adv': "Particules avancées (trail joueur, explosion boss avec fragments, sparkle collectible)",
        'has_minimap':       "Minimap (coin bas-droite, 80×80px, joueur point blanc, ennemis points rouges, coffres points jaunes)",
        'has_secrets':       "Easter egg (salle secrète ou item caché, code Konami ou zone cachée, récompense surprise)",
    }

    missing = {k: v for k, v in polish_systems.items() if not detected.get(k)}
    if not missing:
        phase3_log.info("[Enrichisseur P3] Tous les systèmes de polish déjà présents — skip")
        return html

    missing_str = "\n".join(f"- {v}" for v in missing.values())

    genre = gp.genre_principal
    code_sample = _extract_code_sample(html, 16000)

    prompt = f"""Tu ajoutes du polish visuel/audio à un jeu HTML5 {genre} : "{titre}".
Code actuel : {len(html)} caractères.

SYSTÈMES DÉJÀ PRÉSENTS : {detected_str}

AMÉLIORATIONS POLISH À AJOUTER :
{missing_str}

EXTRAIT DU CODE ACTUEL :
```javascript
{code_sample}
```

CONSIGNES :
1. Screen shake : ajouter triggerShake(mag, dur) + updateShake(dt) comme NOUVELLES fonctions seulement
2. WebAudio : ajouter initAudio() + sfx.play() comme NOUVELLE fonction seulement
3. Particules avancées : ajouter spawnTrail(x,y) comme NOUVELLE fonction seulement
4. NE PAS utiliser replaced_functions — trop risqué de corrompre le code existant
5. Ne pas dupliquer des fonctions déjà présentes
6. Garder chaque fonction sous 25 lignes — pas de newlines littéraux dans les strings JSON, utiliser \\n

IMPORTANT JSON :
- Toutes les fonctions dans "new_functions" sont des strings JSON sur UNE SEULE LIGNE
- Échapper les guillemets doubles en \\" et les newlines en \\n
- Chaque fonction max 25 lignes

Réponds en JSON valide :
{{
  "systemes_ajoutes": ["screen_shake", "webAudio"],
  "global_vars": ["let shakeX = 0, shakeY = 0, shakeDur = 0;"],
  "replaced_functions": [],
  "new_functions": [
    "function triggerShake(mag, dur) {{ shakeX=(Math.random()-0.5)*mag; shakeY=(Math.random()-0.5)*mag; shakeDur=dur; }}",
    "function updateShake(dt) {{ if(shakeDur>0){{ shakeDur-=dt; shakeX*=0.85; shakeY*=0.85; if(shakeDur<=0){{shakeX=0;shakeY=0;}} }} }}"
  ],
  "commentaire": "..."
}}"""

    result = _call_enrichment(prompt, SYSTEM_ENRICHISSEUR)
    if not result or not isinstance(result, dict):
        phase3_log.warning("[Enrichisseur P3] Réponse invalide — code inchangé")
        return html

    added = result.get('systemes_ajoutes', [])
    phase3_log.info(f"[Enrichisseur P3] Polish identifié : {added}")

    enriched = _apply_enrichment_patch(html, result)
    if len(enriched) <= len(html):
        phase3_log.warning(f"[Enrichisseur P3] Patch sans gain — code inchangé")
        return html

    phase3_log.agent_done("Enrichisseur P3", f"{len(enriched)} chars (delta: +{len(enriched) - len(html)})")
    return enriched


def _repair_json(raw: str) -> dict | None:
    """
    Parse robuste d'un JSON contenant du code JS multilignes.
    Le LLM met souvent des newlines littéraux dans les strings JSON (invalide).
    Machine à états : parcourt char par char, échappe les newlines/tabs dans les strings.
    """
    # 1. Parse direct
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        pass

    # 2. Extraire le bloc JSON (entre { et })
    start = raw.find('{')
    end = raw.rfind('}')
    if start < 0 or end <= start:
        return None
    raw = raw[start:end + 1]

    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        pass

    # 3. Réparer : échapper les newlines/tabs littéraux à l'intérieur des strings
    repaired = []
    in_string = False
    i = 0
    while i < len(raw):
        c = raw[i]
        if in_string:
            if c == '\\':
                i += 1
                if i < len(raw):
                    next_c = raw[i]
                    # Séquences JSON valides : " \ / b f n r t u
                    if next_c in '"\\\\/bfnrtu':
                        repaired.append('\\')
                        repaired.append(next_c)
                    else:
                        # Escape invalide (\p, \d, \w, etc.) — doubler le backslash
                        repaired.append('\\')
                        repaired.append('\\')
                        repaired.append(next_c)
                else:
                    repaired.append('\\')
                    repaired.append('\\')
                i += 1
                continue
            elif c == '"':
                in_string = False
                repaired.append(c)
            elif c == '\n':
                repaired.append('\\n')
            elif c == '\r':
                repaired.append('\\r')
            elif c == '\t':
                repaired.append('\\t')
            else:
                repaired.append(c)
        else:
            if c == '"':
                in_string = True
            repaired.append(c)
        i += 1

    try:
        return _json.loads(''.join(repaired))
    except _json.JSONDecodeError as e:
        # 4. Réparation par fermeture forcée (JSON tronqué par limite de tokens)
        # Fermer la chaîne courante si on est dedans, puis fermer accolades/crochets
        try:
            partial = ''.join(repaired)
            in_str2 = False
            esc2 = False
            opens_brace = 0
            opens_bracket = 0
            for ch in partial:
                if esc2:
                    esc2 = False
                    continue
                if ch == '\\' and in_str2:
                    esc2 = True
                    continue
                if ch == '"':
                    in_str2 = not in_str2
                elif not in_str2:
                    if ch == '{':
                        opens_brace += 1
                    elif ch == '}':
                        opens_brace -= 1
                    elif ch == '[':
                        opens_bracket += 1
                    elif ch == ']':
                        opens_bracket -= 1
            closing = ''
            if in_str2:
                closing += '"'
            if opens_bracket > 0:
                closing += ']' * opens_bracket
            if opens_brace > 0:
                closing += '}' * opens_brace
            if closing:
                return _json.loads(partial + closing)
        except _json.JSONDecodeError:
            pass
        phase3_log.warning(f"[Enrichisseur] JSON repair échoué : {e}")
        return None


@with_fallback(None)
def _call_enrichment(prompt: str, system: str) -> dict:
    # Utilise call_gemini (texte brut) avec max_tokens élevé pour éviter la troncature
    # puis _repair_json pour gérer les newlines littéraux dans les strings JS
    raw = call_gemini(
        prompt=prompt,
        temperature=0.3,
        system_instruction=system,
        json_mode=True,
        max_tokens=55000,
    )
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n", 1)
        raw = lines[1] if len(lines) > 1 else ""
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].strip()
    return _repair_json(raw)

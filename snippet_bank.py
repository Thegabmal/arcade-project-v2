"""
Snippet Bank — extrait et stocke les implémentations validées des jeux high-score.
Fournit des exemples de code JS réels au créateur pour réduire les hallucinations
sur les patterns complexes (collisions, physique, génération de niveaux, etc.)

Stockage : snippet_bank.json
  {
    "rpg:collision":    { "code": "...", "score": 8.7, "game": "Dungeon...", "lines": 25 },
    "platformer:init":  { "code": "...", "score": 9.1, "game": "PlatformerX", "lines": 18 },
    ...
  }

Règles :
  - Score minimum MIN_SCORE pour stocker un snippet
  - 1 slot par (genre, function_type) — le meilleur score gagne
  - Taille max MAX_LINES par snippet
  - Injection max MAX_INJECT_CHARS dans le prompt créateur
"""

import re
import json
import os

BANK_FILE = os.path.join(os.path.dirname(__file__), "snippet_bank.json")
MIN_SCORE = 8.0     # Score minimum pour extraire
MAX_LINES = 55      # Lignes max par snippet
MAX_INJECT_CHARS = 2800  # Chars max injectés dans le prompt (évite de le saturer)

# Mapping : pattern regex de nom de fonction → type de slot
# On extrait la MEILLEURE implémentation de chaque slot par genre
_SLOT_PATTERNS = [
    (r'checkCollisions?|detectCollisions?|handleCollisions?|resolveCollisions?', 'collision'),
    (r'updateEnemies?|processEnemies?',                                           'enemy_update'),
    (r'createEnemy|spawnEnemy|makeEnemy',                                         'enemy_create'),
    (r'updatePlayer|movePlayer|handlePlayer',                                     'player_update'),
    (r'updatePhysics|applyGravity|physicsStep',                                   'physics'),
    (r'spawnParticles?|emitParticles?|addParticles?',                             'particles'),
    (r'generateDungeon|generateLevel|generateMap|buildDungeon|buildLevel',        'level_gen'),
    (r'initGame|resetGame|restartGame|startGame|newGame',                         'init'),
    (r'drawHUD|renderHUD|drawUI|renderUI|updateHUD',                              'hud'),
    (r'spawnBoss|createBoss|initBoss',                                            'boss_spawn'),
    (r'checkLevelUp|levelUp|gainXP|addXP',                                       'levelup'),
]

_SLOT_RE = [(re.compile(r'(?i)^' + pat + r'$'), slot) for pat, slot in _SLOT_PATTERNS]


def _slot_for_name(func_name: str) -> str | None:
    """Retourne le type de slot pour un nom de fonction, ou None si non pertinent."""
    for pattern, slot in _SLOT_RE:
        if pattern.match(func_name):
            return slot
    return None


def _extract_function(js: str, func_name: str) -> str | None:
    """
    Extrait le corps complet d'une fonction par comptage d'accolades.
    Gère les fonctions déclarées : function foo(params) { ... }
    Retourne None si la fonction est trop longue ou introuvable.
    """
    m = re.search(
        r'function\s+' + re.escape(func_name) + r'\s*\([^)]*\)\s*\{',
        js
    )
    if not m:
        return None

    start = m.start()
    brace_start = m.end() - 1  # position du { d'ouverture
    depth = 0
    i = brace_start

    while i < len(js):
        c = js[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                snippet = js[start:end]
                lines = snippet.split('\n')
                if len(lines) <= MAX_LINES:
                    return snippet
                return None  # Trop long
        i += 1

    return None


def _extract_all_function_names(js: str) -> list[str]:
    """Retourne tous les noms de fonctions déclarées dans le code."""
    return re.findall(r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(', js)


def _load() -> dict:
    if not os.path.exists(BANK_FILE):
        return {}
    try:
        with open(BANK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        with open(BANK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def store(html: str, genre: str, game_name: str, score_global: float) -> int:
    """
    Extrait les fonctions pertinentes du HTML et les stocke si le score est suffisant.
    Retourne le nombre de slots mis à jour.

    Principe : 1 slot par (genre, function_type), le meilleur score gagne toujours.
    """
    if score_global < MIN_SCORE:
        return 0

    # Extraire le JS principal (le script le plus long)
    scripts = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
    if not scripts:
        return 0
    js = max(scripts, key=len)
    if len(js) < 500:
        return 0

    genre = genre.lower().strip()
    bank = _load()
    updated = 0

    func_names = _extract_all_function_names(js)
    for func_name in func_names:
        slot_type = _slot_for_name(func_name)
        if not slot_type:
            continue

        slot_key = f"{genre}:{slot_type}"
        existing = bank.get(slot_key)

        # On remplace seulement si le nouveau score est meilleur
        if existing and existing.get("score", 0) >= score_global:
            continue

        snippet = _extract_function(js, func_name)
        if not snippet:
            continue

        lines = len(snippet.split('\n'))
        bank[slot_key] = {
            "code": snippet,
            "score": round(score_global, 2),
            "game": game_name[:40],
            "func_name": func_name,
            "lines": lines,
        }
        updated += 1

    if updated:
        _save(bank)

    return updated


def query(genre: str) -> str:
    """
    Retourne les snippets validés pour un genre, formatés pour le prompt créateur.
    Limité à MAX_INJECT_CHARS pour ne pas saturer le contexte.

    Retourne une chaîne vide si aucun snippet disponible pour ce genre.
    """
    genre = genre.lower().strip()
    bank = _load()

    # Collecter les slots pour ce genre, triés par score décroissant
    slots = [
        (key.split(':')[1], entry)
        for key, entry in bank.items()
        if key.startswith(f"{genre}:")
    ]
    if not slots:
        # Essayer les sous-genres proches (ex: "dungeon crawler" → "rpg")
        _GENRE_ALIASES = {
            "dungeon crawler": "rpg", "dungeon": "rpg",
            "action rpg": "rpg", "action-rpg": "rpg",
            "run and gun": "shooter", "bullet hell": "shooter",
            "tower defense": "strategy", "rts": "strategy",
            "endless runner": "platformer", "side-scroller": "platformer",
        }
        alias = _GENRE_ALIASES.get(genre)
        if alias:
            slots = [
                (key.split(':')[1], entry)
                for key, entry in bank.items()
                if key.startswith(f"{alias}:")
            ]

    if not slots:
        return ""

    slots.sort(key=lambda x: -x[1].get("score", 0))

    # Priorité d'injection : collision > level_gen > init > player_update > enemy_update > autres
    PRIORITY = ['collision', 'level_gen', 'init', 'player_update', 'enemy_update',
                'physics', 'boss_spawn', 'hud', 'particles', 'levelup', 'enemy_create']
    slots.sort(key=lambda x: PRIORITY.index(x[0]) if x[0] in PRIORITY else 99)

    lines = [
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"FONCTIONS VALIDÉES — Genre '{genre}' (extraites de jeux ayant obtenu ≥ 8/10)",
        "Adapte ces implémentations — ne les copie pas telles quelles.",
        "Elles prouvent ce qui FONCTIONNE réellement dans ce genre.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    total_chars = sum(len(l) for l in lines)

    injected = 0
    for slot_type, entry in slots:
        code = entry.get("code", "")
        if not code:
            continue

        header = f"\n// ── {slot_type.upper()} — {entry.get('game', '?')} (score {entry.get('score', 0):.1f}/10) ──"
        block = header + "\n" + code

        if total_chars + len(block) > MAX_INJECT_CHARS:
            break

        lines.append(block)
        total_chars += len(block)
        injected += 1

        if injected >= 3:  # Max 3 snippets pour ne pas saturer
            break

    if injected == 0:
        return ""

    return "\n".join(lines) + "\n"


def get_stats() -> str:
    """Résumé lisible de la banque pour logs/debug."""
    bank = _load()
    if not bank:
        return "Snippet Bank vide."
    lines = [f"=== Snippet Bank ({len(bank)} slots) ==="]
    for key, entry in sorted(bank.items()):
        lines.append(
            f"  {key:35s}  score={entry.get('score',0):.1f}  "
            f"lines={entry.get('lines',0)}  game={entry.get('game','?')[:30]}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_stats())

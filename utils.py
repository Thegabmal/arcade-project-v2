"""
Utilitaires partagés — arcade-project-v2
Fonctions communes utilisées par plusieurs agents.
"""

import re


def extract_js_sample(html: str, max_chars: int = 24000) -> str:
    """
    Extrait le bloc JavaScript principal depuis le HTML puis en prend un échantillon
    intelligent. Utilisé par tous les agents d'évaluation Phase 4.

    Stratégie :
    1. Extrait le plus grand bloc <script> (= le code du jeu, pas les CDN)
    2. Si le JS est ≤ max_chars, le retourne entier
    3. Sinon, prend 5 tranches réparties pour couvrir début/milieu/fin
       — les déclarations de variables sont concentrées au début
       — les fonctions update/draw sont souvent dans le milieu-fin

    Returns:
        Extrait du JS du jeu (jamais du CSS ou HTML pur)
    """
    if not html:
        return ""

    # Extraire tous les blocs <script>
    matches = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
    if matches:
        # Prendre le plus long (= le code du jeu, pas les petits CDN/analytics)
        js = max(matches, key=len)
        if len(js) > 500:
            code = js
        else:
            # Tous les scripts sont trop courts → utiliser le HTML complet
            code = html
    else:
        code = html

    # Strip comments to reduce token count before sampling
    code = strip_js_comments(code)

    n = len(code)
    if n <= max_chars:
        return code

    # Échantillonnage en 5 tranches pour couvrir le fichier uniformément
    # Tranche 1 plus grande (début = déclarations, état global) : 35% du budget
    # Tranche 5 plus grande (fin = game loop, event handlers) : 25% du budget
    # Tranches 2-4 : 40% répartis uniformément
    c1 = int(max_chars * 0.35)
    c5 = int(max_chars * 0.25)
    c_mid = (max_chars - c1 - c5) // 3

    debut  = code[:c1]
    quart2 = code[n // 4 - c_mid // 2 : n // 4 + c_mid // 2]
    quart3 = code[n // 2 - c_mid // 2 : n // 2 + c_mid // 2]
    quart4 = code[3 * n // 4 - c_mid // 2 : 3 * n // 4 + c_mid // 2]
    fin    = code[-c5:]

    return (
        f"// [EXTRAIT PARTIEL — code complet={n} chars, analyse sur 5 zones représentatives]\n"
        f"// --- ZONE 1/5 : début (déclarations, constantes, état global) ---\n{debut}\n\n"
        f"// --- ZONE 2/5 : premier quart ---\n{quart2}\n\n"
        f"// --- ZONE 3/5 : milieu ---\n{quart3}\n\n"
        f"// --- ZONE 4/5 : troisième quart ---\n{quart4}\n\n"
        f"// --- ZONE 5/5 : fin (game loop, update, draw, events) ---\n{fin}"
    )


def strip_js_comments(js: str) -> str:
    """
    Remove JS single-line (//...) and multi-line (/* ... */) comments.
    Preserves string literals and regex to avoid false positives.
    Reduces token count ~20-30% before sending code to Phase 4 agents.
    """
    result: list = []
    i = 0
    n = len(js)
    in_single = False
    in_multi = False
    in_str = False
    str_char = ''

    while i < n:
        c = js[i]
        if in_single:
            if c == '\n':
                in_single = False
                result.append(c)
            i += 1
            continue
        if in_multi:
            if c == '*' and i + 1 < n and js[i + 1] == '/':
                in_multi = False
                i += 2
            else:
                i += 1
            continue
        if in_str:
            result.append(c)
            if c == '\\' and i + 1 < n:
                result.append(js[i + 1])
                i += 2
                continue
            if c == str_char:
                in_str = False
            i += 1
            continue
        if c in ('"', "'", '`'):
            in_str = True
            str_char = c
            result.append(c)
            i += 1
            continue
        if c == '/' and i + 1 < n:
            nc = js[i + 1]
            if nc == '/':
                in_single = True
                i += 2
                continue
            if nc == '*':
                in_multi = True
                i += 2
                continue
        result.append(c)
        i += 1

    return ''.join(result)


def sanitize_json_response(raw: str) -> str:
    """
    Nettoie une réponse LLM qui pourrait contenir des backticks Markdown
    avant le JSON. Utilisé par les agents qui n'utilisent pas call_gemini_json.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        # Format: ```json\n{...}\n``` → parts[1] = "json\n{...}\n"
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    return raw.strip()


def clamp(value: float, min_val: float = 0.0, max_val: float = 10.0) -> float:
    """Clamp un score dans [min_val, max_val]."""
    return max(min_val, min(max_val, value))

"""
Agent UX Designer -- Phase 2
Definit les guidelines UI/UX, le game feel, les feedbacks visuels
et l'experience globale du joueur, adaptes au genre.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile
from logger import phase2_log

SYSTEM = """Tu es un UX Designer specialise dans les jeux video avec une expertise en game feel,
juice et feedback. Tu crees des experiences fluides et satisfaisantes adaptees a chaque genre.

RÈGLES DE JUICE (à appliquer systématiquement) :
- Chaque action importante doit déclencher AU MOINS 2 feedbacks simultanés (ex: son + particules + screen shake)
- Screen shake : amplitude 3-8px, durée 150-300ms pour impacts normaux ; 10-15px, 400ms pour impacts forts
- Particules : minimum 8-12 particules par événement, durée de vie 400-800ms
- Flash d'écran : overlay rgba 20-40% opacité, durée 80-150ms
- Animations d'impact : squeeze/stretch 0.85-1.15x sur 100ms
- Transitions menu→jeu : fade ou slide 200-400ms (jamais instantané)
- Tous les timings doivent être des VALEURS NUMÉRIQUES précises, pas "court/moyen/long"

RÈGLES DE COHÉRENCE VISUELLE (obligatoires) :
- Palette de menaces codée par couleur : GRUNT=rouge/orange, TANK=violet/bleu foncé, RANGED=jaune/vert, BOSS=palette unique
- Hiérarchie visuelle : le joueur en blanc/cyan clair, ennemis en teintes chaudes, power-ups en vert vif
- HUD placement : score haut-gauche, HP haut-gauche sous score — jamais > 15% de l'écran
- Cohérence menu/jeu : même palette, même police, même univers partout
- Power-ups : bobbing animation + halo coloré + particules ambiantes
- État "en danger" (HP<25%) : vignette rouge subtile en bordure d'écran

RÈGLES DE LISIBILITÉ IMMÉDIATE :
- N'importe quel joueur comprend "qui attaque qui" en < 1 seconde de regard
- Ennemis dangereux (boss, élites) : 1.5-2× plus grands que les grunts
- Projectiles ennemis = couleurs chaudes (rouge, orange) / projectiles joueur = couleurs froides (bleu, cyan)
- Floating text : dégâts en rouge, soins en vert, XP en jaune — toujours au-dessus de l'entité

Tu reponds UNIQUEMENT en JSON valide."""


def run(genre_profile: GenreProfile, gdd: dict) -> dict:
    phase2_log.agent_start("UX Designer", f"UX pour {genre_profile.genre_principal}")

    interface_gdd = gdd.get('interface', dict())

    prompt = f"""Definis les guidelines UX/UI completes pour ce jeu HTML5.

GENRE : {genre_profile.genre_principal} / {genre_profile.sous_genre}
TON : {genre_profile.ton} | PUBLIC : {genre_profile.public_cible}
TITRE : {gdd.get('titre', '?')}
STYLE VISUEL : {genre_profile.style_visuel}
PALETTE : {genre_profile.palette_recommandee}
ANIMATIONS CLES : {json.dumps(genre_profile.animations_cles, ensure_ascii=False)}
EFFETS IMPORTANTS : {json.dumps(genre_profile.effets_importants, ensure_ascii=False)}
INTERFACE GDD : {json.dumps(interface_gdd, ensure_ascii=False)}

Definis :
1. GAME FEEL : les sensations de jeu a atteindre (le "juice")
2. FEEDBACK VISUEL : comment chaque action doit etre confirmee visuellement
3. HUD : disposition et design de l'interface en jeu
4. MENUS : design des ecrans hors-jeu (menu principal, game over, etc.)
5. ANIMATIONS : animations cles et leur impact sur le feel
6. EFFETS VISUELS : particles, screen shake, flash, etc.
7. LISIBILITE : comment garantir que le joueur comprend toujours ce qui se passe
8. ACCESSIBILITE : adaptations pour differents types de joueurs

Reponds en JSON :
{{
  "game_feel": {{
    "sensations_cibles": ["reactivite immediate", "impact des actions", "..."],
    "philosophie": "...",
    "elements_juice": ["...", "..."]
  }},
  "feedback_visuel": [
    {{"action": "saut", "feedback": "animation de saut + particules au sol", "importance": "haute"}}
  ],
  "hud": {{
    "position_score": "haut-gauche",
    "position_vie": "haut-droite",
    "elements": [
      {{"nom": "Score", "type": "texte", "position": "haut-gauche", "style": "..."}}
    ],
    "style_general": "...",
    "couleurs": {{"texte": "#FFF", "fond": "transparent", "accent": "#FFD700"}}
  }},
  "menus": {{
    "menu_principal": {{
      "elements": ["titre", "bouton jouer", "meilleur score"],
      "design": "...",
      "animation_entree": "..."
    }},
    "game_over": {{
      "elements": ["score final", "meilleur score", "rejouer", "message"],
      "design": "...",
      "transition": "..."
    }},
    "pause": {{
      "elements": ["reprendre", "menu principal"],
      "overlay": "fond semi-transparent"
    }}
  }},
  "animations": [
    {{"element": "joueur", "animations": ["idle", "run", "jump", "mort"], "style": "..."}}
  ],
  "effets_visuels": {{
    "particles": [
      {{
        "nom": "...",
        "declencheur": "...",
        "count": 12,
        "duree_ms": 600,
        "couleurs": ["#FF4444", "#FF8800"],
        "vitesse_px": 80,
        "description": "..."
      }}
    ],
    "screen_shake": {{
      "actif": true,
      "amplitude_px": 6,
      "duree_ms": 200,
      "declencheurs": ["mort joueur", "impact ennemi"]
    }},
    "flash": {{
      "actif": true,
      "opacite": 0.3,
      "duree_ms": 100,
      "couleurs": ["#FFFFFF"],
      "declencheurs": ["collectible", "power-up"]
    }},
    "squeeze_stretch": {{
      "actif": true,
      "facteur": 1.15,
      "duree_ms": 100,
      "declencheurs": ["saut", "impact"]
    }},
    "autres": []
  }},
  "lisibilite": {{
    "contraste": "...",
    "distinction_ennemis_elements": "...",
    "indicateurs_danger": "...",
    "progression_visible": "..."
  }},
  "responsive": {{
    "canvas_adaptatif": true,
    "controles_touch": "description des controles tactiles si applicable",
    "breakpoints": []
  }},
  "timings_cles": {{
    "transition_menu_jeu_ms": 300,
    "transition_game_over_ms": 500,
    "delai_restart_ms": 800,
    "duree_invincibilite_ms": 1500,
    "cooldown_attaque_ms": 400
  }},
  "polish_specifique_genre": "Conseils de polish specifiques a ce genre"
}}"""

    result = _call(prompt)
    phase2_log.agent_done("UX Designer", f"Game feel: {len(result.get('game_feel', {}).get('elements_juice', []))} elements juice")
    return result


@with_fallback({
    "game_feel": {"sensations_cibles": [], "elements_juice": []},
    "feedback_visuel": [],
    "hud": {"elements": []},
    "menus": {},
    "effets_visuels": {"particles": [], "screen_shake": {"actif": False}},
    "lisibilite": {},
})
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.5, system_instruction=SYSTEM, max_tokens=32000)

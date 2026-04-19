"""
Agent Playtester — Phase 4
Simule l'expérience d'un joueur en lisant le code.
Évalue le fun factor, l'engagement, la courbe de difficulté et la rejouabilité.
Adapté au genre et au public cible.
"""

import json
from config import call_gemini_json, with_fallback
from genre_profile import GenreProfile, EvaluationResult
from logger import phase4_log

SYSTEM = """Tu es un playtester professionnel senior avec 15 ans d'expérience sur tous les genres de jeux.
Tu évalues les jeux avec l'œil d'un joueur exigeant : fun factor, profondeur, rejouabilité.
Tu es honnête et sévère — un jeu basique avec 1 ennemi et aucun boss mérite 4-5/10, pas 7/10.
Tu attends de vrais systèmes (boss phases, combos, power-ups, progression) pour donner 7+/10.
Tu réponds UNIQUEMENT en JSON valide."""


def run(code: str, genre_profile: GenreProfile, gdd: dict) -> EvaluationResult:
    phase4_log.agent_start("Playtester", f"Simulation joueur {genre_profile.public_cible}")

    from utils import extract_js_sample
    code_extrait = extract_js_sample(code, 20000)

    prompt = f"""Simule l'expérience d'un joueur sur ce jeu {genre_profile.genre_principal}.

CODE :
```html
{code_extrait}
```

PROFIL DU JEU :
- Genre : {genre_profile.genre_principal} / {genre_profile.sous_genre}
- Ton : {genre_profile.ton}
- Public cible : {genre_profile.public_cible}
- Core loop : {genre_profile.boucle_core}
- Titre : {gdd.get('titre', '?')}
- Concept : {gdd.get('concept', '')}

Tu joues ce jeu pendant 10-15 minutes. Évalue rigoureusement avec cette grille :

RUBRIQUE GÉNÉRALE :
- 0-3 : Injouable (crash, écran vide, aucune réponse aux inputs)
- 4-5 : Basique — core loop présente mais vide de contenu (1 ennemi, pas de boss, pas de systèmes)
- 6   : Correct — jouable, quelques features mais manque de profondeur ou de fun réel
- 7   : Bien — vrai gameplay avec progression, variété, quelques moments forts
- 8   : Très bien — fun immédiat, systèmes riches, on veut rejouer
- 9   : Excellent — mémorable, profond, présentable en démo professionnelle
- 10  : Exceptionnel (réserve pour les jeux vraiment remarquables — rare)

1. PREMIÈRE IMPRESSION (0-10) : Menu soigné ? Instructions claires ? Envie de jouer ?
2. FUN FACTOR (0-10) : Est-ce vraiment fun ? Éléments fun concrets ? Moments ennuyeux ?
3. PROFONDEUR SYSTÈMES (0-10) : Boss avec phases ? Types d'ennemis variés ? Power-ups ? Combo ? XP/progression ?
   → Un jeu sans aucun de ces systèmes ne peut pas dépasser 5/10 ici
4. ENGAGEMENT (0-10) : Envie de continuer après 5 min ? Qu'est-ce qui retient le joueur ?
5. DIFFICULTÉ (0-10) : Bien calibrée ? Pas d'insta-kill injuste ? Courbe progressive ?
6. GAME FEEL (0-10) : Contrôles réactifs ? Feedback immédiat ? Satisfaction des actions ?
   → Screen shake, particules, sons visuels = +points significatifs
7. REJOUABILITÉ (0-10) : Envie de rejouer ? Raisons concrètes (highscore, variété, progression) ?

Sois sévère : un jeu HTML5 arcade DOIT avoir du contenu pour mériter 7+/10.

Réponds en JSON :
{{
  "premiere_impression": {{
    "score": 7.0,
    "commentaire": "..."
  }},
  "fun_factor": {{
    "score": 6.5,
    "commentaire": "...",
    "elements_fun": ["...", "..."],
    "elements_ennuyeux": ["...", "..."]
  }},
  "profondeur_systemes": {{
    "score": 6.0,
    "systemes_presents": ["boss avec 2 phases", "3 types d'ennemis", "combo system", "..."],
    "systemes_manquants": ["power-ups", "progression joueur", "..."],
    "commentaire": "Évaluation de la richesse des systèmes de jeu"
  }},
  "engagement": {{
    "score": 7.0,
    "premiere_minute": "...",
    "apres_5_minutes": "...",
    "crochet_principal": "ce qui retient le joueur"
  }},
  "difficulte": {{
    "score": 6.5,
    "calibration": "trop facile / bien calibrée / trop difficile",
    "commentaire": "..."
  }},
  "game_feel": {{
    "score": 7.5,
    "reactivite_controles": "...",
    "satisfaction_actions": "...",
    "effets_juice": ["screen shake", "particules", "..."],
    "points_negatifs": ["...", "..."]
  }},
  "rejouabilite": {{
    "score": 7.0,
    "commentaire": "...",
    "raisons_de_rejouer": ["...", "..."]
  }},
  "issues": [
    {{
      "severite": "majeur",
      "description": "...",
      "suggestion": "..."
    }}
  ],
  "points_forts": ["...", "..."],
  "score_total": 7.0,
  "verdict_joueur": "Ce que dirait un joueur après avoir joué 5 minutes"
}}"""

    result = _call(prompt)
    return _parse(result, "Playtester")


def _parse(result: dict, agent_name: str) -> EvaluationResult:
    ev = EvaluationResult(agent_name=agent_name)

    # Score pondéré : fun, profondeur des systèmes et game feel sont prioritaires pour Arcade AI
    WEIGHTS = {
        "premiere_impression": 0.10,
        "fun_factor":          0.25,  # Fun immédiat — essentiel pour une démo
        "profondeur_systemes": 0.25,  # Profondeur — distingue un vrai jeu d'un prototype
        "engagement":          0.15,  # Rétention
        "difficulte":          0.05,
        "game_feel":           0.15,  # Juice factor — contrôles + feedback
        "rejouabilite":        0.05,
    }
    weighted_sum = sum(
        result.get(k, {}).get("score", 5.0) * w
        for k, w in WEIGHTS.items()
    )
    # score_total du LLM utilisé comme sanity check mais on garde notre formule pondérée
    llm_score = float(result.get("score_total", weighted_sum))
    ev.score = (weighted_sum * 0.6 + llm_score * 0.4)  # Blend pour stabilité
    ev.score = max(0.0, min(10.0, ev.score))
    ev.issues = result.get("issues", [])
    ev.points_forts = result.get("points_forts", [])
    ev.commentaire_global = result.get("verdict_joueur", "")

    ev.criteres = [
        {"nom": k, "score_obtenu": v.get("score", 5), "score_max": 10}
        for k, v in result.items()
        if isinstance(v, dict) and "score" in v and k != "issues"
    ]

    phase4_log.score("Playtester", ev.score)
    phase4_log.info(f"Verdict : {ev.commentaire_global[:80]}...")
    return ev


@with_fallback({
    "fun_factor": {"score": 5.0, "commentaire": "Analyse indisponible"},
    "score_total": 5.0,
    "issues": [], "points_forts": [],
    "verdict_joueur": "Analyse non disponible"
})
def _call(prompt: str) -> dict:
    return call_gemini_json(prompt, temperature=0.5, system_instruction=SYSTEM)

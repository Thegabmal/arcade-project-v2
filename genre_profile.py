"""
GenreProfile — objet central transmis à tous les agents.
Créé en Phase 1, enrichi en Phase 2, utilisé partout.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class Classification:
    genre_principal: str = ""
    sous_genre: str = ""
    ton: str = ""
    public_cible: str = ""
    style_visuel_attendu: str = ""
    type_gameplay: str = ""   # arcade, casual, hardcore, narrative, puzzle...
    confiance: float = 0.0
    raisonnement: str = ""


@dataclass
class Research:
    mecaniques_populaires: list = field(default_factory=list)
    mecaniques_tendance: list = field(default_factory=list)
    jeux_reference: list = field(default_factory=list)
    pieges_courants: list = field(default_factory=list)
    standards_visuels: list = field(default_factory=list)
    techniques_recommandees: list = field(default_factory=list)
    core_loop_typique: str = ""
    progression_typique: str = ""
    notes_techniques: str = ""


@dataclass
class GenreProfile:
    # Identité du genre
    genre_principal: str = ""
    sous_genre: str = ""
    ton: str = ""
    public_cible: str = ""
    type_gameplay: str = ""

    # Mécaniques
    mecaniques_obligatoires: list = field(default_factory=list)
    mecaniques_bonus: list = field(default_factory=list)
    mecaniques_a_eviter: list = field(default_factory=list)

    # Visuels & audio
    style_visuel: str = ""
    palette_recommandee: str = ""
    animations_cles: list = field(default_factory=list)
    effets_importants: list = field(default_factory=list)

    # Design
    boucle_core: str = ""
    structure_progression: str = ""
    courbe_difficulte: str = ""

    # Évaluation adaptive (critères générés dynamiquement)
    criteres_qc_technique: list = field(default_factory=list)
    criteres_qc_gameplay: list = field(default_factory=list)
    criteres_qc_visuel: list = field(default_factory=list)

    # Références
    jeux_reference: list = field(default_factory=list)
    pieges_courants: list = field(default_factory=list)
    notes_techniques: str = ""

    # Technologie de rendu
    technologie_rendu: str = "canvas2d"  # "canvas2d" ou "threejs"

    # Narratif
    is_narrative: bool = False  # True si le jeu a une histoire/quêtes/dialogues

    # Prompt enrichi (sortie finale de la Phase 1)
    prompt_utilisateur_original: str = ""
    prompt_enrichi: str = ""
    prompt_technique: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "GenreProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        """Résumé compact pour les logs."""
        return (
            f"Genre: {self.genre_principal} / {self.sous_genre} | "
            f"Ton: {self.ton} | Public: {self.public_cible} | "
            f"Gameplay: {self.type_gameplay}"
        )


@dataclass
class ModuleArchitecture:
    """Décomposition du jeu en modules JavaScript indépendants."""
    modules: list = field(default_factory=list)          # [{"nom", "description", "taille_max", "fonctions_exposees", "variables_requises", "variables_ecrites"}]
    variables_globales: list = field(default_factory=list)   # variables partagées
    variables_init: dict = field(default_factory=dict)        # {nom: expression_init}
    ordre_execution: list = field(default_factory=list)       # ordre des modules
    startup_code: str = "init(); requestAnimationFrame(gameLoop);"
    technologie: str = "canvas2d"                             # "canvas2d" ou "threejs"

    def get_module(self, nom: str) -> dict:
        for m in self.modules:
            if isinstance(m, dict) and m.get("nom") == nom:
                return m
        return {}

    def module_names(self) -> list:
        return [m.get("nom", "") for m in self.modules if isinstance(m, dict)]


@dataclass
class GeneratedModules:
    """Résultat de la génération modulaire."""
    modules: dict = field(default_factory=dict)          # {nom: js_code_string}
    architecture: ModuleArchitecture = field(default_factory=ModuleArchitecture)
    modules_valides: list = field(default_factory=list)
    modules_echoues: list = field(default_factory=list)
    modules_regeneres: dict = field(default_factory=dict)  # {nom: nb_tentatives}


@dataclass
class NarrativeContext:
    """Contexte narratif généré par agent_scenariste — Phase 2 optionnelle."""
    titre: str = ""
    synopsis: str = ""
    acte1: str = ""
    acte2: str = ""
    acte3: str = ""
    personnages: list = field(default_factory=list)   # [{nom, role, motivation, description}]
    quetes: list = field(default_factory=list)        # [{nom, objectif, recompense, dialogue_intro}]
    dialogues: list = field(default_factory=list)     # [{perso, texte, choix: [{texte, consequence}]}]
    lore: str = ""
    ton_narratif: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "NarrativeContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ConceptionContext:
    """Agrège les sorties de la Phase 2."""
    genre_profile: GenreProfile = field(default_factory=GenreProfile)
    gdd: dict = field(default_factory=dict)           # Game Design Document
    tech_specs: dict = field(default_factory=dict)    # Spécifications techniques
    ux_specs: dict = field(default_factory=dict)      # Guidelines UX/UI
    level_design: dict = field(default_factory=dict)  # Design des niveaux
    narrative_context: Optional[NarrativeContext] = None  # Sortie de agent_scenariste (si is_narrative)

    def to_context_string(self) -> str:
        """Retourne un contexte complet formaté pour le créateur."""
        parts = [
            "=== GENRE PROFILE ===",
            self.genre_profile.to_json(),
            "\n=== GAME DESIGN DOCUMENT ===",
            json.dumps(self.gdd, ensure_ascii=False, indent=2),
            "\n=== SPÉCIFICATIONS TECHNIQUES ===",
            json.dumps(self.tech_specs, ensure_ascii=False, indent=2),
            "\n=== GUIDELINES UX/UI ===",
            json.dumps(self.ux_specs, ensure_ascii=False, indent=2),
            "\n=== LEVEL DESIGN ===",
            json.dumps(self.level_design, ensure_ascii=False, indent=2),
        ]
        if self.narrative_context:
            parts.append("\n=== CONTEXTE NARRATIF ===")
            parts.append(self.narrative_context.to_json())
        return "\n".join(parts)


@dataclass
class EvaluationResult:
    """Résultat d'un agent d'évaluation."""
    agent_name: str = ""
    score: float = 0.0          # 0-10
    criteres: list = field(default_factory=list)   # [{nom, score, poids, commentaire}]
    issues: list = field(default_factory=list)     # [{severite, description, suggestion}]
    points_forts: list = field(default_factory=list)
    commentaire_global: str = ""


@dataclass
class EvaluationBundle:
    """Agrège tous les résultats d'évaluation de la Phase 4."""
    qc_technique: EvaluationResult = field(default_factory=EvaluationResult)
    qc_gameplay: EvaluationResult = field(default_factory=EvaluationResult)
    qc_visuel: EvaluationResult = field(default_factory=EvaluationResult)
    execution: EvaluationResult = field(default_factory=EvaluationResult)
    playtester: EvaluationResult = field(default_factory=EvaluationResult)
    anti_pattern: EvaluationResult = field(default_factory=EvaluationResult)
    benchmark: EvaluationResult = field(default_factory=EvaluationResult)

    def score_global(self) -> float:
        """Score pondéré global — calibré pour Arcade AI (démo professionnelle).

        Priorités :
        - Gameplay (profondeur + systèmes) : 25% — c'est ce qui impressionne une démo
        - Technique (code correct)         : 20% — fondamental, mais moins dominant maintenant
        - Visual (qualité visuelle)        : 15% — la démo doit être belle
        - Execution (test navigateur)      : 20% — validation que ça tourne (pipeline stabilisée)
        - Playtester (fun factor)          : 15% — est-ce qu'on a envie de rejouer ?
        - Anti-pattern                     :  3% — fusionné dans gameplay, poids réduit
        - Benchmark (comparaison genre)    :  2% — contextuel uniquement
        """
        weights = {
            "qc_technique": 0.20,
            "qc_gameplay":  0.25,
            "qc_visuel":    0.15,
            "execution":    0.20,
            "playtester":   0.15,
            "anti_pattern": 0.03,
            "benchmark":    0.02,
        }
        # Si le playtester est en fallback (quota épuisé), on l'exclut du calcul
        # et on redistribue son poids sur les autres agents pour ne pas pénaliser injustement.
        playtester_fallback = (
            self.playtester.score == 5.0
            and "non disponible" in self.playtester.commentaire_global.lower()
        )
        if playtester_fallback:
            excluded_weight = weights.pop("playtester")
            # Redistribuer proportionnellement sur les agents restants
            total_remaining = sum(weights.values())
            weights = {k: v + v / total_remaining * excluded_weight for k, v in weights.items()}

        total = 0.0
        for attr, w in weights.items():
            result = getattr(self, attr)
            total += result.score * w
        return round(total, 2)

    def has_blocking_issues(self) -> bool:
        """
        Retourne True si le jeu est probablement non jouable.
        C1 — Critères de blocage :
        - Score d'exécution < 5.0 (test headless raté — jeu probablement cassé)
        - Score technique < 5.5 (code trop défaillant)
        - Score d'exécution < 6.5 ET issue critique dans QC Technique
        """
        # C1 : seuils minimums par dimension
        if self.execution.score < 5.0:
            return True
        if self.qc_technique.score < 5.5:
            return True

        # Exécution passable (5.0–6.5) : bloquer si le QC technique signale un bug critique
        if self.execution.score < 6.5:
            for issue in self.qc_technique.issues:
                if issue.get("severite") == "critique":
                    return True

        return False

    def playability_score(self) -> float:
        """
        C3 : Score de jouabilité dédié — sépare "beau" de "jouable".
        Basé uniquement sur execution + technique + gameplay.
        Minimum requis pour sauvegarder : 6.0.
        """
        weights = {
            "execution":    0.40,
            "qc_technique": 0.30,
            "qc_gameplay":  0.30,
        }
        total = 0.0
        for attr, w in weights.items():
            result = getattr(self, attr)
            total += result.score * w
        return round(total, 2)

    def all_issues(self) -> list:
        """Toutes les issues de tous les agents, triées par sévérité."""
        issues = []
        severity_order = {"critique": 0, "majeur": 1, "mineur": 2}
        for attr in ["qc_technique", "qc_gameplay", "qc_visuel", "execution",
                     "playtester", "anti_pattern", "benchmark"]:
            result = getattr(self, attr)
            for issue in result.issues:
                issues.append({**issue, "source": attr})
        issues.sort(key=lambda x: severity_order.get(x.get("severite", "mineur"), 2))
        return issues

    def summary(self) -> str:
        scores = {
            "Technique": self.qc_technique.score,
            "Gameplay": self.qc_gameplay.score,
            "Visuel": self.qc_visuel.score,
            "Execution": self.execution.score,
            "Playtester": self.playtester.score,
            "Anti-pattern": self.anti_pattern.score,
            "Benchmark": self.benchmark.score,
        }
        lines = [f"  {k}: {v}/10" for k, v in scores.items()]
        lines.append(f"  GLOBAL: {self.score_global()}/10")
        return "\n".join(lines)

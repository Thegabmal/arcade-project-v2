"""
Calibration run — Day 1 of quality improvement plan.

Runs the 3 main LLM-based QC agents (technique, gameplay, visuel) on each
of the 10 model games and reports their scores.

Expected: model games should score 8.5-9.0. If they score below 8.0,
the evaluators are miscalibrated and need prompt adjustment before we
raise the pipeline thresholds.

Usage:
    python calibrate_evaluators.py
    python calibrate_evaluators.py --agent gameplay   # single agent only
    python calibrate_evaluators.py --dry-run          # print metadata only
"""

import os
import sys
import json
import argparse
import time
import statistics

MODELS_DIR = "jeux_modeles"

# Known metadata for each model game (genre + sous_genre used to build GenreProfile)
MODEL_META = {
    "shoot_em_up.html":   {"genre": "shmup",          "sous_genre": "vertical_shmup",          "titre": "Shoot Em Up Modèle"},
    "platformer.html":    {"genre": "platformer",      "sous_genre": "2d_platformer",           "titre": "Platformer Modèle"},
    "rpg_narratif.html":  {"genre": "rpg",             "sous_genre": "jrpg_narratif",           "titre": "RPG Narratif Modèle"},
    "puzzle_match3.html": {"genre": "puzzle",          "sous_genre": "match3",                  "titre": "Puzzle Match-3 Modèle"},
    "endless_runner.html":{"genre": "runner",          "sous_genre": "endless_runner",          "titre": "Endless Runner Modèle"},
    "breakout.html":      {"genre": "arcade",          "sous_genre": "breakout_casse_briques",  "titre": "Breakout Modèle"},
    "tower_defense.html": {"genre": "tower_defense",   "sous_genre": "grid_tower_defense",      "titre": "Tower Defense Modèle"},
    "visual_novel.html":  {"genre": "visual_novel",    "sous_genre": "sci_fi_vn",               "titre": "Visual Novel Modèle"},
    "dungeon_crawler.html":{"genre": "rpg",            "sous_genre": "dungeon_crawler_action",  "titre": "Dungeon Crawler Modèle"},
    "roguelite.html":     {"genre": "roguelite",       "sous_genre": "action_roguelite_meta",   "titre": "Roguelite Modèle"},
}

# Pipeline weights (from coordinateur.py)
WEIGHTS = {
    "technique":   0.20,
    "gameplay":    0.25,
    "visuel":      0.15,
    "execution":   0.20,
    "playtester":  0.15,
    "anti_pattern":0.03,
    "benchmark":   0.02,
}


def make_genre_profile(meta: dict) -> "GenreProfile":
    from genre_profile import GenreProfile
    gp = GenreProfile()
    gp.genre_principal = meta["genre"]
    gp.sous_genre = meta["sous_genre"]
    gp.ton = "arcade"
    gp.type_gameplay = "arcade"
    gp.boucle_core = f"Jeu de référence {meta['genre']}"
    gp.style_visuel = "pixel art, canvas 2D"
    gp.mecaniques_obligatoires = []
    gp.jeux_reference = []
    return gp


def run_technique(code: str, gp) -> float:
    from agents.phase4 import agent_qc_technique
    result = agent_qc_technique.run(code, gp)
    return result.score


def run_gameplay(code: str, gp, titre: str) -> tuple[float, float]:
    from agents.phase4 import agent_qc_gameplay
    gdd = {"titre": titre, "concept": f"Jeu modèle {gp.genre_principal}"}
    result = agent_qc_gameplay.run(code, gp, gdd)
    gp_score = result["gameplay"].score
    ap_score = result["anti_pattern"].score
    return gp_score, ap_score


def run_visuel(code: str, gp) -> float:
    from agents.phase4 import agent_qc_visuel
    result = agent_qc_visuel.run(code, gp)
    return result.score


def calibrate(agent_filter: str = "all", dry_run: bool = False):
    results = {}

    files = sorted(f for f in os.listdir(MODELS_DIR) if f.endswith(".html"))

    for fname in files:
        meta = MODEL_META.get(fname)
        if not meta:
            print(f"  SKIP {fname} (no metadata)")
            continue

        path = os.path.join(MODELS_DIR, fname)
        with open(path, encoding="utf-8") as f:
            code = f.read()

        gp = make_genre_profile(meta)
        scores = {}

        if dry_run:
            print(f"  DRY-RUN  {fname}  ({meta['genre']})")
            continue

        print(f"\n{'-'*60}")
        print(f"  {fname}  [{meta['genre']}]")

        try:
            if agent_filter in ("all", "technique"):
                t0 = time.time()
                scores["technique"] = run_technique(code, gp)
                print(f"    technique   {scores['technique']:.2f}  ({time.time()-t0:.1f}s)")
                time.sleep(3)  # respect API_DELAY

            if agent_filter in ("all", "gameplay"):
                t0 = time.time()
                gp_s, ap_s = run_gameplay(code, gp, meta["titre"])
                scores["gameplay"] = gp_s
                scores["anti_pattern"] = ap_s
                print(f"    gameplay    {scores['gameplay']:.2f}  ({time.time()-t0:.1f}s)")
                print(f"    anti_pattern {scores['anti_pattern']:.2f}")
                time.sleep(3)

            if agent_filter in ("all", "visuel"):
                t0 = time.time()
                scores["visuel"] = run_visuel(code, gp)
                print(f"    visuel      {scores['visuel']:.2f}  ({time.time()-t0:.1f}s)")
                time.sleep(3)

        except Exception as e:
            print(f"    ERROR: {e}")
            scores["error"] = str(e)

        if scores and "error" not in scores:
            # Partial weighted score (only agents run)
            weighted = sum(scores.get(k, 0) * WEIGHTS[k] for k in scores if k in WEIGHTS)
            weight_sum = sum(WEIGHTS[k] for k in scores if k in WEIGHTS)
            partial_avg = weighted / weight_sum if weight_sum else 0
            scores["partial_avg"] = partial_avg
            print(f"    ── partial avg: {partial_avg:.2f}")

        results[fname] = {"meta": meta, "scores": scores}

    if dry_run:
        print(f"\n[calibrate] Dry-run complete — {len(files)} games listed")
        return

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("CALIBRATION SUMMARY")
    print(f"{'='*60}")

    all_partial = []
    per_agent = {a: [] for a in ("technique", "gameplay", "visuel", "anti_pattern")}

    for fname, r in results.items():
        s = r["scores"]
        if "error" in s:
            continue
        pa = s.get("partial_avg")
        if pa:
            all_partial.append(pa)
        for a in per_agent:
            if a in s:
                per_agent[a].append(s[a])

        line = f"  {fname:28s}"
        for a in ("technique", "gameplay", "visuel"):
            v = s.get(a)
            marker = "  " if v is None else ("OK" if v >= 8.0 else "!!")
            line += f"  {a[:4]}={v:.2f}{marker}" if v is not None else f"  {a[:4]}=----"
        if "partial_avg" in s:
            line += f"  avg={s['partial_avg']:.2f}"
        print(line)

    print()
    for agent, vals in per_agent.items():
        if vals:
            avg = statistics.mean(vals)
            mn = min(vals)
            mx = max(vals)
            calibrated = "OK" if avg >= 8.0 else "MISCALIBRATED (too strict)" if avg < 7.0 else "MARGINAL"
            print(f"  {agent:14s}  avg={avg:.2f}  min={mn:.2f}  max={mx:.2f}  → {calibrated}")

    if all_partial:
        overall = statistics.mean(all_partial)
        print(f"\n  Overall partial avg across model games: {overall:.2f}")
        if overall >= 8.5:
            print("  [OK] Evaluators WELL CALIBRATED -- model games score correctly")
        elif overall >= 8.0:
            print("  [~] Evaluators ACCEPTABLE -- minor prompt tuning may help")
        elif overall >= 7.0:
            print("  [!] Evaluators SLIGHTLY STRICT -- consider softening criteria")
        else:
            print("  [!!] Evaluators MISCALIBRATED -- scoring model games too harshly, adjust before raising thresholds")

    # Save results to JSON for reference
    out = "calibration_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibrate QC evaluators against model games")
    parser.add_argument("--agent", default="all", choices=["all", "technique", "gameplay", "visuel"],
                        help="Which agent(s) to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="List games without calling API")
    args = parser.parse_args()
    calibrate(agent_filter=args.agent, dry_run=args.dry_run)

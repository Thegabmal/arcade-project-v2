"""
patch_bank.py — Banque de corrections validées inter-jeux.

Stocke les patches qui ont passé le guard exec (score non régressé) pour les réutiliser
sur les prochains jeux sans repasser par le LLM.

Format JSON :
{
  "signature": [
    {
      "issue_pattern": "sous-chaîne qui identifie le type d'issue",
      "search":  "extrait de code à remplacer (regex ou littéral)",
      "replace": "code corrigé",
      "genre":   ["platformer", "rpg", ...],
      "count":   3,          // nombre de fois appliqué avec succès
      "exec_delta": 1.5      // amélioration exec moyenne
    }
  ]
}
"""
import json
import os
import re
import threading
from pathlib import Path

_BANK_PATH = Path(__file__).parent / "patch_bank.json"
_lock = threading.Lock()


def _load() -> dict:
    if not _BANK_PATH.exists():
        return {}
    try:
        with open(_BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(bank: dict) -> None:
    with open(_BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)


def _signature(issue_desc: str) -> str:
    """Clé normalisée pour une issue (insensible à la casse, sans ponctuation)."""
    key = issue_desc.lower()
    key = re.sub(r"[^a-z0-9àâéèêëîïôùûüç\s]", " ", key)
    key = re.sub(r"\s+", "_", key.strip())
    return key[:80]


def store_patch(
    issue_desc: str,
    search: str,
    replace: str,
    genre: str,
    exec_delta: float = 0.0,
) -> None:
    """
    Enregistre une correction validée dans la banque.
    Appelé par agent_patcher après qu'un patch passe le guard exec.
    """
    if not search or search == replace:
        return
    sig = _signature(issue_desc)
    with _lock:
        bank = _load()
        entries = bank.setdefault(sig, [])
        # Chercher entrée existante identique
        for entry in entries:
            if entry.get("search") == search and entry.get("replace") == replace:
                entry["count"] = entry.get("count", 0) + 1
                entry["exec_delta"] = (entry.get("exec_delta", 0.0) * (entry["count"] - 1) + exec_delta) / entry["count"]
                if genre and genre not in entry.get("genre", []):
                    entry.setdefault("genre", []).append(genre)
                _save(bank)
                return
        # Nouvelle entrée
        entries.append({
            "issue_pattern": issue_desc[:120],
            "search": search,
            "replace": replace,
            "genre": [genre] if genre else [],
            "count": 1,
            "exec_delta": exec_delta,
        })
        # Garder les 10 meilleures entrées par signature (par count desc)
        bank[sig] = sorted(entries, key=lambda e: e.get("count", 0), reverse=True)[:10]
        _save(bank)


def get_patches_for_issue(issue_desc: str, genre: str = "", min_count: int = 1) -> list[dict]:
    """
    Retourne les patches connus pour une issue donnée, triés par count desc.
    Filtre optionnel par genre (retourne aussi les patches tous genres).
    """
    sig = _signature(issue_desc)
    bank = _load()
    entries = bank.get(sig, [])
    # Filtrer par count minimum
    entries = [e for e in entries if e.get("count", 0) >= min_count]
    # Trier : genre correspondant en premier, puis tous
    if genre:
        entries = sorted(
            entries,
            key=lambda e: (genre not in e.get("genre", []), -e.get("count", 0))
        )
    return entries


def try_apply_known_patch(script: str, issue_desc: str, genre: str = "") -> tuple[str, bool]:
    """
    Tente d'appliquer un patch connu depuis la banque sur le script.
    Retourne (script_patché, appliqué).
    Essaie les patches par ordre de count desc.
    """
    patches = get_patches_for_issue(issue_desc, genre=genre, min_count=2)
    for patch in patches:
        search = patch.get("search", "")
        replace = patch.get("replace", "")
        if not search or search not in script:
            continue
        patched = script.replace(search, replace, 1)
        if patched != script:
            return patched, True
    return script, False


def stats() -> dict:
    """Statistiques rapides de la banque."""
    bank = _load()
    total_sigs = len(bank)
    total_entries = sum(len(v) for v in bank.values())
    total_applications = sum(e.get("count", 0) for v in bank.values() for e in v)
    return {
        "signatures": total_sigs,
        "entries": total_entries,
        "total_applications": total_applications,
    }

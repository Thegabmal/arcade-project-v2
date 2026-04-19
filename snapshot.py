"""
snapshot.py — Système de snapshots de la pipeline.

Usage :
    python snapshot.py save "description-courte"    # commit + tag stable/vN
    python snapshot.py list                          # liste les snapshots
    python snapshot.py restore stable/v3             # restaure un snapshot
    python snapshot.py diff stable/v2                # diff vs snapshot
"""
import subprocess
import sys
import re


def _run(cmd: list, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check,
                          cwd="C:/Users/gabin/Desktop/arcade-project-v2")


def _next_tag() -> str:
    result = _run(['git', 'tag', '-l', 'stable/v*'], check=False)
    tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
    nums = []
    for t in tags:
        m = re.match(r'stable/v(\d+)', t)
        if m:
            nums.append(int(m.group(1)))
    return f"stable/v{max(nums) + 1 if nums else 1}"


def cmd_save(description: str = ""):
    """Commit les fichiers pipeline + crée un tag stable/vN."""
    # Stage tous les fichiers Python + config (pas les jeux ni la DB)
    pipeline_patterns = [
        'agents/', 'coordinateur.py', 'code_validator.py', 'js_syntax_checker.py',
        'config.py', 'genre_profile.py', 'logger.py', 'rag.py', 'app.py',
        'memory.py', 'patch_bank.py', 'snapshot.py', '.gitignore', 'CLAUDE.md',
    ]
    for p in pipeline_patterns:
        _run(['git', 'add', '--', p], check=False)

    tag = _next_tag()
    msg = f"{tag}" + (f" — {description}" if description else "")

    result = _run(['git', 'commit', '-m', msg], check=False)
    if 'nothing to commit' in result.stdout + result.stderr:
        print(f"[snapshot] Aucun changement — pas de commit. Tag actuel conservé.")
        return

    _run(['git', 'tag', tag])
    print(f"[snapshot] OK Snapshot cree : {tag}")
    if description:
        print(f"[snapshot]   Description : {description}")


def cmd_list():
    """Liste tous les snapshots stables."""
    result = _run(['git', 'tag', '-l', 'stable/v*', '--sort=-version:refname'], check=False)
    tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
    if not tags:
        print("[snapshot] Aucun snapshot trouvé.")
        return
    print(f"[snapshot] {len(tags)} snapshot(s) :")
    for tag in tags:
        log = _run(['git', 'log', '-1', '--format=%ci %s', tag], check=False)
        print(f"  {tag}  {log.stdout.strip()}")


def cmd_restore(tag: str):
    """Restaure les fichiers pipeline depuis un tag (sans toucher jeux_sauvegardes/)."""
    # Vérifier que le tag existe
    result = _run(['git', 'tag', '-l', tag], check=False)
    if tag not in result.stdout:
        print(f"[snapshot] Erreur : tag '{tag}' introuvable. Utilise 'python snapshot.py list'.")
        return
    # Checkout uniquement les fichiers pipeline (pas tout le working tree)
    _run(['git', 'checkout', tag, '--',
          'agents/', 'coordinateur.py', 'code_validator.py', 'js_syntax_checker.py',
          'config.py', 'genre_profile.py', 'logger.py', 'rag.py', 'app.py',
          'memory.py', 'patch_bank.py', 'snapshot.py'], check=False)
    print(f"[snapshot] ✓ Restauration depuis {tag} — fichiers pipeline remis à l'état du snapshot.")
    print(f"[snapshot]   Les jeux sauvegardés et la DB RAG sont inchangés.")


def cmd_diff(tag: str):
    """Affiche les différences entre le code actuel et un snapshot."""
    result = _run(['git', 'diff', tag, '--stat',
                   '--', 'agents/', 'coordinateur.py', 'code_validator.py',
                   'config.py', 'app.py'], check=False)
    if result.stdout.strip():
        print(result.stdout)
    else:
        print(f"[snapshot] Aucune différence avec {tag}.")


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] == 'help':
        print(__doc__)
    elif args[0] == 'save':
        cmd_save(' '.join(args[1:]))
    elif args[0] == 'list':
        cmd_list()
    elif args[0] == 'restore' and len(args) >= 2:
        cmd_restore(args[1])
    elif args[0] == 'diff' and len(args) >= 2:
        cmd_diff(args[1])
    else:
        print(__doc__)

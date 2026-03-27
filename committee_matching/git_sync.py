from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


def git_add_if_available(root_dir: str | Path, paths: Iterable[str]) -> str:
    root = Path(root_dir)
    git_dir = root / '.git'
    if not git_dir.exists():
        return 'git repository not found; skipped git add'

    cmd = ['git', 'add', *paths]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        return f'git add failed: {result.stderr.strip()}'
    return 'git add completed'

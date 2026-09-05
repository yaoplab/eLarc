"""Exécution de sous-processus commune : timeout, UTF-8, encodage (pattern lint_all.py)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class CollectorError(Exception):
    """Erreur technique d'un collecteur (timeout, crash, sortie illisible)."""


def run_subprocess(cmd: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            env=env,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CollectorError(f"timeout {timeout}s : {' '.join(cmd)}") from exc


def module_of(file: str, app: str, root: Path) -> str | None:
    """Normalise un chemin de fichier en module relatif à la racine, séparateur '/'."""
    if not file:
        return None
    p = str(file).replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    # Chemin absolu -> relatif à la racine
    if ":/" in p[:3] or p.startswith("/"):
        try:
            p = str(Path(file).resolve().relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            return None
    # Relatif au projet (pas encore préfixé par le repo) -> préfixe le repo
    if not p.startswith(app + "/"):
        p = f"{app}/{p}"
    return p

"""Collecteur : build PyInstaller d'une app cible (sous-processus, cwd=repo).

Un échec produit un candidat source='larcforge:build' (visible dans le
registre et l'IHM) ; un succès ne produit rien — execute_build() résout
alors les échecs build open de l'app.

L'entrée est un launcher temporaire (les `python -m App` utilisent des
imports relatifs, invalides comme script PyInstaller). Les sorties vont
dans {racine}/dist/{app}/, cohérent avec dist/Blado existant.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from ..models import IssueCandidate
from .base import CollectorError, run_subprocess

# Cibles supportées en v1. LarcForge : l'IHM est importée paresseusement
# (cmd_ui) — PyInstaller ne la verrait pas dans l'analyse statique de
# cli.py ; les modules UI sont donc énumérés en hidden-imports.
BUILD_TARGETS: dict[str, dict] = {
    "LarcForge": {
        "pkg": "larcforge",
        "hiddenimports": [
            "larcforge.ui.app",
            "larcforge.ui.main_window",
            "larcforge.ui.workers",
            "larcforge.ui.profiles",
            "larcforge.ui.db",
            "larcforge.ui.panels.common",
            "larcforge.ui.panels.dashboard_panel",
            "larcforge.ui.panels.run_panel",
            "larcforge.ui.panels.issues_panel",
            "larcforge.ui.panels.config_panel",
            "larcforge.ui.panels.help_panel",
        ],
    },
}

# Les autres apps (LarcSuperviseur, LarcSecretaire, …) arrivent aux étapes
# suivantes : leurs entrées `python -m App` et leurs données spécifiques
# (photos, icônes, SQLite) demandent des fichiers .spec dédiés.


def supported_apps() -> list[str]:
    return sorted(BUILD_TARGETS)


def pyinstaller_available(python: str) -> bool:
    """PyInstaller présent dans l'interpréteur qui exécute LarcForge ?"""
    return importlib.util.find_spec("PyInstaller") is not None


def _launcher_script(pkg: str, temp_dir: Path) -> Path:
    """Script d'entrée PyInstaller : importe le package comme un module."""
    path = temp_dir / "larcforge_entry.py"
    path.write_text(
        f"from {pkg}.cli import main\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    return path


def collect(root: Path, python: str, app: str = "LarcForge",
            onefile: bool = False,
            timeout: int = 900) -> tuple[list[IssueCandidate], list[str], dict]:
    """Lance PyInstaller sur l'app. Retourne (candidats, erreurs, infos).

    infos : {app, out (chemin relatif), size, onefile, rc} — rempli même en
    cas d'échec (out/size absents alors).
    """
    info0 = {"app": app, "onefile": onefile}
    target = BUILD_TARGETS.get(app)
    if target is None:
        msg = (f"[build/{app}] app non supportée en v1 "
               f"({', '.join(supported_apps())})")
        return [], [msg], info0
    proot = root / app
    if not proot.is_dir():
        return [], [f"[build/{app}] dossier introuvable : {proot}"], info0
    if not pyinstaller_available(python):
        return [], ["[build] PyInstaller absent — installez : "
                    "pip install pyinstaller"], info0

    temp_dir = Path(tempfile.mkdtemp(prefix="larcforge_build_"))
    launcher = _launcher_script(target["pkg"], temp_dir)
    out_dir = root / "dist" / app
    cmd = [
        python, "-m", "PyInstaller", "--noconfirm",
        "--name", app,
        "--distpath", str(out_dir),
        "--workpath", str(temp_dir / "work"),
        "--specpath", str(temp_dir),
        "--log-level", "WARN",
    ]
    if onefile:
        cmd.append("--onefile")
    for mod in target["hiddenimports"]:
        cmd += ["--hidden-import", mod]
    cmd.append(str(launcher))

    try:
        result = run_subprocess(cmd, cwd=proot, timeout=timeout)
    except CollectorError as exc:
        return [], [f"[build/{app}] {exc}"], {"app": app, "onefile": onefile}

    # PyInstaller 6 : onedir → distpath/{app}/{app}.exe (+ _internal) ;
    # --onefile → distpath/{app}.exe. Les deux layouts sont vérifiés.
    exe_onedir = out_dir / app / f"{app}.exe"
    exe_onefile = out_dir / f"{app}.exe"
    exe = exe_onedir if exe_onedir.is_file() else exe_onefile
    info = {
        "app": app,
        "onefile": onefile,
        "rc": result.returncode,
        "out": str(exe.relative_to(root)) if exe.is_file() else None,
        "size": exe.stat().st_size if exe.is_file() else None,
    }
    if result.returncode != 0 or not exe.is_file():
        detail = "\n".join(result.stderr.splitlines()[-15:]) or result.stdout[-2000:]
        cand = IssueCandidate(
            source="larcforge:build",
            app_name=app,
            module=f"build/{app}",
            func="pyinstaller",
            rule="build",
            message=f"Échec du build PyInstaller ({app}) — voir le détail",
            traceback=detail[:3000] or None,
            context={"rc": result.returncode},
        )
        return [cand], [], info
    return [], [], info

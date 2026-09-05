"""Collecteur : pytest des repos avec tests/, parse le junitxml.

Marker 'integration' exclu par défaut (requiert une vraie PostgreSQL).
pytest rc≠0 avec junit exploitable = résultat ; sans junit (collection error) =
erreur technique.
"""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ..models import IssueCandidate
from .base import CollectorError, run_subprocess

DEFAULT_PROJECTS = ["LarcCommon", "LarcSuperviseur", "LarcProf", "LarcPhibuilder"]


def _parse_junit(junit: Path, project: str) -> list[IssueCandidate]:
    tree = ET.parse(junit)
    cands: list[IssueCandidate] = []
    for tc in tree.iter("testcase"):
        failure = tc.find("failure")
        error = tc.find("error")
        if failure is None and error is None:
            continue
        node = failure if failure is not None else error
        text = (node.text or "").strip()
        msg = (node.get("message") or "").strip() or text.splitlines()[0] if text else ""
        name = tc.get("name") or ""
        classname = tc.get("classname") or ""
        module = classname.replace(".", "/") if classname else None
        cands.append(IssueCandidate(
            source="pytest",
            app_name=project,
            module=module,
            func=name,
            rule=name,
            message=msg[:500] or "Test en échec",
            level="ERROR",
        ))
    return cands


def collect(root: Path, python: str, projects: list[str] | None = None,
            include_integration: bool = False,
            timeout: int = 900) -> tuple[list[IssueCandidate], list[str]]:
    cands: list[IssueCandidate] = []
    errors: list[str] = []
    for project in projects or DEFAULT_PROJECTS:
        proot = root / project
        if not (proot / "tests").is_dir():
            continue
        junit = Path(tempfile.gettempdir()) / f"larcforge_junit_{project}.xml"
        cmd = [python, "-m", "pytest", "tests",
               "--junitxml", str(junit), "--rootdir", str(proot), "-q"]
        if not include_integration:
            cmd += ["-m", "not integration"]
        try:
            result = run_subprocess(cmd, cwd=proot, timeout=timeout)
        except CollectorError as exc:
            errors.append(f"[pytest/{project}] {exc}")
            continue
        if not junit.is_file():
            errors.append(
                f"[pytest/{project}] pas de junit.xml (collection error ? rc={result.returncode})")
            continue
        try:
            cands.extend(_parse_junit(junit, project))
        except ET.ParseError:
            errors.append(f"[pytest/{project}] junit.xml illisible")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[pytest/{project}] parse junit : {exc}")
    return cands, errors

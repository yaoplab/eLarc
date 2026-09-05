"""Vérifie que TOUS les clients peuvent importer Larcommon.

LINTER_META = {
    "key": "LARCCOMMON",
    "label": "Larcommon Cross-Client Import Check",
    "category": "integration",
    "description": "Vérifie que chaque client peut importer Larcommon sans erreur"
}
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass

# Clients qui dépendent de Larcommon
CLIENTS = [
    "LarcProf",
    "LarcSecretaire",
    "LarcRH",
    "LarcCompta",
    "LarcSuperviseur",
    "LarcHub",
    "LarcConfig",
]


@dataclass
class Candidate:
    """Compatible avec runner.py."""
    app_name: str
    module: str
    func: str
    message: str
    rule: str = "LARCCOMMON"
    source: str = "linter"

    def signature(self) -> str:
        return f"{self.app_name}|{self.module}|{self.message}"


def collect(root: Path, python: str, projects: list[str], timeout: int):
    """Collecte les erreurs import cross-client.

    Retourne : (candidates, errors)
    """
    candidates = []
    errors = []

    # Seulement vérifier si LarcCommon est dans les projets
    if "LarcCommon" not in projects:
        return candidates, errors

    print("🔍 Cross-Client Validation: Larcommon → tous les clients")

    for client in CLIENTS:
        client_path = root / client
        if not client_path.exists():
            continue

        print(f"  Testant {client}...", end=" ", flush=True)

        try:
            # Test d'import
            result = subprocess.run(
                [
                    python, "-c",
                    f"import sys; sys.path.insert(0, '{root}'); from larccommon import *"
                ],
                cwd=str(client_path),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                # Import échoué
                error_msg = result.stderr.strip().split('\n')[-1]  # Dernière ligne

                print(f"❌ FAIL")
                candidates.append(Candidate(
                    app_name=client,
                    module="__init__.py",
                    func="import",
                    message=f"Cannot import Larcommon: {error_msg[:80]}",
                    rule="LARCCOMMON"
                ))
            else:
                print(f"✅ OK")

        except subprocess.TimeoutExpired:
            print(f"⏱️ TIMEOUT")
            errors.append(f"[{client}] Import timeout (>{timeout}s)")
        except Exception as e:
            print(f"❌ ERROR")
            errors.append(f"[{client}] {str(e)[:100]}")

    return candidates, errors


if __name__ == "__main__":
    # Test local
    root = Path(__file__).parent.parent
    cands, errs = collect(root, sys.executable, ["LarcCommon"], 30)

    print(f"\nRésultat: {len(cands)} issues, {len(errs)} erreurs")
    for c in cands:
        print(f"  ❌ {c.app_name}: {c.message}")

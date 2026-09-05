"""Point d'entrée racine : permet `python -m LarcForge` (comme les autres applis Larc).

Relais vers le paquet installé `larcforge`. L'exécution réelle est dans
`larcforge/__main__.py` (`python -m larcforge`).
"""

import sys

from larcforge.cli import main

if __name__ == "__main__":
    sys.exit(main())
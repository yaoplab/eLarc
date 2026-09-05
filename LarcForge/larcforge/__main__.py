"""Point d'entrée : python -m larcforge <sous-commande> [options]."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

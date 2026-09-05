"""Point d'entrée : python -m LarcDocs"""
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
_common = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'LarcCommon'))
if os.path.isdir(_common) and _common not in sys.path:
    sys.path.insert(0, _common)
from LarcDocs.main import main
if __name__ == '__main__':
    main()


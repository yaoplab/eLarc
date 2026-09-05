import os
from larccommon.logger import log, set_log_to_file, get_log_path, set_log_filename

# Surcharger le chemin du fichier log pour eLarcProfPy
_here = os.path.dirname(os.path.abspath(__file__))
set_log_filename(os.path.normpath(os.path.join(_here, '..', 'elarc.log')))

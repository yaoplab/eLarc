import os
import shutil
import urllib.request

from PySide6.QtGui import QImage, QImageReader

from .app_config import app_config
from .logger import log
from .session import ConnMode, session

_SUPABASE_REF = "crvyxfsuvwqxzlhsfbwq"
_STORAGE_URL = f"https://{_SUPABASE_REF}.supabase.co/storage/v1/object/public/student-photos"

PHOTO_SIZE = 500  # Dimensions obligatoires 500x500


def _intranet_path(sid: int) -> str:
    return os.path.join(app_config.get("photos_dir"), f"{sid}.png")


def _cache_path(sid: int) -> str:
    return os.path.join(app_config.get("photos_cache_dir"), f"{sid}.png")


def get_photo_path(sid: int) -> str:
    """Renvoie un chemin valide vers la photo de l'élève.

    Priorité : fichier local (dossier partagé intranet) → cache → cloud.
    - Intranet : chemin local direct (dossier partagé LarcSuperviseur)
    - Cloud    : télécharge depuis Supabase Storage dans le cache local
    """
    local = _intranet_path(sid)
    if os.path.isfile(local):
        return local

    cache = _cache_path(sid)
    if os.path.isfile(cache):
        return cache

    if session.conn_mode == ConnMode.INTRANET:
        return local

    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        url = f"{_STORAGE_URL}/{sid}.png"
        urllib.request.urlretrieve(url, cache)
        log(f"Photos: telecharge {sid}.png depuis le cloud")
        return cache
    except Exception as e:
        log(f"Photos: echec telechargement {sid}.png ({e})")
        return local


def validate_photo(source_path: str) -> tuple[bool, str]:
    """Valide qu'une photo est 500x500 et peut etre lue.

    Returns:
        (ok, message_erreur)
    """
    reader = QImageReader(source_path)
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        return False, f"Format d'image non reconnu : {reader.errorString()}"

    w, h = img.width(), img.height()
    if w != PHOTO_SIZE or h != PHOTO_SIZE:
        return False, f"L'image doit faire exactement {PHOTO_SIZE}x{PHOTO_SIZE}px (reçue : {w}x{h})"

    return True, ""


def save_photo(sid: int, source_path: str) -> str:
    """Sauvegarde une photo 500x500 PNG depuis un fichier source.

    - Valide que l'image est 500x500
    - Convertit en PNG si necessaire
    - Sauvegarde dans le dossier intranet ET le cache
    - Sauvegarde AUSSI dans le dossier LarcCommon/media/ (utilise par StudentCard)
    - Fichier nomme <sid>.png
    Retourne le chemin de destination (intranet).
    """
    ok, err = validate_photo(source_path)
    if not ok:
        raise ValueError(err)

    dest = _intranet_path(sid)
    cache = _cache_path(sid)

    # Chemin LarcCommon (utilise par larccommon.photos.get_photo_path → StudentCard)
    _larc_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'LarcCommon'))
    _larc_media = os.path.join(_larc_root, 'media')
    _larc_dest = os.path.join(_larc_media, f'{sid}.png')
    _larc_cache = os.path.join(_larc_media, 'cache', f'{sid}.png')

    try:
        img = QImage(source_path)
        if img.format() != QImage.Format_ARGB32:
            img = img.convertToFormat(QImage.Format_ARGB32)

        for p in [dest, cache, _larc_dest, _larc_cache]:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if not img.save(p, "PNG"):
                raise IOError(f"Echec ecriture {p}")

        log(f"Photos: sauvegarde {sid}.png (500x500) depuis {source_path}")
    except Exception as e:
        log(f"Photos: echec sauvegarde {sid}.png ({e})")
        raise
    return dest

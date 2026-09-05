import os

from larccommon.session import ConnMode, session


class FileResolver:
    """Résout un chemin relatif vers un chemin local ou cloud selon le mode de connexion.

    Usage:
        resolver = FileResolver(base_dir="C:/Projets/LarcSecretaire/data/students",
                                cloud_root="https://cloud.arc-en-ciel.org/students")
        local = resolver.local_path("123/doc.pdf")
        url   = resolver.cloud_url("123/doc.pdf")
    """

    def __init__(self, base_dir: str = "", cloud_root: str = ""):
        self._base_dir = base_dir
        self._cloud_root = cloud_root

    def local_path(self, relative_path: str) -> str:
        if self._base_dir:
            return os.path.normpath(os.path.join(self._base_dir, relative_path))
        return relative_path

    def cloud_url(self, relative_path: str) -> str:
        if self._cloud_root:
            sep = "/" if not self._cloud_root.endswith("/") else ""
            return f"{self._cloud_root}{sep}{relative_path.replace(os.sep, '/')}"
        return relative_path

    def resolve(self, relative_path: str) -> str:
        """Retourne le chemin accessible selon le mode de connexion."""
        if session.conn_mode in (ConnMode.INTRANET, ConnMode.OFFLINE):
            return self.local_path(relative_path)
        return self.cloud_url(relative_path)

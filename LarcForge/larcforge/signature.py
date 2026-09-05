"""Signature d'une issue — empreinte sha256 pour le dédoublonnage.

Règles :
- line EXCLUE du hash (un décalage de ligne n'est pas un nouveau bug).
- level/traceback/context exclus (une ERROR qui devient WARNING reste le même bug).
- message BRUT conservé en colonne ; seule l'entrée du hash est normalisée.
- Préfixe 'v1|' pour faire évoluer le schéma sans collision.
"""

from __future__ import annotations

import hashlib
import re


def norm(s: str | None) -> str:
    """Normalisation pour l'entrée du hash UNIQUEMENT."""
    s = (s or "").strip().replace("\\", "/")
    s = re.sub(r"\s+", " ", s)          # collapse espaces/retours
    s = re.sub(r"\d{3,}", "#N", s)      # neutralise lignes/horodatages
    return s


def signature(source: str, app_name: str, module: str | None,
              func: str | None, message: str | None) -> str:
    """Empreinte déterministe d'une issue."""
    payload = "v1|" + "|".join([source, app_name, norm(module), norm(func), norm(message)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

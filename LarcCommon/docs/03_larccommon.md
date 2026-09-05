
# larccommon — Infrastructure partagée Larc

## Modules

### database.py — Connexion PostgreSQL

```python
from larccommon.database import db

db.connect_intranet()   # → bool (connexion Intranet)
db.connect_cloud()      # → bool (connexion Supabase Cloud)
db.server_conn          # → connection psycopg2 active
db.mode                 # → DBMode (NONE / INTRANET / CLOUD)
```

Lit les paramètres depuis `config.ini` (via `config_loader.find_cfg()`).
Deux profils : `IntranetDatabase` et `SupabaseDatabase`.

### auth.py — Authentification

- `OAuth2Manager` : OAuth2 PKCE avec Google (Cloud)
- Auth locale Intranet : email + SHA-256 (Intranet)
- Rate limiting : 5 tentatives → 30s lockout

### session.py — Session applicative

```python
from larccommon.session import session

session.conn_mode       # → ConnMode (INTRANET / CLOUD / OFFLINE)
session.is_authenticated
session.role            # → UserRole (SUPERVISEUR / COORD / ADMIN)
session.user_id
session.full_name
```

### theme.py — Gestionnaire de thèmes

```python
from larccommon.theme import theme_manager

theme_manager.names()          # → [(key, label), ...]
theme_manager.set_active("ocean")
theme_manager.palette.primary  # → "#0D47A1"
theme_manager.font_size(14)    # → int
theme_manager.bind(app)        # Applique le QSS global
```

Intègre `PhiBuilder` pour la génération QSS. Combine QSS M3 global
+ QSS personnalisé de l'application.

### l10n/ — Traductions multilingues

```python
from larccommon.l10n import _

_( "common.button.save" )      # → "Enregistrer" / "Save"
_( "dashboard.title" )          # → clé si non trouvée

from larccommon.l10n import Translator
tr = Translator("en")
tr.load_dir("mon_app/l10n")     # Fusionne avec les traductions de l'app
```

Format JSON avec clés contextuelles (`module.composant.action`).

### logger.py — Journalisation

```python
from larccommon.logger import log

log("Message")                  # Écrit dans superviseur.log + stdout
set_log_to_file(False)          # Désactiver fichier
get_log_path()                  # Chemin du fichier log
```

### network.py — Détection réseau

```python
from larccommon.network import detect_network

intranet_ok, internet_ok = detect_network()
# Ping 192.168.2.90 (Intranet) + google.com (Internet)
```

### photos.py — Gestion photos élèves

```python
from larccommon.photos import get_photo_path, ensure_cached, PhotoPreloader

path = get_photo_path(student_id)       # → chemin photo (cache ou intranet)
ensure_cached(student_id)               # → bool
preloader = PhotoPreloader(student_ids)
preloader.start()                       # Précharge en QThread
```

### event_helpers.py — Helpers événements

```python
from larccommon.event_helpers import event_icon, event_color

icon = event_icon("absence")            # → "🚪"
color = event_color("violence")         # → "#C62828"
```

### config_loader.py — Localisation config.ini

```python
from larccommon.config_loader import find_cfg

path = find_cfg()   # Cherche dans :
# 1. ../config.ini (racine de l'app)
# 2. ../../eLarcProfPy/config.ini (projet frère)
```

### app_config.py — Configuration DB

```python
from larccommon.app_config import app_config

app_config.get("photos_dir")    # → chemin dossier photos
# Charge depuis la table larcauth_config (PostgreSQL)
```

---
name: auth-pin
description: Authentification par code PIN hors connexion — LarcProf, SQLite elarc.db, AuthManager.auth_pin()
category: infrastructure
trigger: PIN, hors connexion, offline, session_cache, LarcProf
---

# Auth PIN (Offline)

Utilisé par **LarcProf** pour l'accès hors connexion (enseignants sans réseau intranet).

```python
from larccommon.auth import AuthManager
ok, auth_result, error = AuthManager.auth_pin(email, pin, local_conn)
# PIN 4-8 chiffres, credentials dans SQLite elarc.db (session_cache)
```

Cycle de vie : création du PIN au premier login hors connexion → stockage SQLite → vérification locale. Voir `auth-review` pour la check-list complète.

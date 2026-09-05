---
name: auth-oauth2
description: Authentification Google OAuth2 PKCE — configurable, sans domaine restreint par défaut
category: infrastructure
trigger: OAuth2, Google, PKCE, auth_cloud, cloud login
---

# Auth OAuth2 PKCE

## Configuration (`LarcCommon/config.ini`)

```ini
[OAuth2]
ClientID=xxx.apps.googleusercontent.com
ClientSecret=GOCSPX-xxx
HostedDomain=  # optionnel
```

## Flux

```python
from larccommon.auth import OAuth2Manager
ok, auth_result, error = OAuth2Manager.authenticate()
# Ouvre le navigateur → callback localhost:8765 → échange token
# → vérifie larcauth_aecuser (email + is_active) → AuthResult
```

## Vérification

- `lint_auth_checker.py` ; check-list complète dans `auth-review` (ClientID/Secret, callback URI, timeout 120s).

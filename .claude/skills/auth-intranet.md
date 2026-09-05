---
name: auth-intranet
description: Authentification intranet Larc — SHA-256, table larcauth_aecuser, AuthManager.auth_intranet(), hiérarchie des rôles
category: infrastructure
trigger: login, auth, authentification, connexion, mot de passe, password, SHA-256, AuthManager, intranet
---

# Auth Intranet

## Flux

```python
from larccommon.auth import AuthManager
ok, auth_result, error = AuthManager.auth_intranet(email, password)
# auth_result: AuthResult(user_id, email, full_name, role, term_id, term_label, fk_language)
```

## Règles

| # | Règle |
|---|---|
| A1 | Mot de passe hashé SHA-256 (hex) |
| A2 | Table `larcauth_aecuser` : email (UNIQUE), password_hash, last_name/first_name, flags type_director / type_coordonator / type_supervisor / type_secretary |
| A3 | `is_active = TRUE` requis pour se connecter |
| A4 | Hiérarchie des rôles : ADMIN > COORD > SECR > SUPERVISEUR > PROF |

## Résolution du rôle

Le rôle vient des flags de la table (`type_director` → ADMIN, `type_coordonator` → COORD, `type_secretary` → SECR, `type_supervisor` → SUPERVISEUR), pas d'un champ `role` unique.

## Vérification

- `lint_auth_checker.py` ; connexion `db.connect_intranet()` testée dans `auth-review`.

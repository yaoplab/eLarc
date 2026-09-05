---
name: auth-review
description: Audit de l'authentification — OAuth2 Google, PostgreSQL local, PIN hors connexion
category: quality
trigger: audit auth, vérifie auth, check auth, revue auth, authentification, login, OAuth
---

# Auth Review — Audit Authentification Larc

Vérifier la configuration et la sécurité des 3 modes d'authentification.

## Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_auth_checker.py
python D:/projets/scripts/lint_db_checker.py
```

2. Vérifier la configuration :
```bash
grep -A2 "\[OAuth2\]" LarcCommon/config.ini
grep -A5 "\[IntranetDatabase\]" LarcCommon/config.ini
```

3. Tester la connexion :
```bash
python -c "from larccommon.database import db; print('INTRANET OK' if db.connect_intranet() else 'INTRANET FAIL')"
```

## Checklist

### OAuth2
- [ ] [OAuth2] ClientID et ClientSecret dans config.ini
- [ ] URI http://localhost:8765/callback autorisée Google Console
- [ ] Domaine arc-en-ciel.org (hd)
- [ ] Timeout 120s
- [ ] Utilisateur dans larcauth_aecuser
- [ ] Flag role non NULL

### Intranet
- [ ] [IntranetDatabase] Host/Port/DB/User/Pass dans config.ini
- [ ] db.connect_intranet() → True
- [ ] Password hash = SHA-256
- [ ] session.conn_mode = ConnMode.INTRANET

### PIN
- [ ] session_cache.db existe
- [ ] Premier login Intranet/OAuth2 AVANT PIN
- [ ] PIN = 4-8 chiffres, isdigit()
- [ ] pin_hash = SHA-256
- [ ] session.conn_mode = ConnMode.OFFLINE

## Skills de référence

- `auth-oauth2` — Google OAuth2 PKCE
- `auth-intranet` — PostgreSQL local SHA-256
- `auth-pin` — PIN hors connexion
- `database-operations` — connexions DB

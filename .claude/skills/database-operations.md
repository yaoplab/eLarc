---
name: database-operations
description: Opérations base de données Larc/Blado — singleton db, connexions intranet/cloud, autocommit, pattern UPDATE-only (gabarit), psycopg2 paramétré.
category: infrastructure
trigger: base de données, SQL, psycopg2, db, connexion, connect_intranet, autocommit, UPDATE, INSERT, gabarit, slot
---

# Database Operations

## Singleton DB

```python
from larccommon.database import db
db.connect_intranet()      # PostgreSQL local (config.ini)
db.connect_cloud()         # Supabase (fallback)
conn = db.server_conn      # connexion active
```

## Règles

| # | Règle |
|---|---|
| DB1 | Paramètres SQL via `%s` (jamais f-string pour les valeurs) |
| DB2 | `autocommit=True` sur toutes les connexions |
| DB3 | Gabarit : UPDATE uniquement après seed, jamais INSERT/DELETE |
| DB4 | Slot libre = `is_active=FALSE` (staff) ou `enabled=FALSE` (élève) |
| DB5 | `conn.commit()` explicite seulement pour transactions multi-tables |

## Pattern Gabarit

```python
# Activation d'un slot (jamais INSERT)
cur.execute("UPDATE larcauth_staff SET first_name=%s, ..., is_active=TRUE WHERE id=%s AND is_active=FALSE", ...)
if cur.rowcount == 0:  # slot déjà pris
    return None
```

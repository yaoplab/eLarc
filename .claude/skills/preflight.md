---
name: preflight
description: Check-list mécanique pré-soumission — 13 règles C1-C13 : on_primary_container, QMessageBox+input, ThemedDialog, labels dessus, safe_slot, widget wiring, tooltips, refresh parent, erreurs silencieuses
category: quality
trigger: pré-soumission, preflight, check-list, avant commit, livraison
---

# Preflight — Check-list Pré-soumission

Dernier rempart automatique avant la review humaine. Une violation 🔴 = FAIL.

| # | Règle | Gravité |
|---|---|---|
| C1 | **`on_primary_container` interdit** dans le code applicatif (`Palette` n'a pas cet attribut → AttributeError) | 🔴 |
| C2 | **`QMessageBox` + widget de saisie interdit** — utiliser `ThemedDialog` | 🔴 |
| C3 | **`QDialog` direct interdit** — hériter de `ThemedDialog` | 🔴 |
| C4 | **Label AU-DESSUS du champ** — jamais `addWidget(label)` après `addWidget(field)` | 🔴 |
| C5 | **`theme_manager.image.X`** — seuls `logo` et `theme_btn` sont autorisés | 🔴 |
| C6 | **Colonnes de tableau** — `set_headers` doit avoir une colonne pour chaque `setItem`/`setCellWidget` | 🔴 |
| C7 | **`@safe_slot`** obligatoire sur toute méthode `_on_*` connectée à un signal | 🔴 |
| C8 | **Widget wiring** — tout widget créé dans `_setup_ui()` doit avoir un `addWidget()` dans une méthode `_load_*()` | 🔴 |
| C9 | **Tooltip** sur bouton icône-seul — `setIcon()` sans `setText()` → `setToolTip()` obligatoire | 🔴 |
| C10 | **Refresh parent** — après un `.exec()` qui retourne True, la vue parente doit être rafraîchie | 🟡 |
| C11 | **Largeur champ date** — `QDateEdit`/`QDateTimeEdit` doit avoir `setMinimumWidth` | 🔴 |
| C12 | **Padding champ date/combo** — pas de padding uniforme ≥ `space_sm` | 🔴 |
| C13 | **Erreurs silencieuses** — tout `except: pass` ou `return` muet dans un handler est interdit | 🔴 |

```bash
python scripts/lint_preflight.py   # 0 violation sinon FAIL
```

Règles couvertes automatiquement par le linter `lint_preflight.py` ; C8/C10 restent semi-manuels.

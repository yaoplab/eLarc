---
name: zero-hardcoding
description: Règle absolue — zéro px ou #XXXXXX en dur dans le code. Tout passe par ds.* ou theme_manager.palette.*. Toléré : 0 et 1.
category: design
trigger: hardcoding, px en dur, couleur en dur, valeur littérale, setFixedHeight, setStyleSheet, setSpacing, setContentsMargins
---

# Zero Hardcoding — Règle Absolue

> **Aucune valeur pixel ou couleur littérale.** Tout passe par `ds.*` ou `theme_manager.palette.*`. Toléré : `0` et `1`.

## Interdit ❌

```python
layout.setSpacing(12)                    # px en dur
field.setFixedHeight(52)                 # px en dur
field.setStyleSheet("color: #1565C0")    # couleur en dur
layout.setContentsMargins(20, 20, 20, 20) # px en dur
```

## Obligatoire ✅

```python
layout.setSpacing(ds.space_sm)           # 12px via token
field.setFixedHeight(ds.field_height)     # 52px via token
field.setStyleSheet(ds.flat_input_qss())  # QSS via générateur
layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
```

## Vérification

```bash
python scripts/lint_qss_hardcoding.py
```

---
name: pyside6-review
description: Audit du code PySide6 — @safe_slot, anti-patterns Qt, règle des 1000 lignes
category: quality
trigger: audit pyside6, vérifie pyside6, check pyside6, revue pyside6, vérifie les slots, vérifie safe_slot
---

# PySide6 Review — Audit PySide6 Larc

Lancer les linters PySide6 et vérifier les règles manuelles.

## Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_safe_slot.py --dir .
python D:/projets/scripts/lint_file_size.py --dir . --stats
python D:/projets/scripts/lint_widget_purity.py --check-baseline
```

2. Vérifier manuellement les règles sans linter :
   - **D1** : `widget.update()` sur widget pas monté → `try: except RuntimeError: pass`
   - **D2** : Signaux cross-thread → `Signal` + `@Slot()` avec `QThread`
   - **B3** : Dialogue fermé avant d'en ouvrir un nouveau
   - **B4** : Dialogues en lazy init (pas dans `__init__`)
   - **E1** : Widget phibuilder construit sans `theme=` → avertissement `UserWarning`
     depuis 2026-09-08 (voir `LarcCommon/phibuilder/widgets/*.py`). Si un test/script
     émet ce warning, c'est un écran non stylé — corriger en ajoutant
     `theme=theme_manager.phi_theme`, ne jamais supprimer le warning.

3. Vérifier la règle "pas de `theme=phi`" :
```bash
grep -rn "theme=phi" --include="*.py" . | grep -v test_ | grep -v __pycache__
```

## Skills de référence

- `pyside6-wrapper` — @safe_slot, anti-patterns, 1000 lignes
- `theme-reactivity` — règle G (pas de theme=phi)

## Format du rapport

```
## PySide6 Review : `fichier.py`

### Bloquant (P0)
- Ligne 45 : lambda nu → slot nommé + @safe_slot
- Ligne 67 : variable `_` → renommer en `_outer`

### Recommandé (P1)
- Ligne 120 : dialogue dans __init__ → lazy init

### Stats
- lint_safe_slot.py : X violations
- lint_file_size.py : X fichiers > 1000 lignes
```

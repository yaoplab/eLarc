---
name: feature-review
description: Audit des fonctionnalités — événements, vignettes, dossier élève, widgets
category: quality
trigger: audit feature, vérifie feature, check feature, revue feature, événements, event generator, vignettes, card dashboard, dossier élève
---

# Feature Review — Audit Fonctionnalités Larc

Vérifier la conformité design des fonctionnalités métier.

## Procédure

1. Lancer les linters design :
```bash
python D:/projets/scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5+D6+D7 --fix-only
python D:/projets/scripts/lint_qss_hardcoding.py --fix-only
```

2. Audit spécifique :
```bash
# Event Generator
grep -rn "event_color\|event_icon" views/ | grep -v test_
# Card Dashboard
grep -rn "CardFields\|CARD_SECRETAIRE\|CARD_SUPERVISEUR\|CARD_PROF" views/
# Student Record
grep -rn "notes_json\|dossier_panel\|student_form" views/
# Widgets bruts (dette technique)
grep -rn "QPushButton\|QLineEdit\|QComboBox\|QTableWidget" --include="*.py" views/
```

## Checklist (toutes features)
- [ ] 0 couleur hex hardcodée
- [ ] 0 px en dur
- [ ] theme_changed → _restyle_all() dans chaque classe
- [ ] @safe_slot sur tous les handlers
- [ ] ThemedWidget pour conteneurs avec QSS background
- [ ] Traductions i18n pour tous les textes

## Skills de référence

- `[[event-generator]]` — wizard événements élèves
- `[[card-dashboard]]` — vignettes KPI configurables
- `[[student-record]]` — dossier élève par catégories
- `[[toolkit-reference]]` — catalogue widgets phibuilder
- `[[dashboard-pattern]]` — pattern canonique tableau de bord
- `[[search-detail-pattern]]` — pattern recherche + fiche détail
- `[[form-pattern]]` — pattern formulaire par sections
- `[[card-grid-pattern]]` — pattern grille responsive

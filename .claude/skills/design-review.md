---
name: design-review
description: Audit complet du design system Larc - tokens, couleurs, hardcoding, réactivité au thème
category: quality
trigger: audit design, vérifie le design, check design, revue design, design review
---

# Design Review — Audit Design System Larc

Lancer les 3 linters design et produire un rapport consolidé.

## Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5+D6+D7 --fix-only
python D:/projets/scripts/lint_qss_hardcoding.py --fix-only
python D:/projets/scripts/audit_theme_reactive.py
python D:/projets/scripts/audit_design_system.py --check-baseline
python D:/projets/scripts/lint_widget_purity.py --check-baseline
python D:/projets/scripts/lint_ui_quality.py
python D:/projets/scripts/lint_palette_contrast.py
```

2. Pour chaque violation, mapper vers la règle du skill :
   - D1 → color-rules : couleur explicite manquante
   - D3 → color-rules : hex hardcodé
   - R1-R16 → zero-hardcoding : px en dur
   - J1-J7 → theme-reactivity : thème non réactif
   - K1-K26 → sidebar-spec : sidebar non conforme
   - V1-V8 → ui-quality : finition UI (V8 = gap icône↔texte des boutons, 8px = ds.space_xs)
   - **W1 → pyside6-wrapper : widget PySide6 brut, remplacer par phibuilder.widgets**

3. Proposer la correction en citant la règle.

4. **QA visuelle obligatoire (tout écran neuf ou modifié significativement)** :
   lancer l'écran isolément (voir le pattern de script utilisé pour le
   diagnostic du 2026-09-08 dans `docs/superpowers/plans/2026-09-08-larccommon-ui-quality-enforcement.md`,
   Task 3 Step 3), capturer une image, et vérifier contre `composition-principles`
   avant de considérer l'écran terminé. Aucun linter ne voit un espace mort, une
   carte invisible faute de contraste réel, ou une hiérarchie visuelle faible —
   c'est le filet de sécurité pour tout ce que le code seul ne révèle pas.

## Skills de référence

- `design-tokens` — tokens numériques
- `color-rules` — palette et règles couleur
- `zero-hardcoding` — règle absolue tokens
- `theme-reactivity` — pattern _STYLE + _restyle_all
- `sidebar-spec` — spécification visuelle sidebar
- `ergonomics` — patterns de composition M3+Fibonacci
- `card-dashboard` — vignettes KPI
- `student-record` — dossier élève

## Format du rapport

```markdown
## Rapport design-review : `fichier.py`

### ❌ Violations (P0)
| Ligne | Règle | Code actuel | Correction |
|---|---|---|---|
| 45 | R7 | setContentsMargins(6,6,6,6) | setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm) |

### ✅ Conforme
- Utilise ds.flat_input_qss() pour les champs

### 📊 Progression
X violations → 0 cible
```

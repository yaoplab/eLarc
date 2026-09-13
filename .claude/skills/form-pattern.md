---
name: form-pattern
description: Pattern canonique de formulaire — sections avec cards, champs avec label AU-DESSUS, flat_input_qss, boutons en bas à droite.
category: feature
trigger: formulaire, form, dialogue, section, StaffFormDialog, ThemedDialog, sauvegarde, champ, field
---

# Form Pattern — Formulaire par Sections

## Structure

```
ThemedDialog
├── Section 1 (Identité)
│   ├── _section_card(title, icon)
│   ├── _field_row(label, widget)
│   └── _field_row(label, widget)
├── Section 2 (Contact)
│   └── ...
└── ButtonBox (Annuler | Sauvegarder)
```

## Pattern section

```python
def _section_card(title, icon_name):
    phi = theme_manager.phi_theme
    card = M3Card(theme=phi, variant=CardVariant.ELEVATED)  # jamais un QWidget stylé à la main
    layout = card.content_layout()
    layout.setSpacing(ds.space_sm)
    # header avec icône + titre
    return card, layout
```

## Pattern champ

```python
def _field_row(label, widget):
    phi = theme_manager.phi_theme
    p = theme_manager.palette

    # style= pour le rôle typo, set_color() pour la couleur sémantique.
    # JAMAIS setStyleSheet("color: ...") sur un M3Label : ça écrase la typo M3.
    lbl = M3Label(label, theme=phi, style="body_medium")
    lbl.set_color(p.text_soft)

    # Pas de setFixedHeight() sur un M3TextField : sa feuille de style interne
    # (min-height + padding) impose déjà sa hauteur réelle (~62px) et gagne
    # contre un setFixedHeight() plus petit — voir composition-principles §4.
    return widget
```

## Deux pièges qui ne lèvent aucune erreur

Détaillés dans `m3-elevation` (section « le piège inverse ») et
`composition-principles` §4 — à lire avant de reprendre un écran existant :

1. **`theme=` écrase le QSS parent.** Poser `theme=` sur un widget phibuilder
   qui était stylé par un QSS ancêtre (`#hdrTitle { font-weight: bold }`)
   fait perdre ce style — le widget pose désormais le sien. Utiliser
   `style=` + `set_color()` (labels) ou `variant=`/`accent_color=` (boutons).
2. **Les tailles fixes deviennent trop petites.** Un `setFixedSize()` calculé
   avant que les widgets aient leur vrai style M3 ne suffit plus une fois
   `theme=` posé (padding réel plus généreux) → chevauchement silencieux des
   widgets. Mesurer `win.layout().sizeHint()` avant de figer une taille.

## Pattern sauvegarde

Boutons en bas : Annuler (outlined, gauche) | Sauvegarder (filled, droite)
```python
btn_save = M3Button("Sauvegarder", variant=BTN_FILLED, theme=phi)
btn_save.clicked.connect(lambda: self._save())
```

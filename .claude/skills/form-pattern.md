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
    card = QWidget()
    card.setStyleSheet(f"background:{ds.p.surface};border:1px solid {ds.p.outline};border-radius:{ds.radius_sm}px;")
    layout = QVBoxLayout(card)
    layout.setSpacing(ds.space_sm)
    # header avec icône + titre
    return card, layout
```

## Pattern champ

```python
def _field_row(label, widget):
    lbl = M3Label(label)
    lbl.setStyleSheet(f"color:{ds.p.text_soft};font-size:{ds.font_small}px;")
    widget.setFixedHeight(ds.field_height)
    widget.setStyleSheet(ds.flat_input_qss())
    return widget
```

## Pattern sauvegarde

Boutons en bas : Annuler (outlined, gauche) | Sauvegarder (filled, droite)
```python
btn_save = M3Button("Sauvegarder", variant=BTN_FILLED, theme=phi)
btn_save.clicked.connect(lambda: self._save())
```

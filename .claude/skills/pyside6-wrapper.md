---
name: pyside6-wrapper
description: PySide6 rules — @safe_slot obligatoire sur tous les slots, widgets via phibuilder (jamais QPushButton/QLineEdit/QTableWidget brut), fichiers ≤1000 lignes.
category: infrastructure
trigger: PySide6, Qt, slot, on_click, clicked, QPushButton, QLineEdit, QTableWidget, safe_slot, ThemedDialog, M3
---

# PySide6 Wrapper — Règles Obligatoires

## 1. @safe_slot sur TOUS les slots Qt

```python
from larccommon.safe_slot import safe_slot

class MyWidget(QWidget):
    @safe_slot("mon_bouton")
    def on_click(self):
        ...
```

**Jamais** de slot sans `@safe_slot`. Interdit : `button.clicked.connect(lambda: ...)` sans wrapper.

## 2. Widgets via phibuilder — jamais Qt brut

| ❌ Interdit | ✅ Obligatoire |
|---|---|
| `QPushButton("OK")` | `M3Button("OK", variant=BTN_FILLED, theme=phi)` |
| `QLineEdit()` | `M3TextField(theme=phi)` |
| `QComboBox()` | `M3Combo(theme=phi)` |
| `QTableWidget()` | `M3TableWidget()` |

## 3. Dialogues via ThemedDialog

```python
from larccommon.widgets.themed_widget import ThemedDialog
```

## 4. Fichiers ≤ 1000 lignes

Si >1000 lignes → découper en sous-modules.

## 5. Anti-patterns interdits

- Pas de `QTimer.singleShot` pour contourner des bugs
- Pas de `processEvents()`
- Pas de `_` comme variable throwaway (écrase i18n)

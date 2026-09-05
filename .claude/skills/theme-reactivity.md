---
name: theme-reactivity
description: Réactivité au changement de thème — pattern _STYLE + _restyle_all. Tout widget doit se restyler quand le thème change.
category: design
trigger: thème, theme, restyle, _STYLE, _restyle_all, theme_changed, dark mode, light mode
---

# Theme Reactivity — _STYLE + _restyle_all

## Pattern obligatoire

```python
class MyWidget(QWidget):
    def __init__(self):
        self._STYLE = ""
        self._build_ui()
        ds.theme_changed.connect(self._restyle_all)

    def _build_ui(self):
        # utiliser self._STYLE pour le QSS
        self._restyle_all()

    def _restyle_all(self):
        p = theme_manager.palette
        self._STYLE = f"""
            QWidget {{ background: {p.background}; color: {p.text_strong}; }}
        """
        self.setStyleSheet(self._STYLE)
```

## Règle

- Toute classe visuelle DOIT avoir `_restyle_all`
- Se connecter à `ds.theme_changed` ou `theme_manager.theme_changed`
- Utiliser `theme_manager.palette` (pas `ds.p` directement dans le QSS)

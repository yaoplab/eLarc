---
name: color-rules
description: Règles de couleur Larc — palette M3, rôles sémantiques (primary, error, success), jamais de #XXXXXX en dur, thèmes dark/light.
category: design
trigger: couleur, color, palette, #XXXXXX, primary, surface, error, success, outline, thème, theme
---

# Color Rules — Palette M3

## Palette active (via `ds.p.*` et `theme_manager.palette.*`)

| Token | Rôle |
|---|---|
| `ds.p.primary` | Actions principales, liens |
| `ds.p.on_primary` | Texte sur primary |
| `ds.p.surface` | Fond des cartes/dialogues |
| `ds.p.on_surface` | Texte principal |
| `ds.p.background` | Fond de fenêtre |
| `ds.p.error` | Erreurs, suppression |
| `ds.p.success` | Succès, validation |
| `ds.p.outline` | Bordures |
| `ds.p.text_strong` | Texte accentué |
| `ds.p.text_soft` | Texte secondaire |
| `ds.p.text_disabled` | Texte désactivé |

## Interdit ❌

```python
setStyleSheet("color: #1565C0")     # couleur en dur
setStyleSheet("background: white")   # couleur nommée
```

## Obligatoire ✅

```python
setStyleSheet(f"color: {ds.p.primary}")
setStyleSheet(f"background: {ds.p.background}")
# ou via générateurs:
field.setStyleSheet(ds.flat_input_qss())
```

## 4 Thèmes

`blue` (clair), `dark` (sombre), `sobre` (clair), `contrast` (clair)
Changer via `theme_manager.set_active('dark')`.

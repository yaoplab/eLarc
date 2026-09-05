
# LarcCommon — Décisions algorithmiques et design

## 01_phibuilder_theme.md — Génération de thème

### Problème
Comment générer une palette de couleurs Material Design 3 cohérente
à partir d'une seule couleur de seed ?

### Solution
Utiliser le HCT color engine de Google (via `materialyoucolor`).

```
Seed (#6750A4)
  → Hct.from_int(argb)       # Teinte/Chroma/Tonalité
  → SchemeTonalSpot(hct)     # Génère 5 tonalités clés
  → MaterialDynamicColors    # → 60+ rôles M3
```

### Pourquoi pas une palette fixe ?
- M3 spec définit des relations mathématiques entre couleurs
- Garantit accessibilité WCAG (contraste, lisibilité)
- Support natif du mode clair/sombre
- 9 variantes disponibles (tonal_spot, expressive, monochrome...)

## 02_phibuilder_proportions.md — Proportions Fibonacci

### Problème
Comment dimensionner les éléments UI de manière cohérente et harmonieuse ?

### Solution
Suite de Fibonacci × base_spacing pour les espacements, nombre d'or (φ)
pour les ratios.

```
Espacements : Fib(0..11) × 4px
  → 0, 4, 8, 12, 20, 32, 52, 84, 136, 220, 356, 576

Typographie : base_font × φ^i (i: -2..8)
  → 5.3, 8.6, 14, 22.7, 36.7, 59.4, 96.2, ...

Grid : 12 colonnes, ratio φ pour largeur sidebar (1), contenu (φ)
```

## 03_theme_bridge.md — Intégration PhiBuilder dans LarcSuperviseur

### Problème
Comment ajouter le QSS Material Design 3 de PhiBuilder dans LarcSuperviseur
sans casser le système de thème existant ?

### Solution
1. ThèmeManager crée un PhiBuilder interne
2. `_reapply()` concatène : QSS PhiBuilder + QSS personnalisé
3. Les palettes manuelles (Palette) sont conservées pour compatibilité
4. `set_active()` synchronise seed couleur et mode dark sur le PhiBuilder

```
bind(app)
  → PhiBuilder(seed_color="#0D47A1", is_dark=False)
  → _reapply()
      → app.setStyleSheet(phibuilder.qss + custom_qss)

set_active("nuit")
  → phibuilder.set_seed_color("#4A148C")
  → phibuilder.set_dark_mode(True)
  → _reapply()
```

## 04_l10n.md — Traductions multilingues

### Problème
Comment gérer les traductions dans les applications Larc ?

### Solution
1. Fichiers JSON avec clés contextuelles
2. Un fichier par langue par application
3. Dossier `l10n/` dans chaque projet
4. Fusion automatique (larccommon + app)

```
larccommon/l10n/fr.json     ← Socle commun
LarcSuperviseur/l10n/fr.json ← Spécifique app

Translator.load_dir("larccommon/l10n")
Translator.load_dir("LarcSuperviseur/l10n")
# Fusionné dans _strings
```

### Pourquoi des clés contextuelles ?
```json
{
  "login.button.validate": "Valider",
  "dashboard.button.filter": "Valider"
}
```
Plutôt que des clés plates, on peut changer un bouton sans affecter l'autre.

## 05_themes_multiples.md — 5 thèmes variés

### Problème
Comment offrir des thèmes visuellement distincts tout en gardant
la compatibilité M3 ?

### Solution
Chaque thème a :
1. Une **seed couleur** différente (pour PhiBuilder → M3 QSS)
2. Une **palette manuelle** (pour les styles inline existants)

Les 5 thèmes couvrent 3 moods :
- **Froids** : Océan (bleu), Forêt (vert) → apaisant
- **Chauds** : Lave (rouge), Sable (ambre) → énergique
- **Sombre** : Nuit (violet) → calme, faible luminosité

Format extensible : `THEMES_CONFIG` est une liste, ajouter un thème
revient à ajouter une ligne + une palette.

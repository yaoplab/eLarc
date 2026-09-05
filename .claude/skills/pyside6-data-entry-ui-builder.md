---
name: pyside6-data-entry-ui-builder
description: Skill SOURCE (theme.txt) — génère des interfaces PySide6 de saisie dense 10/10 : Fibonacci, palette marque #1F4494/#24A9E1, validation in-line, AdaptiveScrollArea, PasswordLineEdit, CleanComboBox
category: design
trigger: data entry, saisie dense, pyside6-data-entry, formulaire 10/10, theme.txt
---

# Pyside6 Data Entry UI Builder — skill source (ex. theme.txt)

Génère des interfaces PySide6 (Qt6) d'excellence opérationnelle pour la saisie de données denses
(10/10 UX/UI). Aligné sur les proportions de Fibonacci, la palette marque (#1F4494 & #24A9E1),
la validation in-line robuste, l'absence de cadres superflus, et la gestion adaptative des viewports denses.

> Version condensée alignée sur le design system Larc : `[[data-entry-ui]]`.

## Instructions

1. **Proportions et grille Fibonacci (harmonie géométrique)**
   - Hauteur des champs de saisie & boutons : **34px** (F₆)
   - Hauteur des TextAreas / cartes compactes : **55px** (F₇) / **89px** (F₈)
   - Échelle des espacements (Margins/Paddings) : **3px, 5px, 8px, 13px, 21px**
   - Ratio de découpage des colonnes du Layout : **1 : 1.618** (Golden Ratio)
2. **Responsive viewport guard (protection petits écrans)**
   - Par défaut : ZÉRO défilement visible dans le corps principal
   - Encapsuler le formulaire dans une sous-classe `AdaptiveScrollArea` qui n'active la barre de
     défilement verticale QUE si la hauteur de fenêtre est < 768px (`resizeEvent`)
3. **Valeur par défaut & validation in-line**
   - Tous les champs obligatoires sont préremplis avec des valeurs par défaut valides
   - En cas d'erreur : bordure rouge `#EF4444` (`has_error="true"`) et `QLabel#errorMessage`
     directement sous le champ (11px)
   - Champ Mot de Passe : `PasswordLineEdit` avec action œil pour basculer le mode d'affichage
4. **QComboBox épurée & découvrable (clic gauche)**
   - Déclenchement au CLIC GAUCHE standard
   - Flèche classique supprimée (`QComboBox::drop-down { width: 0px; border: none; }`)
   - DÉCOUVRABILITÉ UX : légère bordure inférieure d'accent (`#24A9E1`) et changement de fond au
     survol (`:hover`) avec curseur `PointingHandCursor`
5. **Palette marque & coins arrondis réservés**
   - Primaire : `#1F4494` | Accent/Hover : `#24A9E1` | Erreur : `#EF4444`
   - `QPushButton` : `border-radius: 5px` (nombre Fibonacci)
   - Cartes, conteneurs et champs de saisie : angles droits (`border-radius: 0px`)
   - Aucune bordure sur les cartes de section (`QFrame#sectionCard`)

## Palettes

```python
# light_brand_blue
PRIMARY="#1F4494"; ACCENT="#24A9E1"; ERROR="#EF4444"
BG_APP="#F0F4F8"; BG_PANEL="#FFFFFF"; BG_INPUT="#FFFFFF"
BORDER_INPUT="#CBD5E1"; TEXT_PRIMARY="#0F172A"; TEXT_SECONDARY="#5B6778"; TEXT_MONO="#1F4494"

# deep_dark_blue
PRIMARY="#1F4494"; ACCENT="#24A9E1"; ERROR="#EF4444"
BG_APP="#0F172A"; BG_PANEL="#1E293B"; BG_INPUT="#0F172A"
BORDER_INPUT="#334155"; TEXT_PRIMARY="#F1F5F9"; TEXT_SECONDARY="#A5B0BF"; TEXT_MONO="#38BDF8"
```

## Composants (snippets source)

```python
class AdaptiveScrollArea(QScrollArea):
    """Ne s'active que sous 768px de hauteur."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    def resizeEvent(self, event):
        if event.size().height() < 768:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        super().resizeEvent(event)

class PasswordLineEdit(QLineEdit):
    """Champ mot de passe avec bouton œil."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_action = self.addAction(QIcon("eye_icon.png"),
                                            QLineEdit.ActionPosition.TrailingPosition)
        self.toggle_action.triggered.connect(self._toggle_visibility)
    def _toggle_visibility(self):
        if self.echoMode() == QLineEdit.EchoMode.Password:
            self.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.setEchoMode(QLineEdit.EchoMode.Password)

class CleanComboBox(QComboBox):
    """ComboBox épurée et découvrable."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
```

## QSS template (extraits clés)

```css
QFrame#sectionCard { background: BG_PANEL; border: none; border-radius: 0px; padding: 13px; }
QLabel#sectionTitle { color: PRIMARY; font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; padding-bottom: 5px; border-bottom: 2px solid ACCENT; margin-bottom: 8px; }
QLabel#fieldLabel { color: TEXT_SECONDARY; font-size: 12px; font-weight: 500; }
QLabel#errorMessage { color: ERROR; font-size: 11px; font-weight: 500; margin-top: 3px; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { background: BG_INPUT; border: 1px solid BORDER_INPUT;
  border-radius: 0px; padding: 0 8px; min-height: 34px; max-height: 34px; font-size: 13px; }
QComboBox { border-bottom: 2px solid ACCENT; }
QComboBox::drop-down { width: 0px; border: none; }
*[has_error="true"] { border: 2px solid ERROR !important; }
*[class="mono-data"] { font-family: 'JetBrains Mono', 'Consolas', monospace; color: TEXT_MONO; font-weight: 600; }
QPushButton#primaryBtn { background: PRIMARY; color: #FFFFFF; border: none; border-radius: 5px;
  min-height: 34px; font-weight: 600; padding: 0 21px; }
QPushButton#primaryBtn:hover { background: ACCENT; }
```

## Règles de sortie

- Encapsuler systématiquement le conteneur central de formulaires dans une `AdaptiveScrollArea`
  pour garantir un fonctionnement parfait sur toutes les définitions d'écran.
- Les erreurs de validation doivent basculer la propriété `has_error="true"` du composant et
  insérer dynamiquement le `QLabel#errorMessage` sous le champ.

## Références

- `[[data-entry-ui]]` — version condensée alignée design system Larc (widgets phibuilder, tokens)
- `[[form-pattern]]` — structure de formulaire par sections ; `[[design-tokens]]` — tokens ds.*

from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken, RADIUS_BTN

class StyleBuilder:
    def __init__(self, theme: Theme):
        self.theme = theme
        self.c = theme.colors
        self.s = theme.spacing
        self.typo = theme.typo
    def _sp(self, token: SpacingToken | int) -> int:
        if isinstance(token, int):
            return token * self.s.base_spacing
        return self.s.spacing(token)
    def build(self) -> str:
        return "\n".join([
            self._global(), self._window(), self._button(), self._line_edit(),
            self._combo(), self._date_edit(), self._checkbox_radio(), self._scrollbar(), self._slider(),
            self._progress(), self._tabs(), self._menu(), self._tooltip(),
            self._groupbox(), self._list_tree(), self._splitter(), self._statusbar(), self._card(),
            self._data_entry(),
        ])
    def _global(self) -> str:
        return f"\n* {{ font-family: '{self.typo.family}'; font-size: {self.typo.body_medium.size}px; color: {self.c.on_surface}; background-color: transparent; }}\n"
    def _window(self) -> str:
        # NB : le sélecteur QWidget matche aussi les QLabel (sous-classes) —
        # sans le reset ci-dessous, chaque libellé hériterait d'un fond opaque
        # (rectangles blancs sur la sidebar grise, etc.).
        return (f"QMainWindow, QDialog, QWidget {{ background-color: {self.c.surface}; }}\n"
                f"QLabel {{ background-color: transparent; }}\n")
    def _button(self) -> str:
        # Radius boutons = F₅ (skill data-entry-ui)
        p, h, r = self._sp(SpacingToken.MD), self._sp(SpacingToken.XL), RADIUS_BTN
        # NB : le height QSS s'applique au CONTENU ; le padding s'ajoute par-dessus.
        # padding vertical 0 → hauteur totale = 52 px (ds.button_height), pas 68.
        return f"""
QPushButton {{ padding: 0 {p}px; height: {h}px; font-weight: {self.typo.label_large.weight};
  font-size: {self.typo.label_large.size}px; letter-spacing: {self.typo.label_large.letter_spacing}px;
  border: none; border-radius: {r}px; background-color: {self.c.primary}; color: {self.c.on_primary}; }}
QPushButton:hover {{ background-color: {self.c.primary_container}; color: {self.c.on_primary_container}; }}
QPushButton:pressed {{ background-color: {self.c.primary}; }}
QPushButton:disabled {{ background-color: {self.c.surface_container_highest}; color: {self.c.on_surface}; }}
QPushButton[flat="true"] {{ background-color: transparent; color: {self.c.primary}; }}
QPushButton[flat="true"]:hover {{ background-color: rgba(0,0,0,0.05); }}
"""
    def _line_edit(self) -> str:
        r = self._sp(SpacingToken.NONE)  # angles droits (skill data-entry-ui)
        # QLineEdit : hauteur totale 32 px (comme ds.field_height).
        # QTextEdit/QPlainTextEdit : multilignes — pas de height, padding normal.
        return f"""
QLineEdit {{ padding: 0 {self._sp(SpacingToken.MD)}px;
  border: 1px solid {self.c.outline}; border-radius: {r}px; background-color: {self.c.surface}; color: {self.c.on_surface};
  height: {self._sp(SpacingToken.LG) - self._sp(SpacingToken.XXS) // 2}px;
  selection-background-color: {self.c.primary_container}; selection-color: {self.c.on_primary_container}; }}
QTextEdit, QPlainTextEdit {{ padding: {self._sp(SpacingToken.XS)}px {self._sp(SpacingToken.MD)}px;
  border: 1px solid {self.c.outline}; border-radius: {r}px; background-color: {self.c.surface}; color: {self.c.on_surface};
  selection-background-color: {self.c.primary_container}; selection-color: {self.c.on_primary_container}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {self.c.primary}; }}
QLineEdit:disabled {{ background-color: {self.c.surface_container_highest}; color: {self.c.on_surface}; }}
"""
    def _date_edit(self) -> str:
        # Sans règle dédiée, QDateEdit est peint par le style natif (texte bleu
        # #0067C0 illisible sur fond clair). On l'aligne sur les QLineEdit.
        # NB : rendu réel = height + 5 px (bordure 2 + boutons spin ~3)
        # → height 27 donne un total de 32 px (mesuré, cf. lint_design section 8).
        r = self._sp(SpacingToken.XS)
        return f"""
QDateEdit, QTimeEdit {{ padding: 0 {self._sp(SpacingToken.MD)}px;
  border: 1px solid {self.c.outline}; border-radius: {r}px; background-color: {self.c.surface};
  color: {self.c.on_surface}; height: {self._sp(SpacingToken.LG) - self._sp(SpacingToken.XXS) // 2 - 3}px; }}
QDateEdit:focus, QTimeEdit:focus {{ border: 2px solid {self.c.primary}; }}
QDateEdit::drop-down, QTimeEdit::drop-down {{ border: none; width: {self._sp(SpacingToken.LG)}px; }}
QDateEdit::up-button, QDateEdit::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{ height: {self._sp(SpacingToken.XS)}px; }}
QCalendarWidget QWidget {{ background-color: {self.c.surface}; color: {self.c.on_surface}; }}
QCalendarWidget QAbstractItemView {{ background-color: {self.c.surface}; color: {self.c.on_surface};
  selection-background-color: {self.c.primary_container}; selection-color: {self.c.on_primary_container}; }}
QCalendarWidget QToolButton {{ background-color: transparent; color: {self.c.on_surface};
  border: none; padding: {self._sp(SpacingToken.XS)}px; }}
"""
    def _combo(self) -> str:
        r = self._sp(SpacingToken.XS)
        return f"""
QComboBox {{ padding: 0 {self._sp(SpacingToken.MD)}px;
  border: 1px solid {self.c.outline}; border-radius: {r}px; background-color: {self.c.surface};
  color: {self.c.on_surface}; height: {self._sp(SpacingToken.LG) - self._sp(SpacingToken.XXS) // 2}px; }}
QComboBox:hover {{ border-color: {self.c.on_surface}; }}
QComboBox:focus {{ border: 2px solid {self.c.primary}; }}
QComboBox::drop-down {{ border: none; width: {self._sp(SpacingToken.LG)}px; }}
QComboBox::down-arrow {{ width: {self._sp(SpacingToken.MD)}px; height: {self._sp(SpacingToken.MD)}px; }}
QComboBox QAbstractItemView {{ background-color: {self.c.surface}; border: 1px solid {self.c.outline};
  border-radius: {r}px; padding: {self._sp(SpacingToken.XS)}px; outline: none;
  selection-background-color: {self.c.primary_container}; selection-color: {self.c.on_primary_container}; }}
"""
    def _checkbox_radio(self) -> str:
        # Aucune règle QSS : toute règle sur QCheckBox/QRadioButton bascule le
        # widget en rendu QSS et fait disparaître la case native (contour
        # invisible signalé 2026-08-14). On laisse Fusion dessiner des cases
        # traditionnelles (choix utilisateur, 2026-08-13).
        return ""
    def _scrollbar(self) -> str:
        return f"""
QScrollBar:vertical {{ width: {self._sp(SpacingToken.MD) + 4}px; background: transparent; margin: 0; }}
QScrollBar::handle:vertical {{ background: {self.c.outline}; border-radius: {self._sp(SpacingToken.XS)}px; min-height: {self._sp(SpacingToken.XL)}px; }}
QScrollBar::handle:vertical:hover {{ background: {self.c.on_surface}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; background: none; }}
QScrollBar:horizontal {{ height: {self._sp(SpacingToken.MD) + 4}px; background: transparent; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {self.c.outline}; border-radius: {self._sp(SpacingToken.XS)}px; min-width: {self._sp(SpacingToken.XL)}px; }}
QScrollBar::handle:horizontal:hover {{ background: {self.c.on_surface}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; background: none; }}
"""
    def _slider(self) -> str:
        return f"""
QSlider::groove:horizontal {{ height: {self._sp(SpacingToken.XS)}px; background: {self.c.surface_container_highest};
  border-radius: {self._sp(SpacingToken.XS)}px; }}
QSlider::handle:horizontal {{ width: {self._sp(SpacingToken.MD)}px; height: {self._sp(SpacingToken.MD)}px;
  margin: -{self._sp(SpacingToken.XS)}px 0; background: {self.c.primary}; border-radius: {self._sp(SpacingToken.MD) // 2}px; }}
QSlider::handle:horizontal:hover {{ background: {self.c.primary_container}; }}
QSlider::sub-page:horizontal {{ background: {self.c.primary}; border-radius: {self._sp(SpacingToken.XS)}px; }}
"""
    def _progress(self) -> str:
        return f"""
QProgressBar {{ height: {self._sp(SpacingToken.XS)}px; background: {self.c.surface_container_highest};
  border: none; border-radius: {self._sp(SpacingToken.XS)}px; text-align: center;
  font-size: {self.typo.label_small.size}px; }}
QProgressBar::chunk {{ background: {self.c.primary}; border-radius: {self._sp(SpacingToken.XS)}px; }}
"""
    def _tabs(self) -> str:
        return f"""
QTabWidget::pane {{ border: 1px solid {self.c.outline}; border-radius: {self._sp(SpacingToken.SM)}px;
  background: {self.c.surface}; top: -1px; }}
QTabBar::tab {{ padding: {self._sp(SpacingToken.MD)}px {self._sp(SpacingToken.LG)}px;
  font-weight: {self.typo.label_large.weight}; font-size: {self.typo.label_large.size}px;
  color: {self.c.on_surface}; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {self.c.primary}; border-bottom: 2px solid {self.c.primary}; }}
QTabBar::tab:hover {{ color: {self.c.primary}; }}
QTabBar::tab:disabled {{ color: {self.c.on_surface_variant}; }}
"""
    def _menu(self) -> str:
        return f"""
QMenuBar {{ background: {self.c.surface}; border-bottom: 1px solid {self.c.outline}; padding: {self._sp(SpacingToken.XS)}px; }}
QMenuBar::item {{ padding: {self._sp(SpacingToken.XS)}px {self._sp(SpacingToken.MD)}px; border-radius: {self._sp(SpacingToken.XS)}px; }}
QMenuBar::item:selected {{ background: {self.c.primary_container}; color: {self.c.on_primary_container}; }}
QMenu {{ background: {self.c.surface}; border: 1px solid {self.c.outline}; border-radius: {self._sp(SpacingToken.SM)}px; padding: {self._sp(SpacingToken.XS)}px; }}
QMenu::item {{ padding: {self._sp(SpacingToken.XS)}px {self._sp(SpacingToken.LG)}px; border-radius: {self._sp(SpacingToken.XS)}px; font-size: {self.typo.body_medium.size}px; }}
QMenu::item:selected {{ background: {self.c.primary_container}; color: {self.c.on_primary_container}; }}
QMenu::separator {{ height: 1px; background: {self.c.outline}; margin: {self._sp(SpacingToken.XS)}px 0; }}
"""
    def _tooltip(self) -> str:
        return f"""
QToolTip {{ background: {self.c.surface_container_highest}; color: {self.c.on_surface};
  border: 1px solid {self.c.outline}; border-radius: {self._sp(SpacingToken.XS)}px;
  padding: {self._sp(SpacingToken.XS)}px {self._sp(SpacingToken.MD)}px; font-size: {self.typo.body_small.size}px; }}
"""
    def _groupbox(self) -> str:
        return f"""
QGroupBox {{ font-weight: {self.typo.title_small.weight}; font-size: {self.typo.title_small.size}px;
  border: 1px solid {self.c.outline}; border-radius: {self._sp(SpacingToken.SM)}px;
  margin-top: {self._sp(SpacingToken.XXL)}px; padding: {self._sp(SpacingToken.LG)}px {self._sp(SpacingToken.MD)}px {self._sp(SpacingToken.MD)}px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
  padding: 0 {self._sp(SpacingToken.MD)}px; color: {self.c.primary}; }}
"""
    def _list_tree(self) -> str:
        return f"""
QListWidget, QTreeWidget, QListView, QTableView {{ background: {self.c.surface};
  border: 1px solid {self.c.outline}; border-radius: {self._sp(SpacingToken.SM)}px;
  outline: none; selection-background-color: {self.c.primary_container};
  selection-color: {self.c.on_primary_container}; alternate-background-color: {self.c.surface_container_highest}; }}
QHeaderView::section {{ background: {self.c.surface}; color: {self.c.on_surface};
  padding: {self._sp(SpacingToken.MD)}px; border: none; border-bottom: 1px solid {self.c.outline};
  font-weight: {self.typo.label_large.weight}; }}
QHeaderView::section:hover {{ background: {self.c.surface_container_highest}; }}
"""
    def _splitter(self) -> str:
        return f"""
QSplitter::handle {{ background: {self.c.outline}; margin: {self._sp(SpacingToken.XXS) // 2}px; }}
QSplitter::handle:horizontal {{ width: {self._sp(SpacingToken.XXS) // 2}px; }}
QSplitter::handle:vertical {{ height: {self._sp(SpacingToken.XXS) // 2}px; }}
QSplitter::handle:hover {{ background: {self.c.primary}; }}
"""
    def _statusbar(self) -> str:
        return f"""
QStatusBar {{ background: {self.c.surface}; border-top: 1px solid {self.c.outline};
  padding: {self._sp(SpacingToken.XS)}px; font-size: {self.typo.body_small.size}px; color: {self.c.on_surface}; }}
QStatusBar::item {{ border: none; }}
"""
    def _card(self) -> str:
        # Cartes sans bordure, angles droits (skill data-entry-ui)
        return f"""
QFrame[card="true"] {{ background: {self.c.surface}; border: none;
  border-radius: {self._sp(SpacingToken.NONE)}px; padding: {self._sp(SpacingToken.LG)}px; }}
"""

    def _data_entry(self) -> str:
        """Fragments saisie dense (skill pyside6-data-entry-ui-builder)."""
        return f"""
QFrame#sectionCard {{ background: {self.c.surface}; border: none;
  border-radius: {self._sp(SpacingToken.NONE)}px;
  padding: {self._sp(SpacingToken.SM)}px; }}
QLabel#sectionTitle {{ color: {self.c.primary}; font-size: {self.typo.title_small.size}px;
  font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
  padding-bottom: {self._sp(SpacingToken.XXS)}px;
  border-bottom: 2px solid {self.c.accent}; margin-bottom: {self._sp(SpacingToken.XS)}px; }}
QLabel#fieldLabel {{ color: {self.c.on_surface_variant}; font-size: {self.typo.body_small.size}px;
  font-weight: 500; }}
QLabel#errorMessage {{ color: {self.c.error}; font-size: {self.typo.label_small.size}px;
  font-weight: 500; margin-top: 2px; }}
*[class="mono-data"] {{ font-family: 'Consolas', 'JetBrains Mono', monospace;
  color: {self.c.primary}; font-weight: 600; }}
"""

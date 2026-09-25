from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSizePolicy
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken

# Échelle phi partagée (base 4) pour les tailles indépendantes du thème
_SCALE = PhiScale()

class M3ComboBox(QComboBox):
    """ComboBox épurée (skill data-entry-ui) : sans flèche, soulignement
    accent, survol fond clair, curseur main."""
    def __init__(self, items: list[str] | None = None, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(_SCALE.spacing(SpacingToken.MD) * 2)  # 40px
        self.setCursor(Qt.PointingHandCursor)
        # Une combo ne s'active que par clic/clavier : sans ça, la molette
        # qui défile un tableau change silencieusement sa valeur.
        self.setFocusPolicy(Qt.StrongFocus)
        if items:
            self.addItems(items)
        self._update_style()

    def wheelEvent(self, event):
        # Jamais de changement par la molette, même avec le focus : la fenêtre
        # donne le focus initial à la première combo, sans aucun clic.
        event.ignore()

    def keyPressEvent(self, event):
        # Flèches/Page/Début/Fin ne changent la valeur que liste ouverte (choix
        # explicite) ; sinon elles reviennent au tableau/formulaire parent.
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown,
                            Qt.Key_Home, Qt.Key_End):
            event.ignore()
            return
        super().keyPressEvent(event)
    def _update_style(self):
        if self._theme is None:
            import warnings
            warnings.warn(
                f"{type(self).__name__} cree sans theme= -- aucun style applique. "
                f"Passer theme=theme_manager.phi_theme.",
                stacklevel=2,
            )
            return
        t, c, s = self._theme, self._theme.colors, self._theme.spacing
        p, r = s.spacing(SpacingToken.MD), s.spacing(SpacingToken.NONE)
        self.setStyleSheet(f"""
M3ComboBox {{ padding: 0 {p}px; height: {p * 2}px; border: 1px solid {c.outline};
  border-bottom: 2px solid {c.accent}; border-radius: {r}px;
  background-color: {c.surface}; color: {c.on_surface}; font-family: '{t.typo.family}'; font-size: {t.typo.body_large.size}px; }}
M3ComboBox:hover {{ background-color: {c.surface_container_highest}; }}
M3ComboBox:focus, M3ComboBox:open {{ border: 2px solid {c.primary}; border-bottom: 2px solid {c.accent}; }}
M3ComboBox::drop-down {{ border: none; width: {s.spacing(SpacingToken.NONE)}px; }}
M3ComboBox QAbstractItemView {{ background-color: {c.surface}; border: 1px solid {c.outline}; border-radius: {r}px;
  padding: {s.spacing(SpacingToken.XS)}px; outline: none; color: {c.on_surface};
  font-family: '{t.typo.family}'; font-size: {t.typo.body_medium.size}px;
  selection-background-color: {c.primary_container}; selection-color: {c.on_surface}; }}
M3ComboBox QAbstractItemView::item {{ padding: {s.spacing(SpacingToken.SM)}px {s.spacing(SpacingToken.MD)}px;
  border-radius: {s.spacing(SpacingToken.NONE)}px; min-height: {s.spacing(SpacingToken.XL)}px; }}
""")

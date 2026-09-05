"""Composants partagés des panels : titres réactifs, carte DB down, note."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QTextEdit

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import M3Button, M3Card, M3Dialog, M3Label
from phibuilder.widgets.button import ButtonVariant

from ...taxonomy import category_info, type_colors


def restyle_label(lbl: M3Label, style_name: str, color: str) -> None:
    """Re-pose la typographie M3 d'un label (couleur gelée à la construction
    — pattern LarcConfig : _label_qss)."""
    s = getattr(theme_manager.phi_theme.typo, style_name)
    lbl.setStyleSheet(
        f"M3Label {{ font-family: '{s.family}'; font-size: {s.size}px; "
        f"font-weight: {s.weight}; letter-spacing: {s.letter_spacing}px; "
        f"color: {color}; }}")


def restyle_card(card: M3Card) -> None:
    """Re-pose le style M3 d'une carte (figé à la construction — le theme
    manager change d'objet Theme au changement de thème)."""
    card._update_style()


class SectionTitle(M3Label):
    """Titre de section réactif au thème."""

    _STYLE = "headline_small"

    def __init__(self, text: str, parent=None):
        super().__init__(text, theme=theme_manager.phi_theme,
                         style=self._STYLE, parent=parent)

    def restyle(self):
        restyle_label(self, self._STYLE, theme_manager.palette.text_strong)


class BodyLabel(M3Label):
    """Label de corps réactif au thème."""

    _STYLE = "body_medium"

    def __init__(self, text: str, parent=None):
        super().__init__(text, theme=theme_manager.phi_theme,
                         style=self._STYLE, parent=parent)

    def restyle(self):
        restyle_label(self, self._STYLE, theme_manager.palette.text_soft)


class DbUnavailableCard(M3Card):
    """Carte « Base de données indisponible » avec bouton Réessayer."""

    retry = Signal()

    def __init__(self, message: str = "", parent=None):
        super().__init__(theme=theme_manager.phi_theme, variant=ds.CARD_ELEVATED,
                         parent=parent)
        cl = self.content_layout()
        cl.setSpacing(ds.space_sm)

        self._msg = BodyLabel(
            message or "La base de données est indisponible. Vérifiez le "
                       "service PostgreSQL ou la configuration, puis réessayez.")
        cl.addWidget(self._msg)

        self._btn = M3Button("Réessayer", theme=theme_manager.phi_theme,
                             variant=ButtonVariant.TONAL)
        self._btn.setIcon(md3_icon("refresh", color=theme_manager.palette.primary,
                                   size=ds.icon_md))
        self._btn.setIconSize(QSize(ds.icon_md, ds.icon_md))
        self._btn.clicked.connect(self._on_retry)
        cl.addWidget(self._btn, alignment=Qt.AlignLeft)

    def set_message(self, message: str):
        self._msg.setText(message)

    @safe_slot("DbUnavailableCard.on_retry")
    def _on_retry(self):
        self.retry.emit()

    def _restyle(self):
        self._msg.restyle()
        self._btn.setIcon(md3_icon("refresh", color=theme_manager.palette.primary,
                                   size=ds.icon_md))


class NoteDialog(M3Dialog):
    """Dialogue de note (résolution de fiche) : zone texte + Annuler/Résoudre.

    Hérite de M3Dialog (C3 : jamais de QDialog direct — le toolkit fournit
    titre, message et rangée de boutons ; la zone de note s'insère avant).
    """

    def __init__(self, title: str, message: str = "", ok_text: str = "Résoudre",
                 parent=None):
        super().__init__(parent, title=title, theme=theme_manager.phi_theme)
        self.setMinimumWidth(ds.space_xxxl * 4)
        self.cancel_btn.setText("Annuler")
        self.confirm_btn.setText(ok_text)
        if message:
            self.message_label.setText(message)
        else:
            self.message_label.setVisible(False)
        self._note = QTextEdit()
        self._note.setFixedHeight(ds.space_xxxl * 2)
        self._note.setStyleSheet(ds.flat_input_qss())
        # M3Dialog construit : titre (0), message (1), boutons (2) — la note
        # s'insère juste avant la rangée de boutons.
        self.layout().insertWidget(2, self._note)

    def note(self) -> str:
        return self._note.toPlainText().strip()

    def exec_note(self) -> str | None:
        """Ouvre le dialogue ; retourne la note, ou None si annulé."""
        if self.exec() == QDialog.Accepted:
            return self.note()
        return None


class TypeBadge(M3Label):
    """Chip coloré d'une catégorie d'erreur (réactif au thème).

    Pill : fond = couleur « badge » de la catégorie, texte = couleur « texte »
    (résolu par larccommon.theme.error_category_color au moment du paint), coins
    arrondis. La couleur suit donc le thème actif sans redémarrage.
    """

    def __init__(self, category: str, text: str | None = None, parent=None):
        self._category = category
        super().__init__("", theme=theme_manager.phi_theme,
                         style="label_medium", parent=parent)
        self.setText(text or category_info(category)["label"])
        self._restyle()

    def set_category(self, category: str, text: str | None = None):
        self._category = category
        if text is not None:
            self.setText(text)
        self._restyle()

    def restyle(self):
        self._restyle()

    def _restyle(self):
        badge, _container, texte = type_colors(self._category)
        self.setStyleSheet(
            f"M3Label {{ background-color: {badge}; color: {texte}; "
            f"border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_xxs}px {ds.space_sm}px; }}")

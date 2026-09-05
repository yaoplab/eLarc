"""ChangePasswordDialog — changement de mot de passe intranet (partagé).

Accessible depuis le menu profil de la TopBar (topbar.change_password).
Pattern form-pattern : ThemedDialog, labels au-dessus des champs (C4),
erreurs inline rouges (pas de popup brut), Annuler/Enregistrer.
"""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from phibuilder.widgets import M3Button

from larccommon.auth import AuthManager
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.session import session
from larccommon.theme import theme_manager
from larccommon.widgets.themed_widget import ThemedDialog


class ChangePasswordDialog(ThemedDialog):
    """Mot de passe actuel + nouveau + confirmation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("password.title"))
        self.setModal(True)
        # Fibonacci (standard des sections Larc, cf. StaffEventDialog) :
        # 233 + Φ×233 = 610 px min
        self.setMinimumWidth(ds.sidebar_width + ds.golden_width(ds.sidebar_width))
        self.setMaximumWidth(ds.form_max_width)  # IE6 : popup plafonné
        self._setup_ui()

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        # Erreur inline (ui-quality #5 : rouge, pas de popup brut)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(
            f"color: {p.error}; font-size: {s(11)}px; border: none;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        self._current_field = self._make_field(_("password.current"), layout)
        self._new_field = self._make_field(_("password.new"), layout)
        self._confirm_field = self._make_field(_("password.confirm"), layout)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = M3Button(_("common.button.cancel"))
        cancel_btn.setFixedHeight(ds.button_height)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = M3Button(_("common.button.save"))
        save_btn.setFixedHeight(ds.button_height)
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; "
            f"font-size: {s(13)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _make_field(self, label: str, layout: QVBoxLayout) -> QLineEdit:
        """Label AU-DESSUS du champ (preflight C4) + champ mot de passe + œil."""
        p = theme_manager.palette
        s = theme_manager.font_size
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold; "
            f"color: {p.text_strong}; border: none;")
        layout.addWidget(lbl)
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setFixedHeight(ds.field_height)
        field.setMaximumWidth(ds.field_max_width)
        field.setStyleSheet(ds.flat_input_qss())
        eye = field.addAction(
            md3_icon("visibility", color=p.text_soft, size=18),
            QLineEdit.TrailingPosition)
        eye.setToolTip(_("password.show"))
        eye.triggered.connect(
            lambda checked, f=field, a=eye: self._toggle_visibility(f, a))
        layout.addWidget(field)
        return field

    def _toggle_visibility(self, field: QLineEdit, action):
        """Bascule l'affichage du mot de passe (œil ↔ œil barré)."""
        reveal = field.echoMode() == QLineEdit.Password
        field.setEchoMode(QLineEdit.Normal if reveal else QLineEdit.Password)
        action.setIcon(md3_icon(
            "visibility_off" if reveal else "visibility",
            color=theme_manager.palette.text_soft, size=18))
        action.setToolTip(_("password.hide") if reveal else _("password.show"))

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    @safe_slot("ChangePasswordDialog._on_save")
    def _on_save(self):
        current = self._current_field.text()
        new = self._new_field.text()
        confirm = self._confirm_field.text()
        if not current or not new or not confirm:
            self._show_error(_("password.error_empty"))
            return
        if new != confirm:
            self._show_error(_("password.error_mismatch"))
            return
        ok, msg = AuthManager.change_password(session.email or "", current, new)
        if not ok:
            self._show_error(msg)
            return
        QMessageBox.information(self, _("password.title"), _("password.success"))
        self.accept()

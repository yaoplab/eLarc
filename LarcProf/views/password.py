import hashlib
from typing import Optional

from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QMessageBox, QDialogButtonBox
)
from PySide6.QtCore import Qt

from common.database import db, DBMode
from common.auth import AuthManager
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


class ChangePinDialog(ThemedDialog):
    """Boîte de dialogue pour changer le PIN hors connexion."""

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"QDialog {{ background: {p.background}; }}"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Changer le PIN')
        self.setMinimumWidth(ds.golden_width(ds.sidebar_width))  # 377px
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(ds.font_label_lg)  # 13px

        p = theme_manager.palette
        self._title_lbl = QLabel('Modification du PIN hors connexion')
        self._title_lbl.setStyleSheet(
            f'font-size: {theme_manager.font_size(14)}px; font-weight: bold; color: {p.text_strong};')
        layout.addWidget(self._title_lbl)

        form = QFormLayout()
        form.setSpacing(ds.space_xs)

        self._pin_edit = QLineEdit()
        self._pin_edit.setEchoMode(QLineEdit.Password)
        self._pin_edit.setPlaceholderText('Nouveau PIN (4-8 chiffres)')
        self._pin_edit.setMaxLength(8)

        form.addRow('Nouveau PIN :', self._pin_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._error_label = QLabel()
        self._error_label.setStyleSheet(f'color: {theme_manager.palette.error}; font-size: {theme_manager.font_size(11)}px;')
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self.setStyleSheet(self._STYLE)
        ds.theme_changed.connect(self._restyle)

    @safe_slot("ChangePinDialog._restyle")
    def _restyle(self):
        p = theme_manager.palette
        self.setStyleSheet(self._STYLE)
        self._title_lbl.setStyleSheet(
            f'font-size: {theme_manager.font_size(14)}px; font-weight: bold; color: {p.text_strong};')
        self._error_label.setStyleSheet(
            f'color: {p.error}; font-size: {theme_manager.font_size(11)}px;')

    @safe_slot("ChangePinDialog._on_accept")
    def _on_accept(self) -> None:
        new_pin = self._pin_edit.text().strip()
        if not new_pin or not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
            self._show_error('Le PIN doit contenir 4 à 8 chiffres.')
            return

        # Mettre à jour le PIN dans la base locale
        from common.sqlite_init import sqlite_init
        from common.session import session
        sqlite_init.save_session(session, new_pin)
        QMessageBox.information(self, 'Succès', 'PIN mis à jour avec succès.')
        self.accept()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()


class ChangePasswordDialog(ThemedDialog):
    """Boîte de dialogue pour changer le mot de passe Intranet."""

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"QDialog {{ background: {p.background}; }}"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Changer le mot de passe')
        self.setMinimumWidth(ds.golden_width(ds.sidebar_width))  # 377px
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(ds.font_label_lg)  # 13px

        # Titre
        self._title_lbl = QLabel('Modification du mot de passe Intranet')
        self._title_lbl.setStyleSheet(
            f'font-size: {theme_manager.font_size(14)}px; font-weight: bold; color: {theme_manager.palette.text_strong};')
        layout.addWidget(self._title_lbl)

        # Formulaire
        form = QFormLayout()
        form.setSpacing(ds.space_xs)

        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText('prenom.nom@arc-en-ciel.org')
        self._old_pass_edit = QLineEdit()
        self._old_pass_edit.setEchoMode(QLineEdit.Password)
        self._old_pass_edit.setPlaceholderText('Ancien mot de passe')
        self._new_pass_edit = QLineEdit()
        self._new_pass_edit.setEchoMode(QLineEdit.Password)
        self._new_pass_edit.setPlaceholderText('Nouveau mot de passe')
        self._confirm_pass_edit = QLineEdit()
        self._confirm_pass_edit.setEchoMode(QLineEdit.Password)
        self._confirm_pass_edit.setPlaceholderText('Confirmer le nouveau mot de passe')

        form.addRow('Email :', self._email_edit)
        form.addRow('Ancien mot de passe :', self._old_pass_edit)
        form.addRow('Nouveau mot de passe :', self._new_pass_edit)
        form.addRow('Confirmer :', self._confirm_pass_edit)

        layout.addLayout(form)

        # Boutons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._error_label = QLabel()
        self._error_label.setStyleSheet(f'color: {theme_manager.palette.error}; font-size: {theme_manager.font_size(11)}px;')
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self.setStyleSheet(self._STYLE)
        ds.theme_changed.connect(self._restyle)

    @safe_slot("ChangePasswordDialog._restyle")
    def _restyle(self):
        p = theme_manager.palette
        self.setStyleSheet(self._STYLE)
        self._title_lbl.setStyleSheet(
            f'font-size: {theme_manager.font_size(14)}px; font-weight: bold; color: {p.text_strong};')
        self._error_label.setStyleSheet(
            f'color: {p.error}; font-size: {theme_manager.font_size(11)}px;')

    @safe_slot("ChangePasswordDialog._on_accept")
    def _on_accept(self) -> None:
        email = self._email_edit.text().strip()
        old_pass = self._old_pass_edit.text()
        new_pass = self._new_pass_edit.text()
        confirm = self._confirm_pass_edit.text()

        if not email or not old_pass or not new_pass or not confirm:
            self._show_error('Tous les champs sont obligatoires.')
            return

        if new_pass != confirm:
            self._show_error('Les nouveaux mots de passe ne correspondent pas.')
            return

        if len(new_pass) < 6:
            self._show_error('Le nouveau mot de passe doit contenir au moins 6 caractères.')
            return

        # Vérifier l'ancien mot de passe via AuthManager (qui accepte Aec-2026)
        ok, _, err = AuthManager.auth_intranet(email, old_pass)
        if not ok:
            self._show_error(f'Ancien mot de passe incorrect : {err}')
            return

        # Mettre à jour le mot de passe dans PostgreSQL
        conn = db.server_conn
        if conn is None or db.server_mode != DBMode.INTRANET:
            self._show_error('Pas de connexion Intranet.')
            return

        new_hash = _sha256_hex(new_pass)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE larcauth_aecuser SET password = %s "
                    "WHERE LOWER(email) = %s",
                    (new_hash, email.lower())
                )
            conn.commit()
            QMessageBox.information(self, 'Succès', 'Mot de passe modifié avec succès.')
            self.accept()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._show_error(f'Erreur lors de la mise à jour : {e}')

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()

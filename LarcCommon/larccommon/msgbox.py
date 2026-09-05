"""Boîtes de dialogue aux boutons TOUJOURS visibles (tous thèmes).

Les QMessageBox/QColorDialog natifs Windows n'appliquent pas le QSS aux
boutons (OK blanc sur fond blanc). Ce module remplace les méthodes
statiques par un DIALOGUE Qt maison — rendu Qt garanti, styles par widget
avec la palette du thème actif.

Usage : appeler patch_message_boxes() une fois au démarrage (main.py).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
    QColorDialog,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager


def _button_qss(is_primary: bool) -> str:
    p = theme_manager.palette
    s = theme_manager.font_size
    if is_primary:
        return (f"QPushButton {{ background-color: {p.primary}; color: {p.on_primary}; "
                f"border: none; border-radius: {ds.radius_btn}px; "
                f"padding: {ds.space_xs}px {ds.space_xs * 2}px; "
                f"font-size: {s(13)}px; font-weight: bold; }} "
                f"QPushButton:hover {{ background-color: {p.primary_container}; "
                f"color: {p.text_strong}; }}")
    return (f"QPushButton {{ background-color: {p.surface_variant}; color: {p.text_strong}; "
            f"border: {ds.border_width}px solid {p.outline}; "
            f"border-radius: {ds.radius_btn}px; "
            f"padding: {ds.space_xs}px {ds.space_xs * 2}px; "
            f"font-size: {s(13)}px; }} "
            f"QPushButton:hover {{ background-color: {p.surface}; }}")


class _Box(QDialog):
    """Message box Qt avec boutons stylés par widget (rendu garanti)."""

    def __init__(self, icon_name: str, title: str, text: str,
                 buttons: list[tuple[int, str, bool]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(ds.window_width // 3)
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(f"QDialog {{ background: {p.surface}; }}")

        v = QVBoxLayout(self)
        v.setContentsMargins(ds.space_md + ds.space_xxs, ds.space_md + ds.space_xxs,
                             ds.space_md + ds.space_xxs, ds.space_md + ds.space_xxs)
        v.setSpacing(ds.space_m3)

        row = QHBoxLayout()
        row.setSpacing(ds.space_m3)
        from larccommon.icons import icon as md3_icon
        ic = QLabel()
        ic.setPixmap(md3_icon(icon_name, color=p.primary, size=ds.icon_md).pixmap(ds.icon_md, ds.icon_md))
        row.addWidget(ic, 0, Qt.AlignTop)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {p.text_strong}; font-size: {s(14)}px; border: none;")
        row.addWidget(lbl, 1)
        v.addLayout(row)

        self._result = None
        btns = QHBoxLayout()
        btns.addStretch()
        for role, label, is_prim in buttons:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(_button_qss(is_prim))
            b.clicked.connect(lambda checked=False, r=role:
                              (setattr(self, "_result", r), self.accept()))
            btns.addWidget(b)
        v.addLayout(btns)

    def exec(self):
        super().exec()
        return self._result


def _show(icon_name, title, text, buttons, parent):
    # no-popup-feedback : la boîte EST le message de sortie
    box = _Box(icon_name, title, text, buttons, parent)
    return box.exec()


def patch_message_boxes() -> None:
    """Remplace QMessageBox.* et QColorDialog.getColor par des versions Qt
    aux boutons visibles (styles par widget, palette du thème actif)."""
    from PySide6.QtWidgets import QMessageBox as _MB

    _MB.information = staticmethod(
        lambda parent, title, text, *a, **k:
        _show("info", title, text, [(QMessageBox.Ok, "OK", True)], parent))
    _MB.warning = staticmethod(
        lambda parent, title, text, *a, **k:
        _show("warning", title, text, [(QMessageBox.Ok, "OK", True)], parent))
    _MB.critical = staticmethod(
        lambda parent, title, text, *a, **k:
        _show("error", title, text, [(QMessageBox.Ok, "OK", True)], parent))
    _MB.question = staticmethod(
        lambda parent, title, text, *a, **k:
        _show("info", title, text,
              [(QMessageBox.No, "Non", False), (QMessageBox.Yes, "Oui", True)],
              parent))

    # Sélecteur de couleur Qt (les boutons du natif sont invisibles)
    def _patched_get_color(initial=QColor(), parent=None, title="", options=0):
        # no-popup-feedback : le sélecteur de couleur EST le message de sortie
        dlg = QColorDialog(initial, parent)
        if title:
            dlg.setWindowTitle(title)
        dlg.show()
        for b in dlg.findChildren(QPushButton):
            b.setStyleSheet(_button_qss(True))
            b.setCursor(Qt.PointingHandCursor)
        dlg.exec()
        return dlg.selectedColor()

    QColorDialog.getColor = staticmethod(_patched_get_color)

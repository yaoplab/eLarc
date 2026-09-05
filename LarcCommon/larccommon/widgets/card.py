from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.photos import get_photo_path
from .avatar import make_avatar
from .card_config import DEFAULT_CONFIG


class StudentCard(QFrame):
    clicked = Signal(int)

    def __init__(self, student_id: int, last_name: str, first_name: str, cfg=None):
        super().__init__()
        self._cfg = cfg or DEFAULT_CONFIG
        self._sid = student_id
        self._last_name = last_name
        self._first_name = first_name
        self.setFrameShape(QFrame.NoFrame)
        self._build(self._cfg)
        self._update_style(self._cfg)
        self.setFixedSize(self._cfg.card_w, self._cfg.card_h)
        self.setCursor(Qt.PointingHandCursor)

    def _build(self, cfg):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout()
        layout.setSpacing(cfg.spacing)
        layout.setContentsMargins(cfg.margin, cfg.margin, cfg.margin, cfg.margin)

        self._name_label = QLabel()
        self._name_label.setTextFormat(Qt.RichText)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setText(
            f"<b style='font-size:{s(cfg.font_name)}px; color:{p.text_strong}'>{self._last_name}</b><br>"
            f"<span style='font-size:{s(cfg.font_name)}px; color:{p.text_soft}'>{self._first_name}</span>"
        )

        self._photo_badge = QFrame()
        self._photo_badge.setFixedSize(cfg.badge_size, cfg.badge_size)
        self._photo_badge.setAttribute(Qt.WA_StyledBackground, True)
        self._photo_badge.setStyleSheet(
            f"background: {p.primary_container}; "
            f"border-radius: {cfg.border_radius}px;"
        )
        badge_layout = QVBoxLayout(self._photo_badge)
        badge_layout.setAlignment(Qt.AlignCenter)
        badge_layout.setContentsMargins(0, 0, 0, 0)

        self._photo = QLabel()
        self._photo.setFixedSize(cfg.photo_size, cfg.photo_size)
        self._photo.setAlignment(Qt.AlignCenter)

        pix = QPixmap(get_photo_path(self._sid))
        if pix.isNull() or pix.size().isNull():
            pix = make_avatar(self._last_name, self._first_name, cfg.photo_size, cfg.avatar_font)
        else:
            pix = pix.scaled(cfg.photo_size, cfg.photo_size,
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo.setPixmap(pix)

        badge_layout.addWidget(self._photo)

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(cfg.font_status)}px; font-weight: bold;")

        self._exit_label = QLabel()
        self._exit_label.setAlignment(Qt.AlignCenter)
        self._exit_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(cfg.font_exit)}px; "
            f"color: {theme_manager.palette.text_disabled};")

        layout.addWidget(self._name_label)
        layout.addStretch()
        layout.addWidget(self._photo_badge, 0, Qt.AlignCenter)

        # Q5 : 4 indicateurs D/M/P/E sous la photo (secretariat)
        self._badge_labels: dict[str, QLabel] = {}
        _badge_size = 14
        _badge_font = f"font-size: {max(7, _badge_size - 7)}px; font-weight: bold;"
        self._badges_row = QHBoxLayout()
        self._badges_row.setSpacing(ds.space_xxs)
        self._badges_row.setContentsMargins(0, 0, 0, 0)
        for badge_key, letter in [
            ("dossier_valid", "D"), ("parent_valid", "M"),
            ("photo_valid", "P"), ("email_valid", "E"),
        ]:
            circle = QLabel(letter)
            circle.setFixedSize(_badge_size, _badge_size)
            circle.setAlignment(Qt.AlignCenter)
            circle.setStyleSheet(
                f"background: {p.surface}; color: {p.error}; "
                f"border: 1px solid {p.error}; "
                f"border-radius: {_badge_size // 2}px; {_badge_font}")
            self._badges_row.addWidget(circle)
            self._badge_labels[badge_key] = circle
        layout.addLayout(self._badges_row)

        # Ligne evenements (superviseur) — cachee par defaut
        self._evt_label = QLabel()
        self._evt_label.setAlignment(Qt.AlignCenter)
        self._evt_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(10)}px; "
            f"color: {theme_manager.palette.text_strong};")
        self._evt_label.hide()
        layout.addWidget(self._evt_label)

        layout.addSpacing(cfg.spacing)
        layout.addWidget(self._status_label)
        layout.addWidget(self._exit_label)
        self.setLayout(layout)

    def _update_style(self, cfg):
        p = theme_manager.palette
        self._default_style = (
            f"StudentCard {{"
            f"  background: {p.surface};"
            f"  color: {p.text_strong};"
            f"  border: 1px solid {p.outline_variant};"
            f"  border-radius: {cfg.border_radius}px; padding: {cfg.padding}px;"
            f"}}"
            f"StudentCard:hover {{"
            f"  background: {p.surface_variant};"
            f"  color: {p.text_strong};"
            f"  border-color: {p.outline};"
            f"}}"
        )
        self.setStyleSheet(self._default_style)

    def refresh_photo(self):
        """Recharge la photo depuis le disque (apres changement)."""
        from PySide6.QtGui import QPixmapCache
        QPixmapCache.clear()
        pix = QPixmap(get_photo_path(self._sid))
        if pix.isNull() or pix.size().isNull():
            pix = make_avatar(self._last_name, self._first_name,
                            self._cfg.photo_size, self._cfg.avatar_font)
        else:
            pix = pix.scaled(self._cfg.photo_size, self._cfg.photo_size,
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo.setPixmap(pix)

    def mousePressEvent(self, event):
        self.clicked.emit(self._sid)
        super().mousePressEvent(event)

    def set_status(self, text: str, color: str):
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(13)}px; font-weight: bold; color: {color};")

    def set_exit_count(self, count: int):
        self._exit_label.setText(f"{count} sortie(s)" if count else '')

    def set_payment_status(self, status: str):
        """Bordure coloree + texte. Fond toujours surface (homogene)."""
        p = theme_manager.palette
        c = self._cfg
        colors = {
            "retard": (p.error, "En retard"),
            "normal": (p.success, "En cours"),
            "solde":  (p.primary, "Soldé"),
        }
        border_c, label = colors.get(status, (p.outline, ""))
        self.setStyleSheet(
            f"StudentCard {{"
            f"  background: {p.surface};"
            f"  color: {p.text_strong};"
            f"  border: {ds.border_width * 2}px solid {border_c};"
            f"  border-radius: {c.border_radius}px; padding: {c.padding}px;"
            f"}}"
            f"StudentCard:hover {{"
            f"  background: {p.surface_variant};"
            f"  border-color: {border_c};"
            f"}}")
        s = theme_manager.font_size
        self._status_label.setText(label)
        self._status_label.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {border_c};")

    def set_absent(self, absent: bool):
        p = theme_manager.palette
        c = self._cfg
        if absent:
            self.setStyleSheet(
                f"StudentCard {{"
                f"  background: {p.error_container};"
                f"  color: {p.text_strong};"
                f"  border: 2px solid {p.error};"
                f"  border-radius: {c.border_radius}px; padding: {c.padding}px;"
                f"}}"
                f"StudentCard:hover {{"
                f"  background: {p.error_container}; color: {p.text_strong};"
                f"  border-color: {p.error};"
                f"}}")
        else:
            self.setStyleSheet(self._default_style)

    # ── Champs etendus (secretaire, superviseur) ──

    def set_classroom(self, text: str):
        """Affiche la classe sous le nom."""
        if not hasattr(self, '_classroom_label'):
            self._classroom_label = QLabel()
            self._classroom_label.setAlignment(Qt.AlignCenter)
            self.layout().insertWidget(2, self._classroom_label)
        s = theme_manager.font_size
        p = theme_manager.palette
        self._classroom_label.setText(text)
        self._classroom_label.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_strong};")

    def set_presence(self, status: str):
        """Pastille coloree : present/absent/late/exited."""
        p = theme_manager.palette
        colors = {"present": p.success, "absent": p.error,
                  "late": p.tertiary, "exited": p.secondary}
        color = colors.get(status, p.text_disabled)
        labels = {"present": "Present", "absent": "Absent",
                  "late": "Retard", "exited": "Sorti"}
        self.set_status(labels.get(status, ""), color)

    _ROLE_SECRETARY = "secretary"
    _ROLE_SUPERVISOR = "supervisor"

    def set_role(self, role: str):
        """Configure la vignette pour un role : badges D/M/P/E (secretaire) ou compteurs (superviseur)."""
        if role == self._ROLE_SECRETARY:
            self._badges_row is not None  # garde les badges visibles
            self._evt_label.hide()
        else:
            # Superviseur : cacher les badges D/M/P/E, montrer le compteur d'evenements
            for i in range(self._badges_row.count()):
                w = self._badges_row.itemAt(i).widget()
                if w:
                    w.hide()
            self._evt_label.show()

    def set_validation(self, validation: dict | None):
        """Colorie les 4 cercles D/M/P/E selon les flags de validation JSONB."""
        if not hasattr(self, "_badge_labels") or not self._badge_labels or not validation:
            return
        p = theme_manager.palette
        _badge_size = 14
        _badge_font = f"font-size: {max(7, _badge_size - 7)}px; font-weight: bold;"
        for flag_key, badge_key in [
            ("dossier", "dossier_valid"), ("parent", "parent_valid"),
            ("photo", "photo_valid"), ("email", "email_valid"),
        ]:
            circle = self._badge_labels.get(badge_key)
            if circle is None:
                continue
            entry = validation.get(flag_key, {}) if isinstance(validation, dict) else {}
            ok = entry.get("ok", False)
            if ok:
                circle.setStyleSheet(
                    f"background: {p.success}; color: {p.on_error}; "
                    f"border: 1px solid {p.success}; "
                    f"border-radius: {_badge_size // 2}px; {_badge_font}")
            else:
                circle.setStyleSheet(
                    f"background: {p.surface}; color: {p.error}; "
                    f"border: 1px solid {p.error}; "
                    f"border-radius: {_badge_size // 2}px; {_badge_font}")

    def set_event_count(self, count: int):
        """Nombre d'evenements (superviseur). Masque le label si 0."""
        if count > 0:
            self._evt_label.setText(f"{count} evt(s)")
            self._evt_label.show()
        else:
            self._evt_label.hide()

    def set_metrics(self, absences: int = 0, lates: int = 0):
        """Affiche absences et retards du mois."""
        if not hasattr(self, '_metrics_label'):
            self._metrics_label = QLabel()
            self._metrics_label.setAlignment(Qt.AlignCenter)
            self.layout().addWidget(self._metrics_label)
        p = theme_manager.palette
        s = theme_manager.font_size
        parts = []
        if absences > 0:
            color = p.error if absences >= 10 else p.text_soft
            parts.append(f"<span style='color:{color}'>{absences} abs</span>")
        if lates > 0:
            color = p.tertiary if lates >= 5 else p.text_soft
            parts.append(f"<span style='color:{color}'>{lates} ret</span>")
        self._metrics_label.setText(" · ".join(parts) if parts else "")
        self._metrics_label.setStyleSheet(f"font-size: {s(10)}px;")
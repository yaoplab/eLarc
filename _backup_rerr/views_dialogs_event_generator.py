from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.logger import log
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.widgets import M3Button, M3Card, M3Label, M3TextField
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from LarcSuperviseur.common.database import db
from LarcSuperviseur.common.network import detect_network
from LarcSuperviseur.common.session import session
from LarcSuperviseur.common.theme import theme_manager
from LarcSuperviseur.views.core.event_type_repo import EventTypeRepo


class EventGenerator(ThemedDialog):
    # Couleurs résolues dynamiquement depuis la palette M3 (pas de hex en dur)
    _CAT_COLORS = {
        "Bureau BI": ("error", "on_error"),
        "Médical": ("primary", "on_primary"),
        "Sortie": ("tertiary", "on_tertiary"),
        "Suivi": ("active", "surface"),
    }

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            EventGenerator#evt_root {{
                background: {p.surface};
            }}
            QDateEdit, QTimeEdit {{
                padding: {ds.space_md}px;
                border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
                font-size: {s(13)}px;
                background: {p.surface};
                color: {p.text_strong};
                font-weight: bold;
            }}
            QLabel#evt_sep {{
                color: {p.outline};
            }}
            QPushButton#evt_crumb {{
                color: {p.text_strong};
                font-size: {s(14)}px; font-weight: bold;
                border: none; background: transparent;
                text-align: left; padding: {ds.space_xxs}px 0;
            }}
            QPushButton#evt_crumb:hover {{
                color: {p.primary_container};
            }}
            QLabel#evt_source {{
                font-weight: bold;
            }}
        """

    @safe_slot("EventGenerator._restyle_all")
    def _restyle_all(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass
        self._update_source_label()
        self._bd_update()

    def __init__(self, student_id: int, parent=None):
        super().__init__(parent)
        self._student_id = student_id
        self._locations = []
        self._classroom_lieu_ids = set()
        self._selected_lieu_id = 0
        self._selected_lieu_label = ""
        self._selected_subject = ""
        self._context = None
        self._ctx_has_step = False
        self._type_hierarchy = {}
        self._student_classroom_id = None
        self._student_classroom_label = ""
        self._loader = EventTypeRepo()
        self._path = []
        self._mode = None
        self._modes = []
        self._absence_types = []
        self._retard_durations = []
        self.setWindowTitle(_("event.window_title").format(id=student_id))
        self.setMinimumWidth(ds.window_width * 17 // 30)  # 680px
        self._load_student_classroom()
        self._load_types_from_db()
        self._load_locations()
        ds.theme_changed.connect(self._restyle_all)
        self._init_ui()
        self.setStyleSheet(self._STYLE)

    # ── Data loading ──

    def _load_student_classroom(self):
        data = self._loader.get_student_classroom(self._student_id)
        if data:
            self._student_classroom_id = data["classroom_id"]
            self._student_classroom_label = data["label"]

    def _load_locations(self):
        self._locations = self._loader.get_locations()

    def _load_types_from_db(self):
        """Taxonomie pilotée par l'arbre larcauth_type_event (migration 2026-08-30).

        N0 = racines (Absence, Événement, Retard) ; N1 absence = enfants de la
        racine absence (école/cours) ; motifs = enfants du N1 ; Événement :
        contexte éphémère (En cours/Ailleurs) puis matières/lieux puis l'arbre
        des types sous la racine 'evenement'.
        """
        try:
            roots = self._loader.get_event_types_roots()
        except Exception as e:
            log(f"EventGenerator._load_types_from_db: {e}")
            roots = []
        if not roots:
            log("EventGenerator._load_types_from_db: aucun mode chargé — fallback 'Autres'")
            self._modes = [("Autres", "autres")]
            self._type_hierarchy = {}
            self._absence_branches = {}
            self._root_by_code = {}
            return
        self._root_by_code = {r["code"]: r for r in roots}
        self._modes = [(r["label"], r["code"]) for r in roots]
        # Branche Absence : N1 (école/cours) → motifs
        self._absence_branches = {}
        absence_root = self._root_by_code.get("absence")
        if absence_root:
            self._absence_branches = {
                c["id"]: c for c in self._loader.get_event_types_children(absence_root["id"])
            }
        # Arbre des types pour la branche Événement (même liste en cours/ailleurs)
        self._type_hierarchy = {}
        if "evenement" in self._root_by_code:
            self._type_hierarchy = self._loader.get_event_types_subtree("evenement")

    # ── UI ──

    def _init_ui(self):
        p = theme_manager.palette

        # Le fond est géré par _STYLE via EventGenerator#evt_root
        self.setObjectName("evt_root")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg  # 32px → Fibo LG
        )
        outer.setSpacing(ds.space_md)  # 20px → Fibo MD

        # ── Breadcrumb bar ──
        self._crumb_widget = QWidget()
        self._crumb_layout = QHBoxLayout(self._crumb_widget)
        self._crumb_layout.setContentsMargins(0, 0, 0, 0)
        self._crumb_layout.setSpacing(ds.space_xs)  # 8px → Fibo XS
        self._crumb_widget.hide()
        outer.addWidget(self._crumb_widget)

        # ── Step container (espace unique réinitialisé à chaque étape) ──
        self._step_card = M3Card(variant=CardVariant.ELEVATED, parent=self)
        sl = self._step_card.content_layout()
        sl.setContentsMargins(
            ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg  # 32px
        )
        self._step_grid = QGridLayout()
        self._step_grid.setSpacing(ds.space_sm)  # 12px → Fibo SM
        sl.addLayout(self._step_grid)
        outer.addWidget(self._step_card)

        # ── Badge (résumé de l'événement) ──
        self._bd = M3Card(variant=CardVariant.FILLED, parent=self)
        bdl = self._bd.content_layout()
        bdl.setContentsMargins(
            ds.space_xl, ds.space_sm, ds.space_xl, ds.space_sm  # 52px 12px
        )
        self._btxt = M3Label("", style="title_medium")
        self._btxt.setAlignment(Qt.AlignCenter)
        bdl.addWidget(self._btxt)
        self._bd.hide()
        outer.addWidget(self._bd)

        # ── Final section (date / note / actions) ──
        self._final = QWidget()
        fl = QVBoxLayout(self._final)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(ds.space_md)  # 20px

        dr = QHBoxLayout()
        dr.setSpacing(ds.space_md)  # 20px
        dr.addWidget(M3Label(_("event.date"), style="body_medium"))
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dddd dd MMMM yyyy")
        dr.addWidget(self._date_edit, 2)
        dr.addWidget(M3Label(_("event.time"), style="body_medium"))
        self._time_edit = QTimeEdit(QTime.currentTime())
        self._time_edit.setDisplayFormat("HH:mm")
        dr.addWidget(self._time_edit, 1)
        self._src = M3Label("", style="body_small")
        self._update_source_label()
        dr.addWidget(self._src)
        fl.addLayout(dr)

        fl.addWidget(M3Label(_("event.note"), style="body_medium"))
        self._ni = M3TextField(placeholder=_("event.note_placeholder"))
        fl.addWidget(self._ni)

        ar = QHBoxLayout()
        ar.addStretch()
        cb = M3Button(_("common.button.cancel"), variant=ButtonVariant.OUTLINED)
        cb.clicked.connect(self.reject)
        ar.addWidget(cb)
        self._vb = M3Button(_("event.validate_button"), variant=ButtonVariant.FILLED)
        self._vb.clicked.connect(self._validate)
        ar.addWidget(self._vb)
        fl.addLayout(ar)

        self._final.hide()
        outer.addWidget(self._final)

        self._show_step()

    # ── Step rendering ──

    def _show_step(self):
        self._step_card.hide()
        self._clear_grid(self._step_grid)
        self._update_breadcrumb()

        if not self._path:
            self._show_mode_buttons()
            self._step_card.show()
            self._bd.hide()
            self._final.hide()
            return

        if self._is_final_step():
            self._step_card.hide()
            self._bd_update()
            self._bd.show()
            self._final.show()
            return

        if self._mode in ("absence", "retard"):
            if len(self._path) == 1:
                self._show_absence_branches()
            elif len(self._path) == 2:
                self._show_absence_motifs()
        elif self._mode == "evenement":
            if len(self._path) == 1:
                self._show_context_buttons()
            elif len(self._path) == 2:
                self._show_context_pick()
            elif len(self._path) >= 3:
                self._show_type_options()
        elif self._mode == "autres":  # fallback (DB vide)
            if len(self._path) == 1:
                self._show_locations()
            elif len(self._path) >= 2:
                self._show_type_options()

        self._step_card.show()
        self._bd.hide()
        self._final.hide()

        self.adjustSize()

    def _show_mode_buttons(self):
        h = ds.space_xl * 2  # 104px
        for idx, (label, mode) in enumerate(self._modes):
            b = M3Button(label, variant=ButtonVariant.TONAL)
            b.setMinimumHeight(h)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked, l=label, m=mode: self._on_step_click(l, mode=m))
            self._step_grid.addWidget(b, 0, idx)

    def _children_by_label(self, parent_id: int) -> dict:
        return {c["label"]: c for c in self._loader.get_event_types_children(parent_id)}

    def _absent_branch_node(self):
        """Nœud N1 du mode absence/retard correspondant à _path[1]."""
        root = self._root_by_code.get(self._mode)
        if not root or len(self._path) < 2:
            return None
        return self._children_by_label(root["id"]).get(self._path[1])

    def _show_absence_branches(self):
        """N1 : enfants de la racine du mode (Absent de l'école / Absent du cours)."""
        root = self._root_by_code.get(self._mode)
        if not root:
            return
        for idx, c in enumerate(self._loader.get_event_types_children(root["id"])):
            b = M3Button(c["label"], variant=ButtonVariant.TONAL)
            b.setMinimumHeight(ds.space_xl - ds.space_xxs)  # 48px
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked, l=c["label"]: self._on_step_click(l))
            self._step_grid.addWidget(b, idx // 3, idx % 3)

    def _show_absence_motifs(self):
        """N2 : motifs/cas = enfants du N1 sélectionné (path[1])."""
        node = self._absent_branch_node()
        if not node:
            return
        for idx, c in enumerate(self._loader.get_event_types_children(node["id"])):
            b = M3Button(c["label"], variant=ButtonVariant.TONAL)
            b.setMinimumHeight(ds.space_xl - ds.space_xxs)  # 48px
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked, l=c["label"]: self._on_step_click(l))
            self._step_grid.addWidget(b, idx // 3, idx % 3)

    def _show_context_buttons(self):
        """N1 Événement : contexte éphémère En cours / Ailleurs (pas des nœuds DB)."""
        h = ds.space_xl * 2  # 104px
        for idx, (label, ctx) in enumerate(
            [(_("event_types.in_class"), "cours"), (_("event_types.elsewhere"), "hors")]
        ):
            b = M3Button(label, variant=ButtonVariant.TONAL)
            b.setMinimumHeight(h)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked, l=label, c=ctx: self._on_step_click(l, context=c))
            self._step_grid.addWidget(b, 0, idx)

    def _show_context_pick(self):
        """N2 Événement : matières (En cours) ou lieux (Ailleurs) ; sinon types."""
        if self._context == "cours" and self._student_classroom_id:
            term_id = self._loader.get_term_id()
            subjects = self._loader.get_classroom_subjects(self._student_classroom_id, term_id)
            if subjects:
                self._ctx_has_step = True
                self._show_subjects()
                return
        elif self._context == "hors" and self._locations:
            self._ctx_has_step = True
            self._show_locations()
            return
        self._show_type_options()

    def _show_locations(self):
        for idx, (lid, sid, lieu_name) in enumerate(self._locations):
            b = M3Button(lieu_name, variant=ButtonVariant.OUTLINED)
            b.setMinimumHeight(ds.space_xl - ds.space_xs)  # 44px
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(
                lambda checked, l=lieu_name, lid=lid: self._on_step_click(
                    l, lieu_id=lid, lieu_label=l
                )
            )
            self._step_grid.addWidget(b, idx // 3, idx % 3)
            if sid:
                self._classroom_lieu_ids.add(lid)

    def _is_classroom(self):
        return self._selected_lieu_id in self._classroom_lieu_ids

    def _show_subjects(self):
        if not self._student_classroom_id:
            self._show_type_options()
            return
        term_id = self._loader.get_term_id()
        subjects = self._loader.get_classroom_subjects(self._student_classroom_id, term_id)
        if not subjects:
            self._show_type_options()
            return
        for idx, (sid, label, tid, tname) in enumerate(subjects):
            b = M3Button(label, variant=ButtonVariant.OUTLINED)
            b.setMinimumHeight(ds.space_xl - ds.space_sm)  # 40px
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tname or "")
            b.clicked.connect(lambda checked, l=label: self._on_step_click(l, subject_label=l))
            self._step_grid.addWidget(b, idx // 4, idx % 4)

    def _show_type_options(self):
        p = theme_manager.palette
        node = self._get_type_node()
        if node is None:
            return
        if isinstance(node, dict):
            for idx, (k, v) in enumerate(node.items()):
                roles = self._CAT_COLORS.get(k, ("primary", "on_primary"))
                bg = getattr(p, roles[0], p.primary)
                fg = getattr(p, roles[1], p.on_primary)
                b = M3Button(k, variant=ButtonVariant.FILLED)
                b.setMinimumHeight(ds.button_height)  # 52px
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"M3Button {{ background-color: {bg}; color: {fg}; }}")
                b.clicked.connect(lambda checked, l=k: self._on_step_click(l))
                self._step_grid.addWidget(b, idx // 2, idx % 2)
        elif isinstance(node, list):
            for idx, leaf in enumerate(node):
                b = M3Button(leaf, variant=ButtonVariant.TONAL)
                b.setMinimumHeight(ds.space_xl - ds.space_xxs)  # 48px
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda checked, l=leaf: self._on_step_click(l))
                self._step_grid.addWidget(b, idx // 3, idx % 3)

    # ── Step click ──

    def _on_step_click(self, label, **data):
        self._path.append(label)
        if "mode" in data:
            self._mode = data["mode"]
            self._context = None
            self._ctx_has_step = False
        if "context" in data:
            self._context = data["context"]
            self._ctx_has_step = False
        if "lieu_id" in data:
            self._selected_lieu_id = data["lieu_id"]
            self._selected_lieu_label = data.get("lieu_label", label)
        if "subject_label" in data:
            self._selected_subject = data["subject_label"]
        self._show_step()

    # ── Breadcrumb ──

    def _update_breadcrumb(self):
        while self._crumb_layout.count():
            item = self._crumb_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.deleteLater()

        if not self._path:
            self._crumb_widget.hide()
            return

        p = theme_manager.palette
        s = theme_manager.font_size

        for i, label in enumerate(self._path):
            if i > 0:
                sep = M3Label(">", style="body_medium")
                sep.setObjectName("evt_sep")
                self._crumb_layout.addWidget(sep)

            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFlat(True)
            is_last = i == len(self._path) - 1
            if is_last:
                btn.setStyleSheet(
                    f"QPushButton {{ color: {p.text_strong}; font-size: {s(14)}px; font-weight: bold; "
                    f"border: none; background: transparent; text-align: left; "
                    f"padding: {ds.space_xxs}px 0; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ color: {p.primary}; font-size: {s(14)}px; font-weight: bold; "
                    f"border: none; background: transparent; text-align: left; "
                    f"padding: {ds.space_xxs}px 0; }}"
                    f"QPushButton:hover {{ color: {p.primary_container}; }}"
                )
                btn.clicked.connect(lambda checked, idx=i: self._on_crumb_click(idx))
            self._crumb_layout.addWidget(btn)

        self._crumb_layout.addStretch()
        self._crumb_widget.show()

    def _on_crumb_click(self, index):
        self._path = self._path[: index + 1]
        if self._mode == "evenement":
            if len(self._path) < 2:
                self._context = None
            self._selected_lieu_id = 0
            self._selected_lieu_label = ""
            self._selected_subject = ""
        elif self._mode == "autres" and len(self._path) < 2:
            self._selected_lieu_id = 0
            self._selected_lieu_label = ""
        self._show_step()

    # ── Helpers ──

    def _clear_grid(self, g):
        while g.count():
            w = g.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _type_start(self):
        """Index dans _path où commence les types (branche Événement)."""
        if self._mode == "evenement" and len(self._path) >= 2:
            return 3 if self._ctx_has_step else 2
        return None

    def _get_type_node(self):
        start = self._type_start()
        if start is None:
            return None
        if len(self._path) == start:
            return self._type_hierarchy
        node = self._type_hierarchy
        for label in self._path[start:]:
            if isinstance(node, dict):
                node = node.get(label)
            elif isinstance(node, list):
                return None
            else:
                return None
        return node

    def _is_final_step(self):
        if not self._path:
            return False
        if self._mode in ("absence", "retard"):
            if len(self._path) >= 3:
                return True
            if len(self._path) == 2:
                node = self._absent_branch_node()
                if node is None or not self._loader.get_event_types_children(node["id"]):
                    return True
            return False
        if self._mode in ("evenement", "autres"):
            start = self._type_start()
            if start is None or len(self._path) < start:
                return False
            if len(self._path) == start:
                return False  # une catégorie vient d'être choisie → niveau suivant
            node = self._get_type_node()
            if node is None or not isinstance(node, (dict, list)) or len(node) == 0:
                return True
        return False

    def _compute_type_path(self):
        """Chaîne canonique DEPUIS la racine de catégorie (préfixes compatibles
        avec les motifs ILIKE actuels : 'Absence%', 'Sortie%', 'Bureau BI'…)."""
        if self._mode in ("absence", "retard") and len(self._path) >= 2:
            return " > ".join(self._path)
        if self._mode in ("evenement", "autres"):
            start = self._type_start()
            if start is not None and len(self._path) > start:
                return " > ".join(self._path[start:])
        return None

    # ── Badge & source ──

    def _bd_update(self):
        p = theme_manager.palette
        type_path = self._compute_type_path()
        if not type_path:
            self._bd.hide()
            return
        if self._mode == "absence":
            self._btxt.setText(_("event.badge_absence").format(path=type_path))
            self._btxt.setStyleSheet(f"color: {p.on_error}; font-weight: bold;")
            self._bd.setStyleSheet(f"M3Card {{ background: {p.error}; border-radius: {ds.radius_md}px; }}")
        elif self._mode == "retard":
            self._btxt.setText(_("event.badge_retard").format(path=type_path))
            self._btxt.setStyleSheet(f"color: {p.on_tertiary}; font-weight: bold;")
            self._bd.setStyleSheet(f"M3Card {{ background: {p.tertiary}; border-radius: {ds.radius_md}px; }}")
        else:
            txt = _("event.badge_other").format(path=type_path)
            if self._selected_lieu_label:
                txt += f"  —  {self._selected_lieu_label}"
            self._btxt.setText(txt)
            self._btxt.setStyleSheet(f"color: {p.on_primary}; font-weight: bold;")
            self._bd.setStyleSheet(f"M3Card {{ background: {p.primary}; border-radius: {ds.radius_md}px; }}")
        self._bd.show()

    def _update_source_label(self):
        p = theme_manager.palette
        ok, _ign = detect_network()
        if ok and db.is_server_connected:
            self._src.setText(_("event.source_intranet"))
            self._src.setStyleSheet(f"color: {p.primary}; font-weight: bold;")
        else:
            self._src.setText(_("event.source_cloud"))
            self._src.setStyleSheet(f"color: {p.tertiary}; font-weight: bold;")

    # ── Validate ──

    @safe_slot("EventGenerator.validate")
    def _validate(self):
        type_path = self._compute_type_path()
        if not type_path:
            QMessageBox.warning(
                self, _("common.dialog.error_title"), _("event.select_type_required")
            )
            return
        evt = self._date_edit.date().toString("yyyy-MM-dd")
        try:
            cur = db.server_conn.cursor()
            cur.execute("SELECT MAX(date_all) FROM larcauth_agenda")
            r = cur.fetchone()
            if r and r[0]:
                last = str(r[0])[:10]
                if evt > last:
                    QMessageBox.warning(
                        self,
                        _("common.dialog.error_title"),
                        _("event.date_error").format(last=last),
                    )
                    return
        except Exception as e:
            log(f"EventGenerator._validate: {e}")
        self.accept()

    def get_data(self) -> dict:
        dt = self._date_edit.dateTime()
        dt.setTime(self._time_edit.time())
        type_path = self._compute_type_path()
        is_abs_or_ret = self._mode in ("absence", "retard")
        return {
            "student_id": self._student_id,
            "event_type": type_path,
            "event_type_id": self._loader.resolve_event_type_id(type_path) if type_path else None,
            "event_at": dt.toString("yyyy-MM-dd HH:mm:ss"),
            "classroom_id": self._student_classroom_id,
            "classroom_label": self._student_classroom_label,
            "lieu_id": self._selected_lieu_id if not is_abs_or_ret else 0,
            "lieu_label": self._selected_lieu_label if not is_abs_or_ret else "",
            "subject_id": None,
            "subject_label": self._selected_subject,
            "note": self._ni.text().strip(),
            "source": "cloud" if not detect_network()[0] else "intranet",
        }

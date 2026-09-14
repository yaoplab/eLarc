"""
SidebarWidget — Barre latérale partagée pour LarcSuperviseur et LarcSecretaire.

Utilise QssHelper.sidebar_*() pour le QSS (Sous-système K du skill design-system-larc).
Garantit un rendu identique dans les deux apps.

Usage:
    from larccommon.widgets.sidebar import SidebarWidget

    prog_style = {
        "PEI": ("primary", "primary_container", "on_primary"),  # ← noms de rôles, PAS couleurs
        ...
    }
    sections = [
        ("Collège", [("PEI", "PEI"), ("MYP", "MYP")]),
        ("Lycée", [("DP", "DPFr"), ("DPEn", "DPEn")]),
    ]
    sidebar = SidebarWidget(sections, prog_style)
    sidebar.load_classes(class_list)  # [(id, label, program_id, sigle), ...]

    sidebar.class_selected.connect(self._on_class_clicked)
    sidebar.group_selected.connect(self._on_group_selected)
    sidebar.all_selected.connect(self._on_all_clicked)

Les couleurs sont résolues dynamiquement depuis theme_manager.palette à chaque
_rebuild(), ce qui garantit une harmonie parfaite après changement de thème.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from phibuilder.widgets import M3Button, M3Frame, M3ScrollArea

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import QssHelper, theme_manager
from larccommon.widgets.themed_widget import ThemedWidget


class SidebarWidget(M3ScrollArea):
    """Barre latérale modulaire conforme au Sous-système K.

    Les couleurs des programmes sont stockées sous forme de **noms de rôles**
    (ex: "primary", "primary_container") et résolues dynamiquement depuis
    ``theme_manager.palette`` à chaque ``_rebuild()``. Cela garantit un rendu
    identique dans les deux apps, quel que soit le thème actif.

    Signaux :
        class_selected(int, str)  — émis quand une classe est cliquée
        all_selected()            — émis quand "Toutes les classes" est cliqué
        group_selected(str)       — émis quand une section/programme est cliqué
    """

    class_selected = Signal(int, str)
    all_selected = Signal()
    group_selected = Signal(str)

    # Tailles fixes (px) — voir Sous-système K9/K11/K14
    COL_W = 89       # theme_manager.image.logo
    H_PROG = 34      # hauteur en-tête programme (harmonisé avec bouton classe)
    H_CLASS = 34     # hauteur bouton classe (theme_manager.image.theme_btn)
    H_ALL = 55       # hauteur bouton Toutes classes (SpacingToken.HUGE)

    def __init__(
        self,
        sections: list[tuple[str, list[tuple[str, str]]]],
        prog_style: dict[str, tuple[str, str, str]],
        parent: Optional[QWidget] = None,
    ):
        """Initialise le sidebar.

        Args:
            sections: [(nom_section, [(colonne, clé_prog), ...]), ...]
                      ex: [("Collège", [("PEI", "PEI"), ("MYP", "MYP")])]
            prog_style: {clé: (fg_role, bg_role, on_fg_role)}
                      ex: {"PEI": ("primary", "primary_container", "on_primary")}
                      Les rôles sont les noms d'attributs de ``Palette``.
            parent: widget parent optionnel
        """
        super().__init__(theme=theme_manager.phi_theme, parent=parent)
        self._sections = sections
        self._prog_style = prog_style
        self._classes: list[tuple] = []
        self._selected_btn: Optional[M3Button] = None

        # Conteneur (K1: M3ScrollArea + K5: sidebar_container)
        # Stocké dans _container pour appliquer le QSS DIRECTEMENT dessus
        # (évite le bug Qt où le QSS du parent QScrollArea ne cascade pas au contenu)
        self._container = ThemedWidget(object_name="sidebar")
        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setFrameShape(M3Frame.NoFrame)
        self.setFixedWidth(ds.sidebar_width)  # K2: ds.sidebar_width = 233

        # Fond réel (PAS « transparent » : palette noire héritée sinon —
        # bug contraste 2026-08-16). Le fond est aussi géré par _container.
        self.viewport().setStyleSheet(
            f"background: {theme_manager.palette.surface};")

        # Guard palette sur le container (redondant avec QSS mais robuste en dark)
        pal = self._container.palette()
        pal.setColor(self._container.backgroundRole(), QColor(theme_manager.palette.surface))
        self._container.setPalette(pal)
        self._container.setAutoFillBackground(True)

        # Layout (K3: ds.space_sm vertical margins, K4: ds.space_xs spacing)
        # Marges horizontales = 0 (le parent sidebar_layout les gere)
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, ds.space_sm, 0, ds.space_sm)
        self._layout.setSpacing(ds.space_xs)

        # Connexion au changement de thème
        theme_manager.theme_changed.connect(self._rebuild)

    def set_header_widgets(self, widgets: list):
        """Widgets inseres en haut du sidebar (avant les sections)."""
        self._header_widgets = widgets

    def load_classes(self, classes: list[tuple]):
        """Charge les classes et reconstruit le sidebar."""
        self._classes = classes
        self._rebuild()

    def _resolve_colors(self, fg_role: str, bg_role: str, on_fg_role: str) -> tuple[str, str, str]:
        """Résout les noms de rôles en couleurs actuelles depuis la palette active."""
        p = theme_manager.palette
        return (getattr(p, fg_role), getattr(p, bg_role), getattr(p, on_fg_role))

    @safe_slot("SidebarWidget._rebuild")
    def _rebuild(self):
        """Reconstruit toutes les sections du sidebar avec les couleurs actuelles.
        Appelé automatiquement lors du changement de thème (theme_changed).
        """
        # Nettoyage — les header widgets (externes, persistants, re-ajoutés
        # ci-dessous) ne doivent PAS être détruits : ce sont les MÊMES objets
        # réutilisés à chaque rebuild, contrairement aux boutons de section/
        # classe qui sont recréés à chaque appel.
        header_widgets = set(getattr(self, '_header_widgets', []))
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w and w not in header_widgets:
                w.deleteLater()
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    cw = child.widget()
                    if cw:
                        cw.deleteLater()

        self._selected_btn = None

        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size

        # Appliquer le fond DIRECTEMENT sur le conteneur (QScrollArea ne cascade pas fiablement)
        bg = p.surface
        self._container.setStyleSheet(
            f"background: {bg}; border: none;"
        )
        # Guard palette : garantit le fond même si Qt réinitialise le QSS
        pal = self._container.palette()
        pal.setColor(self._container.backgroundRole(), QColor(bg))
        self._container.setPalette(pal)

        # Widgets d'en-tete (boutons d'action, etc.)
        for w in getattr(self, '_header_widgets', []):
            self._layout.addWidget(w)

        # Grouper les classes par programme
        groups: dict[str, list[tuple[int, str]]] = {k: [] for k in self._prog_style}
        for row in self._classes:
            if len(row) >= 4:
                cid, label, _pid, sigle = row[:4]
                if sigle in groups:
                    groups[sigle].append((cid, label))

        for sec_name, columns in self._sections:
            # En-tête section — fond sombre, texte clair (style bouton proéminent)
            sec_hdr = M3Button(sec_name, theme=theme_manager.phi_theme)
            sec_hdr.setObjectName("sidebar_sec_hdr")
            sec_hdr.setMinimumHeight(ds.field_height + ds.space_xs)
            sec_hdr.setCursor(Qt.PointingHandCursor)
            sec_hdr.setStyleSheet(
                f"M3Button {{ background: {p.text_strong}; color: {p.surface}; "
                f"border: none; border-radius: {ds.radius_sm}px; "
                f"font-size: {s(12)}px; font-weight: bold; "
                f"padding: {ds.space_xs}px {ds.space_sm}px; }}"
                f"M3Button:hover {{ background: {p.primary}; color: {p.on_primary}; }}")
            sec_hdr.clicked.connect(
                lambda checked, sn=sec_name: self._on_section_clicked(sn)
            )
            self._layout.addWidget(sec_hdr)

            grd = QGridLayout()
            grd.setSpacing(ds.space_xxs)

            for col_idx, (hdr_text, prog_key) in enumerate(columns):
                if prog_key not in self._prog_style:
                    continue
                fg_role, bg_role, on_fg_role = self._prog_style[prog_key]
                fg, bg, on_fg = self._resolve_colors(fg_role, bg_role, on_fg_role)
                items = groups.get(prog_key, [])

                # En-tête programme (K8: couleur PLEINE, QSS sans sélecteur)
                col_hdr = M3Button(hdr_text, theme=theme_manager.phi_theme)
                col_hdr.setObjectName("sidebar_prog_hdr")
                col_hdr.setFixedSize(self.COL_W, self.H_PROG)
                col_hdr.setCursor(Qt.PointingHandCursor)
                col_hdr.setStyleSheet(QssHelper.sidebar_program_header_inline(p, s, fg, on_fg))
                col_hdr.clicked.connect(
                    lambda checked, pk=prog_key: self._on_prog_clicked(pk)
                )
                grd.addWidget(col_hdr, 0, col_idx)

                # Boutons de classe (K10: couleur CONTAINER, QSS sans sélecteur)
                for i, (cid, label) in enumerate(items):
                    btn = M3Button(label, theme=theme_manager.phi_theme)
                    btn.setObjectName("sidebar_class_btn")
                    btn.setFixedSize(self.COL_W, self.H_CLASS)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setCheckable(True)  # K12
                    btn.setStyleSheet(QssHelper.sidebar_class_button_inline(p, s, bg, fg))
                    btn.clicked.connect(
                        lambda checked, c=cid, l=label, b=btn: self._on_class_clicked(c, l, b)
                    )
                    grd.addWidget(btn, i + 1, col_idx)

            self._layout.addLayout(grd)
            self._layout.addSpacing(ds.space_xs)

        # Bouton Lycée + Collège (même style que les en-têtes de section)
        self._all_btn = M3Button(_("sidebar.all_classes"), theme=theme_manager.phi_theme)
        self._all_btn.setObjectName("sidebar_all_btn")
        self._all_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        self._all_btn.setCursor(Qt.PointingHandCursor)
        self._all_btn.setStyleSheet(
            f"M3Button {{ background: {p.text_strong}; color: {p.surface}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"font-size: {s(12)}px; font-weight: bold; "
            f"padding: {ds.space_xs}px {ds.space_sm}px; }}"
            f"M3Button:hover {{ background: {p.primary}; color: {p.on_primary}; }}")
        self._all_btn.clicked.connect(self._on_all_clicked)
        self._layout.addWidget(self._all_btn)
        self._layout.addStretch()

        # Repartir en haut à chaque reconstruction — sinon le scroll
        # automatique de Qt (clic sur « Toutes les classes » en bas)
        # masque les sections du haut (Maternelle/Primaire invisibles)
        self.verticalScrollBar().setValue(0)

    # ---- Gestion de la sélection -----------------------------------------------

    def _clear_selection(self):
        if self._selected_btn is not None:
            try:
                self._selected_btn.setChecked(False)
            except RuntimeError:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
            self._selected_btn = None

    # ---- Handlers avec @safe_slot ---------------------------------------------

    @safe_slot("SidebarWidget.on_section_clicked")
    def _on_section_clicked(self, section: str):
        self._clear_selection()
        self.group_selected.emit(section)

    @safe_slot("SidebarWidget.on_prog_clicked")
    def _on_prog_clicked(self, prog: str):
        self._clear_selection()
        self.group_selected.emit(f"grp_{prog.lower()}")

    @safe_slot("SidebarWidget.on_class_clicked")
    def _on_class_clicked(self, class_id: int, label: str, btn: M3Button):
        self._clear_selection()
        btn.setChecked(True)
        self._selected_btn = btn
        self.class_selected.emit(class_id, label)

    def _restyle(self):
        """Alias pour D7 : _rebuild() reconstruit tout avec les couleurs actuelles."""
        self._rebuild()

    @safe_slot("SidebarWidget.on_all_clicked")
    def _on_all_clicked(self):
        self._clear_selection()
        self.all_selected.emit()
        # Remonter en haut : le clic sur le bouton du bas fait défiler la
        # sidebar (ensureWidgetVisible) et cache les sections supérieures
        self.verticalScrollBar().setValue(0)

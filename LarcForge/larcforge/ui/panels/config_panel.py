"""Panneau Configuration : racine, marque (école/thème), profils de
connexion DB, profils de vérification — personnalisation « école ».

Chaque section enregistre immédiatement dans ui_config.json (store.save) :
la configuration fonctionne même quand la base est indisponible (c'est
d'ici qu'on répare l'accès DB).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import THEMES_CONFIG, theme_manager
from phibuilder.widgets import (
    M3Button, M3Card, M3ComboBox, M3Label, M3ScrollArea, M3TextField,
)
from phibuilder.widgets.button import ButtonVariant

from ... import config as cfg
from ... import database as pg
from .common import BodyLabel, SectionTitle, restyle_card, restyle_label
from .run_panel import _LEVELS, _SINCE

_THEME_KEYS = [k for k, _, _, _ in THEMES_CONFIG]


class ConfigPanel(QWidget):
    """Formulaire de configuration — 4 cartes, sauvegarde immédiate."""

    branding_changed = Signal()

    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        self._cards: list[M3Card] = []
        self._labels: list = []
        self._msg_labels: dict[str, BodyLabel] = {}
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        phi = theme_manager.phi_theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        lay.setSpacing(ds.space_sm)
        self._title = SectionTitle("Configuration")
        lay.addWidget(self._title)
        lay.addWidget(BodyLabel(
            "Personnalisez l'outil pour votre école : nom affiché, thème, "
            "bases de données et contrôles à lancer. Chaque section "
            "enregistre immédiatement (fichier ui_config.json)."))

        scroll = M3ScrollArea(theme=phi)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(M3ScrollArea.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        cl.setSpacing(ds.space_sm)

        self._build_root_card(cl)
        self._build_branding_card(cl)
        self._build_db_card(cl)
        self._build_run_card(cl)
        cl.addStretch()
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)

    def _card(self, parent_layout: QVBoxLayout, title: str,
              subtitle: str) -> M3Card:
        card = M3Card(theme=theme_manager.phi_theme, variant=ds.CARD_FILLED)
        cl = card.content_layout()
        cl.setSpacing(ds.space_sm)
        lbl = M3Label(title, theme=theme_manager.phi_theme, style="title_medium")
        cl.addWidget(lbl)
        self._labels.append(lbl)
        sub = BodyLabel(subtitle)
        cl.addWidget(sub)
        parent_layout.addWidget(card)
        self._cards.append(card)
        return card

    def _field_row(self, layout: QVBoxLayout, label: str,
                   placeholder: str = "") -> M3TextField:
        """Champ plein largeur avec libellé au-dessus (pattern _flat_field)."""
        layout.addWidget(BodyLabel(label))
        field = M3TextField(theme=theme_manager.phi_theme,
                            placeholder=placeholder)
        field.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(field)
        return field

    def _msg(self, layout: QVBoxLayout, key: str) -> BodyLabel:
        msg = BodyLabel("")
        layout.addWidget(msg)
        self._msg_labels[key] = msg
        return msg

    def _checks_group(self, layout: QVBoxLayout, title: str,
                      keys: list[str]) -> dict[str, QCheckBox]:
        """Ligne de cases à cocher + bouton « Tout cocher » câblé."""
        row = QHBoxLayout()
        row.setSpacing(ds.space_sm)
        row.addWidget(BodyLabel(title))
        row.addStretch()
        tout = M3Button("Tout cocher", theme=theme_manager.phi_theme,
                        variant=ButtonVariant.TEXT)
        row.addWidget(tout)
        layout.addLayout(row)
        checks: dict[str, QCheckBox] = {}
        box = QHBoxLayout()
        box.setSpacing(ds.space_md)
        for key in keys:
            c = QCheckBox(str(key))
            c.setStyleSheet(ds.flat_input_qss())
            box.addWidget(c)
            checks[str(key)] = c
        layout.addLayout(box)
        tout.clicked.connect(lambda checked, g=checks: self._toggle_checks(g))
        return checks

    @safe_slot("ConfigPanel.toggle_checks")
    def _toggle_checks(self, checks: dict[str, QCheckBox]):
        any_checked = any(c.isChecked() for c in checks.values())
        for c in checks.values():
            c.setChecked(not any_checked)

    # ── 1. Racine du monorepo ─────────────────────────────────────────

    def _build_root_card(self, cl: QVBoxLayout):
        card = self._card(cl, "Racine du monorepo",
                          "Le dossier qui contient les dépôts "
                          "(LarcCommon, LarcSuperviseur…).")
        clc = card.content_layout()
        self._root_field = self._field_row(
            clc, "Chemin (laissez vide pour la racine automatique)",
            "ex. C:\\projets")
        btn = M3Button("Enregistrer la racine", theme=theme_manager.phi_theme,
                       variant=ButtonVariant.TONAL)
        btn.setIcon(md3_icon("save", color=theme_manager.palette.primary,
                             size=ds.icon_md))
        btn.clicked.connect(self._save_root)
        clc.addWidget(btn, alignment=Qt.AlignLeft)
        self._msg(clc, "root")

    # ── 2. Marque ─────────────────────────────────────────────────────

    def _build_branding_card(self, cl: QVBoxLayout):
        card = self._card(cl, "Marque (votre école)",
                          "Le nom affiché dans la fenêtre et le thème "
                          "de couleurs.")
        clc = card.content_layout()
        row = QHBoxLayout()
        row.setSpacing(ds.space_sm)
        self._school_field = M3TextField(theme=theme_manager.phi_theme)
        self._school_field.setStyleSheet(ds.flat_input_qss())
        row.addWidget(self._school_field, 3)
        self._theme_combo = M3ComboBox(
            items=[label for _, label, _, _ in THEMES_CONFIG],
            theme=theme_manager.phi_theme)
        self._theme_combo.setFixedHeight(ds.field_height + ds.space_xs)
        row.addWidget(self._theme_combo, 2)
        clc.addLayout(row)
        btn = M3Button("Enregistrer la marque", theme=theme_manager.phi_theme,
                       variant=ButtonVariant.TONAL)
        btn.setIcon(md3_icon("save", color=theme_manager.palette.primary,
                             size=ds.icon_md))
        btn.clicked.connect(self._save_branding)
        clc.addWidget(btn, alignment=Qt.AlignLeft)
        self._msg(clc, "branding")

    # ── 3. Connexions aux bases (une par école) ───────────────────────

    def _build_db_card(self, cl: QVBoxLayout):
        card = self._card(
            cl, "Connexions aux bases de données",
            "Chaque école peut avoir sa propre base PostgreSQL. Laissez "
            "les champs vides pour reprendre le config.ini (IntranetDatabase).")
        clc = card.content_layout()

        top = QHBoxLayout()
        top.setSpacing(ds.space_sm)
        self._db_combo = M3ComboBox(items=[], theme=theme_manager.phi_theme)
        self._db_combo.setFixedHeight(ds.field_height + ds.space_xs)
        self._db_combo.currentIndexChanged.connect(self._on_db_selected)
        top.addWidget(self._db_combo, 3)
        new = M3Button("Nouveau", theme=theme_manager.phi_theme,
                       variant=ButtonVariant.TEXT)
        new.setIcon(md3_icon("add", color=theme_manager.palette.primary,
                             size=ds.icon_md))
        new.clicked.connect(self._db_new)
        top.addWidget(new)
        self._db_delete = M3Button("Supprimer", theme=theme_manager.phi_theme,
                                   variant=ButtonVariant.TEXT)
        self._db_delete.setIcon(md3_icon("delete",
                                         color=theme_manager.palette.error,
                                         size=ds.icon_md))
        self._db_delete.clicked.connect(self._db_delete_sel)
        top.addWidget(self._db_delete)
        clc.addLayout(top)

        self._db_form: dict[str, M3TextField] = {}
        grid = QGridLayout()
        grid.setSpacing(ds.space_sm)
        fields = [("nom", "Nom du profil"), ("section", "Section config.ini"),
                  ("host", "Hôte"), ("port", "Port"), ("dbname", "Base"),
                  ("user", "Utilisateur")]
        for i, (key, label) in enumerate(fields):
            grid.addWidget(BodyLabel(label), i, 0)
            f = M3TextField(theme=theme_manager.phi_theme)
            f.setStyleSheet(ds.flat_input_qss())
            grid.addWidget(f, i, 1)
            self._db_form[key] = f
        grid.addWidget(BodyLabel("Mot de passe"), len(fields), 0)
        pwd = M3TextField(theme=theme_manager.phi_theme)
        pwd.setStyleSheet(ds.flat_input_qss())
        pwd.setEchoMode(QLineEdit.Password)  # enum seul — champ masqué
        grid.addWidget(pwd, len(fields), 1)
        self._db_form["password"] = pwd
        clc.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(ds.space_sm)
        save = M3Button("Sauvegarder le profil", theme=theme_manager.phi_theme,
                        variant=ButtonVariant.TONAL)
        save.setIcon(md3_icon("save", color=theme_manager.palette.primary,
                              size=ds.icon_md))
        save.clicked.connect(self._db_save)
        row.addWidget(save)
        self._db_test = M3Button("Tester la connexion",
                                 theme=theme_manager.phi_theme,
                                 variant=ButtonVariant.TONAL)
        self._db_test.setIcon(md3_icon("refresh",
                                       color=theme_manager.palette.primary,
                                       size=ds.icon_md))
        self._db_test.clicked.connect(self._db_test_conn)
        row.addWidget(self._db_test)
        self._db_activate = M3Button("Utiliser comme connexion active",
                                     theme=theme_manager.phi_theme,
                                     variant=ButtonVariant.FILLED)
        self._db_activate.setIcon(md3_icon(
            "check_circle", color=theme_manager.palette.on_primary,
            size=ds.icon_md))
        self._db_activate.clicked.connect(self._db_activate_sel)
        row.addWidget(self._db_activate)
        row.addStretch()
        clc.addLayout(row)
        self._msg(clc, "db")

    # ── 4. Profils de vérification (une école = ses contrôles) ────────

    def _build_run_card(self, cl: QVBoxLayout):
        card = self._card(
            cl, "Profils de vérification",
            "Un profil enregistre les contrôles d'une école : projets, "
            "linters, tests, fenêtre de temps. Le profil « actif » "
            "pré-remplit le panneau Vérifications.")
        clc = card.content_layout()

        top = QHBoxLayout()
        top.setSpacing(ds.space_sm)
        self._rp_combo = M3ComboBox(items=[], theme=theme_manager.phi_theme)
        self._rp_combo.setFixedHeight(ds.field_height + ds.space_xs)
        self._rp_combo.currentIndexChanged.connect(self._on_rp_selected)
        top.addWidget(self._rp_combo, 3)
        new = M3Button("Nouveau", theme=theme_manager.phi_theme,
                       variant=ButtonVariant.TEXT)
        new.setIcon(md3_icon("add", color=theme_manager.palette.primary,
                             size=ds.icon_md))
        new.clicked.connect(self._rp_new)
        top.addWidget(new)
        self._rp_delete = M3Button("Supprimer", theme=theme_manager.phi_theme,
                                   variant=ButtonVariant.TEXT)
        self._rp_delete.setIcon(md3_icon("delete",
                                         color=theme_manager.palette.error,
                                         size=ds.icon_md))
        self._rp_delete.clicked.connect(self._rp_delete_sel)
        top.addWidget(self._rp_delete)
        clc.addLayout(top)

        self._rp_name = self._field_row(clc, "Nom du profil",
                                        "ex. École Saint-Joseph")

        self._rp_checks: dict[str, dict[str, QCheckBox]] = {}
        for group, keys in (("projects", cfg.PROJETS),
                            ("linters", cfg.LINTER_KEYS),
                            ("tests", cfg.TEST_PROJECTS)):
            self._rp_checks[group] = self._checks_group(
                clc, f"{group} :", [str(k) for k in keys])

        self._rp_include = QCheckBox(
            "Inclure les tests d'intégration (lent — LarcCloudSync)")
        self._rp_include.setStyleSheet(ds.flat_input_qss())
        clc.addWidget(self._rp_include)

        row = QHBoxLayout()
        row.setSpacing(ds.space_sm)
        self._rp_since = M3ComboBox(items=[l for _, l in _SINCE],
                                    theme=theme_manager.phi_theme)
        self._rp_since.setFixedHeight(ds.field_height + ds.space_xs)
        row.addWidget(self._rp_since, 2)
        self._rp_level = M3ComboBox(items=[l for _, l in _LEVELS],
                                    theme=theme_manager.phi_theme)
        self._rp_level.setFixedHeight(ds.field_height + ds.space_xs)
        row.addWidget(self._rp_level, 2)
        row.addStretch()
        clc.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(ds.space_sm)
        save = M3Button("Sauvegarder le profil", theme=theme_manager.phi_theme,
                        variant=ButtonVariant.TONAL)
        save.setIcon(md3_icon("save", color=theme_manager.palette.primary,
                              size=ds.icon_md))
        save.clicked.connect(self._rp_save)
        row.addWidget(save)
        self._rp_activate = M3Button("Utiliser par défaut dans Vérifications",
                                     theme=theme_manager.phi_theme,
                                     variant=ButtonVariant.FILLED)
        self._rp_activate.setIcon(md3_icon(
            "check_circle", color=theme_manager.palette.on_primary,
            size=ds.icon_md))
        self._rp_activate.clicked.connect(self._rp_activate_sel)
        row.addWidget(self._rp_activate)
        row.addStretch()
        clc.addLayout(row)
        self._msg(clc, "run")

    # ── Chargement / synchronisation ──────────────────────────────────

    @safe_slot("ConfigPanel.reload")
    def reload(self):
        """Re-synchronise les formulaires depuis la configuration."""
        cfg_ui = self._ctx.config
        self._root_field.setText(cfg_ui.root_override or "")
        self._school_field.setText(cfg_ui.branding.school_name)
        try:
            idx = _THEME_KEYS.index(cfg_ui.branding.theme)
        except ValueError:
            idx = 0
        self._theme_combo.setCurrentIndex(idx)
        self._refresh_db_combo()
        self._refresh_rp_combo()
        for msg in self._msg_labels.values():
            msg.setText("")

    def _refresh_db_combo(self, keep: str | None = None):
        names = [p.name for p in self._ctx.config.db_profiles]
        self._db_combo.clear()
        self._db_combo.addItems(names)
        if names and keep is not None:
            try:
                self._db_combo.setCurrentIndex(names.index(keep))
            except ValueError:
                pass

    def _refresh_rp_combo(self, keep: str | None = None):
        names = [p.name for p in self._ctx.config.run_profiles]
        self._rp_combo.clear()
        self._rp_combo.addItems(names)
        if names and keep is not None:
            try:
                self._rp_combo.setCurrentIndex(names.index(keep))
            except ValueError:
                pass

    def _save(self, key: str, message: str):
        self._ctx.store.save(self._ctx.config)
        self._msg_labels[key].setText(message)

    # ── 1. Racine ─────────────────────────────────────────────────────

    @safe_slot("ConfigPanel.save_root")
    def _save_root(self):
        value = self._root_field.text().strip() or None
        self._ctx.config.root_override = value
        self._save("root", "✓ Racine enregistrée — elle sera utilisée "
                           "aux prochains lancements.")

    # ── 2. Marque ─────────────────────────────────────────────────────

    @safe_slot("ConfigPanel.save_branding")
    def _save_branding(self):
        cfg_ui = self._ctx.config
        cfg_ui.branding.school_name = self._school_field.text().strip() \
            or "Larc"
        theme_key = _THEME_KEYS[self._theme_combo.currentIndex()]
        cfg_ui.branding.theme = theme_key
        self._save("branding",
                   f"✓ Marque enregistrée : {cfg_ui.branding.school_name}, "
                   f"thème {theme_key}.")
        if theme_key != theme_manager.active_name:  # attribut str
            theme_manager.set_active(theme_key)  # → _restyle_all
        self.branding_changed.emit()

    # ── 3. Connexions DB ──────────────────────────────────────────────

    def _db_form_values(self) -> dict[str, str]:
        return {k: f.text().strip() for k, f in self._db_form.items()}

    @safe_slot("ConfigPanel.db_new")
    def _db_new(self):
        for f in self._db_form.values():
            f.setText("")
        self._db_form["nom"].setText("Nouvelle école")
        self._db_combo.setCurrentIndex(-1)

    @safe_slot("ConfigPanel.on_db_selected")
    def _on_db_selected(self, index: int):
        profiles = self._ctx.config.db_profiles
        if 0 <= index < len(profiles):
            p = profiles[index]
            for key, f in self._db_form.items():
                f.setText(getattr(p, key) or "")

    def _current_db(self):
        index = self._db_combo.currentIndex()
        profiles = self._ctx.config.db_profiles
        if 0 <= index < len(profiles):
            return profiles[index], index
        return None, index

    def _db_profile_from_form(self):
        from ..profiles import DbProfile

        values = self._db_form_values()
        return DbProfile(
            name=values["nom"] or "test",
            section=values["section"] or "IntranetDatabase",
            host=values["host"] or None,
            port=values["port"] or None,
            dbname=values["dbname"] or None,
            user=values["user"] or None,
            password=values["password"] or None,
        )

    @safe_slot("ConfigPanel.db_save")
    def _db_save(self):
        profile = self._db_profile_from_form()
        if not profile.name or profile.name == "test":
            self._msg_labels["db"].setText(
                "Donnez un nom au profil avant d'enregistrer.")
            return
        profiles = self._ctx.config.db_profiles
        index = self._db_combo.currentIndex()
        if 0 <= index < len(profiles) and profiles[index].name == profile.name:
            profiles[index] = profile
        else:
            for i, p in enumerate(profiles):
                if p.name == profile.name:
                    profiles[i] = profile
                    break
            else:
                profiles.append(profile)
        self._save("db", f"✓ Connexion « {profile.name} » enregistrée.")
        self._refresh_db_combo(keep=profile.name)

    @safe_slot("ConfigPanel.db_delete_sel")
    def _db_delete_sel(self):
        profiles = self._ctx.config.db_profiles
        index = self._db_combo.currentIndex()
        if not (0 <= index < len(profiles)):
            return
        name = profiles[index].name
        del profiles[index]
        if self._ctx.config.active_db_profile == name:
            self._ctx.config.active_db_profile = None
        self._save("db", f"Connexion « {name} » supprimée.")
        self._refresh_db_combo()
        self._db_new()

    @safe_slot("ConfigPanel.db_test_conn")
    def _db_test_conn(self):
        profile = self._db_profile_from_form()
        try:
            conn = self._ctx.open_db(profile)
        except pg.DBUnavailable as exc:
            self._msg_labels["db"].setText(f"Échec de connexion : {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self._msg_labels["db"].setText(f"Échec de connexion : {exc}")
            return
        conn.close()
        self._msg_labels["db"].setText(
            f"✓ Connexion réussie à {profile.host or 'config.ini'} "
            f"{profile.port or ''} / {profile.dbname or ''}")

    @safe_slot("ConfigPanel.db_activate_sel")
    def _db_activate_sel(self):
        profile, _ = self._current_db()
        if profile is None:
            return
        self._ctx.config.active_db_profile = profile.name
        self._save("db", f"✓ « {profile.name} » devient la connexion "
                         "active pour tout l'outil.")

    # ── 4. Profils de vérification ────────────────────────────────────

    @safe_slot("ConfigPanel.rp_new")
    def _rp_new(self):
        self._rp_name.setText("")
        for group in self._rp_checks.values():
            for c in group.values():
                c.setChecked(True)
        self._rp_include.setChecked(False)
        self._rp_since.setCurrentIndex(0)
        self._rp_level.setCurrentIndex(0)
        self._rp_combo.setCurrentIndex(-1)

    @safe_slot("ConfigPanel.on_rp_selected")
    def _on_rp_selected(self, index: int):
        profiles = self._ctx.config.run_profiles
        if not (0 <= index < len(profiles)):
            return
        p = profiles[index]
        self._rp_name.setText(p.name)
        for key in self._rp_checks["projects"]:
            self._rp_checks["projects"][key].setChecked(key in p.projects)
        for key in self._rp_checks["linters"]:
            self._rp_checks["linters"][key].setChecked(key in p.linters)
        for key in self._rp_checks["tests"]:
            self._rp_checks["tests"][key].setChecked(key in p.test_projects)
        self._rp_include.setChecked(p.include_integration)
        for i, (since_key, _) in enumerate(_SINCE):
            if int(since_key) == (p.since_h or 24):
                self._rp_since.setCurrentIndex(i)
                break
        for i, (level_key, _) in enumerate(_LEVELS):
            if level_key == (p.level or "ERROR,WARNING"):
                self._rp_level.setCurrentIndex(i)
                break

    def _rp_profile_from_form(self):
        from ..profiles import RunProfile

        return RunProfile(
            name=self._rp_name.text().strip(),
            projects=[k for k, c in self._rp_checks["projects"].items()
                      if c.isChecked()],
            linters=[k for k, c in self._rp_checks["linters"].items()
                     if c.isChecked()],
            test_projects=[k for k, c in self._rp_checks["tests"].items()
                           if c.isChecked()],
            include_integration=self._rp_include.isChecked(),
            since_h=int(_SINCE[self._rp_since.currentIndex()][0]),
            level=_LEVELS[self._rp_level.currentIndex()][0],
        )

    @safe_slot("ConfigPanel.rp_save")
    def _rp_save(self):
        profile = self._rp_profile_from_form()
        if not profile.name:
            self._msg_labels["run"].setText(
                "Donnez un nom au profil avant d'enregistrer.")
            return
        profiles = self._ctx.config.run_profiles
        for i, p in enumerate(profiles):
            if p.name == profile.name:
                profiles[i] = profile
                break
        else:
            profiles.append(profile)
        self._save("run", f"✓ Profil de vérification « {profile.name} » "
                          "enregistré.")
        self._refresh_rp_combo(keep=profile.name)

    @safe_slot("ConfigPanel.rp_delete_sel")
    def _rp_delete_sel(self):
        profiles = self._ctx.config.run_profiles
        index = self._rp_combo.currentIndex()
        if not (0 <= index < len(profiles)):
            return
        name = profiles[index].name
        del profiles[index]
        if self._ctx.config.active_run_profile == name:
            self._ctx.config.active_run_profile = None
        self._save("run", f"Profil « {name} » supprimé.")
        self._refresh_rp_combo()
        self._rp_new()

    @safe_slot("ConfigPanel.rp_activate_sel")
    def _rp_activate_sel(self):
        index = self._rp_combo.currentIndex()
        profiles = self._ctx.config.run_profiles
        if not (0 <= index < len(profiles)):
            return
        name = profiles[index].name
        self._ctx.config.active_run_profile = name
        self._save("run", f"✓ « {name} » pré-remplira désormais le panneau "
                          "Vérifications.")

    # ── Réactivité thème ──────────────────────────────────────────────

    def _restyle(self):
        p = theme_manager.palette
        self._title.restyle()
        for lbl in self._labels:
            restyle_label(lbl, "title_medium", p.text_strong)
        for msg in self._msg_labels.values():
            msg.restyle()
        for card in self._cards:
            restyle_card(card)
        fields = [self._root_field, self._school_field, self._rp_name]
        fields.extend(self._db_form.values())
        for field in fields:
            field.setStyleSheet(ds.flat_input_qss())

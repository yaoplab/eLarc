# Fix réactivité thème incomplète (LarcSuperviseur) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger la cause racine #3 de l'audit design LarcSuperviseur (docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md) : plusieurs écrans ne se remettent pas à jour visuellement après un changement de thème (`ds.theme_changed` non connecté, ou connecté mais incomplet), et un bug runtime critique dans `main_window.py` casse le repaint du dashboard à chaque clic sur le sélecteur de thème de la top bar.

**Architecture:** Chaque widget/dialogue palette-dépendant expose une méthode `_restyle_all()` (ou utilise l'existant) connectée à `ds.theme_changed` dans son `__init__`, qui régénère tous les `setStyleSheet()` locaux avec `p = theme_manager.palette` frais. Pour les widgets stylés via objectName + une propriété `_STYLE` (pattern déjà en place dans `student_detail.py`), on préfère ajouter les nouveaux éléments à `_STYLE` plutôt que dupliquer un mécanisme de restyle imperatif séparé.

**Tech Stack:** Python 3.x, PySide6/Qt6, pytest + pytest-qt (`qtbot`), fixtures `mock_db`/`mock_session`/`mock_theme` (LarcSuperviseur/tests/conftest.py).

**Spec:** docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md (section "Cause racine #3")

## Global Constraints

- Ne changer que la réactivité thème (connexion `theme_changed` + régénération des styles) — aucun changement de layout, de logique métier, ou de comportement fonctionnel.
- Chaque widget dont une variable locale (`save_btn`, etc.) doit être restylée devient un attribut d'instance (`self._save_btn`) — c'est le seul changement structurel autorisé au-delà de l'ajout de `_restyle_all`/`theme_changed`.
- Test de régression standard par tâche : construire le widget, appeler `ds.theme_changed.emit()` (ou changer `theme_manager.set_active(...)` si mocké), puis vérifier que les éléments concernés reflètent la nouvelle palette (ex: `widget.styleSheet()` contient la nouvelle couleur, ou qu'aucune exception n'est levée — `refresh_all`/`_on_theme_selected` en particulier doit être testé pour l'absence de `NameError`).
- Lancer chaque suite de test isolément avec `D:\projets\.venv\Scripts\python.exe -m pytest tests/<fichier> -v -m "not integration"` depuis `D:\projets\LarcSuperviseur`.
- Baseline connue (ignorer, hors périmètre) : `tests/test_event_dialog.py::test_load_event_populates`, `::test_save_updates_and_accepts` (ValueError pré-existant), et 3 échecs dans `tests/test_event_generator.py` (ModuleNotFoundError, wizard que l'utilisateur corrige lui-même).

---

### Task 1: main_window.py — corrige le bug NameError de `_on_theme_selected` + unifie avec `_restyle`

**Files:**
- Modify: `LarcSuperviseur/views/main_window.py:738-767`, `:855` (`refresh_all`)
- Test: `LarcSuperviseur/tests/test_main_window.py`

**Interfaces:**
- Consomme : `theme_manager`, `session`, `ds.p` (déjà importés dans le fichier).
- Produit : `_restyle_all(self)` — nouvelle méthode unique remplaçant `_restyle` et le corps stylistique de `_on_theme_selected`.

- [ ] **Step 1: Write the failing test**

Ajouter à `LarcSuperviseur/tests/test_main_window.py` :

```python
def test_theme_selected_no_crash_and_repaints(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)

    w._on_theme_selected("dark")  # doit NE PAS lever NameError et doit appeler refresh_all

    assert w._cards_widget.styleSheet() != ""
    assert w._group_scroll.viewport().styleSheet() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_window.py::test_theme_selected_no_crash_and_repaints -v -m "not integration"`
Expected: le test peut "passer" faussement car `@safe_slot` avale le `NameError` silencieusement — pour observer le vrai échec, vérifier plutôt que `w._cards_widget.styleSheet()` reste vide (le style n'a jamais été appliqué à cause du crash avant d'atteindre ces lignes). Si l'assertion échoue avec un styleSheet vide, c'est la preuve du bug.

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/main_window.py`, remplacer les deux méthodes `_restyle` (L738-745) et `_on_theme_selected` (L747-767) par :

```python
    @safe_slot("MainWindow._restyle_all")
    def _restyle_all(self):
        """Réapplique le style courant à tous les fonds réels (PAS transparents —
        palette noire sinon) après un changement de thème, interne ou externe
        (PreferencesDialog, sélecteur top bar)."""
        p = theme_manager.palette
        self.setStyleSheet(self._STYLE)
        self._top_bar.restyle()
        self._rebuild_student_detail_theme()
        self._top_bar.update_network()
        if hasattr(self, "_cards_scroll"):
            self._cards_scroll.viewport().setStyleSheet(f"background: {p.surface};")
        if hasattr(self, "_cards_widget"):
            self._cards_widget.setStyleSheet(f"background: {p.surface};")
        if hasattr(self, "_group_scroll"):
            self._group_scroll.viewport().setStyleSheet(f"background: {p.background};")
        if self._current_group_mode:
            self.refresh_all()

    @safe_slot("MainWindow.on_theme_selected")
    def _on_theme_selected(self, key: str):
        theme_manager.set_active(key)
        session.theme_pref = key
        self._restyle_all()
```

Ligne 855 (`def refresh_all(self):`), ajouter le décorateur juste au-dessus :

```python
    @safe_slot("MainWindow.refresh_all")
    def refresh_all(self):
```

Chercher tout autre appelant de `self._restyle(` dans le fichier (`grep -n "_restyle(" LarcSuperviseur/views/main_window.py`) et le remplacer par `self._restyle_all(`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_window.py::test_theme_selected_no_crash_and_repaints -v -m "not integration"`
Expected: PASS — `_cards_widget`/`_group_scroll` ont bien un styleSheet non vide après l'appel.

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_main_window.py -v -m "not integration"`
Expected: tous les tests passent (y compris les tests existants `test_theme_change_no_crash` qui appelle `w._restyle()` — le renommer en `w._restyle_all()` dans ce test existant aussi).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/main_window.py LarcSuperviseur/tests/test_main_window.py
git commit -m "fix(larcsuperviseur): NameError dans _on_theme_selected, unifie avec _restyle_all"
```

---

### Task 2: top_bar.py — connecte theme_changed, recolore les menus au restyle

**Files:**
- Modify: `LarcSuperviseur/views/top_bar.py:87`, `:109-140` (stocker les actions), `:24-36` (`__init__`), `:329-352` (`restyle`)
- Test: `LarcSuperviseur/tests/test_top_bar.py`

**Interfaces:**
- Consomme : `ds` (déjà importé), `theme_manager`, `md3_icon`.
- Produit : `self._prefs_action`, `self._pwd_action`, `self._logout_action`, `self._theme_menu_actions` (list) — nouveaux attributs d'instance consommés uniquement par `restyle()`.

- [ ] **Step 1: Write the failing test**

Ajouter à `LarcSuperviseur/tests/test_top_bar.py` :

```python
def test_restyle_recolors_menu_icons(qtbot, mock_theme):
    from LarcSuperviseur.views.top_bar import TopBar

    bar = TopBar(lambda k: None, lambda k: None, lambda: None)
    qtbot.addWidget(bar)

    old_icon = bar._prefs_action.icon()
    bar.restyle()
    new_icon = bar._prefs_action.icon()

    assert isinstance(old_icon, type(new_icon))  # smoke : setIcon() a bien été rappelé, pas d'exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_top_bar.py::test_restyle_recolors_menu_icons -v -m "not integration"`
Expected: FAIL — `AttributeError: 'TopBar' object has no attribute '_prefs_action'` (l'action n'est pas encore stockée comme attribut).

- [ ] **Step 3: Write minimal implementation**

Ligne 87, ajouter `theme=` :

```python
        self._theme_menu = M3Menu(theme=theme_manager.phi_theme)
```

Lignes 94-104, stocker chaque action de thème dans une liste :

```python
        self._theme_menu_actions = []
        for key, label in theme_manager.names():
            icon_name = _theme_icon_names.get(key, "light_mode")
            pal = theme_manager.get_palette(key)
            ic = md3_icon(
                icon_name,
                color=pal.primary if pal else "#1565C0",
                size=ds.icon_sm,
            )
            a = self._theme_menu.addAction(ic, label)
            a.setData(key)
            self._theme_menu_actions.append((a, icon_name))
        self._theme_menu.triggered.connect(self._on_theme_triggered)
```

Ligne 122, ajouter `theme=` et corriger l'ordre des arguments :

```python
        self._profile_menu = M3Menu(theme=theme_manager.phi_theme, parent=self)
```

Lignes 123-138, stocker les actions comme attributs :

```python
        self._prefs_action = self._profile_menu.addAction(
            md3_icon("settings", color=p.text_strong, size=ds.icon_sm),
            _("topbar.preferences"),
        )
        self._prefs_action.triggered.connect(self._on_preferences)
        self._pwd_action = self._profile_menu.addAction(
            md3_icon("lock", color=p.text_strong, size=ds.icon_sm),
            _("topbar.change_password"),
        )
        self._pwd_action.triggered.connect(self._on_change_password)
        self._profile_menu.addSeparator()
        self._logout_action = self._profile_menu.addAction(
            md3_icon("logout", color=p.text_strong, size=ds.icon_sm),
            _("topbar.logout"),
        )
        self._logout_action.triggered.connect(self._on_logout)
```

Dans `__init__` (après `self._start_clock()`), ajouter :

```python
        ds.theme_changed.connect(self.restyle)
```

(nécessite `from larccommon.design_system import ds` — déjà présent en tête de fichier, ligne 1).

Dans `restyle()` (après `self._update_network_label()`), ajouter :

```python
        for action, icon_name in self._theme_menu_actions:
            action.setIcon(md3_icon(icon_name, color=p.primary, size=ds.icon_sm))
        self._prefs_action.setIcon(md3_icon("settings", color=p.text_strong, size=ds.icon_sm))
        self._pwd_action.setIcon(md3_icon("lock", color=p.text_strong, size=ds.icon_sm))
        self._logout_action.setIcon(md3_icon("logout", color=p.text_strong, size=ds.icon_sm))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_top_bar.py::test_restyle_recolors_menu_icons -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_top_bar.py -v -m "not integration"`
Expected: tous les tests passent (existants + nouveau).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/top_bar.py LarcSuperviseur/tests/test_top_bar.py
git commit -m "fix(larcsuperviseur): TopBar reagit a theme_changed, recolore ses menus, theme= sur ses M3Menu"
```

---

### Task 3: timetable_editor.py — ajoute `_restyle_all` + `theme_changed`

**Files:**
- Modify: `LarcSuperviseur/views/dialogs/timetable_editor.py:31-65`
- Test: `LarcSuperviseur/tests/test_timetable_editor.py`

**Interfaces:**
- Produit : `self._save_btn` (attribut, remplace la variable locale `save_btn`), `_restyle_all(self)`.

- [ ] **Step 1: Write the failing test**

Ajouter à `LarcSuperviseur/tests/test_timetable_editor.py` :

```python
def test_restyle_all_no_crash(qtbot, mock_db, mock_session, mock_theme):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchall.side_effect = [[], [], []]

    editor = _make_editor(qtbot, mock_db)

    editor._restyle_all()  # ne doit pas lever d'exception

    assert editor._save_btn.styleSheet() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_timetable_editor.py::test_restyle_all_no_crash -v -m "not integration"`
Expected: FAIL — `AttributeError: 'TimetableEditor' object has no attribute '_restyle_all'`.

- [ ] **Step 3: Write minimal implementation**

Ligne 38-39, renommer en attribut d'instance :

```python
        p = theme_manager.palette
        self.setStyleSheet(f"TimetableEditor {{ background-color: {p.surface}; border-radius: {ds.radius_lg}px; }}")
        ds.theme_changed.connect(self._restyle_all)
```

Ligne 57 (`save_btn = M3Button(...)`) jusqu'à ligne 65 (`save_btn.clicked.connect(self._save)`), remplacer toutes les occurrences de `save_btn` par `self._save_btn` :

```python
        self._save_btn = M3Button(_("timetable.save_button"), theme=theme_manager.phi_theme)
        self._save_btn.setMinimumHeight(ds.space_lg + ds.space_xxs)  # 36px
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; font-weight: bold; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_md}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        self._save_btn.clicked.connect(self._save)
```

(mettre à jour aussi les lignes suivantes qui référencent `save_btn` dans le layout, ex. `btn_row.addWidget(save_btn)` → `btn_row.addWidget(self._save_btn)`).

Ajouter une nouvelle méthode juste après `__init__` :

```python
    @safe_slot("TimetableEditor._restyle_all")
    def _restyle_all(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(f"TimetableEditor {{ background-color: {p.surface}; border-radius: {ds.radius_lg}px; }}")
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; font-weight: bold; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_md}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_timetable_editor.py::test_restyle_all_no_crash -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_timetable_editor.py -v -m "not integration"`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/dialogs/timetable_editor.py LarcSuperviseur/tests/test_timetable_editor.py
git commit -m "fix(larcsuperviseur): TimetableEditor reagit a theme_changed"
```

---

### Task 4: event_dialog.py (EventEditDialog) — ajoute `_restyle_all` + `theme_changed`

**Files:**
- Modify: `LarcSuperviseur/views/core/event_dialog.py:21-75`
- Test: `LarcSuperviseur/tests/test_event_dialog.py`

**Interfaces:**
- Produit : `self._save_btn` (attribut, remplace la variable locale `save_btn`), `_restyle_all(self)`.
- Consomme : `ds` (déjà importé ligne 1).

- [ ] **Step 1: Write the failing test**

Ajouter à `LarcSuperviseur/tests/test_event_dialog.py` :

```python
def test_restyle_all_no_crash(qtbot, mock_db, mock_session, mock_theme):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours", None, datetime(2026, 7, 8, 8, 30),
        "Salle de cours", "Maths", "", "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",)]

    dlg = _make_dlg(qtbot, mock_db)

    dlg._restyle_all()  # ne doit pas lever d'exception

    assert dlg._save_btn.styleSheet() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_dialog.py::test_restyle_all_no_crash -v -m "not integration"`
Expected: FAIL — `AttributeError: 'EventEditDialog' object has no attribute '_restyle_all'`.

- [ ] **Step 3: Write minimal implementation**

Lignes 21-31 (`__init__`), ajouter la connexion après `self.setStyleSheet(...)` :

```python
        p = theme_manager.palette
        self.setStyleSheet(f"EventEditDialog {{ background-color: {p.surface}; border-radius: {ds.radius_lg}px; }}")
        ds.theme_changed.connect(self._restyle_all)
        self._setup_ui()
        self._load_event()
```

Ligne 63 (`save_btn = M3Button(...)`) jusqu'à ligne 69 (`save_btn.clicked.connect(self._save)`), remplacer par `self._save_btn` :

```python
        self._save_btn = M3Button(_("event_dialog.save_button"), theme=theme_manager.phi_theme)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}"
        )
        self._save_btn.clicked.connect(self._save)
```

(mettre à jour `btn_row.addWidget(save_btn)` → `btn_row.addWidget(self._save_btn)`).

Ajouter une nouvelle méthode juste après `_setup_ui` (ou en fin de classe) :

```python
    @safe_slot("EventEditDialog._restyle_all")
    def _restyle_all(self):
        p = theme_manager.palette
        self.setStyleSheet(f"EventEditDialog {{ background-color: {p.surface}; border-radius: {ds.radius_lg}px; }}")
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_dialog.py::test_restyle_all_no_crash -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_event_dialog.py -v -m "not integration"`
Expected: tous les tests passent (sauf les 2 échecs pré-existants documentés, hors périmètre).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/core/event_dialog.py LarcSuperviseur/tests/test_event_dialog.py
git commit -m "fix(larcsuperviseur): EventEditDialog reagit a theme_changed"
```

---

### Task 5: event_types_panel.py (EventTypeEditDialog) — ajoute `_restyle_all` + `theme_changed`

**Files:**
- Modify: `LarcSuperviseur/views/panels/event_types_panel.py:32-97`
- Test: `LarcSuperviseur/tests/test_event_types_panel.py`

**Interfaces:**
- Produit : `_restyle_all(self)` sur `EventTypeEditDialog` (distinct de `EventTypesPanel._restyle`, qui existe déjà et reste inchangé).

- [ ] **Step 1: Write the failing test**

Ajouter à `LarcSuperviseur/tests/test_event_types_panel.py` :

```python
def test_edit_dialog_restyle_all_no_crash(qtbot, mock_db, mock_session, mock_theme):
    from LarcSuperviseur.views.panels.event_types_panel import EventTypeEditDialog
    from LarcSuperviseur.views.core.event_type_repo import EventTypeRepo

    dlg = EventTypeEditDialog(EventTypeRepo(), mode="create", roots=[])
    qtbot.addWidget(dlg)

    dlg._restyle_all()  # ne doit pas lever d'exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_types_panel.py::test_edit_dialog_restyle_all_no_crash -v -m "not integration"`
Expected: FAIL — `AttributeError: 'EventTypeEditDialog' object has no attribute '_restyle_all'`.

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/panels/event_types_panel.py`, ligne 47 (`p = theme_manager.palette`) jusqu'à ligne 97 (`self.setStyleSheet(...)`), après la ligne 97, ajouter :

```python
        ds.theme_changed.connect(self._restyle_all)
```

Ajouter une nouvelle méthode juste après `__init__` :

```python
    @safe_slot("EventTypeEditDialog._restyle_all")
    def _restyle_all(self):
        p = theme_manager.palette
        self.setStyleSheet(f"EventTypeEditDialog {{ background: {p.surface}; }}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_types_panel.py::test_edit_dialog_restyle_all_no_crash -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_event_types_panel.py -v -m "not integration"`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/panels/event_types_panel.py LarcSuperviseur/tests/test_event_types_panel.py
git commit -m "fix(larcsuperviseur): EventTypeEditDialog reagit a theme_changed"
```

---

### Task 6: student_detail.py — intègre les 3 labels d'identité à `_restyle_all`

**Files:**
- Modify: `LarcSuperviseur/views/panels/student_detail.py:65-105` (`_STYLE`), `:152-165` (construction des labels)
- Test: `LarcSuperviseur/tests/test_student_detail.py`

**Interfaces:**
- Consomme : `_STYLE` (propriété existante), `_restyle_all` (méthode existante, déjà connectée à `ds.theme_changed` en L58).

- [ ] **Step 1: Write the failing test**

Ajouter à `LarcSuperviseur/tests/test_student_detail.py` :

```python
def test_restyle_all_updates_identity_labels(qtbot, mock_db, mock_session, mock_theme):
    from LarcSuperviseur.views.panels.student_detail import StudentDetail
    from LarcSuperviseur.common.theme import theme_manager

    detail = StudentDetail()
    qtbot.addWidget(detail)

    old_style = detail._sd_name_lbl.styleSheet()
    theme_manager.palette.text_strong = "#123456"  # simule un nouveau thème
    detail._restyle_all()

    assert "#123456" in detail._sd_name_lbl.styleSheet()
    assert detail._sd_name_lbl.styleSheet() != old_style
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_student_detail.py::test_restyle_all_updates_identity_labels -v -m "not integration"`
Expected: FAIL — `_sd_name_lbl.styleSheet()` reste inchangé (couleur de l'ancien thème), `_restyle_all()` ne touche pas ce label.

- [ ] **Step 3: Write minimal implementation**

Dans la propriété `_STYLE` (retour du f-string, après le bloc `QLabel#sd_period_val`), ajouter :

```python
            QLabel#sd_name_lbl {{
                font-size: {s(18)}px; font-weight: bold; color: {p.text_strong}; border: none;
            }}
            QLabel#sd_class_lbl {{
                font-size: {s(ds.font_label_lg)}px; color: {p.text_strong}; border: none;
            }}
            QLabel#sd_id_lbl {{
                font-size: {s(ds.font_label_sm)}px; color: {p.text_strong}; border: none;
            }}
```

Aux lignes de construction (152-165), remplacer les 3 `.setStyleSheet(...)` par `.setObjectName(...)` :

```python
        self._sd_name_lbl = QLabel("—")
        self._sd_name_lbl.setObjectName("sd_name_lbl")
        identity.addWidget(self._sd_name_lbl)  # Q22c

        self._sd_class_lbl = QLabel("—")
        self._sd_class_lbl.setObjectName("sd_class_lbl")
        identity.addWidget(self._sd_class_lbl)  # Q22d

        self._sd_id_lbl = QLabel("—")
        self._sd_id_lbl.setObjectName("sd_id_lbl")
        identity.addWidget(self._sd_id_lbl)  # Q22e
```

(Le `self.setStyleSheet(self._STYLE)` déjà appelé dans `__init__` (L60) et dans `_restyle_all` (L110) applique maintenant ces 3 règles par cascade objectName — aucun autre changement nécessaire.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_student_detail.py::test_restyle_all_updates_identity_labels -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_student_detail.py -v -m "not integration"`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/panels/student_detail.py LarcSuperviseur/tests/test_student_detail.py
git commit -m "fix(larcsuperviseur): student_detail integre nom/classe/ID a la reactivite theme"
```

---

## Hors périmètre (volontairement non traité par ce plan)

- `dialogs/preferences.py` : toujours du code mort (cause racine #2), exclu.
- Recoloration fine du texte HTML de `EventEditDialog._info` (couleurs inline dans le HTML généré par `_load_event`, dépend de données chargées) : gap mineur documenté, déféré — la structure du dialogue (fond, bouton) est corrigée, le contenu HTML recharge de toute façon à la prochaine ouverture/rafraîchissement.
- Causes racines #2, #4, #5 : traitées dans des plans séparés après celui-ci.

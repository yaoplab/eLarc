# Fix widgets phibuilder sans theme= (LarcSuperviseur) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger la cause racine #1 de l'audit design LarcSuperviseur (docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md) : des widgets `phibuilder.widgets` (M3Label, M3TextEdit, M3Button, M3ComboBox, M3Menu, M3TableWidget) instanciés sans `theme=`, qui restent silencieusement non stylés (`_update_style()` émet un `warnings.warn` puis `return`).

**Architecture:** Chaque site d'instanciation reçoit `theme=theme_manager.phi_theme` (déjà importé dans tous les fichiers concernés). Deux boutons "Annuler" gagnent `variant=ButtonVariant.OUTLINED` pour se distinguer visuellement du bouton d'action principal (déjà `FILLED` par défaut). `TimetableEditor` (sous-classe `M3Dialog`) NE reçoit PAS `theme=` dans `super().__init__()` — `M3Dialog` construit sa propre UI complète (titre/message/boutons Cancel-Confirm en anglais) quand `theme` est fourni, ce qui entrerait en conflit avec le layout custom de `_init_ui()`. À la place, on applique le fond/rayon directement via `setStyleSheet`, comme le fait déjà `EventTypeEditDialog` (event_types_panel.py:97) pour la même raison.

**Tech Stack:** Python 3.x, PySide6/Qt6, pytest + pytest-qt (`qtbot`), fixtures `mock_db`/`mock_session`/`mock_theme` (LarcSuperviseur/tests/conftest.py).

**Spec:** docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md (section "Cause racine #1")

## Global Constraints

- Ne jamais passer `theme=` à `M3Dialog.__init__()` pour `TimetableEditor`/`EventEditDialog` — ces sous-classes construisent leur propre layout et entreraient en conflit avec l'UI auto-générée de `M3Dialog` (titre + message + boutons Cancel/Confirm).
- Chaque fix ne touche QUE l'ajout de `theme=theme_manager.phi_theme` (+ `variant=` pour les boutons Annuler) — aucun autre changement de comportement, layout ou logique.
- Test de régression standard par tâche : `recwarn` (fixture pytest intégrée, pas d'import requis) doit ne contenir aucun warning dont le message contient `"cree sans theme="` après construction de l'écran/dialogue.
- Lancer chaque suite de test isolément avec `pytest tests/<fichier> -v -m "not integration"` depuis `D:\projets\LarcSuperviseur`.

---

### Task 1: main_events.py — EventsMixin._edit_event + _show_event_context_menu

**Files:**
- Modify: `LarcSuperviseur/views/main_events.py:9-20` (imports), `:161`, `:180-181`, `:203`, `:230`, `:266`
- Test: `LarcSuperviseur/tests/test_main_window.py`

**Interfaces:**
- Consumes : fixtures `qtbot`, `mock_db`, `mock_session`, `mock_theme` (conftest.py) ; helper `_make_window(qtbot, mock_db, mock_session)` déjà défini dans test_main_window.py.
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `LarcSuperviseur/tests/test_main_window.py` :

```python
def test_edit_event_dialog_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn, monkeypatch):
    from datetime import datetime
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)

    w = _make_window(qtbot, mock_db, mock_session)
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours", None, datetime(2026, 7, 8, 8, 30),
        "Salle de cours", "Maths", "", "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",), ("Sortie",)]
    recwarn.clear()

    w._edit_event(42)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_window.py::test_edit_event_dialog_no_theme_warning -v -m "not integration"` (depuis `D:\projets\LarcSuperviseur`)
Expected: FAIL — `theme_warnings` contient au moins les 5 warnings actuels (M3Label ×2, M3TextEdit, M3Button cancel_btn, M3Menu — ce dernier n'est PAS déclenché par `_edit_event` mais par `_show_event_context_menu`, donc ici on attend au moins 4 warnings : L161, L180, L181, L230).

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/main_events.py`, ajouter l'import de `ButtonVariant` (ligne 9, dans le bloc `from phibuilder.widgets import (...)`, ajouter une ligne après le bloc) :

```python
from phibuilder.widgets.button import ButtonVariant
```

Ligne 161-166, ajouter `theme=theme_manager.phi_theme` à `M3Label` :

```python
        info = M3Label(
            f"<b>{student_name}</b> — {etype}<br>"
            f"<span style='color:{p.text_disabled};font-size:{theme_manager.font_size(10)}px;'>"
            f"{e_at.strftime('%d/%m/%Y %H:%M') if e_at else ''} | {lieu or ''}"
            f"{' | ' + subject if subject else ''}</span>",
            theme=theme_manager.phi_theme,
        )
```

Ligne 180-181 :

```python
        note_label = M3Label(_("event.edit_note"), theme=theme_manager.phi_theme)
        note_input = M3TextEdit(theme=theme_manager.phi_theme)
```

Ligne 203 :

```python
        save_btn = M3Button(_("event.save"), theme=theme_manager.phi_theme)
```

Ligne 230 :

```python
        cancel_btn = M3Button(_("event.cancel"), theme=theme_manager.phi_theme, variant=ButtonVariant.OUTLINED)
```

Ligne 266 :

```python
        menu = M3Menu(theme=theme_manager.phi_theme, parent=self)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_window.py::test_edit_event_dialog_no_theme_warning -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_main_window.py -v -m "not integration"`
Expected: tous les tests passent (y compris les 4 tests existants).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/main_events.py LarcSuperviseur/tests/test_main_window.py
git commit -m "fix(larcsuperviseur): theme= manquant sur les widgets M3 de main_events.py"
```

---

### Task 2: event_dialog.py — EventEditDialog

**Files:**
- Modify: `LarcSuperviseur/views/core/event_dialog.py:1-16` (imports), `:35`, `:47-48`, `:60`, `:67`
- Test: `LarcSuperviseur/tests/test_event_dialog.py`

**Interfaces:**
- Consumes : helper `_make_dlg(qtbot, mock_db)` déjà défini dans le fichier de test.
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `LarcSuperviseur/tests/test_event_dialog.py` :

```python
def test_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours",
        None,
        datetime(2026, 7, 8, 8, 30),
        "Salle de cours",
        "Maths",
        "",
        "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",), ("Sortie",)]
    recwarn.clear()

    _make_dlg(qtbot, mock_db)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_dialog.py::test_no_theme_warning -v -m "not integration"`
Expected: FAIL — au moins 5 warnings (`_info`, `_note_label`, `_note_input`, `save_btn`, `cancel_btn`).

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/core/event_dialog.py`, ligne 5, ajouter l'import :

```python
from phibuilder.widgets.button import ButtonVariant
```

Ligne 35 :

```python
        self._info = M3Label(theme=theme_manager.phi_theme)
```

Ligne 47-48 :

```python
        self._note_label = M3Label(_("event_dialog.note"), theme=theme_manager.phi_theme)
        self._note_input = M3TextEdit(theme=theme_manager.phi_theme)
```

Ligne 60 :

```python
        save_btn = M3Button(_("event_dialog.save_button"), theme=theme_manager.phi_theme)
```

Ligne 67 :

```python
        cancel_btn = M3Button(_("event_dialog.cancel_button"), theme=theme_manager.phi_theme, variant=ButtonVariant.OUTLINED)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_dialog.py::test_no_theme_warning -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_event_dialog.py -v -m "not integration"`
Expected: tous les tests passent (y compris les 4 tests existants — si `test_load_event_populates` échoue déjà pour une autre raison, documenter mais ne pas corriger ici, hors périmètre de cette tâche).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/core/event_dialog.py LarcSuperviseur/tests/test_event_dialog.py
git commit -m "fix(larcsuperviseur): theme= manquant sur les widgets M3 de EventEditDialog"
```

---

### Task 3: event_types_panel.py — EventTypeEditDialog + EventTypesPanel

**Files:**
- Modify: `LarcSuperviseur/views/panels/event_types_panel.py:57`, `:58`, `:65`, `:66`, `:74-75`, `:82-83`, `:145`, `:149-154`, `:162`
- Create: `LarcSuperviseur/tests/test_event_types_panel.py`

**Interfaces:**
- Consumes : fixtures `qtbot`, `mock_db`, `mock_session`, `mock_theme`.
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Write the failing test**

Créer `LarcSuperviseur/tests/test_event_types_panel.py` :

```python
"""Tests UI (qtbot) d'EventTypesPanel — écran d'administration des types d'événements."""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QDialog

from LarcSuperviseur.views.panels.event_types_panel import EventTypesPanel


def test_construct_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    panel = EventTypesPanel()
    qtbot.addWidget(panel)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]


def test_add_root_dialog_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn, monkeypatch):
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)

    panel = EventTypesPanel()
    qtbot.addWidget(panel)
    recwarn.clear()

    panel._on_add_root()

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_types_panel.py -v -m "not integration"`
Expected: FAIL sur les deux tests (M3Label ×5, M3ComboBox ×2, M3Button ×6, M3TextField ×2, M3TableWidget ×1 — tous non stylés).

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/panels/event_types_panel.py` :

Ligne 57-58 :

```python
        cl.addWidget(M3Label(_("event_types.label_label"), theme=theme_manager.phi_theme, style="label_small"))
        self._label = M3TextField(placeholder=_("event_types.label_label"), theme=theme_manager.phi_theme)
```

Ligne 65-66 :

```python
        cl.addWidget(M3Label(_("event_types.code_label"), theme=theme_manager.phi_theme, style="label_small"))
        self._code = M3TextField(placeholder=_("event_types.code_auto"), theme=theme_manager.phi_theme)
```

Ligne 74-75 :

```python
            cl.addWidget(M3Label(_("event_types.parent_label"), theme=theme_manager.phi_theme, style="label_small"))
            self._parent = M3ComboBox(theme=theme_manager.phi_theme)
```

Ligne 82-83 :

```python
            cl.addWidget(M3Label(_("event_types.absence_scope_label"), theme=theme_manager.phi_theme, style="label_small"))
            self._scope = M3ComboBox(theme=theme_manager.phi_theme)
```

Ligne 145 :

```python
        outer.addWidget(M3Label(_("event_types.title"), theme=theme_manager.phi_theme, style="title_medium"))
```

Ligne 149-154 :

```python
        self._btn_add_root = M3Button(_("event_types.add_root"), theme=theme_manager.phi_theme, variant=ButtonVariant.FILLED)
        self._btn_add_child = M3Button(_("event_types.add_child"), theme=theme_manager.phi_theme, variant=ButtonVariant.TONAL)
        self._btn_rename = M3Button(_("event_types.rename"), theme=theme_manager.phi_theme, variant=ButtonVariant.TONAL)
        self._btn_disable = M3Button(_("event_types.disable"), theme=theme_manager.phi_theme, variant=ButtonVariant.TONAL)
        self._btn_up = M3Button(_("event_types.reorder_up"), theme=theme_manager.phi_theme, variant=ButtonVariant.TEXT)
        self._btn_down = M3Button(_("event_types.reorder_down"), theme=theme_manager.phi_theme, variant=ButtonVariant.TEXT)
```

Ligne 162 :

```python
        self._table = M3TableWidget(0, 4, theme=theme_manager.phi_theme)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_types_panel.py -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the timetable/event suites to check no regression**

Run: `pytest tests/test_event_types_panel.py tests/test_event_dialog.py -v -m "not integration"`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/panels/event_types_panel.py LarcSuperviseur/tests/test_event_types_panel.py
git commit -m "fix(larcsuperviseur): theme= manquant sur les widgets M3 de EventTypesPanel"
```

---

### Task 4: event_actions.py — EventActions.get_context_menu

**Files:**
- Modify: `LarcSuperviseur/views/core/event_actions.py:125`
- Create: `LarcSuperviseur/tests/test_event_actions_qt.py` (fichier séparé de `test_event_actions.py`, qui reste volontairement sans dépendance Qt — cf. son propre docstring)

**Interfaces:**
- Consumes : fixtures `qtbot`, `mock_db`, `mock_session`, `mock_theme`.
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Write the failing test**

Créer `LarcSuperviseur/tests/test_event_actions_qt.py` :

```python
"""Tests UI (qtbot) d'EventActions.get_context_menu — seule méthode Qt-dépendante
de ce module (cf. test_event_actions.py pour les tests non-Qt)."""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QWidget

from LarcSuperviseur.views.core.event_actions import EventActions


def test_get_context_menu_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    fake_cursor = mock_db.server_conn.cursor.return_value
    fake_cursor.fetchone.return_value = None

    parent = QWidget()
    qtbot.addWidget(parent)
    recwarn.clear()

    EventActions().get_context_menu(1, parent=parent)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_actions_qt.py -v -m "not integration"`
Expected: FAIL — 1 warning (M3Menu ligne 125).

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/core/event_actions.py`, ligne 125 :

```python
        menu = M3Menu(theme=theme_manager.phi_theme, parent=parent)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_actions_qt.py -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full event_actions suite to check no regression**

Run: `pytest tests/test_event_actions.py tests/test_event_actions_qt.py -v -m "not integration"`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/core/event_actions.py LarcSuperviseur/tests/test_event_actions_qt.py
git commit -m "fix(larcsuperviseur): theme= manquant sur M3Menu de EventActions.get_context_menu"
```

---

### Task 5: timetable_editor.py — TimetableEditor

**Files:**
- Modify: `LarcSuperviseur/views/dialogs/timetable_editor.py:31-39` (`__init__`), `:47`, `:55`, `:120`
- Test: `LarcSuperviseur/tests/test_timetable_editor.py`

**Interfaces:**
- Consumes : helper `_make_editor(qtbot, mock_db)` déjà défini dans le fichier de test.
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `LarcSuperviseur/tests/test_timetable_editor.py` :

```python
def test_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchall.side_effect = [
        [(1, time(8, 0), time(8, 55), 1), (2, time(9, 0), time(9, 55), 1)],
        [(11, 1, 1, "Maths")],
        [("Maths",), ("Anglais",)],
    ]
    recwarn.clear()

    _make_editor(qtbot, mock_db)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_timetable_editor.py::test_no_theme_warning -v -m "not integration"`
Expected: FAIL — M3TableWidget (1) + M3ComboBox ×10 (2 créneaux × 5 jours) + M3Button save_btn (1) = 12 warnings.

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/dialogs/timetable_editor.py`, dans `__init__` (après la ligne `self.setMinimumSize(...)`, avant `self._init_ui()`), ajouter le fond thémé SANS passer `theme=` à `super().__init__()` (cf. contrainte globale du plan — `M3Dialog` construirait sinon sa propre UI en conflit avec `_init_ui()`) :

```python
    def __init__(self, class_id: int, class_label: str, term_id: int, parent=None):
        super().__init__(parent)
        self._loader = DataLoader()
        self._class_id = class_id
        self._term_id = term_id
        self.setWindowTitle(_("timetable.title").format(label=class_label))
        self.setMinimumSize(ds.window_width * 2 // 3, ds.window_height * 5 // 8)  # 800×500
        p = theme_manager.palette
        self.setStyleSheet(f"TimetableEditor {{ background-color: {p.surface}; border-radius: {ds.radius_lg}px; }}")
        self._init_ui()
        self._load_data()
```

Ligne 47 :

```python
        self._tt_grid = M3TableWidget(theme=theme_manager.phi_theme)
```

Ligne 55 :

```python
        save_btn = M3Button(_("timetable.save_button"), theme=theme_manager.phi_theme)
```

Ligne 120 :

```python
                    combo = M3ComboBox(theme=theme_manager.phi_theme)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_timetable_editor.py::test_no_theme_warning -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Run the full file suite to check no regression**

Run: `pytest tests/test_timetable_editor.py -v -m "not integration"`
Expected: tous les tests passent (y compris les 3 tests existants).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/dialogs/timetable_editor.py LarcSuperviseur/tests/test_timetable_editor.py
git commit -m "fix(larcsuperviseur): theme= manquant sur les widgets M3 de TimetableEditor"
```

---

## Hors périmètre (volontairement non traité par ce plan)

- `dialogs/preferences.py` : exclu — c'est du code mort (cause racine #2, "implémentations dupliquées"), la vraie décision est de le supprimer, pas d'y ajouter `theme=`.
- `event_actions.py:122-143` (le reste de `get_context_menu` au-delà du fix `theme=`) et la duplication `main_events._edit_event` vs `event_dialog.EventEditDialog` : signalés dans l'audit comme observations UX/flux, hors périmètre design — l'auteur du projet les traite séparément.
- QA visuelle (capture d'écran avant/après) : à faire manuellement après ce plan, les tests ci-dessus vérifient l'absence de warning, pas le rendu pixel.

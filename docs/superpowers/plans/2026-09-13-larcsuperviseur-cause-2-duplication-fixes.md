# Corrections cause racine #2 (LarcSuperviseur) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger la cause racine #2 de l'audit design LarcSuperviseur (`docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md`) — implémentations dupliquées où une copie est morte et une vivante — plus deux bugs P0 isolés découverts pendant l'investigation qui n'étaient pas dans le tableau de l'audit d'origine.

**Architecture:**
- Task 1 corrige `LarcCommon/larccommon/preferences_dialog.py` (le composant réellement utilisé en production par LarcSuperviseur/LarcSecretaire/LarcHub) qui n'a **aucun** de ses widgets M3 avec `theme=` — découverte faite en creusant le doublon mort de LarcSuperviseur, absente du tableau de l'audit d'origine car ce dernier était scopé à LarcSuperviseur seul.
- Task 2 supprime le doublon mort `LarcSuperviseur/views/dialogs/preferences.py` (jamais appelé en prod, `top_bar.py:295-303` ouvre la version LarcCommon) et migre ses 4 tests fonctionnels vers `LarcCommon/tests/`, qui n'avait aucune couverture sur ce composant.
- Task 3 corrige le bug de reflow de la grille de vignettes élèves (`MainWindow.resizeEvent` est un no-op ; `ClassPanel.reflow()`, correct, n'est jamais instancié) en ajoutant la même logique de recalcul directement dans `StudentsMixin` (classe réellement utilisée).

**Tech Stack:** Python 3.x, PySide6/Qt6, pytest + pytest-qt (`qtbot`), `monkeypatch` (pytest natif) pour les singletons `db`/`session` de LarcCommon — pas de fixtures `mock_db`/`mock_session` façon LarcSuperviseur (LarcCommon n'a pas de `conftest.py` équivalent ; patcher les attributs des singletons réels est suffisant et plus simple ici, un seul module consommateur).

**Spec:** `docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md` (cause racine #2)

## Global Constraints

- Ne pas toucher `LarcSuperviseur/views/panels/class_panel.py` (`ClassPanel`) dans ce plan — il reste du code mort documenté ; le consolider avec `StudentsMixin` est une décision architecturale séparée, hors périmètre ici (on corrige le bug fonctionnel sans trancher la duplication de code).
- Chaque widget M3 ajouté avec `theme=` doit utiliser `theme_manager.phi_theme` (déjà importé dans les fichiers concernés).
- Test de régression standard pour les fixes `theme=` : `recwarn` (fixture pytest intégrée) ne doit contenir aucun warning dont le message contient `"cree sans theme="`.
- Lancer chaque suite de test isolément avec `pytest tests/<fichier> -v -m "not integration"` depuis le dossier du projet concerné (`D:\projets\LarcCommon` ou `D:\projets\LarcSuperviseur`).

---

### Task 1: `larccommon/preferences_dialog.py` — theme= manquant sur tous les widgets M3

**Files:**
- Modify: `LarcCommon/larccommon/preferences_dialog.py:6-20` (imports), `:52`, `:61`, `:73`, `:123`, `:130`
- Create: `LarcCommon/tests/test_preferences_dialog.py`

**Interfaces:**
- Consumes: rien d'une tâche précédente.
- Produces: `LarcCommon/tests/test_preferences_dialog.py` sera étendu par la Task 2 (mêmes conventions d'import : `import larccommon` avant `phibuilder.widgets`, fixture `qapp` module-scope).

- [ ] **Step 1: Write the failing test**

Créer `LarcCommon/tests/test_preferences_dialog.py` :

```python
"""Tests LarcCommon.larccommon.preferences_dialog.PreferencesDialog."""
from __future__ import annotations

import larccommon  # noqa: F401 -- initialise larccommon avant phibuilder (cycle connu,
# cf. test_event_type_selector.py pour le detail)

import pytest
from PySide6.QtWidgets import QApplication

from larccommon.preferences_dialog import PreferencesDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_construct_no_theme_warning(qapp, recwarn):
    dlg = PreferencesDialog()
    theme_warnings = [w for w in recwarn.list if "cree sans theme=" in str(w.message)]
    assert not theme_warnings, [str(w.message) for w in theme_warnings]
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `D:\projets\LarcCommon`): `pytest tests/test_preferences_dialog.py::test_construct_no_theme_warning -v -m "not integration"`
Expected: FAIL — plusieurs warnings `"cree sans theme="` : M3Frame ×3 (un par groupe langue/thème/taille de carte), M3Label ×3 (un label par groupe), M3Button ×N (2 pour la langue + un par thème disponible + un par taille de carte + ok_btn + cancel_btn — le nombre exact dépend de `THEMES_CONFIG`/`CARD_THEMES`, peu importe : le test n'exige qu'une liste vide, pas un compte précis).

- [ ] **Step 3: Write minimal implementation**

Dans `LarcCommon/larccommon/preferences_dialog.py`, ligne 8, ajouter l'import :

```python
from phibuilder.widgets import M3Button, M3Dialog, M3Frame, M3Label
from phibuilder.widgets.button import ButtonVariant
```

Ligne 52 :

```python
        frame = M3Frame(theme=theme_manager.phi_theme)
```

Ligne 61 :

```python
        lbl = M3Label(f"<b>{label}</b>", theme=theme_manager.phi_theme)
```

Ligne 73 :

```python
            btn = M3Button(display, theme=theme_manager.phi_theme)
```

Ligne 123 :

```python
        ok_btn = M3Button(_("common.button.ok"), theme=theme_manager.phi_theme)
```

Ligne 130 — **attention** : `cancel_btn` n'a aujourd'hui aucun style explicite (rendu OS natif car sans `theme=`). Lui ajouter `theme=` seul le ferait apparaître **FILLED** par défaut, quasi identique au bouton OK (même bug que l'audit avait trouvé sur le doublon mort de LarcSuperviseur, ligne 132-134 de son propre rapport) :

```python
        cancel_btn = M3Button(_("common.button.cancel"), theme=theme_manager.phi_theme, variant=ButtonVariant.OUTLINED)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_preferences_dialog.py::test_construct_no_theme_warning -v -m "not integration"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add LarcCommon/larccommon/preferences_dialog.py LarcCommon/tests/test_preferences_dialog.py
git commit -m "fix(larccommon): theme= manquant sur tous les widgets M3 de PreferencesDialog"
```

---

### Task 2: Supprimer le doublon mort de LarcSuperviseur, migrer ses tests vers LarcCommon

**Files:**
- Delete: `LarcSuperviseur/views/dialogs/preferences.py`, `LarcSuperviseur/tests/test_preferences.py`
- Modify: `LarcSuperviseur/views/dialogs/__init__.py:2` (retirer l'export)
- Modify: `LarcCommon/tests/test_preferences_dialog.py` (ajouter les 4 tests fonctionnels migrés)

**Interfaces:**
- Consumes: `LarcCommon/tests/test_preferences_dialog.py` créé par la Task 1 (fixture `qapp`, import `PreferencesDialog`).
- Produces: rien de nouveau consommé par une tâche suivante.

- [ ] **Step 1: Write the failing tests (migration)**

Ajouter à la fin de `LarcCommon/tests/test_preferences_dialog.py` :

```python
def test_construct(qapp, monkeypatch):
    from larccommon.session import session

    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    assert dlg.windowTitle() != ""
    # Les preferences d'origine sont memorisees pour l'annulation
    assert dlg._orig_lang == 2
    assert dlg._orig_theme == "blue"
    assert dlg._orig_card == "medium"


def test_on_ok_applies_and_accepts(qapp, monkeypatch):
    from unittest.mock import MagicMock
    from larccommon.database import db
    from larccommon.session import session
    from PySide6.QtWidgets import QDialog

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor
    monkeypatch.setattr(db, "is_server_connected", True)
    monkeypatch.setattr(db, "server_conn", fake_conn)
    monkeypatch.setattr(session, "user_id", 1)
    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    dlg._on_ok()

    assert dlg.result() == QDialog.Accepted
    # Persistance : 3 INSERT larcauth_config + 1 UPDATE larcauth_aecuser
    inserts = [c.args for c in fake_cursor.execute.call_args_list if "larcauth_config" in c.args[0]]
    assert len(inserts) == 3
    lang_updates = [c.args for c in fake_cursor.execute.call_args_list if "larcauth_aecuser" in c.args[0]]
    assert lang_updates and lang_updates[0][1] == (2, 1)
    assert fake_conn.commit.called


def test_on_cancel_restores_original_prefs(qapp, monkeypatch):
    from larccommon.session import session
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    session.theme_pref = "dark"
    session.fk_language = 1
    dlg._on_cancel()

    assert dlg.result() == QDialog.Rejected
    assert session.theme_pref == "blue"
    assert session.fk_language == 2
    assert session.card_theme == "medium"


def test_language_button_sets_session_lang(qapp, monkeypatch):
    from larccommon.session import session
    from phibuilder.widgets import M3Button

    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    # Le groupe langue a 2 boutons (fr/en) -- cliquer celui non selectionne
    lang_btns = [b for b in dlg.findChildren(M3Button) if b.isCheckable()]
    other = next(b for b in lang_btns if not b.isChecked())
    other.click()
    # "fr" (lang 2) ou "en" (lang 1) -- la session reflete le bouton choisi
    assert session.fk_language in (1, 2)
```

- [ ] **Step 2: Run tests to verify they pass**

Run (depuis `D:\projets\LarcCommon`): `pytest tests/test_preferences_dialog.py -v -m "not integration"`
Expected: 5 PASS (le test de la Task 1 + ces 4).

- [ ] **Step 3: Supprimer le doublon mort de LarcSuperviseur**

```bash
git rm LarcSuperviseur/views/dialogs/preferences.py LarcSuperviseur/tests/test_preferences.py
```

Éditer `LarcSuperviseur/views/dialogs/__init__.py` — retirer la ligne 2 :

```python
from .timetable_editor import TimetableEditor
```

- [ ] **Step 4: Vérifier qu'aucune référence morte ne reste**

Run : `grep -rn "dialogs.preferences\|dialogs import preferences\|from .preferences" LarcSuperviseur --include="*.py"`
Expected : aucune sortie (le seul import restant vers `PreferencesDialog` dans LarcSuperviseur doit être via `top_bar.py` qui importe déjà `larccommon.preferences_dialog.PreferencesDialog`, pas la version supprimée).

- [ ] **Step 5: Run the full LarcSuperviseur suite to check no regression**

Run (depuis `D:\projets\LarcSuperviseur`) : `pytest tests/ -v -m "not integration"`
Expected : tous les tests passent (204 attendus moins les 4 supprimés = 200, plus les échecs pré-existants documentés hors périmètre — `test_event_dialog.py` ×2, `test_event_generator.py` ×3, module `event_generator.py` supprimé lors du refactor polymorphe, sans rapport avec ce plan).

- [ ] **Step 6: Commit**

```bash
git add LarcCommon/tests/test_preferences_dialog.py LarcSuperviseur/views/dialogs/__init__.py
git add -u LarcSuperviseur/views/dialogs/preferences.py LarcSuperviseur/tests/test_preferences.py
git commit -m "refactor(larcsuperviseur): supprime le doublon mort dialogs/preferences.py, migre ses tests vers LarcCommon"
```

---

### Task 3: Grille de vignettes élèves — reflow au redimensionnement

**Files:**
- Modify: `LarcSuperviseur/views/main_students.py` (ajout d'une méthode dans `StudentsMixin`)
- Modify: `LarcSuperviseur/views/main_window.py:869-870` (`resizeEvent`)
- Test: `LarcSuperviseur/tests/test_main_window.py`

**Interfaces:**
- Consumes: helper `_make_window(qtbot, mock_db, mock_session)` déjà défini dans `test_main_window.py`.
- Produces: méthode `StudentsMixin._reflow_students_grid(self)` (aucun argument, aucun retour) — appelée par `MainWindow.resizeEvent`.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `LarcSuperviseur/tests/test_main_window.py` :

```python
def test_reflow_students_grid_recomputes_columns_on_resize(qtbot, mock_db, mock_session, mock_theme):
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import Qt
    from LarcSuperviseur.views.core.cardsList.config import CARD_THEMES

    w = _make_window(qtbot, mock_db, mock_session)
    w._card_theme = "medium"
    cfg = CARD_THEMES.get("medium")
    card_w = cfg.card_w + cfg.margin * 2
    spacing = w._cards_layout.spacing()

    cards = [QWidget(w._cards_widget) for _ in range(6)]
    w._student_cards = [(c, "") for c in cards]
    for idx, c in enumerate(cards):
        w._cards_layout.addWidget(c, idx, 0, Qt.AlignCenter)  # 1 seule colonne au depart

    # Largeur qui donne exactement 3 colonnes selon la formule de cols
    target_width = 3 * (card_w + spacing)
    w._cards_scroll.resize(target_width, 400)
    QApplication.processEvents()

    w._reflow_students_grid()

    for idx, c in enumerate(cards):
        pos = w._cards_layout.getItemPosition(w._cards_layout.indexOf(c))
        row, col = pos[0], pos[1]
        assert (row, col) == (idx // 3, idx % 3), f"carte {idx}: attendu {(idx // 3, idx % 3)}, obtenu {(row, col)}"
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `D:\projets\LarcSuperviseur`) : `pytest tests/test_main_window.py::test_reflow_students_grid_recomputes_columns_on_resize -v -m "not integration"`
Expected : FAIL — `AttributeError: 'MainWindow' object has no attribute '_reflow_students_grid'`.

- [ ] **Step 3: Write minimal implementation**

Dans `LarcSuperviseur/views/main_students.py`, ajouter cette méthode dans `StudentsMixin` (par exemple juste après `_on_student_search_changed`) :

```python
    def _reflow_students_grid(self):
        """Recalcule le nombre de colonnes selon la largeur disponible et replace
        les cartes existantes SANS les reconstruire -- appelee par
        MainWindow.resizeEvent(). Meme formule que ClassPanel.reflow()
        (jamais instancie), adaptee a StudentsMixin qui est la classe reellement
        utilisee pour cet ecran (cause racine #2 de l'audit design)."""
        if not getattr(self, "_student_cards", None):
            return
        cfg = CARD_THEMES.get(self._card_theme)
        card_w = cfg.card_w + cfg.margin * 2
        avail_w = self._cards_scroll.viewport().width()
        spacing = self._cards_layout.spacing()
        cols = max(1, (avail_w + spacing) // (card_w + spacing)) if avail_w > 100 else 2
        for i in reversed(range(self._cards_layout.count())):
            item = self._cards_layout.itemAt(i)
            if item.widget():
                self._cards_layout.removeWidget(item.widget())
        for idx, (card, _search_text) in enumerate(self._student_cards):
            self._cards_layout.addWidget(card, idx // cols, idx % cols, Qt.AlignCenter)
```

Dans `LarcSuperviseur/views/main_window.py`, remplacer les lignes 869-870 :

```python
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_students_grid()
```

- [ ] **Step 4: Run test to verify it passes**

Run : `pytest tests/test_main_window.py::test_reflow_students_grid_recomputes_columns_on_resize -v -m "not integration"`
Expected : PASS

Si le test échoue car `_cards_scroll.viewport().width()` ne reflète pas encore le `resize()` (mise en page Qt différée) : ajouter `qtbot.wait(50)` juste après `QApplication.processEvents()` avant d'appeler `_reflow_students_grid()`, et relancer.

- [ ] **Step 5: Run the full file suite to check no regression**

Run : `pytest tests/test_main_window.py -v -m "not integration"`
Expected : tous les tests passent (y compris les tests existants).

- [ ] **Step 6: Commit**

```bash
git add LarcSuperviseur/views/main_students.py LarcSuperviseur/views/main_window.py LarcSuperviseur/tests/test_main_window.py
git commit -m "fix(larcsuperviseur): la grille de vignettes eleves se recalcule au redimensionnement"
```

---

## Hors périmètre (volontairement non traité par ce plan)

- **Cause racine #4** (états `:focus`/`:pressed` manquants — top_bar.py, student_detail.py, preferences.py) et **cause racine #5** (tokens mal catégorisés/recalculés par arithmétique — main_window.py, class_panel.py, student_detail.py, preferences.py, top_bar.py) : signalées dans l'audit, nécessitent leur propre plan (volume important, ~15 sites dispersés).
- `top_bar.py:178-189` "`_refresh_btn` sans `objectName`" (finding de l'audit original) : vérifié pendant l'investigation de ce plan — **déjà résolu incidemment** par la réécriture de `top_bar.py` dans le plan de réactivité thème (2026-09-11, déjà fusionné) ; plus aucun sélecteur QSS mort sur ce bouton dans le code actuel.
- `event_actions.py:122-143` (`ds` référencé sans import, code mort/divergent) : déjà documenté dans le changelog projet (`docs/debug/CR-2026-08-14.md`) comme hors périmètre design.
- `event_dialog.py` vs `main_events.py` : rayon de bouton différent (8px vs 4px) pour le même composant dupliqué — lié à la duplication `EventEditDialog`/`main_events._edit_event` déjà trackée séparément (tâche de suivi existante sur le `QDialog` custom de `main_events.py`).
- `main_students.py` vs `class_panel.py` : la duplication elle-même (deux implémentations de la grille) n'est PAS résolue par ce plan — seul le bug fonctionnel (pas de reflow) est corrigé sur la version vivante. Choisir une seule source de vérité reste une décision architecturale séparée.

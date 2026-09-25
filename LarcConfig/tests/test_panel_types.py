"""Tests UI (qtbot) de TypesPanel — édition du libellé (colonne 2) et emplacements libres.

Non-régression : `_on_item_changed` ne doit plus tronquer le libellé tapé
par l'utilisateur en supposant que le préfixe d'indentation visuel
("    " * depth) reste intact après une édition normale de la cellule
(sélection totale du texte + retype), qui remplace TOUT le contenu de la
cellule y compris ce préfixe.

Pas de framework Qt de test dédié dans ce fichier avant ce correctif — on
suit le pattern qtbot déjà utilisé dans LarcSuperviseur/tests (mock_db,
mock_session, mock_theme n'existent pas pour LarcConfig : on mocke
directement les fonctions de LarcConfig.common.db_access importées dans
le module panel_types, et on utilise le vrai theme_manager — un singleton
sans dépendance DB/réseau, donc sûr à instancier tel quel dans un test).
"""
from __future__ import annotations

import copy
from unittest.mock import MagicMock

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtCore import Qt

import LarcConfig.views.panel_types as panel_types_mod
from LarcConfig.views.panel_types import TypesPanel

FAKE_ROWS = [
    {'id': 21000, 'depth': 0, 'label': 'Absence', 'code': 'absence', 'enabled': True,
     'is_free': False, 'parent_id': None},
    {'id': 21100, 'depth': 1, 'label': "Absent de l'école", 'code': 'absence_school',
     'enabled': True, 'is_free': False, 'parent_id': 21000},
]
FREE_ROW = {'id': 21200, 'depth': 1, 'label': 'Categorie_Niv21000_Level_2',
            'code': 'type_niv2_21200', 'enabled': False, 'is_free': True, 'parent_id': 21000}


def _make_panel(qtbot, monkeypatch, rows=None):
    calls = []

    def _tree(fk_language, include_free=False):
        calls.append(include_free)
        return copy.deepcopy(rows or FAKE_ROWS)   # le panneau modifie ses lignes en place

    monkeypatch.setattr(panel_types_mod, "get_event_type_tree", _tree)
    monkeypatch.setattr(panel_types_mod, "set_event_type_active", MagicMock(return_value=True))
    monkeypatch.setattr(panel_types_mod, "set_event_type_label", MagicMock(return_value=True))
    monkeypatch.setattr(panel_types_mod, "activate_event_type", MagicMock(return_value=True))
    panel = TypesPanel(user={"id": 1})
    panel._tree_calls = calls
    qtbot.addWidget(panel)
    return panel


def test_reload_stores_raw_label_in_user_role(qtbot, monkeypatch):
    """La cellule affiche l'indentation, mais Qt.UserRole garde le libellé nu."""
    panel = _make_panel(qtbot, monkeypatch)

    item_depth1 = panel._table.item(1, 2)
    assert item_depth1.text() == "    Absent de l'école"
    assert item_depth1.data(Qt.UserRole) == "Absent de l'école"


def test_full_cell_replacement_saves_untruncated_label(qtbot, monkeypatch):
    """Reproduction du bug : sélection totale de la cellule + retype.

    Qt remplace alors TOUT le texte affiché (y compris le préfixe
    d'indentation) par le texte tapé par l'utilisateur. L'ancien code
    coupait aveuglément les N premiers caractères du texte final
    (len("    " * depth)), tronquant le vrai libellé tapé. Le correctif
    ne doit sauvegarder que le préfixe d'indentation s'il est encore
    présent — jamais tronquer un texte qui ne le porte pas.
    """
    panel = _make_panel(qtbot, monkeypatch)

    item = panel._table.item(1, 2)  # depth=1, préfixe normal = "    "
    # Simule : l'utilisateur sélectionne tout puis tape un nouveau texte SANS
    # ré-écrire l'indentation (comportement normal d'une édition de cellule).
    item.setText("Nouveau libellé complet")

    panel_types_mod.set_event_type_label.assert_called_once_with(21100, "Nouveau libellé complet")


def test_full_cell_replacement_updates_user_role_for_next_edit(qtbot, monkeypatch):
    """Après sauvegarde, Qt.UserRole doit refléter le nouveau libellé (pas l'ancien),
    et l'affichage doit ré-appliquer l'indentation proprement — sinon une 2e
    édition consécutive repartirait d'un état obsolète."""
    panel = _make_panel(qtbot, monkeypatch)

    item = panel._table.item(1, 2)
    item.setText("Premier changement")

    assert item.data(Qt.UserRole) == "Premier changement"
    assert item.text() == "    Premier changement"

    panel_types_mod.set_event_type_label.reset_mock()
    item.setText("Deuxieme changement")

    panel_types_mod.set_event_type_label.assert_called_once_with(21100, "Deuxieme changement")
    assert item.data(Qt.UserRole) == "Deuxieme changement"


def test_edit_preserving_indent_prefix_still_strips_it(qtbot, monkeypatch):
    """Si l'utilisateur ne touche qu'à la fin du texte (indentation intacte),
    le préfixe reste correctement retiré du libellé sauvegardé."""
    panel = _make_panel(qtbot, monkeypatch)

    item = panel._table.item(1, 2)
    item.setText("    Absent de l'ecole (retard)")

    panel_types_mod.set_event_type_label.assert_called_once_with(21100, "Absent de l'ecole (retard)")


def test_default_view_asks_without_free_slots(qtbot, monkeypatch):
    panel = _make_panel(qtbot, monkeypatch)
    assert panel._tree_calls == [False]
    panel._view_combo.setCurrentIndex(1)
    assert panel._tree_calls[-1] is True


def test_free_slot_cannot_be_activated_before_renaming(qtbot, monkeypatch):
    """Un emplacement libre (Categorie_Niv…) doit être renommé avant d'être activé."""
    warned = MagicMock()
    monkeypatch.setattr(panel_types_mod.QMessageBox, "warning", warned)
    panel = _make_panel(qtbot, monkeypatch, rows=FAKE_ROWS + [FREE_ROW])

    panel._table.item(2, 4).setCheckState(Qt.Checked)

    warned.assert_called_once()
    panel_types_mod.set_event_type_active.assert_not_called()


def test_renamed_free_slot_can_be_activated(qtbot, monkeypatch):
    free = dict(FREE_ROW, label="Bagarre")           # déjà renommé
    panel = _make_panel(qtbot, monkeypatch, rows=FAKE_ROWS + [free])

    panel._table.item(2, 4).setCheckState(Qt.Checked)

    panel_types_mod.set_event_type_active.assert_called_once_with(21200, True)


def test_title_shows_language_and_selection_shows_path_and_range(qtbot, monkeypatch):
    panel = _make_panel(qtbot, monkeypatch)
    assert panel._title.text() == "Types d'événements — Français"

    panel._table.setCurrentCell(1, 2)          # « Absent de l'école », niveau 2
    assert panel._where.text() == "Absence > Absent de l'école — ID 21100 (sa branche : de 21100 à 21199)"

    panel._lang_combo.setCurrentIndex(1)
    assert panel._title.text() == "Types d'événements — English"
    assert "encore ceux du français" in panel._hint.text()


def test_text_filter_hides_non_matching_rows(qtbot, monkeypatch):
    panel = _make_panel(qtbot, monkeypatch)
    panel._filter_text.setText("école")
    assert [panel._table.isRowHidden(i) for i in range(2)] == [True, False]
    panel._filter_text.setText("21000")                 # filtre par ID
    assert [panel._table.isRowHidden(i) for i in range(2)] == [False, True]
    panel._filter_text.setText("")
    assert [panel._table.isRowHidden(i) for i in range(2)] == [False, False]


def test_level_filter_keeps_only_that_level(qtbot, monkeypatch):
    panel = _make_panel(qtbot, monkeypatch)
    panel._filter_level.setCurrentIndex(2)              # N2
    assert [panel._table.isRowHidden(i) for i in range(2)] == [True, False]


def test_columns_are_user_resizable(qtbot, monkeypatch):
    from PySide6.QtWidgets import QHeaderView
    panel = _make_panel(qtbot, monkeypatch)
    h = panel._table.horizontalHeader()
    assert h.sectionResizeMode(0) == QHeaderView.Interactive
    assert h.sectionResizeMode(3) == QHeaderView.Interactive


def test_used_type_is_locked_and_cannot_be_disabled(qtbot, monkeypatch):
    rows = [dict(FAKE_ROWS[0], usage=3), dict(FAKE_ROWS[1], usage=3)]
    warned = MagicMock()
    monkeypatch.setattr(panel_types_mod.QMessageBox, "warning", warned)
    panel = _make_panel(qtbot, monkeypatch, rows=rows)

    label_item = panel._table.item(1, 2)
    assert not (label_item.flags() & Qt.ItemIsEditable)          # libellé verrouillé
    assert panel._table.item(1, 3).text() == "3"                 # colonne « Utilisé »

    panel._table.item(1, 4).setCheckState(Qt.Unchecked)          # tentative de désactivation
    warned.assert_called_once()
    panel_types_mod.set_event_type_active.assert_not_called()


def test_unused_type_stays_editable_and_can_be_disabled(qtbot, monkeypatch):
    panel = _make_panel(qtbot, monkeypatch)
    assert panel._table.item(1, 2).flags() & Qt.ItemIsEditable
    assert panel._table.item(1, 3).text() == ""

    panel._table.item(1, 4).setCheckState(Qt.Unchecked)
    panel_types_mod.set_event_type_active.assert_called_once_with(21100, False)


def test_disabled_real_type_stays_listed_and_can_be_reenabled(qtbot, monkeypatch):
    off = dict(FAKE_ROWS[1], id=21200, label="Ancien motif", enabled=False, is_free=False)
    panel = _make_panel(qtbot, monkeypatch, rows=FAKE_ROWS + [off])
    assert panel._table.rowCount() == 3                        # le type désactivé reste visible
    assert "1 désactivés" in panel._hint.text()

    panel._table.item(2, 4).setCheckState(Qt.Checked)
    panel_types_mod.set_event_type_active.assert_called_once_with(21200, True)


def _dialogs(monkeypatch, path):
    """Remplace les boîtes de dialogue (fichier, message) par des doubles."""
    monkeypatch.setattr(panel_types_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (path, "")))
    monkeypatch.setattr(panel_types_mod.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (path, "")))
    info, warn = MagicMock(), MagicMock()
    monkeypatch.setattr(panel_types_mod.QMessageBox, "information", info)
    monkeypatch.setattr(panel_types_mod.QMessageBox, "warning", warn)
    return info, warn


def test_export_writes_an_xlsx_file(qtbot, monkeypatch, tmp_path):
    panel = _make_panel(qtbot, monkeypatch)
    target = tmp_path / "export"                       # extension ajoutée automatiquement
    info, _warn = _dialogs(monkeypatch, str(target))
    monkeypatch.setattr(panel_types_mod.types_excel, "export_types_xlsx",
                        lambda path, author="": open(path, "wb").close() or path)

    panel._on_export()

    assert (tmp_path / "export.xlsx").exists()
    info.assert_called_once()


def test_import_of_unreadable_file_warns_and_changes_nothing(qtbot, monkeypatch, tmp_path):
    panel = _make_panel(qtbot, monkeypatch)
    bad = tmp_path / "bad.xlsx"
    bad.write_text("pas un classeur")
    _info, warn = _dialogs(monkeypatch, str(bad))

    panel._on_import()

    warn.assert_called_once()
    panel_types_mod.set_event_type_label.assert_not_called()


def test_import_asks_confirmation_and_applies_only_when_confirmed(qtbot, monkeypatch, tmp_path):
    from LarcConfig.common import types_excel as tx
    panel = _make_panel(qtbot, monkeypatch)
    path = tmp_path / "in.xlsx"
    _dialogs(monkeypatch, str(path))
    plan = tx.ImportPlan(changes=[tx.Change(2, 21100, 'label', "Absent de l'école", "Autre")])
    monkeypatch.setattr(tx, "read_types_xlsx", lambda p: {2: []})
    monkeypatch.setattr(tx, "plan_import", lambda sheets, current: plan)
    applied = MagicMock(return_value=(1, []))
    monkeypatch.setattr(tx, "apply_plan", applied)

    monkeypatch.setattr(panel, "_confirm_import", lambda p: False)       # l'utilisateur annule
    panel._on_import()
    applied.assert_not_called()

    monkeypatch.setattr(panel, "_confirm_import", lambda p: True)        # l'utilisateur confirme
    panel._on_import()
    applied.assert_called_once_with(plan)


def test_preview_text_lists_changes_and_refusals():
    from LarcConfig.common import types_excel as tx
    plan = tx.ImportPlan(
        changes=[tx.Change(2, 21200, 'label', "A", "B"), tx.Change(2, 21300, 'activate', "Non", "Oui")],
        rejected=[(2, 21100, "utilisé par 2 événement(s) : renommage interdit")])
    text = panel_types_mod.preview_text(plan)
    assert "2 modification(s)" in text and "1 ligne(s) refusée(s)" in text
    assert "« A » → « B »" in text and "activé" in text and "renommage interdit" in text

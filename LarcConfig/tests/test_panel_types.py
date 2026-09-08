"""Tests UI (qtbot) de TypesPanel — édition du libellé (colonne 3).

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

from unittest.mock import MagicMock

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtCore import Qt

import LarcConfig.views.panel_types as panel_types_mod
from LarcConfig.views.panel_types import TypesPanel

FAKE_ROWS = [
    {
        'id': 1, 'depth': 0, 'label': 'Absence', 'category': 'absence',
        'parent_label': None, 'code': 'absence', 'enabled': True,
    },
    {
        'id': 2, 'depth': 1, 'label': "Absent de l'école", 'category': 'absence',
        'parent_label': 'Absence', 'code': 'absence_school', 'enabled': True,
    },
]


def _make_panel(qtbot, monkeypatch, rows=None):
    monkeypatch.setattr(panel_types_mod, "get_event_types", lambda fk_language: rows or FAKE_ROWS)
    monkeypatch.setattr(panel_types_mod, "set_event_type_active", MagicMock(return_value=True))
    monkeypatch.setattr(panel_types_mod, "set_event_type_label", MagicMock(return_value=True))
    monkeypatch.setattr(panel_types_mod, "activate_event_type", MagicMock(return_value=True))
    panel = TypesPanel(user={"id": 1})
    qtbot.addWidget(panel)
    return panel


def test_reload_stores_raw_label_in_user_role(qtbot, monkeypatch):
    """La cellule affiche l'indentation, mais Qt.UserRole garde le libellé nu."""
    panel = _make_panel(qtbot, monkeypatch)

    item_depth1 = panel._table.item(1, 3)
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

    item = panel._table.item(1, 3)  # depth=1, préfixe normal = "    "
    # Simule : l'utilisateur sélectionne tout puis tape un nouveau texte SANS
    # ré-écrire l'indentation (comportement normal d'une édition de cellule).
    item.setText("Nouveau libellé complet")

    panel_types_mod.set_event_type_label.assert_called_once_with(2, "Nouveau libellé complet")


def test_full_cell_replacement_updates_user_role_for_next_edit(qtbot, monkeypatch):
    """Après sauvegarde, Qt.UserRole doit refléter le nouveau libellé (pas l'ancien),
    et l'affichage doit ré-appliquer l'indentation proprement — sinon une 2e
    édition consécutive repartirait d'un état obsolète."""
    panel = _make_panel(qtbot, monkeypatch)

    item = panel._table.item(1, 3)
    item.setText("Premier changement")

    assert item.data(Qt.UserRole) == "Premier changement"
    assert item.text() == "    Premier changement"

    panel_types_mod.set_event_type_label.reset_mock()
    item.setText("Deuxieme changement")

    panel_types_mod.set_event_type_label.assert_called_once_with(2, "Deuxieme changement")
    assert item.data(Qt.UserRole) == "Deuxieme changement"


def test_edit_preserving_indent_prefix_still_strips_it(qtbot, monkeypatch):
    """Si l'utilisateur ne touche qu'à la fin du texte (indentation intacte),
    le préfixe reste correctement retiré du libellé sauvegardé."""
    panel = _make_panel(qtbot, monkeypatch)

    item = panel._table.item(1, 3)
    item.setText("    Absent de l'ecole (retard)")

    panel_types_mod.set_event_type_label.assert_called_once_with(2, "Absent de l'ecole (retard)")

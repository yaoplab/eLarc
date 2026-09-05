"""Tests pour le moteur de synchronisation (SyncManager).

Utilise SQLite en memoire pour local et ref, pas de PostgreSQL requis.
"""
import os
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'LarcCommon'))


class TestSyncDecide(unittest.TestCase):

    def test_noop_equal(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide('x', 'x', 'x'), CellAction.NOOP)

    def test_noop_both_null(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide(None, None, None), CellAction.NOOP)

    def test_pull_changed_on_server_only(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide('old', 'old', 'new'), CellAction.PULL)

    def test_push_changed_locally_only(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide('new', 'old', 'old'), CellAction.PUSH)

    def test_conflict_both_changed(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide('local', 'old', 'server'), CellAction.CONFLICT)

    def test_conflict_both_different_from_ref(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide('L', 'R', 'S'), CellAction.CONFLICT)

    def test_local_new_row_pull(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide(None, None, 'S'), CellAction.PULL)

    def test_local_new_row_push(self):
        from LarcProf.common.sync import _decide, CellAction
        self.assertEqual(_decide('L', None, None), CellAction.PUSH)

    def test_normalize_none(self):
        from LarcProf.common.sync import _normalize
        self.assertIsNone(_normalize(None))

    def test_normalize_empty_string(self):
        from LarcProf.common.sync import _normalize
        self.assertIsNone(_normalize(''))

    def test_normalize_null_string(self):
        from LarcProf.common.sync import _normalize
        self.assertIsNone(_normalize('null'))

    def test_normalize_keeps_value(self):
        from LarcProf.common.sync import _normalize
        self.assertEqual(_normalize('hello'), 'hello')

    def test_normalize_number(self):
        from LarcProf.common.sync import _normalize
        self.assertEqual(_normalize(42), 42)


class TestSyncReport(unittest.TestCase):

    def test_empty_report(self):
        from LarcProf.common.sync import SyncReport
        r = SyncReport()
        self.assertFalse(r.has_errors)
        self.assertFalse(r.has_conflicts)
        self.assertIn('Rien', r.summary())

    def test_report_with_pulls(self):
        from LarcProf.common.sync import SyncReport
        r = SyncReport(pulled=5, pushed=3)
        self.assertIn('5 pull', r.summary())
        self.assertIn('3 push', r.summary())

    def test_report_with_conflicts(self):
        from LarcProf.common.sync import SyncReport
        r = SyncReport(conflicts=['c1', 'c2'])
        self.assertTrue(r.has_conflicts)
        self.assertIn('2 conflit', r.summary())

    def test_report_with_errors(self):
        from LarcProf.common.sync import SyncReport
        r = SyncReport(errors=['e1'])
        self.assertTrue(r.has_errors)
        self.assertIn('1 erreur', r.summary())


if __name__ == '__main__':
    unittest.main()

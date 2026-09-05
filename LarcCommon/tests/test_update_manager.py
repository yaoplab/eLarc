"""Tests UpdateManager — registre de versions et mise à jour douce (R3)."""
from larccommon import update_manager as um
from larccommon.update_manager import UpdateInfo, UpdateManager, _version_tuple


class TestUpdateManager:
    def test_version_tuple_ordering(self):
        assert _version_tuple('1.0') == (1, 0)
        assert _version_tuple('1.10.2') > _version_tuple('1.9.9')
        assert _version_tuple('2.0') > _version_tuple('1.99')
        assert _version_tuple('abc') == (0,)

    def test_disabled_returns_none(self):
        mgr = UpdateManager('LarcProf', '1.0', {'Enabled': 'false'})
        assert mgr.check() is None

    def test_flags(self):
        assert UpdateManager('X', '1.0', {'Silent': 'true'}).silent() is True
        assert UpdateManager('X', '1.0').silent() is False
        assert UpdateManager('X', '1.0').enabled() is False
        assert UpdateManager('X', '1.0',
                             {'Enabled': 'true'}).enabled() is True

    def test_check_interval_min(self):
        assert UpdateManager('X', '1.0',
                             {'CheckIntervalMin': '30'}).check_interval_min() == 30
        # borne basse 10 min
        assert UpdateManager('X', '1.0',
                             {'CheckIntervalMin': '1'}).check_interval_min() == 10

    def test_apply_pending_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(um, 'PENDING_FILE', str(tmp_path / 'pending.json'))
        mgr = UpdateManager('X', '1.0', {'Enabled': 'true'})
        info = UpdateInfo('X', '1.0', '2.0', notes='corrections')
        assert mgr.apply(info, r'D:\projets\LarcProf\main.py', ['--mode4'])
        pending = mgr.pending()
        assert pending is not None
        assert pending['target'] == '2.0'
        assert pending['main'] == r'D:\projets\LarcProf\main.py'
        assert pending['argv'] == ['--mode4']
        mgr.clear_pending()
        assert mgr.pending() is None

    def test_should_apply_on_quit_silent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(um, 'PENDING_FILE', str(tmp_path / 'pending.json'))
        # Silencieux + aucune version distante (DB non connectée) → False
        mgr = UpdateManager('X', '1.0', {'Enabled': 'true', 'Silent': 'true'})
        assert mgr.should_apply_on_quit() is False
        # Update en attente → re-tenter même sans DB
        mgr.apply(UpdateInfo('X', '1.0', '2.0'), r'C:\main.py', [])
        assert mgr.should_apply_on_quit() is True
        mgr.clear_pending()

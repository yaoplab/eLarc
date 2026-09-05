"""Tests ErrorReporter — transport asynchrone, spool, dégradation (R1).

Les tests n'appellent PAS start() : report() → flush() est déterministe.
"""
import json

from larccommon.error_reporting import ErrorReporter


class FakeCursor:
    def __init__(self):
        self.rows = []

    def executemany(self, sql, rows):
        self.rows.extend(rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self):
        self.autocommit = True
        self.cursor_obj = FakeCursor()

    def cursor(self):
        return self.cursor_obj

    def close(self):
        pass


class TestErrorReporting:
    def test_flush_batch_to_pg(self, tmp_path):
        fake = FakeConn()
        rep = ErrorReporter('TestApp', '1.0',
                            {'Enabled': 'true', 'FlushIntervalSec': '3600'},
                            pg_conn_provider=lambda: fake,
                            spool_dir=str(tmp_path))
        rep.report('ERROR', 'msg1')
        rep.report('ERROR', 'msg2')
        rep.flush(timeout=2)
        rows = fake.cursor_obj.rows
        assert len(rows) == 2
        assert rows[0][1] == 'TestApp'  # app_name
        assert rows[0][7] == 'ERROR'    # level
        assert rows[0][11] == 'msg1'    # message
        rep.stop()

    def test_pg_down_goes_to_spool(self, tmp_path):
        rep = ErrorReporter('TestApp', '1.0',
                            {'Enabled': 'true', 'FlushIntervalSec': '3600'},
                            pg_conn_provider=lambda: None,
                            spool_dir=str(tmp_path))
        rep.report('ERROR', 'spooled')
        rep.flush(timeout=2)
        assert len(rep._spool.peek(10)) == 1
        rep.stop()

    def test_spool_replay_idempotent(self, tmp_path):
        fake = FakeConn()
        rep = ErrorReporter('TestApp', '1.0',
                            {'Enabled': 'true', 'FlushIntervalSec': '3600'},
                            pg_conn_provider=lambda: fake,
                            spool_dir=str(tmp_path))
        payload = json.dumps({'ts': '2026-08-23T00:00:00', 'level': 'ERROR',
                              'message': 'x', 'traceback': '', 'module': '',
                              'func': '', 'line': 0, 'context': {},
                              'app_name': 'TestApp', 'app_version': '1.0',
                              'user_id': None, 'user_name': None, 'role': None,
                              'conn_mode': None})
        sid = rep._spool.enqueue(payload)
        assert sid is not None
        rep._replay_spool()
        rows = fake.cursor_obj.rows
        assert len(rows) == 1
        assert rows[0][-1] == sid  # spool_id conservé (idempotence)
        assert rep._spool.peek(10) == []  # rejoué → supprimé
        rep.stop()

    def test_disabled_is_noop(self, tmp_path):
        rep = ErrorReporter('TestApp', '1.0', {'Enabled': 'false'},
                            spool_dir=str(tmp_path))
        rep.report('ERROR', 'rien')
        rep.flush(timeout=1)
        assert rep._queue.qsize() == 0
        assert rep._spool.peek(10) == []
        rep.stop()

    def test_queue_full_drops_without_raise(self, tmp_path):
        rep = ErrorReporter('TestApp', '1.0',
                            {'Enabled': 'true', 'QueueMax': '1',
                             'FlushIntervalSec': '3600'},
                            pg_conn_provider=lambda: None,
                            spool_dir=str(tmp_path))
        for _ in range(50):  # file pleine → drop compté, jamais de raise
            rep.report('ERROR', 'x' * 100)
        assert rep._dropped > 0
        rep.stop()

    def test_report_exception_context(self, tmp_path):
        fake = FakeConn()
        rep = ErrorReporter('TestApp', '1.0',
                            {'Enabled': 'true', 'FlushIntervalSec': '3600'},
                            pg_conn_provider=lambda: fake,
                            spool_dir=str(tmp_path))
        try:
            1 / 0
        except ZeroDivisionError as e:
            rep.report_exception(e, context={'probe': 1})
        rep.flush(timeout=2)
        rows = fake.cursor_obj.rows
        assert len(rows) == 1
        assert 'ZeroDivisionError' in rows[0][11]  # message
        assert rows[0][12]  # traceback présent
        assert rows[0][13]  # context JSON présent
        rep.stop()

    def test_start_stop_cycle(self, tmp_path):
        rep = ErrorReporter('TestApp', '1.0',
                            {'Enabled': 'true', 'FlushIntervalSec': '3600'},
                            pg_conn_provider=lambda: None,
                            spool_dir=str(tmp_path))
        rep.start()
        rep.report('ERROR', 'threaded')
        rep.stop()  # ne doit ni lever ni bloquer

"""Tests audit_context — contexte d'audit au niveau SESSION (R2)."""
from larccommon import audit_context
from larccommon.session import ConnMode, session


class FakeCur:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))


class FakeConn:
    def __init__(self):
        self.cur = FakeCur()

    def cursor(self):
        return self.cur


class TestAuditContext:
    def test_attach_sets_four_session_vars(self):
        audit_context._user_id = 42
        audit_context._user_name = 'Yao Lab'
        audit_context._sync_source = 'intranet'
        conn = FakeConn()
        audit_context.attach(conn)
        assert len(conn.cur.executed) == 4
        assert conn.cur.executed[0][1] == ('42',)           # modified_by
        assert conn.cur.executed[1][1] == ('Yao Lab',)      # modified_by_name
        assert conn.cur.executed[3][1] == ('intranet',)     # sync_source
        for sql, _ in conn.cur.executed:
            assert 'SET LOCAL' not in sql
            assert 'set_config' in sql

    def test_attach_none_is_noop(self):
        audit_context.attach(None)  # ne doit pas lever

    def test_refresh_reads_session(self):
        session.user_id = 7
        session.full_name = 'Test User'
        session.conn_mode = ConnMode.INTRANET
        audit_context.refresh()
        assert audit_context.current_user_id() == 7
        assert audit_context.current_user_name() == 'Test User'
        assert audit_context._sync_source == 'intranet'

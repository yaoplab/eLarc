"""Tests ErrorSpool — tampon SQLite local (R1)."""
from larccommon.error_spool import ErrorSpool


class TestErrorSpool:
    def test_enqueue_peek_mark_done(self, tmp_path):
        sp = ErrorSpool(str(tmp_path / 'spool.db'))
        sid = sp.enqueue('{"a": 1}')
        assert sid is not None
        rows = sp.peek(10)
        assert len(rows) == 1
        assert rows[0][0] == sid
        assert rows[0][1] == '{"a": 1}'
        sp.mark_done([sid])
        assert sp.peek(10) == []
        sp.close()

    def test_peek_oldest_first(self, tmp_path):
        sp = ErrorSpool(str(tmp_path / 'spool.db'))
        sp.enqueue('first')
        sp.enqueue('second')
        rows = sp.peek(10)
        assert rows[0][1] == 'first'
        assert rows[1][1] == 'second'
        sp.close()

    def test_prune_above_max(self, tmp_path):
        sp = ErrorSpool(str(tmp_path / 'spool.db'), max_rows=5)
        ids = [sp.enqueue(f'x{i}') for i in range(10)]
        assert all(i is not None for i in ids)
        dropped = sp.prune()
        assert dropped > 0
        assert len(sp.peek(100)) <= 5
        sp.close()

    def test_failure_returns_none(self, tmp_path):
        # Chemin invalide (un fichier bloque le dossier) → enqueue échoue sans lever
        blocker = tmp_path / 'blocker'
        blocker.write_text('x')
        sp = ErrorSpool(str(blocker / 'spool.db'))
        assert sp.enqueue('x') is None
        assert sp.peek(10) == []
        sp.close()

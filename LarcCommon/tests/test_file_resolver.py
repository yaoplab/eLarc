import os

from larccommon.session import ConnMode, session
from larccommon.widgets.file_resolver import FileResolver


class TestFileResolver:
    def test_local_path(self):
        r = FileResolver(base_dir="/data/students")
        assert r.local_path("123/doc.pdf") == os.path.normpath("/data/students/123/doc.pdf")
        assert r.local_path("123/sub/doc.pdf") == os.path.normpath("/data/students/123/sub/doc.pdf")

    def test_cloud_url(self):
        r = FileResolver(cloud_root="https://cloud.example.com/students")
        assert r.cloud_url("123/doc.pdf") == "https://cloud.example.com/students/123/doc.pdf"
        assert r.cloud_url("456/x.pdf") == "https://cloud.example.com/students/456/x.pdf"

    def test_cloud_url_trailing_slash(self):
        r = FileResolver(cloud_root="https://cloud.example.com/students/")
        assert r.cloud_url("123/doc.pdf") == "https://cloud.example.com/students/123/doc.pdf"

    def test_resolve_intranet_returns_local(self):
        r = FileResolver(base_dir="/local", cloud_root="https://cloud/x")
        old = session.conn_mode
        session.conn_mode = ConnMode.INTRANET
        try:
            assert r.resolve("1/doc.pdf") == os.path.normpath("/local/1/doc.pdf")
        finally:
            session.conn_mode = old

    def test_resolve_cloud_returns_url(self):
        r = FileResolver(base_dir="/local", cloud_root="https://cloud/x")
        old = session.conn_mode
        session.conn_mode = ConnMode.CLOUD
        try:
            assert r.resolve("1/doc.pdf") == "https://cloud/x/1/doc.pdf"
        finally:
            session.conn_mode = old

    def test_resolve_offline_returns_local(self):
        r = FileResolver(base_dir="/local", cloud_root="https://cloud/x")
        old = session.conn_mode
        session.conn_mode = ConnMode.OFFLINE
        try:
            assert r.resolve("1/doc.pdf") == os.path.normpath("/local/1/doc.pdf")
        finally:
            session.conn_mode = old

    def test_empty_base_dir(self):
        r = FileResolver()
        assert r.local_path("doc.pdf") == "doc.pdf"

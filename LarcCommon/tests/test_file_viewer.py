import os
import tempfile

from larccommon.widgets.file_viewer import FileViewer


class TestFileViewer:
    def test_create_with_image(self, qtbot):
        # Create a tiny valid PNG
        import struct
        import zlib

        def create_png(w, h):
            raw = b""
            for y in range(h):
                raw += b"\x00" + b"\xff\x00\x00" * w
            compressed = zlib.compress(raw)
            ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
            ihdr_chunk = b"IHDR" + ihdr
            ihdr_chunk = (
                struct.pack(">I", len(ihdr))
                + ihdr_chunk
                + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
            )
            idat_chunk = b"IDAT" + compressed
            idat_chunk = (
                struct.pack(">I", len(compressed))
                + idat_chunk
                + struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
            )
            iend_chunk = (
                struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
            )
            return b"\x89PNG\r\n\x1a\n" + ihdr_chunk + idat_chunk + iend_chunk

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(create_png(4, 4))
            png_path = f.name

        try:
            dlg = FileViewer(png_path)
            assert dlg.windowTitle() == os.path.basename(png_path)
            assert dlg.minimumWidth() == 610
            dlg.accept()
        finally:
            os.unlink(png_path)

    def test_create_with_text(self, qtbot):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("Hello world test content")
            txt_path = f.name

        try:
            dlg = FileViewer(txt_path)
            assert dlg.windowTitle() == os.path.basename(txt_path)
            dlg.accept()
        finally:
            os.unlink(txt_path)

    def test_create_with_unknown(self, qtbot):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"binary")
            bin_path = f.name

        try:
            dlg = FileViewer(bin_path)
            assert dlg.windowTitle() == os.path.basename(bin_path)
            dlg.accept()
        finally:
            os.unlink(bin_path)

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QTableWidget

from larccommon.widgets.table_settings import TableSettings


class TestTableSettings:
    def test_save_restore(self, qtbot):
        settings = QSettings("LarcTest", "LarcCommonTest")
        settings.clear()

        table = QTableWidget()
        table.setColumnCount(3)
        table.setRowCount(2)

        # Set some column widths
        table.setColumnWidth(0, 100)
        table.setColumnWidth(1, 200)
        table.setColumnWidth(2, 300)

        # Save
        TableSettings.save(table, "test_table")

        # Create a new table and restore
        table2 = QTableWidget()
        table2.setColumnCount(3)
        table2.setRowCount(2)
        TableSettings.restore(table2, "test_table")

        assert table2.columnWidth(0) == 100
        assert table2.columnWidth(1) == 200
        assert table2.columnWidth(2) == 300

        settings.clear()

    def test_restore_no_saved_state(self, qtbot):
        table = QTableWidget()
        table.setColumnCount(2)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 60)
        TableSettings.restore(table, "nonexistent_key")
        # Widths should remain unchanged
        assert table.columnWidth(0) == 50
        assert table.columnWidth(1) == 60

    def test_reset(self, qtbot):
        settings = QSettings("LarcTest", "LarcCommonTest")
        settings.clear()

        table = QTableWidget()
        table.setColumnCount(1)
        table.setColumnWidth(0, 42)
        TableSettings.save(table, "reset_test")
        TableSettings.reset("reset_test")

        key = settings.value("table/reset_test/columns")
        assert key is None

        settings.clear()

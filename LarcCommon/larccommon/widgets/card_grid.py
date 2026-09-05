from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt

from larccommon.theme import theme_manager
from .card import StudentCard
from .card_config import DEFAULT_CONFIG


def fill_cards_grid(layout, scroll_widget, students, event_stats, on_student_clicked, cfg=None):
    cfg = cfg or DEFAULT_CONFIG
    for i in reversed(range(layout.count())):
        w = layout.itemAt(i).widget()
        if w:
            w.deleteLater()

    avail_w = scroll_widget.viewport().width()
    card_w = cfg.card_w
    spacing = cfg.spacing
    cols = max(1, (avail_w + spacing) // (card_w + spacing)) if avail_w > 100 else 3

    import json as _json
    for idx, s in enumerate(students):
        sid = s['id']
        card = StudentCard(sid, s['last_name'], s['first_name'], cfg)
        card.set_role(StudentCard._ROLE_SECRETARY)
        # Validation D/M/P/E
        val = s.get("validation")
        if isinstance(val, str):
            val = _json.loads(val) if val else {}
        card.set_validation(val)
        stats = event_stats.get(sid, {'exit': 0, 'presence': 'Présent'})
        card.set_exit_count(stats['exit'])
        is_absent = stats['presence'] == 'Absent'
        color = theme_manager.palette.error if is_absent else theme_manager.palette.success
        card.set_status(stats['presence'], color)
        card.set_absent(is_absent)
        card.clicked.connect(on_student_clicked)
        layout.addWidget(card, idx // cols, idx % cols, Qt.AlignCenter)

    remaining = len(students) % cols
    if remaining:
        for i in range(cols - remaining):
            spacer = QWidget()
            spacer.setFixedSize(cfg.card_w, cfg.card_h)
            layout.addWidget(spacer, len(students) // cols, cols - remaining + i, Qt.AlignCenter)
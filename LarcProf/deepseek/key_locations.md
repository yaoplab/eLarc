# Key code locations for quick re-entry
# eLarcProfPy - 2 June 2026 (top bar + functional grid)

## main_window.py — Top bar + Workspace with grid

### Layout
```
root (QVBoxLayout)
├── header (QFrame)
├── top_bar (QWidget with QHBoxLayout) — always visible
│   ├── Section 1: Matiere-Classe (QFrame, fixedWidth 210)
│   │   ├── Combo + Autre combo
│   ├── Section 2: Formatives (QFrame, stretch=1)
│   │   ├── Title + "Gérer" button
│   │   ├── QScrollArea (maxHeight 160) — active slots only
│   │   │   └── Each row: F## | Label(90px) | Nature(70px) | Active crits
│   │   ├── Toggle buttons: Toute | Aucune | Commentaire
│   ├── Section 3: Sommatives (same structure)
│   └── Section 4: Jugements (QFrame, fixedWidth 170)
│       ├── 3 toggles: Jgt | Note sur 7 | Commentaire
│       ├── Separator
│       └── 4 toggles: Critère A/B/C/D
└── workspace_widget (QVBoxLayout, hidden until selection)
    ├── students_grid (stretch=1) — QTableWidget
    └── actions_bar (Synchroniser + Enregistrer et quitter)
```

### Key methods
- `_setup_ui` (line 99): layout setup
- `_build_top_bar` (line 153): creates all 4 sections
- `_build_matiere_section` (line 180): combos
- `_build_eval_section` (line 230): F or S section with scrollable active-slot list
- `_build_jugements_section` (line 317): section 4
- `_load_combined_data` (line 492): loads CTS, students, populates combos
- `_on_item_selected` (line 637): loads evals, shows workspace, fills grid
- `_fill_grille` (line 954): builds dynamic columns, loads notes via fk_student_id
- `_on_cell_changed` (line 1082): tracks dirty cells on edit
- `_save_grid_edits` (line 1096): writes dirty cells to SQLite
- `_update_icons` (line 745): builds scrollable slot rows for F/S sections
- `_on_slot_icon_clicked` (line 851): toggle slot visibility in grid
- `_on_toggle_all` / `_on_toggle_none` / `_on_toggle_comment` (lines 877-916)
- `_on_selection_changed` (line 943): saves edits + rebuilds grid + updates top bar
- `_on_sync` (line 443): saves grid edits → sync
- `_on_save_and_quit` (line 463): saves grid edits → sync → close

### State variables
- `_visible_f: set[int]` — slot indices visible in grid for Formatives
- `_visible_s: set[int]` — same for Sommatives
- `_visible_crits: dict[str, bool]` — A/B/C/D toggle state
- `_show_f_comment` / `_show_s_comment` / `_show_jgt_comment`: bool
- `_current_ts_id: int | None` — current classroom_termsubject id
- `_evals_f` / `_evals_s: list[dict]` — loaded evaluation data
- `_row_ids: dict[int, int]` — student_id → learner table row id
- `_dirty_cells: dict[tuple[int, str], str]` — (student_id, col_name) → value
- `_current_table: str` — learner table name (PEI or DP)
- `_current_student_ids: list[int]` — student ids in grid row order
- `_current_col_names: list[str]` — column display names

## sqlite_init.py — Seed data

### Key methods
- `take_teacher_data` (line 483): seeds 5 business tables + _ref pairs
- PEI query (line 539-551): `SELECT pei.*, lht.fk_student_id` from PostgreSQL
- DP query (line 556-568): `SELECT dp.*, lht.fk_student_id` from PostgreSQL

## sync.py — SyncManager (489 lines)

### Key methods
- `pull_push` (line 152): orchestrates full sync cycle
- `compute_cell_diff` (line 213): cell-level diff via shadow-table pattern
- `apply_pull` / `apply_push` / `apply_resolution` (lines 307, 334, 371)
- `touch_sync_state` (line 422): updates sync_state table

### Decision Matrix (per cell)
| local vs ref | server vs ref | Action |
|---|---|---|
| = | = | NOOP |
| = | ≠ | PULL |
| ≠ | = | PUSH |
| ≠ | ≠ | CONFLICT |

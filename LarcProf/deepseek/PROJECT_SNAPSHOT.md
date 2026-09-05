# eLarcProfPy — Project Snapshot

> Generated: 2 June 2026
> Purpose: Resume work without rescanning all files.

## TL;DR

Python/PySide6 desktop app for teachers to manage evaluations (formatives/sommatives).
Connects to PostgreSQL intranet or Supabase cloud, syncs to local SQLite (`elarc.db`).
Phase 1 (login/auth) done. Phase 2 (workspace with grid) functional.

## Architecture

```
eLarcProfPy/
├── main.py                 # QApplication + LoginWindow + CLI --mode4 / --test-create-db
├── common/
│   ├── network.py          # detect_network() → INTRANET/INTERNET/OFFLINE
│   ├── database.py         # Database class, db (global singleton)
│   ├── session.py          # UserRole, ConnMode, AuthResult, Session, session (global)
│   ├── auth.py             # AuthManager + OAuth2Manager (PKCE Google)
│   ├── sqlite_init.py      # SQLiteInit, DDL, save_session, sync cursors, _migrate_columns()
│   ├── sync.py             # SyncManager (489 lines, implemented)
│   └── logger.py           # log() → elarc.log
├── views/
│   ├── login.py            # LoginWindow — 4 tabs (Intranet, Cloud, PIN, New Instance)
│   ├── password.py         # ChangePinDialog + ChangePasswordDialog
│   ├── main_window.py      # MainWindow — top bar + grid (1215 lines)
│   ├── eval_manager.py     # _SlotBar, EvalManagerWindow
│   └── evaluation_panel.py # Obsolete (unused by main_window)
├── export_to_sqlite.py     # Export PostgreSQL → SQLite utility
├── docs/                   # Algorithmic documentation (01-20 + etat + historique)
└── deepseek/               # This file
```

## CLI Modes

| Command | Action |
|---|---|
| `python main.py` | Open login window |
| `python main.py --mode4 [email]` | Create instance from Intranet CLI (auth, init SQLite, `init_module_config`, `take_teacher_data`, save session) |
| `python main.py --test-create-db` | Create temp SQLite, verify tables |

## Current State (Phase 2 — Functional)

### Working:
- **Top bar**: 4 sections (Matière-Classe, Formatives active-only scroll, Sommatives active-only scroll, Jugements)
- **Grid**: dynamic columns from visible F/S slots + criteria + jugements
- **Grid editing**: double-click → `_on_cell_changed()`, saved via `_save_grid_edits()`
- **Data matching**: `fk_student_id` links students to note rows (via seed `take_teacher_data`)
- **Sync**: `common/sync.py` fully implemented (shadow-table diff, pull/push/conflict)
- **EvalManagerWindow**: full evaluation management with progressive slot display
- **Auto-migration**: missing columns added on SQLite init
- **Take teacher data bypass**: normal login skips seed (reserved for `--mode4`)

### Known Issue:
- Teacher 1021 (Patrice LABONNE), term 3: all 189 evaluations have `crit_a..crit_d = '0'`
- No criteria checked → no active evaluations displayed for any subject
- This is a server data issue, not a code bug

### Legacy DB issue:
- Old databases seeded before 2 June 2026 lack `fk_student_id` column in learner tables
- Grid shows message "relancez --mode4" in status bar

## Key File Locations (line numbers)

| What | File | Lines |
|---|---|---|
| take_teacher_data bypass | `views/login.py` | ~567-571 |
| _setup_ui (layout) | `views/main_window.py` | 99-123 |
| _build_top_bar | `views/main_window.py` | 153-178 |
| _build_eval_section | `views/main_window.py` | 230-315 |
| _build_jugements_section | `views/main_window.py` | 317-379 |
| _fill_grille | `views/main_window.py` | 954-1079 |
| _on_cell_changed | `views/main_window.py` | 1082-1094 |
| _save_grid_edits | `views/main_window.py` | 1096-1121 |
| fk_student_id in seed | `common/sqlite_init.py` | PEI/DP queries |
| SyncManager.pull_push | `common/sync.py` | 152-208 |
| _migrate_columns | `common/sqlite_init.py` | 365-371 |

## Next Steps
1. Grade validation (0-8 PEI / 0-20 DP)
2. Test dataset for term 3
3. Dashboard per role (PROF → COORD → SECR → ADMIN)
4. Test on real T1/T2 data

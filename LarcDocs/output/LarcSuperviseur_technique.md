# Documentation technique — Supervision des présences et événements

## Architecture

Application de supervision pour le suivi des présences, retards et événements des élèves.

LarcSuperviseur est une application PySide6 (Qt6) desktop, développée en Python. Elle utilise les widgets Material Design 3 via **phibuilder** et se connecte à PostgreSQL via **psycopg2**.

---

## Base de données

- `student_event`
- `larcauth_type_event`
- `larcauth_lieu`
- `larcauth_academicyear`

---

## Documentation de référence

*Source : AGENTS.md*

### What this is

PySide6 (Qt6) desktop apps for student attendance/event supervision + administration.
Direct psycopg2 PostgreSQL — no ORM, no REST API.
Windows-only. Bilingual UI (FR/EN via `LARC_LANG` env var).
Requires `LarcCommon` installed (`pip install -e D:\Projets\LarcCommon`).
Dépend aussi de `materialyoucolor` (moteur de couleurs M3).

### How to run

```bash
cd C:\Projets
set LARC_LANG=fr    # Français (défaut)
set LARC_LANG=en    # English
python -m LarcSuperviseur          # Supervision
python -m LarcSecretaire           # Secrétariat
python -m LarcHub                  # Hub
python -m LarcConfig               # Configuration (i18n, thèmes, rôles, logs, types, lieux)
```

### Architecture des dépôts

| Dépôt | Rôle | Entrée |
|---|---|---|
| `LarcCommon/` | Librairie partagée : `larccommon`, `phibuilder` | `pip install -e D:\Projets\LarcCommon` |
| `LarcSuperviseur/` | Supervision présence/événements | `python -m LarcSuperviseur` |
| `LarcSecretaire/` | Secrétariat (notes, dossiers, parents) | `python -m LarcSecretaire` |
| `LarcHub/` | Hub LarcAdmin (fusion Supervision + Secrétariat) | `python -m LarcHub` |
| `LarcConfig/` | Configuration (i18n, thèmes, rôles, logs, types, lieux) | `python -m La

### LarcCommon (D:\Projets\LarcCommon/)

**larccommon** :
- `larccommon/theme.py` — `ThemeManager` + 4 thèmes (blue/dark/sobre/contrast) + `phi_theme` (unifié phibuilder) + `ImageScale` (tailles standard)
- `larccommon/l10n/` — `Translator` + `fr.json`/`en.json` (~650 clés)
- `larccommon/database.py` — `db` (connexion PostgreSQL directe)
- `larccommon/network.py` — `detect_network()` → (intranet_ok, internet_ok)
- `larccommon/config_loader.py` — `find_cfg()` cherche config.ini (priorité LarcCommon/)
- `larccommon/icons.py` — Icônes Mat

### Règles de code

- **Imports UI** : TOUJOURS depuis `phibuilder.widgets`, JAMAIS de `PySide6.QtWidgets` direct
- **Exceptions** : `QMessageBox`, `QApplication`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QButtonGroup`, `QTableWidgetItem` (pas de wrapper M3)
- **Couleurs** : `theme_manager.phi_theme` pour widgets M3, `theme_manager.palette` pour QSS
- **Icônes** : `from larccommon.icons import icon as md3_icon` → `md3_icon('name', color, size=18)`
  - **INTERDIT** : images (PNG/JPG) comme icônes — toujours uti

### Design System — `larccommon/design_system.py`

**RÈGLE ABSOLUE POUR TOUTE NOUVELLE CRÉATION UI : ZÉRO HARDCODING.**

Toutes les tailles, espacements, couleurs, bordures doivent passer par le Design System :

```python
from larccommon.design_system import ds

# Espacement — jamais setSpacing(12) ou setContentsMargins(6,6,6,6)
layout.setSpacing(ds.space_sm)
layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

# Hauteurs des champs — jamais setFixedHeight(52)
field.setFixedHeight(ds.field_height)

# Bordures — jamais b

### Design System — `larccommon/design_system.py`

| Catégorie | Token | Valeur |
|---|---|---|
| Espacement | `ds.space_xs` / `ds.space_sm` / `ds.space_md` / `ds.space_xl` | 8 / 12 / 20 / 52 px |
| Champs | `ds.field_height` | 32 px |
| Boutons | `ds.button_height` / `ds.icon_lg` | 52 px |
| Bordures | `ds.radius_xs` / `ds.radius_sm` / `ds.border_width` | 4 / 8 / 1 px |
| Polices | `ds.font_title` / `ds.font_body` / `ds.font_small` | 14 / 13 / 11 px |
| Tableaux | `ds.table_row_min` / `ds.table_qss()` | 32 px |

### Design System — `larccommon/design_system.py`

- Tout champ de saisie DOIT avoir un `padding` gauche ≥ `ds.space_md` (20px) — le premier caractère ne touche jamais la bordure
- Le `_flat_field` standard complet :
  ```python
  f"background: transparent; border: 1px solid {p.outline}; "
  f"border-radius: {ds.radius_xs}px; padding: {ds.space_md}px; "
  f"color: {p.text_strong}; font-size: {ds.font_body}px;"
  ```
- **INTERDIT** d'oublier `padding` ou `color` dans un override QSS de champ

### Design System — `larccommon/design_system.py`

```python
phi = theme_manager.phi_theme
sp = phi.spacing.spacing
p = theme_manager.palette
_fh = ds.field_height   # 52 px

# Card identité
card = M3Card(theme=phi, variant=ds.CARD_ELEVATED)
cl = card.content_layout()
cl.setSpacing(ds.space_sm)

field = M3TextField(theme=phi)
field.setFixedHeight(_fh)
field.setStyleSheet(ds.flat_input_qss())

# Tableau
table = M3TableWidget(theme=phi)
table.setStyleSheet(ds.table_qss())
table.horizontalHeader().setFixedHeight(ds.space_lg)
```


---

## Dépendances

- **PySide6** >= 6.5 — Framework Qt6
- **psycopg2-binary** >= 2.9 — Driver PostgreSQL
- **materialyoucolor** >= 3.0 — Moteur de couleurs M3
- **LarcCommon** — Librairie partagée

---

## Modules

| Fichier | Rôle |
|---------|------|
| `main_window.py` | Orchestrateur principal |
| `top_bar.py` | Barre du haut (date, réseau, thème, périodes) |
| `sidebar.py` | Navigation gauche (programmes, classes) |
| `group_panel.py` | Stats groupe : KPIs, charts, historique |
| `class_panel.py` | Grille cartes élèves |
| `student_detail.py` | Détail élève : photo, infos, événements |
| `data_loader.py` | Requêtes DB (33 méthodes) |
| `event_actions.py` | CRUD événements + menu contextuel |
| `event_generator.py` | Wizard génération événement |
| `timetable_editor.py` | Éditeur emploi du temps |

---

## Analyse du code source — LarcSuperviseur

**36 fichiers** analysés.

- 16 classes
- 18 fonctions libres

### Fichiers

| Fichier | Classes | Fonctions | Doc |
|---------|---------|-----------|-----|
| `main.py` | 0 | 1 | non |
| `app_config.py` | 0 | 0 | non |
| `auth.py` | 0 | 0 | non |
| `config_loader.py` | 0 | 0 | non |
| `database.py` | 0 | 0 | non |
| `event_helpers.py` | 0 | 0 | non |
| `logger.py` | 0 | 0 | non |
| `network.py` | 0 | 0 | non |
| `photos.py` | 0 | 0 | non |
| `session.py` | 0 | 0 | non |
| `theme.py` | 0 | 0 | non |
| `trace.py` | 0 | 3 | non |
| `run_ddl.py` | 0 | 0 | non |
| `test_queries.py` | 0 | 0 | non |
| `demo_login_m3.py` | 0 | 0 | oui |
| `i18n_manager.py` | 0 | 11 | oui |
| `show_icons.py` | 0 | 1 | oui |
| `test_i18n.py` | 0 | 1 | oui |
| `login.py` | 2 | 0 | non |
| `main_window.py` | 1 | 0 | non |
| `top_bar.py` | 1 | 0 | non |
| `data_loader.py` | 1 | 0 | non |
| `event_actions.py` | 1 | 0 | non |
| `event_dialog.py` | 1 | 0 | non |
| `time_manager.py` | 1 | 0 | non |
| `avatar.py` | 0 | 0 | non |
| `card.py` | 0 | 0 | non |
| `config.py` | 0 | 0 | non |
| `grid.py` | 0 | 0 | non |
| `event_generator.py` | 1 | 0 | non |
| `preferences.py` | 1 | 1 | non |
| `timetable_editor.py` | 2 | 0 | non |
| `class_panel.py` | 1 | 0 | non |
| `group_panel.py` | 1 | 0 | non |
| `sidebar.py` | 1 | 0 | non |
| `student_detail.py` | 1 | 0 | non |

### Classes principales

#### `_Worker` (login.py)
_—_
- 2 méthodes
  - `__init__(fn, *args, parent)`
  - `run()`

#### `LoginWindow` (login.py)
_—_
- 19 méthodes
  - `_check_rate_limit(cls, key)`
  - `_record_failure(cls, key)`
  - `__init__()`
  - `_get_current_term_label()`
  - `_init_ui()`
  - `eventFilter(obj, event)`
  - `_on_force_toggle(checked)`
  - `_tab_intranet()`
  - `_tab_cloud()`
  - `_on_intranet()`
  - ... +9 méthodes

#### `MainWindow` (main_window.py)
_—_
- 35 méthodes
  - `_STYLE()`
  - `__init__()`
  - `_init_ui()`
  - `_compact_tables()`
  - `_build_student_detail()`
  - `_rebuild_student_detail_theme()`
  - `_build_sidebar()`
  - `_on_section_clicked(section)`
  - `_on_prog_clicked(prog)`
  - `_on_class_clicked(class_id, label, btn)`
  - ... +25 méthodes

#### `TopBar` (top_bar.py)
_UI bandeau 2 lignes : date/heure/terme, réseau, thème, boutons période._
- 16 méthodes
  - `__init__(on_period_click, on_theme_change, on_refresh)`
  - `_build_ui()`
  - `_start_clock()`
  - `_make_period_btn(label)`
  - `set_unit_periods(periods)`
  - `show_period_row(visible)`
  - `_update_datetime()`
  - `update_network()`
  - `_update_network_label()`
  - `set_loading(busy, msg)`
  - ... +6 méthodes

#### `DataLoader` (data_loader.py)
_All database queries in one place._
- 39 méthodes
  - `conn()`
  - `_cursor()`
  - `get_active_term()`
  - `get_term_id()`
  - `get_current_term_label()`
  - `get_unit_periods()`
  - `get_programs()`
  - `get_classes()`
  - `get_all_classrooms()`
  - `get_student_classroom(student_id)`
  - ... +29 méthodes

#### `EventActions` (event_actions.py)
_CRUD operations on student_event._
- 9 méthodes
  - `__init__()`
  - `conn()`
  - `get_event_by_id(event_id)`
  - `edit_event(event_id, data)`
  - `toggle_validation(event_id, validate)`
  - `delete_event(event_id)`
  - `get_context_menu(event_id, parent)`
  - `get_event_id_from_table(table)`
  - `get_event_id_from_row(table, row)`

#### `EventEditDialog` (event_dialog.py)
_—_
- 4 méthodes
  - `__init__(event_id, parent)`
  - `_setup_ui()`
  - `_load_event()`
  - `_save()`

#### `TimeManager` (time_manager.py)
_Centralised session time state: current date, period, unit periods, term._
- 5 méthodes
  - `__init__()`
  - `period_dates()`
  - `go_today()`
  - `select_period(key)`
  - `set_term(term_id, term_label)`

#### `EventGenerator` (event_generator.py)
_—_
- 25 méthodes
  - `__init__(student_id, parent)`
  - `_load_student_classroom()`
  - `_load_locations()`
  - `_load_types_from_db()`
  - `_init_ui()`
  - `_show_step()`
  - `_show_mode_buttons()`
  - `_show_absence_natures()`
  - `_show_retard_durations()`
  - `_show_locations()`
  - ... +15 méthodes

#### `PreferencesDialog` (preferences.py)
_—_
- 7 méthodes
  - `__init__(parent)`
  - `_make_group(label, options, get_current, set_current)`
  - `_refresh_group_styles(group)`
  - `_init_ui()`
  - `_apply()`
  - `_on_ok()`
  - `_on_cancel()`

#### `TimeSlotGrid` (timetable_editor.py)
_—_
- 5 méthodes
  - `__init__()`
  - `load(classroom_id, term_id, weekday, student_id)`
  - `set_student(student_id)`
  - `_update_student_labels()`
  - `_open_event_dialog(timetable_id, timeperiod_id, slot_label)`

#### `TimetableEditor` (timetable_editor.py)
_—_
- 5 méthodes
  - `__init__(class_id, class_label, term_id, parent)`
  - `_init_ui()`
  - `_load_data()`
  - `_build_grid()`
  - `_save()`

#### `ClassPanel` (class_panel.py)
_Student cards grid for a selected class._
- 6 méthodes
  - `__init__(parent)`
  - `_init_ui()`
  - `load(class_id, date_from, date_to)`
  - `_on_card_click(student_id)`
  - `reflow()`
  - `show_student_highlight(student_id)`

#### `GroupPanel` (group_panel.py)
_Group statistics: KPIs, charts, and event history._
- 12 méthodes
  - `__init__(parent)`
  - `_init_ui()`
  - `load(mode, date_from, date_to)`
  - `_update_everything(mode, date_from, date_to)`
  - `_load_history(date_from, date_to)`
  - `_set_loading(busy, msg)`
  - `_get_event_id_from_table(table)`
  - `_show_context_menu(table, pos)`
  - `_on_event_table_dblclick(row, col)`
  - `_edit_event(event_id)`
  - ... +2 méthodes

#### `Sidebar` (sidebar.py)
_—_
- 8 méthodes
  - `__init__(parent)`
  - `load_data()`
  - `_build_sections()`
  - `_on_section_clicked(section)`
  - `_on_prog_clicked(prog)`
  - `_on_class_clicked(class_id, label, btn)`
  - `_on_all_clicked()`
  - `_clear_selection()`

#### `StudentDetail` (student_detail.py)
_—_
- 15 méthodes
  - `__init__(parent)`
  - `_period_dates()`
  - `_init_ui()`
  - `load(student_id)`
  - `_build_donut(evts)`
  - `_build_bars(evts)`
  - `_on_add_event()`
  - `set_period_label(label)`
  - `_get_event_id_from_table(table)`
  - `_show_context_menu(table, pos)`
  - ... +5 méthodes

### Fonctions libres

- **`main()`** (main.py) — —
- **`trace(msg)`** (trace.py) — —
- **`enable()`** (trace.py) — —
- **`disable()`** (trace.py) — —
- **`load()`** (i18n_manager.py) — Charge les deux JSON.
- **`save(fr, en)`** (i18n_manager.py) — Sauvegarde les deux JSON.
- **`scan_code()`** (i18n_manager.py) — Extrait toutes les clés _('key') du code source.
- **`cmd_status()`** (i18n_manager.py) — —
- **`cmd_missing()`** (i18n_manager.py) — —
- **`cmd_unused()`** (i18n_manager.py) — —
- **`cmd_add(key, fr_val, en_val)`** (i18n_manager.py) — —
- **`cmd_search(texte)`** (i18n_manager.py) — —
- **`cmd_sync()`** (i18n_manager.py) — —
- **`cmd_export()`** (i18n_manager.py) — —
- **`help()`** (i18n_manager.py) — —
- **`main()`** (show_icons.py) — —
- **`main()`** (test_i18n.py) — —
- **`_btn_style(selected)`** (preferences.py) — —

### Dépendances (imports)

**Internes** : `LarcSuperviseur.common.app_config.app_config`, `LarcSuperviseur.common.auth.OAuth2Manager`, `LarcSuperviseur.common.database.db`, `LarcSuperviseur.common.event_helpers.event_color`, `LarcSuperviseur.common.event_helpers.event_icon`, `LarcSuperviseur.common.logger.log`, `LarcSuperviseur.common.network.detect_network`, `LarcSuperviseur.common.photos.PhotoPreloader`, `LarcSuperviseur.common.photos.get_photo_path`, `LarcSuperviseur.common.photos.get_uncached_ids`, `LarcSuperviseur.common.session.ConnMode`, `LarcSuperviseur.common.session.UserRole`, `LarcSuperviseur.common.session.session`, `LarcSuperviseur.common.theme.QssHelper`, `LarcSuperviseur.common.theme.theme_manager`, `LarcSuperviseur.common.trace.trace`, `LarcSuperviseur.views.core.cardsList.DEFAULT_CONFIG`, `LarcSuperviseur.views.core.cardsList.StudentCard`, `LarcSuperviseur.views.core.cardsList.card.StudentCard`, `LarcSuperviseur.views.core.cardsList.config.CARD_THEMES`, `LarcSuperviseur.views.core.cardsList.grid.fill_cards_grid`, `LarcSuperviseur.views.core.data_loader.DataLoader`, `LarcSuperviseur.views.core.event_actions.EventActions`, `LarcSuperviseur.views.core.event_dialog.EventEditDialog`, `LarcSuperviseur.views.core.time_manager.TimeManager`, `LarcSuperviseur.views.dialogs.event_generator.EventGenerator`, `LarcSuperviseur.views.dialogs.timetable_editor.TimetableEditor`, `LarcSuperviseur.views.login.LoginWindow`, `LarcSuperviseur.views.main_window.MainWindow`, `LarcSuperviseur.views.panels.student_detail.StudentDetail`

**Externes** : `PySide6.QtCharts.QBarCategoryAxis`, `PySide6.QtCharts.QBarSeries`, `PySide6.QtCharts.QBarSet`, `PySide6.QtCharts.QChart`, `PySide6.QtCharts.QChartView`, `PySide6.QtCharts.QDateTimeAxis`, `PySide6.QtCharts.QLineSeries`, `PySide6.QtCharts.QPieSeries`, `PySide6.QtCharts.QValueAxis`, `PySide6.QtCore.QCoreApplication`, `PySide6.QtCore.QDate`, `PySide6.QtCore.QDateTime`, `PySide6.QtCore.QEvent`, `PySide6.QtCore.QSize`, `PySide6.QtCore.QThread`, `PySide6.QtCore.QTime`, `PySide6.QtCore.QTimer`, `PySide6.QtCore.Qt`, `PySide6.QtCore.Signal`, `PySide6.QtGui.QBrush`, `PySide6.QtGui.QColor`, `PySide6.QtGui.QFont`, `PySide6.QtGui.QIcon`, `PySide6.QtGui.QPainter`, `PySide6.QtGui.QPixmap`, `PySide6.QtWidgets.QApplication`, `PySide6.QtWidgets.QButtonGroup`, `PySide6.QtWidgets.QCheckBox`, `PySide6.QtWidgets.QDateEdit`, `PySide6.QtWidgets.QDialog`, `PySide6.QtWidgets.QFrame`, `PySide6.QtWidgets.QGridLayout`, `PySide6.QtWidgets.QHBoxLayout`, `PySide6.QtWidgets.QLabel`, `PySide6.QtWidgets.QMessageBox`, `PySide6.QtWidgets.QProgressDialog`, `PySide6.QtWidgets.QPushButton`, `PySide6.QtWidgets.QScrollArea`, `PySide6.QtWidgets.QTableWidget`, `PySide6.QtWidgets.QTableWidgetItem`, `PySide6.QtWidgets.QTimeEdit`, `PySide6.QtWidgets.QVBoxLayout`, `PySide6.QtWidgets.QWidget`, `collections.defaultdict`, `csv`, `datetime.datetime`, `hashlib`, `json`, `os`, `pathlib.Path`, `re`, `sys`, `time`, `typing.Optional`

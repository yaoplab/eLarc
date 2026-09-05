# Manuel utilisateur — Supervision des présences et événements

## Présentation

Application de supervision pour le suivi des présences, retards et événements des élèves.

---

## Fonctionnalités

- Suivi des absences et retards en temps réel
- Génération d'événements (absence journée, retard, événements)
- Statistiques par groupe, classe et élève
- Tableau de bord avec KPIs et graphiques
- Gestion des photos élèves
- Éditeur d'emploi du temps


---

## Rôles utilisateurs

- **Superviseur (écriture)**
- **Coordinateur (valider)**
- **Administrateur (complet)**


---

## Résumé depuis AGENTS.md

### Sections principales

- **What this is**
- **How to run**
- **Architecture des dépôts**
- **LarcCommon (D:\Projets\LarcCommon/)**
- **Règles de code**
- **Design System — `larccommon/design_system.py` > Tokens rapides**
- **Design System — `larccommon/design_system.py` > Contrainte stricte padding champs**
- **Design System — `larccommon/design_system.py` > Pattern standard pour un formulaire**
- **Design System — `larccommon/design_system.py`**
- **Audit padding/margin (10/07/2026) > Règle absolue**
- **Audit padding/margin (10/07/2026) > Tokens disponibles (`larccommon/design_system._DesignSystem` → singleton `ds`)**
- **Audit padding/margin (10/07/2026) > Résultat par projet**
- **Audit padding/margin (10/07/2026) > Priorité**
- **Audit padding/margin (10/07/2026) > Fichier de référence**
- **Audit padding/margin (10/07/2026)**
- **LarcSuperviseur — Architecture**
- **EventGenerator (réécrit 07/07)**
- **LarcCommon/theme.py — Unification palettes**
- **Icônes MD3 (larccommon/icons.py)**
- **DB**
- **User roles**
- **Tracing**
- **Internationalisation (i18n)**
- **DB notes**
- **État actuel (07/07/2026)**
- **Commandes utiles**
- **eLarcProfPy — Architecture (09/07/2026) > HomeWindow — Dashboard**
- **eLarcProfPy — Architecture (09/07/2026) > Mapping boutons → vues cibles**
- **eLarcProfPy — Architecture (09/07/2026) > Login — 4 onglets + i18n**
- **eLarcProfPy — Architecture (09/07/2026) > phi_theme dans eLarcProfPy**
- **eLarcProfPy — Architecture (09/07/2026) > i18n eLarcProfPy**
- **eLarcProfPy — Architecture (09/07/2026)**
- **Mise à jour 10/07/2026**
- **Mise à jour 09/07/2026**
- **Mise a jour 08/07/2026**
- **Mise a jour 08/07/2026 (soir)**
- **Mise à jour 10/07/2026**

### Structure des fichiers (extrait)

| Dépôt | Rôle | Entrée |
| `LarcCommon/` | Librairie partagée : `larccommon`, `phibuilder` | `pip install -e D:\Projets\LarcCommon` |
| `LarcSuperviseur/` | Supervision présence/événements | `python -m LarcSuperviseur` |
| `LarcSecretaire/` | Secrétariat (notes, dossiers, parents) | `python -m LarcSecretaire` |
| `LarcHub/` | Hub LarcAdmin (fusion Supervision + Secrétariat) | `python -m LarcHub` |
| `LarcConfig/` | Configuration (i18n, thèmes, rôles, logs, types, lieux) | `python -m LarcConfig` |
| `eLarcProfPy/` | Professeurs (SQLite locale, séparé) | — |
| Catégorie | Token | Valeur |
| Espacement | `ds.space_xs` / `ds.space_sm` / `ds.space_md` / `ds.space_xl` | 8 / 12 / 20 / 52 px |
| Champs | `ds.field_height` | 32 px |
| Boutons | `ds.button_height` / `ds.icon_lg` | 52 px |
| Bordures | `ds.radius_xs` / `ds.radius_sm` / `ds.border_width` | 4 / 8 / 1 px |
| Polices | `ds.font_title` / `ds.font_body` / `ds.font_small` | 14 / 13 / 11 px |
| Tableaux | `ds.table_row_min` / `ds.table_qss()` | 32 px |
| Projet | padding: QSS | setContentsMargins | setSpacing | setFixedWidth |
| LarcSecretaire (focus) | 51 (dont 11 hard) | 28 (dont 10 hard) | 78 (dont 18 hard) | 0 hard |
| LarcProf | 60 (dont 57 hard) | 38 (dont 30 hard) | 47 (dont 43 hard) | 4 hard |
| LarcSuperviseur | 5 (tous hard) | 24 (dont 18 hard) | 40 (dont 25 hard) | 1 hard (sidebar 233px) |
| LarcHub | 5 (tous hard) | 4 (tous hard) | 7 (tous hard) | 0 hard |
| LarcConfig | 0 hard | 9 (dont 1 hard) | 12 (dont 3 hard) | 1 hard (sidebar 233px) |
| Fichier | Rôle | Lignes |
| `main.py` | Point d'entrée | 38 |
| `views/main_window.py` | Orchestrateur principal | ~1725 |
| `views/top_bar.py` | Barre du haut (date, réseau, thème, périodes) | ~280 |
| `views/panels/sidebar.py` | Navigation gauche (programmes, classes) | ~160 |
| `views/panels/group_panel.py` | Stats groupe : KPIs, charts, historique | ~500 |
| `views/panels/class_panel.py` | Grille cartes élèves | 90 |
| `views/panels/student_detail.py` | Détail élève : photo, infos, événements | ~400 |
| `views/core/data_loader.py` | Toutes les requêtes DB (33 méthodes) | 759 |
| `views/core/event_actions.py` | CRUD événements + menu contextuel | 130 |
| `views/core/event_dialog.py` | Dialogue édition événement | 87 |
| `views/dialogs/event_generator.py` | Wizard génération événement | ~480 |
| `views/dialogs/timetable_editor.py` | Éditeur emploi du temps | 209 |
| Fichier | Rôle | Lignes |
| `main.py` | Point d'entrée + modes CLI (`--mode4`, `--test-create-db`) | 137 |
| `views/login.py` | Login 4 onglets (Intranet/Cloud/PIN/Nouvelle instance) + i18n | ~1180 |
| `views/home_window.py` | Dashboard intermédiaire : profil, synchro, boutons PEI/DP | ~650 |
| `views/main_window.py` | Espace de travail : top bar + grille élèves × notes | ~1438 |
| `views/eval_manager.py` | Gestionnaire d'évaluations (non-modal) | 431 |
| `views/password.py` | ChangePinDialog + ChangePasswordDialog | — |
| `common/theme.py` | ThemeManager local + `phi_theme` (Theme phibuilder unifié) | ~370 |
| `common/database.py` | Database (PostgreSQL Intranet/Cloud + SQLite) | 203 |
| `common/session.py` | UserRole, ConnMode, AuthResult, Session | 82 |
| `common/sync.py` | SyncManager (shadow-table _ref, diff cellule, pull/push) | 489 |
| `common/sqlite_init.py` | SQLiteInit (DDL, seed, take_teacher_data, migrations) | 793 |
| `common/auth.py` | AuthManager (Intranet) + OAuth2Manager (Google PKCE) | — |
| `common/network.py` | detect_network() shim → larccommon | — |

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
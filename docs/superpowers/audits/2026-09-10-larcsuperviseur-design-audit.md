# Audit design graphique — LarcSuperviseur

Date : 2026-09-10
Périmètre : design graphique uniquement (tokens, couleurs, spacing, MD3, thème, focus/hover). Pas de logique métier/fonctionnelle, sauf observations explicitement séparées pour le générateur d'événements.
Méthode : 5 agents en lecture seule (aucune modification), un par écran, appliquant la checklist `design-review` (linters + skills `.claude/skills/*.md`) + inspection manuelle sémantique (composition, focus/hover, cohérence thème).

## Tableau macro

| Écran | Fichiers | PB total | P0 | P1 | P2 |
|---|---|---|---|---|---|
| Login | views/login.py | ✅ déjà corrigé (bordure focus textfield.py) | – | – | – |
| Dashboard initial | main_window.py, top_bar.py, main_group.py | 22 | 4 | 9 | 9 |
| Vignettes élèves + détail | main_students.py, panels/class_panel.py, core/cardsList/*, panels/student_detail.py | 16 | 2 | 8 | 6 |
| Générateur d'événements | main_events.py, core/event_actions.py, core/event_dialog.py, panels/event_types_panel.py | 24 | 10 | 10 | 4 |
| Éditeur emploi du temps | dialogs/timetable_editor.py | 9 | 3 | 4 | 2 |
| Préférences | dialogs/preferences.py | 8 | 2 | 3 | 3 |
| **Total** | | **79** | **21** | **34** | **24** |

## 5 causes racines transverses

1. **Widgets `phibuilder` instanciés sans `theme=`** — `_update_style()` émet un `warnings.warn` puis `return` sans rien styliser. Rendu OS natif silencieux. Concentré sur le générateur d'événements et l'éditeur d'emploi du temps (M3Label, M3TextEdit, M3Button, M3ComboBox, M3Menu, M3Dialog, M3TableWidget).
2. **Implémentations dupliquées, une morte une vivante, du même écran** — `ClassPanel` (correct, reflow) jamais instancié vs `main_students.py` (vivant, sans reflow) ; `EventEditDialog`/M3Dialog vs `main_events._edit_event`/QDialog brut ; `LarcSuperviseur/dialogs/preferences.py` (mort) vs `larccommon/preferences_dialog.py` (réellement ouvert par top_bar.py).
3. **Réactivité thème incomplète** — TopBar, TimetableEditor, PreferencesDialog, EventEditDialog, EventTypeEditDialog sans `_restyle_all` connecté à `ds.theme_changed`. Bug runtime critique : `main_window.py:748-766` (`_on_theme_selected`) référence `p.surface`/`p.background` sans `p = theme_manager.palette` → NameError avalé par `@safe_slot`, le dashboard ne se repeint jamais après changement de thème depuis la top bar.
4. **États `:focus`/`:pressed` manquants** sur boutons/champs stylés à la main — même famille que le bug `textfield.py` déjà corrigé.
5. **Tokens hors de leur catégorie sémantique** ou recalculés par arithmétique pour retomber sur un pixel précis — invisible aux linters, dérive lente du design system.

---

## Rapport détaillé : Dashboard initial (main_window.py / top_bar.py / main_group.py)

### Violations

| Fichier | Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|---|
| main_window.py | 748–766 (`_on_theme_selected`) | Bug runtime / theme-reactivity | `p.surface`/`p.background` utilisés sans `p = theme_manager.palette` en scope → NameError garanti, avalé par `@safe_slot`. `refresh_all()` jamais atteint. | P0 | Ajouter `p = theme_manager.palette` en tête de méthode. |
| main_window.py | 738–745 (`_restyle`) | theme-reactivity / composition | Oublie `_cards_scroll.viewport()` et `_group_scroll.viewport()` ; n'appelle pas `refresh_all()`. | P1 | Unifier `_restyle`/`_on_theme_selected` en une méthode qui met à jour tous les viewports + refresh_all(). |
| main_window.py | 855 (`refresh_all`) | pyside6-wrapper | Connecté comme slot Qt sans `@safe_slot`. | P1 | Ajouter `@safe_slot("MainWindow.refresh_all")`. |
| main_window.py | 313, 318, 333, 346 | zero-hardcoding (esprit) | Dimensions dérivées par arithmétique de `ds.window_width/height` au lieu de `ds.space_*`. | P1 | Remplacer par tokens `ds.space_*` ou token dédié. |
| main_window.py | 242–266 | dashboard-pattern | Ordre `addWidget(val); addWidget(lbl)` inversé vs skill (label au-dessus). | P2 | Vérifier intention, sinon inverser l'ordre. |
| main_window.py | 334–338 | composition-principles | `_absents_group` en `Qt.AlignTop` peut laisser un vide vertical sous 320px. | P2 | Vérifier visuellement, contraindre l'étirement si besoin. |
| top_bar.py | 177 | zero-hardcoding | `addSpacing(13)` en dur. | P0 | Remplacer par token `ds.*`. |
| top_bar.py | 178–189 | Bug QSS (famille textfield.py) | `_refresh_btn` sans `setObjectName("refresh_btn")` → sélecteur QSS `#refresh_btn{padding:0}` ne matche jamais → icône potentiellement écrasée dans une boîte 32×32. | P0 | Ajouter `setObjectName("refresh_btn")`. |
| top_bar.py | 109–140 | Dead QSS | `_profile_btn` sans `setObjectName("profile_btn")` — sélecteur mort (sans impact visuel actuel). | P2 | Poser l'objectName ou retirer la référence morte. |
| top_bar.py | 21 | pyside6-wrapper | `TopBar(QFrame)` — héritage Qt brut hors exceptions autorisées. | P1 | Hériter de `M3Frame` ou `QWidget` + `WA_StyledBackground`. |
| top_bar.py | 193 | pyside6-wrapper / lint_widget_purity | `QFrame()` brut. | P1 | Remplacer par `M3Frame()`. |
| top_bar.py | classe entière | theme-reactivity | 13 `setStyleSheet` palette-dépendants, jamais auto-connecté à `theme_changed` (fonctionne seulement car MainWindow appelle `restyle()` manuellement). | P1 | `ds.theme_changed.connect(self.restyle)` dans `__init__`. |
| top_bar.py | 122–139 | theme-reactivity | Icônes du menu profil colorées une fois à la construction, jamais régénérées par `restyle()`. | P1 | Recolorer les icônes dans `restyle()`. |
| top_bar.py | 99 | color-rules (D3) | `"#1565C0"` hex en dur en fallback. | P2 | Utiliser un token de repli `ds.p.primary`. |
| top_bar.py | 54 | design-tokens | `setSpacing(d.radius_lg)` — token de rayon utilisé comme spacing. | P2 | Utiliser `ds.space_*`. |
| top_bar.py | 42–47 | zero-hardcoding (esprit) | Marges dérivées par arithmétique (10px/6px) hors échelle Fibonacci. | P2 | Utiliser token direct proche. |
| top_bar.py | 267 | ui-quality V1 | `"⟳ " + msg` — unicode brut au lieu de `md3_icon`. | P2 | Remplacer par icône ou spinner dédié. |
| top_bar.py (QssHelper period_btn/phi_btn/class_btn) | — | Focus (famille textfield.py) | Seuls `:hover`/`:checked` définis, jamais `:focus` — anneau de focus M3Button potentiellement perdu. | P2 | Ajouter `:focus` explicite dans le QSS. |
| main_group.py | 526 | color-rules (D3, non détecté par le linter) | `QColor("#2e7d32")` hex en dur pour la colonne « validé », alors que le reste utilise `p.success`. | P1 | Remplacer par `theme_manager.palette.success`. |
| main_group.py | 527 | zero-hardcoding | `QFont("Segoe UI", 10, QFont.Bold)` — police/taille en dur. | P2 | Utiliser `theme_manager.font_size(...)`. |

### Conforme
- Couleurs de charts (main_group.py) systématiquement via `theme_manager.palette.*`, sauf l'exception L526.
- Slots Qt majoritairement `@safe_slot`.
- Widgets phibuilder utilisés de façon quasi systématique (2 exceptions QFrame relevées).
- `theme_btn` est le seul bouton top_bar correctement câblé objectName ↔ QSS.
- `lint_palette_contrast.py` : 0 écart.

---

## Rapport détaillé : Vignettes élèves + détail (main_students.py / class_panel.py / cardsList/* / student_detail.py)

### Violations

| Fichier | Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|---|
| main_students.py | 190-213 (+ main_window.py:873-875) | card-grid-pattern CG12 | `cols` calculé une seule fois ; `resizeEvent` est un no-op — la grille ne se recalcule jamais au redimensionnement. | P0 | Brancher un vrai reflow depuis `resizeEvent` (algorithme déjà écrit dans `ClassPanel.reflow()`). |
| class_panel.py (entier) vs main_students.py | — | Duplication | `ClassPanel`/`fill_cards_grid` corrects mais jamais instanciés ; l'écran réel reconstruit sa grille à la main dans `main_students.py`, sans reflow. | P1 | Choisir une seule source de vérité (déléguer à ClassPanel ou supprimer le doublon). |
| class_panel.py | 39-44 | design-tokens | `ds.font_label_lg` utilisé comme marge de grille. | P1 | Remplacer par un vrai token d'espacement. |
| main_students.py | 111, 181-215 | card-grid-pattern CG4 | Classe vide → grille simplement vide, pas de message "Aucun élève". | P1 | Ajouter un état vide explicite. |
| student_detail.py | 152-165 vs 107-114 | theme-reactivity | `_sd_name_lbl`/`_sd_class_lbl`/`_sd_id_lbl` stylés une fois en QLabel brut, jamais repris par `_restyle_all()`. | P0 | Déplacer leur style dans `_STYLE`/`_restyle_all`, ou migrer vers `M3Label` + `.set_color()`. |
| student_detail.py | imports 27-34, usages multiples | pyside6-wrapper (W1, baseline connue) | QFrame/QLabel/QPushButton bruts pour photo/identité/cadres KPI/bouton +. | P1 | Migrer vers M3Card/M3Frame/M3Label/M3Button avec `theme=`. |
| student_detail.py | 204 | ui-quality V1 | Bouton "+" en texte brut au lieu d'icône `md3_icon`. | P2 | Utiliser M3Button + icône `add`. |
| student_detail.py | 79,82,87,93,103,154 | zero-hardcoding | Tailles de police en littéral (`s(24)`, `s(11)`...) alors que L159/164 montrent le bon pattern `s(ds.font_*)`. | P1 | Remplacer par tokens `ds.font_*`. |
| student_detail.py | 175, 192 | zero-hardcoding | `setContentsMargins(..., 2, ..., 2)` — littéral 2 non toléré. | P1 | Remplacer par token adapté. |
| student_detail.py | 96 | zero-hardcoding | Padding recalculé par arithmétique sur tokens pour viser 1px/6px. | P2 | Choisir un padding directement sur l'échelle de tokens. |
| student_detail.py | 224-225 (baseline connue) | design-tokens | `setDefaultSectionSize(22)`/`setMinimumSectionSize(18)` proches mais différents de `ds.table_row_min` (21). | P1 | Utiliser `ds.table_row_min`. |
| student_detail.py | 473-479 vs main_window.py:839-846 | Bug navigation | `set_period_label()` déclenche placeholder + `back_requested` avant `load()` — signal parasite masqué par l'ordre d'appel actuel, fragile. | P1 | Séparer mise à jour du libellé et réinitialisation complète. |
| student_detail.py | 84-91 | m3-elevation (focus) | Bouton "+" : seul `:hover` défini, pas de `:pressed`/focus visible. | P2 | Ajouter états, ou migrer vers M3Button natif. |
| main_students.py | 74 | m3-elevation | Titre via HTML inline coloré au lieu de `M3Label` + `.set_color()`. | P2 | Utiliser l'API M3Label. |
| main_students.py | 74 | card-grid-pattern CG1 | Pas de compteur d'élèves dans le titre. | P2 | Ajouter le nombre d'élèves. |
| main_students.py | imports 9-64 | hygiène | ~45 imports inutilisés (dont QDialog/QTableWidget hors exceptions autorisées, à l'état mort). | P2 | Nettoyer les imports. |

### Note hors tableau
`core/cardsList/{card,avatar,grid,config}.py` sont de simples ré-exports vers `LarcCommon/larccommon/widgets/*` (hors périmètre). À signaler pour un futur audit LarcCommon : `StudentCard` hérite de QFrame brut, seul `:hover` défini (pas de focus clavier).

### Conforme
- 0 violation `lint_d1_color_checker` sur tout LarcSuperviseur.
- `StudentDetail`/`MainWindow` marqués "Protégé" par `audit_theme_reactive.py` au niveau classe.
- Split événements/graphiques ≈ 62/38, conforme au ratio doré recommandé.
- Table événements bien stylée (M3TableWidget, colonne ID masquée, dernière colonne étirée).

---

## Rapport détaillé : Générateur d'événements (main_events.py / event_actions.py / event_dialog.py / event_types_panel.py)

### Violations design

| Fichier | Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|---|
| main_events.py | 161, 180 | m3-elevation | `M3Label` sans `theme=` → illisible en thème sombre. | P0 | Passer `theme=theme_manager.phi_theme`. |
| main_events.py | 181 | m3-elevation | `M3TextEdit` (note_input) sans `theme=`. | P0 | Idem. |
| main_events.py | 230 | m3-elevation / form-pattern | `cancel_btn` sans `theme=`, non stylé, à côté d'un bouton Enregistrer stylé manuellement. | P0 | Passer `theme=` + `variant=OUTLINED`. |
| main_events.py | 266 | m3-elevation (API) | `M3Menu(self)` — `self` reçu comme `title` au lieu de `parent`. | P0 | `M3Menu(theme=..., parent=self)`. |
| event_dialog.py | 35, 47 | m3-elevation | `M3Label` sans `theme=`. | P0 | Idem. |
| event_dialog.py | 48 | m3-elevation | `M3TextEdit` sans `theme=`. | P0 | Idem. |
| event_dialog.py | 67 | m3-elevation | `cancel_btn` sans `theme=`. | P0 | Idem + `variant=OUTLINED`. |
| event_types_panel.py | 57,65,74,82,145 | m3-elevation | Tous les `M3Label` (dont le titre d'écran) sans `theme=`. | P0 | Passer `theme=` partout. |
| event_types_panel.py | 75, 83 | m3-elevation | `M3ComboBox` sans `theme=`, rendu natif OS à côté de champs bien stylés. | P0 | Passer `theme=`. |
| event_types_panel.py | 149-154 | m3-elevation | 6 boutons de la barre d'action sans `theme=` → toute la barre en rendu OS natif. | P0 | Passer `theme=` sur les 6 boutons. |
| main_events.py | 203-208 | theme-reactivity / design-tokens | `save_btn` stylé en dur avec token legacy `theme_manager.design.radius` différent de `ds.radius_*`. | P1 | Utiliser `variant=FILLED` sans style manuel. |
| main_events.py | 155 | pyside6-wrapper (W1 baseline) | `QDialog(self)` brut alors qu'une version M3Dialog équivalente existe (`EventEditDialog`). | P1 | Réutiliser `EventEditDialog`. |
| main_events.py | 158 | zero-hardcoding | `QVBoxLayout(dlg)` sans spacing/margins `ds.*`. | P1 | Ajouter `setSpacing`/`setContentsMargins` via `ds.*`. |
| event_actions.py | 122-143 | zero-hardcoding / import | `ds.icon_sm` référencé mais `ds` jamais importé → NameError si appelé (code mort/divergent confirmé par le changelog projet). | P1 | Importer `ds` ou supprimer la méthode. |
| event_actions.py | 125 | m3-elevation (API) | `M3Menu(parent)` — même bug d'argument positionnel que main_events.py:266. | P1 | `M3Menu(theme=..., parent=parent)`. |
| event_dialog.py | 19 (classe) | theme-reactivity | Pas de `_restyle`/`theme_changed`. | P1 | Ajouter le pattern `_restyle_all`. |
| event_dialog.py | 60-65 | theme-reactivity / design-tokens | `border-radius: ds.radius_sm` (8px) différent du bouton équivalent de main_events.py (4px) — même composant, rendu différent selon le point d'entrée. | P1 | Unifier (idéalement supprimer le doublon). |
| event_dialog.py | 31 | zero-hardcoding | `QVBoxLayout(self)` sans marges `ds.*`. | P1 | Ajouter spacing/margins. |
| event_types_panel.py | 32, 97 (classe) | theme-reactivity | Pas de `_restyle`/`theme_changed` ; `setStyleSheet` posé une fois. | P1 | Ajouter le pattern `_restyle_all`. |
| event_types_panel.py | 299 | pyside6-wrapper (W1) + ui-quality | `QMenu(self)` brut sans icônes, contrairement au menu équivalent de main_events.py. | P1 | Remplacer par `M3Menu` + icônes. |
| main_events.py | 163 | design-tokens | `theme_manager.font_size(10)` — taille magique hors échelle. | P2 | Utiliser `ds.font_small`. |
| main_events.py | imports | hygiène | Nombreux imports inutilisés, dont classes Qt non autorisées à l'état mort. | P2 | Nettoyer. |
| event_dialog.py | 49, 99/102 | design-tokens | Hauteur de note calculée différemment de main_events.py pour un rendu visuellement proche mais non identique. | P2 | Extraire une constante unique partagée. |
| event_types_panel.py | 58,66,162 | m3-elevation (masqué) | `M3TextField`/`M3TableWidget` sans `theme=` mais compensés par un style de secours — warning inutile. | P2 | Passer `theme=` quand même. |

### Conforme
- 0 hex/couleur en dur sur les 5 fichiers.
- `EventTypeEditDialog` : champs bien stylés (`ds.flat_input_qss()`, `ds.field_height`).
- `EventTypesPanel` : table stylée, lignes verrouillées grisées avec tooltip.
- `main_events._show_event_context_menu` : icônes cohérentes par action.
- `theme_manager.palette` utilisé partout (jamais `ds.p` directement).
- `ds.golden_width(500)` bien utilisé pour `EventTypeEditDialog`.
- `@safe_slot` présent sur tous les slots identifiés.

### Observations UX/flux (hors périmètre design, transmises pour information — l'auteur corrige lui-même la logique du wizard)
- Deux implémentations parallèles de "éditer un événement" (`main_events._edit_event` en QDialog brut vs `EventEditDialog` en M3Dialog) avec rendu différent selon le point d'entrée.
- `EventActions.get_context_menu` est du code mort/divergent, déjà documenté dans le changelog projet (`docs/debug/CR-2026-08-14.md`).
- Le même changelog documente une triplication de la logique `toggle_validation` (TOCTOU) — action exposée dans le menu contextuel de cet écran.
- `EventTypeEditDialog._scope` : libellés "École"/"Cours" non traduits (`_()`) contrairement au reste du dialogue.
- Changer de catégorie non-feuille efface silencieusement la note déjà saisie, sans confirmation.

---

## Rapport détaillé : Éditeur d'emploi du temps (timetable_editor.py)

### Violations

| Fichier | Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|---|
| timetable_editor.py | 22, 32 | m3-elevation / theme-reactivity | `M3Dialog` sans `theme=` → fenêtre entière garde le chrome OS brut. | P0 | Passer `theme=theme_manager.phi_theme` à `super().__init__`. |
| timetable_editor.py | 47 | m3-elevation | `M3TableWidget()` sans `theme=` → grille horaire (contenu principal) sans aucun style. | P0 | Passer `theme=`. |
| timetable_editor.py | 120 | m3-elevation | `M3ComboBox()` sans `theme=` dans la boucle `_build_grid` (jusqu'à 25 combos). | P0 | Passer `theme=` à chaque combo. |
| timetable_editor.py | 55-62 | pyside6-wrapper / color-rules | `save_btn` sans `theme=`, QSS local incomplet (manque `:focus`/`:pressed`/`:disabled`). | P1 | Utiliser `theme=` + `variant=FILLED` ou compléter le QSS local. |
| timetable_editor.py | 22 (classe) | theme-reactivity | Pas de `_restyle`/`theme_changed`. | P1 | Ajouter le pattern `_restyle_all`. |
| timetable_editor.py | 37 | ui-quality | `setMinimumSize` = 800×500, sous le minimum documenté 987×610 ; risque de clipping des colonnes (780px de colonnes fixes). | P1 | Mesurer la taille réelle nécessaire et fixer ≥ 987×610. |
| timetable_editor.py | 134, 136 | zero-hardcoding | `setColumnWidth(0,80)`/`setColumnWidth(c,140)` en dur, redondant avec `resizeColumnsToContents()` juste au-dessus. | P2 | Remplacer par tokens ou supprimer l'appel mort. |
| timetable_editor.py | 91-136 | composition-principles | Grille vide (0 créneau) sans message explicite. | P2 | Ajouter un état vide. |

### Conforme
- Imports Qt limités aux exceptions autorisées.
- `_save` correctement `@safe_slot`.
- `horizontalHeader().setStretchLastSection(True)`.
- Gestion d'erreur de `_load_data` conforme au pattern attendu.
- Reste du QSS du bouton passe par les tokens `ds.*`.
- Aucune violation automatique des 7 linters sur ce fichier.

---

## Rapport détaillé : Préférences (dialogs/preferences.py)

**Constat préalable** : `LarcSuperviseur/views/dialogs/preferences.py` est une réimplémentation complète, **jamais utilisée en production** — `top_bar.py:295-303` ouvre `larccommon.preferences_dialog.PreferencesDialog`. Code mort référencé seulement par son propre test.

### Violations

| Fichier | Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|---|
| dialogs/preferences.py | fichier entier | Architecture / Duplication | Réimplémentation intégrale jamais appelée en production. | P0 | Supprimer le doublon (et son export), rebrancher le test sur la version partagée. |
| dialogs/preferences.py | 132-134 | form-pattern / input-ergonomics | `cancel_btn` sans style explicite → apparaît quasi identique au bouton OK (rempli couleur primaire). | P0 | Styler explicitement en outlined/text. |
| dialogs/preferences.py | 35-189 (classe) | theme-reactivity | Pas de `_restyle_all`/`theme_changed`. | P1 | Ajouter le pattern. |
| dialogs/preferences.py | 48,57,69,124,132 | form-pattern / pyside6-wrapper | `M3Frame`/`M3Label`/`M3Button` sans `theme=`, compensés par QSS manuel dupliquant le moteur M3 + warning à chaque ouverture. | P1 | Passer `theme=` et utiliser `variant=`/`accent_color=`/`set_color()`. |
| dialogs/preferences.py | 19-32 (`_btn_style`) | Focus (famille textfield.py) | Pas d'état `:focus` défini pour les boutons segmentés. | P1 | Ajouter `QPushButton:focus`. |
| dialogs/preferences.py | 90-95 | design-tokens | `ds.font_label_lg` (typo) utilisé comme marge. | P2 | Remplacer par `ds.space_sm`/`ds.space_md`. |
| dialogs/preferences.py | 39 | composition-principles | `setFixedSize` par formule de fractions arbitraire plutôt que mesurée. | P2 | Mesurer `sizeHint()` réel avant de figer. |
| dialogs/preferences.py | 64 | hygiène | Commentaire résiduel confus sur une règle déjà respectée. | P2 | Nettoyer le commentaire. |

### Conforme
- 0 violation des 7 linters (couleurs/dimensions).
- Imports conformes à la règle absolue.
- `@safe_slot` présent sur les 2 slots.
- Pas de champ de saisie dans cet écran (contrainte padding non applicable).

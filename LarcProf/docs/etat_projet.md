# État du Projet — LarcProf (ex-eLarcProfPy)

_Audit du 9 juillet 2026_

## 1. Verdict Global

Phase 2 opérationnelle : top bar refactorée avec slots actifs uniquement, grille élèves × notes avec données réelles, édition par double-clic et sauvegarde en SQLite. SyncManager implémenté et branché. Daemon LarcCloudSync créé (Intranet ↔ Cloud).

**Nouveau (09/07)** : Dashboard intermédiaire (HomeWindow) entre login et notes, login reconstruit avec QSS classes + Fibonacci + i18n, visibilité conditionnelle des boutons PEI/DP.

## 2. Phase 1 — Connexion (✅ TERMINÉE)

- ✅ 4 onglets : Intranet (SHA-256), Cloud (OAuth2 PKCE), PIN (hors ligne), Nouvelle instance
- ✅ Changement mot de passe / PIN via `views/password.py`
- ✅ Login reconstruit : QSS classes, Fibonacci, i18n via `_()`, ratio φ (480×780)
- ✅ Base unique `elarc.db` avec DDL complet + migration automatique

## 3. Phase 2 — Workspace (✅ FONCTIONNEL)

### HomeWindow — Dashboard (nouveau 09/07)
- ✅ Écran intermédiaire login → notes
- ✅ Profil prof + indicateurs connexion (Intranet/Cloud ●/○)
- ✅ Stats synchro : date, source, compteur modifs non sync par table
- ✅ Boutons conditionnels PEI/DP avec requêtes DB de visibilité
- ✅ `_BTN_VIEW` mapping vers 11 vues cibles distinctes
- ✅ Professeur principal bouton (fk_headteacher_id)
- ✅ Renommé "LarcProf" dans tous les titres

### Top bar
- ✅ 4 sections fixes : Matière-Classe, Formatives, Sommatives, Jugements
- ✅ Slots actifs uniquement, inactifs invisibles
- ✅ Clic slot → bascule colonne dans la grille
- ✅ Boutons Toute / Aucune / Commentaire par section

### Grille élèves × notes
- ✅ Colonnes dynamiques, chargement SQLite, édition double-clic
- ✅ `_save_grid_edits()` → SQLite

### EvalManagerWindow
- ✅ Fenêtre non-modale, tabs F01-F12, éditeur markdown
- ✅ Bug `destroyed` lambda corrigé (try/except RuntimeError)

### SyncManager
- ✅ `common/sync.py` : diff cellule via shadow-tables `_ref`
- ✅ Bouton Synchroniser dans HomeWindow

## 4. Theme & i18n

- ✅ `common/theme.py` ThemeManager avec `phi_theme` (Theme phibuilder + PhiScale)
- ✅ `_M3Colors` mappe palette locale → propriétés M3
- ✅ Fibonacci via `theme_manager.phi_theme.spacing.spacing(SpacingToken.XXL)`
- ✅ i18n : 18 clés `prof_login.*` dans LarcCommon fr.json/en.json
- ✅ Translator initialisé dans LoginWindow (`LARC_LANG` env var)
- ⚠ Ne pas utiliser `_` comme variable throwaway → `_outer`, `_ignored`

## 5. Problèmes Connus

- `EvalManagerWindow.destroyed` lambda → wrappé dans try/except RuntimeError
- SQLite stocke tous les booléens en integer (0/1), pas en text — requêtes utilisent `enabled = 1`
- `larcauth_classroom_termothersubject` vide pour le prof 1021 → boutons interdisc/PP masqués

## 6. 🚧 À Faire

1. Vues cibles : `college_notes_opt1`, `college_notes_opt2`, `lycee_notes_0`, `lycee_notes_opt1/2/3`
2. `colleges_eleves` / `lycee_eleves` : connexion serveur directe, UI simplifiée LarcSuperviseur
3. `college_bulletin` / `lycee_bulletin` : notes et commentaires SQLite
4. Appliquer scripts SQL sync sur Intranet/Cloud
5. Jeu de test données T3
6. Dashboard par rôle (COORD, SECR, ADMIN)

---

_Mémoire persistante LarcProf — 9 juillet 2026_

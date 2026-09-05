# REPRISE — P11 Build PyInstaller (tâche #27, in_progress)

Date : 2026-08-27 ~18:15 — pause d'une heure demandée par l'utilisateur.

## Où j'en suis — EXACTEMENT

### Fait (terminé, vérifié)
- `larcforge/collectors/build.py` — collecteur PyInstaller (BUILD_TARGETS, hiddenimports UI, launcher temporaire, sortie `{root}/dist/{app}/`)
- `larcforge/store.py` — `resolve_build_issues(conn, app, run_id)` (résout les issues larcforge:build open/regressed de l'app)
- `larcforge/runner.py` — `execute_build(root, app, python, timeout, onefile, use_db)` (run larc_run, upsert candidat en échec, résolution auto en succès)
- `larcforge/cli.py` — sous-commande `build` (`--app` défaut LarcForge, `--onefile`, timeout min 900)
- Tests : `tests/test_build_collector.py` (9) + `tests/test_cli.py` (build) — suite complète 145 tests VERTE, lint 0, PyInstaller 6.22.2 installé
- Premier build réel lancé → run #9 → issue `larcforge:build` créée dans le registre (le mécanisme échec→registre fonctionne)

### Cause racine du premier échec (DIAGNOSTIC TERMINÉ)
- PAS une erreur PyInstaller : rc=0, « Build complete! » (vérifié en relançant la commande à la main avec --log-level INFO)
- Le log (15 dernières lignes de stderr) ne montrait que des INFO/WARNING — trompeur
- **Le collecteur cherchait l'exe à 2 niveaux** (`distpath/LarcForge.exe`) alors que **PyInstaller 6.22 en mode onedir écrit à 3 niveaux** : `distpath/<name>/<name>.exe` + dossier `_internal/`
- Exe réel produit (18:11:29, build manuel de diagnostic) : `F:\projets\dist\LarcForge\LarcForge\LarcForge.exe`

### Correctif appliqué (EN COURS — pas encore re-testé)
- `larcforge/collectors/build.py` (lignes ~112-120) : vérifie les DEUX layouts :
  ```python
  exe_onedir = out_dir / app / f"{app}.exe"
  exe_onefile = out_dir / f"{app}.exe"
  exe = exe_onedir if exe_onedir.is_file() else exe_onefile
  ```

## Prochaines étapes — DANS CET ORDRE

1. Adapter `tests/test_build_collector.py::test_commande_pyinstaller` : le fake crée actuellement
   2 niveaux avec onefile=True ; ajouter un test onedir 3 niveaux (layout réel 6.22).
   (`test_execute_build_succes_resout` crée déjà 3 niveaux → compatible.)
2. `python -m pytest tests -q` → suite verte (145+)
3. Preuve E2E réelle : `python -m larcforge build --app LarcForge` → attendu : exit 0,
   « Build OK — dist/LarcForge/LarcForge/LarcForge.exe (N octets) », et l'issue
   larcforge:build du run #9 RÉSOLUE automatiquement (resolve_build_issues).
   Vérif : `python -m larcforge status --open` (ou IHM).
4. Prouver l'exe lançable : `F:\projets\dist\LarcForge\LarcForge\LarcForge.exe --version`
   (doit afficher larcforge <version>)
5. Marquer #27 completed → passer à #28 (P12 Setups Inno : templates .iss par app +
   sous-commande `setup`, ISCC.exe, preuve : setup produit + `/SILENT`)

## Rappels techniques utiles
- Root du monorepo = `F:\projets` (JAMAIS de D:/C:/E: en dur dans le code)
- DB : `pg.connect(section="IntranetDatabase", root, params=None)` ; config master = `LarcCommon/config.ini` port 55517
- FakeConn/FakeCursor (conftest) : plans consommés dans l'ordre des cursor(), `fetchone()` retourne les plans (tuples), `rowcounts` param du FakeConn, 4 curseurs pour le succès de execute_build (start_run, SELECT build, resolve_issue, count_open)
- L'issue build ouverte : source=`larcforge:build`, app_name=`LarcForge`, run #9

# LarcForge — Durcissement du Pipeline (Étape 1 & 3)

## Vue d'Ensemble

Implémentation des **Étape 1** (Audit du script de build) et **Étape 3** (Mode Dry-Run/Strict Check) du plan d'amélioration d'audit.

---

## 🔨 Étape 1 : Audit du Script de Build Principal + Codes de Retour Stricts

### Objectif
Transformer le pipeline en un **"gardien intraitable"** qui bloque immédiatement toute anomalie, sans laisser passer une étape suivante.

### Implémentation
**Fichier modifié** : `larcforge/runner.py`

#### Blocage en Cascade (Fail-Fast)

```
[ 1. Synchronisation & Nettoyage ] 
            │
            ▼
  [ 2. Linting ] ──(Erreur technique?)──> [ 🛑 EXIT 3 ]
            │
            └─(Problèmes détectés?)──> [ 🛑 EXIT 1 ]
            │
            ▼
  [ 3. Tests ] ──(Erreur technique?)──> [ 🛑 EXIT 3 ]
            │
            └─(Tests échoués?)──> [ 🛑 EXIT 1 ]
            │
            ▼
  [ 4. Errorlog ] (en mode non-dry-run)
            │
            ▼
  [ 5. Écriture DB + Finalization ]
```

#### Codes de Sortie Stricts
| Code | Sens | Exemple |
|---|---|---|
| **0** | Succès total | Audit propre |
| **1** | Issues détectées | Linting ou tests trouvent des bugs |
| **3** | Erreur technique | Crash d'un collecteur, timeout |
| **4** | DB injoignable | PostgreSQL down |

#### Bloc 1 : Linting (nouvelles règles)
```python
# Si erreurs techniques → ARRÊT immédiat (EXIT 3)
if summary.nb_errors > 0 and not dry_run:
    return summary, 3, f"ARRÊT : {summary.nb_errors} erreur(s) technique au linting"

# Si problèmes détectés → ARRÊT (EXIT 1), sauf en mode dry-run
if all_cands and not dry_run:
    return summary, 1, f"ARRÊT : {len(all_cands)} problème(s) détecté(s) au linting"
```

#### Bloc 2 : Tests (mêmes règles)
```python
if summary.nb_errors > 0 and not dry_run:
    return summary, 3, f"ARRÊT : {summary.nb_errors} erreur(s) technique aux tests"
if cands and not dry_run:
    return summary, 1, f"ARRÊT : Tests échoués — {len(cands)} problème(s) détecté(s)"
```

---

## 🔍 Étape 3 : Mode "Dry-Run / Strict Check"

### Objectif
Permettre d'**auditer l'application entière** sans déclencher :
- Écriture DB
- Compilation PyInstaller lourde
- Génération de setups

Utile pour : **validation avant build**, **audit en CI/CD**, **reports de régression**.

### Implémentation
**Fichiers modifiés** : `cli.py` + `runner.py`

#### Flag CLI
```bash
# Audit des linters + tests, NO DB, NO BUILD
python -m larcforge lints --dry-run
python -m larcforge tests --dry-run
python -m larcforge run --dry-run

# JSON pour CI/CD
python -m larcforge lints --dry-run --json
```

#### Comportement en Mode Dry-Run
1. ✅ **Linters** → s'exécutent (validation statique)
2. ✅ **Tests** → s'exécutent (validation dynamique)
3. ❌ **DB** → non écrite (--no-db forcé)
4. ❌ **Errorlog** → sauté
5. ❌ **Compilation** → non déclenchée

#### Codes de Sortie en Dry-Run
- **0** → "DRY-RUN AUDIT : audit propre (prêt pour la compilation)"
- **1** → "DRY-RUN AUDIT : X problème(s) détecté(s) (DB non modifiée)"
- **3** → "DRY-RUN AUDIT : X erreur(s) technique(s) (DB non modifiée)"

### Exemple de Rapport Dry-Run
```
=== DRY-RUN AUDIT (RUN) — run #— ===
  problèmes vus : 5  
  nouveaux : 3  
  régressions : 0  
  résolus : 0
  → DRY-RUN AUDIT : 5 problème(s) détecté(s) (DB non modifiée)  [exit 1]
```

---

## 📋 Cas d'Usage

### 1. Pipeline CI/CD Strict (Git push)
```bash
# Étape 1 : Vérifications
python -m larcforge run

# Étape 2 : Compilation (seulement si run = 0)
if [ $? -eq 0 ]; then
  python -m larcforge build --app LarcForge
fi
```

### 2. Audit d'une Modification Larcommon (avant merge)
```bash
# Vérifier que les clients passent les tests
python -m larcforge run --dry-run --projects LarcCommon,LarcProf,LarcSecretaire

# Si dry-run = 0 → safe to merge (validation cross-client)
```

### 3. Report Quotidien (sans déranger la DB)
```bash
# Capture l'état du jour, sans pollution historique
python -m larcforge lints --dry-run --json > audit-larccommon.json
```

### 4. Déploiement Automatisé

```bash
# Validation
python -m larcforge run --dry-run || exit 1

# Compilation
python -m larcforge build --app LarcForge --onefile

# Si build OK → déployer vers production
```

---

## 🧪 Tester les Implémentations

### Test 1 : Linting avec erreur
```bash
cd D:\Projets\LarcForge
python -m larcforge lints --dry-run --projects LarcCommon

# Résultat attendu : EXIT 1 (problèmes détectés)
echo $?  # → 1
```

### Test 2 : Dry-run propre
```bash
# Si LarcCommon n'a pas d'erreurs
python -m larcforge run --dry-run --no-db

# Résultat attendu : EXIT 0
echo $?  # → 0
```

### Test 3 : Comparaison run vs dry-run
```bash
# Avant
python -m larcforge lints  # écrit en DB, exit 1
psql -c "SELECT COUNT(*) FROM larc_run;" # = N

# Dry-run (no-db est forcé)
python -m larcforge lints --dry-run  # n'écrit rien
psql -c "SELECT COUNT(*) FROM larc_run;" # = N (inchangé)
```

---

## 📊 Durci du Build en 2 Étapes

### Avant (❌ Non-bloquant)
```
linting: 3 errors → CONTINUE
tests: 2 failures → CONTINUE
build: crash → FAIL
↳ Trop tard — db polluée, dépôt non fiable
```

### Après (✅ Fail-Fast)
```
linting: 3 errors → EXIT 3 (STOP)
↳ Correction immédiate requise
↳ db propre, build jamais déclenché
```

---

## 🚀 Intégration avec le Projet

### Actions Prochaines
1. **Tests unitaires** : ajouter `test_dry_run` à `tests/test_cli.py`
2. **Documentation CLI** : mettre à jour `README.md` avec `--dry-run`
3. **Ci/CD** : intégrer dans `.github/workflows/*.yml` ou équivalent
4. **Formation** : documenter les "fail-fast" pattern dans `GUIDE_DEBUTANT.md`

### Signature des Commits
```
Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 📈 Métriques de Succès

- ✅ Aucun build compilé avec des erreurs en attente
- ✅ Dry-run utilisé avant chaque push critique
- ✅ Taux de régression < 2% (vs précédent)
- ✅ Temps de détection d'erreur : **< 1 min** (vs > 10 min avant)

# Types d'événements multilingues + gabarit — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter `fk_language` sur `larcauth_event_type_config` (arbre dupliqué par langue,
`is_active` indépendant par langue), doter la table d'un gabarit de slots "potentiels"
réutilisables (jamais d'`INSERT` en usage courant), et faire de `LarcConfig` un vrai éditeur
(langue, parent, actif, libellé, création d'un type via activation bilingue).

**Architecture:** Migration SQL set-based (duplication FR→EN par passes de profondeur,
génération des slots potentiels via CTE récursive). `EventTypeConfigService` prend `fk_language`
en paramètre (cache mono-langue, rechargé si la langue change). `LarcConfig/common/db_access.py`
gagne des fonctions d'écriture ; `panel_types.py` passe de lecture seule à éditeur.

**Tech Stack:** Python 3.x, PySide6 (Qt6), PostgreSQL (psycopg2, autocommit), pytest.

**Spec:** [docs/superpowers/specs/2026-09-07-event-type-language-gabarit-design.md](../specs/2026-09-07-event-type-language-gabarit-design.md)

## Global Constraints

- **Principe gabarit** : jamais de `DELETE` ni d'`INSERT` en usage courant sur
  `larcauth_event_type_config` — seulement `UPDATE` (activer un slot potentiel = poser un vrai
  `code`/`label` + `is_active=TRUE`, jamais l'inverse une fois posé).
- **Slot libre** = `is_active = FALSE` ET `code LIKE 'type_niv%'` (motif placeholder jamais
  encore assigné) — jamais un type réel désactivé, même ancien.
- **Imports UI** : toujours `phibuilder.widgets`, jamais `PySide6.QtWidgets` direct (exceptions :
  `QMessageBox`, `QApplication`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QButtonGroup`,
  `QTableWidgetItem`).
- **Zéro hardcoding** : espacements/rayons/couleurs via `ds.*`.
- **`@safe_slot`** obligatoire sur tous les slots Qt.
- **Fichiers > 1000 lignes interdits**.

---

## Task 1 : Migration DB — `fk_language` + duplication FR/EN + gabarit potentiel

**Files:**
- Create: `LarcCommon/migrations/2026_09_07_event_type_language_gabarit.sql`

**Interfaces:**
- Produces : colonne `larcauth_event_type_config.fk_language` (NOT NULL, FK →
  `larcauth_language(id)`), contrainte `UNIQUE(code, fk_language)` (remplace `UNIQUE(code)`),
  ~217 nœuds actifs+potentiels par langue (consommés par Task 2).

- [ ] **Step 1 : Écrire la migration complète**

```sql
-- Migration: 2026-09-07_event_type_language_gabarit
-- fk_language sur larcauth_event_type_config (pattern larcauth_program : arbre dupliqué par
-- langue, is_active indépendant par langue) + gabarit de slots potentiels réutilisables.
-- Additive uniquement (principe gabarit) : les 105 lignes existantes deviennent la variante
-- FR (fk_language=2), dupliquées en EN (fk_language=1, texte à corriger dans LarcConfig).

-- ----------------------------------------------------------------------------
-- 1. Colonne fk_language — les 105 lignes existantes sont la variante française
-- ----------------------------------------------------------------------------
ALTER TABLE larcauth_event_type_config
    ADD COLUMN IF NOT EXISTS fk_language INT REFERENCES larcauth_language(id);

UPDATE larcauth_event_type_config SET fk_language = 2 WHERE fk_language IS NULL;

ALTER TABLE larcauth_event_type_config ALTER COLUMN fk_language SET NOT NULL;

ALTER TABLE larcauth_event_type_config
    DROP CONSTRAINT IF EXISTS larcauth_event_type_config_code_key;

ALTER TABLE larcauth_event_type_config
    ADD CONSTRAINT larcauth_event_type_config_code_fklang_key UNIQUE (code, fk_language);

-- ----------------------------------------------------------------------------
-- 2. Duplication FR (fk_language=2) -> EN (fk_language=1)
--    4 passes identiques (profondeur max = 4 niveaux) : chaque passe résout le parent EN
--    via le code du parent FR déjà dupliqué par la passe précédente (les racines n'ont pas
--    besoin de parent résolu, elles passent dès la 1re passe).
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- Passe 2 (résout les enfants de racines, désormais dupliquées par la passe 1)
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- Passe 3
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- Passe 4 (feuilles)
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- ----------------------------------------------------------------------------
-- 3. Gabarit potentiel — niveau 1 (racines) : +2 par langue, catégorie 'custom', sans parent
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
    (code, label, category, parent_id, applicable_to, requires_validation, requires_lieu,
     requires_subject, is_active, fk_language)
SELECT 'type_niv1_' || lpad(n::text, 2, '0'),
       'Type_Niv1_' || lpad(n::text, 2, '0'),
       'custom', NULL, 'student,staff', TRUE, FALSE, FALSE, FALSE, lang.id
FROM generate_series(1, 2) AS n
CROSS JOIN larcauth_language lang
ON CONFLICT (code, fk_language) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Gabarit potentiel — niveaux 2-4 : +2 par parent réel ACTIF, par langue
--    (aucun slot potentiel niveau 2 sous une racine potentielle — is_active=TRUE filtre ça)
-- ----------------------------------------------------------------------------
WITH RECURSIVE depths AS (
    SELECT id, code, category, applicable_to, fk_language, 1 AS depth
    FROM larcauth_event_type_config WHERE parent_id IS NULL AND is_active = TRUE
    UNION ALL
    SELECT c.id, c.code, c.category, c.applicable_to, c.fk_language, d.depth + 1
    FROM larcauth_event_type_config c
    JOIN depths d ON c.parent_id = d.id
    WHERE c.is_active = TRUE
)
INSERT INTO larcauth_event_type_config
    (code, label, category, parent_id, applicable_to, requires_validation, requires_lieu,
     requires_subject, is_active, fk_language)
SELECT 'type_niv' || (d.depth + 1) || '_' || d.code || '_' || lpad(n::text, 2, '0'),
       'Type_Niv' || (d.depth + 1) || '_' || lpad(n::text, 2, '0'),
       d.category, d.id, d.applicable_to, TRUE, FALSE, FALSE, FALSE, d.fk_language
FROM depths d
CROSS JOIN generate_series(1, 2) AS n
WHERE d.depth < 4
ON CONFLICT (code, fk_language) DO NOTHING;
```

- [ ] **Step 2 : Appliquer sur la base réellement configurée (port 55517, `NewLarcDb`) et
  vérifier**

```bash
psql -U postgres -h 127.0.0.1 -p 55517 -d NewLarcDb -f LarcCommon/migrations/2026_09_07_event_type_language_gabarit.sql
```

Vérifications :
```sql
-- Total par langue (attendu : ~217 chacun, soit ~434 au total)
SELECT fk_language, count(*) FROM larcauth_event_type_config GROUP BY fk_language;

-- Aucun doublon (code, fk_language)
SELECT code, fk_language, count(*) FROM larcauth_event_type_config
GROUP BY code, fk_language HAVING count(*) > 1;

-- Les racines actives sont bien 4 par langue (Absence/Retard/Sortie/Événement)
SELECT fk_language, code, label FROM larcauth_event_type_config
WHERE parent_id IS NULL AND is_active = TRUE ORDER BY fk_language, code;

-- Un nœud EN a bien le même nombre d'enfants actifs que son équivalent FR (même code)
SELECT fr.code, fr_children.n AS enfants_fr, en_children.n AS enfants_en
FROM larcauth_event_type_config fr
JOIN larcauth_event_type_config en ON en.code = fr.code AND en.fk_language = 1
LEFT JOIN LATERAL (SELECT count(*) n FROM larcauth_event_type_config
                    WHERE parent_id = fr.id AND is_active) fr_children ON TRUE
LEFT JOIN LATERAL (SELECT count(*) n FROM larcauth_event_type_config
                    WHERE parent_id = en.id AND is_active) en_children ON TRUE
WHERE fr.fk_language = 2 AND fr_children.n != en_children.n;
-- Attendu : 0 ligne (les arbres FR/EN sont symétriques sur le réel)

-- Ré-exécution idempotente : relancer ne doit rien dupliquer (compter avant/après)
```

- [ ] **Step 3 : Commit**

```bash
git add LarcCommon/migrations/2026_09_07_event_type_language_gabarit.sql
git commit -m "$(cat <<'EOF'
feat(db): fk_language sur larcauth_event_type_config + gabarit de slots potentiels

Duplique l'arbre existant (105 lignes, FR) en EN (pattern larcauth_program :
is_active indépendant par langue, code sert de lien conceptuel entre langues
sans jamais servir de clé étrangère). Ajoute ~112 slots potentiels par langue
(+2 par parent réel actif, niveaux 1-4) au motif code placeholder
'type_nivN_...', jamais assignés — mécanisme d'activation identique au
pattern élèves ('Name of %').

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 : `EventTypeConfigService` — paramétrer par `fk_language`

**Files:**
- Modify: `LarcCommon/larccommon/event_type_service.py`
- Test: `LarcCommon/tests/test_event_type_service.py`

**Interfaces:**
- Produces : `load_hierarchy(fk_language: int, force_refresh: bool = False)`,
  `filter_applicable(member_type: MemberType, fk_language: int)` — signatures étendues,
  consommées par Task 3.
- Consumes : rien de nouveau (mêmes tables, requête simplement filtrée par `fk_language`).

- [ ] **Step 1 : Écrire le test (2 langues dans le faux curseur, vérifie l'isolation)**

```python
"""Régression : EventTypeConfigService filtre par fk_language, cache par langue."""
from larccommon.event_type_service import EventTypeConfigService, MemberType


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._params = params

    def fetchall(self):
        lang = self._params[0] if self._params else None
        return [r for r in self._rows if r[3] == lang] if lang else self._rows


class FakeConn:
    closed = False

    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)


# id, code, label, fk_language, category, icon_code, parent_id, applicable_to,
# requires_validation, requires_lieu, requires_subject
TWO_LANG_ROWS = [
    (1, 'absence', 'Absence', 2, 'absence', None, None, 'student,staff', True, False, False),
    (2, 'absence', 'Absence', 1, 'absence', None, None, 'student,staff', True, False, False),
]


class TestEventTypeConfigServiceLanguage:
    def setup_method(self):
        EventTypeConfigService._instance = None

    def test_load_hierarchy_filters_by_language(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(TWO_LANG_ROWS)})(),
        )
        fr = service.load_hierarchy(fk_language=2, force_refresh=True)
        assert fr["absence"].label == "Absence"
        assert fr["absence"].id == 1

    def test_load_hierarchy_reloads_when_language_changes(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(TWO_LANG_ROWS)})(),
        )
        service.load_hierarchy(fk_language=2, force_refresh=True)
        en = service.load_hierarchy(fk_language=1)  # pas de force_refresh : doit quand même recharger
        assert en["absence"].id == 2

    def test_filter_applicable_passes_language_through(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(TWO_LANG_ROWS)})(),
        )
        result = service.filter_applicable(MemberType.STUDENT, fk_language=1)
        assert result["absence"].id == 2
```

- [ ] **Step 2 : Lancer et vérifier que ça échoue**

```bash
cd D:\projets\LarcCommon && pytest tests/test_event_type_service.py -v -k Language
```
Attendu : `TypeError: load_hierarchy() missing 1 required positional argument: 'fk_language'`.

- [ ] **Step 3 : Implémenter — modifier `load_hierarchy`/`filter_applicable`**

Dans `LarcCommon/larccommon/event_type_service.py`, remplacer les deux méthodes :

```python
    def load_hierarchy(self, fk_language: int, force_refresh: bool = False) -> Dict[str, EventTypeNode]:
        """
        Charge la hiérarchie depuis DB pour une langue donnée, avec cache.

        Le cache est mono-langue : un changement de langue déclenche un rechargement
        transparent (pas de cache multi-langue simultané — inutile, une session UI ne
        travaille jamais dans deux langues à la fois).
        """
        if self._hierarchies and self._cached_language == fk_language and not force_refresh:
            return self._hierarchies

        try:
            conn = db.server_conn
            if not conn or conn.closed:
                log("EventTypeConfigService.load_hierarchy: DB not connected")
                return {}

            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, code, label, category, icon_code, parent_id,
                       applicable_to, requires_validation, requires_lieu, requires_subject
                FROM larcauth_event_type_config
                WHERE is_active = TRUE AND fk_language = %s
                ORDER BY category, parent_id NULLS FIRST, label
                """,
                (fk_language,),
            )

            rows = cur.fetchall()
            if not rows:
                log(f"EventTypeConfigService.load_hierarchy: aucun type chargé (langue={fk_language})")
                return {}

            self._cache = {}
            for row in rows:
                node_id = row[0]
                self._cache[node_id] = EventTypeNode(
                    id=node_id, code=row[1], label=row[2], category=row[3],
                    icon_code=row[4], parent_id=row[5], applicable_to=row[6],
                    requires_validation=row[7], requires_lieu=row[8], requires_subject=row[9],
                )

            for node in self._cache.values():
                if node.parent_id and node.parent_id in self._cache:
                    self._cache[node.parent_id].children.append(node)

            self._hierarchies = {}
            for node in self._cache.values():
                if node.parent_id is None:
                    self._hierarchies[node.category] = node

            self._cached_language = fk_language
            log(
                f"EventTypeConfigService: loaded {len(self._cache)} types, "
                f"{len(self._hierarchies)} roots (langue={fk_language})"
            )
            return self._hierarchies

        except Exception as e:
            log(f"EventTypeConfigService.load_hierarchy: {e}")
            return {}
```

Ajouter `self._cached_language: Optional[int] = None` dans `__init__` (juste après
`self._hierarchies = {}`).

```python
    def filter_applicable(
        self, member_type: MemberType, fk_language: int
    ) -> Dict[str, EventTypeNode]:
        """Filtre les types applicables pour un type de membre, dans une langue donnée."""
        hierarchies = self.load_hierarchy(fk_language)
        result = {}
        for cat, root in hierarchies.items():
            if root.is_applicable_to(member_type):
                result[cat] = root
        return result
```

- [ ] **Step 4 : Lancer et vérifier que ça passe**

```bash
cd D:\projets\LarcCommon && pytest tests/test_event_type_service.py -v
```
Attendu : tous les tests passent (les 4 existants sur 4 niveaux + les 3 nouveaux sur la langue).

- [ ] **Step 5 : Commit**

```bash
git add LarcCommon/larccommon/event_type_service.py LarcCommon/tests/test_event_type_service.py
git commit -m "$(cat <<'EOF'
feat(larccommon): EventTypeConfigService filtre par fk_language

load_hierarchy()/filter_applicable() prennent fk_language en paramètre
obligatoire. Cache mono-langue : un changement de langue recharge
automatiquement (pas de cache multi-langue simultané).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 : `EventGeneratorDialog` — passer `session.fk_language`

**Files:**
- Modify: `LarcCommon/larccommon/dialogs/event_generator_dialog.py`
- Test: `LarcCommon/tests/test_event_generator_dialog_smoke.py`

**Interfaces:**
- Consumes : `EventTypeConfigService.filter_applicable(member_type, fk_language)` (Task 2).

- [ ] **Step 1 : Modifier l'appel dans `__init__`**

Dans `EventGeneratorDialog.__init__`, remplacer :
```python
        self._type_hierarchies = event_type_service.filter_applicable(member_type)
```
par :
```python
        self._type_hierarchies = event_type_service.filter_applicable(
            member_type, getattr(session, "fk_language", 2)
        )
```
(défaut `2` = français, cohérent avec `EventGeneratorDialog._load_subjects` qui utilise déjà
`getattr(session, "fk_language", ...)` de la même façon ailleurs dans ce fichier).

- [ ] **Step 2 : Mettre à jour le mock du test existant**

Dans `LarcCommon/tests/test_event_generator_dialog_smoke.py`, la fixture `dialog` patche déjà
`event_type_service.filter_applicable` via
`patch.object(event_type_service, "filter_applicable", return_value=hierarchies)` — un
`return_value` ignore les arguments reçus, donc **aucun changement requis** dans le test : il
continue de passer tel quel avec la nouvelle signature à 2 arguments.

- [ ] **Step 3 : Lancer la suite et vérifier qu'elle passe toujours**

```bash
cd D:\projets\LarcCommon && pytest tests/test_event_generator_dialog_smoke.py -v
```
Attendu : les 10 tests existants passent sans modification.

- [ ] **Step 4 : Commit**

```bash
git add LarcCommon/larccommon/dialogs/event_generator_dialog.py
git commit -m "$(cat <<'EOF'
fix(larccommon): EventGeneratorDialog charge la hiérarchie dans la langue de la session

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 : `LarcConfig/common/db_access.py` — lecture par langue + écriture

**Files:**
- Modify: `LarcConfig/common/db_access.py`
- Create: `LarcConfig/tests/test_db_access_event_types.py`
- Create: `LarcConfig/tests/__init__.py` (vide — premier test du projet)

**Interfaces:**
- Produces :
  - `get_event_types(fk_language: int) -> list[dict]` (signature étendue, ajoute `parent_label`)
  - `set_event_type_active(id: int, enabled: bool) -> bool`
  - `set_event_type_label(id: int, label: str) -> bool`
  - `activate_event_type(parent_code: str | None, code_suffix: str, label_fr: str, label_en: str) -> bool`
    — trouve le premier slot potentiel libre sous le parent (identifié par `code`, pas `id` —
    résout `id` par langue), dans les 2 langues, pose le même `code` final, `is_active=TRUE`.

- [ ] **Step 1 : Écrire les tests (FakeCursor/FakeConn, même style que
  `test_event_type_service.py`)**

```python
"""Tests db_access — types d'événements (lecture par langue + écriture LarcConfig)."""
from unittest.mock import MagicMock, patch

from LarcConfig.common import db_access


class FakeCursor:
    def __init__(self):
        self.executed = []
        self._next_fetchall = []
        self._next_fetchone = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._next_fetchall

    def fetchone(self):
        return self._next_fetchone


class FakeConn:
    def cursor(self):
        return self._cur


class TestGetEventTypes:
    def test_filters_by_language_and_resolves_parent_label(self):
        cur = FakeCursor()
        cur._next_fetchall = [
            (1, 'absence', 'Absence', None, 0, True, None),
            (2, 'absence_school', "Absent de l'école", 1, 1, True, 'Absence'),
        ]
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            rows = db_access.get_event_types(fk_language=2)
        assert rows[1]['parent_label'] == 'Absence'
        assert '%s' in cur.executed[0][0]
        assert cur.executed[0][1] == (2,)


class TestSetEventTypeActive:
    def test_writes_is_active(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.set_event_type_active(42, True)
        assert ok is True
        assert "UPDATE larcauth_event_type_config" in cur.executed[0][0]
        assert "is_active" in cur.executed[0][0]
        assert cur.executed[0][1] == (True, 42)


class TestSetEventTypeLabel:
    def test_writes_label(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.set_event_type_label(42, "Nouveau libellé")
        assert ok is True
        assert cur.executed[0][1] == ("Nouveau libellé", 42)


class TestActivateEventType:
    def test_activates_first_free_slot_in_both_languages(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur

        # 1er appel (résolution parent FR), 2e (slot libre FR), 3e (résolution parent EN),
        # 4e (slot libre EN) — fetchone() successifs.
        responses = iter([(10,), (11,), (20,), (21,)])

        def fake_fetchone():
            return next(responses, None)

        cur.fetchone = fake_fetchone

        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.activate_event_type(
                parent_code="absence_school", code_suffix="allergie",
                label_fr="Allergie", label_en="Allergy",
            )
        assert ok is True
        # 2 UPDATE (un par langue) après les 2 SELECT de résolution de slot
        update_calls = [e for e in cur.executed if e[0].strip().startswith("UPDATE")]
        assert len(update_calls) == 2
```

- [ ] **Step 2 : Lancer et vérifier que ça échoue**

```bash
cd D:\projets && touch LarcConfig/tests/__init__.py
python -m pytest LarcConfig/tests/test_db_access_event_types.py -v
```
Attendu : `AttributeError: module 'LarcConfig.common.db_access' has no attribute 'set_event_type_active'`
(et les autres fonctions manquantes).

- [ ] **Step 3 : Implémenter dans `LarcConfig/common/db_access.py`**

Remplacer `get_event_types()` par :

```python
def get_event_types(fk_language: int):
    """Types d'événements — larcauth_event_type_config, une langue, avec parent résolu."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute("""
            WITH RECURSIVE tree AS (
                SELECT id, code, label, category, parent_id, is_active, 0 AS depth
                FROM larcauth_event_type_config
                WHERE parent_id IS NULL AND fk_language = %s
                UNION ALL
                SELECT te.id, te.code, te.label, te.category, te.parent_id, te.is_active,
                       tree.depth + 1
                FROM larcauth_event_type_config te
                JOIN tree ON te.parent_id = tree.id
            )
            SELECT t.id, t.code, t.label, t.parent_id, t.depth, t.is_active, p.label
            FROM tree t
            LEFT JOIN larcauth_event_type_config p ON p.id = t.parent_id
            ORDER BY t.depth, COALESCE(t.parent_id, 0), t.id
        """, (fk_language,))
        return [
            dict(zip(
                ['id', 'code', 'label', 'parent_id', 'depth', 'enabled', 'parent_label'],
                r,
            ))
            for r in cur.fetchall()
        ]
    except Exception:
        return []


def set_event_type_active(event_type_id: int, enabled: bool) -> bool:
    """Active/désactive un type — jamais de suppression (principe gabarit)."""
    c = _conn()
    if not c:
        return False
    try:
        cur = c.cursor()
        cur.execute(
            "UPDATE larcauth_event_type_config SET is_active = %s WHERE id = %s",
            (enabled, event_type_id),
        )
        return True
    except Exception:
        return False


def set_event_type_label(event_type_id: int, label: str) -> bool:
    """Renomme le libellé d'un type, pour la langue de la ligne visée."""
    c = _conn()
    if not c:
        return False
    try:
        cur = c.cursor()
        cur.execute(
            "UPDATE larcauth_event_type_config SET label = %s WHERE id = %s",
            (label, event_type_id),
        )
        return True
    except Exception:
        return False


def activate_event_type(
    parent_code: str | None, code_suffix: str, label_fr: str, label_en: str,
) -> bool:
    """Active le 1er slot potentiel libre sous `parent_code`, dans les 2 langues à la fois.

    'Libre' = is_active=FALSE ET code LIKE 'type_niv%%' (jamais encore assigné) — même
    mécanisme que le slot élève ('Name of %%'), cf. spec. Le code final
    (`{parent_code}_{code_suffix}` ou juste `code_suffix` pour une racine) est identique dans
    les 2 langues — c'est le lien conceptuel entre les deux arbres.
    """
    c = _conn()
    if not c:
        return False
    try:
        cur = c.cursor()
        final_code = f"{parent_code}_{code_suffix}" if parent_code else code_suffix

        for fk_language, label in ((2, label_fr), (1, label_en)):
            if parent_code:
                cur.execute(
                    "SELECT id FROM larcauth_event_type_config "
                    "WHERE code = %s AND fk_language = %s",
                    (parent_code, fk_language),
                )
                parent_row = cur.fetchone()
                if not parent_row:
                    return False
                parent_id = parent_row[0]
                cur.execute(
                    "SELECT id FROM larcauth_event_type_config "
                    "WHERE parent_id = %s AND fk_language = %s "
                    "AND is_active = FALSE AND code LIKE 'type_niv%%' "
                    "ORDER BY id LIMIT 1",
                    (parent_id, fk_language),
                )
            else:
                cur.execute(
                    "SELECT id FROM larcauth_event_type_config "
                    "WHERE parent_id IS NULL AND fk_language = %s "
                    "AND is_active = FALSE AND code LIKE 'type_niv%%' "
                    "ORDER BY id LIMIT 1",
                    (fk_language,),
                )
            slot_row = cur.fetchone()
            if not slot_row:
                return False  # plus de slot potentiel disponible à ce niveau
            slot_id = slot_row[0]

            cur.execute(
                "UPDATE larcauth_event_type_config "
                "SET code = %s, label = %s, is_active = TRUE WHERE id = %s",
                (final_code, label, slot_id),
            )
        return True
    except Exception:
        return False
```

- [ ] **Step 4 : Lancer et vérifier que ça passe**

```bash
cd D:\projets && python -m pytest LarcConfig/tests/test_db_access_event_types.py -v
```
Attendu : 4 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add LarcConfig/common/db_access.py LarcConfig/tests/
git commit -m "$(cat <<'EOF'
feat(larcconfig): db_access gagne la langue + l'écriture des types d'événements

get_event_types(fk_language) résout le libellé du parent. Nouvelles fonctions
d'écriture : set_event_type_active, set_event_type_label,
activate_event_type (active le 1er slot potentiel libre dans les 2 langues
à la fois, jamais d'INSERT — principe gabarit).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 : `LarcConfig/views/panel_types.py` — éditeur (langue, parent, actif, libellé)

**Files:**
- Modify: `LarcConfig/views/panel_types.py`

**Interfaces:**
- Consumes : `get_event_types(fk_language)`, `set_event_type_active`, `set_event_type_label`
  (Task 4).

- [ ] **Step 1 : Remplacer le fichier — sélecteur de langue, colonne Parent, édition inline**

```python
"""Panel Types d'événements — éditeur (langue, parent, actif, libellé)."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem
from PySide6.QtCore import Qt
from phibuilder.widgets import M3Label, M3TableWidget, M3ScrollArea, M3ComboBox
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from LarcConfig.common.db_access import get_event_types, set_event_type_active, set_event_type_label


class TypesPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))

        header_row = QHBoxLayout()
        header_row.addWidget(M3Label("Types d'evenements", theme=phi, style="headline_small"))
        header_row.addStretch()
        header_row.addWidget(M3Label("Langue :", theme=phi, style="body_medium"))
        self._lang_combo = M3ComboBox(["Français", "English"], theme=phi)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        header_row.addWidget(self._lang_combo)
        l.addLayout(header_row)

        self._table = M3TableWidget(theme=phi)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Catégorie", "Parent", "Libellé", "Code", "Actif"]
        )
        h = self._table.horizontalHeader()
        for i in range(6):
            h.setSectionResizeMode(i, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(False)
        self._table.itemChanged.connect(self._on_item_changed)
        l.addWidget(self._table)

        self.setWidget(container)
        self.setWidgetResizable(True)

        self._rows: list[dict] = []
        self._loading = False
        self._reload(fk_language=2)

    def _fk_language(self) -> int:
        return 2 if self._lang_combo.currentIndex() == 0 else 1

    def _reload(self, fk_language: int):
        self._loading = True
        self._rows = get_event_types(fk_language)
        self._table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            indent = "    " * r['depth']
            self._table.setItem(i, 0, self._readonly_item(str(r['id'])))
            self._table.setItem(i, 1, self._readonly_item(r['category'] or ''))
            self._table.setItem(i, 2, self._readonly_item(r['parent_label'] or ''))
            self._table.setItem(i, 3, QTableWidgetItem(f"{indent}{r['label'] or ''}"))
            self._table.setItem(i, 4, self._readonly_item(r['code'] or ''))
            active_item = QTableWidgetItem()
            active_item.setFlags(active_item.flags() | Qt.ItemIsUserCheckable)
            active_item.setCheckState(Qt.Checked if r.get('enabled') else Qt.Unchecked)
            self._table.setItem(i, 5, active_item)
        self._loading = False

    @staticmethod
    def _readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @safe_slot("TypesPanel._on_language_changed")
    def _on_language_changed(self, _index: int):
        self._reload(self._fk_language())

    @safe_slot("TypesPanel._on_item_changed")
    def _on_item_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        event_type_id = self._rows[row]['id']
        if item.column() == 5:
            set_event_type_active(event_type_id, item.checkState() == Qt.Checked)
        elif item.column() == 3:
            depth = self._rows[row]['depth']
            new_label = item.text()[len("    " * depth):]
            set_event_type_label(event_type_id, new_label)
```

- [ ] **Step 1b : Ajouter le bouton "Créer un type" (action d'activation bilingue)**

Compléter `LarcConfig/views/panel_types.py` : importer `activate_event_type` et
`QDialog, QFormLayout, QLineEdit` (exceptions autorisées à la règle imports UI), ajouter un
bouton dans `header_row` et le dialogue minimal qu'il ouvre :

```python
from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit
from phibuilder.widgets import M3Button
from LarcConfig.common.db_access import (
    get_event_types, set_event_type_active, set_event_type_label, activate_event_type,
)
```

Dans `__init__`, après `header_row.addWidget(self._lang_combo)` :
```python
        create_btn = M3Button("Créer un type", theme=phi)
        create_btn.clicked.connect(self._on_create_type)
        header_row.addWidget(create_btn)
```

Nouvelle méthode :
```python
    @safe_slot("TypesPanel._on_create_type")
    def _on_create_type(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Créer un type d'événement")
        form = QFormLayout(dlg)
        parent_edit = QLineEdit()
        parent_edit.setPlaceholderText("code du parent (vide = nouvelle racine)")
        suffix_edit = QLineEdit()
        label_fr_edit = QLineEdit()
        label_en_edit = QLineEdit()
        form.addRow("Parent (code) :", parent_edit)
        form.addRow("Suffixe code :", suffix_edit)
        form.addRow("Libellé FR :", label_fr_edit)
        form.addRow("Libellé EN :", label_en_edit)
        ok_btn = M3Button("Créer")
        ok_btn.clicked.connect(dlg.accept)
        form.addRow(ok_btn)
        if dlg.exec() == QDialog.Accepted:
            ok = activate_event_type(
                parent_code=parent_edit.text().strip() or None,
                code_suffix=suffix_edit.text().strip(),
                label_fr=label_fr_edit.text().strip(),
                label_en=label_en_edit.text().strip(),
            )
            if not ok:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Erreur",
                    "Aucun slot potentiel libre sous ce parent, dans l'une des 2 langues.",
                )
            self._reload(self._fk_language())
```

- [ ] **Step 2 : Vérifier au lancement (LarcConfig)**

```bash
cd D:\projets && LARC_LANG=fr .venv\Scripts\python.exe -m LarcConfig
```
Ouvrir le panel "Types d'événements" : le sélecteur de langue doit basculer FR/EN, la colonne
Parent doit afficher le libellé résolu (pas juste l'indentation), cocher/décocher "Actif" doit
persister après un rechargement de langue puis retour, éditer un libellé (double-clic sur la
colonne Libellé) doit se répercuter en base, et "Créer un type" (parent existant, ex.
`absence_school`) doit activer un slot potentiel dans les 2 langues et le faire apparaître au
rechargement.

- [ ] **Step 3 : Commit**

```bash
git add LarcConfig/views/panel_types.py
git commit -m "$(cat <<'EOF'
feat(larcconfig): TypesPanel devient éditable (langue, parent, actif, libellé)

Passe de lecture seule à éditeur : sélecteur de langue (FR/EN), colonne
Parent résolue (répond au besoin "qui est le père de qui"), case Actif et
libellé éditables en place, bouton "Créer un type" (active un slot
potentiel libre dans les 2 langues à la fois — principe gabarit, jamais
d'INSERT).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 : Validation finale — lints, tests, graphify, checklist manuelle

**Files:** aucun fichier de code — validation transverse.

- [ ] **Step 1 : Lints ciblés**

```bash
cd D:\projets
python scripts/lint_qss_hardcoding.py --dir LarcConfig
python scripts/lint_qss_hardcoding.py --dir LarcCommon/larccommon
python scripts/lint_safe_slot.py --dir LarcConfig
python scripts/lint_file_size.py --dir LarcConfig
python scripts/lint_file_size.py --dir LarcCommon
```
Attendu : aucune erreur bloquante introduite par ce plan (des violations pré-existantes
ailleurs dans le monorepo sont acceptables, non liées à ce travail).

- [ ] **Step 2 : Suite de tests complète**

```bash
cd D:\projets\LarcCommon && pytest tests/ -q
cd D:\projets && python -m pytest LarcConfig/tests/ -v
```
Attendu : tous les tests passent, y compris les nouveaux de ce plan.

- [ ] **Step 3 : Régénérer le graphe de connaissances (changement structurel : nouvelle
  colonne, nouvelles fonctions, panel réécrit)**

```bash
cd D:\projets
graphify extract . --code-only --force
graphify cluster-only .
```

- [ ] **Step 4 : Checklist manuelle finale**

- [ ] `EventGeneratorDialog` (LarcSuperviseur) : l'arbre affiche bien la hiérarchie dans la
  langue de la session (`LARC_LANG=en` puis `LARC_LANG=fr`) — OK
- [ ] `LarcConfig` → Types d'événements : bascule FR/EN affiche des arbres différents, colonne
  Parent lisible — OK
- [ ] Décocher "Actif" sur un type FR n'affecte pas son équivalent EN (indépendance confirmée)
  — OK
- [ ] Un événement déjà enregistré (`event_type_config_id` existant) reste lisible après avoir
  désactivé son type dans LarcConfig — OK (aucune donnée orpheline)

- [ ] **Step 5 : Commit final (si des ajustements ont été faits pendant la checklist)**

```bash
git add -A
git status
git commit -m "$(cat <<'EOF'
chore: validation finale types d'événements multilingues + gabarit

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

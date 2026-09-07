# Hiérarchie des types d'événements + vue arbre — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la navigation "un niveau à la fois" de `EventGeneratorDialog` par une vue
scindée (arbre complet + panneau détails), enrichir `larcauth_event_type_config` à 4 niveaux avec
la distinction Absence/Sortie, permettre la validation à un niveau intermédiaire (note masquée
tant qu'une feuille n'est pas atteinte), et corriger les flux d'édition existants qui
contournaient encore la hiérarchie configurable.

**Architecture:** Un nouveau composant générique `M3TreeWidget` (phibuilder) affiche n'importe
quelle hiérarchie ; un composant partagé `EventTypeSelectorWidget` (larccommon) l'enrobe avec
recherche, bouton "Confirmer ce choix" et badge résumé, et devient le point de sélection commun à
la création (`EventGeneratorDialog`) et aux deux flux d'édition (`main_events.py`,
`EventEditDialog`). Une nouvelle colonne `event_type_config_id` (FK vers
`larcauth_event_type_config`) sur `student_event`/`staff_event` fiabilise le lien
événement → nœud (au lieu du texte du chemin, fragile aux renommages).

**Tech Stack:** Python 3.x, PySide6 (Qt6), PostgreSQL (psycopg2, autocommit), pytest.

**Spec:** [docs/superpowers/specs/2026-09-07-event-type-hierarchy-and-tree-ui-design.md](../specs/2026-09-07-event-type-hierarchy-and-tree-ui-design.md)
(inclut la section "Correctif découvert lors de la mise en plan" ajoutée après validation initiale
— lire avant de commencer).

## Global Constraints

- **Principe gabarit** : jamais de `DELETE` sur `larcauth_event_type_config` ni sur ses lignes —
  toujours `UPDATE`/`is_active = FALSE` pour désactiver un code obsolète (CLAUDE.md).
- **Imports UI** : toujours depuis `phibuilder.widgets`, jamais `PySide6.QtWidgets` direct, sauf
  exceptions autorisées (`QMessageBox`, `QApplication`, `QVBoxLayout`, `QHBoxLayout`,
  `QGridLayout`, `QButtonGroup`, `QTableWidgetItem`) — un nouveau widget `phibuilder` peut bien
  sûr subclasser Qt en interne (comme `M3TableWidget` subclasse `QTableWidget`).
- **Zéro hardcoding** : espacements/rayons/couleurs via `ds.*` (`larccommon.design_system.ds`),
  jamais de valeur en dur.
- **`@safe_slot`** obligatoire sur tous les slots Qt connectés à un signal.
- **Pas de saisie libre** : le motif d'un événement est toujours choisi dans l'arbre fermé,
  jamais tapé en texte libre. "Autre" reste une feuille fermée sans champ texte associé.
- **Note conditionnelle** : le champ note n'est visible que si le nœud confirmé par
  l'enseignant n'a **aucun enfant** (feuille, y compris "Autre" explicite). Si le choix s'arrête
  à un nœud intermédiaire, seules la date et l'heure restent visibles.
- **Fichiers > 1000 lignes interdits** (`scripts/lint_file_size.py`).
- Pas de `QTimer.singleShot` pour contourner un bug Qt, pas de `processEvents()`.

---

## Task 1 : Migration DB — hiérarchie 4 niveaux + colonnes de liaison

**Files:**
- Create: `LarcCommon/migrations/2026_09_07_event_type_hierarchy_v2.sql`

**Interfaces:**
- Produces : nouveaux codes `larcauth_event_type_config` listés ci-dessous (consommés par
  `EventTypeConfigService.load_hierarchy()` sans changement de code, cf. Task 2) ; colonnes
  `student_event.event_type_config_id` et `staff_event.event_type_config_id` (INTEGER, nullable,
  `REFERENCES larcauth_event_type_config(id)`), consommées par les Tasks 7-10.

- [ ] **Step 1 : Écrire la migration complète**

```sql
-- Migration: 2026-09-07_event_type_hierarchy_v2
-- Hiérarchie 4 niveaux : distingue Absence / Sortie, ajoute motifs détaillés,
-- supprime la redondance "Incident", relie student_event/staff_event au nœud exact choisi.
-- Additive uniquement : aucun DELETE, aucune suppression de code existant (principe gabarit).

-- ----------------------------------------------------------------------------
-- 0. Élargir la contrainte de catégorie pour accueillir 'sortie'
-- ----------------------------------------------------------------------------
ALTER TABLE larcauth_event_type_config DROP CONSTRAINT IF EXISTS check_category;
ALTER TABLE larcauth_event_type_config ADD CONSTRAINT check_category
    CHECK (category IN ('absence', 'retard', 'evenement', 'sortie', 'custom'));

-- ----------------------------------------------------------------------------
-- 1. Colonnes de liaison event_type_config_id (additives, nullable)
-- ----------------------------------------------------------------------------
ALTER TABLE IF EXISTS student_event
    ADD COLUMN IF NOT EXISTS event_type_config_id INTEGER
    REFERENCES larcauth_event_type_config(id);
CREATE INDEX IF NOT EXISTS idx_student_event_type_config
    ON student_event(event_type_config_id);

ALTER TABLE IF EXISTS staff_event
    ADD COLUMN IF NOT EXISTS event_type_config_id INTEGER
    REFERENCES larcauth_event_type_config(id);
CREATE INDEX IF NOT EXISTS idx_staff_event_type_config
    ON staff_event(event_type_config_id);

-- ----------------------------------------------------------------------------
-- 2. ABSENCE — nouveaux motifs sous absence_school (Maladie déjà existant)
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_mild', 'Légère (rhume, fièvre)', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_mild');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_severe', 'Grave / Hospitalisation', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_severe');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_chronic', 'Chronique (suivi médical)', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_chronic');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_other', 'Autre', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_other');

-- Motif familial (nouveau, sous absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_family', 'Motif familial', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_family');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_family'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('absence_school_family_death', 'Décès'),
    ('absence_school_family_event', 'Événement familial'),
    ('absence_school_family_travel', 'Déplacement'),
    ('absence_school_family_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- Rendez-vous médical (nouveau, sous absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_appointment', 'Rendez-vous médical', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_appointment');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_appointment'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('absence_school_appointment_gp', 'Généraliste'),
    ('absence_school_appointment_specialist', 'Spécialiste'),
    ('absence_school_appointment_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- Motif administratif (nouveau, sous absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_admin', 'Motif administratif', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_admin');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_admin'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('absence_school_admin_process', 'Démarches'),
    ('absence_school_admin_summons', 'Convocation externe'),
    ('absence_school_admin_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- "Autre" direct sous absence_school (absence_school_justified/unjustified existent déjà)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_other', 'Autre', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_other');

UPDATE larcauth_event_type_config SET label = 'Justifiée (sans détail)'
WHERE code = 'absence_school_justified';

-- absence_class : nouveaux motifs (Convoqué / Activité scolaire / Autre), désactivation des anciens
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_class'),
       'student', TRUE, FALSE, TRUE, TRUE
FROM (VALUES
    ('absence_class_summoned', 'Convoqué (direction/administration)'),
    ('absence_class_school_activity', 'Activité scolaire (sport, sortie pédagogique, compétition)'),
    ('absence_class_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

UPDATE larcauth_event_type_config SET is_active = FALSE
WHERE code IN ('absence_class_sick', 'absence_class_justified', 'absence_class_unjustified');

-- ----------------------------------------------------------------------------
-- 3. SORTIE — nouvelle racine (élève présent puis retiré, distinct de Absence)
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie', 'Sortie', 'sortie', NULL, 'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie_class', 'Sortie du cours', 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie'),
       'student,staff', TRUE, FALSE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie_class');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_class'),
       'student,staff', TRUE, v.requires_lieu, TRUE, TRUE
FROM (VALUES
    ('sortie_class_toilets', 'Toilettes', FALSE),
    ('sortie_class_infirmary', 'Infirmerie', TRUE),
    ('sortie_class_office', 'Bureau direction/vie scolaire', TRUE),
    ('sortie_class_forgot_material', 'Matériel oublié', FALSE),
    ('sortie_class_other', 'Autre', FALSE)
) AS v(code, label, requires_lieu)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- Mauvais comportement : student uniquement (le staff n'est pas "sorti" pour ce motif)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie_class_misbehavior', 'Mauvais comportement', 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_class'),
       'student', TRUE, FALSE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie_class_misbehavior');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_class_misbehavior'),
       'student', TRUE, FALSE, TRUE, TRUE
FROM (VALUES
    ('sortie_class_misbehavior_minor', 'Indiscipline légère'),
    ('sortie_class_misbehavior_insolence', 'Insolence'),
    ('sortie_class_misbehavior_verbal', 'Violence verbale'),
    ('sortie_class_misbehavior_physical', 'Violence physique'),
    ('sortie_class_misbehavior_fraud', 'Fraude'),
    ('sortie_class_misbehavior_theft', 'Vol'),
    ('sortie_class_misbehavior_damage', 'Dégradation matériel'),
    ('sortie_class_misbehavior_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie_school', 'Sortie de l''école', 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie_school');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('sortie_school_parent', 'Récupéré par parent/tuteur'),
    ('sortie_school_appointment', 'Rendez-vous médical'),
    ('sortie_school_illness', 'Malaise/renvoyé'),
    ('sortie_school_exception', 'Autorisation exceptionnelle'),
    ('sortie_school_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- ----------------------------------------------------------------------------
-- 4. RETARD — restructuration à 4 niveaux (École / Cours × durée × motif)
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'retard_school', 'Retard à l''école', 'retard',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'),
       'student', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'retard_school');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'retard_class', 'Retard au cours', 'retard',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'),
       'student', TRUE, FALSE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'retard_class');

-- Reparenter les durées existantes (retard_5min/15min/30min) sous retard_school
UPDATE larcauth_event_type_config SET
    parent_id = (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_school'),
    label = '5 min'
WHERE code = 'retard_5min';

UPDATE larcauth_event_type_config SET
    parent_id = (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_school'),
    label = '15 min'
WHERE code = 'retard_15min';

UPDATE larcauth_event_type_config SET
    parent_id = (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_school'),
    label = '30 min et +'
WHERE code = 'retard_30min';

-- Motifs sous chaque durée "école" (retard_5min/15min/30min) + nouvelles durées "cours"
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'retard', v.parent_id, 'student', TRUE, FALSE, v.requires_subject, TRUE
FROM (
    SELECT 'retard_5min_' || m.suffix AS code, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_5min') AS parent_id,
           FALSE AS requires_subject
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
    UNION ALL
    SELECT 'retard_15min_' || m.suffix, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_15min'), FALSE
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
    UNION ALL
    SELECT 'retard_30min_' || m.suffix, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_30min'), FALSE
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'retard',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_class'),
       'student', TRUE, FALSE, TRUE, TRUE
FROM (VALUES
    ('retard_class_5', '5 min'),
    ('retard_class_15plus', '15 min et +')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'retard', v.parent_id, 'student', TRUE, FALSE, TRUE, TRUE
FROM (
    SELECT 'retard_class_5_' || m.suffix AS code, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_class_5') AS parent_id
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
    UNION ALL
    SELECT 'retard_class_15plus_' || m.suffix, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_class_15plus')
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- ----------------------------------------------------------------------------
-- 5. ÉVÉNEMENT — Comportement (Positif/Négatif/Matériel oublié/Manque de travail), Santé
--    "Incident" supprimé (redondant avec Comportement > Négatif)
-- ----------------------------------------------------------------------------
UPDATE larcauth_event_type_config SET is_active = FALSE WHERE code = 'event_incident';

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_positive', 'Positif', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_positive');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior_positive'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_behavior_positive_merit', 'Mérite/Encouragement'),
    ('event_behavior_positive_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_negative', 'Négatif', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_negative');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior_negative'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_behavior_negative_minor', 'Indiscipline légère'),
    ('event_behavior_negative_insolence', 'Insolence'),
    ('event_behavior_negative_verbal', 'Violence verbale'),
    ('event_behavior_negative_physical', 'Violence physique'),
    ('event_behavior_negative_fraud', 'Fraude'),
    ('event_behavior_negative_theft', 'Vol'),
    ('event_behavior_negative_damage', 'Dégradation matériel'),
    ('event_behavior_negative_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_forgot_material', 'Matériel oublié (élève continue de travailler)', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_forgot_material');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_lack_of_work', 'Manque de travail', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_lack_of_work');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior_lack_of_work'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_behavior_lack_of_work_homework', 'Devoirs non faits'),
    ('event_behavior_lack_of_work_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_health'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_health_illness', 'Malaise'),
    ('event_health_injury', 'Blessure'),
    ('event_health_emergency', 'Urgence médicale'),
    ('event_health_pai', 'Suivi PAI'),
    ('event_health_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);
```

- [ ] **Step 2 : Appliquer la migration sur une copie locale de NewLarcDB et vérifier**

```bash
psql -U postgres -h 127.0.0.1 -d NewLarcDB -f LarcCommon/migrations/2026_09_07_event_type_hierarchy_v2.sql
```

Vérifications :
```sql
-- Racines : evenement, absence, retard, sortie (4)
SELECT code, label FROM larcauth_event_type_config WHERE parent_id IS NULL AND is_active;

-- Aucun doublon de code
SELECT code, count(*) FROM larcauth_event_type_config GROUP BY code HAVING count(*) > 1;

-- event_incident bien désactivé, plus dans l'arbre actif
SELECT is_active FROM larcauth_event_type_config WHERE code = 'event_incident';  -- FALSE

-- Colonnes de liaison présentes
SELECT column_name FROM information_schema.columns
WHERE table_name IN ('student_event','staff_event') AND column_name = 'event_type_config_id';

-- Ré-exécution idempotente : relancer le script une 2e fois ne doit lever aucune erreur
-- ni dupliquer de lignes (vérifier count(*) stable avant/après).
```

- [ ] **Step 3 : Commit**

```bash
git add LarcCommon/migrations/2026_09_07_event_type_hierarchy_v2.sql
git commit -m "$(cat <<'EOF'
feat(db): hiérarchie 4 niveaux Absence/Sortie/Retard/Événement + liaison event_type_config_id

Migration additive (principe gabarit, aucun DELETE) : ajoute la racine Sortie
distincte d'Absence, détaille les motifs (maladie/familial/RDV médical/administratif,
mauvais comportement dupliqué sous Sortie ET Événement), désactive "Incident"
(redondant avec Comportement > Négatif) et les anciens motifs d'absence_class.
Ajoute student_event/staff_event.event_type_config_id pour relier fiablement un
événement à son nœud exact (au lieu du texte du chemin, fragile aux renommages).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 : Test de régression `EventTypeConfigService` sur 4 niveaux

**Files:**
- Create: `LarcCommon/tests/test_event_type_service.py`

**Interfaces:**
- Consumes: `larccommon.event_type_service.EventTypeConfigService`, `MemberType`,
  `larccommon.database.db` (monkeypatché).
- Produces: rien de nouveau — test de régression pur (le service n'a pas besoin de changer,
  cf. spec "Composants réutilisés sans changement").

- [ ] **Step 1 : Écrire le test (faux curseur retournant 4 niveaux)**

```python
"""Régression : EventTypeConfigService doit gérer 4 niveaux de hiérarchie sans changement de code."""
from larccommon.event_type_service import EventTypeConfigService, MemberType


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self._rows


class FakeConn:
    closed = False

    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)


# id, code, label, category, icon_code, parent_id, applicable_to,
# requires_validation, requires_lieu, requires_subject
FOUR_LEVEL_ROWS = [
    (1, 'absence', 'Absence', 'absence', None, None, 'student,staff', True, False, False),
    (2, 'absence_school', "Absence de l'école", 'absence', None, 1, 'student,staff', True, False, False),
    (3, 'absence_school_sick', 'Maladie', 'absence', None, 2, 'student,staff', True, False, False),
    (4, 'absence_school_sick_mild', 'Légère', 'absence', None, 3, 'student,staff', True, False, False),
]


class TestEventTypeConfigServiceFourLevels:
    def setup_method(self):
        # Reset du singleton entre les tests (cache de classe partagé)
        EventTypeConfigService._instance = None

    def test_load_hierarchy_builds_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        hierarchies = service.load_hierarchy(force_refresh=True)

        assert "absence" in hierarchies
        root = hierarchies["absence"]
        level2 = root.children[0]
        level3 = level2.children[0]
        level4 = level3.children[0]
        assert level4.code == "absence_school_sick_mild"
        assert level4.children == []

    def test_get_path_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(force_refresh=True)
        leaf = service.get_by_code("absence_school_sick_mild")
        assert service.get_path(leaf) == "Absence > Absence de l'école > Maladie > Légère"

    def test_filter_applicable_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(force_refresh=True)
        result = service.filter_applicable(MemberType.STUDENT)
        assert "absence" in result

    def test_get_by_id_returns_intermediate_node(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(force_refresh=True)
        intermediate = service.get_by_id(3)  # absence_school_sick, a des enfants
        assert intermediate.code == "absence_school_sick"
        assert len(intermediate.children) == 1
```

- [ ] **Step 2 : Lancer et vérifier que ça passe**

```bash
cd D:\projets\LarcCommon && pytest tests/test_event_type_service.py -v
```
Attendu : 4 tests PASS (le service existant gère déjà N niveaux, aucune modification de
`event_type_service.py` n'est nécessaire pour ce test — c'est un test de non-régression).

- [ ] **Step 3 : Commit**

```bash
git add LarcCommon/tests/test_event_type_service.py
git commit -m "$(cat <<'EOF'
test: régression EventTypeConfigService sur hiérarchie à 4 niveaux

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 : `M3TreeWidget` — composant arbre générique (phibuilder)

**Files:**
- Create: `LarcCommon/phibuilder/widgets/tree.py`
- Test: `LarcCommon/tests/test_m3_tree_widget.py`

**Interfaces:**
- Produces: `M3TreeWidget(QTreeWidget)` avec :
  - `set_data(roots: list, children_fn: Callable[[object], list], label_fn: Callable[[object], str], icon_fn: Callable[[object], QIcon] | None = None)`
  - `current_node() -> object | None`
  - `select_node(node, path: list)` — déplie et sélectionne un nœud à partir de son chemin racine→nœud
  - `filter_text(text: str)` — filtre/replie les branches ne correspondant pas
  - Signal `node_activated = Signal(object)` (Entrée/Espace/double-clic sur l'item courant)
- Consumes: rien de spécifique à `EventTypeNode` — widget générique réutilisable (n'importe quel
  objet avec une fonction enfants/label).

- [ ] **Step 1 : Écrire le test (pyest-qt non disponible ici → test logique pur sans `qtbot`,
  instancie directement les widgets comme le fait le reste du repo)**

```python
"""Tests M3TreeWidget — arbre générique (hiérarchie, filtre, sélection)."""
import pytest
from PySide6.QtWidgets import QApplication

from phibuilder.widgets.tree import M3TreeWidget


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class Node:
    def __init__(self, code, label, children=None):
        self.code = code
        self.label = label
        self.children = children or []


def make_tree():
    leaf_a = Node("a", "Alpha")
    leaf_b = Node("b", "Beta")
    root = Node("root", "Racine", [leaf_a, leaf_b])
    return root, leaf_a, leaf_b


class TestM3TreeWidget:
    def test_set_data_builds_items(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        assert widget.topLevelItemCount() == 1
        assert widget.topLevelItem(0).childCount() == 2

    def test_current_node_returns_underlying_object(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        item = widget.topLevelItem(0).child(0)
        widget.setCurrentItem(item)
        assert widget.current_node() is leaf_a

    def test_filter_text_hides_non_matching_leaves(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        widget.filter_text("alpha")
        root_item = widget.topLevelItem(0)
        assert root_item.child(0).isHidden() is False  # Alpha matches
        assert root_item.child(1).isHidden() is True   # Beta hidden

    def test_filter_text_empty_shows_everything(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        widget.filter_text("alpha")
        widget.filter_text("")
        root_item = widget.topLevelItem(0)
        assert root_item.child(0).isHidden() is False
        assert root_item.child(1).isHidden() is False

    def test_select_node_by_path_expands_and_selects(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        widget.select_node(leaf_a, path=[root, leaf_a])
        assert widget.current_node() is leaf_a
        assert widget.topLevelItem(0).isExpanded()
```

- [ ] **Step 2 : Lancer et vérifier que ça échoue (module absent)**

```bash
cd D:\projets\LarcCommon && pytest tests/test_m3_tree_widget.py -v
```
Attendu : FAIL avec `ModuleNotFoundError: No module named 'phibuilder.widgets.tree'`

- [ ] **Step 3 : Implémenter `M3TreeWidget`**

```python
"""M3TreeWidget: Material Design 3 generic tree widget.

Features:
- Hiérarchie générique (fonction enfants/label/icône fournie par l'appelant)
- Recherche/filtre : filter_text() masque les branches non correspondantes, déplie les parents des correspondances
- Navigation clavier : flèches (natif QTreeWidget), Entrée (déplier/replier ou activer une feuille), Espace (activer), Echap (désélectionner)
- Focus visible : 2px outline
- Accessibilité : setData(Qt.AccessibleTextRole, ...) par item
- Touch target : 44px minimum par ligne (QSS)
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QSizePolicy, QTreeWidget, QTreeWidgetItem

from phibuilder.theme import Theme


class M3TreeWidget(QTreeWidget):
    """Arbre M3 générique avec recherche, clavier et accessibilité."""

    node_activated = Signal(object)

    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._children_fn: Callable[[object], list] = lambda n: []
        self._label_fn: Callable[[object], str] = lambda n: str(n)
        self._icon_fn: Optional[Callable[[object], QIcon]] = None

        self.setHeaderHidden(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAccessibleName("Arbre de types d'événements")
        self.setAccessibleDescription(
            "Flèches pour naviguer, Entrée pour déplier/replier, Espace pour confirmer le choix"
        )

        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, t = self._theme.colors, self._theme.typo

        self.setStyleSheet(f"""
M3TreeWidget {{
    background-color: {c.surface};
    border: 1px solid {c.outline};
    border-radius: 8px;
    outline: none;
    font-family: '{t.family}';
    font-size: {t.body_medium.size}px;
    color: {c.on_surface};
}}
M3TreeWidget::item {{
    padding: 8px;
    min-height: 32px;
}}
M3TreeWidget::item:selected {{
    background-color: {c.primary_container};
    color: {c.on_primary_container};
}}
M3TreeWidget::item:hover {{
    background-color: {c.surface_container_highest};
}}
M3TreeWidget::item:focus {{
    outline: 2px solid {c.primary};
    outline-offset: 0px;
}}
""")

    def set_data(
        self,
        roots: list,
        children_fn: Callable[[object], list],
        label_fn: Callable[[object], str],
        icon_fn: Optional[Callable[[object], QIcon]] = None,
    ):
        """Charge la hiérarchie. `children_fn`/`label_fn` sont appliqués à chaque nœud."""
        self._children_fn = children_fn
        self._label_fn = label_fn
        self._icon_fn = icon_fn
        self.clear()
        for root in roots:
            self._add_node(root, self.invisibleRootItem())
        self.expandToDepth(0)

    def _add_node(self, node: object, parent_item: QTreeWidgetItem) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent_item)
        label = self._label_fn(node)
        item.setText(0, label)
        item.setData(0, Qt.UserRole, node)
        item.setData(0, Qt.AccessibleTextRole, label)
        if self._icon_fn:
            ic = self._icon_fn(node)
            if ic:
                item.setIcon(0, ic)
        for child in self._children_fn(node):
            self._add_node(child, item)
        return item

    def current_node(self) -> Optional[object]:
        item = self.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def select_node(self, node: object, path: list):
        """Déplie le chemin racine→nœud puis sélectionne le nœud."""
        self._select_recursive(self.invisibleRootItem(), path, 0, node)

    def _select_recursive(self, parent_item: QTreeWidgetItem, path: list, depth: int, target):
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_node = child_item.data(0, Qt.UserRole)
            if depth < len(path) and child_node is path[depth]:
                child_item.setExpanded(True)
                if child_node is target:
                    self.setCurrentItem(child_item)
                    self.scrollToItem(child_item)
                    return True
                if self._select_recursive(child_item, path, depth + 1, target):
                    return True
        return False

    def filter_text(self, text: str):
        """Masque les branches ne contenant aucune correspondance ; déplie les parents des matches."""
        text = (text or "").strip().lower()
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            self._filter_recursive(root.child(i), text)

    def _filter_recursive(self, item: QTreeWidgetItem, text: str) -> bool:
        self_match = (not text) or (text in item.text(0).lower())
        child_match = False
        for i in range(item.childCount()):
            if self._filter_recursive(item.child(i), text):
                child_match = True
        visible = self_match or child_match
        item.setHidden(not visible)
        if text and child_match:
            item.setExpanded(True)
        return visible

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            if item and item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
            elif item:
                self.node_activated.emit(self.current_node())
            event.accept()
        elif event.key() == Qt.Key_Space:
            node = self.current_node()
            if node is not None:
                self.node_activated.emit(node)
            event.accept()
        elif event.key() == Qt.Key_Escape:
            self.clearSelection()
            event.accept()
        else:
            super().keyPressEvent(event)

    def refresh(self):
        """Restyle based on current theme."""
        self._update_style()
```

- [ ] **Step 4 : Lancer et vérifier que ça passe**

```bash
cd D:\projets\LarcCommon && pytest tests/test_m3_tree_widget.py -v
```
Attendu : 5 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add LarcCommon/phibuilder/widgets/tree.py LarcCommon/tests/test_m3_tree_widget.py
git commit -m "$(cat <<'EOF'
feat(phibuilder): ajoute M3TreeWidget, arbre M3 générique avec recherche et clavier

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 : Export `M3TreeWidget` depuis `phibuilder.widgets`

**Files:**
- Modify: `LarcCommon/phibuilder/widgets/__init__.py`

**Interfaces:**
- Produces: `from phibuilder.widgets import M3TreeWidget` (utilisé par la Task 5).

- [ ] **Step 1 : Ajouter l'import et l'export**

```python
from phibuilder.widgets.tree import M3TreeWidget
```
Ajouter après la ligne `from phibuilder.widgets.scrollarea import AdaptiveScrollArea` et ajouter
`"M3TreeWidget"` à la liste `__all__`.

- [ ] **Step 2 : Vérifier l'import**

```bash
cd D:\projets && python -c "from phibuilder.widgets import M3TreeWidget; print(M3TreeWidget)"
```
Attendu : affiche `<class 'phibuilder.widgets.tree.M3TreeWidget'>` sans erreur.

- [ ] **Step 3 : Commit**

```bash
git add LarcCommon/phibuilder/widgets/__init__.py
git commit -m "$(cat <<'EOF'
feat(phibuilder): exporte M3TreeWidget depuis phibuilder.widgets

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 : `EventTypeSelectorWidget` — composant partagé (arbre + confirmation + badge)

**Files:**
- Create: `LarcCommon/larccommon/dialogs/event_type_selector.py`
- Test: `LarcCommon/tests/test_event_type_selector.py`

**Interfaces:**
- Consumes: `phibuilder.widgets.M3TreeWidget`, `phibuilder.widgets.{M3TextField, M3Button, M3Card, M3Label}`,
  `larccommon.event_type_service.{EventTypeNode, EventTypeConfigService, MemberType}`.
- Produces:
  - `EventTypeSelectorWidget(QWidget)` avec :
    - `__init__(hierarchies: dict[str, EventTypeNode], parent=None)`
    - Signal `type_confirmed = Signal(object)` — émis avec l'`EventTypeNode` confirmé (feuille
      ou intermédiaire).
    - `preselect(node: EventTypeNode)` — déplie/sélectionne un nœud existant (flux d'édition).
    - `is_leaf(node: EventTypeNode) -> bool` (méthode statique) : `len(node.children) == 0`,
      utilisée par les appelants (Tasks 7-9) pour décider d'afficher ou non le champ note.

- [ ] **Step 1 : Écrire le test**

```python
"""Tests EventTypeSelectorWidget — arbre + confirmation partagés (création + édition)."""
import pytest
from PySide6.QtWidgets import QApplication

from larccommon.dialogs.event_type_selector import EventTypeSelectorWidget
from larccommon.event_type_service import EventTypeNode


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_hierarchy():
    leaf = EventTypeNode(
        id=3, code="absence_school_sick_mild", label="Légère", category="absence",
        icon_code=None, parent_id=2, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
    )
    mid = EventTypeNode(
        id=2, code="absence_school_sick", label="Maladie", category="absence",
        icon_code=None, parent_id=1, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
        children=[leaf],
    )
    root = EventTypeNode(
        id=1, code="absence", label="Absence", category="absence",
        icon_code=None, parent_id=None, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
        children=[mid],
    )
    return {"absence": root}, root, mid, leaf


class TestEventTypeSelectorWidget:
    def test_is_leaf_true_for_node_without_children(self):
        _, _, _, leaf = make_hierarchy()
        assert EventTypeSelectorWidget.is_leaf(leaf) is True

    def test_is_leaf_false_for_node_with_children(self):
        _, _, mid, _ = make_hierarchy()
        assert EventTypeSelectorWidget.is_leaf(mid) is False

    def test_confirm_button_disabled_until_selection(self):
        hierarchies, *_ = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        assert widget._confirm_btn.isEnabled() is False

    def test_selecting_node_enables_confirm_and_emits_on_click(self, qtbot=None):
        hierarchies, root, mid, leaf = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        received = []
        widget.type_confirmed.connect(received.append)

        top_item = widget._tree.topLevelItem(0)
        child_item = top_item.child(0)
        widget._tree.setCurrentItem(child_item)
        assert widget._confirm_btn.isEnabled() is True

        widget._confirm_btn.click()
        assert received == [mid]

    def test_preselect_expands_and_selects_existing_node(self):
        hierarchies, root, mid, leaf = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        widget.preselect(leaf)
        assert widget._tree.current_node() is leaf
```

- [ ] **Step 2 : Lancer et vérifier que ça échoue**

```bash
cd D:\projets\LarcCommon && pytest tests/test_event_type_selector.py -v
```
Attendu : FAIL — `ModuleNotFoundError: No module named 'larccommon.dialogs.event_type_selector'`

- [ ] **Step 3 : Implémenter `EventTypeSelectorWidget`**

```python
"""EventTypeSelectorWidget — sélecteur hiérarchique partagé (création ET édition d'événement).

Composant unique consommé par EventGeneratorDialog (création) et par les flux d'édition
(main_events.py, EventEditDialog) — évite de dupliquer la logique arbre + recherche +
confirmation à chaque endroit où un type d'événement doit être choisi.
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from larccommon.design_system import ds
from larccommon.event_type_service import EventTypeNode, event_type_service
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import M3Button, M3Card, M3Label, M3TextField, M3TreeWidget
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant


class EventTypeSelectorWidget(QWidget):
    """Arbre de types d'événements + recherche + bouton de confirmation + badge résumé."""

    type_confirmed = Signal(object)  # EventTypeNode

    def __init__(self, hierarchies: Dict[str, EventTypeNode], parent=None):
        super().__init__(parent)
        self._hierarchies = hierarchies
        self._roots = list(hierarchies.values())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_sm)

        self._search = M3TextField(placeholder=_("event.tree_search_placeholder"))
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._tree = M3TreeWidget(theme=theme_manager.phi_theme)
        self._tree.setMinimumHeight(ds.space_xxl * 3)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.node_activated.connect(self._on_node_activated)
        self._tree.set_data(
            self._roots,
            children_fn=lambda n: n.children,
            label_fn=lambda n: n.label,
        )
        layout.addWidget(self._tree, 1)

        self._badge = M3Card(variant=CardVariant.FILLED, parent=self)
        badge_layout = self._badge.content_layout()
        badge_layout.setContentsMargins(ds.space_md, ds.space_xs, ds.space_md, ds.space_xs)
        self._badge_text = M3Label("", style="body_medium")
        self._badge_text.setWordWrap(True)
        badge_layout.addWidget(self._badge_text)
        self._badge.hide()
        layout.addWidget(self._badge)

        self._confirm_btn = M3Button(_("event.confirm_choice"), variant=ButtonVariant.FILLED)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm_clicked)
        layout.addWidget(self._confirm_btn)

    @staticmethod
    def is_leaf(node: EventTypeNode) -> bool:
        """Un nœud est une feuille (y compris 'Autre') s'il n'a aucun enfant."""
        return len(node.children) == 0

    @safe_slot("EventTypeSelectorWidget._on_search_changed")
    def _on_search_changed(self, text: str):
        self._tree.filter_text(text)

    @safe_slot("EventTypeSelectorWidget._on_selection_changed")
    def _on_selection_changed(self):
        node = self._tree.current_node()
        self._confirm_btn.setEnabled(node is not None)
        if node is not None:
            self._badge_text.setText(event_type_service.get_path(node))
            self._badge.show()
        else:
            self._badge.hide()

    @safe_slot("EventTypeSelectorWidget._on_node_activated")
    def _on_node_activated(self, node: EventTypeNode):
        """Espace/Entrée sur une feuille = raccourci clavier équivalent au bouton Confirmer."""
        if node is not None and self.is_leaf(node):
            self.type_confirmed.emit(node)

    @safe_slot("EventTypeSelectorWidget._on_confirm_clicked")
    def _on_confirm_clicked(self):
        node = self._tree.current_node()
        if node is not None:
            self.type_confirmed.emit(node)

    def preselect(self, node: EventTypeNode):
        """Déplie/sélectionne un nœud existant (rouverture en édition)."""
        # Reconstruit le chemin d'objets EventTypeNode racine→nœud pour M3TreeWidget.select_node
        chain = []
        current = node
        while current is not None:
            chain.insert(0, current)
            current = event_type_service.get_by_id(current.parent_id) if current.parent_id else None
        self._tree.select_node(node, chain)
        self._on_selection_changed()
```

- [ ] **Step 4 : Lancer et vérifier que ça passe**

```bash
cd D:\projets\LarcCommon && pytest tests/test_event_type_selector.py -v
```
Attendu : 4 tests PASS.

- [ ] **Step 5 : Ajouter les clés de traduction manquantes**

Dans `LarcCommon/larccommon/l10n/fr.json`, ajouter (à côté des clés `event.*` existantes, ligne
~148) :
```json
"event.tree_search_placeholder": "Rechercher un type...",
"event.confirm_choice": "Confirmer ce choix",
```
Dans `LarcCommon/larccommon/l10n/en.json`, ajouter les équivalents :
```json
"event.tree_search_placeholder": "Search a type...",
"event.confirm_choice": "Confirm this choice",
```

- [ ] **Step 6 : Commit**

```bash
git add LarcCommon/larccommon/dialogs/event_type_selector.py LarcCommon/tests/test_event_type_selector.py LarcCommon/larccommon/l10n/fr.json LarcCommon/larccommon/l10n/en.json
git commit -m "$(cat <<'EOF'
feat(larccommon): EventTypeSelectorWidget partagé (arbre + confirmation + badge)

Composant unique réutilisé par la création et les deux flux d'édition d'événement,
pour permettre la validation à n'importe quel niveau de la hiérarchie.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 : Exporter `EventTypeSelectorWidget` depuis `larccommon.dialogs`

**Files:**
- Modify: `LarcCommon/larccommon/dialogs/__init__.py`

**Interfaces:**
- Produces: `from larccommon.dialogs import EventTypeSelectorWidget` (utilisé par Tasks 8-9).

- [ ] **Step 1 : Ajouter l'export**

```python
"""Dialogs module — common dialogs for LARC applications."""

from larccommon.dialogs.event_generator_dialog import (
    EventGeneratorDialog,
    EventData,
    MemberType,
)
from larccommon.dialogs.event_type_selector import EventTypeSelectorWidget

__all__ = [
    "EventGeneratorDialog",
    "EventData",
    "MemberType",
    "EventTypeSelectorWidget",
]
```

- [ ] **Step 2 : Vérifier l'import**

```bash
cd D:\projets && python -c "from larccommon.dialogs import EventTypeSelectorWidget; print(EventTypeSelectorWidget)"
```

- [ ] **Step 3 : Commit**

```bash
git add LarcCommon/larccommon/dialogs/__init__.py
git commit -m "$(cat <<'EOF'
feat(larccommon): exporte EventTypeSelectorWidget depuis larccommon.dialogs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 : Refonte `EventGeneratorDialog` en vue scindée

**Files:**
- Modify: `LarcCommon/larccommon/dialogs/event_generator_dialog.py`

**Interfaces:**
- Consumes: `EventTypeSelectorWidget` (Task 5), `phibuilder.widgets.M3Splitter`.
- Produces: `EventData` gagne un champ `type_id: int` (id du nœud confirmé — consommé par
  Tasks 8/10 pour peupler `event_type_config_id`). Le champ note n'apparaît que si
  `EventTypeSelectorWidget.is_leaf(selected_node)` est vrai.

- [ ] **Step 1 : Ajouter `type_id` à `EventData` et remplacer la navigation pas-à-pas par la vue
  scindée**

Remplacer entièrement le contenu de `event_generator_dialog.py` par :

```python
"""EventGeneratorDialog — Wizard polymorphe pour créer événements (Student/Staff).

Vue scindée : arbre complet des types à gauche (EventTypeSelectorWidget), formulaire
date/heure/lieu/matière/note à droite. Le professeur peut valider à n'importe quel
niveau de l'arbre ; le champ note n'apparaît que si le choix atteint une feuille.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QDate, QTime, Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QMessageBox,
    QDateEdit,
    QTimeEdit,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.event_type_service import EventTypeNode, MemberType, event_type_service
from larccommon.dialogs.event_type_selector import EventTypeSelectorWidget
from larccommon.l10n import _
from larccommon.logger import log
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.widgets import M3Button, M3Card, M3Label, M3Splitter, M3TextField
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant


@dataclass
class EventData:
    """Résultat du wizard : données à insérer en base."""

    member_id: int  # student_id ou staff_id
    member_type: MemberType
    type_code: str  # Code de larcauth_event_type_config
    type_id: int  # id de larcauth_event_type_config — pour event_type_config_id
    type_path: str  # Chemin lisible : "Absence > Absence de l'école > Maladie"
    event_at: str  # Format ISO : "2026-09-05T14:30:00"
    lieu_label: Optional[str] = None
    subject_label: Optional[str] = None
    note: str = ""
    created_location: str = "intranet"  # "intranet" ou "cloud"


class EventGeneratorDialog(ThemedDialog):
    """
    Wizard polymorphe pour créer événements (Student ou Staff).

    Vue scindée : EventTypeSelectorWidget (gauche) + formulaire (droite).
    Émet Signal(EventData) → caller insère en base.
    """

    event_created = Signal(EventData)

    def __init__(self, member_id: int, member_type: MemberType, parent=None):
        super().__init__(parent)
        self._member_id = member_id
        self._member_type = member_type
        self._selected_node: Optional[EventTypeNode] = None
        self._selected_lieu_label: str = ""
        self._selected_subject: str = ""
        self._locations: list = []

        self._selector: Optional[EventTypeSelectorWidget] = None
        self._detail_panel: Optional[QWidget] = None
        self._date_edit: Optional[QDateEdit] = None
        self._time_edit: Optional[QTimeEdit] = None
        self._note_input: Optional[M3TextField] = None
        self._note_label: Optional[M3Label] = None
        self._validate_btn: Optional[M3Button] = None

        self._type_hierarchies = event_type_service.filter_applicable(member_type)
        if not self._type_hierarchies:
            log(f"EventGeneratorDialog: aucun type pour {member_type.value}")

        member_label = _("event.student") if member_type == MemberType.STUDENT else _("event.staff")
        self.setWindowTitle(f"{member_label} {member_id}")
        self.setMinimumWidth(ds.window_width * 9 // 10)
        self.setMinimumHeight(ds.window_height * 3 // 4)

        self._load_locations()
        self._init_ui()
        ds.theme_changed.connect(self._restyle_all)
        self._restyle_all()

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            EventGeneratorDialog#evt_root {{
                background: {p.surface};
            }}
            QDateEdit, QTimeEdit {{
                padding: {ds.space_md}px;
                border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
                font-size: {s(13)}px;
                background: {p.surface};
                color: {p.text_strong};
                font-weight: bold;
            }}
        """

    @safe_slot("EventGeneratorDialog._restyle_all")
    def _restyle_all(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass

    def _load_locations(self):
        try:
            conn = db.server_conn
            if not conn:
                return
            cur = conn.cursor()
            cur.execute("SELECT lieu_id, site_id, lieu_name FROM larcauth_lieu WHERE is_active = TRUE")
            self._locations = cur.fetchall()
        except Exception as e:
            log(f"EventGeneratorDialog._load_locations: {e}")
            self._locations = []

    def _init_ui(self):
        self.setObjectName("evt_root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)

        splitter = M3Splitter(Qt.Horizontal, theme=theme_manager.phi_theme)

        self._selector = EventTypeSelectorWidget(self._type_hierarchies)
        self._selector.type_confirmed.connect(self._on_type_confirmed)
        splitter.addWidget(self._selector)

        self._detail_panel = self._build_detail_panel()
        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 35)
        splitter.setStretchFactor(1, 65)

        outer.addWidget(splitter, 1)

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        fl = QVBoxLayout(panel)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(ds.space_md)

        card = M3Card(variant=CardVariant.ELEVATED)
        cl = card.content_layout()
        cl.setSpacing(ds.space_md)

        dr = QHBoxLayout()
        dr.setSpacing(ds.space_md)
        dr.addWidget(M3Label(_("event.date"), style="body_medium"))
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dddd dd MMMM yyyy")
        dr.addWidget(self._date_edit, 2)
        dr.addWidget(M3Label(_("event.time"), style="body_medium"))
        self._time_edit = QTimeEdit(QTime.currentTime())
        self._time_edit.setDisplayFormat("HH:mm")
        dr.addWidget(self._time_edit, 1)
        cl.addLayout(dr)

        self._note_label = M3Label(_("event.note"), style="body_medium")
        self._note_input = M3TextField(placeholder=_("event.note_placeholder"))
        self._note_input.setMaxLength(200)
        cl.addWidget(self._note_label)
        cl.addWidget(self._note_input)
        self._note_label.hide()
        self._note_input.hide()

        fl.addWidget(card, 1)
        fl.addStretch()

        ar = QHBoxLayout()
        ar.addStretch()
        cb = M3Button(_("common.button.cancel"), variant=ButtonVariant.OUTLINED)
        cb.clicked.connect(self.reject)
        ar.addWidget(cb)
        self._validate_btn = M3Button(_("event.validate_button"), variant=ButtonVariant.FILLED)
        self._validate_btn.setEnabled(False)
        self._validate_btn.clicked.connect(self._on_validate)
        ar.addWidget(self._validate_btn)
        fl.addLayout(ar)

        return panel

    @safe_slot("EventGeneratorDialog._on_type_confirmed")
    def _on_type_confirmed(self, node: EventTypeNode):
        """Le professeur a cliqué 'Confirmer ce choix' (feuille ou nœud intermédiaire)."""
        self._selected_node = node
        self._validate_btn.setEnabled(True)

        is_leaf = EventTypeSelectorWidget.is_leaf(node)
        self._note_label.setVisible(is_leaf)
        self._note_input.setVisible(is_leaf)
        if not is_leaf:
            self._note_input.clear()

    def _check_working_day(self) -> bool:
        try:
            conn = db.server_conn
            if not conn:
                return True
            date = self._date_edit.date().toPython()
            cur = conn.cursor()
            cur.execute("SELECT working_day FROM larcauth_agenda WHERE agenda_date = %s", (date,))
            row = cur.fetchone()
            return bool(row[0]) if row else True
        except Exception as e:
            log(f"EventGeneratorDialog._check_working_day: {e}")
            return True

    def _check_active_term(self) -> bool:
        try:
            conn = db.server_conn
            if not conn:
                return True
            cur = conn.cursor()
            cur.execute("SELECT current_term_number FROM larcauth_academicyear LIMIT 1")
            return bool(cur.fetchone())
        except Exception as e:
            log(f"EventGeneratorDialog._check_active_term: {e}")
            return True

    def _get_datetime_iso(self) -> str:
        date = self._date_edit.date().toPython()
        time = self._time_edit.time().toPython()
        return f"{date}T{time}"

    @safe_slot("EventGeneratorDialog._on_validate")
    def _on_validate(self):
        if not self._check_working_day():
            QMessageBox.warning(self, _("event.error"), _("event.error_not_working_day"))
            return
        if not self._check_active_term():
            QMessageBox.warning(self, _("event.error"), _("event.error_inactive_term"))
            return
        if not self._selected_node:
            QMessageBox.warning(self, _("event.error"), _("event.error_no_type"))
            return

        node = self._selected_node
        is_leaf = EventTypeSelectorWidget.is_leaf(node)

        event_data = EventData(
            member_id=self._member_id,
            member_type=self._member_type,
            type_code=node.code,
            type_id=node.id,
            type_path=event_type_service.get_path(node),
            event_at=self._get_datetime_iso(),
            lieu_label=self._selected_lieu_label if node.requires_lieu else None,
            subject_label=self._selected_subject if node.requires_subject else None,
            note=(self._note_input.text() if is_leaf and self._note_input else ""),
            created_location="intranet",
        )

        self.event_created.emit(event_data)
        self.accept()
```

  Note : le choix de lieu/matière (`_selected_lieu_label`/`_selected_subject`) reste vide dans
  cette passe — ils n'étaient déjà pas branchés dans la version pas-à-pas d'origine (aucun widget
  ne les renseignait, seul `requires_lieu`/`requires_subject` conditionnait leur transmission).
  Ce n'est pas une régression introduite par ce refactor ; en laisser la résolution hors scope
  (comme dans le code existant) évite d'élargir le plan à un sujet non demandé par la spec.

- [ ] **Step 2 : Test manuel — vue scindée**

Lancer `python -m LarcSuperviseur`, ouvrir la fiche d'un élève, créer un événement :
- L'arbre complet (Absence/Sortie/Retard/Événement) est visible à gauche dès l'ouverture.
- Taper dans la recherche filtre les branches en temps réel.
- Cliquer sur "Absence > Absence de l'école > Maladie" (nœud intermédiaire) puis "Confirmer ce
  choix" : le champ note doit être **masqué**, seuls date/heure restent visibles, bouton Valider
  actif.
- Redescendre jusqu'à "Légère" (feuille) et confirmer : le champ note **réapparaît**.
- Valider : l'événement est inséré (vérifier dans `LarcSuperviseur/views/main_events.py`, Task 8
  pas encore appliquée à ce stade → `type_id` est calculé mais pas encore persisté, c'est normal).

- [ ] **Step 3 : Commit**

```bash
git add LarcCommon/larccommon/dialogs/event_generator_dialog.py
git commit -m "$(cat <<'EOF'
feat(larccommon): EventGeneratorDialog en vue scindée avec sélection à tout niveau

Remplace la navigation pas-à-pas par EventTypeSelectorWidget (arbre complet visible +
recherche). Le professeur peut confirmer un choix intermédiaire ; la note n'apparaît
que sur une feuille. EventData gagne type_id pour la liaison DB (Task suivante).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8 : `main_events.py` — persister `event_type_config_id` + refondre `_edit_event`

**Files:**
- Modify: `LarcSuperviseur/views/main_events.py`

**Interfaces:**
- Consumes: `EventData.type_id` (Task 7), `EventTypeSelectorWidget` (Task 5),
  `larccommon.event_type_service.event_type_service`.

- [ ] **Step 1 : `_insert_student_event` — ajouter `event_type_config_id`**

```python
    def _insert_student_event(self, evt: EventData):
        """Insère l'événement créé dans la table student_event."""
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.error"), _("main.error_no_db_connection"))
            return
        self._top_bar.set_loading(True, _("main.saving"))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO student_event
                (student_id, event_type, event_type_config_id, event_at, lieu_label,
                 subject_label, note, source, created_by, created_location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    evt.member_id,
                    evt.type_path,
                    evt.type_id,
                    evt.event_at,
                    evt.lieu_label,
                    evt.subject_label,
                    evt.note,
                    "EventGeneratorDialog",
                    session.user_id,
                    evt.created_location,
                ),
            )
            conn.commit()
            self._top_bar.set_loading(False)
            self._load_student_detail(evt.member_id)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_on_add_event insert: {e}")
            self._top_bar.set_loading(False)
            conn.rollback()
            QMessageBox.critical(
                self, _("common.error"), f"{_('main.error_save_failed')} : {e}"
            )
```

- [ ] **Step 2 : Refondre `_edit_event` sur `EventTypeSelectorWidget`**

Remplacer intégralement la méthode `_edit_event` existante (elle utilisait un `M3ComboBox` sur
`SELECT DISTINCT event_type`) :

```python
    @safe_slot("MainWindow.edit_event")
    def _edit_event(self, event_id: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.error"), _("main.error_no_db_connection"))
            return
        cur = conn.cursor()
        cur.execute(
            """
            SELECT se.event_type, se.event_type_config_id, se.event_at, se.lieu_label,
                   se.subject_label, se.note,
                   aec.last_name || ' ' || aec.first_name AS student_name
            FROM student_event se
            JOIN larcauth_aecuser aec ON aec.id = se.student_id
            WHERE se.event_id = %s
        """,
            (event_id,),
        )
        row = cur.fetchone()
        if not row:
            QMessageBox.warning(self, _("common.error"), _("main.error_event_not_found"))
            return
        etype, etype_config_id, e_at, lieu, subject, note, student_name = row

        dlg = QDialog(self)
        dlg.setWindowTitle(f"{_('event.edit_title')} #{event_id}")
        dlg.setMinimumSize(ds.window_width * 3 // 5, ds.window_height * 4 // 5)
        layout = QVBoxLayout(dlg)
        p = theme_manager.palette

        info = M3Label(
            f"<b>{student_name}</b> — {etype}<br>"
            f"<span style='color:{p.text_disabled};font-size:{theme_manager.font_size(10)}px;'>"
            f"{e_at.strftime('%d/%m/%Y %H:%M') if e_at else ''} | {lieu or ''}"
            f"{' | ' + subject if subject else ''}</span>"
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        hierarchies = event_type_service.filter_applicable(MemberType.STUDENT)
        selector = EventTypeSelectorWidget(hierarchies)
        existing_node = event_type_service.get_by_id(etype_config_id) if etype_config_id else None
        if existing_node:
            selector.preselect(existing_node)
        layout.addWidget(selector, 1)

        note_label = M3Label(_("event.edit_note"))
        note_input = M3TextEdit()
        note_input.setText(note or "")
        note_input.setMaximumHeight(ds.space_xxl + ds.space_lg)
        note_label.setVisible(existing_node is not None and EventTypeSelectorWidget.is_leaf(existing_node))
        note_input.setVisible(note_label.isVisible())
        layout.addWidget(note_label)
        layout.addWidget(note_input)

        state = {"node": existing_node}

        @safe_slot("MainWindow.edit_event.on_type_confirmed")
        def on_type_confirmed(node):
            state["node"] = node
            is_leaf = EventTypeSelectorWidget.is_leaf(node)
            note_label.setVisible(is_leaf)
            note_input.setVisible(is_leaf)
            if not is_leaf:
                note_input.clear()

        selector.type_confirmed.connect(on_type_confirmed)

        btn_row = QHBoxLayout()
        save_btn = M3Button(_("event.save"))
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {theme_manager.design.radius}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}"
        )

        @safe_slot("MainWindow.edit_event.save")
        def on_save():
            node = state["node"]
            if not node:
                QMessageBox.warning(dlg, _("common.error"), _("event.error_no_type"))
                return
            is_leaf = EventTypeSelectorWidget.is_leaf(node)
            cur.execute(
                "UPDATE student_event SET event_type = %s, event_type_config_id = %s, note = %s WHERE event_id = %s",
                (
                    event_type_service.get_path(node),
                    node.id,
                    note_input.toPlainText().strip() if is_leaf else "",
                    event_id,
                ),
            )
            conn.commit()
            dlg.accept()

        save_btn.clicked.connect(on_save)
        cancel_btn = M3Button(_("event.cancel"))
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()
```

- [ ] **Step 3 : Ajouter les imports nécessaires en tête de fichier**

```python
from larccommon.dialogs import EventGeneratorDialog, EventData, MemberType, EventTypeSelectorWidget
from larccommon.event_type_service import event_type_service
```
(la première ligne remplace l'import existant `from larccommon.dialogs import EventGeneratorDialog, EventData, MemberType`).

- [ ] **Step 4 : Test manuel**

- Créer un nouvel événement (Task 7 déjà en place) : vérifier en base que
  `student_event.event_type_config_id` est bien renseigné (`SELECT event_type_config_id FROM
  student_event ORDER BY event_id DESC LIMIT 1;`).
- Double-cliquer cet événement dans l'historique → `_edit_event` s'ouvre, l'arbre est déplié et
  positionné exactement sur le nœud d'origine (via `preselect`), pas de champ note si le nœud
  d'origine était intermédiaire.
- Modifier le type vers une autre feuille, enregistrer, rouvrir : le nouveau nœud est bien
  présélectionné.

- [ ] **Step 5 : Commit**

```bash
git add LarcSuperviseur/views/main_events.py
git commit -m "$(cat <<'EOF'
fix(larcsuperviseur): persiste event_type_config_id et unifie l'édition sur l'arbre

_insert_student_event renseigne désormais event_type_config_id. _edit_event
n'utilise plus le SELECT DISTINCT event_type legacy : il réouvre EventTypeSelectorWidget
sur le nœud exact via preselect(), avec la même règle de note conditionnelle qu'à la
création.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9 : `EventEditDialog` (`event_dialog.py`) — même refonte pour `student_detail.py`

**Files:**
- Modify: `LarcSuperviseur/views/core/event_dialog.py`

**Interfaces:**
- Consumes: mêmes composants que Task 8 (`EventTypeSelectorWidget`, `event_type_service`).
- Produces: `EventEditDialog` reste appelé exactement pareil par
  `LarcSuperviseur/views/panels/student_detail.py:_edit_event` (`EventEditDialog(event_id,
  self)`), aucune modification requise côté `student_detail.py`.

- [ ] **Step 1 : Réécrire `event_dialog.py`**

```python
from larccommon.design_system import ds
from larccommon.dialogs import EventTypeSelectorWidget
from larccommon.event_type_service import event_type_service, MemberType
from larccommon.l10n import _
from phibuilder.widgets import M3Button, M3Dialog, M3Label, M3TextEdit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
)

from LarcSuperviseur.common.database import db
from LarcSuperviseur.common.theme import theme_manager
from larccommon.safe_slot import safe_slot


class EventEditDialog(M3Dialog):
    def __init__(self, event_id: int, parent=None):
        super().__init__(parent)
        self._event_id = event_id
        self._conn = db.server_conn
        self._selected_node = None
        self.setWindowTitle(_("event_dialog.title").format(id=event_id))
        self.setMinimumSize(ds.window_width * 3 // 5, ds.window_height * 4 // 5)
        self._setup_ui()
        self._load_event()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        if not db.is_server_connected:
            return

        self._info = M3Label()
        self._info.setWordWrap(True)
        self._info.setTextFormat(Qt.RichText)
        layout.addWidget(self._info)

        hierarchies = event_type_service.filter_applicable(MemberType.STUDENT)
        self._selector = EventTypeSelectorWidget(hierarchies)
        self._selector.type_confirmed.connect(self._on_type_confirmed)
        layout.addWidget(self._selector, 1)

        self._note_label = M3Label(_("event_dialog.note"))
        self._note_input = M3TextEdit()
        self._note_input.setMaximumHeight(ds.window_height * 3 // 20)
        self._note_input.setAccessibleName(_("event_dialog.note"))
        self._note_input.setToolTip(_("event.note_tooltip"))
        self._note_input.textChanged.connect(self._on_note_changed)
        layout.addWidget(self._note_label)
        layout.addWidget(self._note_input)
        self._note_label.hide()
        self._note_input.hide()

        p = theme_manager.palette
        btn_row = QHBoxLayout()
        save_btn = M3Button(_("event_dialog.save_button"))
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}"
        )
        save_btn.clicked.connect(self._save)
        cancel_btn = M3Button(_("event_dialog.cancel_button"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _load_event(self):
        conn = self._conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error"), _("event_dialog.no_connection"))
            self.reject()
            return
        cur = conn.cursor()
        cur.execute(
            """
            SELECT se.event_type, se.event_type_config_id, se.event_at, se.lieu_label,
                   se.subject_label, se.note,
                   aec.last_name || ' ' || aec.first_name AS student_name
            FROM student_event se
            JOIN larcauth_aecuser aec ON aec.id = se.student_id
            WHERE se.event_id = %s
        """,
            (self._event_id,),
        )
        row = cur.fetchone()
        if not row:
            QMessageBox.warning(self, _("common.dialog.error"), _("event_dialog.not_found"))
            self.reject()
            return
        etype, etype_config_id, e_at, lieu, subject, note, student_name = row
        p = theme_manager.palette
        s = theme_manager.font_size
        self._info.setText(
            f"<b style='color:{p.text_strong}'>{student_name}</b> — {etype}<br>"
            f"<span style='color:{p.text_disabled};font-size:{s(10)}px;'>"
            f"{e_at.strftime('%d/%m/%Y %H:%M') if e_at else ''} | {lieu or ''}"
            f"{' | ' + subject if subject else ''}</span>"
        )
        self._note_input.setText(note or "")
        if etype_config_id:
            node = event_type_service.get_by_id(etype_config_id)
            if node:
                self._selected_node = node
                self._selector.preselect(node)
                is_leaf = EventTypeSelectorWidget.is_leaf(node)
                self._note_label.setVisible(is_leaf)
                self._note_input.setVisible(is_leaf)

    @safe_slot("EventEditDialog._on_type_confirmed")
    def _on_type_confirmed(self, node):
        self._selected_node = node
        is_leaf = EventTypeSelectorWidget.is_leaf(node)
        self._note_label.setVisible(is_leaf)
        self._note_input.setVisible(is_leaf)
        if not is_leaf:
            self._note_input.clear()

    @safe_slot("EventEditDialog._on_note_changed")
    def _on_note_changed(self):
        """Tronque la note à 200 caractères (M3TextEdit n'a pas de setMaxLength natif)."""
        text = self._note_input.toPlainText()
        if len(text) > 200:
            cursor = self._note_input.textCursor()
            pos = cursor.position()
            self._note_input.blockSignals(True)
            self._note_input.setPlainText(text[:200])
            cursor.setPosition(min(pos, 200))
            self._note_input.setTextCursor(cursor)
            self._note_input.blockSignals(False)

    @safe_slot("EventEditDialog._save")
    def _save(self):
        conn = self._conn
        if not conn:
            return
        if not self._selected_node:
            QMessageBox.warning(self, _("common.dialog.error"), _("event.error_no_type"))
            return
        is_leaf = EventTypeSelectorWidget.is_leaf(self._selected_node)
        cur = conn.cursor()
        cur.execute(
            "UPDATE student_event SET event_type = %s, event_type_config_id = %s, note = %s WHERE event_id = %s",
            (
                event_type_service.get_path(self._selected_node),
                self._selected_node.id,
                self._note_input.toPlainText().strip() if is_leaf else "",
                self._event_id,
            ),
        )
        conn.commit()
        self.accept()
```

- [ ] **Step 2 : Test manuel**

Depuis `LarcSuperviseur/views/panels/student_detail.py`, ouvrir un élève, double-cliquer un
événement de son historique : `EventEditDialog` doit s'ouvrir avec l'arbre positionné sur le
nœud d'origine et respecter la règle de note conditionnelle, comme dans la Task 8.

- [ ] **Step 3 : Commit**

```bash
git add LarcSuperviseur/views/core/event_dialog.py
git commit -m "$(cat <<'EOF'
fix(larcsuperviseur): EventEditDialog utilise EventTypeSelectorWidget au lieu du combo legacy

Même correctif que main_events.py._edit_event, appliqué au flux d'édition ouvert
depuis la fiche élève (student_detail.py).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10 : `LarcRH/views/staff_events.py` — persister `event_type_config_id`

**Files:**
- Modify: `LarcRH/views/staff_events.py`

**Interfaces:**
- Consumes: `EventData.type_id` (Task 7).

- [ ] **Step 1 : Ajouter la colonne à l'INSERT**

```python
def _insert_staff_event(evt: EventData, parent=None):
    """Insère l'événement staff créé dans la table staff_event."""
    try:
        conn = db.server_conn
        if not conn:
            QMessageBox.critical(parent, _("common.error"), _("common.db_error"))
            return

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO staff_event
            (staff_id, event_type, event_type_config_id, event_at, note, created_by,
             created_location, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'EventGeneratorDialog')
            """,
            (
                evt.member_id,
                evt.type_path,
                evt.type_id,
                evt.event_at,
                evt.note,
                session.user_id,
                evt.created_location,
            ),
        )
        conn.commit()

        QMessageBox.information(parent, _("common.success"), _("event.saved_success"))
        _refresh_parent_grid(parent)

    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log(f"_insert_staff_event: {e}")
        QMessageBox.critical(parent, _("common.error"), _("event.save_error"))
        if conn:
            conn.rollback()
```
(seule la clause `INSERT INTO staff_event (...)` et le tuple de valeurs changent — le reste de
la fonction et du fichier est inchangé.)

- [ ] **Step 2 : Test manuel**

Depuis LarcRH, ouvrir la fiche d'un membre du staff, générer un événement (ex. Absence), vérifier
`SELECT event_type_config_id FROM staff_event ORDER BY event_id DESC LIMIT 1;` non NULL.

- [ ] **Step 3 : Commit**

```bash
git add LarcRH/views/staff_events.py
git commit -m "$(cat <<'EOF'
fix(larcrh): persiste event_type_config_id sur staff_event

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11 : `LarcConfig/common/db_access.py` — `get_event_types()` sur la nouvelle hiérarchie

**Files:**
- Modify: `LarcConfig/common/db_access.py`

**Interfaces:**
- Produces: `get_event_types() -> list[dict]` retourne désormais des lignes de
  `larcauth_event_type_config` avec un champ `depth` calculé (0=racine), consommées par Task 12.
  Signature de retour changée : `{'id', 'code', 'label', 'category', 'parent_id', 'depth', 'enabled'}`
  (remplace l'ancien `{'id', 'cat', 'niv2', 'niv3', 'enabled'}` — Task 12 est mise à jour en
  conséquence dans la même passe).

- [ ] **Step 1 : Remplacer `get_event_types()`**

```python
def get_event_types():
    """Types d'événements — larcauth_event_type_config (arbre à 4 niveaux)."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute("""
            WITH RECURSIVE tree AS (
                SELECT id, code, label, category, parent_id, is_active, 0 AS depth
                FROM larcauth_event_type_config
                WHERE parent_id IS NULL
                UNION ALL
                SELECT te.id, te.code, te.label, te.category, te.parent_id, te.is_active,
                       tree.depth + 1
                FROM larcauth_event_type_config te
                JOIN tree ON te.parent_id = tree.id
            )
            SELECT id, code, label, category, parent_id, depth, is_active
            FROM tree
            ORDER BY category, depth,
                     COALESCE(parent_id, 0), id
        """)
        return [
            dict(zip(['id', 'code', 'label', 'category', 'parent_id', 'depth', 'enabled'], r))
            for r in cur.fetchall()
        ]
    except Exception:
        return []
```

- [ ] **Step 2 : Vérifier manuellement**

```bash
cd D:\projets && python -c "
from LarcConfig.common.db_access import get_event_types
rows = get_event_types()
print(len(rows), 'lignes')
print(rows[0])
"
```
Attendu : plus de 90 lignes (racines + toute la hiérarchie), première ligne = une racine
(`depth=0`).

- [ ] **Step 3 : Commit**

```bash
git add LarcConfig/common/db_access.py
git commit -m "$(cat <<'EOF'
fix(larcconfig): get_event_types() lit larcauth_event_type_config (arbre récursif)

Remplace la requête sur l'ancienne table plate larcauth_type_event, qui n'était
pas la hiérarchie réellement utilisée par EventGeneratorDialog.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12 : `LarcConfig/views/panel_types.py` — affichage hiérarchique

**Files:**
- Modify: `LarcConfig/views/panel_types.py`

**Interfaces:**
- Consumes: `get_event_types()` (Task 11, nouveau format `{'id','code','label','category','parent_id','depth','enabled'}`).

- [ ] **Step 1 : Réécrire le panel pour indenter par profondeur et afficher le code**

```python
"""Panel Types d'événements."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QTableWidgetItem
from phibuilder.widgets import M3Label, M3TableWidget, M3ScrollArea
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from LarcConfig.common.db_access import get_event_types


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
        l.addWidget(M3Label("Types d'evenements", theme=phi, style="headline_small"))

        table = M3TableWidget(theme=phi)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["ID", "Catégorie", "Libellé", "Code", "Actif"])
        h = table.horizontalHeader()
        for i in range(5):
            h.setSectionResizeMode(i, QHeaderView.Stretch)
        table.setAlternatingRowColors(False)

        rows = get_event_types()
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            indent = "    " * r['depth']
            table.setItem(i, 0, QTableWidgetItem(str(r['id'])))
            table.setItem(i, 1, QTableWidgetItem(r['category'] or ''))
            table.setItem(i, 2, QTableWidgetItem(f"{indent}{r['label'] or ''}"))
            table.setItem(i, 3, QTableWidgetItem(r['code'] or ''))
            table.setItem(i, 4, QTableWidgetItem('Oui' if r.get('enabled') else 'Non'))

        l.addWidget(table)
        self.setWidget(container)
        self.setWidgetResizable(True)
```

  Note : ce panel reste une table indentée (pas un `M3TreeWidget`) — la spec demande un
  "affichage hiérarchique cohérent avec la nouvelle profondeur", pas explicitement un arbre
  interactif pour l'admin ; l'indentation textuelle par profondeur suffit à rendre la
  hiérarchie lisible sans reconstruire tout un écran d'édition CRUD (hors scope de cette spec,
  qui porte sur la création/édition d'événement, pas sur l'admin des types eux-mêmes).

- [ ] **Step 2 : Test manuel**

```bash
python -m LarcConfig
```
Ouvrir le panel Types d'événements : vérifier que les 4 racines (Absence, Retard, Événement,
Sortie) apparaissent en tête, suivies de leurs enfants indentés, jusqu'à la profondeur 4
(ex. "Absence > Absence de l'école > Maladie > Légère").

- [ ] **Step 3 : Commit**

```bash
git add LarcConfig/views/panel_types.py
git commit -m "$(cat <<'EOF'
feat(larcconfig): panel_types.py affiche la hiérarchie 4 niveaux (indentation par profondeur)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13 : Validation finale — lints, graphify, checklist manuelle

**Files:** aucun fichier de code — validation transverse.

- [ ] **Step 1 : Lints ciblés sur les fichiers touchés**

```bash
cd D:\projets
python scripts/lint_qss_hardcoding.py LarcCommon/phibuilder/widgets/tree.py LarcCommon/larccommon/dialogs/event_type_selector.py LarcCommon/larccommon/dialogs/event_generator_dialog.py
python scripts/lint_d1_color_checker.py LarcCommon/phibuilder/widgets/tree.py
python scripts/lint_accessibility.py LarcCommon/phibuilder/widgets/tree.py
python scripts/lint_focus_visible.py LarcCommon/phibuilder/widgets/tree.py
python scripts/lint_keyboard_nav.py LarcCommon/phibuilder/widgets/tree.py
python scripts/lint_safe_slot.py LarcSuperviseur/views/main_events.py LarcSuperviseur/views/core/event_dialog.py LarcCommon/larccommon/dialogs/event_generator_dialog.py
python scripts/lint_file_size.py
```
Attendu : aucune erreur bloquante (`sys.exit(1)`) ; des avertissements non bloquants sont
acceptables (cf. les scripts eux-mêmes : `sys.exit(1 if errors else 0)`).

- [ ] **Step 2 : Suite de tests complète LarcCommon**

```bash
cd D:\projets\LarcCommon && pytest tests/ -v
```
Attendu : tous les tests passent, y compris les nouveaux (`test_event_type_service.py`,
`test_m3_tree_widget.py`, `test_event_type_selector.py`).

- [ ] **Step 3 : Régénérer le graphe de connaissances (changement structurel : nouveau widget +
  nouvelle migration + nouveau module)**

```bash
cd D:\projets
graphify extract . --code-only --force
graphify cluster-only .
```

- [ ] **Step 4 : Checklist manuelle finale**

- [ ] `EventGeneratorDialog` (LarcSuperviseur, élève) : vue scindée, recherche, sélection à tout
  niveau, note conditionnelle — OK
- [ ] `EventGeneratorDialog` (LarcRH, staff) : idem, `event_type_config_id` renseigné — OK
- [ ] Édition depuis `main_events.py` (historique global) : arbre pré-positionné, note
  conditionnelle — OK
- [ ] Édition depuis `student_detail.py` (fiche élève) : idem via `EventEditDialog` — OK
- [ ] `LarcConfig` : panel Types d'événements affiche la nouvelle hiérarchie à 4 niveaux — OK
- [ ] Un événement créé en s'arrêtant à un niveau intermédiaire, puis rouvert et précisé jusqu'à
  une feuille : la note redevient éditable et se sauvegarde — OK
- [ ] `Sortie du cours > Mauvais comportement > Insolence` et
  `Événement > Comportement > Négatif > Insolence` apparaissent bien comme deux entrées
  distinctes sélectionnables séparément — OK

- [ ] **Step 5 : Commit final (si des ajustements ont été faits pendant la checklist)**

```bash
git add -A
git status  # vérifier qu'aucun fichier inattendu n'est inclus avant de committer
git commit -m "$(cat <<'EOF'
chore: validation finale hiérarchie types d'événements + vue arbre (lints, graphify, tests)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

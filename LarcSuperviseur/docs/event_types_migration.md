# Migration des types d'événements (2026-08-30) — notes de compatibilité

## Ce qui a changé

- `larcauth_type_event` : arbre auto-référencé (`parent_id`, `code` UNIQUE par
  langue, `label`, `sort_order`, `absence_scope`, `context`) + PK sur `idtypeevent`.
- `student_event.event_type_id` (FK) — la sémantique porte désormais sur l'ID ;
  `event_type` (texte) reste pour l'affichage et les statistiques legacy.
- Verrou strict : un type référencé est IMMUABLE (trigger `guard_type_event_used`
  ERRCODE 23513 + checks Python `data_loader` + grisage UI panel admin).
- Nœuds structurels : IDs 1-14 (FR) et 21-34 (EN) ; `type_event = NULL` → invisibles
  pour les lecteurs legacy (`get_event_types_tree`, LarcConfig panel_types).

## Chaîne canonique écrite par le wizard

`Absence > Absent de l'école > Maladie` · `Bureau BI > Violence > Auteur` ·
`Sortie > Perturbation > Bavardage` — chemin depuis la RACINE DE CATÉGORIE
(les segments éphémères Événement/En cours/ailleurs/matière/lieu ne sont pas
stockés ; matière/lieu restent dans `subject_label` / `lieu_label`).

## Compatibilité des stats actuelles (INCHANGÉES — aucune régression)

- Motifs ILIKE "absence" : `event_type = 'absence'` OR `ILIKE 'Suivi > Absence%'`
  OR `ILIKE 'Absence%'` — satisfaits par les chaînes canoniques FR
  (data_loader.get_class_stats L183-212, get_presence_rate L241-286,
  main_window _load_group_stats ~L897-921).
- Motifs "sortie/exit" : `'exit'` / `'Sortie%'` / `'%Fuite%'` / `'Fugue%'` — OK.
- `event_helpers.event_icon/event_color` (LarcCommon\larccommon\event_helpers.py) :
  startswith() sur la catégorie — OK pour les chaînes canoniques FR.
- Vues `student_daily_summary` / `student_alerts` (sql\student_event.sql) :
  exact-match keywords legacy — inchangées.

### ⚠️ Limite EN
Les événements saisis dans la branche EN produisent des chaînes anglaises
(`Medical > ...`) que les motifs ILIKE/startswith FR ne matchent pas. La
migration définitive des KPIs vers les CODES (ci-dessous) règle ce cas.

## Requête cible future des KPIs (remplacement des ILIKE)

```sql
SELECT count(DISTINCT se.event_id)
FROM student_event se
LEFT JOIN larcauth_type_event te ON te.idtypeevent = se.event_type_id
WHERE te.code = 'absence'          -- racine par code (stable)
   OR te.parent_id = (SELECT idtypeevent FROM larcauth_type_event
                      WHERE code = 'absence' AND fk_language = 2)
   OR se.event_type = 'absence'    -- keywords legacy (event_type_id NULL)
```

## Sync

- **LarcCloudSync** : sync wholesale de `larcauth_type_event` (`SELECT *` +
  UPDATE reconstruit) → nouvelles colonnes propagées automatiquement ; à
  vérifier intranet vs cloud après un cycle (config.json cadence 3).
- **LarcProf** (SQLite) : décision retenue — `event_type_id` NON ajouté au sync
  local (reste NULL) ; stats string inchangées.
- **LarcSecretaire** : écrit des keywords legacy → `event_type_id` NULL ;
  helpers dupliqués non modifiés ; convergence future vers `event_helpers`
  recommandée.

## ⚠️ La prod diverge du seed (constaté 2026-08-30)

- La prod a **57 lignes avec des IDs 1100-2500** (pas 100-406) : libellés réels
  modifiés (« Violence physique », « Harcèlement » avec espace…), catégories EN
  `BI Office`, `Removal`, `Class absence` (fk_language=1) et une catégorie FR
  hybride `Absence cours` (fk_language=2).
- **NE PAS exécuter le re-seed `type_event_data.sql` sur la prod** : il
  réinsérerait les 27 lignes seed (IDs 100-406) EN PLUS des lignes réelles
  (doublons sémantiques). Le seed est réservé aux bases fraîches.
- La migration gère la prod réelle : nœuds structurels FR 1-19 / EN 21-29
  (labels EN alignés sur la prod), cas spéciaux `Absence cours` → absent-cours,
  `Class absence` → absent-cours EN, `Follow-up > Tardiness` → retard EN,
  trim des libellés, motifs d'absence école créés (15-19), backfill enrichi
  (`Absence > X` → absent-ecole/cours, `Retard …` → racine retard).
- Les libellés de N2 du seed (Violence, Harcèlement…) peuvent rester vides en
  prod (les lignes réelles ont d'autres libellés) — désactivables via l'UI admin.

## Exécution

1. `psql -U postgres -d NewLarcDB -f sql/migration_20260830_event_type_tree.sql`
2. `python LarcSuperviseur/sql/backfill_event_type_id.py`
3. Vérifications : racines (parent_id IS NULL), `event_type_id` backfillés,
   trigger 23513 sur un type utilisé.

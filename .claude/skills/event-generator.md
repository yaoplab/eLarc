---
name: event-generator
description: Générateur d'événements élèves (arrivée, départ, sortie, retour, absence, justifié, retard) — wizard 3 modes, event_helpers, table student_event
category: feature
trigger: événement, absence, retard, event, event_generator, wizard, student_event, event_icon, event_color
---

# Event Generator — Événements Élèves

Wizard séquentiel LarcSuperviseur/LarcProf. Modules : `LarcSuperviseur/views/core/event_actions.py`, `LarcCommon/larccommon/event_helpers.py`, `LarcSuperviseur/views/dialogs/event_generator.py`.

## Types d'événements

| Type | Description |
|---|---|
| `arrival` | Arrivée d'un élève |
| `departure` | Départ d'un élève |
| `exit` | Sortie temporaire |
| `return` | Retour après sortie |
| `absence` | Absence injustifiée |
| `justified` | Absence justifiée |
| `late` | Retard |

## Helpers

```python
from larccommon.event_helpers import event_icon, event_color
icon = event_icon('absence')    # icône du type
color = event_color('absence')  # couleur du type
```

⚠️ Dette connue : `event_color()` utilise des hex en dur — migration planifiée vers les tokens palette (`ds.p.success`, `ds.p.primary`, `ds.p.error`, `ds.p.tertiary`).

## Wizard 3 modes

| Mode | Description | Utilisateurs |
|---|---|---|
| Absence journée | Marquer un élève absent toute la journée | Superviseur |
| Retard | Enregistrer un retard avec heure | Superviseur, Prof |
| Événements | Arrivée, départ, sortie, retour | Superviseur |

## Structure DB

```sql
-- Table des événements (simplifié)
CREATE TABLE student_event (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES larcauth_aecuser(id),
    event_type VARCHAR(20),  -- arrival | departure | exit | return | absence | justified | late
    event_date DATE, event_time TIME,
    created_by INTEGER, created_at TIMESTAMP DEFAULT NOW()
);
```

## Pattern wizard

```python
class EventGenerator(QWidget):
    MODE_ABSENCE, MODE_LATE, MODE_EVENTS = 1, 2, 3
    # _start_wizard(mode) → étape 1 : sélection élève(s) → étape 2 : détails → étape 3 : confirm + INSERT
```

## Adaptation RH

LarcRH : `LarcRH/views/staff_events.py` — même pattern adapté à `staff_event` (absences/retards/primes du personnel).

**Règle agenda (bloquante)** : la génération d'événements RH n'est autorisée
que les **jours ouvrés** — `larcauth_agenda.working_day = TRUE` (le « enabled »
du jour, vérifié via `HRDatabase.is_working_day()`). Jour non ouvré (week-end,
férié) → `open_staff_event_generator` refuse avec un message, et l'absence du
jour ne s'applique nulle part (cartes, KPI « Absents du jour », effectifs).

## Checklist

- [ ] 3 modes disponibles ; sélection élève individuelle ou groupe
- [ ] event_type valide (7 types) ; date et heure enregistrées
- [ ] event_color() hex hardcodés → migration tokens planifiée ; i18n sur les types

## Références croisées

- design-tokens (ds.p.*), color-rules (D1-D3), pyside6-wrapper (@safe_slot sur les handlers)

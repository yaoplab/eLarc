---
name: scolarite-finance
description: Règles métier scolarité — balance, statut, projection, alertes, recouvrement. Contexte Larc scolaire (LarcCompta).
category: feature
trigger: scolarité, frais, paiement, balance, échéancier, LarcCompta, impayés, recouvrement
---

# Scolarité Finance — LarcCompta

Règles métier des frais de scolarité : modèle parent-based, statut, propagation parent→enfant, projection, alertes, exports. Référence complète : `LarcCompta/CAHIER_DES_CHARGES.md`.

## SF — Modèle de données

| # | Règle | ❌ Interdit | ✅ Obligatoire |
|---|---|---|---|
| SF1 | **Paiement lié au parent** | `compta_payment.student_id` | `compta_payment.parent_id` — un virement = un parent |
| SF2 | **Balance unique par parent** | Calcul du statut à la volée | `compta_parent_balance` (1 ligne parent/an) — lu en 1 SELECT |
| SF3 | **Barème par niveau** | Prix unique par programme | `compta_fee_level` : chaque niveau (PEI-1, MYP-3, DP-2) a son tarif |
| SF4 | **Frais par élève** | Modifier le barème pour un cas particulier | `compta_student_fee` : copie modifiable individuellement |
| SF5 | **Historique tracé** | Écraser sans trace | `change_history` (JSONB) daté à chaque changement |
| SF6 | **Preuves attachées** | Paiement sans justificatif | `compta_payment.file_url` + `cloud_url` |

## S1 — Algorithme de statut

- **S1a** total_due = Σ `compta_student_fee.annual_fee` ; **S1b** total_paid = Σ `compta_payment.amount`
- **S1c** Milestone `inscription` non soldé + date dépassée → `en_retard` (prioritaire)
- **S1d** Attendu mensuel = total_due × % échéancier OU Σ milestones si personnalisé
- **S1e** Statut : `paid ≥ total_due` → `solde` / `paid ≥ attendu` → `en_cours` / sinon → `en_retard`
- **S1f** Propagation : parent X → tous ses enfants X (`larcauth_student.statut_scolarite`)
- **S1g** Override : `status_override=TRUE` + badge ✎

3 états = 3 bordures : En retard ROUGE · En cours VERT · Soldé BLEU.

## S2 — Dashboard & projection

- **S2a** Jauge % encaissé + détail par programme
- **S2b** Deux courbes : standard (pointillés) + ajustée (pleine, hors milestones perso)
- **S2c** Top 10 impayés : parent, enfants, restant, dernier paiement
- **S2d** Alerte proactive : badge rouge sur « Rappels » si `en_retard ≥ seuil` et `restant > seuil_montant`
- **S2e** Export Word : Impayés / Bilan annuel / Relevé individuel

## S3 — Vignettes élèves

- **S3a** Bordure 2px ROUGE/VERT/BLEU (`set_payment_status(status)`)
- **S3b** Label statut coloré ; **S3c** fond `ds.p.surface` uniforme (la bordure seule change) ; **S3d** badges D/M/P/E masqués

## S4 — Dossier parent

- **S4a** 1 SELECT `compta_parent_balance` ; **S4b** enfants + frais (niveau, classe, annual_fee) ; **S4c** paiements + preuves cliquables ; **S4d** `change_history` en timeline ; **S4e** combo override (`en_cours`/`solde`/`en_retard`/`exonere`)

## S5 — Recouvrement

- **S5a** Liste impayés triable (montant, ancienneté, programme) + filtres par seuil
- **S5b** Sélection multiple → rappel groupé ; **S5c** colonne Résultat (`payé depuis`/`sans effet`)

## Code clé

```python
def get_parent_status(parent_id: int) -> dict:
    # 1 SELECT compta_parent_balance (parent_id + année académique)
    # → {total_due, total_paid, remaining, status, status_override, change_history}

def sync_balance(parent_id: int):
    # 1. INSERT INTO compta_parent_balance ... ON CONFLICT (parent_id, academic_year)
    #    DO UPDATE SET total_due/total_paid/remaining/status,
    #    change_history = change_history || EXCLUDED.change_history::jsonb
    # 2. Propagation : UPDATE larcauth_student SET statut_scolarite = %s
    #    WHERE id IN (SELECT student_id FROM larcauth_student_parent WHERE parent_id = %s)

# Alerte proactive (S2d) :
# SELECT COUNT(*) FROM compta_parent_balance
# WHERE status='en_retard' AND remaining > %s → badge si ≥ seuil
```

## Checklist

- [ ] SF1 paiement par `parent_id` (jamais `student_id`) ; SF2 balance en 1 SELECT ; SF5 change_history à jour
- [ ] S1a-S1e statut correct (inscription prioritaire) ; S1f propagation enfants ; S1g override
- [ ] S2a jauge ; S2b deux courbes ; S2d badge Rappels ; S2e export Word
- [ ] S3 bordures colorées + fond uniforme ; S4 dossier parent complet ; S5 liste actionnable

## Références croisées

- design-tokens, color-rules (D1), zero-hardcoding, dashboard-pattern, search-detail-pattern, card-grid-pattern, `LarcCompta/CAHIER_DES_CHARGES.md`

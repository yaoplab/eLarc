---
name: rh-audit-fonctionnel
description: Audit fonctionnel RH — Togo. Grille 14 domaines, matrice de couverture, calcul CNSS 4%/16.5%, barème impôt progressif, SMIC 35k FCFA, gabarit employés. Analyse reproductible garantie.
category: feature
trigger: audit RH, analyse fonctionnelle RH, couverture RH, gap analysis RH, manque RH, que manque-t-il, logiciel RH complet, fonctionnalités RH, cahier des charges RH, spécification RH, RH au Togo
---

# Audit Fonctionnel RH — Grille d'analyse universelle

**Objectif** : Produire une analyse fonctionnelle REPRODUCTIBLE de tout logiciel RH.
**Pourquoi** : Sans grille standardisée, chaque session produit un résultat différent. Ce skill garantit la cohérence.

**Méthode** : 3 phases — (1) Inventaire du code, (2) Croisement avec les 14 domaines RH, (3) Gap analysis → matrice de couverture.

---

## 1. Les 14 domaines RH — Grille universelle

### 🔴 P1 — Critiques (sans eux, un RH ne peut pas travailler)

**RH1 — Dossier Employé** : identité, contacts, photo, matricule, situation familiale, urgences, pièces d'identité, CNSS, N° fiscal. Critère 90% = fiche complète.

**RH2 — Contrats** : CDI/CDD/stage, période d'essai, salaire brut, volume horaire, classification, historique, avenants. Critère 85% = multi-contrats + avenants.

**RH3 — Congés** : solde annuel (CA, maladie, maternité, sans solde), demandes avec dates, circuit validation, historique, lien paie. Critère 80% = demandes + validation + lien paie.

**RH4 — Paie** : config CNSS employeur/employé, barème impôt, bulletin mensuel détaillé (salaire base, primes, heures sup, indemnités, retenues, avances, net), calcul automatique brut→net, journal de paie, historique 12 mois, export PDF, déclaration CNSS trimestrielle. **Critère 0% si aucun bulletin automatique.**

**RH5 — Présence & Temps** : pointage arrivée/départ, calcul heures, heures sup (majoration configurable), lien paie. Critère 10% = absences seules, 80% = pointage + heures sup.

### 🟡 P2 — Importants (RH complet)

**RH6 — Événements** : absences, retards, sorties, missions avec motif + note + horodatage + lien paie. Critère 60% = sans lien paie, 90% = avec.

**RH7 — Recrutement** : fiches de poste, candidatures, pipeline (présélection→entretiens→offre→embauché), onboarding. Critère 0% si rien.

**RH8 — Formation** : plan annuel, catalogue, suivi individuel (certificats, expiration). Critère 0% si rien.

**RH9 — Évaluation** : entretiens annuels, objectifs (fixation, suivi, bilan), grille compétences. Critère 0% si rien.

**RH10 — Portail Employé** : self-service (congés, bulletins, infos perso), login dédié. Critère 0% si rien.

### 🟢 P3 — Complémentaires

**RH11 — Workflow** : circuit validation multi-niveaux, notifications, historique.

**RH12 — Notes de Frais** : déclaration, justificatifs, validation → remboursement.

**RH13 — Santé & Sécurité** : visites médicales, accidents travail, EPI.

**RH14 — Reporting** : dashboard (effectif, turnover, absentéisme, masse salariale), exports Excel/PDF, bilan social. Critère 60% = dashboard basique.

---

## 2. Contexte Togo — Obligatoire

- **CNSS** : employé 4% + employeur 16.5% du salaire brut plafonné. Déclaration trimestrielle DNS.
- **Impôt salaire** : barème progressif, prélèvement à la source.
- **SMIG** : 35 000 FCFA/mois (indicatif 2026).
- **Congés** : 2.5j/mois = 30j/an.
- **Paiement** : TMoney (Togocel) / Flooz (Moov Africa) — optionnels.
- **Devise** : FCFA (XOF), taux fixe 1€ = 655.957 XOF.

---

## 3. Méthode d'analyse — 3 phases OBLIGATOIRES

### Phase 1 : Inventaire du code
1. Lire TOUT le schéma SQL (tables, colonnes, contraintes)
2. Lire TOUTES les méthodes de la couche données (`get_*`, `save_*`, `search_*`)
3. Lire TOUTES les vues/écrans
4. Lister chaque fonctionnalité → table SQL → vue associée

### Phase 2 : Croisement
1. Pour chaque domaine RH1–RH14, déterminer le % exact de couverture
2. Utiliser les critères de chaque domaine — être strict
3. **Ne pas créditer** un domaine partiellement implémenté comme « couvert »

### Phase 3 : Gap Analysis
1. Domaines à 0% = manquants
2. Calculer couverture globale
3. Prioriser P1 > P2 > P3
4. Produire les 3 sorties standard (section 4)

---

## 4. Format de sortie STANDARD — Obligatoire

Toute analyse DOIT produire :

### 4.1 ✅ Déjà couvert
Tableau : Module | Fonctionnalités

### 4.2 ❌ Manquant par priorité
Listes 🔴 P1, 🟡 P2, 🟢 P3 avec description précise de chaque item.

### 4.3 Matrice de couverture
Tableau : Domaine RH | Couvert | Manquant

Code couleur : 🟢 ≥80% | 🟡 30-79% | 🔴 <30%

### 4.4 Recommandation MVP
Top 3 des priorités pour qu'un RH puisse travailler.

---

## 5. Règles d'audit

| # | Règle | Gravité |
|---|---|---|
| A1 | Chaque % justifié par du code lu ou du SQL trouvé — jamais subjectif | 🔴 P0 |
| A2 | Contexte Togo (CNSS, barème, SMIG, Code du Travail) dans l'analyse paie | 🔴 P0 |
| A3 | Matrice 14 domaines obligatoire | 🔴 P0 |
| A4 | Créditer l'existant, déclarer l'absent avec % exact | 🔴 P0 |
| A5 | Priorités : P1 (paie+présence) > P2 (recrutement+formation+évaluation+portail) > P3 (reste) | 🔴 P0 |
| A6 | Format section 4 exact — ne pas improviser | 🟡 P1 |
| A7 | Spécifier si le logiciel est standalone ou couplé à un contexte métier (ex: scolaire) | 🔴 P0 |

## 6. Patterns de conception RH — Référence

### 6.1 Gabarit d'employés (Template/Slot Pattern)

**Principe** : Les employés sont pré-alloués par plages d'IDs. L'embauche = activation d'un slot (UPDATE), jamais INSERT.

```
Service ID × 1000 + i  →  ID employé
Service 01 (Direction) → 01001–01999 (999 slots)
Service 12 (Compta)    → 12001–12999
```

**Implémentation** : `generate_series(id_start, id_end)` avec `is_active=FALSE`, `first_name='Employé'`, `last_name='ID{id}'`. L'activation remplit les champs réels et passe `is_active=TRUE`.

### 6.2 Calendrier (Agenda Pattern)

Table `larcauth_agenda` : une ligne par jour (format ID=YYYYMMDD), avec `working_day` et `holiday_name`. Les événements (absences, retards) sont liés au jour agenda via `fk_agenda_id`. DDL dans `LarcProf/LarcNewCloudSchéma.sql`, liée à l'année académique via `agenda_start_id`/`agenda_end_id` (migration LarcRH `migration_20260809_academicyear_unit.sql`).

### 6.3 Cycle de vie employé

```
[SLOT INACTIF] → Embauche (UPDATE) → [ACTIF] → Suspendu/Préavis → Départ → [INACTIF]
                       ↓                    ↓
                  Contrat créé         Contrat rompu
                  Congés init (30j)    Solde congés gelé
```

### 6.4 Référentiel CNSS Togo

| Poste | Taux | Base |
|---|---|---|
| Cotisation salariale | 4% | Salaire brut plafonné (300 000 FCFA/mois) |
| Cotisation patronale | 16.5% | Même plafond |
| Déclaration | Trimestrielle | DNS (Déclaration Nominative des Salaires) |
| Pénalité retard | 1.5%/mois | Article 14 Code Sécurité Sociale |

### 6.5 Barème impôt sur salaire (Togo — indicatif)

| Tranche (FCFA/mois) | Taux |
|---|---|
| 0 – 35 000 | 0% |
| 35 001 – 150 000 | 10% |
| 150 001 – 300 000 | 15% |
| 300 001 – 600 000 | 20% |
| > 600 000 | 30% |

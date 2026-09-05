---
name: student-record
description: Dossier élève/employé par catégories — navigation par onglets, formulaires adaptés, documents joints. Pattern StaffDetail LarcRH.
category: feature
trigger: dossier, fiche, detail, StaffDetail, catégories, onglets, student_record
---

# Student/Employee Record — Dossier par Catégories

## Pattern

```
┌─ Photo + Nom + Statut (sticky header) ─────────────────┐
├─ Sidebar catégories ─┬─ Espace de travail ──────────────┤
│ 📋 Identité          │ Formulaire / affichage           │
│ 🎓 Diplômes          │ adapté à la catégorie            │
│ 📄 Contrats          │                                  │
│ 🏖 Congés            │                                  │
│ 📂 Documents         │                                  │
│ 📅 Événements        │                                  │
└──────────────────────┴──────────────────────────────────┘
```

## Règles

- Catégories chargées depuis `staff_detail_category` (clé, label, icône, ordre)
- Chaque catégorie = un widget dans un QStackedWidget
- Lazy loading : `_load_{key}()` appelé au premier affichage
- Fallback si table vide : `_FALLBACK_CATEGORIES`

## Vérification du dossier (LarcRH — port Blado)

Carte « Vérification du dossier — Vérifié et Validé » dans la fiche :
- `HRDatabase.DOSSIER_CHECK_ITEMS` — 5 items indispensables (matricule, CNSS,
  pièce d'identité, contact urgence nom/tél), validation 100 % manuelle
- Table `staff_dossier_check` (staff_id, item_key, validated, validated_by,
  validated_at) — UNIQUE (staff_id, item_key)
- Checkboxes NATIVES (pas de QSS — le rendu QSS ferait disparaître la case)
- Progression : « N/5 items vérifiés — dossier incomplet » / « Dossier COMPLET »

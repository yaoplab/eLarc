
# Historique de construction — LarcCommon

## Itération 1 — Création (22 juin 2026)

### Problème initial
Les applications Larc (LarcSuperviseur, LarcSecretaire, etc.) partagent
des modules d'infrastructure (DB, auth, logger, theme) mais chaque projet
a sa propre copie de `common/`. Pas de bibliothèque UI commune.

### Décision
Créer `LarcCommon` comme dépôt central :

1. **phibuilder/** — UI toolkit Material Design 3 + Fibonacci
   - Déplacé depuis l'ancien `LarcPhibuilder`
   - 12 widgets M3, génération QSS, thème dynamique
   - 51 tests passants

2. **larccommon/** — Infrastructure partagée
   - Modules copiés depuis `LarcSuperviseur/common/`
   - Ajout du module `l10n/` pour les traductions multilingues
   - `theme.py` modifié pour intégrer `PhiBuilder` (QSS M3 global)

3. **LarcSuperviseur/common/** — Modules passerelle
   - Chaque fichier réexporte depuis `larccommon.modules`
   - Aucune modification des vues nécessaire
   - `top_bar.py` modifié : vignettes colorées pour les thèmes

4. **5 thèmes** : Océan, Forêt, Nuit, Lave, Sable
   - Utilisent PhiBuilder/materialyoucolor pour le QSS M3
   - Palettes manuelles pour compatibilité ascendante

### Prochaines itérations
- Traductions dans les vues (intégration l10n)
- Refactoring UI avec phibuilder widgets
- Nettoyage ancien dépôt LarcPhibuilder

## Itération 2 — LarcRH & règles métier RH (16 août 2026)

### Règle agenda (fondamentale)
**`larcauth_agenda.working_day` est le « enabled » du jour** :
- `working_day = TRUE` → jour ouvré → on peut **générer des événements**
  (absences/retards du personnel)
- `working_day = FALSE` (week-end, férié — ex. Assomption) → génération
  **interdite** (`open_staff_event_generator` bloqué avec message) et
  l'absence du jour **ne s'applique pas** (cartes, KPI « Absents du jour »,
  effectifs présents)

### Autres éléments de l'itération
- Code couleur des types d'employés (`STAFF_TYPE_COLORS` dans theme.py,
  2 déclinaisons clair/sombre, légende `StaffTypeLegend`)
- Vignettes Fibonacci 200×323, photo 140×140, bordure couleur du type
- Dashboard RH : KPI « Effectif actif » aligné sur la grille (retrait du
  filtre `is_active`), complétude limitée au personnel (plus les élèves),
  histogramme vertical avec fallback par catégorie
- Composants partagés : `password_dialog.py`, `staff_type_legend.py`,
  `msgbox.py`, `ergonomics.py` (garde-molette)
- KB agent consolidée : `.claude/skills/` unique (open-design supprimé)
- Système de vérification du dossier (« Vérifié et Validé ») porté de Blado :
  checkboxes par item indispensable (matricule, CNSS, pièce d'identité,
  contacts urgence), table `staff_dossier_check`, progression dans la fiche
- Dashboard « Complétude des dossiers » unifié avec les checkboxes : score et
  barres calculés depuis `staff_dossier_check` (même source que la carte de
  vérification) ; doublon « Pièce d'identité » supprimé des documents manquants
- Audit trail RH : colonnes created_by/modified_by (id aecuser) sur toutes
  les tables RH (migration appliquée Intranet + Supabase), remplies par
  _audit_by() ; tableaux informationnels (événements, contrats, congés)
  affichent le NOM du créateur/modificateur. Histogrammes plus hauts
  (356 = GIANT×4) et sans arrondis.

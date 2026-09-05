# LarcRH — Cahier des Charges Fonctionnel

**Version** : 1.0 — 2026-08-08
**Périmètre** : Gestion des Ressources Humaines — Établissement scolaire privé (IBO ou national)
**Effectif cible** : 100 à 300 employés
**Typologie** : Enseignants, coordinateurs, personnel non enseignant, direction

---

## Table des matières

1. [Module 1 — Dossier employé](#module-1--dossier-employé)
2. [Module 2 — Contrats et emploi](#module-2--contrats-et-emploi)
3. [Module 3 — Congés et absences](#module-3--congés-et-absences)
4. [Module 4 — Paie et rémunération](#module-4--paie-et-rémunération)
5. [Module 5 — Évaluation et performance](#module-5--évaluation-et-performance)
6. [Module 6 — Formation et développement professionnel](#module-6--formation-et-développement-professionnel)
7. [Module 7 — Recrutement](#module-7--recrutement)
8. [Module 8 — Documents administratifs](#module-8--documents-administratifs)
9. [Module 9 — Tableaux de bord et rapports](#module-9--tableaux-de-bord-et-rapports)
10. [Module 10 — Paie et déclarations](#module-10--paie-et-déclarations)
11. [Module 11 — Spécificités IBO](#module-11--spécificités-ibo)
12. [Module 12 — Courriers et modèles de lettres](#module-12--courriers-et-modèles-de-lettres)
13. [Récapitulatif et priorisation](#récapitulatif-et-priorisation)

---

## Architecture générale

### Profils utilisateurs

| Profil | Périmètre |
|---|---|
| **DRH / Directeur RH** | Tout l'établissement — tous les modules |
| **Chef d'établissement / Directeur** | Vue complète, validation des décisions clés (embauche, licenciement, budget) |
| **Coordinateur pédagogique** | Enseignants de son programme — évaluations, formations, absences |
| **Comptable** | Module paie et déclarations (lecture seule sur le reste) |
| **Employé (self-service)** | Son propre dossier, demandes de congé, consultations |

### Règles métier transversales

- **Gabarit d'IDs** : Plages réservées par catégorie (1001-2000 Collège/Lycée, 2001-3000 Primaire, 3001-4000 Maternelle, 4001-5000 Staff non enseignant). Utilisation du pattern `UPDATE` sur slots existants, jamais de suppression.
- **Multi-campus** : Filtrage par campus (via `larcauth_campus`), mode multi-site pour les groupes scolaires.
- **Traçabilité** : Toute action sensible (modification contrat, validation congé, évaluation) loguée avec auteur + horodatage.
- **Conformité** : Alignement sur le Code du Travail togolais (ou adaptable au pays) pour les durées de congé, préavis, cotisations CNSS.

---

## Module 1 — Dossier employé

### 1.1 État actuel

| Fait | À faire / À améliorer |
|---|---|
| Grille photos responsive (Fibonacci 136×220) | Ajout filtres (campus, statut, programme) |
| Fiche édition (nom, email, téléphone, rôles, date embauche) | Enrichir avec ~25 champs supplémentaires |
| Timeline événements (absences, retards) | Vue synthétique + filtres par type/période |

### 1.2 Fonctionnalités à implémenter

#### 1.2.1 Fiche employé enrichie

**Données personnelles :**
- Civilité, nom, prénom, date de naissance, nationalité
- Situation familiale (célibataire, marié, divorcé, veuf)
- Nombre d'enfants / personnes à charge
- Adresse personnelle complète
- Téléphone personnel, téléphone urgence
- Email personnel, email professionnel
- Photo d'identité (upload + recadrage automatique)
- Numéro CNSS / sécurité sociale
- Numéro d'identification fiscale
- Pièce d'identité (type, numéro, date expiration)
- Groupe sanguin, personne à contacter en urgence

**Données professionnelles :**
- Matricule / ID employé
- Date d'embauche initiale
- Ancienneté calculée automatiquement
- Catégorie professionnelle (cadre, agent de maîtrise, employé)
- Statut (actif, suspendu, en préavis, parti)
- Date de départ (si applicable) + motif
- Campus d'affectation principal
- Campus secondaires (si multi-site)
- Programme(s) d'enseignement (le cas échéant)
- Matières enseignées
- Classes/niveaux attribués
- Charge horaire hebdomadaire contractuelle
- Supérieur hiérarchique (lien vers fiche du chef)

**Diplômes et qualifications :**
- Liste des diplômes (type, établissement, année, pays)
- Certifications (IB, Cambridge, DELF, TOEFL, etc.)
- Langues parlées (niveau CECRL)
- Années d'expérience (total, dans l'établissement, dans le programme)

#### 1.2.2 Grille et recherche

- **Filtres** : par campus, catégorie, statut, programme, matière enseignée
- **Recherche plein texte** : nom, prénom, email, matière
- **Tri** : par nom, ancienneté, date d'embauche, campus
- **Vue compacte / vue détaillée** : toggle grille ↔ liste tabulaire
- **Export CSV/Excel** de la liste filtrée

#### 1.2.3 Self-service employé

- Portail employé (login personnel)
- Consultation de sa propre fiche
- Mise à jour des coordonnées personnelles (avec flux de validation)
- Consultation de ses bulletins de paie
- Consultation de son solde de congés
- Demande de congé / absence
- Consultation de son planning

---

## Module 2 — Contrats et emploi

### 2.1 Gestion des contrats

#### Types de contrats supportés

| Type | Description | Usage typique |
|---|---|---|
| CDI | Contrat à durée indéterminée | Enseignants permanents, staff administratif |
| CDD | Contrat à durée déterminée | Remplacements, projets, postes temporaires |
| CDD renouvelable | CDD avec clause de renouvellement | Enseignants en période d'essai prolongée |
| Stage | Convention de stage | Stagiaires, étudiants |
| Prestataire | Contrat de prestation de services | Consultants, intervenants ponctuels |
| Vacataire | Contrat de vacation | Enseignants à l'heure, examinateurs |
| Temps partiel | CDI ou CDD à temps partiel | Enseignants à mi-temps, staff à temps réduit |

#### Fonctions

- Création de contrat (date début, date fin si CDD, type, période d'essai)
- Renouvellement de contrat (avec historique des renouvellements)
- Avenants (modification de salaire, temps de travail, affectation)
- Calcul automatique de la date de fin de période d'essai
- Alerte préavis : échéance de CDD, fin de période d'essai (J-30, J-15, J-7)
- Génération du contrat en PDF/Word (template paramétrable)
- Historique complet des contrats par employé (frise chronologique)

#### Données du contrat

- Type de contrat, dates (début, fin, période d'essai)
- Salaire brut mensuel
- Indemnités (logement, transport, panier, technicité)
- Prime de bilan / 13e mois
- Volume horaire contractuel (heures/semaine)
- Convention collective applicable
- Classification / échelon
- Clause de confidentialité, clause de non-concurrence
- Documents liés (contrat signé scanné)

### 2.2 Workflow de fin de contrat

- Démission : enregistrement date préavis, calcul automatique durée préavis selon ancienneté
- Licenciement : motif, date notification, préavis, indemnités calculées
- Départ retraite : date, calcul indemnité départ
- Fin de CDD : alerte 30 jours avant, proposition renouvellement ou non
- Checklist de départ (documents à remettre, matériel à récupérer, accès à couper)
- Génération certificat de travail automatique (PDF)

### 2.3 Organigramme

- Visualisation arborescente de la structure
- Niveaux : Direction → Coordinateurs → Enseignants / Chefs de service → Staff
- Glisser-déposer pour réorganiser
- Export image/PDF
- Version historique (archives annuelles)

---

## Module 3 — Congés et absences

### 3.1 Types de congés

| Code | Type | Cadre légal (Togo) |
|---|---|---|
| CA | Congé annuel | 2,5 jours/mois travaillé (30 jours/an) |
| CM | Congé maladie | Jusqu'à 6 mois (3 mois plein traitement + 3 mois demi) |
| MAT | Congé maternité | 14 semaines (6 avant, 8 après) |
| PAT | Congé paternité | 3 jours ouvrables |
| CF | Congé familial (mariage, décès) | 3 à 5 jours selon événement |
| CS | Congé sans solde | Sur accord direction |
| CFOR | Congé de formation | Lié au plan de formation |
| SYN | Congé syndical | Pour représentants du personnel |
| REC | Récupération | Heures supplémentaires récupérées |
| AUT | Autorisation d'absence | Absence ponctuelle avec accord |
| VAC | Vacances scolaires | Spécifique aux enseignants (calendrier académique) |

### 3.2 Moteur de solde de congés

- **Crédit automatique** : 2,5 jours/mois pour les congés annuels (proratisé si temps partiel)
- **Calcul en jours ouvrés** (lundi-vendredi) ou **jours calendaires** selon paramétrage
- **Report** : possibilité de reporter N jours sur l'année suivante (configurable)
- **Plafond d'accumulation** : alerte si stock > seuil
- **Décompte automatique** à la validation du congé
- **Régularisation** manuelle possible par la DRH
- **Visualisation** : compteur temps réel pour l'employé et le responsable

### 3.3 Workflow de demande de congé

```
Employé dépose demande → Supérieur hiérarchique notifié → Validation/Refus → DRH notifiée → Solde mis à jour
```

- **Saisine** : type de congé, dates (début/fin), motif, pièce jointe éventuelle (certificat médical)
- **Circuit de validation** paramétrable par type de congé :
  - Congé annuel → Chef direct
  - Congé maladie > 3 jours → Chef direct + DRH
  - Congé sans solde → Chef direct + DRH + Direction
- **Délégation** automatique si le validateur est absent
- **Délai de réponse** : rappel automatique si pas de réponse sous 48h/72h
- **Calendrier visuel** des absences par équipe/campus
- **Détection de conflits** : alerte si trop de personnes absentes simultanément dans un même département

### 3.4 Gestion des absences (hors congés)

- **Absence signalée** (retard, absence non justifiée)
- **Saisie rapide** par le surveillant/coordinateur
- **Régularisation** a posteriori (justificatif → transformation en congé)
- **Suivi des récidives** : seuils d'alerte configurables (3 absences non justifiées = courrier)
- **Lettres types** : rappel à l'ordre, mise en demeure (génération automatique)

---

## Module 4 — Rémunération et paie

### 4.1 Structure de rémunération

#### Composantes paramétrables

| Catégorie | Exemples |
|---|---|
| Salaire de base | Brut mensuel, taux horaire |
| Primes fixes | Logement, transport, panier, technicité, ancienneté |
| Primes variables | Heures supplémentaires, cours de rattrapage, examens |
| Indemnités | 13e mois, prime de bilan, indemnité de départ |
| Retenues | Absences non justifiées, pénalités |
| Cotisations sociales | CNSS (part salariale 4% + part patronale 16,5% au Togo) |
| Impôts | ITS (Impôt sur le Traitement et Salaires), retenue à la source |
| Autres retenues | Avance sur salaire, saisie, prêt employeur |

#### Grille salariale

- Barème par catégorie, échelon, ancienneté
- Points d'indice (si convention collective applicable)
- Historique des évolutions salariales par employé
- Simulation d'augmentation (impact budgétaire)

### 4.2 Bulletin de paie

- **Génération mensuelle** automatisée (batch)
- **Calcul** : brut → cotisations → net imposable → ITS → net à payer
- **Édition PDF** avec template personnalisable (logo école, mentions légales)
- **Envoi par email** aux employés (batch ou individuel)
- **Archive** : bulletins consultables par l'employé (self-service) et la DRH
- **Correction** : possibilité d'annuler et régénérer un bulletin erroné
- **Export comptable** : écritures comptables (journal de paie) pour LarcCompta

### 4.3 Déclarations sociales et fiscales

- **CNSS** : déclaration mensuelle/nominative, bordereau de versement
- **ITS** : déclaration mensuelle, retenue à la source
- **État annuel des salaires** : récapitulatif par employé
- **Attestations** : attestation de salaire, attestation d'emploi, attestation CNSS
- ** Formats export** : CSV, PDF, selon normes locales

---

## Module 5 — Évaluation et performance

### 5.1 Cycles d'évaluation

- **Périodicité configurable** : annuelle, semestrielle, trimestrielle
- **Types d'évaluation** :
  - Auto-évaluation (l'employé s'évalue lui-même)
  - Évaluation par le supérieur hiérarchique
  - Évaluation par les pairs (360°)
  - Évaluation par les élèves/parents (pour les enseignants, si souhaité)
- **Grilles d'évaluation paramétrables** par catégorie de personnel

### 5.2 Grille d'évaluation enseignant (inspirée critères IB)

| Domaine | Critères |
|---|---|
| Pratique pédagogique | Qualité de l'enseignement, différenciation, évaluation des élèves |
| Gestion de classe | Climat, discipline, engagement des élèves |
| Collaboration | Travail en équipe, contribution aux projets transversaux |
| Développement pro | Formations suivies, veille pédagogique, innovation |
| Vie scolaire | Participation aux événements, surveillance, tutorat |
| Programme IB | Mise en œuvre du programme, respect des exigences IB, planification |

### 5.3 Observations de classe

- **Planification** : calendrier des visites de classe
- **Grille d'observation** paramétrable
- **Saisie en direct ou différé**
- **Feedback** écrit + réunion de débriefing planifiée
- **Suivi** des plans d'amélioration (actions à mener, échéances)

### 5.4 Objectifs professionnels

- Fixation d'objectifs annuels (SMART)
- Suivi trimestriel de progression
- Atteinte / Non-atteinte en fin de cycle
- Liens avec le plan de formation (Module 6)

---

## Module 6 — Formation et développement professionnel

### 6.1 Catalogue de formations

- **Formations internes** : proposées par l'établissement
- **Formations externes** : catalogue IB, universités, organismes
- **Catégories IB** :
  - Catégorie 1 (nouveaux enseignants IB)
  - Catégorie 2 (enseignants expérimentés IB)
  - Catégorie 3 (approfondissement thématique)
- **Fiche formation** : titre, organisme, dates, coût, durée, prérequis, places

### 6.2 Demandes de formation

```
Employé demande → Chef hiérarchique → DRH (validation budgétaire) → Acceptation/Refus → Inscription
```

- **Critères de validation** : lien avec objectifs professionnels, budget disponible, pertinence
- **Budget formation** : enveloppe par employé et/ou par programme
- **Suivi post-formation** : évaluation à chaud/à froid, mise en pratique

### 6.3 Dossier formation de l'employé

- Historique complet des formations suivies
- Certificats et attestations (upload PDF)
- Heures de formation cumulées par année
- Alertes certifications à renouveler (IB, secourisme, etc.)

---

## Module 7 — Recrutement

### 7.1 Postes à pourvoir

- Création d'une fiche de poste (intitulé, description, prérequis, campus, programme)
- Statut : brouillon → publié → en cours de recrutement → pourvu → annulé
- Date d'ouverture, date de clôture souhaitée
- Budget salarial alloué

### 7.2 Pipeline de recrutement

Étapes paramétrables :
1. **Réception candidature** (CV + lettre de motivation)
2. **Pré-sélection** (filtrage par critères)
3. **Entretien téléphonique / visio**
4. **Entretien sur site** (avec grille d'évaluation)
5. **Leçon de démonstration** (pour les enseignants)
6. **Test écrit / étude de cas**
7. **Vérification des références**
8. **Proposition d'embauche**
9. **Négociation / Acceptation**
10. **Intégration**

### 7.3 Fiche candidat

- CV + documents (upload)
- Coordonnées, nationalité, situation familiale
- Historique des étapes franchies
- Notes et évaluations des entretiens
- Grilles de notation standardisées
- Comparaison de candidats (vue comparative)

### 7.4 Intégration (onboarding)

- Checklist d'intégration paramétrable
- Tâches automatiques : création compte email, badge, accès logiciels
- Documents à fournir (liste avec suivi)
- Parcours de formation initiale
- Période d'accompagnement / mentorat
- Évaluation de la période d'essai

---

## Module 8 — Documents administratifs

### 8.1 Coffre-fort documentaire

Par employé, classement thématique :
- **Identité** : CNI/passeport, acte de naissance, photo
- **Diplômes** : Bac, Licence, Master, Doctorat, certifications
- **Contrats** : contrats de travail, avenants
- **Paie** : bulletins, attestations
- **Congés** : demandes, justificatifs médicaux
- **Évaluations** : comptes-rendus, objectifs
- **Formations** : certificats, attestations
- **Divers** : courriers, sanctions, récompenses

### 8.2 Fonctions documentaires

- Upload glisser-déposer (PDF, JPG, PNG, DOCX)
- Aperçu intégré
- Classement automatique par type
- Recherche plein texte (si OCR)
- Alertes expiration (pièce d'identité, certification, contrat CDD)
- Génération automatique de documents (contrats, certificats, attestations)

### 8.3 Génération de documents

| Document | Déclencheur |
|---|---|
| Contrat de travail | Validation recrutement |
| Avenant | Modification contrat |
| Certificat de travail | Départ employé |
| Attestation d'emploi | Demande employé / DRH |
| Attestation de salaire | Demande employé (banque, logement) |
| Courrier disciplinaire | Saisie incident |
| Lettre de mission | Affectation temporaire |

---

## Module 9 — Tableaux de bord et rapports

### 9.1 KPIs et indicateurs

**Effectif :**
- Effectif total, par campus, par catégorie, par programme, par sexe
- Pyramide des âges, pyramide d'ancienneté
- Taux d'encadrement (élèves/enseignant, élèves/staff)

**Mouvements :**
- Entrées/sorties par période (turnover)
- Taux de rétention annuel
- Ancienneté moyenne

**Absentéisme :**
- Taux d'absentéisme global, par catégorie, par période
- Jours d'absence par type (maladie, sans solde, injustifié)
- Top 10 des absents

**Budget :**
- Masse salariale mensuelle/annuelle
- Masse salariale par campus, par catégorie
- Projection glissements annuels (ancienneté, promotions)
- Budget formation consommé / alloué

### 9.2 Rapports périodiques

| Rapport | Périodicité | Destinataire |
|---|---|---|
| État du personnel | Mensuel | Direction |
| Rapport de paie | Mensuel | Comptabilité |
| Bilan social | Annuel | Direction / Conseil |
| Rapport CNSS | Mensuel/Trimestriel | CNSS |
| Déclaration ITS | Mensuel | Administration fiscale |
| Rapport IB (staffing) | Annuel | IBO |
| Audit interne | Annuel | Qualité |

### 9.3 Exports

- Tous les tableaux exportables en Excel/CSV/PDF
- Graphiques (donut, barres, courbes) interactifs
- Dashboard configurable (choix des widgets, disposition)

---

## Module 10 — Spécificités IB et internationales

### 10.1 Suivi des exigences IB par employé

- **Enseignant IB** : programme (PYP, MYP, DP, CP), matières, niveau de certification IB
- **Ateliers IB suivis** : catégorie, date, organisateur, certificat
- **Statut IB** : en formation, certifié, examinateur, chef d'équipe, visiteur d'établissement
- **Exigences IB** : rappel des formations obligatoires par cycle d'évaluation (5 ans)
- **Planning visites IB** : préparation, rôles des enseignants, documents à jour

### 10.2 Gestion des coordinateurs IB

- Coordinateur PYP, MYP, DP, CP — identification dans l'organigramme
- Charge de décharge horaire associée
- Suivi des réunions de programme
- Planification des évaluations/révisions IB
- Suivi des unités de recherche / planification collaborative

### 10.3 Expatriés et contrats internationaux

- Statut expatrié (contrat local vs contrat expatrié)
- Avantages spécifiques : billet d'avion annuel, déménagement, scolarité enfants, assurance santé internationale
- Gestion des visas et permis de travail (alerte expiration)
- Paie en devise locale et/ou devise étrangère
- Convention fiscale (exonération, double imposition)

---

## Module 11 — Spécificités locales (adaptables par pays)

### 11.1 Conformité Code du Travail

Paramétrage par pays (Togo par défaut, adaptable) :
- Durée légale du travail (40h/semaine au Togo)
- SMIG (Salaire Minimum Interprofessionnel Garanti)
- Congés légaux et leur durée
- Préavis de licenciement/démission selon ancienneté
- Indemnités de licenciement
- Jours fériés (calendrier national)

### 11.2 Organismes sociaux

- CNSS — taux de cotisation, plafond, déclarations
- Inspection du Travail — registre de l'employeur
- Médecine du travail — visites périodiques, suivi

### 11.3 Conventions collectives

- Possibilité de charger une convention collective (grille salariale, primes, classifications)
- Paramétrage des règles spécifiques à l'enseignement privé (confessionnel ou laïc)

---

## Module 12 — Courriers et modèles de lettres

### 12.1 Vision d'ensemble

Le module Courriers est le **centre de génération documentaire** du RH. Il centralise tous les modèles de lettres officielles nécessaires à la vie administrative d'un établissement scolaire, qu'ils soient émis par la DRH (courrier sortant) ou par l'employé (demande entrante).

**Objectifs :**
- Disposer d'un catalogue exhaustif de modèles prêts à l'emploi, spécifiques au secteur éducatif
- Générer un courrier en 3 clics : sélection employé → sélection modèle → les champs sont pré-remplis automatiquement
- Uniformiser la forme et le ton des communications officielles
- Garantir la conformité légale (mentions obligatoires, formules exécutoires)
- Traçabilité : chaque courrier généré est horodaté et archivé dans le dossier de l'employé

### 12.2 Catalogue exhaustif des modèles

Les modèles sont classés en deux grandes familles : **RH → Employé** (courrier descendant) et **Employé → RH** (demande montante).

---

#### 12.2.1 Famille A — Contrat et emploi (RH → Employé)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| A01 | **Contrat de travail — CDI** | Embauche définitive | Validation recrutement |
| A02 | **Contrat de travail — CDD** | Emploi temporaire / remplacement | Validation recrutement |
| A03 | **Contrat de travail — Temps partiel** | CDI ou CDD à temps réduit | Validation recrutement |
| A04 | **Contrat de vacation** | Enseignant à l'heure / examinateur | Validation recrutement |
| A05 | **Convention de stage** | Stagiaire / étudiant | Validation recrutement |
| A06 | **Avenant au contrat** | Modification salaire, temps, affectation | Modification contrat |
| A07 | **Renouvellement de CDD** | Prolongation de contrat | Décision direction |
| A08 | **Confirmation fin de période d'essai** | Période d'essai concluante | Échéance période d'essai |
| A09 | **Non-renouvellement de période d'essai** | Rupture pendant l'essai | Décision direction |
| A10 | **Lettre de mission** | Mission ponctuelle (examen, projet) | Nouvelle mission |
| A11 | **Notification de fin de CDD** | Fin de contrat sans renouvellement | Échéance CDD |
| A12 | **Proposition de CDI après CDD** | Transformation CDD → CDI | Décision direction |

#### 12.2.2 Famille B — Rémunération et avantages (RH → Employé)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| B01 | **Notification d'augmentation** | Hausse salariale / changement échelon | Décision direction |
| B02 | **Notification de promotion** | Changement de grade / fonction | Décision direction |
| B03 | **Notification de prime exceptionnelle** | Prime de bilan, 13e mois, gratification | Décision direction |
| B04 | **Notification de mutation** | Changement de campus | Décision direction |
| B05 | **Confirmation d'ancienneté** | Attestation années de service | Demande employé |
| B06 | **Attestation d'emploi** | Justificatif pour banque, logement, visa | Demande employé |
| B07 | **Attestation d'emploi — version IB** | Format exigé par l'IBO pour visite d'évaluation | Préparation visite IB |
| B08 | **Attestation de salaire** | Justificatif de revenus | Demande employé |
| B09 | **Certificat de travail** | Document obligatoire de fin de contrat | Départ employé |
| B10 | **Attestation de retenue ITS** | Justificatif fiscal annuel | Fin d'exercice fiscal |
| B11 | **Attestation CNSS** | Justificatif sécurité sociale | Demande employé |

#### 12.2.3 Famille C — Discipline et rappels à l'ordre (RH → Employé)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| C01 | **Rappel à l'ordre — Absences** | Premier niveau après absences injustifiées répétées | Seuil atteint (ex : 3 absences) |
| C02 | **Rappel à l'ordre — Retards** | Premier niveau après retards répétés | Seuil atteint (ex : 5 retards) |
| C03 | **Rappel à l'ordre — Manquement professionnel** | Comportement inapproprié, non-respect consignes | Signalement hiérarchique |
| C04 | **Avertissement écrit** | Premier niveau disciplinaire formel | Décision DRH |
| C05 | **Blâme** | Deuxième niveau disciplinaire | Décision DRH + Direction |
| C06 | **Mise à pied conservatoire** | Suspension temporaire avec retenue salaire | Faute grave présumée |
| C07 | **Convocation à entretien préalable — Sanction** | Entretien avant sanction disciplinaire | Procédure disciplinaire |
| C08 | **Convocation à entretien préalable — Licenciement** | Entretien avant licenciement | Procédure licenciement |
| C09 | **Notification de sanction disciplinaire** | Décision finale après entretien | Suite entretien |
| C10 | **Notification de licenciement** | Rupture du contrat pour faute | Décision direction |
| C11 | **Notification de licenciement économique** | Suppression de poste | Décision direction |
| C12 | **Mise en demeure — Abandon de poste** | Absence prolongée sans justificatif | Seuil critique atteint |

#### 12.2.4 Famille D — Congés et absences (RH → Employé)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| D01 | **Accusé réception demande de congé** | Confirmation de prise en compte | Demande reçue |
| D02 | **Accord de congé annuel** | Validation congé payé | Demande approuvée |
| D03 | **Refus de congé annuel** | Refus motivé (service, pic activité) | Demande refusée |
| D04 | **Accord de congé sans solde** | Validation absence non rémunérée | Demande approuvée |
| D05 | **Refus de congé sans solde** | Refus motivé | Demande refusée |
| D06 | **Confirmation congé maladie** | Accusé réception avec rappel obligations (certificat sous 48h) | Réception certificat |
| D07 | **Accord de congé de formation** | Validation absence pour formation | Demande approuvée |
| D08 | **Accord de congé familial** | Mariage, décès, naissance | Demande approuvée |
| D09 | **Notification congé maternité** | Confirmation dates et droits | Déclaration grossesse |
| D10 | **Accord de congé paternité** | Validation 3 jours | Demande approuvée |
| D11 | **Refus de congé maternité/paternité** | Refus motivé (rare — non-respect conditions) | Demande non conforme |
| D12 | **Demande de justificatif complémentaire** | Certificat médical manquant, pièce justificative | Absence non justifiée |

#### 12.2.5 Famille E — Fin de contrat et départ (RH → Employé)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| E01 | **Accusé réception de démission** | Confirmation réception lettre démission | Réception démission |
| E02 | **Dispense de préavis** | Accord de la direction pour réduire/annuler le préavis | Décision direction |
| E03 | **Refus de dispense de préavis** | Le préavis complet est exigé | Décision direction |
| E04 | **Rappel obligations de préavis** | Courrier de rappel si employé ne respecte pas le préavis | Non-respect constaté |
| E05 | **Solde de tout compte** | Reçu pour solde de tout compte (document légal) | Départ effectif |
| E06 | **Certificat de travail** | Document obligatoire remis au départ | Départ effectif |
| E07 | **Attestation Pôle Emploi / Assedic** | Document pour droits chômage (si applicable) | Départ effectif |
| E08 | **Lettre de recommandation** | À la demande de l'employé, sur papier en-tête | Demande employé |
| E09 | **Notification départ retraite** | Confirmation date et calcul indemnité | Départ retraite |
| E10 | **Convention de rupture conventionnelle** | Accord mutuel de rupture | Négociation aboutie |
| E11 | **Homologation rupture conventionnelle** | Document final après délai de rétractation | Fin délai rétractation |

#### 12.2.6 Famille F — Vie professionnelle et administrative (RH → Employé)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| F01 | **Convocation à réunion** | Réunion pédagogique, administrative, conseil | Planification réunion |
| F02 | **Convocation à entretien professionnel** | Entretien annuel d'évaluation | Cycle évaluation |
| F03 | **Convocation à entretien de retour** | Retour après absence longue (maladie > 3 mois) | Reprise effective |
| F04 | **Convocation à visite médicale** | Médecine du travail (visite périodique / reprise) | Échéance / réintégration |
| F05 | **Note de service** | Communication officielle à tout ou partie du personnel | Décision direction |
| F06 | **Circulaire interne** | Information générale (rentrée, sécurité, procédures) | Événement / besoin |
| F07 | **Notification de changement d'affectation** | Changement de classe, niveau, programme | Décision coordinateur |
| F08 | **Notification de changement d'horaires** | Modification de l'emploi du temps | Réorganisation |
| F09 | **Demande de pièces administratives** | Documents manquants au dossier | Vérification dossier |
| F10 | **Notification d'échéance administrative** | Permis de travail, visa, certification à renouveler | Échéance approche (J-60) |
| F11 | **Accusé réception de courrier** | Confirmation réception d'un courrier employé | Réception courrier |
| F12 | **Notification de décision** | Décision générique (jury, commission, conseil) | Décision rendue |
| F13 | **Lettre de félicitations** | Reconnaissance exceptionnelle (prix, publication, résultats) | Fait notable |
| F14 | **Lettre de remerciement** | Départ volontaire, fin de mission, retraite | Départ |

#### 12.2.7 Famille G — Recrutement (RH → Candidat)

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| G01 | **Accusé réception candidature** | Confirmation de réception CV + LM | Candidature reçue |
| G02 | **Convocation à entretien** | Entretien téléphonique, visio, ou sur site | Présélection |
| G03 | **Convocation à leçon de démonstration** | Test pédagogique pour enseignants | Présélection |
| G04 | **Refus de candidature** | Candidature non retenue après examen | Décision recrutement |
| G05 | **Proposition d'embauche** | Offre formelle avec conditions (salaire, dates) | Candidat retenu |
| G06 | **Confirmation d'embauche** | Confirmation après acceptation de l'offre | Acceptation reçue |
| G07 | **Demande de références** | Contact des anciens employeurs | Vérification références |
| G08 | **Demande de pièces complémentaires** | Documents manquants (diplômes, casier judiciaire) | Constitution dossier |

#### 12.2.8 Famille H — Employé → RH (demandes montantes)

| # | Modèle | Usage | Initiateur |
|---|---|---|---|
| H01 | **Demande de congé annuel** | Congé payé | Employé |
| H02 | **Demande de congé maladie** | Avec certificat médical en PJ | Employé |
| H03 | **Demande de congé sans solde** | Absence non rémunérée | Employé |
| H04 | **Demande de congé de formation** | Formation professionnelle | Employé |
| H05 | **Demande de congé familial** | Mariage, décès, naissance | Employé |
| H06 | **Demande d'autorisation d'absence** | Absence ponctuelle (rendez-vous administratif, médical) | Employé |
| H07 | **Demande de congé maternité** | Avec certificat médical | Employée |
| H08 | **Demande de congé paternité** | Avec acte de naissance | Employé |
| H09 | **Demande d'aménagement d'horaires** | Temps partiel, horaires adaptés | Employé |
| H10 | **Demande de formation** | Inscription à une formation externe ou IB | Employé |
| H11 | **Demande d'attestation** | Emploi, salaire, travail | Employé |
| H12 | **Lettre de démission** | Départ volontaire | Employé |
| H13 | **Demande de rupture conventionnelle** | Rupture à l'amiable | Employé |
| H14 | **Demande de départ à la retraite** | Liquidation droits retraite | Employé |
| H15 | **Demande de mise à disposition syndicale** | Détachement syndical | Employé |
| H16 | **Contestation de sanction disciplinaire** | Recours contre avertissement/blâme | Employé |
| H17 | **Réclamation salariale** | Erreur paie, heures non payées, primes | Employé |
| H18 | **Demande d'avance sur salaire** | Demande d'acompte | Employé |
| H19 | **Déclaration de grossesse** | Information officielle pour droits maternité | Employée |
| H20 | **Changement de coordonnées** | Adresse, téléphone, email, situation familiale | Employé |
| H21 | **Demande de remboursement de frais** | Frais professionnels, mission, déplacement | Employé |
| H22 | **Signalement — Harcèlement ou discrimination** | Alerte RH formelle | Employé |
| H23 | **Demande de visite médicale** | Médecine du travail | Employé |
| H24 | **Demande de temps partiel** | Réduction du temps de travail | Employé |

#### 12.2.9 Famille I — Spécifique IB / International

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| I01 | **Attestation d'enseignement IB** | Justificatif expérience programme IB pour IB Educator Certificate | Demande enseignant |
| I02 | **Lettre de recommandation IB** | Candidature à un poste IB dans une autre école | Demande enseignant |
| I03 | **Confirmation supervision EE / Mémoire / PP** | Attestation de charge d'encadrement | Demande enseignant |
| I04 | **Notification affectation examinateur IB** | Désignation pour correction d'examens IB | Désignation IB |
| I05 | **Invitation à atelier IB** | Convocation à une formation IB (Cat. 1/2/3) | Inscription atelier |
| I06 | **Attestation de visiteur d'établissement IB** | Justificatif pour IBEN (IB Educator Network) | Mission IB |

#### 12.2.10 Famille J — Syndical et instances représentatives

| # | Modèle | Usage | Déclencheur typique |
|---|---|---|---|
| J01 | **Convocation réunion des délégués du personnel** | Réunion périodique obligatoire | Échéance légale |
| J02 | **Procès-verbal de réunion DP** | Compte-rendu officiel | Réunion tenue |
| J03 | **Réponse à revendication syndicale** | Réponse écrite de la direction | Revendication reçue |
| J04 | **Notification élections professionnelles** | Organisation scrutin | Échéance mandat |
| J05 | **Accord d'établissement** | Accord collectif négocié | Négociation aboutie |

### 12.3 Fonctionnalités du module Courriers

#### 12.3.1 Gestionnaire de modèles

- **Catalogue intégré** : les ~75 modèles listés ci-dessus sont livrés pré-remplis en français (modèles par défaut)
- **Éditeur de modèle** : interface WYSIWYG ou édition du DOCX source
- **Variables de fusion** : chaque modèle contient des placeholders `{{nom}}`, `{{date}}`, etc. (cf. §12.4)
- **Import personnalisé** : le RH peut ajouter ses propres modèles DOCX
- **Duplication** : créer une variante d'un modèle existant sans repartir de zéro
- **Gestion des versions** : chaque modification crée une nouvelle version horodatée ; possibilité de revenir à une version antérieure
- **Activation / désactivation** : masquer un modèle obsolète sans le supprimer
- **Catégorisation** : par famille (A à J) + tags personnalisés
- **Recherche** : par mot-clé dans le titre ou le contenu du modèle

#### 12.3.2 Génération de courrier

Workflow en 3 étapes :

1. **Sélection du destinataire** : employé (ou candidat) depuis la grille ou la fiche détail
2. **Sélection du modèle** : navigation par familles ou recherche plein texte
3. **Prévisualisation et génération** :
   - Tous les champs connus sont pré-remplis automatiquement (nom, dates, poste, salaire, etc.)
   - Les champs manquants sont mis en évidence pour saisie manuelle
   - Prévisualisation en temps réel (rendu HTML ou DOCX)
   - Bouton "Générer" → ouverture du DOCX/PDF final

#### 12.3.3 Fonctions complémentaires

- **Envoi direct par email** : le courrier généré est envoyé à l'adresse email professionnelle de l'employé
- **Impression directe** : avec en-tête officiel de l'établissement
- **Archivage automatique** : chaque courrier généré est horodaté et classé dans le dossier documentaire de l'employé (Module 8, catégorie "Courriers")
- **Historique des générations** : qui a généré quel courrier, pour qui, quand
- **Envoi groupé** : sélectionner N employés, générer le même courrier pour tous (ex : convocation à la réunion de rentrée)
- **Signature électronique** : possibilité d'insérer une signature scannée du directeur/DRH
- **Numérotation automatique** : incrémentation du numéro de référence (ex : `RH/2026/0142`)
- **Log de traçabilité** : toute génération est journalisée (auteur, destinataire, modèle, date)

#### 12.3.4 Parapheur électronique (workflow optionnel Phase 3)

- Circuit de validation avant envoi : Brouillon → Relecture DRH → Signature Direction → Envoyé
- Possibilité de commentaires / annotations avant validation
- Délégation automatique en cas d'absence du signataire

### 12.4 Variables de fusion disponibles

Chaque modèle peut utiliser les variables suivantes, automatiquement remplies depuis la base :

#### Variables employé

| Variable | Source | Description |
|---|---|---|
| `{{civilite}}` | `title` | M., Mme, Dr |
| `{{prenom}}` | `first_name` | Prénom |
| `{{nom}}` | `last_name` | Nom de famille |
| `{{nom_complet}}` | Calculé | `{{civilite}} {{prenom}} {{nom}}` |
| `{{date_naissance}}` | `birth_date` | JJ/MM/AAAA |
| `{{nationalite}}` | `nationality` | Nationalité |
| `{{adresse}}` | `address` | Adresse complète |
| `{{telephone}}` | `phone` | Téléphone |
| `{{email}}` | `email` | Email |
| `{{matricule}}` | `id` | Numéro matricule |
| `{{poste}}` | `job_title` | Intitulé du poste |
| `{{campus}}` | Calculé via jointure | Campus d'affectation |
| `{{anciennete}}` | Calculé | Ancienneté en années/mois |
| `{{date_embauche}}` | `hire_date` | Date d'embauche |
| `{{type_contrat}}` | `contract_type` | CDI, CDD, etc. |
| `{{salaire_brut}}` | `salary` | Salaire brut mensuel |
| `{{statut}}` | `emp_status` | Actif, Suspendu, etc. |
| `{{categorie_pro}}` | `professional_category` | Cadre / Agent de maîtrise / Employé |
| `{{superieur}}` | Calculé | Nom du supérieur hiérarchique |

#### Variables établissement

| Variable | Source | Description |
|---|---|---|
| `{{nom_ecole}}` | Configuration | Nom officiel de l'établissement |
| `{{adresse_ecole}}` | Configuration | Adresse du siège |
| `{{telephone_ecole}}` | Configuration | Téléphone officiel |
| `{{email_ecole}}` | Configuration | Email officiel |
| `{{logo_ecole}}` | Fichier | Logo en en-tête |
| `{{nom_directeur}}` | Configuration | Nom du chef d'établissement |
| `{{nom_DRH}}` | Configuration | Nom du DRH |
| `{{cachet_ecole}}` | Image | Cachet humide scanné |

#### Variables contexte

| Variable | Source | Description |
|---|---|---|
| `{{date_jour}}` | Système | Date du jour |
| `{{date_debut}}` | Contexte | Date de début (congé, contrat, etc.) |
| `{{date_fin}}` | Contexte | Date de fin |
| `{{motif}}` | Saisie | Motif du courrier |
| `{{reference}}` | Auto | Numéro de référence |
| `{{objet}}` | Auto/saisie | Objet du courrier |
| `{{corps}}` | Modèle | Corps du texte (partie variable saisissable) |
| `{{signature}}` | Configuration | Nom et fonction du signataire |

### 12.5 Architecture technique

#### Base de données

```sql
CREATE TABLE hr_letter_template (
    id SERIAL PRIMARY KEY,
    family CHAR(1) NOT NULL,       -- A à J
    code VARCHAR(8) NOT NULL,       -- ex: A01, H04
    title VARCHAR(200) NOT NULL,    -- Titre affiché
    description TEXT,               -- Usage / contexte
    docx_template BYTEA,            -- Fichier DOCX source (template python-docx)
    variables TEXT[],                -- Liste des variables utilisées (ex: {civilite, nom, date_jour})
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    is_builtin BOOLEAN DEFAULT true, -- true = livré par défaut, false = ajouté par l'utilisateur
    created_by INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE hr_generated_letter (
    id SERIAL PRIMARY KEY,
    staff_id INT NOT NULL,           -- Destinataire
    template_id INT NOT NULL,        -- Modèle utilisé
    file_path VARCHAR(500),          -- Chemin fichier généré (PDF/DOCX)
    reference VARCHAR(50),           -- Numéro de référence RH/2026/0142
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    generated_by INT,                -- ID utilisateur ayant généré
    status VARCHAR(20) DEFAULT 'draft'  -- draft, sent, archived
);
```

#### Génération DOCX

- Utilisation de `python-docx` pour le remplacement des variables dans les templates
- Les placeholders `{{variable}}` sont détectés et remplacés par les valeurs réelles
- Le logo et les signatures sont insérés comme images
- Le fichier final est sauvegardé en `.docx` et exportable en `.pdf`

#### Interface utilisateur

L'interface reprend le pattern Q7 (section cards) + barre latérale :

```
┌────────────────────────────────────────────────────────────────┐
│  Courriers                                          [+ Nouveau]│
├──────────┬─────────────────────────────────────────────────────┤
│          │                                                     │
│ Familles │  ┌─────────────────────────────────────────────┐    │
│          │  │                                             │    │
│ ▸ A Contrat   │  C01 — Rappel à l'ordre — Absences        │    │
│ ▸ B Rémunér.  │  Modèle de premier rappel après 3 absences │    │
│ ▸ C Discipl.  │  injustifiées consécutives.                │    │
│ ▸ D Congés    │  Variables : nom, date_jour, nb_absences   │    │
│ ▸ E Départ    │                                             │    │
│ ▸ F Vie pro   │  [Aperçu] [Générer] [Modifier]            │    │
│ ▸ G Recrut.   │                                             │    │
│   H Demandes   │  └─────────────────────────────────────────────┘    │
│ ▸ I IB/Inter. │                                                     │
│ ▸ J Syndical  │  ┌─────────────────────────────────────────────┐    │
│               │  │ C02 — Rappel à l'ordre — Retards           │    │
│               │  │ ...                                         │    │
│               │  └─────────────────────────────────────────────┘    │
│          │                                                     │
└──────────┴─────────────────────────────────────────────────────┘
```

### 12.6 Priorisation

| # | Fonctionnalité | Effort | Phase |
|---|---|---|---|
| 12.1 | Catalogue des ~75 modèles intégrés (fichiers DOCX pré-remplis) | 5j | Phase 1 |
| 12.2 | Interface gestionnaire de modèles (navigation familles, recherche) | 4j | Phase 1 |
| 12.3 | Moteur de fusion variables (python-docx) + prévisualisation | 5j | Phase 1 |
| 12.4 | Workflow génération en 3 clics (sélection → prévisualisation → génération) | 3j | Phase 1 |
| 12.5 | Archivage automatique dans dossier employé | 2j | Phase 1 |
| 12.6 | Numérotation automatique des références | 1j | Phase 1 |
| 12.7 | Import / édition de modèles personnalisés | 2j | Phase 2 |
| 12.8 | Envoi groupé (N employés simultanément) | 2j | Phase 2 |
| 12.9 | Envoi direct par email | 2j | Phase 2 |
| 12.10 | Parapheur électronique (workflow validation) | 5j | Phase 3 |

**Total Module 12** : ~31 jours/homme (20j Phase 1 socle minimal, 6j Phase 2, 5j Phase 3)

---

## Récapitulatif et priorisation

### Déjà réalisé (LarcRH v1)

| Composant | Couverture |
|---|---|
| Authentification (Intranet/Cloud) | ✓ |
| Grille photos par catégorie | ✓ |
| Fiche employé basique | ✓ |
| Événements/absences simples | ✓ |
| Gestionnaire documentaire (upload/métadonnées) | ✓ |

### Priorités d'implémentation

#### Phase 1 — Fondations (socle RH minimal)

| # | Fonctionnalité | Effort |
|---|---|---|
| 1.1 | Fiche employé enrichie (25+ champs) | 5j |
| 1.2 | Filtres, recherche plein texte, export CSV | 3j |
| 2.1 | Gestion des contrats (création, historique, alertes) | 8j |
| 3.1 | Solde de congés (crédit automatique, décompte) | 5j |
| 3.3 | Workflow demande/validation de congé | 7j |
| 8.1 | Coffre-fort documentaire par employé | 5j |
| **12.1-5** | **Module Courriers — 75 modèles + fusion + génération 3 clics** | **20j** |

**Total Phase 1** : ~53 jours

#### Phase 2 — Gestion avancée

| # | Fonctionnalité | Effort |
|---|---|---|
| 2.2 | Workflow fin de contrat + checklist départ | 5j |
| 2.3 | Organigramme interactif | 4j |
| 1.2.3 | Portail self-service employé | 8j |
| 4.1 | Structure de rémunération + grille salariale | 6j |
| 4.2 | Génération bulletins de paie | 10j |
| 5.1 | Cycles d'évaluation | 6j |
| 8.3 | Génération automatique de documents | 5j |

**Total Phase 2** : ~44 jours

#### Phase 3 — Modules spécialisés

| # | Fonctionnalité | Effort |
|---|---|---|
| 7.1-7.4 | Module recrutement (pipeline complet) | 10j |
| 5.2-5.4 | Observations de classe + objectifs pro | 7j |
| 6.1-6.3 | Module formation et développement pro | 7j |
| 4.3 | Déclarations sociales et fiscales | 8j |
| 10.x | Spécificités IB | 6j |
| 10.3 | Gestion expatriés | 5j |
| 9.x | Tableaux de bord et KPIs | 8j |

**Total Phase 3** : ~51 jours

#### Phase 4 — Conformité et international

| # | Fonctionnalité | Effort |
|---|---|---|
| 11.x | Adaptation multi-pays (paramétrage Code du Travail) | 8j |
| 10.x | Rapports IB, visites d'évaluation | 5j |
| 9.x | Rapports périodiques automatisés | 5j |
| — | Mobile (Flutter via LarcSupMobile) | 15j |

**Total Phase 4** : ~33 jours

---

### Synthèse des efforts

| Phase | Contenu | Effort estimé | Couverture fonctionnelle |
|---|---|---|---|
| Phase 1 | Fondations | 53 j/h | ~40% |
| Phase 2 | Gestion avancée | 44 j/h | ~70% |
| Phase 3 | Modules spécialisés | 51 j/h | ~90% |
| Phase 4 | Conformité + mobile | 33 j/h | ~100% |
| **Total** | | **~181 jours/homme** | |

### Décisions architecturales à prendre

1. **Moteur de calcul de paie** : développement interne vs API externe vs intégration avec un logiciel de paie existant (le plus complexe techniquement)
2. **Génération PDF** : bibliothèque Python (ReportLab/WeasyPrint) vs templates DOCX (python-docx)
3. **Self-service** : portail web (Flask/FastAPI) vs module intégré dans l'app desktop PySide6
4. **Mobile** : Flutter (conformément au projet LarcSupMobile) vs PWA
5. **Multi-pays** : fichier de configuration par pays (YAML/JSON) vs base de données paramétrique

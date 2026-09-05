-- LarcRH — Migration Courriers et modèles de lettres (Module 12)
-- À exécuter sur Intranet (127.0.0.1:5432) ET Supabase Cloud (6543)
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260808_hr_letters.sql

BEGIN;

-- ============================================================================
-- 1. hr_letter_template — Catalogue des modèles de courriers
-- ============================================================================

CREATE TABLE IF NOT EXISTS hr_letter_template (
    id          SERIAL PRIMARY KEY,
    family      CHAR(1)      NOT NULL,   -- A à J (cf. Module 12 §12.2)
    code        VARCHAR(8)   NOT NULL,   -- ex: 'A01', 'H04'
    title       VARCHAR(200) NOT NULL,   -- Titre affiché
    description TEXT,                     -- Usage / contexte / déclencheur
    docx_data   BYTEA,                   -- Fichier DOCX template (python-docx)
    variables   TEXT[],                   -- Placeholders: {civilite, nom, date_jour, ...}
    version     INT DEFAULT 1,
    is_active   BOOLEAN DEFAULT TRUE,
    is_builtin  BOOLEAN DEFAULT TRUE,    -- TRUE = livré par défaut, FALSE = ajout utilisateur
    created_by  INT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_letter_template_family ON hr_letter_template(family, is_active);
CREATE INDEX IF NOT EXISTS idx_letter_template_code   ON hr_letter_template(code);

-- ============================================================================
-- 2. hr_generated_letter — Courriers générés (archives)
-- ============================================================================

CREATE TABLE IF NOT EXISTS hr_generated_letter (
    id           SERIAL PRIMARY KEY,
    staff_id     INT          NOT NULL,   -- Destinataire (FK larcauth_aecuser.id)
    template_id  INT          NOT NULL,   -- Modèle utilisé (FK hr_letter_template.id)
    file_path    VARCHAR(500),            -- Chemin fichier généré (DOCX/PDF)
    reference    VARCHAR(50),             -- Numéro référence: RH/2026/0142
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    generated_by INT,                     -- ID utilisateur ayant généré
    status       VARCHAR(20) DEFAULT 'draft'  -- draft, sent, archived
);

CREATE INDEX IF NOT EXISTS idx_generated_letter_staff    ON hr_generated_letter(staff_id);
CREATE INDEX IF NOT EXISTS idx_generated_letter_template ON hr_generated_letter(template_id);

-- ============================================================================
-- 3. Seed — ~75 modèles de courriers (métadonnées uniquement, sans template DOCX)
--    Les fichiers DOCX seront créés ultérieurement via python-docx.
-- ============================================================================

INSERT INTO hr_letter_template (family, code, title, description) VALUES
-- Famille A — Contrat et emploi
('A', 'A01', 'Contrat de travail — CDI',                'Embauche définitive. Déclencheur : validation recrutement.'),
('A', 'A02', 'Contrat de travail — CDD',                'Emploi temporaire / remplacement. Déclencheur : validation recrutement.'),
('A', 'A03', 'Contrat de travail — Temps partiel',      'CDI ou CDD à temps réduit. Déclencheur : validation recrutement.'),
('A', 'A04', 'Contrat de vacation',                     'Enseignant à l''heure / examinateur. Déclencheur : validation recrutement.'),
('A', 'A05', 'Convention de stage',                     'Stagiaire / étudiant. Déclencheur : validation recrutement.'),
('A', 'A06', 'Avenant au contrat',                      'Modification salaire, temps, affectation. Déclencheur : modification contrat.'),
('A', 'A07', 'Renouvellement de CDD',                   'Prolongation de contrat. Déclencheur : décision direction.'),
('A', 'A08', 'Confirmation fin de période d''essai',     'Période d''essai concluante. Déclencheur : échéance période d''essai.'),
('A', 'A09', 'Non-renouvellement de période d''essai',   'Rupture pendant l''essai. Déclencheur : décision direction.'),
('A', 'A10', 'Lettre de mission',                       'Mission ponctuelle (examen, projet). Déclencheur : nouvelle mission.'),
('A', 'A11', 'Notification de fin de CDD',              'Fin de contrat sans renouvellement. Déclencheur : échéance CDD.'),
('A', 'A12', 'Proposition de CDI après CDD',            'Transformation CDD → CDI. Déclencheur : décision direction.'),

-- Famille B — Rémunération et avantages
('B', 'B01', 'Notification d''augmentation',            'Hausse salariale / changement échelon.'),
('B', 'B02', 'Notification de promotion',               'Changement de grade / fonction.'),
('B', 'B03', 'Notification de prime exceptionnelle',    'Prime de bilan, 13e mois, gratification.'),
('B', 'B04', 'Notification de mutation',                'Changement de campus.'),
('B', 'B05', 'Confirmation d''ancienneté',              'Attestation années de service.'),
('B', 'B06', 'Attestation d''emploi',                    'Justificatif pour banque, logement, visa.'),
('B', 'B07', 'Attestation d''emploi — version IB',       'Format exigé par l''IBO pour visite d''évaluation.'),
('B', 'B08', 'Attestation de salaire',                  'Justificatif de revenus.'),
('B', 'B09', 'Certificat de travail',                   'Document obligatoire de fin de contrat.'),
('B', 'B10', 'Attestation de retenue ITS',              'Justificatif fiscal annuel.'),
('B', 'B11', 'Attestation CNSS',                        'Justificatif sécurité sociale.'),

-- Famille C — Discipline
('C', 'C01', 'Rappel à l''ordre — Absences',            'Premier niveau après absences injustifiées répétées.'),
('C', 'C02', 'Rappel à l''ordre — Retards',             'Premier niveau après retards répétés.'),
('C', 'C03', 'Rappel à l''ordre — Manquement pro.',     'Comportement inapproprié, non-respect consignes.'),
('C', 'C04', 'Avertissement écrit',                     'Premier niveau disciplinaire formel.'),
('C', 'C05', 'Blâme',                                   'Deuxième niveau disciplinaire.'),
('C', 'C06', 'Mise à pied conservatoire',               'Suspension temporaire avec retenue salaire.'),
('C', 'C07', 'Convocation entretien préalable — Sanction', 'Entretien avant sanction disciplinaire.'),
('C', 'C08', 'Convocation entretien préalable — Licenciement', 'Entretien avant licenciement.'),
('C', 'C09', 'Notification de sanction disciplinaire',  'Décision finale après entretien.'),
('C', 'C10', 'Notification de licenciement',            'Rupture du contrat pour faute.'),
('C', 'C11', 'Notification de licenciement économique', 'Suppression de poste.'),
('C', 'C12', 'Mise en demeure — Abandon de poste',     'Absence prolongée sans justificatif.'),

-- Famille D — Congés (RH → Employé)
('D', 'D01', 'Accusé réception demande de congé',       'Confirmation de prise en compte.'),
('D', 'D02', 'Accord de congé annuel',                  'Validation congé payé.'),
('D', 'D03', 'Refus de congé annuel',                   'Refus motivé (service, pic activité).'),
('D', 'D04', 'Accord de congé sans solde',              'Validation absence non rémunérée.'),
('D', 'D05', 'Refus de congé sans solde',               'Refus motivé.'),
('D', 'D06', 'Confirmation congé maladie',              'Accusé réception avec rappel obligations (certificat sous 48h).'),
('D', 'D07', 'Accord de congé de formation',            'Validation absence pour formation.'),
('D', 'D08', 'Accord de congé familial',                'Mariage, décès, naissance.'),
('D', 'D09', 'Notification congé maternité',            'Confirmation dates et droits.'),
('D', 'D10', 'Accord de congé paternité',               'Validation 3 jours.'),
('D', 'D11', 'Refus de congé maternité/paternité',      'Refus motivé (non-respect conditions).'),
('D', 'D12', 'Demande de justificatif complémentaire',  'Certificat médical manquant, pièce justificative.'),

-- Famille E — Fin de contrat
('E', 'E01', 'Accusé réception de démission',           'Confirmation réception lettre démission.'),
('E', 'E02', 'Dispense de préavis',                     'Accord pour réduire/annuler le préavis.'),
('E', 'E03', 'Refus de dispense de préavis',            'Le préavis complet est exigé.'),
('E', 'E04', 'Rappel obligations de préavis',           'Courrier si employé ne respecte pas le préavis.'),
('E', 'E05', 'Solde de tout compte',                    'Reçu pour solde de tout compte (document légal).'),
('E', 'E06', 'Certificat de travail',                   'Document obligatoire remis au départ.'),
('E', 'E07', 'Attestation Pôle Emploi / Assedic',       'Document pour droits chômage.'),
('E', 'E08', 'Lettre de recommandation',                'Sur papier en-tête, à la demande.'),
('E', 'E09', 'Notification départ retraite',            'Confirmation date et calcul indemnité.'),
('E', 'E10', 'Convention de rupture conventionnelle',   'Accord mutuel de rupture.'),
('E', 'E11', 'Homologation rupture conventionnelle',    'Document final après délai de rétractation.'),

-- Famille F — Vie professionnelle
('F', 'F01', 'Convocation à réunion',                   'Réunion pédagogique, administrative, conseil.'),
('F', 'F02', 'Convocation à entretien professionnel',   'Entretien annuel d''évaluation.'),
('F', 'F03', 'Convocation à entretien de retour',       'Retour après absence longue (maladie > 3 mois).'),
('F', 'F04', 'Convocation à visite médicale',           'Médecine du travail (visite périodique / reprise).'),
('F', 'F05', 'Note de service',                         'Communication officielle à tout ou partie du personnel.'),
('F', 'F06', 'Circulaire interne',                      'Information générale (rentrée, sécurité, procédures).'),
('F', 'F07', 'Notification de changement d''affectation','Changement de classe, niveau, programme.'),
('F', 'F08', 'Notification de changement d''horaires',   'Modification de l''emploi du temps.'),
('F', 'F09', 'Demande de pièces administratives',       'Documents manquants au dossier.'),
('F', 'F10', 'Notification d''échéance administrative',  'Permis de travail, visa, certification à renouveler.'),
('F', 'F11', 'Accusé réception de courrier',            'Confirmation réception courrier employé.'),
('F', 'F12', 'Notification de décision',                'Décision générique (jury, commission, conseil).'),
('F', 'F13', 'Lettre de félicitations',                 'Reconnaissance exceptionnelle.'),
('F', 'F14', 'Lettre de remerciement',                  'Départ volontaire, fin de mission, retraite.'),

-- Famille G — Recrutement
('G', 'G01', 'Accusé réception candidature',            'Confirmation de réception CV + LM.'),
('G', 'G02', 'Convocation à entretien',                 'Entretien téléphonique, visio, ou sur site.'),
('G', 'G03', 'Convocation à leçon de démonstration',    'Test pédagogique pour enseignants.'),
('G', 'G04', 'Refus de candidature',                    'Candidature non retenue après examen.'),
('G', 'G05', 'Proposition d''embauche',                  'Offre formelle avec conditions (salaire, dates).'),
('G', 'G06', 'Confirmation d''embauche',                  'Confirmation après acceptation de l''offre.'),
('G', 'G07', 'Demande de références',                   'Contact des anciens employeurs.'),
('G', 'G08', 'Demande de pièces complémentaires',       'Documents manquants (diplômes, casier judiciaire).'),

-- Famille H — Demandes montantes (Employé → RH)
('H', 'H01', 'Demande de congé annuel',                 'Congé payé. Initiateur : Employé.'),
('H', 'H02', 'Demande de congé maladie',                'Avec certificat médical en PJ. Initiateur : Employé.'),
('H', 'H03', 'Demande de congé sans solde',             'Absence non rémunérée. Initiateur : Employé.'),
('H', 'H04', 'Demande de congé de formation',           'Formation professionnelle. Initiateur : Employé.'),
('H', 'H05', 'Demande de congé familial',               'Mariage, décès, naissance. Initiateur : Employé.'),
('H', 'H06', 'Demande d''autorisation d''absence',       'Absence ponctuelle (rdv administratif, médical).'),
('H', 'H07', 'Demande de congé maternité',              'Avec certificat médical. Initiatrice : Employée.'),
('H', 'H08', 'Demande de congé paternité',              'Avec acte de naissance. Initiateur : Employé.'),
('H', 'H09', 'Demande d''aménagement d''horaires',       'Temps partiel, horaires adaptés.'),
('H', 'H10', 'Demande de formation',                    'Inscription à une formation externe ou IB.'),
('H', 'H11', 'Demande d''attestation',                   'Emploi, salaire, travail.'),
('H', 'H12', 'Lettre de démission',                     'Départ volontaire. Initiateur : Employé.'),
('H', 'H13', 'Demande de rupture conventionnelle',      'Rupture à l''amiable. Initiateur : Employé.'),
('H', 'H14', 'Demande de départ à la retraite',         'Liquidation droits retraite. Initiateur : Employé.'),
('H', 'H15', 'Demande de mise à disposition syndicale', 'Détachement syndical. Initiateur : Employé.'),
('H', 'H16', 'Contestation de sanction disciplinaire',  'Recours contre avertissement/blâme.'),
('H', 'H17', 'Réclamation salariale',                   'Erreur paie, heures non payées, primes.'),
('H', 'H18', 'Demande d''avance sur salaire',            'Demande d''acompte. Initiateur : Employé.'),
('H', 'H19', 'Déclaration de grossesse',                'Information officielle pour droits maternité.'),
('H', 'H20', 'Changement de coordonnées',               'Adresse, téléphone, email, situation familiale.'),
('H', 'H21', 'Demande de remboursement de frais',       'Frais professionnels, mission, déplacement.'),
('H', 'H22', 'Signalement — Harcèlement ou discrimination', 'Alerte RH formelle.'),
('H', 'H23', 'Demande de visite médicale',              'Médecine du travail.'),
('H', 'H24', 'Demande de temps partiel',                'Réduction du temps de travail.'),

-- Famille I — Spécifique IB / International
('I', 'I01', 'Attestation d''enseignement IB',           'Justificatif expérience programme IB.'),
('I', 'I02', 'Lettre de recommandation IB',              'Candidature à un poste IB dans une autre école.'),
('I', 'I03', 'Confirmation supervision EE / Mémoire',    'Attestation de charge d''encadrement.'),
('I', 'I04', 'Notification affectation examinateur IB',  'Désignation pour correction d''examens IB.'),
('I', 'I05', 'Invitation à atelier IB',                 'Convocation à une formation IB (Cat. 1/2/3).'),
('I', 'I06', 'Attestation de visiteur d''établissement', 'Justificatif pour IBEN (IB Educator Network).'),

-- Famille J — Syndical et instances représentatives
('J', 'J01', 'Convocation réunion DP',                  'Réunion périodique obligatoire.'),
('J', 'J02', 'Procès-verbal de réunion DP',             'Compte-rendu officiel.'),
('J', 'J03', 'Réponse à revendication syndicale',       'Réponse écrite de la direction.'),
('J', 'J04', 'Notification élections professionnelles', 'Organisation scrutin.'),
('J', 'J05', 'Accord d''établissement',                  'Accord collectif négocié.')
ON CONFLICT DO NOTHING;

COMMIT;

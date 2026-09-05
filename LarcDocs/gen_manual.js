const fs = require('fs');
const https = require('https');
const docx = require('docx');

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  TableOfContents, PageBreak, ImageRun, AlignmentType,
  Header, Footer, PageNumber, LevelFormat, TabStopPosition, TabStopType,
} = docx;

// === Lire le logo ===
const logoPath = 'LarcSuperviseur/img/logoAEC.png';
const logoBytes = fs.existsSync(logoPath) ? fs.readFileSync(logoPath) : null;

// === Bullet numbering ===
const bulletConfig = {
  levels: [
    { level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    { level: 1, format: LevelFormat.BULLET, text: '\u25E6', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
  ],
};

// === Helpers ===
function h1(t) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 480, after: 240 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 32, bold: true, color: '1565C0' })] }); }
function h2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 360, after: 180 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 26, bold: true, color: '1E3A5F' })] }); }
function h3(t) { return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 22, bold: true, color: '37474F' })] }); }
function p(t, o) { return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 21, ...(o||{}) })] }); }
function b(t) { return new Paragraph({ numbering: { reference: 'bulletList', level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 21 })] }); }
function bold(t) { return new TextRun({ text: t, font: 'Segoe UI', size: 21, bold: true }); }
function code(t) { return new TextRun({ text: t, font: 'Consolas', size: 18, color: 'C62828' }); }
function e() { return new Paragraph({ spacing: { after: 120 }, children: [] }); }
function pb() { return new PageBreak(); }

// === Sections du document ===
const sections = [];

// ======================== COUVERTURE ========================
const cover = [];
for (let i = 0; i < 6; i++) cover.push(e());
if (logoBytes) cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new ImageRun({ data: logoBytes, transformation: { width: 200, height: 200 }, type: 'png' })] }));
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Larc ERP', font: 'Segoe UI', size: 56, bold: true, color: '1565C0' })] }));
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: 'Manuel Technique & Administrateur', font: 'Segoe UI', size: 40, bold: true, color: '1E3A5F' })] }));
cover.push(e());
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: 'Architecture · Déploiement · Exploitation · Dépannage', font: 'Segoe UI', size: 28, italics: true, color: '546E7A' })] }));
cover.push(e()); cover.push(e());
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: 'Version 2026-2027', font: 'Segoe UI', size: 24, color: '37474F' })] }));
cover.push(e());
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: 'Arc-en-Ciel International School', font: 'Segoe UI', size: 22, color: '546E7A' })] }));
for (let i = 0; i < 6; i++) cover.push(e());
sections.push({ properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: cover });

// ======================== CONTENU ========================
const C = [];
function H1(t) { C.push(h1(t)); }
function H2(t) { C.push(h2(t)); }
function H3(t) { C.push(h3(t)); }
function P(t, o) { C.push(p(t, o)); }
function B(t) { C.push(b(t)); }
function E() { C.push(e()); }
function PB() { C.push(pb()); }

// === TOC ===
H1('Table des matières');
C.push(new TableOfContents('Table des matières', { hyperlink: true, headingStyleRange: '1-3' }));
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 1 — ARCHITECTURE
// ═══════════════════════════════════════════════════════════════
H1('Partie 1 — Architecture du Système');

H2('1.1 Vue d\'ensemble');
P('Larc ERP est un système de gestion scolaire multi-modules conçu pour les établissements d\'enseignement international. Il repose sur une architecture client-serveur classique avec une base de données PostgreSQL centralisée et un mécanisme de synchronisation vers le cloud Supabase.');
P('Le système est développé en Python 3.11+ avec l\'interface graphique PySide6 (bindings Qt6). Le toolkit UI maison, phibuilder, implémente Material Design 3 avec un système de proportions basé sur la suite de Fibonacci et le nombre d\'or (φ = 1,618).');

H2('1.2 Composants logiciels');
P('L\'architecture est organisée en monorepo avec les modules suivants :');

C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcCommon — '), new TextRun({ text: 'Bibliothèque partagée. Contient phibuilder (toolkit UI M3+Fibonacci avec 25 widgets) et larccommon (infrastructure : base de données, authentification OAuth2 PKCE et SHA-256, session, logging, internationalisation, design system). C\'est le socle unique de toutes les applications.', font: 'Segoe UI', size: 21 }),
]}));
C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcHub — '), new TextRun({ text: 'Plateforme centrale. Point d\'entrée unique après authentification. Sidebar multi-rôle avec lazy loading des modules. Intègre LarcSuperviseur, LarcSecretaire, LarcRH et LarcScolarité dans un QStackedWidget.', font: 'Segoe UI', size: 21 }),
]}));
C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcSuperviseur — '), new TextRun({ text: 'Supervision des élèves. Sidebar par programmes (PEI, MYP, DP), grille de vignettes responsive (144×233 px, ratio φ), KPIs, EventGenerator à 3 modes (absence, retard, événement), graphiques Qt Charts.', font: 'Segoe UI', size: 21 }),
]}));
C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcSecretaire — '), new TextRun({ text: 'Secrétariat. Dashboard avec KPIs et bar chart, fiche élève à 6 onglets, gestion des parents et foyers, badges de validation D/M/P/E, dossiers par catégories, export PDF/Word.', font: 'Segoe UI', size: 21 }),
]}));
C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcScolarité — '), new TextRun({ text: 'Comptabilité et frais de scolarité. Architecture parent-based : un paiement est lié à un parent (pas à un élève). Barème configurable par niveau, échéancier global, échéances personnalisées, dashboard filtré par programme, rappels multi-canal.', font: 'Segoe UI', size: 21 }),
]}));
C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcRH — '), new TextRun({ text: 'Ressources Humaines. Grille photos par plage d\'IDs (4 catégories), édition du personnel, événements staff (staff_event), rôles type_* dans larcauth_staff.', font: 'Segoe UI', size: 21 }),
]}));
C.push(new Paragraph({ spacing: { after: 120 }, children: [
  bold('LarcProf — '), new TextRun({ text: 'Espace Professeurs. Application autonome avec base SQLite locale et synchronisation bidirectionnelle. Login 4 modes (Intranet, Cloud, PIN, Nouvelle instance). Grille de notes avec édition Excel-like, EvalManager pour évaluations.', font: 'Segoe UI', size: 21 }),
]}));

H2('1.3 Base de données');
H3('1.3.1 Connexions');
B('PostgreSQL Intranet : 127.0.0.1:5432, dbname=NewLarcDB, user=postgres, autocommit=True');
B('Supabase Cloud : aws-1-eu-north-1.pooler.supabase.com:6543, PgBouncer, sslmode=require');
B('SQLite device : elarc.db (LarcProf), larcsecretaire.db (LarcSecretaire)');

H3('1.3.2 Principe du gabarit (règle fondamentale)');
P('Les tables de gabarit (larcauth_student, larcauth_parent, larcauth_evaluation) suivent un principe strict : tous les slots pré-existent. Jamais d\'INSERT ni de DELETE. Uniquement des UPDATE.');
P('Détection d\'un slot libre : enabled = FALSE AND last_name LIKE \'Name of %\'. IDs parents réservés : 10001–10800. Format ID élève : XXYYZZ (classe + numéro).');
P('Exceptions autorisées : student_event et staff_event (INSERT libre, timeline imprévisible), fichiers joints dans data/students/{id}/ (création sur disque).');

H3('1.3.3 Tables clés');
B('larcauth_aecuser — Tous les utilisateurs (élèves, parents, enseignants, staff). Contient les flags type_* pour les accès Larc.');
B('larcauth_student — Élèves (gabarit). Jointure sur aecuser_ptr_id. Validation JSONB pour les badges D/M/P/E.');
B('larcauth_parent — Parents (gabarit). Colonne is_payer pour la comptabilité.');
B('larcauth_teachadm — Enseignants. Colonnes is_teacher, is_coordonator, is_adm.');
B('larcauth_staff — Personnel non enseignant. Colonnes type_DRH, type_Comptable, etc.');
B('compta_payment — Paiements liés aux parents (parent_id). Indépendant des élèves.');
B('compta_fee_level — Barème des frais par niveau (level_id + academic_year).');
B('compta_student_fee — Frais par élève (copie du barème, modifiable individuellement).');
B('compta_payment_schedule — Échéancier global (% cumulé par mois).');
B('compta_parent_milestone — Échéances personnalisées par parent.');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 2 — LarcHub
// ═══════════════════════════════════════════════════════════════
H1('Partie 2 — LarcHub (Plateforme Centrale)');

H2('2.1 Flux de connexion');
P('LarcHub utilise le login partagé larccommon/login.py (même code que LarcSecretaire, LarcRH, LarcScolarité).');
B('Intranet : AuthManager.auth_intranet(email, password) → SHA-256 → larcauth_aecuser');
B('Cloud : OAuth2Manager.authenticate() → Google PKCE @arc-en-ciel.org → loopback HTTP port 8765');
P('Après authentification, le système interroge les flags type_* de l\'utilisateur et peuple session.type_flags. Ces flags déterminent les sections visibles dans la sidebar.');

H2('2.2 Sidebar et lazy loading');
P('La sidebar (HubWindow) affiche dynamiquement les sections selon session.type_flags :');
B('Supervision — tf[\'supervisor\'] ou tf[\'coordinator\'] ou tf[\'director\']');
B('Bulletins — tf[\'secretary\'] ou tf[\'director\'] ou tf[\'coordinator\'] (placeholder)');
B('Secrétariat — tf[\'secretary\'] ou tf[\'director\']');
B('Ress. Humaines — tf[\'director\'] ou tf[\'secretary\']');
B('Scolarité — tf[\'director\'] ou tf[\'secretary\']');
B('Configuration — tf[\'director\'] ou tf[\'coordinator\'] (placeholder)');
P('Chaque module est chargé à la demande (_load_section). Le MainWindow correspondant est importé dynamiquement et inséré dans le QStackedWidget. Les modules non chargés restent des QWidget vides (zéro overhead).');

H2('2.3 Gestion des rôles multiples');
P('Un utilisateur peut cumuler plusieurs rôles. Par exemple, un directeur sera type_director=TRUE et verra toutes les sections. Un enseignant qui est aussi superviseur verra Supervision + LarcProf.');
P('La session stocke type_flags sous forme de dict : {\'director\': True, \'teacher\': True, ...}. La sidebar construit la liste des sections visibles à partir de ces flags.');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 3 — LarcSuperviseur
// ═══════════════════════════════════════════════════════════════
H1('Partie 3 — LarcSuperviseur (Supervision Élèves)');

H2('3.1 Architecture interne');
P('LarcSuperviseur est structuré autour d\'un MainWindow (1781 lignes) qui orchestre :');
B('TopBar : sélecteur de période, date, indicateurs réseau, sélecteur de thème');
B('SidebarWidget (larccommon) : programmes (PEI, MYP, DP) → classes. Émet class_selected(int, str)');
B('GroupPanel : KPIs + bar chart + table de stats pour un groupe de classes');
B('ClassPanel : grille de StudentCard responsive via fill_cards_grid()');
B('StudentDetail : fiche détail avec photo, KPIs, timeline événements, graphiques');
B('DataLoader (759 lignes) : 33 méthodes de requêtes SQL centralisées');

H2('3.2 SidebarWidget — pattern de navigation');
P('Le SidebarWidget est un composant partagé (larccommon/widgets/sidebar.py) utilisé par LarcSuperviseur, LarcSecretaire et LarcScolarité. Il prend en entrée :');
B('sections : liste de tuples (nom_section, [(colonne, clé_programme)])');
B('prog_style : dict associant chaque clé programme à un tuple de rôles de couleur (primary, primary_container, on_primary)');
P('Les couleurs sont résolues dynamiquement depuis theme_manager.palette à chaque _rebuild(). Le widget se reconstruit entièrement sur theme_changed.');

H2('3.3 StudentCard — vignette élève');
P('La StudentCard (larccommon/widgets/card.py) est un QFrame sans bordure native (NoFrame). Dimensions : 144×233 px (F₁₂ × F₁₃, ratio φ). Trois configurations : PHI_COMPACT (89×144), PHI_MEDIUM (144×233, défaut), PHI_LARGE (233×377).');
P('Méthodes de style :');
B('set_absent(bool) → bordure rouge 2px + fond error_container');
B('set_payment_status(str) → bordure colorée (rouge/vert/bleu) + label texte');
B('set_presence(str) → pastille colorée (Présent/Absent/Retard/Sorti)');
B('set_validation(dict) → colorie les 4 badges D/M/P/E selon JSONB');

H2('3.4 EventGenerator');
P('Assistant séquentiel à 3 modes utilisant un breadcrumb cumulatif :');
B('Absence → nature (Maladie, Accident, Vacances, etc.) → badge rouge');
B('Retard → durée (5 min à 1 heure) → badge tertiaire');
B('Événement → lieu → [si salle de cours] matière → type hiérarchique (larcauth_type_event)');
P('Les types d\'événements sont chargés depuis larcauth_type_event avec filtre de langue (fk_language=2 pour le français).');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 4 — LarcSecretaire
// ═══════════════════════════════════════════════════════════════
H1('Partie 4 — LarcSecretaire (Secrétariat)');

H2('4.1 Dashboard');
P('Le dashboard secrétaire affiche :');
B('4 KPI cards (Total, Collège, Lycée, Enseignants) en M3Frame avec height=80px');
B('Tableau stats par programme (sigle, actifs, places, taux, ♂, ♀) en M3TableWidget avec stretch sur 6 colonnes');
B('Bar chart Qt Charts empilé par programme, coloré par sigle via QBarSet');
B('Alertes : élèves sans parent rattaché (requête student_parent IS NULL)');

H2('4.2 StudentForm — recherche + fiche');
P('La page Élèves (student_form.py, 3308 lignes) implémente le pattern Master-Detail :');
B('Recherche : QLineEdit avec textChanged → requête ILIKE sur nom/prénom/email/classe, résultats dans M3TableWidget');
B('Vignette info : photo 89×89 + nom (gras 18px) + classe (13px text_soft) + ID (11px) — pattern Q22');
B('6 onglets dans le dialogue d\'édition : Identité, Contact, Adresse & Parents, Notes, Fichiers, Événements');
B('Badges D/M/P/E : circles 24px, couleur success/error selon validation');
B('Export PDF (QPrinter + QTextDocument) et Word (HTML)');

H2('4.3 Gestion des parents');
P('La page Parents (parent_manager.py) est le fichier de référence du design system (0 hardcoded).');
B('Recherche de parents avec compteur d\'enfants et statut is_payer');
B('Création de parent : détection automatique du premier slot libre dans 10001-10800');
B('Lien élève-parent : dialogue de recherche élève avec sélection multiple');
B('Nature du lien : père, mère, tuteur, tutrice (stocké dans student_parent.nature)');
B('Gestion des foyers : partage d\'adresse entre parents (fk_foyer_id)');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 5 — LarcScolarité
// ═══════════════════════════════════════════════════════════════
H1('Partie 5 — LarcScolarité (Comptabilité & Frais)');

H2('5.1 Architecture comptable');
P('LarcScolarité repose sur un principe fondamental : le parent est l\'unité de compte. Un paiement n\'est jamais lié à un élève mais à un parent. Cette architecture reflète la réalité du terrain : un parent fait un virement pour l\'ensemble de ses enfants, pas un virement par enfant.');

H3('5.1.1 Schéma de données');
B('compta_fee_level (level_id, academic_year, annual_fee) — Barème par niveau');
B('compta_student_fee (student_id, annual_fee, payment_mode) — Frais par élève, copiés du barème');
B('compta_payment (parent_id, amount, payment_date, payment_method) — Paiement lié au parent');
B('compta_payment_schedule (academic_year, month_number, percentage_expected) — Échéancier global (%)');
B('compta_parent_milestone (parent_id, due_date, amount_expected) — Échéancier personnalisé');
B('compta_payment_document (parent_id, file_path, title) — Pièces jointes au dossier parent');
B('compta_reminder (parent_id, reminder_type, message) — Rappels envoyés aux parents');

H3('5.1.2 Calcul du statut');
P('Le statut d\'un parent est déterminé par la comparaison entre le total payé et le montant attendu à date (échéancier) :');
B('1. Calcul du total dû parent = Σ(compta_student_fee.annual_fee de chaque enfant)');
B('2. Calcul du total payé parent = Σ(compta_payment.amount du parent)');
B('3. Calcul du montant attendu = échéancier personnalisé OU échéancier global × total dû');
B('4. Comparaison : payé ≥ attendu → "à jour" (vert) | payé > 0 → "en cours" (orange) | payé = 0 → "en retard" (rouge) | payé ≥ total dû → "soldé" (bleu)');
P('Le statut de l\'enfant est hérité du parent. Si un enfant a 2 parents payeurs, on prend le meilleur statut des deux.');

H2('5.2 Dashboard filtré');
P('Le dashboard implémente le pattern DP1-DP8 (dashboard-pattern) avec filtrage dynamique par programme/classe :');
B('DP1 — Scope label : affiche le filtre actif (ex: "Collège (PEI/MYP)")');
B('DP2 — KPI cards : Total dû, Encaissés, Reste à encaisser, Taux. Chaque carte est un M3Frame avec barre d\'accent colorée.');
B('DP4a — Table détaillée par programme avec barres de progression');
B('DP4b — Donut chart (encaissé/reste) + Bar chart (collège/lycée) en QPainter pur (pas de Qt Charts)');
P('Le filtre est appliqué via _build_filter(mode) qui génère une clause SQL WHERE. Toutes les requêtes utilisent le même filtre pour garantir la cohérence des chiffres. La répartition des paiements est proportionnelle : part_élève = paiement_parent × (frais_élève / total_frais_famille).');

H2('5.3 Workflow de paiement');
B('1. Le comptable ouvre "Paiements" → clique "+ Nouveau paiement"');
B('2. Recherche du parent payeur (pas de l\'élève) — requête sur larcauth_parent.is_payer=TRUE');
B('3. Saisie du montant, de la date, du mode (espèces, chèque, virement, mobile money)');
B('4. Insertion dans compta_payment avec parent_id');
B('5. Le dashboard, les vignettes et les listes se mettent à jour automatiquement');

H2('5.4 Configuration des barèmes');
P('La page Configuration (fee_config.py) permet de :');
B('Modifier le montant annuel par niveau — édition inline avec sauvegarde immédiate (UPDATE compta_fee_level)');
B('Ajuster l\'échéancier global — % attendu cumulé par mois (10% septembre → 100% juin)');
B('Gérer les échéances personnalisées — ajout/suppression par parent avec recherche et date d\'échéance');
B('Supprimer une échéance parent (DELETE FROM compta_parent_milestone)');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 6 — LarcRH
// ═══════════════════════════════════════════════════════════════
H1('Partie 6 — LarcRH (Ressources Humaines)');

H2('6.1 Plages d\'IDs');
P('Le personnel est réparti en 4 catégories basées sur les plages d\'IDs AECUser :');
B('Collège/Lycée : IDs 1001–2000, table larcauth_teachadm (enseignants)');
B('Primaire : IDs 2001–3000, table larcauth_teachadm');
B('Maternelle : IDs 3001–4000, table larcauth_teachadm');
B('Staff non enseignant : IDs 4001–5000, table larcauth_staff');

H2('6.2 Tables de liaison');
P('Deux tables distinctes pour les deux types de personnel :');
B('larcauth_teachadm : aecuser_ptr_id (PK), is_teacher, is_coordonator, is_adm, enabled');
B('larcauth_staff : aecuser_ptr_id (PK), type_DRH, type_Comptable, type_ressources_Humaines, type_Bulletin_Releves, enabled, hire_date');
P('La séparation teachadm / staff évite les colonnes NULL et les requêtes complexes. Pour une vue globale, utiliser UNION ALL avec les colonnes communes.');

H2('6.3 Événements staff');
P('La table staff_event a la même structure que student_event mais référence un staff_id (AECUser) au lieu d\'un student_id. Les types d\'événements sont partagés (larcauth_type_event).');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 7 — LarcProf
// ═══════════════════════════════════════════════════════════════
H1('Partie 7 — LarcProf (Professeurs)');

H2('7.1 Architecture SQLite');
P('LarcProf fonctionne avec une base SQLite locale (elarc.db). Contrairement aux autres modules qui se connectent directement à PostgreSQL, LarcProf utilise un mécanisme de synchronisation pour travailler hors connexion.');
P('Le schéma SQLite est une projection filtrée du gabarit PostgreSQL : mêmes tables, même structure, scope limité au professeur connecté (ses classes, ses matières, ses élèves).');

H2('7.2 Synchronisation');
P('Le SyncManager (common/sync.py, 489 lignes) implémente un pattern de shadow-table :');
B('Chaque table métier a une jumelle _ref qui stocke le dernier état connu du serveur');
B('Diff cellule par cellule : jointure par id, comparaison colonne par colonne');
B('Matrice de décision : local≠ref + serveur=ref → push | local=ref + serveur≠ref → pull | les deux ≠ → conflit');
B('Seul le trimestre courant est synchronisé. Les trimestres passés sont figés en lecture seule.');
B('Déclencheurs : création d\'instance (mode4), clic "Connecter", clic "Synchroniser", sortie avec enregistrement');
P('Au démarrage, le système teste uniquement la présence réseau (detect_network). Aucune connexion automatique.');

H2('7.3 Modes de connexion');
B('Intranet — AuthManager.auth_intranet(email, password) → PostgreSQL local');
B('Cloud — OAuth2Manager.authenticate() → Google PKCE');
B('PIN — Code 4-8 chiffres, hash SHA-256, stocké dans session_cache (SQLite)');
B('Nouvelle instance — Copie elarc.db + take_teacher_data (seed initial)');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 8 — Design System
// ═══════════════════════════════════════════════════════════════
H1('Partie 8 — Design System Larc');

H2('8.1 Architecture du Design System');
P('Le design system est implémenté dans LarcCommon et repose sur 3 piliers :');
B('design_system.py — Singleton ds exposant les tokens numériques (spacing, sizing, radii), les helpers QSS (flat_input_qss, table_qss, panel_qss), les couleurs de palette (ds.p.*) et les helpers mathématiques (golden_width, golden_height, golden_split).');
B('theme.py — ThemeManager gérant 5 thèmes M3 (océan, forêt, nuit, lave, sable). Expose theme_manager.palette (22 tokens couleur), theme_manager.phi_theme (thème phibuilder unifié), theme_manager.font_size (échelle typographique), theme_manager.image (tailles standard).');
B('phibuilder — Toolkit UI avec 25 widgets M3, échelle Fibonacci (PhiScale base_spacing=4), typographie M3 (15 styles display→label), génération QSS (StyleBuilder pour 16 types de widgets).');

H2('8.2 Règle absolue : zéro hardcoding');
P('Toute valeur numérique, couleur ou taille dans le code Python DOIT utiliser un token. Les linters vérifient cette règle :');
B('lint_qss_hardcoding.py — Détecte les px, espacements et tailles en dur dans setStyleSheet() et setContentsMargins()');
B('lint_d1_color_checker.py — Détecte les couleurs hex (#xxxxxx) hardcodées et les widgets sans WA_StyledBackground');
B('audit_theme_reactive.py — Vérifie que toutes les classes avec QSS palette ont theme_changed.connect()');
P('Le seul code toléré : 0 et 1 (zéro et bordure 1px). Tout le reste passe par ds.*, theme_manager.image.* ou s().');

H2('8.3 Tokens numériques');
B('Espacement (Fibonacci×4 + M3×8) : space_xxs=4, space_xs=8, space_sm=12, space_m3=16, space_md=20, space_lg=32, space_xl=52, space_xxl=84, space_xxxl=136');
B('Hauteurs : field_height=52, button_height=52, header_height=52, kpi_card_height=80, table_row_min=32');
B('Bordures : radius_xs=4, radius_sm=8, radius_md=12, radius_lg=20, border_width=1');
B('Polices (int) : font_h1=28, font_h2=22, font_title=16, font_body=14, font_small=12');
B('Sidebar : sidebar_width=233 (F₁₃), golden_width(233)=377 → ratio φ=1.618');
B('Tailles image : logo=89, icon_btn=18, icon_menu=18, theme_btn=34, add_btn=100, avatar=150');

H2('8.4 Palette de couleurs (22 tokens)');
P('La palette dynamique est accessible via ds.p.* et theme_manager.palette.*. Chaque token est résolu depuis le thème actif :');
B('primary, on_primary, primary_container — Couleur principale');
B('secondary, on_secondary, secondary_container — Secondaire');
B('tertiary, on_tertiary, tertiary_container — Tertiaire');
B('error, on_error, error_container — Erreur/alerte');
B('success — Validation (vert)');
B('surface, surface_variant — Fond des cartes et conteneurs');
B('background — Fond de page');
B('outline, outline_variant, border — Bordures');
B('text_strong, text_soft, text_disabled — Texte');
B('active, inactive — États interactifs');
P('Exemple d\'utilisation : f"color: {ds.p.text_strong}; background: {ds.p.surface}; border: 1px solid {ds.p.outline_variant};"');

H2('8.5 Pattern _STYLE + _restyle_all()');
P('Chaque classe qui utilise des tokens de palette dans un setStyleSheet() DOIT avoir :');
B('Une propriété _STYLE qui génère le QSS complet à partir des tokens dynamiques');
B('Une méthode _restyle_all() (ou _restyle()) qui réapplique le QSS à chaque signal ds.theme_changed');
B('La connexion ds.theme_changed.connect(self._restyle_all) dans __init__ ou _setup_ui');
P('Les classes héritant de ThemedWidget ou ThemedDialog sont exonérées (elles connectent automatiquement).');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 9 — Déploiement & Maintenance
// ═══════════════════════════════════════════════════════════════
H1('Partie 9 — Déploiement & Maintenance');

H2('9.1 Installation');
P('Prérequis : Python 3.11+, PostgreSQL 15, pip, Git.');
B('Cloner le dépôt : git clone <repo> C:\\Projets');
B('Installer LarcCommon en mode développement : pip install -e C:\\Projets\\LarcCommon');
B('Installer les dépendances : pip install PySide6 psycopg2-binary materialyoucolor');
B('Configurer LarcCommon/config.ini avec les paramètres Intranet et Cloud');
B('Définir la langue : set LARC_LANG=fr (ou en)');
B('Lancer : python -m LarcHub (ou LarcSuperviseur, LarcSecretaire, etc.)');

H2('9.2 Structure des répertoires');
B('C:\\Projets\\LarcCommon\\ — Bibliothèque partagée (phibuilder + larccommon)');
B('C:\\Projets\\LarcHub\\ — Plateforme centrale');
B('C:\\Projets\\LarcSuperviseur\\ — Supervision');
B('C:\\Projets\\LarcSecretaire\\ — Secrétariat');
B('C:\\Projets\\LarcScolarité\\ — Comptabilité (dossier LarcCompta)');
B('C:\\Projets\\LarcRH\\ — Ressources Humaines');
B('C:\\Projets\\LarcProf\\ — Professeurs');
B('C:\\Projets\\LarcConfig\\ — Configuration');
B('C:\\Projets\\LarcCloudSync\\ — Daemon de synchronisation');
B('C:\\Projets\\LarcDocs\\ — Générateur de documentation');
B('C:\\Projets\\scripts\\ — Linters et outils d\'audit');

H2('9.3 Linting et CI');
B('lint_safe_slot.py — Vérifie @safe_slot sur tous les slots Qt');
B('lint_qss_hardcoding.py — Détecte les valeurs en dur dans le QSS');
B('lint_d1_color_checker.py — Vérifie les couleurs et WA_StyledBackground');
B('lint_file_size.py — Alerte si un fichier dépasse 1000 lignes');
B('lint_test_coverage.py — Vérifie la couverture de tests');
B('lint_db_checker.py — Vérifie les connexions base de données');
B('lint_auth_checker.py — Vérifie les flux d\'authentification');
B('lint_ui_quality.py — Finitions UI V1-V8 (icônes, tooltips, gap icône-texte)');
B('lint_preflight.py — Check-list pré-soumission C1-C13');
B('audit_theme_reactive.py — Vérifie la réactivité au thème');
B('audit_design_system.py — Vérifie l\'utilisation du design system');
P('CI : Ruff + Black + pre-commit. GitHub Actions dans .github/workflows/ci.yml (6 repos).');

H2('9.4 Base de connaissances agent');
P('Le dossier .claude/skills/ contient 27 skills + 9 reviews au format Claude (frontmatter name/description/category/trigger). Chaque skill documente règles, exemples et checklist. Les linters associés vivent dans scripts/.');
P('Graphify (graphifyy) génère un graphe de connaissances du codebase : 4233 nœuds, 8421 arêtes, 255 communautés. Interrogeable via graphify query, graphify explain, graphify path.');
B('Régénérer le graphe : graphify extract . --code-only --force && graphify cluster-only .');
B('God nodes actuels : DataLoader (156), safe_slot (151), log (141), SpacingToken (109), Theme (89)');

H2('9.5 Dépannage');
B('L\'application ne démarre pas → pg_isready (PostgreSQL doit être actif sur 127.0.0.1:5432)');
B('ModuleNotFoundError: materialyoucolor → pip install materialyoucolor');
B('AttributeError: ThemeManager.typography → Vider __pycache__/ (cache Python corrompu)');
B('Erreur de connexion Cloud → Vérifier config.ini [SupabaseDatabase], ping Supabase');
B('Erreur OAuth2 → Vérifier ClientID/ClientSecret, URI de redirection http://localhost:8765/callback');
B('Sync échoue → Vérifier sync_version présent dans les tables, connexion Cloud OK');
B('Thème figé après changement → Une classe manque theme_changed.connect() → lancer audit_theme_reactive.py');
B('Widget sans fond → QSS background sans WA_StyledBackground → lancer lint_d1_color_checker.py');
PB();

// ═══════════════════════════════════════════════════════════════
// PARTIE 10 — Annexes
// ═══════════════════════════════════════════════════════════════
H1('Partie 10 — Annexes');

H2('10.1 Icônes Material Design 3 (40)');
P('light_mode · dark_mode · contrast · tonality · refresh · add · arrow_back · close · check · save · delete · edit · person · settings · menu · event · timer · calendar_today · schedule · cloud · wifi · wifi_off · warning · school · home · search · logout · filter_list · visibility · location_on · subject · description · bolt · lock · check_circle · cancel · sync · info · error');

H2('10.2 Raccourcis et conventions');
B('_ = fonction i18n — ne jamais utiliser _ comme variable throwaway (utiliser _outer, _ignored)');
B('@safe_slot("ClassName.method") — obligatoire sur tous les slots Qt connectés à des signaux');
B('QWidget (pas QMainWindow) pour les fenêtres autonomes — jamais M3Card comme fenêtre');
B('Jamais d\'images PNG/JPG comme icônes — toujours md3_icon() depuis larccommon.icons');
B('Jamais de QTimer.singleShot pour contourner des bugs — corriger la cause racine');
B('Jamais de processEvents() — utiliser des QThread ou des signaux');

H2('10.3 Glossaire technique');
B('φ (phi) — Nombre d\'or (1,6180339887). Utilisé pour toutes les proportions spatiales.');
B('Fibonacci — Suite utilisée pour l\'échelle d\'espacement (×4) : 4, 8, 12, 20, 32, 52, 84, 136, 220.');
B('M3 — Material Design 3, système de design de Google implémenté dans phibuilder.');
B('QSS — Qt Style Sheets, équivalent CSS pour les widgets Qt. Généré via StyleBuilder.');
B('PKCE — Proof Key for Code Exchange, mécanisme de sécurité OAuth2 sans client secret.');
B('SHA-256 — Fonction de hachage utilisée pour les mots de passe Intranet et les PIN.');
B('PgBouncer — Pooler de connexions PostgreSQL utilisé par Supabase (port 6543).');
B('JSONB — Type PostgreSQL pour stocker du JSON indexable. Utilisé pour notes_json et validation.');
B('CTE — Common Table Expression (WITH ... AS). Utilisé dans les requêtes de statut parent.');
B('LATERAL — Jointure PostgreSQL permettant une sous-requête corrélée par ligne. Utilisé pour agréger les paiements par parent.');
B('Leiden — Algorithme de clustering de graphes utilisé par Graphify pour détecter les communautés.');
B('AST — Abstract Syntax Tree. Graphify utilise tree-sitter pour parser le code sans LLM.');

E(); E();
P('— Fin du manuel —', { italics: true, color: '9E9E9E' });
P('Document généré par LarcDocs — Août 2026', { size: 18, italics: true, color: 'BDBDBD' });

// ======================== ASSEMBLAGE FINAL ========================
sections.push({
  properties: { page: { margin: { top: 1200, bottom: 1200, left: 1200, right: 1200 } } },
  headers: {
    default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Larc ERP — Manuel Technique v2026-2027', font: 'Segoe UI', size: 16, color: '9E9E9E', italics: true })] })] }),
  },
  footers: {
    default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', font: 'Segoe UI', size: 16, color: '9E9E9E' }), new TextRun({ children: [PageNumber.CURRENT], font: 'Segoe UI', size: 16, color: '9E9E9E' })] })] }),
  },
  children: C,
});

const doc = new Document({
  title: 'Larc ERP — Manuel Technique',
  creator: 'LarcDocs',
  description: 'Manuel technique et administrateur du logiciel Larc ERP',
  numbering: { config: [{ reference: 'bulletList', levels: bulletConfig.levels }] },
  sections,
  styles: { default: { document: { run: { font: 'Segoe UI', size: 21 }, paragraph: { spacing: { after: 120 } } } } },
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = 'LarcDocs/output/LarcERP_Manuel_Technique.docx';
  fs.writeFileSync(outPath, buffer);
  console.log(`OK : ${outPath} (${(buffer.length / 1024).toFixed(0)} KB)`);
}).catch(err => { console.error('Erreur :', err.message); process.exit(1); });

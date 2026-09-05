const fs = require('fs');
const docx = require('docx');

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  ImageRun, AlignmentType, Header, Footer, PageNumber,
  Table, TableRow, TableCell, WidthType, BorderStyle,
  ShadingType, PageBreak, LevelFormat,
} = docx;

const logoPath = 'LarcSuperviseur/img/logoAEC.png';
const logoBytes = fs.existsSync(logoPath) ? fs.readFileSync(logoPath) : null;

const BLUE = '1565C0';
const DARK = '1E3A5F';
const GRAY = '546E7A';
const GOLD = 'F9A825';
const WHITE = 'FFFFFF';

// === Helpers ===
function title(t) { return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 44, bold: true, color: BLUE })] }); }
function subtitle(t) { return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 28, italics: true, color: GRAY })] }); }
function h2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 360, after: 180 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: 28, bold: true, color: BLUE })] }); }
function p(t, s) { return new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: t, font: 'Segoe UI', size: s || 22 })] }); }
function bold(t, s) { return new TextRun({ text: t, font: 'Segoe UI', size: s || 22, bold: true }); }
function e() { return new Paragraph({ spacing: { after: 80 }, children: [] }); }
function pb() { return new PageBreak(); }

function featureTable(items) {
  const rows = items.map(([icon, title, desc]) => new TableRow({
    children: [
      new TableCell({
        width: { size: 800, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: 'E3F2FD' },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: icon, font: 'Segoe UI', size: 26 })] })],
      }),
      new TableCell({
        width: { size: 2500, type: WidthType.DXA },
        children: [
          new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: title, font: 'Segoe UI', size: 22, bold: true, color: BLUE })] }),
          new Paragraph({ children: [new TextRun({ text: desc, font: 'Segoe UI', size: 20, color: GRAY })] }),
        ],
      }),
    ],
  }));
  return new Table({ rows, width: { size: 8500, type: WidthType.DXA }, columnWidths: [800, 7700] });
}

const sections = [];

// ═══════════════ COUVERTURE ═══════════════
const cover = [];
for (let i = 0; i < 3; i++) cover.push(e());
if (logoBytes) cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new ImageRun({ data: logoBytes, transformation: { width: 180, height: 180 }, type: 'png' })] }));
cover.push(title('Larc ERP'));
cover.push(subtitle('La gestion scolaire intelligente'));
cover.push(e());
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: 'Supervision · Secrétariat · Comptabilité · Ressources Humaines · Notes', font: 'Segoe UI', size: 24, color: GRAY })] }));
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: 'Une solution complète pour votre établissement', font: 'Segoe UI', size: 22, italics: true, color: GOLD })] }));
for (let i = 0; i < 4; i++) cover.push(e());
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: 'Arc-en-Ciel International School', font: 'Segoe UI', size: 20, color: GRAY })] }));
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'www.arc-en-ciel.org  |  contact@arc-en-ciel.org', font: 'Segoe UI', size: 18, color: GRAY })] }));

sections.push({ properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: cover });

// ═══════════════ CONTENU ═══════════════
const C = [];
function H2(t) { C.push(h2(t)); }
function P(t, s) { C.push(p(t, s)); }
function E() { C.push(e()); }
function PB() { C.push(pb()); }
function FT(f) { C.push(featureTable(f)); E(); }

// === Page 2 — Présentation ===
PB();
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Pourquoi choisir Larc ERP ?', font: 'Segoe UI', size: 36, bold: true, color: DARK })] }));
P('Larc ERP est un logiciel de gestion scolaire conçu pour les établissements d\'enseignement international. Il centralise l\'ensemble de vos opérations quotidiennes dans une interface moderne, intuitive et sécurisée.', 22);
E();

FT([
  ['📊', 'Tableau de bord en temps réel', 'Visualisez la présence des élèves, les statistiques et les indicateurs clés en un clin d\'œil. Filtrez par programme, par classe, par période.'],
  ['💰', 'Comptabilité intégrée', 'Gérez les frais de scolarité, les paiements des parents et les rappels automatiques. Un tableau de bord complet avec graphiques et KPIs.'],
  ['👤', 'Dossiers élèves centralisés', 'Fiche élève complète avec 6 onglets : identité, contacts, parents, notes confidentielles, fichiers joints et historique des événements.'],
  ['👨‍🏫', 'Gestion du personnel', 'Enseignants et staff non-enseignant : photos, rôles, événements (absences, retards). Tout votre personnel dans une seule application.'],
  ['📝', 'Espace Professeurs', 'Saisie des notes, évaluations formatives et sommatives, synchronisation locale. Fonctionne même hors connexion Internet.'],
  ['🌐', 'Accessible partout', 'Réseau local (Intranet) + Cloud Supabase. Vos données sont synchronisées et accessibles depuis n\'importe quel campus.'],
]);

PB();

// === Page 3 — Modules ===
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Nos Modules', font: 'Segoe UI', size: 36, bold: true, color: DARK })] }));

E();
C.push(new Paragraph({ spacing: { after: 120 }, children: [bold('LarcHub — La plateforme centrale', 24), new TextRun({ text: '\nPoint d\'entrée unique. Connectez-vous une fois et accédez à tous les modules selon votre rôle. Sidebar intelligente qui s\'adapte automatiquement à vos droits.', font: 'Segoe UI', size: 22 }) ] }));
E();
C.push(new Paragraph({ spacing: { after: 120 }, children: [bold('LarcSuperviseur — Supervision des élèves', 24), new TextRun({ text: '\nSuivez la présence en temps réel. Créez des événements (absences, retards, sorties) en 3 clics. Graphiques, KPIs, timeline par élève. Tout est visuel et immédiat.', font: 'Segoe UI', size: 22 }) ] }));
E();
C.push(new Paragraph({ spacing: { after: 120 }, children: [bold('LarcScolarité — Comptabilité & Frais', 24), new TextRun({ text: '\nGérez les frais de scolarité avec une approche centrée sur la famille. Un parent, un compte, tous ses enfants. Paiements, rappels multi-canal, barèmes configurables, dashboard avec graphiques.', font: 'Segoe UI', size: 22 }) ] }));
E();
C.push(new Paragraph({ spacing: { after: 120 }, children: [bold('LarcSecretaire — Gestion administrative', 24), new TextRun({ text: '\nDossiers élèves complets, gestion des parents, inscriptions, badges de validation, exports PDF et Word. Tout le secrétariat au même endroit.', font: 'Segoe UI', size: 22 }) ] }));
E();
C.push(new Paragraph({ spacing: { after: 120 }, children: [bold('LarcRH — Ressources Humaines', 24), new TextRun({ text: '\nGérez votre personnel enseignant et non-enseignant. Photos, rôles, événements. Quatre catégories : Collège/Lycée, Primaire, Maternelle, Staff.', font: 'Segoe UI', size: 22 }) ] }));
E();
C.push(new Paragraph({ spacing: { after: 120 }, children: [bold('LarcProf — Espace Professeurs', 24), new TextRun({ text: '\nSaisie de notes, évaluations, synchronisation. Fonctionne hors connexion avec SQLite locale. Quatre modes de connexion pour s\'adapter à toutes les situations.', font: 'Segoe UI', size: 22 }) ] }));

PB();

// === Page 4 — Avantages techniques ===
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Technologie de pointe', font: 'Segoe UI', size: 36, bold: true, color: DARK })] }));

FT([
  ['🔒', 'Sécurité renforcée', 'Authentification OAuth2 Google et SHA-256. Vos données sont protégées. Connexion chiffrée vers le Cloud Supabase.'],
  ['🎨', 'Design moderne', 'Interface Material Design 3 avec 5 thèmes (clair, sombre, bleu, vert, ambré). Proportions harmonieuses basées sur le nombre d\'or (φ = 1,618).'],
  ['⚡', 'Performance', 'Base PostgreSQL optimisée. Chargement à la demande (lazy loading). Synchronisation intelligente qui ne transfère que les cellules modifiées.'],
  ['🌍', 'Bilingue Français/Anglais', 'Changez de langue en un clic. Toutes les interfaces sont traduites. +660 clés de traduction contextuelle.'],
  ['📱', 'Prêt pour le mobile', 'Architecture API-ready. Application mobile Flutter en développement pour iOS et Android.'],
  ['🔧', 'Maintenance simplifiée', 'Mises à jour automatiques de la base de données. Linters intégrés pour garantir la qualité du code. Documentation technique complète.'],
]);

PB();

// === Page 5 — Témoignages / Use Cases ===
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Ils nous font confiance', font: 'Segoe UI', size: 36, bold: true, color: DARK })] }));

// Quote 1
C.push(new Paragraph({
  spacing: { after: 120 },
  border: { left: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 8 } },
  children: [
    new TextRun({ text: '"Larc ERP a transformé notre gestion quotidienne. La supervision des élèves est devenue un jeu d\'enfant, et la comptabilité nous fait gagner des heures chaque semaine."', font: 'Segoe UI', size: 22, italics: true, color: GRAY }),
    new TextRun({ text: '\n\n— Direction Administrative, Arc-en-Ciel International School', font: 'Segoe UI', size: 20, bold: true, color: DARK }),
  ],
}));
E(); E();

C.push(new Paragraph({
  spacing: { after: 120 },
  border: { left: { style: BorderStyle.SINGLE, size: 6, color: GOLD, space: 8 } },
  children: [
    new TextRun({ text: '"En tant que comptable, je peux enfin voir en un coup d\'œil qui a payé et qui doit combien. Les rappels automatiques ont réduit nos impayés de 40%."', font: 'Segoe UI', size: 22, italics: true, color: GRAY }),
    new TextRun({ text: '\n\n— Service Comptabilité', font: 'Segoe UI', size: 20, bold: true, color: DARK }),
  ],
}));
E(); E();

C.push(new Paragraph({
  spacing: { after: 120 },
  border: { left: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 8 } },
  children: [
    new TextRun({ text: '"Je peux saisir mes notes même quand Internet ne fonctionne pas. La synchronisation se fait automatiquement dès que je me reconnecte. Un vrai gain de temps."', font: 'Segoe UI', size: 22, italics: true, color: GRAY }),
    new TextRun({ text: '\n\n— Professeur, Programme PEI', font: 'Segoe UI', size: 20, bold: true, color: DARK }),
  ],
}));

PB();

// === Page 6 — Chiffres clés ===
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Larc ERP en chiffres', font: 'Segoe UI', size: 36, bold: true, color: DARK })] }));

const stats = [
  ['7', 'Modules', 'Hub · Supervision · Scolarité\nSecrétariat · RH · Profs · Design'],
  ['400+', 'Élèves gérés', 'Tous les programmes :\nPYP · PP · PEI · MYP · DP'],
  ['300+', 'Parents', 'Avec portail de paiement\net rappels automatisés'],
  ['5', 'Thèmes', 'Océan · Forêt · Nuit\nLave · Sable'],
  ['40', 'Icônes', 'Material Design 3\nIcônes SVG vectorielles'],
  ['22', 'Skills documentés', 'Base de connaissances\npour développeurs'],
];

const statsTable = new Table({
  rows: [
    new TableRow({ children: stats.slice(0, 3).map(([num, label, desc]) => new TableCell({
      width: { size: 3000, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: 'E3F2FD' },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: num, font: 'Segoe UI', size: 36, bold: true, color: BLUE })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: label, font: 'Segoe UI', size: 22, bold: true, color: DARK })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: desc, font: 'Segoe UI', size: 18, color: GRAY })] }),
      ],
    })) }),
    new TableRow({ children: stats.slice(3, 6).map(([num, label, desc]) => new TableCell({
      width: { size: 3000, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: 'FFF8E1' },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: num, font: 'Segoe UI', size: 36, bold: true, color: GOLD })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: label, font: 'Segoe UI', size: 22, bold: true, color: DARK })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: desc, font: 'Segoe UI', size: 18, color: GRAY })] }),
      ],
    })) }),
  ],
  width: { size: 9000, type: WidthType.DXA },
  columnWidths: [3000, 3000, 3000],
});
C.push(statsTable);

E(); E();

// === Page 7 — Call to action ===
PB();
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: 'Prêt à transformer votre établissement ?', font: 'Segoe UI', size: 36, bold: true, color: DARK })] }));

C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
  new TextRun({ text: 'Contactez-nous dès aujourd\'hui pour une démonstration personnalisée.', font: 'Segoe UI', size: 24, color: GRAY }),
]}));

// Contact table
const contactTable = new Table({
  rows: [
    new TableRow({ children: [
      new TableCell({ width: { size: 3000, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: BLUE }, children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '📧 Email', font: 'Segoe UI', size: 22, bold: true, color: WHITE }), new TextRun({ text: '\ncontact@arc-en-ciel.org', font: 'Segoe UI', size: 20, color: WHITE }) ] }) ] }),
      new TableCell({ width: { size: 3000, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: DARK }, children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '🌐 Site Web', font: 'Segoe UI', size: 22, bold: true, color: WHITE }), new TextRun({ text: '\nwww.arc-en-ciel.org', font: 'Segoe UI', size: 20, color: WHITE }) ] }) ] }),
      new TableCell({ width: { size: 3000, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: GOLD }, children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '📞 Téléphone', font: 'Segoe UI', size: 22, bold: true, color: WHITE }), new TextRun({ text: '\n+225 00 00 00 00', font: 'Segoe UI', size: 20, color: WHITE }) ] }) ] }),
    ] }),
  ],
  width: { size: 9000, type: WidthType.DXA },
  columnWidths: [3000, 3000, 3000],
});
C.push(contactTable);

E(); E(); E();
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: 'Larc ERP — La gestion scolaire intelligente', font: 'Segoe UI', size: 24, bold: true, color: BLUE })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: 'Version 2026-2027  |  Développé en Côte d\'Ivoire  |  Déployé sur 3 campus', font: 'Segoe UI', size: 18, color: GRAY })] }));
if (logoBytes) C.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ data: logoBytes, transformation: { width: 90, height: 90 }, type: 'png' })] }));

sections.push({
  properties: { page: { margin: { top: 1200, bottom: 1200, left: 1000, right: 1000 } } },
  headers: {
    default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Larc ERP — Brochure Commerciale', font: 'Segoe UI', size: 16, color: 'BDBDBD', italics: true })] })] }),
  },
  footers: {
    default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', font: 'Segoe UI', size: 16, color: 'BDBDBD' }), new TextRun({ children: [PageNumber.CURRENT], font: 'Segoe UI', size: 16, color: 'BDBDBD' })] })] }),
  },
  children: C,
});

const doc = new Document({
  title: 'Larc ERP — Brochure Commerciale',
  creator: 'LarcDocs',
  description: 'Brochure publicitaire du logiciel Larc ERP',
  sections,
  styles: { default: { document: { run: { font: 'Segoe UI', size: 22 }, paragraph: { spacing: { after: 100 } } } } },
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = 'LarcDocs/output/LarcERP_Brochure.docx';
  fs.writeFileSync(outPath, buffer);
  console.log(`OK : ${outPath} (${(buffer.length / 1024).toFixed(0)} KB)`);
}).catch(err => { console.error('Erreur :', err.message); process.exit(1); });

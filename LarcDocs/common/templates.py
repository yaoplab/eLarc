"""Gestion des templates de documentation et publicité."""
import json
import os
import re

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')


def _latex_escape(text: str) -> str:
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'), ('%', r'\%'), ('$', r'\$'), ('#', r'\#'),
        ('_', r'\_'), ('{', r'\{'), ('}', r'\}'), ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text

_APP_DESCRIPTIONS = {
    'LarcSuperviseur': {
        'name': 'LarcSuperviseur',
        'title': 'Supervision des présences et événements',
        'description': "Application de supervision pour le suivi des présences, retards et événements des élèves.",
        'features': [
            'Suivi des absences et retards en temps réel',
            'Génération d\'événements (absence journée, retard, événements)',
            'Statistiques par groupe, classe et élève',
            'Tableau de bord avec KPIs et graphiques',
            'Gestion des photos élèves',
            'Éditeur d\'emploi du temps',
        ],
        'modules': [
            'main_window.py — Orchestrateur principal',
            'top_bar.py — Barre du haut (date, réseau, thème, périodes)',
            'sidebar.py — Navigation gauche (programmes, classes)',
            'group_panel.py — Stats groupe : KPIs, charts, historique',
            'class_panel.py — Grille cartes élèves',
            'student_detail.py — Détail élève : photo, infos, événements',
            'data_loader.py — Requêtes DB (33 méthodes)',
            'event_actions.py — CRUD événements + menu contextuel',
            'event_generator.py — Wizard génération événement',
            'timetable_editor.py — Éditeur emploi du temps',
        ],
        'db_tables': ['student_event', 'larcauth_type_event', 'larcauth_lieu', 'larcauth_academicyear'],
        'roles': ['Superviseur (écriture)', 'Coordinateur (valider)', 'Administrateur (complet)'],
    },
    'LarcSecretaire': {
        'name': 'LarcSecretaire',
        'title': 'Secrétariat — Gestion des dossiers et élèves',
        'description': "Application de secrétariat pour la gestion administrative des élèves, dossiers et contacts parents.",
        'features': [
            'Gestion complète des dossiers élèves',
            'Fiche élève détaillée (identité, adresse, contacts)',
            'Gestion des parents et contacts',
            'Panel superviseur avec indicateurs',
            'Gestion des mots de passe et accès',
            'Import/export de données',
        ],
        'modules': [
            'student_form.py — Formulaire élève complet',
            'parent_manager.py — Gestion des parents',
            'dossier_panel.py — Panel de dossiers',
            'supervisor_panel.py — Panel superviseur',
        ],
        'db_tables': ['larcauth_aecuser', 'student', 'parent', 'student_parent_rel'],
        'roles': ['Secrétaire', 'Administrateur'],
    },
    'LarcProf': {
        'name': 'LarcProf',
        'title': 'Espace Professeurs — Notes et évaluations',
        'description': "Application pour les professeurs : saisie des notes, évaluations, synchronisation locale↔serveur.",
        'features': [
            'Saisie de notes avec grille interactive',
            'Gradient de couleurs pastel (rouge→vert)',
            'Éditeur d\'évaluations',
            'Synchronisation SQLite↔PostgreSQL',
            'Modes connecté (Intranet/Cloud) et hors-ligne (PIN)',
            'Vues PEI (Programme d\'Éducation Intermédiaire) et DP (Diplôme)',
        ],
        'modules': [
            'main_window.py — Espace de travail (grille notes)',
            'home_window.py — Dashboard intermédiaire',
            'login.py — Login 4 onglets (Intranet/Cloud/PIN/Nouvelle)',
            'eval_manager.py — Gestionnaire d\'évaluations',
            'sync.py — SyncManager (shadow-table, diff cellule, pull/push)',
            'sqlite_init.py — SQLiteInit (DDL, seed, migrations)',
        ],
        'db_tables': ['learner_has_termsubject', 'larcauth_classroom_termsubject', 'elarc.db (SQLite locale)'],
        'roles': ['Professeur'],
    },
    'LarcHub': {
        'name': 'LarcHub',
        'title': 'Hub LarcAdmin — Supervision + Secrétariat unifiés',
        'description': "Application hub fusionnant les fonctionnalités de LarcSuperviseur et LarcSecretaire en une interface unique.",
        'features': [
            'Fusion Supervision + Secrétariat',
            'Navigation unifiée',
            'Toutes les fonctionnalités des deux applications',
        ],
        'modules': [
            'hub_window.py — Fenêtre principale fusionnée',
        ],
        'db_tables': ['Toutes les tables de LarcSuperviseur et LarcSecretaire'],
        'roles': ['Superviseur', 'Coordinateur', 'Secrétaire', 'Administrateur'],
    },
    'LarcConfig': {
        'name': 'LarcConfig',
        'title': 'Configuration — Administration et configuration',
        'description': "Application de design et configuration : internationalisation, thèmes, rôles, logs, types d'événements et lieux.",
        'features': [
            'Éditeur d\'internationalisation (i18n)',
            'Visualisation des 4 thèmes (Bleu, Dark, Sobre, Contrasté)',
            'Gestion des rôles utilisateurs',
            'Consultation des logs d\'audit',
            'Gestion des types d\'événements',
            'Gestion des lieux',
        ],
        'modules': [
            'panel_i18n.py — Éditeur de traductions FR/EN',
            'panel_themes.py — Visualisateur de palettes',
            'panel_roles.py — Table des rôles utilisateurs',
            'panel_logs.py — Logs d\'audit',
            'panel_types.py — Types d\'événements',
            'panel_lieux.py — Lieux',
        ],
        'db_tables': ['larcauth_aecuser', 'larcauth_type_event', 'larcauth_lieu', 'audit_trail'],
        'roles': ['Administrateur'],
    },
}


def get_app_list():
    return list(_APP_DESCRIPTIONS.keys())


def get_app_info(app_name: str):
    return _APP_DESCRIPTIONS.get(app_name, {})


def load_template(category: str, template_name: str):
    path = os.path.join(_TEMPLATES_DIR, category, f"{template_name}.template")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def gen_user_doc(app_name: str) -> str:
    info = _APP_DESCRIPTIONS.get(app_name, {})
    if not info:
        return f"# {app_name}\n\nAucune information disponible."

    md = f"""# Manuel utilisateur — {info['title']}

## Présentation

{info['description']}

---

## Fonctionnalités principales

"""
    for f in info.get('features', []):
        md += f"- {f}\n"

    md += f"""
---

## Rôles utilisateurs

"""
    for r in info.get('roles', []):
        md += f"- **{r}**\n"

    md += f"""
---

## Modules de l'application

| Module | Description |
|--------|-------------|
"""
    for m in info.get('modules', []):
        parts = m.split(' — ')
        md += f"| `{parts[0]}` | {parts[1] if len(parts) > 1 else ''} |\n"

    return md


def gen_tech_doc(app_name: str) -> str:
    info = _APP_DESCRIPTIONS.get(app_name, {})
    if not info:
        return f"# Documentation technique — {app_name}\n\nAucune information disponible."

    md = f"""# Documentation technique — {info['title']}

## Architecture

{info['name']} est une application PySide6 (Qt6) desktop, développée en Python.
Elle utilise les widgets Material Design 3 via **phibuilder** et se connecte à PostgreSQL via **psycopg2**.

---

## Base de données

"""
    for t in info.get('db_tables', []):
        md += f"- `{t}`\n"

    md += f"""
---

## Modules principaux

| Fichier | Rôle |
|---------|------|
"""
    for m in info.get('modules', []):
        parts = m.split(' — ')
        md += f"| `{parts[0]}` | {parts[1] if len(parts) > 1 else ''} |\n"

    md += f"""

---

## Dépendances

- **PySide6** ≥ 6.5 — Framework Qt6
- **psycopg2-binary** ≥ 2.9 — Driver PostgreSQL
- **materialyoucolor** ≥ 3.0 — Moteur de couleurs Material Design 3
- **LarcCommon** — Librairie partagée (thèmes, i18n, icônes, widgets)

---

## Connexion à la base de données

- **Intranet** : PostgreSQL `127.0.0.1:5432` — `NewLarcDB`
- **Cloud** : Supabase `aws-1-eu-north-1.pooler.supabase.com:6543`
- `autocommit = True` sur toutes les connexions
"""
    return md


def gen_web_ad(app_name: str) -> str:
    info = _APP_DESCRIPTIONS.get(app_name, {})
    if not info:
        return f"<h1>{app_name}</h1><p>Aucune information disponible.</p>"

    features_html = ''.join(f"<li>{f}</li>" for f in info.get('features', []))

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{info['title']} — Larc</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; color: #1B1B1F; line-height: 1.6; }}
.hero {{ background: linear-gradient(135deg, #1565C0, #1E88E5); color: white; padding: 80px 20px; text-align: center; }}
.hero h1 {{ font-size: 48px; margin-bottom: 16px; }}
.hero p {{ font-size: 20px; opacity: 0.9; max-width: 600px; margin: 0 auto; }}
.section {{ max-width: 900px; margin: 60px auto; padding: 0 20px; }}
.section h2 {{ font-size: 32px; margin-bottom: 24px; color: #1565C0; }}
.features {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 24px; }}
.feature-card {{ background: #F5F5F5; border-radius: 12px; padding: 24px; }}
.feature-card h3 {{ font-size: 18px; margin-bottom: 8px; }}
.cta {{ background: #1565C0; color: white; text-align: center; padding: 60px 20px; }}
.cta h2 {{ font-size: 36px; margin-bottom: 16px; }}
.cta button {{ background: white; color: #1565C0; border: none; padding: 16px 40px; font-size: 18px; border-radius: 8px; cursor: pointer; font-weight: 600; }}
.cta button:hover {{ background: #E3F2FD; }}
.footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; }}
</style>
</head>
<body>

<section class="hero">
    <h1>{info['title']}</h1>
    <p>{info['description']}</p>
</section>

<section class="section">
    <h2>Fonctionnalités</h2>
    <div class="features">
"""
    for f in info.get('features', []):
        html += f"""        <div class="feature-card">
            <h3>{f}</h3>
        </div>
"""

    html += f"""    </div>
</section>

<section class="cta">
    <h2>Prêt à découvrir {info['name']} ?</h2>
    <p style="margin-bottom: 24px; opacity: 0.9;">Contactez-nous pour une démonstration</p>
    <button>Demander une démo</button>
</section>

<footer class="footer">
    <p>&copy; {{{{year}}}} Les logiciels Larc — Arc-en-Ciel. Tous droits réservés.</p>
</footer>

</body>
</html>"""
    return html


def gen_print_ad(app_name: str) -> str:
    info = _APP_DESCRIPTIONS.get(app_name, {})
    if not info:
        return f"# {app_name}\n\nAucune information disponible."

    md = f"""# {info['title']}

{info['description']}

---

## Points clés

"""
    for f in info.get('features', []):
        md += f"- **{f}**\n"

    md += f"""

---

## Bénéfices

- **Gain de temps** : automatisation des tâches répétitives
- **Fiabilité** : données sécurisées sur PostgreSQL
- **Ergonomie** : interface Material Design 3 intuitive
- **Flexibilité** : mode connecté (Intranet/Cloud) ou hors-ligne
- **Évolutivité** : mises à jour régulières

---

## Contact

**Arc-en-Ciel**  
Email : contact@arc-en-ciel.education  
Site : www.arc-en-ciel.education

---

*{info['name']} — Une solution de la suite Larc*
"""
    return md


def gen_tech_doc_latex(app_name: str) -> str:
    info = _APP_DESCRIPTIONS.get(app_name, {})
    if not info:
        return r"\section*{" + _latex_escape(app_name) + "}\nAucune information disponible."

    name = _latex_escape(info.get('name', app_name))
    title = _latex_escape(info.get('title', ''))
    desc = _latex_escape(info.get('description', ''))

    features_latex = '\n'.join("  \\item " + _latex_escape(f) for f in info.get('features', []))
    roles_latex = '\n'.join("  \\item \\textbf{" + _latex_escape(r) + "}" for r in info.get('roles', []))
    db_tables_latex = '\n'.join("  \\item \\texttt{" + _latex_escape(t) + "}" for t in info.get('db_tables', []))

    modules_latex = ""
    for m in info.get('modules', []):
        parts = m.split(' — ')
        file = _latex_escape(parts[0])
        desc_mod = _latex_escape(parts[1]) if len(parts) > 1 else ''
        modules_latex += "    \\texttt{" + file + "} & " + desc_mod + " \\\\ \\hline\n"

    return """\\documentclass[11pt,a4paper]{article}
\\usepackage[french]{babel}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage{geometry}
\\geometry{margin=2.5cm}
\\usepackage{hyperref}
\\usepackage{xcolor}

\\definecolor{larcblue}{HTML}{1565C0}

\\title{\\color{larcblue}""" + title + """ — Documentation technique}
\\author{Les logiciels Larc — Arc-en-Ciel}
\\date{\\today}

\\begin{document}
\\maketitle
\\tableofcontents
\\newpage

\\section{Architecture}

""" + name + """ est une application \\textbf{PySide6 (Qt6)} desktop,
développée en Python~3. Elle utilise les widgets Material Design~3 via
\\texttt{phibuilder} et se connecte à PostgreSQL via \\texttt{psycopg2}.

\\section{Fonctionnalités principales}

\\begin{itemize}
""" + features_latex + """
\\end{itemize}

\\section{Rôles utilisateurs}

\\begin{itemize}
""" + roles_latex + """
\\end{itemize}

\\section{Base de données}

Tables principales~:

\\begin{itemize}
""" + db_tables_latex + """
\\end{itemize}

\\section{Modules principaux}

\\begin{center}
\\begin{tabular}{|l|l|}
\\hline
\\textbf{Fichier} & \\textbf{Rôle} \\\\ \\hline
""" + modules_latex + """\\end{tabular}
\\end{center}

\\section{Dépendances}

\\begin{itemize}
  \\item \\textbf{PySide6} $\\ge$ 6.5 — Framework Qt6
  \\item \\textbf{psycopg2-binary} $\\ge$ 2.9 — Driver PostgreSQL
  \\item \\textbf{materialyoucolor} $\\ge$ 3.0 — Moteur de couleurs Material Design~3
  \\item \\textbf{LarcCommon} — Librairie partagée (thèmes, i18n, icônes, widgets)
\\end{itemize}

\\section{Connexion à la base de données}

\\begin{itemize}
  \\item \\textbf{Intranet} : PostgreSQL \\texttt{127.0.0.1:5432} — \\texttt{NewLarcDB}
  \\item \\textbf{Cloud} : Supabase \\texttt{aws-1-eu-north-1.pooler.supabase.com:6543}
  \\item \\texttt{autocommit = True} sur toutes les connexions
\\end{itemize}

\\end{document}
"""


def gen_print_ad_latex(app_name: str) -> str:
    info = _APP_DESCRIPTIONS.get(app_name, {})
    if not info:
        return r"\section*{" + _latex_escape(app_name) + "}\nAucune information disponible."

    name = _latex_escape(info.get('name', app_name))
    title = _latex_escape(info.get('title', ''))
    desc = _latex_escape(info.get('description', ''))

    features_latex = '\n'.join("  \\item \\textbf{" + _latex_escape(f) + "}" for f in info.get('features', []))

    return """\\documentclass[11pt,a4paper]{article}
\\usepackage[french]{babel}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage{geometry}
\\geometry{margin=2cm, bottom=2.5cm}
\\usepackage{hyperref}
\\usepackage{xcolor}

\\definecolor{larcblue}{HTML}{1565C0}
\\definecolor{larclight}{HTML}{E3F2FD}

\\newcommand{\\larcsection}[1]{
  \\vspace{1em}
  {\\color{larcblue}\\Large\\textbf{#1}}
  \\vspace{0.5em}
}

\\begin{document}
\\thispagestyle{empty}

\\begin{center}
  {\\Huge\\color{larcblue}\\textbf{""" + name + """}}\\\\[0.3cm]
  {\\Large """ + title + """}
\\end{center}

\\vspace{0.8cm}

\\begin{center}
\\fcolorbox{larcblue}{larclight}{
  \\begin{minipage}{0.85\\textwidth}
    \\centering
    """ + desc + """
  \\end{minipage}
}
\\end{center}

\\larcsection{Points clés}

\\begin{itemize}
""" + features_latex + """
\\end{itemize}

\\larcsection{Bénéfices}

\\begin{itemize}
  \\item \\textbf{Gain de temps} : automatisation des tâches répétitives
  \\item \\textbf{Fiabilité} : données sécurisées sur PostgreSQL
  \\item \\textbf{Ergonomie} : interface Material Design~3 intuitive
  \\item \\textbf{Flexibilité} : mode connecté (Intranet/Cloud) ou hors-ligne
  \\item \\textbf{Évolutivité} : mises à jour régulières
\\end{itemize}

\\vspace{1.5cm}

\\begin{center}
\\fbox{
  \\begin{minipage}{0.85\\textwidth}
    \\centering
    {\\large\\textbf{Contact}}\\\\[0.3cm]
    \\textbf{Arc-en-Ciel}\\\\
    Email : \\href{mailto:contact@arc-en-ciel.education}{contact@arc-en-ciel.education}\\\\
    Site : \\href{https://www.arc-en-ciel.education}{www.arc-en-ciel.education}
  \\end{minipage}
}
\\end{center}

\\vfill

\\begin{center}
  {\\footnotesize\\color{gray} """ + name + """ — Une solution de la suite Larc}
\\end{center}

\\end{document}
"""


def get_source_dir(app_name: str) -> str:
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(base, app_name)


def gen_auto_user_doc(app_name: str) -> str:
    from LarcDocs.common.code_parser import gen_summary_from_code
    from LarcDocs.common.doc_parser import gen_agents_summary, find_agents_md

    info = _APP_DESCRIPTIONS.get(app_name, {})
    src_dir = get_source_dir(app_name)
    has_src = os.path.isdir(src_dir)
    has_agents = bool(find_agents_md(app_name))

    md = f"# Manuel utilisateur — {info.get('title', app_name)}"
    md += f"\n\n## Présentation\n\n{info.get('description', 'Application de la suite Larc.')}"

    if info.get('features'):
        md += "\n\n---\n\n## Fonctionnalités\n\n"
        for f in info['features']:
            md += f"- {f}\n"

    if info.get('roles'):
        md += "\n\n---\n\n## Rôles utilisateurs\n\n"
        for r in info['roles']:
            md += f"- **{r}**\n"

    if has_agents:
        md += "\n\n---\n\n"
        md += gen_agents_summary(app_name)

    if has_src and info.get('modules'):
        md += "\n\n---\n\n## Modules\n\n| Fichier | Rôle |\n|---------|------|\n"
        for m in info['modules']:
            parts = m.split(' — ')
            md += f"| `{parts[0]}` | {parts[1] if len(parts) > 1 else ''} |\n"

    if has_src:
        md += "\n\n---\n\n"
        try:
            md += gen_summary_from_code(src_dir)
        except Exception as e:
            md += f"\n\n*Erreur lors de l'analyse du code : {e}*"

    return md


def gen_auto_tech_doc(app_name: str) -> str:
    from LarcDocs.common.code_parser import gen_summary_from_code
    from LarcDocs.common.doc_parser import parse_agents_md, find_agents_md

    info = _APP_DESCRIPTIONS.get(app_name, {})
    src_dir = get_source_dir(app_name)
    has_agents = bool(find_agents_md(app_name))
    agents_data = {}
    if has_agents:
        agents_data = parse_agents_md(find_agents_md(app_name))

    md = f"# Documentation technique — {info.get('title', app_name)}"
    md += f"\n\n## Architecture\n\n{info.get('description', '')}"
    md += f"\n\n{info.get('name', app_name)} est une application PySide6 (Qt6) desktop, "
    md += "développée en Python. Elle utilise les widgets Material Design 3 via **phibuilder** "
    md += "et se connecte à PostgreSQL via **psycopg2**.\n"

    if info.get('db_tables'):
        md += "\n---\n\n## Base de données\n\n"
        for t in info['db_tables']:
            md += f"- `{t}`\n"

    if has_agents:
        md += "\n---\n\n## Documentation de référence"
        md += f"\n\n*Source : {os.path.basename(find_agents_md(app_name))}*\n\n"
        for s in agents_data.get('sections', [])[:10]:
            title = s.get('title', '')
            if title and len(s.get('content', '')) > 50:
                md += f"### {title}\n\n{s['content'][:500]}\n\n"

    md += "\n---\n\n## Dépendances\n\n"
    md += "- **PySide6** >= 6.5 — Framework Qt6\n"
    md += "- **psycopg2-binary** >= 2.9 — Driver PostgreSQL\n"
    md += "- **materialyoucolor** >= 3.0 — Moteur de couleurs M3\n"
    md += "- **LarcCommon** — Librairie partagée\n\n"

    if info.get('modules'):
        md += "---\n\n## Modules\n\n| Fichier | Rôle |\n|---------|------|\n"
        for m in info['modules']:
            parts = m.split(' — ')
            md += f"| `{parts[0]}` | {parts[1] if len(parts) > 1 else ''} |\n"

    try:
        code_summary = gen_summary_from_code(src_dir) if os.path.isdir(src_dir) else ""
        if code_summary:
            md += f"\n---\n\n{code_summary}\n"
    except Exception as e:
        md += f"\n\n*Erreur analyse code : {e}*"

    return md


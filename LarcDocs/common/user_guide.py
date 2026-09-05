"""Génération de guides utilisateur illustrés (pas-à-pas, captures d'écran)."""
import os


_SCENARIOS = {
    'LarcSuperviseur': {
        'title': 'Guide de prise en main — LarcSuperviseur',
        'intro': (
            "LarcSuperviseur est l'application de supervision des présences et événements. "
            "Elle permet de suivre en temps réel les absences, retards et événements des élèves, "
            "avec des statistiques par groupe, classe et élève."
        ),
        'prerequis': [
            "Avoir un compte utilisateur (Superviseur, Coordinateur ou Administrateur)",
            "PostgreSQL doit être en marche sur le réseau local",
            "L'application LarcSuperviseur doit être installée",
        ],
        'steps': [
            {
                'title': '1. Connexion',
                'description': (
                    "Au lancement, une fenêtre de connexion s'affiche. "
                    "Saisissez votre **email** et votre **mot de passe**, puis cliquez sur **Connexion Intranet**."
                ),
                'screenshot': '01-login.png',
                'tips': [
                    "Si le bouton Intranet est grisé, vérifiez que vous êtes bien connecté au réseau local.",
                    "Le thème (Bleu, Dark, Sobre, Contrasté) peut être changé avant connexion via le bouton en haut à droite.",
                ],
            },
            {
                'title': '2. L\'écran principal',
                'description': (
                    "Après connexion, vous arrivez sur l'écran principal divisé en trois zones :\n\n"
                    "- **Barre du haut** : date du jour, état du réseau (🟢 Intranet / ☁️ Cloud), sélecteur de période, bouton de thème\n"
                    "- **Barre latérale gauche** : navigation par programme (PEI, DP) puis par classe\n"
                    "- **Zone centrale** : le contenu change selon la sélection (groupe, classe, ou élève)"
                ),
                'screenshot': '02-ecran-principal.png',
                'tips': [
                    "Cliquez sur un programme dans la barre latérale pour voir ses classes.",
                    "Cliquez sur une classe pour afficher la grille des élèves.",
                ],
            },
            {
                'title': '3. Enregistrer une absence journée',
                'description': (
                    "1. Dans la grille des élèves, cliquez sur l'élève concerné\n"
                    "2. Dans la fiche élève qui s'affiche à droite, cliquez sur le bouton **+ Événement**\n"
                    "3. Dans le générateur, cliquez sur **Absence journée**\n"
                    "4. Choisissez la nature de l'absence : Maladie, Accident, Vacances, etc.\n"
                    "5. Cliquez sur **Valider** pour enregistrer\n\n"
                    "Un badge rouge ✕ apparaît sur la carte de l'élève."
                ),
                'screenshot': '03-absence-journee.png',
                'tips': [
                    "Le breadcrumb en haut du générateur permet de revenir en arrière à tout moment.",
                ],
            },
            {
                'title': '4. Enregistrer un retard',
                'description': (
                    "1. Sélectionnez l'élève dans la grille\n"
                    "2. Cliquez sur **+ Événement**\n"
                    "3. Dans le générateur, cliquez sur **Retard**\n"
                    "4. Choisissez la durée : 5 min, 10 min, 15 min, 30 min, 45 min ou 1h00\n"
                    "5. Cliquez sur **Valider**\n\n"
                    "Un badge orange ⏱ apparaît sur la carte de l'élève."
                ),
                'screenshot': '04-retard.png',
                'tips': [
                    "La durée est un choix parmi 6 valeurs prédéfinies.",
                ],
            },
            {
                'title': '5. Créer un événement détaillé',
                'description': (
                    "1. Sélectionnez l'élève, puis **+ Événement**\n"
                    "2. Cliquez sur **Événements**\n"
                    "3. Choisissez un **lieu** (ex: Bureau BI, Infirmerie, Salle de classe)\n"
                    "4. Si salle de cours : choisissez une **matière**\n"
                    "5. Choisissez le **type d'événement** dans l'arborescence :\n"
                    "   - Bureau BI > Violence > Auteur\n"
                    "   - Médical > Consultation\n"
                    "   - Sortie > Récréation\n"
                    "   - Suivi > Retenue\n"
                    "6. Cliquez sur **Valider**\n\n"
                    "Le breadcrumb cumulatif vous montre le chemin parcouru :\n"
                    "`Événements > Bureau BI > Violence > Auteur`"
                ),
                'screenshot': '05-evenement-detaille.png',
                'tips': [
                    "Chaque segment du breadcrumb est cliquable pour revenir à cette étape.",
                    "Les matières ne s'affichent que si vous sélectionnez une salle de cours.",
                ],
            },
            {
                'title': '6. Consulter les statistiques',
                'description': (
                    "Quand un **groupe** (et non une classe) est sélectionné dans la barre latérale, "
                    "le panneau central affiche :\n\n"
                    "- **KPIs** : nombre d'absences, retards, événements du jour\n"
                    "- **Graphiques** : donut des types d'événements, barres par période\n"
                    "- **Historique** : tableau des événements récents\n\n"
                    "Sélectionnez une classe pour voir les statistiques par élève."
                ),
                'screenshot': '06-statistiques.png',
                'tips': [
                    "Les graphiques sont interactifs : passez la souris pour voir les détails.",
                ],
            },
            {
                'title': '7. Fiche détaillée d\'un élève',
                'description': (
                    "En cliquant sur un élève dans la grille, le panneau de droite affiche :\n\n"
                    "- **Photo** de l'élève\n"
                    "- **Informations** : nom, prénom, classe, programme\n"
                    "- **Contact** : email, téléphone des parents\n"
                    "- **Événements** : liste chronologique avec icônes et couleurs\n"
                    "- **Graphique** : répartition des types d'événements\n\n"
                    "Cliquez droit sur un événement dans le tableau pour le **modifier** ou le **supprimer**."
                ),
                'screenshot': '07-fiche-eleve.png',
                'tips': [
                    "Le menu contextuel (clic droit) permet d'éditer ou supprimer un événement.",
                ],
            },
            {
                'title': '8. Éditer l\'emploi du temps',
                'description': (
                    "Depuis la barre du haut, le bouton **📅 Emploi du temps** ouvre l'éditeur.\n\n"
                    "Vous pouvez :\n"
                    "- Visualiser les créneaux par jour et heure\n"
                    "- Ajouter ou modifier des cours\n"
                    "- Associer des matières et des professeurs à chaque créneau"
                ),
                'screenshot': '08-emploi-du-temps.png',
                'tips': [
                    "L'emploi du temps est lié au terme actif défini par l'administrateur.",
                ],
            },
            {
                'title': '9. Personnaliser l\'interface',
                'description': (
                    "Plusieurs options de personnalisation sont disponibles :\n\n"
                    "- **Thème** : bouton en haut à droite (4 thèmes : Bleu, Dark, Sobre, Contrasté)\n"
                    "- **Langue** : menu profil → Préférences → Français ou English\n"
                    "- **Période** : sélecteur dans la barre du haut pour filtrer par trimestre\n"
                    "- **Taille des vignettes** : réglable dans les Préférences"
                ),
                'screenshot': '09-personnalisation.png',
                'tips': [
                    "Le thème et la langue sont sauvegardés dans votre profil et restaurés à la prochaine connexion.",
                ],
            },
        ],
        'faq': [
            {
                'q': "Je ne vois pas tous les élèves dans la grille.",
                'a': "Vérifiez que vous avez sélectionné la bonne **période** (trimestre) dans la barre du haut. Les élèves sont filtrés par période active."
            },
            {
                'q': "Comment modifier un événement déjà enregistré ?",
                'a': "Dans la fiche élève, faites un **clic droit** sur l'événement dans le tableau, puis choisissez **Modifier**."
            },
            {
                'q': "Le bouton + Événement est grisé.",
                'a': "Votre rôle doit être **Superviseur** (écriture), **Coordinateur** (validation) ou **Administrateur** pour créer des événements."
            },
            {
                'q': "Comment changer mon mot de passe ?",
                'a': "Menu Profil (icône personne en haut) → **Préférences** → onglet Sécurité."
            },
        ],
    },
    'LarcSecretaire': {
        'title': 'Guide de prise en main — LarcSecretaire',
        'intro': (
            "LarcSecretaire est l'application de gestion administrative des élèves. "
            "Elle permet de gérer les dossiers complets, les contacts parents, les documents."
        ),
        'prerequis': [
            "Avoir un compte Secrétaire ou Administrateur",
            "PostgreSQL en marche sur le réseau local",
        ],
        'steps': [
            {
                'title': '1. Connexion',
                'description': "Connectez-vous avec votre email et mot de passe (onglet Intranet ou Cloud).",
                'screenshot': '01-login.png',
                'tips': [],
            },
            {
                'title': '2. Tableau de bord',
                'description': (
                    "L'écran principal affiche :\n"
                    "- Le nombre total d'élèves et de dossiers\n"
                    "- Les dernières modifications\n"
                    "- L'accès rapide aux sections principales"
                ),
                'screenshot': '02-tableau-de-bord.png',
                'tips': [],
            },
            {
                'title': '3. Créer un dossier élève',
                'description': (
                    "1. Cliquez sur **+ Nouvel élève**\n"
                    "2. Remplissez les sections : Identité, Adresse, Parents\n"
                    "3. Ajoutez une photo si disponible\n"
                    "4. Cliquez sur **Enregistrer**"
                ),
                'screenshot': '03-nouvel-eleve.png',
                'tips': [
                    "Tous les champs marqués d'un astérisque (*) sont obligatoires.",
                ],
            },
            {
                'title': '4. Gérer les parents et contacts',
                'description': (
                    "Dans la fiche élève, section Parents :\n"
                    "- Ajoutez un parent existant ou créez-en un nouveau\n"
                    "- Renseignez : nom, prénom, email, téléphone, adresse\n"
                    "- Définissez la relation (père, mère, tuteur, etc.)\n"
                    "- Activez/désactivez les notifications"
                ),
                'screenshot': '04-parents.png',
                'tips': [
                    "Un parent peut être lié à plusieurs élèves (fratrie).",
                ],
            },
            {
                'title': '5. Gérer les documents',
                'description': (
                    "Le panneau Dossiers permet de :\n"
                    "- **Ajouter** des fichiers (PDF, images, Word)\n"
                    "- **Prévisualiser** les documents dans l'application\n"
                    "- **Télécharger** ou **supprimer** des fichiers\n"
                    "- Classer par type (administratif, médical, pédagogique)"
                ),
                'screenshot': '05-documents.png',
                'tips': [],
            },
            {
                'title': '6. Panel superviseur',
                'description': (
                    "Accessible aux Administrateurs :\n"
                    "- Vue d'ensemble des absences et événements\n"
                    "- Indicateurs et KPIs\n"
                    "- Export des données"
                ),
                'screenshot': '06-superviseur.png',
                'tips': [],
            },
        ],
        'faq': [
            {
                'q': "Comment rechercher un élève rapidement ?",
                'a': "Utilisez la barre de recherche en haut du tableau de bord. Tapez le nom ou prénom."
            },
            {
                'q': "Puis-je importer des élèves depuis un fichier Excel ?",
                'a': "Oui, utilisez la fonction **Import** dans le menu Fichier. Formats acceptés : CSV, XLSX."
            },
        ],
    },
    'LarcProf': {
        'title': 'Guide de prise en main — LarcProf',
        'intro': (
            "LarcProf est l'application pour les professeurs. "
            "Elle permet de saisir les notes et évaluations, avec synchronisation entre l'ordinateur du professeur et le serveur."
        ),
        'prerequis': [
            "Avoir un compte Professeur",
            "SQLite est automatique, PostgreSQL pour la synchronisation",
        ],
        'steps': [
            {
                'title': '1. Connexion',
                'description': (
                    "LarcProf propose 4 modes de connexion :\n"
                    "- **Intranet** : connexion au serveur local\n"
                    "- **Cloud** : connexion via Supabase/Google\n"
                    "- **Hors connexion (PIN)** : code PIN à 4 chiffres\n"
                    "- **Nouvelle instance** : première installation"
                ),
                'screenshot': '01-login.png',
                'tips': [
                    "Le mode PIN permet de travailler sans connexion réseau.",
                ],
            },
            {
                'title': '2. Tableau de bord',
                'description': (
                    "Après connexion, le dashboard affiche :\n"
                    "- Votre profil (nom, email, classes)\n"
                    "- État de la connexion (Intranet ●/○, Cloud ●/○)\n"
                    "- Dernière synchronisation\n"
                    "- Boutons d'accès aux sections selon votre profil (PEI/DP)"
                ),
                'screenshot': '02-dashboard.png',
                'tips': [
                    "Les boutons PEI/DP s'affichent uniquement si vous enseignez ces programmes.",
                ],
            },
            {
                'title': '3. Saisir des notes',
                'description': (
                    "1. Cliquez sur une section (ex: Unité de groupes de matières)\n"
                    "2. Sélectionnez votre classe-matière\n"
                    "3. La grille affiche les élèves en lignes et les critères en colonnes\n"
                    "4. Cliquez dans une cellule et tapez la note\n"
                    "5. Les couleurs pastel (rouge→blanc→vert) vous guident visuellement\n"
                    "6. Cliquez sur **Enregistrer** (mode hors-ligne) ou **Synchroniser** (mode connecté)"
                ),
                'screenshot': '03-grille-notes.png',
                'tips': [
                    "Navigation Excel-like : flèches, Tab, Entrée pour passer d'une cellule à l'autre.",
                    "Cliquez sur l'en-tête Nom/Prénom pour inverser l'ordre de tri.",
                ],
            },
            {
                'title': '4. Créer une évaluation',
                'description': (
                    "Le bouton **Gérer les évaluations** (icône 📋) ouvre une fenêtre permettant de :\n"
                    "- Créer une nouvelle évaluation (nom, date, coefficient)\n"
                    "- Activer/désactiver les critères de notation\n"
                    "- Supprimer une évaluation existante\n\n"
                    "Les colonnes de la grille s'adaptent automatiquement aux critères activés."
                ),
                'screenshot': '04-evaluations.png',
                'tips': [
                    "Seules les colonnes des critères activés pour l'évaluation sélectionnée sont affichées.",
                ],
            },
            {
                'title': '5. Synchroniser les données',
                'description': (
                    "Quand vous êtes connecté au réseau :\n"
                    "1. Cliquez sur **Synchroniser** dans le dashboard\n"
                    "2. L'application compare les données locales (SQLite) et serveur (PostgreSQL)\n"
                    "3. Les modifications sont envoyées et reçues automatiquement\n\n"
                    "Le compteur dans la carte Synchro indique le nombre de modifications en attente."
                ),
                'screenshot': '05-synchronisation.png',
                'tips': [
                    "Faites une synchronisation avant de quitter l'application pour sauvegarder votre travail.",
                    "En mode hors-ligne, vos notes sont sauvegardées localement et synchronisées plus tard.",
                ],
            },
        ],
        'faq': [
            {
                'q': "Je ne vois pas mes classes dans le dashboard.",
                'a': "Vérifiez que l'administrateur vous a bien assigné les classes-matières pour le trimestre en cours."
            },
            {
                'q': "Comment fonctionne le mode hors-ligne ?",
                'a': "Définissez un code PIN à 4 chiffres. Vos données sont stockées en local (SQLite) et synchronisées dès que vous vous reconnectez."
            },
        ],
    },
}


def get_apps_with_guide():
    return list(_SCENARIOS.keys())


def gen_user_guide(app_name: str) -> str:
    data = _SCENARIOS.get(app_name)
    if not data:
        return f"# Guide utilisateur — {app_name}\n\nAucun guide disponible pour cette application."

    screenshots_dir = f"screenshots/{app_name}"

    md = f"# {data['title']}\n\n"
    md += f"{data['intro']}\n\n"

    md += "---\n\n## Prérequis\n\n"
    for p in data['prerequis']:
        md += f"- {p}\n"

    md += "\n---\n\n## Prise en main pas à pas\n\n"

    for i, step in enumerate(data['steps']):
        md += f"### {step['title']}\n\n"
        md += f"{step['description']}\n\n"

        if step.get('screenshot'):
            md += f"![{step['title']}]({screenshots_dir}/{step['screenshot']})\n\n"
            md += f"> **Capture à faire** : `{screenshots_dir}/{step['screenshot']}`\n\n"

        if step.get('tips'):
            for tip in step['tips']:
                md += f"> 💡 **Astuce** : {tip}\n"
            md += "\n"

        md += "---\n\n"

    if data.get('faq'):
        md += "## Foire aux questions\n\n"
        for item in data['faq']:
            md += f"**Q: {item['q']}**\n\n"
            md += f"R: {item['a']}\n\n"

    md += "\n---\n\n"
    md += "## Liste des captures d'écran à réaliser\n\n"
    md += "| # | Description | Fichier |\n"
    md += "|---|-------------|--------|\n"
    for i, step in enumerate(data['steps']):
        if step.get('screenshot'):
            md += f"| {i+1} | {step['title']} | `{screenshots_dir}/{step['screenshot']}` |\n"

    md += f"\n---\n\n*Guide généré automatiquement — Dernière mise à jour : {{date}}*\n"
    return md


def list_screenshots_needed(app_name: str) -> list:
    data = _SCENARIOS.get(app_name)
    if not data:
        return []
    screenshots_dir = os.path.join(os.path.dirname(__file__), '..', 'screenshots', app_name)
    needed = []
    for step in data['steps']:
        if step.get('screenshot'):
            path = os.path.join(screenshots_dir, step['screenshot'])
            needed.append({
                'step': step['title'],
                'file': step['screenshot'],
                'description': step['description'][:100] + '...',
                'exists': os.path.exists(path),
            })
    return needed


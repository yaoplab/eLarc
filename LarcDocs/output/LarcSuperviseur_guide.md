# Guide de prise en main — LarcSuperviseur

LarcSuperviseur est l'application de supervision des présences et événements. Elle permet de suivre en temps réel les absences, retards et événements des élèves, avec des statistiques par groupe, classe et élève.

---

## Prérequis

- Avoir un compte utilisateur (Superviseur, Coordinateur ou Administrateur)
- PostgreSQL doit être en marche sur le réseau local
- L'application LarcSuperviseur doit être installée

---

## Prise en main pas à pas

### 1. Connexion

Au lancement, une fenêtre de connexion s'affiche. Saisissez votre **email** et votre **mot de passe**, puis cliquez sur **Connexion Intranet**.

![1. Connexion](screenshots/LarcSuperviseur/01-login.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/01-login.png`

> 💡 **Astuce** : Si le bouton Intranet est grisé, vérifiez que vous êtes bien connecté au réseau local.
> 💡 **Astuce** : Le thème (Bleu, Dark, Sobre, Contrasté) peut être changé avant connexion via le bouton en haut à droite.

---

### 2. L'écran principal

Après connexion, vous arrivez sur l'écran principal divisé en trois zones :

- **Barre du haut** : date du jour, état du réseau (🟢 Intranet / ☁️ Cloud), sélecteur de période, bouton de thème
- **Barre latérale gauche** : navigation par programme (PEI, DP) puis par classe
- **Zone centrale** : le contenu change selon la sélection (groupe, classe, ou élève)

![2. L'écran principal](screenshots/LarcSuperviseur/02-ecran-principal.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/02-ecran-principal.png`

> 💡 **Astuce** : Cliquez sur un programme dans la barre latérale pour voir ses classes.
> 💡 **Astuce** : Cliquez sur une classe pour afficher la grille des élèves.

---

### 3. Enregistrer une absence journée

1. Dans la grille des élèves, cliquez sur l'élève concerné
2. Dans la fiche élève qui s'affiche à droite, cliquez sur le bouton **+ Événement**
3. Dans le générateur, cliquez sur **Absence journée**
4. Choisissez la nature de l'absence : Maladie, Accident, Vacances, etc.
5. Cliquez sur **Valider** pour enregistrer

Un badge rouge ✕ apparaît sur la carte de l'élève.

![3. Enregistrer une absence journée](screenshots/LarcSuperviseur/03-absence-journee.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/03-absence-journee.png`

> 💡 **Astuce** : Le breadcrumb en haut du générateur permet de revenir en arrière à tout moment.

---

### 4. Enregistrer un retard

1. Sélectionnez l'élève dans la grille
2. Cliquez sur **+ Événement**
3. Dans le générateur, cliquez sur **Retard**
4. Choisissez la durée : 5 min, 10 min, 15 min, 30 min, 45 min ou 1h00
5. Cliquez sur **Valider**

Un badge orange ⏱ apparaît sur la carte de l'élève.

![4. Enregistrer un retard](screenshots/LarcSuperviseur/04-retard.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/04-retard.png`

> 💡 **Astuce** : La durée est un choix parmi 6 valeurs prédéfinies.

---

### 5. Créer un événement détaillé

1. Sélectionnez l'élève, puis **+ Événement**
2. Cliquez sur **Événements**
3. Choisissez un **lieu** (ex: Bureau BI, Infirmerie, Salle de classe)
4. Si salle de cours : choisissez une **matière**
5. Choisissez le **type d'événement** dans l'arborescence :
   - Bureau BI > Violence > Auteur
   - Médical > Consultation
   - Sortie > Récréation
   - Suivi > Retenue
6. Cliquez sur **Valider**

Le breadcrumb cumulatif vous montre le chemin parcouru :
`Événements > Bureau BI > Violence > Auteur`

![5. Créer un événement détaillé](screenshots/LarcSuperviseur/05-evenement-detaille.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/05-evenement-detaille.png`

> 💡 **Astuce** : Chaque segment du breadcrumb est cliquable pour revenir à cette étape.
> 💡 **Astuce** : Les matières ne s'affichent que si vous sélectionnez une salle de cours.

---

### 6. Consulter les statistiques

Quand un **groupe** (et non une classe) est sélectionné dans la barre latérale, le panneau central affiche :

- **KPIs** : nombre d'absences, retards, événements du jour
- **Graphiques** : donut des types d'événements, barres par période
- **Historique** : tableau des événements récents

Sélectionnez une classe pour voir les statistiques par élève.

![6. Consulter les statistiques](screenshots/LarcSuperviseur/06-statistiques.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/06-statistiques.png`

> 💡 **Astuce** : Les graphiques sont interactifs : passez la souris pour voir les détails.

---

### 7. Fiche détaillée d'un élève

En cliquant sur un élève dans la grille, le panneau de droite affiche :

- **Photo** de l'élève
- **Informations** : nom, prénom, classe, programme
- **Contact** : email, téléphone des parents
- **Événements** : liste chronologique avec icônes et couleurs
- **Graphique** : répartition des types d'événements

Cliquez droit sur un événement dans le tableau pour le **modifier** ou le **supprimer**.

![7. Fiche détaillée d'un élève](screenshots/LarcSuperviseur/07-fiche-eleve.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/07-fiche-eleve.png`

> 💡 **Astuce** : Le menu contextuel (clic droit) permet d'éditer ou supprimer un événement.

---

### 8. Éditer l'emploi du temps

Depuis la barre du haut, le bouton **📅 Emploi du temps** ouvre l'éditeur.

Vous pouvez :
- Visualiser les créneaux par jour et heure
- Ajouter ou modifier des cours
- Associer des matières et des professeurs à chaque créneau

![8. Éditer l'emploi du temps](screenshots/LarcSuperviseur/08-emploi-du-temps.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/08-emploi-du-temps.png`

> 💡 **Astuce** : L'emploi du temps est lié au terme actif défini par l'administrateur.

---

### 9. Personnaliser l'interface

Plusieurs options de personnalisation sont disponibles :

- **Thème** : bouton en haut à droite (4 thèmes : Bleu, Dark, Sobre, Contrasté)
- **Langue** : menu profil → Préférences → Français ou English
- **Période** : sélecteur dans la barre du haut pour filtrer par trimestre
- **Taille des vignettes** : réglable dans les Préférences

![9. Personnaliser l'interface](screenshots/LarcSuperviseur/09-personnalisation.png)

> **Capture à faire** : `screenshots/LarcSuperviseur/09-personnalisation.png`

> 💡 **Astuce** : Le thème et la langue sont sauvegardés dans votre profil et restaurés à la prochaine connexion.

---

## Foire aux questions

**Q: Je ne vois pas tous les élèves dans la grille.**

R: Vérifiez que vous avez sélectionné la bonne **période** (trimestre) dans la barre du haut. Les élèves sont filtrés par période active.

**Q: Comment modifier un événement déjà enregistré ?**

R: Dans la fiche élève, faites un **clic droit** sur l'événement dans le tableau, puis choisissez **Modifier**.

**Q: Le bouton + Événement est grisé.**

R: Votre rôle doit être **Superviseur** (écriture), **Coordinateur** (validation) ou **Administrateur** pour créer des événements.

**Q: Comment changer mon mot de passe ?**

R: Menu Profil (icône personne en haut) → **Préférences** → onglet Sécurité.


---

## Liste des captures d'écran à réaliser

| # | Description | Fichier |
|---|-------------|--------|
| 1 | 1. Connexion | `screenshots/LarcSuperviseur/01-login.png` |
| 2 | 2. L'écran principal | `screenshots/LarcSuperviseur/02-ecran-principal.png` |
| 3 | 3. Enregistrer une absence journée | `screenshots/LarcSuperviseur/03-absence-journee.png` |
| 4 | 4. Enregistrer un retard | `screenshots/LarcSuperviseur/04-retard.png` |
| 5 | 5. Créer un événement détaillé | `screenshots/LarcSuperviseur/05-evenement-detaille.png` |
| 6 | 6. Consulter les statistiques | `screenshots/LarcSuperviseur/06-statistiques.png` |
| 7 | 7. Fiche détaillée d'un élève | `screenshots/LarcSuperviseur/07-fiche-eleve.png` |
| 8 | 8. Éditer l'emploi du temps | `screenshots/LarcSuperviseur/08-emploi-du-temps.png` |
| 9 | 9. Personnaliser l'interface | `screenshots/LarcSuperviseur/09-personnalisation.png` |

---

*Guide généré automatiquement — Dernière mise à jour : {date}*

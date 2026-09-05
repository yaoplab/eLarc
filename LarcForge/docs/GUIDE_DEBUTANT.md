# Guide du débutant — LarcForge

Bienvenue ! Ce guide explique **pas à pas** comment utiliser LarcForge,
l'outil de contrôle de la qualité du logiciel de votre école.
Aucune connaissance technique n'est requise : tout se fait en **cliquant**,
avec des **cases à cocher** et des **menus déroulants**.

---

## 1. Qu'est-ce que LarcForge ?

LarcForge est un **centre de contrôle** qui vérifie automatiquement les
applications de l'école (présence, secrétariat, professeurs, comptabilité…).

À chaque vérification, il examine :

- **Les règles de qualité du code** (linters) : mises en forme, couleurs,
  tailles de fichiers, connexions à la base…
- **Les tests automatiques** : chaque application passe ses propres tests.
- **Les erreurs remontées par les applications** (journal d'erreurs).

Le résultat est un **registre de fiches** : une fiche = un problème détecté.
Vous pouvez résoudre une fiche (avec une note) ou la rouvrir.

> **En clair :** vous lancez un bouton, LarcForge inspecte tout, et vous
> montre ce qui ne va pas — avec la possibilité de suivre chaque problème
> jusqu'à sa correction.

---

## 2. Démarrer l'outil

### Ouvrir l'interface

Depuis le dossier des projets, lancez la commande :

```
python -m larcforge ui
```

Une fenêtre s'ouvre avec **5 rubriques** dans la colonne de gauche :

| Rubrique | À quoi ça sert |
|---|---|
| **Accueil** | Le tableau de bord : chiffres clés et alertes |
| **Vérifications** | Lancer les contrôles de tout le parc logiciel |
| **Registre des issues** | La liste des problèmes détectés (les « fiches ») |
| **Configuration** | Adapter l'outil à votre école |
| **Aide** | Ce guide, et les explications de chaque écran |

> **Astuce :** l'outil fonctionne même si la base de données est
> momentanément indisponible. Un message « Base de données indisponible »
> s'affiche avec un bouton **Réessayer**.

---

## 3. Rubrique Accueil — le tableau de bord

À chaque visite, l'Accueil se rafraîchit et affiche :

- **4 grands chiffres** : fiches ouvertes, régressions, résolues, total.
- **Alertes** : modules modifiés sans fiche résolue, fiches dont le fichier
  a changé depuis leur détection.
- **Derniers runs** : historique des dernières vérifications (numéro,
  commande, résultat).
- **Modules modifiés** : quels fichiers ont changé au dernier contrôle.

**Que faire ici ?** Rien de particulier : c'est un **état des lieux**.
Si des alertes apparaissent, ouvrez le **Registre des issues** pour traiter
les fiches concernées.

---

## 4. Rubrique Vérifications — lancer les contrôles

C'est le cœur de l'outil. Tout se règle avec des cases à cocher et des menus.

### 4.1 Le type de vérification (menu déroulant)

| Choix | Effet |
|---|---|
| **Tout vérifier** (recommandé) | Linters + tests + erreurs d'application |
| Linters seulement | Uniquement les règles de qualité du code |
| Tests pytest seulement | Uniquement les tests automatiques |
| Erreurs d'application (24 h) | Uniquement le journal d'erreurs |

### 4.2 Les cases à cocher

- **Projets** : les applications à contrôler (cochez toutes par défaut).
- **Linters** : les règles de qualité à appliquer (laissez tout coché).
- **Tests** : les applications dont les tests seront lancés.
  La case *« tests d'intégration »* est décochée par défaut (lente).

### 4.3 Les menus d'options

- **Fenêtre de temps** : sur quelle période chercher les erreurs
  (24 h, 12 h, 48 h…). Le plus courant : **24 dernières heures**.
- **Niveaux** : *Erreurs et avertissements* (recommandé), ou seulement
  les erreurs.

### 4.4 Le bandeau de sécurité

Sous les options, un bandeau vous informe :

- 🟢 **« Résolution automatique active »** : c'est le cas avec
  *Tout vérifier*. Les fiches corrigées sont automatiquement marquées
  résolues au run suivant.
- 🟠 **« Vérifications personnalisées »** : vous avez modifié la sélection.
  Les fiches ne seront pas résolues automatiquement — vous les traiterez
  à la main dans le Registre.

> **Règle d'or :** pour une vérification complète, gardez
> **« Tout vérifier »** avec tout coché.

### 4.5 Lancer et suivre

1. Cliquez sur **« Lancer la vérification »**.
2. Une barre de progression s'affiche avec le temps écoulé.
3. À la fin, le résultat s'affiche : nombre de fiches trouvées,
   de régressions, d'erreurs techniques.
4. S'il y a des fiches, un bouton **« Voir le registre des issues »**
   vous emmène directement dans la liste.

> Si vous fermez l'outil pendant une vérification, une confirmation
> vous demandera si vous voulez vraiment quitter (le run serait marqué
> comme interrompu).

---

## 5. Rubrique Registre des issues — les fiches

### 5.1 Filtrer la liste

- **Statut** : Tous / Ouvertes / Résolues / Régressées.
- **App** : une application précise (ex. LarcSuperviseur).
- **Source** : Linters / Tests / Erreurs d'application.
- **Recherche** : tapez un mot (ex. `NameError`) puis Entrée ou
  **Filtrer**.

Le compteur sous les filtres indique le nombre de fiches affichées
(500 maximum — affinez les filtres si besoin).

### 5.2 Lire une fiche

Cliquez sur une ligne : le **détail** s'affiche en bas —
message, fonction concernée, traceback complet, dates de détection.

### 5.3 Résoudre une fiche

1. Sélectionnez une fiche **ouverte** (ou régressée).
2. Cliquez sur **« Résoudre avec une note »**.
3. Écrivez ce qui a été fait (ex. « correction du calcul de moyenne »).
4. Validez : la fiche passe **Résolue** avec votre note.

### 5.4 Réouvrir une fiche

Une fiche résolue peut être rouverte (elle repasse **Ouverte** et la
note est effacée) — utile si le problème réapparaît.

---

## 6. Rubrique Configuration — adapter à votre école

Tout est enregistré **immédiatement** dans le fichier `ui_config.json`
(à côté de LarcForge).

### 6.1 Marque

- **Nom de l'école** : affiché dans le titre de la fenêtre et la colonne
  de gauche. Ex. « École Saint-Joseph ».
- **Thème** : Bleu, Dark, Sobre ou Contrasté — la fenêtre change de
  couleurs instantanément.

### 6.2 Racine du monorepo

Le dossier qui contient les applications. **Laissez vide** si LarcForge
se trouve dans le même dossier que les projets (cas standard).

### 6.3 Connexions aux bases de données

Une **école = sa propre base PostgreSQL**. Pour en ajouter une :

1. **Nouveau**, puis donnez un nom au profil.
2. Renseignez l'adresse (hôte), le port, le nom de la base,
   l'utilisateur et le mot de passe — **laissez vides** pour reprendre
   le fichier `config.ini` standard.
3. **Tester la connexion** : vérifie que tout est bon.
4. **Utiliser comme connexion active** : toute l'interface utilisera
   désormais cette base.

### 6.4 Profils de vérification

Un profil enregistre **les contrôles d'une école** : quels projets,
quels linters, quels tests, quelle fenêtre de temps.

1. **Nouveau**, donnez un nom (ex. « École Saint-Joseph — contrôles »).
2. Cochez/décochez selon les besoins.
3. **Sauvegarder le profil**, puis **Utiliser par défaut dans
   Vérifications** : le panneau Vérifications se pré-remplira
   automatiquement avec ce profil.

---

## 7. Résoudre les problèmes courants

| Symptôme | Cause possible | Solution |
|---|---|---|
| « Base de données indisponible » | Le service PostgreSQL est arrêté | Démarrez PostgreSQL puis **Réessayer** |
| « Erreur technique » à la fin d'un run | Problème de collecte (fichier verrouillé…) | Relancez la vérification |
| La résolution automatique est inactive | Vous avez modifié la sélection | Revenez à **« Tout vérifier »** |
| L'outil ne s'ouvre pas | PySide6 absent | `pip install "larcforge[gui]"` |

---

## 8. Rappels utiles

- **Une fiche = un problème.** Traitez-les une par une dans le Registre.
- **Résolvez avec une note** : la note est conservée dans le registre —
  elle explique le « pourquoi » aux futurs responsables.
- **Réouvrez sans crainte** : réouvrir ne supprime rien, la fiche
  redevient simplement à traiter.
- **Configuration = votre école.** Nom, thème, base de données,
  contrôles : tout est dans `ui_config.json` et s'applique au
  prochain lancement.

---

*Guide généré pour LarcForge — dernier run de vérification : voir
l'Accueil. Bon contrôle ! 🎓*

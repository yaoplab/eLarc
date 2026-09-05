# Documentation algorithmique d'eLarcProf

Ce dossier contient la description détaillée de l'algorithme global du programme.

## Structure

- `01_introduction.md` – introduction et ordre de lecture
- `02_point_entree_main.md` – point d'entrée (modes normal et CLI)
- `03_fenetre_connexion.md` – fenêtre de connexion
- `04_detection_reseau.md` – détection du réseau
- `05_connexion_intranet.md` – connexion intranet
- `06_connexion_cloud.md` – connexion cloud
- `07_authentification_intranet.md` – authentification intranet
- `08_authentification_cloud_oauth2.md` – authentification cloud OAuth2
- `09_authentification_pin.md` – authentification PIN
- `10_creation_instance_locale.md` – création instance locale
- `11_export_sqlite.md` – export SQLite
- `12_gestion_session.md` – gestion session
- `13_ouverture_fenetre_principale.md` – ouverture fenêtre principale (Phase 2)
- `14_changement_password_pin.md` – dialogues de changement de mot de passe et de PIN
- `15_logger.md` – logger applicatif `elarc.log`
- `16_main_window.md` – **fenêtre principale (top bar refactorée, grille élèves × notes)** — MIS À JOUR
- `17_pei_dp_separation.md` – décision architecturale : 2 fichiers UI distincts (PEI / DP)
- `18_tableau_de_bord_prof.md` – projet de tableau de bord par rôle (non implémenté)
- `19_evaluation_panel.md` – panneaux d'évaluations F/S (obsolète depuis la top bar)
- `20_eval_manager.md` – fenêtre de gestion complète des évaluations
- `etat_projet.md` – **état du projet à jour**
- `historique_construction.md` – **journal chronologique complet, itérations 1 à 20**

## Utilisation

Lisez les fichiers dans l'ordre numérique pour comprendre le flux complet.

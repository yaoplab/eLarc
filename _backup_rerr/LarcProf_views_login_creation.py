import os
import shutil

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from common.auth import AuthManager, OAuth2Manager
from common.database import DBMode, db
from common.session import AuthResult, UserRole
from common.sqlite_init import sqlite_init
from larccommon.safe_slot import safe_slot


# ---------------------------------------------------------------------------
# Generic background worker
# ---------------------------------------------------------------------------


class LoginCreationMixin:
    """Mixin LoginCreationMixin — voir le module parent."""
    # ------------------------------------------------------------------
    # New instance (inchangé)
    # ------------------------------------------------------------------
    @safe_slot("Unknown._browse_dest")
    def _browse_dest(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier parent")
        if folder:
            self._edt_n_dest.setText(folder)

    @safe_slot("Unknown._on_create")
    def _on_create(self) -> None:
        self._hide_error()
        email = self._edt_n_email.text().strip()
        parent = self._edt_n_dest.text().strip()
        if not email or not parent:
            self._show_error("Email et dossier de destination requis.")
            return

        if db.server_conn is not None and db.server_mode == DBMode.INTRANET:
            exists, infos = AuthManager.check_teacher_exists(email)
            if not exists:
                self._show_error("Cet email ne correspond à aucun professeur actif.")
                return
        elif db.server_conn is not None and db.server_mode == DBMode.CLOUD:
            exists, infos = AuthManager.check_teacher_exists(email)
            if not exists:
                self._show_error("Cet email ne correspond à aucun professeur actif.")
                return
        else:
            self._log("Tentative de connexion à l'Intranet…")
            if db.connect_intranet():
                exists, infos = AuthManager.check_teacher_exists(email)
                if not exists:
                    self._show_error("Cet email ne correspond à aucun professeur actif.")
                    return
            else:
                self._log("Intranet indisponible, tentative de connexion au Cloud…")
                if db.connect_cloud():
                    exists, infos = AuthManager.check_teacher_exists(email)
                    if not exists:
                        self._show_error("Cet email ne correspond à aucun professeur actif.")
                        return
                else:
                    self._show_error(
                        "Aucune connexion serveur disponible (Intranet ni Cloud). "
                        "La création d'instance est impossible."
                    )
                    return

        if db.server_mode == DBMode.INTRANET:
            from PySide6.QtWidgets import QInputDialog, QLineEdit

            pwd, ok = QInputDialog.getText(
                self,
                "Mot de passe",
                f"Veuillez saisir le mot de passe pour {email} :",
                QLineEdit.Password,
            )
            if not ok or not pwd:
                self._show_error("Mot de passe requis pour créer l'instance.")
                return

            auth_ok, _ignored, err = AuthManager.auth_intranet(email, pwd)
            if not auth_ok:
                self._show_error(f"Mot de passe incorrect : {err}")
                return

        elif db.server_mode == DBMode.CLOUD:
            self._log("Lancement de l'authentification OAuth2 Google…")
            auth_ok, res, err = OAuth2Manager.authenticate()
            if not auth_ok:
                self._show_error(f"Authentification Cloud échouée : {err}")
                return
            if res.email.lower() != email.lower():
                self._show_error("L'email du compte Google ne correspond pas à l'email saisi.")
                return
        else:
            self._show_error("Mode de connexion inconnu.")
            return

        slug = email.split("@")[0].replace(".", "_")
        dest = os.path.normpath(os.path.join(parent, f"eLarcProf_{slug}"))
        try:
            self._show_progress("Création du dossier de destination…")
            os.makedirs(dest, exist_ok=True)
            self._log(f"Dossier créé : {dest}")

            src = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
            self._show_progress("Copie des fichiers du projet…")
            for item in os.listdir(src):
                if item in ("__pycache__", ".git", ".venv"):
                    continue
                s = os.path.join(src, item)
                d = os.path.join(dest, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            dest_cfg = os.path.join(dest, "config.ini")
            if not os.path.exists(dest_cfg):
                self._log("config.ini introuvable dans la source, copie du config.ini source.")
                src_cfg = os.path.normpath(os.path.join(src, "config.ini"))
                if os.path.exists(src_cfg):
                    shutil.copy2(src_cfg, dest_cfg)
                else:
                    self._log("ATTENTION : aucun config.ini source trouve.")
                self._log(f"config.ini par défaut créé : {dest_cfg}")
            src_db = os.path.normpath(os.path.join(src, "elarc.db"))
            if os.path.exists(src_db):
                shutil.copy2(src_db, os.path.join(dest, "elarc.db"))
                self._log("elarc.db copié.")
            else:
                self._log("elarc.db introuvable dans la source.")
            self._log("Copie terminée.")

            dest_db = os.path.join(dest, "elarc.db")
            if not sqlite_init.init(dest_db):
                self._show_error(
                    "Impossible d'initialiser la base locale dans le dossier de destination."
                )
                return

            self._show_progress("Téléchargement des données professeur...")
            QApplication.processEvents()
            ok_ttd, err_ttd = sqlite_init.take_teacher_data(infos, self._log, db.local_conn, None)
            if not ok_ttd:
                self._log(f"take_teacher_data: {err_ttd}")

            ok, missing = sqlite_init.verify_tables()
            if not ok:
                self._log(f"ATTENTION : Tables manquantes dans la base locale : {missing}")

            sqlite_init.init_module_config(
                annee_scolaire=infos["annee_scolaire"],
                trimestre_courant=infos["trimestre_courant"],
                nom_professeur=f"{infos['first_name']} {infos['last_name']}",
                email_professeur=email,
            )

            res = AuthResult(
                user_id=infos["user_id"],
                email=email,
                full_name=f"{infos['first_name']} {infos['last_name']}",
                role=UserRole.PROF,
                term_id=infos["trimestre_courant"],
                term_label=infos["trimestre_label"],
            )
            sqlite_init.save_session(res)

            self._show_progress("Écriture du fichier instance.ini…")
            cfg_dest = os.path.join(dest, "instance.ini")
            with open(cfg_dest, "w", encoding="utf-8") as f:
                f.write(f"[Instance]\nEmail={email}\nCreated=auto\n")
            self._log(f"instance.ini créé : {cfg_dest}")

            self._show_progress("Création du lanceur lancer.bat…")
            bat = os.path.join(dest, "lancer.bat")
            with open(bat, "w", encoding="utf-8") as f:
                f.write('@echo off\ncd /d "%~dp0"\npython main.py\npause\n')
            self._log(f"lancer.bat créé : {bat}")

            self._show_progress("Instance créée avec succès.")
            QMessageBox.information(
                self,
                "Instance créée",
                f"Instance créée dans :\n{dest}\n\nLancez lancer.bat pour démarrer.",
            )
            self._hide_error()
        except Exception as e:
            self._show_error(f"Erreur de création : {e}")
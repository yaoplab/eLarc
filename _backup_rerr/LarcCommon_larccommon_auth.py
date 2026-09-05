"""AuthManager + OAuth2 PKCE."""
import os
import hashlib
import secrets
import base64
import configparser
import threading
import webbrowser
import json
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Tuple

from .session import AuthResult, UserRole
from .database import db, DBMode
from .design_system import ds
from .logger import log
from .config_loader import find_cfg


def _deduce_role_superviseur(is_dir: bool, is_coord: bool, is_sup: bool) -> UserRole:
    if is_dir: return UserRole.ADMIN
    if is_coord: return UserRole.COORD
    if is_sup: return UserRole.SUPERVISEUR
    return UserRole.SUPERVISEUR


def _load_active_term(cur) -> Tuple[int, str]:
    try:
        cur.execute("""
            SELECT t.id, t.label FROM larcauth_term t, larcauth_academicyear ay
            WHERE ay.s_id = 1 AND t.trim = ay.current_term_number
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return int(row[0]), row[1]
        # Fallback : dernier terme
        cur.execute("""
            SELECT id, label FROM larcauth_term ORDER BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return int(row[0]), row[1]
    except Exception:
        pass
    return 0, ''


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _deduce_role(is_adm: bool = False, is_coord: bool = False,
                 is_sup: bool = False, is_secretary: bool = False) -> UserRole:
    if is_adm: return UserRole.ADMIN
    if is_coord: return UserRole.COORD
    if is_secretary: return UserRole.SECR
    if is_sup: return UserRole.SUPERVISEUR
    return UserRole.PROF


class AuthManager:

    @classmethod
    def change_password(cls, email: str, current: str, new: str) -> Tuple[bool, str]:
        """Change le mot de passe intranet (SHA-256). Retourne (ok, message)."""
        conn = db.server_conn
        if conn is None or db.server_mode != DBMode.INTRANET:
            return False, "Non connecté à l'intranet"
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password FROM larcauth_aecuser WHERE LOWER(email) = %s",
                    (email.strip().lower(),),
                )
                row = cur.fetchone()
            if row is None:
                return False, "Utilisateur introuvable"
            if row[0] and row[0] != _sha256_hex(current):
                return False, "Mot de passe actuel incorrect"
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE larcauth_aecuser SET password = %s WHERE LOWER(email) = %s",
                    (_sha256_hex(new), email.strip().lower()),
                )
            return True, ""
        except Exception as e:
            log(f"change_password: {e}")
            return False, str(e)

    @classmethod
    def auth_intranet(cls, email: str, password: str) -> Tuple[bool, AuthResult, str]:
        conn = db.server_conn
        if conn is None or db.server_mode != DBMode.INTRANET:
            return False, AuthResult(), "Non connect\xe9 \xe0 l'intranet"

        pass_hash = _sha256_hex(password)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, last_name, first_name, password "
                    "FROM larcauth_aecuser WHERE LOWER(email) = %s",
                    (email.strip().lower(),)
                )
                row = cur.fetchone()
            if row is None:
                return False, AuthResult(), 'Utilisateur introuvable'
            stored_hash = row[4]
            if stored_hash and stored_hash != pass_hash:
                return False, AuthResult(), 'Mot de passe incorrect'

            user_id = row[0]
            full_name = f"{row[3]} {row[2]}".strip()

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT type_director, type_coordonator, type_supervisor, "
                    "type_secretary FROM larcauth_aecuser WHERE id = %s",
                    (user_id,)
                )
                roles = cur.fetchone()
            if roles and any(roles):
                role = _deduce_role(is_adm=bool(roles[0]), is_coord=bool(roles[1]),
                                    is_sup=bool(roles[2]), is_secretary=bool(roles[3]))
            else:
                role = UserRole.PROF

            with conn.cursor() as cur:
                term_id, term_label = _load_active_term(cur)
                cur.execute("SELECT fk_language FROM larcauth_aecuser WHERE id = %s", (user_id,))
                rr = cur.fetchone()
                fk_lang = int(rr[0]) if rr else 2

            return True, AuthResult(
                user_id=user_id, email=email.strip().lower(),
                full_name=full_name, role=role,
                term_id=term_id, term_label=term_label,
                fk_language=fk_lang,
            ), ''
        except Exception as e:
            return False, AuthResult(), str(e)

    @classmethod
    def auth_pin(cls, email: str, pin: str, local_conn=None) -> Tuple[bool, AuthResult, str]:
        if local_conn is None:
            return False, AuthResult(), 'Base locale non disponible'
        pin_hash = _sha256_hex(pin)
        try:
            row = local_conn.execute(
                "SELECT user_id, email, full_name, role, term_id, term_label "
                "FROM session_cache WHERE LOWER(email) = ? AND pin_hash = ?",
                (email.strip().lower(), pin_hash)
            ).fetchone()
            if row is None:
                return False, AuthResult(), 'Email ou PIN incorrect'
            return True, AuthResult(
                user_id=int(row['user_id']),
                email=row['email'],
                full_name=row['full_name'],
                role=UserRole(row['role']),
                term_id=int(row['term_id'] or 0),
                term_label=row['term_label'] or '',
            ), ''
        except Exception as e:
            return False, AuthResult(), str(e)

    @classmethod
    def check_teacher_exists(cls, email: str) -> Tuple[bool, dict]:
        conn = db.server_conn
        if conn is None or db.server_mode not in (DBMode.INTRANET, DBMode.CLOUD):
            return False, {}
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, first_name, last_name, email "
                    "FROM public.larcauth_aecuser WHERE email = %s",
                    (email,)
                )
                user_row = cur.fetchone()
                if user_row is None:
                    return False, {}
                user_id = user_row[0]
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM public.larcauth_teachadm WHERE aecuser_ptr_id = %s",
                    (user_id,)
                )
                if cur.fetchone() is None:
                    return False, {}
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ay.label, ay.current_term_number, tm.label
                    FROM public.larcauth_academicyear ay
                    JOIN public.larcauth_term tm ON tm.trim = ay.current_term_number
                    WHERE ay.current_term_number IS NOT NULL
                    ORDER BY ay.start_date DESC LIMIT 1
                """)
                year_row = cur.fetchone()
                if year_row is None:
                    return False, {}
            return True, {
                'user_id': user_id,
                'first_name': user_row[1],
                'last_name': user_row[2],
                'email': user_row[3],
                'annee_scolaire': year_row[0],
                'trimestre_courant': year_row[1],
                'trimestre_label': year_row[2],
            }
        except Exception as e:
            log(f"AuthManager.check_teacher_exists: {e}")
            return False, {}


# ---------------------------------------------------------------------------
# OAuth2 PKCE — Google Workspace @arc-en-ciel.org
# ---------------------------------------------------------------------------

class _CallbackHandler(BaseHTTPRequestHandler):
    code:  str             = ''
    event: threading.Event = threading.Event()

    def do_GET(self) -> None:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if 'code' in qs:
            _CallbackHandler.code = qs['code'][0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(
            (f'<html><body style="font-family:sans-serif;text-align:center;padding:{ds.space_xl - ds.space_sm}px">'
             '<h2>✔ Authentification réussie</h2>'
             '<p>Vous pouvez fermer cet onglet et revenir à {0}.</p>'
             '</body></html>').format(OAuth2Manager.APP_DISPLAY).encode('utf-8')
        )
        _CallbackHandler.event.set()

    def log_message(self, *args) -> None:
        pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


class OAuth2Manager:
    PORT           = 8765
    HOSTED_DOMAIN  = 'arc-en-ciel.org'
    APP_DISPLAY    = 'LarcSuperviseur'
    REDIRECT       = f'http://localhost:{PORT}/callback'
    GOOGLE_AUTH    = 'https://accounts.google.com/o/oauth2/v2/auth'
    GOOGLE_TOKEN   = 'https://oauth2.googleapis.com/token'

    @classmethod
    def authenticate(cls) -> Tuple[bool, AuthResult, str]:
        cfg = configparser.ConfigParser()
        cfg.read(find_cfg())
        client_id     = cfg.get('OAuth2', 'ClientID',     fallback='')
        client_secret = cfg.get('OAuth2', 'ClientSecret', fallback='')
        if not client_id:
            return False, AuthResult(), 'ClientID OAuth2 manquant dans config.ini'

        verifier  = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode('ascii')).digest())
        state     = _b64url(secrets.token_bytes(16))

        params = {
            'client_id':             client_id,
            'redirect_uri':          cls.REDIRECT,
            'response_type':         'code',
            'scope':                 'openid email profile',
            'code_challenge':        challenge,
            'code_challenge_method': 'S256',
            'state':                 state,
            'hd':                    cls.HOSTED_DOMAIN,
            'access_type':           'offline',
            'prompt':                'select_account',
        }
        auth_url = cls.GOOGLE_AUTH + '?' + urllib.parse.urlencode(params)

        _CallbackHandler.code = ''
        _CallbackHandler.event.clear()

        srv = HTTPServer(('localhost', cls.PORT), _CallbackHandler)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        webbrowser.open(auth_url)

        if not _CallbackHandler.event.wait(timeout=120):
            srv.server_close()
            return False, AuthResult(), 'Délai de 2 min dépassé'

        srv.server_close()
        code = _CallbackHandler.code
        if not code:
            return False, AuthResult(), 'Code OAuth2 non reçu'

        token_body = urllib.parse.urlencode({
            'code':          code,
            'client_id':     client_id,
            'client_secret': client_secret,
            'redirect_uri':  cls.REDIRECT,
            'grant_type':    'authorization_code',
            'code_verifier': verifier,
        }).encode()
        try:
            req = urllib.request.Request(
                cls.GOOGLE_TOKEN, data=token_body, method='POST',
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                tokens = json.loads(resp.read())
        except Exception as e:
            return False, AuthResult(), f'Échange de token échoué : {e}'

        id_token = tokens.get('id_token', '')
        if not id_token:
            return False, AuthResult(), 'Token ID absent de la réponse'

        parts = id_token.split('.')
        if len(parts) < 2:
            return False, AuthResult(), 'Token ID malformé'
        pad     = '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))

        email = payload.get('email', '')
        hd    = payload.get('hd', '')
        if hd != cls.HOSTED_DOMAIN:
            return False, AuthResult(), f'Domaine non autorisé : {hd or "(aucun)"}'

        conn = db.server_conn
        if conn is None:
            return True, AuthResult(email=email, full_name=payload.get('name', '')), ''

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, first_name, last_name, "
                    "type_director, type_coordonator, type_supervisor "
                    "FROM public.larcauth_aecuser WHERE LOWER(email) = %s",
                    (email.lower(),)
                )
                row = cur.fetchone()
            if row is None:
                return False, AuthResult(), f'Utilisateur {email} non trouvé'

            user_id, first_name, last_name = row[0], row[1], row[2]
            is_dir, is_coord, is_sup = row[3], row[4], row[5]
            full_name = f"{first_name} {last_name}".strip()

            if not (is_dir or is_coord or is_sup):
                return False, AuthResult(), (
                    'Accès réservé aux superviseurs, coordinateurs et administrateurs.')

            role = _deduce_role_superviseur(is_dir, is_coord, is_sup)

            with conn.cursor() as cur:
                term_id, term_label = _load_active_term(cur)
                cur.execute("SELECT fk_language FROM larcauth_aecuser WHERE id = %s", (user_id,))
                rr = cur.fetchone()
                fk_lang = int(rr[0]) if rr else 2

            return True, AuthResult(
                user_id=user_id, email=email, full_name=full_name,
                role=role, term_id=term_id, term_label=term_label,
                fk_language=fk_lang,
            ), ''
        except Exception as e:
            return False, AuthResult(), str(e)

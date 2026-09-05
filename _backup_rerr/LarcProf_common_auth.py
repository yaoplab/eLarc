"""Auth — eLarcProfPy layer over larccommon.auth."""
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

from common.session import AuthResult, UserRole
from common.database import db, DBMode
from larccommon.auth import AuthManager, _deduce_role, _load_active_term, _sha256_hex
from larccommon.config_loader import find_cfg
from larccommon.design_system import ds


# ---------------------------------------------------------------------------
# OAuth2 PKCE — Google Workspace @arc-en-ciel.org (version eLarcProfPy)
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
            f'<html><body style="font-family:sans-serif;text-align:center;padding:{ds.space_xl - ds.space_sm}px">'
            '<h2>✔ Authentification réussie</h2>'
            '<p>Vous pouvez fermer cet onglet et revenir à eLarcProf.</p>'
            '</body></html>'.encode('utf-8')
        )
        _CallbackHandler.event.set()

    def log_message(self, *args) -> None:
        pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


class OAuth2Manager:
    PORT         = 8765
    REDIRECT     = f'http://localhost:{PORT}/callback'
    GOOGLE_AUTH  = 'https://accounts.google.com/o/oauth2/v2/auth'
    GOOGLE_TOKEN = 'https://oauth2.googleapis.com/token'

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
            'hd':                    'arc-en-ciel.org',
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
        if hd != 'arc-en-ciel.org':
            return False, AuthResult(), f'Domaine non autorisé : {hd or "(aucun)"}'

        # Instance binding : vérifier que l'email correspond au professeur de cette instance
        try:
            _local_conn = db.local_conn
            if _local_conn is None:
                return False, AuthResult(), (
                    "Aucune base locale. Créez d'abord une instance "
                    "via l'onglet \"Nouvelle instance\" ou le mode 4.")
            _cur = _local_conn.cursor()
            _cur.execute("SELECT email_professeur FROM module_config WHERE id = 1")
            _row = _cur.fetchone()
            if not _row or not _row[0]:
                return False, AuthResult(), (
                    "Module non instancié. Créez d'abord une instance "
                    "via l'onglet \"Nouvelle instance\" ou le mode 4.")
            if _row[0].lower() != email.lower():
                return False, AuthResult(), (
                    f'Cette instance est liée à {_row[0]}. '
                    f'Connectez-vous avec ce compte ou créez votre propre instance.')
        except Exception as e:
            return False, AuthResult(), f'Erreur de lecture du module : {e}'

        conn = db.server_conn
        if conn is None:
            return True, AuthResult(email=email, full_name=payload.get('name', '')), ''

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, first_name, last_name FROM public.larcauth_aecuser "
                    "WHERE LOWER(email) = %s",
                    (email.lower(),)
                )
                row = cur.fetchone()
            if row is None:
                return False, AuthResult(), f'Utilisateur {email} non trouvé'

            user_id   = row[0]
            full_name = f"{row[1]} {row[2]}".strip()

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT type_director, type_coordonator, type_supervisor, "
                    "type_secretary FROM larcauth_aecuser WHERE id = %s",
                    (user_id,)
                )
                roles = cur.fetchone()
            if roles is None or not any(roles):
                return False, AuthResult(), 'Aucun rôle trouvé'

            role = _deduce_role(is_adm=bool(roles[0]), is_coord=bool(roles[1]),
                                is_sup=bool(roles[2]), is_secretary=bool(roles[3]))
            with conn.cursor() as cur:
                term_id, term_label = _load_active_term(cur)

            return True, AuthResult(
                user_id=user_id, email=email, full_name=full_name,
                role=role, term_id=term_id, term_label=term_label,
            ), ''
        except Exception as e:
            return False, AuthResult(), str(e)

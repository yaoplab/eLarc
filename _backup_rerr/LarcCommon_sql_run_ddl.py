"""Runner DDL central LARC — exécute les fichiers .sql de LarcCommon/sql/.

Usage :
    python LarcCommon/sql/run_ddl.py [--cloud] [fichier.sql ...]

Sans argument : tous les *.sql du dossier dans l'ordre (01, 02, 03...).
--cloud : connexion Supabase au lieu de l'Intranet (objets identiques).
Découpe les instructions en respectant les blocs $$ (fonctions PL/pgSQL).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from larccommon.database import db  # noqa: E402


def split_statements(sql: str) -> list[str]:
    """Découpe sur ';' hors blocs $$ ... $$ et hors commentaires '--'.

    Les PL/pgSQL contiennent des ';' internes (blocs $$) et les commentaires
    d'en-tête peuvent en contenir aussi — les deux sont respectés. Les
    morceaux composés uniquement de commentaires/espaces sont ignorés.
    """
    stmts: list[str] = []
    buf: list[str] = []
    in_dollar = False
    i = 0
    n = len(sql)
    while i < n:
        if not in_dollar and sql.startswith('$$', i):
            in_dollar = True
            buf.append('$$')
            i += 2
            continue
        if in_dollar and sql.startswith('$$', i):
            in_dollar = False
            buf.append('$$')
            i += 2
            continue
        if not in_dollar:
            # Commentaire de ligne : avaler jusqu'au '\n'
            if sql.startswith('--', i):
                j = sql.find('\n', i)
                i = n if j == -1 else j + 1
                continue
            if sql[i] == ';':
                stmts.append(''.join(buf).strip())
                buf = []
                i += 1
                continue
        buf.append(sql[i])
        i += 1
    if ''.join(buf).strip():
        stmts.append(''.join(buf).strip())
    return [s for s in stmts if s]


def main() -> int:
    cloud = '--cloud' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]

    ok = db.connect_cloud() if cloud else db.connect_intranet()
    if not ok:
        print(f"ERREUR : connexion {'Cloud' if cloud else 'Intranet'} impossible")
        return 1

    conn = db.server_conn
    cur = conn.cursor()
    ddl_dir = Path(__file__).resolve().parent

    files = [Path(a) for a in args] if args else sorted(ddl_dir.glob('*.sql'))
    total_ok = total_stmts = 0
    for path in files:
        if not path.is_absolute():
            candidate = ddl_dir / path
            if candidate.is_file():
                path = candidate
        if not path.is_file():
            print(f"  INTROUVABLE: {path}")
            continue
        with open(path, encoding='utf-8') as f:
            stmts = split_statements(f.read())
        print(f"== {path.name} ({len(stmts)} instructions)")
        for stmt in stmts:
            try:
                cur.execute(stmt)
                total_ok += 1
                print(f"  OK: {stmt[:70].replace(chr(10), ' ')}")
            except Exception as e:
                print(f"  SKIP: {str(e)[:120]}")
        total_stmts += len(stmts)

    print(f"\n{total_ok}/{total_stmts} instructions exécutées")
    db.disconnect_all()
    return 0


if __name__ == '__main__':
    sys.exit(main())

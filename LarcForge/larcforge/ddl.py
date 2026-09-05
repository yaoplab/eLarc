"""Exécution de DDL : découpage SQL + application (algorithme de LarcCommon/sql/run_ddl.py)."""

from __future__ import annotations


def split_statements(sql: str) -> list[str]:
    """Découpe sur ';' hors blocs $$ ... $$ et hors commentaires '--'."""
    stmts: list[str] = []
    buf: list[str] = []
    in_dollar = False
    i = 0
    n = len(sql)
    while i < n:
        if not in_dollar and sql.startswith("$$", i):
            in_dollar = True
            buf.append("$$")
            i += 2
            continue
        if in_dollar and sql.startswith("$$", i):
            in_dollar = False
            buf.append("$$")
            i += 2
            continue
        if not in_dollar:
            if sql.startswith("--", i):
                j = sql.find("\n", i)
                i = n if j == -1 else j + 1
                continue
            if sql[i] == ";":
                stmts.append("".join(buf).strip())
                buf = []
                i += 1
                continue
        buf.append(sql[i])
        i += 1
    if "".join(buf).strip():
        stmts.append("".join(buf).strip())
    return [s for s in stmts if s]


def apply_sql(conn, sql_text: str) -> tuple[list[str], list[str]]:
    """Applique les instructions. Retourne (ok, skips) avec un extrait de chaque."""
    ok: list[str] = []
    skips: list[str] = []
    with conn.cursor() as cur:
        for stmt in split_statements(sql_text):
            try:
                cur.execute(stmt)
                ok.append(stmt.replace("\n", " ")[:70])
            except Exception as exc:  # noqa: BLE001
                skips.append(f"{stmt.replace(chr(10), ' ')[:40]} : {exc}")
    return ok, skips

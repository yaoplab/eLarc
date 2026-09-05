"""
Synchronisation device ↔ serveur via le pattern shadow-table (`_ref`).

Voir CONTEXT.md (section "Architecture de synchronisation") pour la philosophie.

Pattern :
- Chaque table métier a une jumelle `<table>_ref` au schéma identique.
- `<table>`     : état local courant (modifié par le prof).
- `<table>_ref` : snapshot du dernier état serveur connu (à la dernière synchro réussie).

Diff au niveau cellule, lignes joinées par `id`.
Matrice de décision par cellule (local vs ref / serveur vs ref) :
    =/= : no-op
    =/≠ : pull  (local = serveur, ref = serveur)
    ≠/= : push  (serveur = local, ref = local)
    ≠/≠ : conflit → IHM de résolution

Scope : `WHERE term_id = module_config.trimestre_courant` uniquement.
Les trimestres passés sont figés et ignorés par le diff.

Implémentation complète (31 mai 2026).
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Dict, Any, Tuple

from .database import db, DBMode
from .logger import log as _log
from .sqlite_init import BUSINESS_TABLES


class CellAction(Enum):
    """Action déduite de la matrice de décision pour une cellule."""
    NOOP = 'noop'
    PULL = 'pull'
    PUSH = 'push'
    CONFLICT = 'conflict'


@dataclass
class CellDiff:
    """Une cellule en divergence entre local/ref/serveur."""
    table: str
    row_id: int
    column: str
    local_value: Any
    ref_value: Any
    server_value: Any
    action: CellAction


@dataclass
class SyncReport:
    """Résultat d'une passe de synchro."""
    pulled: int = 0
    pushed: int = 0
    conflicts: list = field(default_factory=list)   # list[CellDiff]
    errors: list = field(default_factory=list)       # list[str]

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        parts = []
        if self.pulled:
            parts.append(f"{self.pulled} pull(s)")
        if self.pushed:
            parts.append(f"{self.pushed} push(es)")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflit(s)")
        if self.errors:
            parts.append(f"{len(self.errors)} erreur(s)")
        return " | ".join(parts) if parts else "Rien à synchroniser"


class SyncManager:
    """
    Orchestrateur de la synchro device ↔ serveur.

    Toutes les méthodes opèrent sur le `trimestre_courant` lu dans
    `module_config`. Les trimestres passés sont hors scope.
    """

    # Colonnes à ignorer lors du diff (métadonnées sync, timestamps)
    _IGNORE_COLS = frozenset({
        'id', 'sync_version', 'synced_at', 'synced_by',
        'last_modified_at', 'sync_revision',
        'note_on_7_checked',  # colonne locale (validation /7) — jamais synchronisée
    })

    def __init__(self) -> None:
        self._current_term: Optional[int] = None

    # ------------------------------------------------------------------
    # Garde-fous
    # ------------------------------------------------------------------
    def _ensure_current_term(self) -> int:
        """Lit `trimestre_courant` depuis `module_config`. Erreurs si absent."""
        conn = db.local_conn
        if conn is None:
            raise RuntimeError("Aucune connexion SQLite locale disponible")
        row = conn.execute(
            "SELECT trimestre_courant FROM module_config WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("module_config manquant — le module n'est pas instancié")
        term = int(row[0])
        if term <= 0:
            raise RuntimeError(f"trimestre_courant invalide : {term}")
        self._current_term = term
        _log(f"SyncManager: trimestre courant = {term}")
        return term

    def _ensure_server_connected(self) -> None:
        """Vérifie qu'une connexion serveur est active (intranet ou cloud)."""
        if db.server_conn is None:
            raise RuntimeError("Aucune connexion serveur active (intranet ou cloud requis)")

    # ------------------------------------------------------------------
    # Récupération des colonnes métier (hors ignore)
    # ------------------------------------------------------------------
    def _get_cols(self, table: str, conn) -> List[str]:
        """Retourne la liste des colonnes métier d'une table (sans les _IGNORE)."""
        if hasattr(conn, 'cursor'):
            # PostgreSQL ou SQLite avec cursor
            try:
                cur = conn.cursor()
                if hasattr(cur, 'description') or True:
                    cur.execute(f'SELECT * FROM "{table}" LIMIT 0')
                    cols = [desc[0] for desc in cur.description]
                    return [c for c in cols if c.lower() not in self._IGNORE_COLS]
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
        # Fallback SQLite
        try:
            cur = conn.cursor()
            cur.execute(f'PRAGMA table_info("{table}")')
            cols = [r[1] for r in cur.fetchall()]
            return [c for c in cols if c.lower() not in self._IGNORE_COLS]
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return []

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------
    def pull_push(self) -> SyncReport:
        """
        Synchronise les 3 tables métiers pour le trimestre courant.
        Lit `trimestre_courant` dans `module_config`, applique la matrice
        de décision cellule par cellule, met à jour `sync_state` à la fin.
        """
        report = SyncReport()

        try:
            term = self._ensure_current_term()
            self._ensure_server_connected()
        except RuntimeError as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            report.errors.append(str(e))
            _log(f"SyncManager.pull_push: échec garde-fou — {e}")
            return report

        _log("SyncManager.pull_push: démarrage de la synchro")

        import time
        for table in BUSINESS_TABLES:
            try:
                t0 = time.time()
                diffs = list(self.compute_cell_diff(table))
                dt = time.time() - t0
                print(f'[SYNC] {table}: {len(diffs)} diffs in {dt:.1f}s')
                _log(f"SyncManager: {table} — {len(diffs)} diffs, computing took {dt:.1f}s")
                if not diffs:
                    _log(f"SyncManager: {table} — aucune divergence")
                    continue

                pulls = 0
                pushes = 0
                conflicts = []

                for diff in diffs:
                    if diff.action == CellAction.PULL:
                        self.apply_pull(diff)
                        pulls += 1
                    elif diff.action == CellAction.PUSH:
                        self.apply_push(diff)
                        pushes += 1
                    elif diff.action == CellAction.CONFLICT:
                        conflicts.append(diff)

                report.pulled += pulls
                report.pushed += pushes
                report.conflicts.extend(conflicts)

                local_conn.commit()

                # Mettre à jour sync_state si pas de conflits
                if not conflicts:
                    self.touch_sync_state(table)
                    _log(f"SyncManager: {table} — {pulls} pull(s), {pushes} push(es), sync_state mis à jour")
                else:
                    _log(f"SyncManager: {table} — {len(conflicts)} conflit(s), sync_state non mis à jour")

            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                msg = f"Erreur sur {table}: {e}"
                report.errors.append(msg)
                _log(f"SyncManager.pull_push: {msg}")

        _log(f"SyncManager.pull_push: terminé — {report.summary()}")
        return report

    # ------------------------------------------------------------------
    # Diff cellule par cellule
    # ------------------------------------------------------------------
    def compute_cell_diff(self, table: str) -> Iterable[CellDiff]:
        """
        Calcule la liste des cellules en divergence pour une table donnée.
        Joint local + `<table>_ref` + serveur sur `id`, filtre par
        `term_id = trimestre_courant`, ne retourne que les cellules
        dont l'action n'est pas NOOP.
        """
        local_conn = db.local_conn
        if local_conn is None:
            return

        ref_table = f"{table}_ref"
        cols = self._get_cols(table, local_conn)
        if not cols:
            _log(f"SyncManager.compute_cell_diff: aucune colonne pour {table}")
            return

        # 1. Lire local et ref depuis SQLite
        local_rows: Dict[int, Dict[str, Any]] = {}
        ref_rows: Dict[int, Dict[str, Any]] = {}

        try:
            for row in local_conn.execute(f'SELECT * FROM "{table}"'):
                row_dict = dict(row)
                # Normaliser la clé en str : SQLite (TEXT) et serveur (BIGINT)
                # renvoient des types différents ; sinon chaque id apparaît en
                # double dans all_ids et les diffs s'écrasent mutuellement.
                local_rows[str(row_dict['id'])] = row_dict
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager: erreur lecture local {table}: {e}")
            return

        try:
            for row in local_conn.execute(f'SELECT * FROM "{ref_table}"'):
                row_dict = dict(row)
                ref_rows[str(row_dict['id'])] = row_dict
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager: erreur lecture ref {ref_table}: {e}")
            return

        # 2. Lire serveur via PostgreSQL
        server_rows: Dict[int, Dict[str, Any]] = {}
        try:
            server_conn = db.server_conn
            if server_conn is not None:
                with server_conn.cursor() as cur:
                    # Pour evaluation : filtrer via fk_classroom_termsubject →
                    # trimestre courant ET professeur connecté (même filtre que
                    # take_teacher_data, sinon on rapatrierait les évaluations
                    # de toute l'école)
                    if table == 'larcauth_evaluation':
                        from common.session import session
                        cur.execute(f"""
                            SELECT e.* FROM public."{table}" e
                            JOIN public.larcauth_classroom_termsubject cts
                                ON cts.id = e.fk_classroom_termsubject_id
                            JOIN public.larcauth_classroom c ON c.id = cts.fk_classroom_id
                            WHERE cts.fk_term_id = %s
                              AND cts.fk_teacher_id = %s
                              AND cts.enabled = true
                              AND c.enabled = true
                        """, (self._current_term, session.user_id))
                    else:
                        # PEI/DP : scope par professeur + trimestre via
                        # learner_has_termsubject (même filtre que le seed)
                        cur.execute(f"""
                            SELECT e.*, lht.fk_student_id
                            FROM public."{table}" e
                            JOIN public.larcauth_learner_has_termsubject lht
                                ON lht.id = e.learner_has_termsubject_ptr_id
                            JOIN public.larcauth_classroom_termsubject cts
                                ON cts.id = lht.fk_classroom_termsubject_id
                            JOIN public.larcauth_classroom c ON c.id = cts.fk_classroom_id
                            WHERE cts.fk_term_id = %s
                              AND cts.fk_teacher_id = %s
                              AND cts.enabled = true
                              AND c.enabled = true
                        """, (self._current_term, session.user_id))

                    server_cols = [desc[0] for desc in cur.description]
                    for row in cur.fetchall():
                        row_dict = dict(zip(server_cols, row))
                        server_rows[str(row_dict['id'])] = row_dict
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager: erreur lecture serveur {table}: {e}")
            # Continuer avec ce qu'on a (pull impossible mais push possible)

        # 3. Comparer cellule par cellule
        all_ids = set(local_rows.keys()) | set(ref_rows.keys()) | set(server_rows.keys())

        for row_id in all_ids:
            local_row = local_rows.get(row_id)
            ref_row = ref_rows.get(row_id)
            server_row = server_rows.get(row_id)

            for col in cols:
                local_val = _normalize(local_row.get(col) if local_row else None)
                ref_val = _normalize(ref_row.get(col) if ref_row else None)
                server_val = _normalize(server_row.get(col) if server_row else None)

                action = _decide(local_val, ref_val, server_val)
                if action == CellAction.NOOP:
                    continue

                yield CellDiff(
                    table=table,
                    row_id=row_id,
                    column=col,
                    local_value=local_val,
                    ref_value=ref_val,
                    server_value=server_val,
                    action=action,
                )

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def apply_pull(self, diff: CellDiff) -> None:
        """Applique un pull : `local = serveur`, `ref = serveur`."""
        local_conn = db.local_conn
        server_conn = db.server_conn
        if local_conn is None:
            return

        col = diff.column
        val = diff.server_value
        row_id = diff.row_id
        table = diff.table
        ref_table = f"{table}_ref"

        # Ligne absente en local (id présent côté serveur seulement) :
        # la créer d'abord (local + ref) à partir des données serveur.
        # Sans cela, l'UPDATE ci-dessous ne touche aucune ligne et la
        # ligne reste à jamais absente en local.
        try:
            exists = local_conn.execute(
                f'SELECT 1 FROM "{table}" WHERE id = ?', (row_id,)
            ).fetchone()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager.apply_pull: erreur SELECT {table}[{row_id}]: {e}")
            raise
        if exists is None:
            if server_conn is None:
                _log(f"SyncManager.apply_pull: ligne {table}[{row_id}] absente "
                     f"en local et pas de serveur — pull impossible")
                return
            try:
                with server_conn.cursor() as cur:
                    cur.execute(f'SELECT * FROM public."{table}" WHERE id = %s', (row_id,))
                    srow = cur.fetchone()
                    scol = [d[0] for d in cur.description]
                if srow is None:
                    _log(f"SyncManager.apply_pull: {table}[{row_id}] introuvable côté serveur")
                    return
                pairs = ", ".join(f'"{c}"' for c in scol)
                marks = ", ".join("?" for _i in scol)
                values = [_to_sqlite(v) for v in srow]
                local_conn.execute(f'INSERT INTO "{table}" ({pairs}) VALUES ({marks})', values)
                local_conn.execute(f'INSERT INTO "{ref_table}" ({pairs}) VALUES ({marks})', values)
                _log(f"SyncManager.apply_pull: {table}[{row_id}] créée en local (rapatriement serveur)")
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                _log(f"SyncManager.apply_pull: erreur INSERT {table}[{row_id}]: {e}")
                raise

        try:
            local_conn.execute(
                f'UPDATE "{table}" SET "{col}" = ? WHERE id = ?',
                (_to_sqlite(val), row_id)
            )
            local_conn.execute(
                f'UPDATE "{ref_table}" SET "{col}" = ? WHERE id = ?',
                (_to_sqlite(val), row_id)
            )
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager.apply_pull: erreur {table}.{col}[{row_id}]: {e}")
            raise

    def apply_push(self, diff: CellDiff) -> None:
        """Applique un push : `serveur = local`, `ref = local`."""
        local_conn = db.local_conn
        server_conn = db.server_conn
        if local_conn is None or server_conn is None:
            return

        col = diff.column
        val = diff.local_value
        row_id = diff.row_id
        table = diff.table
        ref_table = f"{table}_ref"

        try:
            # Poser le contexte d'audit au niveau SESSION (set_config, false) —
            # SET LOCAL serait un no-op sous autocommit.
            with server_conn.cursor() as cur:
                from larccommon.audit_context import attach, refresh
                refresh()
                attach(server_conn)
                cur.execute(
                    f'UPDATE public."{table}" SET "{col}" = %s WHERE id = %s',
                    (val, row_id)
                )

            # Mettre à jour ref local
            local_conn.execute(
                f'UPDATE "{ref_table}" SET "{col}" = ? WHERE id = ?',
                (_to_sqlite(val), row_id)
            )
            local_conn.commit()
            _log(f"SyncManager.apply_push: {table}.{col}[{row_id}] = {val}")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager.apply_push: erreur {table}.{col}[{row_id}]: {e}")
            raise

    def apply_resolution(self, diff: CellDiff, keep: str) -> None:
        """
        Applique la résolution choisie par le prof sur un conflit.
        `keep` ∈ {'local', 'server'}. Met à jour la cellule des 3 côtés
        (local, ref, serveur) avec la valeur retenue.
        """
        if keep not in ('local', 'server'):
            raise ValueError(f"keep doit être 'local' ou 'server', pas '{keep}'")

        val = diff.local_value if keep == 'local' else diff.server_value
        local_conn = db.local_conn
        server_conn = db.server_conn

        if local_conn is None:
            raise RuntimeError("Aucune connexion SQLite locale")

        table = diff.table
        ref_table = f"{table}_ref"
        col = diff.column
        row_id = diff.row_id

        try:
            # UPDATE local
            local_conn.execute(
                f'UPDATE "{table}" SET "{col}" = ? WHERE id = ?',
                (_to_sqlite(val), row_id)
            )
            # UPDATE ref
            local_conn.execute(
                f'UPDATE "{ref_table}" SET "{col}" = ? WHERE id = ?',
                (_to_sqlite(val), row_id)
            )
            local_conn.commit()

            # UPDATE serveur si dispo
            if server_conn is not None and keep == 'local':
                with server_conn.cursor() as cur:
                    source = 'intranet' if db.server_mode == DBMode.INTRANET else 'cloud'
                    cur.execute(f"SET LOCAL app.sync_source = '{source}'")
                    from common.session import session
                    cur.execute(f"SET LOCAL app.modified_by = {int(session.user_id or 0)}")
                    cur.execute(
                        f'UPDATE public."{table}" SET "{col}" = %s WHERE id = %s',
                        (val, row_id)
                    )

            _log(f"SyncManager.apply_resolution: {table}.{col}[{row_id}] = {val} (gardé {keep})")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager.apply_resolution: erreur: {e}")
            raise

    def touch_sync_state(self, table: str) -> None:
        """Met à jour `sync_state.last_sync` pour la table à `now()`."""
        local_conn = db.local_conn
        if local_conn is None:
            return
        source = 'intranet' if db.server_mode == DBMode.INTRANET else 'cloud' if db.server_mode == DBMode.CLOUD else 'unknown'
        try:
            local_conn.execute(
                """INSERT INTO sync_state (table_name, last_sync, last_source)
                   VALUES (?, datetime('now'), ?)
                   ON CONFLICT(table_name) DO UPDATE SET
                       last_sync   = excluded.last_sync,
                       last_source = excluded.last_source""",
                (table, source)
            )
            local_conn.commit()
            _log(f"SyncManager.touch_sync_state: {table} mis à jour")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"SyncManager.touch_sync_state: erreur pour {table}: {e}")


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def _normalize(val: Any) -> Any:
    """Normalise les valeurs pour comparaison (None, str, number)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip()
    if s == '' or s.lower() in ('null', 'none'):
        return None
    return s


def _to_sqlite(val: Any) -> Any:
    """Convertit une valeur pour insertion SQLite."""
    if val is None:
        return None
    return str(val)


def _decide(local: Any, ref: Any, server: Any) -> CellAction:
    """
    Matrice de décision par cellule.
    local vs ref | server vs ref | Action
    ==============|===============|========
    =             | =             | NOOP
    =             | ≠             | PULL
    ≠             | =             | PUSH
    ≠             | ≠             | CONFLICT
    """
    local_changed = (local != ref)
    server_changed = (server != ref)

    if not local_changed and not server_changed:
        return CellAction.NOOP
    if not local_changed and server_changed:
        return CellAction.PULL
    if local_changed and not server_changed:
        return CellAction.PUSH
    return CellAction.CONFLICT


# Singleton global, à l'image de `db` et `sqlite_init`.
sync = SyncManager()

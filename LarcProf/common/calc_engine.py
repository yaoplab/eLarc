"""Moteur de calcul des notes PEI (sur 7) et DP (sur 20).

Lit le JSON calc_formula depuis larcauth_classroom_termsubject et applique
la formule pour calculer la note finale d'un eleve.

PEI : moyenne ponderée par critère (F×wf + S×ws) → somme des critères
      → conversion en note/7 (boundaries ou linéaire)
DP  : EI × coeff_ei + moy(F/20) × coeff_f + moy(S/20) × coeff_s
"""
import json
from typing import Optional

from .database import db
from .session import session


# ── Defaults ──────────────────────────────────────────────────

_DEFAULT_PEI = {
    "type": "PEI",
    "criteria": ["A", "B", "C", "D"],
    "formative_weight": 0.4,
    "summative_weight": 0.6,
    # Regle explicite (documentee pour tout logiciel tiers) : si un seul
    # type (F ou S) a des notes, il compte seul a 100 %.
    "solo_rule": "if_only_one_type",
    "conversion": {
        "method": "boundaries",
        "boundaries": [
            {"min": 0,  "max": 5,  "note": 1},
            {"min": 6,  "max": 9,  "note": 2},
            {"min": 10, "max": 14, "note": 3},
            {"min": 15, "max": 18, "note": 4},
            {"min": 19, "max": 23, "note": 5},
            {"min": 24, "max": 27, "note": 6},
            {"min": 28, "max": 32, "note": 7},
        ],
    },
}

_DEFAULT_DP = {
    "type": "DP",
    "criteria": [],
    "conversion": {
        "method": "formula",
        "ei_coefficient": 0.125,
        "formative_coefficient": 1.125,
        "summative_coefficient": 0.75,
    },
}

_TEMPLATES_PEI = {
    "4c": {"criteria": ["A", "B", "C", "D"]},
    "3c": {"criteria": ["A", "C", "D"]},
    "2c": {"criteria": ["A", "D"]},
    "1c": {"criteria": ["A"]},
}


def _recalc_boundaries(criteria_count: int) -> list[dict]:
    """Recalcule les bandes IB proportionnellement au nombre de critères."""
    max_total = criteria_count * 8
    boundaries = []
    for note in range(1, 8):
        # Distribution proportionnelle des seuils
        pct_low = (note - 1) / 7
        pct_high = note / 7
        boundaries.append({
            "min": round(pct_low * max_total),
            "max": round(pct_high * max_total) - 1 if note < 7 else max_total,
            "note": note,
        })
    # Ajuster le dernier max
    boundaries[-1]["max"] = max_total
    return boundaries


class CalcEngine:
    """Calcule la note finale d'un eleve pour un termsubject donne."""

    @classmethod
    def get_formula(cls, termsubject_id: int) -> dict:
        """Lit le JSON calc_formula. NULL → retourne le défaut selon le cycle."""
        conn = db.local_conn
        if conn is None:
            return _DEFAULT_PEI
        row = conn.execute(
            "SELECT calc_formula FROM larcauth_classroom_termsubject WHERE id = ?",
            (str(termsubject_id),)
        ).fetchone()
        if row and row[0]:
            formula = json.loads(row[0])
            # Interop : toute formule PEI expose la regle solo, meme si la cle
            # manque dans une vieille formule (lecture tiers toujours conforme).
            if formula.get("type") == "PEI":
                formula.setdefault("solo_rule", "if_only_one_type")
            return formula
        # Detecter le cycle via la table level → program
        prog_row = conn.execute("""
            SELECT p.sigle FROM larcauth_classroom_termsubject cts
            JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE cts.id = ?
        """, (str(termsubject_id),)).fetchone()
        sigle = (prog_row[0] or '').upper() if prog_row else 'PEI'
        if sigle in ('DP', 'DPFR', 'DPEN', 'IBDP', 'DIPLOMA'):
            return dict(_DEFAULT_DP)
        return dict(_DEFAULT_PEI)

    @classmethod
    def save_formula(cls, termsubject_id: int, formula: dict) -> bool:
        """Enregistre le JSON dans calc_formula."""
        conn = db.local_conn
        if conn is None:
            return False
        json_str = json.dumps(formula, ensure_ascii=False)
        conn.execute(
            "UPDATE larcauth_classroom_termsubject SET calc_formula = ? WHERE id = ?",
            (json_str, str(termsubject_id)),
        )
        conn.commit()
        return True

    @classmethod
    def compute_note(cls, student_id: int, termsubject_id: int,
                     active_crits: list | None = None,
                     override: dict[str, str] | None = None) -> Optional[float]:
        """Calcule la note finale d'un eleve.

        active_crits : criteres effectifs (ex. criteres non deselectonnes
        dans le top bar). La note/7 s'adapte au nombre de criteres
        restants : si 3 criteres restent, le mode de calcul (bandes IB ou
        linear) est proportionne a 3, si 2 a 2, etc.

        override : cellules de notes en cours de saisie (non encore
        enregistrees) — {nom_colonne: valeur str} — qui remplacent la base.

        Retourne la note (float) ou None si pas assez de donnees.
        """
        formula = cls.get_formula(termsubject_id)
        if formula["type"] == "DP":
            return cls._compute_dp(student_id, termsubject_id, formula)
        return cls._compute_pei(student_id, termsubject_id, formula, active_crits, override)

    # ── PEI ────────────────────────────────────────────────────

    @classmethod
    def _compute_pei(cls, student_id: int, termsubject_id: int, formula: dict,
                     active_crits: list | None = None,
                     override: dict[str, str] | None = None) -> Optional[float]:
        full_criteria = formula.get("criteria", ["A", "B", "C", "D"])
        # Le top bar « Affichage colonnes » fait foi : les criteres actifs
        # (visibles) sont les criteres effectifs du calcul. La formule PEI ne
        # gere plus criteria (dialogue sans templates) — un vestige ['A']
        # restreindrait la note a un seul critere alors que la grille affiche
        # les 4 colonnes notees.
        criteria = list(active_crits) if active_crits else list(full_criteria)
        if not criteria:
            return None
        wf = formula.get("formative_weight", 0.4)
        ws = formula.get("summative_weight", 0.6)
        total_w = wf + ws
        if total_w == 0:
            return None

        conn = db.local_conn
        if conn is None:
            return None

        # Charger les evaluations actives pour ce termsubject
        evals_rows = conn.execute("""
            SELECT type_evaluation, index_eval, crit_a, crit_b, crit_c, crit_d
            FROM larcauth_evaluation
            WHERE fk_classroom_termsubject_id = ? AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
        """, (str(termsubject_id),)).fetchall()

        # Organiser: par critère → [(type, index, actif)]
        evals_by_criterion: dict[str, list[tuple[str, int]]] = {c: [] for c in criteria}
        for r in evals_rows:
            etype = str(r[0]).strip().upper()
            idx = int(r[1])
            for i, crit in enumerate(("A", "B", "C", "D")):
                if crit in criteria and str(r[2 + i]).strip() in ("1", "TRUE", "ON"):
                    evals_by_criterion[crit].append((etype, idx))

        # Trouver le learner row via fk_student_id (colonne directement dans la table PEI locale)
        learner_row = conn.execute(
            'SELECT learner_has_termsubject_ptr_id FROM larcauth_learnerpei_has_termsubjectpei '
            'WHERE fk_student_id = ? LIMIT 1',
            (student_id,)
        ).fetchone()

        if learner_row is None:
            return None
        learner_id = learner_row[0]

        # Moyenne par critère : d'abord par type, puis combinaison pondérée
        criterion_averages = {}
        for crit in criteria:
            f_vals, s_vals = [], []
            for etype, idx in evals_by_criterion[crit]:
                col = f"{etype[0].lower()}{idx:02d}_note_{crit.lower()}"
                row = conn.execute(
                    f'SELECT "{col}" FROM larcauth_learnerpei_has_termsubjectpei '
                    f'WHERE learner_has_termsubject_ptr_id = ?',
                    (learner_id,)
                ).fetchone()
                if override is not None and col in override:
                    # Saisie en cours (non encore enregistree) : la valeur
                    # live remplace celle de la base.
                    raw = override[col]
                    if raw not in (None, ''):
                        (f_vals if etype in ("F", "FORMATIVES") else s_vals).append(float(raw))
                elif row and row[0] is not None:
                    if etype in ("F", "FORMATIVES"):
                        f_vals.append(float(row[0]))
                    else:
                        s_vals.append(float(row[0]))

            f_mean = sum(f_vals) / len(f_vals) if f_vals else None
            s_mean = sum(s_vals) / len(s_vals) if s_vals else None

            # Regle « solo » (solo_rule = "if_only_one_type", documentee dans
            # calc_formula) : si un seul type a des notes, il compte seul.
            if f_mean is not None and s_mean is not None:
                criterion_averages[crit] = f_mean * wf + s_mean * ws
            elif s_mean is not None:
                criterion_averages[crit] = s_mean  # 100 % sommatives
            elif f_mean is not None:
                criterion_averages[crit] = f_mean  # 100 % formatives
            else:
                criterion_averages[crit] = 0.0

        # Somme des critères
        total_sum = sum(criterion_averages.values())
        if total_sum == 0:
            return None

        # Conversion
        conv = formula.get("conversion", {})
        method = conv.get("method", "boundaries")

        if method == "boundaries":
            boundaries = conv.get("boundaries", [])
            if len(criteria) != len(full_criteria):
                # Criteres deselectonnes : les bandes IB de la formule
                # couvrent N×8 points — reproportionner au nombre de
                # criteres effectifs (3 restants → /24, 2 → /16, etc.).
                boundaries = _recalc_boundaries(len(criteria))
            return cls._apply_boundaries(total_sum, boundaries)
        else:
            # linear
            max_total = len(criteria) * 8
            return round((total_sum / max_total) * 7)

    @classmethod
    def _apply_boundaries(cls, total: float, boundaries: list[dict]) -> int:
        """Bandes IB : le resultat est TOUJOURS un entier (jamais de virgule).

        La note rendue est la plus haute bande dont le seuil minimal est
        atteint. On compare au `min` (pas a l'intervalle ferme) : les bandes
        recalcubees par _recalc_boundaries ont des arrondis qui laissent des
        trous entre elles (ex. bande 4 = 14-17, bande 5 = 18-22) ; un total
        de 17,6 retombait dans le fallback (note 1) alors qu'il doit rendre
        la note 4 (seuil 14 atteint, seuil 18 pas encore).
        """
        note = 1
        for b in boundaries:
            if total < b["min"]:
                break
            note = int(b["note"])
        return note

    # ── DP ─────────────────────────────────────────────────────

    @classmethod
    def _compute_dp(cls, student_id: int, termsubject_id: int, formula: dict) -> Optional[float]:
        conn = db.local_conn
        if conn is None:
            return None

        learner_row = conn.execute(
            'SELECT learner_has_termsubject_ptr_id FROM larcauth_learnerdp_has_termsubjectdp '
            'WHERE fk_student_id = ? LIMIT 1',
            (student_id,)
        ).fetchone()

        if learner_row is None:
            return None
        learner_id = learner_row[0]

        conv = formula.get("conversion", {})
        ei_c = conv.get("ei_coefficient", 0.125)
        f_c = conv.get("formative_coefficient", 1.125)
        s_c = conv.get("summative_coefficient", 0.75)

        def _read(col):
            row = conn.execute(
                f'SELECT "{col}" FROM larcauth_learnerdp_has_termsubjectdp '
                f'WHERE learner_has_termsubject_ptr_id = ?', (learner_id,)
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0

        # EI: lire ei_note
        ei_val = _read("ei_note")

        # Formatives sur 20: f01_note..f12_note
        f_vals = []
        for i in range(1, 13):
            v = _read(f"f{i:02d}_note")
            if v > 0:
                f_vals.append(v)
        f_mean = sum(f_vals) / len(f_vals) if f_vals else 0.0

        # Sommatives sur 20: s01_note..s12_note
        s_vals = []
        for i in range(1, 13):
            v = _read(f"s{i:02d}_note")
            if v > 0:
                s_vals.append(v)
        s_mean = sum(s_vals) / len(s_vals) if s_vals else 0.0

        note = ei_val * ei_c + f_mean * f_c + s_mean * s_c
        return round(note, 1)

    # ── Templates ──────────────────────────────────────────────

    @classmethod
    def get_templates_pei(cls) -> dict[str, dict]:
        """Retourne les templates PEI pré-remplis."""
        templates = {}
        for key, cfg in _TEMPLATES_PEI.items():
            crits = cfg["criteria"]
            templates[key] = {
                "type": "PEI",
                "criteria": crits,
                "formative_weight": 0.4,
                "summative_weight": 0.6,
                "solo_rule": "if_only_one_type",
                "conversion": {
                    "method": "boundaries",
                    "boundaries": _recalc_boundaries(len(crits)),
                },
            }
        return templates

    @classmethod
    def get_templates_dp(cls) -> dict[str, dict]:
        """Retourne les templates DP pré-remplis."""
        return {
            "standard": dict(_DEFAULT_DP),
            "simple": {
                "type": "DP",
                "criteria": [],
                "conversion": {
                    "method": "simple_avg",
                },
            },
        }

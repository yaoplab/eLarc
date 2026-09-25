"""Règles pures de choix de matières par élève (PEI et DP).

Aucun Qt, aucun SQL — logique métier testable isolément. Utilisée par la
grille élèves (Onglet B) du futur panneau « Classes & matières ».
"""
from dataclasses import dataclass, field

# Trimestre affiché (1/2/3) -> fk_term_id. Le 4e "trimestre" correspond aux
# vacances : rien à configurer (décision D1 du plan 2026-09-19).
TERM_SLOTS = {1: 1, 2: 2, 3: 3}

# Un groupe de matières (nr_group_in_pgm) accepte 0, 1 ou 2 matières
# activées — jamais plus, en PEI comme en DP.
MAX_SUBJECTS_PER_GROUP = 2

# DP : les groupes 1 à 5 doivent chacun avoir au moins une matière ; le
# groupe 6 (Arts) est optionnel (une 2e matière d'un autre groupe le remplace).
DP_GROUPS_REQUIRED = {1, 2, 3, 4, 5}


@dataclass
class Subject:
    """Une matière activée pour un élève à un trimestre donné."""
    group: int
    niv_sup: bool = False
    label: str = ''


def group_counts(subjects: list[Subject]) -> dict[int, int]:
    """Nombre de matières activées par groupe."""
    counts: dict[int, int] = {}
    for s in subjects:
        counts[s.group] = counts.get(s.group, 0) + 1
    return counts


def group_overflow_violations(subjects: list[Subject]) -> list[int]:
    """Groupes dépassant MAX_SUBJECTS_PER_GROUP (0 ou 1 matière n'est jamais une anomalie)."""
    return sorted(g for g, n in group_counts(subjects).items() if n > MAX_SUBJECTS_PER_GROUP)


@dataclass
class DPStatus:
    total: int
    groups_covered: set = field(default_factory=set)
    ns_count: int = 0
    nm_count: int = 0
    compliant: bool = False


def dp_status(subjects: list[Subject]) -> DPStatus:
    """Statut de conformité DP : voyant vert si 6 matières, groupes 1-5
    couverts et exactement 3 Sup (NS) + 3 niveau moyen (NM)."""
    total = len(subjects)
    groups_covered = {s.group for s in subjects if s.group in DP_GROUPS_REQUIRED}
    ns_count = sum(1 for s in subjects if s.niv_sup)
    nm_count = total - ns_count
    compliant = (
        total == 6
        and DP_GROUPS_REQUIRED.issubset(groups_covered)
        and ns_count == 3
        and nm_count == 3
    )
    return DPStatus(total=total, groups_covered=groups_covered,
                     ns_count=ns_count, nm_count=nm_count, compliant=compliant)


def dp_status_reasons(status: DPStatus) -> list[str]:
    """Motifs de non-conformité DP (liste vide si conforme) — partagés par la
    grille écran et les exports."""
    reasons = []
    if status.total != 6:
        reasons.append(f"{status.total} matière(s) (6 attendues)")
    missing = sorted(DP_GROUPS_REQUIRED - status.groups_covered)
    if missing:
        reasons.append("groupe(s) manquant(s) : " + ", ".join(str(m) for m in missing))
    if status.ns_count != 3 or status.nm_count != 3:
        reasons.append(f"{status.ns_count} NS / {status.nm_count} NM (3/3 attendus)")
    return reasons

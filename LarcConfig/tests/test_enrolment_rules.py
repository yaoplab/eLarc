"""Tests enrolment_rules — règles pures de choix de matières (PEI et DP)."""
from LarcConfig.common.enrolment_rules import (
    DP_GROUPS_REQUIRED,
    MAX_SUBJECTS_PER_GROUP,
    Subject,
    dp_status,
    group_counts,
    group_overflow_violations,
)


class TestGroupCounts:
    def test_counts_subjects_per_group(self):
        subjects = [Subject(group=1), Subject(group=1), Subject(group=3)]
        assert group_counts(subjects) == {1: 2, 3: 1}

    def test_empty_list_gives_empty_counts(self):
        assert group_counts([]) == {}


class TestGroupOverflowViolations:
    def test_no_violation_with_zero_one_or_two_per_group(self):
        # PEI/DP : un groupe peut avoir 0, 1 ou 2 matières — jamais une anomalie.
        subjects = [Subject(group=1), Subject(group=2), Subject(group=2)]
        assert group_overflow_violations(subjects) == []

    def test_flags_group_with_more_than_two_subjects(self):
        subjects = [Subject(group=5), Subject(group=5), Subject(group=5)]
        assert group_overflow_violations(subjects) == [5]


class TestDpStatus:
    def test_real_student_231101_is_compliant(self):
        # Cas réel du plan 2026-09-19 : Français NM(1), Maths NM(2),
        # Économie NS + Gestion NS(3), Biologie NM(4), Anglais NS(5) — pas d'Arts.
        subjects = [
            Subject(group=1, niv_sup=False, label='Français'),
            Subject(group=2, niv_sup=False, label='Maths'),
            Subject(group=3, niv_sup=True, label='Économie'),
            Subject(group=3, niv_sup=True, label='Gestion'),
            Subject(group=4, niv_sup=False, label='Biologie'),
            Subject(group=5, niv_sup=True, label='Anglais'),
        ]
        status = dp_status(subjects)
        assert status.total == 6
        assert status.groups_covered == {1, 2, 3, 4, 5}
        assert status.ns_count == 3
        assert status.nm_count == 3
        assert status.compliant is True

    def test_student_with_arts_and_correct_split_is_compliant(self):
        subjects = [
            Subject(group=1, niv_sup=False),
            Subject(group=2, niv_sup=False),
            Subject(group=3, niv_sup=False),
            Subject(group=4, niv_sup=True),
            Subject(group=5, niv_sup=True),
            Subject(group=6, niv_sup=True, label='Arts'),
        ]
        assert dp_status(subjects).compliant is True

    def test_five_subjects_is_not_compliant(self):
        subjects = [
            Subject(group=1, niv_sup=False),
            Subject(group=2, niv_sup=False),
            Subject(group=3, niv_sup=True),
            Subject(group=4, niv_sup=False),
            Subject(group=5, niv_sup=True),
        ]
        status = dp_status(subjects)
        assert status.total == 5
        assert status.compliant is False

    def test_group_four_uncovered_is_not_compliant(self):
        subjects = [
            Subject(group=1, niv_sup=False),
            Subject(group=2, niv_sup=False),
            Subject(group=3, niv_sup=True),
            Subject(group=3, niv_sup=False),
            Subject(group=5, niv_sup=True),
            Subject(group=6, niv_sup=True),
        ]
        status = dp_status(subjects)
        assert 4 not in status.groups_covered
        assert status.compliant is False

    def test_two_ns_five_nm_is_not_compliant(self):
        # Sous l'ancienne règle (avertissement 3-4 NS) ce cas passait ;
        # la nouvelle règle dure exige exactement 3 NS + 3 NM.
        subjects = [
            Subject(group=1, niv_sup=False),
            Subject(group=2, niv_sup=False),
            Subject(group=3, niv_sup=False),
            Subject(group=4, niv_sup=False),
            Subject(group=5, niv_sup=True),
            Subject(group=6, niv_sup=True),
        ]
        status = dp_status(subjects)
        assert status.ns_count == 2
        assert status.nm_count == 4
        assert status.compliant is False


def test_max_subjects_per_group_constant_is_two():
    assert MAX_SUBJECTS_PER_GROUP == 2


def test_dp_groups_required_is_one_to_five():
    assert DP_GROUPS_REQUIRED == {1, 2, 3, 4, 5}


def test_entry_text_tags():
    from LarcConfig.common.enrolment_rules import entry_text
    assert entry_text("Anglais NS", True, False, True) == "Anglais NS"
    assert entry_text("Français", True, False, True) == "Français (NS)"
    assert entry_text("Sciences", False, True, False) == "Sciences (*)"

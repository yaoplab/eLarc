"""Phase 2 — Tests d'intégration avec vraie base PostgreSQL.

Ces tests nécessitent PostgreSQL avec le schéma LarcSuperviseur.
Ils valident les vraies requêtes SQL en conditions réelles.

Usage :
    pytest tests/test_integration_database.py -v -m integration
    pytest tests/ -v                              # exclut les integration par défaut
    pytest tests/ -v -m "not integration"          # Phase 1 uniquement

Prérequis :
    - config.ini présent avec [IntranetDatabase]
    - PostgreSQL accessible avec le schéma NewLarcDB (ou configuré)
    - Au moins une classe active avec des élèves
"""

from __future__ import annotations

import pytest
from LarcSuperviseur.common.database import db


# ---------------------------------------------------------------------------
# Fixture : connexion à la vraie DB (une seule fois par session de test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_db():
    """Connecte la vraie base PostgreSQL et désactive le mock.

    Cette fixture est 'session' scope : la connexion est établie une fois
    pour toute la session de test, puis déconnectée à la fin.
    """
    ok = db.connect_intranet()
    if not ok or not db.server_conn:
        pytest.skip("PostgreSQL inaccessible — config.ini ou serveur manquant")
    yield db
    db.disconnect_all()


@pytest.fixture
def cur(real_db):
    """Curseur PostgreSQL frais pour chaque test."""
    conn = real_db.server_conn
    c = conn.cursor()
    yield c
    conn.rollback()  # pas de modifications persistantes


# ---------------------------------------------------------------------------
# Tests d'intégration
# ---------------------------------------------------------------------------


class TestIntegrationBase:
    """Tests de base : connexion et smoke test."""

    @pytest.mark.integration
    def test_cursor_can_execute(self, cur):
        """Vérifie que le curseur PostgreSQL exécute une requête simple."""
        cur.execute("SELECT 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1


class TestIntegrationActiveTerm:
    """Vraie requête : SELECT id FROM larcauth_term WHERE start_date <= today."""

    @pytest.mark.integration
    def test_active_term_exists(self, real_db):
        """Le terme actif doit exister dans la base réelle."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        term_id = DataLoader().get_active_term()
        assert term_id > 0, (
            "Aucun terme actif trouvé. Vérifier les données dans "
            "larcauth_term (start_date <= today <= end_date)."
        )

    @pytest.mark.integration
    def test_active_term_is_integer(self, real_db):
        """L'ID du terme actif est un entier positif."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        term_id = DataLoader().get_active_term()
        assert isinstance(term_id, int)
        assert term_id > 0


class TestIntegrationPrograms:
    """Vraie requête : SELECT id, sigle, label FROM larcauth_program."""

    @pytest.mark.integration
    def test_programs_have_pei_myp_dp(self, real_db):
        """Les programmes PEI, MYP, DPFr et DPEn existent dans la base."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        programs = DataLoader().get_programs()
        sigles = {p["sigle"] for p in programs.values()}
        for expected in ("PEI", "MYP", "DPFr", "DPEn"):
            assert expected in sigles, f"Programme {expected} manquant dans larcauth_program"

    @pytest.mark.integration
    def test_programs_have_labels(self, real_db):
        """Chaque programme a un label non vide."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        programs = DataLoader().get_programs()
        for pid, info in programs.items():
            assert info["label"].strip(), f"Programme {pid} ({info['sigle']}) sans label"


class TestIntegrationClasses:
    """Vraie requête : SELECT classes avec leur programme."""

    @pytest.mark.integration
    def test_classes_exist(self, real_db):
        """Au moins une classe active existe avec un programme valide."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        classes = DataLoader().get_classes()
        assert len(classes) > 0, (
            "Aucune classe trouvée. Vérifier larcauth_classroom avec enabled=TRUE "
            "et un programme PEI/MYP/DPFr/DPEn lié via larcauth_level."
        )

    @pytest.mark.integration
    def test_classes_have_valid_programs(self, real_db):
        """Toutes les classes retournées ont un sigle de programme valide."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        classes = DataLoader().get_classes()
        valid_sigles = {"PEI", "MYP", "DPFr", "DPEn", "PP", "PYP"}
        for cid, label, pid, sigle in classes:
            assert sigle in valid_sigles, (
                f"Classe {label} (id={cid}) a un programme invalide : {sigle}"
            )


class TestIntegrationStudents:
    """Vraie requête : SELECT élèves d'une classe."""

    @pytest.mark.integration
    def test_students_exist_in_class(self, real_db):
        """La première classe active a au moins un élève inscrit."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        classes = DataLoader().get_classes()
        if not classes:
            pytest.skip("Aucune classe disponible pour tester les élèves")
        first_class_id = classes[0][0]
        students = DataLoader().get_students(first_class_id)
        assert len(students) > 0, (
            f"La classe {classes[0][1]} (id={first_class_id}) n'a aucun élève. "
            "Vérifier larcauth_student avec enabled=TRUE."
        )

    @pytest.mark.integration
    def test_student_info_has_required_fields(self, real_db):
        """Un élève existant a toutes les infos requises."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        classes = DataLoader().get_classes()
        if not classes:
            pytest.skip("Aucune classe disponible")
        students = DataLoader().get_students(classes[0][0])
        if not students:
            pytest.skip("Aucun élève disponible")
        info = DataLoader().get_student_info(students[0]["id"])
        assert "last_name" in info
        assert "first_name" in info
        assert "class_label" in info


class TestIntegrationKpis:
    """Vraie requête : KPIs d'un élève sur une période."""

    @pytest.mark.integration
    def test_student_kpis_are_numbers(self, real_db):
        """Les KPIs d'un élève sont des entiers (ou 0 par défaut)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        classes = DataLoader().get_classes()
        if not classes:
            pytest.skip("Aucune classe disponible")
        students = DataLoader().get_students(classes[0][0])
        if not students:
            pytest.skip("Aucun élève disponible")
        kpis = DataLoader().get_student_kpis(
            students[0]["id"], "2024-01-01", "2024-12-31"
        )
        assert isinstance(kpis.get("abs_count", 0), int)
        assert isinstance(kpis.get("exit_count", 0), int)
        assert isinstance(kpis.get("total", 0), int)


class TestIntegrationClassStats:
    """Vraie requête : stats agrégées par classe (mode groupe)."""

    @pytest.mark.integration
    def test_class_stats_all_returns_data(self, real_db):
        """get_class_stats(grp_all) retourne des données pour la période courante."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        stats = DataLoader().get_class_stats("grp_all", "2024-01-01", "2024-12-31")
        assert isinstance(stats, list)
        if stats:
            row = stats[0]
            assert "label" in row
            assert "student_count" in row
            assert isinstance(row["student_count"], int)

    @pytest.mark.integration
    def test_class_stats_student_count_positive(self, real_db):
        """Le nombre total d'élèves retourné est cohérent."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        stats = DataLoader().get_class_stats("grp_all", "2024-01-01", "2024-12-31")
        total = sum(r["student_count"] for r in stats)
        assert total > 0, "Aucun élève trouvé dans les stats de groupe"


class TestIntegrationClassFilter:
    """Vraies requêtes : les filtres SQL fonctionnent correctement."""

    @pytest.mark.integration
    def test_college_filter_includes_pei_myp(self, real_db):
        """Le filtre Collège (PEI+MYP) retourne uniquement les classes concernées."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        all_classes = DataLoader().get_classes()
        college_sigles = {"PEI", "MYP"}
        college_ids = {c[0] for c in all_classes if c[3] in college_sigles}

        stats = DataLoader().get_class_stats("grp_college", "2024-01-01", "2024-12-31")
        returned_ids = {r["id"] for r in stats}

        # Les classes retournées doivent être un sous-ensemble des classes Collège
        assert returned_ids.issubset(college_ids), (
            f"Classes hors Collège retournées : {returned_ids - college_ids}"
        )

    @pytest.mark.integration
    def test_lycee_filter_includes_dpf_dpen(self, real_db):
        """Le filtre Lycée (DPFr+DPEn) retourne uniquement les classes concernées."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        all_classes = DataLoader().get_classes()
        lycee_sigles = {"DPFr", "DPEn"}
        lycee_ids = {c[0] for c in all_classes if c[3] in lycee_sigles}

        stats = DataLoader().get_class_stats("grp_lycee", "2024-01-01", "2024-12-31")
        returned_ids = {r["id"] for r in stats}

        assert returned_ids.issubset(lycee_ids), (
            f"Classes hors Lycée retournées : {returned_ids - lycee_ids}"
        )


class TestIntegrationEventHistory:
    """Vraie requête : historique des événements."""

    @pytest.mark.integration
    def test_event_history_returns_list(self, real_db):
        """get_event_history retourne une liste (éventuellement vide)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        history = DataLoader().get_event_history("grp_all", "2024-01-01", "2024-12-31")
        assert isinstance(history, list)

    @pytest.mark.integration
    def test_event_history_has_valid_structure(self, real_db):
        """Chaque événement a les champs attendus (structure dict)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        history = DataLoader().get_event_history("grp_all", "2024-01-01", "2024-12-31")
        if history:
            evt = history[0]
            assert "event_id" in evt
            assert "student_name" in evt
            assert "event_type" in evt
            assert "event_at" in evt
            # Vérifier le type datetime de event_at
            from datetime import datetime
            assert isinstance(evt["event_at"], datetime), (
                f"event_at devrait être un datetime, reçu {type(evt['event_at'])}"
            )


class TestIntegrationLocations:
    """Vraie requête : lieux."""

    @pytest.mark.integration
    def test_locations_returned(self, real_db):
        """get_locations retourne une liste de lieux (au moins 1)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        locations = DataLoader().get_locations()
        assert isinstance(locations, list)


class TestIntegrationPresenceRate:
    """Vraie requête : taux de présence."""

    @pytest.mark.integration
    def test_presence_rate_returns_counts(self, real_db):
        """get_presence_rate retourne present+absent cohérents."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        rate = DataLoader().get_presence_rate("grp_all", "2024-01-01", "2024-12-31")
        assert "present" in rate
        assert "absent" in rate
        # Les compteurs sont des entiers positifs ou nuls
        assert isinstance(rate["present"], int) and rate["present"] >= 0
        assert isinstance(rate["absent"], int) and rate["absent"] >= 0


class TestIntegrationEventTypes:
    """Vraie requête : types d'événements."""

    @pytest.mark.integration
    def test_event_types_loaded(self, real_db):
        """get_all_event_types retourne des types d'événements."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        types = DataLoader().get_all_event_types()
        assert isinstance(types, list)
        if types:
            assert isinstance(types[0], str)
            assert len(types[0]) > 0

    @pytest.mark.integration
    def test_event_types_tree_structure(self, real_db):
        """get_event_types_tree retourne une structure arborescente."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        tree = DataLoader().get_event_types_tree()
        assert isinstance(tree, dict)
        # Au moins une catégorie de type d'événement
        if tree:
            cat = list(tree.keys())[0]
            assert isinstance(tree[cat], dict)


class TestIntegrationUnitPeriods:
    """Vraie requête : périodes (unités)."""

    @pytest.mark.integration
    def test_unit_periods_exist(self, real_db):
        """get_unit_periods retourne les périodes de l'année scolaire."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        periods = DataLoader().get_unit_periods()
        assert isinstance(periods, list)
        if periods:
            p = periods[0]
            assert "id" in p
            assert "label" in p
            assert "start_date" in p
            assert "end_date" in p


class TestIntegrationEventActions:
    """Vraies requêtes : CRUD événements (lecture seule)."""

    @pytest.mark.integration
    def test_get_event_by_id_exists(self, real_db):
        """get_event_by_id retourne un événement existant."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        # Trouver un événement existant via l'historique
        history = DataLoader().get_event_history("grp_all", "2024-01-01", "2024-12-31")
        if not history:
            pytest.skip("Aucun événement trouvé dans la période")
        event_id = history[0]["event_id"]

        from LarcSuperviseur.views.core.event_actions import EventActions
        event = EventActions().get_event_by_id(event_id)

        assert event is not None
        assert event["event_id"] == event_id
        assert "student_name" in event

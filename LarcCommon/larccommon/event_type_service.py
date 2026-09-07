"""EventTypeConfigService — gestionnaire centralisé des types d'événements.

Charge depuis larcauth_event_type_config avec cache et invalidation.
Supporte N niveaux d'hiérarchie (vs hardcodé 3).
Filtre par member_type (student vs staff).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from larccommon.database import db
from larccommon.logger import log


class MemberType(Enum):
    STUDENT = "student"
    STAFF = "staff"


@dataclass
class EventTypeNode:
    """Représente un type d'événement dans la hiérarchie."""
    id: int
    code: str
    label: str
    category: str  # "absence", "retard", "evenement", "custom"
    icon_code: Optional[str]
    parent_id: Optional[int]
    applicable_to: str  # "student,staff" ou "student" ou "staff"
    requires_validation: bool
    requires_lieu: bool
    requires_subject: bool
    children: List['EventTypeNode'] = field(default_factory=list)

    def is_applicable_to(self, member_type: MemberType) -> bool:
        """Vérifie si ce type s'applique au type de membre."""
        types = self.applicable_to.split(',')
        return member_type.value in types


class EventTypeConfigService:
    """Singleton : gestionnaire centralisé des types d'événements avec cache."""

    _instance: Optional['EventTypeConfigService'] = None
    _cache: Optional[Dict[int, EventTypeNode]] = None
    _hierarchies: Dict[str, EventTypeNode] = {}

    def __new__(cls) -> 'EventTypeConfigService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache = None
        self._hierarchies = {}
        self._cached_language: Optional[int] = None

    def load_hierarchy(self, fk_language: int, force_refresh: bool = False) -> Dict[str, EventTypeNode]:
        """
        Charge la hiérarchie depuis DB pour une langue donnée, avec cache.

        Le cache est mono-langue : un changement de langue déclenche un rechargement
        transparent (pas de cache multi-langue simultané — inutile, une session UI ne
        travaille jamais dans deux langues à la fois).

        Retourne dict : {category: root_node}
        Exemple : {"absence": Node(...), "retard": Node(...), ...}

        Args:
            fk_language: id de la langue (larcauth_language.id)
            force_refresh: Invalider le cache et recharger depuis DB

        Returns:
            Dict[str, EventTypeNode] : racines par catégorie, ou {} si erreur
        """
        if self._hierarchies and self._cached_language == fk_language and not force_refresh:
            return self._hierarchies

        try:
            conn = db.server_conn
            if not conn or conn.closed:
                log("EventTypeConfigService.load_hierarchy: DB not connected")
                return {}

            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, code, label, category, icon_code, parent_id,
                       applicable_to, requires_validation, requires_lieu, requires_subject
                FROM larcauth_event_type_config
                WHERE is_active = TRUE AND fk_language = %s
                ORDER BY category, parent_id NULLS FIRST, label
                """,
                (fk_language,),
            )

            rows = cur.fetchall()
            if not rows:
                log(f"EventTypeConfigService.load_hierarchy: aucun type chargé (langue={fk_language})")
                return {}

            # Réinitialiser le cache
            self._cache = {}

            # Construire les nœuds
            for row in rows:
                node_id = row[0]
                self._cache[node_id] = EventTypeNode(
                    id=node_id,
                    code=row[1],
                    label=row[2],
                    category=row[3],
                    icon_code=row[4],
                    parent_id=row[5],
                    applicable_to=row[6],
                    requires_validation=row[7],
                    requires_lieu=row[8],
                    requires_subject=row[9],
                )

            # Attacher les enfants aux parents
            for node in self._cache.values():
                if node.parent_id and node.parent_id in self._cache:
                    self._cache[node.parent_id].children.append(node)

            # Extraire les racines (parent_id = None) par catégorie
            self._hierarchies = {}
            for node in self._cache.values():
                if node.parent_id is None:  # Racine
                    self._hierarchies[node.category] = node

            self._cached_language = fk_language
            log(
                f"EventTypeConfigService: loaded {len(self._cache)} types, "
                f"{len(self._hierarchies)} roots (langue={fk_language})"
            )
            return self._hierarchies

        except Exception as e:
            log(f"EventTypeConfigService.load_hierarchy: {e}")
            return {}

    def get_children(self, parent_id: int) -> List[EventTypeNode]:
        """Retourne les enfants directs d'un nœud."""
        if self._cache is None:
            self.load_hierarchy()

        if not self._cache or parent_id not in self._cache:
            return []

        return self._cache[parent_id].children

    def get_by_code(self, code: str) -> Optional[EventTypeNode]:
        """Retourne un nœud par son code."""
        if self._cache is None:
            self.load_hierarchy()

        if not self._cache:
            return None

        for node in self._cache.values():
            if node.code == code:
                return node

        return None

    def get_by_id(self, node_id: int) -> Optional[EventTypeNode]:
        """Retourne un nœud par son ID."""
        if self._cache is None:
            self.load_hierarchy()

        return self._cache.get(node_id) if self._cache else None

    def filter_applicable(
        self, member_type: MemberType, fk_language: int
    ) -> Dict[str, EventTypeNode]:
        """
        Filtre les types applicables pour un type de membre, dans une langue donnée.

        Args:
            member_type: MemberType.STUDENT ou MemberType.STAFF
            fk_language: id de la langue (larcauth_language.id)

        Returns:
            Dict[str, EventTypeNode] : racines applicables par catégorie
        """
        hierarchies = self.load_hierarchy(fk_language)
        result = {}

        for cat, root in hierarchies.items():
            if root.is_applicable_to(member_type):
                result[cat] = root

        return result

    def get_path(self, node: EventTypeNode) -> str:
        """
        Retourne le chemin complet du nœud (racine → nœud).

        Exemple : "Absence > Absent de l'école > Maladie"

        Args:
            node: EventTypeNode

        Returns:
            str : chemin avec " > " comme séparateur
        """
        if self._cache is None:
            self.load_hierarchy()

        path = [node.label]
        current = node

        while current.parent_id:
            parent = self._cache.get(current.parent_id) if self._cache else None
            if not parent:
                break
            path.insert(0, parent.label)
            current = parent

        return " > ".join(path)

    def invalidate_cache(self):
        """Invalide le cache (appelé si config DB change)."""
        self._cache = None
        self._hierarchies = {}
        self._cached_language = None
        log("EventTypeConfigService: cache invalidated")


# Singleton global
event_type_service = EventTypeConfigService()

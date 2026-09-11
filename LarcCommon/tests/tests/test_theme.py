import pytest
from larccommon.theme import _LarcM3Colors, _THEME_PALETTES


@pytest.mark.parametrize("theme_key", list(_THEME_PALETTES.keys()))
def test_surface_container_roles_are_distinct(theme_key):
    c = _LarcM3Colors(_THEME_PALETTES[theme_key])
    roles = {
        "surface": c.surface,
        "surface_variant": c.surface_variant,
        "surface_container_low": c.surface_container_low,
        "surface_container": c.surface_container,
        "surface_container_high": c.surface_container_high,
        "surface_container_highest": c.surface_container_highest,
    }
    # Chaque rôle doit avoir une valeur propre — aucun alias entre deux rôles distincts
    assert len(set(roles.values())) == len(roles), f"{theme_key}: rôles dupliqués -> {roles}"

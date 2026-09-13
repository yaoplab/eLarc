"""Régression : `ds.phi` (Theme M3) et `ds.phi_scale` (PhiScale) ne doivent
pas se marcher dessus.

`_DesignSystem` définissait autrefois deux propriétés `phi` dans la même
classe : l'accesseur Theme historique (`self._tm.phi_theme`) et un nouvel
accesseur PhiScale ajouté par la fondation "2b. PHI TOKENS". Python gardait
silencieusement la seconde définition, donc `ds.phi` retournait un `PhiScale`
au lieu d'un `Theme` partout — cassant `ds.c.*` (M3ColorScheme) et le pattern
documenté `M3Button(theme=ds.phi, ...)` utilisé dans toute la suite
d'applications.
"""

from phibuilder.phi.phi_scale import PhiScale
from phibuilder.theme import Theme


def test_ds_phi_returns_theme_not_phiscale():
    """`ds.phi` doit rester l'accesseur Theme M3 (self._tm.phi_theme)."""
    from larccommon.design_system import ds

    assert isinstance(ds.phi, Theme)
    assert hasattr(ds.phi, "colors")


def test_ds_c_resolves_without_raising():
    """`ds.c` (= ds.phi.colors) doit résoudre une couleur M3 sans lever."""
    from larccommon.design_system import ds

    primary = ds.c.primary
    assert isinstance(primary, str)
    assert primary  # non vide


def test_ds_phi_scale_returns_phiscale_instance():
    """`ds.phi_scale` est le nouvel accesseur PhiScale (spacing/sizing)."""
    from larccommon.design_system import ds

    assert isinstance(ds.phi_scale, PhiScale)
    assert hasattr(ds.phi_scale, "spacing")
    assert hasattr(ds.phi_scale, "sizing")
    # Cohérent avec les raccourcis phi_space_* / phi_size_* de ds, qui
    # lisent déjà self._phi directement.
    assert ds.phi_scale.spacing.xxs == ds.phi_space_xxs
    assert ds.phi_scale.sizing.xs == ds.phi_size_xs


def test_ds_phi_and_phi_scale_are_distinct():
    """Les deux accesseurs ne doivent jamais retourner le même objet."""
    from larccommon.design_system import ds

    assert ds.phi is not ds.phi_scale
    assert not isinstance(ds.phi, PhiScale)
    assert not isinstance(ds.phi_scale, Theme)

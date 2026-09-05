from phibuilder.theme import Theme, ThemeConfig
from phibuilder.style import StyleBuilder
from phibuilder.phi.scale import SpacingToken
from typing import Any

class PhiBuilder:
    def __init__(self, seed_color: str = "#6750A4", is_dark: bool = False):
        self._config = ThemeConfig(seed_color=seed_color, is_dark=is_dark, variant="tonal_spot", font_family="Segoe UI")
        self._theme = Theme(self._config)
        self._rebuild()
    def _rebuild(self):
        self._qss = StyleBuilder(self._theme).build()
    @property
    def theme(self) -> Theme:
        return self._theme
    @property
    def qss(self) -> str:
        return self._qss
    def apply(self, widget: Any):
        widget.setStyleSheet(self._qss)
    def set_dark_mode(self, dark: bool):
        self._config.is_dark = dark
        self._theme = Theme(self._config)
        self._rebuild()
    def toggle_dark_mode(self):
        self.set_dark_mode(not self._config.is_dark)
    def set_seed_color(self, color: str):
        self._config.seed_color = color
        self._theme = Theme(self._config)
        self._rebuild()
    def set_font(self, family: str):
        self._config.font_family = family
        self._theme = Theme(self._config)
        self._rebuild()
    def set_variant(self, variant: str):
        self._config.variant = variant
        self._theme = Theme(self._config)
        self._rebuild()
    def export_qss(self, path: str):
        with open(path, "w") as f:
            f.write(self._qss)
    def export_theme_json(self, path: str):
        import json
        with open(path, "w") as f:
            json.dump(self._theme.colors.all_colors, f, indent=2)
    @property
    def palette(self) -> dict[str, str]:
        return dict(self._theme.colors.all_colors)

from dataclasses import dataclass
from phibuilder.phi.constants import PHI
from phibuilder.phi.scale import SpacingToken, PhiScale

@dataclass
class Column:
    width: int = 1
    offset: int = 0
    order: int = 0
    visible: bool = True

class PhiGrid:
    def __init__(self, columns: int = 12, gutter: SpacingToken = SpacingToken.MD,
                 margin: SpacingToken = SpacingToken.LG, base_spacing: int = 4):
        self.columns = columns
        self.gutter = gutter
        self.margin = margin
        self._scale = PhiScale(base_spacing)
    @property
    def gutter_px(self) -> int:
        return self._scale.spacing(self.gutter)
    @property
    def margin_px(self) -> int:
        return self._scale.spacing(self.margin)
    def column_width(self, total_width: int, span: int = 1) -> int:
        usable = total_width - 2 * self.margin_px
        gaps = (self.columns - 1) * self.gutter_px
        col_width = (usable - gaps) // self.columns
        return col_width * span + (span - 1) * self.gutter_px
    def phi_split(self, total: int, inverse: bool = False) -> tuple[int, int]:
        if inverse:
            return (round(total - total / PHI), round(total / PHI))
        return (round(total / PHI), round(total - total / PHI))
    def golden_rectangle(self, width: int) -> tuple[int, int]:
        return (width, round(width / PHI))
    def golden_spiral(self, n: int = 5) -> list[tuple[int, int, int]]:
        from phibuilder.phi.sequence import fibonacci_sequence
        sizes = fibonacci_sequence(1, n)
        rects, x, y = [], 0, 0
        for i, s in enumerate(sizes):
            rects.append((x, y, s, s))
            if i % 4 == 0: x += s
            elif i % 4 == 1: y += s
            elif i % 4 == 2: x -= sizes[i - 1] if i > 0 else s
            elif i % 4 == 3: y -= sizes[i - 1] if i > 0 else s
        return rects

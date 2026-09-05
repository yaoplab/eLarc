from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class BorderRadius:
    top_left: int; top_right: int; bottom_right: int; bottom_left: int
    @classmethod
    def all(cls, r: int):
        return cls(r, r, r, r)
    def qss(self) -> str:
        if self.top_left == self.top_right == self.bottom_right == self.bottom_left:
            return f"border-radius: {self.top_left}px;"
        return (f"border-top-left-radius: {self.top_left}px; border-top-right-radius: {self.top_right}px; "
                f"border-bottom-right-radius: {self.bottom_right}px; border-bottom-left-radius: {self.bottom_left}px;")

M3_SHAPES = {
    "none": BorderRadius.all(0), "xs": BorderRadius.all(4), "sm": BorderRadius.all(8),
    "md": BorderRadius.all(12), "lg": BorderRadius.all(16), "xl": BorderRadius.all(28),
    "full": BorderRadius.all(9999),
}

class M3Shape(str, Enum):
    NONE = "none"; XS = "xs"; SM = "sm"; MD = "md"; LG = "lg"; XL = "xl"; FULL = "full"
    @property
    def radius(self) -> BorderRadius:
        return M3_SHAPES[self.value]
    def qss(self) -> str:
        return self.radius.qss()

from dataclasses import dataclass
from enum import IntEnum

@dataclass(frozen=True)
class Shadow:
    offset_x: int; offset_y: int; blur: int; spread: int = 0; opacity: float = 0.3

M3_ELEVATION = {
    0: [], 1: [Shadow(0,1,3,0,0.3), Shadow(0,1,2,0,0.15)],
    2: [Shadow(0,1,5,0,0.3), Shadow(0,2,2,0,0.15)],
    3: [Shadow(0,1,8,0,0.3), Shadow(0,3,4,0,0.15)],
    4: [Shadow(0,2,10,0,0.3), Shadow(0,4,5,0,0.15)],
    5: [Shadow(0,4,12,0,0.3), Shadow(0,6,7,0,0.15)],
}

class M3Elevation(IntEnum):
    LEVEL_0 = 0; LEVEL_1 = 1; LEVEL_2 = 2; LEVEL_3 = 3; LEVEL_4 = 4; LEVEL_5 = 5
    @property
    def shadows(self) -> list[Shadow]:
        return M3_ELEVATION[self.value]
    def qss_shadow(self, color: str = "#000000") -> str:
        parts = [f"{s.offset_x}px {s.offset_y}px {s.blur}px {s.spread}px rgba(0,0,0,{s.opacity})"
                 for s in self.shadows]
        return ", ".join(parts) if parts else "none"

def elevation_shadows(level: int) -> list[Shadow]:
    return M3_ELEVATION.get(level, [])

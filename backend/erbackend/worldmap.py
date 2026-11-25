"""Współrzędne: lokalne (mapa/kafel z save'a lub MSB) -> świat (m60/m61) -> piksele mapy strony.

Ten sam wzór co tools/extract (extract_data.TRANSFORM, extract_world.World.to_map), którym liczone są
pozycje łask/bossów/skarbów w assets/data — więc pozycja gracza i plamy krwi trafiają w to samo miejsce mapy:
    świat:   X = gx*256 + x + 128,  Z = gz*256 + z + 128          (kafel mAA_gx_gz_00, AA = 60/61)
    piksele: px = X - ox,  py = size - (Z - oz)                    (ox/oz/size z map_transform)
Lochi -> świat: WorldMapLegacyConvParam (punkt src w lochu = punkt dst na świecie, łańcuchy rekurencyjnie);
małe lochy (katakumby, jaskinie, tunele, lochy DLC) — cała zawartość przy wejściu (approx);
podziemia m12 — dokładnie, na mapie M01; Farum Azula m13 — w wirze burzy (FARUM).
"""
from __future__ import annotations

import json
import math
import os

from .gamedata import DATA_DIR

ENTRANCE_AREAS = {30, 31, 32, 39, 40, 41, 42, 43}
UNDERGROUND = {"M00": "M01"}          # podziemia (m12) — osobna mapa gry (jak tools/extract/extract_world.py)
FARUM = {"px": 8520, "py": 4500, "scale": 0.9, "x": -107.0, "z": 350.0}   # Farum Azula (m13) w wirze burzy


RECT_Y = (-10.0, 40.0)        # region "rect" jest płaski (szer. × głęb.) — wysokość: 10 m pod spodem, 40 m nad


def inside_shape(s: dict, p: tuple, margin: float = 0.0) -> bool:
    """Czy punkt p (x, y, z) leży w regionie MSB s = {shape, x, y, z, rot_y, dims} (ten sam układ lokalny)."""
    dx, dy, dz = p[0] - s["x"], p[1] - s["y"], p[2] - s["z"]
    a = -math.radians(s.get("rot_y") or 0.0)
    lx, lz = dx * math.cos(a) + dz * math.sin(a), -dx * math.sin(a) + dz * math.cos(a)
    shape, d = s["shape"], s["dims"]
    if shape == "sphere":
        return math.dist(p, (s["x"], s["y"], s["z"])) <= d[0] + margin
    if shape == "circle":
        return math.hypot(dx, dz) <= d[0] + margin and RECT_Y[0] - margin <= dy <= RECT_Y[1] + margin
    if shape == "cylinder":
        return math.hypot(dx, dz) <= d[0] + margin and -margin <= dy <= d[1] + margin
    if shape in ("rect", "box"):
        ok = abs(lx) <= d[0] / 2 + margin and abs(lz) <= d[1] / 2 + margin
        lo, hi = (0.0, d[2]) if shape == "box" else RECT_Y
        return ok and lo - margin <= dy <= hi + margin
    return False


def parse_map(map_id: str | None) -> tuple[int, int, int] | None:
    try:
        a, gx, gz = (int(v) for v in map_id[1:].split("_")[:3])
        return a, gx, gz
    except (AttributeError, ValueError, TypeError):
        return None


class WorldMap:
    def __init__(self, extras: dict | None):
        extras = extras or {}
        self.transform = extras.get("transform") or {}
        self.conv = []
        for row in extras.get("legacy_conv", []):
            src, sx, sy, sz, dst, dx, dy, dz = row
            self.conv.append((parse_map(src), (sx, sy, sz), parse_map(dst), (dx, dy, dz)))
        self.play_regions = extras.get("play_regions") or {}

    @classmethod
    def load(cls, data_dir: str = DATA_DIR) -> "WorldMap":
        path = os.path.join(data_dir, "world_extras.json")
        if not os.path.exists(path):
            return cls(None)
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    @property
    def available(self) -> bool:
        return bool(self.transform)

    # --- przeliczenia ------------------------------------------------------------------------
    def to_overworld(self, area, gx, gz, x, y, z, depth=0):
        """-> (area, gx, gz, x, y, z, approx) w m60/m61 albo None."""
        if area in (60, 61):
            return area, gx, gz, x, y, z, False
        if depth > 5:
            return None
        cands = sorted((c for c in self.conv if c[0] == (area, gx, gz)),
                       key=lambda c: (c[2][0] not in (60, 61), (c[1][0] - x) ** 2 + (c[1][2] - z) ** 2))
        for _src, sp, dst, dp in cands:
            if area in ENTRANCE_AREAS:
                res = self.to_overworld(*dst, *dp, depth + 1)
                res = res and (*res[:6], True)
            else:
                res = self.to_overworld(*dst, dp[0] + x - sp[0], dp[1] + y - sp[1], dp[2] + z - sp[2], depth + 1)
            if res:
                return res
        return None

    def world(self, map_id: str, x: float, y: float, z: float) -> dict | None:
        """Pozycja w układzie świata: {area, X, Y, Z, approx} (X/Z w metrach od początku siatki)."""
        m = parse_map(map_id)
        if not m or x is None:
            return None
        w = self.to_overworld(*m, x, y, z)
        if not w:
            return None
        a, gx, gz, wx, wy, wz, approx = w
        return {"area": a, "X": gx * 256 + wx + 128, "Y": wy, "Z": gz * 256 + wz + 128, "approx": approx}

    def to_map(self, map_id: str, x: float, y: float, z: float) -> dict | None:
        """Piksele mapy strony: {map: "M00"/"M01"/"M10", px, py, approx} albo None."""
        m = parse_map(map_id)
        if m and m[0] == 13 and x is not None and self.available:
            f = FARUM
            return {"map": "M00", "px": round(f["px"] + (x - f["x"]) * f["scale"], 1),
                    "py": round(f["py"] - (z - f["z"]) * f["scale"], 1), "approx": False}
        w = self.world(map_id, x, y, z)
        if not w:
            return None
        for key, t in self.transform.items():
            if t["area"] == w["area"]:
                return {"map": UNDERGROUND.get(key, key) if m and m[0] == 12 else key,
                        "px": round(w["X"] - t["ox"], 1), "py": round(t["size"] - (w["Z"] - t["oz"]), 1),
                        "approx": w["approx"]}
        return None

    def distance(self, map_a: str, pa: tuple, map_b: str, pb: tuple) -> float | None:
        """Odległość 3D między punktami (lokalnie, gdy ta sama mapa; przez świat dla kafli m60/m61)."""
        if map_a == map_b:
            return math.dist(pa, pb)
        a, b = parse_map(map_a), parse_map(map_b)
        if a and b and a[0] == b[0] and a[0] in (60, 61):
            wa = (a[1] * 256 + pa[0], pa[1], a[2] * 256 + pa[2])
            wb = (b[1] * 256 + pb[0], pb[1], b[2] * 256 + pb[2])
            return math.dist(wa, wb)
        return None

    def to_frame(self, map_src: str, p: tuple, map_dst: str) -> tuple | None:
        """Punkt p z układu mapy map_src w układzie lokalnym map_dst (ta sama mapa albo kafle tego samego świata)."""
        if map_src == map_dst:
            return p
        a, b = parse_map(map_src), parse_map(map_dst)
        if a and b and a[0] == b[0] and a[0] in (60, 61):
            return (p[0] + (a[1] - b[1]) * 256, p[1], p[2] + (a[2] - b[2]) * 256)
        return None

    # --- regiony ------------------------------------------------------------------------------
    def region_name(self, region_id: int) -> dict:
        e = self.play_regions.get(str(region_id))
        return {"id": region_id, **(e or {"name": None, "region": None, "subregion": None, "map_id": None, "kind": None})}

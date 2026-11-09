#!/usr/bin/env python
"""Crossing zones and approach arms for K305, found from the data and labelled with OSM.

    python zones.py --data dashboard/data --map dashboard/config/k305_map.json --out dashboard/config

Crossings: cells (0.5 m) where pedestrians spend time AND vehicles drive, grouped into connected areas.
           This uses the recorded tracks, not the OSM drawing, so small map alignment errors do not matter.
           Each area is labelled with the nearest OSM crossing node and road, if one is close.
Arms:      the junction center is where vehicle presence is densest; the vehicle legs are the peaks of the
           vehicle presence by angle around it; arm borders lie halfway between neighbouring legs.
           Each arm gets a compass direction (via the OSM alignment) and the nearest OSM road name.

Writes zones.json and zones_check.png. Use `arm_of(x, y, zones)` / `crossing_of(x, y, zones)` elsewhere.
"""
import argparse
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

LIM, CELL = 46.0, 0.5
N = int(2 * LIM / CELL)
VEHICLES = ["Car", "Van", "Truck", "Bus"]
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def grid(dens, classes):
    s = dens[dens["cls"].isin(classes)].groupby(["ix", "iy"])["dwell_s"].sum()
    g = np.zeros((N, N))
    g[s.index.get_level_values("iy"), s.index.get_level_values("ix")] = s.to_numpy()
    return g


def cell_xy(i, j):
    """grid column i, row j -> cell center in sensor meters"""
    return -LIM + (np.asarray(i) + 0.5) * CELL, -LIM + (np.asarray(j) + 0.5) * CELL


def components(mask, min_cells):
    """4-neighbour connected areas of a boolean grid, largest first."""
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for j0, i0 in zip(*np.nonzero(mask)):
        if seen[j0, i0]:
            continue
        q, cells = deque([(j0, i0)]), []
        seen[j0, i0] = True
        while q:
            j, i = q.popleft()
            cells.append((j, i))
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = j + dj, i + di
                if 0 <= a < N and 0 <= b < N and mask[a, b] and not seen[a, b]:
                    seen[a, b] = True
                    q.append((a, b))
        if len(cells) >= min_cells:
            out.append(np.array(cells))
    return sorted(out, key=len, reverse=True)


def convex_hull(pts):
    pts = sorted(set(map(tuple, np.round(pts, 2))))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def point_in_polygon(x, y, poly):
    """Ray casting, vectorised over points."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    inside = np.zeros(x.shape, bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        hit = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1)
        inside ^= hit
    return inside


def dist_to_polyline(px, py, xy):
    xy = np.asarray(xy, float)
    best = np.inf
    for a, b in zip(xy[:-1], xy[1:]):
        ab = b - a
        t = np.clip(((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / max(ab @ ab, 1e-12), 0, 1)
        best = min(best, math.hypot(px - (a[0] + t * ab[0]), py - (a[1] + t * ab[1])))
    return best


def sensor_angle_to_bearing(angle_deg, transform):
    """Direction in the sensor frame (deg, math convention) -> compass bearing (deg clockwise from north)."""
    enu = angle_deg + transform["rotation_deg"]           # p = R(rotation) (q - shift)
    if transform.get("mirror"):
        enu = -enu
    return (90.0 - enu) % 360


def blur(a, sigma_cells):
    r = int(3 * sigma_cells)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_cells) ** 2)
    k /= k.sum()
    a = np.apply_along_axis(lambda m: np.convolve(m, k, "same"), 0, a)
    return np.apply_along_axis(lambda m: np.convolve(m, k, "same"), 1, a)


def find_crossings(V, P, C, osm, min_ped_s, min_veh_s, min_area_m2, road_sigma_m=1.0):
    # vehicle presence is striped by lane; smooth it into a road surface before intersecting with pedestrians
    road = blur(V, road_sigma_m / CELL) >= min_veh_s
    mask = road & (P >= min_ped_s)
    out = []
    for k, cells in enumerate(components(mask, int(min_area_m2 / CELL ** 2))):
        x, y = cell_xy(cells[:, 1], cells[:, 0])
        hull = convex_hull(np.c_[x, y])
        cx, cy = float(x.mean()), float(y.mean())
        near = min(osm["crossing_nodes"], key=lambda c: math.hypot(c["x"] - cx, c["y"] - cy), default=None)
        dn = math.hypot(near["x"] - cx, near["y"] - cy) if near else None
        roads = [(dist_to_polyline(cx, cy, r["xy"]), r["name"]) for r in osm["roads"] if r.get("name")]
        road = min(roads)[1] if roads else None
        out.append({
            "id": f"X{k + 1}", "center": [round(cx, 2), round(cy, 2)], "polygon": [list(p) for p in hull],
            "area_m2": round(len(cells) * CELL ** 2, 1),
            "ped_dwell_s": round(float(P[cells[:, 0], cells[:, 1]].sum()), 1),
            "cyc_dwell_s": round(float(C[cells[:, 0], cells[:, 1]].sum()), 1),
            "road": road,
            "osm_crossing_node": near["id"] if near and dn < 10 else None,
            "osm_crossing_distance_m": round(dn, 1) if dn is not None else None,
        })
    return out


def find_arms(V, osm, core_radius, ring=(15.0, 42.0)):
    # junction center: densest vehicle area at a 6 m scale
    r = int(6 / CELL)
    k = np.ones(2 * r + 1)
    sm = np.apply_along_axis(lambda m: np.convolve(m, k, "same"), 0, np.log1p(V))
    sm = np.apply_along_axis(lambda m: np.convolve(m, k, "same"), 1, sm)
    j, i = np.unravel_index(np.argmax(sm), sm.shape)
    cx, cy = (float(v) for v in cell_xy(i, j))
    # vehicle presence by angle in a ring around the center
    jj, ii = np.nonzero(V > 0)
    x, y = cell_xy(ii, jj)
    rr = np.hypot(x - cx, y - cy)
    sel = (rr > ring[0]) & (rr < ring[1])
    ang = np.degrees(np.arctan2(y[sel] - cy, x[sel] - cx)) % 360
    h, _ = np.histogram(ang, bins=72, range=(0, 360), weights=np.log1p(V[jj[sel], ii[sel]]))
    h = np.convolve(np.r_[h[-2:], h, h[:2]], np.ones(5) / 5, "same")[2:-2]
    peaks = [b for b in range(72) if h[b] >= h[b - 1] and h[b] >= h[(b + 1) % 72] and h[b] > 0.35 * h.max()]
    # keep the strongest peaks at least 40 deg apart
    peaks = sorted(peaks, key=lambda b: -h[b])
    legs = []
    for b in peaks:
        a = b * 5 + 2.5
        if all(min(abs(a - c), 360 - abs(a - c)) >= 40 for c in legs):
            legs.append(a)
    legs = sorted(legs)
    tr = osm["transform_enu_to_sensor"]
    arms = []
    for n_, a in enumerate(legs):
        prev_a, next_a = legs[n_ - 1], legs[(n_ + 1) % len(legs)]
        lo = (a - ((a - prev_a) % 360) / 2) % 360
        hi = (a + ((next_a - a) % 360) / 2) % 360
        bearing = sensor_angle_to_bearing(a, tr)
        px, py = cx + 30 * math.cos(math.radians(a)), cy + 30 * math.sin(math.radians(a))
        roads = [(dist_to_polyline(px, py, rd["xy"]), rd["name"]) for rd in osm["roads"] if rd.get("name")]
        arms.append({"id": None, "compass": COMPASS[int(((bearing + 22.5) % 360) // 45)], "sensor_angle_deg": round(a, 1),
                     "from_deg": round(lo, 1), "to_deg": round(hi, 1), "bearing_deg": round(bearing, 1),
                     "road": min(roads)[1] if roads and min(roads)[0] < 25 else None})
    if len(arms) == 4:
        # four legs: give them N / E / S / W by the best overall angle match (one label each)
        from itertools import permutations
        target = {"N": 0, "E": 90, "S": 180, "W": 270}

        def diff(b, t):
            return min(abs(b - t), 360 - abs(b - t))

        best = min(permutations("NESW"), key=lambda p: sum(diff(a["bearing_deg"], target[lab]) for a, lab in zip(arms, p)))
        for a, lab in zip(arms, best):
            a["id"] = lab
    else:
        seen = {}
        for a in arms:
            seen[a["compass"]] = seen.get(a["compass"], 0) + 1
            a["id"] = a["compass"] if seen[a["compass"]] == 1 else f"{a['compass']}{seen[a['compass']]}"
    return {"center": [round(cx, 2), round(cy, 2)], "core_radius_m": core_radius, "arms": arms}


def arm_of(x, y, zones):
    """Arm id for sensor points, 'core' inside the junction, vectorised."""
    cx, cy = zones["junction"]["center"]
    x, y = np.asarray(x, float), np.asarray(y, float)
    ang = np.degrees(np.arctan2(y - cy, x - cx)) % 360
    out = np.full(x.shape, "core", dtype=object)
    far = np.hypot(x - cx, y - cy) > zones["junction"]["core_radius_m"]
    for a in zones["junction"]["arms"]:
        lo, hi = a["from_deg"], a["to_deg"]
        inside = ((ang >= lo) & (ang < hi)) if lo < hi else ((ang >= lo) | (ang < hi))
        out[far & inside] = a["id"]
    return out


def crossing_of(x, y, zones):
    """Crossing id for sensor points, None outside every crossing."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    out = np.full(x.shape, None, dtype=object)
    for c in zones["crossings"]:
        out[point_in_polygon(x, y, c["polygon"]) & (out == None)] = c["id"]  # noqa: E711
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="dashboard/data", help="folder with density_<variant>.parquet")
    ap.add_argument("--variant", default="stitched", help="density variant to use (stitched keeps waiting people)")
    ap.add_argument("--map", default="dashboard/config/k305_map.json")
    ap.add_argument("--out", default="dashboard/config")
    ap.add_argument("--min-ped-s", type=float, default=15.0, help="pedestrian dwell per 0.5 m cell per day")
    ap.add_argument("--min-veh-s", type=float, default=10.0, help="smoothed vehicle dwell per 0.5 m cell per day (road surface)")
    ap.add_argument("--min-area-m2", type=float, default=6.0)
    ap.add_argument("--core-radius-m", type=float, default=12.0)
    args = ap.parse_args(argv)

    dens = pd.read_parquet(Path(args.data) / f"density_{args.variant}.parquet")
    osm = json.loads(Path(args.map).read_text(encoding="utf-8"))
    V, P, C = grid(dens, VEHICLES), grid(dens, ["Pedestrian"]), grid(dens, ["Cyclist"])
    crossings = find_crossings(V, P, C, osm, args.min_ped_s, args.min_veh_s, args.min_area_m2)
    junction = find_arms(V, osm, args.core_radius_m)
    zones = {"schema": 1, "source": f"density_{args.variant}.parquet + {Path(args.map).name}",
             "parameters": {k: getattr(args, k) for k in ("variant", "min_ped_s", "min_veh_s", "min_area_m2", "core_radius_m")},
             "junction": junction, "crossings": crossings}
    out = Path(args.out)
    (out / "zones.json").write_text(json.dumps(zones, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"junction center {junction['center']}, arms: " + ", ".join(f"{a['id']} ({a['road']})" for a in junction["arms"]))
    for c in crossings:
        print(f"  {c['id']}: {c['area_m2']} m2 at {c['center']}, road {c['road']}, ped dwell {c['ped_dwell_s']:.0f} s, "
              f"OSM crossing {c['osm_crossing_node']} ({c['osm_crossing_distance_m']} m)")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 9))
    ext = [-LIM, LIM, -LIM, LIM]
    ax.imshow(np.log1p(V), origin="lower", extent=ext, cmap="Greys")
    ax.imshow(np.ma.masked_less(np.log1p(P), 2), origin="lower", extent=ext, cmap="autumn", alpha=0.5)
    cx, cy = junction["center"]
    ax.add_patch(plt.Circle((cx, cy), args.core_radius_m, fill=False, color="blue", ls="--"))
    for a in junction["arms"]:
        for b in (a["from_deg"],):
            ax.plot([cx, cx + 60 * math.cos(math.radians(b))], [cy, cy + 60 * math.sin(math.radians(b))], "b:", lw=1)
        tx, ty = cx + 30 * math.cos(math.radians(a["sensor_angle_deg"])), cy + 30 * math.sin(math.radians(a["sensor_angle_deg"]))
        ax.text(tx, ty, f"{a['id']} ({a['bearing_deg']:.0f} deg)\n{a['road'] or ''}", color="blue", fontsize=10, ha="center", weight="bold")
    for c in crossings:
        poly = np.array(c["polygon"] + [c["polygon"][0]])
        ax.plot(poly[:, 0], poly[:, 1], "-", color="lime", lw=2)
        ax.text(c["center"][0], c["center"][1], c["id"], color="darkgreen", fontsize=11, weight="bold")
    for c in osm["crossing_nodes"]:
        ax.plot(c["x"], c["y"], "c^", ms=8)
    ax.set(xlim=(-LIM, LIM), ylim=(-LIM, LIM), aspect="equal", xlabel="x (m)", ylabel="y (m)",
           title="K305 zones: crossings (green), arms (blue), OSM crossing nodes (cyan)")
    plt.tight_layout()
    plt.savefig(out / "zones_check.png", dpi=100)
    print(f"written {out / 'zones.json'} and zones_check.png")


if __name__ == "__main__":
    main()

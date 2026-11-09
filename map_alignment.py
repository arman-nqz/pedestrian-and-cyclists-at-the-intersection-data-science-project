#!/usr/bin/env python
"""Align an OpenStreetMap extract of K305 to the LiDAR sensor coordinates.

The sensor reports positions in meters in its own frame (origin at the sensor, unknown rotation).
OSM has latitude / longitude. We look for the rotation + shift (and mirror, if needed) that puts the
OSM roads where the recorded vehicles drive, then check the result independently with pedestrians
(footways and crossings).

    python map_alignment.py --osm map.osm --data-dir <folder with the 288 json> --out dashboard/config

Writes in --out:
    k305_map.json       transform + OSM features (roads, footways, crossings, signals) in sensor meters
    alignment_check.png overlay of the map on vehicle and pedestrian density

Method: coarse search over rotation (1 degree steps, FFT cross-correlation over shifts, 1 m cells), then
a fine local search (0.25 degree, 0.5 m) on the road points. Needs numpy, matplotlib.
"""
import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

MOTOR_HIGHWAYS = {"secondary", "trunk", "trunk_link", "residential", "service", "primary", "tertiary"}
PED_HIGHWAYS = {"footway", "path", "steps", "cycleway", "pedestrian"}
HALF = 52          # half size of the sensor window in meters (sensor range is about 45 m)
CELL = 1.0         # coarse cell size in meters


# ---------------------------------------------------------------- OSM
def parse_osm(path):
    root = ET.parse(path).getroot()
    nodes = {}
    for n in root.findall("node"):
        tags = {t.get("k"): t.get("v") for t in n.findall("tag")}
        nodes[n.get("id")] = (float(n.get("lat")), float(n.get("lon")), tags)
    ways = []
    for w in root.findall("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        refs = [nd.get("ref") for nd in w.findall("nd") if nd.get("ref") in nodes]
        if len(refs) >= 2:
            ways.append({"id": w.get("id"), "tags": tags, "refs": refs})
    return nodes, ways


def to_local(lat, lon, lat0, lon0):
    """Equirectangular projection: east / north meters around (lat0, lon0)."""
    x = (lon - lon0) * 111320.0 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 110540.0
    return x, y


def way_xy(way, nodes, lat0, lon0):
    return np.array([to_local(nodes[r][0], nodes[r][1], lat0, lon0) for r in way["refs"]])


def densify(poly, step=0.5):
    pts = []
    for a, b in zip(poly[:-1], poly[1:]):
        n = max(1, int(np.hypot(*(b - a)) / step))
        pts.append(a + (b - a) * (np.arange(n)[:, None] / n))
    pts.append(poly[-1:])
    return np.vstack(pts)


# ---------------------------------------------------------------- sensor density
def load_density(data_dir, every=6, min_speed=0.3):
    """Position histograms (1 m cells) for vehicles and pedestrians from every n-th file."""
    files = sorted(Path(data_dir).glob("*.json"))[::every]
    size = int(2 * HALF / CELL)
    veh = np.zeros((size, size))
    ped = np.zeros((size, size))
    vel = np.zeros((2, size, size))   # sum of vehicle velocities (fast vehicles only)
    vcount = np.zeros((size, size))
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        for frame in data["frames"]:
            for o in frame["objects"]:
                p, v = o["bounding_box"]["position"], o["velocity"]
                if np.hypot(v["x"], v["y"]) < min_speed:
                    continue  # ignore standing objects: ghosts and queues would blur the road shape
                i, j = int((p["x"] + HALF) / CELL), int((p["y"] + HALF) / CELL)
                if 0 <= i < size and 0 <= j < size:
                    if o["class_name"] == "Pedestrian":
                        ped[j, i] += 1
                    elif o["class_name"] in ("Car", "Van", "Truck", "Bus"):
                        veh[j, i] += 1
                        if np.hypot(v["x"], v["y"]) > 2.0:
                            vel[0, j, i] += v["x"]
                            vel[1, j, i] += v["y"]
                            vcount[j, i] += 1
    return veh, ped, (vel, vcount), len(files)


def blur(a, sigma):
    """Gaussian blur with numpy only."""
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, a)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, a)


# ---------------------------------------------------------------- alignment
def rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def raster(points, n, cell=CELL):
    """Points (meters, canvas centered at 0) -> n x n count image."""
    img = np.zeros((n, n))
    i = np.floor(points[:, 0] / cell + n / 2).astype(int)
    j = np.floor(points[:, 1] / cell + n / 2).astype(int)
    ok = (i >= 0) & (i < n) & (j >= 0) & (j < n)
    np.add.at(img, (j[ok], i[ok]), 1)
    return img


def coarse_search(road_pts, dens, mirror, n=640):
    """For each rotation find the best shift by FFT cross-correlation. Returns list of (score, deg, shift)."""
    d = np.log1p(dens)
    d = blur(d, 1.5)
    d = d - d.mean()
    pad = np.zeros((n, n))
    h = d.shape[0]
    a = n // 2 - h // 2
    pad[a:a + h, a:a + h] = d
    fd = np.conj(np.fft.rfft2(pad))
    pts = road_pts * np.array([1.0, -1.0 if mirror else 1.0])
    res = []
    for deg in range(0, 360):
        q = pts @ rot(-deg).T  # ENU -> sensor axes (shift still unknown)
        m = blur(raster(q, n), 2.0)
        corr = np.fft.irfft2(fd * np.fft.rfft2(m), s=(n, n))
        k = np.unravel_index(np.argmax(corr), corr.shape)
        # corr[k] = sum_q D(q) M(q + s)  with s in cells relative to the centered canvases
        sy, sx = k[0] if k[0] < n // 2 else k[0] - n, k[1] if k[1] < n // 2 else k[1] - n
        # a mask point at position m lands on density position q = m - s, so the sensor shift is -s
        res.append((float(corr[k]), deg, -np.array([sx, sy]) * CELL))
    return sorted(res, key=lambda r: -r[0])


def sample(img, pts):
    """Bilinear sample of a 1 m density image at sensor points (meters)."""
    size = img.shape[0]
    u = (pts[:, 0] + HALF) / CELL - 0.5
    v = (pts[:, 1] + HALF) / CELL - 0.5
    ok = (u >= 0) & (u < size - 1) & (v >= 0) & (v < size - 1)
    out = np.full(len(pts), np.nan)
    u, v = u[ok], v[ok]
    i, j = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i, v - j
    out[ok] = (img[j, i] * (1 - fu) * (1 - fv) + img[j, i + 1] * fu * (1 - fv)
               + img[j + 1, i] * (1 - fu) * fv + img[j + 1, i + 1] * fu * fv)
    return out


def to_sensor(enu, deg, shift, mirror):
    """ENU meters -> sensor meters."""
    p = enu * np.array([1.0, -1.0 if mirror else 1.0])
    return p @ rot(-deg).T + shift


def refine(road_pts, dens, deg0, shift0, mirror):
    d = blur(np.log1p(dens), 1.5)
    d = d - d.mean()
    best = (-1e9, deg0, shift0)
    for dd in np.arange(-4, 4.01, 0.25):
        for sx in np.arange(-6, 6.01, 0.5):
            for sy in np.arange(-6, 6.01, 0.5):
                sh = shift0 + np.array([sx, sy])
                s = sample(d, to_sensor(road_pts, deg0 + dd, sh, mirror))
                if np.isfinite(s).sum() < 50:
                    continue
                sc = float(np.nansum(s)) / len(road_pts)  # road outside the sensor window counts as 0, not as a free pass
                if sc > best[0]:
                    best = (sc, deg0 + dd, sh)
    return best


def sensor_handedness(velfield):
    """Is the sensor frame mirrored compared with the real world? Uses right-hand traffic (Germany).

    Take the main flow axis. Vehicles moving along +axis must be on the right of vehicles moving along -axis
    when the frame is a normal (right-handed) map. Returns (mirrored, lateral_gap_m, axis_deg).
    """
    vel, vcount = velfield
    size = vcount.shape[0]
    ii, jj = np.meshgrid(np.arange(size), np.arange(size))
    X, Y = (ii + 0.5) * CELL - HALF, (jj + 0.5) * CELL - HALF
    m = vcount > 5
    vx = np.where(m, vel[0] / np.maximum(vcount, 1), 0)
    vy = np.where(m, vel[1] / np.maximum(vcount, 1), 0)
    ang = np.degrees(np.arctan2(vy, vx))[m] % 180
    h, e = np.histogram(ang, bins=36, range=(0, 180), weights=vcount[m])
    axis_deg = float(e[np.argmax(h)] + 2.5)
    u = np.array([np.cos(np.radians(axis_deg)), np.sin(np.radians(axis_deg))])
    nrm = np.array([-u[1], u[0]])  # left normal
    cosang = (vx * u[0] + vy * u[1]) / np.maximum(np.hypot(vx, vy), 1e-9)
    lat = X * nrm[0] + Y * nrm[1]
    fwd, bwd = m & (cosang > 0.9), m & (cosang < -0.9)
    lf = np.average(lat[fwd], weights=vcount[fwd])
    lb = np.average(lat[bwd], weights=vcount[bwd])
    return bool(lf > lb), float(lb - lf), axis_deg


def oneway_direction_check(ways, nodes, lat0, lon0, deg, shift, mirror, velfield):
    """OSM oneway=yes roads: does the recorded vehicle velocity point the way the road is drawn?

    Independent check of the whole transform (rotation, mirror, shift). Returns (matching points, points tested).
    """
    vel, vcount = velfield
    tot = agree = 0
    for w in ways:
        if w["tags"].get("oneway") not in ("yes", "1") or w["tags"].get("highway") not in MOTOR_HIGHWAYS:
            continue
        q = densify(to_sensor(way_xy(w, nodes, lat0, lon0), deg, shift, mirror), 1.0)
        dirs = np.gradient(q, axis=0)
        i = np.floor((q[:, 0] + HALF) / CELL).astype(int)
        j = np.floor((q[:, 1] + HALF) / CELL).astype(int)
        ok = (i >= 0) & (i < vcount.shape[1]) & (j >= 0) & (j < vcount.shape[0])
        cnt = np.zeros(len(q))
        cnt[ok] = vcount[j[ok], i[ok]]
        sel = cnt > 5
        if sel.sum() < 3:
            continue
        v = np.stack([vel[0][j[sel], i[sel]], vel[1][j[sel], i[sel]]], axis=1) / cnt[sel][:, None]
        d = dirs[sel] / np.maximum(np.hypot(dirs[sel][:, 0], dirs[sel][:, 1]), 1e-9)[:, None]
        cos = (v * d).sum(1) / np.maximum(np.hypot(v[:, 0], v[:, 1]), 1e-9)
        tot += int(sel.sum())
        agree += int((cos > 0).sum())
    return agree, tot


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", default="dashboard/config")
    ap.add_argument("--every", type=int, default=6, help="use every n-th json file for the density")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    nodes, ways = parse_osm(args.osm)
    signals = [(v[0], v[1]) for v in nodes.values() if v[2].get("highway") == "traffic_signals"]
    lat0 = float(np.mean([s[0] for s in signals]))
    lon0 = float(np.mean([s[1] for s in signals]))
    print(f"{len(nodes)} nodes, {len(ways)} ways; junction center {lat0:.6f}, {lon0:.6f} ({len(signals)} signal nodes)")

    motor = [w for w in ways if w["tags"].get("highway") in MOTOR_HIGHWAYS]
    road_pts = np.vstack([densify(way_xy(w, nodes, lat0, lon0)) for w in motor])
    # use only road points within 150 m of the junction: the sensor sees about 45 m
    road_pts = road_pts[np.hypot(road_pts[:, 0], road_pts[:, 1]) < 150]
    print(f"{len(road_pts):,} road points")

    print("loading density ...")
    veh, ped, velfield, nfiles = load_density(args.data_dir, args.every)
    print(f"files used: {nfiles}; vehicle detections {int(veh.sum()):,}, pedestrian {int(ped.sum()):,}")

    mirrored, gap, axis_deg = sensor_handedness(velfield)
    print(f"handedness test: flow axis {axis_deg:.0f} deg, flow along +axis is {gap:.1f} m to the {'left' if mirrored else 'right'} "
          f"of the opposite flow -> sensor frame {'IS' if mirrored else 'is NOT'} mirrored (right-hand traffic assumed)")
    hyps = []
    for mirror in (False, True):
        sc, deg, sh = coarse_search(road_pts, veh, mirror)[0]
        fine_sc, deg, sh = refine(road_pts, veh, deg, sh, mirror)
        ag, tot = oneway_direction_check(ways, nodes, lat0, lon0, deg, sh, mirror, velfield)
        hyps.append({"mirror": mirror, "deg": deg, "shift": sh, "coarse_score": sc, "road_score": fine_sc, "oneway_match": [ag, tot]})
        print(f"mirror={mirror}: rotation {deg:.2f} deg, shift {sh.round(2)} m, road score {fine_sc:.3f}, "
              f"one-way roads: vehicle direction matches at {ag}/{tot} points")
    best = next(h for h in hyps if h["mirror"] == mirrored)
    deg, sh, mirror, fine_sc = best["deg"], best["shift"], best["mirror"], best["road_score"]
    print(f"chosen (by handedness): mirror={mirror}, rotation {deg:.2f} deg, shift {sh.round(2)} m")

    # independent check: pedestrians should be on footways and crossings, not on random lines
    ped_ways = [w for w in ways if w["tags"].get("highway") in PED_HIGHWAYS or w["tags"].get("footway") == "crossing"]
    ped_pts = np.vstack([densify(way_xy(w, nodes, lat0, lon0)) for w in ped_ways])
    dped = blur(np.log1p(ped), 1.5)
    s_ped = sample(dped, to_sensor(ped_pts, deg, sh, mirror))
    s_ped = s_ped[np.isfinite(s_ped)]
    rng = np.random.default_rng(0)
    rand = sample(dped, rng.uniform(-HALF + 3, HALF - 3, size=(5000, 2)))
    check = {"footway_points_in_range": int(len(s_ped)),
             "mean_log_ped_density_on_footways": round(float(s_ped.mean()), 3),
             "mean_log_ped_density_random_points": round(float(np.nanmean(rand)), 3)}
    print("pedestrian check:", check)

    # features in sensor meters
    def feat(w):
        xy = to_sensor(way_xy(w, nodes, lat0, lon0), deg, sh, mirror)
        return {"id": w["id"], "name": w["tags"].get("name"), "highway": w["tags"].get("highway"),
                "footway": w["tags"].get("footway"), "oneway": w["tags"].get("oneway"),
                "xy": np.round(xy, 2).tolist()}

    def node_feat(i, v):
        xy = to_sensor(np.array([to_local(v[0], v[1], lat0, lon0)]), deg, sh, mirror)[0]
        return {"id": i, "x": round(float(xy[0]), 2), "y": round(float(xy[1]), 2), "tags": v[2]}

    keep = lambda f: any(np.hypot(*p) < 80 for p in f["xy"])
    result = {
        "schema": 1,
        "osm_file": Path(args.osm).name,
        "origin": {"lat": lat0, "lon": lon0, "note": "junction center = mean of the traffic signal nodes"},
        "transform_enu_to_sensor": {"rotation_deg": round(float(deg), 3), "shift_m": np.round(sh, 3).tolist(), "mirror": mirror,
                                    "formula": "q = R(-rotation) @ (x_east, +-y_north) + shift"},
        "quality": {"fine_road_score": round(float(fine_sc), 3), **check, "density_files": nfiles,
                    "hypotheses": [{"mirror": h["mirror"], "rotation_deg": round(float(h["deg"]), 3), "shift_m": np.round(h["shift"], 3).tolist(),
                                    "road_score": round(float(h["road_score"]), 3), "oneway_match": h["oneway_match"],
                                    } for h in hyps],
                    "handedness": {"flow_axis_deg": round(axis_deg, 1), "lateral_gap_m": round(gap, 2), "mirrored": mirrored}},
        "roads": [f for f in map(feat, motor) if keep(f)],
        "footways": [f for f in map(feat, ped_ways) if keep(f)],
        "crossing_nodes": [node_feat(i, v) for i, v in nodes.items() if v[2].get("highway") == "crossing"],
        "signal_nodes": [node_feat(i, v) for i, v in nodes.items() if v[2].get("highway") == "traffic_signals"],
    }
    result["crossing_nodes"] = [c for c in result["crossing_nodes"] if np.hypot(c["x"], c["y"]) < 80]
    result["signal_nodes"] = [c for c in result["signal_nodes"] if np.hypot(c["x"], c["y"]) < 80]
    (out / "k305_map.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

    # picture
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(15, 7.5))
    ext = [-HALF, HALF, -HALF, HALF]
    for ax, dens, title, color_ways in [(axes[0], veh, "Vehicle density + OSM roads", result["roads"]),
                                        (axes[1], ped, "Pedestrian density + OSM footways, crossings, signals", result["footways"])]:
        ax.imshow(np.log1p(dens), origin="lower", extent=ext, cmap="magma")
        for f in color_ways:
            xy = np.array(f["xy"])
            ax.plot(xy[:, 0], xy[:, 1], color="cyan", lw=1.2, alpha=0.9)
        ax.set(title=title, xlim=(-46, 46), ylim=(-46, 46), aspect="equal", xlabel="x (m)", ylabel="y (m)")
    for c in result["crossing_nodes"]:
        axes[1].plot(c["x"], c["y"], "o", color="lime", ms=7, mec="k")
    for c in result["signal_nodes"]:
        axes[1].plot(c["x"], c["y"], "s", color="yellow", ms=7, mec="k")
    for f in result["roads"]:
        if f["name"]:
            xy = np.array(f["xy"])
            inside = xy[np.hypot(xy[:, 0], xy[:, 1]) < 44]
            if len(inside):
                axes[0].text(*inside[len(inside) // 2], f["name"], color="white", fontsize=7)
    fig.suptitle(f"OSM aligned to sensor frame: rotation {deg:.1f} deg, shift {sh.round(1)} m, mirror={mirror}")
    plt.tight_layout()
    plt.savefig(out / "alignment_check.png", dpi=110)
    print(f"written {out / 'k305_map.json'} and alignment_check.png")


if __name__ == "__main__":
    main()

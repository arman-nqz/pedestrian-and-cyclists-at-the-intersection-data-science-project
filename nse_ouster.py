"""Compare NSE and Ouster BlueCity on the same time window.

1. Put Ouster positions into the NSE frame (estimate_transform):
   - every pair of MOVING vehicles seen by both systems at the same moment votes for the shift that would put one on
     top of the other; only the right rotation makes the votes pile up (Hough voting over 360 deg),
   - then a rigid least-squares fit (Kabsch) on mutual nearest neighbours refines it.
   Clocks are not adjusted: a cross-correlation of moving-vehicle counts per second gave 0 s offset (W1).
2. Match detections frame by frame (match_frames): for each NSE frame take the nearest Ouster frame (<= 60 ms),
   move Ouster objects by their velocity to the NSE time, and pair mutual nearest neighbours within RADIUS_M,
   whatever their class.
3. Only the area both systems cover is compared (common_mask).
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

VEHICLES = ["Car", "Van", "Truck", "Bus"]
GROUPS = ["Pedestrian", "Cyclist", "Motorcycle", "Vehicle", "Unknown"]
RADIUS_M = 1.5
LIM = 46.0


def group(cls):
    """Class -> comparison group (both systems)."""
    cls = pd.Series(cls).astype(str)
    return np.where(cls.isin(VEHICLES), "Vehicle", np.where(cls.isin(GROUPS), cls, "Unknown"))


def rot(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[c, -s], [s, c]])


def to_nse(o, tr):
    """Ouster rows -> NSE frame (positions, velocities, yaw). tr = {"rotation_deg", "shift_m"}"""
    R = rot(-tr["rotation_deg"])
    out = o.copy()
    p = o[["x", "y"]].to_numpy(float) @ R.T + np.asarray(tr["shift_m"])
    v = o[["vx", "vy"]].to_numpy(float) @ R.T
    out["x"], out["y"], out["vx"], out["vy"] = p[:, 0], p[:, 1], v[:, 0], v[:, 1]
    out["yaw"] = (o["yaw"].to_numpy(float) - np.radians(tr["rotation_deg"]) + np.pi) % (2 * np.pi) - np.pi
    return out


def _paired_frames(n, o, min_speed=None, classes=None, step=1, max_dt=0.06):
    """[(t, nse rows, ouster rows moved to time t)] for NSE frames that have an Ouster frame within max_dt."""
    if classes is not None:
        n, o = n[n["class_name"].isin(classes)], o[o["class_name"].isin(classes)]
    if min_speed is not None:
        n = n[np.hypot(n["vx"], n["vy"]) > min_speed]
        o = o[np.hypot(o["vx"], o["vy"]) > min_speed]
    ot = np.unique(o["t"].to_numpy())
    if len(ot) == 0:
        return []
    og = dict(tuple(o.groupby("t")))
    out = []
    for k, (t, fr) in enumerate(n.groupby("t")):
        if k % step:
            continue
        j = np.searchsorted(ot, t)
        cand = [ot[x] for x in (j - 1, j) if 0 <= x < len(ot)]
        to = min(cand, key=lambda x: abs(x - t))
        if abs(to - t) > max_dt:
            continue
        of = og[to].copy()
        of["x"] = of["x"] + (t - to) * of["vx"]
        of["y"] = of["y"] + (t - to) * of["vy"]
        out.append((t, fr, of))
    return out


def _kabsch(A, B):
    ca, cb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((B - cb).T @ (A - ca))
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[1] *= -1
        R = Vt.T @ U.T
    return R, ca - R @ cb


def _mutual_nn(pa, pb, radius):
    d = np.hypot(pa[:, None, 0] - pb[None, :, 0], pa[:, None, 1] - pb[None, :, 1])
    a = d.argmin(1)
    ok = (d[np.arange(len(pa)), a] < radius) & (d.argmin(0)[a] == np.arange(len(pa)))
    return np.flatnonzero(ok), a[ok], d[np.arange(len(pa)), a][ok]


def estimate_transform(n, o, step=3):
    """Ouster -> NSE rigid transform from moving vehicles. Returns dict with rotation, shift and quality numbers."""
    frames = [(fr[["x", "y"]].to_numpy(float), of[["x", "y"]].to_numpy(float))
              for _, fr, of in _paired_frames(n, o, min_speed=3, classes=VEHICLES, step=step)]

    def votes(deg, binm, lim=80):
        R = rot(-deg)
        v = np.vstack([(pn[:, None, :] - (po @ R.T)[None, :, :]).reshape(-1, 2) for pn, po in frames])
        v = v[(np.abs(v) < lim).all(1)]
        nb = int(2 * lim / binm)
        H, xe, ye = np.histogram2d(v[:, 0], v[:, 1], bins=nb, range=[[-lim, lim], [-lim, lim]])
        Hs = sliding_window_view(np.pad(H, 1), (3, 3)).sum(axis=(2, 3))
        i, j = np.unravel_index(np.argmax(Hs), Hs.shape)
        return float(Hs[i, j]), np.array([xe[i] + binm / 2, ye[j] + binm / 2])

    coarse = sorted(((*votes(d, 0.5), d) for d in range(360)), key=lambda r: -r[0])
    c_best, sh, deg = coarse[0]
    second = next(r for r in coarse if min(abs(r[2] - deg), 360 - abs(r[2] - deg)) > 10)
    fine = max(((*votes(d, 0.25), d) for d in np.arange(deg - 2, deg + 2.01, 0.1)), key=lambda r: r[0])
    _, sh, deg = fine
    # least-squares refinement on mutual nearest neighbours (all vehicles, every 2nd frame)
    for radius in (2.0, 1.5, 1.0, 1.0):
        A, B = [], []
        tr = {"rotation_deg": deg, "shift_m": sh}
        for _, fr, of in _paired_frames(n, to_nse(o, tr), classes=VEHICLES, step=2):
            pa, pb = fr[["x", "y"]].to_numpy(float), of[["x", "y"]].to_numpy(float)
            ia, ib, _ = _mutual_nn(pa, pb, radius)
            A.append(pa[ia])
            B.append(pb[ib])
        A, B = np.vstack(A), np.vstack(B)
        R, t = _kabsch(A, B)
        deg, sh = deg - np.degrees(np.arctan2(R[1, 0], R[0, 0])), R @ sh + t
    resid = np.hypot(*(A - (B @ R.T + t)).T)
    return {"rotation_deg": round(float(deg), 4), "shift_m": [round(float(sh[0]), 4), round(float(sh[1]), 4)],
            "vote_peak_ratio": round(c_best / max(second[0], 1), 2), "refine_pairs": int(len(A)),
            "median_residual_m": round(float(np.median(resid)), 3)}


def common_mask(n, o_nse, cell=1.0, min_rows=20):
    """Grid of cells where both systems have at least min_rows detections in the window (any class)."""
    size = int(2 * LIM / cell)

    def grid(d):
        g = np.zeros((size, size))
        i = np.floor((d["x"].to_numpy() + LIM) / cell).astype(int)
        j = np.floor((d["y"].to_numpy() + LIM) / cell).astype(int)
        ok = (i >= 0) & (i < size) & (j >= 0) & (j < size)
        np.add.at(g, (j[ok], i[ok]), 1)
        return g

    return (grid(n) >= min_rows) & (grid(o_nse) >= min_rows)


def in_mask(d, mask, cell=1.0):
    size = mask.shape[0]
    i = np.floor((d["x"].to_numpy() + LIM) / cell).astype(int)
    j = np.floor((d["y"].to_numpy() + LIM) / cell).astype(int)
    ok = (i >= 0) & (i < size) & (j >= 0) & (j < size)
    out = np.zeros(len(d), bool)
    out[ok] = mask[j[ok], i[ok]]
    return out


def match_frames(n, o_nse, radius=RADIUS_M, step=1):
    """Per-detection match table. One row per NSE detection and per unmatched Ouster detection.

    columns: t, nse_group, ouster_group ('none' if unmatched), dist_m, x, y, nse_speed, ouster_speed
    """
    rows = []
    for t, fr, of in _paired_frames(n, o_nse, step=step):
        pa, pb = fr[["x", "y"]].to_numpy(float), of[["x", "y"]].to_numpy(float)
        ga, gb = group(fr["class_name"].to_numpy()), group(of["class_name"].to_numpy())
        sa, sb = np.hypot(fr["vx"], fr["vy"]).to_numpy(), np.hypot(of["vx"], of["vy"]).to_numpy()
        ia, ib, dist = _mutual_nn(pa, pb, radius) if len(pa) and len(pb) else (np.array([], int),) * 2 + (np.array([]),)
        matched_a = np.zeros(len(pa), bool)
        matched_a[ia] = True
        matched_b = np.zeros(len(pb), bool)
        matched_b[ib] = True
        for a, b, d in zip(ia, ib, dist):
            rows.append((t, ga[a], gb[b], d, pa[a, 0], pa[a, 1], sa[a], sb[b]))
        for a in np.flatnonzero(~matched_a):
            rows.append((t, ga[a], "none", np.nan, pa[a, 0], pa[a, 1], sa[a], np.nan))
        for b in np.flatnonzero(~matched_b):
            rows.append((t, "none", gb[b], np.nan, pb[b, 0], pb[b, 1], np.nan, sb[b]))
    return pd.DataFrame(rows, columns=["t", "nse_group", "ouster_group", "dist_m", "x", "y", "nse_speed", "ouster_speed"])


def summarize(matches, n_frames):
    """Per group: detections per frame in each system, share matched, same-group share, median distance."""
    out = []
    for g in GROUPS:
        nse = matches[matches["nse_group"] == g]
        ous = matches[matches["ouster_group"] == g]
        both = nse[nse["ouster_group"] != "none"]
        out.append({
            "group": g,
            "nse_per_frame": round(len(nse) / n_frames, 2),
            "ouster_per_frame": round(len(ous) / n_frames, 2),
            "nse_matched_share": round(len(both) / len(nse), 3) if len(nse) else None,
            "ouster_matched_share": round((ous["nse_group"] != "none").mean(), 3) if len(ous) else None,
            "same_group_share": round((both["ouster_group"] == g).mean(), 3) if len(both) else None,
            "median_dist_m": round(float(both["dist_m"].median()), 3) if len(both) else None,
        })
    return pd.DataFrame(out)

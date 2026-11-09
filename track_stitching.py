"""Join track fragments that the sensor split into several ids.

The LiDAR tracker sometimes loses an object and gives it a new `track_id` when it
reappears. `stitch_tracks()` finds track ends and starts that probably belong to the
same object and gives them one id.

Input: a DataFrame with columns
    t (epoch seconds), track_id, class_name, x, y, vx, vy, length, width
Output: the same rows plus
    trk        id of the segment (a track split at gaps longer than GAP_S)
    trk_s      id after stitching (use this as the track id)
    class_final  majority class over the stitched track

Method (greedy mutual-best assignment, not a global Hungarian solve):
  1. split tracks at time gaps > GAP_S                    (Liu, Saunier, Bilodeau 2025)
  2. for each segment end, look for segment starts that begin within MAX_GAP_S seconds
     (STATIC_GAP_S if the object was almost standing still)
  3. gate: the start must be near end position + velocity * gap
  4. cost = position error / tolerance + class penalty + size difference
  5. keep pairs that choose each other with a clear margin; skip joins at the sensor edge
Validated with `synthetic_cut_test()` (cut holes into long tracks, see how many are repaired).
"""
import numpy as np
import pandas as pd

GAP_S = 1.0            # split tracks at gaps longer than this
MAX_GAP_S = 3.0        # longest gap to bridge for a moving object
STATIC_GAP_S = 10.0    # longest gap for an (almost) standing object
STATIC_SPEED = 0.3     # m/s, below this the object counts as standing
BASE_TOL_M = 1.5       # allowed position error at zero gap
SPEED_TOL = 0.3        # extra tolerance as a share of the distance traveled during the gap
AMBIG_MARGIN = 0.2     # best option must beat the second best by this much (cost units)

SOFT_PAIRS = {frozenset(p) for p in [("Pedestrian", "Cyclist"), ("Cyclist", "Motorcycle"), ("Car", "Van"),
                                     ("Van", "Truck"), ("Truck", "Bus"), ("Car", "Truck")]}


def class_penalty(a, b):
    if a == b:
        return 0.0
    return 0.5 if frozenset((a, b)) in SOFT_PAIRS else np.inf


def segment_tracks(df, gap_s=GAP_S):
    """Split tracks at time gaps; add `trk` (segment id) and majority-vote `class_final`."""
    d = df.sort_values(["track_id", "t"], kind="stable").reset_index(drop=True)
    gap = d.groupby("track_id")["t"].diff() > gap_s
    d["seg"] = gap.groupby(d["track_id"]).cumsum().astype("int64")
    d["trk"] = d["track_id"].astype("int64") * 1000 + d["seg"]
    d["class_name"] = d["class_name"].astype(str)
    counts = d.groupby(["trk", "class_name"]).size().reset_index(name="n")
    top = counts.sort_values("n").groupby("trk").tail(1).set_index("trk")["class_name"]
    d["class_final"] = d["trk"].map(top)
    return d


def build_endpoints(seg):
    """One row per segment: where and when it starts and ends."""
    g = seg.groupby("trk", sort=False)
    first = g[["t", "x", "y", "vx", "vy"]].first()
    last = g[["t", "x", "y", "vx", "vy"]].last()
    return pd.DataFrame({
        "t_start": first["t"], "sx": first["x"], "sy": first["y"],
        "t_end": last["t"], "ex": last["x"], "ey": last["y"], "evx": last["vx"], "evy": last["vy"],
        "cls": g["class_final"].first(),
        "length": g["length"].median(), "width": g["width"].median(),
        "frames": g.size(),
    })


def stitch(ep, edge_r, max_gap_s=MAX_GAP_S, static_gap_s=STATIC_GAP_S, base_tol_m=BASE_TOL_M, speed_tol=SPEED_TOL):
    """Returns (links, pairs). links: accepted joins a -> b. pairs: all gated candidates with cost."""
    ep = ep.sort_values("t_start")
    keys = ep.index.to_numpy()
    t_start = ep["t_start"].to_numpy()
    sx, sy = ep["sx"].to_numpy(), ep["sy"].to_numpy()
    t_end, ex, ey = ep["t_end"].to_numpy(), ep["ex"].to_numpy(), ep["ey"].to_numpy()
    evx, evy = ep["evx"].to_numpy(), ep["evy"].to_numpy()
    cls = ep["cls"].to_numpy()
    ln, wd = ep["length"].to_numpy(), ep["width"].to_numpy()
    s_edge = np.hypot(sx, sy) > edge_r
    e_edge = np.hypot(ex, ey) > edge_r

    out = []
    for i in range(len(ep)):
        if e_edge[i]:
            continue
        speed = float(np.hypot(evx[i], evy[i]))
        gap_max = static_gap_s if speed < STATIC_SPEED else max_gap_s
        lo = np.searchsorted(t_start, t_end[i], side="right")
        hi = np.searchsorted(t_start, t_end[i] + gap_max, side="right")
        if hi <= lo:
            continue
        j = np.arange(lo, hi)
        j = j[~s_edge[j]]
        if j.size == 0:
            continue
        gap = t_start[j] - t_end[i]
        px, py = ex[i] + evx[i] * gap, ey[i] + evy[i] * gap
        err = np.hypot(sx[j] - px, sy[j] - py)
        tol = base_tol_m + speed_tol * speed * gap
        ok = err <= tol
        if not ok.any():
            continue
        j, gap, err, tol = j[ok], gap[ok], err[ok], tol[ok]
        pen = np.array([class_penalty(cls[i], cls[k]) for k in j])
        size = np.minimum(1.0, (np.abs(ln[j] - ln[i]) / np.maximum(ln[j], ln[i]) + np.abs(wd[j] - wd[i]) / np.maximum(wd[j], wd[i])) / 2)
        cost = err / tol + pen + size
        good = np.isfinite(cost)
        for k, g_, e_, c_ in zip(j[good], gap[good], err[good], cost[good]):
            out.append((keys[i], keys[k], float(g_), float(e_), float(c_)))
    pairs = pd.DataFrame(out, columns=["a", "b", "gap_s", "err_m", "cost"])
    if pairs.empty:
        return pairs.copy(), pairs

    def best_and_margin(p, by):
        p = p.sort_values([by, "cost"])
        rank = p.groupby(by).cumcount()
        second = p.groupby(by)["cost"].shift(-1)
        best = p[rank == 0].copy()
        best["margin"] = (second[rank == 0] - best["cost"]).fillna(np.inf)
        return best.set_index(by)

    best_a = best_and_margin(pairs, "a")
    best_b = best_and_margin(pairs, "b")
    cand = pairs.merge(best_a[["b", "margin"]].reset_index().rename(columns={"b": "b_best", "margin": "margin_a"}), on="a")
    cand = cand[cand["b"] == cand["b_best"]]
    cand = cand.merge(best_b[["a", "margin"]].reset_index().rename(columns={"a": "a_best", "margin": "margin_b"}), on="b")
    links = cand[(cand["a"] == cand["a_best"]) & (cand["margin_a"] >= AMBIG_MARGIN) & (cand["margin_b"] >= AMBIG_MARGIN)]
    return links[["a", "b", "gap_s", "err_m", "cost"]].reset_index(drop=True), pairs


def link_ids(ep, links):
    """New id per segment: follow links in time order so chains A->B->C share one id."""
    prev = dict(zip(links["b"], links["a"]))
    sid = {}
    for k in ep.sort_values("t_start").index:
        sid[k] = sid[prev[k]] if k in prev else k
    return pd.Series(sid)


def stitch_tracks(df, edge_quantile=0.999, edge_factor=0.9, return_details=False, **stitch_kw):
    """Segment, stitch and return (df with trk / trk_s / class_final, links).

    With return_details=True it returns (df, links, endpoints table, edge radius) instead.
    """
    seg = segment_tracks(df)
    ep = build_endpoints(seg)
    radius = np.hypot(seg["x"].to_numpy()[::50], seg["y"].to_numpy()[::50])
    edge_r = edge_factor * float(np.quantile(radius, edge_quantile))
    links, _ = stitch(ep, edge_r, **stitch_kw)
    sid = link_ids(ep, links)
    seg["trk_s"] = seg["trk"].map(sid)
    seg["class_seg"] = seg["class_final"]  # majority class per segment, before stitching
    # class per stitched track (majority vote over rows)
    counts = seg.groupby(["trk_s", "class_name"]).size().reset_index(name="n")
    top = counts.sort_values("n").groupby("trk_s").tail(1).set_index("trk_s")["class_name"]
    seg["class_final"] = seg["trk_s"].map(top)
    if return_details:
        return seg, links, ep, edge_r
    return seg, links


def synthetic_cut_test(seg, ep, edge_r, n=3000, seed=0):
    """Cut 0.5-3 s holes into long real tracks, give the second half a new id, and see if stitch() repairs them."""
    rng = np.random.default_rng(seed)
    pool = ep[(ep["frames"] >= 60) & (np.hypot(ep["ex"] - ep["sx"], ep["ey"] - ep["sy"]) >= 5)]
    sample = rng.choice(pool.index.to_numpy(), size=min(n, len(pool)), replace=False)
    sub = seg[seg["trk"].isin(sample)].sort_values(["trk", "t"])
    rows, truth = [], {}
    for trk, g in sub.groupby("trk"):
        n_ = len(g)
        L = int(rng.integers(5, 31))
        i = int(rng.integers(10, max(11, n_ - 10 - L - 1)))
        if i + L + 1 >= n_:
            continue
        a, b = g.iloc[i], g.iloc[i + L + 1]
        o = ep.loc[trk]
        k2 = -(int(trk) + 1)
        rows.append((trk, o["t_start"], o["sx"], o["sy"], a["t"], a["x"], a["y"], a["vx"], a["vy"], o["cls"], o["length"], o["width"], i + 1))
        rows.append((k2, b["t"], b["x"], b["y"], o["t_end"], o["ex"], o["ey"], o["evx"], o["evy"], o["cls"], o["length"], o["width"], n_ - i - L - 1))
        truth[trk] = k2
    cols = ["t_start", "sx", "sy", "t_end", "ex", "ey", "evx", "evy", "cls", "length", "width", "frames"]
    new = pd.DataFrame([r[1:] for r in rows], index=[r[0] for r in rows], columns=cols)
    lk, _ = stitch(pd.concat([ep.drop(index=list(truth)), new]), edge_r)
    chosen = dict(zip(lk["a"], lk["b"]))
    res = pd.DataFrame({"trk": list(truth), "cls": [ep.loc[k, "cls"] for k in truth]})
    res["joined_right"] = [chosen.get(k) == v for k, v in truth.items()]
    res["joined_wrong"] = [(k in chosen) and chosen[k] != v for k, v in truth.items()]
    return res

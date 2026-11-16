"""Dashboard build B3 - transparent cross-sensor candidate matching of track segments (no identity is assumed from ids).
For every pedestrian/cyclist-relevant segment of one sensor (NS Pedestrian/Cyclist/Motorcycle-dominant; OU segments containing a PERSON or
BICYCLE label) every time-overlapping segment of the OTHER sensor (any class, class-agnostic like C2) within reach is evaluated:
  * common time grid (0.2 s) where both segments have a sample within 0.35 s (no interpolation across gaps);
  * clock uncertainty: the Newsense track is shifted by dt in [-0.7, +0.7] s (step 0.1; Stage 3 v2 Newsense-Ouster bound) and the
    dt with the smallest median distance is kept (reported as best_dt_s);
  * metrics: overlap_s, overlap_frac (of the shorter segment), median / p90 distance, share of grid points within 2 m,
    direction agreement (mean cosine of 1-s displacement directions when both move > 0.5 m/s), median |speed difference|, class pair.
Edge classes (thresholds fixed a priori, documented in docs/METHODOLOGY.md):
  strong   : overlap >= 2 s, overlap_frac >= 0.5, median <= 1.0 m, p90 <= 2.0 m, within2m >= 0.8, direction agreement >= 0.5 (or n/a when stationary)
  possible : overlap >= 1 s, median <= 2.0 m, within2m >= 0.5
  rejected : otherwise (top alternatives kept with the reason)
match_cost = median distance in m (a ranking quantity, NOT a probability).
Investigation candidates are formed in b3b_candidates.py.
Output: data/match_edges.parquet
"""
import os, math, json, collections
import numpy as np, pandas as pd
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DD = os.path.join(B, 'data')
seg = pd.read_parquet(os.path.join(DD, 'segments.parquet'))
tracks = {}
for s in ('NS', 'OU'):
    o = pd.read_parquet(os.path.join(DD, f'obs_seg_{s}.parquet'), columns=['seg', 't', 'x', 'y', 'vx', 'vy'])
    for k, g in o.groupby('seg', sort=False): tracks[k] = (g.t.values, g.x.values, g.y.values, np.hypot(g.vx.values, g.vy.values))
    del o
def vru_relevant(r):
    if r.sensor == 'NS': return r.grp in ('PED', 'CYC', 'MOTO')
    return ('PERSON' in r.classes) or ('BICYCLE' in r.classes)
seg['vru'] = [vru_relevant(r) for r in seg.itertuples()]
bbox = {r.seg: (r.t0, r.t1) for r in seg.itertuples()}
ext = {}
for k, (t, x, y, v) in tracks.items(): ext[k] = (x.min(), x.max(), y.min(), y.max())
OFFS = np.round(np.arange(-0.7, 0.701, 0.1), 2)
def valid(tq, ts):
    i = np.clip(np.searchsorted(ts, tq), 1, len(ts) - 1); d = np.minimum(np.abs(ts[i] - tq), np.abs(ts[i - 1] - tq)) if len(ts) > 1 else np.abs(ts[0] - tq)
    return d <= 0.35
def evaluate(a, b):
    """a, b: segment keys; NS is shifted. returns metric dict or None."""
    ns, ou = (a, b) if a.startswith('NS') else (b, a)
    tn, xn, yn, vn = tracks[ns]; to, xo, yo, vo = tracks[ou]
    lo, hi = max(tn[0], to[0]) - 0.7, min(tn[-1], to[-1]) + 0.7
    if hi - lo < 0.5: return None
    g = np.arange(lo, hi, 0.2); vo_ = valid(g, to)
    best = None
    for off in OFFS:
        gn = g + off; m = vo_ & valid(gn, tn) & (gn >= tn[0]) & (gn <= tn[-1]) & (g >= to[0]) & (g <= to[-1])
        if m.sum() < 3: continue
        d = np.hypot(np.interp(gn[m], tn, xn) - np.interp(g[m], to, xo), np.interp(gn[m], tn, yn) - np.interp(g[m], to, yo))
        med = float(np.median(d))
        if best is None or med < best[0]: best = (med, off, m, d)
    if best is None: return None
    med, off, m, d = best; gg = g[m]
    # direction agreement on 1-s displacements
    cs = []
    for k in range(0, len(gg) - 5, 5):
        t1, t2 = gg[k], gg[k + 5]
        if t2 - t1 > 1.2: continue
        dxn = np.interp(t2 + off, tn, xn) - np.interp(t1 + off, tn, xn); dyn = np.interp(t2 + off, tn, yn) - np.interp(t1 + off, tn, yn)
        dxo = np.interp(t2, to, xo) - np.interp(t1, to, xo); dyo = np.interp(t2, to, yo) - np.interp(t1, to, yo)
        nn, no = math.hypot(dxn, dyn), math.hypot(dxo, dyo)
        if nn > 0.5 and no > 0.5: cs.append((dxn * dxo + dyn * dyo) / (nn * no))
    sd = np.abs(np.interp(gg + off, tn, vn) - np.interp(gg, to, vo))
    ov = len(gg) * 0.2; shorter = min(tn[-1] - tn[0], to[-1] - to[0]) + 0.2
    return dict(ns_seg=ns, ou_seg=ou, overlap_s=round(ov, 1), overlap_frac=round(min(1.0, ov / shorter), 3), median_d=round(med, 3), p90_d=round(float(np.quantile(d, 0.9)), 3),
                within2m=round(float((d <= 2).mean()), 3), dir_agree=round(float(np.mean(cs)), 3) if cs else np.nan, n_dir=len(cs), speed_diff_med=round(float(np.median(sd)), 3), best_dt_s=float(off))
def classify(e):
    da_ok = np.isnan(e['dir_agree']) or e['dir_agree'] >= 0.5
    if e['overlap_s'] >= 2 and e['overlap_frac'] >= 0.5 and e['median_d'] <= 1.0 and e['p90_d'] <= 2.0 and e['within2m'] >= 0.8 and da_ok: return 'strong', 'all strong criteria met'
    if e['overlap_s'] >= 1 and e['median_d'] <= 2.0 and e['within2m'] >= 0.5:
        why = [n for n, ok in (('overlap < 2 s', e['overlap_s'] >= 2), ('overlap fraction < 0.5', e['overlap_frac'] >= 0.5), ('median > 1 m', e['median_d'] <= 1.0),
                               ('p90 > 2 m', e['p90_d'] <= 2.0), ('< 80 % within 2 m', e['within2m'] >= 0.8), ('directions differ', da_ok)) if not ok]
        return 'possible', 'possible only: ' + ', '.join(why)
    why = [n for n, ok in (('overlap < 1 s', e['overlap_s'] >= 1), ('median > 2 m', e['median_d'] <= 2.0), ('< 50 % within 2 m', e['within2m'] >= 0.5)) if not ok]
    return 'rejected', 'rejected: ' + ', '.join(why)
# candidate pairs: time overlap + spatial reach (3 m margin)
segs = {s: seg[seg.sensor == s].sort_values('t0').reset_index(drop=True) for s in ('NS', 'OU')}
edges = []; done = set()
for s, o in (('NS', 'OU'), ('OU', 'NS')):
    A = segs[s][segs[s].vru]; Bt = segs[o]; t0s = Bt.t0.values; t1s = Bt.t1.values; keys = Bt.seg.values
    for r in A.itertuples():
        j = np.searchsorted(t0s, r.t1 + 0.7)
        cand = np.where(t1s[:j] >= r.t0 - 0.7)[0]
        ea = ext[r.seg]
        for c in cand:
            k = keys[c]; eb = ext[k]
            if eb[0] > ea[1] + 3 or eb[1] < ea[0] - 3 or eb[2] > ea[3] + 3 or eb[3] < ea[2] - 3: continue
            pair = (r.seg, k) if s == 'NS' else (k, r.seg)
            if pair in done: continue
            done.add(pair); e = evaluate(*pair)
            if e is None: continue
            e['edge_class'], e['reason'] = classify(e); edges.append(e)
    print(s, 'evaluated pairs so far', len(edges), flush=True)
E = pd.DataFrame(edges)
info = seg.set_index('seg')
E['ns_grp'] = info.loc[E.ns_seg, 'grp'].values; E['ou_grp'] = info.loc[E.ou_seg, 'grp'].values
E['ns_id'] = info.loc[E.ns_seg, 'id'].values; E['ou_id'] = info.loc[E.ou_seg, 'id'].values
E['class_agree'] = np.where(E.ns_grp.replace({'MOTO': 'CYC'}) == E.ou_grp, 'same group', np.where(E.ou_grp == 'UNK', 'Ouster UNKNOWN', 'different'))
E.to_parquet(os.path.join(DD, 'match_edges.parquet'), index=False)
print(E.edge_class.value_counts().to_dict())
# investigation candidates are built by b3b_candidates.py

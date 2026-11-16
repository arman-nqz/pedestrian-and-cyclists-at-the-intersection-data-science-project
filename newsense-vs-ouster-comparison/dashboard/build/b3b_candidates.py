"""Dashboard build B3b - investigation candidates from the evaluated match edges (b3_matching.py).
Problem avoided: plain connected components chain hundreds of segments at waiting areas (groups, long stationary tracks).
Rule (both directions, symmetric):
  1. For each segment, its accepted partners (strong/possible) are taken in order of match cost (median distance); a partner is SELECTED only if
     its time overlap with that segment does not overlap (> 1 s) the overlap of an already selected partner -> one partner per moment,
     several sequential partners allowed (= fragmentation of the other sensor).
  2. An edge is kept only if BOTH ends selected it (mutual).
  3. Ambiguity flag of a segment: another accepted partner overlapping the selected one in time has a median distance within 0.5 m of it.
Candidates = connected components of kept edges whose ends are NOT ambiguity-flagged (flagged segments form their own candidate, with all
competing partners shown in the dashboard), seeded by pedestrian/cyclist-relevant segments.
Status: Ambiguous (any member flagged, a sensor has simultaneous segments, or a lone segment has acceptable partners that were claimed elsewhere), Strong candidate match (>= 1 strong kept edge),
Possible match, Unmatched (one sensor only, no acceptable partner at all, >= 50 % of observations in the common region), Cannot determine (one sensor only, mostly outside it).
Outputs: data/candidates.parquet, data/candidate_members.parquet, data/match_edges.parquet (adds columns selected_ns, selected_ou, kept, ambiguous_flag)
"""
import os, collections
import numpy as np, pandas as pd
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DD = os.path.join(B, 'data')
seg = pd.read_parquet(os.path.join(DD, 'segments.parquet')); info = seg.set_index('seg')
E = pd.read_parquet(os.path.join(DD, 'match_edges.parquet'))
seg['vru'] = [(r.grp in ('PED', 'CYC', 'MOTO')) if r.sensor == 'NS' else (('PERSON' in r.classes) or ('BICYCLE' in r.classes)) for r in seg.itertuples()]
t0 = info.t0.to_dict(); t1 = info.t1.to_dict()
acc = E[E.edge_class != 'rejected'].copy()
def window(a, b): return max(t0[a], t0[b]), min(t1[a], t1[b])
sel = set(); amb = set()
for side, other in (('ns_seg', 'ou_seg'), ('ou_seg', 'ns_seg')):
    for k, g in acc.sort_values('median_d').groupby(side, sort=False):
        chosen = []
        for r in g.itertuples():
            w = window(getattr(r, side), getattr(r, other))
            clash = [c for c in chosen if min(w[1], c[1]) - max(w[0], c[0]) > 1.0]
            if clash:
                if r.median_d - clash[0][2] <= 0.5: amb.add(k)
                continue
            chosen.append((w[0], w[1], r.median_d)); sel.add((side, r.Index))
E['selected_ns'] = [('ns_seg', i) in sel for i in E.index]; E['selected_ou'] = [('ou_seg', i) in sel for i in E.index]
E['kept'] = E.selected_ns & E.selected_ou & (E.edge_class != 'rejected')
E['ambiguous_flag'] = E.ns_seg.isin(amb) | E.ou_seg.isin(amb)
E.to_parquet(os.path.join(DD, 'match_edges.parquet'), index=False)
K = E[E.kept & ~E.ambiguous_flag]; adj = collections.defaultdict(set)   # ambiguous segments are not chained: they become their own candidate
for r in K.itertuples(): adj[r.ns_seg].add(r.ou_seg); adj[r.ou_seg].add(r.ns_seg)
comp_of = {}; comps = []
for k in sorted(seg.seg[seg.vru], key=lambda k: t0[k]):
    if k in comp_of: continue
    stack = [k]; mem = []
    while stack:
        u = stack.pop()
        if u in comp_of: continue
        comp_of[u] = len(comps); mem.append(u); stack.extend(adj[u] - comp_of.keys())
    comps.append(sorted(mem, key=lambda k: (t0[k], k)))   # tie-break by name: member order must not depend on set iteration order (PYTHONHASHSEED)
has_acc = set(acc.ns_seg) | set(acc.ou_seg)
def simultaneous(ms):
    # equal start times: longer segment first, so a segment lying inside another is always detected (the result must not depend on set iteration order)
    ms = sorted(ms, key=lambda k: (t0[k], -t1[k], k)); return any(t0[b] < t1[a] - 1.0 for a, b in zip(ms, ms[1:]))
rows = []; members = []
for ci, mem in enumerate(comps):
    inv = f'INV-{ci + 1:05d}'; m = info.loc[mem]
    ns, ou = [k for k in mem if k.startswith('NS')], [k for k in mem if k.startswith('OU')]
    ce = K[K.ns_seg.isin(ns) & K.ou_seg.isin(ou)]
    # a segment with acceptable partners (strong/possible) that ended up alone is ambiguous: its partners were claimed by another segment
    # or are themselves ambiguous. 'Unmatched' therefore means: no acceptable partner at all.
    lone_but_accepted = (not (ns and ou)) and any(k in has_acc for k in mem)
    flag = any(k in amb for k in mem) or lone_but_accepted or (len(ns) > 1 and simultaneous(ns)) or (len(ou) > 1 and simultaneous(ou))
    if ns and ou: status = 'Ambiguous' if flag else 'Strong candidate match' if (ce.edge_class == 'strong').any() else 'Possible match'
    elif flag: status = 'Ambiguous'   # flagged segment: >= 2 partners at similar distance at the same time
    else: status = 'Unmatched' if float((m.region_share * m.n).sum() / m.n.sum()) >= 0.5 else 'Cannot determine'
    rows.append(dict(inv=inv, status=status, sensors='both' if ns and ou else ('Newsense only' if ns else 'Ouster only'),
        ns_ids=', '.join(sorted(set(m[m.sensor == 'NS'].id), key=int)), ou_ids=', '.join(sorted(set(m[m.sensor == 'OU'].id), key=int)),
        ns_segments=len(ns), ou_segments=len(ou), ns_class='/'.join(sorted(set(m[m.sensor == 'NS'].grp))) or '-', ou_class='/'.join(sorted(set(m[m.sensor == 'OU'].grp))) or '-',
        t0=m.t0.min(), t1=m.t1.max(), dur=m.t1.max() - m.t0.min(), n_obs=int(m.n.sum()), ns_obs=int(m[m.sensor == 'NS'].n.sum()), ou_obs=int(m[m.sensor == 'OU'].n.sum()),
        x=float((m.x0 + m.x1).mean() / 2), y=float((m.y0 + m.y1).mean() / 2), region_share=float((m.region_share * m.n).sum() / m.n.sum()),
        robust_path_max=float(m.robust_path.max()), moving=bool((m.robust_path > 2).any()), best_median_d=float(ce.median_d.min()) if len(ce) else np.nan,
        id_issue=bool(m.start_event.isin(['LONG', 'MID', 'SWAP', 'SHORT', 'MASK']).any() or m.end_event.str.startswith('id re-appears').any()),
        fragmented=bool(len(ns) > 1 or len(ou) > 1), class_change=bool((m.class_changes > 0).any())))
    members += [dict(inv=inv, seg=k) for k in mem]
C = pd.DataFrame(rows); C.to_parquet(os.path.join(DD, 'candidates.parquet'), index=False); pd.DataFrame(members).to_parquet(os.path.join(DD, 'candidate_members.parquet'), index=False)
C['size'] = C.ns_segments + C.ou_segments
print('kept edges', int(E.kept.sum()), E[E.kept].edge_class.value_counts().to_dict()); print(C.status.value_counts().to_dict()); print(C['size'].describe().round(2).to_dict())
print(C[C.moving].status.value_counts().to_dict())

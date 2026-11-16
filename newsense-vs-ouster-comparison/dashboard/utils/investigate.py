"""Object investigation logic: candidate -> member segments -> history, events, comparison metrics, matching evidence and an interpretation
generated only from the selected object's data."""
import math
import numpy as np, pandas as pd
from . import data as D
from .timebase import clock
from .config import GRP_NAME, SENSOR_NAME
EV_TEXT = {'LONG': 'this ID had last been seen {gap:.0f} s earlier, {jump:.0f} m away (ID re-used for another object)',
           'MID': 'this ID had last been seen {gap:.0f} s earlier, {jump:.0f} m away (ID re-used)',
           'SHORT': 'same ID re-attached after a {gap:.1f} s loss, {jump:.1f} m away',
           'MASK': 'same ID continues across an Ouster log gap ({gap:.1f} s, analysis mask)',
           'SWAP': 'ID jumped {jump:.0f} m within {gap:.1f} s (instant ID swap with another object)'}
def H_project(H, x, y):
    w = H[2][0] * x + H[2][1] * y + H[2][2]; return (H[0][0] * x + H[0][1] * y + H[0][2]) / w, (H[1][0] * x + H[1][1] * y + H[1][2]) / w
def in_camera(x, y):
    H = D.video_index()['homography']['H']; u, v = H_project(H, x, y); return 0 <= u <= 720 and 60 <= v <= 480
def members(inv):
    C, M = D.candidates(); S = D.segments().set_index('seg')
    keys = list(M[M.inv == inv].seg); return C[C.inv == inv].iloc[0], S.loc[keys].reset_index()
def related_edges(keys, top=12):
    E = D.edges(); e = E[E.ns_seg.isin(keys) | E.ou_seg.isin(keys)].copy()
    e['member_pair'] = e.ns_seg.isin(keys) & e.ou_seg.isin(keys)
    return e.sort_values(['member_pair', 'kept', 'median_d'], ascending=[False, False, True]).head(top)
def histories(segs):
    return {r.seg: D.obs(r.sensor).seg(r.seg) for r in segs.itertuples()}
def events(segs, hist):
    ev = []
    for r in segs.itertuples():
        h = hist[r.seg]; s = r.sensor; nm = SENSOR_NAME[s]
        ev.append(dict(t=float(r.t0), s=s, label=f'{nm} ID {r.id}: first observation ({h.cls.iloc[0]})', kind='first'))
        ev.append(dict(t=float(r.t1), s=s, label=f'{nm} ID {r.id}: last observation; afterwards {r.end_event}', kind='last'))
        if r.start_event in EV_TEXT:
            ev.append(dict(t=float(r.t0) + 0.01, s=s, label=f'{nm} ID {r.id}: ' + EV_TEXT[r.start_event].format(gap=r.gap_before or 0, jump=r.jump_before or 0), kind='id'))
        c = h.cls.astype(str).values; tt = h.t.values
        for i in np.where(c[1:] != c[:-1])[0]:
            ev.append(dict(t=float(tt[i + 1]), s=s, label=f'{nm} ID {r.id}: class {c[i]} → {c[i + 1]}', kind='class'))
        d = np.diff(tt)
        for i in np.where(d > 1.0)[0]:
            ev.append(dict(t=float(tt[i]), s=s, label=f'{nm} ID {r.id}: no samples for {d[i]:.1f} s (object not reported)', kind='gap'))
            ev.append(dict(t=float(tt[i + 1]), s=s, label=f'{nm} ID {r.id}: reported again after {d[i]:.1f} s', kind='gap'))
        if s == 'OU':
            co = h.coasted.values.astype(bool)
            for i in np.where(co[1:] & ~co[:-1])[0]:
                n = int(np.argmin(co[i + 1:])) if not co[i + 1:].all() else len(co) - i - 1
                ev.append(dict(t=float(tt[i + 1]), s=s, label=f'Ouster ID {r.id}: predicted (coasted) positions for {n} samples', kind='coast'))
            rf = h.refind_t.values; ok = ~np.isnan(rf)
            for i in range(1, len(rf)):
                if ok[i] and (not ok[i - 1] or rf[i] != rf[i - 1]):
                    ev.append(dict(t=float(tt[i]), s=s, label=f'Ouster ID {r.id}: refind_time flag set ({clock(rf[i], True)}) - vendor re-find, identity not verified', kind='refind'))
    return sorted(ev, key=lambda e: e['t'])
def both_window(segs, hist):
    """periods where both sensors report a member (samples within 0.2 s)."""
    ns = np.sort(np.concatenate([hist[k].t.values for k in segs[segs.sensor == 'NS'].seg] or [np.array([])]))
    ou = np.sort(np.concatenate([hist[k].t.values for k in segs[segs.sensor == 'OU'].seg] or [np.array([])]))
    if not len(ns) or not len(ou): return None
    i = np.clip(np.searchsorted(ou, ns), 1, len(ou) - 1); near = np.minimum(np.abs(ou[i] - ns), np.abs(ou[i - 1] - ns)) <= 0.2
    return (float(ns[near].min()), float(ns[near].max()), float(near.sum() * 0.1)) if near.any() else None
def metrics(segs, hist):
    out = {}
    for s in ('NS', 'OU'):
        g = segs[segs.sensor == s]
        if not len(g): out[s] = None; continue
        h = pd.concat([hist[k] for k in g.seg]).sort_values('t')
        gaps = [d for k in g.seg for d in np.diff(hist[k].t.values) if d > 0.35]
        reuse = [f"ID {r.id}: {r.start_event}" for r in g.itertuples() if r.start_event not in ('FIRST', '')] + [f"ID {r.id}: {r.end_event}" for r in g.itertuples() if r.end_event.startswith('id re-appears')]
        cl = h.cls.astype(str).value_counts()
        out[s] = {'Tracking ID(s)': ', '.join(dict.fromkeys(g.id.astype(str))), 'Classification (share of samples)': ', '.join(f"{k} {v / len(h):.0%}" if v / len(h) >= 0.01 else f'{k} <1% ({v} samples)' for k, v in cl.items()),
                  'First detection': clock(g.t0.min(), True), 'Last detection': clock(g.t1.max(), True), 'Duration (first to last, s)': round(float(g.t1.max() - g.t0.min()), 1),
                  'Observations': int(len(h)), 'Track length, robust moving path (m)': round(float(g.robust_path.sum()), 1), 'Track length, all steps (m)': round(float(g.path_all_steps.sum()), 1),
                  'Average reported speed (m/s)': round(float(h.speed.mean()), 2), 'Maximum reported speed (m/s)': round(float(h.speed.max()), 2),
                  'Fragmentation (segments)': int(len(g)), 'Missing periods > 0.35 s (count, total s)': f'{len(gaps)}, {sum(gaps):.1f}',
                  'Class changes within the track': int(g.class_changes.sum()), 'ID reuse / re-attachment': '; '.join(reuse) or 'none',
                  'Predicted (coasted) samples': f"{int(h.coasted.sum())} ({h.coasted.mean():.0%})" if s == 'OU' else 'not reported by this sensor',
                  'Inside shared coverage': f"{float(h.region.mean()):.0%} of samples"}
    return out
def interpretation(cand, segs, hist, m, bw, edges):
    L = []; ns, ou = m['NS'], m['OU']
    st = cand.status
    if ns and ou:
        L.append(f"**Both sensors report an object here.** Matching status: **{st}**" + (f" (best median distance {cand.best_median_d:.2f} m)." if cand.best_median_d == cand.best_median_d else '.'))
        if bw: L.append(f"They report it at the same time for about {bw[2]:.1f} s ({clock(bw[0])}–{clock(bw[1])}).")
        dn, do = ns['Duration (first to last, s)'], ou['Duration (first to last, s)']
        longer = 'Ouster' if do > dn * 1.1 else 'Newsense' if dn > do * 1.1 else None
        L.append(f"**Tracking time:** Newsense {dn} s, Ouster {do} s" + (f" — {longer} follows the object longer." if longer else ' — similar.'))
        gn, go = sorted(set(segs[segs.sensor == 'NS'].grp)), sorted(set(segs[segs.sensor == 'OU'].grp))
        agree = {g.replace('MOTO', 'CYC') for g in gn} & set(go)
        L.append(f"**Classification:** Newsense {', '.join(GRP_NAME.get(g, g) for g in gn)}; Ouster {', '.join(GRP_NAME.get(g, g) for g in go)}" + (' — the coarse groups agree.' if agree else ' — the sensors disagree (who is right is not decidable from sensor data).'))
    else:
        s = 'NS' if ns else 'OU'; o = 'Ouster' if s == 'NS' else 'Newsense'
        if st == 'Cannot determine': L.append(f"**Only {SENSOR_NAME[s]} reports this object, but mostly outside the area both sensors cover** — {o} could not have seen it there. No conclusion about a miss is possible.")
        elif st == 'Unmatched': L.append(f"**Only {SENSOR_NAME[s]} reports this object.** It lies in the shared area, and {o} has no track within 2 m at that time. Either {o} missed it, or {SENSOR_NAME[s]}'s object is not real (e.g. a static false object). Watch the video to judge.")
        else: L.append(f"**Only {SENSOR_NAME[s]} track(s) in this candidate, and the match is ambiguous**: {o} has nearby tracks that fit about equally well or that were assigned to another object (see the evidence table).")
    for s, mm in (('NS', ns), ('OU', ou)):
        if not mm: continue
        f = mm['Fragmentation (segments)']; reuse = mm['ID reuse / re-attachment']
        if f > 1: L.append(f"**{SENSOR_NAME[s]} breaks this object into {f} track segments** ({mm['Tracking ID(s)']}).")
        if reuse != 'none': L.append(f"**{SENSOR_NAME[s]} ID events:** {reuse}.")
        if mm['Class changes within the track']: L.append(f"**{SENSOR_NAME[s]} changes the class {mm['Class changes within the track']} time(s)** within the track ({mm['Classification (share of samples)']}).")
        mp = mm['Missing periods > 0.35 s (count, total s)']
        if not mp.startswith('0,'): L.append(f"{SENSOR_NAME[s]} has {mp.split(',')[0]} period(s) without samples (total {mp.split(',')[1].strip()} s).")
    if ou and ou['Predicted (coasted) samples'] != '0 (0%)': L.append(f"Ouster reports **predicted (not measured)** positions for {ou['Predicted (coasted) samples']} of its samples.")
    L.append("**What cannot be concluded:** which sensor is correct, whether the object is a real person, and whether a candidate match is the same physical person. There is no ground truth; the video can support but not prove identity.")
    return L
def examples():
    """Deterministic example candidates for each requested category (or None if no valid example exists)."""
    C, _ = D.candidates(); C = C[C.moving]
    C = C.assign(cam=[in_camera(x, y) for x, y in zip(C.x, C.y)])
    def pick(df, by, asc=False):
        df = df[df.cam] if df.cam.any() else df
        return None if df.empty else df.sort_values(by, ascending=asc).iloc[0].inv
    S = D.segments().set_index('seg'); _, M = D.candidates()
    return {
     'Tracked by both sensors (strong candidate match)': pick(C[(C.status == 'Strong candidate match') & (C.ns_segments == 1) & (C.ou_segments == 1)], 'dur'),
     'Newsense-only candidate (unmatched in shared area)': pick(C[(C.status == 'Unmatched') & (C.sensors == 'Newsense only') & (C.region_share > 0.9)], 'robust_path_max'),
     'Ouster-only candidate (unmatched in shared area)': pick(C[(C.status == 'Unmatched') & (C.sensors == 'Ouster only') & (C.region_share > 0.9)], 'robust_path_max'),
     'Ambiguous match (group)': pick(C[(C.status == 'Ambiguous') & (C.sensors == 'both') & (C.ns_segments + C.ou_segments <= 4)], 'dur'),
     'Tracking interruption / ID issue (fragmented)': pick(C[(C.status.isin(['Strong candidate match', 'Possible match'])) & (C.ns_segments >= 2) & C.id_issue | (C.status.isin(['Strong candidate match', 'Possible match']) & (C.ns_segments >= 3))], 'dur'),
    }

"""Dashboard build B2 - track segments, id events and per-segment metrics (identical rules for both sensors; C3 definitions).
Segment: one sensor id; a new segment starts when the same id re-appears after > 5 s, or steps > 15 m within <= 1 s (C3 / NS-15).
Id event at a segment start (C3 v2 classes): FIRST (first appearance), MASK (gap <= 12 s spanning a masked Ouster log gap), SHORT (5-30 s),
MID (30-60 s), LONG (> 60 s), SWAP (> 15 m within <= 1 s). Dominant group = most frequent coarse group of the segment.
Robust moving path (CORR-01 rule): positions decimated to >= 1 s, step counted if 0.5-30 m (reported per segment, all coverage and region-only).
Also: orientation check (reported yaw/heading vs velocity direction for moving vehicles) -> decides whether footprints are drawn rotated.
Outputs: data/segments.parquet, data/obs_seg_NS.parquet / obs_seg_OU.parquet (obs + segment key), data/orientation_check.json
"""
import os, json, math
import numpy as np, pandas as pd
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DD = os.path.join(B, 'data')
GAPS = [(1793255611.628, 1793255619.128), (1793256261.131, 1793256263.331), (1793258775.342, 1793258782.843), (1793258899.443, 1793258901.543)]
segrows = []; orient = {}
for s in ('NS', 'OU'):
    df = pd.read_parquet(os.path.join(DD, f'obs_{s}.parquet'))
    df = df.sort_values(['id', 't'], kind='stable').reset_index(drop=True)
    t, x, y = df.t.values, df.x.values, df.y.values; same = np.r_[False, df.id.values[1:] == df.id.values[:-1]]
    dt = np.r_[np.nan, np.diff(t)]; st = np.r_[np.nan, np.hypot(np.diff(x), np.diff(y))]
    gap = same & (dt > 5); tel = same & (dt <= 1) & (st > 15); newseg = (~same) | gap | tel
    seg_no = newseg.cumsum() - 1
    df['seg'] = [f'{s}:{i}#' for i in df.id.values]
    k = df.groupby('id').cumcount()   # placeholder, replaced below
    # per-id segment index
    idx_in_id = pd.Series(newseg.astype(int)).groupby(df.id.values).cumsum().values - 1
    df['seg'] = df['seg'] + idx_in_id.astype(str)
    ev = np.where(~same, 'FIRST', np.where(tel, 'SWAP', ''))
    for i in np.where(gap)[0]:
        g = dt[i]; mask = g <= 12 and any(t[i - 1] <= a and t[i] >= b for a, b in GAPS)
        ev[i] = 'MASK' if mask else 'SHORT' if g <= 30 else 'MID' if g <= 60 else 'LONG'
    df['start_event'] = np.where(newseg, ev, ''); df['gap_before'] = np.where(newseg & same, dt, np.nan); df['jump_before'] = np.where(newseg & same, st, np.nan)
    sp = np.hypot(df.vx.values, df.vy.values); df['speed'] = sp
    # orientation check on moving vehicles
    mv = (df.grp.values == 'VEH') & (sp > 3)
    vel = np.degrees(np.arctan2(df.vy.values[mv], df.vx.values[mv])); yw = df.yaw_deg.values[mv]
    d = np.abs(((yw - vel) + 90) % 180 - 90)  # box symmetric -> compare modulo 180
    orient[s] = dict(n=int(mv.sum()), share_within_20deg=round(float((d <= 20).mean()), 3), median_abs_diff_deg=round(float(np.median(d)), 1))
    df.to_parquet(os.path.join(DD, f'obs_seg_{s}.parquet'), index=False)
    for key, g in df.groupby('seg', sort=False):
        tt, xx, yy, rr = g.t.values, g.x.values, g.y.values, g.region.values
        d_ = np.diff(tt); stp = np.hypot(np.diff(xx), np.diff(yy)); ok = (d_ > 0) & (d_ <= 1)
        grp = g.grp.value_counts(); dom = grp.index[0]
        cls_seq = g.cls.values; trans = int((cls_seq[1:] != cls_seq[:-1]).sum())
        # robust path
        rp = rp_reg = 0.0; lt = lx = ly = lr = None
        for ti, xi, yi, ri in zip(tt, xx, yy, rr):
            if lt is None or ti - lt > 2: lt, lx, ly, lr = ti, xi, yi, ri; continue
            if ti - lt < 1: continue
            dd = math.hypot(xi - lx, yi - ly)
            if 0.5 <= dd <= 30:
                rp += dd
                if lr and ri: rp_reg += dd
            lt, lx, ly, lr = ti, xi, yi, ri
        first = g.iloc[0]
        segrows.append(dict(seg=key, sensor=s, id=first.id, seg_index=int(key.split('#')[1]), t0=tt[0], t1=tt[-1], dur=tt[-1] - tt[0], n=len(g),
            grp=dom, grp_share=round(grp.iloc[0] / len(g), 3), classes='>'.join(pd.unique(cls_seq)), first_cls=cls_seq[0], last_cls=cls_seq[-1], class_changes=trans,
            x0=xx[0], y0=yy[0], x1=xx[-1], y1=yy[-1], disp=math.hypot(xx[-1] - xx[0], yy[-1] - yy[0]), path_all_steps=float(stp[ok].sum()), robust_path=rp, robust_path_region=rp_reg,
            mean_speed=float(g.speed.mean()), max_speed=float(g.speed.max()), moving_share=float((g.speed > 0.5).mean()), region_share=float(rr.mean()),
            gaps_gt_0p35s=int((d_ > 0.35).sum()), gaps_1_5s=int(((d_ > 1) & (d_ <= 5)).sum()), max_gap=float(d_.max()) if len(d_) else 0.0,
            coasted_share=float(g.coasted.mean()) if s == 'OU' else np.nan, refind_values=int(g.refind_t.dropna().nunique()) if s == 'OU' else 0,
            start_event=first.start_event, gap_before=first.gap_before, jump_before=first.jump_before))
    print(s, df.seg.nunique(), 'segments', orient[s], flush=True)
seg = pd.DataFrame(segrows)
# end event: what happens to the id after this segment
seg = seg.sort_values(['sensor', 'id', 't0']).reset_index(drop=True)
nxt = seg.groupby(['sensor', 'id'])['start_event'].shift(-1)
seg['end_event'] = np.where(nxt.isna(), 'id not seen again', 'id re-appears: ' + nxt.fillna(''))
seg.to_parquet(os.path.join(DD, 'segments.parquet'), index=False)
json.dump(orient, open(os.path.join(DD, 'orientation_check.json'), 'w', encoding='utf-8'), indent=1)
print(seg.groupby('sensor').size().to_dict(), seg.groupby(['sensor', 'start_event']).size().to_dict())

"""Dashboard build B5 - video time index, projection parameters and conflict-event table (all from validated project files; nothing new estimated).
Video timing chain (as used in C2/C7/video round 2, unchanged):
  t_sensor -> t_ref = t_sensor - DELTA (CK-01 empirical 2.81 s; used ONLY for frame look-up, cause unresolved)
  -> overlay time = t_ref + offset_SCU3K2(t_ref) (Stage 3 clock_model_v2: a0 + slope (t_ref - t0))
  -> PTS in part p = (overlay - overlay_at_pts0[p]) * pts_s_per_overlay_s[p]   (Stage 3 v2 video tick mapping)
Projection: Ouster-world ground point -> SCU3K2 pixel with the C2 v4 stationary-object homography (5 pairs, residuals 0.7-8.7 px).
Conflict events: C7 v2 event files (unchanged) + per-event cross-sensor match under the two V2 definitions (any level / also severe).
Outputs: data/video_index.json, data/events.parquet
"""
import os, json, math
import pandas as pd
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); from utils.paths import OUT as H, S4, RAW  # configurable paths
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DD = os.path.join(B, 'data')
cm = json.load(open(os.path.join(H, 'stage3_clock_assessment', 'v2', 'clock_model_v2.json'), encoding='utf-8'))['sources']['miovision_SCU3K2_overlay']['model']
ticks = json.load(open(os.path.join(H, 'stage3_clock_assessment', 'v2', 'b6_video_ticks_v2.json'), encoding='utf-8'))
delta = json.load(open(os.path.join(S4, 'checkpoint2_sensor_validation', 'data', 'c2e_video_sensor_offset.json'), encoding='utf-8'))['estimate_s']
Hm = json.load(open(os.path.join(S4, 'checkpoint2_sensor_validation', 'data', 'c2e_homography_v4_stationary.json'), encoding='utf-8'))
parts = {}
for p in ('001', '002', '003', '004', '005', '006', '007'):
    k = f'SCU3K2_1029_{p}.csv'
    if k in ticks: parts[p] = dict(overlay_at_pts0_epoch=ticks[k]['overlay_at_pts0_epoch'], pts_s_per_overlay_s=ticks[k]['pts_s_per_overlay_s'],
                                   duration_s=round(ticks[k]['frames'] * ticks[k]['frame_interval_s'], 2), frame_interval_s=ticks[k]['frame_interval_s'],
                                   file=f'Standard_SCU3K2_2026-10-29_0600.{p}.mp4', static_name=f'scu3k2_1029_{p}.mp4')
json.dump(dict(clock=dict(a0_s=cm['a0_s'], slope_per_s=cm['slope_per_s'], t0_ref_epoch=cm['t0_ref_epoch'], source='stage3_clock_assessment/v2/clock_model_v2.json (unchanged)'),
               delta_s=delta, delta_source='stage4_traffic_analysis/checkpoint2_sensor_validation/data/c2e_video_sensor_offset.json (CK-01; cause unresolved; look-up only)',
               parts=parts, image=dict(width=720, height=480, fps=29.97, codec='H.264 (avc1)'),
               homography=dict(H=Hm['H'], residuals_px=Hm['residuals_px'], pairs=Hm['pairs'], method=Hm['method'], source='stage4_traffic_analysis/checkpoint2_sensor_validation/data/c2e_homography_v4_stationary.json')),
          open(os.path.join(DD, 'video_index.json'), 'w', encoding='utf-8'), indent=1)
E = {s: pd.read_csv(os.path.join(S4, 'checkpoint7_interactions', 'data', f'c7_events_v2_{s}.csv')) for s in ('NS', 'OU')}
sev = lambda r: (r.kind == 'TTC' and r.value < 1.5) or (r.kind == 'PET' and r.value < 2) or r.kind == 'PROX'
rows = []
for s, o in (('NS', 'OU'), ('OU', 'NS')):
    other = E[o]
    for r in E[s].itertuples():
        same = other[(other.kind == r.kind) & ((other.t - r.t).abs() <= 2) & (((other.x - r.x) ** 2 + (other.y - r.y) ** 2) ** 0.5 <= 5)]
        sv = same[[sev(q) for q in same.itertuples()]] if len(same) else same
        rows.append(dict(sensor=s, kind=r.kind, value=r.value, severe=sev(r), t=r.t, x=r.x, y=r.y, vru_state=r.vru_state, vru_class=r.vru_class, veh_class=r.veh_class,
                         vru_seg=f'{s}:{r.vru}', veh_seg=f'{s}:{r.veh}', angle=r.angle, coasted=r.coasted, veh_speed=r.veh_speed, braking_proxy=r.braking_proxy,
                         other_any_level=len(same) > 0, other_also_severe=len(sv) > 0, other_events=len(same)))
ev = pd.DataFrame(rows); ev.to_parquet(os.path.join(DD, 'events.parquet'), index=False)
m = ev[(ev.vru_state == 'moving') & ev.severe & (ev.kind == 'TTC')]
print(m.groupby('sensor')[['other_any_level', 'other_also_severe']].sum(), m.groupby('sensor').size())

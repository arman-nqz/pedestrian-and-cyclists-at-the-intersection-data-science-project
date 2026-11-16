"""Time helpers. Sensor time <-> SCU3K2 video PTS using ONLY the validated chain (Stage 3 clock_model_v2 + video tick mapping) and the
CK-01 empirical look-up offset (2.81 s, cause unresolved). Pure functions; mirrored in components/player.js (tested for equality)."""
import json, os, datetime as dt
from .config import DATA, CET_OFFSET
VI = json.load(open(os.path.join(DATA, 'video_index.json'), encoding='utf-8'))
CK = VI['clock']; DELTA = VI['delta_s']
def offset(t_ref): return CK['a0_s'] + CK['slope_per_s'] * (t_ref - CK['t0_ref_epoch'])
def sensor_to_video(t_sensor, manual=0.0):
    """-> (part, pts) or (None, None). manual = user visual alignment in s (added to the sensor side, never stored as a correction)."""
    t_ref = t_sensor - DELTA - manual; ov = t_ref + offset(t_ref)
    for p, m in VI['parts'].items():
        pts = (ov - m['overlay_at_pts0_epoch']) * m['pts_s_per_overlay_s']
        if 0 <= pts <= m['duration_s']: return p, pts
    return None, None
def video_to_sensor(part, pts, manual=0.0):
    m = VI['parts'][part]; ov = pts / m['pts_s_per_overlay_s'] + m['overlay_at_pts0_epoch']
    t_ref = (ov - CK['a0_s'] + CK['slope_per_s'] * CK['t0_ref_epoch']) / (1 + CK['slope_per_s'])
    return t_ref + DELTA + manual
def clock(t, ms=False):
    s = dt.datetime.fromtimestamp(t + CET_OFFSET, dt.timezone.utc).strftime('%H:%M:%S.%f')
    return s[:-3] if ms else s[:-7]
def stamp(t): return dt.datetime.fromtimestamp(t + CET_OFFSET, dt.timezone.utc).strftime('%d %b %H:%M:%S')

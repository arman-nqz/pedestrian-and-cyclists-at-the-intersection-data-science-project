"""Cached data access. Large tables are loaded once per server process (st.cache_resource) with compact dtypes; object histories are
looked up through precomputed row ranges (no scanning). V2 integrity is verified at start-up; nothing falls back to V1."""
import os, re, json, csv
import numpy as np, pandas as pd, streamlit as st
from .config import DATA, OUT, V2, SOURCES, src
@st.cache_resource(show_spinner='Checking the V2 package ...')
def v2_status():
    out = dict(ok=True, problems=[], corrections=[])
    if not os.path.isdir(V2): out['ok'] = False; out['problems'].append('FINAL_PACKAGE_V2 not found'); return out
    log = open(src('v2_change_log'), encoding='utf-8').read(); cc = sorted(set(re.findall(r'\*\*(CC-\d\d)\*\*', log)))
    out['corrections'] = cc
    if len(cc) != 13: out['ok'] = False; out['problems'].append(f'{len(cc)} of 13 corrections found in V2_CHANGE_LOG.md')
    val = open(src('v2_validation'), encoding='utf-8').read()
    if 'all automated checks passed' not in val: out['ok'] = False; out['problems'].append('V2_VALIDATION_REPORT.md does not report all checks passed')
    for k, f in SOURCES['files'].items():
        if not os.path.exists(src(k)): out['ok'] = False; out['problems'].append(f'missing source {f["path"]} (looked in {src(k)})')
    return out
def jload(key): return json.load(open(src(key), encoding='utf-8'))
@st.cache_data
def comparison_csv(): return pd.read_csv(src('v2_comparison_csv'))
@st.cache_data
def register(): return pd.read_csv(src('register_v4'))
@st.cache_data
def segments():
    s = pd.read_parquet(os.path.join(DATA, 'segments.parquet')); return s
@st.cache_data
def candidates():
    c = pd.read_parquet(os.path.join(DATA, 'candidates.parquet')); m = pd.read_parquet(os.path.join(DATA, 'candidate_members.parquet'))
    return c, m
@st.cache_data
def edges(): return pd.read_parquet(os.path.join(DATA, 'match_edges.parquet'))
@st.cache_data
def events(): return pd.read_parquet(os.path.join(DATA, 'events.parquet'))
@st.cache_data
def agg_minute(): return pd.read_parquet(os.path.join(DATA, 'agg_minute.parquet'))
@st.cache_data
def heat(): return pd.read_parquet(os.path.join(DATA, 'heat.parquet'))
@st.cache_data
def class_transitions(): return pd.read_parquet(os.path.join(DATA, 'class_transitions.parquet'))
@st.cache_data
def background(): return json.load(open(os.path.join(DATA, 'background.json'), encoding='utf-8'))
@st.cache_data
def video_index(): return json.load(open(os.path.join(DATA, 'video_index.json'), encoding='utf-8'))
@st.cache_data
def frames_index(): return json.load(open(os.path.join(DATA, 'frames.json'), encoding='utf-8'))
COLS = ['t', 'id', 'seg', 'cls', 'grp', 'x', 'y', 'vx', 'vy', 'speed', 'L', 'W', 'yaw_deg', 'score', 'lag_s', 'refind_t', 'coasted', 'region', 'start_event']
class Obs:
    """Observation store of one sensor: sorted by segment, with row ranges per segment and a time-sorted row index."""
    def __init__(self, sensor):
        df = pd.read_parquet(os.path.join(DATA, f'obs_seg_{sensor}.parquet'), columns=COLS)
        for c in ('id', 'seg', 'cls', 'grp', 'start_event'): df[c] = df[c].astype('category')
        for c in ('x', 'y', 'vx', 'vy', 'speed', 'L', 'W', 'yaw_deg', 'score', 'lag_s'): df[c] = df[c].astype('float32')
        df = df.sort_values(['seg', 't'], kind='stable').reset_index(drop=True)
        codes = df.seg.cat.codes.values; b = np.r_[0, np.where(np.diff(codes) != 0)[0] + 1, len(df)]
        self.rng = {df.seg.cat.categories[codes[b[i]]]: (b[i], b[i + 1]) for i in range(len(b) - 1)}
        self.order = np.argsort(df.t.values, kind='stable').astype(np.int32); self.ts = df.t.values[self.order]
        self.df = df; self.sensor = sensor
    def seg(self, key):
        a, b = self.rng.get(key, (0, 0)); return self.df.iloc[a:b]
    def window(self, t0, t1):
        i, j = np.searchsorted(self.ts, t0), np.searchsorted(self.ts, t1, side='right'); return self.df.iloc[np.sort(self.order[i:j])]
@st.cache_resource(show_spinner='Loading the observation index (once per session server) ...')
def obs(sensor): return Obs(sensor)

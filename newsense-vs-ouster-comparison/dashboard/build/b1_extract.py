"""Dashboard build B1 - extract the common-period object streams of both sensors from the ORIGINAL dataset (read-only).
Run with the data_science_class environment: python -I build/b1_extract.py
Same rules as the canonical C3 observation cache (stage4_traffic_analysis/checkpoint3_tracks/data/obs_*_common.csv.gz):
29 Oct 07:12:00-08:35:00 CET, Ouster log gaps +-0.5 s excluded for both sensors, Newsense converted to the Ouster world frame with
the validated C1 transform (c1b_transform.json). Additional fields kept for the dashboard: reported orientation, size, Newsense score,
Ouster update lag (coasting), refind_time, creation time and point count. Output: data/obs_NS.parquet, data/obs_OU.parquet, data/frames.json
"""
import os, re, json, gzip, math
import pandas as pd
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); from utils.paths import OUT as H, S4, RAW  # configurable paths
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
T0, T1 = 1793254320.0, 1793259300.0
GAPS = [(1793255611.628, 1793255619.128), (1793256261.131, 1793256263.331), (1793258775.342, 1793258782.843), (1793258899.443, 1793258901.543)]
excl = lambda t: any(a - 0.5 <= t <= b + 0.5 for a, b in GAPS)
TR = json.load(open(os.path.join(S4, 'checkpoint1_geometry', 'data', 'c1b_transform.json'), encoding='utf-8'))['best']
s, th, tx, ty = TR['scale'], math.radians(TR['theta_deg']), TR['tx'], TR['ty']; c, sn = math.cos(th), math.sin(th)
G = {'Pedestrian': 'PED', 'Cyclist': 'CYC', 'Motorcycle': 'MOTO', 'Car': 'VEH', 'Van': 'VEH', 'Truck': 'VEH', 'Bus': 'VEH',
     'PERSON': 'PED', 'BICYCLE': 'CYC', 'VEHICLE': 'VEH', 'LARGE_VEHICLE': 'VEH', 'UNKNOWN': 'UNK'}
cells = set(map(tuple, json.load(open(os.path.join(S4, 'checkpoint1_geometry', 'data', 'c1f_coverage.json'), encoding='utf-8'))['common_region']['cells_any']))
reg = lambda x, y: (math.floor(x / 2), math.floor(y / 2)) in cells
rows = []; frames = {'NS': [], 'OU': []}
nd = os.path.join(RAW, 'newsense', 'object_list', 'k305_object_list_2026-10-29_aggregation_5min')
for fn in sorted(os.listdir(nd)):
    m = re.search(r'_(\d\d)-(\d\d)_to_', fn)
    if not m: continue
    a = 1793228400 + int(m.group(1)) * 3600 + int(m.group(2)) * 60
    if a + 300 <= T0 or a >= T1: continue
    for fr in json.load(open(os.path.join(nd, fn), encoding='utf-8'))['frames']:
        t = fr['frame_timestamp']['seconds'] + fr['frame_timestamp']['nanosec'] * 1e-9
        if not (T0 <= t < T1): continue
        frames['NS'].append(round(t, 3))
        if excl(t): continue
        for o in fr['objects']:
            b = o['bounding_box']; p = b['position']; sc = b['scale']
            x, y = s * (c * p['x'] - sn * p['y']) + tx, s * (sn * p['x'] + c * p['y']) + ty
            vx, vy = s * (c * o['velocity']['x'] - sn * o['velocity']['y']), s * (sn * o['velocity']['x'] + c * o['velocity']['y'])
            rows.append(('NS', round(t, 3), str(o['track_id']), o['class_name'], G.get(o['class_name'], 'UNK'), round(x, 3), round(y, 3), round(vx, 3), round(vy, 3),
                         round(max(sc['x'], sc['y']), 2), round(min(sc['x'], sc['y']), 2), round(sc['z'], 2), round(math.degrees(b['yaw'] + th) % 360, 1),
                         o.get('score'), None, None, None, None, reg(x, y)))
print('NS rows', len(rows), flush=True)
od = os.path.join(RAW, 'ouster', 'ouster')
for fn in sorted(f for f in os.listdir(od) if f.endswith('.gz')):
    for line in gzip.open(os.path.join(od, fn), 'rt', encoding='utf-8'):
        try: d = json.loads(line)
        except ValueError: continue
        if 'objects' not in d: continue
        t = d['timestamp'] / 1e6
        if not (T0 <= t < T1): continue
        frames['OU'].append(round(t, 3))
        if excl(t): continue
        for o in d['objects']:
            p = o['position']; dm = o.get('dimensions') or {}; v = o['velocity']; rf = o.get('refind_time')
            rows.append(('OU', round(t, 3), str(o['id']), o.get('classification'), G.get(o.get('classification'), 'UNK'), round(p['x'], 3), round(p['y'], 3), round(v['x'], 3), round(v['y'], 3),
                         round(dm.get('length', float('nan')), 2), round(dm.get('width', float('nan')), 2), round(dm.get('height', float('nan')), 2), round((o.get('heading') or 0.0) % 360, 1),
                         o.get('classification_confidence'), round((d['timestamp'] - o['update_ts']) / 1e6, 3), None if rf is None else round(rf / 1e6, 3),
                         round(o['creation_ts'] / 1e6, 3), o.get('num_points'), reg(p['x'], p['y'])))
    print(fn, len(rows), flush=True)
cols = ['sensor', 't', 'id', 'cls', 'grp', 'x', 'y', 'vx', 'vy', 'L', 'W', 'Hgt', 'yaw_deg', 'score', 'lag_s', 'refind_t', 'created_t', 'npts', 'region']
df = pd.DataFrame(rows, columns=cols); del rows
df['coasted'] = df['lag_s'] > 0.05
for sname in ('NS', 'OU'):
    part = df[df.sensor == sname].drop(columns='sensor').sort_values(['t', 'id'], kind='stable').reset_index(drop=True)
    part.to_parquet(os.path.join(OUT, f'obs_{sname}.parquet'), index=False); print(sname, len(part))
json.dump({k: sorted(v) for k, v in frames.items()}, open(os.path.join(OUT, 'frames.json'), 'w', encoding='utf-8'))

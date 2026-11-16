"""Dashboard build B4 - lightweight aggregates for the analysis pages (computed from the B1/B2 tables; identical rules for both sensors).
Outputs:
  data/agg_minute.parquet : sensor, minute (epoch of minute start), grp, region, observations, moving_obs (speed > 0.5 m/s), ids, segments
  data/heat.parquet       : sensor, grp, state (moving / stationary), cx, cy (1 m cells, Ouster world), observations, region
  data/background.json    : 1 m cells with moving VRU observations of either sensor (map context only - NOT a surveyed map)
  data/class_transitions.parquet : sensor, from_cls, to_cls, n (within-segment label changes)
"""
import os, json, math
import numpy as np, pandas as pd
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DD = os.path.join(B, 'data')
aggs, heats, trans = [], [], []
bg = {}
for s in ('NS', 'OU'):
    o = pd.read_parquet(os.path.join(DD, f'obs_seg_{s}.parquet'), columns=['t', 'id', 'seg', 'cls', 'grp', 'x', 'y', 'speed', 'region'])
    o['minute'] = (o.t // 60 * 60).astype('int64'); o['moving'] = o.speed > 0.5
    a = o.groupby(['minute', 'grp', 'region']).agg(observations=('t', 'size'), moving_obs=('moving', 'sum'), ids=('id', 'nunique'), segments=('seg', 'nunique')).reset_index()
    a.insert(0, 'sensor', s); aggs.append(a)
    o['cx'] = np.floor(o.x).astype(int); o['cy'] = np.floor(o.y).astype(int); o['state'] = np.where(o.moving, 'moving', 'stationary')
    h = o.groupby(['grp', 'state', 'cx', 'cy']).agg(observations=('t', 'size'), region=('region', 'max')).reset_index(); h.insert(0, 'sensor', s); heats.append(h)
    v = o[o.moving & o.grp.isin(['PED', 'CYC', 'MOTO'])].groupby(['cx', 'cy']).size()
    for (cx, cy), n in v.items(): bg[(cx, cy)] = bg.get((cx, cy), 0) + int(n)
    o = o.sort_values(['seg', 't'], kind='stable'); same = o.seg.values[1:] == o.seg.values[:-1]; ch = same & (o.cls.values[1:] != o.cls.values[:-1])
    t_ = pd.DataFrame({'from_cls': o.cls.values[:-1][ch], 'to_cls': o.cls.values[1:][ch]}).value_counts().reset_index(name='n'); t_.insert(0, 'sensor', s); trans.append(t_)
    print(s, len(a), len(h), flush=True)
pd.concat(aggs).to_parquet(os.path.join(DD, 'agg_minute.parquet'), index=False)
pd.concat(heats).to_parquet(os.path.join(DD, 'heat.parquet'), index=False)
pd.concat(trans).to_parquet(os.path.join(DD, 'class_transitions.parquet'), index=False)
json.dump([[k[0], k[1], v] for k, v in bg.items() if v >= 20], open(os.path.join(DD, 'background.json'), 'w', encoding='utf-8'))
print('background cells', sum(v >= 20 for v in bg.values()))

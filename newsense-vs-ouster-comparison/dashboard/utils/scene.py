"""Scene helpers for Watch the Sensors (display only). Symmetric highlighting: a track of the other sensor is also highlighted when, at some
shared moment in the window, it is within `radius` m of a highlighted track (frames paired within `tol` s; no interpolation, no clock shift).
This makes the class filter symmetric between the two sensors' vocabularies; it says nothing about identity."""
import numpy as np, pandas as pd
from . import data as D

def symmetric_selection(t0, t1, classes, radius=2.0, tol=0.1):
    """Returns (base, extra): base = segment keys highlighted by class per sensor; extra = other-sensor keys added by proximity."""
    w = {s: D.obs(s).window(t0, t1)[['t', 'x', 'y', 'seg', 'grp']].copy() for s in ('NS', 'OU')}
    for s in w: w[s]['seg'] = w[s].seg.astype(str)
    base = {s: set(w[s][w[s].grp.isin(classes)].seg) for s in w}
    extra = {'NS': set(), 'OU': set()}
    if w['NS'].empty or w['OU'].empty: return base, extra
    fN = np.unique(w['NS'].t.values); fO = np.unique(w['OU'].t.values)
    j = np.clip(np.searchsorted(fN, fO), 1, len(fN) - 1); j = np.where(np.abs(fN[j - 1] - fO) < np.abs(fN[j] - fO), j - 1, j)
    ok = np.abs(fN[j] - fO) <= tol; pair = dict(zip(fO[ok], fN[j[ok]]))
    gN = {t: g for t, g in w['NS'].groupby('t')}
    for tO, gO in w['OU'].groupby('t'):
        if tO not in pair: continue
        gN_ = gN[pair[tO]]
        d = np.hypot(gN_.x.values[:, None] - gO.x.values[None], gN_.y.values[:, None] - gO.y.values[None]) <= radius
        if not d.any(): continue
        sN = gN_.seg.values; sO = gO.seg.values
        selN = np.isin(sN, list(base['NS'])); selO = np.isin(sO, list(base['OU']))
        extra['OU'] |= set(sO[(d & selN[:, None]).any(0)]) - base['OU']
        extra['NS'] |= set(sN[(d & selO[None, :]).any(1)]) - base['NS']
    return base, extra

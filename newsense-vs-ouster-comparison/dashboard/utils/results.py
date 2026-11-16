"""V2 result cards (UI v2). Values are passed through unchanged from FINAL_PACKAGE_V2/FINAL_SENSOR_COMPARISON.csv; only the titles are plain language."""
import re
import streamlit as st
from . import data as D, ui
from .config import PERIOD
# (substring of the V2 metric name, plain-language title, unit)
CARDS = {
 'ped_confirmed': ('Pedestrian observations confirmed', 'How often does the other sensor confirm a pedestrian sample?', ''),
 'cyc_confirmed': ('Cyclist observations confirmed', 'How often does the other sensor confirm a cyclist sample?', ''),
 'ped_path': ('Jitter-robust moving pedestrian path', 'How much pedestrian movement did each sensor record?', 'km'),
 'cyc_path': ('moving cyclist path', 'Cyclist movement recorded: with Newsense "motorcycles" counted as cyclists / cyclist label only', 'km'),
 'vru_path': ('pedestrians + cyclists combined', 'Pedestrian and cyclist movement combined', 'km'),
 'ids': ('Identifier reused', 'Tracking IDs given to a different object / instant ID swaps (83 min)', ''),
 'reattach': ('re-attached', 'Same tracking ID continued after a 5–30 s loss', ''),
 'breaks': ('Moving-track breaks', 'Track breaks per km of movement: pedestrians / cyclists / vehicles', 'per km'),
 'duration': ('Median pedestrian track duration', 'Typical (median) pedestrian tracking duration in the shared area', 's'),
 'jitter': ('Stationary jitter', 'Position wobble of standing objects: vehicles / pedestrians (steadiness, not accuracy)', 'cm'),
 'footprint': ('Detection footprint', 'Area in which each sensor reported objects', 'm²'),
 'hotspot': ('Static false pedestrians', 'Fixed-point "pedestrians" at the K1 signal pole', ''),
 'severe': ('Severe candidates', 'Severe potential-conflict candidates: TTC < 1.5 s / PET < 2 s', ''),
 'severe_agree': ('matched by the other sensor', 'Severe TTC candidates also found by the other sensor: any level / also severe', ''),
 'stationary': ('stationary VRU', 'Close-approach events with a standing person (of which at Newsense hotspot cells)', ''),
 'doubles': ('two VRU classes', 'Same object reported as two different person classes at once (pairs)', ''),
}
def row(key):
    V = D.comparison_csv(); m = V[V.metric.str.contains(CARDS[key][0], regex=False)]
    return None if m.empty else m.iloc[0]
def card(key, details=True):
    sub, title, unit = CARDS[key]; r = row(key)
    if r is None: ui.kpi(title, 'n/a', 'n/a', note='Not found in the V2 table'); return
    note = '' if str(r.interpretation).strip() in ('-', 'nan', '') else str(r.interpretation)
    for a, b in ((r'\bNS\b', 'Newsense'), (r'\bOU\b', 'Ouster'), (r'\bVRU\b', 'pedestrian/cyclist'), (r'\bPED\b', 'pedestrians'), (r'\bCYC\b', 'cyclists'), (r'\bVEH\b', 'vehicles'), (r'\bids\b', 'IDs')):
        note = re.sub(a, b, note)
    ui.kpi(title, r.newsense, r.ouster, unit, note=note)
    if details:
        with st.popover('Definition, sample and uncertainty', width='stretch'):
            st.markdown(f"**V2 metric:** {r.metric}\n\n**Definition / method:** {r.method}\n\n**Sample:** {r.sample_size}\n\n**Uncertainty:** {r.uncertainty}\n\n"
                        f"**Limitation:** {r.limitations}\n\n**Like-for-like comparison?** {r.fair}\n\n**Leans to:** {r.verdict} (evidence: {r.evidence_level})\n\n"
                        f"**Source:** {r.source} · FINAL_PACKAGE_V2/FINAL_SENSOR_COMPARISON.csv · {PERIOD}")
def grid(keys, ncol=3):
    for i in range(0, len(keys), ncol):
        cols = st.columns(ncol)
        for col, k in zip(cols, keys[i:i + ncol]):
            with col: card(k)

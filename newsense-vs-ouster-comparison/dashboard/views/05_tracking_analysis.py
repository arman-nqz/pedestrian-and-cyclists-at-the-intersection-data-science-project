"""Tracking (UI v4): how reliably did each sensor keep object tracks and IDs? Same data and V2 values; fewer elements on the page."""
import pandas as pd, numpy as np, streamlit as st, plotly.graph_objects as go
from utils import data as D, ui, page
from utils.config import C, GRP_NAME, src
NAME = {'NS': 'Newsense', 'OU': 'Ouster'}
ui.intro('Tracking', 'Once a sensor has detected someone, how long can it follow them, how often does it lose them, and what happens to their tracking ID?',
         'Ouster follows pedestrian tracks for <b>longer</b> (median 9.3 s vs 4.7 s) and shows <b>no observed tracking-ID reuse</b>. Newsense has <b>more fragmented moving tracks</b> '
         'and gave 639 tracking IDs to a different object later. Ouster instead continued the same ID after short losses 359 times; whether it was really the same person is <b>not independently verified</b>. '
         'These are consistency measures: neither sensor\'s tracking can be described as absolutely accurate.', eyebrow='Compare Sensor Performance')
page.style()
d_, b_, i_, r_ = page.v2('Median pedestrian track duration'), page.v2('Moving-track breaks'), page.v2('Identifier reused'), page.v2('re-attached')
page.metric_strip([('Median pedestrian tracking duration (shared area)', f'{d_.newsense} s', f'{d_.ouster} s', 'longer = followed for longer'),
                   ('Track breaks per km of movement: pedestrians / cyclists* / vehicles', b_.newsense, b_.ouster, '*cyclists incl. Newsense "motorcycles"; T = 2 s'),
                   ('IDs re-used for another object / instant ID swaps', i_.newsense, i_.ouster, '83 minutes'),
                   ('Same ID continued after a 5–30 s loss', r_.newsense.split(' (')[0], r_.ouster, 'Ouster re-find flag; same person not verified. Newsense: its 2 such events are re-used IDs')])
S = D.segments()

page.section('How long does each sensor follow an object?')
c1, c2 = st.columns([1, 2])
region = c1.toggle('Shared area only', True, help='Only track pieces with at least half of their samples in the area both sensors can see.')
grp = c2.pills('Object types', ['PED', 'CYC', 'MOTO', 'VEH', 'UNK'], selection_mode='multi', default=['PED', 'CYC'], format_func=lambda g: GRP_NAME[g]) or ['PED']
Q = S[S.grp.isin(grp)]; Q = Q[Q.region_share >= 0.5] if region else Q
fig = go.Figure(); med = {}
for s in ('NS', 'OU'):
    q = Q[Q.sensor == s]; med[s] = q.dur.median(); fig.add_histogram(x=q.dur.clip(upper=120), name=f"{NAME[s]} ({len(q):,} track pieces)", marker_color=C[s], opacity=0.65, xbins=dict(size=2))
fig.update_layout(barmode='overlay')
st.plotly_chart(ui.plot_style(fig, 360, 'Duration of track pieces (longer than 120 s shown at 120 s)', 'tracking duration (s)', 'number of track pieces'), width='stretch')
st.caption(f'Newsense has many more very short track pieces. This chart counts whole track pieces (medians here: Newsense {med["NS"]:.1f} s, Ouster {med["OU"]:.1f} s). '
           'The V2 values in the row above clip each track to the shared area, which shortens long Ouster tracks (pedestrians 4.7 s vs 9.3 s). Both use identical rules for both sensors.')

page.section('How often are moving tracks broken?', 'A break = a moving track ends and a new one starts nearby within T seconds, i.e. one object was split into several tracking IDs.')
B = D.jload('corr02')
win = st.segmented_control('Continuation window T', ['T = 1 s', 'T = 2 s', 'T = 3 s'], default='T = 2 s') or 'T = 2 s'; T = win[-3]
cats = [('Pedestrians', 'PED'), ('Cyclists<br>(label only)', 'CYC_ONLY'), ('Cyclists + Newsense<br>"motorcycles"', 'CYC_MOTO'), ('Vehicles', 'VEH')]
k1, k2 = st.columns([1.6, 1])
fig3 = go.Figure([go.Bar(x=[c[0] for c in cats], y=[B[f'{s}_T{T}_{k}'] for _, k in cats], name=NAME[s], marker_color=C[s], text=[B[f'{s}_T{T}_{k}'] for _, k in cats], textposition='outside') for s in ('NS', 'OU')])
fig3.update_layout(barmode='group')
k1.plotly_chart(ui.plot_style(fig3, 380, f'Track breaks per km of movement ({win})', 'object type', 'breaks per km of movement'), width='stretch')
k2.markdown("""**Reading it**
* Newsense breaks moving tracks more often in every group and for every T.
* Cyclist rates use the **same labels for breaks and distance** (correction CORR-02). The earlier value 20.9 mixed the two and is withdrawn.
* The size of the difference depends on how Ouster "UNKNOWN" fragments are counted (pedestrians 1.2–1.9×, vehicles 2.0–3.4×); the direction holds in every variant.""")
ui.source('corrections/corr02_breaks_per_robust_km.json', 'CORR-02_cyclist_break_rate.md', 'final_audit/data/fa6_fragmentation.json (sensitivity)')

page.section('What happens to tracking IDs?')
ev = S.groupby(['sensor', 'start_event']).size().unstack(0).fillna(0).astype(int)
lab = {'FIRST': 'New ID (first appearance)', 'LONG': 'ID re-used after more than 60 s (another object)', 'MID': 'ID re-used after 30–60 s', 'SHORT': 'Same ID after a 5–30 s loss', 'MASK': 'Continues across a sensor log gap', 'SWAP': 'Instant swap (jump > 15 m within 1 s)'}
e1, e2 = st.columns([1.3, 1])
e1.dataframe(pd.DataFrame({'What happened at the start of a track piece': [lab[k] for k in ev.index], 'Newsense': ev.get('NS', 0).values, 'Ouster': ev.get('OU', 0).values}), hide_index=True, width='stretch')
e2.markdown("""* **Newsense** re-issues IDs to **different** objects (639 in total: 636 after more than 60 s, median 35 m away, type changed in 85 %) and swaps IDs between objects 59 times. Its 2 "same ID after 5–30 s" events are 25 m away with a type change, i.e. also reuse.
* **Ouster** never re-used an ID for another object. It **continued** the same ID after a 5–30 s loss 359 times, each flagged by its own `refind_time`. **Whether this was the same physical person is not verified.**
* An unbroken track can still switch between two people in a group: continuity is not proof of correct identity.""")

st.markdown('## More detail')
with st.expander('Five terms that are easy to confuse'):
    st.markdown("""
| Term | Plain meaning |
|---|---|
| **ID reuse** | The sensor later gives the same tracking number to a **different** object |
| **Instant ID swap** | A tracking ID jumps more than 15 m within 1 s: it moved to another object |
| **Track fragmentation** | One object was split into several tracking IDs or track pieces |
| **Re-attachment** | After losing an object for a few seconds, the sensor continues with the **same** ID |
| **Interruption** | The sensor stops reporting the object for a while (gap) or ends the track |
""")
with st.expander('V2 table: median tracking duration in the shared area'):
    c3m = D.jload('c3_metrics')
    st.dataframe(pd.DataFrame([{'Object type': GRP_NAME[g], 'Newsense median (s)': c3m['NS_REGION']['groups'].get(g, {}).get('duration_p50'), 'Ouster median (s)': c3m['OU_REGION']['groups'].get(g, {}).get('duration_p50'),
                  'Newsense track pieces': c3m['NS_REGION']['groups'].get(g, {}).get('segments'), 'Ouster track pieces': c3m['OU_REGION']['groups'].get(g, {}).get('segments')} for g in ('PED', 'CYC', 'VEH')]), hide_index=True, width='stretch')
    ui.source('c3_track_metrics.json (shared region)')
with st.expander('Time before an ID appears again'):
    fig2 = go.Figure()
    for s in ('NS', 'OU'):
        q = S[(S.sensor == s) & S.gap_before.notna() & (S.start_event != 'SWAP')]; fig2.add_histogram(x=np.log10(q.gap_before), name=NAME[s], marker_color=C[s], opacity=0.7, xbins=dict(size=0.1))
    fig2.update_layout(barmode='overlay'); fig2.update_xaxes(tickvals=[np.log10(v) for v in (5, 10, 30, 60, 300, 1000, 3000)], ticktext=['5 s', '10 s', '30 s', '1 min', '5 min', '17 min', '50 min'])
    st.plotly_chart(ui.plot_style(fig2, 320, 'Ouster re-uses an ID after seconds (same object); Newsense after minutes (other objects)', 'time since the ID was last seen (log scale)', 'number of track pieces'), width='stretch')
    st.markdown(f"**Short losses bridged inside one ID** (not counted as breaks): gaps of 1–5 s within a track piece. Newsense **{int(S[S.sensor == 'NS'].gaps_1_5s.sum()):,}**, Ouster **{int(S[S.sensor == 'OU'].gaps_1_5s.sum()):,}** (all types, each sensor's full view).")
with st.expander('Position jumps and estimated positions'):
    J = pd.read_csv(src('a5_traj')); j = J[J.group == 'PED'].set_index('sensor')
    p1, p2 = st.columns(2)
    p1.markdown('**Pedestrian tracks with a sudden position jump**')
    p1.dataframe(pd.DataFrame({'Jump threshold': ['faster than 12 m/s and more than 1 m (C2)', 'more than 2 m and twice the limit', 'more than 3 m'], 'Newsense': [f"{j.loc['NS', c]:.1%}" for c in ('share_tracks_jump_C2', 'share_tracks_jump_D2', 'share_tracks_jump_D3')],
                               'Ouster': [f"{j.loc['OU', c]:.1%}" for c in ('share_tracks_jump_C2', 'share_tracks_jump_D2', 'share_tracks_jump_D3')]}), hide_index=True, width='stretch')
    p1.caption('Newsense never jumps (probably filtered upstream: a jump becomes a new track). Ouster jumps occur mostly inside groups (video 2/2). Smoother is not more accurate.')
    co = D.jload('c3_metrics')['OU_REGION']['groups']; p2.markdown('**Ouster estimated (predicted) positions, shared area**')
    p2.dataframe(pd.DataFrame([{'Object type': GRP_NAME[g], 'Share of samples': f"{co[g]['coasted_sample_share']:.1%}", 'Longest runs, 95th percentile (samples)': co[g]['coast_run_p95']} for g in ('PED', 'CYC', 'VEH', 'UNK')]), hide_index=True, width='stretch')
    p2.caption('Newsense does not flag estimated positions, so its share is unknown (not zero).')
    ui.source('checkpoint2_audit/trajectory_quality_audit.csv', 'c3_track_metrics.json')

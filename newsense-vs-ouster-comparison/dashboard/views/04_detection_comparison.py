"""Detection & classification (UI v4): what did each sensor detect, and how did it classify objects?
Same data and calculations as before; fewer charts on the page, the rest in expanders."""
import pandas as pd, numpy as np, streamlit as st, plotly.graph_objects as go
from utils import data as D, ui, page
from utils.config import C, PERIOD, GRP_NAME, src
from utils.timebase import clock
NAME = {'NS': 'Newsense', 'OU': 'Ouster'}
ui.intro('Detection & classification', 'What did each sensor detect, and what type did it give each object?',
         'Only <b>29.7 %</b> of Newsense pedestrian samples have an Ouster object nearby, while <b>72.1 %</b> of Ouster\'s have a Newsense object nearby. '
         'Much of the difference is Newsense "pedestrians" <b>standing still at fixed points</b>, such as the K1 signal pole. '
         'When both sensors report the same object, they often disagree on <b>pedestrian versus cyclist</b>, and the video settled only 1 of 17 such cases.',
         eyebrow='Compare Sensor Performance')
page.style()
M = D.jload('c2_match'); dc = M['detection_confirmation']
r_ped, r_cyc, r_c2p, r_dbl = page.v2('Pedestrian observations confirmed'), page.v2('Cyclist observations confirmed'), page.v2('NS Cyclist labelled PERSON'), page.v2('two VRU classes')
page.metric_strip([('Pedestrian samples confirmed by the other sensor', r_ped.newsense, r_ped.ouster, 'other sensor reports any object within 2 m, same moment'),
                   ('Cyclist samples confirmed by the other sensor', r_cyc.newsense, r_cyc.ouster, 'same rule'),
                   ('Newsense cyclists that Ouster calls PERSON', r_c2p.newsense, '–', 'among matched samples; who is right is unresolved'),
                   ('Same object reported as two person classes at once', r_dbl.newsense, r_dbl.ouster, 'persistent pairs (≥ 10 frames)')])
ui.info('<b>Read these as agreement, not accuracy.</b> There is no ground truth, and a recorded sample is one object in one frame (10 per second), not a person: one person standing for 100 s gives about 1,000 samples.')

page.section('How did the two sensors classify the same objects?', 'When both report an object at the same place and moment, which type does each give it?')
cc = M['class_agreement_classes']; ns_c = ['Pedestrian', 'Cyclist', 'Motorcycle', 'Car', 'Van', 'Truck', 'Bus']; ou_c = ['PERSON', 'BICYCLE', 'UNKNOWN', 'VEHICLE', 'LARGE_VEHICLE']
z = np.array([[cc.get(f'{a}|{b}', 0) for b in ou_c] for a in ns_c]); zr = z / np.maximum(z.sum(1, keepdims=True), 1)
a1, a2 = st.columns([1.5, 1])
fig4 = go.Figure(go.Heatmap(z=zr, x=ou_c, y=ns_c, colorscale=[[0, '#F8FAFC'], [1, C['BOTH']]], text=[[f'{p:.0%}<br>({n:,})' for p, n in zip(rp, rn)] for rp, rn in zip(zr, z)], texttemplate='%{text}', showscale=False,
                          hovertemplate='Newsense %{y} → Ouster %{x}: %{z:.0%}<extra></extra>'))
fig4.update_yaxes(autorange='reversed')
a1.plotly_chart(ui.plot_style(fig4, 430, 'Share of each Newsense type that Ouster labels as …', 'Ouster label', 'Newsense label'), width='stretch')
with a2:
    st.markdown("""**How to read it:** each row adds up to 100 %. A dark cell on the diagonal-like pattern (Pedestrian → PERSON, Car → VEHICLE) means the sensors agree.

**What stands out**
* Vehicles agree almost always (98.8–99.0 % in V2).
* **39 %** of Newsense *Cyclist* samples are *PERSON* to Ouster.
* Newsense *Motorcycle* is mostly Ouster *BICYCLE* (63 %): Newsense often calls bicycles motorcycles.
* Ouster has an *UNKNOWN* class; it starts 73 % of its pedestrian tracks as UNKNOWN in the shared area.""")
    st.caption('Source: c2c_match_main.json (C2, 47,297 frame pairs, class-agnostic 2 m matching). Who is right cannot be decided from sensor data; the video decided only 1 of 17 conflicts.')

page.section('Moving or standing?', 'How many samples of each type were moving, and how many were standing still?')
f1, f3 = st.columns([1, 1])
region = f1.segmented_control('Area', ['Shared area only (fair)', 'Each sensor\'s full view'], default='Shared area only (fair)') or 'Shared area only (fair)'
grps = st.pills('Object types', ['PED', 'CYC', 'MOTO', 'VEH', 'UNK'], selection_mode='multi', default=['PED', 'CYC', 'MOTO', 'VEH', 'UNK'], format_func=lambda g: GRP_NAME[g]) or ['PED', 'CYC']
T0, T1 = 1793254320, 1793259300
tr = f3.slider('Minutes after 07:12', 0, 83, (0, 83))
A = D.agg_minute(); A = A[A.grp.isin(grps) & A.minute.between(T0 + tr[0] * 60, T0 + tr[1] * 60 - 1)]
if region.startswith('Shared'): A = A[A.region]
g = A.groupby(['sensor', 'grp'])[['observations', 'moving_obs']].sum().reset_index(); g['stationary_obs'] = g.observations - g.moving_obs
b1, b2 = st.columns([1.5, 1])
fig = go.Figure()
for s in ('NS', 'OU'):
    q = g[g.sensor == s]
    fig.add_bar(x=[GRP_NAME[x] for x in q.grp], y=q.moving_obs, name=f'{NAME[s]}: moving', marker_color=C[s], offsetgroup=s)
    fig.add_bar(x=[GRP_NAME[x] for x in q.grp], y=q.stationary_obs, name=f'{NAME[s]}: standing', marker_color=C['NS_LIGHT' if s == 'NS' else 'OU_LIGHT'], marker_line=dict(color=C[s], width=1), offsetgroup=s, base=q.moving_obs)
fig.update_layout(barmode='group')
b1.plotly_chart(ui.plot_style(fig, 430, 'Recorded samples: moving (dark, > 0.5 m/s) and standing (light)', 'object type', 'recorded samples'), width='stretch')
hp = page.v2('Static false pedestrians')
with b2:
    st.markdown(f"""**Standing "pedestrians" and the K1 signal pole**
* Newsense reports far more **standing** pedestrian samples than Ouster. Many sit at a few **fixed points** ("hotspot cells").
* At the largest, the **K1 signal pole**, Newsense reported {hp.newsense.split('(')[1].split(';')[0]}; the video shows the signal pole and no person (9 frames checked). Ouster reports nothing there.
* Counting **every** sample, Newsense has 2.5× more pedestrians; counting **movement**, it records 0.67–0.91× of Ouster (see the expander below).
* The other nine hotspot cells are **not verified** on video.""")
    st.caption(f'{PERIOD}; {clock(T0 + tr[0] * 60)}–{clock(T0 + tr[1] * 60)}; area: {region}.')

page.section('Why do the labels disagree?')
st.markdown("""* **Different vocabularies.** Newsense: Pedestrian, Cyclist, Motorcycle, Car, Van, Truck, Bus. Ouster: PERSON, BICYCLE, VEHICLE, LARGE_VEHICLE, UNKNOWN. Comparisons use coarse groups.
* **Pedestrian versus cyclist** is the hardest boundary for both: a person pushing a bike, or a slow cyclist, can reasonably be either.
* **Labels change within one track:** both sensors relabel objects as they move (details below). Newsense also reports one object as two person types at the same time (628 persistent pairs vs 1 for Ouster).
* **No ground truth:** the video could decide only 1 of 17 sampled disagreements, so neither sensor can be called "right".""")

st.markdown('## More detail')
with st.expander('Confirmation by object type (table and chart)'):
    st.dataframe(pd.DataFrame([{'Object type (reporting sensor)': GRP_NAME[k], 'Sensor': NAME[s], 'Recorded samples': v['n'], 'Confirmed by the other sensor': v['matched'], 'Share': f"{v['share']:.1%}"} for s in ('NS', 'OU') for k, v in dc[s].items()]), hide_index=True, width='stretch')
    cf = go.Figure()
    for s in ('NS', 'OU'):
        ks = [k for k in ('PED', 'CYC', 'VEH') if k in dc[s]]
        cf.add_bar(x=[GRP_NAME[k] for k in ks], y=[dc[s][k]['share'] * 100 for k in ks], name=f'{NAME[s]} samples confirmed by {NAME["OU" if s == "NS" else "NS"]}', marker_color=C[s], text=[f"{dc[s][k]['share']:.1%}" for k in ks], textposition='outside')
    cf.update_layout(barmode='group'); cf.update_yaxes(range=[0, 105])
    st.plotly_chart(ui.plot_style(cf, 360, 'Share of samples with an object of the other sensor within 2 m', 'object type', 'confirmed (%)'), width='stretch')
    st.caption('Class-agnostic: any object of the other sensor counts. Changing the 2 m gate to 1–3 m changes shares by at most 3 percentage points (C2). Source: c2c_match_main.json.')
with st.expander('The pedestrian ratio depends on what you count'):
    Rr = pd.read_csv(src('a2_ratio')); rp = D.jload('corr01b')
    rows = list(zip(Rr.description, Rr.ratio_ns_over_ou)) + [('robust moving path (CORR-01, movement measure)', round(rp['NS']['PED'] / rp['OU']['PED'], 2))]
    fig5 = go.Figure(go.Bar(y=[r[0] for r in rows], x=[r[1] for r in rows], orientation='h', marker_color=[C['NS'] if v > 1 else C['OU'] for _, v in rows], text=[f'{v:.2f}' for _, v in rows], textposition='outside'))
    fig5.add_vline(x=1, line_dash='dash', line_color=C['INK']); fig5.update_yaxes(autorange='reversed')
    st.plotly_chart(ui.plot_style(fig5, 420, 'Newsense ÷ Ouster, pedestrians (blue: Newsense higher; green: Ouster higher)', 'ratio Newsense / Ouster (1 = equal)', None), width='stretch')
    st.caption('Counting every sample gives 2.5×; movement-based measures give 0.67–0.91×. The ">0.3 m/s" ratio (1.12) still includes Newsense position jitter. Sources: pedestrian_ratio_recalculation.csv, corr01b_robust_path.json.')
with st.expander('Track pieces by type, moving and standing'):
    S = D.segments(); S = S[S.grp.isin(grps) & (S.t1 >= T0 + tr[0] * 60) & (S.t0 <= T0 + tr[1] * 60)]
    if region.startswith('Shared'): S = S[S.region_share >= 0.5]
    sg = S.assign(moving=S.robust_path > 2).groupby(['sensor', 'grp', 'moving']).size().reset_index(name='n')
    fig2 = go.Figure()
    for s in ('NS', 'OU'):
        for mv in (True, False):
            q = sg[(sg.sensor == s) & (sg.moving == mv)]
            fig2.add_bar(x=[GRP_NAME[x] for x in q.grp], y=q.n, name=f"{NAME[s]}: {'moving' if mv else 'standing'}", marker_color=C[s] if mv else C['NS_LIGHT' if s == 'NS' else 'OU_LIGHT'], marker_line=dict(color=C[s], width=1), offsetgroup=s)
    fig2.update_layout(barmode='stack'); st.plotly_chart(ui.plot_style(fig2, 360, 'Track pieces by main object type (moving = moved more than 2 m)', 'object type', 'track pieces'), width='stretch')
    st.caption('Track pieces are not people: Newsense splits one person into several pieces more often (see Tracking). Uses the filters above.')
with st.expander('Label changes within one track'):
    T = D.class_transitions(); T['Change'] = T.from_cls + ' → ' + T.to_cls
    c1, c2 = st.columns(2)
    for col, s in ((c1, 'NS'), (c2, 'OU')):
        q = T[T.sensor == s].sort_values('n', ascending=False).head(8)
        col.markdown(f"**{NAME[s]}**: {int(T[T.sensor == s].n.sum()):,} type changes in total"); col.dataframe(q[['Change', 'n']].rename(columns={'n': 'Count'}), hide_index=True, width='stretch')
    C3 = D.jload('c3_metrics'); d = C3['NS_doubles_FULL']; o = C3['OU_doubles_FULL']
    st.markdown(f"**Same object, two types at once** (two IDs less than 0.3 m apart with different types for at least 10 frames): Newsense **{d['pairs_persistent_ge10_frames']}** pairs ({', '.join(f'{k} {v}' for k, v in d['persistent_by_classes'].items())}); Ouster **{o['pairs_persistent_ge10_frames']}**.")
with st.expander('Recorded samples per minute'):
    ts = A.groupby(['sensor', 'minute', 'grp']).observations.sum().reset_index()
    fig3 = go.Figure()
    for (s, gg), q in ts.groupby(['sensor', 'grp']):
        fig3.add_scatter(x=[clock(t) for t in q.minute], y=q.observations, name=f'{NAME[s]} {GRP_NAME[gg]}', line=dict(color=C[s], dash={'PED': 'solid', 'CYC': 'dash', 'MOTO': 'dot', 'VEH': 'longdash', 'UNK': 'dashdot'}[gg]))
    st.plotly_chart(ui.plot_style(fig3, 340, 'Recorded samples per minute', 'time (CET)', 'samples per minute'), width='stretch')
with st.expander('Newsense on both mornings (time of day)'):
    st.caption('Newsense only: Ouster object data exist for 83 minutes on 29 Oct.')
    C6 = D.jload('c6_15min')
    days = st.pills('Dates', list(C6), selection_mode='multi', default=list(C6)) or list(C6)
    VAR = {'PED_path_m': 'moving pedestrian distance (m)', 'CYC_path_m': 'moving cyclist distance (m)', 'VEH_path_m': 'vehicle distance (m)', 'stat_PED_s_hot': 'standing "pedestrian" seconds at hotspot points', 'stat_PED_s_other': 'standing pedestrian seconds elsewhere'}
    var = st.selectbox('Quantity', list(VAR), format_func=VAR.get)
    f6 = go.Figure()
    for dd, dash in zip(days, ('dot', 'solid')):
        k = sorted(C6[dd]); f6.add_scatter(x=k, y=[C6[dd][qq].get(var, 0) for qq in k], name=dd, line=dict(color=C['NS'], dash=dash, width=2))
    st.plotly_chart(ui.plot_style(f6, 320, 'Newsense, per 15 minutes, shared area, 06:00–13:00', 'time of day (CET)', VAR[var]), width='stretch')
    st.caption('Both mornings peak at 07:30–07:45 and daily totals agree within 5 % (V2). Standing "pedestrians" at hotspots were 2.4× higher on 29 Oct (likely a configuration change), so they are not comparable between days. Source: c6_ns_15min.json.')
with st.expander('Definitions'):
    st.markdown("""* **Recorded sample (observation):** one object in one sensor frame (10 per second).
* **Confirmed:** the other sensor reports any object within 2 m at the same moment (class-agnostic; C2).
* **Moving:** reported speed above 0.5 m/s (samples) or more than 2 m robust movement (track pieces).
* **Shared area:** the 2,780 m² both sensors can see (C1); fair comparisons use only this area.
* **Hotspot cells:** ten 2 m cells with persistent standing Newsense pedestrians (C2 audit).""")
ui.source('dashboard/data (from the original object lists)', 'c2c_match_main.json', 'c3_track_metrics.json', 'FINAL_PACKAGE_V2/FINAL_SENSOR_COMPARISON.csv')

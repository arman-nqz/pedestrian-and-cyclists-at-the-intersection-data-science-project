"""Movement paths (UI v4): what movement trajectories did each sensor record? Same data; path view and single-track inspection in two tabs."""
import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import data as D, ui, page
from utils.config import C, GRP_NAME
from utils.timebase import clock
NAME = {'NS': 'Newsense', 'OU': 'Ouster'}
ui.intro('Movement paths', 'What movement paths did each sensor record? Choose an object type and a time window, compare the two sensors side by side, then inspect any single track.',
         'Ouster draws <b>longer, more continuous paths</b> and reaches further across the junction; Newsense paths are shorter and more often broken into pieces. '
         'A smooth, complete-looking path is not proof of accuracy: there is no ground truth for positions.', eyebrow='Compare Sensor Performance')
page.style()
S = D.segments(); T0 = 1793254320
f1, f2, f3, f4 = st.columns([1, 1.3, 1, 1])
grp = f1.selectbox('Object type', ['PED', 'CYC', 'MOTO', 'VEH', 'UNK'], format_func=lambda g: GRP_NAME[g])
tr = f2.slider('Minutes after 07:12', 0, 83, (10, 30))
shared = f3.toggle('Shared area only', True, help='Outside the shared area the other sensor cannot see anything, so comparing there would be unfair.')
nmax = f4.slider('Tracks drawn per sensor (most)', 50, 600, 250, 50)
Q = S[(S.grp == grp) & (S.robust_path > 2) & (S.t0 <= T0 + tr[1] * 60) & (S.t1 >= T0 + tr[0] * 60)]
if shared: Q = Q[Q.region_share >= 0.8]
st.caption(f'Moving {GRP_NAME[grp]} tracks (moved more than 2 m), {clock(T0 + tr[0] * 60)}–{clock(T0 + tr[1] * 60)} on 29 Oct 2026.')
tab1, tab2 = st.tabs(['Movement paths of both sensors', 'Inspect one track ›'])
with tab1:
    fig = make_subplots(1, 2, subplot_titles=('Newsense', 'Ouster'), shared_xaxes=True, shared_yaxes=True, horizontal_spacing=0.03)
    stats = {}
    for j, s in enumerate(('NS', 'OU')):
        q = Q[Q.sensor == s].sort_values('robust_path', ascending=False).head(nmax); O = D.obs(s); xs, ys = [], []
        for k in q.seg:
            h = O.seg(k); xs += list(h.x[::3]) + [None]; ys += list(h.y[::3]) + [None]
        fig.add_trace(go.Scattergl(x=xs, y=ys, mode='lines', line=dict(color=C[s], width=1), opacity=0.35, name=NAME[s], hoverinfo='skip'), 1, j + 1)
        qq = Q[Q.sensor == s]
        stats[NAME[s]] = {'Moving tracks': f'{len(qq):,} ({len(q):,} drawn)', 'Median tracking duration (s)': round(qq.dur.median(), 1) if len(qq) else '–',
                          'Median movement distance per track (m)': round(qq.robust_path.median(), 1) if len(qq) else '–', 'Total movement distance (m)': f'{round(qq.robust_path.sum()):,}',
                          'Tracks with 1–5 s interruptions': int((qq.gaps_1_5s > 0).sum()), 'Tracks with type changes': int((qq.class_changes > 0).sum())}
    fig.update_yaxes(scaleanchor='x', scaleratio=1); fig.update_layout(showlegend=False)
    fig.update_xaxes(title_text='x (m), Ouster frame; north not verified'); fig.update_yaxes(title_text='y (m)', col=1)
    st.plotly_chart(ui.plot_style(fig, 580, None), width='stretch')
    a, b = st.columns([1.2, 1])
    a.dataframe(pd.DataFrame(stats).astype(str), width='stretch')
    b.markdown("""**What to notice**
* **Length:** Ouster tracks run further across the junction; Newsense tracks stop and restart more often (more, shorter pieces).
* **Continuity:** the number of tracks is not the number of people: one person split into three pieces counts three times.
* **Coverage:** Ouster also draws paths where Newsense cannot see (switch off *Shared area only*).""")
    st.caption('Movement distance = robust moving path (1-s steps of at least 0.5 m, CORR-01). Longest tracks are drawn first.')
with tab2:
    st.markdown('**Click a row** to see that track\'s path, speed and position over time. You can then open it in *Follow One Person* with the video.')
    sens = st.segmented_control('Sensor', ['Both', 'Newsense', 'Ouster'], default='Both') or 'Both'
    lst = Q if sens == 'Both' else Q[Q.sensor == ('NS' if sens == 'Newsense' else 'OU')]
    lst = lst.sort_values('t0')[['seg', 'sensor', 'id', 't0', 'dur', 'robust_path', 'classes', 'start_event']].copy()
    tbl = pd.DataFrame({'Sensor': lst.sensor.map(NAME), 'Tracking ID': lst.id, 'Start': [clock(t) for t in lst.t0], 'Duration (s)': lst.dur.round(1), 'Movement distance (m)': lst.robust_path.round(1),
                        'Types reported': lst.classes, 'ID event at start': lst.start_event, 'Track key': lst.seg}).reset_index(drop=True)
    sel = st.dataframe(tbl, hide_index=True, width='stretch', height=280, on_select='rerun', selection_mode='single-row')
    if sel and sel.selection.rows:
        key = tbl.iloc[sel.selection.rows[0]]['Track key']; s = key[:2]; h = D.obs(s).seg(key); co = h.coasted.values.astype(bool); tt = [clock(t, True) for t in h.t]
        g = make_subplots(2, 2, column_widths=[0.45, 0.55], specs=[[{'rowspan': 2}, {}], [None, {}]], subplot_titles=('Path (colour = time)', 'Reported speed', 'Position over time'), vertical_spacing=0.18)
        g.add_trace(go.Scatter(x=h.x, y=h.y, mode='lines+markers', marker=dict(size=5, color=h.t - h.t.min(), colorscale=[[0, '#E2E8F0'], [1, C[s]]], line=dict(width=0)), line=dict(color=C[s], width=1), name='reported position',
                               customdata=tt, hovertemplate='%{customdata}<br>x %{x:.2f}, y %{y:.2f}<extra></extra>'), 1, 1)
        if co.any(): g.add_trace(go.Scatter(x=h.x[co], y=h.y[co], mode='markers', marker=dict(symbol='circle-open', size=9, color=C['UNCERTAIN']), name='Ouster estimated position'), 1, 1)
        g.add_trace(go.Scatter(x=tt, y=h.speed, name='speed (m/s)', line=dict(color=C[s])), 1, 2)
        g.add_trace(go.Scatter(x=tt, y=h.x, name='x (m)', line=dict(color='#94A3B8')), 2, 2); g.add_trace(go.Scatter(x=tt, y=h.y, name='y (m)', line=dict(color='#475569', dash='dot')), 2, 2)
        g.update_yaxes(scaleanchor='x', scaleratio=1, row=1, col=1, title_text='y (m)'); g.update_xaxes(title_text='x (m)', row=1, col=1)
        g.update_yaxes(title_text='m/s', row=1, col=2); g.update_yaxes(title_text='m', row=2, col=2)
        st.plotly_chart(ui.plot_style(g, 520, None), width='stretch')
        d = np.diff(h.t.values); st_ = np.hypot(np.diff(h.x.values), np.diff(h.y.values))
        st.markdown(f"**{NAME[s]} ID {h.id.iloc[0]}** · {len(h):,} samples · {h.t.iloc[-1] - h.t.iloc[0]:.1f} s · interruptions > 0.35 s: {(d > 0.35).sum()} · largest single step: {st_.max():.2f} m · estimated positions: {int(co.sum())}")
        Cn, M = D.candidates(); inv = M[M.seg == key].inv
        if len(inv) and st.button(f'Follow this object with the video (Investigation #{inv.iloc[0].split("-")[1]})', type='primary'):
            st.session_state['inv'] = inv.iloc[0]; st.switch_page(st.session_state['_pages']['follow'] if '_pages' in st.session_state else 'views/02_object_investigation.py')
ui.source('dashboard/data/segments.parquet + obs_seg_*.parquet (original object lists; C3 segmentation; CORR-01 robust path)')

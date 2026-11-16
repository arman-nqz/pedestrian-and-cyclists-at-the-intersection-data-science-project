import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
from utils import data as D, ui, page
from utils.config import C, GRP_NAME
from utils.timebase import clock
from components import player
ui.intro('Potential conflicts', 'Where might pedestrians or cyclists and vehicles have come dangerously close? Safety indicators (time to collision, post-encroachment time, distance) are computed with identical rules for both sensors.',
         'Each sensor flags a similar number of severe candidates with moving pedestrians or cyclists (time to collision: 31 Newsense, 35 Ouster), but they <b>rarely flag the same ones</b>: '
         'only 1 of 31 and 1 of 35 is also severe in the other sensor. Lists of conflicts are therefore largely sensor-specific. These are <b>candidates for review, not confirmed near-misses</b>.', eyebrow='Compare Sensor Performance')
ui.warn('<b>These are not accidents or confirmed near-misses.</b> Each event is a surrogate indicator computed from one sensor\'s tracks. No signal-violation or phase-specific analysis is possible (timing CK-01 unresolved; no surveyed stop lines).')
E = D.events(); AG = D.jload('c7_agreement_v3')
page.style()
sv, sa = page.v2('Severe candidates'), page.v2('matched by the other sensor')
page.metric_strip([('Severe candidates with moving pedestrians/cyclists: TTC < 1.5 s / PET < 2 s', sv.newsense, sv.ouster, 'counts of candidate events, not of people or accidents'),
                   ('Severe TTC events found by the other sensor: at any level', sa.newsense.split(' / ')[0], sa.ouster.split(' / ')[0], 'other sensor has a TTC event < 3 s within ±2 s and 5 m'),
                   ('… and also severe there', sa.newsense.split(' / ')[1], sa.ouster.split(' / ')[1], 'about 1 event in 30')])
page.section('Does the other sensor see the same events?', 'For each severe event of one sensor: does the other sensor report an event of the same kind nearby (any level), and is that event also severe?')
rows = []
for k, lab in (('TTC', 'TTC < 1.5 s'), ('PET', 'PET < 2 s (crossing ≥ 30°)'), ('PROX', 'distance < 3 m')):
    a, b = AG[f'NS_{k}_moving'], AG[f'OU_{k}_moving']
    rows.append({'Indicator (severe)': lab, 'Newsense events': a['n'], 'Ouster events': b['n'], 'NS found by OU — any level': f"{a['any_level']}/{a['n']}", 'OU found by NS — any level': f"{b['any_level']}/{b['n']}",
                 'NS found by OU — also severe': f"{a['severe_both']}/{a['n']}", 'OU found by NS — also severe': f"{b['severe_both']}/{b['n']}"})
st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
st.markdown("""**Two agreement definitions (V2).** *Any level*: the other sensor has an event of the same kind within ±2 s and 5 m at any recorded level (TTC < 3 s, PET < 3 s). *Also severe*: that event is itself severe.
On severity the sensors agree on about **1 event in 30** (TTC: 1/31 and 1/35). Conflict lists are therefore largely sensor-specific.""")
ui.source('checkpoint7_interactions/data/c7_agreement_v3.json', 'c7_events_v2_*.csv (unchanged C7 v2 events)')
with st.expander('Close-approach events with a standing pedestrian (and why they are treated separately)'):
    stv = page.v2('stationary VRU')
    st.markdown(f"""* **TTC < 3 s events with a standing pedestrian or cyclist:** Newsense **{stv.newsense}**, Ouster **{stv.ouster}** (in brackets: of these, inside the 10 Newsense hotspot cells).
* About half of Newsense's standing-pedestrian events lie in its hotspot cells, where Newsense persistently reports standing "pedestrians" (shown to be infrastructure on video only at the K1 signal pole). No event is labelled spurious or real: they are unverified.
* The main agreement figures above therefore use **moving** pedestrians and cyclists only. Use the *Pedestrian/cyclist state* filter below to include standing ones.

Source: FINAL_PACKAGE_V2/FINAL_SENSOR_COMPARISON.csv.""")
with st.expander('What are TTC, PET and proximity?'):
    st.markdown('**Time to collision (TTC):** if both kept their current speed and direction, how many seconds until they would meet? Severe below 1.5 s. **Post-encroachment time (PET):** the time between one road user leaving a spot and the other arriving there (paths crossing at 30° or more). Severe below 2 s. **Proximity:** centres closer than 3 m while the vehicle moves faster than 2 m/s.')
page.section('Explore the events', 'Filter the candidates, see where they happened, and select one in the table to watch it in the original video with both sensors.')
f1, f2, f3, f4, f5 = st.columns(5)
kind = f1.multiselect('Indicator', ['TTC', 'PET', 'PROX'], ['TTC', 'PET'])
sev = f2.radio('Severity', ['Severe only', 'All recorded'], index=0)
state = f3.multiselect('Pedestrian/cyclist state', ['moving', 'stationary'], ['moving'])
sens = f4.multiselect('Sensor', ['NS', 'OU'], ['NS', 'OU'], format_func=lambda s: 'Newsense' if s == 'NS' else 'Ouster')
agr = f5.selectbox('Other sensor', ['any', 'found (any level)', 'found (also severe)', 'not found'])
q = E[E.kind.isin(kind) & E.vru_state.isin(state) & E.sensor.isin(sens)]
if sev == 'Severe only': q = q[q.severe]
if agr == 'found (any level)': q = q[q.other_any_level]
elif agr == 'found (also severe)': q = q[q.other_also_severe]
elif agr == 'not found': q = q[~q.other_any_level]
hot = {tuple(int(v // 2) for v in c) for c in D.jload('a2_counts')['hotspot_cells']}
q = q.assign(hotspot=[(int(np.floor(x / 2)), int(np.floor(y / 2))) in hot for x, y in zip(q.x, q.y)])
tbl = pd.DataFrame({'Time': [clock(t, True) for t in q.t], 'Sensor': q.sensor.map({'NS': 'Newsense', 'OU': 'Ouster'}), 'Indicator': q.kind, 'Value': q.value.round(2), 'Severe': q.severe,
                    'Pedestrian / cyclist': q.vru_class.map(GRP_NAME) + ' (' + q.vru_state + ')', 'Vehicle': q.veh_class, 'Angle (°)': q.angle, 'Vehicle speed (m/s)': q.veh_speed,
                    'Other sensor: any level': q.other_any_level, 'Other sensor: also severe': q.other_also_severe, 'In NS hotspot cell': q.hotspot,
                    'Estimated position involved': q.coasted.astype(bool), 'x': q.x, 'y': q.y, 't_raw': q.t, 'VRU segment': q.vru_seg, 'Vehicle segment': q.veh_seg}).sort_values('Time').reset_index(drop=True)
m1, m2 = st.columns([1.4, 1])
with m1:
    st.caption(f'{len(tbl):,} events match. Select one to open its video and tracks.')
    sel = st.dataframe(tbl.drop(columns=['x', 'y', 't_raw']), hide_index=True, width='stretch', height=360, on_select='rerun', selection_mode='single-row')
    st.download_button('Export (CSV)', tbl.to_csv(index=False).encode(), 'k305_conflict_candidates.csv', 'text/csv')
fig = go.Figure()
for s in ('NS', 'OU'):
    qq = tbl[tbl.Sensor == ('Newsense' if s == 'NS' else 'Ouster')]
    fig.add_scatter(x=qq.x, y=qq.y, mode='markers', name='Newsense' if s == 'NS' else 'Ouster', marker=dict(color=C[s], size=8, symbol=['circle' if a else 'x' for a in qq['Other sensor: any level']], line=dict(width=1, color='white')))
bg = D.background(); fig.add_scattergl(x=[c[0] + .5 for c in bg], y=[c[1] + .5 for c in bg], mode='markers', marker=dict(size=3, color='#CBD5E1'), name='pedestrian and cyclist activity (context)', hoverinfo='skip')
fig.data = fig.data[::-1]; fig.update_yaxes(scaleanchor='x', scaleratio=1); fig.update_layout(title='Where the events happened (● other sensor also has an event, ✕ not)')
m2.plotly_chart(ui.plot_style(fig, 480, None, 'x position (m)', 'y position (m)').update_layout(legend=dict(orientation='h', y=-0.2, x=0, xanchor='left', yanchor='top')), width='stretch')
if sel and sel.selection.rows:
    r = tbl.iloc[sel.selection.rows[0]]; t = float(r.t_raw)
    st.markdown(f"### {r.Sensor} {r.Indicator} = {r.Value} · {r['Pedestrian / cyclist']} and {r.Vehicle} at {r.Time}")
    st.markdown(f"Threshold: {'TTC < 1.5 s severe, < 3 s recorded' if r.Indicator == 'TTC' else 'PET < 2 s severe, < 3 s recorded; paths crossing ≥ 30°' if r.Indicator == 'PET' else 'centre distance < 3 m with vehicle > 2 m/s'}. "
                f"Other sensor: {'an event of the same kind nearby' if r['Other sensor: any level'] else 'no corresponding event'}{' (also severe)' if r['Other sensor: also severe'] else ''}."
                + (' **Inside a Newsense hotspot cell (static false objects documented there).**' if r['In NS hotspot cell'] else ''))
    ev = [dict(t=float(t), s=r['VRU segment'][:2], label=f'{r.Indicator} = {r.Value}', kind='conflict')]
    other = E[(E.sensor != r['VRU segment'][:2]) & ((E.t - t).abs() <= 2) & (((E.x - r.x) ** 2 + (E.y - r.y) ** 2) ** 0.5 <= 5)]
    ev += [dict(t=float(o.t), s=o.sensor, label=f"other sensor: {o.kind} = {o.value:.2f}", kind='conflict') for o in other.itertuples()]
    segs = [r['VRU segment'], r['Vehicle segment']] + list(other.vru_seg) + list(other.veh_seg)
    p = player.build_payload(float(t) - 8, float(t) + 6, list(dict.fromkeys(segs)), ev, margin=8)
    p['tStart'] = float(t) - 4; player.render(p)
    st.caption('Selected = the VRU and vehicle of this event, plus the participants of corresponding events of the other sensor. Watch whether a real interaction is visible; a single sensor event is not evidence of a near-miss.')
ui.source('dashboard/data/events.parquet (from checkpoint7_interactions/data/c7_events_v2_*.csv)', 'agreement rule as c7_agreement_v3.py')

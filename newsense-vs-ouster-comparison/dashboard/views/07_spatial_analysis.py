import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import data as D, ui, page
from utils.config import C, GRP_NAME
ui.intro('Where objects are seen', 'Where does each sensor report pedestrians, cyclists and vehicles, and how large is the area each one can see?',
         'Ouster reports objects over an area about <b>3.5 times larger</b> than Newsense (10,172 vs 2,908 m²). Newsense\'s standing "pedestrians" concentrate at a few <b>fixed points</b>; '
         'the largest is at the K1 signal pole, where the video shows no person. Reporting objects somewhere does not prove good detection there.', eyebrow='Compare Sensor Performance')
page.style()
page.section('Where does each sensor report objects?', 'Choose an object type and whether it was moving or standing. Each square is a 2 m × 2 m cell on the ground.')
H = D.heat(); F = D.jload('c1f'); hot = D.jload('a2_counts')['hotspot_cells']
c1, c2, c3, c4 = st.columns(4)
grp = c1.selectbox('Object type', ['PED', 'CYC', 'MOTO', 'VEH', 'UNK'], format_func=lambda g: GRP_NAME[g])
state = c2.radio('Motion', ['moving', 'stationary', 'both'], horizontal=True, format_func=lambda v: {'moving': 'moving', 'stationary': 'standing', 'both': 'both'}[v])
view = c3.radio('View', ['Side by side', 'Difference (shared area)'], horizontal=True)
shared = c4.toggle('Shared area only', False); showhot = c4.toggle('Mark the 10 Newsense hotspot points', True)
q = H[H.grp == grp] if state == 'both' else H[(H.grp == grp) & (H.state == state)]
if shared: q = q[q.region]
q = q.groupby(['sensor', 'cx', 'cy']).observations.sum().reset_index()
xr, yr = (-100, 100), (-100, 100)
def grid(s, step=2):
    g = q[q.sensor == s].assign(gx=lambda d: (d.cx // step) * step, gy=lambda d: (d.cy // step) * step).groupby(['gx', 'gy']).observations.sum()
    xs = np.arange(-100, 100, step); ys = np.arange(-100, 100, step); z = np.full((len(ys), len(xs)), np.nan)
    for (gx, gy), v in g.items():
        if -100 <= gx < 100 and -100 <= gy < 100: z[int((gy + 100) // step), int((gx + 100) // step)] = v
    return xs + step / 2, ys + step / 2, z
def hotlayer(fig, r=1, c=1):
    if not showhot: return
    tr = go.Scatter(x=[h[0] for h in hot], y=[h[1] for h in hot], mode='markers', marker=dict(symbol='square-open', size=14, color=C['UNCERTAIN'], line=dict(width=2)), name='Newsense hotspot cell', showlegend=(c == 1))
    if getattr(fig, '_grid_ref', None) is not None: fig.add_trace(tr, r, c)
    else: fig.add_trace(tr)        # single-panel 'Difference' view (fixes a crash present since UI v1)
if view == 'Side by side':
    fig = make_subplots(1, 2, subplot_titles=('Newsense', 'Ouster'), shared_yaxes=True, horizontal_spacing=0.04)
    for j, s in enumerate(('NS', 'OU')):
        xs, ys, z = grid(s); scale = [[0, '#F8FAFC'], [0.3, C['NS_LIGHT' if s == 'NS' else 'OU_LIGHT']], [1, C[s]]]
        fig.add_trace(go.Heatmap(x=xs, y=ys, z=np.log10(z), colorscale=scale, showscale=False, hovertemplate='x %{x} m, y %{y} m<br>log10 recorded samples %{z:.2f}<extra></extra>'), 1, j + 1); hotlayer(fig, 1, j + 1)
    fig.update_xaxes(range=[-75, 75]); fig.update_yaxes(range=[-75, 75], scaleanchor='x', scaleratio=1)
    fig.update_layout(title=f'{GRP_NAME[grp]} recorded samples per 2 m cell ({state}; logarithmic colour scale)')
else:
    xs, ys, zn = grid('NS'); _, _, zo = grid('OU'); com = {tuple(c) for c in F['common_region']['cells_any']}
    share = np.where(np.isnan(zn) & np.isnan(zo), np.nan, np.nan_to_num(zn) / (np.nan_to_num(zn) + np.nan_to_num(zo) + 1e-9))
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            if (int((x - 1) // 2), int((y - 1) // 2)) not in com: share[i, j] = np.nan
    fig = go.Figure(go.Heatmap(x=xs, y=ys, z=share, zmin=0, zmax=1, colorscale=[[0, C['OU']], [0.5, '#F1F5F9'], [1, C['NS']]], colorbar=dict(title='Newsense share'),
                               hovertemplate='x %{x} m, y %{y} m<br>Newsense share %{z:.0%}<extra></extra>'))
    fig.update_xaxes(range=[-45, 40]); fig.update_yaxes(range=[-40, 45], scaleanchor='x', scaleratio=1)
    fig.update_layout(title=f'Which sensor reports more {GRP_NAME[grp]} samples ({state}) — shared area only'); hotlayer(fig)
st.markdown(f"""<div class='k-info'><b>How to read the map:</b> darker = <b>more recorded samples</b> in that cell (one object in one frame, 10 per second), <b>not more individual people</b>: one person standing for a minute makes a cell dark.
{'Orange squares mark the ten Newsense hotspot cells (persistent standing Newsense pedestrians).' if showhot else ''} Axes are the Ouster coordinate frame in metres; there is no official map, so north, street names and zones are not shown.</div>""", unsafe_allow_html=True)
st.plotly_chart(ui.plot_style(fig, 640, None, 'x position (m), Ouster frame; north not verified', 'y position (m)'), width='stretch')
st.caption('Standing Newsense pedestrians cluster at fixed points; at the largest, the K1 signal pole, the video shows the pole and no person. The other hotspot cells are not verified on video.')
page.section('How large is the area each sensor can see?', 'Cells where each sensor reported any object in at least 3 different 10-second periods (29 Oct 07:12–08:35).')
cells = {'Both sensors (common region)': F['common_region']['cells_any'], 'Newsense only': F['exclusive_cells']['ANY']['newsense_only'], 'Ouster only': F['exclusive_cells']['ANY']['ouster_only']}
cf = go.Figure()
for (name, cl), col in zip(cells.items(), (C['BOTH'], C['NS'], C['OU'])):
    cf.add_trace(go.Scattergl(x=[c[0] * 2 + 1 for c in cl], y=[c[1] * 2 + 1 for c in cl], mode='markers', marker=dict(symbol='square', size=4, color=col), name=f'{name}: {len(cl) * 4:,} m²'))
cf.update_yaxes(scaleanchor='x', scaleratio=1); cf.update_layout(title='Detection footprint per sensor (2 m cells)')
a, b = st.columns([1.3, 1]); a.plotly_chart(ui.plot_style(cf, 560, None, 'x position (m)', 'y position (m)').update_layout(legend=dict(orientation='h', y=-0.16, x=0, xanchor='left', yanchor='top')), width='stretch')
b.markdown("""* Ouster's footprint is **3.5×** Newsense's (2.3–4.8× depending on class group and threshold). Newsense ends about 40–47 m from its origin; Ouster reaches about 97 m.
* A footprint shows where a sensor **reported** objects. It does not prove good detection there; Ouster's far-range quality is unverified (OU-12).
* C1 §9 item 7 ("Ouster coverage is smaller") is **withdrawn** (C1 correction note 01): it measured where stationary Newsense vehicles lie, not area.
* A small zone where Newsense reports stationary vehicles that Ouster does not report as vehicles is **unresolved** (U-02): occlusion or Newsense false objects.
* Every cross-sensor number in this dashboard is restricted to the shared area unless stated.""")
ui.source('dashboard/data/heat.parquet (original object lists)', 'checkpoint1_geometry/data/c1f_coverage.json', 'checkpoint2_audit/data/a2_counts.json (hotspot cells)', 'C1_CORRECTION_NOTE_01_coverage.md')

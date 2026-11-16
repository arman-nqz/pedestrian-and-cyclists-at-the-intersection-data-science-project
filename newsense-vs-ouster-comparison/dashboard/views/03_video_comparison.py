"""Watch the Sensors (UI v2): any moment of the original video with both sensors' detections, on the video and on two maps."""
import os
import pandas as pd, streamlit as st
from utils import data as D, ui, timebase as TB, scene
from utils.config import RAW
from utils.timebase import clock
from components import player
ui.intro('Watch the Sensors', 'What happened at the intersection at a given moment, and what did each sensor report? Choose a time and play the original camera recording with the detections of both sensors drawn on top and on two maps.',
         'Look for <b>coloured dots without a person</b> (a sensor reports something the camera does not show) and <b>people without a dot</b> (a sensor missed someone, or the person is outside its view). '
         'The video helps you judge, but it is not a perfect ground truth: it is hazy in the distance and only one camera view is available.', eyebrow='Explore', finding_title='What to look for')
T0, T1 = 1793254320.0, 1793259300.0
c1, c2, c3 = st.columns([2, 1, 2])
start = c1.slider('Start time (29 Oct 2026, CET)', 0, int(T1 - T0 - 30), int(1793256000 - T0), step=5, format='+%d s', help='Seconds after 07:12:00, the start of the compared period.')
c1.caption(f'The window starts at **{clock(T0 + start)}**')
dur = c2.select_slider('Window length', [30, 60, 90, 120, 180], 60, format_func=lambda v: f'{v} s')
mode = c3.segmented_control('Show on the video', ['Both sensors', 'Newsense', 'Ouster', 'Video only'], default='Both sensors') or 'Both sensors'
with st.expander('Options: object types and map style'):
    classes = st.pills('Highlight these object types (others are grey)', ['PED', 'CYC', 'MOTO', 'VEH', 'UNK'], selection_mode='multi', default=['PED', 'CYC', 'MOTO'],
                       format_func=lambda g: {'PED': 'Pedestrians', 'CYC': 'Cyclists', 'MOTO': 'Motorcycles (Newsense)', 'VEH': 'Vehicles', 'UNK': 'Unknown (Ouster)'}[g]) or ['PED', 'CYC', 'MOTO']
    sym = st.toggle('Highlight symmetrically: also highlight the other sensor\'s objects that come within 2 m of a highlighted object', True,
                    help='Each sensor uses its own labels (Newsense "Cyclist" vs Ouster "PERSON", for example). Without this option, a person labelled differently by the two sensors is highlighted in only one of them.')
    combined = st.toggle('Draw both sensors on one map', False)
t0 = T0 + start; t1 = min(T1, t0 + dur)
base, extra = scene.symmetric_selection(t0, t1, classes)
sel = sorted(base['NS'] | base['OU'] | ((extra['NS'] | extra['OU']) if sym else set()))
opts = {'Both sensors': dict(vNS=True, vOU=True), 'Newsense': dict(vNS=True, vOU=False), 'Ouster': dict(vNS=False, vOU=True), 'Video only': dict(vNS=False, vOU=False, vctx=False)}[mode]
opts.update(ghost=False, ids=False, combined=combined, fullpath=False)
b = [-38.0, 36.0, -30.0, 26.0]   # fixed view covering the shared area and the camera's ground view
evs = [dict(t=float(r.t), s=r.sensor, label=f"{'Newsense' if r.sensor == 'NS' else 'Ouster'}: potential conflict candidate, {r.kind} {r.value:.2f} ({r.vru_class}-{r.veh_class}, {r.vru_state})", kind='conflict')
       for r in D.events().query('@t0 <= t <= @t1 and severe').itertuples()]
n_extra = len(extra['NS']) + len(extra['OU'])
st.caption(f'{len(sel)} highlighted tracks in this window' + (f' ({n_extra} of them added because they come within 2 m of a highlighted track of the other sensor)' if sym and n_extra else '') +
           '. On the video, Newsense is a filled dot and Ouster a ring. Red markers on the timeline are severe potential-conflict candidates (not confirmed near-misses); use "Next event" to jump between them.')
player.render(player.build_payload(t0, t1, sel, evs, bounds=b, opts=opts))
with st.expander('Which camera sees which part of the junction? (approximate coverage)'):
    import json, plotly.graph_objects as go
    CAMS = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'cameras.json'), encoding='utf-8'))
    cA, cB = set(map(tuple, CAMS['coverage_cells_approx']['SCU3K2'])), set(map(tuple, CAMS['coverage_cells_approx']['SCU4YV']))
    fig = go.Figure()
    bgc = D.background(); fig.add_scattergl(x=[c[0] + .5 for c in bgc], y=[c[1] + .5 for c in bgc], mode='markers', marker=dict(size=3, color='#E2E8F0'), name='pedestrian and cyclist activity', hoverinfo='skip')
    for cells, col, lab in ((cA - cB, '#334155', 'Camera 1 (SCU3K2) only'), (cB - cA, '#B45309', 'Camera 2 (SCU4YV) only'), (cA & cB, '#7C3AED', 'both cameras')):
        fig.add_scatter(x=[c[0] for c in cells], y=[c[1] for c in cells], mode='markers', marker=dict(symbol='square', size=9, color=col, opacity=.75), name=f'{lab} ({len(cells)} cells)')
    fig.update_yaxes(scaleanchor='x', scaleratio=1, range=[-46, 46]); fig.update_xaxes(range=[-46, 46])
    st.plotly_chart(ui.plot_style(fig, 520, 'Approximate ground area each camera sees where moving traffic was present', 'x position (m), Ouster frame; north not verified', 'y position (m)'), width='stretch')
    st.markdown("""* **How this was derived:** each image area's motion was correlated with Ouster's moving objects per 2 m ground cell (29 Oct 07:12–08:00). Cells appear only where traffic moved, so empty pavements are missing.
* **Accuracy:** tested on SCU3K2 against its calibration, the cells lie a median 2.4 m from the calibrated position (71 % within 4 m). It is **not a calibrated field of view**, and camera positions are not known.
* **Reading it:** Camera 1 mainly covers the −y half and one approach arm; Camera 2 mainly the +y half and the opposite arm; both see the centre.""")
    ui.source('diagnostics/MULTI_CAMERA_INVESTIGATION.md', 'config/cameras.json (approximate coverage cells)')
with st.expander('Which videos exist and how they are used'):
    VI = D.video_index(); rows = []
    for p, m in VI['parts'].items():
        a = TB.video_to_sensor(p, 0); bb = TB.video_to_sensor(p, m['duration_s'])
        rows.append({'Video': m['file'], 'Type': 'Camera 1 · SCU3K2 original (30 fps), approved timing', 'Sensor-time span (CET)': f'{clock(a)} – {clock(bb)}', 'Used': 'playback + sensor overlays' if a < T1 and bb > T0 else 'playback only (no Ouster data at this time)'})
    for p_, m_ in CAMS['cameras']['SCU4YV']['parts'].items():
        rows.append({'Video': m_['file'], 'Type': 'Camera 2 · SCU4YV original (30 fps), measured timing ±0.5 s', 'Sensor-time span (CET)': f"{clock(m_['overlay_at_pts0_epoch'] - CAMS['cameras']['SCU4YV']['delta_s'])} – {clock(m_['overlay_at_pts0_epoch'] + m_['duration_s'] / m_['pts_s_per_overlay_s'] - CAMS['cameras']['SCU4YV']['delta_s'])}", 'Used': 'second camera view (no sensor dots)'})
    _ten = os.path.join(RAW, 'ouster', '10 mins')
    for f in (sorted(os.listdir(_ten)) if os.path.isdir(_ten) else []):   # absent when the original dataset is not available
        if f.endswith('.mp4'): rows.append({'Video': f'ouster/10 mins/{f}', 'Type': '10 fps extract of the same camera footage (not a LiDAR recording)', 'Sensor-time span (CET)': 'see Stage 3 (starts ~52 s late)', 'Used': 'not used (the originals are used instead)'})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.caption('Camera 2 (SCU4YV) was excluded from the V2 analysis (clock unconfirmed at the time). Its offset to the sensors was measured on 14 Nov 2026 (−79.8 s ± 0.5 s) for display; it has no ground calibration, so no sensor positions are drawn on it. Ouster raw laser recordings (PCAP) are not shown.')
with st.expander('Technical details: how the video is aligned and projected'):
    st.markdown("""* **Time:** sensor time → video time uses the approved clock model (Stage 3 v2) and the video tick mapping, plus the empirical 2.81 s look-up offset (CK-01, cause unresolved). The same chain is implemented in Python and in the browser and tested for equality.
* **Projection:** ground positions are projected into the 720 × 480 image with the C2 v4 homography (5 reference points, 0.7–8.7 px residual). Far-field and elevated objects are less accurate; no boxes are drawn on the image.
* **Maps:** detections in the Ouster world frame (metres), footprints from reported size and orientation. Nothing is drawn where a sensor reports nothing; no boxes, point clouds or frames are generated.""")
    ui.source('video: mio vision/K305/2026_10_29/Standard_SCU3K2_2026-10-29_0600.00x.mp4 (read-only, streamed)', 'detections: dashboard/data/obs_*.parquet', 'timing: clock_model_v2.json + c2e_video_sensor_offset.json', 'projection: c2e_homography_v4_stationary.json')

"""Data quality & limitations (UI v4): how reliable and complete is the evidence? Concise sections; register and detail in expanders."""
import json, numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
from utils import data as D, ui, md, page
from utils.config import C, src
from utils.timebase import clock
ui.intro('Data quality & limitations', 'How reliable and complete is the evidence behind this comparison, and what can it not show?',
         'The biggest limits are: <b>no ground truth</b>, <b>one 83-minute period</b> with Ouster object data, and an <b>unexplained 2.81 s video offset</b>. '
         'Sensor agreement is therefore never presented as accuracy. 56 issues are documented in the register, with evidence, corrections and remaining uncertainty.', eyebrow='Understand the Research')
page.style()
page.section('The limitations at a glance')
page.table(pd.DataFrame([
    ('No ground truth', 'Nobody counted the real people', 'Detection rates, false positives and position accuracy cannot be measured', 'Results are reported as agreement and consistency only'),
    ('One short period', 'Ouster object data: 29 Oct 07:11:44–08:34:59', '83 shared minutes, one morning, one site', 'All cross-sensor results use this period; Newsense two-day patterns shown separately'),
    ('Timestamp uncertainty', 'Clocks agree only approximately', 'Events closer than about 1 s cannot be ordered across sources', 'Bounds stated; no signal-phase or red-light analysis'),
    ('Camera synchronisation', 'Camera clocks need a model and an extra unexplained offset', 'Video can support, but not prove, what a sensor reported at an instant', 'Camera 1: approved chain; camera 2: measured, display only'),
    ('Different coverage', 'Each sensor sees a different area', 'Counting everything would favour the wider sensor', 'Comparisons restricted to the 2,780 m² shared area'),
    ('Missing data', 'Frames and log periods missing', 'Small gaps in tracks and counts', 'Ouster log gaps masked for both sensors'),
    ('Unverified identities', 'Tracking IDs and matches are not checked against real people', 'A match or re-attached ID may be a different person', 'Matches called candidates; ambiguous cases stay ambiguous'),
    ('Video validation', 'Single rater, small samples, hazy far field', 'Video cannot give detection rates', 'Video results labelled indicative'),
    ('Different vocabularies', 'The sensors use different object types', 'Some results depend on label mapping', 'Coarse groups; both mappings shown (e.g. cyclists with/without "motorcycles")'),
    ('Same-analyst audit', 'The final audit re-implemented the key results, by the same analyst', 'Not an independent external review', 'Not described as fully scientifically validated')],
    columns=['Limitation', 'What it means', 'Effect on the results', 'How it is handled']))

page.section('Timestamp uncertainty')
a, b = st.columns([1.1, 1])
with a: page.table(pd.DataFrame([('Newsense ↔ Ouster', '± 0.7 s'), ('Newsense ↔ traffic signals', 'about ± 1 s'), ('Ouster ↔ traffic signals', 'about ± 1.5 s'),
                          ('Camera 1 (SCU3K2) ↔ sensors', 'clock model + 2.81 s offset (cause unresolved)'), ('Camera 2 (SCU4YV) ↔ sensors', '− 79.8 s ± 0.5 s, measured for display (not V2)')],
                         columns=['Between', 'Known to']))
b.markdown("""* The sensors' clocks were compared with the traffic-signal log (Stage 3 v2); the clock model is unchanged.
* **The 2.81 s offset (issue CK-01):** both sensors' timestamps are about 2.81 s later than the camera-derived reference for the same motion. The cause is unknown, so it is used **only** to find video frames, never as a clock correction.
* Consequence: no analysis of red-light behaviour or signal phases.""")

page.section('Camera synchronisation')
st.markdown("""* **Camera 1 (SCU3K2)** has approved timing and a ground calibration, so sensor positions can be drawn on it (accuracy 0.7–8.7 px at the five reference points; less accurate far away).
* **Camera 2 (SCU4YV)** was excluded from the V2 results because its clock was unconfirmed. For the dashboard its offset was measured on 14 Nov 2026 (−79.8 s ± 0.5 s, 29 Oct 07:12–08:35) by one method, validated on camera 1. It has **no ground calibration**, so no sensor positions are drawn on it, and it is not used to check detections.
* In *independent* mode camera 2 is explicitly **not synchronised**. Details: `diagnostics/MULTI_CAMERA_INVESTIGATION.md`.""")

page.section('Sensor coverage differences')
st.markdown("""* Ouster reports objects over an area about 3.5 times larger than Newsense (10,172 vs 2,908 m²). A larger footprint shows where a sensor **reported** objects; it does not prove better detection there (Ouster's far-range quality is unverified).
* An earlier statement that "Ouster coverage is smaller" was **withdrawn** (C1 correction note 01).
* All cross-sensor numbers use the shared area unless stated.""")

page.section('Missing data and excluded periods')
st.markdown("""* **Ouster:** object logs only 29 Oct 07:11:44–08:34:59; 4.9 % of frames missing; two 7.5 s and two 2.1–2.2 s log gaps, **masked for both sensors** in every comparison; a processing alert at 07:16–07:17. Four 10-minute raw laser recordings were delivered but not converted into objects. A completeness check (14 Nov) found indirect signs that further object logs may have existed but were not delivered; **unconfirmed**.
* **Newsense:** two mornings (28 and 29 Oct); 2 dropped frames in the compared period; gaps on 28 Oct 13:10–15:29 and 16:45–19:44; no documentation.
* **Video:** both cameras 06:00–13:00 on both days; hourly file changes lose 0.1–0.9 s.""")

page.section('Unverified identities, video checks and agreement')
st.markdown("""* **Identities are never verified.** A tracking ID is a number, not a person. Re-attached Ouster IDs (359) and dashboard matches are candidates; ambiguous cases are left ambiguous.
* **Video validation is indicative.** One rater, small stratified samples, many undecidable views; it found real persons missed by each sensor, and confirmed the K1 signal pole as a Newsense false object, but cannot give rates.
* **Agreement is not accuracy.** If both sensors miss a person, they agree and are both wrong; if they disagree, the data alone cannot say which is right.""")

st.markdown('## How reliable is each kind of information shown here?')
page.table(pd.DataFrame([
    ('Sensor detections, IDs, classes, positions, speeds', 'Measured (original object lists)', 'Accuracy unknown (no ground truth)'),
    ('Newsense → Ouster coordinate transform', 'Validated (C1; median residual 0.15 m)', 'Valid 29 Oct 07:12–08:35'),
    ('Sensor ↔ video timing', 'Estimated (clock model v2 + CK-01 2.81 s look-up offset)', 'Cause of 2.81 s unresolved'),
    ('Projection of ground points into the image', 'Estimated (5-point homography, 0.7–8.7 px)', 'Less accurate far away and for elevated points'),
    ('Cross-sensor candidate matches (dashboard)', 'Derived (transparent rules, not a probability)', 'Identity never confirmed'),
    ('Bounding-box footprints on maps', 'Measured size + reported orientation', 'Orientation checked against motion (98–100 %)'),
    ('Video confirmation of objects', 'Indicative (single rater)', 'No detection rates possible'),
    ('Camera 2 (SCU4YV) timing and view', 'Measured for display (−79.8 s ± 0.5 s)', 'Not part of V2; no ground calibration'),
    ('Ouster point clouds (PCAP)', 'Unavailable in the dashboard', 'No decoder in this environment; four 10-min raw captures exist, not converted to objects'),
    ('Compass directions, street names, stop lines', 'Unavailable', 'No official map (GE-01)')], columns=['Information', 'Status', 'Caveat']))

st.markdown('## More detail')
with st.expander('Issue register v4: all 56 documented issues (searchable)'):
    R = D.register()
    f1, f2, f3 = st.columns([1, 1, 2])
    sens = f1.multiselect('Source', sorted(R.sensor.unique()), sorted(R.sensor.unique())); stt = f2.multiselect('Status', sorted(R.status.unique()), sorted(R.status.unique()))
    qq = f3.text_input('Search (ID, problem, evidence …)')
    r = R[R.sensor.isin(sens) & R.status.isin(stt)]
    if qq: r = r[pd.Series([qq.lower() in ' '.join(map(str, row)).lower() for row in r.itertuples(index=False)], index=r.index, dtype=bool)]   # aligned mask: safe when nothing matches or r is already empty
    if r.empty: st.caption(f'No register entry matches "{qq}".')
    st.dataframe(r[['id', 'sensor', 'problem', 'affected_period', 'evidence', 'impact', 'correction_applied', 'status', 'remaining_uncertainty', 'affects_fairness']].rename(columns=lambda c: c.replace('_', ' ').capitalize()),
                 hide_index=True, width='stretch', height=420)
    cnt = R.groupby(['sensor', 'status']).size().unstack(fill_value=0); st.dataframe(cnt, width='stretch')
    ui.source('stage4_traffic_analysis/register/issue_correction_register.csv (register v4, generated by build_register_v4.py)')
with st.expander('All limitations and uncertainties (V2 text)'):
    for heads, rows in md.tables(src('v2_limitations')):
        st.dataframe(pd.DataFrame(rows, columns=heads), hide_index=True, width='stretch')
    ui.source('FINAL_PACKAGE_V2/FINAL_LIMITATIONS_AND_UNCERTAINTIES.md')
with st.expander('Missing frames over time (29 Oct, compared period)'):
    FR = D.frames_index(); T0, T1 = 1793254320.0, 1793259300.0
    fig = go.Figure()
    for s in ('NS', 'OU'):
        f = np.array(FR[s]); d = np.diff(f); bad = d > 0.15
        fig.add_scatter(x=[clock(t) for t in f[1:][bad]], y=d[bad], mode='markers', name=f"{'Newsense' if s == 'NS' else 'Ouster'}: {bad.sum():,} frame intervals > 0.15 s", marker=dict(color=C[s], size=6))
    fig.update_yaxes(type='log')
    st.plotly_chart(ui.plot_style(fig, 320, 'Missing frames: pauses between consecutive frames longer than 0.15 s (10 per second expected)', 'time (CET)', 'pause length (s, log scale)'), width='stretch')

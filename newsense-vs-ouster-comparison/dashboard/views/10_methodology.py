"""How the research works (UI v4): how the comparison was performed, without reading source code."""
import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
from utils import ui, page
from utils.config import C
ui.intro('How the research works', 'How was the comparison between Newsense and Ouster performed, and what do the measures on the other pages mean?',
         'Both sensors\' object lists were put into <b>one coordinate system</b> and <b>one time base</b>, cut to the <b>area both can see</b>, and processed with <b>identical rules</b>. '
         'The results describe where the sensors <b>agree or differ</b>; without ground truth they do not say which sensor is right.', eyebrow='Understand the Research')
page.style()
STEPS = [('1', 'Raw object lists', 'Newsense JSON and Ouster logs: every object, 10× per second'), ('2', 'Same place', 'Newsense converted into the Ouster frame (validated transform)'),
         ('3', 'Same time', 'Clocks compared with the traffic-signal log; 83 shared minutes'), ('4', 'Same area', 'Only the 2,780 m² both sensors can see'),
         ('5', 'Same rules', 'Tracks, movement, IDs and conflicts computed identically'), ('6', 'Compare & check', 'Agreement, differences, video checks, audit → V2 results')]
st.markdown('<div style="display:flex;gap:6px;align-items:stretch;flex-wrap:wrap;margin:.6rem 0 1.2rem 0">' + '<div style="align-self:center;color:#94A3B8;font-size:1.2rem">→</div>'.join(
    f'<div style="flex:1 1 140px;background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:10px 12px"><div class="k-step">{n}</div><b>{t}</b><div style="font-size:.84rem;color:#475569;margin-top:4px">{d}</div></div>' for n, t, d in STEPS) + '</div>', unsafe_allow_html=True)

page.section('The data sources')
page.table(pd.DataFrame([
    ('Newsense', 'Commercial traffic sensor system; object list with position, size, speed, type and tracking ID, 10× per second', '28 and 29 Oct (comparison: 29 Oct 07:12–08:35)', 'Sensor under test'),
    ('Ouster', 'LiDAR laser scanner with perception software; object list with the same kind of fields, plus a flag for estimated positions', '29 Oct 07:11–08:35 only (object logs)', 'Sensor under test'),
    ('Camera 1 · SCU3K2', 'MioVision traffic camera, 720×480, 30 fps', '28 and 29 Oct, 06:00–13:00', 'Visual reference with approved timing and ground calibration'),
    ('Camera 2 · SCU4YV', 'Second MioVision camera, other viewpoint', '28 and 29 Oct, 06:00–13:00', 'Extra view in the dashboard only (timing measured, not part of V2)'),
    ('Traffic signals', 'Signal states once per second', '28 and 29 Oct, 06:00–13:00', 'Common time reference for the clocks')],
    columns=['Source', 'What it records', 'Period', 'Role']))
st.caption('Neither sensor is ground truth, and neither is the camera: video checks are indicative (single rater, small samples).')

page.section('Making the two sensors comparable')
a, b = st.columns(2)
with a:
    st.markdown("""**Same place.** Newsense uses its own coordinate system. It was converted into Ouster's with a rotation (171.4°), a shift and a scale, fitted on objects both sensors saw. Matched positions then agree to a median of 0.15 m.

**Same time.** Each clock was compared with the traffic-signal log. Newsense and Ouster agree to within about ±0.7 s; against the signals the bounds are about ±1 s (Newsense) and ±1.5 s (Ouster). The camera needs its own clock model plus an unexplained 2.81 s offset.""")
with b:
    st.markdown("""**Same area.** Each sensor sees a different area. Cross-sensor numbers use only the **shared area** (2,780 m², in 2 m cells), so neither sensor is penalised for objects it could not see.

**Same rules.** Every measure (tracks, breaks, movement distance, ID events, conflict indicators) is computed by the same code with the same thresholds for both sensors. Log gaps of one sensor are masked for both.""")

page.section('How the measures are calculated')
page.table(pd.DataFrame([
    ('Confirmation (agreement)', 'Share of one sensor\'s samples with any object of the other sensor within 2 m at the same moment', 'Detection'),
    ('Track piece', 'One tracking ID, split when the ID reappears after more than 5 s or jumps more than 15 m within 1 s', 'Tracking, Movement paths'),
    ('Movement distance (robust moving path)', 'Positions taken once per second; a step counts only if it is at least 0.5 m, so standing jitter adds nothing', 'Movement, Key results'),
    ('Track breaks per km', 'A moving track ends and a new one starts nearby within T seconds, divided by the movement distance', 'Tracking'),
    ('ID events', 'Reuse of an ID for another object, instant swaps, and re-attachment of the same ID after a short loss', 'Tracking'),
    ('Potential-conflict indicators', 'Time to collision, post-encroachment time and proximity between a pedestrian/cyclist and a vehicle; "severe" below fixed thresholds', 'Potential conflicts')],
    columns=['Measure', 'How it is calculated', 'Used on']))

page.section('How object matching works (Follow One Person)')
st.markdown("""This matching is used only by the dashboard to organise investigations; it is **not part of the V2 results**.
1. Each pedestrian/cyclist track of one sensor is compared with every overlapping track of the other sensor, every 0.2 s where both have real samples.
2. The Newsense clock may be shifted by up to ±0.7 s to find the best fit.
3. Overlap, median and 90th-percentile distance, share within 2 m and direction agreement decide whether a pair is **strong**, **possible** or **rejected**.
4. Two tracks are linked only if each chooses the other. If a second partner fits about as well, the case is **ambiguous** and no choice is made.
5. **No match confirms identity**: two people walking together look the same to this method.""")

page.section('Main assumptions and limitations')
st.markdown("""* **No ground truth:** agreement between sensors is not accuracy; detection rates and false-positive rates cannot be measured.
* **One short period:** 83 shared minutes on one morning at one site.
* **Timing:** sensor-to-sensor ±0.7 s; the 2.81 s camera offset is unexplained.
* **Different vocabularies:** class comparisons use coarse groups; some results depend on how labels are mapped.
* **Same-analyst audit:** the final audit re-implemented the key calculations from raw data, but it was done by the same analyst.

Full list: *Data quality & limitations*.""")

st.markdown('## More detail')
with st.expander('Formulas'):
    st.latex(r'\begin{bmatrix}x_O\\y_O\end{bmatrix} = s\,R(\theta)\begin{bmatrix}x_N\\y_N\end{bmatrix} + \begin{bmatrix}t_x\\t_y\end{bmatrix},\quad \theta = 171.395^\circ,\ s = 0.99958,\ t = (-18.110,\ 4.567)\ \text{m}')
    st.latex(r'\text{breaks per km} = \frac{\#\{\text{moving track ends with a continuation within } T\}}{\text{robust moving path (km)}}')
    st.latex(r'\text{TTC} = \min_{\tau>0}\ \tau \;:\; \lVert \Delta\mathbf{p} + \tau\,\Delta\mathbf{v} \rVert = R \quad (R = 2.5\ \text{m car},\ 3.5\ \text{m truck/bus})')
    st.latex(r't_{\text{overlay}} = t_{\text{ref}} + a_0 + b\,(t_{\text{ref}} - t_0),\qquad t_{\text{ref}} = t_{\text{sensor}} - 2.81\,\text{s}')
    st.caption('PET (post-encroachment time): the time between one road user leaving a spot and the other arriving there (within 1.5 m, paths crossing at 30° or more). Severe: TTC < 1.5 s, PET < 2 s, distance < 3 m.')
with st.expander('Why "movement distance" ignores standing jitter (illustration)'):
    t = np.arange(0, 20, 0.1); x = np.where(t < 10, 0.0, (t - 10) * 1.3) + np.random.default_rng(1).normal(0, 0.025, len(t))
    raw = np.abs(np.diff(x)).cumsum(); dec = x[::10]; st_ = np.abs(np.diff(dec)); rob = np.where(st_ >= 0.5, st_, 0).cumsum()
    f = go.Figure([go.Scatter(x=t[1:], y=raw, name='sum of every 0.1 s step (includes jitter)', line=dict(color=C['UNCERTAIN'])), go.Scatter(x=t[::10][1:], y=rob, name='robust: 1 s steps of at least 0.5 m', line=dict(color=C['BOTH']))])
    st.plotly_chart(ui.plot_style(f, 300, 'Synthetic example: a person stands 10 s, then walks 10 s', 'time (s)', 'accumulated path (m)'), width='stretch')
with st.expander('Uncertainty and evidence levels'):
    st.markdown("""**Sources of uncertainty:** position noise (2–6 cm at rest), position jumps (Ouster, 1–2 m in groups), clock uncertainty (±0.7–1.5 s), the unexplained 2.81 s video offset, the image projection (up to about 9 px at reference points), class-boundary differences and small samples (83 min, one morning).

**Evidence levels used throughout:** *measured* (computed from data), *estimated* (model-based), *indicative* (small or single-rater sample), *unavailable / unverified*.""")
with st.expander('Glossary: plain words in this dashboard and the technical terms in the reports'):
    page.table(pd.DataFrame([
    ('Recorded sensor sample', 'Observation', 'One object in one sensor frame (10 per second).'),
    ('Track piece', 'Track segment', 'One sensor ID, split when it re-appears after > 5 s or jumps > 15 m within ≤ 1 s (C3 rule).'),
    ('One object was split into multiple tracking IDs', 'Track fragmentation', 'Measured as moving-track breaks with a nearby continuation per km of robust movement.'),
    ('Interruption', 'Missing period / gap', 'No sample for more than 0.35 s inside a track piece.'),
    ('Estimated position', 'Predicted / coasted sample', 'Ouster sample whose update is older than 0.05 s (update_ts). Newsense has no such flag.'),
    ('Movement distance', 'Robust moving path (CORR-01)', 'Positions sampled once per second; a step counts only if it is at least 0.5 m.'),
    ('No reliable match found in the other sensor', 'Unmatched candidate', 'One sensor only, inside the shared area, no acceptable partner.'),
    ('More than one possible match, so identity cannot be determined', 'Ambiguous match', 'Competing partners within 0.5 m, simultaneous segments, or partners claimed elsewhere.'),
    ('Strong candidate match', 'Strong candidate match', 'Overlap ≥ 2 s and ≥ 50 %, median ≤ 1 m, p90 ≤ 2 m, ≥ 80 % within 2 m, same direction. Not a confirmed identity.'),
    ('Investigation number (#00718)', 'Candidate ID (INV-00718)', 'Dashboard-generated reference for a possible cross-sensor match.'),
    ('Shared area', 'Common region (C1)', '2 m cells covered by both sensors, 2,780 m².'),
    ('Standing "pedestrian" at a fixed point', 'Stationary detection in a Newsense hotspot cell', 'Ten cells with persistent stationary Newsense pedestrians; the largest is the K1 signal pole.'),
    ('Pedestrian or cyclist', 'VRU (vulnerable road user)', 'Pedestrians and cyclists; Newsense "Motorcycle" is treated separately or added to cyclists where stated.'),
    ('Time to collision / post-encroachment time', 'TTC / PET', 'Surrogate safety indicators; candidates, never confirmed near-misses.'),
    ('Video offset', 'CK-01 (2.81 s)', 'Empirical look-up offset between sensor and video time; cause unresolved; not a clock correction.'),
], columns=['Plain wording (dashboard)', 'Technical term (reports)', 'Definition']))

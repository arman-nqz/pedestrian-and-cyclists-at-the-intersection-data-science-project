"""Presentation mode (UI v2): a guided, step-by-step research presentation for professors. No filters; large video; evidence and limitations in sequence."""
import streamlit as st
from utils import ui, investigate as I, inv_view as V, results as R
from utils.config import C
P = st.session_state.get('_pages')
ui.style()
st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {display:none !important;}
.block-container {max-width:1400px; padding-top:1.4rem;} .k-lead {font-size:1.18rem;} .k-card p {font-size:1rem;}</style>""", unsafe_allow_html=True)
ex = I.examples(); keys = list(ex)
STEPS = [('intro', 'Question'), ('method', 'Method'),
         ('ex0', 'Ex. 1 · Both sensors'), ('ex1', 'Ex. 2 · Newsense only'), ('ex2', 'Ex. 3 · Ouster only'), ('ex3', 'Ex. 4 · Ambiguous'), ('ex4', 'Ex. 5 · Interruption'),
         ('results', 'Results'), ('limits', 'Limits')]
names = [n for _, n in STEPS]
if 'pstep' not in st.session_state: st.session_state['pstep'] = names[0]
top = st.columns([3, 1])
top[0].markdown("<div class='k-eyebrow'>K305 Traffic Analysis · research presentation</div>", unsafe_allow_html=True)
with top[1]:
    if P: st.page_link(P['home'], label='Exit presentation', icon=':material/close:')
choice = st.segmented_control('Step', names, key='pstep', label_visibility='collapsed') or names[0]
i = names.index(choice); step = STEPS[i][0]
st.caption(f'Step {i + 1} of {len(STEPS)}')
def go(n): st.session_state['pstep'] = n
def nav():
    a, _, b = st.columns([1, 4, 1])
    if i > 0: a.button(f'← {names[i - 1]}', key=f'prev_{step}', width='stretch', on_click=go, args=(names[i - 1],))
    if i < len(STEPS) - 1: b.button(f'{names[i + 1]} →', key=f'next_{step}', type='primary', width='stretch', on_click=go, args=(names[i + 1],))

if step == 'intro':
    st.markdown('# How well do Newsense and Ouster detect and track pedestrians and cyclists?')
    st.markdown("<div class='k-lead'>Two commercial sensor systems watched intersection K305 in Aschaffenburg at the same time. We compare what each reported about people walking and cycling, "
                "using identical rules for both, with the original traffic camera as the visual reference.</div>", unsafe_allow_html=True)
    a, b, c = st.columns(3)
    with a: ui.card(f"<span style='color:{C['NS']}'>● Newsense</span>", 'Traffic sensor system. Reports position, size, speed and type of every object, 10 times per second.', 'Data on both study days.', C['NS'])
    with b: ui.card(f"<span style='color:{C['OU']}'>● Ouster</span>", 'LiDAR laser scanner with perception software that turns laser points into tracked objects, 10 times per second.', 'Object data: 29 Oct, 07:11–08:35 only.', C['OU'])
    with c: ui.card(f"<span style='color:{C['CAM']}'>● Original camera</span>", 'Independent MioVision traffic camera. Lets us check by eye what was really there; not a perfect ground truth.', 'Recorded 06:00–13:00 on both days.', C['CAM'])
    st.markdown('### The comparison period')
    ui.warn('All cross-sensor results use <b>29 October 2026, 07:12–08:35 (83 minutes)</b>, the only period with Ouster object data. Ouster also delivered four 10-minute raw laser recordings that were not converted into objects.')
elif step == 'method':
    st.markdown('# How we compare fairly')
    a, b = st.columns(2)
    with a:
        ui.card('1 · Same place', 'Newsense positions are converted into the Ouster coordinate frame with a validated transform (median residual 0.15 m). Cross-sensor numbers use only the 2,780 m² both sensors can see.')
        st.write('')
        ui.card('2 · Same rules', 'Tracks, interruptions, movement distance and conflict indicators are computed with identical code and thresholds for both sensors.')
    with b:
        ui.card('3 · Agreement, not accuracy', 'Without ground truth we can measure whether the sensors <i>agree</i>, not who is <i>right</i>. If both miss a person, they agree and are both wrong.')
        st.write('')
        ui.card('4 · Honest timing', 'Sensors agree to about ±0.7 s. The video needs an extra 2.81 s offset whose cause is unexplained; it is used only to find video frames.')
    st.markdown('### Reading the examples')
    st.markdown("<div class='k-lead'>Each example shows the original video with the sensors' positions as coloured dots, one map per sensor, and a timeline of when each sensor reported the object. "
                "An <b>investigation number</b> groups tracks that <i>may</i> belong to one person; it never confirms identity, and ambiguous cases stay ambiguous.</div>", unsafe_allow_html=True)
elif step.startswith('ex'):
    k = keys[int(step[2])]; inv = ex[k]
    if inv is None: st.info('No valid example of this kind exists in the data.')
    else:
        X = V.load(inv); V.header(X); V.play(X, layout='stack', window=180)
        a, b = st.columns([1.15, 1])
        with a: V.tracking_cards(X)
        with b: V.match_explanation(X)
        if P: st.page_link(P['follow'], label='Open this investigation with all technical details', icon=':material/open_in_new:', query_params={'inv': inv})
elif step == 'results':
    st.markdown('# Key results (V2)')
    ui.finding('There is <b>no overall winner</b>. Ouster follows pedestrians and cyclists for longer and with far fewer tracking-ID problems. Newsense reports steadier positions, '
               'but many of its "pedestrians" are standing still at fixed points. On which interactions are <b>severe</b>, the sensors agree on only about 1 event in 30.', 'Main finding')
    R.grid(['ped_path', 'duration', 'breaks'])
    R.grid(['ids', 'hotspot', 'severe_agree'])
    st.caption('Agreement and consistency measures, not accuracy. 29 Oct 2026, 07:12–08:35. Open "Definition, sample and uncertainty" on any card for details.')
elif step == 'limits':
    st.markdown('# What the data cannot tell us')
    a, b = st.columns(2)
    with a:
        ui.card('No ground truth', 'Detection rates, false-positive rates and position accuracy cannot be measured. Video checks are indicative only (single rater, small samples).')
        st.write(''); ui.card('One short period', '83 minutes on one morning at one site. Ouster object data exist only for this period; whether more was recorded is being clarified with the provider.')
        st.write(''); ui.card('Timing', 'The 2.81 s video offset is unexplained. Sensor-to-signal timing is known to ±1–1.5 s, so no red-light or signal-phase analysis is possible.')
    with b:
        ui.card('Different vocabularies', 'Ouster has no motorcycle class and labels many objects UNKNOWN; Newsense often calls cyclists "motorcycles". Some results depend on how labels are mapped.')
        st.write(''); ui.card('Matching is a candidate', 'Cross-sensor matches in this dashboard are a transparent heuristic, not a probability. No match confirms identity.')
        st.write(''); ui.card('Review status', 'The final audit re-implemented the key calculations from raw data, but it was done by the same analyst. The work is not described as fully scientifically validated.')
    if P: st.page_link(P['quality'], label='All limitations and the issue register (56 entries)', icon=':material/fact_check:')
st.write(''); nav()

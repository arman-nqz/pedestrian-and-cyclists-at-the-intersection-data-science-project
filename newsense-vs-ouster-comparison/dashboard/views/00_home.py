"""Home (UI v2): what the project is, the two sensors, data coverage, and where to start."""
import streamlit as st, plotly.graph_objects as go
from utils import ui
from utils.config import C
P = st.session_state.get('_pages')   # set by app.py; None when a page is run on its own (tests)
ui.setup('K305 Traffic Analysis', 'How well do Newsense and Ouster detect and track pedestrians and cyclists?', 'University research project · Intersection K305, Aschaffenburg')
st.markdown("""<div class='k-lead'>Two commercial sensor systems watched the same busy intersection (Würzburger Straße / Ring) at the same time.
This project compares, with identical rules for both, what each one reported about people walking and cycling: whether it saw them, what it called them,
how long it could follow them, and where the two disagree. The original camera recording is used as the visual reference.</div>""", unsafe_allow_html=True)

a, b, c = st.columns(3)
with a: ui.card(f"<span style='color:{C['NS']}'>● Newsense</span>", 'A commercial traffic sensor system that reports every object it detects about ten times per second: position, size, speed and type (pedestrian, cyclist, car …).', 'Recorded on both study days (28 Oct with gaps).', C['NS'])
with b: ui.card(f"<span style='color:{C['OU']}'>● Ouster</span>", 'A LiDAR (laser-scanning) sensor with perception software that turns millions of laser points into a list of tracked objects, also about ten times per second.', 'Object data available for 83 minutes on 29 October.', C['OU'])
with c: ui.card(f"<span style='color:{C['CAM']}'>● Original camera</span>", 'An independent MioVision traffic camera (SCU3K2) filming the intersection. It is not a perfect reference, but it lets you check by eye what was really there.', 'Recorded 06:00–13:00 on both days.', C['CAM'])

st.markdown('## Study dates and data coverage')
ui.warn('<b>Coverage notice.</b> The Ouster object data analysed here cover only <b>29 October 2026, about 07:11–08:35</b>. All direct comparisons between the two sensors therefore use '
        'this 83-minute period. Ouster also delivered four 10-minute raw laser recordings (29 Oct) that were not converted into object data. A separate data-completeness check (14 Nov) '
        'found indirect signs that more Ouster object logs may have been produced but not delivered; this is unconfirmed and is being clarified with the provider.')
ROWS = [('Original camera', C['CAM'], {28: [(6, 13)], 29: [(6, 13)]}, 'solid'),
        ('Newsense objects', C['NS'], {28: [(0, 13 + 9 / 60), (15.5, 16 + 44 / 60), (19.75, 24)], 29: [(0, 24)]}, 'solid'),
        ('Ouster objects (analysed)', C['OU'], {28: [(19 + 45 / 60, 19 + 46.3 / 60)], 29: [(7 + 11.7 / 60, 8 + 35 / 60)]}, 'solid'),
        ('Ouster raw laser recordings (not analysed)', C['OU'], {29: [(7 + 34.5 / 60, 7 + 44.35 / 60), (8 + 18.3 / 60, 8 + 28.3 / 60), (9 + 4.2 / 60, 9 + 14.2 / 60), (10 + 24.7 / 60, 10 + 34.7 / 60)]}, 'open')]
fig = go.Figure(); tv, tt = [], []
for day, yoff in ((28, 5.4), (29, 0)):
    for i, (name, col, spans, kind) in enumerate(ROWS):
        y = yoff + (3 - i); tv.append(y); tt.append(f'{day} Oct · {name}')
        for a_, b_ in spans.get(day, []):
            fig.add_shape(type='rect', x0=a_, x1=max(b_, a_ + 0.06), y0=y - 0.32, y1=y + 0.32, fillcolor=col if kind == 'solid' else 'rgba(255,255,255,0)', line=dict(color=col, width=1.5))
    fig.add_hline(y=yoff - 0.75, line_color='#E5E7EB', line_width=1) if day == 28 else None
fig.add_shape(type='rect', x0=7.2, x1=8 + 35 / 60, y0=-0.55, y1=3.55, fillcolor=C['BOTH'], opacity=0.10, line_width=0)
fig.add_annotation(x=8.6, y=3.55, text='Compared period 07:12–08:35', showarrow=False, xanchor='left', yanchor='bottom', font=dict(size=11, color=C['BOTH']))
fig.update_xaxes(range=[0, 24], tickvals=list(range(0, 25, 3)), ticktext=[f'{h:02d}:00' for h in range(0, 25, 3)], showgrid=True)
fig.update_yaxes(tickvals=tv, ticktext=tt, range=[-0.7, 9.0], showgrid=False, tickfont=dict(size=12, color='#334155'))
st.plotly_chart(ui.plot_style(fig, 420, 'What was recorded, and when (local time, CET)', 'time of day'), width='stretch', config={'displayModeBar': False})
st.caption('Newsense has gaps on 28 Oct (13:10–15:29, 16:45–19:44). The 78-second Ouster fragment on 28 Oct evening is not used. Sources: Stage 1 inventory (verified file contents) and the Ouster data-completeness investigation.')

st.markdown('## Where to start')
cards = [('watch', ':material/videocam:', 'Watch the Sensors', 'Play any moment of the original video with the Newsense and Ouster detections drawn on top and on two maps.'),
         ('follow', ':material/person_search:', 'Follow One Person', 'Pick one pedestrian or cyclist and see, second by second, how each sensor detected, labelled and tracked them.'),
         ('results', ':material/insights:', 'Compare Sensor Performance', 'The main findings: detection, classification, tracking, movement, coverage and potential conflicts.'),
         ('method', ':material/school:', 'Understand the Research', 'How the comparison works, what the terms mean, what the data cannot tell us, and a guided presentation.')]
cols = st.columns(4)
for col, (k, icon, title, txt) in zip(cols, cards):
    with col.container(key=f'navcard_{k}'):
        st.markdown(f"<h3 style='margin:0 0 .3rem 0'>{title}</h3><p style='color:#475569;font-size:.93rem;min-height:6.4em'>{txt}</p>", unsafe_allow_html=True)
        if P: st.page_link(P[k], label='Open', icon=icon)

st.markdown('## Three things to keep in mind')
x, y, z = st.columns(3)
with x: ui.card('Neither sensor is the truth', 'There is no independent ground truth. When the sensors disagree, the data alone cannot say which one is right. More detections do not mean better detection.')
with y: ui.card('Agreement is not accuracy', 'If both sensors report the same thing, they <i>agree</i>. They could still both be wrong. The dashboard never presents agreement as accuracy.')
with z: ui.card('Timing is not perfect', 'Video and sensors are aligned with an approved clock model plus a 2.81-second offset whose cause is still unexplained. The two sensors agree to about ±0.7 s.')
st.markdown("<div class='k-src' style='margin-top:1.4rem'>All results come from the corrected V2 research package. Its final audit was a re-implementation by the same analyst, not an external review, so the work is not described as fully scientifically validated.</div>", unsafe_allow_html=True)

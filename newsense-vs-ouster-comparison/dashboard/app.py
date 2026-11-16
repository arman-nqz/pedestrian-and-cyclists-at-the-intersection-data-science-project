"""K305 Traffic Analysis dashboard (UI v2). Launch: ./run_dashboard.sh  (= streamlit run app.py in the data_science_class environment)."""
import streamlit as st
st.set_page_config(page_title='K305 Traffic Analysis', page_icon=':material/traffic:', layout='wide', initial_sidebar_state='expanded')
from utils import data as D, video_server, ui
video_server.ensure_running()
status = D.v2_status()
ui.style()
P = dict(
    home=st.Page('views/00_home.py', title='Home', icon=':material/home:', default=True, url_path='home'),
    watch=st.Page('views/03_video_comparison.py', title='Watch the Sensors', icon=':material/videocam:', url_path='watch_the_sensors'),
    follow=st.Page('views/02_object_investigation.py', title='Follow One Person', icon=':material/person_search:', url_path='follow_one_person'),
    results=st.Page('views/01_overview.py', title='Key results', icon=':material/insights:', url_path='key_results'),
    detection=st.Page('views/04_detection_comparison.py', title='Detection & classification', icon=':material/visibility:', url_path='detection'),
    tracking=st.Page('views/05_tracking_analysis.py', title='Tracking', icon=':material/timeline:', url_path='tracking'),
    paths=st.Page('views/06_trajectory_analysis.py', title='Movement paths', icon=':material/route:', url_path='movement_paths'),
    spatial=st.Page('views/07_spatial_analysis.py', title='Where objects are seen', icon=':material/map:', url_path='where_objects_are_seen'),
    conflicts=st.Page('views/08_conflict_analysis.py', title='Potential conflicts', icon=':material/warning:', url_path='potential_conflicts'),
    method=st.Page('views/10_methodology.py', title='How the research works', icon=':material/school:', url_path='methodology'),
    quality=st.Page('views/09_data_quality.py', title='Data quality & limitations', icon=':material/fact_check:', url_path='data_quality'),
    present=st.Page('views/11_presentation.py', title='Presentation mode', icon=':material/co_present:', url_path='presentation'))
st.session_state['_pages'] = P
with st.sidebar:
    st.markdown("<div style='font-weight:700;font-size:1.05rem;letter-spacing:-.01em'>K305 Traffic Analysis</div>"
                "<div style='color:#64748B;font-size:.85rem;margin-bottom:.4rem'>Newsense vs Ouster · pedestrians and cyclists</div>", unsafe_allow_html=True)
import os
_vids = video_server.whitelist(); _found = sorted(n for n, p in _vids.items() if os.path.isfile(p))
if not _found:
    st.sidebar.warning('Camera videos not found, so the video panels stay empty. Everything else works. To add video: copy the 4 MP4 files into the dashboard/videos folder and restart (see QUICK_START.md).')
if not status['ok']:
    st.error('The dashboard uses only the corrected V2 research package and never falls back to V1. V2 is incomplete:\n\n' + '\n'.join(f'- {p}' for p in status['problems'])); st.stop()
pg = st.navigation({'': [P['home']],
                    'Explore': [P['watch'], P['follow']],
                    'Compare Sensor Performance': [P['results'], P['detection'], P['tracking'], P['paths'], P['spatial'], P['conflicts']],
                    'Understand the Research': [P['method'], P['quality'], P['present']]})
with st.sidebar:
    st.markdown(f"<div style='margin-top:1rem;font-size:.8rem;color:#475569;border-top:1px solid #E5E7EB;padding-top:.8rem'>"
                f"<b style='color:#059669'>●</b> Results from the corrected <b>V2</b> research package ({len(status['corrections'])}/13 corrections verified).<br>"
                f"<span style='color:#64748B'>Not fully scientifically validated: the final audit was a re-implementation by the same analyst, not an external review.</span></div>", unsafe_allow_html=True)
pg.run()

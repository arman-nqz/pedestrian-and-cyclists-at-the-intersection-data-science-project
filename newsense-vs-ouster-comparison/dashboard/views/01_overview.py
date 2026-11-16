"""Key results (UI v2): the main V2 findings first, as plain questions; definitions and the full scorecard on demand."""
import pandas as pd, streamlit as st
from utils import data as D, ui, md, results as R
from utils.config import src
ui.intro('Key results', 'What did the comparison find? Each card asks one question and shows the answer for both sensors, using the corrected V2 results. Open a card\'s details for its definition, sample size and uncertainty.',
         'There is <b>no overall winner</b>. Ouster follows pedestrians and cyclists for longer and with far fewer tracking-ID problems. Newsense reports steadier positions, '
         'but many of its "pedestrians" are standing still at fixed points such as a signal pole. On which interactions are <b>severe</b>, the two sensors agree on only about 1 event in 30.',
         eyebrow='Compare Sensor Performance')
ui.legend()
ui.info('These are <b>agreement and consistency measures</b>, not accuracy: there is no ground truth. Values cover 29 Oct 2026, 07:12–08:35 (83 minutes), in the area both sensors can see unless stated.')
st.markdown('## Detection: did the sensors see pedestrians and cyclists?')
R.grid(['ped_confirmed', 'cyc_confirmed', 'hotspot'])
st.markdown('## Movement: how much walking and cycling was recorded?')
R.grid(['ped_path', 'cyc_path', 'vru_path'])
st.markdown('## Tracking: could each sensor follow one object?')
R.grid(['duration', 'breaks', 'ids'])
R.grid(['reattach', 'jitter', 'footprint'])
st.markdown('## Safety indicators: potential conflicts (not near-misses)')
R.grid(['severe', 'severe_agree', 'stationary'])
st.markdown('## More detail')
with st.expander('Full scorecard: all 31 V2 metrics, aspect by aspect (no overall winner is computed)'):
    V = D.comparison_csv()
    sc = V[['aspect', 'metric', 'newsense', 'ouster', 'verdict', 'evidence_level', 'fair']].rename(columns={'aspect': 'Aspect', 'metric': 'Metric', 'newsense': 'Newsense', 'ouster': 'Ouster', 'verdict': 'Leans to', 'evidence_level': 'Evidence', 'fair': 'Like-for-like?'})
    st.dataframe(sc, hide_index=True, width='stretch', height=560)
    st.download_button('Download the V2 comparison table (CSV)', V.to_csv(index=False).encode(), 'FINAL_SENSOR_COMPARISON_V2.csv', 'text/csv')
    ui.source('FINAL_PACKAGE_V2/FINAL_SENSOR_COMPARISON.csv (31 metrics)')
with st.expander('Open questions the data cannot settle'):
    heads, rows = md.tables(src('unresolved'))[0]
    st.dataframe(pd.DataFrame(rows, columns=heads), hide_index=True, width='stretch', height=320)
    ui.source('stage4_traffic_analysis/final_audit/UNRESOLVED_ISSUES.md')
with st.expander('What the sensors delivered in the compared period (recorded sensor samples and track pieces)'):
    A = D.agg_minute(); S = D.segments()
    cnt = A.groupby(['sensor', 'grp']).observations.sum().unstack(0).fillna(0).astype(int); segc = S.groupby(['sensor', 'grp']).size().unstack(0).fillna(0).astype(int)
    names = {'PED': 'Pedestrian', 'CYC': 'Cyclist', 'MOTO': 'Motorcycle (Newsense only)', 'VEH': 'Vehicle', 'UNK': 'Unknown (Ouster only)'}
    st.dataframe(pd.DataFrame({'Object type': [names[g] for g in cnt.index], 'Newsense recorded samples': cnt.get('NS', 0).values, 'Ouster recorded samples': cnt.get('OU', 0).values,
                               'Newsense track pieces': segc.reindex(cnt.index).get('NS', 0).fillna(0).astype(int).values, 'Ouster track pieces': segc.reindex(cnt.index).get('OU', 0).fillna(0).astype(int).values}), hide_index=True, width='stretch')
    st.caption('A recorded sample is one object in one frame (10 per second), not a person. A track piece is one sensor ID split at gaps > 5 s or jumps > 15 m (C3 rule). Totals equal the C3 cache (1,138,826 / 1,559,358 samples; 8,744 / 17,827 track pieces).')

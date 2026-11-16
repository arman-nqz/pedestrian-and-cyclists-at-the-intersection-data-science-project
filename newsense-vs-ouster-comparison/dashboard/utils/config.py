"""Central configuration: paths, the authoritative (V2) sources, colours and vocabulary. Every page imports from here."""
import os, json
DASH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from .paths import OUT, S4, V2, DATA, RAW, resolve   # configurable via K305_OUTPUTS_DIR / K305_V2_DIR / K305_RAW_DATA_DIR
SOURCES = json.load(open(os.path.join(DASH, 'config', 'sources.json'), encoding='utf-8'))
def src(key): return resolve(SOURCES['files'][key]['path'])
# colours (dashboard identity, used everywhere)
C = dict(NS='#2563EB', OU='#059669', CAM='#334155', BOTH='#7C3AED', UNCERTAIN='#D97706', NA='#9CA3AF', INK='#0F172A', MUTED='#64748B', GRID='#E2E8F0',
         NS_LIGHT='#DBEAFE', OU_LIGHT='#D1FAE5', BOTH_LIGHT='#EDE9FE', UNC_LIGHT='#FEF3C7', NA_LIGHT='#F1F5F9')
SENSOR_NAME = {'NS': 'Newsense', 'OU': 'Ouster'}
GRP_NAME = {'PED': 'Pedestrian', 'CYC': 'Cyclist', 'MOTO': 'Motorcycle (Newsense)', 'VEH': 'Vehicle', 'UNK': 'UNKNOWN (Ouster)'}
STATUS_COLOR = {'Strong candidate match': C['BOTH'], 'Possible match': '#A78BFA', 'Ambiguous': C['UNCERTAIN'], 'Unmatched': '#E11D48', 'Cannot determine': C['NA']}
STATUS_HELP = {
 'Strong candidate match': 'Both sensors have a track at the same place and time: overlap >= 2 s, median distance <= 1 m, 90 % of points within 2 m, same direction. A candidate, not a confirmed identity.',
 'Possible match': 'Tracks overlap >= 1 s with median distance <= 2 m, but at least one strong criterion fails (listed in the evidence table).',
 'Ambiguous': 'Two or more tracks of a sensor fit about equally well (groups, waiting areas), or the partners were claimed by another track. No single partner can be chosen.',
 'Unmatched': 'Seen by one sensor only, although the place lies in the shared coverage area and no acceptable partner exists in the other sensor.',
 'Cannot determine': 'Seen by one sensor only, mostly outside the area both sensors cover, so the other sensor could not have seen it.'}
PERIOD = '29 Oct 2026, 07:12-08:35 CET (common period; Ouster log gaps masked)'
CET_OFFSET = 3600

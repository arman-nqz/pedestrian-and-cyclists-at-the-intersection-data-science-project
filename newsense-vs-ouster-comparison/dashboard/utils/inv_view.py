"""Rendering of one investigation (UI v2). Used by 'Follow One Person' and by the presentation mode.
All values come from utils.investigate (unchanged logic) - this module only words and arranges them."""
import html
import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
from . import data as D, investigate as I, ui
from .config import C, STATUS_HELP, SENSOR_NAME, GRP_NAME
from .timebase import clock
from components import player

GRP_PLAIN = {'PED': 'Pedestrian', 'CYC': 'Cyclist', 'MOTO': 'Motorcycle (Newsense label)', 'VEH': 'Vehicle', 'UNK': 'Unknown (Ouster label)', '-': None}

def label(inv): return 'Investigation #' + inv.split('-')[1]

def object_type(ns, ou):
    a, b = GRP_PLAIN.get(ns), GRP_PLAIN.get(ou)
    if a and b and a != b: return f'{a} (Newsense) / {b} (Ouster)'
    return a or b or 'Unknown'

def load(inv):
    cand, segs = I.members(inv); hist = I.histories(segs); evs = I.events(segs, hist); bw = I.both_window(segs, hist); m = I.metrics(segs, hist)
    return dict(inv=inv, cand=cand, segs=segs, hist=hist, evs=evs, bw=bw, m=m)

# ---------------------------------------------------------------- plain per-sensor summary (derived only from I.metrics and the segments)
def sensor_summary(X, s):
    mm = X['m'][s]
    if not mm: return None
    g = X['segs'][X['segs'].sensor == s].sort_values('t0')
    ids = list(dict.fromkeys(g.id.astype(str)))
    cnt, tot = mm['Missing periods > 0.35 s (count, total s)'].split(',')
    between = [float(b - a) for a, b in zip(g.t1.values[:-1], g.t0.values[1:]) if b > a]
    shares = mm['Classification (share of samples)']
    return dict(ids=ids, first=mm['First detection'], last=mm['Last detection'], dur=mm['Duration (first to last, s)'], n=mm['Observations'],
                pieces=mm['Fragmentation (segments)'], gaps_n=int(cnt), gaps_s=float(tot), between=between, class_changes=mm['Class changes within the track'],
                classes=shares, predicted=mm['Predicted (coasted) samples'], path=mm['Track length, robust moving path (m)'], reuse=mm['ID reuse / re-attachment'],
                shared=mm['Inside shared coverage'])

def interruptions_text(S):
    parts = []
    if S['gaps_n']: parts.append(f"{S['gaps_n']} interruption{'s' if S['gaps_n'] != 1 else ''} inside a track (total {S['gaps_s']:.1f} s without a position)")
    if S['pieces'] > 1: parts.append(f"split into {S['pieces']} track pieces" + (f" with {len(S['between'])} gap{'s' if len(S['between']) != 1 else ''} between them" if S['between'] else ''))
    return 'No. ' + 'Continuous track.' if not parts else 'Yes: ' + '; '.join(parts) + '.'

def classification_text(S, s):
    if S['class_changes'] == 0 and ',' not in S['classes']: return f"Yes: always {S['classes'].split(' ')[0]}."
    return f"No: {S['class_changes']} change{'s' if S['class_changes'] != 1 else ''} ({S['classes']})." if S['class_changes'] else f"Mixed labels across track pieces ({S['classes']})."

def ids_text(S):
    return ', '.join(S['ids']) + ('' if len(S['ids']) == 1 else f" ({len(S['ids'])} different IDs)")

# ---------------------------------------------------------------- blocks
def header(X, show_links=True):
    c = X['cand']; inv = X['inv']
    st.markdown(f"## {label(inv)} &nbsp; {ui.badge(c.status)}", unsafe_allow_html=True)
    plain = ui.STATUS_PLAIN[c.status][1]
    who = {'both': 'Both sensors reported a track here.', 'Newsense only': 'Only Newsense reported a track here.', 'Ouster only': 'Only Ouster reported a track here.'}[c.sensors]
    st.markdown(f"<div class='k-lead' style='margin-top:-.2rem'>{who} {plain} Object type: <b>{html.escape(object_type(c.ns_class, c.ou_class))}</b>. "
                f"Time: {clock(c.t0)}–{clock(c.t1)} on 29 Oct 2026.</div>", unsafe_allow_html=True)

def play(X, layout='side', window=240):
    c = X['cand']; segs = X['segs']; evs = list(X['evs'])
    t0, t1 = float(c.t0) - 8, float(c.t1) + 8
    if t1 - t0 > window:
        st.info(f'This investigation spans {t1 - t0:.0f} s. The player shows {window} s at a time; choose where the window starts.')
        off = st.slider('Window start (seconds after the first report)', 0, int(t1 - t0 - window), 0, 10, key=f'win_{X["inv"]}'); t0 += off; t1 = t0 + window
    if X['bw']: evs.append(dict(t=X['bw'][0], s='BOTH', label='Both sensors report a track (first common moment)', kind='both'))
    payload = player.build_payload(t0, t1, list(segs.seg), [e for e in evs if t0 <= e['t'] <= t1], title=X['inv'], opts={'layout': layout, **({'camlay': 'cam1'} if layout == 'stack' else {})})
    payload['tStart'] = min(t1, max(t0, float(c.t0) + 1.0))
    player.render(payload)

def tracking_cards(X):
    st.markdown('### How did each sensor track it?')
    cols = st.columns(2)
    for col, s in zip(cols, ('NS', 'OU')):
        S = sensor_summary(X, s)
        with col:
            if S is None:
                ui.card(f"<span style='color:{C[s]}'>{SENSOR_NAME[s]}</span>", 'Did not report a matching track for this investigation.' +
                        (' The object was mostly outside the area this sensor can see.' if X['cand'].status == 'Cannot determine' else ''), color=C[s]); continue
            rows = [('First detected', S['first'][:8]), ('Last detected', S['last'][:8]), ('Total tracking duration', f"{S['dur']} s"),
                    ('Number of tracking IDs', len(S['ids'])), ('Track pieces', S['pieces']), ('Interruptions inside tracks', f"{S['gaps_n']} ({S['gaps_s']:.1f} s)"),
                    ('Classification changes', S['class_changes']), ('Recorded sensor samples', f"{S['n']:,}"),
                    ('Estimated positions', S['predicted'] if s == 'OU' else 'not flagged by Newsense')]
            kv = ''.join(f'<div>{html.escape(a)}</div><div>{html.escape(str(b))}</div>' for a, b in rows)
            st.markdown(f"<div class='k-card' style='border-top:3px solid {C[s]}'><h4 style='color:{C[s]}'>{SENSOR_NAME[s]}</h4>"
                        f"<p>{SENSOR_NAME[s]} tracked {'this candidate' if s == 'NS' else 'its candidate'} from <b>{S['first'][:8]}</b> to <b>{S['last'][:8]}</b> ({S['dur']} s) "
                        f"with tracking ID{'s' if len(S['ids']) > 1 else ''} <b>{html.escape(', '.join(S['ids']))}</b>.</p><div class='k-kv'>{kv}</div></div>", unsafe_allow_html=True)
    if X['m']['NS'] and X['m']['OU']:
        st.caption('Overlapping times do not show that the two tracks belong to the same physical person. The match result below says how well positions agree; it is never a confirmed identity.')

def comparison_table(X):
    st.markdown('### Side-by-side comparison')
    S = {s: sensor_summary(X, s) for s in ('NS', 'OU')}
    na = 'not detected'
    q = [('What tracking number(s) were assigned?', lambda v, s: ids_text(v)),
         ('How long was it tracked?', lambda v, s: f"{v['dur']} seconds ({v['first'][:8]}–{v['last'][:8]})"),
         ('How many recorded sensor samples?', lambda v, s: f"{v['n']:,}"),
         ('Were there tracking interruptions?', lambda v, s: interruptions_text(v)),
         ('Was its classification consistent?', classification_text),
         ('Were any positions estimated rather than measured?', lambda v, s: v['predicted'] if s == 'OU' else 'Unknown: Newsense does not flag estimated positions.'),
         ('How far did it move (movement distance)?', lambda v, s: f"{v['path']} m"),
         ('Was a tracking ID re-used or re-attached?', lambda v, s: 'No.' if v['reuse'] == 'none' else v['reuse'])]
    rows = ''.join(f"<tr><td class='q'>{html.escape(a)}</td><td>{html.escape(str(f(S['NS'], 'NS') if S['NS'] else na))}</td><td>{html.escape(str(f(S['OU'], 'OU') if S['OU'] else na))}</td></tr>" for a, f in q)
    st.markdown(f"""<style>.k-cmp {{width:100%; border-collapse:separate; border-spacing:0; background:#fff; border:1px solid #E5E7EB; border-radius:14px; overflow:hidden; font-size:.93rem;}}
.k-cmp th {{text-align:left; padding:10px 14px; background:#F8FAFC; font-weight:600; border-bottom:1px solid #E5E7EB;}} .k-cmp td {{padding:9px 14px; border-bottom:1px solid #F1F5F9; vertical-align:top;}}
.k-cmp tr:last-child td {{border-bottom:0;}} .k-cmp td.q {{color:#334155; font-weight:500; width:34%;}}</style>
<table class='k-cmp'><tr><th>Question</th><th style='color:{C["NS"]}'>Newsense</th><th style='color:{C["OU"]}'>Ouster</th></tr>{rows}</table>""", unsafe_allow_html=True)

def match_explanation(X):
    c = X['cand']; E = I.related_edges(list(X['segs'].seg), top=50)
    alt = E[~E.member_pair & (E.edge_class != 'rejected')] if not E.empty else E
    st.markdown('### What does the match result mean here?')
    d = c.best_median_d
    if c.status == 'Ambiguous':
        txt = ('<b>This is an ambiguous match.</b> ' + (f'The closest Newsense and Ouster tracks were a median of {d:.2f} m apart, ' if d == d else '') +
               (f'but {len(alt)} other track pair{"s" if len(alt) != 1 else ""} fit{"s" if len(alt) == 1 else ""} acceptably too ' if len(alt) else 'but the acceptable partners were also claimed by other tracks ') +
               '(for example people walking in a group). The dashboard therefore does not decide which tracks belong together. <b>A small matching distance alone does not prove identity.</b>')
        ui.warn(txt)
    elif c.status in ('Strong candidate match', 'Possible match'):
        ui.info(f"<b>{ui.STATUS_PLAIN[c.status][0]}.</b> The tracks overlap in time and their positions were a median of {d:.2f} m apart. "
                'This supports, but does not prove, that both sensors saw the same road user: two people walking together would look the same. Check the video.')
    elif c.status == 'Unmatched':
        o = 'Ouster' if c.sensors == 'Newsense only' else 'Newsense'
        ui.info(f'<b>No reliable match in the other sensor.</b> The object was inside the area both sensors can see, but {o} had no acceptable track within 2 m at that time. '
                f'Either {o} missed it, or the reported object is not real (for example a fixed object reported as a person). The data alone cannot decide; the video can help.')
    else:
        ui.info('<b>Cannot determine.</b> The object was mostly outside the area the other sensor can see, so its absence there says nothing about a missed detection.')
    st.markdown('**What cannot be concluded:** which sensor is correct, whether this is a real person, and whether tracks from the two sensors belong to the same physical person. There is no ground truth.')

def technical(X):
    c, segs, hist, m, evs = X['cand'], X['segs'], X['hist'], X['m'], X['evs']
    st.markdown('### Technical details')
    with st.expander('Identifiers, original candidate ID and status definition'):
        st.markdown(f"""* **Investigation number:** {label(X['inv'])} = original candidate ID `{X['inv']}`, generated by this dashboard to organise a *possible* cross-sensor match. It is **not** a person's identity.
* **Newsense tracking ID(s):** {c.ns_ids or '—'} · **Ouster tracking ID(s):** {c.ou_ids or '—'} (original sensor IDs; the two sensors number objects independently).
* **Track segments (keys):** {', '.join(f'`{k}`' for k in segs.seg)}
* **Match status (technical term):** {c.status}. {STATUS_HELP[c.status]}
* **Best median distance between matched tracks:** {('%.3f m' % c.best_median_d) if c.best_median_d == c.best_median_d else 'n/a'} (a ranking quantity, not a probability).
* **Direct link:** `/follow_one_person?inv={X['inv']}`""")
    with st.expander('All metrics (original technical names)'):
        rows = sorted({k for s in ('NS', 'OU') if m[s] for k in m[s]}, key=lambda k: list((m['NS'] or m['OU']).keys()).index(k) if k in (m['NS'] or m['OU']) else 99)
        comp = pd.DataFrame({'Metric': rows, 'Newsense': [(m['NS'] or {}).get(r, 'not detected') for r in rows], 'Ouster': [(m['OU'] or {}).get(r, 'not detected') for r in rows]})
        st.dataframe(comp.astype(str), hide_index=True, width='stretch', height=min(600, 36 * len(comp) + 40))
        st.markdown('**Generated interpretation (from this object\'s data only)**')
        for line in I.interpretation(c, segs, hist, m, X['bw'], None): st.markdown('- ' + line)
        st.caption('Robust moving path = CORR-01 rule (1-s steps ≥ 0.5 m). Missing period = gap between consecutive samples > 0.35 s. Fragmentation = number of track segments (C3 rule: new segment after > 5 s or a jump > 15 m within ≤ 1 s).')
    with st.expander('Matching evidence: every compared track pair, including rejected alternatives'):
        E = I.related_edges(list(segs.seg), top=15)
        if E.empty: st.info('No track of the other sensor overlapped this object in time and space, so there was nothing to compare.')
        else:
            show = pd.DataFrame({'Newsense': 'ID ' + E.ns_id.astype(str) + ' (' + E.ns_grp + ')', 'Ouster': 'ID ' + E.ou_id.astype(str) + ' (' + E.ou_grp + ')', 'In this investigation': np.where(E.member_pair, 'yes', 'alternative'),
                                 'Overlap (s)': E.overlap_s, 'Overlap fraction': E.overlap_frac, 'Median distance (m)': E.median_d, '90th percentile distance (m)': E.p90_d, 'Within 2 m': (E.within2m * 100).round(0).astype(int).astype(str) + ' %',
                                 'Direction agreement (cos)': E.dir_agree.round(2), 'Speed difference (m/s)': E.speed_diff_med, 'Best clock shift (s)': E.best_dt_s, 'Class': E.class_agree,
                                 'Edge class': E.edge_class, 'Mutually selected': np.where(E.kept, 'yes', 'no'), 'Ambiguity flag': np.where(E.ambiguous_flag, 'yes', ''), 'Reason': E.reason})
            st.dataframe(show, hide_index=True, width='stretch')
        st.markdown("""Each row compares one Newsense track with one Ouster track over their common time, after shifting the Newsense clock by the *best clock shift* (searched within the ±0.7 s Stage 3 bound).
*strong*: overlap ≥ 2 s and ≥ 50 % of the shorter track, median ≤ 1 m, 90th percentile ≤ 2 m, ≥ 80 % within 2 m, same direction. *possible*: overlap ≥ 1 s, median ≤ 2 m, ≥ 50 % within 2 m.
A link enters the investigation only if **both** tracks choose each other as their best partner for that moment. The median distance is a ranking quantity, **not a probability**; it is not calibrated against ground truth.""")
    with st.expander('Trajectory, speed and distance charts'):
        c1, c2 = st.columns([3, 2])
        fig = go.Figure()
        for r in segs.itertuples():
            h = hist[r.seg]; col = C[r.sensor]
            fig.add_trace(go.Scatter(x=h.x, y=h.y, mode='lines+markers', name=f'{SENSOR_NAME[r.sensor]} ID {r.id}', line=dict(color=col, width=2), marker=dict(size=4, color=col),
                                     customdata=np.c_[[clock(t, True) for t in h.t], h.speed, h.cls.astype(str)], hovertemplate='%{customdata[0]}<br>x %{x:.2f} m, y %{y:.2f} m<br>%{customdata[2]}, %{customdata[1]:.2f} m/s<extra>' + f'{SENSOR_NAME[r.sensor]} ID {r.id}</extra>'))
            fig.add_trace(go.Scatter(x=[h.x.iloc[0]], y=[h.y.iloc[0]], mode='markers+text', text=['start'], textposition='top center', marker=dict(symbol='circle-open', size=12, color=col), showlegend=False, hoverinfo='skip'))
        fig.update_yaxes(scaleanchor='x', scaleratio=1)
        c1.plotly_chart(ui.plot_style(fig, 480, 'Path on the ground (Ouster coordinate frame)', 'x position (m); north not verified', 'y position (m)'), width='stretch')
        sp = go.Figure()
        for r in segs.itertuples():
            h = hist[r.seg]; sp.add_trace(go.Scatter(x=[clock(t, True) for t in h.t], y=h.speed, mode='lines', name=f'{SENSOR_NAME[r.sensor]} ID {r.id}', line=dict(color=C[r.sensor])))
        c2.plotly_chart(ui.plot_style(sp, 240, 'Reported speed', 'time (CET)', 'speed (m/s)'), width='stretch')
        K = D.edges(); K = K[K.kept & K.ns_seg.isin(segs.seg) & K.ou_seg.isin(segs.seg)]
        dfig = go.Figure()
        for r in K.itertuples():
            a, b = hist[r.ns_seg], hist[r.ou_seg]; g = np.arange(max(a.t.min() - r.best_dt_s, b.t.min()), min(a.t.max() - r.best_dt_s, b.t.max()), 0.2)
            if len(g) < 2: continue
            d = np.hypot(np.interp(g + r.best_dt_s, a.t, a.x) - np.interp(g, b.t, b.x), np.interp(g + r.best_dt_s, a.t, a.y) - np.interp(g, b.t, b.y))
            dfig.add_trace(go.Scatter(x=[clock(t, True) for t in g], y=d, mode='lines', name=f'Newsense {r.ns_id} ↔ Ouster {r.ou_id}', line=dict(color=C['BOTH'])))
        c2.plotly_chart(ui.plot_style(dfig, 240, 'Distance between matched tracks', 'time (CET)', 'distance (m)'), width='stretch')
        c2.caption('Distance uses linear interpolation between actual samples on a 0.2 s grid, only where both have samples, with the best clock shift of the pair. Empty when no pair was kept.')
    with st.expander('Event log'):
        st.dataframe(pd.DataFrame([dict(Time=clock(e['t'], True), Sensor={'NS': 'Newsense', 'OU': 'Ouster', 'BOTH': 'Both'}[e['s']], Event=e['label']) for e in evs]), hide_index=True, width='stretch')
    with st.expander('Raw sensor samples (CSV export)'):
        raw = pd.concat([hist[k].assign(sensor=k[:2]) for k in segs.seg]).sort_values('t')
        raw = raw[['sensor', 't', 'id', 'cls', 'x', 'y', 'vx', 'vy', 'speed', 'L', 'W', 'yaw_deg', 'score', 'lag_s', 'refind_t', 'coasted', 'region']]
        raw.insert(2, 'time CET', [clock(t, True) for t in raw.t])
        st.dataframe(raw, hide_index=True, width='stretch', height=340)
        st.download_button('Download these samples (CSV)', raw.to_csv(index=False).encode(), f"{X['inv']}_samples.csv", 'text/csv', key=f"dl_{X['inv']}")
        st.caption('Original detections (Newsense converted to the Ouster frame). score = Newsense score / Ouster classification confidence; lag_s = Ouster update lag (> 0.05 s = estimated); refind_t = Ouster refind_time; coasted = estimated position.')

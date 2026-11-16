"""Shared UI (dashboard UI v2): design tokens, page intro, cards, status badges, glossary terms, chart styling.
Presentation only - no research value is computed here."""
import html, streamlit as st
from .config import C, STATUS_COLOR

FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, 'Helvetica Neue', Arial, sans-serif"
CSS = f"""
<style>
:root {{ --ns:{C['NS']}; --ou:{C['OU']}; --cam:{C['CAM']}; --both:{C['BOTH']}; --unc:{C['UNCERTAIN']}; --ink:{C['INK']}; --muted:{C['MUTED']};
        --line:#E5E7EB; --soft:#F8FAFC; --card:#FFFFFF; --radius:14px; }}
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {{ font-family:{FONT}; }}
.block-container {{ padding-top:2.2rem; padding-bottom:4rem; max-width:1320px; }}
[data-testid="stSidebar"] {{ background:#FFFFFF; border-right:1px solid var(--line); }}
[data-testid="stSidebarNav"] a span {{ font-size:.92rem; }}
h1 {{ font-size:2.0rem !important; font-weight:700 !important; letter-spacing:-0.02em; color:var(--ink); margin-bottom:.2rem !important; }}
h2 {{ font-size:1.35rem !important; font-weight:650 !important; letter-spacing:-0.01em; color:var(--ink); margin-top:1.6rem !important; }}
h3 {{ font-size:1.1rem !important; font-weight:650 !important; color:var(--ink); }}
h4, h5 {{ font-weight:600 !important; color:var(--ink); }}
p, li {{ line-height:1.55; }}
.k-eyebrow {{ font-size:.78rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin-bottom:.35rem; }}
.k-lead {{ font-size:1.08rem; color:#334155; max-width:860px; margin:.2rem 0 1rem 0; line-height:1.55; }}
.k-card {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius); padding:18px 20px; box-shadow:0 1px 2px rgba(15,23,42,.04); height:100%; }}
.k-card h4 {{ margin:0 0 6px 0; font-size:1rem; }}
.k-card p {{ margin:0; color:#475569; font-size:.92rem; }}
.k-card .k-mini {{ font-size:.8rem; color:var(--muted); margin-top:8px; }}
.k-finding {{ background:#F5F3FF; border:1px solid #DDD6FE; border-radius:var(--radius); padding:14px 18px; margin:.4rem 0 1rem 0; }}
.k-finding .t {{ font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#6D28D9; }}
.k-finding .b {{ font-size:1.0rem; color:var(--ink); margin-top:4px; line-height:1.5; }}
.k-note {{ background:#FFFBEB; border:1px solid #FDE68A; border-radius:12px; padding:10px 14px; font-size:.9rem; color:#78350F; margin:.4rem 0 .8rem 0; }}
.k-info {{ background:#F1F5F9; border:1px solid var(--line); border-radius:12px; padding:10px 14px; font-size:.9rem; color:#334155; margin:.4rem 0 .8rem 0; }}
.k-badge {{ display:inline-flex; align-items:center; gap:6px; padding:3px 11px; border-radius:999px; font-size:.82rem; font-weight:600; border:1px solid; }}
.k-dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; }}
.k-chip {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:.78rem; font-weight:600; margin-right:4px; color:#fff; }}
.k-sensor {{ display:inline-flex; align-items:center; gap:6px; font-weight:600; }}
.k-src {{ font-size:.76rem; color:var(--muted); margin-top:.6rem; }}
.k-kv {{ display:grid; grid-template-columns: 1fr auto; gap:7px 14px; font-size:.92rem; margin-top:10px; }}
.k-kv div:nth-child(odd) {{ color:#475569; }} .k-kv div:nth-child(even) {{ font-weight:600; text-align:right; font-variant-numeric:tabular-nums; }}
.k-stat {{ font-size:1.6rem; font-weight:700; font-variant-numeric:tabular-nums; letter-spacing:-0.01em; }}
.k-stat-l {{ font-size:.8rem; color:var(--muted); }}
.k-term {{ border-bottom:1px dotted #94A3B8; cursor:help; }}
.k-legend {{ display:flex; flex-wrap:wrap; gap:16px; font-size:.86rem; color:#334155; margin:.2rem 0 .6rem 0; }}
.k-legend span {{ display:inline-flex; align-items:center; gap:6px; }}
.k-step {{ display:inline-flex; width:26px; height:26px; border-radius:50%; background:#EEF2FF; color:#4338CA; font-weight:700; align-items:center; justify-content:center; font-size:.85rem; margin-right:8px; }}
div[data-testid="stExpander"] details {{ border-radius:12px; border-color:var(--line); background:#FFFFFF; }}
div[data-testid="stExpander"] summary p {{ font-weight:600; }}
div[data-testid="stMetric"] {{ background:#FFFFFF; border:1px solid var(--line); border-radius:12px; padding:10px 14px; }}
.stTabs [data-baseweb="tab-list"] {{ gap:4px; }}
.stTabs [data-baseweb="tab"] {{ padding:6px 14px; }}
div[class*="st-key-navcard"] {{ background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:20px 20px 12px 20px; box-shadow:0 1px 3px rgba(15,23,42,.05); transition:box-shadow .15s, border-color .15s; }}
div[class*="st-key-navcard"]:hover {{ box-shadow:0 6px 20px rgba(15,23,42,.08); border-color:#C7D2FE; }}
[data-testid="stToolbar"] {{ display:none; }}
footer {{ visibility:hidden; }}
</style>"""

# ---------------------------------------------------------------- plain-language vocabulary (display only)
STATUS_PLAIN = {
    'Strong candidate match': ('Strong candidate match', 'Both sensors had a track at the same place and time, and the positions agree closely. This is a candidate, not a confirmed identity.'),
    'Possible match': ('Possible match', 'Both sensors had a nearby track, but the agreement is weaker than for a strong candidate.'),
    'Ambiguous': ('Ambiguous: identity cannot be determined', 'More than one possible match exists (for example in a group), so the dashboard does not choose one.'),
    'Unmatched': ('No reliable match in the other sensor', 'Only one sensor reported this object, inside the area both sensors can see.'),
    'Cannot determine': ('Cannot determine', 'Only one sensor reported this object, mostly outside the area the other sensor can see.'),
}
GLOSSARY = {
    'Tracking ID': 'The number a sensor gives an object so it can follow it from frame to frame. Each sensor numbers objects independently; equal numbers mean nothing.',
    'Investigation number': 'A reference created by this dashboard (#00718 = INV-00718) to group tracks that may belong to one road user. It is not a person\'s identity.',
    'Recorded sensor sample': 'One position report of one object in one sensor frame (10 per second). Called an "observation" in the research reports.',
    'Track fragmentation': 'One object was split into several tracking IDs or track pieces, so the sensor lost and restarted it.',
    'Tracking interruption': 'A period of more than 0.35 s in which a sensor reported no position for a tracked object.',
    'Estimated position': 'A position the sensor predicted while it had no direct measurement (Ouster "coasted" samples). Newsense does not flag these.',
    'Classification change': 'The sensor changed the object type it reported (e.g. Pedestrian to Cyclist) during one track.',
    'Movement distance': 'Distance travelled while the object was moving above the speed threshold (the "robust moving path": 1-s steps of at least 0.5 m). It ignores the jitter of standing objects.',
    'Shared area': 'The 2,780 m² both sensors can see. Cross-sensor comparisons are made only there.',
    'Agreement vs accuracy': 'Agreement means both sensors report the same thing. It does not show which one is right: there is no ground truth.',
}

def style():
    st.markdown(CSS, unsafe_allow_html=True)

def setup(title, subtitle='', eyebrow=''):
    """Page header: eyebrow, title, lead sentence."""
    style()
    if eyebrow: st.markdown(f'<div class="k-eyebrow">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f'# {title}')
    if subtitle: st.markdown(f'<div class="k-lead">{subtitle}</div>', unsafe_allow_html=True)

def intro(title, answers, finding_text=None, eyebrow='', finding_title='Main finding'):
    """Standard page opening: what the page answers, then the main finding first."""
    setup(title, answers, eyebrow)
    if finding_text: finding(finding_text, finding_title)

def finding(text, title='What to notice'):
    st.markdown(f'<div class="k-finding"><div class="t">{html.escape(title)}</div><div class="b">{text}</div></div>', unsafe_allow_html=True)

def card(title, body, mini='', color=None):
    bar = f'border-top:3px solid {color};' if color else ''
    st.markdown(f'<div class="k-card" style="{bar}"><h4>{title}</h4><p>{body}</p>{f"<div class=k-mini>{mini}</div>" if mini else ""}</div>', unsafe_allow_html=True)

def sensor_tag(s):
    name = {'NS': 'Newsense', 'OU': 'Ouster', 'CAM': 'Original camera', 'BOTH': 'Both sensors'}[s]
    col = {'NS': C['NS'], 'OU': C['OU'], 'CAM': C['CAM'], 'BOTH': C['BOTH']}[s]
    return f'<span class="k-sensor"><span class="k-dot" style="background:{col}"></span>{name}</span>'

def legend():
    st.markdown('<div class="k-legend">' + ''.join(f'<span>{sensor_tag(s)}</span>' for s in ('CAM', 'NS', 'OU', 'BOTH')) +
                f'<span><span class="k-dot" style="background:{C["UNCERTAIN"]}"></span>Uncertain</span><span><span class="k-dot" style="background:{C["NA"]}"></span>Not available</span></div>', unsafe_allow_html=True)

def chip(text, color, fg='#fff'): return f'<span class="k-chip" style="background:{color};color:{fg}">{html.escape(str(text))}</span>'

def badge(status, plain=True):
    col = STATUS_COLOR.get(status, C['NA']); lab = STATUS_PLAIN.get(status, (status, ''))[0] if plain else status
    return f'<span class="k-badge" style="color:{col};border-color:{col}55;background:{col}14"><span class="k-dot" style="background:{col}"></span>{html.escape(lab)}</span>'

def term(word, key=None):
    """Inline glossary term with a hover definition."""
    d = GLOSSARY.get(key or word, '')
    return f'<span class="k-term" title="{html.escape(d)}">{html.escape(word)}</span>'

def glossary(keys, title='What do these terms mean?', expanded=False):
    with st.expander(title, expanded=expanded):
        for k in keys: st.markdown(f'**{k}**: {GLOSSARY[k]}')

def kpi(label, ns, ou, unit='', note='', src_txt=''):
    """Two-sensor result card (values passed through unchanged from V2)."""
    st.markdown(f'''<div class="k-card"><div style="font-weight:600;color:#334155;font-size:.92rem;min-height:2.6em">{html.escape(label)}</div>
      <div style="display:flex;gap:22px;margin-top:6px;flex-wrap:wrap">
      <div><div class="k-stat" style="color:{C['NS']};{'font-size:.95rem;font-weight:600;line-height:1.35' if len(str(ns)) > 18 else ''}">{html.escape(str(ns))}</div><div class="k-stat-l">Newsense {html.escape(unit)}</div></div>
      <div><div class="k-stat" style="color:{C['OU']};{'font-size:.95rem;font-weight:600;line-height:1.35' if len(str(ou)) > 18 else ''}">{html.escape(str(ou))}</div><div class="k-stat-l">Ouster {html.escape(unit)}</div></div></div>
      {f'<div style="font-size:.84rem;color:#475569;margin-top:10px;line-height:1.45">{html.escape(note)}</div>' if note else ''}
      {f'<div class="k-src">{html.escape(src_txt)}</div>' if src_txt else ''}</div>''', unsafe_allow_html=True)

def source(*items):
    st.markdown('<div class="k-src">Source: ' + ' · '.join(html.escape(i) for i in items) + '</div>', unsafe_allow_html=True)

def warn(text): st.markdown(f'<div class="k-note">{text}</div>', unsafe_allow_html=True)
def info(text): st.markdown(f'<div class="k-info">{text}</div>', unsafe_allow_html=True)

def timing_note(short=True):
    txt = ('<b>Timing uncertainty.</b> The video is matched to sensor time with the approved clock model plus an extra 2.81 s offset whose cause is still '
           '<b>unexplained</b>. The two sensors agree with each other to within about ±0.7 s.')
    if not short: txt += ' The offset is used only to find the right video frames; it is never treated as a clock correction.'
    warn(txt)

def plot_style(fig, h=360, title=None, x=None, y=None):
    """Consistent chart styling. Pass axis titles (with units) explicitly."""
    t = title if title is not None else fig.layout.title.text
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=78 if t else 36, b=50), paper_bgcolor='white', plot_bgcolor='white',
                      font=dict(family=FONT, size=13, color=C['INK']), legend=dict(orientation='h', y=1.0, x=1, yanchor='bottom', xanchor='right', font=dict(size=12), bgcolor='rgba(255,255,255,0)'),
                      hoverlabel=dict(bgcolor='white', font=dict(family=FONT)), title=dict(text=t, font=dict(size=15), x=0, xanchor='left', y=0.98, yanchor='top', yref='container'))
    fig.update_xaxes(gridcolor='#EEF2F7', zeroline=False, linecolor='#CBD5E1', title_font=dict(size=12, color=C['MUTED']))
    fig.update_yaxes(gridcolor='#EEF2F7', zeroline=False, linecolor='#CBD5E1', title_font=dict(size=12, color=C['MUTED']))
    if x: fig.update_xaxes(title_text=x)
    if y: fig.update_yaxes(title_text=y)
    return fig

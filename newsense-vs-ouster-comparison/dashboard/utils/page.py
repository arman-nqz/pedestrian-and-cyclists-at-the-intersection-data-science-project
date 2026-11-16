"""UI v4 helpers for the analytical pages (additive; utils/ui.py is unchanged so the interactive pages keep their exact look).
metric_strip: one compact row of Newsense-vs-Ouster numbers (values passed through unchanged)."""
import html, streamlit as st
from .config import C
CSS = f"""<style>
.k4-strip {{display:grid; grid-template-columns:repeat(var(--n),1fr); background:#fff; border:1px solid #E5E7EB; border-radius:14px; margin:.3rem 0 1.1rem 0;}}
.k4-strip > div {{padding:12px 16px; border-right:1px solid #F1F5F9;}} .k4-strip > div:last-child {{border-right:0;}}
.k4-l {{font-size:.8rem; color:#475569; font-weight:600; line-height:1.3; min-height:2.1em;}}
.k4-v {{display:flex; flex-direction:column; gap:2px; margin-top:6px;}}
.k4-v span {{font-size:1.25rem; font-weight:700; font-variant-numeric:tabular-nums;}} .k4-v small {{font-size:.72rem; color:#64748B; font-weight:500; margin-left:3px;}}
.k4-n {{font-size:.75rem; color:#64748B; margin-top:5px; line-height:1.35;}}
.k4-q {{font-size:.95rem; color:#475569; margin:-.4rem 0 .6rem 0;}}
@media (max-width: 900px) {{ .k4-strip {{grid-template-columns:1fr 1fr;}} }}
</style>"""
def style(): st.markdown(CSS, unsafe_allow_html=True)
def metric_strip(items):
    """items: list of (label, newsense_value, ouster_value, note)."""
    cells = ''.join(f"<div><div class='k4-l'>{html.escape(l)}</div><div class='k4-v'><span style='color:{C['NS']}'>{html.escape(str(a))}<small>Newsense</small></span>"
                    f"<span style='color:{C['OU']}'>{html.escape(str(b))}<small>Ouster</small></span></div>" + (f"<div class='k4-n'>{html.escape(n)}</div>" if n else '') + "</div>" for l, a, b, n in items)
    st.markdown(f"<div class='k4-strip' style='--n:{len(items)}'>{cells}</div>", unsafe_allow_html=True)
def section(title, question=None):
    st.markdown(f'## {title}')
    if question: st.markdown(f"<div class='k4-q'>{html.escape(question)}</div>", unsafe_allow_html=True)
def v2(sub):
    """Row of the V2 comparison table whose metric contains `sub` (read-only)."""
    from . import data as D
    V = D.comparison_csv(); m = V[V.metric.str.contains(sub, regex=False)]; return m.iloc[0]
def table(df, widths=None):
    """Wrapping, read-only text table (for explanatory tables; numeric/interactive tables stay st.dataframe)."""
    w = widths or [None] * len(df.columns)
    head = ''.join(f"<th style='{f'width:{x};' if x else ''}'>{html.escape(str(c))}</th>" for c, x in zip(df.columns, w))
    body = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in r) + '</tr>' for r in df.itertuples(index=False))
    st.markdown(f"""<style>.k4-t {{width:100%; border-collapse:separate; border-spacing:0; background:#fff; border:1px solid #E5E7EB; border-radius:12px; overflow:hidden; font-size:.9rem; margin:.2rem 0 .8rem 0;}}
.k4-t th {{text-align:left; padding:9px 12px; background:#F8FAFC; font-weight:600; border-bottom:1px solid #E5E7EB; color:#334155;}} .k4-t td {{padding:8px 12px; border-bottom:1px solid #F1F5F9; vertical-align:top; line-height:1.45;}}
.k4-t tr:last-child td {{border-bottom:0;}} .k4-t td:first-child {{font-weight:600; color:#0F172A;}}</style><table class='k4-t'><tr>{head}</tr>{body}</table>""", unsafe_allow_html=True)

"""Plotly helpers: the K305 base map (OSM roads, footways, zones) in sensor meters."""
import math

import plotly.graph_objects as go

from lib import data

LIM = 46


def base_map(fig, show_osm=True, show_zones=True, row=None, col=None):
    kw = {"row": row, "col": col} if row else {}
    osm = data.osm_map() if show_osm else None
    if osm:
        for group, color, width in (("roads", "rgba(120,120,120,0.55)", 1.5), ("footways", "rgba(60,150,90,0.55)", 1)):
            xs, ys = [], []
            for f in osm[group]:
                for x, y in f["xy"]:
                    xs.append(x)
                    ys.append(y)
                xs.append(None)
                ys.append(None)
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=width),
                                     name=f"OSM {group}", hoverinfo="skip", showlegend=True), **kw)
    z = data.zones() if show_zones else None
    if z:
        for c in z["crossings"]:
            poly = c["polygon"] + [c["polygon"][0]]
            fig.add_trace(go.Scatter(x=[p[0] for p in poly], y=[p[1] for p in poly], mode="lines", fill="toself",
                                     line=dict(color="#1a9850", width=2), fillcolor="rgba(26,152,80,0.12)",
                                     name=c["id"], hovertext=f"{c['id']}: crossing, {c['road'] or ''}", hoverinfo="text",
                                     showlegend=False), **kw)
        cx, cy = z["junction"]["center"]
        for a in z["junction"]["arms"]:
            ang = math.radians(a["sensor_angle_deg"])
            fig.add_annotation(x=cx + 33 * math.cos(ang), y=cy + 33 * math.sin(ang), text=f"<b>{a['id']}</b>",
                               showarrow=False, font=dict(size=14, color="#1f4e8c"), **({"row": row, "col": col} if row else {}))
    return fig


def square_axes(fig, row=None, col=None):
    kw = {"row": row, "col": col} if row else {}
    fig.update_xaxes(range=[-LIM, LIM], title="x (m)", constrain="domain", **kw)
    fig.update_yaxes(range=[-LIM, LIM], title="y (m)", scaleanchor="x" if not row else None, constrain="domain", **kw)
    return fig

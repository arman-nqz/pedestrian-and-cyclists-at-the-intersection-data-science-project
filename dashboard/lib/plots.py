"""Plotly helpers: the K305 base map (OSM-style roads, buildings, street names, zones) in sensor meters."""
import math

import numpy as np
import plotly.graph_objects as go

from lib import data

LIM = 46
LAND = "#f2efe9"
# highway type: (fill, casing, default width m, draw order); OSM Carto colors
ROAD_STYLE = {
    "trunk": ("#f9b29c", "#c84e2f", 7.0, 5),
    "trunk_link": ("#f9b29c", "#c84e2f", 3.5, 4),
    "primary": ("#fcd6a4", "#a06b00", 8.0, 5),
    "secondary": ("#f7fabf", "#707d05", 7.0, 3),
    "tertiary": ("#ffffff", "#8f8f8f", 6.0, 2),
    "residential": ("#ffffff", "#9a9a9a", 6.0, 1),
    "service": ("#ffffff", "#9a9a9a", 4.0, 0),
}
LANE_M = 3.0


def _band(xy, width):
    """Polygon around a polyline, `width` meters wide (simple vertex normals; fine for a background map)."""
    p = np.asarray(xy, float)
    if len(p) < 2:
        return None
    d = np.gradient(p, axis=0)
    d /= np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
    n = np.c_[-d[:, 1], d[:, 0]] * width / 2
    ring = np.vstack([p + n, (p - n)[::-1], p[:1] + n[:1]])
    return ring


def _join(polys):
    xs, ys = [], []
    for q in polys:
        xs += list(q[:, 0]) + [None]
        ys += list(q[:, 1]) + [None]
    return xs, ys


def _width(f):
    try:
        return int(f.get("lanes")) * LANE_M
    except (TypeError, ValueError):
        return ROAD_STYLE[f["highway"]][2]


def _labels(roads, lim=LIM - 4, min_len=12, spacing=30):
    """(x, y, angle, name): one label per named road piece inside the view, at least `spacing` m apart per name."""
    out = []
    for f in sorted(roads, key=lambda f: -len(f["xy"])):
        if not f.get("name"):
            continue
        p = np.asarray(f["xy"], float)
        seg = np.diff(p, axis=0)
        mid = (p[1:] + p[:-1]) / 2
        inside = (np.abs(mid) < lim).all(axis=1)
        L = np.hypot(seg[:, 0], seg[:, 1]) * inside
        if L.sum() < min_len:
            continue
        cum = np.cumsum(L)
        i = int(np.searchsorted(cum, cum[-1] / 2))  # segment at half the visible length
        x, y = mid[i]
        if any(n == f["name"] and math.hypot(x - a, y - b) < spacing for a, b, _, n in out):
            continue
        ang = -math.degrees(math.atan2(seg[i, 1], seg[i, 0]))
        ang = (ang + 90) % 180 - 90  # keep text upright
        out.append((float(x), float(y), ang, f["name"]))
    return out


def base_map(fig, show_osm=True, show_zones=True, row=None, col=None):
    """Draw the map. Area layers go *behind* traces already in the figure; names and zones go on top."""
    kw = {"row": row, "col": col} if row else {}
    osm = data.osm_map() if show_osm else None
    if osm:
        n_before = len(fig.data)
        common = dict(mode="lines", hoverinfo="skip", showlegend=False, legendgroup="osm")

        def area(polys, fill, line, width=0.6, **extra):
            if polys:
                xs, ys = _join(polys)
                fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=fill, line=dict(color=line, width=width),
                                         **common, **extra), **kw)

        area([np.asarray(f["xy"]) for f in osm.get("areas", [])], "#cdebb0", "#aed1a0")
        area([np.asarray(f["xy"]) for f in osm.get("buildings", [])], "#d9d0c9", "#b9a99c")
        for r in osm.get("railway", []):
            p = np.asarray(r["xy"])
            fig.add_trace(go.Scatter(x=p[:, 0], y=p[:, 1], line=dict(color="#8a8a8a", width=4), **common), **kw)
            fig.add_trace(go.Scatter(x=p[:, 0], y=p[:, 1], line=dict(color="#ffffff", width=2, dash="dash"), **common), **kw)
        roads = sorted((f for f in osm["roads"] if f["highway"] in ROAD_STYLE), key=lambda f: ROAD_STYLE[f["highway"]][3])
        for f in roads:  # casings first, so overlapping pieces merge into one road
            fill, casing, _, _ = ROAD_STYLE[f["highway"]]
            area([_band(f["xy"], _width(f) + 1.2)], casing, casing, width=0.5)
        for hw in sorted({f["highway"] for f in roads}, key=lambda h: ROAD_STYLE[h][3]):
            fill = ROAD_STYLE[hw][0]
            area([_band(f["xy"], _width(f)) for f in roads if f["highway"] == hw], fill, fill, width=0.5)
        xs, ys = _join([np.asarray(f["xy"]) for f in osm["footways"]])
        fig.add_trace(go.Scatter(x=xs, y=ys, line=dict(color="#fa8072", width=1.5, dash="dot"), name="OpenStreetMap",
                                 mode="lines", hoverinfo="skip", showlegend=True, legendgroup="osm"), **kw)
        new = fig.data[n_before:]
        fig.data = tuple(new) + tuple(fig.data[:n_before])  # map behind the data
        for x, y, ang, name in _labels(osm["roads"], spacing=60 if row else 35):  # small subplots: fewer labels
            fig.add_annotation(x=x, y=y, text=name, textangle=ang, showarrow=False,
                               font=dict(size=9 if row else 11, color="#333333"), bgcolor="rgba(255,255,255,0.6)", **kw)
        fig.update_layout(plot_bgcolor=LAND)
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=False, zeroline=False)
    z = data.zones() if show_zones else None
    if z:
        for c in z["crossings"]:
            poly = c["polygon"] + [c["polygon"][0]]
            fig.add_trace(go.Scatter(x=[p[0] for p in poly], y=[p[1] for p in poly], mode="lines", fill="toself",
                                     line=dict(color="#1a9850", width=2), fillcolor="rgba(26,152,80,0.12)",
                                     name=c["id"], hovertext=f"{c['id']}: crossing, {c['road'] or ''}", hoverinfo="text",
                                     showlegend=False), **kw)
            cx_, cy_ = np.mean(c["polygon"], axis=0)
            fig.add_annotation(x=cx_, y=cy_, text=c["id"], showarrow=False, font=dict(size=10, color="#1a6a3a"), **kw)
        cx, cy = z["junction"]["center"]
        for a in z["junction"]["arms"]:
            ang = math.radians(a["sensor_angle_deg"])
            fig.add_annotation(x=cx + 33 * math.cos(ang), y=cy + 33 * math.sin(ang), text=f"<b>{a['id']}</b>",
                               showarrow=False, font=dict(size=14, color="#1f4e8c"), **kw)
    return fig


def square_axes(fig, row=None, col=None):
    kw = {"row": row, "col": col} if row else {}
    fig.update_xaxes(range=[-LIM, LIM], title="x (m)", constrain="domain", **kw)
    fig.update_yaxes(range=[-LIM, LIM], title="y (m)", scaleanchor="x" if not row else None, constrain="domain", **kw)
    return fig

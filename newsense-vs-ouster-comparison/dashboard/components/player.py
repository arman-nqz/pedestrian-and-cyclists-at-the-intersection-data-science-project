"""Synchronized player component (original video + Newsense map + Ouster map + timeline). Builds a compact payload from ACTUAL sensor rows
(utils.data.Obs) and renders components/player.js inside an iframe. The video is streamed read-only by utils/video_server.py."""
import os, json, math
import numpy as np, streamlit as st
import streamlit.components.v1 as components
from utils import data as D, timebase as TB, video_server
from utils.config import C
CAMS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'cameras.json')
JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'player.js'), encoding='utf-8').read()
GAPS = [(1793255611.628, 1793255619.128), (1793256261.131, 1793256263.331), (1793258775.342, 1793258782.843), (1793258899.443, 1793258901.543)]
CLS = ['Pedestrian', 'Cyclist', 'Motorcycle', 'Car', 'Van', 'Truck', 'Bus', 'PERSON', 'BICYCLE', 'VEHICLE', 'LARGE_VEHICLE', 'UNKNOWN']
CI = {c: i for i, c in enumerate(CLS)}
def build_payload(t0, t1, selected, events, title='', margin=12.0, bounds=None, context=True, max_ctx_dist=None, opts=None):
    """t0, t1: sensor-time window; selected: list of segment keys (both sensors); events: list of dict(t, s, label)."""
    segs, sidx, frames = [], {}, {}
    sel = set(selected); xs, ys = [], []
    for s in ('NS', 'OU'):
        w = D.obs(s).window(t0, t1)
        if not context: w = w[w.seg.isin(sel)]
        if len(sel) and bounds is None:
            ws = w[w.seg.isin(sel)]; xs += list(ws.x); ys += list(ws.y)
        frames[s] = w
    if bounds is None:
        if not xs: bounds = [-40.0, 40.0, -40.0, 40.0]
        else:
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2; half = max(max(xs) - min(xs), (max(ys) - min(ys)) * 4 / 3, 24) / 2 + margin
            bounds = [cx - half, cx + half, cy - half * 0.75, cy + half * 0.75]
    out = {}
    for s in ('NS', 'OU'):
        w = frames[s]
        w = w[(w.x >= bounds[0] - 5) & (w.x <= bounds[1] + 5) & (w.y >= bounds[2] - 5) & (w.y <= bounds[3] + 5) | w.seg.isin(sel)].sort_values('t', kind='stable')
        si = []
        for k, i_, g, c in zip(w.seg.astype(str), w.id.astype(str), w.grp.astype(str), w.cls.astype(str)):
            if k not in sidx: sidx[k] = len(segs); segs.append(dict(k=k, s=s, id=i_, grp=g, sel=int(k in sel)))
            si.append(sidx[k])
        r = lambda a, n=2: [round(float(v), n) for v in a]
        out[s] = dict(t=r(w.t, 3), si=si, x=r(w.x), y=r(w.y), L=r(w.L.fillna(0.6), 1), W=r(w.W.fillna(0.6), 1), yaw=r(w.yaw_deg.fillna(0), 0), sp=r(w.speed),
                      c=[CI.get(c, 11) for c in w.cls.astype(str)], co=[int(bool(v)) for v in w.coasted])
    for k in sel:
        if k not in sidx: sidx[k] = len(segs); segs.append(dict(k=k, s=k[:2], id=k.split(':')[1].split('#')[0], grp='?', sel=1))
    vi = D.video_index()
    video = dict(base=f'http://127.0.0.1:{video_server.PORT}', parts={p: dict(name=m['static_name'], ov0=m['overlay_at_pts0_epoch'], ratio=m['pts_s_per_overlay_s'], dur=m['duration_s'])
                 for p, m in vi['parts'].items()}, clock=dict(a0=vi['clock']['a0_s'], slope=vi['clock']['slope_per_s'], t0=vi['clock']['t0_ref_epoch']),
                 delta=vi['delta_s'], H=vi['homography']['H'], img=[720, 480])
    # ranges without video
    novid = []; tt = t0; cur = None
    while tt <= t1:
        p, _ = TB.sensor_to_video(tt)
        if p is None and cur is None: cur = tt
        if p is not None and cur is not None: novid.append([cur, tt]); cur = None
        tt += 1.0
    if cur is not None: novid.append([cur, t1])
    bg = [c for c in D.background() if bounds[0] - 1 <= c[0] <= bounds[1] and bounds[2] - 1 <= c[1] <= bounds[3]]
    common = [c for c in D.jload('c1f')['common_region']['cells_any'] if bounds[0] - 2 <= c[0] * 2 <= bounds[1] and bounds[2] - 2 <= c[1] * 2 <= bounds[3]]
    gaps = [[a, b, 'Ouster log gap (masked for both sensors)'] for a, b in GAPS if b >= t0 and a <= t1]
    video2 = None; cov = {}
    if os.path.exists(CAMS_PATH):
        cams = json.load(open(CAMS_PATH, encoding='utf-8')); c = cams['cameras'].get('SCU4YV')
        if c:
            video2 = dict(base=f'http://127.0.0.1:{video_server.PORT}', label=c['label'], delta=c['delta_s'], unc=c['uncertainty_s'], sync_text=c['sync_text'],
                          parts={p: dict(name=m['static_name'], ov0=m['overlay_at_pts0_epoch'], ratio=m['pts_s_per_overlay_s'], dur=m['duration_s']) for p, m in c['parts'].items()})
        cov = {k: [list(map(int, v)) for v in vals] for k, vals in cams.get('coverage_cells_approx', {}).items()}
    return dict(video2=video2, coverage=cov, title=title, t0=t0, t1=t1, tStart=t0 + 0.25, segs=segs, frames=out, events=sorted(events, key=lambda e: e['t']), video=video, bounds=bounds,
                bg=bg, common=common, gaps=gaps, novideo=novid, cls=CLS, opts=opts or {})
def render(payload, height='content'):
    """Render the player. Layout: payload['opts']['layout'] = 'side' (video left, maps right; default) or 'stack' (video full width, maps below)."""
    video_server.ensure_running()
    stack = (payload.get('opts') or {}).get('layout') == 'stack'
    delta = payload['video']['delta']
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
* {{box-sizing:border-box;}}
body {{font-family:-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, sans-serif; margin:0; color:#0F172A; background:transparent; font-size:13px;}}
#wrap {{padding:1px;}}
.top {{display:flex; gap:14px; {'flex-direction:column;' if stack else ''}}}
.pane {{background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:10px 12px; display:flex; flex-direction:column; gap:6px; min-width:0;}}
.ttl {{font-size:13.5px; font-weight:600; display:flex; justify-content:space-between; gap:8px; align-items:baseline; flex-wrap:wrap;}}
.ttl .sub {{font-weight:400; color:#64748B; font-size:12px;}}
#mcol {{display:flex; gap:12px; {'flex-direction:row;' if stack else 'flex-direction:column;'}}}
#mcol .pane {{flex:1 1 0; padding:8px 10px;}}
#vbox, .vbox {{position:relative; border-radius:10px; overflow:hidden; background:#0F172A;}} #vid2 {{width:100%; height:100%; display:block; object-fit:contain;}}
.novid {{display:none; position:absolute; inset:0; align-items:center; justify-content:center; background:#F1F5F9; color:#64748B; font-size:13px; text-align:center; padding:12px;}}
.top {{flex-wrap:wrap;}} .camtools {{display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; margin:0 0 10px; font-size:12.5px;}}
.seg {{display:inline-flex; border:1px solid #CBD5E1; border-radius:10px; overflow:hidden; background:#fff;}} .seg button {{border:0; border-right:1px solid #E2E8F0; background:#fff; padding:6px 11px; font-size:12.5px; cursor:pointer; font-family:inherit; color:#0F172A;}}
.seg button:last-child {{border-right:0;}} .seg button.on {{background:#0F172A; color:#fff;}} .seg button:disabled {{color:#94A3B8; cursor:not-allowed;}}
.camhelp {{flex-basis:100%;}} .camhelp div {{margin-top:4px; color:#475569; line-height:1.45;}}
.c2note {{font-size:12px; border-radius:8px; padding:6px 9px; line-height:1.4;}} .c2note.linked {{background:#F5F3FF; color:#4C1D95;}} .c2note.indep {{background:#FEF2F2; color:#991B1B; font-weight:600;}}
#vid {{width:100%; height:100%; display:block; object-fit:contain;}} #vov {{position:absolute; left:0; top:0; pointer-events:none;}}
#novid {{display:none; position:absolute; inset:0; align-items:center; justify-content:center; background:#F1F5F9; color:#64748B; font-size:13px; text-align:center; padding:12px;}}
canvas.map {{border-radius:8px; display:block; border:1px solid #F1F5F9;}}
.st {{font-size:11.5px; padding:2px 8px; border-radius:999px; font-weight:600;}} .st.off {{background:#F1F5F9; color:#64748B;}}
.bar {{display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:12px 0 6px;}}
.btn {{border:1px solid #CBD5E1; background:#fff; border-radius:10px; padding:7px 12px; cursor:pointer; font-size:13px; color:#0F172A; display:inline-flex; gap:6px; align-items:center; font-family:inherit;}}
.btn:hover {{background:#F1F5F9;}} .btn .ic {{font-size:11px;}}
#bplay {{background:#0F172A; color:#fff; border-color:#0F172A; min-width:96px; justify-content:center; font-weight:600;}} #bplay:hover {{background:#1E293B;}}
.grp {{display:inline-flex; border:1px solid #CBD5E1; border-radius:10px; overflow:hidden;}} .grp .btn {{border:0; border-radius:0; border-right:1px solid #E2E8F0;}} .grp .btn:last-child {{border-right:0;}}
select {{border:1px solid #CBD5E1; border-radius:10px; padding:6px 8px; font-size:13px; background:#fff; font-family:inherit;}}
#slider {{flex:1; min-width:180px; accent-color:#0F172A;}}
#clock {{font-size:15px; font-variant-numeric:tabular-nums;}} .clockbox {{display:flex; flex-direction:column; line-height:1.2; min-width:120px;}} #vclock {{font-size:11px; color:#64748B;}}
.opts {{display:flex; flex-wrap:wrap; gap:6px 16px; font-size:12.5px; color:#334155; align-items:center;}}
.opts label {{display:inline-flex; gap:5px; align-items:center; cursor:pointer;}}
details {{font-size:12.5px; color:#334155;}} details summary {{cursor:pointer; color:#4338CA; font-weight:600; margin:2px 0;}}
.timing {{background:#FFFBEB; border:1px solid #FDE68A; color:#78350F; border-radius:10px; padding:7px 11px; font-size:12px; margin-top:8px;}}
.timing summary {{color:#92400E;}}
#manwarn {{display:none; color:#B45309; font-weight:600; margin-top:4px;}}
.tlbox {{background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:10px 12px; margin-top:10px;}}
.tlttl {{font-weight:600; font-size:13.5px; margin-bottom:6px;}} #tl {{display:block; cursor:pointer;}}
.lg {{display:flex; flex-wrap:wrap; gap:6px 16px; font-size:12px; color:#475569; margin-top:6px;}} .lg span {{display:inline-flex; gap:6px; align-items:center;}}
.sw {{display:inline-block; width:18px; height:10px; border-radius:2px;}}
#ro {{background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:10px 14px; margin-top:10px;}}
.rr {{padding:3px 0; font-size:13px;}} .dot {{display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px;}} .muted {{color:#64748B;}}
.foot {{font-size:11.5px; color:#64748B; margin-top:8px; line-height:1.45;}}
</style></head><body><div id="wrap">
<div class="camtools" id="camtools">
 <span class="muted">Cameras</span><span class="seg" id="camlay"><button data-v="two">Both cameras</button><button data-v="cam1">Camera 1 only (SCU3K2)</button><button data-v="cam2">Camera 2 only (SCU4YV)</button></span>
 <span class="muted" id="linklab">Camera 2 timing</span><span class="seg" id="camlink"><button data-v="linked">Linked (measured ±0.5 s)</button><button data-v="indep">Independent (not synchronised)</button></span>
 <details class="camhelp"><summary>Which camera sees what?</summary><div>Camera 1 (SCU3K2) looks across the junction toward a modern white building and into the morning sun; sensor positions are drawn on it with the approved calibration.
 Camera 2 (SCU4YV) looks along the wide road toward older brick façades; it has <b>no ground calibration</b>, so no sensor positions are drawn on it.
 An approximate coverage map (from motion correlation, not a calibrated field of view) is on the Watch the Sensors page. The cameras overlap in the centre of the junction.</div></details>
</div>
<div class="top" id="top">
 <div class="pane" id="vcol">
  <div class="ttl"><span><span class="dot" style="background:#334155"></span>Camera 1 · SCU3K2: what actually appears in the footage?</span><span class="sub" id="c1clock">MioVision · unmodified</span></div>
  <div id="vbox"><video id="vid" muted playsinline preload="auto"></video><canvas id="vov"></canvas><div id="novid">No original video exists for this time.<br>The sensor maps continue on their own clock.</div></div>
  <div class="opts"><label><input type="checkbox" id="o_video"> Show sensor positions on this camera</label>
   <span style="display:inline-flex;gap:6px;align-items:center"><span class="dot" style="background:#2563EB;margin:0"></span>Newsense (filled dot)</span>
   <span style="display:inline-flex;gap:6px;align-items:center"><span style="display:inline-block;width:11px;height:11px;border:2.5px solid #059669;border-radius:50%"></span>Ouster (ring)</span>
   <span class="muted">a dot inside a ring = both sensors report an object there</span></div>
 </div>
 <div class="pane" id="vcol2" style="display:none">
  <div class="ttl"><span><span class="dot" style="background:#B45309"></span>Camera 2 · SCU4YV: the other viewpoint</span><span class="sub" id="c2clock"></span></div>
  <div id="vbox2" class="vbox"><video id="vid2" muted playsinline preload="auto"></video><div id="novid2" class="novid">No SCU4YV video exists for this time.</div></div>
  <div id="c2bar" class="opts" style="display:none"><span class="grp"><button class="btn" id="b2back">◀ 1 frame</button><button class="btn" id="b2play"><span class="ic">▶</span> Play</button><button class="btn" id="b2fwd">1 frame ▶</button></span>
   <input id="slider2" type="range" min="0" max="1000" value="0" style="flex:1;min-width:120px"></div>
  <div id="c2note" class="c2note"></div>
 </div>
 <div id="mcol">
  <div class="pane"><div class="ttl"><span id="tA"></span><span id="sA"></span></div><canvas id="mapA" class="map"></canvas></div>
  <div class="pane" id="paneB"><div class="ttl"><span><b style="color:#059669">Ouster</b>: what did this sensor detect?</span><span id="sB"></span></div><canvas id="mapB" class="map"></canvas></div>
 </div>
</div>
<div class="bar">
 <button class="btn" id="bprev" title="Jump to the previous event">⏮ Previous event</button>
 <span class="grp"><button class="btn" id="bback" title="One video frame back (left arrow)">◀ 1 frame</button><button class="btn" id="bplay"><span class="ic">▶</span> Play</button><button class="btn" id="bfwd" title="One video frame forward (right arrow)">1 frame ▶</button></span>
 <button class="btn" id="bnext" title="Jump to the next event">Next event ⏭</button>
 <label class="muted" style="font-size:12px">Speed <select id="speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label>
 <input id="slider" type="range" min="0" max="1000" value="0" aria-label="Position in time">
 <span class="clockbox"><span id="clock"></span><span id="vclock"></span></span>
</div>
<details><summary>More display options</summary><div class="opts" style="margin:6px 0 4px">
 <label><input type="checkbox" id="o_combined"> Show both sensors on one map</label>
 <label><input type="checkbox" id="o_ghost"> Show the other sensor's track faintly</label>
 <label><input type="checkbox" id="o_trails"> Path so far</label><label><input type="checkbox" id="o_fullpath"> Whole path in this window (incl. later positions, dashed)</label><label><input type="checkbox" id="o_ids"> Tracking IDs</label><label><input type="checkbox" id="o_ctx"> Other road users (grey)</label>
 <label><input type="checkbox" id="o_vNS"> Video: Newsense dots</label><label><input type="checkbox" id="o_vOU"> Video: Ouster dots</label><label><input type="checkbox" id="o_vctx"> Video: other road users</label>
 <span class="grp"><button class="btn" id="bs10" title="Back 0.1 s (one sensor frame)">−0.1 s</button><button class="btn" id="bf10" title="Forward 0.1 s (one sensor frame)">+0.1 s</button></span>
 <span class="muted">Keyboard: space = play/pause, ← → = one frame</span></div></details>
<details class="timing"><summary>⚠ Timing uncertainty: video offset of {delta:.2f} s is unexplained · sensors agree to about ±0.7 s</summary>
 <div style="margin-top:6px">Video time is converted from sensor time with the approved clock model (Stage 3 v2) plus an empirical {delta:.2f} s look-up offset (CK-01) whose cause is unresolved.
 Use the slider only to check visually whether a different alignment looks better. It shifts the video, is never saved and is not a clock correction.</div>
 <label style="display:inline-flex;gap:8px;align-items:center;margin-top:6px">Manual visual alignment <input id="manual" type="range" min="-5" max="5" step="0.1" value="0" style="width:160px"> <span id="manv">+0.0 s</span></label>
 <div id="manwarn">Manual alignment is active: visual aid only, not a clock correction.</div></details>
<div class="tlbox"><div class="tlttl">When did each sensor report this object? <span class="muted" style="font-weight:400;font-size:12px">· click to jump · hover for details</span></div>
 <canvas id="tl"></canvas>
 <div class="lg"><span><span class="sw" style="background:#2563EB"></span>Newsense reported a position</span><span><span class="sw" style="background:#059669"></span>Ouster reported a position</span>
 <span><span class="sw" style="background:repeating-linear-gradient(135deg,#94A3B8 0 1px,#fff 1px 5px);border:1px solid #CBD5E1"></span>Interruption (no position &gt; 0.35 s)</span>
 <span><span class="sw" style="background:#D97706;height:4px"></span>Estimated position (Ouster)</span><span>◇ Classification change</span>
 <span><span class="sw" style="background:#E11D48;width:3px"></span>Current moment</span><span><span class="sw" style="background:rgba(148,163,184,.35)"></span>Sensor log gap</span><span><span class="sw" style="background:rgba(217,119,6,.15)"></span>No video</span></div></div>
<div id="ro"></div>
<div class="foot">Maps are drawn in the Ouster coordinate frame (metres); Newsense positions are converted with the validated transform. Grey cells show where pedestrians and cyclists were detected (not a surveyed map); north is not verified, so no compass is shown.
On the maps, rectangles are the current positions (reported size and heading; a dashed outline is an Ouster estimated position), the solid line is the path so far,
the optional faint dashed line is the whole path within the shown window including <b>later</b> positions, and a small dot marks where a track starts in the window. Dots on the video are ground positions projected with a 5-point calibration (0.7–8.7 px at the reference points; less accurate far away).
The date and time printed inside the video image come from the camera's own clock, which runs about 51 s behind the sensors; the player corrects for this with the approved clock model.
Overlapping times never prove that two tracks belong to the same person.</div>
</div><script>window.K305 = {json.dumps(payload, separators=(',', ':'))};</script><script>{JS}</script></body></html>"""
    st.iframe(html, height=height)

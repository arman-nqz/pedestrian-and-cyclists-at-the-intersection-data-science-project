// K305 synchronized player (UI v2). Data come only from the payload P (actual sensor rows, validated time chain, validated homography).
// Nothing is interpolated into the display: each panel shows the most recent actual sensor frame at or before the current time.
(function () {
  const P = window.K305;
  const COL = { NS: '#2563EB', OU: '#059669', CAM: '#334155', BOTH: '#7C3AED', UNC: '#D97706', NA: '#9CA3AF', INK: '#0F172A', MUTED: '#64748B', NOW: '#E11D48' };
  const NAME = { NS: 'Newsense', OU: 'Ouster' };
  const $ = (id) => document.getElementById(id);
  const fmt = (t) => { const d = new Date((t + 3600) * 1000); return d.toISOString().substr(11, 10); };
  const fmtS = (t) => fmt(t).substr(0, 8);
  const segs = P.segs;
  const LAYOUT = (P.opts && P.opts.layout) || 'side';
  const scene = P.segs.filter(g => g.sel).length > 24;
  // ---------------- per-sensor frame index
  const F = {};
  for (const s of ['NS', 'OU']) {
    const d = P.frames[s]; const n = d.t.length; const ft = [], fs = [];
    for (let i = 0; i < n; i++) if (i === 0 || d.t[i] !== d.t[i - 1]) { ft.push(d.t[i]); fs.push(i); }
    fs.push(n); F[s] = { d, ft, fs };
  }
  // per-segment trails (actual samples) + estimated-position flags + classes
  const TR = segs.map(() => ({ t: [], x: [], y: [], co: [], c: [] }));
  for (const s of ['NS', 'OU']) { const d = P.frames[s]; for (let i = 0; i < d.t.length; i++) { const k = d.si[i]; if (segs[k].sel) { TR[k].t.push(d.t[i]); TR[k].x.push(d.x[i]); TR[k].y.push(d.y[i]); TR[k].co.push(d.co[i]); TR[k].c.push(d.c[i]); } } }
  function frameAt(s, t) { const ft = F[s].ft; let lo = 0, hi = ft.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (ft[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
  // ---------------- time chain (identical to utils/timebase.py)
  const V = P.video; let manual = 0;
  function sensorToVideo(ts) {
    if (!V) return [null, null];
    const tr = ts - V.delta - manual; const ov = tr + V.clock.a0 + V.clock.slope * (tr - V.clock.t0);
    for (const p in V.parts) { const m = V.parts[p]; const pts = (ov - m.ov0) * m.ratio; if (pts >= 0 && pts <= m.dur) return [p, pts]; }
    return [null, null];
  }
  function videoToSensor(p, pts) {
    const m = V.parts[p]; const ov = pts / m.ratio + m.ov0; const tr = (ov - V.clock.a0 + V.clock.slope * V.clock.t0) / (1 + V.clock.slope); return tr + V.delta + manual;
  }
  // ---------------- camera 2 (SCU4YV): overlay = sensor time + delta (measured, see config/cameras.json); no ground calibration
  const V2 = P.video2; const vid2 = $('vid2');
  let camlay = (P.opts && P.opts.camlay) || (V2 ? 'two' : 'cam1'); let link2 = !(P.opts && P.opts.link2 === false);
  let part2 = null, ready2 = false, ov2 = null, playing2 = false;
  function overlay1(ts) { const tr = ts - V.delta - manual; return tr + V.clock.a0 + V.clock.slope * (tr - V.clock.t0); }
  function cam2Pos(ov) { if (!V2) return [null, null]; for (const p in V2.parts) { const m = V2.parts[p]; const pts = (ov - m.ov0) * m.ratio; if (pts >= 0 && pts <= m.dur) return [p, pts]; } return [null, null]; }
  function cam2Ov(p, pts) { const m = V2.parts[p]; return pts / m.ratio + m.ov0; }
  function setPart2(p, pts, play) {
    if (!V2 || p === null) { part2 = null; vid2.style.display = 'none'; $('novid2').style.display = 'flex'; return; }
    vid2.style.display = 'block'; $('novid2').style.display = 'none';
    if (part2 !== p) { part2 = p; ready2 = false; vid2.src = V2.base + '/' + V2.parts[p].name; vid2.load(); vid2.addEventListener('loadedmetadata', () => { ready2 = true; vid2.currentTime = pts; vid2.playbackRate = speed; if (play) vid2.play(); }, { once: true }); }
    else if (ready2) vid2.currentTime = pts;
  }
  function cam2Active() { return V2 && camlay !== 'cam1'; }
  function linked2() { return link2 || camlay === 'cam2'; }
  function sync2(force) {
    if (!cam2Active() || !linked2()) return;
    const [p, pts] = cam2Pos(t + V2.delta);
    if (p === null || p !== part2) { setPart2(p, pts, playing); return; }
    if (!ready2) return;
    if (force || Math.abs(vid2.currentTime - pts) > 0.2) vid2.currentTime = pts;
    if (playing && vid2.paused) { vid2.playbackRate = speed; vid2.play(); } else if (!playing && !vid2.paused) vid2.pause();
  }
  // ---------------- state
  let t = P.tStart, playing = false, speed = 1, part = null, lastWall = null, ready = false;
  const vid = $('vid');
  function setPart(p, pts, play) {
    if (!V || p === null) { part = null; vid.style.display = 'none'; $('novid').style.display = 'flex'; return; }
    vid.style.display = 'block'; $('novid').style.display = 'none';
    if (part !== p) { part = p; ready = false; vid.src = V.base + '/' + V.parts[p].name; vid.load(); vid.addEventListener('loadedmetadata', () => { ready = true; vid.currentTime = pts; vid.playbackRate = speed; if (play) vid.play(); }, { once: true }); }
    else if (ready) { vid.currentTime = pts; }
  }
  function seek(ts) { t = Math.max(P.t0, Math.min(P.t1, ts)); const [p, pts] = sensorToVideo(t); if (camlay !== 'cam2') setPart(p, pts, playing); sync2(true); draw(); }
  function play(on) {
    playing = on; $('bplay').innerHTML = on ? '<span class="ic">❚❚</span> Pause' : '<span class="ic">▶</span> Play';
    if (part && ready && camlay !== 'cam2') { if (on) { vid.playbackRate = speed; vid.play(); } else vid.pause(); }
    if (cam2Active() && linked2() && part2 && ready2) { if (on) { vid2.playbackRate = speed; vid2.play(); } else vid2.pause(); }
    lastWall = null;
  }
  function tick(wall) {
    if (playing) {
      if (camlay === 'cam2' && part2 && ready2 && !vid2.paused) { t = cam2Ov(part2, vid2.currentTime) - V2.delta; }
      else if (camlay !== 'cam2' && part && ready && !vid.paused) { t = videoToSensor(part, vid.currentTime); }
      else if ((camlay === 'cam2' && !part2) || (camlay !== 'cam2' && !part)) { if (lastWall !== null) t += (wall - lastWall) / 1000 * speed; }
      lastWall = wall;
      if (t >= P.t1) { t = P.t1; play(false); }
      const [p] = sensorToVideo(t); if (V && camlay !== 'cam2' && p !== part) { const [p2, pts2] = sensorToVideo(t); setPart(p2, pts2, true); }
      sync2(false);
      draw();
    }
    if (cam2Active() && !linked2() && part2 && ready2) { ov2 = cam2Ov(part2, vid2.currentTime); clock2(); }
    requestAnimationFrame(tick);
  }
  const hms = (ov) => new Date((ov + 3600) * 1000).toISOString().substr(11, 8);
  function clock2() {
    if (!V2) return;
    const ov = linked2() ? t + V2.delta : ov2;
    $('c2clock').innerHTML = ov === null ? '' : `camera clock <b>${hms(ov)}</b>` + (linked2() ? ` · ≈ sensor ${fmtS(t)} (±${V2.unc} s)` : ' · own timeline');
    if (!linked2() && ov2 !== null) { const a = overlay1(P.t0), b = overlay1(P.t1); $('slider2').value = (ov2 - a) / (b - a) * 1000; }
  }
  // ---------------- drawing helpers
  const opt = { ctx: true, ids: true, trails: true, ghost: true, combined: false, vNS: true, vOU: true, vctx: false, fullpath: true };
  if (P.opts) for (const k of Object.keys(opt)) if (k in P.opts) opt[k] = P.opts[k];
  function hexA(h, a) { const n = parseInt(h.slice(1), 16); return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; }
  const B = P.bounds; // xmin xmax ymin ymax
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  function fit(cv, w, h) { cv.style.width = w + 'px'; cv.style.height = h + 'px'; cv.width = Math.round(w * DPR); cv.height = Math.round(h * DPR); const c = cv.getContext('2d'); c.setTransform(DPR, 0, 0, DPR, 0, 0); return c; }
  function cssW(cv) { return cv.width / DPR; } function cssH(cv) { return cv.height / DPR; }
  function mapT(cv) {
    const W = cssW(cv), H = cssH(cv), pad = 14; const sx = (W - 2 * pad) / (B[1] - B[0]), sy = (H - 2 * pad) / (B[3] - B[2]); const s = Math.min(sx, sy);
    const ox = pad + ((W - 2 * pad) - s * (B[1] - B[0])) / 2, oy = pad + ((H - 2 * pad) - s * (B[3] - B[2])) / 2;
    return { s, f: (x, y) => [ox + (x - B[0]) * s, H - (oy + (y - B[2]) * s)] };
  }
  function footprint(ctx, T, x, y, L, W, yaw, fill, stroke, dashed) {
    const a = yaw * Math.PI / 180, c = Math.cos(a), s = Math.sin(a); L = Math.max(L || 0.6, 0.4); W = Math.max(W || 0.6, 0.4);
    const pts = [[L / 2, W / 2], [L / 2, -W / 2], [-L / 2, -W / 2], [-L / 2, W / 2]].map(([u, v]) => T.f(x + u * c - v * s, y + u * s + v * c));
    ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath();
    ctx.fillStyle = fill; ctx.fill(); ctx.setLineDash(dashed ? [4, 3] : []); ctx.strokeStyle = stroke; ctx.lineWidth = 1.6; ctx.stroke(); ctx.setLineDash([]);
  }
  function drawBase(ctx, T, cv) {
    const W = cssW(cv), H = cssH(cv);
    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);
    for (const [cx, cy] of P.common) { const [a, b] = T.f(cx * 2, cy * 2 + 2); ctx.fillStyle = 'rgba(124,58,237,0.045)'; ctx.fillRect(a, b, 2 * T.s, 2 * T.s); }
    for (const [cx, cy, n] of P.bg) { const [a, b] = T.f(cx, cy + 1); ctx.fillStyle = `rgba(100,116,139,${Math.min(0.30, 0.04 + Math.log10(n) * 0.07)})`; ctx.fillRect(a, b, T.s, T.s); }
    const [a0, b0] = [12, H - 12]; ctx.strokeStyle = COL.INK; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(a0, b0); ctx.lineTo(a0 + 10 * T.s, b0); ctx.stroke();
    ctx.fillStyle = COL.MUTED; ctx.font = '11px -apple-system, system-ui'; ctx.fillText('10 m', a0, b0 - 5);
  }
  function drawSensor(ctx, T, s, ghostOther) {
    const fi = frameAt(s, t); const d = F[s].d; const age = fi >= 0 ? t - F[s].ft[fi] : null;
    segs.forEach((g, k) => {
      if (!g.sel || (g.s !== s && !ghostOther)) return; const tr = TR[k]; if (!tr.t.length) return;
      const col = g.s === s ? COL[g.s] : hexA(COL[g.s], 0.45);
      if (opt.fullpath) { ctx.lineWidth = g.s === s ? 1.2 : 1; ctx.strokeStyle = hexA(COL[g.s], 0.20); ctx.setLineDash([3, 3]); ctx.beginPath(); tr.t.forEach((tt, i) => { const [a, b] = T.f(tr.x[i], tr.y[i]); i ? ctx.lineTo(a, b) : ctx.moveTo(a, b); }); ctx.stroke(); ctx.setLineDash([]); }
      if (opt.trails) { ctx.strokeStyle = col; ctx.lineWidth = g.s === s ? 2.6 : 1.6; ctx.beginPath(); let st = false; for (let i = 0; i < tr.t.length && tr.t[i] <= t; i++) { const [a, b] = T.f(tr.x[i], tr.y[i]); st ? ctx.lineTo(a, b) : ctx.moveTo(a, b); st = true; } ctx.stroke(); }
      if (opt.fullpath || tr.t[0] <= t) { const [sa, sb] = T.f(tr.x[0], tr.y[0]); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(sa, sb, 3, 0, 7); ctx.fill(); }
    });
    if (fi < 0 || age > 0.5) return { n: 0, age, ids: [] };
    let n = 0; const ids = [];
    for (let i = F[s].fs[fi]; i < F[s].fs[fi + 1]; i++) {
      const g = segs[d.si[i]]; const sel = g.sel;
      if (!sel && !opt.ctx) continue;
      const co = s === 'OU' && d.co[i];
      if (sel) { footprint(ctx, T, d.x[i], d.y[i], d.L[i], d.W[i], d.yaw[i], hexA(COL[s], 0.45), COL[s], co); n++; ids.push(g.id);
        if (opt.ids) { const [a, b] = T.f(d.x[i], d.y[i]); const txt = `ID ${g.id} · ${P.cls[d.c[i]]}${co ? ' · estimated' : ''}`; ctx.font = '600 12px -apple-system, system-ui'; const w = ctx.measureText(txt).width;
          ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.fillRect(a + 7, b - 22, w + 8, 17); ctx.fillStyle = COL.INK; ctx.fillText(txt, a + 11, b - 9); } }
      else footprint(ctx, T, d.x[i], d.y[i], d.L[i], d.W[i], d.yaw[i], 'rgba(148,163,184,0.22)', 'rgba(100,116,139,0.55)', co);
    }
    return { n, age, ids };
  }
  function status(s, r) {
    if (r.age === null || r.age > 0.5) return `<span class="st off">no report at this moment</span>`;
    if (!r.n) return `<span class="st off">${scene ? 'no highlighted object' : 'selected object not reported'}</span>`;
    return `<span class="st" style="background:${hexA(COL[s], 0.12)};color:${COL[s]}">reporting · ${r.ids.length > 3 ? r.ids.length + ' highlighted objects' : 'ID ' + r.ids.join(', ')}</span>`;
  }
  function drawMaps() {
    const combined = opt.combined;
    $('paneB').style.display = combined ? 'none' : 'flex';
    const panes = combined ? [['mapA', ['NS', 'OU']]] : [['mapA', ['NS']], ['mapB', ['OU']]];
    for (const [id, ss] of panes) {
      const cv = $(id), ctx = cv.getContext('2d'), T = mapT(cv); drawBase(ctx, T, cv);
      const res = ss.map(s => [s, drawSensor(ctx, T, s, !combined && opt.ghost)]);
      $(id === 'mapA' ? 'sA' : 'sB').innerHTML = res.map(([s, r]) => (ss.length > 1 ? `<b style="color:${COL[s]};font-size:11.5px">${NAME[s]}</b> ` : '') + status(s, r)).join(' ');
    }
    $('tA').innerHTML = combined ? '<b style="color:#7C3AED">Newsense and Ouster on one map</b>' : '<b style="color:#2563EB">Newsense</b>: what did this sensor detect?';
  }
  function proj(x, y) { const H = V.H; const w = H[2][0] * x + H[2][1] * y + H[2][2]; return [(H[0][0] * x + H[0][1] * y + H[0][2]) / w, (H[1][0] * x + H[1][1] * y + H[1][2]) / w]; }
  function drawVideoOverlay() {
    const cv = $('vov'), ctx = cv.getContext('2d'); ctx.clearRect(0, 0, cssW(cv), cssH(cv));
    if (!V || !part) return; const sx = cssW(cv) / V.img[0], sy = cssH(cv) / V.img[1];
    const inImg = (u, v) => u >= 0 && u <= V.img[0] && v >= 0 && v <= V.img[1];
    for (const s of ['NS', 'OU']) {
      if ((s === 'NS' && !opt.vNS) || (s === 'OU' && !opt.vOU)) continue;
      segs.forEach((g, k) => { if (!g.sel || g.s !== s || !opt.trails) return; const tr = TR[k]; ctx.strokeStyle = hexA(COL[s], 0.8); ctx.lineWidth = 2; ctx.beginPath(); let st = false;
        for (let i = 0; i < tr.t.length && tr.t[i] <= t; i++) { if (tr.t[i] < t - 6) continue; const [u, v] = proj(tr.x[i], tr.y[i]); if (!inImg(u, v)) { st = false; continue; } st ? ctx.lineTo(u * sx, v * sy) : ctx.moveTo(u * sx, v * sy); st = true; } ctx.stroke(); });
      const fi = frameAt(s, t); if (fi < 0 || t - F[s].ft[fi] > 0.5) continue; const d = F[s].d;
      for (let i = F[s].fs[fi]; i < F[s].fs[fi + 1]; i++) {
        const g = segs[d.si[i]]; if (!g.sel && !opt.vctx) continue; const [u, v] = proj(d.x[i], d.y[i]); if (!inImg(u, v)) continue;
        const X = u * sx, Y = v * sy;
        if (!g.sel) { ctx.beginPath(); ctx.arc(X, Y, 3, 0, 7); ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.fill(); ctx.strokeStyle = hexA(COL[s], 0.9); ctx.lineWidth = 1.5; ctx.stroke(); }
        else if (s === 'NS') { ctx.beginPath(); ctx.arc(X, Y, 5.5, 0, 7); ctx.fillStyle = hexA(COL.NS, 0.95); ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke(); }
        else { ctx.beginPath(); ctx.arc(X, Y, 10, 0, 7); ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 5; ctx.stroke(); ctx.strokeStyle = COL.OU; ctx.lineWidth = 3; ctx.stroke(); }
        if (g.sel && opt.ids) { ctx.font = '600 12px -apple-system, system-ui'; const txt = `${NAME[s]} ${g.id}`; const w = ctx.measureText(txt).width; const ly = s === 'NS' ? Y - 21 : Y + 6; ctx.fillStyle = hexA(COL[s], 0.92); ctx.fillRect(X + 11, ly, w + 10, 17); ctx.fillStyle = '#fff'; ctx.fillText(txt, X + 16, ly + 13); }
      }
    }
  }
  // ---------------- timeline: one row per sensor (sub-lanes only where tracks of one sensor overlap in time)
  const TL = $('tl'); let hover = null; const LBL = 92, RPAD = 16, TOP = 24, BOT = 22;
  const sel = segs.map((g, k) => [g, k]).filter(([g, k]) => g.sel && TR[k].t.length);
  const lanes = { NS: [], OU: [] }; const laneOf = {};
  if (!scene) for (const s of ['NS', 'OU']) {
    const list = sel.filter(([g]) => g.s === s).sort((a, b) => TR[a[1]].t[0] - TR[b[1]].t[0]);
    for (const [g, k] of list) { const a = TR[k].t[0], b = TR[k].t[TR[k].t.length - 1]; let li = lanes[s].findIndex(e => e < a - 0.2); if (li < 0) { lanes[s].push(b); li = lanes[s].length - 1; } else lanes[s][li] = b; laneOf[k] = li; }
  }
  const LANE = 22; const rowH = s => scene ? 40 : Math.max(1, lanes[s].length) * LANE + 8;
  const rowY = { NS: TOP, OU: TOP + rowH('NS') + 10 };
  const TLH = TOP + rowH('NS') + 10 + rowH('OU') + BOT;
  function tlX(tt) { return LBL + (tt - P.t0) / (P.t1 - P.t0) * (cssW(TL) - LBL - RPAD); }
  function hatch(ctx, x, y, w, h, col) { ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); ctx.strokeStyle = col; ctx.lineWidth = 1; for (let i = -h; i < w; i += 5) { ctx.beginPath(); ctx.moveTo(x + i, y + h); ctx.lineTo(x + i + h, y); ctx.stroke(); } ctx.restore(); }
  const hits = [];
  function drawTimeline() {
    const ctx = TL.getContext('2d'); const W = cssW(TL), H = cssH(TL); ctx.clearRect(0, 0, W, H); hits.length = 0;
    ctx.font = '12px -apple-system, system-ui';
    for (const [a, b] of P.novideo) { ctx.fillStyle = 'rgba(217,119,6,0.10)'; ctx.fillRect(tlX(a), TOP - 6, Math.max(2, tlX(b) - tlX(a)), H - TOP - BOT + 6); }
    for (const [a, b] of P.gaps) { ctx.fillStyle = 'rgba(148,163,184,0.28)'; ctx.fillRect(tlX(a), TOP - 6, Math.max(2, tlX(b) - tlX(a)), H - TOP - BOT + 6); hits.push({ x0: tlX(a) - 2, x1: tlX(b) + 2, y0: 0, y1: H, txt: `Sensor log gap ${fmtS(a)}–${fmtS(b)} (excluded for both sensors)` }); }
    for (const s of ['NS', 'OU']) {
      const y = rowY[s], h = rowH(s);
      ctx.fillStyle = '#F8FAFC'; ctx.fillRect(LBL, y - 4, W - LBL - RPAD, h);
      ctx.fillStyle = COL[s]; ctx.font = '600 13px -apple-system, system-ui'; ctx.fillText(NAME[s], 8, y + 13);
      ctx.font = '12px -apple-system, system-ui';
      if (scene) {
        const Wd = Math.max(1, Math.floor(W - LBL - RPAD)); const cnt = new Array(Wd).fill(0); let mx = 1; let nseg = 0;
        sel.forEach(([g, k]) => { if (g.s !== s) return; nseg++; const tr = TR[k]; const a = Math.max(0, Math.floor(tlX(tr.t[0]) - LBL)), b = Math.min(Wd - 1, Math.ceil(tlX(tr.t[tr.t.length - 1]) - LBL)); for (let i = a; i <= b; i++) { cnt[i]++; mx = Math.max(mx, cnt[i]); } });
        for (let i = 0; i < Wd; i++) if (cnt[i]) { ctx.fillStyle = hexA(COL[s], 0.15 + 0.85 * cnt[i] / mx); ctx.fillRect(LBL + i, y, 1, 22); }
        ctx.fillStyle = COL.MUTED; ctx.font = '11px -apple-system, system-ui'; ctx.fillText(`${nseg} highlighted tracks · darker = more at the same time (max ${mx})`, LBL + 4, y + 34); continue;
      }
      if (!lanes[s].length) { ctx.fillStyle = COL.MUTED; ctx.fillText('No track of this sensor in this investigation', LBL + 8, y + 12); continue; }
      sel.forEach(([g, k]) => {
        if (g.s !== s) return; const tr = TR[k]; const ly = y + laneOf[k] * LANE; const bh = LANE - 6;
        const a0 = tr.t[0], a1 = tr.t[tr.t.length - 1];
        hatch(ctx, tlX(a0), ly, Math.max(1, tlX(a1) - tlX(a0)), bh, hexA(COL[s], 0.45));
        let a = tr.t[0];
        for (let i = 1; i <= tr.t.length; i++) {
          if (i === tr.t.length || tr.t[i] - tr.t[i - 1] > 0.35) {
            const x0 = tlX(a), x1 = Math.max(tlX(a) + 2, tlX(tr.t[i - 1])); ctx.fillStyle = COL[s]; ctx.fillRect(x0, ly, x1 - x0, bh);
            if (i < tr.t.length) { hits.push({ x0: x1, x1: tlX(tr.t[i]), y0: ly, y1: ly + bh, txt: `${NAME[s]} ID ${g.id}: interruption, no position for ${(tr.t[i] - tr.t[i - 1]).toFixed(1)} s (${fmtS(tr.t[i - 1])}–${fmtS(tr.t[i])})` }); a = tr.t[i]; }
          }
        }
        for (let i = 0; i < tr.t.length; i++) if (tr.co[i]) { ctx.fillStyle = COL.UNC; ctx.fillRect(tlX(tr.t[i]), ly + bh - 4, Math.max(1.5, tlX(tr.t[i] + 0.1) - tlX(tr.t[i])), 4); }
        for (let i = 1; i < tr.c.length; i++) if (tr.c[i] !== tr.c[i - 1]) { const x = tlX(tr.t[i]), yy = ly + bh / 2; ctx.fillStyle = '#fff'; ctx.strokeStyle = COL.INK; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.moveTo(x, yy - 6); ctx.lineTo(x + 5, yy); ctx.lineTo(x, yy + 6); ctx.lineTo(x - 5, yy); ctx.closePath(); ctx.fill(); ctx.stroke();
          hits.push({ x0: x - 6, x1: x + 6, y0: ly, y1: ly + bh, txt: `${NAME[s]} ID ${g.id}: classification changed ${P.cls[tr.c[i - 1]]} → ${P.cls[tr.c[i]]} at ${fmtS(tr.t[i])}` }); }
        const lab = `ID ${g.id}`; ctx.font = '600 11px -apple-system, system-ui'; const wl = ctx.measureText(lab).width;
        if (tlX(a1) - tlX(a0) > wl + 14) { ctx.fillStyle = '#fff'; ctx.fillText(lab, tlX(a0) + 6, ly + bh - 5); }
        else { ctx.fillStyle = COL[s]; ctx.fillText(lab, Math.min(W - RPAD - wl, tlX(a1) + 4), ly + bh - 5); }
        ctx.font = '12px -apple-system, system-ui';
        hits.push({ x0: tlX(a0), x1: tlX(a1), y0: ly, y1: ly + bh, txt: `${NAME[s]} tracking ID ${g.id}: ${fmtS(a0)}–${fmtS(a1)} (${(a1 - a0).toFixed(1)} s)` });
      });
    }
    if (scene) P.events.forEach(e => { const x = tlX(e.t), y = rowY[e.s === 'OU' ? 'OU' : 'NS'] - 6; ctx.fillStyle = COL.NOW; ctx.beginPath(); ctx.moveTo(x, y + 6); ctx.lineTo(x - 5, y - 3); ctx.lineTo(x + 5, y - 3); ctx.fill(); hits.push({ x0: x - 6, x1: x + 6, y0: y - 6, y1: y + 8, txt: e.label }); });
    ctx.fillStyle = COL.MUTED; ctx.font = '11px -apple-system, system-ui'; const n = Math.max(3, Math.min(8, Math.floor((W - LBL) / 110)));
    for (let i = 0; i <= n; i++) { const tt = P.t0 + (P.t1 - P.t0) * i / n; const x = tlX(tt); ctx.fillStyle = '#E2E8F0'; ctx.fillRect(x, TOP - 6, 1, H - TOP - BOT + 6); ctx.fillStyle = COL.MUTED; ctx.fillText(fmtS(tt), Math.min(W - 50, Math.max(LBL, x - 22)), H - 5); }
    const xn = tlX(t); ctx.strokeStyle = COL.NOW; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(xn, 15); ctx.lineTo(xn, H - BOT); ctx.stroke();
    ctx.font = '600 11px -apple-system, system-ui'; const nl = fmtS(t); const nw = ctx.measureText(nl).width; const nx = Math.min(W - nw - 10, Math.max(0, xn - nw / 2 - 5));
    ctx.fillStyle = COL.NOW; ctx.fillRect(nx, 0, nw + 10, 15); ctx.fillStyle = '#fff'; ctx.fillText(nl, nx + 5, 11);
    if (hover) { ctx.font = '12px -apple-system, system-ui'; const w = ctx.measureText(hover.txt).width + 14; const x = Math.min(W - w - 2, Math.max(2, hover.x - w / 2)); const y = Math.max(16, hover.y - 28); ctx.fillStyle = 'rgba(15,23,42,0.92)'; ctx.fillRect(x, y, w, 21); ctx.fillStyle = '#fff'; ctx.fillText(hover.txt, x + 7, y + 15); }
  }
  TL.addEventListener('click', ev => { const r = TL.getBoundingClientRect(); const x = ev.clientX - r.left; if (x > LBL) seek(P.t0 + (x - LBL) / (cssW(TL) - LBL - RPAD) * (P.t1 - P.t0)); });
  TL.addEventListener('mousemove', ev => { const r = TL.getBoundingClientRect(); const x = ev.clientX - r.left, y = ev.clientY - r.top; hover = null;
    for (let i = hits.length - 1; i >= 0; i--) { const h = hits[i]; if (x >= h.x0 && x <= h.x1 && y >= h.y0 - 2 && y <= h.y1 + 2) { hover = { txt: h.txt, x, y: h.y0 }; break; } } drawTimeline(); });
  TL.addEventListener('mouseleave', () => { hover = null; drawTimeline(); });
  // ---------------- readout: what is reported at this moment, in words
  function readout() {
    const cur = {}; const parts = [];
    for (const s of ['NS', 'OU']) { const fi = frameAt(s, t); const items = [];
      if (fi >= 0 && t - F[s].ft[fi] <= 0.5) { const d = F[s].d;
        for (let i = F[s].fs[fi]; i < F[s].fs[fi + 1]; i++) { const g = segs[d.si[i]]; if (!g.sel) continue; cur[s] = cur[s] || []; cur[s].push([d.x[i], d.y[i]]);
          items.push(`ID <b>${g.id}</b>, ${P.cls[d.c[i]]}, ${d.sp[i].toFixed(1)} m/s` + (s === 'OU' ? (d.co[i] ? ', <span style="color:#B45309;font-weight:600">estimated position</span>' : ', measured position') : '')); } }
      let body;
      if (!items.length) body = `<span class="muted">${scene ? 'reports no highlighted object at this moment' : 'does not report the selected object at this moment'}</span>`;
      else if (items.length > 4) { const cnt = {}; const d = F[s].d; for (let i = F[s].fs[fi]; i < F[s].fs[fi + 1]; i++) if (segs[d.si[i]].sel) cnt[P.cls[d.c[i]]] = (cnt[P.cls[d.c[i]]] || 0) + 1;
        body = `reports <b>${items.length}</b> highlighted objects (` + Object.entries(cnt).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${v} ${k}`).join(', ') + ')'; }
      else body = items.join(' · ');
      parts.push(`<div class="rr"><span class="dot" style="background:${COL[s]}"></span><b style="color:${COL[s]}">${NAME[s]}</b>&nbsp; ${body}</div>`); }
    if (scene) {
      const all = {}; for (const s of ['NS', 'OU']) { const fi = frameAt(s, t); all[s] = []; if (fi >= 0 && t - F[s].ft[fi] <= 0.5) { const d = F[s].d; for (let i = F[s].fs[fi]; i < F[s].fs[fi + 1]; i++) all[s].push([d.x[i], d.y[i]]); } }
      const near = (s) => { const o = s === 'NS' ? 'OU' : 'NS'; return (cur[s] || []).filter(a => all[o].some(b => Math.hypot(a[0] - b[0], a[1] - b[1]) <= 1.0)).length; };
      if ((cur.NS || []).length || (cur.OU || []).length) parts.push(`<div class="rr muted">Agreement at this moment: <b style="color:#0F172A">${near('NS')} of ${(cur.NS || []).length}</b> highlighted Newsense and <b style="color:#0F172A">${near('OU')} of ${(cur.OU || []).length}</b> highlighted Ouster objects have an object of the other sensor (any type, within the map area) within 1 m. This is agreement between sensors, not proof that they saw the same people.</div>`);
    }
    if (!scene && (cur.NS || cur.OU)) {
      const pos = (cur.NS || []).concat(cur.OU || []); const cov2 = new Set(((P.coverage || {}).SCU4YV || []).map(c => c[0] + ',' + c[1]));
      const in1 = pos.some(([x, y]) => { const [u, v] = proj(x, y); return u >= 0 && u <= 720 && v >= 0 && v <= 480; });
      const in2 = pos.some(([x, y]) => cov2.has((Math.floor(x / 2) * 2 + 1) + ',' + (Math.floor(y / 2) * 2 + 1)));
      parts.push(`<div class="rr muted">Camera view: <b style="color:#0F172A">SCU3K2</b> ${in1 ? 'position falls inside the image (calibrated projection)' : 'position falls <b>outside</b> the image'} · ` +
        (V2 ? `<b style="color:#0F172A">SCU4YV</b> ${in2 ? 'inside its approximate coverage' : 'outside its approximate coverage'} (no calibration; approximate)` : '') + `. Whether the person is hidden behind something must be judged by eye; the two views are not matched by appearance.</div>`);
    }
    let dist = '';
    if (cur.NS && cur.OU && !scene && cur.NS.length + cur.OU.length <= 4) { let m = 1e9; for (const a of cur.NS) for (const b of cur.OU) m = Math.min(m, Math.hypot(a[0] - b[0], a[1] - b[1])); dist = `<div class="rr muted">Distance between the two reported positions: <b style="color:#0F172A">${m.toFixed(2)} m</b>. A small distance supports, but does not prove, that both sensors saw the same person.</div>`; }
    $('ro').innerHTML = `<div class="tlttl">At ${fmtS(t)}</div>` + parts.join('') + dist;
  }
  function draw() {
    const [p, pts] = sensorToVideo(t);
    $('clock').innerHTML = `<b>${fmt(t)}</b>`;
    $('vclock').innerHTML = p ? `video part .${p} · ${pts.toFixed(2)} s` : '<span style="color:#B45309">no original video for this time</span>';
    $('slider').value = (t - P.t0) / (P.t1 - P.t0) * 1000;
    if (V) $('c1clock').innerHTML = p ? `camera clock <b>${hms(overlay1(t))}</b> · sensor ${fmtS(t)}` : 'no video for this time';
    clock2();
    drawMaps(); drawVideoOverlay(); drawTimeline(); readout();
  }
  // ---------------- controls
  $('bplay').onclick = () => play(!playing);
  $('bback').onclick = () => { play(false); if (camlay === 'cam2' && part2 && ready2) { vid2.currentTime = Math.max(0, vid2.currentTime - 1 / 29.97); t = cam2Ov(part2, vid2.currentTime) - V2.delta; draw(); return; } if (part && ready) { vid.currentTime = Math.max(0, vid.currentTime - 1 / 29.97); t = videoToSensor(part, vid.currentTime); sync2(true); draw(); } else seek(t - 0.1); };
  $('bfwd').onclick = () => { play(false); if (camlay === 'cam2' && part2 && ready2) { vid2.currentTime = vid2.currentTime + 1 / 29.97; t = cam2Ov(part2, vid2.currentTime) - V2.delta; draw(); return; } if (part && ready) { vid.currentTime = vid.currentTime + 1 / 29.97; t = videoToSensor(part, vid.currentTime); sync2(true); draw(); } else seek(t + 0.1); };
  $('bs10').onclick = () => { play(false); seek(t - 0.1); }; $('bf10').onclick = () => { play(false); seek(t + 0.1); };
  $('bprev').onclick = () => { const e = P.events.filter(e => e.t < t - 0.05).pop(); if (e) { play(false); seek(e.t); } };
  $('bnext').onclick = () => { const e = P.events.find(e => e.t > t + 0.05); if (e) { play(false); seek(e.t); } };
  $('speed').onchange = ev => { speed = parseFloat(ev.target.value); if (part && ready) vid.playbackRate = speed; if (part2 && ready2) vid2.playbackRate = speed; };
  $('slider').oninput = ev => seek(P.t0 + ev.target.value / 1000 * (P.t1 - P.t0));
  $('manual').oninput = ev => { manual = parseFloat(ev.target.value); $('manv').textContent = (manual >= 0 ? '+' : '') + manual.toFixed(1) + ' s'; $('manwarn').style.display = manual === 0 ? 'none' : 'block'; const keep = t; seek(keep); };
  for (const k of Object.keys(opt)) { const el = $('o_' + k); if (el) { el.checked = opt[k]; el.onchange = ev => { opt[k] = ev.target.checked; $('o_video').checked = opt.vNS && opt.vOU; if (k === 'combined') resize(); else draw(); }; } }
  $('o_video').checked = opt.vNS && opt.vOU;
  $('o_video').onchange = ev => { opt.vNS = opt.vOU = ev.target.checked; $('o_vNS').checked = $('o_vOU').checked = ev.target.checked; draw(); };
  document.addEventListener('keydown', ev => { if (ev.target.tagName === 'INPUT' || ev.target.tagName === 'SELECT') return; if (ev.code === 'Space') { ev.preventDefault(); play(!playing); } else if (ev.code === 'ArrowRight') $('bfwd').click(); else if (ev.code === 'ArrowLeft') $('bback').click(); });
  function setSeg(id, v) { for (const b of $(id).querySelectorAll('button')) b.classList.toggle('on', b.dataset.v === v); }
  function applyCams() {
    if (!V2) { $('camtools').style.display = 'none'; camlay = 'cam1'; }
    setSeg('camlay', camlay); setSeg('camlink', linked2() ? 'linked' : 'indep');
    for (const b of $('camlink').querySelectorAll('button')) b.disabled = camlay !== 'two';
    $('vcol').style.display = camlay === 'cam2' ? 'none' : 'flex'; $('vcol2').style.display = cam2Active() ? 'flex' : 'none';
    if (camlay === 'cam2') { vid.pause(); } if (!cam2Active()) vid2.pause();
    $('c2bar').style.display = cam2Active() && !linked2() ? 'flex' : 'none';
    const n = $('c2note');
    if (V2 && linked2()) { n.className = 'c2note linked'; n.innerHTML = `Linked to the sensor time with a <b>measured</b> offset: camera clock = sensor time ${V2.delta.toFixed(1)} s (uncertainty ±${V2.unc} s; measured on 14 Nov 2026 by motion correlation with Ouster; not part of the V2 results). No sensor positions are drawn on this camera (no ground calibration).`; }
    else if (V2) { n.className = 'c2note indep'; n.innerHTML = 'NOT SYNCHRONISED: own timeline. This camera plays independently; it does not show the same instant as camera 1 or the sensor maps. Equal clock readings do not mean the same moment. Do not use these frames to check a detection at a specific time.'; }
    resize();
    if (cam2Active()) { if (linked2()) sync2(true); else { if (ov2 === null) ov2 = overlay1(t); const [p, pts] = cam2Pos(ov2); setPart2(p, pts, false); } }
    if (camlay !== 'cam2') { const [p, pts] = sensorToVideo(t); setPart(p, pts, playing); }
    draw();
  }
  for (const b of $('camlay').querySelectorAll('button')) b.onclick = () => { camlay = b.dataset.v; applyCams(); };
  for (const b of $('camlink').querySelectorAll('button')) b.onclick = () => { if (b.disabled) return; link2 = b.dataset.v === 'linked'; playing2 = false; vid2.pause(); $('b2play').innerHTML = '<span class="ic">▶</span> Play'; if (!link2) ov2 = overlay1(t); applyCams(); };
  $('b2play').onclick = () => { if (!part2 || !ready2) return; playing2 = !playing2; if (playing2) { vid2.playbackRate = speed; vid2.play(); } else vid2.pause(); $('b2play').innerHTML = playing2 ? '<span class="ic">❚❚</span> Pause' : '<span class="ic">▶</span> Play'; };
  $('b2fwd').onclick = () => { if (part2 && ready2) { vid2.pause(); playing2 = false; $('b2play').innerHTML = '<span class="ic">▶</span> Play'; vid2.currentTime += 1 / 29.97; } };
  $('b2back').onclick = () => { if (part2 && ready2) { vid2.pause(); playing2 = false; $('b2play').innerHTML = '<span class="ic">▶</span> Play'; vid2.currentTime = Math.max(0, vid2.currentTime - 1 / 29.97); } };
  $('slider2').oninput = ev => { const a = overlay1(P.t0), b = overlay1(P.t1); ov2 = a + ev.target.value / 1000 * (b - a); const [p, pts] = cam2Pos(ov2); setPart2(p, pts, playing2); clock2(); };
  vid2.addEventListener('seeked', () => { if (!linked2() && part2) { ov2 = cam2Ov(part2, vid2.currentTime); clock2(); } else if (camlay === 'cam2' && !playing && part2) { t = cam2Ov(part2, vid2.currentTime) - V2.delta; draw(); } });
  vid.addEventListener('seeked', () => { if (!playing && part && camlay !== 'cam2') { t = videoToSensor(part, vid.currentTime); sync2(false); draw(); } });
  function resize() {
    const w = $('wrap').clientWidth; let vw, vh, mw, mh;
    if (camlay === 'two') {
      vw = Math.floor((w - 20) / 2); vh = Math.round((vw - 26) * 480 / 720); mw = opt.combined ? w - 32 : Math.floor((w - 18) / 2) - 24; mh = Math.round(Math.min(mw * 0.6, 360));
      for (const id of ['vcol', 'vcol2']) $(id).style.width = vw + 'px';
      $('vbox').style.height = vh + 'px'; $('vbox2').style.height = vh + 'px'; fit($('vov'), vw - 26, vh);
      $('mcol').style.width = (w - 4) + 'px'; $('mcol').style.flexDirection = 'row';
      for (const id of ['mapA', 'mapB']) fit($(id), mw, mh);
      fit(TL, w - 28, TLH); draw(); return;
    }
    $('mcol').style.flexDirection = LAYOUT === 'stack' ? 'row' : 'column';
    if (LAYOUT === 'stack') { vw = w - 2; vh = Math.round((vw - 26) * 480 / 720); mw = opt.combined ? w - 30 : Math.floor((w - 12) / 2) - 24; mh = Math.round(Math.min(mw * 0.62, 400)); }
    else { vw = Math.floor((w - 14) * 0.62); vh = Math.round((vw - 26) * 480 / 720); mw = w - 14 - vw - 24; mh = opt.combined ? vh + 30 : Math.floor((vh - 30) / 2); }
    $('vcol').style.width = vw + 'px'; $('vcol2').style.width = vw + 'px'; $('vbox').style.height = vh + 'px'; $('vbox2').style.height = vh + 'px'; fit($('vov'), vw - 26, vh);
    $('mcol').style.width = (LAYOUT === 'stack' ? w : mw + 24) + 'px';
    for (const id of ['mapA', 'mapB']) fit($(id), mw, mh);
    fit(TL, w - 28, TLH); draw();
  }
  window.addEventListener('resize', resize);
  if (scene) document.querySelector('.tlttl').firstChild.textContent = 'When did each sensor report the highlighted objects? ';
  applyCams(); requestAnimationFrame(tick);
})();

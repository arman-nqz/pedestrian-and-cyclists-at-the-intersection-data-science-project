"""
=============================================================================
TRAFFIC NEAR-MISS ANALYSIS PIPELINE — Vectorised Edition
Intersection K305 | Dataset: 2026-10-14
=============================================================================

Academic References:
  - TTC: Hayward (1972); Minderhoud & Bovy (2001)
  - PET: Allen et al. (1978); Laureshyn et al. (2010)
  - Safety Triangle: Heinrich (1931)

Design: Streaming per 5-min chunk; all TTC computed with NumPy broadcasting.
=============================================================================
"""

import argparse
import json, os, glob, sys, math, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    missing = exc.name or "a required package"
    raise SystemExit(
        f"Missing dependency: {missing}. Create an environment and install requirements:\n"
        "  python -m venv .venv\n"
        "  .venv/bin/python -m pip install -r requirements.txt\n"
        "  .venv/bin/python near_miss_analysis.py"
    ) from exc

# =============================================================================
# GLOBAL CONFIGURATION — easily adjustable for future datasets
# =============================================================================
CONFIG = {
    "TTC_THRESHOLD_SEC":        1.5,
    "PET_THRESHOLD_SEC":        1.5,
    "SMOOTHING_WINDOW":         5,
    "MIN_TRACK_LENGTH":         5,
    "MAX_VELOCITY_MS":          50.0,
    "INTERACTION_RADIUS_M":     25.0,
    "TTC_LOOKAHEAD_SEC":        5.0,
    "TTC_MIN_CLOSING_SPEED":    0.1,
    "PET_CONFLICT_ZONE_SIZE_M": 3.0,
    "PET_GRID_CELL_M":          2.0,
    "PET_MAX_GAP_SEC":          10.0,
    "PET_VISIT_GAP_SEC":        0.25,
    "EVENT_GAP_SEC":            0.25,
    "INCLUDE_NON_VRU":          False,
    "MOTORIZED_CLASSES":  {"Car","Truck","Bus","Van","Motorcycle"},
    "VULNERABLE_CLASSES": {"Pedestrian","Cyclist"},
    "DATA_DIR":   "/home/arman/Projects/University data science project cameras/database/k305_object_list_2026-10-14_aggregation_5min",
    "OUTPUT_DIR": "output",
}

# Numeric category codes for vectorised logic
CAT_MOTOR = 1; CAT_VUL = 2; CAT_OTHER = 0
DEFAULTS_RADIUS = {
    "Car":1.5,"Truck":2.5,"Bus":3.5,"Van":1.8,
    "Motorcycle":0.8,"Pedestrian":0.4,"Cyclist":0.7,
}

# =============================================================================
# MODULE 1: PARSING
# =============================================================================

def parse_chunk(chunk:Dict) -> pd.DataFrame:
    rows = []
    for frame in chunk.get("frames",[]):
        ts  = frame["frame_timestamp"]["seconds"] + frame["frame_timestamp"]["nanosec"]*1e-9
        tsl = frame.get("timestamp_local","")
        for obj in frame.get("objects",[]):
            bb  = obj.get("bounding_box",{})
            pos = bb.get("position",{})
            vel = obj.get("velocity",{})
            sc  = bb.get("scale",{})
            L   = sc.get("x",np.nan); W = sc.get("y",np.nan)
            r   = (0.5*math.sqrt(L*L+W*W) if not (math.isnan(L) or math.isnan(W))
                   else DEFAULTS_RADIUS.get(obj.get("class_name","Car"),1.5))
            cn  = obj.get("class_name","Unknown")
            if cn in CONFIG["MOTORIZED_CLASSES"]:  cat = CAT_MOTOR
            elif cn in CONFIG["VULNERABLE_CLASSES"]: cat = CAT_VUL
            else: cat = CAT_OTHER
            rows.append((ts, tsl, int(obj["track_id"]), cn, cat,
                         pos.get("x",np.nan), pos.get("y",np.nan),
                         vel.get("x",np.nan), vel.get("y",np.nan), r))
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows, columns=["ts","tsl","tid","cls","cat","x","y","vx","vy","r"])

# =============================================================================
# MODULE 2: PREPROCESSING (vectorised per-track smoothing)
# =============================================================================

def rolling_mean_1d(arr:np.ndarray, w:int) -> np.ndarray:
    """Centre-aligned rolling mean without pandas overhead."""
    hw = w//2
    out = np.empty_like(arr, dtype=float)
    n = len(arr)
    for i in range(n):
        lo = max(0,i-hw); hi = min(n,i+hw+1)
        out[i] = np.nanmean(arr[lo:hi])
    return out


def preprocess_chunk(df:pd.DataFrame, quality:Optional[Dict[str,int]]=None) -> pd.DataFrame:
    if df.empty: return df
    W=CONFIG["SMOOTHING_WINDOW"]; VMAX=CONFIG["MAX_VELOCITY_MS"]; MINLEN=CONFIG["MIN_TRACK_LENGTH"]

    # Dedup: keep first occurrence per (ts,tid) – data already sorted by score asc
    before_dedup = len(df)
    df = df.sort_values(["tid","ts"]).drop_duplicates(subset=["ts","tid"])
    if quality is not None:
        quality["duplicate_rows_removed"] += before_dedup - len(df)

    # Outlier velocity
    spd = np.sqrt(df["vx"]**2+df["vy"]**2)
    bad = spd > VMAX
    if quality is not None:
        quality["velocity_outliers_removed"] += int(bad.sum())
    df.loc[bad,"vx"] = np.nan; df.loc[bad,"vy"] = np.nan

    # Per-track smoothing — using pandas groupby but only for short arrays
    parts = []
    for tid, g in df.groupby("tid", sort=False):
        g = g.sort_values("ts")
        if len(g) < MINLEN:
            if quality is not None:
                quality["short_tracks_removed"] += 1
            continue
        arr = g[["x","y","vx","vy"]].values.astype(float)
        # Linear interpolation over NaN
        for col in range(4):
            a = arr[:,col]
            nans = np.isnan(a)
            if nans.any() and (~nans).any():
                xp = np.where(~nans)[0]; fp = a[~nans]
                a[nans] = np.interp(np.where(nans)[0], xp, fp)
            arr[:,col] = rolling_mean_1d(a, W)
        g = g.copy()
        g["x"]  = arr[:,0]; g["y"]  = arr[:,1]
        g["vx"] = arr[:,2]; g["vy"] = arr[:,3]
        g["spd"] = np.sqrt(g["vx"]**2+g["vy"]**2)
        parts.append(g)

    if not parts: return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)

# =============================================================================
# MODULE 3: VECTORISED TTC
# =============================================================================

def compute_ttc_vectorised(frame_df:pd.DataFrame) -> List[Dict]:
    """
    Compute TTC for all pairs in one frame using numpy broadcasting.
    O(N²) pairs evaluated simultaneously as array operations.

    Math:
      Δr = r2-r1,  Δv = v1-v2  (closing velocity)
      d²(t) = |Δr - Δv·t|² = R²
      → a·t²+b·t+c=0 where
          a = |Δv|²
          b = -2(Δr·Δv)
          c = |Δr|²-R²
      TTC = smallest positive real root.

    Ref: Hayward (1972)
    """
    recs = frame_df.to_dict("records")
    n = len(recs)
    if n < 2: return []

    xs  = np.array([r["x"]  for r in recs])
    ys  = np.array([r["y"]  for r in recs])
    vxs = np.array([r["vx"] for r in recs])
    vys = np.array([r["vy"] for r in recs])
    rs  = np.array([r["r"]  for r in recs])
    cats= np.array([r["cat"] for r in recs])
    spds= np.array([r["spd"] for r in recs])

    # Pairwise differences using broadcasting
    dx  = xs[:,None] - xs[None,:]     # (n,n)
    dy  = ys[:,None] - ys[None,:]
    dvx = vxs[:,None] - vxs[None,:]  # closing velocity
    dvy = vys[:,None] - vys[None,:]
    R   = rs[:,None] + rs[None,:]     # combined radii

    a = dvx**2 + dvy**2
    # Relative position at time t is d(t) = d(0) + (v1-v2)t.
    # A positive TTC therefore requires objects to be approaching, not separating.
    b = 2.0*(dx*dvx + dy*dvy)
    c = dx**2 + dy**2 - R**2
    disc = b**2 - 4.0*a*c

    VMIN2 = CONFIG["TTC_MIN_CLOSING_SPEED"]**2
    MAXTTC = CONFIG["TTC_LOOKAHEAD_SEC"]
    THRESH  = CONFIG["TTC_THRESHOLD_SEC"]
    RMAX2   = CONFIG["INTERACTION_RADIUS_M"]**2

    # Masks
    dist2 = dx**2+dy**2
    motor_vru = (((cats[:,None] == CAT_MOTOR) & (cats[None,:] == CAT_VUL))
                 | ((cats[:,None] == CAT_VUL) & (cats[None,:] == CAT_MOTOR)))
    category_mask = ((cats[:,None]!=CAT_OTHER) | (cats[None,:]!=CAT_OTHER)) if CONFIG["INCLUDE_NON_VRU"] else motor_vru
    valid = (np.triu(np.ones((n,n),bool),k=1)          # upper-triangle only
             & (dist2 <= RMAX2)                          # spatial filter
             & category_mask                              # motorised-vulnerable by default
             & (a >= VMIN2)                              # has relative motion
             & (disc >= 0)                               # real solution
             & (c >= 0))                                 # not already overlapping

    results = []
    if not valid.any(): return results

    ii, jj = np.where(valid)
    sq   = np.sqrt(disc[ii,jj])
    a_   = a[ii,jj]; b_ = b[ii,jj]
    t1   = (-b_ - sq)/(2*a_)
    t2   = (-b_ + sq)/(2*a_)
    # Smallest positive root
    t1_pos = np.where(t1>0, t1, np.inf)
    t2_pos = np.where(t2>0, t2, np.inf)
    ttc_arr = np.minimum(t1_pos, t2_pos)

    keep = (ttc_arr > 0) & (ttc_arr <= MAXTTC)
    for k in np.where(keep)[0]:
        i,j = int(ii[k]), int(jj[k])
        ttc = float(ttc_arr[k])
        o1  = recs[i]; o2 = recs[j]
        results.append({
            "ts":    o1["ts"],
            "tsl":   o1.get("tsl",""),
            "tid1":  o1["tid"],
            "tid2":  o2["tid"],
            "cls1":  o1["cls"],
            "cls2":  o2["cls"],
            "cat1":  o1["cat"],
            "cat2":  o2["cat"],
            "xmid":  (o1["x"]+o2["x"])*0.5,
            "ymid":  (o1["y"]+o2["y"])*0.5,
            "spd1":  float(spds[i]),
            "spd2":  float(spds[j]),
            "dist":  float(math.sqrt(float(dist2[i,j]))),
            "ttc":   ttc,
            "nm":    ttc < THRESH,
            "itype": f"{o1['cls']}_vs_{o2['cls']}",
        })
    return results


def run_ttc_on_chunk(df:pd.DataFrame) -> List[Dict]:
    results = []
    for ts, frame in df.groupby("ts"):
        if len(frame) >= 2:
            results.extend(compute_ttc_vectorised(frame))
    return results

# =============================================================================
# MODULE 4: PET ACCUMULATOR
# =============================================================================

class PETAccumulator:
    """Streaming grid-cell occupancy accumulator."""

    def __init__(self):
        self.cell_g  = CONFIG["PET_GRID_CELL_M"]
        # tid → cell → [timestamps]
        self.data: Dict[int,Dict[Tuple,List[float]]] = defaultdict(lambda: defaultdict(list))
        self.meta: Dict[int,Dict] = {}

    def _cell(self,x,y):
        g=self.cell_g; return (math.floor(x/g),math.floor(y/g))

    def update(self, df:pd.DataFrame):
        for row in df.itertuples(index=False):
            tid=row.tid
            if tid not in self.meta:
                self.meta[tid]={"cls":row.cls,"cat":row.cat}
            self.data[tid][self._cell(row.x,row.y)].append(row.ts)

    def compute(self) -> List[Dict]:
        """Return grid-cell PET proxy events.

        A visit is a contiguous sequence of observations in one cell.  This
        prevents a track that revisits a cell later in the day from being
        treated as one long encroachment.
        """
        THRESH = CONFIG["PET_THRESHOLD_SEC"]
        MAXGAP = CONFIG["PET_MAX_GAP_SEC"]
        VISITGAP = CONFIG["PET_VISIT_GAP_SEC"]
        cell_visits: Dict[Tuple,List[Dict]] = defaultdict(list)
        for tid,cells in self.data.items():
            for cell,times in cells.items():
                times=np.sort(np.asarray(times, dtype=float))
                for visit in np.split(times, np.where(np.diff(times) > VISITGAP)[0] + 1):
                    if len(visit):
                        cell_visits[cell].append({"tid":tid, "times":visit, **self.meta[tid]})

        results=[]
        for cell,visits in cell_visits.items():
            if len(visits)<2: continue
            for i in range(len(visits)):
                for j in range(i+1,len(visits)):
                    v1,v2=visits[i],visits[j]
                    if v1["tid"] == v2["tid"]: continue
                    c1,c2=v1["cat"],v2["cat"]
                    motor_vru=(c1,c2) in {(CAT_MOTOR,CAT_VUL),(CAT_VUL,CAT_MOTOR)}
                    if not CONFIG["INCLUDE_NON_VRU"] and not motor_vru: continue
                    if CONFIG["INCLUDE_NON_VRU"] and c1==CAT_OTHER and c2==CAT_OTHER: continue
                    a1,a2=v1["times"],v2["times"]
                    if min(abs(a1.mean()-a2.mean()), abs(a1.min()-a2.max()), abs(a2.min()-a1.max())) > MAXGAP: continue
                    pet=_calc_pet(a1,a2)
                    if pet is None: continue
                    c1s,c2s=v1["cls"],v2["cls"]
                    results.append({
                        "cx":cell[0],"cy":cell[1],
                        "zx":cell[0]*self.cell_g+self.cell_g/2,
                        "zy":cell[1]*self.cell_g+self.cell_g/2,
                        "ts":min(a1.min(),a2.min()),
                        "tid1":v1["tid"],"tid2":v2["tid"],
                        "cls1":c1s,"cls2":c2s,
                        "cat1":c1,"cat2":c2,
                        "pet":round(pet,4),
                        "nm": pet<THRESH,
                        "itype":f"{c1s}_vs_{c2s}",
                    })
        return results


def _calc_pet(a1:np.ndarray, a2:np.ndarray) -> Optional[float]:
    """Calculate PET between two occupancy time-arrays at a shared zone."""
    e1,x1 = a1.min(),a1.max()
    e2,x2 = a2.min(),a2.max()
    if not (x1<e2 or x2<e1): return 0.0  # simultaneous
    return float(e2-x1) if x1<e2 else float(e1-x2)

# =============================================================================
# MODULE 5: SVG PLOTS (zero external dependencies)
# =============================================================================

class SVG:
    C={"bg":"#f8f9fa","grid":"#dee2e6","ax":"#212529",
       "red":"#e74c3c","blue":"#2980b9","green":"#27ae60",
       "grey":"#95a5a6","orange":"#e67e22","purple":"#8e44ad"}

    def __init__(self,w,h,title=""):
        self.w=w;self.h=h;self.t=title
        self.pl=88;self.pr=42;self.pt=68;self.pb=78
        self.e=[]

    def _px(self,x,xmn,xmx):
        return self.pl+(x-xmn)/max(xmx-xmn,1e-9)*(self.w-self.pl-self.pr)
    def _py(self,y,ymn,ymx):
        return self.h-self.pb-(y-ymn)/max(ymx-ymn,1e-9)*(self.h-self.pt-self.pb)

    def _e(self,s): self.e.append(s)

    def rect(self,x,y,w,h,f,op=1,st="none",sw=0,rx=0):
        self._e(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{f}" opacity="{op}" stroke="{st}" stroke-width="{sw}" rx="{rx}"/>')
    def circ(self,cx,cy,r,f,op=0.75):
        self._e(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{f}" opacity="{op}"/>')
    def ln(self,x1,y1,x2,y2,st="#333",sw=1.5,dash=""):
        d=f' stroke-dasharray="{dash}"' if dash else ""
        self._e(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{st}" stroke-width="{sw}"{d}/>')
    def txt(self,x,y,s,an="middle",sz=12,bold=False,fill="#212529",rot=None):
        fw="bold" if bold else "normal"
        r=f' transform="rotate({rot},{x:.1f},{y:.1f})"' if rot else ""
        self._e(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{an}" font-size="{sz}" font-family="Arial,sans-serif" font-weight="{fw}" fill="{fill}"{r}>{s}</text>')

    def axes(self,xmn,xmx,ymn,ymx,xl,yl,nt=6):
        pw=self.w-self.pl-self.pr; ph=self.h-self.pt-self.pb
        x0=self.pl; x1=x0+pw; y0=self.h-self.pb; y1=self.pt
        self.rect(x0,y1,pw,ph,self.C["bg"],st=self.C["grid"],sw=1)
        for i in range(nt+1):
            gx=x0+pw*i/nt; gy=y0-ph*i/nt
            self.ln(gx,y1,gx,y0,self.C["grid"],0.6)
            self.ln(x0,gy,x1,gy,self.C["grid"],0.6)
            self.txt(gx,y0+20,f"{xmn+(xmx-xmn)*i/nt:.2g}",sz=10)
            self.txt(x0-10,gy+4,f"{ymn+(ymx-ymn)*i/nt:.2g}",an="end",sz=10)
        self.ln(x0,y0,x1,y0,self.C["ax"])
        self.ln(x0,y0,x0,y1,self.C["ax"])
        self.txt((x0+x1)/2,self.h-12,xl,sz=13,bold=True)
        self.txt(16,(y0+y1)/2+4,yl,sz=13,bold=True,rot=-90)
        self.txt(self.w/2,34,self.t,sz=15,bold=True)
        return xmn,xmx,ymn,ymx

    def scatter(self,xs,ys,xmn,xmx,ymn,ymx,c,sz=5,op=0.72):
        for x,y in zip(xs,ys):
            self.circ(self._px(x,xmn,xmx),self._py(y,ymn,ymx),sz,c,op)

    def vline(self,xv,xmn,xmx,ymn,ymx,c="red",d="6,3"):
        px=self._px(xv,xmn,xmx); self.ln(px,self.pt,px,self.h-self.pb,c,1.8,d)
    def hline(self,yv,xmn,xmx,ymn,ymx,c="red",d="6,3"):
        py=self._py(yv,ymn,ymx); self.ln(self.pl,py,self.w-self.pr,py,c,1.8,d)

    def bars(self,xs,counts,bw,ymx):
        ph=self.h-self.pt-self.pb; y0=self.h-self.pb
        for x,cnt,c in xs:
            bh=cnt/max(ymx,1)*ph
            self.rect(x,y0-bh,bw-1,bh,c,0.85)

    def legend(self,items,lx=None,ly=None):
        lx=lx or self.w-self.pr-185; ly=ly or self.pt+10
        self.rect(lx-5,ly-5,192,len(items)*24+14,"white",st="#ccc",sw=1,rx=5)
        for i,(col,lbl) in enumerate(items):
            cy=ly+14+i*24
            self.circ(lx+10,cy,9,col,0.85)
            self.txt(lx+24,cy+5,lbl,an="start",sz=11)

    def save(self,path):
        os.makedirs(os.path.dirname(path),exist_ok=True)
        hdr=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'
             f'<rect width="{self.w}" height="{self.h}" fill="white"/>\n')
        with open(path,"w") as f:
            f.write(hdr+"\n".join(self.e)+"\n</svg>")
        print(f"  [plot] {os.path.basename(path)}")


def _hist(vals,nbins,vmin,vmax):
    edges=np.linspace(vmin,vmax,nbins+1)
    counts,_=np.histogram(vals,bins=edges)
    return counts,edges

def mk_ttc_hist(ttc_df,out):
    if ttc_df.empty: return
    vals=ttc_df["ttc"].dropna().values
    n=25; vmin,vmax=0,CONFIG["TTC_LOOKAHEAD_SEC"]
    counts,edges=_hist(vals,n,vmin,vmax)
    cv=SVG(820,520,"TTC Distribution — All Interactions (K305)")
    ymax=float(counts.max())*1.15 or 10
    cv.axes(vmin,vmax,0,ymax,"TTC (seconds)","Count")
    pw=cv.w-cv.pl-cv.pr; bw=pw/n
    th=CONFIG["TTC_THRESHOLD_SEC"]
    xs=[(cv.pl+i*bw,counts[i],cv.C["red"] if (edges[i]+edges[i+1])/2<th else cv.C["blue"]) for i in range(n)]
    cv.bars(xs,counts,bw,ymax)
    cv.vline(th,vmin,vmax,0,ymax,cv.C["ax"])
    cv.legend([(cv.C["red"],f"Near-miss TTC<{th}s"),(cv.C["blue"],"Safe")])
    cv.save(os.path.join(out,"plot_ttc_histogram.svg"))

def mk_pet_hist(pet_df,out):
    if pet_df.empty: return
    vals=pet_df["pet"].dropna().values
    n=25; vmin,vmax=0,CONFIG["PET_MAX_GAP_SEC"]
    counts,edges=_hist(vals,n,vmin,vmax)
    cv=SVG(820,520,"PET Distribution — Zone Crossings (K305)")
    ymax=float(counts.max())*1.15 or 10
    cv.axes(vmin,vmax,0,ymax,"PET (seconds)","Count")
    pw=cv.w-cv.pl-cv.pr; bw=pw/n
    th=CONFIG["PET_THRESHOLD_SEC"]
    xs=[(cv.pl+i*bw,counts[i],cv.C["red"] if (edges[i]+edges[i+1])/2<th else cv.C["green"]) for i in range(n)]
    cv.bars(xs,counts,bw,ymax)
    cv.vline(th,vmin,vmax,0,ymax,cv.C["ax"])
    cv.legend([(cv.C["red"],f"Near-miss PET<{th}s"),(cv.C["green"],"Safe")])
    cv.save(os.path.join(out,"plot_pet_histogram.svg"))

def mk_heatmap(traj_xs,traj_ys,cx,cy,out):
    if len(traj_xs)==0: return
    xmn=float(np.percentile(traj_xs,1)); xmx=float(np.percentile(traj_xs,99))
    ymn=float(np.percentile(traj_ys,1)); ymx=float(np.percentile(traj_ys,99))
    cv=SVG(820,700,"Spatial Conflict Heatmap — Intersection K305")
    cv.axes(xmn,xmx,ymn,ymx,"X Position (m)","Y Position (m)")
    np.random.seed(42)
    idx=np.random.choice(len(traj_xs),min(4000,len(traj_xs)),replace=False)
    cv.scatter(traj_xs[idx],traj_ys[idx],xmn,xmx,ymn,ymx,cv.C["grey"],sz=2,op=0.25)
    if cx:
        cv.scatter(cx,cy,xmn,xmx,ymn,ymx,cv.C["red"],sz=9,op=0.8)
    cv.legend([(cv.C["grey"],"All trajectories"),(cv.C["red"],f"Near-misses (N={len(cx)})")])
    cv.save(os.path.join(out,"plot_conflict_heatmap.svg"))

def mk_ttc_vs_pet(ttc_df,pet_df,out):
    if ttc_df.empty or pet_df.empty: return
    nm_t=ttc_df[ttc_df["nm"]].copy(); nm_p=pet_df[pet_df["nm"]].copy()
    if nm_t.empty or nm_p.empty: return
    nm_t["pair"]=nm_t.apply(lambda r:tuple(sorted([r["tid1"],r["tid2"]])),axis=1)
    nm_p["pair"]=nm_p.apply(lambda r:tuple(sorted([r["tid1"],r["tid2"]])),axis=1)
    mg=pd.merge(nm_t[["pair","ttc","cat1","cat2"]],nm_p[["pair","pet"]],on="pair",how="inner")
    if mg.empty: return
    xmn,xmx=0,CONFIG["TTC_LOOKAHEAD_SEC"]; ymn,ymx=0,CONFIG["PET_MAX_GAP_SEC"]
    cv=SVG(820,620,"TTC vs PET — Near-Miss Events (K305)")
    cv.axes(xmn,xmx,ymn,ymx,"TTC (seconds)","PET (seconds)")
    CM={(CAT_MOTOR,CAT_VUL):cv.C["red"],(CAT_VUL,CAT_MOTOR):cv.C["red"],
        (CAT_MOTOR,CAT_MOTOR):cv.C["blue"],(CAT_VUL,CAT_VUL):cv.C["green"]}
    for _,r in mg.iterrows():
        c=CM.get((r["cat1"],r["cat2"]),cv.C["purple"])
        cv.circ(cv._px(r["ttc"],xmn,xmx),cv._py(r["pet"],ymn,ymx),7,c,0.75)
    cv.vline(CONFIG["TTC_THRESHOLD_SEC"],xmn,xmx,ymn,ymx,cv.C["ax"])
    cv.hline(CONFIG["PET_THRESHOLD_SEC"],xmn,xmx,ymn,ymx,cv.C["ax"])
    cv.legend([(cv.C["red"],"Motor vs Vulnerable"),(cv.C["blue"],"Motor vs Motor"),(cv.C["green"],"Vul vs Vul")])
    cv.save(os.path.join(out,"plot_ttc_vs_pet.svg"))

def mk_hourly(ttc_df,pet_df,out):
    counts=[0]*24
    def add(df,flag):
        if df.empty: return
        nm=df[df[flag]].copy()
        nm["dt"]=pd.to_datetime(nm["tsl" if "tsl" in nm.columns else "ts"],utc=False,errors="coerce")
        for h in nm["dt"].dt.hour.dropna().astype(int):
            if 0<=h<24: counts[h]+=1
    add(ttc_df,"nm"); add(pet_df,"nm")
    if sum(counts)==0: return
    ymax=max(counts)*1.15
    cv=SVG(900,520,"Near-Miss Events by Hour of Day — K305")
    cv.axes(0,23,0,ymax,"Hour of Day","Near-Miss Count",nt=8)
    pw=cv.w-cv.pl-cv.pr; bw=pw/24; peak={7,8,9,16,17,18}
    xs=[(cv.pl+h*bw,counts[h],cv.C["red"] if h in peak else cv.C["blue"]) for h in range(24)]
    cv.bars(xs,counts,bw,ymax)
    cv.legend([(cv.C["red"],"Peak rush hours"),(cv.C["blue"],"Off-peak")])
    cv.save(os.path.join(out,"plot_hourly_conflicts.svg"))

def mk_breakdown(ttc_df,pet_df,out):
    rows=[]
    if not ttc_df.empty:
        for t,g in ttc_df[ttc_df["nm"]].groupby("itype"):
            rows.append({"type":t,"metric":"TTC","count":len(g)})
    if not pet_df.empty:
        for t,g in pet_df[pet_df["nm"]].groupby("itype"):
            rows.append({"type":t,"metric":"PET","count":len(g)})
    if not rows: return
    bd=pd.DataFrame(rows)
    types=sorted(bd["type"].unique())
    tc={t:int(bd[(bd["type"]==t)&(bd["metric"]=="TTC")]["count"].sum()) for t in types}
    pc={t:int(bd[(bd["type"]==t)&(bd["metric"]=="PET")]["count"].sum()) for t in types}
    n=len(types); h=max(450,n*55+150)
    cv=SVG(900,h,"Near-Miss Breakdown by Interaction Type (K305)")
    xmax=max(list(tc.values())+list(pc.values()))*1.15 or 10
    cv.axes(0,xmax,0,n,"Count","Interaction Type",nt=5)
    pw=cv.w-cv.pl-cv.pr; ph=cv.h-cv.pt-cv.pb
    rh=ph/max(n,1); bh=rh*0.36
    for i,itype in enumerate(types):
        gyc=cv.h-cv.pb-(i+0.5)*rh
        bw=tc.get(itype,0)/xmax*pw; bw2=pc.get(itype,0)/xmax*pw
        cv.rect(cv.pl,gyc-bh,bw,bh,cv.C["blue"],0.85)
        cv.rect(cv.pl,gyc,bw2,bh,cv.C["red"],0.85)
        cv.txt(cv.pl-6,gyc+bh/4,itype[:38],an="end",sz=10)
    cv.legend([(cv.C["blue"],"TTC near-miss"),(cv.C["red"],"PET near-miss")])
    cv.save(os.path.join(out,"plot_interaction_breakdown.svg"))

# =============================================================================
# MODULE 6: SUMMARY
# =============================================================================

def consolidate_ttc_events(ttc_df:pd.DataFrame) -> pd.DataFrame:
    """Collapse consecutive near-miss frames for a track pair into one event."""
    columns=["event_start_timestamp","event_end_timestamp","duration_sec","frames_in_event",
             "min_ttc_sec","track_id_1","track_id_2","class_1","class_2",
             "interaction_type","x_mid","y_mid","timestamp_local"]
    if ttc_df.empty or not ttc_df["nm"].any():
        return pd.DataFrame(columns=columns)
    data=ttc_df[ttc_df["nm"]].copy()
    data["pair_lo"]=data[["tid1","tid2"]].min(axis=1)
    data["pair_hi"]=data[["tid1","tid2"]].max(axis=1)
    rows=[]
    for _, group in data.groupby(["pair_lo","pair_hi"], sort=False):
        group=group.sort_values("ts")
        starts=np.r_[True, np.diff(group["ts"].to_numpy()) > CONFIG["EVENT_GAP_SEC"]]
        for _, event in group.groupby(np.cumsum(starts), sort=False):
            worst=event.loc[event["ttc"].idxmin()]
            rows.append({
                "event_start_timestamp":float(event["ts"].min()),
                "event_end_timestamp":float(event["ts"].max()),
                "duration_sec":round(float(event["ts"].max()-event["ts"].min()), 4),
                "frames_in_event":int(len(event)), "min_ttc_sec":round(float(worst["ttc"]), 4),
                "track_id_1":int(worst["tid1"]), "track_id_2":int(worst["tid2"]),
                "class_1":worst["cls1"], "class_2":worst["cls2"], "interaction_type":worst["itype"],
                "x_mid":round(float(worst["xmid"]), 4), "y_mid":round(float(worst["ymid"]), 4),
                "timestamp_local":worst.get("tsl", ""),
            })
    return pd.DataFrame(rows, columns=columns).sort_values("min_ttc_sec", ignore_index=True)


def summary(cls_dist,ttc_df,pet_df,n_frames,n_tracks,ttc_events=None,quality=None):
    s={"intersection":"K305","date":"2026-10-14","total_frames":n_frames,
       "total_tracks":n_tracks,"class_distribution":cls_dist,"ttc":{},"pet":{}}
    if not ttc_df.empty:
        nm=ttc_df[ttc_df["nm"]]
        s["ttc"]={"total_frame_interactions":len(ttc_df),"near_miss_frame_observations":int(len(nm)),
                  "near_miss_rate_pct":round(100*len(nm)/max(len(ttc_df),1),2),
                  "min_ttc_sec":round(float(ttc_df["ttc"].min()),4),
                  "mean_ttc_sec":round(float(ttc_df["ttc"].mean()),4),
                  "by_type":nm["itype"].value_counts().to_dict()}
        if ttc_events is not None:
            s["ttc"]["near_miss_events"]=int(len(ttc_events))
    if not pet_df.empty:
        nm=pet_df[pet_df["nm"]]
        s["pet"]={"total_crossings":len(pet_df),"near_misses":int(len(nm)),
                  "near_miss_rate_pct":round(100*len(nm)/max(len(pet_df),1),2),
                  "min_pet_sec":round(float(pet_df["pet"].min()),4),
                  "mean_pet_sec":round(float(pet_df["pet"].mean()),4),
                  "by_type":nm["itype"].value_counts().to_dict()}
    if quality is not None: s["data_quality"]=dict(quality)
    return s

def print_report(s):
    SEP="="*72
    print(f"\n{SEP}\n  FINAL NEAR-MISS ANALYSIS REPORT — K305 | {s['date']}\n{SEP}")
    print(f"  Frames Analysed : {s['total_frames']:,}")
    print(f"  Unique Tracks   : {s['total_tracks']:,}")
    print("  Class Distribution:")
    for k,v in sorted(s["class_distribution"].items(),key=lambda x:-x[1]):
        print(f"    {k:<15}: {v:>8,}")

    def sec(title,d):
        print(f"\n  ── {title} ──")
        if not d: print("  (no data)"); return
        for k,v in d.items():
            if k=="by_type":
                print("  Near-misses by type:")
                for t,c in sorted(v.items(),key=lambda x:-x[1]):
                    print(f"    {t:<40}: {c:>5,}")
            else:
                print(f"  {k:<35}: {v}")

    sec("TIME-TO-COLLISION (TTC)",s.get("ttc",{}))
    sec("POST-ENCROACHMENT TIME (PET)",s.get("pet",{}))
    print(f"\n{SEP}\n")

# =============================================================================
# MAIN
# =============================================================================

def legacy_main():
    np.random.seed(42)
    OUT=CONFIG["OUTPUT_DIR"]; os.makedirs(OUT,exist_ok=True)
    files=sorted(glob.glob(os.path.join(CONFIG["DATA_DIR"],"*.json")))
    if not files: raise FileNotFoundError("No JSON files found")
    N=len(files)

    print("="*72)
    print(f"  NEAR-MISS PIPELINE v3  |  K305  |  2026-10-14  |  {N} chunks")
    print("="*72)

    ttc_rows: List[Dict]=[]
    pet_acc=PETAccumulator()
    cls_set: Dict[str,set]=defaultdict(set)
    n_frames=0
    xs_samp,ys_samp=[],[]

    for fi,fpath in enumerate(files):
        bname=os.path.basename(fpath)
        print(f"  [{fi+1:>3}/{N}] {bname}",end=" ",flush=True)

        with open(fpath) as fh:
            chunk=json.load(fh)

        df=parse_chunk(chunk)
        if df.empty: print("empty"); continue
        df=preprocess_chunk(df)
        if df.empty: print("empty (preprocessed)"); continue

        n_frames+=df["ts"].nunique()
        for _,r in df.drop_duplicates("tid").iterrows():
            cls_set[r["cls"]].add(r["tid"])

        # Trajectory sample (1 in 6 points for heatmap)
        xs_samp.extend(df["x"].values[::6].tolist())
        ys_samp.extend(df["y"].values[::6].tolist())

        # TTC
        chunk_ttc=run_ttc_on_chunk(df)
        ttc_rows.extend(chunk_ttc)
        n_nm=sum(1 for r in chunk_ttc if r["nm"])

        # PET accumulation
        pet_acc.update(df)

        print(f"frames={df['ts'].nunique():>4}  TTC={len(chunk_ttc):>5}  NM={n_nm:>4}")

    # ── Build DataFrames ──────────────────────────────────────────────────
    print("\n[A] Building TTC DataFrame...")
    ttc_df=pd.DataFrame(ttc_rows)
    if not ttc_df.empty:
        print(f"  TTC interactions : {len(ttc_df):,}  |  near-misses : {ttc_df['nm'].sum():,}")

    print("[B] Computing PET...")
    pet_rows=pet_acc.compute()
    pet_df=pd.DataFrame(pet_rows)
    if not pet_df.empty:
        print(f"  Zone crossings   : {len(pet_df):,}  |  near-misses : {pet_df['nm'].sum():,}")

    # ── Save CSVs ─────────────────────────────────────────────────────────
    print("[C] Saving tables...")
    rename_ttc={"ts":"timestamp","tsl":"timestamp_local","tid1":"track_id_1","tid2":"track_id_2",
                "cls1":"class_1","cls2":"class_2","cat1":"category_1","cat2":"category_2",
                "xmid":"x_mid","ymid":"y_mid","spd1":"speed_1","spd2":"speed_2",
                "dist":"distance_m","ttc":"ttc_sec","nm":"is_near_miss_ttc","itype":"interaction_type"}
    rename_pet={"cx":"cell_gx","cy":"cell_gy","zx":"zone_x","zy":"zone_y","ts":"timestamp",
                "tid1":"track_id_1","tid2":"track_id_2","cls1":"class_1","cls2":"class_2",
                "cat1":"category_1","cat2":"category_2","pet":"pet_sec","nm":"is_near_miss_pet","itype":"interaction_type"}

    if not ttc_df.empty:
        out=ttc_df.rename(columns=rename_ttc)
        out.to_csv(os.path.join(OUT,"all_ttc_interactions.csv"),index=False)
        nm=out[out["is_near_miss_ttc"]].sort_values("ttc_sec")
        nm.to_csv(os.path.join(OUT,"near_misses_ttc.csv"),index=False)
        print(f"  near_misses_ttc.csv  → {len(nm):,} rows")

    if not pet_df.empty:
        outp=pet_df.rename(columns=rename_pet)
        outp.to_csv(os.path.join(OUT,"all_pet_interactions.csv"),index=False)
        nmp=outp[outp["is_near_miss_pet"]].sort_values("pet_sec")
        nmp.to_csv(os.path.join(OUT,"near_misses_pet.csv"),index=False)
        print(f"  near_misses_pet.csv  → {len(nmp):,} rows")

    # ── Plots ─────────────────────────────────────────────────────────────
    print("[D] Generating plots...")
    traj_xs=np.array(xs_samp); traj_ys=np.array(ys_samp)
    cx,cy=[],[]
    if not ttc_df.empty:
        nm=ttc_df[ttc_df["nm"]]; cx+=nm["xmid"].tolist(); cy+=nm["ymid"].tolist()
    if not pet_df.empty:
        nm=pet_df[pet_df["nm"]]; cx+=nm["zx"].tolist(); cy+=nm["zy"].tolist()

    mk_ttc_hist(ttc_df,OUT)
    mk_pet_hist(pet_df,OUT)
    mk_heatmap(traj_xs,traj_ys,cx,cy,OUT)
    mk_ttc_vs_pet(ttc_df,pet_df,OUT)
    mk_hourly(ttc_df,pet_df,OUT)
    mk_breakdown(ttc_df,pet_df,OUT)

    # ── Report ────────────────────────────────────────────────────────────
    print("[E] Summary report...")
    n_tracks=sum(len(v) for v in cls_set.values())
    cld={k:len(v) for k,v in cls_set.items()}
    stats=summary(cld,ttc_df,pet_df,n_frames,n_tracks)
    print_report(stats)

    import json as _json
    def ser(o):
        if isinstance(o,(np.integer,)): return int(o)
        if isinstance(o,(np.floating,)): return float(o)
        return str(o)
    with open(os.path.join(OUT,"summary_stats.json"),"w") as f:
        _json.dump(stats,f,indent=2,default=ser)

    print(f"\n[DONE] Outputs → {OUT}\n")
    return ttc_df, pet_df, stats

if __name__=="__main__":
    pass  # The command-line entry point is defined below.


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description="K305 TTC and grid-cell PET proxy analysis")
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument("--all", action="store_true", help="analyse every JSON chunk")
    scope.add_argument("--files", nargs="+", help="specific JSON filenames or paths")
    parser.add_argument("--data-dir", default=CONFIG["DATA_DIR"])
    parser.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--save-all", action="store_true", help="write all frame-level interactions")
    parser.add_argument("--include-non-vru", action="store_true")
    parser.add_argument("--ttc-threshold", type=float, default=CONFIG["TTC_THRESHOLD_SEC"])
    parser.add_argument("--pet-threshold", type=float, default=CONFIG["PET_THRESHOLD_SEC"])
    parser.add_argument("--self-test", action="store_true", help="run deterministic TTC tests and exit")
    return parser.parse_args(argv)


def select_files(args):
    data_dir=Path(args.data_dir)
    available=sorted(data_dir.glob("*.json"))
    if not available: raise FileNotFoundError(f"No JSON files found in {data_dir}")
    if args.files:
        files=[]
        for item in args.files:
            path=Path(item)
            path=path if path.is_file() else data_dir/path
            if not path.is_file(): raise FileNotFoundError(f"Input file not found: {item}")
            files.append(path)
        return sorted(files), "custom"
    if args.all: return available, "full_day"
    preferred=[p for p in available if any(f"_08-{m:02d}_to_08-" in p.name for m in (0,5,10))]
    return (preferred[:3] if len(preferred)>=3 else available[:3]), "sample_08-00_to_08-14"


def consolidate_ttc_events(ttc_df):
    cols=["event_start_timestamp","event_end_timestamp","duration_sec","frames_in_event","min_ttc_sec","track_id_1","track_id_2","class_1","class_2","interaction_type","x_mid","y_mid","timestamp_local"]
    if ttc_df.empty or not ttc_df["nm"].any(): return pd.DataFrame(columns=cols)
    data=ttc_df[ttc_df["nm"]].copy()
    data["lo"]=data[["tid1","tid2"]].min(axis=1); data["hi"]=data[["tid1","tid2"]].max(axis=1)
    rows=[]
    for _, group in data.groupby(["lo","hi"], sort=False):
        group=group.sort_values("ts")
        episode=np.cumsum(np.r_[True,np.diff(group["ts"].to_numpy())>CONFIG["EVENT_GAP_SEC"]])
        for _, event in group.groupby(episode, sort=False):
            worst=event.loc[event["ttc"].idxmin()]
            rows.append({"event_start_timestamp":float(event.ts.min()),"event_end_timestamp":float(event.ts.max()),"duration_sec":round(float(event.ts.max()-event.ts.min()),4),"frames_in_event":len(event),"min_ttc_sec":round(float(worst.ttc),4),"track_id_1":int(worst.tid1),"track_id_2":int(worst.tid2),"class_1":worst.cls1,"class_2":worst.cls2,"interaction_type":worst.itype,"x_mid":round(float(worst.xmid),4),"y_mid":round(float(worst.ymid),4),"timestamp_local":worst.tsl})
    return pd.DataFrame(rows,columns=cols).sort_values("min_ttc_sec",ignore_index=True)


def run_ttc_self_tests():
    def make(rows): return pd.DataFrame(rows,columns=["ts","tsl","tid","cls","cat","x","y","vx","vy","r","spd"])
    def obj(tid,x,vx,cat): return (0.,"",tid,"Car" if cat==CAT_MOTOR else "Pedestrian",cat,x,0.,vx,0.,.5,abs(vx))
    cases={"approaching":(make([obj(1,-5,1,CAT_MOTOR),obj(2,5,-1,CAT_VUL)]),1,4.5,False),"separating":(make([obj(1,-5,-1,CAT_MOTOR),obj(2,5,1,CAT_VUL)]),0,None,None),"parallel":(make([obj(1,0,1,CAT_MOTOR),obj(2,5,1,CAT_VUL)]),0,None,None),"overlapping":(make([obj(1,0,1,CAT_MOTOR),obj(2,.5,-1,CAT_VUL)]),0,None,None),"threshold_boundary":(make([obj(1,-2,1,CAT_MOTOR),obj(2,2,-1,CAT_VUL)]),1,1.5,False)}
    for name,(df,count,ttc,nm) in cases.items():
        result=compute_ttc_vectorised(df); assert len(result)==count, name
        if result: assert abs(result[0]["ttc"]-ttc)<1e-9 and result[0]["nm"] is nm, name
    print("TTC self-tests passed: approaching, separating, parallel, overlapping, threshold boundary.")


def main(argv=None):
    args=parse_args(argv)
    if args.self_test: run_ttc_self_tests(); return
    if args.ttc_threshold<=0 or args.pet_threshold<=0: raise ValueError("thresholds must be positive")
    CONFIG.update(TTC_THRESHOLD_SEC=args.ttc_threshold,PET_THRESHOLD_SEC=args.pet_threshold,INCLUDE_NON_VRU=args.include_non_vru)
    files,label=select_files(args)
    run_dir=Path(args.output_dir)/f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"; run_dir.mkdir(parents=True)
    started=time.perf_counter(); np.random.seed(42)
    print(f"NEAR-MISS PIPELINE | {label} | {len(files)} chunk(s)\nOutput: {run_dir}")
    ttc_rows=[]; pet_acc=PETAccumulator(); cls_set=defaultdict(set); quality=defaultdict(int); n_frames=0; xs=[]; ys=[]
    for i,path in enumerate(files,1):
        with open(path) as fh: raw=parse_chunk(json.load(fh))
        quality["raw_rows"]+=len(raw)
        df=preprocess_chunk(raw,quality)
        if df.empty: print(f"[{i}/{len(files)}] {path.name}: no retained tracks"); continue
        n_frames+=df.ts.nunique()
        for cls,tid in df[["cls","tid"]].drop_duplicates().itertuples(index=False): cls_set[cls].add(tid)
        xs.extend(df.x.values[::6]); ys.extend(df.y.values[::6])
        chunk_ttc=run_ttc_on_chunk(df); ttc_rows.extend(chunk_ttc); pet_acc.update(df)
        print(f"[{i}/{len(files)}] {path.name}: frames={df.ts.nunique()} TTC={len(chunk_ttc)} near-miss frames={sum(r['nm'] for r in chunk_ttc)}")
    ttc_df=pd.DataFrame(ttc_rows); pet_df=pd.DataFrame(pet_acc.compute()); ttc_events=consolidate_ttc_events(ttc_df)
    rename_ttc={"ts":"timestamp","tsl":"timestamp_local","tid1":"track_id_1","tid2":"track_id_2","cls1":"class_1","cls2":"class_2","cat1":"category_1","cat2":"category_2","xmid":"x_mid","ymid":"y_mid","spd1":"speed_1","spd2":"speed_2","dist":"distance_m","ttc":"ttc_sec","nm":"is_near_miss_ttc","itype":"interaction_type"}
    rename_pet={"cx":"cell_gx","cy":"cell_gy","zx":"zone_x","zy":"zone_y","ts":"timestamp","tid1":"track_id_1","tid2":"track_id_2","cls1":"class_1","cls2":"class_2","cat1":"category_1","cat2":"category_2","pet":"pet_sec","nm":"is_near_miss_pet","itype":"interaction_type"}
    ttc_events.to_csv(run_dir/"near_miss_ttc_events.csv",index=False)
    pet_out=pet_df.rename(columns=rename_pet)
    if pet_out.empty: pd.DataFrame(columns=list(rename_pet.values())).to_csv(run_dir/"near_miss_pet_proxy_events.csv",index=False)
    else: pet_out[pet_out.is_near_miss_pet].sort_values("pet_sec").to_csv(run_dir/"near_miss_pet_proxy_events.csv",index=False)
    if args.save_all: ttc_df.rename(columns=rename_ttc).to_csv(run_dir/"all_ttc_frame_interactions.csv",index=False); pet_out.to_csv(run_dir/"all_pet_proxy_interactions.csv",index=False)
    if not args.no_plots:
        cx=[] if ttc_df.empty else ttc_df.loc[ttc_df.nm,"xmid"].tolist(); cy=[] if ttc_df.empty else ttc_df.loc[ttc_df.nm,"ymid"].tolist()
        if not pet_df.empty: cx+=pet_df.loc[pet_df.nm,"zx"].tolist(); cy+=pet_df.loc[pet_df.nm,"zy"].tolist()
        mk_ttc_hist(ttc_df,run_dir); mk_pet_hist(pet_df,run_dir); mk_heatmap(np.asarray(xs),np.asarray(ys),cx,cy,run_dir); mk_ttc_vs_pet(ttc_df,pet_df,run_dir); mk_hourly(ttc_df,pet_df,run_dir); mk_breakdown(ttc_df,pet_df,run_dir)
    quality["retained_rows"]=int(sum(len(t) for cells in pet_acc.data.values() for t in cells.values()))
    stats=summary({k:len(v) for k,v in cls_set.items()},ttc_df,pet_df,n_frames,sum(len(v) for v in cls_set.values()),ttc_events,quality)
    stats.update({"run_scope":label,"selected_files":[p.name for p in files],"output_directory":str(run_dir),"runtime_sec":round(time.perf_counter()-started,2),"pet_note":"PET is a 2 m grid-cell occupancy proxy, not a map-defined conflict-zone PET."})
    with open(run_dir/"run_report.json","w") as fh: json.dump(stats,fh,indent=2,default=lambda o:int(o) if isinstance(o,np.integer) else float(o) if isinstance(o,np.floating) else str(o))
    print_report(stats); print(f"TTC near-miss events: {len(ttc_events):,}\nPET proxy near-miss events: {0 if pet_df.empty else int(pet_df.nm.sum()):,}\nDone in {stats['runtime_sec']} s. Share {run_dir/'run_report.json'} for review.")
    return ttc_df,pet_df,stats


if __name__=="__main__": main()

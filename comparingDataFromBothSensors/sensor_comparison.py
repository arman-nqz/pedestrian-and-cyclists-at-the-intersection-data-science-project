# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Which sensor gives more reliable VRU trajectories: NewSense or Ouster?
#
# **Purpose.** At intersection K305 the team studies pedestrians and cyclists (VRUs). So far we have used the
# NewSense object list. It gives one physical object several track IDs and has flickering detections. An Ouster
# LiDAR object list exists for part of the morning of 29.10. This notebook compares the two sensors on the same
# time and place and builds a scorecard from the numbers. The recommendation at the end is generated from those
# numbers, so it reflects whichever run produced it.
#
# **Data used.**
# - NewSense object lists, 5-minute JSON files at 10 Hz, 29.10 07:20–11:25 CET, the same clock hours on 28.10, and
#   02:00–02:30 CET on 29.10 for the night check.
# - Ouster object lists, gzipped JSON lines at 10 Hz, 29.10 07:20–11:25 CET. The file `..._06-20-00` is skipped
#   because it starts with stale frames.
#
# **Key facts a reader needs.**
# - **Time.** Ouster file names give the *end* of their window in UTC. Data is always selected by timestamp, never
#   by file name. The Ouster clock runs about 0.08 s ahead of NewSense.
# - **Recalibration.** The Ouster was recalibrated at about 08:13 CET.
#   - **Epoch A** is 07:20–08:13 CET (secondary).
#   - **Epoch B** is 08:15–11:25 CET (primary).
#   - 08:13–08:15 CET is dropped from both sensors.
# - **Coordinates.** All positions are shown in the epoch-B Ouster frame, called the *common frame*:
#   - NewSense is moved into it with a fitted 2D rigid transform.
#   - Epoch-A Ouster data uses that transform composed with the inverse of the epoch-A transform.
# - **Variants.**
#   - *filtered* (primary): NewSense detections with score ≥ 0.25, and Ouster tracks with a known class.
#   - *raw*: all detections.
# - **No ground truth.** Neither sensor is ground truth. An unmatched detection is either a false detection by one
#   sensor or a miss by the other.
#
# **Run mode.** `sample` mode (the default) uses 10 minutes per epoch. That is enough to test the code but not
# to choose a sensor, so all sample results are **provisional**. Set `SENSOR_COMPARE_MODE=full` to run on all data.

# %% [markdown]
# ## 1. Setup and run mode

# %%
import os, time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
import sensor_compare as sc

RUN_MODE = os.environ.get("SENSOR_COMPARE_MODE", "sample")   # "sample" or "full"
cfg = sc.mode_config(RUN_MODE)
TAG = "(PROVISIONAL, sample)" if RUN_MODE == "sample" else "(full run)"
sc.plot_style()
pd.set_option("display.width", 160, "display.max_columns", 30, "display.precision", 3)
T_START = time.time()
print("run mode:", RUN_MODE, "| epochs:", {k: [str(sc.to_cet(v)) for v in r] for k, r in cfg["epochs"].items()})
if RUN_MODE == "sample":
    display(Markdown("**PROVISIONAL: sample mode, 10 minutes per epoch. Numbers below test the code; they do not decide between the sensors.**"))

# %% [markdown]
# Full mode loads 49 NewSense files for 29.10, 47 Ouster files, 6 night files and 49 NewSense files for 28.10.
# This check only lists those files and confirms they exist. It does not open them.

# %%
display(sc.check_full_mode_files())
FILES = sc.files_for_mode(RUN_MODE)
print({k: len(v) for k, v in FILES.items()})

# %% [markdown]
# ## 2. Loading, alignment validation and the common region
#
# Each source file is flattened once into Parquet in native coordinates (`output/cache/`). Transforms are applied
# in memory after loading. Missing caches are built here, with one progress line per file.

# %%
t0 = time.time()
all_files = sorted({p for v in FILES.values() for p in v})
build_info = sc.build_cache(all_files, max_workers=6)
T_CACHE = time.time() - t0
print(f"cache build: {T_CACHE:.0f} s, cache size {sc.cache_size_mb():.0f} MB")

# %%
t0 = time.time()
RAW = {"newsense": sc.load_sensor("newsense", FILES["newsense_29"], cfg["epochs"], day="29"),
       "ouster": sc.load_sensor("ouster", FILES["ouster"], cfg["epochs"], day="29")}
VAR = {(s, v): sc.make_variant(RAW[s], v) for s in sc.SENSORS for v in ["filtered", "raw"]}
for (s, v), sd in VAR.items():
    print(f"{s:9s} {v:8s} detections {len(sd.det):>9,d}  tracks {sd.det.trk.nunique():>7,d}  frames {len(sd.frames):>7,d}")
print("track IDs reused after >", sc.TRACK_SPLIT_GAP, "s silence (split into separate tracks):",
      {s: RAW[s].n_id_reuse_splits for s in sc.SENSORS})
print(f"load: {time.time() - t0:.0f} s, peak RSS {sc.rss_mb():.0f} MB")

# %% [markdown]
# ### Validation gates
# The gates run before any metric and stop the notebook if they fail.
#
# **Gate 1: alignment.** For each 5-minute window this is the share of NewSense vehicles faster than 4 m/s that
# have an Ouster vehicle within 1 m in the time-paired frame. Only paired frames count. Values around 0.8–0.9 mean
# the transforms and clocks line up.
# - The gate fails if the median over windows is below 0.70, or if any epoch-B window is below 0.50.
# - The figure also documents the recalibration: each epoch is aligned with its own transform.

# %%
ALIGN = sc.alignment_share(VAR[("newsense", "filtered")], RAW["ouster"])
sc.save_table(ALIGN, cfg, "gate1_alignment_per_window")
display(ALIGN)
GATE1 = sc.gate_alignment(ALIGN)
print(GATE1)
fig = sc.plot_alignment(ALIGN, TAG); sc.save_fig(fig, cfg, "gate1_alignment"); plt.show()

# %% [markdown]
# **Gate 2: clock offset.** The same share is computed for clock offsets from −0.30 to +0.30 s, on up to three
# epoch-B windows spread over the epoch. The best offset must lie between 0 and +0.15 s. After that, +0.08 s is
# used everywhere.
#
# At 10 Hz neighbouring offsets often select the same frame, so the curve has steps.

# %%
b_windows = np.sort(np.unique(sc._window_of(VAR[("newsense", "filtered")].det.query("epoch == 'B'").ts)))
scan_windows = np.unique(b_windows[np.round(np.linspace(0, len(b_windows) - 1, 3)).astype(int)])
SCAN = sc.clock_offset_scan(VAR[("newsense", "filtered")], RAW["ouster"], scan_windows)
sc.save_table(SCAN, cfg, "gate2_clock_offset_scan")
display(SCAN.pivot_table(index="offset", columns="window_cet", values="share"))
GATE2 = sc.gate_clock(SCAN)
print(GATE2)
fig = sc.plot_clock(SCAN, TAG); sc.save_fig(fig, cfg, "gate2_clock_offset"); plt.show()

# %% [markdown]
# **Gate 3: coverage.** After filtering, each sensor must have detections in every 5-minute window of both
# epochs. A shorter last window, such as epoch A ending at 08:13 in full mode, still has to contain data.

# %%
COVER = sc.gate_coverage({s: VAR[(s, "filtered")] for s in sc.SENSORS}, cfg["epochs"])
sc.save_table(COVER, cfg, "gate3_coverage")
display(COVER)
print("Gate 3 (coverage): passed")

# %% [markdown]
# ### Common region
# The Ouster sees about ±80 m and NewSense about ±40 m, so every comparison is restricted to the area both see.
# - **Region cells.** A 2 m cell belongs to the region if each sensor has enough moving detections there (speed
#   ≥ 1 m/s) in epoch B. The threshold is set by the run mode.
# - **Which data is used.** Detection-level metrics use detections inside the region. Track-level metrics use
#   tracks with at least half of their detections inside it.
# - **Reuse.** The same region is used for epoch A, the night check and 28.10.

# %%
REGION = sc.build_region(VAR[("newsense", "filtered")], VAR[("ouster", "filtered")], "B", cfg["region_min"])
VAR = {k: sc.add_region(sd, REGION) for k, sd in VAR.items()}
REG_TAB = pd.DataFrame([dict(sensor=s, variant=v, epoch=ep,
                             det_share_in_region=float(sd.det.loc[sd.det.epoch == ep, "in_region"].mean()),
                             tracks_in_region=int(sd.det.loc[(sd.det.epoch == ep) & sd.det.trk_in_region, "trk"].nunique()))
                        for (s, v), sd in VAR.items() for ep in sorted(cfg["epochs"])])
REG_TAB.insert(0, "region_cells", len(REGION.keys))
sc.save_table(REG_TAB, cfg, "common_region")
display(REG_TAB)
fig = sc.plot_region(REGION, VAR[("newsense", "filtered")], VAR[("ouster", "filtered")], "B", TAG)
sc.save_fig(fig, cfg, "common_region_map"); plt.show()

# %% [markdown]
# ## 3. Stream health
# Stream health is measured on the stream of emitted frames, before any track logic, and does not depend on the
# variant.
# - **Measures.** Frames per 5 minutes (3000 expected at 10 Hz, scaled for shorter windows), the share of frame
#   gaps above 0.15 s, duplicate timestamps (the second frame is dropped), and the longest gap.
# - **Reading the figure.** A ratio of 1.0 is a complete stream. Dips mean dropped frames, which also lower the
#   number of frames that can be paired across sensors.

# %%
HEALTH = pd.concat([sc.stream_health(RAW[s]) for s in sc.SENSORS], ignore_index=True)
HEALTH_W = pd.concat([sc.stream_health_windows(RAW[s]) for s in sc.SENSORS], ignore_index=True)
sc.save_table(HEALTH, cfg, "stream_health"); sc.save_table(HEALTH_W, cfg, "stream_health_per_window")
display(HEALTH)
fig = sc.plot_stream(HEALTH_W, TAG); sc.save_fig(fig, cfg, "stream_health"); plt.show()

# %% [markdown]
# ## 4. Single-sensor track quality
# Each sensor is judged on its own: per group, per epoch and per variant, on tracks in the common region. Lower
# is better for every panel.
#
# | Metric | What it measures |
# | :--- | :--- |
# | Flickering | Share of tracks shorter than 1 s |
# | Gaps inside tracks | Missing frames between a track's first and last detection, counted in the sensor's own emitted frames |
# | Class stability | Tracks that switch between known classes |
# | Implausible motion | Frame steps faster than 4 / 15 / 30 m/s for ped / bike / veh |
# | Jitter | RMS of the second difference of position, on tracks that move at least 3 m |
# | ID handovers | A track ends and, within 2 s, a new track of the same group starts within 1.5 m of the extrapolated position |
#
# - **Handovers** count ID switches that each sensor causes by itself.
# - **Shares near zero are good.** A handover rate of tens per 100 tracks means a VRU trajectory is regularly
#   split into several IDs.
# - **Built-in advantage.** NewSense reports one class and one score per track and does not report gaps inside a
#   track: it starts a new ID instead. So the gap and class-stability rows can favour NewSense by design rather
#   than by quality. The conclusion therefore checks the decision both with and without those rows.

# %%
t0 = time.time()
single_rows, TRACKS = [], {}
for (s, v), sd in VAR.items():
    m, tt = sc.single_sensor_metrics(sd, v)
    single_rows.append(m); TRACKS[(s, v)] = tt
SINGLE = pd.concat(single_rows, ignore_index=True)
order = {g: i for i, g in enumerate(sc.GROUPS)}
SINGLE = SINGLE.sort_values(["variant", "epoch", "group", "sensor"], key=lambda c: c.map(order) if c.name == "group" else c,
                            ascending=[True, False, True, True]).reset_index(drop=True)
sc.save_table(SINGLE, cfg, "single_sensor_metrics")
print(f"single-sensor metrics: {time.time() - t0:.0f} s")
display(SINGLE[SINGLE.variant == "filtered"].set_index(["epoch", "group", "sensor"]).drop(columns=["day", "variant"]).T)
fig = sc.plot_single(SINGLE, "B", "filtered", TAG); sc.save_fig(fig, cfg, "single_sensor_epochB"); plt.show()

# %% [markdown]
# ## 5. Cross-sensor comparison: same time, same place
# This is the core of the comparison. It uses the filtered variants, with epoch B as the primary result and epoch A
# as the secondary one.
# - **Frame pairing.** Each NewSense frame is paired with the Ouster frame nearest to `ts + 0.08 s`, if that frame
#   is within 0.06 s.
# - **Matching.** In each paired frame, detections are matched one-to-one on centre distance (Hungarian
#   assignment, class ignored, at most 2 m). The matched pairs are cached.

# %%
t0 = time.time()
NSF, OUF = VAR[("newsense", "filtered")], VAR[("ouster", "filtered")]
MATCHES, PSTATS, PAIR = sc.match_detections(NSF, OUF, RUN_MODE, "filtered")
sc.mark_matched(NSF, OUF, MATCHES, PAIR)
PAIR_TAB = pd.DataFrame([PSTATS]).assign(ns_unpaired_share=lambda d: d.ns_unpaired / d.ns_frames,
                                         median_match_dist_m=float(MATCHES["dist"].median()))
sc.save_table(PAIR_TAB, cfg, "frame_pairing")
display(PAIR_TAB)
print(f"matching: {time.time() - t0:.0f} s, peak RSS {sc.rss_mb():.0f} MB")

# %% [markdown]
# ### 5.1 Confirmation rate
# This is the share of a sensor's detections, in paired frames and inside the region, that the other sensor also
# reports within 2 m. It is split into moving tracks (net displacement ≥ 3 m) and static tracks.
# - **Reading the figure.** Higher is better.
# - **Caution.** An unmatched detection is either a false detection by this sensor or a miss by the other. The data
#   alone cannot tell which.
# - **Static tracks.** Low static rates may be ghosts on fixed structures, or people waiting whom the other sensor
#   misses.

# %%
CONF = pd.concat([sc.confirmation_rates(NSF, TRACKS[("newsense", "filtered")]),
                  sc.confirmation_rates(OUF, TRACKS[("ouster", "filtered")])], ignore_index=True)
sc.save_table(CONF, cfg, "confirmation_rates")
display(CONF.pivot_table(index=["epoch", "group", "motion"], columns="sensor", values="confirmation_rate")
        .sort_index(level=[0, 1], ascending=[False, True]))
fig = sc.plot_confirmation(CONF, "B", TAG); sc.save_fig(fig, cfg, "confirmation_epochB"); plt.show()

# %% [markdown]
# ### 5.2 Class agreement
# The confusion matrix of track groups over matched pairs in epoch B. Rows are NewSense groups, columns are Ouster
# groups. Mass off the diagonal means the sensors disagree on what the object is.

# %%
CONFUSION = {ep: sc.class_confusion(MATCHES, ep) for ep in sorted(cfg["epochs"])}
for ep, cm in CONFUSION.items():
    sc.save_table(cm, cfg, f"class_confusion_epoch{ep}", index=True)
display(CONFUSION["B"])

# %% [markdown]
# ### 5.3 ID fragmentation seen by the other sensor
# This measures the "several IDs for one object" complaint directly.
# - **Method.** For every track of one sensor with at least 30 matched detections, count the distinct IDs of the
#   *other* sensor that cover at least 5 of those matched frames.
# - **Attribution.** Ouster tracks that map to several NewSense IDs measure **NewSense** fragmentation. NewSense
#   tracks that map to several Ouster IDs measure **Ouster** fragmentation. The figure is labelled by the sensor
#   whose fragmentation is measured.
# - **Reading the figure.** Lower is better. Values near 0 mean one ID per object.

# %%
fr1, per1 = sc.fragmentation(MATCHES, "ou->ns", TRACKS[("ouster", "filtered")])
fr2, per2 = sc.fragmentation(MATCHES, "ns->ou", TRACKS[("newsense", "filtered")])
FRAG = pd.concat([fr1, fr2], ignore_index=True)
sc.save_table(FRAG, cfg, "fragmentation")
display(FRAG)
fig = sc.plot_fragmentation(FRAG, "B", TAG); sc.save_fig(fig, cfg, "fragmentation_epochB"); plt.show()

# %% [markdown]
# ### 5.4 Unconfirmed tracks and video-check candidates
# An unconfirmed track has under 10% of its paired-frame detections matched by the other sensor.
# - **Map.** Clusters at fixed places suggest ghosts on structures, or blind spots of the other sensor.
# - **Video-check list.** The 20 longest unconfirmed VRU tracks per sensor are written to
#   `video_check_candidates.csv`, so someone can check them against the Miovision video.

# %%
UN = pd.concat([sc.unconfirmed_tracks(NSF, TRACKS[("newsense", "filtered")]),
                sc.unconfirmed_tracks(OUF, TRACKS[("ouster", "filtered")])])
UN_SUM = sc.unconfirmed_summary(UN)
sc.save_table(UN_SUM, cfg, "unconfirmed_tracks")
VIDEO = sc.video_candidates(UN)
sc.save_table(VIDEO, cfg, "video_check_candidates")
display(UN_SUM)
print("video-check candidates per sensor:", VIDEO.groupby("sensor").size().to_dict())
fig = sc.plot_unconfirmed_map(UN, "B", TAG); sc.save_fig(fig, cfg, "unconfirmed_map_epochB"); plt.show()

# %% [markdown]
# ## 6. Night check for NewSense ghosts
# Static VRU tracks that only NewSense sees could be real people waiting whom the Ouster misses. They could also
# be false detections on poles and signs.
# - **Night data.** At night almost nobody is on the street, so static long VRU tracks there mark fixed-structure
#   ghosts. They are mapped on the same 2 m grid.
# - **Day comparison.** The table gives the share of daytime unconfirmed static VRU detections that fall into those
#   night cells. Confirmed static VRU detections are shown as a baseline.
# - **Reading the table.** An unconfirmed share well above the baseline points to ghosts.

# %%
NIGHT = sc.make_variant(sc.load_sensor("newsense", FILES["newsense_night"], cfg["night"], day="29N"), "filtered")
NIGHT_KEYS, NIGHT_ST = sc.night_static_cells(NIGHT)
NIGHT_TAB = sc.night_overlap(NSF, TRACKS[("newsense", "filtered")], NIGHT_KEYS)
NIGHT_TAB.insert(0, "night_static_vru_tracks", len(NIGHT_ST)); NIGHT_TAB.insert(1, "night_cells", len(NIGHT_KEYS))
sc.save_table(NIGHT_TAB, cfg, "night_check")
display(NIGHT_TAB)
fig = sc.plot_night(NIGHT_ST, NSF, TRACKS[("newsense", "filtered")], TAG); sc.save_fig(fig, cfg, "night_check_map"); plt.show()

# %% [markdown]
# ## 7. VRU counts per 5 minutes
# A valid traversal is a `ped` or `bike` track that lasts at least 2 s and moves at least 3 m. It is counted in the
# window where it starts.
# - **Reading the figures.** The counts should track each other over time, and the per-window points should sit
#   near the diagonal.
# - **Caution.** A sensor that fragments tracks counts *higher*, so a higher count is not better by itself.

# %%
COUNTS = pd.concat([sc.vru_counts(TRACKS[(s, "filtered")], s) for s in sc.SENSORS], ignore_index=True)
sc.save_table(COUNTS, cfg, "vru_counts_per_5min")
display(COUNTS.pivot_table(index=["epoch", "group"], columns="sensor", values="n", aggfunc="sum")
        .sort_index(ascending=[False, True]))
fig = sc.plot_counts(COUNTS, TAG); sc.save_fig(fig, cfg, "vru_counts"); plt.show()

# %% [markdown]
# ## 8. NewSense on 28.10 versus 29.10
# The Ouster has no data on 28.10, so a same-time comparison is not possible on that day. The single-sensor
# metrics are computed for NewSense on 28.10 and shown next to the 29.10 NewSense values for the same clock hours.
# - **Reading the figure.** Similar bars mean the NewSense behaviour seen on 29.10 is typical. Large differences
#   mean one day is unusual.

# %%
d28_ranges = cfg["day28"]
RAW28 = sc.load_sensor("newsense", FILES["newsense_28"], d28_ranges, day="28")
rows28 = []
for v in ["filtered", "raw"]:
    sd = sc.add_region(sc.make_variant(RAW28, v), REGION)
    rows28.append(sc.single_sensor_metrics(sd, v)[0])
S28 = pd.concat(rows28, ignore_index=True)
S29 = SINGLE[(SINGLE.sensor == "newsense") & SINGLE.epoch.isin(list(d28_ranges))]
DAY_CMP = pd.concat([S28, S29], ignore_index=True)
H28 = sc.stream_health(RAW28)
sc.save_table(DAY_CMP, cfg, "newsense_28_vs_29"); sc.save_table(H28, cfg, "stream_health_newsense_28")
display(DAY_CMP[DAY_CMP.variant == "filtered"].set_index(["epoch", "group", "day"]).drop(columns=["sensor", "variant"])
        .sort_index().T)
fig = sc.plot_day28(DAY_CMP[DAY_CMP.variant == "filtered"], TAG); sc.save_fig(fig, cfg, "newsense_28_vs_29"); plt.show()

# %% [markdown]
# ## 9. Scorecard and conclusion
# The scorecard has one row per metric, group, epoch and variant.
# - **Columns.** Each row gives the NewSense value, the Ouster value, the direction that is better, the number of
#   tracks behind each value, and the better sensor.
# - **Unscored rows.** Context rows (counts, static tracks) and rows with too few tracks are not scored.
# - **Ties.** Values within 5% of each other are ties.
# - **Fragmentation rows.** These are already attributed to the sensor whose fragmentation they measure.

# %%
SCORE = sc.build_scorecard(SINGLE, FRAG, CONF, COUNTS)
sc.save_table(SCORE, cfg, "scorecard")
display(SCORE[(SCORE.variant == "filtered") & (SCORE.epoch == "B") & SCORE.group.isin(sc.VRU)]
        [["metric", "group", "newsense", "ouster", "n_newsense", "n_ouster", "direction", "better"]])

# %% [markdown]
# The next cell builds the conclusion from the scorecard of this run.
# - **Decision rows.** The `ped` and `bike` rows of the filtered variant in epoch B, scored metrics only.
# - **Rule.** A sensor is recommended only if it is better on at least two thirds of the comparable rows and does
#   not lose the fragmentation rows. Both conditions must hold with and without the gap and class-stability rows.
#   Otherwise the evidence is reported as mixed, with the split.
# - **Vehicle rows** are shown as context only, because the project is about VRUs.

# %%
SUMMARY = sc.decide(SCORE, RUN_MODE)
print(SUMMARY)
with open(cfg["out"] / "tables" / "conclusion.txt", "w") as f:
    f.write(SUMMARY + "\n")
print(f"\ntotal notebook time {time.time() - T_START:.0f} s (cache build {T_CACHE:.0f} s), peak RSS {sc.rss_mb():.0f} MB, "
      f"cache {sc.cache_size_mb():.0f} MB")

# %% [markdown]
# ### Limits (they hold in both run modes)
# - **Short window.** The full comparison covers about four hours of one morning (29.10, 07:20–11:25 CET). Sample
#   mode covers only 10 minutes per epoch.
# - **No ground truth.** There is no independent ground truth. Unmatched detections are ambiguous: they are either
#   false detections by one sensor or misses by the other. The video-check list is the way to resolve them.
# - **Ouster reconfiguration.** The Ouster was being reconfigured that morning:
#   - it was recalibrated at 08:13 CET, so epoch A uses a different transform;
#   - it dropped frames frequently before about 08:05 CET.
# - **Untested conditions.** Night, rain and the afternoon peak are untested for the Ouster.
# - **Transform accuracy.** The rigid transforms were fitted on moving vehicles. A residual misalignment of a few
#   decimetres affects the 2 m matching gate very little, but it slightly favours large objects.

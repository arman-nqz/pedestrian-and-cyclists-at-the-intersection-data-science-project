"""Video check: watch the disputed NSE / Ouster moments in both cameras and record what really happened."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from lib import data, sensor_pair as sp, video  # noqa: E402

RESULTS = data.ROOT.parent / "comparingDataFromBothSensors" / "video_check" / "results.csv"
SCORECARD = data.ROOT.parent / "comparingDataFromBothSensors" / "output" / "full" / "tables" / "scorecard.csv"
PAD_BEFORE, PAD_AFTER = 10, 5  # seconds around the check; the video file starts 1 s after the full hour
YES_NO = ["yes", "no", "unclear"]
OPTIONS = {  # answers per check; the first words match the guide in comparingDataFromBothSensors/VIDEO_CHECK_GUIDE.md
    "frag": ["1 person", "2 people", "group", "unclear"],
    "stand": ["someone standing", "nobody", "object (pole, box, sign)", "unclear"],
    "real": YES_NO,
    "O7": ["2 people", "1 person", "other", "unclear"],
    "O6": ["pedestrian", "scooter or motorcycle", "cyclist", "nothing", "unclear"],
}
st.set_page_config(page_title="Video check - K305", layout="wide")
st.title("Video check: NSE vs Ouster")
st.caption("Each check is a moment where the two sensors disagree; the video is the only independent truth. Answers are "
           "saved to `results.csv`. If unsure, answer *unclear* and say why.")

def kind(row):
    if row["id"] in OPTIONS:
        return row["id"]
    return {"fragmentation": "frag", "fragmentation (crowd)": "frag", "static spot": "stand"}.get(row["check_type"], "real")


if not RESULTS.exists():
    st.error(f"`{RESULTS.relative_to(data.ROOT.parent)}` is missing (it comes with the `comparingDataFromBothSensors` folder).")
    st.stop()
df = pd.read_csv(RESULTS, dtype=str, keep_default_na=False)
df["kind"] = df.apply(kind, axis=1)

# --- progress (sidebar) and pick a check
done = df[df["answer"] != ""]
decided = done[done["answer"] != "unclear"]
frag = decided[decided["kind"] == "frag"]
st_ = decided[decided["kind"] == "stand"]
low = decided[decided["id"].isin(["N7", "N8"])]
video.offset_controls()
with st.sidebar:
    st.markdown("### Check")
    prios = st.multiselect("Priority", sorted(df["priority"].unique()), default=["1"])
    only_open = st.checkbox("Only unanswered", value=False)
    st.markdown("### Progress")
    st.metric("Checks answered", f"{len(done)} of {len(df)}")
    st.metric("Fragmentation: one person", f"{(frag['answer'] == '1 person').sum()} of {len(frag)}",
              help="If the isolated cases (O1 to O3) show one person each, NSE really splits one person into several ids.")
    st.metric("Standing spots: nobody or object", f"{st_['answer'].str.startswith(('nobody', 'object')).sum()} of {len(st_)}",
              help="Nobody or an object means a ghost in NSE; someone standing means real people that Ouster ignores.")
    st.metric("Low-score NSE tracks that are real", f"{(low['answer'] == 'yes').sum()} of {len(low)}",
              help="If real, the 0.25 score filter is too strict.")
sub = df[df["priority"].isin(prios)]
if only_open:
    sub = sub[sub["answer"] == ""]
if sub.empty:
    st.info("No checks match the filter.")
    st.stop()
label = {r["id"]: f"{r['id']}  {r['cet_start']}  ({r['check_type']})" + ("  ✓" if r["answer"] else "") for _, r in sub.iterrows()}
c1, c2 = st.columns([1, 3])
cid = c1.selectbox("Check", list(label), format_func=label.get)
row = df[df["id"] == cid].iloc[0]
t0, t1 = video.parse_hms(row["cet_start"]), video.parse_hms(row["cet_end"])
c2.markdown(f"**{row['id']}: {row['question']}**  \n{row['track']}, {row['cet_start']} to {row['cet_end']} ({t1 - t0} s), "
            f"position ({row['x_m']}, {row['y_m']}) m in the comparison frame.")
x, y = sp.common_to_nse(float(row["x_m"]), float(row["y_m"]))
w0, w1 = t0 - PAD_BEFORE, t1 + PAD_AFTER
day = data.meta()["day"] if (data.DATA / "meta.json").exists() else "2026-10-29"
paths = {cam: video.video_for(day, w0 + video.SENSOR_OFFSET_S, cam) for cam in video.CAMERAS}
voff = [off - 1 for p, off in paths.values() if p is not None] or None  # per shown video; files start 1 s after the hour
with st.spinner("Loading both sensors ..."):
    win = sp.window(w0, w1, float(x), float(y))
if win["note"]:
    st.caption(f":orange[{win['note']}]")

left, right = st.columns([1.15, 1])
with left:
    # our own HTML (assets/pair_player.html); st.iframe keeps same-origin access for the video sync
    st.iframe(sp.player_html(win, w0, (t0 - w0, t1 - w0), float(x), float(y), voff), height="content")
with right:
    cams = st.columns(2)
    for col, cam in zip(cams, video.CAMERAS):
        path, off = paths[cam]
        with col:
            st.caption(f"Camera {cam}")
            if path is None:
                st.info("Video not found in `database/miovision`.")
            else:
                st.video(str(path), start_time=max(0, off - 1), muted=True)
    st.caption("The videos follow the player's clock. Use the time printed in the picture; clocks may differ by a few seconds.")
    opts = OPTIONS[row["kind"]]
    cur = row["answer"]
    ans = st.radio("Your answer", opts, index=opts.index(cur) if cur in opts else None, horizontal=True)
    cam_opts = ["", "both", "SCU3K2", "SCU4YV"]
    a1, a2 = st.columns([1, 2])
    cam = a1.selectbox("Best camera", cam_opts, index=cam_opts.index(row["camera"]) if row["camera"] in cam_opts else 0)
    note = a2.text_input("Notes", value=row["notes"], placeholder="glare, too far, hidden behind a truck, how many people ...")
    if st.button("Save answer", type="primary", disabled=ans is None):
        df.loc[df["id"] == cid, ["answer", "camera", "notes"]] = [ans, cam, note]
        df.drop(columns="kind").to_csv(RESULTS, index=False)
        st.success(f"Saved {cid}.")
        st.rerun()

with st.expander("What the answers mean"):
    st.markdown(
        "- **Fragmentation (O1 to O3):** one person means NSE really splits one person into several ids, so Ouster is the "
        "better choice for trajectories. A group means Ouster merged people and the fragmentation result is weaker. "
        "O4 and O5 test the same in crowds.\n"
        "- **Standing spots (N1 to N4, N6):** nobody or an object means NSE ghosts; people waiting is a real point for NSE.\n"
        "- **Low-score tracks (N7, N8):** a real person means our 0.25 filter is too strict and NSE's confirmation advantage "
        "was overstated; nobody means the filter is justified.\n"
        "- **O7:** two people means NSE merged a pair. **N5, O6, O8 to O10:** a real person seen by only one sensor shows "
        "that the other one missed it.")
if SCORECARD.exists():
    with st.expander("Sensor scorecard (full run)"):
        sc = pd.read_csv(SCORECARD)
        sc = sc[(sc["scored"]) & (sc["epoch"] == "B") & (sc["variant"] == "filtered") & sc["group"].isin(["ped", "bike"])]
        st.dataframe(sc[["metric", "group", "newsense", "ouster", "better"]], hide_index=True, width="stretch")

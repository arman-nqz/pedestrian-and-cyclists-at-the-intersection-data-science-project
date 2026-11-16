# Video check: step-by-step guide

**Goal:** watch a few short moments of the Miovision video and write down what really happened. The video is the
only independent "truth" we have, so these checks settle the open questions from `REVIEW_full_results.md`:

1. **Fragmentation.** Does NewSense really give **one** person several IDs?
2. **Standing "pedestrians".** Are the NewSense standing pedestrians real people, or false detections ("ghosts")?
3. **Low-confidence tracks.** Are the NewSense tracks with a low score (below 0.25) real people?

**Time needed:** about 45 minutes for the 5 priority-1 checks, and about 2 hours for all 18.

Everything you need is in the `video_check/` folder:

| File | What it is |
| :--- | :--- |
| `video_check/play.sh` | Opens the video at the right moment. You only type the time. |
| `video_check/video_check_map.png` | Map of where each check is, next to a picture from each camera |
| `video_check/results.csv` | The sheet where you write your answers (opens in LibreOffice Calc) |

---

## Step 0: things to know first (2 minutes)

- **There are two cameras.** `SCU3K2` and `SCU4YV` look at the intersection from different sides. A spot may be
  visible in only one of them, so always check both.
- **The time is printed in the picture.** It is in the bottom-right corner, for example `2026-10-29 08:16:21`. This
  is CET, the same time zone as our tables. Use this printed time and ignore the player's own timer.
- **There is one video file per hour.** `.001` is 06:00–07:00, `.002` is 07:00–08:00, `.003` is 08:00–09:00, and
  so on up to `.007` for 12:00–13:00. The script picks the right file for you.
- **The sensor clock and the video clock may differ by a few seconds.** That doesn't matter much, because every
  check lasts 15 s or longer. The script starts 10 s early so you don't miss anything.
- **The picture quality is low** (720 × 480), with sun glare in the morning. Pause and go frame by frame when
  people are small.

## Step 1: learn where the spots are (5 minutes)

1. Open `video_check/video_check_map.png`.
2. The **left** side is a bird's-eye map in the sensors' coordinates:
   - grey lines are car lanes;
   - green lines are where pedestrians and cyclists walk and ride;
   - each circle is one check (blue = NewSense question, orange = Ouster question).
3. The **right** side shows one picture from each camera.
4. Find the same road shapes in both, so you know which part of the map each camera shows. Useful landmarks:
   - the **curved slip road**, the arc in the lower middle of the map (around x = −10 to 10, y = −20), is the curve
     you can see in camera `SCU4YV`;
   - the **big diagonal road** through the middle of the map is the main road with many lanes;
   - spot **N1/N2** at (−16.3, 1.8) is in the **middle of the road**, between car lanes. Look for a traffic island,
     a pole or a signal box there.
5. **Tip:** do this once. When you open the first check, find its spot in the video, and the others become easy.

## Step 2: open a check (1 minute each)

Open a terminal and go to the folder:

```bash
cd "/home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project/comparingDataFromBothSensors/video_check"
```

Type `./play.sh` followed by the **start time** from the table in step 3:

```bash
./play.sh 08:16:18          # opens both cameras (two windows), 10 s before 08:16:18
./play.sh 08:16:18 3K2      # only camera SCU3K2
./play.sh 08:16:18 4YV      # only camera SCU4YV
```

**Player keys (mpv):**

| Key | Action |
| :--- | :--- |
| `Space` | Pause or play |
| `←` / `→` | Jump back or forward 5 s |
| `,` / `.` | One frame back or forward (while paused) |
| `[` / `]` | Slower or faster |
| `f` | Full screen |
| `q` | Close |

If `play.sh` does not work, open the file by hand in VLC. The files are in
`database/Data from date of 28.10, 29.10./mio vision/miovision/K305/2026_10_29/Standard_SCU3K2_2026-10-29_0600/`. Take
the `.00N.mp4` for the hour you need, and jump to minute:second.

## Step 3: do the checks, in this order

For each check:
1. Run `./play.sh <start time>`.
2. Find the spot (use the map).
3. Watch until the end time.
4. Write your answer in `results.csv`, in the `answer`, `camera` and `notes` columns.

### Priority 1: do these first (about 45 minutes)

| ID | Start | End | Where (map) | What to look at | Write down |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **O1** | 08:16:18 | 08:16:34 | O1, north side (−7, 15) | One person walking. NewSense gave this one track 5 different IDs. | How many people walk there: **1**, **2** or **group** |
| **O2** | 08:17:10 | 08:17:41 | O2, west side (−36, −5) | Same question. NewSense gave 7 IDs. | **1**, **2** or **group** |
| **N1** | 09:02:54 | 09:06:17 | N1/N2, middle of the road (−16, 2) | NewSense says a person stood here for 3 minutes. The Ouster saw nothing. | **Someone standing** (how many?), **nobody**, or **object** (pole, box, sign) |
| **N3** | 08:30:56 | 08:33:03 | N3/N4, east side (19, 1) | NewSense says a person stood here. NewSense also "sees" someone here at night. | **Someone standing**, **nobody** or **object** |
| **N7** | 09:48:31 | 09:50:20 | N7, south-west corner (−28, −13) | The Ouster saw a pedestrian walking. NewSense saw it only with low confidence (0.21). | **Real person walking: yes/no** |

### Priority 2: if you have time (about 45 minutes)

| ID | Start | End | Where | What to look at | Write down |
| :--- | :--- | :--- | :--- | :--- | :--- |
| O3 | 10:13:49 | 10:14:46 | O3, east (20, 7) | One person? NewSense gave 6 IDs | **1**, **2** or **group** |
| O4 | 08:28:00 | 08:28:22 | O4, south-west (−29, −12) | Busy corner. One person, or a group walking together? | **1** or **group (how many)** |
| O5 | 09:17:50 | 09:18:00 | O5, south-west (−32, −20) | Same as O4 | **1** or **group (how many)** |
| N2 | 08:46:28 | 08:48:32 | N1/N2 (−16, 2) | Second look at the middle-of-road spot | **Standing**, **nobody** or **object** |
| N8 | 08:33:14 | 08:34:30 | N8, south (−10, −26) | Same as N7, another sidewalk | **Real person walking: yes/no** |
| O7 | 09:25:17 | 09:26:27 | O7, south-west (−31, −16) | The Ouster sees **two** people walking side by side. Is that true? | **2 people**, **1 person** or **other** |

### Priority 3: optional

| ID | Start | End | Where | What to look at | Write down |
| :--- | :--- | :--- | :--- | :--- | :--- |
| N5 | 10:06:19 | 10:08:41 | N5, west (−33, −10) | NewSense says a cyclist is moving; the Ouster saw nothing | **Cyclist yes/no** |
| O6 | 11:15:29 | 11:16:38 | O6, south (−10, −26) | The Ouster says pedestrian; NewSense says "motorcycle" | **Pedestrian**, **scooter or motorcycle**, **cyclist** or **nothing** |
| O8 | 10:44:40 | 10:46:29 | O8, south (1, −19) | The Ouster says pedestrian; NewSense barely saw it | **Real person yes/no** |
| N4 | 08:06:19 | 08:10:05 | N3/N4 (19, 1) | Same spot as N3, earlier | **Standing**, **nobody** or **object** |
| N6 | 07:24:14 | 07:25:58 | N6, south-west (−29, −12) | NewSense standing person | **Standing**, **nobody** or **object** |
| O9 | 07:41:07 | 07:43:21 | O9, south-east (7, −12) | The Ouster says pedestrian; NewSense nothing | **Real person yes/no** |
| O10 | 07:40:17 | 07:42:26 | O10, south-west (−27, −16) | The Ouster says pedestrian; NewSense nothing | **Real person yes/no** |

**If you are not sure, write "unclear"** and say why in `notes`, for example "glare", "too far", "hidden behind a
truck" or "not visible in either camera". An honest "unclear" is better than a guess.

## Step 4: what your answers mean

| If you see… | It means… | Effect on the decision |
| :--- | :--- | :--- |
| O1, O2 (and O3) show **1 person** | NewSense really splits one person into many IDs | **Confirms the fragmentation problem**, so Ouster is the better choice for trajectories |
| O1, O2 show **a group** | The Ouster merged several people into one track | The fragmentation result is weaker; NewSense may be partly right |
| O4, O5 show **a group** | In crowds the Ouster merges people | Fragmentation in crowds is partly an Ouster problem; isolated cases (O1–O3) still count |
| N1 (and N2): **nobody** or **an object** | NewSense ghost in the middle of the road | NewSense has many false standing pedestrians, so this counts against NewSense |
| N1 (and N2): **people waiting** (for example on an island) | Real people the Ouster ignores when they stand still | **Counts for NewSense** for "where do people wait". Important to report |
| N3: **nobody** | Ghost at a fixed object (this spot also "has people" at night) | Confirms that NewSense produces false detections |
| N7, N8: **real person** | NewSense's low-confidence tracks are real people | Our 0.25 filter is too strict; the confirmation advantage of NewSense was overstated |
| N7, N8: **nobody** | Low-confidence NewSense tracks are noise | The filter is justified |
| O7: **2 people** | NewSense merged a pair into one | Another point against NewSense |
| O6, O8–O10: **real person** | NewSense missed real pedestrians (often far from its sensor) | Counts for the Ouster (coverage) |

## Step 5: summarise (10 minutes)

When you are done, count your answers into one short summary, for example:

> Video check (29.10, N checks): fragmentation cases O1–O3 showed 3/3 single people, so NewSense splits one person
> into several IDs. The middle-of-road spot (N1, N2) showed nobody / people waiting. Low-confidence NewSense tracks
> (N7, N8) were 2/2 real people.

Put that summary in your presentation, on the slide with the open points or the recommendation. Then:
- give the filled `results.csv` to Claude to update `REVIEW_full_results.md` and the recommendation; or
- update AGENT.md, section 2 ("Video check of disputed tracks"), yourself.

## Troubleshooting

| Problem | Fix |
| :--- | :--- |
| `permission denied` when running `./play.sh` | Run `chmod +x play.sh` once, or start it with `bash play.sh 08:16:18` |
| The video opens at the wrong time | Check the time stamp in the picture and use `←` / `→` to move to the right moment. Each file starts 1 s after the full hour. |
| I can't find the spot | Pause, compare with `video_check_map.png`, and try the other camera. If neither camera shows it, write "not visible". |
| Two windows open on top of each other | Drag one to the side, or open one camera at a time (`./play.sh 08:16:18 3K2`) |
| Time doesn't match: the event happens a few seconds earlier or later | That's normal (clock difference); just watch a bit longer |

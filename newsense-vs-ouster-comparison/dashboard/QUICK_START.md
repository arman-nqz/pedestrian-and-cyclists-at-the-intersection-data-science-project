# Quick start: running the K305 dashboard

This guide is for anyone, with no programming needed. The dashboard runs **on your own computer** and opens in your web browser. It is not a website, so it works without an account and stays private to your computer.

You need about **15 minutes the first time**, with an internet connection. After that it starts in under a minute.

---

## Step 1: Install Python (once)

1. Go to **https://www.python.org/downloads/** and download **Python 3.12** for your system.
2. Run the installer.
   * **Windows:** on the first screen, tick **"Add python.exe to PATH"**, then click *Install Now*.
   * **Mac:** click through the installer with the default options.

If Python 3.11 or newer is already installed, you can skip this step.

## Step 2: Download the dashboard (once)

1. Open the project page on GitHub: https://github.com/arman-nqz/pedestrian-and-cyclists-at-the-intersection-data-science-project
2. Choose the branch **`feature/newsense-vs-ouster-comparison`** (the button that says *main*, top left), until it is merged.
3. Click the green **Code** button, then **Download ZIP**.
4. Unzip it, for example into your *Documents* folder.
5. Open the folder **`newsense-vs-ouster-comparison` → `dashboard`**. Everything you need is in there.

## Step 3: Add the camera videos (optional, recommended for presenting)

The dashboard shows the original camera footage next to the sensor data. The videos are **not** on GitHub. Get the **4 video files** from the person who shared this project, via USB stick or shared drive:

```
Standard_SCU3K2_2026-10-29_0600.002.mp4
Standard_SCU3K2_2026-10-29_0600.003.mp4
Standard_SCU4YV_2026-10-29_0600.002.mp4
Standard_SCU4YV_2026-10-29_0600.003.mp4
```

Copy them into the folder **`dashboard/videos/`** (≈ 710 MB). Do not rename them.

Without the videos, everything else works: all pages, charts, maps, results and presentation mode. Only the video panels stay empty.

## Step 4: Start

* **Mac:** double-click **`START_DASHBOARD.command`**.
  * If macOS says it "cannot be opened because it is from an unidentified developer", **right-click** the file, choose **Open**, then **Open** again. On newer macOS versions you may instead have to go to *System Settings → Privacy & Security* and click **Open Anyway**.
* **Windows:** double-click **`START_DASHBOARD.bat`**.
  * If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**.

A black window opens. **The first time**, it installs what the dashboard needs, which takes a few minutes. Then your browser opens the dashboard automatically. If it doesn't, open **http://localhost:8501**.

**Keep the black window open** while you use the dashboard. To stop, close that window.

The black window lists what it found, for example `Camera videos: 4 of 4 found`.

---

## Presenting

The left sidebar has all pages:

| Section | Page | Use it to show |
|---|---|---|
| | **Home** | what the project is, the two sensors, the cameras |
| Explore | **Watch the Sensors** | any moment of the video with both sensors' detections |
| | **Follow One Person** | one pedestrian/cyclist followed in the video and on both sensor maps. Use the 5 example buttons. |
| Compare Sensor Performance | **Key results**, **Detection & classification**, **Tracking**, **Movement paths**, **Where objects are seen**, **Potential conflicts** | the findings, each with its main message first |
| Understand the Research | **How the research works**, **Data quality & limitations** | method and honest limitations |
| | **Presentation mode** | a guided, step-by-step story for an audience, with a large video and no clutter |

**Tips**

* For the meeting, open **Presentation mode** (last item in the sidebar). It walks through the question, the method, five examples, the results and the limits.
* In the video player: **Play/Pause** (space bar), **◀ / ▶** for one frame, **Previous/Next event**, and click on the timeline to jump.
* Wording, as used in the research: sensor *agreement* is not *accuracy*, and "potential conflicts" are **not** confirmed near-misses.
* Rehearse once before the meeting. The very first start takes the longest.

## If something goes wrong

| Problem | Solution |
|---|---|
| "Python 3.11 or newer is not installed" | do Step 1, then start again |
| "Installing the packages failed" | check the internet connection and start again (only needed the first time) |
| Browser shows "This site can't be reached" | wait 10–20 seconds and reload. The black window must still be open. |
| Video panels empty | Step 3: the 4 files must be directly inside `dashboard/videos/` with their original names. Restart afterwards. |
| Something else | close the black window and start again. Rebooting also helps. |

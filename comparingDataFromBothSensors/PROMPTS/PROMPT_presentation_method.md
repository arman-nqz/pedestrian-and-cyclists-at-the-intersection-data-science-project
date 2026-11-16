# Task: build a simple presentation (and a presenter guide) on HOW we compared NewSense and Ouster

## Context

We study pedestrians and cyclists (VRUs) at intersection K305. Two sensors watch
the same intersection at the same time: **NewSense** and **Ouster** (LiDAR). I
compared their object lists for the morning of 29.10 to find out which sensor
reports better data, so the team can keep using that sensor from now on.

I have to present this work. A colleague gives a separate, full presentation of
the **results**. My presentation is about **how we got to those results**:

- **On what basis** we compared the two sensors: what exactly we measured.
- **The logic behind each basis**: why that measurement tells us which sensor
  is better.
- How the separate measurements were combined into one verdict.
- At the end, a **very short summary of what we found, in very simple
  language**.

The audience is not necessarily technical. The deck must be simple, easy to
follow and not overloaded with numbers, formulas or jargon.

## The most important rule: do not invent anything

Use only what is in this directory. Every statement, metric name, threshold,
number and conclusion in the deck and the guide must come from one of the
source files listed below, and you must be able to name that file.

- Do not add metrics, checks, motivations or conclusions that the sources do
  not contain, even if they seem reasonable.
- Where a source explains the reason for a choice, use that reason. Where it
  does not, describe what was done without making up a reason, and add the
  point to the "Open questions for the presenter" list in the guide.
- Analogies are allowed only to make an existing idea easier to understand.
  They must not add any new fact or claim.
- If two sources disagree, follow the code (`sensor_compare.py`) for what was
  actually done and `REVIEW_full_results.md` for how the results should be
  interpreted, and note the disagreement in the guide.

## Read these first, in this order

`ROOT = /home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project`.
All paths below are under `ROOT/comparingDataFromBothSensors/`. Parent
directory names contain spaces and a trailing dot, so quote paths in the shell.

1. `AGENT.md`: the handover guide. Goal, data facts, the method in brief, the
   decision rule, full-run results and caveats. This is your main map.
2. `PROMPTS/PROMPT_sensor_comparison.md`: the original method specification,
   with the reasoning behind the design. (Older files refer to it without the
   `PROMPTS/` folder; it was moved there.)
3. `sensor_compare.py` and `sensor_comparison.py`: the code and the notebook
   source. Use them to confirm what was actually implemented (constants at the
   top of `sensor_compare.py`, the gates, the metrics, `decide()`). Do not
   read the `.ipynb` JSON; the `.py` source and the outputs contain the same
   information.
4. `output/full/tables/conclusion.txt` and `output/full/tables/scorecard.csv`:
   the generated verdict and the per-metric scorecard.
5. `REVIEW_full_results.md`: the independent review of the full results. Use it
   for the caveats and for the plain-language final summary.
6. `output/full/figures/*.png` (11 figures): look at them and reuse the ones
   that help explain the method.
7. `VIDEO_CHECK_GUIDE.md`: only to mention the video check as the next step.

## What the deck should cover

This is a suggested storyline, not a fixed list. Build the actual content
from the sources; if this outline and the sources disagree, the sources win.
Aim for about 10–14 slides, one idea per slide.

1. **The question and why it matters.** Which sensor gives more reliable VRU
   trajectories, and the known complaints about NewSense (from `AGENT.md`).
2. **The data.** Same intersection, same time window, the two epochs (which
   is primary and why), the object lists of both sensors.
3. **Making the two data sets comparable before comparing them.** The checks
   that had to pass before any comparison is fair (alignment, clock offset,
   coverage), the common region, the variants, and how frames of the two
   sensors were paired and objects matched. For each step: what it is and why
   it is needed, in plain words.
4. **The bases of comparison.** For each family of measurements in the
   sources (for example stream health, single-sensor track quality, whether
   one sensor confirms the other's objects, class agreement, fragmentation):
   - what we measured, in one sentence;
   - why it shows which sensor is better, in one sentence;
   - which sensor "wins" when the value is higher or lower.
   Group them so the audience is not given a long list of metric names.
5. **How the measurements become one verdict.** The decision rule as it is
   implemented in `decide()` and described in `AGENT.md`, explained simply,
   including why some rows are also checked without the rows that one sensor
   cannot lose by design.
6. **Extra checks that support the comparison.** The supporting checks in the
   sources (for example the night check, 28.10 vs 29.10, VRU counts), each in
   one line: what it checks and why.
7. **Limits of the method.** The caveats stated in `AGENT.md` and
   `REVIEW_full_results.md`, in plain words.
8. **What we found, very simply.** A few short sentences a non-expert can
   follow, consistent with `conclusion.txt` and `REVIEW_full_results.md`. Keep
   it brief; the colleague presents the details.
9. **Next step.** The video check, as described in `VIDEO_CHECK_GUIDE.md`.

## Style

- Simple language, short sentences, few words per slide. Prefer a figure or a
  simple diagram over text.
- Keep numbers to a minimum, because this is a method talk. When you show a
  number, label it with its epoch, variant and group, and take it unchanged
  from the sources.
- Reuse the existing figures from `output/full/figures/`. Do not create plots
  that need new data processing.
- Every slide has speaker notes.

## Deliverables

Create the folder `comparingDataFromBothSensors/presentation/` with:

| File | Content |
| :--- | :--- |
| `sensor_comparison_method.pptx` | The deck (use the pptx skill), with speaker notes on every slide. |
| `PRESENTATION_GUIDE.md` | How to present it, see below. |

`PRESENTATION_GUIDE.md` must contain:

1. **Overview**: the message of the talk in two or three sentences and the
   total time (about 10–15 minutes).
2. **Slide by slide**: for each slide, what to say in plain talking points,
   the approximate time, and the source file(s) the content comes from.
3. **Handover to the colleague**: where my talk ends and the results
   presentation begins, and one sentence to hand over.
4. **Likely questions and answers**: questions the audience may ask about the
   method, each answered only from the sources (name the source).
5. **Open questions for the presenter**: anything the sources do not explain
   or where they disagree, so I can fill it in myself. Write "none" if there
   are none.

## Rules

- Do not rerun the notebook or any analysis, and do not read the raw data in
  `ROOT/database/` or the Parquet caches. Everything you need is in the files
  listed above.
- Do not modify any existing file, including `output/`. Only create the
  `presentation/` folder and its two files.
- If you need Python (for example to read a CSV or build the `.pptx`), use
  `comparingDataFromBothSensors/.venv/bin/python` or the environment the pptx
  skill sets up. The repo-root `.venv` is broken. Print only aggregates, never
  raw data rows.
- No git: do not commit or push anything.

## Final reply

Reply with a short summary of the deck's storyline, the paths to both files,
and the open questions, if any.

#!/usr/bin/env bash
# Open the Miovision video of 29.10 at a given CET time, 10 s early, in both cameras.
# Usage:  ./play.sh 09:02:54          (both cameras, two windows)
#         ./play.sh 09:02:54 3K2      (one camera: 3K2 or 4YV)
# Clips: .001 = 06:00, .002 = 07:00, ... .007 = 12:00 CET. Each clip starts 1 s after the full hour
# (check the time stamp burned into the bottom right of the picture).
set -euo pipefail
V="/home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project/database/Data from date of 28.10, 29.10./mio vision/miovision/K305/2026_10_29"
t="${1:?give a CET time like 09:02:54}"
IFS=: read -r hh mm ss <<< "$t"
hh=$((10#$hh)); mm=$((10#$mm)); ss=$((10#$ss))
clip=$((hh - 5))
if (( clip < 1 || clip > 7 )); then echo "time must be between 06:00 and 12:59 CET"; exit 1; fi
start=$((mm * 60 + ss - 1 - 10)); (( start < 0 )) && start=0
cams=("${2:-3K2}"); [[ -z "${2:-}" ]] && cams=(3K2 4YV)
for c in "${cams[@]}"; do
  f="$V/Standard_SCU${c}_2026-10-29_0600/Standard_SCU${c}_2026-10-29_0600.00${clip}.mp4"
  echo "camera $c: clip .00${clip}, starting at $((start / 60))m$((start % 60))s"
  mpv --really-quiet --title="SCU$c  $t" --start="$start" --osd-level=1 "$f" &
done
wait

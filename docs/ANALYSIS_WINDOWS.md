# Analysis windows for the 29 October 2026 dataset

The professor asked the four DS3a teams (Topics 4 to 7) to use the same four 10-minute periods to compare **NSE** and **Ouster BlueCity**. This file records our proposal and why. Machine-readable version: `config/analysis_windows.json`.

## Proposed windows (local time, CET = UTC+1)

| Window | Local time | Use |
|---|---|---|
| **W1** | 07:20 to 07:30 | develop and validate first (as the professor suggested) |
| **W2** | 07:40 to 07:50 | busiest pedestrian and cyclist window; about 11% of Ouster frames missing |
| **W3** | 08:00 to 08:10 | quieter period |
| **W4** | 08:20 to 08:30 | |

## Why these windows

They are the only stretch where **every** source exists:

| Source | Coverage on 29 Oct (local time) |
|---|---|
| NSE object list | full day |
| Ouster BlueCity object list | **about 07:12 to 08:35 only** |
| Ouster raw point clouds (`.pcap`) | recordings starting 08:18, 09:04, 10:24; no object lists |
| Traffic signal log (VRS5000) | 06:00 to 13:00, one row per second |
| Video (Miovision, 2 cameras) | 06:00 to 13:00 |

Four windows of 10 minutes spread over the Ouster period, with 10-minute gaps.

## Coverage check (run on the data in `database/`)

| | W1 | W2 | W3 | W4 |
|---|---:|---:|---:|---:|
| NSE frames (of 6,000) | 6,000 | 5,999 | 6,000 | 6,000 |
| Ouster frames (of 6,000) | 5,990 | **5,329** | 5,941 | 5,884 |
| Signal log seconds (of 600) | 600 | 600 | 600 | 600 |
| NSE pedestrian / cyclist track ids | 429 / 189 | 563 / 263 | 246 / 68 | 363 / 91 |
| Ouster PERSON / BICYCLE track ids | 405 / 245 | 680 / 244 | 211 / 99 | 280 / 117 |

Track id counts are raw (before cleaning or stitching) and are not directly comparable between the two systems.

## Pitfalls found on the way

1. **Ouster file names are not local start times.** `object_list+occupations.log.2026-10-29_07-00-00.000.gz` is named after the time the log was rotated, in **UTC**, so it holds 06:55 to 07:00 UTC = **07:55 to 08:00 CET**. Some files hold 10 minutes, so the gaps in the file names (06:35, 07:30) are not gaps in the data. Always use the timestamps inside the file.
2. **The first Ouster file** starts on the evening of 28 October with empty frames; real objects begin about 07:12 on 29 October.
3. **Time zone:** 29 October is CET (UTC+1); daylight saving time ended on 25 October. The 14 October data is CEST (UTC+2).
4. **NSE scores:** the 29 October NSE objects have a `score`; a large share of pedestrian and cyclist detections score below 0.25. The threshold changes counts a lot, so all teams should state which one they use.
5. **Ouster classes** are VEHICLE, LARGE_VEHICLE, PERSON, BICYCLE and UNKNOWN; UNKNOWN is the largest group by track ids. NSE has seven classes. A class mapping has to be agreed for any comparison.
6. **Coordinates:** NSE and Ouster use different coordinate frames; positions cannot be compared without an alignment.

## Draft message to the other teams

> Subject: DS3a 29 Oct dataset: proposal for the four 10-minute windows
>
> Hi all,
>
> For the NSE vs Ouster BlueCity comparison we propose these four windows on 29 October 2026 (local time, CET):
>
> - W1: 07:20 to 07:30 (to develop and validate first)
> - W2: 07:40 to 07:50
> - W3: 08:00 to 08:10
> - W4: 08:20 to 08:30
>
> Reason: the Ouster object lists only cover about 07:12 to 08:35 local time. Signals and video cover 06:00 to 13:00 and NSE covers the whole day, so these windows are the only period where all sources exist.
>
> Two things that cost us time and may help you:
> - The Ouster log file names are rotation times in UTC, not local start times (`..._07-00-00.000.gz` holds 07:55 to 08:00 CET). Use the timestamps inside the files.
> - 29 October is CET (UTC+1), not summer time.
>
> If you have another preference, please reply by [date]. Otherwise we suggest that everyone uses these.
>
> Best regards,
> Team Topic 4

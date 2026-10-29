
import argparse
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon


# Busiest interval identified from the 288 JSON files
DEFAULT_INPUT = Path(
    r"E:\k305_object_list_2026-10-14_aggregation_5min"
    r"\k305_object_list_2026-10-14_07-40_to_07-44.json"
)

OUTPUT_DIR = Path("output")

COLORS = {
    "Car": "#2878B5",
    "Van": "#55A868",
    "Truck": "#8172B2",
    "Bus": "#CC7A00",
    "Motorcycle": "#C44E52",
    "Cyclist": "#00A6A6",
    "Pedestrian": "#E377C2",
}

OTHER_COLOR = "#777777"


def get_position(obj):
    """Read the object's LiDAR x/y coordinates."""
    try:
        pos = obj["bounding_box"]["position"]
        x = float(pos["x"])
        y = float(pos["y"])

        if math.isfinite(x) and math.isfinite(y):
            return x, y

    except (KeyError, TypeError, ValueError):
        pass

    return None


def get_track_id(obj):
    """Return a tracking ID, preserving 0 as an unassigned ID."""
    track_id = obj.get("track_id", 0)

    if track_id is None:
        return 0

    try:
        return int(track_id)
    except (ValueError, TypeError):
        return str(track_id)


def get_dimensions(obj):
    """Read bounding-box dimensions, using safe fallbacks if missing."""
    try:
        scale = obj["bounding_box"]["scale"]

        length = abs(float(scale.get("x", 1.8)))
        width = abs(float(scale.get("y", 0.8)))

        return max(length, 0.3), max(width, 0.3)

    except (KeyError, TypeError, ValueError):
        return 1.8, 0.8


def get_yaw(obj):
    try:
        yaw = float(obj["bounding_box"].get("yaw", 0))
        return yaw if math.isfinite(yaw) else 0.0
    except (KeyError, TypeError, ValueError):
        return 0.0


def read_frames(input_path):
    """Read the frames list from the JSON file."""
    if not input_path.exists():
        raise FileNotFoundError(
            f"JSON file not found:\n{input_path}"
        )

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        frames = data.get("frames", [])
    else:
        frames = data

    if not isinstance(frames, list) or not frames:
        raise ValueError(
            "The JSON file does not contain a non-empty frames list."
        )

    return frames


def make_box(obj):
    """Create a rotated polygon for the object's bounding box."""
    x = obj["x"]
    y = obj["y"]
    length = obj["length"]
    width = obj["width"]
    yaw = obj["yaw"]

    # Some datasets express yaw in radians; support degrees too.
    if abs(yaw) > 2 * math.pi + 0.01:
        yaw = math.radians(yaw)

    corners = np.array([
        [-length / 2, -width / 2],
        [length / 2, -width / 2],
        [length / 2, width / 2],
        [-length / 2, width / 2],
    ])

    rotation = np.array([
        [math.cos(yaw), -math.sin(yaw)],
        [math.sin(yaw), math.cos(yaw)],
    ])

    return corners @ rotation.T + np.array([x, y])


def main():
    parser = argparse.ArgumentParser(
        description="Animate the peak LiDAR traffic interval."
    )

    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to the input JSON file",
    )

    parser.add_argument(
        "--step",
        type=int,
        default=5,
        help="Display every Nth source frame; default is 5",
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=12,
        help="Video playback frames per second",
    )

    parser.add_argument(
        "--trail",
        type=int,
        default=18,
        help="Length of movement trails in displayed frames",
    )

    parser.add_argument(
        "--max-objects",
        type=int,
        default=250,
        help="Maximum objects drawn in a frame; use 0 for unlimited",
    )

    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Show the animation without exporting a video",
    )

    args = parser.parse_args()

    if args.step < 1 or args.fps < 1 or args.trail < 1:
        raise ValueError("--step, --fps and --trail must be positive.")

    input_path = Path(args.input)
    source_frames = read_frames(input_path)

    # Sampling reduces rendering time while preserving the interval's timeline.
    selected_frames = source_frames[::args.step]

    if len(source_frames) > 1 and selected_frames[-1] is not source_frames[-1]:
        selected_frames.append(source_frames[-1])

    parsed_frames = []
    all_x = []
    all_y = []
    observations_by_class = Counter()

    print(f"Reading: {input_path}")
    print(f"Source frames: {len(source_frames):,}")

    # Parse selected frames once rather than reparsing JSON on every animation update.
    for frame in selected_frames:
        parsed_objects = []

        for obj in frame.get("objects", []):
            position = get_position(obj)

            if position is None:
                continue

            x, y = position
            class_name = str(obj.get("class_name", "Unknown"))
            track_id = get_track_id(obj)
            length, width = get_dimensions(obj)
            yaw = get_yaw(obj)

            parsed_objects.append({
                "x": x,
                "y": y,
                "class": class_name,
                "track": track_id,
                "length": length,
                "width": width,
                "yaw": yaw,
            })

            all_x.append(x)
            all_y.append(y)
            observations_by_class[class_name] += 1

        parsed_frames.append({
            "timestamp": frame.get("timestamp_local", "Timestamp unavailable"),
            "objects": parsed_objects,
        })

    if not all_x:
        raise ValueError(
            "No objects with valid bounding-box positions were found."
        )

    # Fixed limits across the entire interval reduce distracting zoom changes.
    x_min, x_max = np.percentile(all_x, [1, 99])
    y_min, y_max = np.percentile(all_y, [1, 99])

    x_padding = max(3, (x_max - x_min) * 0.08)
    y_padding = max(3, (y_max - y_min) * 0.08)

    x_min -= x_padding
    x_max += x_padding
    y_min -= y_padding
    y_max += y_padding

    fig, ax = plt.subplots(figsize=(14, 9))

    try:
        fig.canvas.manager.set_window_title(
            "Peak Traffic LiDAR Animation — 07:40 to 07:44"
        )
    except AttributeError:
        pass

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("LiDAR X position (m)")
    ax.set_ylabel("LiDAR Y position (m)")
    ax.set_title(
        "PEAK TRAFFIC — 14 October 2026, 07:40–07:44\n"
        "Top-down LiDAR object reconstruction"
    )
    ax.grid(True, alpha=0.2)

    status = ax.text(
        0.015,
        0.985,
        "",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": "white",
            "alpha": 0.9,
        },
    )

    legend_handles = []

    for class_name, color in COLORS.items():
        legend_handles.append(
            Line2D(
                [0],
                [0],
                marker="s",
                linestyle="None",
                markersize=8,
                markerfacecolor=color,
                markeredgecolor="black",
                label=class_name,
            )
        )

    ax.legend(
        handles=legend_handles,
        loc="upper right",
        framealpha=0.9,
        title="Object class",
    )

    # Keep drawing objects in lists so they can be removed each frame.
    box_patches = []
    text_labels = []
    trail_lines = []

    # A separate history is maintained for each class-specific tracking ID.
    track_history = defaultdict(list)

    def update(frame_number):
        nonlocal box_patches, text_labels, trail_lines

        for artist in box_patches + text_labels + trail_lines:
            artist.remove()

        box_patches = []
        text_labels = []
        trail_lines = []

        frame = parsed_frames[frame_number]
        objects = frame["objects"]

        # Prefer pedestrians and cyclists if a frame contains too many objects.
        if args.max_objects > 0 and len(objects) > args.max_objects:
            priority = {
                "Pedestrian": 0,
                "Cyclist": 1,
                "Bus": 2,
                "Truck": 3,
                "Van": 4,
                "Motorcycle": 5,
                "Car": 6,
            }

            objects = sorted(
                objects,
                key=lambda obj: (
                    priority.get(obj["class"], 7),
                    str(obj["track"]),
                ),
            )[:args.max_objects]

        for obj in objects:
            x = obj["x"]
            y = obj["y"]
            class_name = obj["class"]
            track_id = obj["track"]

            color = COLORS.get(class_name, OTHER_COLOR)

            polygon = Polygon(
                make_box(obj),
                closed=True,
                facecolor=color,
                edgecolor="black",
                linewidth=0.6,
                alpha=0.8,
            )

            ax.add_patch(polygon)
            box_patches.append(polygon)

            if track_id not in (0, "0"):
                label = f"{class_name} #{track_id}"
            else:
                label = f"{class_name} (untracked)"

            label_artist = ax.text(
                x,
                y + max(obj["width"] * 0.65, 0.35),
                label,
                fontsize=6.5,
                color="black",
                ha="center",
                va="bottom",
                bbox={
                    "boxstyle": "round,pad=0.12",
                    "facecolor": "white",
                    "edgecolor": "none",
                    "alpha": 0.75,
                },
            )

            text_labels.append(label_artist)

            # ID 0 is not treated as a persistent identity.
            if track_id not in (0, "0"):
                key = (class_name, track_id)

                track_history[key].append((x, y))
                track_history[key] = track_history[key][-args.trail:]

                history = track_history[key]

                if len(history) >= 2:
                    line, = ax.plot(
                        [point[0] for point in history],
                        [point[1] for point in history],
                        color=color,
                        linewidth=1.2,
                        alpha=0.75,
                    )

                    trail_lines.append(line)

        status.set_text(
            f"Timestamp: {frame['timestamp']}\n"
            f"Displayed frame: {frame_number + 1}/{len(parsed_frames)}\n"
            f"Visible objects: {len(objects)}\n"
            f"Source interval: 07:40–07:44"
        )

        return box_patches + text_labels + trail_lines + [status]

    animation = FuncAnimation(
        fig,
        update,
        frames=len(parsed_frames),
        interval=1000 / args.fps,
        repeat=False,
        blit=False,
        cache_frame_data=False,
    )

    print(f"Displayed frames: {len(parsed_frames):,}")
    print(f"Frame sampling step: {args.step}")
    print("\nSampled object observations by class:")

    for class_name, count in sorted(observations_by_class.items()):
        print(f"  {class_name}: {count:,}")

    print("\nThese counts are object observations, not unique road users.")

    if not args.preview_only:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        video_path = OUTPUT_DIR / "peak_traffic_0740.mp4"
        ffmpeg_path = shutil.which("ffmpeg")

        if ffmpeg_path:
            print(f"\nExporting MP4 to: {video_path.resolve()}")

            try:
                writer = FFMpegWriter(
                    fps=args.fps,
                    bitrate=2200,
                )

                animation.save(
                    video_path,
                    writer=writer,
                    dpi=100,
                )

                print(f"\nMP4 successfully saved:\n{video_path.resolve()}")

            except Exception as error:
                print(f"\nMP4 export failed: {error}")
                print(
                    "The animation preview will open instead. "
                    "You can install FFmpeg to enable MP4 export."
                )

        else:
            gif_path = OUTPUT_DIR / "peak_traffic_0740.gif"

            print("\nFFmpeg was not found.")
            print("Exporting an animated GIF instead...")

            try:
                writer = PillowWriter(fps=args.fps)

                animation.save(
                    gif_path,
                    writer=writer,
                    dpi=75,
                )

                print(f"\nGIF successfully saved:\n{gif_path.resolve()}")

            except Exception as error:
                print(f"\nGIF export failed: {error}")
                print("Opening the interactive animation preview.")

    plt.show()


if __name__ == "__main__":
    main()


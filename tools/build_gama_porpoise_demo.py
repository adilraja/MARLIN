"""Compose a 12-second M4 demonstration from six retained, verified Kit frames.

This is an offline presentation builder. It never contacts Kit or GAMA and never
changes a retained frame. The GIF holds each actual capture for two seconds;
there are no generated animal poses, interpolated images or intermediate frames.

Run with /usr/bin/python3 -B tools/build_gama_porpoise_demo.py --input <evidence>
--output <new.gif>. A JSON sidecar records input/output hashes and frame timing.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path


KEYFRAME_INDICES = (0, 8, 16, 24, 32, 40)
KEYFRAME_TIMES_S = (0, 4, 8, 12, 16, 20)
FRAME_DURATION_MS = 2000
CAMERA_PATH = "/MarlinGamaPorpoise/DiagnosticCamera"
CANVAS_SIZE = (1480, 930)
BACKGROUND = "#101e2a"
PANEL = "#172a39"
TEXT = "#edf4f6"
MUTED = "#b5c7d2"
ACCENT = "#ffcf66"
STATE_COLOURS = {
    "surface": "#6edcc8",
    "shallow_swim": "#7eb9f0",
    "descent": "#e7a6ec",
    "submerged_swim": "#aeacf3",
    "ascent": "#ffbc7a",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_path(path):
    resolved = path.expanduser().resolve()
    if any(part in {"_build", "extscache", "__pycache__", ".cache"}
           for part in resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Generated/runtime directories are outside this builder's scope")
    return resolved


def number(value, label):
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{label} must be finite")
    return value


def vector(value, length, label):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain {length} values")
    return [number(item, label) for item in value]


def projection_record(record, image_size, label):
    if not isinstance(record, dict) or record.get("projection_metadata_version") != 2:
        raise ValueError(f"{label} requires corrected projection metadata version 2")
    product = record.get("render_product", {})
    if product.get("camera") != CAMERA_PATH or not product.get("path"):
        raise ValueError(f"{label} did not validate the porpoise diagnostic render-product camera")
    if product.get("resolution") != list(image_size):
        raise ValueError(f"{label} render-product resolution does not match retained PNG pixels")
    if "actual_viewport_resolution" in record and record["actual_viewport_resolution"] != list(image_size):
        raise ValueError(f"{label} viewport resolution does not match retained PNG pixels")
    for key in ("actual_view_matrix", "actual_projection_matrix"):
        matrix = record.get(key)
        if not isinstance(matrix, list) or len(matrix) != 4:
            raise ValueError(f"{label}.{key} must be a finite 4 x 4 matrix")
        for row in matrix:
            vector(row, 4, f"{label}.{key}")


def load_evidence(directory):
    """Load only successful retained evidence with the corrected camera proof."""
    from PIL import Image

    result_path = directory / "results.json"
    report = json.loads(result_path.read_text())
    if report.get("passed") is not True:
        raise ValueError("The live acceptance results must have passed:true")
    captures = report.get("captures")
    if not isinstance(captures, list) or len(captures) != len(KEYFRAME_INDICES):
        raise ValueError("Exactly six retained actual Kit captures are required")
    units = number(report["acquired"]["meters_per_scene_unit"], "meters_per_scene_unit")
    if units <= 0:
        raise ValueError("meters_per_scene_unit must be positive")
    rows = report.get("actual_gama_transforms")
    if not isinstance(rows, list) or len(rows) != 41:
        raise ValueError("The complete 41-sample actual composed trajectory is required")
    row_by_index = {}
    for row in rows:
        index = row.get("step_index")
        if type(index) is not int or index in row_by_index:
            raise ValueError("Actual composed trajectory contains invalid/duplicate indices")
        vector(row.get("composed_position_m"), 3, "composed_position_m")
        number(row.get("composed_heading_deg"), "composed_heading_deg")
        if row.get("state") not in STATE_COLOURS:
            raise ValueError("Actual composed trajectory contains an unknown state")
        row_by_index[index] = row
    if set(row_by_index) != set(range(41)):
        raise ValueError("Actual composed trajectory must retain indices 0 through 40")
    rows = [row_by_index[index] for index in range(41)]
    tolerance = number(report["declared_tolerances"]["position_euclidean_m"], "position tolerance")
    if tolerance < 0:
        raise ValueError("Position tolerance must be nonnegative")
    frame_records, seen_files = [], set()
    identity = None
    for capture, index, time_s in zip(captures, KEYFRAME_INDICES, KEYFRAME_TIMES_S):
        if capture.get("ok") is not True or capture.get("render_product_camera_verified") is not True:
            raise ValueError("Every capture requires render_product_camera_verified:true")
        if not all(capture.get(key) is True for key in
                   ("previous_camera_restored", "owned_layer_restored", "controller_gate_restored")):
            raise ValueError("Every capture must have restored camera, owned layer and controller gate")
        state = capture["gama_state"]
        if state.get("schema_version") != "2.0" or state.get("step_index") != index:
            raise ValueError("Capture state indices must be 0, 8, 16, 24, 32, 40 in order")
        if number(state.get("simulation_time_s"), "simulation_time_s") != time_s:
            raise ValueError("Capture times must be 0, 4, 8, 12, 16, 20 GAMA seconds")
        dt = number(state.get("simulation_step_s"), "simulation_step_s")
        if dt != 0.5:
            raise ValueError("This bounded M4 demonstration requires the recorded 0.5-second step")
        agents = state.get("agents")
        if not isinstance(agents, list) or len(agents) != 1:
            raise ValueError("Each capture must retain exactly one actual GAMA agent")
        agent = agents[0]
        current_identity = (state.get("run_id"), state.get("seed"), agent.get("agent_id"), agent.get("species"))
        if identity is None:
            identity = current_identity
        if current_identity != identity or agent.get("species") != "harbour_porpoise":
            raise ValueError("All captures must belong to one actual harbour-porpoise run and agent")
        row = row_by_index[index]
        if agent.get("behavioural_state") != row["state"]:
            raise ValueError("Captured GAMA state and measured composed state disagree")
        capture_position = [item * units for item in vector(
            capture["world_pose"].get("position_scene_units"), 3, "capture composed position")]
        if math.dist(capture_position, row["composed_position_m"]) > tolerance:
            raise ValueError("Captured composed position differs from measured trajectory")
        forward = vector(capture["world_pose"].get("forward_y_up"), 3, "capture forward")
        heading = math.degrees(math.atan2(forward[0], forward[2])) % 360
        heading_tolerance = number(report["declared_tolerances"]["heading_circular_deg"], "heading tolerance")
        if abs((heading - row["composed_heading_deg"] + 180) % 360 - 180) > heading_tolerance:
            raise ValueError("Captured composed heading differs from measured trajectory")
        name = capture.get("retained_frame")
        if not isinstance(name, str) or Path(name).name != name or name in seen_files:
            raise ValueError("Each retained frame must be a distinct local PNG filename")
        seen_files.add(name)
        image_path = checked_path(directory / name)
        if image_path.parent != directory or image_path.suffix.lower() != ".png":
            raise ValueError("Retained frame must be a PNG in the evidence directory")
        with Image.open(image_path) as source:
            if source.format != "PNG":
                raise ValueError("Retained source frames must actually be PNG images")
            source.load()
            image = source.convert("RGB")
        for key in ("projection_before_capture", "projection_after_capture"):
            projection_record(capture.get(key), image.size, key)
        before, after = capture["projection_before_capture"], capture["projection_after_capture"]
        if any(before[key] != after[key] for key in ("actual_view_matrix", "actual_projection_matrix")):
            raise ValueError("Capture camera projection changed while obtaining a retained frame")
        frame_records.append({"image": image, "path": image_path, "sha256": digest(image_path),
                              "index": index, "time_s": time_s, "row": row,
                              "render_product": before["render_product"]})
    return report, rows, frame_records, digest(result_path)


def fonts():
    from PIL import ImageFont

    normal = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    def font(size, strong=False):
        path = bold if strong else normal
        return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()
    return {"title": font(30, True), "state": font(25, True),
            "body": font(19), "small": font(16), "caption": font(18, True)}


def plot_panel(rows, current_index):
    from PIL import Image
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(4.8, 6.8), dpi=100, facecolor=PANEL)
    canvas = FigureCanvasAgg(figure)
    axes = figure.subplots(2, 1)
    figure.subplots_adjust(left=.19, right=.96, top=.94, bottom=.09, hspace=.42)
    x = [row["composed_position_m"][0] for row in rows]
    z = [row["composed_position_m"][2] for row in rows]
    depth = [-row["composed_position_m"][1] for row in rows]
    times = [row["step_index"] * .5 for row in rows]
    for axis in axes:
        axis.set_facecolor(PANEL)
        axis.tick_params(colors=MUTED, labelsize=10)
        axis.xaxis.label.set_color(MUTED)
        axis.yaxis.label.set_color(MUTED)
        axis.title.set_color(TEXT)
        axis.grid(color="#405567", alpha=.5, linewidth=.6)
        for spine in axis.spines.values():
            spine.set_color("#405567")
    xy = axes[0]
    xy.set_title("Actual composed XZ trajectory", fontsize=12, pad=12)
    xy.plot(x, z, color="#748c9f", linewidth=1.3, marker=".", markersize=3)
    xy.plot(x[:current_index+1], z[:current_index+1], color="#7eb9f0", linewidth=2)
    xy.scatter([x[current_index]], [z[current_index]], color=ACCENT, s=70, zorder=4)
    heading = math.radians(rows[current_index]["composed_heading_deg"])
    xy.annotate("", xy=(x[current_index]+.85*math.sin(heading), z[current_index]+.85*math.cos(heading)),
                xytext=(x[current_index], z[current_index]),
                arrowprops={"arrowstyle": "->", "color": ACCENT, "lw": 2})
    span = max(max(x)-min(x), max(z)-min(z)) + 2.1
    centre_x, centre_z = (min(x)+max(x))/2, (min(z)+max(z))/2
    xy.set_xlim(centre_x-span/2, centre_x+span/2)
    xy.set_ylim(centre_z-span/2, centre_z+span/2)
    xy.set_aspect("equal", adjustable="box")
    xy.set_xlabel("X (m)", fontsize=11)
    xy.set_ylabel("Z (m)", fontsize=11)
    vertical = axes[1]
    vertical.set_title("Actual composed root depth", fontsize=12, pad=12)
    vertical.plot(times, depth, color="#748c9f", linewidth=1.3, marker=".", markersize=3)
    vertical.plot(times[:current_index+1], depth[:current_index+1], color="#7eb9f0", linewidth=2)
    vertical.axvline(times[current_index], color=ACCENT, alpha=.6, linewidth=1)
    vertical.scatter([times[current_index]], [depth[current_index]], color=ACCENT, s=70, zorder=4)
    vertical.set_xlim(-.4, 20.4)
    vertical.set_xticks((0, 4, 8, 12, 16, 20))
    vertical.set_ylim(max(depth)+.25, -.05)
    vertical.set_xlabel("GAMA simulation time (s)", fontsize=11)
    vertical.set_ylabel("Depth below Y=0 (m)", fontsize=11)
    canvas.draw()
    return Image.frombytes("RGBA", canvas.get_width_height(), bytes(canvas.buffer_rgba())).convert("RGB")


def compose_frame(record, rows, frame_number, font):
    from PIL import Image, ImageDraw, ImageOps

    image = Image.new("RGB", CANVAS_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)
    row = record["row"]
    state_colour = STATE_COLOURS[row["state"]]
    draw.text((28, 22), "GAMA to MARLIN  |  actual Kit replay", font=font["title"], fill=TEXT)
    draw.text((28, 72), f"t = {record['time_s']:g} s    step {record['index']:02d}    {row['state']}",
              font=font["state"], fill=state_colour)
    x, y, z = row["composed_position_m"]
    draw.text((28, 112), f"Actual composed root:  X {x:+.3f} m   Y {y:+.3f} m   Z {z:+.3f} m"
              f"     heading {row['composed_heading_deg']:.2f} deg", font=font["body"], fill=MUTED)
    draw.rounded_rectangle((24, 154, 958, 824), radius=12, fill=PANEL)
    draw.text((44, 174), "Retained Kit frame  |  diagnostic camera follows the animal", font=font["caption"], fill=TEXT)
    fitted = ImageOps.contain(record["image"], (894, 564), method=Image.Resampling.LANCZOS)
    image.paste(fitted, (44+(894-fitted.width)//2, 216+(564-fitted.height)//2))
    draw.text((44, 792), f"Actual capture {frame_number + 1}/6  |  held for 2 s  |  no interpolated frames",
              font=font["small"], fill=MUTED)
    image.paste(plot_panel(rows, record["index"]), (980, 154))
    draw.text((28, 850), "Engineering demonstration: static pose proxy; temporary below-surface camera and diagnostic light.",
              font=font["body"], fill=TEXT)
    draw.text((28, 882), "41 measured transforms connect the plot samples. Body animation, breathing and biological suitability are not validated.",
              font=font["small"], fill=MUTED)
    return image


def build(input_directory, output_path):
    # Keep Matplotlib's incidental font/config cache outside user caches and the
    # preserved evidence. Set this before its first import.
    os.environ["MPLCONFIGDIR"] = "/tmp/marlin-m4-mpl"
    import matplotlib
    matplotlib.use("Agg")
    from PIL import Image

    directory = checked_path(input_directory)
    output = checked_path(output_path)
    sidecar = output.with_suffix(".json")
    if output.suffix.lower() != ".gif":
        raise ValueError("--output must name a new .gif file")
    if output.exists() or sidecar.exists():
        raise ValueError("Refusing to overwrite an existing GIF or JSON sidecar")
    report, rows, records, result_hash = load_evidence(directory)
    font = fonts()
    frames = [compose_frame(record, rows, index, font) for index, record in enumerate(records)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        frames[0].save(handle, format="GIF", save_all=True, append_images=frames[1:],
                       duration=[FRAME_DURATION_MS]*6, loop=0, disposal=2, optimize=False)
    with Image.open(output) as animation:
        durations = []
        for index in range(animation.n_frames):
            animation.seek(index)
            durations.append(animation.info.get("duration"))
        if animation.n_frames != 6 or durations != [FRAME_DURATION_MS]*6:
            raise ValueError("Saved GIF did not preserve the required six frames and 12-second timing")
    if digest(directory / "results.json") != result_hash or any(
            digest(record["path"]) != record["sha256"] for record in records):
        raise ValueError("Input evidence changed during composition")
    manifest = {
        "milestone": 4, "kind": "actual_kit_replay_demonstration",
        "input_directory": str(directory), "results_sha256": result_hash,
        "trajectory": report.get("trajectory"), "trajectory_sha256": report.get("trajectory_sha256"),
        "run_id": report["captures"][0]["gama_state"]["run_id"],
        "seed": report["captures"][0]["gama_state"]["seed"],
        "output_gif": str(output), "output_sha256": digest(output), "size_px": list(CANVAS_SIZE),
        "duration_ms": sum(durations), "loop": "repeat", "frame_count": 6,
        "interpolated_frames": False, "raw_images_unchanged": True,
        "plot_source": "actual_gama_transforms composed positions/headings; time = recorded step_index * recorded 0.5-second step",
        "limitations": ["Static pose proxy without body animation or biological approval.",
                         "Temporary below-surface diagnostic camera and light; camera follows the animal.",
                         "Six actual snapshots held for two seconds each; display duration is not GAMA simulation time.",
                         "Raw PNGs are fitted without cropping; GIF colour quantization is for presentation, not pixel validation."],
        "frames": [{"step_index": record["index"], "simulation_time_s": record["time_s"],
                    "duration_ms": FRAME_DURATION_MS, "retained_frame": record["path"].name,
                    "retained_frame_sha256": record["sha256"], "state": record["row"]["state"],
                    "composed_position_m": record["row"]["composed_position_m"],
                    "composed_heading_deg": record["row"]["composed_heading_deg"],
                    "render_product": record["render_product"]} for record in records],
    }
    with sidecar.open("x") as handle:
        json.dump(manifest, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return {"gif": str(output), "manifest": str(sidecar), "frame_count": 6, "duration_ms": 12000,
            "output_sha256": manifest["output_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="New passing live-evidence directory")
    parser.add_argument("--output", type=Path, required=True, help="New GIF path; existing outputs are refused")
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.input, arguments.output), indent=2))


if __name__ == "__main__":
    main()

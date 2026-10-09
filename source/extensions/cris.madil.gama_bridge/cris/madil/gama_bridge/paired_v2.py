"""One frozen biological/environmental scene, several Pilot-style GSD cameras."""
import asyncio
from copy import deepcopy
import gc
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import tempfile

from .exchange_v2 import validate_step
from .paired_state_v2 import resolved_record, camera_condition, source_content_hash

GSDS = (.5, 1., 2., 3., 4.)
CAMERA = "/MarlinGamaPairCamera"
RESOLUTION = (1024, 768)
REPO = Path(__file__).resolve().parents[6]
_recovery_caches = []


def validate_conditions(orders, delay_s):
    if not isinstance(orders, list) or not 1 <= len(orders) <= 3:
        raise ValueError("Expected one to three complete five-GSD orders")
    for order in orders:
        if (not isinstance(order, list) or len(order) != 5 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in order) or
                sorted(order) != list(GSDS)):
            raise ValueError("Every order must contain exactly 0.5, 1, 2, 3 and 4 cm/px")
    if type(delay_s) not in (int, float) or not math.isfinite(delay_s) or not 0 <= delay_s <= 5:
        raise ValueError("delay_s must be finite and between zero and five seconds")
    return deepcopy(orders), float(delay_s)


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_pilot_camera(condition, gsd, anchor, plane):
    """Check resolved optics/pose rather than trusting the requested GSD label."""
    c = condition["camera_condition"]
    unit = c["meters_per_scene_unit"]
    matrix = c["composed_camera_matrix"]
    expected = [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0],
        [anchor[0] / unit, (plane + gsd * 100) / unit, anchor[1] / unit, 1]]
    if (c["projection"] != "perspective" or c["resolution_px"] != list(RESOLUTION) or
            not math.isclose(unit, .01, abs_tol=1e-12) or
            any(not math.isclose(matrix[i][j], expected[i][j], rel_tol=1e-10, abs_tol=1e-8)
                for i in range(4) for j in range(4))):
        raise ValueError("Composed camera differs from the declared Pilot nadir pose")
    for key, value in (("focal_length", 50 / (100 * unit)),
            ("horizontal_aperture", 1024 * 5e-5 / unit),
            ("vertical_aperture", 768 * 5e-5 / unit),
            ("horizontal_aperture_offset", 0), ("vertical_aperture_offset", 0)):
        if not math.isclose(c[key], value, rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError("Resolved camera optics differ from the declared Pilot geometry")
    separation = matrix[3][1] * unit - plane
    fx = c["focal_length"] / c["horizontal_aperture"] * RESOLUTION[0]
    fy = c["focal_length"] / c["vertical_aperture"] * RESOLUTION[1]
    measured = [100 * separation / f for f in (fx, fy)]
    if any(not math.isclose(value, gsd, rel_tol=1e-6, abs_tol=1e-8) for value in measured):
        raise ValueError("Actual reference-plane GSD differs from the declared condition")
    return {"passed": True, "measured_reference_gsd_xy_cm_px": measured,
        "camera_separation_from_root_plane_m": separation,
        "reference_footprint_wh_m": [RESOLUTION[0] * measured[0] / 100, RESOLUTION[1] * measured[1] / 100],
        "note": "Direct pinhole reference-plane geometry; underwater refraction remains uncalibrated"}


class KitRuntime:
    """Small dependency boundary for transaction failure tests; one Kit renderer."""
    def __init__(self):
        import carb.settings
        import omni.timeline
        import omni.usd
        from omni.kit.viewport.utility import get_active_viewport
        from cris.madil.render_service import calibration_capture, capture_state, hidef_marine
        from PIL import Image, ImageChops, ImageStat
        self.context = omni.usd.get_context()
        self.viewport = get_active_viewport()
        self.timeline = omni.timeline.get_timeline_interface()
        self.settings = carb.settings.get_settings()
        self.lock, self.gate = calibration_capture, capture_state
        self.marine = hidef_marine
        self.output_root = REPO / "artifacts/gama_pairs"
        self.Image, self.ImageChops, self.ImageStat = Image, ImageChops, ImageStat

    def stage(self):
        return self.context.get_stage()

    def selection(self):
        return self.context.get_selection().get_selected_prim_paths()

    def select(self, paths):
        self.context.get_selection().set_selected_prim_paths(paths, False)

    def renderer(self):
        return self.marine.settings_record()

    def restore_renderer(self, values):
        self.marine.restore_settings(values)

    def display(self):
        return self.settings.get('/persistent/app/viewport/displayOptions')

    def set_display(self, value):
        self.marine.restore_settings({'/persistent/app/viewport/displayOptions': value})

    def ocean_clock(self):
        from cris.madil.render_service import ocean
        state = ocean._ocean_animation_state
        if state is None:
            return {"running": False}
        keys = ("ocean_path", "size", "resolution", "speed", "choppiness", "target_fps", "elapsed", "accumulator", "waves", "position")
        return {"running": ocean._ocean_animation_subscription is not None,
                **{key: deepcopy(state[key]) for key in keys if key in state}}

    def freeze(self, stage, seconds):
        from pxr import Usd
        return self.marine.freeze_stage(stage, Usd.TimeCode(seconds * stage.GetTimeCodesPerSecond()))

    def retain(self, stage):
        from pxr import Usd
        cache = Usd.StageCache()
        cache.Insert(stage)
        return cache

    def dependencies(self, stage):
        return self.marine.asset_dependencies(stage)

    def preflight(self):
        # As in the existing marine capture path, release unreachable capture
        # helpers and USD traceback cycles before checking GPU headroom. This
        # never clears the active stage or the fail-closed recovery caches.
        gc.collect()
        return self.marine.gpu_preflight()

    async def attach(self, stage):
        ok, error = await self.context.attach_stage_async(stage)
        if not ok:
            raise RuntimeError("Could not attach stage: " + str(error))

    async def update(self):
        import omni.kit.app
        await omni.kit.app.get_app().next_update_async()

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)

    def camera(self, stage, gsd, anchor, plane):
        from pxr import Gf, Sdf
        from cris.madil.render_service.calibration_geometry import CalibrationConfig, build_camera
        config = CalibrationConfig(meters_per_scene_unit=.01, image_width_px=1024,
            image_height_px=768, focal_length_mm=50, pixel_pitch_um=5,
            height_above_target_m=gsd * 100, target_plane_y_m=plane,
            target_width_m=2, target_height_m=1)
        camera = build_camera(stage, config, CAMERA, (anchor[0], 0, anchor[1]))
        camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))
        exposure = json.loads((REPO / "experiments/gsd_pilot_v1/environment.json").read_text())["camera_exposure_attributes"]
        for name, value in exposure.items():
            camera.GetPrim().CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(value)

    def projection(self, stage):
        from cris.madil.render_service.capture_projection import record_projection
        return record_projection(stage, self.viewport)

    async def capture(self, target):
        from omni.kit.viewport.utility import capture_viewport_to_file
        if target.exists():
            raise ValueError("Capture probe output must be a fresh file")
        # Same generic viewport backend as Pilot, with a unique file rather
        # than /tmp/marlin_viewport.png. Kit can signal rendered-frame
        # completion before the asynchronous PNG writer has finished.
        capture = capture_viewport_to_file(self.viewport, file_path=str(target))
        await capture.wait_for_result(completion_frames=5)
        for _ in range(300):
            try:
                with self.Image.open(target) as image:
                    image.load()
                    if image.size != RESOLUTION:
                        raise ValueError("Fresh capture has the wrong image dimensions")
                return target
            except (OSError, SyntaxError):
                await self.sleep(.1)
        raise RuntimeError("Unique capture PNG was not completely readable within 30 seconds")

    def difference(self, previous, current):
        with self.Image.open(previous) as a, self.Image.open(current) as b:
            if a.size != RESOLUTION or b.size != RESOLUTION:
                raise ValueError("Captured image is not 1024 by 768")
            diff = self.ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
            return sum(self.ImageStat.Stat(diff).mean) / 3


async def run(owner, token, orders, delay_s, runtime=None):
    """Capture complete GSD orders through the shared frozen-scene transaction."""
    from .paired_transaction_v2 import run as run_transaction
    return await run_transaction(owner, token, orders, delay_s, runtime)

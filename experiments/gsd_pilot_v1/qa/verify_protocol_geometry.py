"""Check the pilot's chosen parameters with the existing USD camera builder.

This is an offline geometry check, not a marine raster/capture certificate.
Run using Blender Python with bytecode disabled.
"""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"))
from calibration_geometry import CalibrationConfig, build_camera
from pxr import Gf, Usd


def main():
    experiment = Path(__file__).resolve().parents[1]
    spec = json.loads((experiment / "specification.json").read_text())
    camera = spec["camera"]
    width, height = camera["image_size_px"]
    records = []
    for requested, separation in zip(spec["gsd_levels_cm_px"], camera["camera_to_reference_plane_separations_m"]):
        config = CalibrationConfig(
            meters_per_scene_unit=spec["coordinates"]["required_stage_meters_per_unit"],
            image_width_px=width, image_height_px=height,
            focal_length_mm=camera["focal_length_mm"], pixel_pitch_um=camera["pixel_pitch_um"],
            height_above_target_m=separation, target_plane_y_m=0,
            target_width_m=2, target_height_m=1,
            pitch_deg=camera["pitch_deg"], roll_deg=camera["roll_deg"],
        )
        stage = Usd.Stage.CreateInMemory()
        authored = build_camera(stage, config, "/Camera")
        frustum = authored.GetCamera(0).frustum
        vp = frustum.ComputeViewMatrix() * frustum.ComputeProjectionMatrix()
        errors = []
        for u in (.5, width / 2, width - .5):
            for v in (.5, height / 2, height - .5):
                p = config.ray_plane(u, v)
                ndc = vp.Transform(Gf.Vec3d(*(n / config.meters_per_scene_unit for n in p)))
                errors.extend((abs((ndc[0] + 1) * width / 2 - u),
                               abs((1 - ndc[1]) * height / 2 - v)))
        local = config.local_gsd(width / 2, height / 2)
        passed = max(errors) < .001 and all(abs(value - requested) < 1e-9 for value in local)
        records.append({"requested_gsd_cm_px": requested, "camera_separation_m": separation,
                        "actual_plane_gsd_xy_cm_px": local, "max_reprojection_error_px": max(errors),
                        "footprint_m": [width * config.gsd_m_px, height * config.gsd_m_px],
                        "passed": passed})
    report = {"scope": "offline_existing_camera_geometry_not_render_validation",
              "passed": len(records) == 5 and all(row["passed"] for row in records),
              "records": records}
    (experiment / "qa/protocol_geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise RuntimeError("Pilot geometry does not satisfy the chosen protocol")


if __name__ == "__main__":
    main()

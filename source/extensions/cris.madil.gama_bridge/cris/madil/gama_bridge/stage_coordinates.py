"""Read-only USD stage inspection for the v2 boundary; no scene or unit setters."""
import math

from .exchange_v2 import preview_transforms, validate_step


def inspect_stage(stage):
    """Report effective metadata and whether it was explicitly authored.

    USD fallbacks are reported for diagnosis but are not sufficient for v2
    conversion. The bridge never silently authors a coordinate convention.
    """
    if stage is None:
        return {"stage_available": False, "suitable_for_v2": False,
                "rejection_reasons": ["No active USD stage"]}
    from pxr import UsdGeom
    units = UsdGeom.GetStageMetersPerUnit(stage)
    axis = str(UsdGeom.GetStageUpAxis(stage))
    authored_units = stage.HasAuthoredMetadata("metersPerUnit")
    authored_axis = stage.HasAuthoredMetadata("upAxis")
    reasons = []
    if not authored_units:
        reasons.append("metersPerUnit must be explicitly authored for v2 conversion")
    if not authored_axis:
        reasons.append("upAxis must be explicitly authored for v2 conversion")
    if not math.isfinite(units) or units <= 0:
        reasons.append("metersPerUnit must be finite and positive")
    if axis != "Y":
        reasons.append("v2 requires a Y-up stage")
    return {"stage_available": True, "root_layer": stage.GetRootLayer().identifier,
            "meters_per_scene_unit": units if math.isfinite(units) else None,
            "up_axis": axis, "meters_per_unit_authored": authored_units,
            "up_axis_authored": authored_axis, "suitable_for_v2": not reasons,
            "rejection_reasons": reasons,
            "mean_sea_level_world_y_m": 0.0,
            "vertical_datum_source": "v2_contract_fixed_plane_not_measured_ocean_surface"}


def preview_on_stage(payload, stage):
    """Validate first, then resolve using inspected units; never author a prim."""
    snapshot = validate_step(payload)
    coordinates = inspect_stage(stage)
    if not coordinates["suitable_for_v2"]:
        raise ValueError("; ".join(coordinates["rejection_reasons"]))
    transforms = preview_transforms(snapshot, coordinates["meters_per_scene_unit"])
    return {"snapshot": snapshot, "stage_coordinates": coordinates,
            "transforms": transforms, "mode": "conversion_preview_only", "rendered": False}

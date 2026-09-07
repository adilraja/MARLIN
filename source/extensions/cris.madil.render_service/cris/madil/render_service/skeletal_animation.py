"""Attach MARLIN-baked joint animation to a composed USD skeleton."""

import json
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt


def _normalized_bone_name(name: str) -> str:
    return name.replace(".", "_")


def bind_baked_skeletal_animation(
    stage,
    cetacean_path: str,
    animation_file: str,
):
    """Author and bind a UsdSkelAnimation from baked joint-local samples."""

    root_prim = stage.GetPrimAtPath(cetacean_path)

    if not root_prim or not root_prim.IsValid():
        return {"ok": False, "error": f"Cetacean not found: {cetacean_path}"}

    skeleton_prims = [
        prim
        for prim in Usd.PrimRange(root_prim)
        if prim.IsA(UsdSkel.Skeleton)
    ]

    if len(skeleton_prims) != 1:
        return {
            "ok": False,
            "error": f"Expected one skeleton, found {len(skeleton_prims)}",
        }

    animation_path = Path(animation_file)

    if not animation_path.is_file():
        return {
            "ok": False,
            "error": f"Baked animation not found: {animation_path}",
        }

    payload = json.loads(animation_path.read_text(encoding="utf-8"))
    skeleton_prim = skeleton_prims[0]
    skeleton = UsdSkel.Skeleton(skeleton_prim)
    joints = skeleton.GetJointsAttr().Get()
    rest_transforms = skeleton.GetRestTransformsAttr().Get()
    bone_names = payload["bone_names"]

    if len(joints) != len(bone_names):
        return {
            "ok": False,
            "error": (
                f"Animation has {len(bone_names)} bones but skeleton has "
                f"{len(joints)} joints"
            ),
        }

    if payload.get("transform_space") != "rest_relative":
        return {
            "ok": False,
            "error": "Animation samples must be baked in rest-relative space",
        }

    if len(rest_transforms) != len(joints):
        return {
            "ok": False,
            "error": "Skeleton rest-transform count does not match its joints",
        }

    for joint, bone_name in zip(joints, bone_names):
        joint_name = str(joint).rsplit("/", 1)[-1]

        if joint_name != _normalized_bone_name(bone_name):
            return {
                "ok": False,
                "error": (
                    f"Joint mismatch: {joint_name} != {bone_name}"
                ),
            }

    animations_path = f"{cetacean_path}/Animations"
    authored_animation_path = f"{animations_path}/SwimCycle"

    existing = stage.GetPrimAtPath(authored_animation_path)

    if existing and existing.IsValid():
        stage.RemovePrim(authored_animation_path)

    UsdGeom.Xform.Define(stage, animations_path)
    animation = UsdSkel.Animation.Define(stage, authored_animation_path)
    animation.GetJointsAttr().Set(joints)

    frames = payload["frames"]
    fps = float(payload["fps"])
    start_frame = float(payload["start_frame"])
    time_codes_per_second = float(stage.GetTimeCodesPerSecond())

    if fps <= 0.0 or time_codes_per_second <= 0.0:
        return {"ok": False, "error": "Invalid animation or stage frame rate"}

    for sample in frames:
        time_seconds = (float(sample["frame"]) - start_frame) / fps
        time_code = Usd.TimeCode(time_seconds * time_codes_per_second)

        local_transforms = []

        for index in range(len(joints)):
            translation = sample["translations"][index]
            rotation = sample["rotations"][index]
            scale = sample["scales"][index]

            rest_relative = Gf.Transform()
            rest_relative.SetTranslation(Gf.Vec3d(*translation))
            rest_relative.SetRotation(
                Gf.Rotation(
                    Gf.Quatd(
                        rotation[0],
                        Gf.Vec3d(
                            rotation[1],
                            rotation[2],
                            rotation[3],
                        ),
                    )
                )
            )
            rest_relative.SetScale(Gf.Vec3d(*scale))

            # OpenUSD defines rest-relative transforms such that:
            # restRelative * restTransform = jointLocalTransform.
            local_transforms.append(
                rest_relative.GetMatrix()
                * Gf.Matrix4d(rest_transforms[index])
            )

        authored = animation.SetTransforms(
            Vt.Matrix4dArray(local_transforms),
            time_code,
        )

        if not authored:
            return {
                "ok": False,
                "error": f"Could not author animation sample at {time_code}",
            }

    binding = UsdSkel.BindingAPI(skeleton_prim)
    binding.CreateAnimationSourceRel().SetTargets([
        Sdf.Path(authored_animation_path)
    ])

    duration_seconds = (
        float(payload["end_frame"])
        - float(payload["start_frame"])
    ) / fps

    return {
        "ok": True,
        "name": payload["name"],
        "skeleton_path": str(skeleton_prim.GetPath()),
        "animation_path": authored_animation_path,
        "joint_count": len(joints),
        "sample_count": len(frames),
        "fps": fps,
        "start_time_seconds": 0.0,
        "end_time_seconds": duration_seconds,
        "duration_seconds": duration_seconds,
    }

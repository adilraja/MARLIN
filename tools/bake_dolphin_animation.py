"""Bake the source glTF swim cycle to joint-local TRS samples.

Run with Blender:
    blender --background --factory-startup --python tools/bake_dolphin_animation.py
"""

import json
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_GLTF = (
    PROJECT_ROOT
    / "assets/cetaceans/bottlenose_dolphin/scene.gltf"
)
OUTPUT_JSON = (
    PROJECT_ROOT
    / "assets/cetaceans/bottlenose_dolphin/animation/swim_cycle.json"
)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE_GLTF))

    armatures = [
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE"
    ]

    if len(armatures) != 1:
        raise RuntimeError(
            f"Expected one dolphin armature, found {len(armatures)}"
        )

    armature = armatures[0]
    actions = [
        action
        for action in bpy.data.actions
        if action.name == "Swim Cycle"
    ]

    if len(actions) != 1:
        raise RuntimeError(
            f"Expected one Swim Cycle action, found {len(actions)}"
        )

    action = actions[0]
    armature.animation_data_create()
    armature.animation_data.action = action

    scene = bpy.context.scene
    scene.render.fps = 24
    scene.render.fps_base = 1.0

    start_frame = int(round(action.frame_range[0]))
    end_frame = int(round(action.frame_range[1]))
    bone_names = [bone.name for bone in armature.data.bones]
    rest_local_matrices = {}

    for bone in armature.data.bones:
        if bone.parent is None:
            rest_local_matrices[bone.name] = bone.matrix_local.copy()
        else:
            rest_local_matrices[bone.name] = (
                bone.parent.matrix_local.inverted_safe()
                @ bone.matrix_local
            )

    frames = []

    for frame in range(start_frame, end_frame + 1):
        scene.frame_set(frame)
        translations = []
        rotations = []
        scales = []

        for bone_name in bone_names:
            pose_bone = armature.pose.bones[bone_name]

            if pose_bone.parent is None:
                local_matrix = pose_bone.matrix.copy()
            else:
                local_matrix = (
                    pose_bone.parent.matrix.inverted_safe()
                    @ pose_bone.matrix
                )

            # Store motion relative to Blender's rest pose. MARLIN applies
            # this delta to the converted USD skeleton's own rest transform,
            # preserving the coordinate conversion authored in the USD.
            rest_relative_matrix = (
                rest_local_matrices[bone_name].inverted_safe()
                @ local_matrix
            )

            translation, rotation, scale = (
                rest_relative_matrix.decompose()
            )
            rotation.normalize()

            translations.append([float(value) for value in translation])
            rotations.append([
                float(rotation.w),
                float(rotation.x),
                float(rotation.y),
                float(rotation.z),
            ])
            scales.append([float(value) for value in scale])

        frames.append({
            "frame": frame,
            "translations": translations,
            "rotations": rotations,
            "scales": scales,
        })

    payload = {
        "name": action.name,
        "transform_space": "rest_relative",
        "fps": scene.render.fps / scene.render.fps_base,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "bone_names": bone_names,
        "frames": frames,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )

    print(
        f"Baked {len(frames)} frames for {len(bone_names)} bones "
        f"to {OUTPUT_JSON}"
    )


if __name__ == "__main__":
    main()

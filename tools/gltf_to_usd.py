import bpy
import os
import sys


def get_args():
    argv = sys.argv

    if "--" not in argv:
        raise RuntimeError(
            "Usage: blender --background --python gltf_to_usd.py "
            "-- --input file.gltf --output file.usd"
        )

    argv = argv[argv.index("--") + 1:]

    args = {}

    i = 0
    while i < len(argv):
        if argv[i] == "--input":
            args["input"] = argv[i + 1]
            i += 2
        elif argv[i] == "--output":
            args["output"] = argv[i + 1]
            i += 2
        else:
            i += 1

    return args


args = get_args()

src = os.path.abspath(args["input"])
dst = os.path.abspath(args["output"])

print("=" * 70)
print("IMPORTING")
print(src)
print("=" * 70)

bpy.ops.wm.read_factory_settings(use_empty=True)

result = bpy.ops.import_scene.gltf(
    filepath=src
)

print("glTF import:", result)

print("\nOBJECTS:")

for obj in bpy.context.scene.objects:

    if obj.type == "MESH":
        dimensions = tuple(
            round(float(v), 4)
            for v in obj.dimensions
        )

        print(
            f"MESH: {obj.name}"
            f" dimensions={dimensions}"
        )

    else:
        print(
            f"{obj.type}: {obj.name}"
        )

os.makedirs(
    os.path.dirname(dst),
    exist_ok=True
)

print("\nEXPORTING")
print(dst)

result = bpy.ops.wm.usd_export(
    filepath=dst
)

print("USD export:", result)

print("=" * 70)
print("DONE")
print(dst)
print("=" * 70)

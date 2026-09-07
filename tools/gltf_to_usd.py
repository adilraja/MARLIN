import bpy
import os
import sys


def calculate_world_bounds(objects):
    """Return combined evaluated world-space bounds for all mesh vertices."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bounds_min = [float("inf")] * 3
    bounds_max = [float("-inf")] * 3
    mesh_count = 0
    vertex_count = 0

    bpy.context.view_layer.update()

    for obj in objects:
        if obj.type != "MESH":
            continue

        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh()

        try:
            matrix_world = evaluated_obj.matrix_world
            mesh_count += 1

            for vertex in mesh.vertices:
                world_position = matrix_world @ vertex.co
                vertex_count += 1

                for axis in range(3):
                    coordinate = float(world_position[axis])
                    bounds_min[axis] = min(bounds_min[axis], coordinate)
                    bounds_max[axis] = max(bounds_max[axis], coordinate)
        finally:
            evaluated_obj.to_mesh_clear()

    if vertex_count == 0:
        raise RuntimeError(
            "The imported model contains no mesh vertices to measure."
        )

    dimensions = [
        bounds_max[axis] - bounds_min[axis]
        for axis in range(3)
    ]

    return {
        "bounds_min": tuple(bounds_min),
        "bounds_max": tuple(bounds_max),
        "dimensions": tuple(dimensions),
        "maximum_dimension": max(dimensions),
        "mesh_count": mesh_count,
        "vertex_count": vertex_count,
    }


def format_vector(values):
    return tuple(round(float(value), 6) for value in values)


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

world_bounds = calculate_world_bounds(
    bpy.context.scene.objects
)

print("\nWORLD-SPACE MODEL BOUNDS:")
print(
    "  minimum:",
    format_vector(world_bounds["bounds_min"]),
)
print(
    "  maximum:",
    format_vector(world_bounds["bounds_max"]),
)
print(
    "  dimensions X/Y/Z:",
    format_vector(world_bounds["dimensions"]),
)
print(
    "  maximum dimension:",
    round(float(world_bounds["maximum_dimension"]), 6),
)
print(
    "  measured meshes / vertices:",
    world_bounds["mesh_count"],
    "/",
    world_bounds["vertex_count"],
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

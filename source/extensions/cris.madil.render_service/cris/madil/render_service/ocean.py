"""Procedural ocean creation, materials, and animation APIs."""

import math

import omni.kit.app
import omni.usd
from pydantic import BaseModel, Field
from pxr import Gf, Sdf, UsdGeom, UsdShade

from .api import router
from .water_material import omnisurface_inputs

# =========================================================================
# CRIS Procedural Ocean
# =========================================================================



class OceanDataModel(BaseModel):
    """Parameters for creating a procedural ocean on the live USD stage."""

    name: str = Field(
        default="Ocean",
        description="USD prim name for the ocean",
    )

    size: float = Field(
        default=16000.0,
        gt=0.0,
        description="Total width/depth of the ocean in stage units",
    )

    resolution: int = Field(
        default=96,
        ge=8,
        le=256,
        description="Number of grid divisions along each axis",
    )

    wave_height: float = Field(
        default=40.0,
        ge=0.0,
        description="Approximate maximum wave amplitude",
    )

    wave_length: float = Field(
        default=650.0,
        gt=0.0,
        description="Base wavelength in stage units",
    )

    choppiness: float = Field(
        default=0.55,
        ge=0.0,
        le=1.5,
        description="Horizontal displacement applied to wave crests",
    )

    position: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="XYZ position of the complete ocean",
    )


@router.post(
    "/scene/ocean",
    summary="Create a procedural ocean on the live stage",
)
async def create_ocean(data: OceanDataModel):
    """Generate a Gerstner-style procedural ocean mesh on the live Kit stage."""

    if not Sdf.Path.IsValidIdentifier(data.name):
        return {
            "ok": False,
            "error": f"Invalid USD prim name: {data.name}",
        }

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No USD stage is currently open in Kit.",
        }

    UsdGeom.Xform.Define(stage, "/World")

    ocean_path = f"/World/{data.name}"

    # Replace a previous ocean with the same name.
    if stage.GetPrimAtPath(ocean_path):
        stage.RemovePrim(ocean_path)

    ocean = UsdGeom.Mesh.Define(stage, ocean_path)

    resolution = data.resolution
    vertex_count = resolution + 1
    spacing = data.size / resolution
    half_size = data.size * 0.5

    # Several waves travelling in different directions.
    # Together they produce a substantially more natural surface
    # than a single sine wave.
    wave_definitions = [
        # direction X, direction Z, amplitude multiplier,
        # wavelength multiplier, phase
        (1.00,  0.15, 0.52, 1.00, 0.00),
        (0.35,  1.00, 0.25, 0.58, 1.30),
        (-0.70, 0.55, 0.15, 0.34, 2.10),
        (0.80, -0.60, 0.08, 0.19, 3.40),
    ]

    points = []

    min_x = float("inf")
    min_y = float("inf")
    min_z = float("inf")

    max_x = float("-inf")
    max_y = float("-inf")
    max_z = float("-inf")

    for row in range(vertex_count):

        z = -half_size + row * spacing

        for column in range(vertex_count):

            x = -half_size + column * spacing

            displaced_x = x
            displaced_z = z
            height = 0.0

            for (
                direction_x,
                direction_z,
                amplitude_factor,
                wavelength_factor,
                phase_offset,
            ) in wave_definitions:

                # Normalize the wave direction.
                direction_length = math.sqrt(
                    direction_x * direction_x +
                    direction_z * direction_z
                )

                dx = direction_x / direction_length
                dz = direction_z / direction_length

                amplitude = data.wave_height * amplitude_factor
                wavelength = data.wave_length * wavelength_factor

                k = (2.0 * math.pi) / wavelength

                theta = (
                    k * (dx * x + dz * z)
                    + phase_offset
                )

                # Vertical displacement.
                height += amplitude * math.sin(theta)

                # Gerstner-style horizontal displacement.
                horizontal = (
                    data.choppiness
                    * amplitude
                    * math.cos(theta)
                )

                displaced_x += dx * horizontal
                displaced_z += dz * horizontal

            point = Gf.Vec3f(
                displaced_x,
                height,
                displaced_z,
            )

            points.append(point)

            min_x = min(min_x, displaced_x)
            min_y = min(min_y, height)
            min_z = min(min_z, displaced_z)

            max_x = max(max_x, displaced_x)
            max_y = max(max_y, height)
            max_z = max(max_z, displaced_z)

    # ------------------------------------------------------------------
    # Build quad topology.
    #
    # Winding is chosen so the surface normals face +Y.
    # ------------------------------------------------------------------

    face_vertex_counts = []
    face_vertex_indices = []

    for row in range(resolution):

        for column in range(resolution):

            i0 = row * vertex_count + column
            i1 = i0 + 1
            i3 = (row + 1) * vertex_count + column
            i2 = i3 + 1

            face_vertex_counts.append(4)

            face_vertex_indices.extend([
                i0,
                i3,
                i2,
                i1,
            ])

    ocean.GetPointsAttr().Set(points)
    ocean.GetFaceVertexCountsAttr().Set(face_vertex_counts)
    ocean.GetFaceVertexIndicesAttr().Set(face_vertex_indices)

    # Render the mesh exactly as generated rather than applying
    # subdivision automatically.
    ocean.GetSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
        # ------------------------------------------------------------------
    # Smooth per-vertex normals
    #
    # Without authored normals, a polygonal mesh using subdivision
    # scheme "none" is shaded face-by-face.  For water we want the
    # lighting to flow smoothly across the generated wave surface.
    # ------------------------------------------------------------------

    normals = []

    for row in range(vertex_count):

        for column in range(vertex_count):

            # Neighboring grid points used to estimate the local
            # tangent directions.
            left_col = max(column - 1, 0)
            right_col = min(column + 1, resolution)

            back_row = max(row - 1, 0)
            front_row = min(row + 1, resolution)

            p_left = points[
                row * vertex_count + left_col
            ]

            p_right = points[
                row * vertex_count + right_col
            ]

            p_back = points[
                back_row * vertex_count + column
            ]

            p_front = points[
                front_row * vertex_count + column
            ]

            # Tangent across X.
            tx = p_right - p_left

            # Tangent across Z.
            tz = p_front - p_back

            # tz × tx gives an upward-facing normal (+Y)
            # for a flat X/Z surface.
            nx = (
                tz[1] * tx[2]
                - tz[2] * tx[1]
            )

            ny = (
                tz[2] * tx[0]
                - tz[0] * tx[2]
            )

            nz = (
                tz[0] * tx[1]
                - tz[1] * tx[0]
            )

            normal_length = math.sqrt(
                nx * nx
                + ny * ny
                + nz * nz
            )

            if normal_length > 1e-8:

                nx /= normal_length
                ny /= normal_length
                nz /= normal_length

            else:

                nx = 0.0
                ny = 1.0
                nz = 0.0

            normals.append(
                Gf.Vec3f(nx, ny, nz)
            )

    ocean.CreateNormalsAttr().Set(normals)

    ocean.SetNormalsInterpolation(
        UsdGeom.Tokens.vertex
    )

    # Visible from above and below.
    ocean.GetDoubleSidedAttr().Set(True)

    # Explicit bounding box helps Kit/viewport framing.
    ocean.GetExtentAttr().Set([
        Gf.Vec3f(min_x, min_y, min_z),
        Gf.Vec3f(max_x, max_y, max_z),
    ])

    # Temporary ocean colour.
    #
    # This is NOT the final water material. It simply makes the
    # procedural surface easy to identify before we add realistic
    # transmission/reflection/refraction.
    ocean_prim = ocean.GetPrim()

    ocean_prim.CreateAttribute(
        "primvars:displayColor",
        Sdf.ValueTypeNames.Color3fArray,
    ).Set([
        Gf.Vec3f(0.025, 0.16, 0.24)
    ])

    ocean_prim.CreateAttribute(
        "primvars:displayColor:interpolation",
        Sdf.ValueTypeNames.Token,
    ).Set("constant")

    # Position the entire ocean.
    xform = UsdGeom.XformCommonAPI(ocean)

    xform.SetTranslate(
        Gf.Vec3d(
            data.position[0],
            data.position[1],
            data.position[2],
        )
    )

    total_vertices = len(points)
    total_faces = len(face_vertex_counts)

    print(
        f"[CRIS Render Service] Procedural ocean created: "
        f"{ocean_path}, "
        f"vertices={total_vertices}, "
        f"faces={total_faces}"
    )

    return {
        "ok": True,
        "prim_path": ocean_path,
        "size": data.size,
        "resolution": data.resolution,
        "vertices": total_vertices,
        "faces": total_faces,
        "wave_height": data.wave_height,
        "wave_length": data.wave_length,
        "choppiness": data.choppiness,
        "position": data.position,
    }


# =========================================================================
# CRIS Ocean Water Material
# =========================================================================



class OceanMaterialDataModel(BaseModel):
    """Configurable NVIDIA OmniSurface seawater parameters."""

    ocean_name: str = Field(default="Ocean")
    material_name: str = Field(default="OceanWater")
    ior: float = Field(default=1.333, ge=1.0, le=3.0)
    roughness: float = Field(default=0.045, ge=0.0, le=1.0)
    transmission: float = Field(default=1.0, ge=0.0, le=1.0)
    base_weight: float = Field(default=0.02, ge=0.0, le=1.0)
    base_color: tuple[float, float, float] = (0.02, 0.10, 0.13)
    transmission_color: tuple[float, float, float] = (0.78, 0.92, 0.95)
    transmission_depth: float = Field(default=100.0, ge=0.0)
    scattering_color: tuple[float, float, float] = (0.005, 0.02, 0.03)
    scattering_anisotropy: float = Field(default=0.0, ge=-1.0, le=1.0)
    thin_walled: bool = True


def _author_omnisurface_inputs(shader, data):
    value_types = {
        "bool": Sdf.ValueTypeNames.Bool,
        "float": Sdf.ValueTypeNames.Float,
        "color3f": Sdf.ValueTypeNames.Color3f,
    }

    for name, (value_kind, value) in omnisurface_inputs(data).items():
        if value_kind == "color3f":
            value = Gf.Vec3f(*value)
        shader.CreateInput(name, value_types[value_kind]).Set(value)


@router.post(
    "/scene/ocean/material",
    summary="Apply configurable NVIDIA OmniSurface seawater",
)
async def apply_ocean_material(data: OceanMaterialDataModel):
    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No live USD stage is currently open.",
        }

    ocean_path = f"/World/{data.ocean_name}"
    ocean_prim = stage.GetPrimAtPath(ocean_path)

    if not ocean_prim or not ocean_prim.IsValid():
        return {
            "ok": False,
            "error": f"Ocean does not exist: {ocean_path}",
        }

    if not Sdf.Path.IsValidIdentifier(data.material_name):
        return {
            "ok": False,
            "error": f"Invalid material name: {data.material_name}",
        }

    UsdGeom.Scope.Define(stage, "/World/Looks")
    material_path = Sdf.Path(f"/World/Looks/{data.material_name}")
    shader_path = material_path.AppendChild("Shader")

    # Recreate the material so legacy opacity inputs cannot survive an update.
    if stage.GetPrimAtPath(material_path):
        stage.RemovePrim(material_path)

    material = UsdShade.Material.Define(stage, material_path)
    shader = UsdShade.Shader.Define(stage, shader_path)

    shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    shader.SetSourceAsset("OmniSurface.mdl", "mdl")
    shader.SetSourceAssetSubIdentifier("OmniSurface", "mdl")
    shader.CreateOutput("out", Sdf.ValueTypeNames.Token)

    material.CreateSurfaceOutput("mdl").ConnectToSource(
        shader.ConnectableAPI(),
        "out",
    )

    _author_omnisurface_inputs(shader, data)
    UsdShade.MaterialBindingAPI.Apply(ocean_prim).Bind(material)

    print(
        "[CRIS Render Service] OmniSurface seawater bound: "
        f"{material_path} -> {ocean_path}"
    )

    return {
        "ok": True,
        "renderer": "NVIDIA OmniSurface",
        "ocean_path": ocean_path,
        "material_path": str(material_path),
        "roughness": data.roughness,
        "ior": data.ior,
        "transmission": data.transmission,
        "base_weight": data.base_weight,
        "base_color": data.base_color,
        "transmission_color": data.transmission_color,
        "transmission_depth": data.transmission_depth,
        "scattering_color": data.scattering_color,
        "scattering_anisotropy": data.scattering_anisotropy,
        "thin_walled": data.thin_walled,
    }

@router.get(
    "/scene/ocean/material/status",
    summary="Inspect the active ocean render material",
)
async def ocean_material_status():
    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {"ok": False, "error": "No live USD stage is open."}

    ocean_prim = stage.GetPrimAtPath("/World/Ocean")
    if not ocean_prim or not ocean_prim.IsValid():
        return {"ok": False, "error": "Ocean not found: /World/Ocean"}

    bound_material, _ = UsdShade.MaterialBindingAPI(
        ocean_prim
    ).ComputeBoundMaterial()

    if not bound_material or not bound_material.GetPrim().IsValid():
        return {"ok": False, "error": "Ocean has no bound material."}

    material_path = bound_material.GetPath()
    shader_prim = stage.GetPrimAtPath(material_path.AppendChild("Shader"))

    def attribute_value(name):
        attribute = shader_prim.GetAttribute(name)
        if not attribute or not attribute.IsValid():
            return None
        value = attribute.Get()
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        try:
            return tuple(float(component) for component in value)
        except (TypeError, ValueError):
            return str(value)

    return {
        "ok": True,
        "bound_material": str(material_path),
        "implementation_source": attribute_value("info:implementationSource"),
        "source_asset": attribute_value("info:mdl:sourceAsset"),
        "source_subidentifier": attribute_value(
            "info:mdl:sourceAsset:subIdentifier"
        ),
        "ior": attribute_value("inputs:specular_reflection_ior"),
        "transmission": attribute_value("inputs:specular_transmission_weight"),
        "transmission_color": attribute_value(
            "inputs:specular_transmission_color"
        ),
        "transmission_depth": attribute_value(
            "inputs:specular_transmission_scattering_depth"
        ),
        "scattering_color": attribute_value(
            "inputs:specular_transmission_scattering_color"
        ),
        "scattering_anisotropy": attribute_value(
            "inputs:specular_transmission_scatter_anisotropy"
        ),
        "thin_walled": attribute_value("inputs:thin_walled"),
    }
import omni.kit.app


_ocean_animation_subscription = None
_ocean_animation_state = None


class OceanAnimationDataModel(BaseModel):
    """Configuration for the live animated procedural ocean."""

    name: str = Field(
        default="Ocean",
        description="Ocean mesh prim name under /World",
    )

    size: float = Field(
        default=16000.0,
        gt=0.0,
    )

    resolution: int = Field(
        default=64,
        ge=16,
        le=128,
        description=(
            "Ocean grid resolution. Start with 64 for interactive animation."
        ),
    )

    wave_height: float = Field(
        default=40.0,
        ge=0.0,
    )

    wave_length: float = Field(
        default=650.0,
        gt=0.0,
    )

    choppiness: float = Field(
        default=0.55,
        ge=0.0,
        le=1.5,
    )

    speed: float = Field(
        default=1.0,
        ge=0.0,
        le=5.0,
        description="Wave animation speed multiplier",
    )

    target_fps: float = Field(
        default=20.0,
        ge=1.0,
        le=30.0,
        description="How often the procedural geometry is recalculated",
    )

    position: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
    )


def _build_ocean_topology(mesh, resolution):
    """Author the grid topology once. Only points change during animation."""

    vertex_count = resolution + 1

    face_vertex_counts = []
    face_vertex_indices = []

    for row in range(resolution):
        for column in range(resolution):

            i0 = row * vertex_count + column
            i1 = i0 + 1
            i3 = (row + 1) * vertex_count + column
            i2 = i3 + 1

            face_vertex_counts.append(4)

            face_vertex_indices.extend([
                i0,
                i3,
                i2,
                i1,
            ])

    mesh.GetFaceVertexCountsAttr().Set(
        face_vertex_counts
    )

    mesh.GetFaceVertexIndicesAttr().Set(
        face_vertex_indices
    )

    mesh.GetSubdivisionSchemeAttr().Set(
        UsdGeom.Tokens.none
    )

    mesh.GetDoubleSidedAttr().Set(True)

def _sample_animated_ocean_point(
    state,
    x,
    z,
    elapsed_time,
):
    """
    Evaluate the same Gerstner-style wave model used by the ocean mesh
    at one local X,Z location.

    Returns:
        displaced_x, height, displaced_z
    """

    displaced_x = x
    displaced_z = z
    height = 0.0

    for wave in state["waves"]:

        dx = wave["dx"]
        dz = wave["dz"]

        amplitude = wave["amplitude"]
        k = wave["k"]

        theta = (
            k * (dx * x + dz * z)
            + wave["phase"]
            + elapsed_time
            * state["speed"]
            * wave["phase_rate"]
        )

        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        # Vertical component.
        height += (
            amplitude
            * sin_theta
        )

        # Gerstner horizontal displacement.
        horizontal = (
            state["choppiness"]
            * amplitude
            * cos_theta
        )

        displaced_x += (
            dx * horizontal
        )

        displaced_z += (
            dz * horizontal
        )

    return (
        displaced_x,
        height,
        displaced_z,
    )
def _sample_ocean_surface_height(
    world_x,
    world_z,
):
    """
    Return the current ocean surface Y value at approximately
    the supplied world-space X,Z position.

    Returns None when no animated ocean is active.
    """

    global _ocean_animation_state

    state = _ocean_animation_state

    if state is None:
        return None

    ocean_position = state.get(
        "position",
        (0.0, 0.0, 0.0),
    )

    ocean_x = float(ocean_position[0])
    ocean_y = float(ocean_position[1])
    ocean_z = float(ocean_position[2])

    # Convert world location into ocean-local coordinates.
    local_x = (
        float(world_x)
        - ocean_x
    )

    local_z = (
        float(world_z)
        - ocean_z
    )

    _, local_height, _ = (
        _sample_animated_ocean_point(
            state,
            local_x,
            local_z,
            state["elapsed"],
        )
    )

    return (
        ocean_y
        + local_height
    )
def _calculate_animated_ocean(state, elapsed_time):
    """Calculate one frame of the animated Gerstner-style ocean."""

    resolution = state["resolution"]
    vertex_count = resolution + 1

    points = []

    min_x = float("inf")
    min_y = float("inf")
    min_z = float("inf")

    max_x = float("-inf")
    max_y = float("-inf")
    max_z = float("-inf")

    # ---------------------------------------------------------------
    # Generate animated vertices
    # ---------------------------------------------------------------

    for x, z in state["base_grid"]:

        displaced_x, height, displaced_z = (
            _sample_animated_ocean_point(
                state,
                x,
                z,
                elapsed_time,
            )
        )

        point = Gf.Vec3f(
            displaced_x,
            height,
            displaced_z,
        )

        points.append(point)

        min_x = min(min_x, displaced_x)
        min_y = min(min_y, height)
        min_z = min(min_z, displaced_z)

        max_x = max(max_x, displaced_x)
        max_y = max(max_y, height)
        max_z = max(max_z, displaced_z)

    # ---------------------------------------------------------------
    # Recalculate smooth normals for the moving surface
    # ---------------------------------------------------------------

    normals = []

    for row in range(vertex_count):

        for column in range(vertex_count):

            left_col = max(column - 1, 0)
            right_col = min(
                column + 1,
                resolution,
            )

            back_row = max(row - 1, 0)
            front_row = min(
                row + 1,
                resolution,
            )

            p_left = points[
                row * vertex_count + left_col
            ]

            p_right = points[
                row * vertex_count + right_col
            ]

            p_back = points[
                back_row * vertex_count + column
            ]

            p_front = points[
                front_row * vertex_count + column
            ]

            tx = p_right - p_left
            tz = p_front - p_back

            nx = (
                tz[1] * tx[2]
                - tz[2] * tx[1]
            )

            ny = (
                tz[2] * tx[0]
                - tz[0] * tx[2]
            )

            nz = (
                tz[0] * tx[1]
                - tz[1] * tx[0]
            )

            normal_length = math.sqrt(
                nx * nx +
                ny * ny +
                nz * nz
            )

            if normal_length > 1e-8:

                nx /= normal_length
                ny /= normal_length
                nz /= normal_length

            else:

                nx = 0.0
                ny = 1.0
                nz = 0.0

            normals.append(
                Gf.Vec3f(nx, ny, nz)
            )

    extent = [
        Gf.Vec3f(min_x, min_y, min_z),
        Gf.Vec3f(max_x, max_y, max_z),
    ]

    return points, normals, extent


def _update_animated_ocean(event):
    """Called from Kit's update loop."""

    global _ocean_animation_state

    state = _ocean_animation_state

    if state is None:
        return

    try:
        dt = float(event.payload["dt"])
    except Exception:
        dt = 1.0 / 60.0

    if dt <= 0.0:
        return

    state["accumulator"] += dt

    frame_interval = (
        1.0 / state["target_fps"]
    )

    # Avoid rebuilding thousands of vertices on every Kit frame.
    if state["accumulator"] < frame_interval:
        return

    elapsed_step = state["accumulator"]

    state["accumulator"] = 0.0
    state["elapsed"] += elapsed_step

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return

    ocean_prim = stage.GetPrimAtPath(
        state["ocean_path"]
    )

    if not ocean_prim or not ocean_prim.IsValid():
        return

    ocean = UsdGeom.Mesh(
        ocean_prim
    )

    points, normals, extent = (
        _calculate_animated_ocean(
            state,
            state["elapsed"],
        )
    )

    ocean.GetPointsAttr().Set(
        points
    )

    ocean.CreateNormalsAttr().Set(
        normals
    )

    ocean.SetNormalsInterpolation(
        UsdGeom.Tokens.vertex
    )

    ocean.GetExtentAttr().Set(
        extent
    )


def shutdown_ocean_animation():
    """Stop the update subscription safely."""

    global _ocean_animation_subscription
    global _ocean_animation_state

    _ocean_animation_subscription = None
    _ocean_animation_state = None


@router.post(
    "/scene/ocean/animation/start",
    summary="Start live procedural ocean animation",
)
async def start_ocean_animation(
    data: OceanAnimationDataModel,
):

    global _ocean_animation_subscription
    global _ocean_animation_state

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No live USD stage is open.",
        }

    if not Sdf.Path.IsValidIdentifier(data.name):
        return {
            "ok": False,
            "error": f"Invalid ocean name: {data.name}",
        }

    # Stop an existing animation first.
    shutdown_ocean_animation()

    UsdGeom.Xform.Define(
        stage,
        "/World",
    )

    ocean_path = f"/World/{data.name}"

    # Define() reuses the existing Ocean prim if present,
    # preserving a material binding that may already exist.
    ocean = UsdGeom.Mesh.Define(
        stage,
        ocean_path,
    )

    _build_ocean_topology(
        ocean,
        data.resolution,
    )

    # Ocean transform.
    xform = UsdGeom.XformCommonAPI(
        ocean,
    )

    xform.SetTranslate(
        Gf.Vec3d(*data.position)
    )

    # Give a newly created ocean a temporary fallback colour.
    ocean_prim = ocean.GetPrim()

    display_color_attr = ocean_prim.GetAttribute(
        "primvars:displayColor"
    )

    if not display_color_attr:
        ocean_prim.CreateAttribute(
            "primvars:displayColor",
            Sdf.ValueTypeNames.Color3fArray,
        ).Set([
            Gf.Vec3f(
                0.025,
                0.16,
                0.24,
            )
        ])

    # ---------------------------------------------------------------
    # Precompute the underlying flat grid.
    # ---------------------------------------------------------------

    spacing = (
        data.size / data.resolution
    )

    half_size = (
        data.size * 0.5
    )

    base_grid = []

    for row in range(
        data.resolution + 1
    ):

        z = (
            -half_size
            + row * spacing
        )

        for column in range(
            data.resolution + 1
        ):

            x = (
                -half_size
                + column * spacing
            )

            base_grid.append(
                (x, z)
            )

    # ---------------------------------------------------------------
    # Multiple directional wave components.
    #
    # phase_rate controls how rapidly each component moves.
    # ---------------------------------------------------------------

    definitions = [
        (1.00,  0.15, 0.52, 1.00, 0.00, 0.70),
        (0.35,  1.00, 0.25, 0.58, 1.30, 1.00),
        (-0.70, 0.55, 0.15, 0.34, 2.10, 1.35),
        (0.80, -0.60, 0.08, 0.19, 3.40, 1.80),
    ]

    waves = []

    for (
        direction_x,
        direction_z,
        amplitude_factor,
        wavelength_factor,
        phase,
        phase_rate,
    ) in definitions:

        direction_length = math.sqrt(
            direction_x * direction_x
            + direction_z * direction_z
        )

        dx = (
            direction_x
            / direction_length
        )

        dz = (
            direction_z
            / direction_length
        )

        amplitude = (
            data.wave_height
            * amplitude_factor
        )

        wavelength = (
            data.wave_length
            * wavelength_factor
        )

        k = (
            2.0
            * math.pi
            / wavelength
        )

        waves.append({
            "dx": dx,
            "dz": dz,
            "amplitude": amplitude,
            "k": k,
            "phase": phase,
            "phase_rate": phase_rate,
        })

    _ocean_animation_state = {
        "ocean_path": ocean_path,
        "size": float(data.size),
        "resolution": data.resolution,
        "base_grid": base_grid,
        "waves": waves,
        "choppiness": data.choppiness,
        "speed": data.speed,
        "target_fps": data.target_fps,
        "accumulator": 0.0,
        "elapsed": 0.0,

        # Needed when querying wave height in world coordinates.
        "position": tuple(data.position),
    }

    # Generate frame zero immediately.
    points, normals, extent = (
        _calculate_animated_ocean(
            _ocean_animation_state,
            0.0,
        )
    )

    ocean.GetPointsAttr().Set(points)

    ocean.CreateNormalsAttr().Set(normals)

    ocean.SetNormalsInterpolation(
        UsdGeom.Tokens.vertex
    )

    ocean.GetExtentAttr().Set(extent)

    # Subscribe to Kit's application update loop.
    _ocean_animation_subscription = (
        omni.kit.app
        .get_app()
        .get_update_event_stream()
        .create_subscription_to_pop(
            _update_animated_ocean,
            name="CRIS Animated Ocean",
        )
    )

    print(
        "[CRIS Render Service] "
        f"Ocean animation started: {ocean_path}"
    )

    return {
        "ok": True,
        "ocean_path": ocean_path,
        "size": data.size,
        "resolution": data.resolution,
        "vertices": (
            data.resolution + 1
        ) ** 2,
        "speed": data.speed,
        "target_fps": data.target_fps,
    }


@router.post(
    "/scene/ocean/animation/stop",
    summary="Stop live procedural ocean animation",
)
async def stop_ocean_animation():

    was_running = (
        _ocean_animation_subscription
        is not None
    )

    shutdown_ocean_animation()

    print(
        "[CRIS Render Service] "
        "Ocean animation stopped"
    )

    return {
        "ok": True,
        "was_running": was_running,
    }


@router.get(
    "/scene/ocean/animation/status",
    summary="Get live ocean animation status",
)
async def ocean_animation_status():

    running = (
        _ocean_animation_subscription is not None
        and _ocean_animation_state is not None
    )

    if not running:
        return {
            "running": False,
        }

    return {
        "running": True,
        "ocean_path": _ocean_animation_state["ocean_path"],
        "size": _ocean_animation_state["size"],
        "resolution": _ocean_animation_state["resolution"],
        "speed": _ocean_animation_state["speed"],
        "choppiness": _ocean_animation_state["choppiness"],
        "target_fps": _ocean_animation_state["target_fps"],
        "elapsed": _ocean_animation_state["elapsed"],
    }
# =========================================================================
# CRIS Live Ocean Animation Control
# =========================================================================


# =========================================================================
# CRIS Live Ocean Animation Control
# =========================================================================


class OceanAnimationUpdateDataModel(BaseModel):

    speed: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
    )

    choppiness: float | None = Field(
        default=None,
        ge=0.0,
        le=1.5,
    )

    target_fps: float | None = Field(
        default=None,
        ge=1.0,
        le=30.0,
    )


@router.post(
    "/scene/ocean/animation/update",
    summary="Update live ocean animation parameters",
)
async def update_ocean_animation(
    data: OceanAnimationUpdateDataModel,
):

    global _ocean_animation_state

    if _ocean_animation_state is None:
        return {
            "ok": False,
            "error": "Ocean animation is not running.",
        }

    changed = {}

    if data.speed is not None:
        _ocean_animation_state["speed"] = data.speed
        changed["speed"] = data.speed

    if data.choppiness is not None:
        _ocean_animation_state["choppiness"] = data.choppiness
        changed["choppiness"] = data.choppiness

    if data.target_fps is not None:
        _ocean_animation_state["target_fps"] = data.target_fps
        changed["target_fps"] = data.target_fps

    if not changed:
        return {
            "ok": False,
            "error": "No parameters were supplied.",
        }

    print(
        "[CRIS Render Service] "
        f"Ocean animation updated: {changed}"
    )

    return {
        "ok": True,
        "ocean_path": _ocean_animation_state["ocean_path"],
        "changed": changed,
        "current": {
            "speed": _ocean_animation_state["speed"],
            "choppiness": _ocean_animation_state["choppiness"],
            "target_fps": _ocean_animation_state["target_fps"],
        },
    }

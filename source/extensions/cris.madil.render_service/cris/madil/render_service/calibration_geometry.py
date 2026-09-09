"""Explicit ideal-pinhole engineering fixture; not a survey camera replica."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class CalibrationConfig:
    meters_per_scene_unit: float
    image_width_px: int
    image_height_px: int
    focal_length_mm: float
    pixel_pitch_um: float
    height_above_target_m: float
    target_width_m: float
    target_height_m: float
    target_plane_y_m: float
    pitch_deg: float = 0
    roll_deg: float = 0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(name + ' must be finite numeric data')
            if name not in ('target_plane_y_m','pitch_deg','roll_deg') and value <= 0:
                raise ValueError(name + ' must be positive')
        if not 0 <= self.pitch_deg <= 60 or abs(self.roll_deg) > 45:
            raise ValueError('Engineering pitch must be 0–60 degrees, roll within ±45 degrees')
        for name in ('image_width_px', 'image_height_px'):
            value = getattr(self, name)
            if type(value) is not int or not 64 <= value <= 2048:
                raise ValueError(name + ' must be an integer from 64 to 2048')
        if not 1e-6 <= self.meters_per_scene_unit <= 100:
            raise ValueError('Scene unit size is outside the engineering test range')
        if max(abs(self.target_plane_y_m), self.height_above_target_m,
               self.target_width_m, self.target_height_m) / self.meters_per_scene_unit > 1e8:
            raise ValueError('Geometry exceeds the safe scene-coordinate range')
        w, h = self.expected_size_px
        if not all(math.isfinite(v) for v in (w,h)) or min(w, h) < 16 or w > self.image_width_px - 16 or h > self.image_height_px - 16:
            raise ValueError('Target must span at least 16 pixels and fit with an image margin')
        for target in self.targets():
            x,y,w,h = target['expected_bbox_xywh_px']
            if min(w,h)<16 or x<4 or y<4 or x+w>self.image_width_px-4 or y+h>self.image_height_px-4:
                raise ValueError('Projected fixture targets must fit inside the image')

    def basis(self):
        p,r = math.radians(self.pitch_deg),math.radians(self.roll_deg)
        right0,up0,forward = (1,0,0),(0,math.sin(p),-math.cos(p)),(0,-math.cos(p),-math.sin(p))
        right = tuple(math.cos(r)*a+math.sin(r)*b for a,b in zip(right0,up0))
        up = tuple(-math.sin(r)*a+math.cos(r)*b for a,b in zip(right0,up0))
        return right,up,forward

    def camera_position(self):
        return (0,self.target_plane_y_m+self.height_above_target_m,
                self.height_above_target_m*math.tan(math.radians(self.pitch_deg)))

    def ray_plane(self,u,v):
        right,up,forward = self.basis()
        f = self.focal_length_mm/(self.pixel_pitch_um*0.001)
        ray = tuple(a+b*(u-self.image_width_px/2)/f-c*(v-self.image_height_px/2)/f
                    for a,b,c in zip(forward,right,up))
        if ray[1]>=-1e-8:
            raise ValueError('Image ray misses the target plane')
        t = -self.height_above_target_m/ray[1]
        return tuple(a+t*b for a,b in zip(self.camera_position(),ray))

    def project(self,point):
        right,up,forward = self.basis()
        delta = tuple(a-b for a,b in zip(point,self.camera_position()))
        dot = lambda a,b: sum(x*y for x,y in zip(a,b))
        depth = dot(delta,forward)
        if depth<=0:
            raise ValueError('Target is behind camera')
        f = self.focal_length_mm/(self.pixel_pitch_um*0.001)
        return (self.image_width_px/2+f*dot(delta,right)/depth,
                self.image_height_px/2-f*dot(delta,up)/depth)

    def local_gsd(self,u,v):
        # One-pixel ground-plane distances along image columns and rows.
        return [100*math.dist(self.ray_plane(u-0.5,v),self.ray_plane(u+0.5,v)),
                100*math.dist(self.ray_plane(u,v-0.5),self.ray_plane(u,v+0.5))]

    def targets(self):
        positions = [(0.5,0.5)] if self.pitch_deg==0 and self.roll_deg==0 else [(u,v) for v in (0.15,0.5,0.85) for u in (0.15,0.5,0.85)]
        result = []
        for i,(u,v) in enumerate(positions):
            u,v = u*self.image_width_px,v*self.image_height_px
            cx,cy,cz = self.ray_plane(u,v)
            corners = [(cx+x*self.target_width_m/2,cy,cz+z*self.target_height_m/2)
                       for x,z in [(-1,-1),(-1,1),(1,1),(1,-1)]]
            poly = [self.project(p) for p in corners]
            xs,ys = zip(*poly)
            result.append({'id': 'Target_%02d'%i,'center_world_m':[cx,cy,cz],
                           'sample_image_px':[u,v], 'corners_world_m':corners,
                           'expected_polygon_px':poly,
                           'expected_bbox_xywh_px':[min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)],
                           'local_gsd_xy_cm_px':self.local_gsd(u,v)})
        return result

    @property
    def gsd_m_px(self):
        return self.height_above_target_m * self.pixel_pitch_um * 0.001 / self.focal_length_mm

    @property
    def expected_size_px(self):
        return self.target_width_m / self.gsd_m_px, self.target_height_m / self.gsd_m_px

    def metadata(self):
        w, h = self.expected_size_px
        fx = self.focal_length_mm / (self.pixel_pitch_um * 0.001)
        return {'schema_version': '1.1.0', 'test_kind': 'engineering_oblique_planar_targets' if self.pitch_deg or self.roll_deg else 'engineering_nadir_planar_target',
                'scientific_camera_calibrated': False, 'config': asdict(self),
                'gsd_cm_px': self.gsd_m_px * 100,
                'gsd_note':'Reference nadir GSD at vertical height; use per-target directional GSD for oblique geometry.',
                'expected_bbox_xywh_px': self.targets()[len(self.targets())//2]['expected_bbox_xywh_px'],
                'targets':self.targets(),
                'intrinsics_px': {'fx': fx, 'fy': fx, 'cx': self.image_width_px/2, 'cy': self.image_height_px/2},
                'projection': 'ideal perspective, square pixels, zero distortion, no aperture offset',
                'image_coordinates': 'top-left edge origin; pixel centers at (column+0.5,row+0.5)',
                'camera_position_m': self.camera_position(), 'world_up': 'Y',
                'camera_basis_right_up_forward':self.basis(),
                'pose_convention':'Engineering only: pitch tilts optical axis toward world -Z from nadir; positive roll rotates camera right toward unrolled up. Not PI HiDef convention.',
                'seed': 0, 'randomisation': 'none; deterministic geometry, RGB not guaranteed bitwise deterministic'}


def build_stage(stage, config):
    from pxr import Gf, Sdf, UsdGeom, UsdShade
    c = config
    unit = c.meters_per_scene_unit
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, unit)
    root = UsdGeom.Xform.Define(stage, '/Calibration')
    stage.SetDefaultPrim(root.GetPrim())

    def plane(name, width, height, y, color, cx=0,cz=0):
        mesh = UsdGeom.Mesh.Define(stage, '/Calibration/' + name)
        mesh.CreatePointsAttr([Gf.Vec3f((x+cx)/unit, y/unit, (z+cz)/unit) for x,z in
                               [(-width/2,-height/2),(-width/2,height/2),(width/2,height/2),(width/2,-height/2)]])
        mesh.CreateFaceVertexCountsAttr([4])
        mesh.CreateFaceVertexIndicesAttr([0,1,2,3])
        mesh.CreateSubdivisionSchemeAttr('none')
        mesh.CreateDoubleSidedAttr(True)
        material = UsdShade.Material.Define(stage, '/Calibration/Looks/' + name)
        shader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild('Shader'))
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0))
        shader.CreateInput('emissiveColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(color))
        shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput('useSpecularWorkflow', Sdf.ValueTypeNames.Int).Set(1)
        shader.CreateInput('specularColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0))
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)

    for target in c.targets():
        x,y,z = target['center_world_m']
        plane(target['id'],c.target_width_m,c.target_height_m,y,1,x,z)
    plane('Background', c.image_width_px*c.gsd_m_px*10, c.image_height_px*c.gsd_m_px*10,
          c.target_plane_y_m-0.01, 0)
    camera = UsdGeom.Camera.Define(stage, '/Calibration/Camera')
    camera.CreateProjectionAttr('perspective')
    # USD focal length and apertures are expressed in tenths of a scene unit.
    camera.CreateFocalLengthAttr(c.focal_length_mm / (100*unit))
    camera.CreateHorizontalApertureAttr(c.image_width_px*c.pixel_pitch_um*1e-5/unit)
    camera.CreateVerticalApertureAttr(c.image_height_px*c.pixel_pitch_um*1e-5/unit)
    camera.CreateHorizontalApertureOffsetAttr(0)
    camera.CreateVerticalApertureOffsetAttr(0)
    camera.CreateClippingRangeAttr(Gf.Vec2f(c.height_above_target_m*0.01/unit, c.height_above_target_m*5/unit))
    camera.CreateFStopAttr(0)
    right,up,forward = c.basis()
    matrix = Gf.Matrix4d(1)
    for i,row in enumerate((right,up,tuple(-a for a in forward))):
        matrix.SetRow(i,Gf.Vec4d(*row,0))
    matrix.SetRow(3,Gf.Vec4d(*(a/unit for a in c.camera_position()),1))
    camera.AddTransformOp().Set(matrix)
    return camera

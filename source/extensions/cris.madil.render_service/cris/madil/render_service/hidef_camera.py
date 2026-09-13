"""HiDef oblique ideal-pinhole reconstruction, not certified camera intrinsics."""
import math
from dataclasses import dataclass
from .calibration_geometry import CalibrationConfig, build_stage

ROLLS = (7.77, 23.17, 7.7675, 23.1748)


@dataclass(frozen=True)
class HiDefConfig(CalibrationConfig):
    aperture_basis: str = 'paper_effective'
    downsample: int = 4

    def __post_init__(self):
        if self.roll_deg not in ROLLS or self.pitch_deg != 30:
            raise ValueError('HiDef requires pitch 30 degrees from nadir and a supported roll case')
        if self.downsample not in (1, 2, 4):
            raise ValueError('Resolution divisor must be 1, 2 or 4')
        if (self.image_width_px, self.image_height_px) != (6576//self.downsample, 2192//self.downsample):
            raise ValueError('HiDef output must retain the 3:1 image aspect')
        if self.aperture_basis not in ('paper_effective', 'manufacturer_roi_hypothesis'):
            raise ValueError('Unknown aperture basis')
        if self.focal_length_mm != 150 or self.height_above_target_m != 549:
            raise ValueError('HiDef reference requires 150 mm and 549 m camera-to-plane separation')
        for target in self.targets():
            x,y,w,h = target['expected_bbox_xywh_px']
            if min(w,h)<16 or min(x,y)<4 or x+w>self.image_width_px-4 or y+h>self.image_height_px-4:
                raise ValueError('HiDef metric targets do not fit output')

    def basis(self):
        # R_x(pitch) R_z(roll) R_nadir, not optical-axis image roll.
        p,r = math.radians(self.pitch_deg), math.radians(self.roll_deg)
        cp,sp,cr,sr = math.cos(p),math.sin(p),math.cos(r),math.sin(r)
        return ((cr,cp*sr,sp*sr), (0,sp,-cp), (sr,-cp*cr,-sp*cr))

    def camera_position(self):
        return (0, self.target_plane_y_m + self.height_above_target_m, 0)

    def metadata(self):
        result = super().metadata()
        result.update(test_kind='hidef_oblique_reconstruction', camera_model='Prosilica GT6600C',
                      model_status='inferred from survey metadata; not deployment certified',
                      reference_resolution=[6576,2192], downsample=self.downsample,
                      acquisition_mode='unresolved; ROI more plausible, binning possible',
                      aperture_basis=self.aperture_basis,
                      effective_sensor_mm=[self.pixel_pitch_um*self.image_width_px/1000,
                                           self.pixel_pitch_um*self.image_height_px/1000],
                      principal_point_status='centred reconstruction assumption; deployed ROI origin unresolved',
                      pose_convention='Y-up; Rx(pitch) Rz(roll) R_nadir; roll is cross-track tilt, not optical-axis rotation',
                      roll_status='geometrically inferred, not measured mounting angle',
                      altitude_status='549 m nominal camera-to-plane separation; historical altitude barometric',
                      distortion_status='zero assumed; lens model and calibration unavailable',
                      radiometry_status='not simulated: Bayer processing, noise, lens MTF, motion blur',
                      reference_nominal_nadir_gsd_cm_px=result['gsd_cm_px']/self.downsample,
                      geometry_only=True)
        return result


def configuration(roll_deg=7.77, downsample=4, aperture_basis='paper_effective'):
    pitch = 36000/6576 if aperture_basis == 'paper_effective' else 5.5
    return HiDefConfig(meters_per_scene_unit=.01, image_width_px=6576//downsample,
                       image_height_px=2192//downsample, focal_length_mm=150,
                       pixel_pitch_um=pitch*downsample, height_above_target_m=549,
                       target_width_m=8, target_height_m=8, target_plane_y_m=0,
                       pitch_deg=30, roll_deg=roll_deg, downsample=downsample,
                       aperture_basis=aperture_basis)


def build_hidef_stage(stage, config):
    camera = build_stage(stage, config)
    # The oblique footprint is displaced from the origin. Expand only the
    # fixture's black background, not the targets or camera geometry.
    from pxr import UsdGeom
    background = UsdGeom.Mesh(stage.GetPrimAtPath('/Calibration/Background'))
    background.GetPointsAttr().Set([p*4 for p in background.GetPointsAttr().Get()])
    camera.GetPrim().SetCustomDataByKey('cameraModel', 'HiDef_Prosilica_GT6600C_reconstruction')
    return camera

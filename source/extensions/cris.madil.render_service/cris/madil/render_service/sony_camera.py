"""Provisional Sony trial pinhole geometry; not a calibrated flight camera."""
from dataclasses import dataclass
from .calibration_geometry import CalibrationConfig


@dataclass(frozen=True)
class SonyConfig(CalibrationConfig):
    downsample: int = 8

    def __post_init__(self):
        if type(self.downsample) is not int or self.downsample not in (1, 8):
            raise ValueError('Sony supports native geometry or divisor-8 preview')
        expected = dict(meters_per_scene_unit=.01, image_width_px=9504//self.downsample,
                        image_height_px=6336//self.downsample, focal_length_mm=85,
                        pixel_pitch_um=35700/9504*self.downsample,
                        height_above_target_m=150, target_plane_y_m=0,
                        pitch_deg=0, roll_deg=0, target_width_m=8, target_height_m=8)
        if any(getattr(self, key) != value for key, value in expected.items()):
            raise ValueError('Sony provisional profile geometry must remain fixed')

    def target_image_positions(self):
        # Test the full image, not just the nadir principal point. Diagnostic
        # targets only: no camera parameter or animal geometry is changed.
        return [(u,v) for v in (.15,.5,.85) for u in (.15,.5,.85)]

    def metadata(self):
        result = super().metadata()
        for key in ('targets', 'expected_bbox_xywh_px', 'gsd_cm_px'):
            result.pop(key, None)
        result.update(
            test_kind='sony_provisional_nadir_pinhole', camera_model='Sony ILX-LR1',
            model_status='published trial camera; not individually calibrated',
            reference_resolution=[9504, 6336], downsample=self.downsample,
            effective_sensor_mm=[35.7, 23.8],
            reference_nominal_nadir_gsd_cm_px=self.gsd_m_px*100/self.downsample,
            output_nominal_nadir_gsd_cm_px=self.gsd_m_px*100,
            nominal_footprint_m=[63.0, 42.0],
            acquisition_mode='9504 x 6336 full-frame 3:2 supported manufacturer mode; trial selection unresolved',
            principal_point_status='centred ideal-pinhole assumption; not measured',
            pose_convention='Y-up; nadir assumed, image right +X, image down +Z; trial mounting pitch/roll/yaw unresolved',
            altitude_status='150 m published flight altitude, assumed camera-to-flat-plane separation; trial height reference unresolved',
            distortion_status='zero assumed, not measured; exact lens and calibration unresolved',
            radiometry_status='No calibrated noise, MTF, shutter/readout, motion blur or lens corrections',
            geometry_only=True,
            evidence={
                'published_trial': {'camera':'Sony ILX-LR1', 'focal_length_mm':85,
                                    'flight_altitude_m':150, 'platform':'autonomous fixed-wing UAV'},
                'manufacturer_specification': {'sensor_mm':[35.7,23.8], 'supported_large_3_2_px':[9504,6336]},
                'assumed_for_simulation': ['full-frame large 3:2 mode', 'nadir mount', 'centred principal point',
                                           'zero distortion', '150 m camera-to-plane height'],
                'unresolved_trial_specific': ['image mode/crop/format', 'mounting pitch/roll/yaw',
                    'exact 85 mm lens', 'focus/aperture', 'intrinsics/distortion', 'lens correction',
                    'shutter mode/exposure/readout', 'flight speed/trigger interval', 'altitude reference']},
            manufacturer_sources=[
                'https://helpguide.sony.net/ilc/2390/v1/en/contents/221h_specifications.html',
                'https://helpguide.sony.net/ilc/2390/v1/en/contents/0404M_jpeg_image_size.html'],
            validation_targets={'source':'Bartlett et al. (2025), Ecological Informatics 90, 103242; trial parameters supplied by user',
                                'nominal_gsd_cm_px':0.6629, 'nominal_swath_width_m':63,
                                'usage':'comparison only; not fitted geometry inputs'})
        return result


def configuration(downsample=8):
    if type(downsample) is not int or downsample not in (1, 8):
        raise ValueError('Sony supports native geometry or divisor-8 preview')
    return SonyConfig(meters_per_scene_unit=.01, image_width_px=9504//downsample,
                      image_height_px=6336//downsample, focal_length_mm=85,
                      pixel_pitch_um=35700/9504*downsample, height_above_target_m=150,
                      target_width_m=8, target_height_m=8, target_plane_y_m=0,
                      downsample=downsample)

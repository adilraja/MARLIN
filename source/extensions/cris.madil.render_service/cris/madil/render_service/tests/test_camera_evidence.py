import json
from pathlib import Path
import unittest


class CameraEvidenceTests(unittest.TestCase):
    def test_paper_nominal_and_provenance_categories(self):
        path = Path(__file__).resolve().parents[4]/'config/camera_hardware_evidence_v1.json'
        data = json.loads(path.read_text())
        h = data['hidef']
        self.assertEqual(h['roll_source'],'inferred_from_ground_footprint_geometry')
        self.assertEqual(h['simulation_rolls_deg'],[7.7675,23.1748])
        self.assertEqual(h['initial_roll_estimates_deg'],[7.5,22.5])
        self.assertIn('inferred from metadata',h['model_status'])
        self.assertEqual(h['acquisition']['acquisition_mode'],'unresolved')
        self.assertIsNone(h['acquisition']['roi_origin_px'])
        p = h['paper_nominal_pinhole']
        for sensor,pixels in zip(p['sensor_dimensions_mm'],p['image_dimensions_px']):
            self.assertAlmostEqual(100*p['camera_to_plane_separation_m']*sensor/p['focal_length_mm']/pixels,2.0036,places=4)
        self.assertEqual(data['sony']['published_trial_parameters']['nominal_gsd_cm_px'],0.6629)

    def test_paper_review_distinguishes_pitch_from_yaw_inference(self):
        path = Path(__file__).resolve().parents[4]/'config/camera_hardware_evidence_v1.json'
        data = json.loads(path.read_text())
        review = data['hidef']['paper_review']
        self.assertEqual(review['nominal_pitch_from_nadir_deg'],30)
        self.assertEqual(review['glare_handling'],'possible 180-deg rig yaw reversal')
        self.assertIsNone(review['exact_yaw_convention'])
        self.assertFalse(review['pitch_sign_reversal_inferred'])
        self.assertFalse(review['full_rotation_convention_resolved'])
        self.assertFalse(data['hidef']['pose_convention_confirmed'])
        self.assertFalse(data['applied_to_survey_config'])

    def test_independent_consistency_calculations(self):
        path = Path(__file__).resolve().parents[4]/'config/camera_hardware_evidence_v1.json'
        data = json.loads(path.read_text())
        self.assertFalse(data['applied_to_survey_config'])
        h = data['hidef']
        check = h['nadir_consistency_check']
        self.assertAlmostEqual(check['height_m']*h['native_pixel_pitch_um'][0]/check['focal_length_mm']*0.1,check['derived_gsd_cm_px'])
        self.assertFalse(h['output_sampling_and_crop_confirmed'])
        self.assertEqual(h['native_resolution_px'][1],2*h['pi_output_resolution_px'][1])
        s = data['sony']
        pitches = [mm*1000/px for mm,px in zip(s['published_sensor_dimensions_mm'],s['documented_mode_resolution_px'])]
        for pitch in pitches:
            self.assertAlmostEqual(pitch,s['derived_effective_pitch_um'])
        check = s['nadir_consistency_check']
        self.assertAlmostEqual(check['height_m']*pitches[0]/check['focal_length_mm']*0.1,check['derived_gsd_cm_px'])
        self.assertAlmostEqual(check['height_m']*s['published_sensor_dimensions_mm'][0]/check['focal_length_mm'],check['derived_horizontal_swath_m'])
        self.assertFalse(s['trial_mode_confirmed'])


if __name__ == '__main__':
    unittest.main()

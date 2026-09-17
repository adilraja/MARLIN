"""Offline comparison tests; run with NumPy and Pillow."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
from analyse_tile_diagnostics import analyse, error, pixels
from verify_capture_projection import verify


class DiagnosticTests(unittest.TestCase):
    def test_full_image_verifier_rejects_partial_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            for meta in ({'tile_diagnostic':{'mode':'baseline'}},
                         {'native_tiling':{'complete_image':False}}):
                (path/'metadata.json').write_text(json.dumps(meta))
                with self.assertRaisesRegex(ValueError,'not a complete image'):
                    verify(path)

    def test_error_uses_absolute_rgb_and_rejects_empty_or_mismatched(self):
        a=np.array([[[1.,2.,3.]]])
        b=np.array([[[4.,0.,7.]]])
        self.assertEqual(error(a,b),{'mean_absolute_rgb_error':3.,'max_absolute_rgb_error':4.})
        with self.assertRaises(ValueError):
            error(a,np.zeros((2,2,3)))
        with self.assertRaises(ValueError):
            error(np.zeros((0,3)),np.zeros((0,3)))

    def test_crops_use_global_pixels_including_negative_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            data=np.arange(6*4*3,dtype=np.uint8).reshape(4,6,3)
            Image.fromarray(data).save(path/'tile.png')
            record={'bounds':[-2,-1,4,3],'file':'tile.png'}
            np.testing.assert_equal(pixels(path,record,[-1,0,2,2]),data[1:3,1:4])
            with self.assertRaises(ValueError):
                pixels(path,record,[-3,0,2,2])

    def test_refuses_different_snapshot_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for i in range(2):
                path=Path(directory)/str(i)
                path.mkdir()
                records=[{'file':name,'bounds':[0,0,1,1],'tile_index':index}
                         for index,name in enumerate(('a.png','b.png'))]
                for record in records:
                    Image.new('RGB',(1,1)).save(path/record['file'])
                meta={'scene_sha256':str(i),'tile_diagnostic':{'mode':'baseline'},
                      'main_viewport_preserved':True,
                      'native_tiling':{'tiles':records,'guard_pixels':0,
                        'overlap_checks':[{'tiles':['a.png','b.png'],
                            'overlap_bounds':[0,0,1,1],'identical_tile_repeat':False}]}}
                (path/'metadata.json').write_text(json.dumps(meta))
                paths.append(path)
            with self.assertRaisesRegex(ValueError,'same frozen scene'):
                analyse(paths)


if __name__=='__main__':
    unittest.main()

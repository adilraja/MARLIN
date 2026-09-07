"""Pure layout checks for the temporary cetacean calibration gallery."""

import ast
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "cetacean_gallery.py"


def load_gallery_constants():
    tree = ast.parse(MODULE_PATH.read_text())

    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name)
                and target.id == "GALLERY_ASSETS"
                for target in node.targets
            ):
                return ast.literal_eval(node.value)

    raise AssertionError("GALLERY_ASSETS was not found")


class CetaceanGalleryTests(unittest.TestCase):
    def test_gallery_contains_every_converted_model(self):
        assets = load_gallery_constants()
        self.assertEqual(len(assets), 11)
        self.assertEqual(len({name for name, _species in assets}), 11)
        self.assertIn(("Manatee", "manatee"), assets)

    def test_every_gallery_usd_exists(self):
        project_root = MODULE_PATH.parents[6]

        for _name, species in load_gallery_constants():
            asset = (
                project_root
                / "assets"
                / "cetaceans"
                / species
                / "usd"
                / f"{species}.usd"
            )
            self.assertTrue(asset.is_file(), str(asset))


if __name__ == "__main__":
    unittest.main()

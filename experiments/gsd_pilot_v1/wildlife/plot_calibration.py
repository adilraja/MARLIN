"""Plot measured geometry and landmark candidates; requires NumPy and Pillow.

These are diagnostic point plots, not rendered training images or silhouettes.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def run():
    root = Path(__file__).resolve().parent
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    for species in ['european_storm_petrel', 'harbour_porpoise']:
        with np.load(root / (species + '_measurement_points.npz')) as data:
            points, landmarks, names = data['points_m'], data['landmark_points_m'], data['landmark_names']
        image = Image.new('RGB', (1200, 750), 'white')
        draw = ImageDraw.Draw(image)
        draw.text((30, 15), species.replace('_', ' ').title() + ' — evaluated geometry, metres', fill='black', font=font)
        for panel, (a, b, title) in enumerate([(0, 2, 'Dorsal X / Z'), (2, 1, 'Side Z / Y')]):
            low, high = points[:, [a, b]].min(0), points[:, [a, b]].max(0)
            scale = min(470 / (high[0] - low[0]), 500 / (high[1] - low[1]))
            center = (low + high) / 2
            def project(values):
                return np.column_stack([panel * 600 + 300 + (values[:, a] - center[0]) * scale,
                                        340 - (values[:, b] - center[1]) * scale])
            draw.point([tuple(point) for point in project(points)], fill='#253345')
            for i, (x, y) in enumerate(project(landmarks)):
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill='#cc3040')
                draw.text((x + 5, y - 20), str(i + 1), fill='#cc3040', font=font)
            draw.text((panel * 600 + 40, 55), title, fill='black', font=font)
            draw.text((panel * 600 + 40, 630), 'Extents: ' + str(np.round(high - low, 4).tolist()) + ' m', fill='black', font=font)
        for i, name in enumerate(names):
            draw.text((30 + (i % 2) * 590, 665 + (i // 2) * 30), str(i + 1) + ': ' + name.replace('_', ' '), fill='#cc3040', font=font)
        image.save(root / (species + '_geometry.png'))


if __name__ == '__main__':
    run()

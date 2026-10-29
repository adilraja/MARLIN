"""Build labelled comparison crops and scientific plots from measured captures."""
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/marlin_m3_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = json.loads((ROOT / 'qa/measurements_final.json').read_text())['rows']
    output = ROOT / 'comparisons'
    output.mkdir(exist_ok=True)

    def select(condition, depth, distance=100):
        return next(r for r in rows if r['request']['condition'] == condition
                    and r['request']['depth_m'] == depth and r['request']['native_distance'] == distance
                    and r['request']['meters_per_scene_unit'] == .01
                    and not r['request']['tone_map_probe'] and not r['request']['exposure_probe'])

    def montage(columns, filename):
        canvas = Image.new('RGB', (len(columns)*256, 3*290+36), '#101820')
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 10), 'HDR previews: fixed clip(RGB/12000,0,1)^(1/2.2), 160x160 crop enlarged 1.5x', fill='white')
        for y, depth in enumerate((.25, .75, 1.25)):
            for x, (label, condition, distance) in enumerate(columns):
                row = select(condition, depth, distance)
                pixels = np.load(ROOT / row['directory'] / 'hdr.npz', allow_pickle=False)['rgba'][..., :3]
                im = Image.fromarray(np.uint8(np.clip(pixels / 12000, 0, 1)**(1/2.2)*255))
                im = im.crop((176, 112, 336, 272)).resize((240, 240), Image.Resampling.NEAREST)
                canvas.paste(im, (x*256+8, y*290+72))
                draw.text((x*256+8, y*290+45), f'{label}; target depth {depth:.2f} m', fill='white')
        canvas.save(output / filename)

    montage([('Clear', 'clear', 100), ('Abs. D=50', 'absorption', 50),
             ('Abs. D=100', 'absorption', 100), ('Abs. D=200', 'absorption', 200)], 'absorption_depth_grid.png')
    montage([('Absorption only', 'absorption', 100), ('Scatter .02', 'scattering_low', 100),
             ('Scatter .05', 'scattering_high', 100)], 'scattering_depth_grid.png')
    row = select('clear', 1.25)
    pixels = np.load(ROOT / row['directory'] / 'hdr.npz', allow_pickle=False)['rgba'][..., :3]
    im = Image.fromarray(np.uint8(np.clip(pixels / 12000, 0, 1)**(1/2.2)*255))
    draw = ImageDraw.Draw(im)
    draw.rectangle((248, 184, 263, 199), outline='red')
    for x0 in (190, 306): draw.rectangle((x0, 184, x0+15, 199), outline='yellow')
    im.save(output / 'fixed_roi_check.png')

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), constrained_layout=True)
    for ax, channel, colour in zip(axes, range(3), ('#c23b35', '#278046', '#2b62b9')):
        for distance, style in ((50, ':'), (100, '-'), (200, '--')):
            chosen = [select('absorption', d, distance) for d in (.25, .75, 1.25)]
            ax.plot([r['request']['depth_m'] for r in chosen],
                    [r['hdr']['signal_relative_to_clear_rgb'][channel] for r in chosen],
                    style, marker='o', color=colour, label=f'Native distance {distance}')
        ax.set(title=f'{"RGB"[channel]} channel', xlabel='Physical target depth (m)',
               ylabel='HDR target-background / clear control')
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('Absorption-only engineering sweep; native HdrColor AOV, fixed ROIs')
    fig.savefig(output / 'absorption_signal.png', dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for condition, label, colour in [('absorption', 'Scatter 0', '#444444'),
                                    ('scattering_low', 'Scatter .02', '#26799a'),
                                    ('scattering_high', 'Scatter .05', '#a76121')]:
        chosen = [select(condition, d) for d in (.25, .75, 1.25)]
        for ax, key in zip(axes, ('signal_rgb', 'background_rgb')):
            values = [r['hdr'][key][0] for r in chosen]
            if key == 'signal_rgb':
                values = [v / select('absorption',d)['hdr']['signal_rgb'][0]
                          for v,d in zip(values,(.25,.75,1.25))]
            ax.plot([r['request']['depth_m'] for r in chosen], values, 'o-', label=label, color=colour)
            ax.grid(alpha=.2); ax.legend(); ax.set_xlabel('Physical target depth (m)')
    axes[0].set_ylabel('Red HDR signal / same-depth absorption-only')
    axes[1].set_ylabel('Background red mean (native HDR AOV units)')
    axes[1].set_yscale('log')
    fig.suptitle('Scattering compared separately at fixed native distance 100 and tint (.6,.8,.9)')
    fig.savefig(output / 'scattering_signal_contrast.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()

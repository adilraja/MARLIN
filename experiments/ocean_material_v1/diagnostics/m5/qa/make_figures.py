"""Standalone scientific figures from retained M5 captures and GPU observations."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/attempt03'


def pixels(label):
    return np.asarray(Image.open(RUN / label / 'hdr_display.png').convert('RGB'))


def pair(reference, other, label, filename):
    a, b = pixels(reference), pixels(other)
    difference = np.abs(a.astype(float) - b.astype(float)).mean(axis=2)
    figure, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), constrained_layout=True)
    for axis, image, title in zip(axes[:2], (a, b), ('PathTracing baseline', label)):
        axis.imshow(image)
        axis.set_title(title)
        axis.set_axis_off()
    heat = axes[2].imshow(difference, cmap='magma', vmin=0, vmax=8)
    axes[2].set_title('Mean absolute RGB difference')
    axes[2].set_axis_off()
    figure.colorbar(heat, ax=axes[2], label='8-bit display values', shrink=.75)
    figure.suptitle('Fixed display: round(255 × clip(HDR / 12000, 0, 1)^(1/2.2)); 512 × 384 native captures', fontsize=11)
    figure.savefig(ROOT / 'figures' / filename, dpi=160)
    plt.close(figure)


def main():
    (ROOT / 'figures').mkdir(exist_ok=True)
    pair('baseline', 'reload_a', 'Fresh disk reload', 'repeat_reload.png')
    if (RUN / 'mode_comparison/hdr_display.png').exists():
        pair('baseline', 'mode_comparison', 'Registered Real-Time Path-Tracing mode', 'mode_comparison.png')
    samples = json.loads((ROOT / 'qa/driver_recovery_2026_11_03/post_reboot_retry03/gpu_samples.json').read_text())
    valid = [sample for sample in samples if 'used_mib' in sample]
    seconds = [sample['monotonic'] - valid[0]['monotonic'] for sample in valid]
    figure, axis = plt.subplots(figsize=(9, 3.6), constrained_layout=True)
    axis.plot(seconds, [sample['used_mib'] for sample in valid], label='GPU used')
    axis.plot(seconds, [sample['free_mib'] for sample in valid], label='GPU free')
    axis.axhline(768, color='0.35', linestyle='--', label='Pre-capture free-memory guard')
    axis.set(xlabel='Seconds since launch monitor started', ylabel='Memory (MiB)',
             title='RTX A2000 / driver 595.99.02 — startup through M5 completion')
    axis.legend(loc='best', fontsize=8)
    axis.grid(alpha=.2)
    figure.savefig(ROOT / 'figures/gpu_observations.png', dpi=160)
    plt.close(figure)


if __name__ == '__main__':
    main()

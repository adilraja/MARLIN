"""Exercise all frozen detector inputs and box/class conversion."""

import json
from pathlib import Path

from dataset import DetectionDataset, prepare, records

ROOT = Path(__file__).resolve().parents[1]


def main():
    checked = 0
    positives = 0
    negatives = 0
    for split, expected in (("train", 180), ("validation", 60), ("test", 60)):
        items = records(split)
        assert len(items) == expected
        for record in items:
            image, boxes = prepare(record)
            assert image.mode == "RGB" and image.size == (1024, 1024)
            assert image.getpixel((0, 0)) == image.getpixel((512, 127)) == (114, 114, 114)
            assert image.getpixel((512, 896)) == image.getpixel((1023, 1023)) == (114, 114, 114)
            assert len(boxes) == (record["intervention"] == "target_present")
            if boxes:
                x1, y1, x2, y2 = boxes[0]
                x, y, w, h = record["original_bbox_xywh_px"]
                assert abs(x1 - x) < 1e-9 and abs(y1 - (y + 128)) < 1e-9
                assert abs(x2 - (x + w)) < 1e-9 and abs(y2 - (y + h + 128)) < 1e-9
                positives += 1
            else:
                negatives += 1
            checked += 1
    assert (checked, positives, negatives) == (300, 250, 50)
    # The Torch wrapper is checked on both target conditions in every split.
    import torch
    tensor_checks = 0
    for split in ("train", "validation", "test"):
        dataset = DetectionDataset(split)
        for wanted in ("target_present", "target_absent"):
            index = next(i for i, v in enumerate(dataset.items) if v["intervention"] == wanted)
            image, target = dataset[index]
            assert image.shape == (3, 1024, 1024) and image.dtype == torch.float32
            assert image.min().item() >= 0 and image.max().item() <= 1
            assert target["boxes"].shape == (int(wanted == "target_present"), 4)
            assert target["labels"].tolist() == ([1] if wanted == "target_present" else [])
            tensor_checks += 1
    result = {"passed": True, "decoded_padded_images": checked,
              "positive_boxes": positives, "empty_negative_targets": negatives,
              "torch_tensor_checks": tensor_checks, "classes": {"0": "background", "1": "wildlife"},
              "image_tensor_shape_chw": [3, 1024, 1024], "image_tensor_range": [0.0, 1.0]}
    (ROOT / "qa/m6_loader_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

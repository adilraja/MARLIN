"""Frozen M6 full-frame input adapter for a TorchVision detection model."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PADDING = (0, 128, 0, 128)
FILL = (114, 114, 114)


def records(split):
    if split not in ("train", "validation", "test"):
        raise ValueError("Unknown split")
    data = json.loads((ROOT / "splits/image_assignments.json").read_text())
    return [v for v in data["images"] if v["split"] == split]


def prepare(record):
    """Return padded RGB image and one or zero xyxy boxes, without resize."""
    from PIL import Image, ImageOps

    with Image.open(ROOT / record["image_path"]) as source:
        if source.size != (1024, 768) or source.mode not in ("RGB", "RGBA"):
            raise ValueError("Unexpected image format or dimensions")
        if source.mode == "RGBA" and source.getchannel("A").getextrema() != (255, 255):
            raise ValueError("Non-opaque alpha would change model appearance")
        rgb = source.convert("RGB")
    image = ImageOps.expand(rgb, border=PADDING, fill=FILL)
    if image.size != (1024, 1024):
        raise ValueError("Incorrect detector dimensions")
    bbox = record["model_bbox_xywh_px"]
    boxes = [] if bbox is None else [[bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]]]
    return image, boxes


class DetectionDataset:
    """TorchVision dataset; class 0 is background, class 1 wildlife."""

    def __init__(self, split):
        self.split = split
        self.items = records(split)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        import numpy as np
        import torch

        record = self.items[index]
        image, boxes = prepare(record)
        pixels = np.asarray(image, dtype=np.uint8)
        tensor = torch.from_numpy(pixels.copy()).permute(2, 0, 1).float().div_(255)
        target = {
            "boxes": torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4),
            "labels": torch.tensor([1] * len(boxes), dtype=torch.int64),
            "image_id": torch.tensor(record["image_id"], dtype=torch.int64),
        }
        return tensor, target


def collate(batch):
    return tuple(zip(*batch))

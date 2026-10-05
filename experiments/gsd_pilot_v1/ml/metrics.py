"""Fixed one-to-one IoU 0.5 detection metrics for the M7 pilot."""


def iou_xyxy(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def ranked_events(frames, threshold=0.001):
    """Return score-ranked TP/FP outcomes; each image has at most one GT."""
    candidates = []
    for frame in frames:
        for prediction in frame["predictions"]:
            if prediction["score"] >= threshold:
                candidates.append((prediction["score"], frame["image_id"],
                                   prediction["box_xyxy_px"], frame["gt_box_xyxy_px"]))
    candidates.sort(key=lambda value: (-value[0], value[1], value[2]))
    matched = set()
    events = []
    for score, image_id, box, gt in candidates:
        positive = gt is not None and image_id not in matched and iou_xyxy(box, gt) >= 0.5
        if positive:
            matched.add(image_id)
        events.append({"score": score, "image_id": image_id, "tp": int(positive),
                       "fp": int(not positive)})
    return events


def ap50(frames):
    total_gt = sum(f["gt_box_xyxy_px"] is not None for f in frames)
    if not total_gt:
        return None
    tp = fp = 0
    points = []
    for event in ranked_events(frames):
        tp += event["tp"]
        fp += event["fp"]
        points.append((tp / total_gt, tp / (tp + fp)))
    return sum(max((precision for recall, precision in points if recall >= level / 100), default=0.0)
               for level in range(101)) / 101


def summarize(frames, threshold):
    events = ranked_events(frames, threshold)
    tp = sum(e["tp"] for e in events)
    fp = sum(e["fp"] for e in events)
    total_gt = sum(f["gt_box_xyxy_px"] is not None for f in frames)
    fn = total_gt - tp
    negatives = [f for f in frames if f["gt_box_xyxy_px"] is None]
    negative_ids = {f["image_id"] for f in negatives}
    negative_fp = sum(e["fp"] for e in events if e["image_id"] in negative_ids)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / total_gt if total_gt else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return {"images": len(frames), "positive_images": total_gt,
            "negative_images": len(negatives), "TP": tp, "FP": fp, "FN": fn,
            "precision": precision, "recall": recall, "F1": f1,
            "AP50": ap50(frames), "false_positives_per_negative_frame":
            negative_fp / len(negatives) if negatives else None,
            "negative_frame_false_positives": negative_fp}


def select_threshold(frames):
    """Maximize pooled validation F1; ties choose the higher confidence."""
    scores = {0.001, 1.0}
    for frame in frames:
        scores.update(p["score"] for p in frame["predictions"])
    scored = [(summarize(frames, threshold)["F1"], threshold) for threshold in sorted(scores)]
    return max(scored)[1]


def self_test():
    frames = [
        {"image_id": 1, "gt_box_xyxy_px": [0, 0, 10, 10],
         "predictions": [{"score": 0.9, "box_xyxy_px": [0, 0, 10, 10]},
                         {"score": 0.8, "box_xyxy_px": [0, 0, 10, 10]}]},
        {"image_id": 2, "gt_box_xyxy_px": None,
         "predictions": [{"score": 0.7, "box_xyxy_px": [0, 0, 10, 10]}]},
        {"image_id": 3, "gt_box_xyxy_px": [0, 0, 10, 10], "predictions": []},
    ]
    assert iou_xyxy([0, 0, 10, 10], [5, 5, 15, 15]) == 25 / 175
    assert summarize(frames, 0.7)["TP"] == 1
    assert summarize(frames, 0.7)["FP"] == 2
    assert summarize(frames, 0.7)["FN"] == 1
    assert summarize(frames, 0.7)["negative_frame_false_positives"] == 1
    assert select_threshold(frames) == 0.9
    assert abs(ap50(frames) - 0.504950495049505) < 1e-12


if __name__ == "__main__":
    self_test()
    print("M7 metric contract passed")

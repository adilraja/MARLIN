"""Index twelve already inspected M7 groups without claiming completion.

Reads retained files only. Existing sheets, images, labels and notes are never
changed. This does not render, capture, contact Kit or create a final M7 review.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import capture_gama_dataset_v2 as client
import capture_gama_dataset_pending_v2 as pending


class Pins:
    def __init__(self):
        self.before = {}

    def add(self, path, digest=None):
        path = client.live.safe_path(path)
        pin = client.pin(path)
        if (digest is not None and pin["sha256"] != digest
                or str(path) in self.before and self.before[str(path)] != pin):
            raise ValueError("A retained review input changed: " + str(path))
        self.before[str(path)] = pin
        return path

    def read(self, path, digest=None):
        return json.loads(self.add(path, digest).read_text())

    def finish(self):
        rows = [{"path": path, "before": pin, "after": client.pin(Path(path))}
                for path, pin in sorted(self.before.items())]
        for row in rows:
            row["unchanged"] = row["before"] == row["after"]
        if not all(row["unchanged"] for row in rows):
            raise ValueError("A source changed during partial review generation")
        return rows


def write(path, document):
    with path.open("x") as stream:
        stream.write(json.dumps(document, indent=2, allow_nan=False) + "\n")


def build(output):
    output = client.live.safe_path(output)
    source = QA / "m7_live_02"
    previews = QA / "m7_live_02_visual_preview"
    if (output.exists() or any(output.is_relative_to(path) or path.is_relative_to(output)
                              for path in (source, previews))):
        raise ValueError("Use a fresh partial output separate from original evidence")
    pins = Pins()
    for path in (Path(__file__), QA / "build_m7_review.py", QA / "finalize_m7_review.py",
                 ROOT / "tools/capture_gama_dataset_v2.py", ROOT / "tools/capture_gama_dataset_pending_v2.py"):
        pins.add(path)
    report = pins.read(source / "results.json")
    declaration = pins.read(source / "declaration.json", report["declaration"]["sha256"])
    if client.validate_declaration(source / "declaration.json") != declaration:
        raise ValueError("Original immutable declaration changed")
    selection = pending.select_pending(declaration, report)
    accepted, observations, groups = set(selection["accepted_keys"]), [], []
    actual = {row["image_id"]: row for row in report["traceable_images"]}
    for run in declaration["runs"]:
        for state in run["selected_states"]:
            key = (run["run_id"], state["step_index"])
            if key not in accepted:
                continue
            stem = f"{run['run_id']}__step_{state['step_index']:03d}"
            folder = previews / stem
            index_path, group_path, perview_path = (folder / name for name in
                                                   ("visual_index.json", "visual_inspection.json", "per_view_visibility_observations.json"))
            index, note, perview = (pins.read(path) for path in (index_path, group_path, perview_path))
            ids = [row["image_id"] for row in index["images"]]
            if (len(ids) != 10 or len(set(ids)) != 10 or ids != note["image_ids_reviewed"]
                    or ids != [row["image_id"] for row in perview["observations"]]
                    or note["visual_index_sha256"] != client.live.digest(index_path)
                    or perview["visual_index_sha256"] != client.live.digest(index_path)
                    or any(note[field] != expected for field, expected in
                           (("run_id", run["run_id"]), ("seed", run["seed"]), ("step_index", state["step_index"])))
                    or len(index["contact_sheets"]) != 1):
                raise ValueError("Manual notes do not cover their exact original group/index")
            sheet = index["contact_sheets"][0]
            pins.add(sheet["file"], sheet["sha256"])
            if note["contact_sheet_sha256"] != sheet["sha256"] or perview["contact_sheet_sha256"] != sheet["sha256"]:
                raise ValueError("Manual note sheet binding changed")
            for row in index["source_hashes_before_after"]:
                if row["unchanged"] is not True or row["before_sha256"] != row["after_sha256"]:
                    raise ValueError("Original preview did not preserve its inputs")
                pins.add(row["path"], row["before_sha256"])
            for measured, observation in zip(index["images"], perview["observations"]):
                recorded = actual[observation["image_id"]]
                if (observation["physically_present"] is not recorded["target_present"]
                        or observation["rendered_visibility"] != "unknown"
                        or observation["manual_observation_is_machine_visibility_label"] is not False
                        or observation["biological_approval"] is not False
                        or not isinstance(observation["manual_contact_sheet_observation"], str)
                        or not observation["manual_contact_sheet_observation"].strip()
                        or any(observation[field] != recorded[field] or observation[field] != measured[field]
                               for field in ("run_id", "seed", "step_index", "variant", "gsd_cm_px"))):
                    raise ValueError("Partial observation changes source/presence/label semantics")
                for field, digest in (("rgb_file", "rgb_sha256"), ("annotation_file", "annotation_sha256"),
                                      ("yolo_file", "yolo_sha256")):
                    path = pins.add(observation[field], observation[digest])
                    if (path != client.live.safe_path(source / recorded[field])
                            or observation[digest] != recorded[digest] or observation[digest] != measured[digest]):
                        raise ValueError("Observation refers to another original image/label")
                if (client.live.safe_path(observation["contact_sheet"]) != client.live.safe_path(sheet["file"])
                        or observation["contact_sheet_sha256"] != sheet["sha256"]):
                    raise ValueError("Per-view observation cites another sheet")
                observations.append(dict(observation))
            groups.append({"run_id": run["run_id"], "seed": run["seed"], "step_index": state["step_index"],
                           "split": run["split"], "behavioural_state": state["agents"][0]["behavioural_state"],
                           "original_gama_depth_m": state["agents"][0]["depth_m"],
                           "contact_sheet": sheet["file"], "contact_sheet_sha256": sheet["sha256"],
                           "source_group_note": str(group_path), "source_group_note_sha256": client.live.digest(group_path),
                           "source_per_view_note": str(perview_path), "source_per_view_note_sha256": client.live.digest(perview_path),
                           "source_index": str(index_path), "source_index_sha256": client.live.digest(index_path),
                           "reviewer": note["reviewer"], "image_ids_reviewed": ids,
                           "engineering_observations": note["engineering_observations"]})
    if (len(groups) != 12 or len(observations) != 120 or len({row["image_id"] for row in observations}) != 120
            or {row["image_id"] for row in observations} != set(actual)):
        raise ValueError("Require exactly the original120 unique inspected views")
    missing = [{"run_id": run, "seed": 2147483647, "step_index": step, "split": "test",
                "expected_views": 10, "variants": ["present", "absent"], "gsd_conditions_cm_px": list(client.GSDS)}
               for run, step in selection["pending_keys"]]
    document = {"kind": "m7_partial_manual_per_view_presentation_observations", "milestone": 7,
                "status": "incomplete", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "expected_images": 150, "reviewed_images": 120, "reviewed_groups": 12,
                "missing_images": 30, "missing_groups": missing,
                "source_campaign": str(source), "source_campaign_passed": False,
                "source_campaign_result": client.pin(source / "results.json"),
                "observations": observations, "source_group_reviews": groups,
                "original_observation_fields_and_paths_preserved": True,
                "source_rgb_annotation_yolo_sheet_hashes_verified": True,
                "engineering_review_metadata_binding_passed": True, "final_milestone_acceptance_claimed": False,
                "final_m7_review": False, "rendered_visibility": "unknown", "biological_approval": False,
                "manual_observations_are_machine_visibility_labels": False,
                "automatic_animal_visibility_threshold_used": False, "visibility_based_frame_selection_used": False,
                "engineering_limitations": ["Some paired background animals differ in RGB shading/detail; cause is unestablished and photometric equivalence is not claimed.",
                                           "Seed42 step016 positives remain physically present, while the owned target is not distinguishable at contact-sheet scale due background overlap.",
                                           "Direct amodal mesh rectangles are not exact visible/refracted outlines. Static pose proxies and water optics remain biologically uncertified."],
                "live_calls_made": False, "new_images_rendered": 0}
    markdown = ["# M7 partial engineering review — incomplete", "",
                "**120 of 150 expected views were reviewed across 12 of 15 groups. Three test groups (30 views) are missing.**", "",
                "This index links the original inspected sheets and preserves their source-bound observations. The source capture attempt remained failed; this is not a final M7 review or milestone acceptance.", "",
                "Missing: seed 2147483647, steps 008, 016 and 032, test split; ten present/removed views per group at 0.5, 1, 2, 3 and 4 cm/px.", "",
                "Machine visibility remains **unknown** and biological approval remains **false**. Manual notes describe presentation at contact-sheet scale only. Gold boxes are direct amodal rectangles; unrelated demonstration animals remain unlabelled background.", "",
                "Observed limits include paired background shading differences with unestablished cause, seed-42 descent overlap, and limited detail at coarser GSDs. No frames were dropped or substituted based on visibility.", ""]
    for group in groups:
        markdown.extend((f"## {group['run_id']} — step {group['step_index']:03d}", "",
                         f"Seed {group['seed']}; **{group['split']}**; {group['behavioural_state']}; root depth {group['original_gama_depth_m']:g} m. All ten original views were inspected.", "",
                         f"[Original inspected contact sheet](<{group['contact_sheet']}>) · [Original source-bound notes](<{group['source_group_note']}>)", ""))
    input_rows = pins.finish()
    output.mkdir(parents=True, exist_ok=False)
    write(output / "visual_inspection.json", document)
    with (output / "index.md").open("x") as stream:
        stream.write("\n".join(markdown))
    write(output / "input_hashes_before_after.json", {"kind": "m7_partial_review_input_preservation", "passed": True,
          "scope": "Every explicitly pinned original review input and code source; no new captures or USD modifications",
          "inputs": input_rows})
    pins.finish()
    return {"artifact_generation_passed": True, "status": "incomplete", "expected_images": 150,
            "reviewed_images": 120, "missing_images": 30, "reviewed_groups": 12, "missing_groups": 3,
            "original_inputs_unchanged": True, "input_files_pinned": len(input_rows),
            "final_milestone_acceptance_claimed": False, "index": str(output / "index.md")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))


if __name__ == "__main__":
    main()

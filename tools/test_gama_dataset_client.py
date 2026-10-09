"""Pure M7 client tests; no HTTP, Kit, USD runtime or experiment execution.

Plans and source snapshots are read from actual sealed GAMA records. Annotation
rectangles, mesh names and projected-vertex hashes below are explicit unit-test
fixtures, not captured imagery or independently verified physical geometry.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import capture_gama_dataset_v2 as client

CAMERA = "/MarlinGamaPairCamera"
OWNED_MESH = "/MarlinGamaPorpoise/Porpoise_001/Model/UnitFixtureMesh"
INSIDE_LABEL = "0 0.195312500000 0.325520833333 0.195312500000 0.260416666667\n"
CLIPPED_LABEL = "0 0.500000000000 0.630208333333 1.000000000000 0.739583333333\n"


class DatasetClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # build_plan reparses retained raw XML and verifies actual run/source
        # hashes. No fake trajectory or replacement state enters this suite.
        cls.plan = client.build_plan()
        cls.state = deepcopy(cls.plan["runs"][0]["selected_states"][0])
        cls.approved_metadata = json.loads(client.DECLARATION.read_text())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.group = Path(self.temporary.name).resolve()
        self.fixture_index = 0

    def declaration(self):
        document = deepcopy(self.plan)
        for key in ("declared_at_utc", "sealed_m5_manifest", "sealed_m6_manifest",
                    "strict_baseline_verification_before_m7_refactor", "historical_m6_source_pins"):
            document[key] = deepcopy(self.approved_metadata[key])
        return document

    def validate_declaration(self, document):
        path = self.group / f"declaration_{self.fixture_index}.json"
        self.fixture_index += 1
        path.write_text(json.dumps(document))
        return client.validate_declaration(path)

    def annotation(self, kind="inside", visibility="inherited"):
        state = self.state
        agent = state["agents"][0]
        present = kind != "absent"
        metadata = {
            "schema_version": "gama_marlin_amodal_annotation_v1", "target_present": present,
            "species": agent["species"], "class_id": 0, "run_id": state["run_id"],
            "step_index": state["step_index"], "simulation_time_s": state["simulation_time_s"],
            "original_gama_depth_m": agent["depth_m"], "vertical_reference": agent["vertical_reference"],
            "behavioural_state": agent["behavioural_state"], "resolution_px": [1024, 768],
            "camera_path": CAMERA, "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
            "class_scope": "Owned harbour porpoise only; unrelated demonstration animals remain unlabelled background",
            "biological_approval": False, "pose_mapping": "static_pose_proxy_v1",
            "pose_scope": "Direct geometry only; body animation, breathing and biological dive pose were not certified",
            "rendered_visibility": "unknown", "visible_mask": None, "refraction_calibrated": False,
            "projected_silhouette_area_px": None, "visible_target_area_px": None,
            "area_semantics": "Rectangle box area only; neither visible pixels nor silhouette area",
            "mesh_paths": [], "vertex_count": 0, "raw_amodal_bbox_xyxy_px": None,
            "amodal_bbox_xyxy_px": None, "amodal_bbox_coco_xywh_px": None,
            "intersects_image": False, "bbox_clipped_to_image": False,
            "annotation_status": "target_physically_removed",
        }
        if not present:
            return metadata, ""
        x, z = agent["horizontal_position_m"]
        y = -agent["depth_m"]
        metadata.update(mesh_paths=[OWNED_MESH], vertex_count=8,
                        projected_vertices_sha256=hashlib.sha256(b"unit-test projected-vertex fixture").hexdigest(),
                        world_bounds_min_m=[x - .7, y - .2, z - .3],
                        world_bounds_max_m=[x + .7, y + .2, z + .3],
                        target_usd_visibility=visibility)
        if kind == "outside":
            metadata.update(raw_amodal_bbox_xyxy_px=[1200., 100., 1300., 200.],
                            annotation_status="physically_present_outside_image")
            return metadata, ""
        if kind == "clipped":
            metadata.update(raw_amodal_bbox_xyxy_px=[-100., 200., 1100., 900.],
                            amodal_bbox_xyxy_px=[0, 200., 1024, 768],
                            amodal_bbox_coco_xywh_px=[0, 200., 1024, 568.],
                            bbox_rectangle_area_px=581632., bbox_clipped_to_image=True)
            label = CLIPPED_LABEL
        else:
            metadata.update(raw_amodal_bbox_xyxy_px=[100., 150., 300., 350.],
                            amodal_bbox_xyxy_px=[100., 150., 300., 350.],
                            amodal_bbox_coco_xywh_px=[100., 150., 200., 200.],
                            bbox_rectangle_area_px=40000.)
            label = INSIDE_LABEL
        metadata.update(intersects_image=True, annotation_status="physically_present_direct_amodal_box")
        return metadata, label

    def item(self, annotation, label):
        folder = self.group / f"unit_fixture_{self.fixture_index}"
        self.fixture_index += 1
        folder.mkdir()
        path, yolo = folder / "annotation.json", folder / "labels.txt"
        path.write_text(json.dumps(annotation))
        yolo.write_text(label)
        return {"target_present": annotation["target_present"],
                "camera_condition": {"camera_condition": {"camera_path": CAMERA}},
                "annotation": deepcopy(annotation), "annotation_file": str(path.relative_to(self.group)),
                "annotation_sha256": client.live.digest(path),
                "yolo_file": str(yolo.relative_to(self.group)), "yolo_sha256": client.live.digest(yolo)}

    def check(self, annotation, label, state=None):
        return client.validate_annotation(self.group, self.item(annotation, label),
                                          self.state if state is None else state)

    def test_plan_reads_five_actual_sources_and_declares_fixed_150_image_workload(self):
        plan = self.plan
        self.assertEqual(plan["seeds"], [1, 42, 184729, 20261008, 2147483647])
        self.assertEqual(plan["snapshot_steps"], [8, 16, 32])
        self.assertEqual(plan["simulation_times_s"], [4., 8., 16.])
        self.assertEqual(plan["gsd_conditions_cm_px"], [.5, 1., 2., 3., 4.])
        self.assertEqual(plan["planned_capture_groups"], 15)
        self.assertEqual(plan["planned_target_present_captures"], 75)
        self.assertEqual(plan["planned_target_absent_captures"], 75)
        self.assertEqual(len({run["run_id"] for run in plan["runs"]}), 5)
        self.assertEqual(len({run["canonical_state_sha256"] for run in plan["runs"]}), 5)
        self.assertTrue(plan["selection_declared_before_m7_image_inspection"])
        self.assertTrue(plan["no_silent_state_replacement"])
        self.assertFalse(plan["scope"]["biological_approval"])
        for run in plan["runs"]:
            self.assertTrue(run["raw_gama_reparse_passed"])
            source = next(row for row in run["source_files"] if row["path"].endswith("/trajectory.json"))
            trajectory = json.loads((client.ROOT / source["path"]).read_text())
            self.assertEqual(run["selected_states"], [trajectory[index] for index in (8, 16, 32)])
            for row in run["source_files"]:
                self.assertEqual(client.pin(client.ROOT / row["path"]), row)

    def test_whole_trajectory_and_related_repeats_have_one_split_and_encounter_group(self):
        assignments = {}
        for run in self.plan["runs"]:
            self.assertIn(run["run_id"], self.plan["splits"][run["split"]])
            self.assertEqual(len(run["selected_states"]), 3)
            related = [run] + run["related_runs_not_rendered"]
            self.assertEqual({row["run_id"] for row in related}, set(run["related_run_ids"]))
            self.assertEqual(len(related), 2 if run["seed"] in (1, 184729, 2147483647) else 1)
            for row in related:
                self.assertEqual(row["split"], run["split"])
                self.assertEqual(row["encounter_group_id"], run["encounter_group_id"])
                self.assertEqual(row["canonical_state_sha256"], run["canonical_state_sha256"])
                self.assertNotIn(row["run_id"], assignments)
                assignments[row["run_id"]] = row["split"]
        self.assertEqual(set(assignments.values()), {"train", "validation", "test"})

    def test_current_timestamped_declaration_matches_real_sources(self):
        document = self.declaration()
        self.assertEqual(self.validate_declaration(document), document)

    def test_declaration_rejects_cross_split_or_cross_encounter_membership(self):
        for case in ("primary_split", "repeat_split", "repeat_group", "repeat_leakage"):
            with self.subTest(case=case):
                document = self.declaration()
                run = document["runs"][0]
                repeat = run["related_runs_not_rendered"][0]
                if case == "primary_split":
                    run["split"] = "test"
                elif case == "repeat_split":
                    repeat["split"] = "test"
                elif case == "repeat_group":
                    repeat["encounter_group_id"] = "unrelated_encounter"
                else:
                    document["splits"]["test"].append(repeat["run_id"])
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_declaration_rejects_changed_selection_or_actual_state_replacement(self):
        for case in ("steps", "snapshot", "no_replacement"):
            with self.subTest(case=case):
                document = self.declaration()
                if case == "steps":
                    document["snapshot_steps"] = [8, 16, 31]
                elif case == "snapshot":
                    document["runs"][0]["selected_states"][0] = deepcopy(document["runs"][0]["selected_states"][1])
                else:
                    document["no_silent_state_replacement"] = False
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_declaration_rejects_tampered_source_identity(self):
        for case in ("bytes", "hash", "seed", "canonical", "reparse"):
            with self.subTest(case=case):
                document = self.declaration()
                run = document["runs"][0]
                if case == "bytes":
                    run["source_files"][0]["bytes"] += 1
                elif case == "hash":
                    run["source_files"][0]["sha256"] = "0" * 64
                elif case == "seed":
                    run["seed"] = 42
                elif case == "canonical":
                    run["canonical_state_sha256"] = "0" * 64
                else:
                    run["raw_gama_reparse_passed"] = False
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_declaration_rejects_changed_historical_seal_pins(self):
        for key in ("sealed_m5_manifest", "sealed_m6_manifest"):
            with self.subTest(key=key):
                document = self.declaration()
                document[key]["sha256"] = "0" * 64
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_declaration_requires_prior_timestamp(self):
        document = self.declaration()
        del document["declared_at_utc"]
        with self.assertRaises(ValueError):
            self.validate_declaration(document)

    def test_declaration_timestamp_must_be_prior_and_timezone_aware(self):
        for timestamp in ("not-a-date", "2026-10-09T00:00:00", "2099-01-01T00:00:00+00:00"):
            with self.subTest(timestamp=timestamp):
                document = self.declaration()
                document["declared_at_utc"] = timestamp
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_declaration_rejects_changed_pre_refactor_evidence_or_unknown_keys(self):
        for case in ("baseline", "historical_source", "unknown_claim"):
            with self.subTest(case=case):
                document = self.declaration()
                if case == "baseline":
                    document["strict_baseline_verification_before_m7_refactor"]["milestone_6"]["changes"] = ["changed"]
                elif case == "historical_source":
                    document["historical_m6_source_pins"][0]["sha256"] = "0" * 64
                else:
                    document["biological_approval"] = True
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_declaration_cannot_award_biological_or_exact_outline_approval(self):
        for key in ("biological_approval", "exact_visible_or_refracted_outline_claimed"):
            with self.subTest(key=key):
                document = self.declaration()
                document["scope"][key] = True
                with self.assertRaises(ValueError):
                    self.validate_declaration(document)

    def test_clipped_positive_has_correct_json_coco_yolo_arithmetic(self):
        annotation, label = self.annotation("clipped")
        result = self.check(annotation, label)
        self.assertTrue(result["passed"])
        self.assertEqual(result["bbox_xyxy_px"], [0, 200., 1024, 768])
        self.assertTrue(result["target_present"] and result["intersects_image"])
        self.assertFalse(result["independent_usd_vertex_projection_verified"])

    def test_present_in_frame_keeps_rendered_visibility_unknown(self):
        annotation, label = self.annotation()
        result = self.check(annotation, label)
        self.assertTrue(result["passed"])
        self.assertEqual(result["rendered_visibility"], "unknown")
        self.assertEqual(result["annotation_status"], "physically_present_direct_amodal_box")

    def test_present_outside_frame_has_empty_label_and_stays_present(self):
        annotation, label = self.annotation("outside")
        result = self.check(annotation, label)
        self.assertTrue(result["passed"] and result["target_present"])
        self.assertFalse(result["intersects_image"])
        self.assertEqual(result["annotation_status"], "physically_present_outside_image")

    def test_usd_invisible_target_stays_positive_with_direct_amodal_label(self):
        annotation, label = self.annotation(visibility="invisible")
        result = self.check(annotation, label)
        self.assertTrue(result["passed"] and result["target_present"])
        self.assertNotEqual(label, "")
        self.assertEqual(result["rendered_visibility"], "unknown")

    def test_removed_target_has_no_geometry_and_an_empty_label(self):
        annotation, label = self.annotation("absent")
        result = self.check(annotation, label)
        self.assertTrue(result["passed"])
        self.assertFalse(result["target_present"])
        self.assertEqual(result["annotation_status"], "target_physically_removed")

    def test_negative_rejects_any_target_geometry_or_positive_label(self):
        changes = {"mesh_paths": [OWNED_MESH], "vertex_count": 8,
                   "raw_amodal_bbox_xyxy_px": [1., 2., 3., 4.],
                   "amodal_bbox_xyxy_px": [1., 2., 3., 4.],
                   "amodal_bbox_coco_xywh_px": [1., 2., 2., 2.],
                   "world_bounds_min_m": [0., 0., 0.], "world_bounds_max_m": None,
                   "projected_vertices_sha256": "1" * 64, "bbox_rectangle_area_px": 0,
                   "target_usd_visibility": "invisible"}
        for key, value in changes.items():
            with self.subTest(key=key):
                annotation, label = self.annotation("absent")
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)
        annotation, _ = self.annotation("absent")
        with self.assertRaises(ValueError):
            self.check(annotation, INSIDE_LABEL)

    def test_annotation_rejects_unsupported_approval_and_certification_claims(self):
        changes = {"biological_approval": True, "refraction_calibrated": True,
                   "exact_visible_or_refracted_outline_claimed": True,
                   "pixel_identical_pairing_claimed": True, "body_animation_certified": True,
                   "rendered_visibility": "visible", "visible_mask": [1, 2, 3],
                   "visible_target_area_px": 200., "projected_silhouette_area_px": 200.,
                   "pose_scope": "Biological dive pose certified", "area_semantics": "Exact visible area"}
        for key, value in changes.items():
            with self.subTest(key=key):
                annotation, label = self.annotation()
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)

    def test_annotation_rejects_source_species_class_or_scope_mismatch(self):
        changes = {"run_id": "unrelated_run", "step_index": 16, "simulation_time_s": 8.,
                   "original_gama_depth_m": 99., "species": "bottlenose_dolphin", "class_id": 1,
                   "pose_mapping": "animated_biological_pose", "class_scope": "All demonstration animals",
                   "camera_path": "/WrongCamera", "annotation_semantics": "visible_mesh_outline"}
        for key, value in changes.items():
            with self.subTest(key=key):
                annotation, label = self.annotation()
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)

    def test_annotation_rejects_another_actual_selected_source_state(self):
        annotation, label = self.annotation()
        different_actual_state = self.plan["runs"][0]["selected_states"][1]
        with self.assertRaises(ValueError):
            self.check(annotation, label, state=different_actual_state)

    def test_positive_mesh_provenance_and_strict_types_are_required(self):
        changes = {"mesh_paths": [], "vertex_count": 0, "projected_vertices_sha256": "wrong",
                   "class_id": False, "step_index": 8., "resolution_px": [1024., 768],
                   "target_present": 1, "target_usd_visibility": "visible"}
        for key, value in changes.items():
            with self.subTest(key=key):
                annotation, label = self.annotation()
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)
        for meshes in ([OWNED_MESH, OWNED_MESH], ["/World/Cetaceans/Other"]):
            with self.subTest(meshes=meshes):
                annotation, label = self.annotation()
                annotation["mesh_paths"] = meshes
                with self.assertRaises(ValueError):
                    self.check(annotation, label)

    def test_changed_clipping_flags_coco_area_or_yolo_coordinates_are_rejected(self):
        changes = {"bbox_clipped_to_image": False, "intersects_image": False,
                   "amodal_bbox_xyxy_px": [0, 200, 1000, 768],
                   "amodal_bbox_coco_xywh_px": [0, 200, 1024, 500], "bbox_rectangle_area_px": 568.,
                   "annotation_status": "physically_present_outside_image"}
        for key, value in changes.items():
            with self.subTest(key=key):
                annotation, label = self.annotation("clipped")
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)
        annotation, _ = self.annotation("clipped")
        with self.assertRaises(ValueError):
            self.check(annotation, "0 0.5 0.6 1 0.7\n")

    def test_outside_target_cannot_gain_geometry_or_nonempty_label(self):
        for key, value in (("amodal_bbox_xyxy_px", [0, 0, 1, 1]),
                           ("bbox_rectangle_area_px", 0), ("target_present", False)):
            with self.subTest(key=key):
                annotation, label = self.annotation("outside")
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)
        annotation, _ = self.annotation("outside")
        with self.assertRaises(ValueError):
            self.check(annotation, INSIDE_LABEL)

    def test_raw_boxes_and_world_bounds_require_finite_ordered_coordinates(self):
        for key, value in (("raw_amodal_bbox_xyxy_px", [300., 150., 100., 350.]),
                           ("raw_amodal_bbox_xyxy_px", [float("nan"), 150., 300., 350.]),
                           ("raw_amodal_bbox_xyxy_px", [True, 150., 300., 350.]),
                           ("world_bounds_min_m", [float("inf"), 0., 0.]),
                           ("world_bounds_min_m", [1e10, 1e10, 1e10])):
            with self.subTest(key=key, value=value):
                annotation, label = self.annotation()
                annotation[key] = value
                with self.assertRaises(ValueError):
                    self.check(annotation, label)

    def test_annotation_and_label_byte_hash_tampering_is_rejected(self):
        for field in ("annotation_file", "yolo_file"):
            with self.subTest(field=field):
                annotation, label = self.annotation()
                item = self.item(annotation, label)
                path = self.group / item[field]
                path.write_bytes(path.read_bytes() + b" ")
                with self.assertRaises(ValueError):
                    client.validate_annotation(self.group, item, self.state)

    def test_inline_annotation_cannot_disagree_with_retained_json(self):
        annotation, label = self.annotation()
        item = self.item(annotation, label)
        item["annotation"]["original_gama_depth_m"] += 1
        with self.assertRaises(ValueError):
            client.validate_annotation(self.group, item, self.state)

    def test_annotation_paths_cannot_escape_the_retained_group(self):
        annotation, label = self.annotation()
        item = self.item(annotation, label)
        for field in ("annotation_file", "yolo_file"):
            with self.subTest(field=field):
                escaped = deepcopy(item)
                escaped[field] = "../outside.json"
                with self.assertRaises(ValueError):
                    client.validate_annotation(self.group, escaped, self.state)


class DatasetHeadroomRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Both snapshot and composed pose came from the retained first M7
        # group. These offline fixtures do not create experiment states.
        retained = client.SPRINT / "qa/m7_live_01/captures/m5_positive_seed_1_a/step_008/group_result.json"
        cls.retained_status = json.loads(retained.read_text())["actor_before"]
        cls.state = deepcopy(cls.retained_status["latest"])
        cls.code_pins = [{"path": "unit-fixture-pinned-runtime.py", "bytes": 1,
                          "sha256": "1" * 64}]

    def setUp(self):
        self.status = deepcopy(self.retained_status)
        self.expected_status = deepcopy(self.status)
        self.attempts, self.waits, self.requests, self.events = [], [], [], []
        self.responses = []
        self.after_capture = None
        self.after_wait = None
        self.current_code = deepcopy(self.code_pins)
        self.status_failure = None

    @staticmethod
    def headroom(free=694):
        return {"ok": False,
                "error": f"Insufficient GPU headroom before capture: {free} MiB free; require at least 768 MiB. No render attempted."}

    def status_read(self):
        self.events.append("status")
        if self.status_failure is not None:
            raise self.status_failure
        return deepcopy(self.status)

    def capture_once(self):
        self.events.append("capture")
        self.requests.append({"run_id": self.state["run_id"], "step_index": self.state["step_index"]})
        if not self.responses:
            raise AssertionError("An unexpected additional capture request was made")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if self.after_capture:
            self.after_capture()
        return response

    def wait(self, delay):
        self.events.append("wait")
        self.waits.append(delay)
        if self.after_wait:
            self.after_wait()

    def code_read(self):
        self.events.append("code")
        return deepcopy(self.current_code)

    def invoke(self):
        return client.capture_with_headroom_retry(
            self.capture_once, self.status_read, self.state, self.expected_status, .01,
            self.attempts, self.code_pins, wait=self.wait,
            utc_now=lambda: "2026-10-09T13:00:00+00:00", code_read=self.code_read)

    def change_held_field(self, case):
        if case == "snapshot":
            self.status["latest"]["agents"][0]["depth_m"] += .1
        elif case == "count":
            self.status["accepted_steps"] += 1
        elif case == "pose":
            self.status["world_pose"]["position_scene_units"][0] += 1
        elif case == "ownership":
            self.status["owned"] = False
        elif case == "guard":
            self.status["guard_error"] = "Unit fixture: owned layer disappeared"
            self.status["transport_state"] = "frozen_guard_failure"
        elif case == "autonomous":
            self.status["autonomous_controller"] = True
        elif case == "actor_count":
            self.status["actor_count"] = 0
        else:
            raise AssertionError(case)

    def test_retry_classifier_requires_exact_error_only_shape_and_below_threshold(self):
        for free in (0, 694, 767):
            with self.subTest(free=free):
                self.assertTrue(client.is_no_render_headroom(self.headroom(free)))
        for free in (-1, 768, 1024):
            with self.subTest(free=free):
                self.assertFalse(client.is_no_render_headroom(self.headroom(free)))
        rejected = [None, [], {"ok": 0, "error": self.headroom()["error"]},
                    {"ok": False, "error": None}, {"error": self.headroom()["error"]}]
        for field, value in (("directory", "/tmp/unit-fixture-rendered"), ("manifest", {}),
                             ("recovery_required", False), ("render_attempted", False)):
            rejected.append(dict(self.headroom(), **{field: value}))
        for altered in (self.headroom()["error"] + "\n", self.headroom()["error"] + " extra",
                        self.headroom()["error"].replace("No render attempted.", "Rendering started."),
                        self.headroom()["error"].replace("768", "512"),
                        self.headroom()["error"].replace("694", "694.0")):
            rejected.append({"ok": False, "error": altered})
        for response in rejected:
            with self.subTest(response=response):
                self.assertFalse(client.is_no_render_headroom(response))

    def test_first_success_returns_without_wait_and_retains_http_time_code_and_status(self):
        success = {"ok": True, "directory": "/tmp/unit-fixture-rendered-group"}
        self.responses = [(success, 200)]
        self.assertIs(self.invoke(), success)
        self.assertEqual(self.waits, [])
        self.assertEqual(len(self.requests), 1)
        attempt = self.attempts[0]
        self.assertEqual(attempt["http_status_code"], 200)
        self.assertEqual(attempt["started_at_utc"], "2026-10-09T13:00:00+00:00")
        self.assertEqual(attempt["response_received_at_utc"], attempt["started_at_utc"])
        self.assertEqual(attempt["response"], success)
        self.assertEqual(attempt["runtime_code_pins_sha256"], client.live.canonical_hash(self.code_pins))
        self.assertTrue(attempt["held_state_before"] and attempt["held_state_after_response"])
        self.assertEqual(self.events, ["code", "status", "capture", "status"])

    def test_three_no_render_rejections_then_fourth_success_keep_same_snapshot(self):
        success = {"ok": True, "directory": "/tmp/unit-fixture-rendered-group"}
        self.responses = [(self.headroom(free), 400) for free in (694, 720, 767)] + [(success, 200)]
        self.assertIs(self.invoke(), success)
        self.assertEqual(self.waits, [20, 20, 20])
        self.assertEqual([item["attempt_index"] for item in self.attempts], [1, 2, 3, 4])
        self.assertEqual(self.requests, [{"run_id": self.state["run_id"], "step_index": 8}] * 4)
        for attempt, free in zip(self.attempts[:3], (694, 720, 767)):
            self.assertEqual(attempt["observed_free_gpu_mib"], free)
            self.assertEqual(attempt["required_free_gpu_mib"], 768)
            self.assertIs(attempt["render_attempted"], False)
            self.assertTrue(attempt["held_state_after_rejection"] and attempt["held_state_after_wait"])
            self.assertTrue(attempt["runtime_code_unchanged_after_wait"])
            self.assertEqual(attempt["status_after_wait"]["latest"], self.state)
        self.assertEqual(self.status, self.expected_status)

    def test_four_rejections_exhaust_without_a_fifth_request_or_fourth_wait(self):
        self.responses = [(self.headroom(), 400)] * 4
        final = self.responses[-1][0]
        self.assertIs(self.invoke(), final)
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(self.waits, [20, 20, 20])
        self.assertTrue(self.attempts[-1]["retry_exhausted"])
        self.assertNotIn("wait_before_next_attempt_s", self.attempts[-1])
        self.assertTrue(all(item["held_state_after_rejection"] for item in self.attempts))

    def test_other_failures_or_returned_render_evidence_are_never_retried(self):
        responses = [{"ok": False, "error": "Capture failed after rendering"},
                     dict(self.headroom(), directory="/tmp/unit-fixture-failed-render"),
                     dict(self.headroom(), recovery_required=True)]
        for response in responses:
            with self.subTest(response=response):
                self.setUp()
                self.responses = [(response, 500)]
                self.assertIs(self.invoke(), response)
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(self.waits, [])
                self.assertFalse(self.attempts[0]["retryable_no_render_headroom"])
                self.assertEqual(self.attempts[0]["http_status_code"], 500)

    def test_changed_held_fields_before_request_abort_atomically(self):
        for case in ("snapshot", "count", "pose", "ownership", "guard", "autonomous", "actor_count"):
            with self.subTest(case=case):
                self.setUp()
                self.change_held_field(case)
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertEqual(self.requests, [])
                self.assertEqual(self.waits, [])
                self.assertFalse(self.attempts[0]["held_state_before"])

    def test_changed_held_fields_after_no_render_rejection_abort_before_wait(self):
        for case in ("snapshot", "count", "pose", "ownership", "guard", "autonomous", "actor_count"):
            with self.subTest(case=case):
                self.setUp()
                self.responses = [(self.headroom(), 400)]
                self.after_capture = lambda case=case: self.change_held_field(case)
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(self.waits, [])
                self.assertFalse(self.attempts[0]["held_state_after_rejection"])
                self.assertEqual(self.attempts[0]["response"], self.headroom())

    def test_changed_held_fields_during_wait_abort_before_next_request(self):
        for case in ("snapshot", "count", "pose", "ownership", "guard", "autonomous", "actor_count"):
            with self.subTest(case=case):
                self.setUp()
                self.responses = [(self.headroom(), 400)]
                self.after_wait = lambda case=case: self.change_held_field(case)
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(self.waits, [20])
                self.assertEqual(len(self.attempts), 1)
                self.assertFalse(self.attempts[0]["held_state_after_wait"])

    def test_pinned_runtime_change_before_first_request_aborts(self):
        self.current_code[0]["sha256"] = "2" * 64
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.requests, [])
        self.assertEqual(self.waits, [])
        self.assertFalse(self.attempts[0]["runtime_code_unchanged"])

    def test_pinned_runtime_change_during_wait_aborts_before_next_request(self):
        self.responses = [(self.headroom(), 400)]
        self.after_wait = lambda: self.current_code[0].update(sha256="2" * 64)
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.waits, [20])
        self.assertFalse(self.attempts[0]["runtime_code_unchanged_after_wait"])

    def test_missing_update_clock_can_advance_while_composed_pose_and_state_stay_held(self):
        success = {"ok": True, "directory": "/tmp/unit-fixture-rendered-group"}
        self.responses = [(self.headroom(), 400), (success, 200)]
        self.after_wait = lambda: self.status.update(seconds_since_update=20., transport_state="frozen_updates_missing")
        self.assertIs(self.invoke(), success)
        self.assertEqual(self.waits, [20])
        self.assertTrue(self.attempts[0]["held_state_after_wait"])
        self.assertEqual(self.status["latest"], self.state)
        self.assertEqual(self.status["world_pose"], self.expected_status["world_pose"])

    def test_composed_pose_is_checked_against_gama_even_when_expected_status_also_wrong(self):
        self.status["world_pose"]["position_scene_units"][0] += 10
        self.expected_status = deepcopy(self.status)
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.requests, [])

    def test_rendered_response_is_returned_for_retention_before_changed_state_abort(self):
        rendered = {"ok": True, "directory": "/tmp/unit-fixture-rendered-group"}
        self.responses = [(rendered, 200)]
        self.after_capture = lambda: self.change_held_field("pose")
        self.assertIs(self.invoke(), rendered)
        self.assertEqual(self.waits, [])
        self.assertFalse(self.attempts[0]["held_state_after_response"])
        self.assertIn("ValueError", self.attempts[0]["post_response_status_error"])
        self.assertIs(self.attempts[0]["response"], rendered)

    def test_rendered_response_is_retained_when_post_response_status_read_fails(self):
        rendered = {"ok": False, "error": "Rendered capture failed", "directory": "/tmp/unit-fixture-rendered-group"}
        self.responses = [(rendered, 500)]
        self.after_capture = lambda: setattr(self, "status_failure", OSError("Unit fixture status read failed"))
        self.assertIs(self.invoke(), rendered)
        self.assertEqual(self.waits, [])
        self.assertFalse(self.attempts[0]["held_state_after_response"])
        self.assertIn("OSError", self.attempts[0]["post_response_status_error"])

    def test_transport_exception_is_not_retried(self):
        self.responses = [OSError("Unit fixture HTTP transport failed")]
        with self.assertRaises(OSError):
            self.invoke()
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.waits, [])
        self.assertNotIn("response", self.attempts[0])


if __name__ == "__main__":
    unittest.main()

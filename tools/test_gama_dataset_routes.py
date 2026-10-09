"""Bounded M7 route tests using existing mocked Kit Services fixtures."""
import asyncio
import importlib
import types
import unittest
from unittest.mock import patch

import test_gama_v2_stage as fixture


class DatasetRouteTests(unittest.TestCase):
    call = fixture.RouteTests.call

    def setUp(self):
        fixture.RouteTests.setUp(self)

    def test_extra_payload_fields_rejected_before_owner_or_stage_access(self):
        before = self.stage.GetRootLayer().ExportToString()
        for payload in ({}, {"ownership_token": "x", "orders": [[.5]]},
                        {"ownership_token": "x", "asset_path": "/arbitrary"},
                        {"ownership_token": "x", "code": "arbitrary"}):
            with self.subTest(payload=payload):
                result = self.call("/integration/gama/v2/actor/dataset-capture", payload)
                self.assertFalse(result["ok"])
                self.assertEqual(self.stage_reads, 0)
                self.assertIsNone(self.extension._actor_v2)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)

    def test_owned_token_delegated_to_fixed_dataset_operation(self):
        owner = types.SimpleNamespace(close=lambda: None)
        self.extension._actor_v2 = owner
        calls = []

        async def capture(actual_owner, token):
            calls.append((actual_owner, token))
            return {"ok": True, "capture_count": 10}

        module = importlib.import_module(fixture.PACKAGE + ".dataset_v2")
        with patch.object(module, "run", capture):
            result = self.call("/integration/gama/v2/actor/dataset-capture", {"ownership_token": "test-credential"})
        self.assertEqual(result, {"ok": True, "capture_count": 10})
        self.assertEqual(calls, [(owner, "test-credential")])
        self.assertEqual(self.stage_reads, 0)

    def test_capture_error_reported_without_exposing_success(self):
        self.extension._actor_v2 = types.SimpleNamespace(close=lambda: None)

        async def capture(_owner, _token):
            raise RuntimeError("Capture transaction refused")

        module = importlib.import_module(fixture.PACKAGE + ".dataset_v2")
        with patch.object(module, "run", capture):
            result = self.call("/integration/gama/v2/actor/dataset-capture", {"ownership_token": "test-credential"})
        self.assertEqual(result, {"ok": False, "error": "Capture transaction refused"})

    def test_cancelled_capture_propagated_for_transaction_cleanup(self):
        self.extension._actor_v2 = types.SimpleNamespace(close=lambda: None)

        async def capture(_owner, _token):
            raise asyncio.CancelledError()

        module = importlib.import_module(fixture.PACKAGE + ".dataset_v2")
        with patch.object(module, "run", capture), self.assertRaises(asyncio.CancelledError):
            self.call("/integration/gama/v2/actor/dataset-capture", {"ownership_token": "test-credential"})


if __name__ == "__main__":
    unittest.main()

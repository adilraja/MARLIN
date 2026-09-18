"""Run with Blender's USD Python; no Kit/renderer needed."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from pxr import Gf, Usd, UsdGeom

package = types.ModuleType("_gama_actor_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge")]
sys.modules[package.__name__] = package
actor = importlib.import_module("_gama_actor_test.actor")


class ActorTests(unittest.TestCase):
    def test_counterfactual_only_authors_visibility(self):
        module = importlib.import_module("_gama_actor_test.counterfactual")
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage, actor.ACTOR)
        UsdGeom.Camera.Define(stage, "/Camera")
        before = stage.GetRootLayer().ExportToString()
        module.hide_only_actor(stage)
        prim = stage.GetPrimAtPath(actor.ACTOR)
        self.assertEqual(UsdGeom.Imageable(prim).ComputeVisibility(), "invisible")
        prim.RemoveProperty("visibility")
        self.assertEqual(stage.GetRootLayer().ExportToString(), before)

    def setUp(self):
        self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(self.stage, "Y")
        UsdGeom.SetStageMetersPerUnit(self.stage, .01)
        UsdGeom.Xform.Define(self.stage, "/World/ExistingAnimal")
        UsdGeom.Camera.Define(self.stage, "/World/Camera")
        self.original = self.stage.GetRootLayer().ExportToString()
        self.session = self.stage.GetSessionLayer().ExportToString()
        self.owner = actor.IsolatedActor()
        self.addCleanup(self.owner.close)
        self.token = self.owner.acquire(self.stage)["ownership_token"]

    def step(self, time=0):
        return {"time_s": time, "seed": 184729, "agents": [{"id": actor.AGENT_ID,
            "species": actor.SPECIES, "state": "shallow_swim", "position_m": [12, -.8, 2],
            "heading_deg": 90, "speed_mps": .6, "depth_m": .8}]}

    def test_pose_and_exact_release(self):
        self.owner.apply(self.stage, self.token, self.step())
        prim = self.stage.GetPrimAtPath(actor.ACTOR)
        transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        self.assertEqual(tuple(transform.ExtractTranslation()), (1200, -80, 200))
        forward = transform.TransformDir(Gf.Vec3d(0, 0, 1))
        self.assertAlmostEqual(forward[0], 1)
        self.assertAlmostEqual(forward[2], 0)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.original)
        self.owner.release(self.token)
        self.assertFalse(self.stage.GetPrimAtPath(actor.ROOT))
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), self.session)

    def test_gates_and_atomic_rejection(self):
        before = self.owner.layer.ExportToString()
        for stage, token, paused in ((self.stage, "wrong", False), (self.stage, self.token, True),
                                     (Usd.Stage.CreateInMemory(), self.token, False)):
            with self.assertRaises(ValueError):
                self.owner.apply(stage, token, self.step(), paused)
        bad = self.step()
        bad["agents"][0]["id"] = "ExistingAnimal"
        with self.assertRaises(ValueError):
            self.owner.apply(self.stage, self.token, bad)
        self.assertEqual(self.owner.layer.ExportToString(), before)
        self.assertEqual(self.owner.buffer.accepted_steps, 0)

    def test_retries_order_disconnect_and_metadata(self):
        self.owner.apply(self.stage, self.token, self.step())
        self.assertTrue(self.owner.apply(self.stage, self.token, self.step())["duplicate"])
        altered = self.step()
        altered["agents"][0]["heading_deg"] = 180
        before = self.owner.layer.ExportToString()
        with self.assertRaises(ValueError):
            self.owner.apply(self.stage, self.token, altered)
        self.assertEqual(self.owner.layer.ExportToString(), before)
        self.assertEqual(self.stage.GetPrimAtPath(actor.ROOT).GetCustomDataByKey("marlin:time_s"), 0)
        self.assertEqual(self.owner.status()["motion_policy"], "hold_last_state_without_updates")
        with self.assertRaises(ValueError):
            self.owner.release(self.token, paused=True)

    def test_existing_root_and_second_ownership_refused(self):
        with self.assertRaises(ValueError):
            self.owner.acquire(self.stage)
        other = actor.IsolatedActor()
        with self.assertRaises(ValueError):
            other.acquire(self.stage)

    def test_stage_replacement_cleanup_targets_original(self):
        foreign = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(foreign, actor.ROOT)
        before = foreign.GetRootLayer().ExportToString()
        self.owner.close()
        self.assertFalse(self.stage.GetPrimAtPath(actor.ROOT))
        self.assertEqual(foreign.GetRootLayer().ExportToString(), before)


if __name__ == "__main__":
    unittest.main()

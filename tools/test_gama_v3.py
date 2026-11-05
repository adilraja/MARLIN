"""M2 hand-authored protocol and composed USD checks; no GAMA/renderer claim.

Run with USD Python -B, passing an unused output JSON path. Numeric gates are
read from the pre-run lock, never inferred from observed outcomes.
"""
from copy import deepcopy
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch

from pxr import Gf, Sdf, Usd, UsdGeom

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / 'experiments/gama_dolphin_behaviour_v1'
package = types.ModuleType('_gama_v3_test')
package.__path__ = [str(REPO / 'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge')]
sys.modules[package.__name__] = package
exchange = importlib.import_module(package.__name__ + '.exchange_v3')
actor = importlib.import_module(package.__name__ + '.actor_v3')
T = json.loads((BASE / 'acceptance_tolerances.json').read_text())
assert hashlib.sha256((BASE / 'acceptance_tolerances.json').read_bytes()).hexdigest() == json.loads((BASE/'qa/m2/locked_plan.json').read_text())['tolerance_sha256']
METRICS = []


def step(i=0, **changes):
    value = json.loads((BASE / 'fixtures/m2/valid_step_0.json').read_text())
    value.update(step_index=i, simulation_time_s=float(i))
    value['agents'][0].update(changes)
    return value


def stage(units=.01):
    s = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(s, 'Y')
    UsdGeom.SetStageMetersPerUnit(s, units)
    UsdGeom.Xform.Define(s, '/World/Cetaceans/ExistingAnimal')
    UsdGeom.Camera.Define(s, '/World/Camera')
    return s


class Contract(unittest.TestCase):
    def test_complete_fixtures_and_nonfinite_rejection(self):
        for item in json.loads((BASE/'fixtures/m2/invalid_steps.json').read_text()):
            with self.subTest(item['name']), self.assertRaises(ValueError):
                exchange.validate_step(item['payload'])
        for name in ('valid_step_0.json', 'valid_step_1.json'):
            value = json.loads((BASE/'fixtures/m2'/name).read_text())
            self.assertEqual(value, exchange.validate_step(value))
        for bad in (math.inf, -math.inf, math.nan, True):
            with self.assertRaises(ValueError):
                exchange.validate_step(step(depth_m=bad))

    def test_clock_identity_order_gap_duplicate_atomicity(self):
        b = exchange.StepBuffer()
        b.accept(step())
        self.assertTrue(b.accept(step())['duplicate'])
        self.assertEqual(b.accepted_steps, 1)
        b.accept(step(1))
        for bad in (step(), step(3), dict(step(2), run_id='other'), dict(step(2), seed=2),
                    dict(step(2), model_version='other'), step(2,agent_id='other')):
            before = deepcopy(b.__dict__)
            with self.assertRaises(ValueError):
                b.accept(bad)
            self.assertEqual(before, b.__dict__)
        with self.assertRaises(ValueError):
            exchange.StepBuffer().accept(step(4))

    def test_wrap_brackets_phase_reordered_queries_and_transition(self):
        b = exchange.StepBuffer()
        b.accept(step(heading_deg=350, roll_deg=170))
        b.accept(step(1, heading_deg=10, roll_deg=-170, horizontal_position_m=[5,9],depth_m=1.8))
        expected_phase = (.25+.5*.8)%1
        f = b.evaluate(.5)
        self.assertEqual(f['agent']['heading_deg'], 0)
        self.assertEqual(f['agent']['roll_deg'], -180)
        self.assertEqual(f['agent']['horizontal_position_m'], [4,8])
        self.assertAlmostEqual(f['agent']['depth_m'],1.3)
        self.assertLessEqual(exchange.phase_distance(f['animation_phase_cycles'],expected_phase),T['animation_phase_error_cycles'])
        self.assertEqual(f['transition_progress'],.25)
        values={t:b.evaluate(t) for t in (0,.25,.5,.75,1)}
        self.assertEqual(values,{t:b.evaluate(t) for t in (1,.5,0,.75,.25)})
        for t in (-.1,1.1):
            with self.assertRaises(ValueError): b.evaluate(t)
        self.assertEqual(exchange._angle(0,180,.5),-90)

    def test_zero_speed_reanchor_and_discrete_state(self):
        b=exchange.StepBuffer(); b.accept(step())
        clock=dict(version='constant_rate_v1',epoch_time_s=1.,epoch_phase_cycles=.05,rate_hz=0.)
        b.accept(step(1,speed_mps=0.,animation_clock=clock,behavioural_state='turn',state_entry_time_s=1.))
        self.assertEqual(b.evaluate(.5)['agent']['behavioural_state'],'steady_swim')
        b.accept(step(2,speed_mps=0.,animation_clock=clock,behavioural_state='turn',state_entry_time_s=1.))
        self.assertLessEqual(exchange.phase_distance(b.evaluate(1)['animation_phase_cycles'],b.evaluate(2)['animation_phase_cycles']),T['animation_phase_error_cycles'])
        with self.assertRaises(ValueError):
            b.accept(step(3,speed_mps=0.,animation_clock={**clock,'epoch_phase_cycles':.3}))
        with self.assertRaises(ValueError):
            b.accept(step(3,behavioural_state='ascent',state_entry_time_s=0.))


class ComposedUSD(unittest.TestCase):
    def setUp(self):
        self.s=stage(); self.original=self.s.GetRootLayer().ExportToString(); self.session=self.s.GetSessionLayer().ExportToString()
        self.a=actor.BottlenoseActor(); self.addCleanup(self.a.close)
        self.token=self.a.acquire(self.s,'Bottlenose_001')['ownership_token']

    def apply(self,value): return self.a.apply(self.s,self.token,value)

    def test_cardinals_units_depth_and_fixed_calibration(self):
        for units in (.01,1.):
            self.a.release(self.token); self.s=stage(units); self.token=self.a.acquire(self.s,'Bottlenose_001')['ownership_token']
            body=self.a.expected_body
            for i,h in enumerate((0,90,180,270)):
                self.apply(step(i,heading_deg=h,horizontal_position_m=[3+i,7-i],depth_m=.8+i))
                matrix=self.a._matrix(self.s.GetPrimAtPath(actor.ACTOR))
                actual=list(matrix.ExtractTranslation()*units)
                expected=[3+i,-(.8+i),7-i]
                pos=max(abs(x-y) for x,y in zip(actual,expected))
                forward=matrix.TransformDir(Gf.Vec3d(0,0,1))
                heading=math.degrees(math.atan2(forward[0],forward[2]))%360
                error=abs((heading-h+180)%360-180)
                METRICS.append(dict(test='cardinal',units=units,heading=h,position_error_m=pos,heading_error_deg=error))
                self.assertLessEqual(pos,T['position_error_m']); self.assertLessEqual(error,T['circular_heading_error_deg'])
                self.assertEqual(self.a._body_signature(),body)
            model=UsdGeom.XformCommonAPI(self.s.GetPrimAtPath(actor.ACTOR+'/Model'))
            tr,rot,sc,piv,order=model.GetXformVectors(Usd.TimeCode.Default())
            self.assertEqual(list(rot),[-90,0,0])
            self.assertTrue(all(abs(v*units-1)<=T['model_scale_relative_error'] for v in sc))

    def test_composed_rotation_order_pitch_and_roll(self):
        h,p,r=37.,23.,-19.
        self.apply(step(heading_deg=h,pitch_deg=p,roll_deg=r))
        matrix=self.a._matrix(self.s.GetPrimAtPath(actor.ACTOR))
        forward=matrix.TransformDir(Gf.Vec3d(0,0,1))
        expected=[math.sin(math.radians(h))*math.cos(math.radians(p)),math.sin(math.radians(p)),math.cos(math.radians(h))*math.cos(math.radians(p))]
        err=max(abs(x-y) for x,y in zip(forward,expected));METRICS.append(dict(test='nose_up_forward',matrix_vector_error=err))
        self.assertLessEqual(err,T['orientation_matrix_absolute_error'])
        # Roll turns the local right vector towards local up before pitch/yaw.
        cr,sr=math.cos(math.radians(r)),math.sin(math.radians(r))
        cp,sp=math.cos(math.radians(p)),math.sin(math.radians(p))
        ch,sh=math.cos(math.radians(h)),math.sin(math.radians(h))
        right=matrix.TransformDir(Gf.Vec3d(1,0,0))
        expected=[cr*ch-sr*sp*sh,sr*cp,-cr*sh-sr*sp*ch]
        self.assertLessEqual(max(abs(x-y) for x,y in zip(right,expected)),T['orientation_matrix_absolute_error'])

    def test_interpolation_query_order_pause_resume_reset_missing_hold(self):
        self.apply(step(heading_deg=350)); self.apply(step(1,heading_deg=10,horizontal_position_m=[5,9]))
        snapshots={}
        for t in (0,.5,1):
            self.a.evaluate(self.s,self.token,t); snapshots[t]=(self.a.expected_matrix,self.a.frame)
        for t in (1,0,.5):
            self.a.evaluate(self.s,self.token,t); self.assertEqual((self.a.expected_matrix,self.a.frame),snapshots[t])
        self.a.set_paused(self.s,self.token,True)
        before=self.a.layer.ExportToString();frame=deepcopy(self.a.frame)
        with self.assertRaises(ValueError): self.apply(step(2))
        with self.assertRaises(ValueError): self.a.evaluate(self.s,self.token,1)
        self.assertEqual(before,self.a.layer.ExportToString())
        with patch.object(actor.time,'monotonic',return_value=self.a.last_received+10):
            self.assertEqual(self.a.status(self.s)['transport_state'],'paused')
        self.a.set_paused(self.s,self.token,False)
        self.assertEqual(before,self.a.layer.ExportToString());self.assertEqual(frame,self.a.frame)
        with patch.object(actor.time,'monotonic',return_value=self.a.last_received+10):
            self.assertEqual(self.a.status(self.s)['transport_state'],'frozen_updates_missing')
        self.assertEqual(before,self.a.layer.ExportToString())
        self.a.reset(self.s,self.token); self.assertEqual(before,self.a.layer.ExportToString())
        self.assertEqual(self.a.buffer.accepted_steps,0)
        self.apply(dict(step(),run_id='reset_run'))

    def test_invalid_duplicate_stale_and_capture_gate_do_not_mutate(self):
        self.apply(step()); self.apply(step(1));before=self.a.layer.ExportToString();count=self.a.buffer.accepted_steps
        self.assertTrue(self.apply(step(1))['duplicate'])
        for value in [step(),step(3),step(2,agent_id='other')]+[x['payload'] for x in json.loads((BASE/'fixtures/m2/invalid_steps.json').read_text())]:
            with self.assertRaises(ValueError): self.apply(value)
            self.assertEqual(before,self.a.layer.ExportToString());self.assertEqual(count,self.a.buffer.accepted_steps)
        with self.assertRaises(ValueError): self.a.apply(self.s,self.token,step(2),paused=True)
        with self.assertRaises(ValueError): self.a.apply(self.s,'wrong',step(2))
        self.assertEqual(before,self.a.layer.ExportToString())

    def test_composition_failure_rolls_back_buffer_and_layer(self):
        self.apply(step());before=self.a.layer.ExportToString();buffer=deepcopy(self.a.buffer.__dict__)
        with patch.object(self.a,'_matrix',return_value=Gf.Matrix4d(2)):
            with self.assertRaises(ValueError): self.a._write(self.s,self.a.buffer.evaluate(0))
        self.assertEqual(before,self.a.layer.ExportToString());self.assertEqual(buffer,self.a.buffer.__dict__)

    def test_conflicting_writer_detected_without_overwriting_foreign_layer(self):
        for target in (actor.ACTOR,actor.ACTOR+'/Model'):
            with Usd.EditContext(self.s,self.s.GetSessionLayer()):
                if target == actor.ACTOR:
                    self.s.GetPrimAtPath(target).GetAttribute('xformOp:transform').Set(Gf.Matrix4d(1).SetTranslate(Gf.Vec3d(999,0,0)))
                else:
                    UsdGeom.XformCommonAPI(self.s.GetPrimAtPath(target)).SetTranslate(Gf.Vec3d(999,0,0))
            before=self.s.GetSessionLayer().ExportToString();owned=self.a.layer.ExportToString()
            self.assertEqual(self.a.status(self.s)['transport_state'],'frozen_guard_failure')
            with self.assertRaises(ValueError):self.apply(step())
            self.assertEqual(before,self.s.GetSessionLayer().ExportToString());self.assertEqual(owned,self.a.layer.ExportToString())
            # Remove only this test's external override; owned layer stays attached.
            edit=Sdf.BatchNamespaceEdit();edit.Add(actor.ROOT,Sdf.Path.emptyPath);self.s.GetSessionLayer().Apply(edit)
        self.assertIsNone(self.a.status(self.s)['guard_error'])

    def test_duplicate_owner_release_and_foreign_stage(self):
        other=actor.BottlenoseActor();self.addCleanup(other.close)
        with self.assertRaises(ValueError):other.acquire(self.s,'Other')
        with self.assertRaises(ValueError):self.a.acquire(self.s,'Other')
        self.assertEqual(self.a.agent_id,'Bottlenose_001')
        foreign=stage();foreign_before=foreign.GetRootLayer().ExportToString()
        with self.assertRaises(ValueError):self.a.apply(foreign,self.token,step())
        self.a.release(self.token)
        self.assertEqual(self.s.GetRootLayer().ExportToString(),self.original)
        self.assertEqual(self.s.GetSessionLayer().ExportToString(),self.session)
        self.assertFalse(self.s.GetPrimAtPath(actor.ROOT));self.assertTrue(self.s.GetPrimAtPath('/World/Cetaceans/ExistingAnimal'))
        self.assertEqual(foreign.GetRootLayer().ExportToString(),foreign_before)

    def test_explicit_stage_coordinates_required(self):
        for configure in (lambda s:None,lambda s:UsdGeom.SetStageUpAxis(s,'Y'),lambda s:UsdGeom.SetStageMetersPerUnit(s,.01)):
            s=Usd.Stage.CreateInMemory();configure(s);a=actor.BottlenoseActor();self.addCleanup(a.close)
            with self.assertRaises(ValueError):a.acquire(s,'Bottlenose_001')


if __name__=='__main__':
    output=Path(sys.argv[1]);assert not output.exists(),output
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,
        failures=[(str(t),e) for t,e in result.failures],errors=[(str(t),e) for t,e in result.errors],
        tolerance_sha256=hashlib.sha256((BASE/'acceptance_tolerances.json').read_bytes()).hexdigest(),
        metrics=METRICS,scope='CPU composed USD; hand-authored fixtures; no new GAMA model or animation integration'),indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)

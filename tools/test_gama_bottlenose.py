"""Check continuous joins and acceptance rejection using actual GAMA evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import analyze_gama_bottlenose as analysis
import gama_bottlenose as runner

BASE=runner.BASE


class BottlenoseAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads(runner.CONFIG.read_text());cls.tol=json.loads(runner.ACCEPTANCE.read_text())
        root=BASE/'trajectories/m3_ref_a01'
        cls.states=json.loads((root/'trajectory.json').read_text());cls.diagnostics=json.loads((root/'diagnostics.json').read_text())
        cls.choice=json.loads((root/'execution.json').read_text())['realised_choices']

    def evaluate(self,s=None,d=None):return analysis.analyze(s or self.states,d or self.diagnostics,self.config,self.tol,False)

    def test_retained_actual_reference_passed(self):self.assertTrue(self.evaluate()['passed'])

    def test_position_teleport_was_rejected(self):
        s=deepcopy(self.states);s[40]['agents'][0]['horizontal_position_m'][0]+=.1
        self.assertFalse(self.evaluate(s)['passed'])

    def test_wrong_vertical_velocity_was_rejected(self):
        s=deepcopy(self.states);s[100]['agents'][0]['vertical_velocity_mps']+=.02
        self.assertFalse(self.evaluate(s)['passed'])

    def test_incoherent_attitude_was_rejected(self):
        s=deepcopy(self.states);s[100]['agents'][0]['pitch_deg']+=1
        self.assertFalse(self.evaluate(s)['passed'])

    def test_disconnected_label_was_rejected(self):
        s=deepcopy(self.states);s[150]['agents'][0]['behavioural_state']='turn'
        with self.assertRaises(ValueError):self.evaluate(s)

    def test_repeated_random_draws_were_rejected(self):
        d=deepcopy(self.diagnostics);d[60]['random_draw_count']=4
        self.assertFalse(self.evaluate(d=d)['passed'])

    def test_gap_and_phase_jump_were_rejected(self):
        with self.assertRaises(ValueError):self.evaluate(self.states[:30]+self.states[31:])
        s=deepcopy(self.states);s[30]['agents'][0]['animation_clock']['epoch_phase_cycles']+=.01
        with self.assertRaises(ValueError):self.evaluate(s)

    def test_continuous_control_values_at_all_boundaries(self):
        p=self.config['parameters'];boundaries=[2,6,10,22,38,48,64,68,72]
        for t in boundaries:
            a,b=[analysis.controls(t+sign*1e-7,p,self.choice) for sign in (-1,1)]
            self.assertLess(abs(analysis.delta(a['heading'],b['heading'])),1e-4)
            for k in ('depth','vy','speed','pitch','vx','vz'):self.assertLess(abs(a[k]-b[k]),1e-5,(t,k))

    def test_zero_speed_retained_defined_heading(self):
        first,last=self.states[0]['agents'][0],self.states[-1]['agents'][0]
        self.assertEqual(first['speed_mps'],0);self.assertEqual(last['speed_mps'],0)
        self.assertEqual(first['heading_deg'],350);self.assertEqual(last['heading_deg'],65)


if __name__=='__main__':
    output=Path(sys.argv[1]);assert not output.exists()
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);result=unittest.TextTestRunner(verbosity=2).run(suite)
    runner.write(output,dict(passed=result.wasSuccessful(),tests=result.testsRun,
        failures=[(str(t),e) for t,e in result.failures],errors=[(str(t),e) for t,e in result.errors],
        actual_gama_input='trajectories/m3_ref_a01',test_source_sha256=runner.sha(Path(__file__))))
    sys.exit(0 if result.wasSuccessful() else 1)

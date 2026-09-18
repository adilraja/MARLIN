"""Synthetic pixel tests, independent of the saved test result."""
import unittest
import numpy as np
from analyse_gama_counterfactual import evidence


class DifferenceTests(unittest.TestCase):
    def test_unchanged_is_not_evidence(self):
        a=np.full((2,2,3),100,dtype=np.uint8)
        self.assertFalse(evidence(a,a,a,a)[0].any())

    def test_repeated_actor_signal_is_evidence(self):
        off=np.full((2,2,3),100,dtype=np.uint8)
        on=off.copy()
        on[0,1]=60
        mask,_,_=evidence(on,off,off,on)
        self.assertEqual(int(mask.sum()),1)
        self.assertTrue(mask[0,1])

    def test_same_state_noise_is_not_actor_effect(self):
        low=np.full((2,2,3),50,dtype=np.uint8)
        high=np.full((2,2,3),150,dtype=np.uint8)
        self.assertFalse(evidence(low,high,low,high)[0].any())

    def test_one_code_value_is_not_evidence(self):
        a=np.full((2,2,3),100,dtype=np.uint8)
        self.assertFalse(evidence(a,a+1,a+1,a)[0].any())


if __name__=="__main__":
    unittest.main()

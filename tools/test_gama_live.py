"""Offline protocol tests: no WebSocket dependency or network access required."""
import json
import math
import unittest
from gama_live import GamaClient, snapshot


class Socket:
    def __init__(self, mode="ok"):
        self.mode=mode
        self.sent=[]
        self.calls=0

    def send(self,value):
        self.sent.append(json.loads(value))

    def recv(self,timeout):
        self.calls+=1
        if self.mode=="timeout":
            raise TimeoutError("test")
        if self.mode=="event" and self.calls==1:
            return json.dumps({"type":"ConnectionSuccessful"})
        command=dict(self.sent[-1])
        if self.mode=="wrong":
            command["request_id"]+=1
        return json.dumps({"type":"UnableToExecuteRequest" if self.mode=="error" else "CommandExecutedSuccessfully",
                           "command":command,"content":"done"})


class ProtocolTests(unittest.TestCase):
    def test_correlated_acknowledgement(self):
        socket=Socket("event")
        client=GamaClient(socket)
        self.assertEqual(client.request("step",exp_id="test",nb_step=1,sync=True),"done")
        self.assertEqual(socket.sent[0]["nb_step"],1)
        self.assertTrue(socket.sent[0]["sync"])
        self.assertEqual(socket.calls,2)

    def test_fail_closed_without_retries(self):
        for mode in ("timeout","wrong","error"):
            socket=Socket(mode)
            client=GamaClient(socket)
            with self.assertRaises((TimeoutError,RuntimeError)):
                client.request("step",nb_step=1,sync=True)
            with self.assertRaises(RuntimeError):
                client.request("step",nb_step=1,sync=True)
            self.assertEqual(len(socket.sent),1)

    def test_cycle_time_seed_and_geometry(self):
        values=[1,0,0,-.8,12,90,12*math.radians(3),184729]
        state=snapshot(values,1)
        self.assertEqual(state["agents"][0]["position_m"],[0,-.8,12])
        for index,value in ((0,2),(1,1),(2,5),(5,0),(6,9),(7,42)):
            bad=list(values)
            bad[index]=value
            with self.assertRaises(ValueError):
                snapshot(bad,1)


if __name__=="__main__":
    unittest.main()

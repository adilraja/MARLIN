"""Bounded, single-flight GAMA WebSocket -> MARLIN HTTP verification.

Never sends play. Never retries a step after a timeout. No MARLIN source changes.
Run against an explicitly started trusted-local GAMA server; this client doesn't
launch or terminate the server. Socket closure disposes client-owned experiments.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.parse import urlparse
from gama_trajectory import ROOT, call, exchange

EXPRESSION = "[simulation.cycle, simulation.time_s, simulation.x_m, simulation.y_m, simulation.z_m, simulation.heading_deg, simulation.speed_mps, simulation.seed]"


class GamaClient:
    def __init__(self, socket, timeout=30):
        self.socket, self.timeout = socket, timeout
        self.serial = 0
        self.trace = []
        self.failed = False

    def request(self, kind, **fields):
        if self.failed:
            raise RuntimeError("Connection failed/uncertain; start a fresh run, never retry a step")
        self.serial += 1
        command = dict(type=kind, request_id=self.serial, **fields)
        self.trace.append({"sent":command})
        try:
            self.socket.send(json.dumps(command))
            deadline = time.monotonic() + self.timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("GAMA acknowledgement deadline exceeded")
                response = json.loads(self.socket.recv(timeout=remaining))
                self.trace.append({"received":response})
                if response.get("type") in ("RuntimeError", "GamaServerError", "SimulationError", "SimulationErrorDialog"):
                    raise RuntimeError(response)
                echoed = response.get("command")
                if echoed is None and response.get("type") in ("ConnectionSuccessful", "SimulationOutput", "SimulationStatus", "SimulationStatusInform", "SimulationStatusNeutral", "SimulationDebug"):
                    continue
                if echoed != command:
                    raise RuntimeError("Unmatched GAMA response; refusing ambiguous command completion")
                if response.get("type") != "CommandExecutedSuccessfully":
                    raise RuntimeError(response)
                return response.get("content")
        except BaseException:
            self.failed = True
            raise

    def read(self, exp_id):
        values = self.request("expression", exp_id=exp_id, expr=EXPRESSION)
        return json.loads(values) if isinstance(values,str) else values


def snapshot(values, expected_cycle):
    if not isinstance(values,list) or len(values)!=8:
        raise ValueError("Expected eight GAMA state values")
    cycle, seconds, x, y, z, heading, speed, seed = values
    if cycle != expected_cycle or seconds != expected_cycle-1 or seed != 184729:
        raise ValueError("Unexpected GAMA step/time/seed; not applying to MARLIN")
    # Installed GAMA JSON transport rounds floats to eight decimal places.
    if not math.isclose(math.hypot(x,z),12,abs_tol=1e-6):
        raise ValueError("Unexpected fixture radius")
    if abs((heading-math.degrees(math.atan2(z,-x))+180)%360-180)>1e-6:
        raise ValueError("Fixture heading is not tangent")
    if not math.isclose(speed,12*math.radians(3),abs_tol=1e-8):
        raise ValueError("Unexpected fixture speed")
    return exchange.validate_step({"time_s":seconds,"seed":int(seed),"agents":[{
        "id":"Gama_Bottlenose_001","species":"bottlenose_dolphin","state":"shallow_swim",
        "position_m":[x,y,z],"heading_deg":heading,"speed_mps":speed,"depth_m":max(0,-y)}]})


def preserved(before, after):
    old = {a["name"]:a for a in before["swimming"]["animals"]}
    new = {a["name"]:a for a in after["swimming"]["animals"]}
    return {
        "eleven_swimmers_running": after["swimming"]["running"] and len(new)==11 and new.keys()==old.keys(),
        "all_swimmers_advanced": new.keys()==old.keys() and all((old[k]["x"],old[k]["z"])!=(new[k]["x"],new[k]["z"]) for k in old),
        "no_deformation_errors": all(not a.get("deformation_error") for a in new.values()),
        "ocean_advanced":after["ocean"]["running"] and after["ocean"]["elapsed"]>before["ocean"]["elapsed"],
        "ocean_parameters_preserved":{k:v for k,v in before["ocean"].items() if k!="elapsed"}=={k:v for k,v in after["ocean"].items() if k!="elapsed"},
        "settings_preserved":before["renderer_settings"]==after["renderer_settings"],
        "lighting_materials_cameras_preserved":before["stable_scene_attributes"]==after["stable_scene_attributes"],
        "active_camera_preserved":before["inspection"]["camera"]==after["inspection"]["camera"],
    }


def run_once(server, marlin, result):
    from websockets.sync.client import connect
    result.update(steps=[], checks={}, protocol=[])
    before = call(marlin,"/integration/gama/marine/audit")
    if not before["swimming"]["running"] or before["swimming"]["animal_count"]!=11 or not before["ocean"]["running"]:
        raise ValueError("Marine gallery and ocean must already be running")
    result["before"] = before
    socket = connect(server,open_timeout=10,close_timeout=3,proxy=None,max_size=1048576)
    client = GamaClient(socket)
    token = None
    try:
        exp_id = client.request("load", model=str(ROOT/"integrations/gama/trajectory_live.gaml"),experiment="live_fixture",console=False,status=False,runtime=True)
        result["experiment_id"] = exp_id
        initial = client.read(exp_id)
        if initial[0]!=0 or initial[-1]!=184729:
            raise ValueError("Initial cycle/seed mismatch")
        acquired = call(marlin,"/integration/gama/actor/acquire",{})
        token = acquired["ownership_token"]
        for cycle in range(1,21):
            client.request("step",exp_id=exp_id,nb_step=1,sync=True)
            step = snapshot(client.read(exp_id),cycle)
            call(marlin,"/integration/gama/actor/step",{"ownership_token":token,"step":step})
            actual = call(marlin,"/integration/gama/actor/status")["world_pose"]
            expected = exchange.preview_transforms(step,acquired["meters_per_scene_unit"])[0]
            if any(abs(a-b)>1e-5 for k in ("position_scene_units","forward_y_up") for a,b in zip(actual[k],expected[k])):
                raise ValueError("Applied USD pose mismatch")
            result["steps"].append(step)
            if cycle==10:
                client.request("pause",exp_id=exp_id)
                held = client.read(exp_id)
                pause_before = call(marlin,"/integration/gama/marine/audit")
                time.sleep(2)
                result["checks"]["pause"] = {
                    "gama_held":client.read(exp_id)==held,
                    "actor_held":call(marlin,"/integration/gama/actor/status")["world_pose"]==actual,
                    **preserved(pause_before,call(marlin,"/integration/gama/marine/audit"))}
        disconnect_before = call(marlin,"/integration/gama/marine/audit")
        socket.close()  # Intentionally disconnect instead of a GAMA stop command.
        time.sleep(2)
        result["checks"]["disconnect"] = {
            "actor_held":call(marlin,"/integration/gama/actor/status")["world_pose"]==actual,
            **preserved(disconnect_before,call(marlin,"/integration/gama/marine/audit"))}
        result["completed"] = True
    finally:
        socket.close()
        result["protocol"] = client.trace
        if token is not None:
            result["release"] = call(marlin,"/integration/gama/actor/release",{"ownership_token":token})
        time.sleep(1)
        after = call(marlin,"/integration/gama/marine/audit")
        result["after"] = after
        result["checks"]["cleanup"] = {
            "actor_released":not call(marlin,"/integration/gama/actor/status")["owned"],
            "layers_restored":before["inspection"]["layers"]==after["inspection"]["layers"],
            **preserved(before,after)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server",default="ws://127.0.0.1:6868")
    parser.add_argument("--marlin",default="http://127.0.0.1:8011")
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    for url in (args.server,args.marlin):
        if urlparse(url).hostname not in ("localhost","127.0.0.1","::1"):
            parser.error("This bounded coordinator supports loopback connections only")
    if args.output.exists():
        parser.error("Choose an unused report path")
    report = {"passed":False,"runs":[],"biological_validation":False,
              "model_sha256":{n:hashlib.sha256((ROOT/"integrations/gama"/n).read_bytes()).hexdigest() for n in ("trajectory.gaml","trajectory_live.gaml")}}
    try:
        for _ in range(2):
            result = {}
            report["runs"].append(result)
            run_once(args.server,args.marlin,result)
        report["identical_trajectories"] = report["runs"][0]["steps"]==report["runs"][1]["steps"]
        report["passed"] = report["identical_trajectories"] and all(
            r.get("completed") and len(r["steps"])==20 and all(all(v.values()) for v in r["checks"].values()) for r in report["runs"])
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({"passed":report["passed"],"report":str(args.output),"error":report.get("error")},indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()

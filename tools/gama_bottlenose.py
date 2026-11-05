"""Record actual GAMA v3 bottlenose runs; never contact or mutate MARLIN.

Reuses the existing record-first legacy-headless XML/subprocess pattern. Refuses
existing output/workspace paths and retains failed executions and raw exports.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import types
import xml.etree.ElementTree as ET

REPO=Path(__file__).resolve().parents[1]
BASE=REPO/'experiments/gama_dolphin_behaviour_v1'
MODEL=REPO/'integrations/gama/bottlenose_constrained_v1.gaml'
CONFIG=BASE/'config/m3_parameters_v1.json'
ACCEPTANCE=BASE/'config/m3_acceptance_v1.json'
package=types.ModuleType('_gama_bottlenose_boundary')
package.__path__=[str(REPO/'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge')]
sys.modules[package.__name__]=package
exchange=importlib.import_module(package.__name__+'.exchange_v3')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def canonical(states):
    copies=[{k:v for k,v in s.items() if k!='run_id'} for s in states]
    return json.dumps(copies,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def load_config():
    config=json.loads(CONFIG.read_text());p=config['parameters']
    if config['version']!='bottlenose_constrained_v1' or config['biological_approval'] is not False:
        raise ValueError('Only the declared engineering model is supported')
    for k,v in p.items():
        if type(v) not in (float,int) or not math.isfinite(v):raise ValueError('Non-finite parameter: '+k)
    for k in ('step','steady_s','turn_s','descent_s','submerged_s','ascent_s','final_steady_s','speed_ramp_s','cruise_speed_mps'):
        if p[k]<=0:raise ValueError('Nonpositive parameter: '+k)
    duration=sum(p[k] for k in ('steady_s','turn_s','descent_s','submerged_s','ascent_s','final_steady_s'))
    count=round(duration/p['step'])+1
    if not 7<=count<=10000:raise ValueError('Unsupported number of samples')
    return config,count


def read_trajectory(path,run_id,seed,variation,config):
    root=ET.parse(path).getroot();rows=root.findall('Step')
    _,count=load_config()
    if root.tag!='Simulation' or len(rows)!=count:raise ValueError('Incomplete actual GAMA export: '+str(len(rows)))
    outputs=set(re.findall(r'monitor "([^"]+)" value:',MODEL.read_text()))
    states=[];diagnostics=[];buffer=exchange.StepBuffer()
    for i,row in enumerate(rows):
        values={}
        for item in row.findall('Variable'):
            key=item.attrib['name']
            if key in values:raise ValueError('Duplicate GAMA output: '+key)
            values[key]=item.text if item.text is not None else item.attrib.get('value')
        if set(values)!=outputs:raise ValueError('Missing/extra GAMA outputs')
        def number(k):
            x=float(values[k])
            if not math.isfinite(x):raise ValueError('Non-finite GAMA value: '+k)
            return x
        if int(row.attrib['id'])!=i or number('step_index')!=i:raise ValueError('Noncontiguous GAMA output')
        if number('actual_seed')!=seed or number('agent_count')!=1:raise ValueError('Actual seed/agent count mismatch')
        if values['run_id']!=run_id or values['enable_variation'].lower()!=str(variation).lower():raise ValueError('Run/mode mismatch')
        for key,value in config['parameters'].items():
            if number('cfg_'+key)!=value:raise ValueError('Effective GAMA parameter mismatch: '+key)
        agent=dict(agent_id=values['agent_id'],species=values['species'],behavioural_state=values['behavioural_state'],
            horizontal_position_m=[number('x_m'),number('z_m')],heading_deg=number('heading_deg'),pitch_deg=number('pitch_deg'),
            roll_deg=number('roll_deg'),speed_mps=number('speed_mps'),vertical_velocity_mps=number('vertical_velocity_mps'),
            vertical_reference=values['vertical_reference'],depth_m=number('depth_m'),state_entry_time_s=number('state_entry_time_s'),
            transition_duration_s=number('transition_duration_s'),animation_clock=dict(version=values['phase_version'],
                epoch_time_s=number('phase_epoch_time_s'),epoch_phase_cycles=number('phase_epoch_cycles'),rate_hz=number('phase_rate_hz')))
        state=dict(schema_version=values['schema_version'],model_version=values['model_version'],run_id=run_id,
            step_index=i,simulation_time_s=number('simulation_time_s'),simulation_step_s=number('simulation_step_s'),seed=seed,agents=[agent])
        buffer.accept(state);states.append(state)
        diagnostics.append(dict(step_index=i,episode=values['episode'],vx_mps=number('vx_mps'),vz_mps=number('vz_mps'),
            random_draw_count=number('random_draw_count'),realised_turn_deg=number('realised_turn_deg'),
            realised_depth_m=number('realised_depth_m'),realised_speed_mps=number('realised_speed_mps')))
    return states,diagnostics


def execute(run_id,seed,variation,lock_path):
    exchange._identifier(run_id,'run_id')
    if type(seed) is not int or not 1<=seed<=2**31-1:raise ValueError('Explicit positive 31-bit seed required')
    config,count=load_config();lock=json.loads(lock_path.read_text())
    for record in lock['inputs']:
        if sha(REPO/record['path'])!=record['sha256']:raise ValueError('Locked implementation input changed: '+record['path'])
    output=BASE/'trajectories'/run_id;workspace=REPO/'artifacts/gama_dolphin_behaviour_v1/workspaces'/run_id
    if output.exists() or workspace.exists():raise ValueError('Run/workspace exists; retain it and choose a new identity')
    output.mkdir(parents=True);workspace.mkdir(parents=True)
    shutil.copyfile(MODEL,output/'model.gaml');shutil.copyfile(CONFIG,output/'parameters.json');shutil.copyfile(ACCEPTANCE,output/'acceptance.json')
    launcher=Path(shutil.which('gama-headless') or '/usr/sbin/gama-headless')
    names=re.findall(r'monitor "([^"]+)" value:',MODEL.read_text())
    plan=ET.Element('Experiment_plan');sim=ET.SubElement(plan,'Simulation',id='0',sourcePath=str(output/'model.gaml'),finalStep=str(count),experiment=config['experiment'],seed=str(seed))
    parameters=ET.SubElement(sim,'Parameters')
    for name,value in {**config['parameters'],'requested_seed':seed,'exchange_run_id':run_id,'enable_variation':variation}.items():
        kind='BOOLEAN' if type(value) is bool else 'STRING' if isinstance(value,str) else 'INT' if type(value) is int else 'FLOAT'
        ET.SubElement(parameters,'Parameter',var=name,type=kind,value=str(value).lower() if type(value) is bool else str(value))
    outputs=ET.SubElement(sim,'Outputs')
    for i,name in enumerate(names):ET.SubElement(outputs,'Output',id=str(i),name=name,framerate='1')
    ET.indent(plan);ET.ElementTree(plan).write(output/'experiment.xml',encoding='utf-8',xml_declaration=True)
    command=[str(launcher),'-m','1024m','-ws',str(workspace),str(output/'experiment.xml'),str(output/'raw')]
    runtime_path=Path('/opt/gama-platform/configuration/config.ini')
    runtime=dict(line.split('=',1) for line in runtime_path.read_text().splitlines() if line.startswith(('gama.version=','gama.commit=','gama.jdk=')))
    report=dict(status='started',run_id=run_id,requested_seed=seed,variation=variation,command=command,cwd=str(REPO),
        started_utc=datetime.now(timezone.utc).isoformat(),runtime=runtime,launcher=str(launcher.resolve()),
        launcher_sha256=sha(launcher),runtime_configuration_sha256=sha(runtime_path),model_sha256=sha(MODEL),
        configuration_sha256=sha(CONFIG),acceptance_sha256=sha(ACCEPTANCE),implementation_lock_sha256=sha(lock_path),
        experiment_plan_sha256=sha(output/'experiment.xml'),marlin_http_used=False,scene_mutated=False,biological_approval=False)
    start=time.monotonic()
    try:
        with (output/'launcher.log').open('x') as log:
            process=subprocess.Popen(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            report['launcher_process_id']=process.pid
            try:code=process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill();process.wait();raise RuntimeError('Timed out; failed run retained')
        report['return_code']=code
        if code:raise RuntimeError('GAMA returned a failure; see retained logs')
        states,diagnostics=read_trajectory(output/'raw/simulation-outputs0.xml',run_id,seed,variation,config)
        write(output/'trajectory.json',states);write(output/'diagnostics.json',diagnostics)
        from analyze_gama_bottlenose import analyze
        result=analyze(states,diagnostics,config,json.loads(ACCEPTANCE.read_text()),variation)
        write(output/'analysis.json',result)
        if not result['passed']:raise ValueError('Declared movement acceptance failed')
        for record in lock['inputs']:
            if sha(REPO/record['path'])!=record['sha256']:raise ValueError('Input changed during execution')
        report.update(status='passed',samples=len(states),actual_seed=states[0]['seed'],canonical_state_sha256=hashlib.sha256(canonical(states)).hexdigest(),
            trajectory_sha256=sha(output/'trajectory.json'),raw_xml_sha256=sha(output/'raw/simulation-outputs0.xml'),
            realised_choices={k:diagnostics[0][k] for k in ('realised_turn_deg','realised_depth_m','realised_speed_mps','random_draw_count')})
    except Exception as error:
        report.update(status='failed',error=type(error).__name__+': '+str(error))
    finally:
        report['elapsed_wall_s']=time.monotonic()-start;report['finished_utc']=datetime.now(timezone.utc).isoformat();write(output/'execution.json',report)
    print(json.dumps(report),flush=True)
    return report['status']=='passed'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--variation',action='store_true');parser.add_argument('--lock',type=Path,required=True);args=parser.parse_args()
    sys.exit(0 if execute(args.run_id,args.seed,args.variation,args.lock) else 1)

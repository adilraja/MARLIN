"""External HTTP flight preview for the cleaned petrel; Ctrl-C stops motion.

This is a rigid-wing gliding demonstration in scene units, not biological
flight calibration. Kit remains the renderer; no alternate simulation engine.
"""
import argparse
import ast
import math
import time
from rebuild_scene import request


def fly(duration=120.0):
    name='ReviewCleaned_european_storm_petrel'
    prim=next((p for p in request('/debug/scene/inspection')['prims']
               if p['path'].endswith('/'+name)),None)
    if prim is None:
        raise RuntimeError('Load compare_cleaned_birds.py first.')
    origin=list(ast.literal_eval(next(op['value'] for op in prim['xform_ops']
                                     if op['name']=='xformOp:translate')))
    origin[1]+=max(0,800-prim['bounds_min'][1])
    radius=600.0
    speed=120.0
    request('/scene/camera/chase/start',{'target_name':name,'camera_name':'PetrelFlightCamera',
        'distance':1800,'height':500,'side_offset':450,'look_ahead':0,
        'look_height':100,'documentary_mode':False,'focal_length':24})
    start=time.monotonic()
    print('Petrel gliding preview started; rigid wings, 800+ scene units above water. Ctrl-C stops.',flush=True)
    try:
        while duration == 0 or time.monotonic()-start < duration:
            angle=(time.monotonic()-start)*speed/radius
            position=[origin[0]+radius*(math.cos(angle)-1),origin[1],origin[2]+radius*math.sin(angle)]
            request('/scene/cetacean/transform',{'name':name,'position':position,
                'rotation':[0,(-math.degrees(angle))%360,0]})
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        print('Flight preview stopped. Petrel remains at its last position.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration',type=float,default=120,help='Seconds, or 0 until Ctrl-C')
    args=parser.parse_args()
    if not math.isfinite(args.duration) or args.duration<0:
        parser.error('duration must be finite and nonnegative')
    fly(args.duration)

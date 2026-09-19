"""Orthographic scientific mesh views, no geometry or texture modifications."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/"artifacts/gama/bottlenose_review"
mesh=json.loads((directory/"mesh.json").read_text())[0]
points=np.asarray(mesh["points"])
faces=[]
offset=0
for count in mesh["counts"]:
    faces.append(mesh["indices"][offset:offset+count]);offset+=count
lo,hi=points.min(0),points.max(0)
calibration=json.loads((directory/"calibration.json").read_text())
factor=calibration["scale_multiplier_relative_to_legacy"]
image=Image.new("RGB",(1200,940),"white")
draw=ImageDraw.Draw(image)
for row,(name,h,v,depth) in enumerate((("Side: +Z right, +Y up",2,1,0),("Top: +Z right, +X up",2,0,1))):
    scale=1000/(hi[h]-lo[h]); center=(lo+hi)/2
    def project(p):return (100+(p[h]-lo[h])*scale,285+row*450-(p[v]-center[v])*scale)
    for face in sorted(faces,key=lambda ids:float(points[ids,depth].mean())):
        pts=points[face]
        normal=np.cross(pts[1]-pts[0],pts[2]-pts[0]);length=np.linalg.norm(normal)
        shade=int(85+130*abs(normal[depth]/length)) if length else 130
        draw.polygon([project(p) for p in pts],fill=(shade,shade,shade))
    draw.text((20,row*450+10),name+"; 2.6 m length candidate, NOT specimen calibration",fill="black")
    for label,color in (("rostrum_tip","red"),("fluke_notch_candidate","blue"),("dorsal_tip","green")):
        p=np.asarray(calibration["landmarks_m"][label])/factor
        x,y=project(p);draw.ellipse((x-4,y-4,x+4,y+4),fill=color);draw.text((x+5,y),label,fill=color)
    if row==0:
        y=project([0,.8/factor,0])[1]
        draw.line((40,y,1160,y),fill="blue",width=2)
        draw.text((40,y+5),f"Mean sea plane at origin depth 0.8 m. Highest mesh point {calibration['mean_plane_clearance_at_fixture_depth_m']:.3f} m below plane.",fill="blue")
draw.text((20,915),"Flat-plane shallow-swim check only. No positive blowhole clearance; animated-wave clearance unresolved.",fill="black")
image.save(directory/"orthographic.png")
print("bounds",lo.tolist(),hi.tolist(),"dimensions",(hi-lo).tolist())
for label,i in (("maxZ",np.argmax(points[:,2])),("minZ",np.argmin(points[:,2])),("maxY",np.argmax(points[:,1]))):print(label,int(i),points[i].tolist())

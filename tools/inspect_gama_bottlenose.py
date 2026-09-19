"""Non-destructive world-space mesh inspection using Blender's USD Python."""
import json
import importlib.util
from pathlib import Path
from pxr import Gf, Usd, UsdGeom

ROOT=Path(__file__).resolve().parents[1]


def main():
    stage=Usd.Stage.CreateInMemory()
    model=UsdGeom.Xform.Define(stage,"/Model")
    model.GetPrim().GetReferences().AddReference(str(ROOT/"assets/cetaceans/bottlenose_dolphin/usd/bottlenose_dolphin.usd"))
    UsdGeom.XformCommonAPI(model).SetRotate(Gf.Vec3f(-90,0,0))
    records=[]
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh=UsdGeom.Mesh(prim)
            transform=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            records.append({"path":str(prim.GetPath()),"points":[list(transform.Transform(Gf.Vec3d(p))) for p in mesh.GetPointsAttr().Get()],
                            "counts":list(mesh.GetFaceVertexCountsAttr().Get()),"indices":list(mesh.GetFaceVertexIndicesAttr().Get())})
    output=ROOT/"artifacts/gama/bottlenose_review"
    output.mkdir(parents=True,exist_ok=True)
    (output/"mesh.json").write_text(json.dumps(records))
    path=ROOT/"source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/calibration.py"
    spec=importlib.util.spec_from_file_location("gama_calibration",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    report=module.measure(model.GetPrim(),ROOT/"assets/cetaceans/bottlenose_dolphin/usd/bottlenose_dolphin.usd")
    (output/"calibration.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Measured meshes:",len(records),"vertices:",sum(len(r["points"]) for r in records))


if __name__=="__main__": main()

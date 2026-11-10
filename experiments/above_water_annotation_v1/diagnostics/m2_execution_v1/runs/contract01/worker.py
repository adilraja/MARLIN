"""Actual USD product rejection/cleanup checks; no image capture."""
import asyncio
import json
import os
from pathlib import Path
import sys
import traceback
from pxr import Gf,Usd,UsdGeom,UsdRender
import omni.kit.app
import omni.usd
from omni.kit.viewport.utility import get_active_viewport_window
sys.path.insert(0,'/home/madil/kit-app-template/source/extensions/cris.madil.render_service/cris/madil/render_service')
from capture_projection import record_product_projection
OUT=Path(os.environ['ANNOTATION_EXECUTION_OUTPUT'])


async def main():
    app=omni.kit.app.get_app();ctx=omni.usd.get_context();r=dict(passed=False,captures=0,checks={})
    try:
        while not app.is_app_ready():await app.next_update_async()
        w=get_active_viewport_window()
        if w:w.destroy()
        await ctx.new_stage_async();stage=ctx.get_stage()
        cam=UsdGeom.Camera.Define(stage,'/Camera');cam.CreateHorizontalApertureAttr(30.72);cam.CreateVerticalApertureAttr(23.04)
        product=UsdRender.Product.Define(stage,'/Render/ContractProduct');product.CreateCameraRel().SetTargets(['/Camera']);product.CreateResolutionAttr(Gf.Vec2i(512,384))
        product.CreatePixelAspectRatioAttr(1);product.CreateDataWindowNDCAttr(Gf.Vec4f(0,0,1,1))
        def check(label,call):
            try:call()
            except ValueError as e:r['checks'][label]=dict(passed=True,error=str(e))
            else:raise AssertionError(label+' was incorrectly accepted')
        def record(path='/Render/ContractProduct',camera='/Camera',size=(512,384)):
            return record_product_projection(stage,path,camera,size,Usd.TimeCode.Default())
        r['valid_product']=record()
        check('missing_product',lambda:record(path='/missing'))
        check('wrong_camera',lambda:record(camera='/missing'))
        check('wrong_resolution',lambda:record(size=(1024,768)))
        product.GetPixelAspectRatioAttr().Set(1.2);check('non_square_pixels',record);product.GetPixelAspectRatioAttr().Set(1)
        product.GetDataWindowNDCAttr().Set(Gf.Vec4f(.1,0,1,1));check('cropped_product',record);product.GetDataWindowNDCAttr().Set(Gf.Vec4f(0,0,1,1))
        cam.GetHorizontalApertureAttr().Set(23.04);check('aspect_mismatch',record);cam.GetHorizontalApertureAttr().Set(30.72)
        stage.RemovePrim('/Camera');check('missing_authored_camera',record)
        stage.RemovePrim('/Render/ContractProduct')
        r['owned_product_removed']=not bool(stage.GetPrimAtPath('/Render/ContractProduct'))
        await ctx.close_stage_async();r['stage_closed']=ctx.get_stage() is None
        r['passed']=r['owned_product_removed'] and r['stage_closed'] and len(r['checks'])==7
    except BaseException:r['error']=traceback.format_exc()
    finally:
        if ctx.get_stage() is not None:await ctx.close_stage_async()
        (OUT/'result.json').write_text(json.dumps(r,indent=2)+'\n');app.post_quit(0 if r['passed'] else 1)

asyncio.ensure_future(main())

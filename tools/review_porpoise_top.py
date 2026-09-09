"""Re-render the existing static candidate without modifying its blend or USD."""
from pathlib import Path
import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parents[1] / 'assets/cetaceans/model_75a_-_harbor_porpoise/working/calibration_v1'
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'harbour_porpoise_calibration_candidate.blend'))
scene = bpy.data.scenes['StaticCalibrationCandidate']
bpy.context.window.scene = scene
points = [obj.matrix_world @ v.co for obj in scene.objects if obj.type == 'MESH' for v in obj.data.vertices]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (low + high) / 2
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.color_type = 'TEXTURE'
scene.display.shading.background_type = 'WORLD'
scene.world = bpy.data.worlds.new('ReviewWorld')
scene.world.color = (.15, .15, .15)
scene.render.resolution_x = 1200
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
bpy.ops.object.camera_add(location=center + Vector((0, 0, 5)))
camera = bpy.context.object
camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = max(high.x-low.x, (high.y-low.y)*1.5)*1.2
scene.camera = camera
scene.render.filepath = str(OUT / 'candidate_top.png')
bpy.ops.render.render(write_still=True)

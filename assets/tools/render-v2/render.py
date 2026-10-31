from pathlib import Path
import bpy, math, os
from mathutils import Vector
root=str(Path(__file__).resolve().parents[4])
out=os.path.join(root,'AURORA-Website','assets','renders-v2')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=os.path.join(root,'AURORA-Website','assets','3d','_src-orig.glb'))
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.render.film_transparent=True
scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'
scene.render.resolution_percentage=100
scene.world.color=(0.16,0.16,0.16)
scene.view_settings.view_transform='AgX'
center=Vector((0.1248,-0.0891,0.006))
def aim(obj, target): obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
def light(name,loc,power,size,target):
 d=bpy.data.lights.new(name,'AREA'); d.energy=power; d.shape='DISK'; d.size=size
 o=bpy.data.objects.new(name,d); scene.collection.objects.link(o); o.location=loc; aim(o,target)
light('large softbox',(-0.03,-0.19,0.32),3.5,0.25,center)
light('fill softbox',(0.30,-0.02,0.22),2.2,0.22,center)
light('rim softbox',(0.22,-0.27,0.16),1.2,0.18,center)
c=bpy.data.cameras.new('Product camera'); cam=bpy.data.objects.new('Product camera',c); scene.collection.objects.link(cam); scene.camera=cam
c.type='PERSP'; c.lens=52
light('underside fill',(0.09,-0.09,-0.25),3,0.25,center)
views=[('hero',(-0.13,-0.24,0.22),center,1600,1050),('top',(0.105,-0.14,0.315),center,1400,1000),('detail',(0.155,-0.20,0.15),Vector((0.15,-0.085,0.009)),1400,1000),('back',(0.12,-0.105,-0.31),center,1400,1000)]
for name,loc,target,w,h in views:
 cam.location=loc; aim(cam,target); scene.render.resolution_x=w; scene.render.resolution_y=h
 scene.render.filepath=os.path.join(out,'aurora-old-model-'+name+'-v2.png'); bpy.ops.render.render(write_still=True)

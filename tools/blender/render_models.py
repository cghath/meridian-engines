"""
Renders unit .glb models to PNGs for a side-by-side look (two views each: front three-quarter
and back three-quarter), on a neutral ground with soft light.

    blender -b --factory-startup -P tools/blender/render_models.py -- <out_dir> <model.glb> [...]
    (or <file.glb:name> to render one named object, a building, out of a file of many)

Writes <out_dir>/<name>-front.png and <name>-back.png. Uses Eevee at a low sample count, so it
stays quick; the models keep the colors they export with (team color is the default blue).
"""

import math
import os
import sys

import bpy
from mathutils import Vector

SIZE = 720


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = SIZE
    scene.render.resolution_y = SIZE
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.11, 0.15, 0.19, 1)
    bg.inputs['Strength'].default_value = 0.9
    # A key light from the front left, a cool fill from the right, a rim from behind.
    for name, rot, energy, color in (
        ('key', (math.radians(50), 0, math.radians(-35)), 3.2, (1, 0.96, 0.9)),
        ('fill', (math.radians(65), 0, math.radians(70)), 1.0, (0.75, 0.85, 1)),
        ('rim', (math.radians(60), 0, math.radians(170)), 2.2, (0.8, 0.9, 1)),
    ):
        light = bpy.data.lights.new(name, 'SUN')
        light.energy = energy
        light.color = color
        light.angle = math.radians(8)
        obj = bpy.data.objects.new(name, light)
        obj.rotation_euler = rot
        scene.collection.objects.link(obj)
    # Ground.
    bpy.ops.mesh.primitive_plane_add(size=40)
    ground = bpy.context.active_object
    mat = bpy.data.materials.new('Ground')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.21, 0.19, 0.16, 1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
    ground.data.materials.append(mat)
    cam = bpy.data.cameras.new('cam')
    cam.lens = 60
    cam_obj = bpy.data.objects.new('cam', cam)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    return scene, cam_obj


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def render(path, out_dir, only=None):
    scene, cam = setup_scene()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    if only:
        # One building out of a file of many: keep it (and its turning head), drop the rest.
        for o in [o for o in bpy.data.objects if o not in before]:
            if o.name != only and (o.parent is None or o.parent.name != only):
                bpy.data.objects.remove(o)
    # The importer adds an Icosphere to draw bones with; it isn't part of the model.
    objs = [o for o in bpy.data.objects if o not in before and not o.name.startswith('Icosphere')]
    for o in bpy.data.objects:
        if o.name.startswith('Icosphere'):
            o.hide_render = True
        if o.animation_data:
            # Stand in the Idle alone: the other clips sit on NLA tracks that would add on top.
            for t in o.animation_data.nla_tracks:
                t.mute = True
            idle = bpy.data.actions.get('Idle')
            if idle:
                o.animation_data.action = idle
    # Stand still: the first frame of the idle (or none).
    scene.frame_set(0)
    bpy.context.view_layer.update()
    lo, hi = bounds(objs)
    centre = (lo + hi) / 2
    height = hi.z - lo.z
    size = max(height, hi.x - lo.x, hi.y - lo.y)
    target = Vector((centre.x, centre.y, lo.z + height * 0.48))
    name = only or os.path.splitext(os.path.basename(path))[0]
    # The models face -Y in Blender.
    for view, angle in (('front', -28), ('back', 150)):
        a = math.radians(angle)
        dist = size * (2.3 if only else 1.85)
        cam.location = target + Vector((math.sin(a) * dist, -math.cos(a) * dist, size * 0.3))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(out_dir, f'{name}-{view}.png')
        bpy.ops.render.render(write_still=True)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == 'MESH')
    print(f'RENDERED {name}: {tris} triangles, {height:.2f} m tall')


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    out_dir, models = argv[0], argv[1:]
    os.makedirs(out_dir, exist_ok=True)
    for m in models:
        # "file.glb:name" renders one named object (a building) out of a file of many.
        path, _, only = m.partition('.glb:')
        render(path + '.glb' if only else m, out_dir, only or None)


main()

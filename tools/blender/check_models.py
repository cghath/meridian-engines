"""
Checks the exported models against the rules the game's tests apply (tests/render/modelLibrary.test.ts
and buildings.test.ts), so they can be dropped in without surprises:

    blender -b --factory-startup -P tools/blender/check_models.py -- <models_dir>

Units: Team and Glow materials present, under 12,000 triangles, posed in Idle at 0.3 s narrower
than tall (game x against game y), and each of six Run poses moving more than 5 cm from the
next and staying under 1.15x the Idle height. Buildings: each named object on its footprint,
standing on the floor, about its height, with Team and Glow faces.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

FPS = 24
RUN_FRAMES = 6


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    body = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')]
    return arm, body


def posed(arm, body, action, t):
    if arm:
        for tr in arm.animation_data.nla_tracks:
            tr.mute = True
        arm.animation_data.action = bpy.data.actions[action]
        bpy.context.scene.frame_set(int(t * FPS), subframe=(t * FPS) % 1)
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in body:
        m = o.evaluated_get(dg).to_mesh()
        pts += [o.matrix_world @ v.co for v in m.vertices]
    return pts


def extent(pts):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def check_unit(path):
    arm, body = load(path)
    problems = []
    mats = {m.name for o in body for m in o.data.materials}
    for need in ('Team', 'Glow'):
        if need not in mats:
            problems.append(f'no {need} material')
    tris = sum(len(p.vertices) - 2 for o in body for p in o.data.polygons)
    if tris >= 12000:
        problems.append(f'{tris} triangles')
    idle = posed(arm, body, 'Idle', .3)
    lo, hi = extent(idle)
    height, width = hi.z - lo.z, hi.x - lo.x
    if width >= height:
        problems.append(f'wider ({width:.2f}) than tall ({height:.2f})')
    run = bpy.data.actions['Run']
    length = (run.frame_range[1] - run.frame_range[0]) / FPS
    frames = [posed(arm, body, 'Run', length * f / RUN_FRAMES) for f in range(RUN_FRAMES)]
    # The game scales a model to its unit's height; this compares at the model's own size, so
    # it uses the same 5 cm on a model about as tall as the unit.
    for f, pts in enumerate(frames):
        nxt = frames[(f + 1) % RUN_FRAMES]
        moved = max(max(abs(a.x - b.x), abs(a.y - b.y), abs(a.z - b.z)) for a, b in zip(pts, nxt))
        rlo, rhi = extent(pts)
        if moved <= .05:
            problems.append(f'run frame {f} barely moves from the next')
        if rhi.z - lo.z > 1.15 * height:
            problems.append(f'run frame {f} too tall')
    print(f'CHECK {os.path.basename(path)}: {tris} tris, {height:.2f} m tall, {width:.2f} m wide: {"ok" if not problems else "; ".join(problems)}')
    return not problems


def check_buildings(path, defs):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    ok = True
    for kind, d in defs.items():
        objs = [o for o in bpy.data.objects if o.name == kind or o.name == f'{kind}_head']
        pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
        body = [o.matrix_world @ v.co for o in objs if o.name == kind for v in o.data.vertices]
        problems = []
        if not objs:
            problems.append('missing')
        else:
            lo, hi = extent(body)
            w, dd = d['size']
            if max(hi.x, -lo.x) > w / 2 + .15 or max(hi.y, -lo.y) > dd / 2 + .15:
                problems.append('off its footprint')
            top = max(p.z for p in pts)
            if min(p.z for p in pts) < .2:
                problems.append('below the floor')
            if not (d['height'] * .75 < top < d['height'] * 1.15):
                problems.append(f'top {top:.2f} m against height {d["height"]}')
            mats = {o.data.materials[p.material_index].name for o in objs for p in o.data.polygons}
            for need in ('Team', 'Glow'):
                if need not in mats:
                    problems.append(f'no {need}')
            if bool(d.get('weapon')) != any(o.name.endswith('_head') for o in objs):
                problems.append('head does not match weapon')
        ok &= not problems
        print(f'CHECK building {kind}: {"ok" if not problems else "; ".join(problems)}')
    return ok


def main():
    d = sys.argv[sys.argv.index('--') + 1]
    here = os.path.dirname(os.path.abspath(__file__))
    defs = json.load(open(os.path.join(here, '..', '..', 'data', 'buildings.json')))
    ok = True
    for f in sorted(os.listdir(d)):
        if f.endswith('.glb') and f != 'meridian-buildings.glb':
            ok &= check_unit(os.path.join(d, f))
    ok &= check_buildings(os.path.join(d, 'meridian-buildings.glb'), defs)
    print('ALL OK' if ok else 'PROBLEMS FOUND')


main()

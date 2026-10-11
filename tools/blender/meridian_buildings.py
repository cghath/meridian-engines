"""
Builds the Meridian Engines' buildings and exports them as one .glb, one object per building,
named as in data/buildings.json (the game's buildingModels.ts keeps each by name).

    blender -b --factory-startup -P tools/blender/meridian_buildings.py -- <out.glb>

Same rules as the game's tools/blender/buildings.py: real size in meters, centered on the
footprint, standing on FLOOR (the top of the ground slab the game draws), the front toward -Y in
Blender (+Z in the game). Every building has Team and Glow faces. The Obelisk aims, so it has a
second object, "obelisk_head", wholly above its cut (FLOOR + 1.6), turning about the middle.

The Engines build with what they are made of: hex columns of dark ore, brass fittings, molten
seams, and a core or a pit of molten ore at the heart of anything that makes something.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meridian import NAMES, TAU, box, capped, cone, hexplate, material, orb, prism, ring  # noqa: E402

FLOOR = 0.25
CUT = FLOOR + 1.6


class Building:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.head = None

    def add(self, bm, paint, head=False, top=None):
        bm.normal_update()
        for f in bm.faces:
            f.material_index = NAMES.index(top if top and f.normal.z > .9 else paint)
        if head and self.head is None:
            self.head = bmesh.new()
        tmp = bpy.data.meshes.new('tmp')
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(tmp)
        bm.free()
        (self.head if head else self.bm).from_mesh(tmp)
        bpy.data.meshes.remove(tmp)

    def col(self, x, y, h, r, base=0.0, paint='Lode', top='Rust', twist=TAU / 12):
        """A standing ore column from the floor (plus `base`), its cut top rust or a given paint."""
        self.add(capped(Vector((x, y, FLOOR + base)), Vector((x, y, FLOOR + base + h)), r, r * .96, twist=twist), paint, top=top)

    def finish(self):
        objs = [self._object(self.name, self.bm)]
        if self.head is not None:
            head = self._object(f'{self.name}_head', self.head)
            head.parent = objs[0]
            objs.append(head)
        tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
        zs = [v.co.z for o in objs for v in o.data.vertices]
        xs = [abs(v.co.x) for o in objs for v in o.data.vertices]
        ys = [abs(v.co.y) for o in objs for v in o.data.vertices]
        print(f'{self.name}: about {tris} triangles, {min(zs):.2f}-{max(zs):.2f} m, reach x {max(xs):.2f} y {max(ys):.2f}')

    @staticmethod
    def _object(name, bm):
        mesh = bpy.data.meshes.new(name)
        for n in NAMES:
            mesh.materials.append(material(n))
        bm.to_mesh(mesh)
        bm.free()
        for p in mesh.polygons:
            p.use_smooth = False
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def footing(b, r, h=.3, paint='Lode'):
    """A low hex platform, a molten seam around its foot."""
    b.add(prism(Vector((0, 0, FLOOR)), Vector((0, 0, FLOOR + h)), r, r * .94, twist=TAU / 12), paint, top='Rust')
    b.add(prism(Vector((0, 0, FLOOR + h * .45)), Vector((0, 0, FLOOR + h * .6)), r * 1.005, r * 1.0, twist=TAU / 12, caps=False), 'Molten')


def lintel(b, a, c, r=.16, paint='Lode'):
    b.add(prism(Vector(a), Vector(c), r, twist=TAU / 12), paint)


def lodehearth():
    """The Lodehearth (main): a ring of tall ore columns joined by lintels around a pit of molten
    ore, a great core hanging above the pit in a brass cradle. Ore is tipped down the front ramp."""
    b = Building('lodehearth')
    footing(b, 2.95, .35)
    base = .39
    b.add(prism(Vector((0, 0, FLOOR + base)), Vector((0, 0, FLOOR + base + .12)), 1.25, 1.1, twist=TAU / 12), 'Brass')
    b.add(prism(Vector((0, 0, FLOOR + base + .1)), Vector((0, 0, FLOOR + base + .16)), 1.05, twist=TAU / 12), 'Molten')
    heights = (4.9, 4.1, 5.4, 4.4, 5.0, 3.9)
    tops = []
    for i, h in enumerate(heights):
        a = i * TAU / 6 + TAU / 12
        x, y = math.cos(a) * 2.25, math.sin(a) * 2.25
        if y < -1.5 and abs(x) < .5:
            continue
        b.col(x, y, h, .42, base, top='Team' if i % 2 == 0 else 'Rust')
        b.add(prism(Vector((x, y, FLOOR + base + h * .45)), Vector((x, y, FLOOR + base + h * .45 + .08)), .3), 'Molten')
        for k, z in enumerate((h * .22, h * .62, h * .8)):
            b.add(hexplate(Vector((x * 1.19, y * 1.19, FLOOR + base + z)), .3 if k else .22, .06, (math.pi / 2, 0, a + math.pi / 2)), 'Brass' if k == 0 else 'Team')
        tops.append(Vector((x, y, FLOOR + base + h - .3)))
    # Lintels between neighbors at a common height, and a smaller ring of columns inside.
    for i in range(len(tops)):
        p, q = tops[i], tops[(i + 1) % len(tops)]
        z = FLOOR + base + 3.7
        lintel(b, (p.x, p.y, z), (q.x, q.y, z), .17, paint='Team' if i % 2 == 0 else 'Lode')
    for i in range(6):
        a = i * TAU / 6
        b.col(math.cos(a) * 1.35, math.sin(a) * 1.35, .5 + (i % 3) * .25, .2, base)
    # The great core: a cradle of brass on three chains of columns, the core lit inside.
    c = Vector((0, 0, FLOOR + base + 3.0))
    b.add(orb(c, .5, 2), 'Glow')
    b.add(ring(c, .66, .05, sides=12), 'Brass')
    b.add(ring(c, .66, .05, axis=(1, 0, 0), sides=12), 'Brass')
    for i in range(3):
        a = i * TAU / 3 + .3
        top = Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, FLOOR + base + 3.7))
        b.add(prism(c + (top - c).normalized() * .6, top, .045, sides=4), 'Brass')
    # The drop-off ramp at the front: a rust chute down to the pit.
    b.add(box(Vector((0, -2.35, FLOOR + .3)), (1.2, 1.1, .2), (-.25, 0, 0)), 'Rust')
    for sx in (-1, 1):
        b.add(box(Vector((sx * .62, -2.35, FLOOR + .45)), (.1, 1.1, .3), (-.25, 0, 0)), 'Brass')
    b.finish()


def plinth():
    """The Plinth (supply): a stepped base and three columns, the tallest crowned with a seed
    core, the cores a Lodehearth can keep burning."""
    b = Building('plinth')
    footing(b, 1.45, .25)
    b.add(prism(Vector((0, 0, FLOOR + .29)), Vector((0, 0, FLOOR + .55)), 1.0, .92, twist=TAU / 12), 'Lode', top='Rust')
    for x, y, h, r, t in ((0, .1, 2.0, .34, 'Team'), (-.55, -.25, 1.35, .26, 'Rust'), (.55, -.2, 1.1, .24, 'Rust')):
        b.col(x, y, h, r, .55, top=t)
        b.add(prism(Vector((x, y, FLOOR + .55 + h * .5)), Vector((x, y, FLOOR + .55 + h * .5 + .06)), r * .72), 'Molten')
    seed = Vector((0, .1, FLOOR + .55 + 2.0 + .2))
    b.add(orb(seed, .17, 2), 'Glow')
    for i in range(3):
        a = i * TAU / 3
        b.add(prism(seed + Vector((math.cos(a) * .22, math.sin(a) * .22, -.22)), seed + Vector((math.cos(a) * .16, math.sin(a) * .16, .2)), .03, sides=4), 'Brass')
    b.add(hexplate(Vector((0, -.25, FLOOR + 1.6)), .2, .05, (math.pi / 2, 0, TAU / 12)), 'Team')
    b.finish()


def kiln():
    """The Kiln (infantry): a beehive kiln of stacked hex courses with a molten mouth at the front,
    where frames are fired from ore; two chimneys and hex banners in the side's color."""
    b = Building('kiln')
    footing(b, 1.95, .25)
    z = FLOOR + .29
    for k, (r, h) in enumerate(((1.55, .7), (1.38, .65), (1.12, .6), (.82, .5), (.5, .35))):
        b.add(prism(Vector((0, .1, z)), Vector((0, .1, z + h)), r, r * .92, twist=TAU / 12 + k * .1), 'Lode' if k % 2 == 0 else 'Rust')
        b.add(prism(Vector((0, .1, z + h)), Vector((0, .1, z + h + .05)), r * .88, twist=TAU / 12), 'Brass' if k % 2 else 'Molten')
        z += h + .05
    # The mouth: a brass frame around a molten arch.
    b.add(box(Vector((0, -1.38, FLOOR + .85)), (1.0, .2, 1.15)), 'Brass')
    b.add(box(Vector((0, -1.45, FLOOR + .8)), (.75, .12, .95), taper=.7), 'Molten')
    b.add(box(Vector((0, -1.42, FLOOR + 1.52)), (1.2, .3, .2)), 'Lode')
    # Chimneys with lit tops.
    for x, h in ((-.85, 3.6), (.75, 3.2)):
        b.col(x, .75, h, .2, .3, top='Molten')
        b.add(ring(Vector((x, .75, FLOOR + .3 + h - .4)), .22, .04, sides=6), 'Brass')
    # Banners: hex tiles down the front flanks.
    for sx in (-1, 1):
        for k in range(3):
            b.add(hexplate(Vector((sx * .95, -1.12, FLOOR + .6 + k * .45)), .17, .05, (math.pi / 2, 0, TAU / 12)), 'Team' if k != 1 else 'Rust')
    b.add(orb(Vector((0, -1.35, FLOOR + 1.85)), .13, 2), 'Glow')
    b.finish()


def foundry():
    """The Foundry (heavy frames): a casting floor under a gantry of paired columns and a heavy
    lintel, a brass hook hanging over a molten channel; a frame half-cast in the pit."""
    b = Building('foundry')
    footing(b, 2.45, .25)
    floor_z = .29
    # The back wall: a row of columns of falling heights.
    for k, x in enumerate((-1.8, -1.2, -.6, 0, .6, 1.2, 1.8)):
        h = 2.6 + (1.4 - abs(x) * .6)
        b.col(x, 1.6, h, .32, floor_z, top='Team' if k % 3 == 0 else 'Rust')
    # The gantry: two pairs of pillars, a lintel across, a trolley and hook.
    for x in (-1.85, 1.85):
        for y in (-1.4, .4):
            b.col(x, y, 3.9, .26, floor_z)
        lintel(b, (x, -1.5, FLOOR + 4.2), (x, .5, FLOOR + 4.2), .2)
    lintel(b, (-1.95, -.55, FLOOR + 4.45), (1.95, -.55, FLOOR + 4.45), .28)
    b.add(hexplate(Vector((0, -.84, FLOOR + 4.45)), .32, .06, (math.pi / 2, 0, TAU / 12)), 'Team')
    for sx in (-1, 1):
        b.add(hexplate(Vector((sx * 1.2, -.84, FLOOR + 4.45)), .22, .06, (math.pi / 2, 0, TAU / 12)), 'Team')
    b.add(box(Vector((.3, -.55, FLOOR + 4.1)), (.5, .5, .3)), 'Brass')
    b.add(prism(Vector((.3, -.55, FLOOR + 3.95)), Vector((.3, -.55, FLOOR + 2.4)), .03, sides=4), 'Brass')
    b.add(cone(Vector((.3, -.55, FLOOR + 2.4)), Vector((.3, -.75, FLOOR + 2.0)), .08, sides=4), 'Brass')
    # The casting pit: molten, with a frame half-poured in it (a torso of columns and its core).
    b.add(prism(Vector((0, -.3, FLOOR + floor_z)), Vector((0, -.3, FLOOR + floor_z + .06)), 1.2, twist=TAU / 12), 'Molten')
    b.add(ring(Vector((0, -.3, FLOOR + floor_z + .06)), 1.22, .06, sides=6), 'Brass')
    for x, y, h in ((0, 0, 1.4), (-.32, -.1, 1.1), (.32, -.1, 1.2), (0, .3, 1.0)):
        b.col(x, y, h, .17, floor_z)
    b.add(orb(Vector((0, -.32, FLOOR + 1.1)), .14, 2), 'Glow')
    # A molten channel to the front edge, where frames walk out.
    b.add(box(Vector((0, -1.85, FLOOR + .32)), (.35, 1.1, .04)), 'Molten')
    b.finish()


def obelisk():
    """The Obelisk (defense): a stepped column to the cut; above it a capstone head that turns,
    a short slag mortar beside a lit core."""
    b = Building('obelisk')
    footing(b, .95, .22)
    b.add(prism(Vector((0, 0, FLOOR + .26)), Vector((0, 0, CUT - .06)), .5, .38, twist=TAU / 12), 'Lode', top='Rust')
    for z in (.55, 1.05):
        b.add(prism(Vector((0, 0, FLOOR + z)), Vector((0, 0, FLOOR + z + .06)), .44 - z * .05, twist=TAU / 12), 'Molten')
    b.add(hexplate(Vector((0, -.42, FLOOR + .8)), .18, .05, (math.pi / 2 - .12, 0, TAU / 12)), 'Team')
    for x, y, h in ((.62, .3, .7), (-.6, .35, .9), (-.3, -.65, .5)):
        b.col(x, y, h, .14, .22)
    # The head: a capstone drum, the mortar barrel forward, a core on top in a cage.
    h0 = CUT + .03
    b.add(capped(Vector((0, 0, h0)), Vector((0, 0, h0 + .55)), .42, .36, twist=TAU / 12), 'Lode', head=True)
    b.add(prism(Vector((0, 0, h0 + .2)), Vector((0, 0, h0 + .26)), .44, twist=TAU / 12), 'Team', head=True)
    b.add(prism(Vector((0, -.1, h0 + .3)), Vector((0, -.85, h0 + .6)), .15, .13, twist=TAU / 12), 'Rust', head=True)
    b.add(prism(Vector((0, -.8, h0 + .58)), Vector((0, -.9, h0 + .62)), .16, twist=TAU / 12), 'Brass', head=True)
    b.add(prism(Vector((0, -.88, h0 + .61)), Vector((0, -.9, h0 + .62)), .08), 'Molten', head=True)
    core = Vector((0, .1, h0 + .75))
    b.add(orb(core, .14, 2), 'Glow', head=True)
    b.add(ring(core, .18, .025, sides=8), 'Brass', head=True)
    for sx in (-1, 1):
        b.add(prism(Vector((sx * .2, .1, h0 + .5)), Vector((sx * .16, .1, h0 + .92)), .025, sides=4), 'Brass', head=True)
    b.finish()


def core_vault():
    """The Core Vault (heroes): a hexagonal vault of columns under a roof of hex tiles in the
    side's color; through the gaps, great cores sleep in brass cradles."""
    b = Building('coreVault')
    footing(b, 1.95, .28)
    base = .32
    for i in range(6):
        a = i * TAU / 6
        x, y = math.cos(a) * 1.5, math.sin(a) * 1.5
        b.col(x, y, 3.2, .3, base, top='Brass')
        b.add(prism(Vector((x, y, FLOOR + base + 1.6)), Vector((x, y, FLOOR + base + 1.66)), .22), 'Molten')
    # The roof: a ring beam and two tiers of hex tiles, a spire with a core-seed.
    z = FLOOR + base + 3.2
    b.add(prism(Vector((0, 0, z)), Vector((0, 0, z + .22)), 1.8, 1.7, twist=0), 'Lode')
    b.add(prism(Vector((0, 0, z + .22)), Vector((0, 0, z + .5)), 1.4, 1.0, twist=TAU / 12), 'Team')
    b.add(prism(Vector((0, 0, z + .5)), Vector((0, 0, z + .75)), .9, .5, twist=0), 'Rust')
    b.add(cone(Vector((0, 0, z + .75)), Vector((0, 0, z + 1.1)), .18), 'Brass')
    # Three cradles inside, a core in each: the heroes waiting.
    for i in range(3):
        a = i * TAU / 3 + TAU / 12
        p = Vector((math.cos(a) * .55, math.sin(a) * .55, FLOOR + base + 1.2 + i * .25))
        b.add(prism(Vector((p.x, p.y, FLOOR + base)), p - Vector((0, 0, .25)), .08, sides=6), 'Brass')
        b.add(orb(p, .24, 2), 'Glow')
        b.add(ring(p, .3, .03, sides=10), 'Brass')
    b.add(prism(Vector((0, 0, FLOOR + base)), Vector((0, 0, FLOOR + base + .06)), 1.15, twist=TAU / 12), 'Molten')
    b.finish()


BUILDINGS = [lodehearth, plinth, kiln, foundry, obelisk, core_vault]


def main():
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for build in BUILDINGS:
        build()
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_animations=False, export_yup=True)


if __name__ == '__main__':
    main()

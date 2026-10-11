"""
Builds the Meridian Engines' units and heroes in Blender and exports each as a .glb for the game.

    blender -b --factory-startup -P tools/blender/meridian.py -- <kind> <out.glb>
    blender -b --factory-startup -P tools/blender/meridian.py -- all <out_dir>

The Engines are frames of hexagonal ore columns held together by molten seams, each with a caged
core (the mind) in its chest. Their limbs are stacks of column segments floating a hand's width
apart, the gaps lit orange, so a unit reads at RTS zoom as a dark faceted silhouette with a
bright heart and glowing joints, in a different language from the Choir's grown bone and the
Directorate's plated metal.

Conventions match the game's other Blender models: Z up, the front toward -Y (the exporter turns
that into the game's Y up, +Z front); materials named "Team" and "Glow" take the owner's color and
the glow color, the rest keep their own; animations "Idle" and "Run" as NLA tracks. Every part is
rigid and follows one bone, which is how machines move.
"""

import math
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


def srgb(hex_):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin((hex_ >> 16) & 255), lin((hex_ >> 8) & 255), lin(hex_ & 255), 1.0)


PAINTS = {
    'Lode': srgb(0x3A3431),     # the dark iron-ore columns
    'Rust': srgb(0x7E4A30),     # oxidized faces and plates
    'Brass': srgb(0xB88E52),    # polished ore: edges, fittings, cages
    'Slag': srgb(0x141316),     # black glass: bores, visors, pits
    'Molten': srgb(0xFF7A1F),   # the seams; keeps its orange whatever the side
    'Team': srgb(0x5A8CC8),
    'Glow': srgb(0xFFD08A),     # the core: the game paints it in the glow color
}
NAMES = list(PAINTS)
TAU = 2 * math.pi


def material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = PAINTS[name]
    if mat.node_tree:
        bsdf = mat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = PAINTS[name]
        bsdf.inputs['Roughness'].default_value = .35 if name in ('Brass', 'Slag') else .8
        if name in ('Molten', 'Glow'):
            bsdf.inputs['Emission Color'].default_value = PAINTS[name]
            bsdf.inputs['Emission Strength'].default_value = 2.0 if name == 'Molten' else 3.0
    return mat


# --- Shapes (each returns a bmesh) ---------------------------------------------------------

def _frame(a, b):
    """A matrix whose Z runs from a to b, origin at a."""
    a, b = Vector(a), Vector(b)
    d = b - a
    q = Vector((0, 0, 1)).rotation_difference(d.normalized()) if d.length > 1e-6 else Euler().to_quaternion()
    return Matrix.Translation(a) @ q.to_matrix().to_4x4(), d.length


def prism(a, b, r, rb=None, sides=6, twist=0.0, caps=True, squash=1.0):
    """A column from a to b: hexagonal by default, tapering from r to rb."""
    rb = r if rb is None else rb
    m, length = _frame(a, b)
    bm = bmesh.new()
    rings = []
    for z, rr in ((0, r), (length, rb)):
        rings.append([bm.verts.new(m @ Vector((math.cos(twist + i * TAU / sides) * rr, math.sin(twist + i * TAU / sides) * rr * squash, z))) for i in range(sides)])
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[1])
    return bm


def capped(a, b, r, rb=None, twist=0.0, bevel=.18):
    """A hex column with a chamfered top: the cap is a smaller hexagon raised on a bevel."""
    rb = r if rb is None else rb
    m, length = _frame(a, b)
    bm = bmesh.new()
    rings = []
    for z, rr in ((0, r), (length - bevel * rb, rb), (length, rb * .62)):
        rings.append([bm.verts.new(m @ Vector((math.cos(twist + i * TAU / 6) * rr, math.sin(twist + i * TAU / 6) * rr, z))) for i in range(6)])
    for k in range(2):
        for i in range(6):
            j = (i + 1) % 6
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[2])
    return bm


def box(at, size, rot=(0, 0, 0), taper=1.0):
    """A block centered at `at`, size (x, y, z), its top scaled by `taper`."""
    bm = bmesh.new()
    sx, sy, sz = (s / 2 for s in size)
    m = Matrix.Translation(Vector(at)) @ Euler(rot, 'XYZ').to_matrix().to_4x4()
    vs = []
    for z in (-sz, sz):
        k = taper if z > 0 else 1
        for x, y in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
            vs.append(bm.verts.new(m @ Vector((x * k, y * k, z))))
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in f])
    return bm


def orb(at, r, subdiv=1):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    bmesh.ops.translate(bm, vec=Vector(at), verts=bm.verts)
    return bm


def cone(a, b, r, sides=6):
    m, length = _frame(a, b)
    bm = bmesh.new()
    ring = [bm.verts.new(m @ Vector((math.cos(i * TAU / sides) * r, math.sin(i * TAU / sides) * r, 0))) for i in range(sides)]
    tip = bm.verts.new(m @ Vector((0, 0, length)))
    for i in range(sides):
        bm.faces.new((ring[(i + 1) % sides], ring[i], tip))
    bm.faces.new(ring)
    return bm


def hexplate(at, r, depth, rot=(0, 0, 0)):
    """A flat hexagonal tile, the Engines' armor."""
    m = Matrix.Translation(Vector(at)) @ Euler(rot, 'XYZ').to_matrix().to_4x4()
    return prism(m @ Vector((0, 0, -depth / 2)), m @ Vector((0, 0, depth / 2)), r, r * .82)


def ring(center, R, r, axis=(0, 0, 1), sides=12, profile=4):
    """A ring of R about `axis` through `center`, its section a small polygon."""
    bm = bmesh.new()
    m = Matrix.Translation(Vector(center)) @ Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    loops = []
    for i in range(sides):
        a = i * TAU / sides
        out = Vector((math.cos(a), math.sin(a), 0))
        loops.append([bm.verts.new(m @ (out * (R + math.cos(k * TAU / profile) * r) + Vector((0, 0, math.sin(k * TAU / profile) * r)))) for k in range(profile)])
    for i in range(sides):
        j = (i + 1) % sides
        for k in range(profile):
            l = (k + 1) % profile
            bm.faces.new((loops[i][k], loops[j][k], loops[j][l], loops[i][l]))
    return bm


# --- The rig ----------------------------------------------------------------------------------

class Rig:
    """A model in the making: bones, and the rigid parts that follow them."""

    def __init__(self):
        self.bones = {}  # name -> (head, tail, parent)
        self.parts = []  # (bmesh, paint, bone)

    def bone(self, name, head, tail, parent=None):
        self.bones[name] = (Vector(head), Vector(tail), parent)

    def add(self, bm, paint, bone):
        self.parts.append((bm, paint, bone))

    def stack(self, a, b, r, bone, n=3, gap=.045, rb=None, paint='Lode', seam='Molten', twist=0.0, cap=False):
        """A limb of n column segments from a to b, the gaps lit by molten discs."""
        a, b = Vector(a), Vector(b)
        rb = r if rb is None else rb
        d = b - a
        length = d.length
        seg = (length - gap * (n - 1)) / n
        u = d.normalized()
        for i in range(n):
            s0 = a + u * (i * (seg + gap))
            s1 = s0 + u * seg
            r0 = r + (rb - r) * (i * (seg + gap)) / length
            r1 = r + (rb - r) * (i * (seg + gap) + seg) / length
            last = cap and i == n - 1
            self.add((capped if last else prism)(s0, s1, r0, r1, twist=twist + i * .18), paint, bone)
            if seam and i < n - 1:
                rr = min(r0, r1) * .62
                self.add(prism(s1 - u * .004, s1 + u * (gap + .004), rr, rr, twist=twist), seam, bone)

    def core(self, at, r, bone, cage='Brass'):
        """The caged core: a bright orb inside six bars and two rings."""
        at = Vector(at)
        self.add(orb(at, r, 2), 'Glow', bone)
        R = r * 1.3
        for i in range(6):
            a = i * TAU / 6 + TAU / 12
            o = Vector((math.cos(a) * R, math.sin(a) * R, 0))
            self.add(prism(at + o - Vector((0, 0, r * 1.15)), at + o + Vector((0, 0, r * 1.15)), r * .09, sides=4), cage, bone)
        for z in (-1.15, 1.15):
            self.add(ring(at + Vector((0, 0, z * r)), R, r * .1, sides=12), cage, bone)

    def bundle(self, center, height, r, bone, count=7, paint='Lode', tops=(.0, .12, -.08, .2, .05, -.12, .15), team_tops=()):
        """A torso of bundled columns: one in the middle and six around it, each a different height."""
        c = Vector(center)
        spots = [(0, 0)] + [(math.cos(i * TAU / 6) * r * 1.73, math.sin(i * TAU / 6) * r * 1.73) for i in range(count - 1)]
        for k, (x, y) in enumerate(spots):
            top = height / 2 + tops[k % len(tops)] * height
            bot = -height / 2 + abs(tops[(k + 3) % len(tops)]) * height * .5
            p = 'Team' if k in team_tops else paint
            self.add(capped(c + Vector((x, y, bot)), c + Vector((x, y, top)), r * .98, twist=TAU / 12), p, bone)


# --- Shared pieces ---------------------------------------------------------------------------

def visor_head(rig, at, r, bone, h=None, slit='Molten', crest=0):
    """A capstone head: a short hex column, a molten slit across the front, a chamfered top."""
    at = Vector(at)
    h = h or r * 1.3
    rig.add(capped(at, at + Vector((0, 0, h)), r, r * .9, twist=TAU / 12), 'Lode', bone)
    rig.add(box(at + Vector((0, -r * .86, h * .52)), (r * 1.25, r * .12, r * .2)), slit, bone)
    for i in range(crest):
        x = (i - (crest - 1) / 2) * r * .5
        rig.add(cone(at + Vector((x, r * .1, h * .9)), at + Vector((x * 1.3, r * .35, h * 1.6 - abs(x) * .6)), r * .16), 'Brass', bone)


def clamp_hand(rig, wrist, bone, r, down=(0, 0, -1), fingers=3):
    """Three brass prongs: a hand that grips like tongs."""
    wrist, d = Vector(wrist), Vector(down).normalized()
    side = d.cross(Vector((0, 1, 0)) if abs(d.y) < .9 else Vector((1, 0, 0))).normalized()
    other = d.cross(side).normalized()
    rig.add(prism(wrist - d * r * .2, wrist + d * r * .5, r * 1.05, r * .9), 'Brass', bone)
    for i in range(fingers):
        a = i * TAU / fingers
        o = (side * math.cos(a) + other * math.sin(a)) * r * .7
        k = wrist + d * r * .5 + o
        rig.add(prism(k, k + d * r * 1.1 + o * .35, r * .22, r * .14, sides=4), 'Lode', bone)
        rig.add(cone(k + d * r * 1.1 + o * .35, k + d * r * 1.5 - o * .3, r * .14, sides=4), 'Brass', bone)


def foot(rig, ankle, bone, r, paint='Lode'):
    """A broad hex foot, a molten seam above it."""
    ankle = Vector(ankle)
    rig.add(prism(Vector((ankle.x, ankle.y - r * .25, 0)), Vector((ankle.x, ankle.y - r * .25, r * .55)), r * 1.25, r * 1.05, twist=TAU / 12), paint, bone)
    rig.add(prism(Vector((ankle.x, ankle.y - r * .25, r * .55)), Vector((ankle.x, ankle.y - r * .25, r * .62)), r * .6), 'Molten', bone)
    for t in (-.5, 0, .5):
        tip = Vector((ankle.x + math.sin(t) * r * 1.9, ankle.y - r * .25 - math.cos(t) * r * 1.9, .02))
        rig.add(cone(Vector((ankle.x + math.sin(t) * r * .8, ankle.y - r * .25 - math.cos(t) * r * .8, r * .2)), tip, r * .32, sides=4), 'Brass', bone)


def biped(rig, hip=1.0, chest=1.6, width=.3, leg=.11, arm=.09, stance=.17, arms_down=True, right=None, left=None):
    """The common Engine frame: hips, a chest block, legs of three floating segments, arms of
    two. Returns the joint positions. `right`/`left` override where the hand goes."""
    j = {'pelvis': Vector((0, 0, hip)), 'chest': Vector((0, 0, chest)), 'neck': Vector((0, -.02, chest + .32))}
    rig.bone('hips', (0, 0, hip - .1), (0, 0, hip + .1))
    rig.bone('spine', (0, 0, hip + .1), (0, 0, chest + .25), 'hips')
    rig.bone('head', j['neck'], j['neck'] + Vector((0, 0, .3)), 'spine')
    for sign, side in ((1, 'L'), (-1, 'R')):
        hp = Vector((stance * sign, 0, hip - .05))
        kn = Vector((stance * sign * 1.05, -.1, hip * .52))
        an = Vector((stance * sign * 1.08, .04, leg * .7))
        sh = Vector(((width + arm * .5) * sign, .0, chest + .12))
        el = Vector(((width + arm * .9) * sign, .06, chest - .32))
        wr = Vector(((width + arm * .7) * sign, -.06, chest - .72))
        hand = right if side == 'R' else left
        if hand:
            el, wr = hand
        j.update({f'hip.{side}': hp, f'knee.{side}': kn, f'ankle.{side}': an, f'shoulder.{side}': sh, f'elbow.{side}': Vector(el), f'wrist.{side}': Vector(wr)})
        rig.bone(f'thigh.{side}', hp, kn, 'hips')
        rig.bone(f'shin.{side}', kn, an, f'thigh.{side}')
        rig.bone(f'upperarm.{side}', sh, el, 'spine')
        rig.bone(f'forearm.{side}', el, wr, f'upperarm.{side}')
        rig.stack(hp, kn, leg * 1.15, f'thigh.{side}', n=2, rb=leg)
        rig.stack(kn, an + Vector((0, 0, leg * .5)), leg, f'shin.{side}', n=2, rb=leg * .85)
        rig.add(orb(kn, leg * .78, 1), 'Brass', f'thigh.{side}')
        foot(rig, an, f'shin.{side}', leg * .9)
        rig.add(orb(sh, arm * 1.25, 1), 'Lode', f'upperarm.{side}')
        rig.stack(sh, el, arm * 1.05, f'upperarm.{side}', n=2, rb=arm)
        rig.add(orb(Vector(el), arm * .75, 1), 'Brass', f'forearm.{side}')
        rig.stack(el, wr, arm, f'forearm.{side}', n=2, rb=arm * .85)
    # The waist: a short stack from the hips up into the chest.
    rig.stack(Vector((0, 0, hip + .08)), Vector((0, 0, chest - .1)), leg * 1.05, 'spine', n=2, rb=leg * 1.2, twist=TAU / 12)
    # A hip girdle of hex columns lying sideways.
    rig.add(prism(Vector((-stance - .06, 0, hip)), Vector((stance + .06, 0, hip)), .12, twist=TAU / 12), 'Lode', 'hips')
    rig.add(prism(Vector((0, 0, hip + .06)), Vector((0, 0, hip + .18)), .07), 'Molten', 'hips')
    return j


def pauldron(rig, at, sign, r, bone='spine', paint='Team', tilt=.45):
    """A hexagonal shoulder plate in the side's color, brass-rimmed."""
    at = Vector(at)
    rig.add(hexplate(at, r, r * .28, (0, tilt * sign, 0)), paint, bone)
    rig.add(hexplate(at + Vector((sign * r * .12, 0, r * .16)), r * .55, r * .2, (0, tilt * sign, 0)), 'Brass', bone)


def tabard(rig, top, w, length, bone='hips', paint='Team', front=True):
    """Hanging hex tiles in the side's color: two rows of scale armor."""
    top = Vector(top)
    y = -1 if front else 1
    for row in range(2):
        for k in range(2 + row):
            x = (k - (1 + row) / 2) * w * .55
            at = top + Vector((x, y * (.01 + row * .012), -row * length * .5 - length * .25))
            rig.add(hexplate(at, w * .34, .03, (math.pi / 2, 0, TAU / 12)), paint if (k + row) % 2 == 0 else 'Rust', bone)


# --- Units ----------------------------------------------------------------------------------

def delver():
    """The Delver (worker): a squat hexagonal hopper on six short legs, a pick-drill in front and a
    bin of ore on its back, its core peeking out above the drill."""
    rig = Rig()
    rig.bone('body', (0, .1, .55), (0, -.3, .6))
    body_at = Vector((0, 0, .62))
    rig.add(capped(body_at - Vector((0, 0, .24)), body_at + Vector((0, 0, .22)), .46, .44, twist=TAU / 12), 'Lode', 'body')
    rig.add(prism(body_at - Vector((0, 0, .26)), body_at - Vector((0, 0, .2)), .36), 'Molten', 'body')
    # Hex plating in the side's color around the hopper's flanks.
    for i in range(6):
        a = i * TAU / 6
        if i in (1, 2):
            continue
        rig.add(hexplate(body_at + Vector((math.cos(a) * .4, math.sin(a) * .4, 0)), .13, .03, (math.pi / 2, 0, a + math.pi / 2)), 'Team', 'body')
    # The ore bin: brass-rimmed, heaped with lit ore.
    bin_at = body_at + Vector((0, .12, .2))
    rig.add(prism(bin_at, bin_at + Vector((0, 0, .2)), .3, .34, twist=TAU / 12), 'Rust', 'body')
    rig.add(ring(bin_at + Vector((0, 0, .2)), .33, .025, sides=6), 'Brass', 'body')
    for dx, dy, h in ((-.1, .02, .22), (.08, -.05, .3), (0, .1, .2), (.12, .1, .14), (-.06, -.1, .16)):
        rig.add(cone(bin_at + Vector((dx, dy, .14)), bin_at + Vector((dx * 1.1, dy * 1.1, .2 + h)), .06, sides=5), 'Molten' if h > .12 else 'Rust', 'body')
    # The core behind a brass grille at the front.
    rig.core(body_at + Vector((0, -.38, .12)), .08, 'body')
    # The pick-drill: a tapering hex shaft ending in a brass point.
    rig.bone('drill', body_at + Vector((0, -.4, -.05)), body_at + Vector((0, -.8, -.25)), 'body')
    d0, d1 = body_at + Vector((0, -.4, -.05)), body_at + Vector((0, -.86, -.3))
    rig.add(prism(d0, d1, .07, .04, twist=.3), 'Lode', 'drill')
    rig.add(cone(d1, d1 + (d1 - d0).normalized() * .2, .05), 'Brass', 'drill')
    for t in (.35, .65):
        p = d0.lerp(d1, t)
        rig.add(ring(p, .075, .015, axis=d1 - d0, sides=6), 'Brass', 'drill')
    # Six short legs, each a hip column and a brass-tipped foot.
    for k, (sign, y) in enumerate(((1, -.25), (1, .05), (1, .32), (-1, -.25), (-1, .05), (-1, .32))):
        name = f'leg{k}'
        hip = Vector((sign * .34, y, .5))
        knee = Vector((sign * .47, y, .46))
        tip = Vector((sign * .49, y * 1.1, .0))
        rig.bone(name, hip, knee, 'body')
        rig.add(prism(hip, knee, .075, .07), 'Lode', name)
        rig.add(orb(knee, .08, 1), 'Brass', name)
        rig.add(prism(knee, tip + Vector((0, 0, .1)), .07, .05), 'Lode', name)
        rig.add(cone(tip + Vector((0, 0, .1)), tip, .05, sides=4), 'Brass', name)
    return rig


def hewn():
    """The Hewn (line infantry): a stocky frame of bundled columns, its right forearm a slag
    launcher (a hex barrel with a lit bore) fed by a hopper on its back."""
    rig = Rig()
    j = biped(rig, hip=.98, chest=1.55, width=.29, leg=.12, arm=.1,
              right=((-.4, -.12, 1.33), (-.38, -.55, 1.3)))
    rig.bundle(j['chest'] + Vector((0, 0, -.02)), .62, .105, 'spine', team_tops=(2, 5))
    rig.core(j['chest'] + Vector((0, -.25, .02)), .085, 'spine')
    visor_head(rig, j['neck'], .13, 'head')
    for sign in (-1, 1):
        pauldron(rig, j[f'shoulder.{"L" if sign > 0 else "R"}'] + Vector((sign * .04, 0, .1)), sign, .16)
    tabard(rig, j['pelvis'] + Vector((0, -.14, -.02)), .3, .34)
    # The slag launcher: a hex barrel over the forearm, a brass muzzle, a lit bore.
    w, e = j['wrist.R'], j['elbow.R']
    d = (w - e).normalized()
    rig.add(prism(e + Vector((0, 0, .1)), w + d * .25 + Vector((0, 0, .1)), .085, .075, twist=TAU / 12), 'Rust', 'forearm.R')
    mz = w + d * .25 + Vector((0, 0, .1))
    rig.add(prism(mz, mz + d * .07, .095, .095, twist=TAU / 12), 'Brass', 'forearm.R')
    rig.add(prism(mz + d * .05, mz + d * .075, .05, .05), 'Molten', 'forearm.R')
    rig.add(ring(e.lerp(w, .5) + Vector((0, 0, .1)), .095, .018, axis=d, sides=6), 'Brass', 'forearm.R')
    clamp_hand(rig, j['wrist.L'], 'forearm.L', .07)
    # The hopper of slag on its back, fed down a brass pipe to the launcher.
    hop = j['chest'] + Vector((0, .3, .12))
    rig.add(prism(hop - Vector((0, 0, .22)), hop + Vector((0, 0, .18)), .15, .19, twist=TAU / 12), 'Lode', 'spine')
    rig.add(prism(hop + Vector((0, 0, .18)), hop + Vector((0, 0, .21)), .15), 'Molten', 'spine')
    rig.add(prism(hop + Vector((-.15, 0, -.1)), j['shoulder.R'] + Vector((-.05, .1, -.05)), .025, sides=5), 'Brass', 'spine')
    return rig


def spindle():
    """The Spindle (scout): a great rolling wheel of hex segments around a hub that holds its
    core, a slim fin of columns above it in the side's color. It runs by rolling."""
    rig = Rig()
    R = .82
    hub = Vector((0, 0, R + .02))
    rig.bone('frame', hub - Vector((0, 0, .3)), hub + Vector((0, 0, .3)))
    rig.bone('wheel', hub + Vector((-.2, 0, 0)), hub + Vector((.2, 0, 0)), 'frame')
    # The rim: twelve hex blocks around, molten seams between.
    n = 12
    for i in range(n):
        a0, a1 = (i + .08) * TAU / n, (i + .92) * TAU / n
        p0 = hub + Vector((0, math.cos(a0) * R, math.sin(a0) * R))
        p1 = hub + Vector((0, math.cos(a1) * R, math.sin(a1) * R))
        rig.add(prism(p0, p1, .12, twist=TAU / 12), 'Team' if i % 3 == 0 else 'Lode', 'wheel')
        am = (i + 1) * TAU / n
        pm = hub + Vector((0, math.cos(am) * R, math.sin(am) * R))
        rig.add(orb(pm, .07, 1), 'Molten', 'wheel')
        # Spokes on every other block.
        if i % 2 == 0:
            mid = (a0 + a1) / 2
            rig.add(prism(hub, hub + Vector((0, math.cos(mid) * (R - .1), math.sin(mid) * (R - .1))), .03, sides=4), 'Brass', 'wheel')
    # The hub: a short hex drum with the core in it, brass caps on both faces.
    rig.add(prism(hub - Vector((.18, 0, 0)), hub + Vector((.18, 0, 0)), .2, twist=TAU / 12), 'Lode', 'wheel')
    for sx in (-1, 1):
        rig.add(prism(hub + Vector((sx * .18, 0, 0)), hub + Vector((sx * .22, 0, 0)), .14), 'Brass', 'wheel')
        rig.add(orb(hub + Vector((sx * .23, 0, 0)), .08, 2), 'Glow', 'wheel')
    # The fork: two struts from the axle up to a small fin of three columns that stays upright.
    top = hub + Vector((0, .1, R + .25))
    for sx in (-1, 1):
        rig.add(prism(hub + Vector((sx * .27, 0, 0)), top + Vector((sx * .12, 0, -.05)), .04, .035, sides=4), 'Brass', 'frame')
    for k, (dy, h) in enumerate(((.0, .55), (.13, .42), (-.12, .3))):
        b = top + Vector((0, dy, -.1))
        rig.add(capped(b, b + Vector((0, dy * .8 + .08, h)), .065, .055, twist=TAU / 12), 'Team' if k == 0 else 'Lode', 'frame')
    rig.add(prism(top + Vector((-.14, 0, -.06)), top + Vector((.14, 0, -.06)), .05, twist=TAU / 12), 'Lode', 'frame')
    rig.add(box(top + Vector((0, -.07, .08)), (.12, .03, .03)), 'Molten', 'frame')
    return rig


def cairn():
    """The Cairn (heavy): a huge stooped walker of stacked columns. Its arms are pillars that
    reach the ground, its fists hex boulders; a small capstone head sits low between broad
    shoulders, plated in the side's color."""
    rig = Rig()
    j = biped(rig, hip=1.12, chest=2.0, width=.55, leg=.19, arm=.2, stance=.3,
              right=((-.9, -.25, 1.45), (-.88, -.45, .55)), left=((.9, -.25, 1.45), (.88, -.45, .55)))
    rig.bundle(j['chest'] + Vector((0, .02, -.08)), .95, .18, 'spine', tops=(.12, .2, .05, -.1, .0, .15, .25), team_tops=(1, 6))
    rig.core(j['chest'] + Vector((0, -.42, -.1)), .13, 'spine')
    # A low head, half sunk between the shoulders.
    visor_head(rig, j['neck'] + Vector((0, -.18, -.12)), .16, 'head', h=.2)
    for sign, side in ((1, 'L'), (-1, 'R')):
        sh = j[f'shoulder.{side}']
        # Shoulders: a cluster of three columns rising, the middle one in the side's color.
        for k, (dx, dy, h) in enumerate(((0, 0, .48), (-.13 * sign, .14, .35), (.1 * sign, -.15, .3))):
            b = sh + Vector((dx, dy, -.1))
            rig.add(capped(b, b + Vector((dx * .3, dy * .2, h)), .13, .12, twist=TAU / 12), 'Team' if k == 0 else 'Lode', 'spine')
        # Fists: a hex boulder, brass knuckles.
        w = j[f'wrist.{side}']
        rig.add(capped(w + Vector((0, 0, .05)), w - Vector((0, 0, .38)), .24, .26, twist=TAU / 12), 'Lode', f'forearm.{side}')
        rig.add(prism(w + Vector((0, 0, .09)), w + Vector((0, 0, .05)), .18), 'Molten', f'forearm.{side}')
        for t in (-.6, 0, .6):
            k = w + Vector((math.sin(t) * .2, -.2, -.25))
            rig.add(cone(k, k + Vector((math.sin(t) * .05, -.12, -.03)), .06, sides=4), 'Brass', f'forearm.{side}')
        rig.add(hexplate(j[f'elbow.{side}'] + Vector((sign * .12, .04, 0)), .2, .05, (0, math.pi / 2, 0)), 'Team', f'forearm.{side}')
    tabard(rig, j['pelvis'] + Vector((0, -.2, 0)), .5, .5)
    return rig


def crucible():
    """The Crucible (artillery): a low four-legged frame carrying a great brass-banded crucible of
    molten ore, its spout raised forward to lob slag across the field."""
    rig = Rig()
    rig.bone('body', (0, .5, 1.0), (0, -.5, 1.0))
    rig.bone('bowl', (0, 0, 1.25), (0, 0, 1.9), 'body')
    rig.add(prism(Vector((0, .6, 1.0)), Vector((0, -.6, 1.0)), .32, .3, twist=TAU / 12, squash=.8), 'Lode', 'body')
    for y in (-.35, .35):
        rig.add(prism(Vector((0, y - .03, 1.0)), Vector((0, y + .03, 1.0)), .3, squash=.85), 'Molten', 'body')
    for sign in (-1, 1):
        for y in (-.2, .3):
            rig.add(hexplate(Vector((sign * .3, y, 1.06)), .17, .04, (0, math.pi / 2 * sign, 0)), 'Team', 'body')
    rig.core(Vector((0, -.66, 1.03)), .1, 'body')
    visor_head(rig, Vector((0, -.78, 1.05)), .1, 'body', h=.14)
    # The crucible: a tapered hex bowl, brass bands, a spout forward, a molten surface.
    base = Vector((0, .05, 1.25))
    rig.add(prism(base, base + Vector((0, 0, .55)), .32, .52, twist=TAU / 12), 'Rust', 'bowl')
    for z, r in ((.1, .36), (.42, .49)):
        rig.add(ring(base + Vector((0, 0, z)), r, .03, sides=6), 'Brass', 'bowl')
    rig.add(prism(base + Vector((0, 0, .5)), base + Vector((0, 0, .54)), .47, twist=TAU / 12), 'Molten', 'bowl')
    rig.add(prism(base + Vector((0, -.45, .48)), base + Vector((0, -.75, .62)), .1, .07, sides=4), 'Rust', 'bowl')
    rig.add(prism(base + Vector((0, -.6, .57)), base + Vector((0, -.76, .64)), .045, .04, sides=4), 'Molten', 'bowl')
    for sign in (-1, 1):
        rig.add(prism(base + Vector((sign * .5, 0, .3)), base + Vector((sign * .32, 0, -.15)), .04, sides=4), 'Brass', 'body')
    # Four legs: column thighs angled out, straight shins, broad feet.
    for k, (sign, y) in enumerate(((1, -.42), (-1, -.42), (1, .45), (-1, .45))):
        name = f'leg{k}'
        hip = Vector((sign * .3, y, .95))
        knee = Vector((sign * .62, y - .05, .78))
        an = Vector((sign * .66, y, .1))
        rig.bone(name, hip, an, 'body')
        rig.stack(hip, knee, .1, name, n=1)
        rig.add(orb(knee, .1, 1), 'Brass', name)
        rig.stack(knee, an + Vector((0, 0, .08)), .095, name, n=2, rb=.085)
        foot(rig, an + Vector((0, .04, 0)), name, .1)
    return rig


def annealer():
    """The Annealer (support): a slender frame with long tong arms and a quench tank on its back;
    it heats cracked frames to glowing and sets them whole. A hex lantern hangs from its tongs."""
    rig = Rig()
    j = biped(rig, hip=.98, chest=1.58, width=.24, leg=.09, arm=.07,
              right=((-.36, -.1, 1.25), (-.3, -.5, 1.1)), left=((.36, -.1, 1.25), (.3, -.5, 1.1)))
    rig.bundle(j['chest'], .55, .085, 'spine', count=7, team_tops=(1, 4))
    rig.core(j['chest'] + Vector((0, -.21, .02)), .075, 'spine')
    visor_head(rig, j['neck'], .11, 'head', h=.2, crest=2)
    tabard(rig, j['pelvis'] + Vector((0, -.12, -.02)), .26, .45)
    tabard(rig, j['pelvis'] + Vector((0, .12, -.02)), .26, .45, front=False)
    # Quench tank: a brass-banded hex drum, a lit window down its side, two vent pipes.
    t = j['chest'] + Vector((0, .3, .0))
    rig.add(prism(t - Vector((0, 0, .32)), t + Vector((0, 0, .3)), .17, .17, twist=TAU / 12), 'Rust', 'spine')
    for z in (-.25, .0, .23):
        rig.add(ring(t + Vector((0, 0, z)), .18, .02, sides=6), 'Brass', 'spine')
    rig.add(box(t + Vector((0, .16, 0)), (.07, .04, .4)), 'Glow', 'spine')
    for sx in (-.08, .08):
        rig.add(prism(t + Vector((sx, 0, .3)), t + Vector((sx * 1.4, .05, .62)), .03, .025, sides=5), 'Brass', 'spine')
        rig.add(orb(t + Vector((sx * 1.4, .05, .64)), .03, 1), 'Molten', 'spine')
    # Tongs on both arms, and the lantern held between them.
    for side in ('L', 'R'):
        clamp_hand(rig, j[f'wrist.{side}'], f'forearm.{side}', .055, down=(0, -.6, -1))
    lamp = Vector((0, -.62, .92))
    rig.add(prism(lamp + Vector((0, 0, .17)), lamp + Vector((0, 0, .22)), .02, sides=4), 'Brass', 'forearm.R')
    rig.add(capped(lamp - Vector((0, 0, .12)), lamp + Vector((0, 0, .14)), .09, .09, twist=TAU / 12), 'Brass', 'forearm.R')
    rig.add(prism(lamp - Vector((0, 0, .09)), lamp + Vector((0, 0, .09)), .095, twist=0), 'Molten', 'forearm.R')
    return rig


def lodestone():
    """The Lodestone (anti-link): a heavy, slow frame bearing a ring of iron hexes that float in
    orbit around it. The field it throws grounds enemy links: no possession near it."""
    rig = Rig()
    j = biped(rig, hip=.9, chest=1.45, width=.3, leg=.12, arm=.1,
              right=((-.42, -.08, 1.15), (-.36, -.42, 1.25)), left=((.42, -.08, 1.15), (.36, -.42, 1.25)))
    rig.bundle(j['chest'], .55, .11, 'spine', team_tops=(3,))
    rig.core(j['chest'] + Vector((0, -.26, 0)), .09, 'spine')
    visor_head(rig, j['neck'], .12, 'head', h=.14, slit='Glow')
    tabard(rig, j['pelvis'] + Vector((0, -.15, -.02)), .3, .32)
    # Hands held forward, palms together, around a lodestone: a black hex lump in a brass ring.
    stone = Vector((0, -.55, 1.27))
    rig.add(capped(stone - Vector((0, 0, .12)), stone + Vector((0, 0, .1)), .1, .09, twist=.4), 'Slag', 'spine')
    rig.add(ring(stone, .14, .015, axis=(0, 1, 0), sides=6), 'Brass', 'spine')
    for side in ('L', 'R'):
        clamp_hand(rig, j[f'wrist.{side}'], f'forearm.{side}', .065, down=(0, -1, 0))
    # The orbiting ring: nine iron hexes on a tilted ring, every third in the side's color, with a
    # faint ring of light where the field runs.
    rig.bone('orbit', (0, 0, 1.6), (0, 0, 2.0), 'spine')
    c = Vector((0, .02, 1.98))
    R = .85
    tilt = Matrix.Rotation(.32, 4, 'X')
    for i in range(9):
        a = i * TAU / 9
        p = c + (tilt @ Vector((math.cos(a) * R, math.sin(a) * R, 0)))
        rig.add(capped(p - Vector((0, 0, .1)), p + Vector((0, 0, .1)), .1, .09, twist=a), 'Team' if i % 3 == 0 else 'Lode', 'orbit')
        rig.add(orb(p + Vector((0, 0, .13)), .035, 1), 'Molten', 'orbit')
    rig.add(ring(c, R, .012, axis=tilt @ Vector((0, 0, 1)), sides=24, profile=3), 'Glow', 'orbit')
    # Two pylons on the back that throw the field.
    for sx in (-.13, .13):
        b = j['chest'] + Vector((sx, .22, .1))
        rig.add(capped(b, b + Vector((sx * .5, .08, .55)), .06, .05, twist=TAU / 12), 'Lode', 'spine')
        rig.add(orb(b + Vector((sx * .5, .08, .6)), .04, 1), 'Glow', 'spine')
    return rig


# --- Heroes ---------------------------------------------------------------------------------

def ashlar():
    """Ashlar, the Mason (front line): a tall, broad frame crowned with three short columns,
    a mantle of hex tiles in the side's color, and a maul that is a whole column on a brass haft."""
    rig = Rig()
    j = biped(rig, hip=1.15, chest=1.95, width=.4, leg=.15, arm=.13, stance=.22,
              right=((-.6, -.12, 1.6), (-.55, -.42, 1.35)))
    rig.bundle(j['chest'] + Vector((0, 0, -.04)), .78, .14, 'spine', tops=(.15, .1, .02, .2, .05, -.05, .12), team_tops=(0,))
    rig.core(j['chest'] + Vector((0, -.34, .02)), .12, 'spine')
    visor_head(rig, j['neck'] + Vector((0, 0, .02)), .15, 'head', h=.24)
    # The crown: three short columns rising behind the head, lit at the tips.
    for k, (dx, h) in enumerate(((0, .4), (-.13, .28), (.13, .28))):
        b = j['neck'] + Vector((dx, .1, .18))
        rig.add(capped(b, b + Vector((dx * .4, .04, h)), .06, .055, twist=TAU / 12), 'Brass' if k == 0 else 'Lode', 'head')
        rig.add(orb(b + Vector((dx * .4, .04, h + .03)), .035, 1), 'Molten', 'head')
    # The mantle: hex tiles over both shoulders and down the back.
    for sign, side in ((1, 'L'), (-1, 'R')):
        pauldron(rig, j[f'shoulder.{side}'] + Vector((sign * .05, 0, .12)), sign, .22)
        pauldron(rig, j[f'shoulder.{side}'] + Vector((sign * .02, .14, .02)), sign, .15, paint='Rust')
    for row, (z, n) in enumerate(((.15, 3), (-.15, 4), (-.45, 3))):
        for k in range(n):
            x = (k - (n - 1) / 2) * .19
            rig.add(hexplate(j['chest'] + Vector((x, .3 + row * .02, z)), .12, .03, (math.pi / 2 - .1, 0, TAU / 12)), 'Team' if (k + row) % 2 == 0 else 'Rust', 'spine')
    tabard(rig, j['pelvis'] + Vector((0, -.17, -.02)), .4, .45)
    # The maul: a brass haft through the right fist, a whole hex column for a head.
    w = j['wrist.R']
    top = w + Vector((0, -.05, .85))
    rig.add(prism(w - Vector((0, 0, .5)), top, .035, .035, sides=6), 'Brass', 'forearm.R')
    rig.add(capped(top + Vector((-.38, 0, 0)), top + Vector((.3, 0, 0)), .17, .17, twist=TAU / 12), 'Lode', 'forearm.R')
    for x in (-.15, .1):
        rig.add(prism(top + Vector((x, 0, 0)), top + Vector((x + .04, 0, 0)), .12), 'Molten', 'forearm.R')
    rig.add(ring(top, .18, .025, axis=(1, 0, 0), sides=6), 'Brass', 'forearm.R')
    clamp_hand(rig, j['wrist.L'], 'forearm.L', .09)
    return rig


def cupel():
    """Cupel, the Refiner (support caster): a walking furnace. Its chest is a kiln with an open
    molten mouth where the others carry a caged core, three chimney pipes rise from its back,
    and it carries a long ladle of molten ore."""
    rig = Rig()
    j = biped(rig, hip=1.05, chest=1.82, width=.38, leg=.12, arm=.1, stance=.2,
              right=((-.5, -.12, 1.45), (-.45, -.45, 1.3)))
    c = j['chest'] + Vector((0, 0, -.05))
    # The kiln body: a broad hex drum, the mouth a molten arch at the front, the great core
    # visible in the fire.
    rig.add(capped(c - Vector((0, 0, .5)), c + Vector((0, 0, .35)), .42, .34, twist=TAU / 12), 'Rust', 'spine')
    rig.add(box(c + Vector((0, -.37, -.08)), (.36, .06, .42), taper=.75), 'Molten', 'spine')
    rig.add(orb(c + Vector((0, -.33, -.04)), .11, 2), 'Glow', 'spine')
    for z in (-.38, .1, .3):
        rig.add(ring(c + Vector((0, 0, z)), .37 - z * .1, .03, sides=6), 'Brass', 'spine')
    for sign in (-1, 1):
        rig.add(hexplate(c + Vector((sign * .36, -.12, .05)), .17, .04, (0, math.pi / 2 * sign, .3 * sign)), 'Team', 'spine')
    # The head: a small hood of columns over the kiln.
    visor_head(rig, j['neck'] + Vector((0, -.05, -.02)), .13, 'head', h=.2, slit='Glow')
    rig.add(hexplate(j['neck'] + Vector((0, .02, .26)), .2, .05, (.2, 0, 0)), 'Team', 'head')
    # Three chimneys on the back, smoking with light.
    for dx, h in ((-.14, .8), (0, 1.0), (.14, .7)):
        b = c + Vector((dx, .3, .1))
        rig.add(prism(b, b + Vector((dx * .3, .08, h)), .065, .055, twist=TAU / 12), 'Lode', 'spine')
        rig.add(prism(b + Vector((dx * .3, .08, h)), b + Vector((dx * .3, .08, h + .05)), .075, twist=TAU / 12), 'Brass', 'spine')
        rig.add(orb(b + Vector((dx * .3, .08, h + .02)), .045, 1), 'Molten', 'spine')
    for sign, side in ((1, 'L'), (-1, 'R')):
        pauldron(rig, j[f'shoulder.{side}'] + Vector((sign * .03, 0, .1)), sign, .17)
    tabard(rig, j['pelvis'] + Vector((0, -.2, -.02)), .38, .5)
    # The ladle: a long brass shaft, a hex cup brimming with molten ore.
    w = j['wrist.R']
    a, b = w + Vector((0, .3, .35)), w + Vector((0, -.55, -.55))
    rig.add(prism(a, b, .025, .025, sides=6), 'Brass', 'forearm.R')
    cup = b + Vector((0, -.05, -.05))
    rig.add(prism(cup - Vector((0, 0, .1)), cup + Vector((0, 0, .06)), .1, .14, twist=TAU / 12), 'Rust', 'forearm.R')
    rig.add(prism(cup + Vector((0, 0, .04)), cup + Vector((0, 0, .065)), .12, twist=TAU / 12), 'Molten', 'forearm.R')
    clamp_hand(rig, j['wrist.L'], 'forearm.L', .075)
    return rig


def gnomon():
    """Gnomon, the Long Shadow (marksman): the tallest frame, narrow as a column, a sundial blade
    rising from its back in the side's color, and a rifle that is one long hex barrel with a lit bore."""
    rig = Rig()
    j = biped(rig, hip=1.3, chest=2.15, width=.22, leg=.1, arm=.075, stance=.15,
              right=((-.3, -.18, 1.95), (-.2, -.55, 1.95)), left=((.3, -.3, 1.85), (.12, -.85, 1.93)))
    rig.bundle(j['chest'], .6, .075, 'spine', tops=(.2, .05, .1, -.05, .15, .0, .1), team_tops=(4,))
    rig.core(j['chest'] + Vector((0, -.19, .03)), .07, 'spine')
    visor_head(rig, j['neck'], .1, 'head', h=.28, slit='Glow')
    # The gnomon: a tall triangular blade rising from the spine, sweeping back over the head.
    bm = bmesh.new()
    base0, base1 = j['chest'] + Vector((0, .18, -.35)), j['chest'] + Vector((0, .2, .25))
    tip = j['chest'] + Vector((0, .55, 1.15))
    vs = []
    for x in (-.025, .025):
        vs.append([bm.verts.new(p + Vector((x, 0, 0))) for p in (base0, base1, tip)])
    bm.faces.new(vs[0])
    bm.faces.new(list(reversed(vs[1])))
    for i in range(3):
        k = (i + 1) % 3
        bm.faces.new((vs[0][i], vs[1][i], vs[1][k], vs[0][k]))
    rig.add(bm, 'Team', 'spine')
    rig.add(prism(base1 + Vector((0, .01, 0)), tip + Vector((0, .01, 0)), .015, .008, sides=4), 'Brass', 'spine')
    rig.add(orb(tip, .04, 1), 'Glow', 'spine')
    # Long thin pauldrons and a long tabard.
    for sign, side in ((1, 'L'), (-1, 'R')):
        pauldron(rig, j[f'shoulder.{side}'] + Vector((sign * .02, 0, .08)), sign, .12, tilt=.7)
    tabard(rig, j['pelvis'] + Vector((0, -.12, -.02)), .26, .6)
    # The rifle: a single long hex barrel, a brass stock, a lit bore, a scope of slag glass.
    a = j['wrist.R'] + Vector((0, .25, .05))
    b = j['wrist.L'] + Vector((0, -.6, .02))
    d = (b - a).normalized()
    rig.add(prism(a, b, .045, .035, twist=TAU / 12), 'Lode', 'forearm.R')
    rig.add(prism(a - d * .3, a, .06, .045, sides=4), 'Brass', 'forearm.R')
    rig.add(prism(b, b + d * .05, .05, twist=TAU / 12), 'Brass', 'forearm.R')
    rig.add(prism(b + d * .04, b + d * .055, .025), 'Glow', 'forearm.R')
    for t in (.3, .6):
        rig.add(prism(a.lerp(b, t) - d * .015, a.lerp(b, t) + d * .015, .05), 'Molten', 'forearm.R')
    s = a.lerp(b, .25) + Vector((0, 0, .08))
    rig.add(prism(s, s + d * .22, .028, sides=6), 'Slag', 'forearm.R')
    return rig


# --- Motion ---------------------------------------------------------------------------------

FRAMES = {'Idle': 48, 'Run': 20}


def biped_actions(lean=.12, stride=.55, arm_swing=.35, held=('R',), heavy=False):
    """Idle: a slow breath, the head turning a little. Run: leaning in, legs striding, the free
    arms swinging; a held weapon arm stays steady."""
    idle, run = {}, {}
    n = FRAMES['Idle']
    idle['spine'] = [(f, (math.sin(f / n * TAU) * .02, 0, 0)) for f in range(0, n + 1, 8)]
    idle['head'] = [(f, (0, 0, math.sin(f / n * TAU) * .12)) for f in range(0, n + 1, 8)]
    for side in ('L', 'R'):
        if side not in held:
            idle[f'upperarm.{side}'] = [(f, (math.sin(f / n * TAU + 1) * .04, 0, 0)) for f in range(0, n + 1, 8)]
    m = FRAMES['Run']
    run['hips'] = [(f, (lean, 0, 0)) for f in (0, m)]
    run['spine'] = [(f, (lean * .5 + math.sin(f / m * TAU * 2) * .03, 0, math.sin(f / m * TAU) * .08)) for f in range(0, m + 1, 5)]
    for sign, side in ((1, 'L'), (-1, 'R')):
        ph = 0 if side == 'L' else math.pi
        run[f'thigh.{side}'] = [(f, (-math.sin(f / m * TAU + ph) * stride - lean, 0, 0)) for f in range(0, m + 1, 5)]
        run[f'shin.{side}'] = [(f, (max(0, math.sin(f / m * TAU + ph + 1.2)) * stride * 1.3, 0, 0)) for f in range(0, m + 1, 5)]
        if side not in held:
            run[f'upperarm.{side}'] = [(f, (math.sin(f / m * TAU + ph) * arm_swing, 0, 0)) for f in range(0, m + 1, 5)]
    bob = .07 if heavy else .05
    bobs = {'Idle': {'hips': [(f, math.sin(f / n * TAU) * .012) for f in range(0, n + 1, 8)]},
            'Run': {'hips': [(f, -abs(math.sin(f / m * TAU)) * bob) for f in range(0, m + 1, 5)]}}
    return {'Idle': (idle, bobs['Idle']), 'Run': (run, bobs['Run'])}


def legged_actions(legs, groups, stride=.35, body='body', extra=None, sideways=False):
    """Many legs: the legs in each group step together, the groups out of phase. Legs that
    stand out sideways (`sideways`, the Delver's) swing about the vertical and lift as they go."""
    n, m = FRAMES['Idle'], FRAMES['Run']
    idle = {body: [(f, (math.sin(f / n * TAU) * .02, 0, 0)) for f in range(0, n + 1, 8)]}
    run = {}
    for g, members in enumerate(groups):
        # An eighth of a turn in, so no sampled frame has every leg standing straight.
        ph = g * TAU / len(groups) + TAU / 8
        for leg in members:
            # Each leg bone swings about its own X, which the roll points sideways.
            if sideways:
                # A sideways bone's Z points up (its roll), so turning about Z swings it fore and aft.
                run[leg] = [(f, (max(0, math.cos(f / m * TAU + ph)) * stride * .5, 0, math.sin(f / m * TAU + ph) * stride)) for f in range(0, m + 1, 5)]
            else:
                run[leg] = [(f, (math.sin(f / m * TAU + ph) * stride, 0, 0)) for f in range(0, m + 1, 5)]
    run[body] = [(f, (.04 + math.sin(f / m * TAU * 2 + TAU / 8) * .03, 0, math.sin(f / m * TAU) * .04)) for f in range(0, m + 1, 5)]
    if extra:
        extra(idle, run)
    return {'Idle': (idle, {}), 'Run': (run, {})}


def spindle_actions():
    n, m = FRAMES['Idle'], FRAMES['Run']
    idle = {'wheel': [(f, (f / n * TAU / 12, 0, 0)) for f in range(0, n + 1, 8)],
            'frame': [(f, (math.sin(f / n * TAU) * .03, 0, 0)) for f in range(0, n + 1, 8)]}
    # One twelfth of a turn per cycle loops seamlessly (the rim repeats every block).
    run = {'wheel': [(f, (-f / m * TAU / 6, 0, 0)) for f in range(0, m + 1, 2)],
           'frame': [(f, (.12, 0, math.sin(f / m * TAU) * .04)) for f in range(0, m + 1, 5)]}
    return {'Idle': (idle, {}), 'Run': (run, {})}


def lodestone_actions():
    acts = biped_actions(lean=.06, stride=.4, held=('L', 'R'), heavy=True)
    n, m = FRAMES['Idle'], FRAMES['Run']
    acts['Idle'][0]['orbit'] = [(f, (0, 0, f / n * TAU / 9)) for f in range(0, n + 1, 4)]
    acts['Run'][0]['orbit'] = [(f, (0, 0, f / m * TAU / 9)) for f in range(0, m + 1, 2)]
    return acts


def crucible_extra(idle, run):
    idle['bowl'] = [(f, (0, math.sin(f / FRAMES['Idle'] * TAU) * .03, 0)) for f in range(0, FRAMES['Idle'] + 1, 8)]


UNITS = {
    'delver': (delver, lambda: legged_actions([f'leg{k}' for k in range(6)], (('leg0', 'leg2', 'leg4'), ('leg1', 'leg3', 'leg5')), stride=.45, sideways=True)),
    'hewn': (hewn, lambda: biped_actions(held=('R',))),
    'spindle': (spindle, spindle_actions),
    'cairn': (cairn, lambda: biped_actions(lean=.08, stride=.4, arm_swing=.3, held=(), heavy=True)),
    'crucible': (crucible, lambda: legged_actions(['leg0', 'leg1', 'leg2', 'leg3'], (('leg0', 'leg3'), ('leg1', 'leg2')), stride=.3, extra=crucible_extra)),
    'annealer': (annealer, lambda: biped_actions(held=('L', 'R'))),
    'lodestone': (lodestone, lodestone_actions),
    'ashlar': (ashlar, lambda: biped_actions(held=('R',), heavy=True)),
    'cupel': (cupel, lambda: biped_actions(lean=.08, held=('R',))),
    'gnomon': (gnomon, lambda: biped_actions(lean=.1, held=('L', 'R'))),
}


# --- Build and export -----------------------------------------------------------------------

def build(rig):
    arm_data = bpy.data.armatures.new('Armature')
    arm = bpy.data.objects.new('Armature', arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, tail, _) in rig.bones.items():
        b = arm_data.edit_bones.new(name)
        b.head, b.tail = head, tail
        # Roll so each bone's X axis points sideways: turning about X swings it forward and back.
        b.align_roll(Vector((0, -1, 0)) if abs((tail - head).normalized().z) > 0.7 else Vector((0, 0, 1)))
    for name, (_, _, parent) in rig.bones.items():
        if parent:
            arm_data.edit_bones[name].parent = arm_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh = bpy.data.meshes.new('Body')
    body = bpy.data.objects.new('Body', mesh)
    bpy.context.collection.objects.link(body)
    for n in NAMES:
        mesh.materials.append(material(n))
    groups = {name: body.vertex_groups.new(name=name) for name in rig.bones}
    joined = bmesh.new()
    deform = joined.verts.layers.deform.verify()
    for bm, paint, bone in rig.parts:
        tmp = bpy.data.meshes.new('tmp')
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(tmp)
        bm.free()
        start, fstart = len(joined.verts), len(joined.faces)
        joined.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        joined.verts.ensure_lookup_table()
        joined.faces.ensure_lookup_table()
        for v in joined.verts[start:]:
            v[deform][groups[bone].index] = 1.0
        for f in joined.faces[fstart:]:
            f.material_index = NAMES.index(paint)
            f.smooth = False
    joined.to_mesh(mesh)
    joined.free()
    body.parent = arm
    body.modifiers.new('Armature', 'ARMATURE').object = arm
    return arm, body


def animate(arm, actions):
    arm.animation_data_create()
    for bone in arm.pose.bones:
        bone.rotation_mode = 'XYZ'
    for name, (rotations, bobs) in actions.items():
        action = bpy.data.actions.new(name)
        arm.animation_data.action = action
        for bone in arm.pose.bones:
            bone.rotation_euler = (0, 0, 0)
            bone.location = (0, 0, 0)
        # Key every bone at the cycle's ends, so a clip never inherits another's pose.
        for bone in arm.pose.bones:
            for f in (0, FRAMES[name]):
                bone.keyframe_insert('rotation_euler', frame=f)
        for bone_name, keys in rotations.items():
            pb = arm.pose.bones[bone_name]
            for f, rot in keys:
                pb.rotation_euler = rot
                pb.keyframe_insert('rotation_euler', frame=f)
        for bone_name, keys in bobs.items():
            pb = arm.pose.bones[bone_name]
            for f, dz in keys:
                pb.location = (0, dz, 0)
                pb.keyframe_insert('location', frame=f)
        track = arm.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 0, action)
        arm.animation_data.action = None


def export(kind, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 24
    make, motions = UNITS[kind]
    rig = make()
    arm, body = build(rig)
    animate(arm, motions())
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    zs = [v.co.z for v in body.data.vertices]
    print(f'{kind}: {len(body.data.vertices)} vertices, about {tris} triangles, {max(zs) - min(zs):.2f} m tall')
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_animations=True,
                              export_animation_mode='NLA_TRACKS', export_apply=False, export_yup=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    kind, out = argv[0], argv[1]
    if kind == 'all':
        for k in UNITS:
            export(k, f'{out}/meridian-{k}.glb')
    else:
        export(kind, out)


if __name__ == '__main__':
    main()

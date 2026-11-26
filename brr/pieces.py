"""Jewellery pieces built from a config dict. Units are millimetres.

Coordinates: z is up. A ring stands upright with the finger hole along y, the stone on top.
"""
import math
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix

from . import gems, materials

RING_SIZE_MM = {3: 14.1, 4: 14.9, 5: 15.7, 6: 16.5, 6.5: 16.9, 7: 17.3, 7.5: 17.7, 8: 18.1, 9: 18.9, 10: 19.8}

# carat -> (length, width) in mm for typical well-cut stones; used when a config gives carat, not mm
CARAT_MM = {
    'round':    lambda ct: (6.5 * ct ** (1 / 3),) * 2,
    'pear':     lambda ct: (10.3 * ct ** (1 / 3), 6.6 * ct ** (1 / 3)),
    'marquise': lambda ct: (12.0 * ct ** (1 / 3), 6.0 * ct ** (1 / 3)),
    'oval':     lambda ct: (9.6 * ct ** (1 / 3), 6.8 * ct ** (1 / 3)),
    'emerald':  lambda ct: (8.0 * ct ** (1 / 3), 6.0 * ct ** (1 / 3)),
    'radiant':  lambda ct: (7.7 * ct ** (1 / 3), 6.0 * ct ** (1 / 3)),
    'cushion':  lambda ct: (6.6 * ct ** (1 / 3), 6.0 * ct ** (1 / 3)),
    'asscher':  lambda ct: (5.9 * ct ** (1 / 3),) * 2,
}


def stone_size(cfg):
    if 'length' in cfg and 'width' in cfg:
        return cfg['length'], cfg['width']
    if 'diameter' in cfg:
        return cfg['diameter'], cfg['diameter']
    return CARAT_MM[cfg['shape']](cfg['carat'])


# ---------------------------------------------------------------- helpers

def _obj_from_bm(name, bm, mat, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat)
    return o


def stone(name, shape, L, W, mat, matrix=Matrix.Identity(4)):
    bm = bmesh.new()
    o2d, hc, hp = gems.stone_mesh(bm, shape, L, W)
    bm.transform(matrix)
    _obj_from_bm(name, bm, mat)
    return o2d, hc, hp


def tube(name, points, radius, mat, closed=False, cap=True, smooth_path=True):
    """A round wire through the given points (prongs, rails, galleries)."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.resolution_u = 12
    cu.use_fill_caps = cap
    sp = cu.splines.new('BEZIER' if smooth_path else 'POLY')
    pts = [Vector(p) for p in points]
    if smooth_path:
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
    else:
        sp.points.add(len(pts) - 1)
        for bp, p in zip(sp.points, pts):
            bp.co = (*p, 1)
    sp.use_cyclic_u = closed
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat)
    return o


def ball(name, loc, radius, mat, squash=1.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=24, ring_count=12)
    o = bpy.context.object
    o.name = name
    o.scale.z = squash
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


def _outline_at(o2d, frac):
    """Point on the outline at a fraction (0..1) of its length, starting at its first point (the tip)."""
    n = len(o2d)
    f = (frac % 1) * n
    i = int(f); t = f - i
    return o2d[i % n] * (1 - t) + o2d[(i + 1) % n] * t


# ---------------------------------------------------------------- pieces

def band(name, inner_r, width, thickness, mat, centre_y=0.0, taper=1.0, segments=160):
    """Ring shank: a rounded-rectangle profile swept round a circle in the x-z plane. `taper` < 1 makes
    the bottom of the shank narrower/thinner than the top."""
    bm = bmesh.new()
    # rounded-rectangle profile (superellipse): (radial offset, offset along the finger)
    prof = []
    for j in range(32):
        t = 2 * math.pi * j / 32
        c, s_ = math.cos(t), math.sin(t)
        prof.append((thickness / 2 * math.copysign(abs(c) ** 0.5, c), width / 2 * math.copysign(abs(s_) ** 0.5, s_)))
    rings = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        s = 1 - (1 - taper) * (1 - math.cos(a)) / 2          # 1 at the top, taper at the bottom
        ring = []
        for dr, dy in prof:
            r = inner_r + thickness / 2 + dr * s
            ring.append(bm.verts.new((r * math.sin(a), centre_y + dy * s, r * math.cos(a))))
        rings.append(ring)
    m = len(prof)
    for i in range(segments):
        A, B = rings[i], rings[(i + 1) % segments]
        for j in range(m):
            bm.faces.new((A[j], A[(j + 1) % m], B[(j + 1) % m], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _obj_from_bm(name, bm, mat, smooth=True)


DEFAULT_PRONGS = {'pear': [0.0, 0.39, 0.61], 'marquise': [0.0, 0.5], 'round': [0.125, 0.375, 0.625, 0.875],
                  'oval': [0.1, 0.4, 0.6, 0.9], 'emerald': [0.07, 0.43, 0.57, 0.93],
                  'radiant': [0.07, 0.43, 0.57, 0.93], 'cushion': [0.125, 0.375, 0.625, 0.875],
                  'asscher': [0.125, 0.375, 0.625, 0.875]}


def set_stone(name, shape, L, W, M, dia, prong_mat, prongs=None, prong_radius=None, root_z=None,
              basket=True, rotate=0.0):
    """One stone in a prong head. M places the stone: its origin is the girdle centre, +z the table.
    `root_z` (local) is where the prongs end below the stone; default is just under the culet."""
    rot = Matrix.Rotation(math.radians(rotate), 4, 'Z')
    o2d, hc, hp = stone(name, shape, L, W, dia, M @ rot)
    o2d = np.array([(rot @ Vector((p[0], p[1], 0)))[:2] for p in o2d])
    fracs = prongs if prongs is not None else DEFAULT_PRONGS.get(shape, DEFAULT_PRONGS['round'])
    pr = prong_radius or 0.058 * W
    rz = root_z if root_z is not None else -hp - 0.3 * W
    for i, f in enumerate(fracs):
        p = _outline_at(o2d, f + rotate / 360.0 * 0)
        out = p / max(np.linalg.norm(p), 1e-6)
        tip_in = 0.25 if f % 0.5 == 0 and shape in ('pear', 'marquise') else 0.18
        path = [(*(p * 0.22), rz), (*(p * 0.55), -0.75 * hp), (*(p + out * pr * 0.9), -0.1),
                (*(p - out * pr * tip_in * 1.8), 0.45 * hc)]
        path = [M @ Vector(q) for q in path]
        tube(f'{name}_prong{i}', path, pr, prong_mat)
        ball(f'{name}_prong{i}_tip', path[-1], pr * 1.08, prong_mat, squash=0.85)
    if basket:
        rail = [M @ Vector((*(q * 0.6), -0.62 * hp)) for q in o2d[::2]]
        tube(f'{name}_gallery', rail, pr * 0.55, prong_mat, closed=True)
    return o2d, hc, hp


def _mats(cfg):
    metal = materials.metal(cfg.get('metal', 'yellow_14k'))
    prong = materials.metal(cfg.get('prong_metal', cfg.get('metal', 'yellow_14k')))
    return metal, prong, materials.diamond(cfg.get('fire', 1.0))


def solitaire_ring(cfg):
    """A solitaire: shank + centre stone + prong head. The ring stands upright, finger hole along y."""
    st = cfg['stone']
    L, W = stone_size(st)
    ri = RING_SIZE_MM.get(cfg.get('ring_size', 6), 16.5) / 2
    bw, bt = cfg.get('band_width', 1.8), cfg.get('band_thickness', 1.6)
    metal, prong_mat, dia = _mats(cfg)
    band('band', ri, bw, bt, metal, taper=cfg.get('taper', 1.0))
    top = ri + bt
    _, hc, hp = gems.stone_mesh(bmesh.new(), st['shape'], L, W)      # proportions only
    gz = top + hp + cfg.get('setting_height', 0.9)                   # girdle height
    set_stone('stone', st['shape'], L, W, Matrix.Translation((0, 0, gz)), dia, prong_mat,
              cfg.get('prongs'), cfg.get('prong_radius'), root_z=top - 0.3 - gz, rotate=st.get('rotate', 0))


def _path_frames(kind, n, length, ellipse=1.0):
    """Positions and tangents of n evenly spaced points on a closed loop lying flat (bracelets)."""
    r = length / (2 * math.pi)
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pos = Vector((r * math.sin(a), r * ellipse * math.cos(a), 0))
        tan = Vector((math.cos(a), -ellipse * math.sin(a), 0)).normalized()
        out.append((pos, tan, a))
    return out


def tennis_bracelet(cfg):
    """A line of stones round a flat loop, each in its own prong basket, with a box clasp at the top.
    `stones` can be one stone or a list that repeats (mixed-shape bracelets)."""
    metal, prong_mat, dia = _mats(cfg)
    stones = cfg['stones'] if isinstance(cfg.get('stones'), list) else [cfg['stone']]
    length = cfg.get('length_in', 7) * 25.4
    sizes = [stone_size(s) for s in stones]
    gap = cfg.get('gap', 0.5)
    pitch = sum(max(min(L, W), W) if s.get('angle', cfg.get('stone_angle', 0)) % 180 == 90 else
                (L * abs(math.cos(math.radians(s.get('angle', cfg.get('stone_angle', 0))))) +
                 W * abs(math.sin(math.radians(s.get('angle', cfg.get('stone_angle', 0))))))
                for s, (L, W) in zip(stones, sizes)) / len(stones) + gap
    n = cfg.get('count') or int(length / pitch)
    frames = _path_frames('circle', n, length, cfg.get('ellipse', 0.96))
    clasp_i = 0
    for i, (pos, tan, a) in enumerate(frames):
        if i == clasp_i and cfg.get('clasp', True):
            _box_clasp(pos, tan, max(sz[1] for sz in sizes), metal)
            continue
        s = stones[i % len(stones)]
        L, W = stone_size(s)
        ang = math.radians(s.get('angle', cfg.get('stone_angle', 0)))
        # stone long axis (local y) along the tangent, then turned by `angle`
        rz = math.atan2(tan.y, tan.x) - math.pi / 2 + ang
        M = Matrix.Translation(pos + Vector((0, 0, 0))) @ Matrix.Rotation(rz, 4, 'Z')
        _, hc, hp = gems.stone_mesh(bmesh.new(), s['shape'], L, W)
        M = Matrix.Translation((0, 0, hp + 0.6)) @ M
        set_stone(f's{i}', s['shape'], L, W, M, dia, prong_mat, s.get('prongs', cfg.get('prongs')),
                  cfg.get('prong_radius'), root_z=-hp - 0.5)
    # the links: a rail under the stones holding everything together
    r = length / (2 * math.pi)
    rail = [Vector((r * math.sin(t), r * cfg.get('ellipse', 0.96) * math.cos(t), 0.35))
            for t in np.linspace(0, 2 * math.pi, 180, endpoint=False)]
    tube('links', rail, 0.35, metal, closed=True)


def _box_clasp(pos, tan, width, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos + Vector((0, 0, width * 0.32)))
    o = bpy.context.object
    o.name = 'clasp'
    o.scale = (width * 1.25, width * 0.75, width * 0.62)
    o.rotation_euler.z = math.atan2(tan.y, tan.x)
    mod = o.modifiers.new('bevel', 'BEVEL'); mod.width = width * 0.12; mod.segments = 4
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    # grooves: thin raised bands across the box
    for k in (-0.3, 0, 0.3):
        bpy.ops.mesh.primitive_cube_add(size=1, location=o.location + tan * width * k + Vector((0, 0, width * 0.32)))
        g = bpy.context.object
        g.scale = (width * 0.06, width * 0.8, width * 0.08)
        g.rotation_euler.z = math.atan2(tan.y, tan.x)
        g.data.materials.append(mat)


def stud_earrings(cfg):
    """A pair of studs lying table-up side by side."""
    metal, prong_mat, dia = _mats(cfg)
    st = cfg['stone']
    L, W = stone_size(st)
    _, hc, hp = gems.stone_mesh(bmesh.new(), st['shape'], L, W)
    sep = max(L, W) * cfg.get('spacing', 1.5)
    for k, x in enumerate((-sep / 2, sep / 2)):
        M = Matrix.Translation((x, 0, hp + 0.4))
        set_stone(f'stud{k}', st['shape'], L, W, M, dia, prong_mat, cfg.get('prongs'), cfg.get('prong_radius'),
                  root_z=-hp - 0.4, rotate=st.get('rotate', 0))


def drop_earrings(cfg):
    """A pair of drops: a column of stones (graduated or mixed shapes) linked top to bottom, lying flat.
    `stones` lists the stones from the top down."""
    metal, prong_mat, dia = _mats(cfg)
    col = cfg['stones']
    sep = cfg.get('spacing', 14)
    for k, x in enumerate((-sep / 2, sep / 2)):
        y = 0
        prev = None
        for j, s in enumerate(col):
            L, W = stone_size(s)
            _, hc, hp = gems.stone_mesh(bmesh.new(), s['shape'], L, W)
            y -= L / 2
            M = Matrix.Translation((x, y, hp + 0.4))
            set_stone(f'd{k}_{j}', s['shape'], L, W, M, dia, prong_mat, s.get('prongs'), cfg.get('prong_radius'),
                      root_z=-hp - 0.4, rotate=s.get('rotate', 0))
            if prev is not None:
                tube(f'd{k}_link{j}', [(x, prev, 0.5), (x, y + L / 2, 0.5)], 0.3, metal, smooth_path=False)
            prev = y - L / 2
            y -= L / 2 + cfg.get('gap', 0.9)
        # post / hook at the top
        tube(f'd{k}_post', [(x, 1.2, 0.6), (x, -0.2, 0.6)], 0.4, metal, smooth_path=False)


def eternity_ring(cfg):
    """Stones all the way round (or `coverage` of the way round) an upright band, tables facing out."""
    metal, prong_mat, dia = _mats(cfg)
    st = cfg['stone']
    L, W = stone_size(st)
    ri = RING_SIZE_MM.get(cfg.get('ring_size', 6), 16.5) / 2
    bt = cfg.get('band_thickness', 1.4)
    band('band', ri, cfg.get('band_width', min(L, W) * 0.7), bt, metal)
    _, hc, hp = gems.stone_mesh(bmesh.new(), st['shape'], L, W)
    R = ri + bt + hp * 0.55                          # girdle radius
    ang = math.radians(st.get('angle', 0))
    along = L * abs(math.cos(ang)) + W * abs(math.sin(ang))
    cover = cfg.get('coverage', 1.0)
    n = cfg.get('count') or int(2 * math.pi * R * cover / (along + cfg.get('gap', 0.3)))
    for i in range(n):
        a = 2 * math.pi * cover * (i + 0.5) / n - math.pi * cover
        # local z (table) points radially out; local y along the band's circle, turned by `angle`
        M = (Matrix.Rotation(a, 4, 'Y') @ Matrix.Translation((0, 0, R)) @ Matrix.Rotation(math.pi / 2 + ang, 4, 'Z'))
        set_stone(f'e{i}', st['shape'], L, W, M, dia, prong_mat, cfg.get('prongs'), cfg.get('prong_radius'),
                  root_z=-hp - 0.2, basket=False)


def chain(name, path, mat, link=1.3, wire=0.14, width=0.75):
    """A cable chain along a path (list of points, mm): small oval links, every other one turned 90 degrees."""
    pts = [Vector(p) for p in path]
    # resample the path evenly at the link pitch
    seg = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum((b - a).length for a, b in seg)
    n = max(2, int(total / link))
    samples = []
    for k in range(n + 1):
        d = total * k / n
        for a, b in seg:
            L = (b - a).length
            if d <= L or (a, b) == seg[-1]:
                samples.append(a.lerp(b, min(d / L, 1.0)))
                break
            d -= L
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=wire, major_segments=24, minor_segments=8)
    proto = bpy.context.object
    proto.name = name + '_proto'
    me = proto.data
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    bpy.data.objects.remove(proto)
    for k in range(len(samples) - 1):
        a, b = samples[k], samples[k + 1]
        c = (a + b) / 2
        t = (b - a).normalized()
        o = bpy.data.objects.new(f'{name}_{k}', me)
        bpy.context.scene.collection.objects.link(o)
        # torus lies in its local XY plane: stretch along x (the chain direction), then align x to the tangent
        o.scale = ((b - a).length * 0.95, width / 2, 1.0)
        rot = t.to_track_quat('X', 'Z')
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = rot @ Matrix.Rotation(math.pi / 2 * (k % 2), 4, 'X').to_quaternion()
        o.location = c


def cluster_pendant(cfg):
    """Stones arranged in a motif (butterfly, flower, star...) lying flat, table up, with an optional gold
    body bar, jump rings at the attach points, and a cable chain running out of frame.

    stones: list of {shape, carat (or length/width), pos: [x, y], rotate: degrees}
    body: {from: [x, y], to: [x, y], radius}
    chain: list of paths, each a list of [x, y] (or [x, y, z]) points, starting at an attach point
    """
    metal, prong_mat, dia = _mats(cfg)
    zmax = 0
    for i, s in enumerate(cfg['stones']):
        L, W = stone_size(s)
        _, hc, hp = gems.stone_mesh(bmesh.new(), s['shape'], L, W)
        x, y = s['pos']
        M = Matrix.Translation((x, y, hp + 0.5))
        set_stone(f'c{i}', s['shape'], L, W, M, dia, prong_mat, s.get('prongs'), cfg.get('prong_radius'),
                  root_z=-hp - 0.3, rotate=s.get('rotate', 0))
        zmax = max(zmax, hp + 0.5)
    if 'body' in cfg:
        b = cfg['body']
        z = zmax + 0.3
        tube('body', [(*b['from'], z), (*b['to'], z)], b.get('radius', 0.7), metal, smooth_path=False)
        ball('body_end0', (*b['from'], z), b.get('radius', 0.7), metal)
        ball('body_end1', (*b['to'], z), b.get('radius', 0.7), metal)
    for j, path in enumerate(cfg.get('chain', [])):
        pts = [tuple(p) + ((zmax * 0.6,) if len(p) == 2 else ()) for p in path]
        # jump ring at the attach point
        bpy.ops.mesh.primitive_torus_add(major_radius=0.55, minor_radius=0.16, location=pts[0])
        ring = bpy.context.object
        ring.name = f'jump{j}'
        ring.rotation_euler.x = math.pi / 2
        ring.data.materials.append(metal)
        bpy.ops.object.shade_smooth()
        chain(f'chain{j}', pts, metal, cfg.get('link', 1.3), cfg.get('wire', 0.14), cfg.get('link_width', 0.6))

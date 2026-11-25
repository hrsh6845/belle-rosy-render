"""Faceted gemstone meshes built from an outline.

Every cut is made the same way: take the stone's outline (round, pear, marquise, oval, emerald...),
place rings of points at different heights and sizes (girdle, crown, table, pavilion, culet), and wrap
them in a convex hull. Flat-shaded, the hull's faces read as facets. All sizes are in millimetres.
"""
import math
import bmesh
import numpy as np
from mathutils import Vector

# ---------------------------------------------------------------- outlines (closed, x across, y along)

def _resample(poly, n, start_index=0):
    """Resample a dense closed polyline to n points evenly spaced by arc length, starting at start_index."""
    poly = np.roll(np.asarray(poly, float), -start_index, axis=0)
    closed = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    targets = np.linspace(0, cum[-1], n, endpoint=False)
    xs = np.interp(targets, cum, closed[:, 0])
    ys = np.interp(targets, cum, closed[:, 1])
    return np.stack([xs, ys], 1)


def outline(shape, length, width, n=64):
    """Return n outline points (x, y) centred on the origin. y is the long axis; the first point is
    the tip for pear and marquise so a facet ridge runs to it."""
    L, W = length, width
    t = np.linspace(0, 2 * math.pi, 4000, endpoint=False)
    if shape == 'round':
        r = W / 2
        pts = np.stack([r * np.sin(t), r * np.cos(t)], 1)
        return _resample(pts, n)
    if shape == 'oval':
        pts = np.stack([W / 2 * np.sin(t), L / 2 * np.cos(t)], 1)
        return _resample(pts, n)
    if shape == 'marquise':
        # two circular arcs meeting at the tips (0, +-L/2)
        a = L / 2; b = W / 2
        R = (a * a + b * b) / (2 * b)          # arc radius
        cx = R - b
        ang = math.asin(a / R)
        th = np.linspace(-ang, ang, 2000)
        right = np.stack([-cx + R * np.cos(th), R * np.sin(th)], 1)[::-1]   # from top tip down the right side
        left = np.stack([cx - R * np.cos(th), R * np.sin(th)], 1)            # from bottom tip up the left side
        pts = np.vstack([right, left])
        top = int(np.argmax(pts[:, 1]))
        return _resample(pts, n, top)
    if shape == 'pear':
        # round end: circle of radius W/2 at the bottom; sides: gently convex curves up to a point at +L/2
        r = W / 2
        cy = -L / 2 + r
        tip = np.array([0.0, L / 2])
        # where the sides leave the circle (a little above its centre, like real pears)
        a0 = math.radians(18)
        p0 = np.array([r * math.cos(a0), cy + r * math.sin(a0)])
        tan0 = np.array([-math.sin(a0), math.cos(a0)])            # circle tangent going up
        # cubic bezier p0 -> tip, leaving along the tangent, arriving at the tip at a ~38 deg half-angle
        d = np.linalg.norm(tip - p0)
        c1 = p0 + tan0 * d * 0.42
        half = math.radians(38)
        c2 = tip + np.array([math.sin(half), -math.cos(half)]) * d * 0.35
        s = np.linspace(0, 1, 1500)[:, None]
        side = (1 - s) ** 3 * p0 + 3 * (1 - s) ** 2 * s * c1 + 3 * (1 - s) * s ** 2 * c2 + s ** 3 * tip
        arc_t = np.linspace(a0, -math.pi - a0, 3000)               # right side down round the bottom to the left
        arc = np.stack([r * np.cos(arc_t), cy + r * np.sin(arc_t)], 1)
        # tip -> right side -> round bottom -> left side (back up towards the tip)
        pts = np.vstack([side[::-1][:-1], arc, (side * np.array([-1, 1]))[1:-1]])
        top = int(np.argmax(pts[:, 1]))
        return _resample(pts, n, top)
    if shape in ('emerald', 'radiant', 'asscher', 'cushion'):
        cut = (0.16 if shape != 'asscher' else 0.24) * min(L, W)  # corner cut
        x, y = W / 2, L / 2
        if shape == 'cushion':
            # superellipse
            p = 3.2
            ct, st = np.cos(t), np.sin(t)
            pts = np.stack([x * np.sign(st) * np.abs(st) ** (2 / p), y * np.sign(ct) * np.abs(ct) ** (2 / p)], 1)
            return _resample(pts, n)
        octa = np.array([[-x + cut, y], [x - cut, y], [x, y - cut], [x, -y + cut],
                         [x - cut, -y], [-x + cut, -y], [-x, -y + cut], [-x, y - cut]])
        dense = []
        for i in range(8):
            a, b = octa[i], octa[(i + 1) % 8]
            for s in np.linspace(0, 1, 400, endpoint=False):
                dense.append(a + (b - a) * s)
        return _resample(np.array(dense), n)
    raise ValueError(f'unknown shape {shape}')


# ---------------------------------------------------------------- proportions per cut

BRILLIANT = dict(table=0.57, crown=0.15, pavilion=0.43, girdle=0.03)   # fractions of width
STEP = dict(table=0.66, crown=0.12, pavilion=0.40, girdle=0.03)


def _ring(pts, scale, z, centre):
    return [Vector(((p[0] - centre[0]) * scale + centre[0], (p[1] - centre[1]) * scale + centre[1], z)) for p in pts]


def _pick(pts, k, phase=0.0):
    n = len(pts)
    idx = [int(round((i + phase) * n / k)) % n for i in range(k)]
    return pts[idx]


def stone_mesh(bm, shape, length, width, depth_scale=1.0):
    """Add a faceted stone to bmesh `bm`, table up, girdle centred on z=0. Returns (girdle points, crown
    height, pavilion depth) so settings can put prongs at the girdle."""
    L, W = length, width
    step = shape in ('emerald', 'asscher')
    P = STEP if step else BRILLIANT
    size = W
    hc, hp, g = P['crown'] * size, P['pavilion'] * size * depth_scale, P['girdle'] * size
    n = 48 if step else 32
    o = outline(shape, L, W, n)
    # pear and marquise tables sit towards the wide part, like real stones
    centre = o.mean(axis=0)
    if shape == 'pear':
        centre = np.array([0.0, centre[1] - 0.06 * L])
    pts = []
    pts += _ring(o, 1.0, g / 2, centre)                         # girdle top
    pts += _ring(o, 1.0, -g / 2, centre)                        # girdle bottom
    if step:
        for s, h in ((0.92, 0.45), (0.82, 0.8)):
            pts += _ring(o, s, g / 2 + h * hc, centre)
        pts += _ring(o, P['table'], g / 2 + hc, centre)
        for s, h in ((0.82, 0.32), (0.6, 0.62), (0.34, 0.88)):
            pts += _ring(o, s, -g / 2 - h * hp, centre)
        keel = o.copy(); keel[:, 0] *= 0.02; keel[:, 1] *= 0.18 if L > W * 1.1 else 0.02
        pts += _ring(keel, 1.0, -g / 2 - hp, (0, 0))
    else:
        k = 8
        main = _pick(o, k, 0.0)                                  # main facet directions (tip for pear/marquise)
        star = _pick(o, k, 0.5)
        upper = _pick(o, 2 * k, 0.25)
        pts += _ring(main, 0.86, g / 2 + 0.42 * hc, centre)      # bezel peaks
        pts += _ring(star, P['table'] + 0.08, g / 2 + 0.93 * hc, centre)  # star points just below the table
        pts += _ring(star, P['table'], g / 2 + hc, centre)       # table octagon
        pts += _ring(main, 0.78, -g / 2 - 0.24 * hp, centre)     # lower-girdle break
        pts += _ring(main, 0.42, -g / 2 - 0.62 * hp, centre)     # pavilion mains
        culet = np.array([[centre[0], centre[1]]])
        if shape in ('marquise', 'pear', 'oval'):
            # a short keel line along the long axis instead of a single culet point
            ext = 0.10 * L
            culet = np.array([[centre[0], centre[1] - ext], [centre[0], centre[1] + ext]])
        pts += [Vector((c[0], c[1], -g / 2 - hp)) for c in culet]
    verts = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=verts)
    # drop points the hull left unused
    loose = [v for v in res.get('geom_unused', []) if isinstance(v, bmesh.types.BMVert)]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.5), verts=bm.verts[:], edges=bm.edges[:])
    return o, hc + g / 2, hp + g / 2

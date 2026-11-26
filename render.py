#!/usr/bin/env python3
"""Render a piece from a YAML config.

    python render.py configs/RG-14Y-TBD-002.yaml            # full quality
    python render.py configs/RG-14Y-TBD-002.yaml --preview  # quick, small, noisy check
    python render.py configs/RG-14Y-TBD-002.yaml --view top # just one of the config's views

Each view in the config becomes renders/<sku>/<sku>-<view>.jpg (plus a transparent .png).
"""
import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from brr import pieces, studio  # noqa: E402

BUILDERS = {
    'solitaire_ring': pieces.solitaire_ring,
    'eternity_ring': pieces.eternity_ring,
    'tennis_bracelet': pieces.tennis_bracelet,
    'stud_earrings': pieces.stud_earrings,
    'drop_earrings': pieces.drop_earrings,
    'cluster_pendant': pieces.cluster_pendant,
}

DEFAULT_VIEWS = {
    'solitaire_ring': {'front': dict(elevation=58), 'angle': dict(elevation=30, azimuth=35)},
    'eternity_ring': {'front': dict(elevation=58), 'angle': dict(elevation=30, azimuth=35)},
    'tennis_bracelet': {'top': dict(elevation=80), 'angle': dict(elevation=40, azimuth=20)},
    'stud_earrings': {'top': dict(elevation=75), 'angle': dict(elevation=40, azimuth=25)},
    'drop_earrings': {'top': dict(elevation=85), 'angle': dict(elevation=50, azimuth=20)},
    'cluster_pendant': {'top': dict(elevation=88), 'angle': dict(elevation=45, azimuth=15)},
}


def scene_bounds():
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in bpy.context.scene.objects:
        if o.type not in ('MESH', 'CURVE') or o.name == 'floor' or not o.visible_camera:
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


def build(cfg):
    studio.reset()
    BUILDERS[cfg['type']](cfg)
    lo, hi = scene_bounds()
    centre = (lo + hi) / 2
    radius = (hi - lo).length / 2
    return lo, hi, centre, radius


def render(cfg_path, preview=False, only=None, out_root='renders'):
    cfg = yaml.safe_load(open(cfg_path))
    sku = cfg.get('sku', os.path.splitext(os.path.basename(cfg_path))[0])
    out_dir = os.path.join(out_root, sku)
    os.makedirs(out_dir, exist_ok=True)
    views = cfg.get('views', DEFAULT_VIEWS[cfg['type']])
    look = cfg.get('studio', {})
    w, h = cfg.get('size', [1600, 1600])
    done = []
    for name, v in views.items():
        if only and name != only:
            continue
        lo, hi, centre, radius = build(cfg)
        if 'focus' in v:                     # frame part of the piece (e.g. a pendant, not its whole chain)
            centre = Vector(v['focus'].get('centre', centre)); radius = v['focus'].get('radius', radius)
        studio.world(look.get('world', 0.7))
        studio.lights(centre, radius * 2, look)
        studio.floor(lo.z - 0.02, radius * 40)
        studio.camera(centre + Vector(v.get('offset', (0, 0, 0))), radius, v.get('elevation', 35),
                      v.get('azimuth', 0), v.get('lens', 100), v.get('fill', look.get('fill', 0.88)), w / h)
        scale = 0.35 if preview else 1.0
        studio.settings(int(w * scale), int(h * scale), samples=int(os.environ.get('BRR_PREVIEW_SAMPLES', 48)) if preview else look.get('samples', 128))
        png = os.path.join(out_dir, f'{sku}-{name}.png')
        bpy.context.scene.render.filepath = os.path.abspath(png)
        bpy.ops.render.render(write_still=True)
        jpg = png[:-4] + '.jpg'
        studio.composite(png, jpg, tuple(look.get('background', (245, 245, 245))))
        print('wrote', jpg)
        done.append(jpg)
    return done


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('configs', nargs='+')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--view')
    ap.add_argument('--out', default='renders')
    a = ap.parse_args()
    for c in a.configs:
        render(c, a.preview, a.view, a.out)

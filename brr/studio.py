"""The studio: light grey seamless look, soft boxes, dark flags for diamond contrast, camera framing,
render settings and the final composite onto the background colour."""
import math
import os
import bpy
import numpy as np
from mathutils import Vector


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = 'CYCLES'
    s.unit_settings.system = 'NONE'          # 1 unit = 1 mm
    return s


def _area(name, loc, target, size, power, color=(1, 1, 1), shape='RECTANGLE', size_y=None):
    d = bpy.data.lights.new(name, 'AREA')
    d.shape = shape
    d.size = size
    if size_y:
        d.size_y = size_y
    d.energy = power
    d.color = color
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def _flag(name, loc, target, w, h, value=0.0):
    """A dark card the camera can't see but the diamond reflects, which gives facets their contrast."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (w, h, 1)
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('Z', 'Y').to_euler()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (value, value, value, 1)
    p.inputs['Roughness'].default_value = 1.0
    o.data.materials.append(m)
    o.visible_camera = False
    o.visible_shadow = False
    return o


def lights(centre, scale, cfg):
    """Soft, bright, mostly-white light from above and the sides, like a jewellery light tent.
    `scale` is the size of the piece in mm, so the setup works for studs and bracelets alike."""
    c = Vector(centre)
    k = scale
    b = cfg.get('brightness', 1.0)
    D = 6 * k
    _area('top', c + Vector((0, -0.6 * D, 1.4 * D)), c, 3.2 * k, 9e3 * b * k * k / 400)
    _area('key', c + Vector((-1.3 * D, -0.9 * D, 0.9 * D)), c, 2.6 * k, 5e3 * b * k * k / 400)
    _area('fill', c + Vector((1.3 * D, -0.6 * D, 0.7 * D)), c, 2.6 * k, 3.5e3 * b * k * k / 400)
    _area('rim', c + Vector((0, 1.4 * D, 0.8 * D)), c, 3.0 * k, 4e3 * b * k * k / 400)
    contrast = cfg.get('contrast', 1.0)
    if contrast > 0:
        # two narrow dark flags left and right, and one low behind the camera
        _flag('flag_l', c + Vector((-0.9 * D, 0.3 * D, 0.35 * D)), c, 0.35 * D * contrast, 1.6 * D)
        _flag('flag_r', c + Vector((0.9 * D, 0.3 * D, 0.35 * D)), c, 0.35 * D * contrast, 1.6 * D)
        _flag('flag_front', c + Vector((0, -1.1 * D, 0.15 * D)), c, 1.2 * D, 0.22 * D * contrast)


def world(value=1.0, strips=6, strip_dark=0.97, strip_width=0.42, top=1.8, below=0.3):
    """A procedural light tent: very bright overhead, a bright wall around the piece broken by darker
    vertical seams (they give diamonds their black-and-white facet pattern), and a dim table below.
    The camera never sees this; it only lights and reflects."""
    w = bpy.data.worlds.new('studio')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    N = nt.nodes; Ln = nt.links
    bg = N['Background']
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    Ln.new(tc.outputs['Generated'], sep.inputs[0])

    def math_(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                Ln.new(v, n.inputs[i])
        return n.outputs[0]

    def smooth(x, lo, hi):
        n = N.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'
        n.inputs['From Min'].default_value = lo; n.inputs['From Max'].default_value = hi
        Ln.new(x, n.inputs['Value'])
        return n.outputs[0]

    x, y, z = sep.outputs
    az = math_('ARCTAN2', y, x)
    wave = math_('SINE', math_('MULTIPLY', az, float(strips)))
    wave01 = math_('ADD', math_('MULTIPLY', wave, 0.5), 0.5)
    seam = smooth(wave01, strip_width, strip_width - 0.08)          # 1 inside a dark seam
    wall = math_('MULTIPLY', math_('SUBTRACT', 1.0, math_('MULTIPLY', seam, strip_dark)), value)
    topm = smooth(z, 0.25, 0.65)
    lit = math_('ADD', math_('MULTIPLY', wall, math_('SUBTRACT', 1.0, topm)), math_('MULTIPLY', topm, top))
    belowm = smooth(z, -0.05, -0.25)
    v = math_('ADD', math_('MULTIPLY', lit, math_('SUBTRACT', 1.0, belowm)), math_('MULTIPLY', belowm, below))
    Ln.new(v, bg.inputs['Strength'])
    bg.inputs['Color'].default_value = (1, 1, 1, 1)


def floor(z, size):
    """Shadow catcher: only the piece's soft shadow ends up in the image."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    o = bpy.context.object
    o.name = 'floor'
    o.is_shadow_catcher = True
    # diamonds must not see (or refract) the catcher, or they turn see-through in the composite
    o.visible_glossy = False
    o.visible_transmission = False
    return o


def camera(centre, radius, elevation=35, azimuth=0, lens=100, fill=0.62, aspect=1.0):
    """Point a long lens at the piece from (elevation, azimuth) degrees and back off until the piece's
    bounding sphere fills `fill` of the frame's shorter side."""
    cam = bpy.data.cameras.new('cam')
    cam.lens = lens
    cam.sensor_width = 36
    cam.clip_start = 1
    cam.clip_end = 1e5
    o = bpy.data.objects.new('cam', cam)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.scene.camera = o
    fov = 2 * math.atan(36 / 2 / lens)
    if aspect > 1:        # landscape: the shorter side is the height
        fov = 2 * math.atan(math.tan(fov / 2) / aspect)
    dist = radius / math.sin(fov / 2 * fill)
    e, a = math.radians(elevation), math.radians(azimuth)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    o.location = Vector(centre) + d * dist
    o.rotation_euler = (Vector(centre) - o.location).to_track_quat('-Z', 'Y').to_euler()
    return o


def settings(width, height, samples=256, bounces=24):
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = width, height
    s.render.resolution_percentage = 100
    s.render.film_transparent = True
    s.view_settings.view_transform = 'AgX'
    s.view_settings.look = 'AgX - High Contrast'
    c = s.cycles
    c.device = 'CPU'
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.01
    c.use_denoising = os.environ.get('BRR_DENOISE', '1') == '1'
    c.max_bounces = bounces
    c.transmission_bounces = bounces
    c.glossy_bounces = bounces // 2
    c.diffuse_bounces = 3
    c.transparent_max_bounces = 8
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.0
    s.render.image_settings.file_format = 'PNG'
    s.render.image_settings.color_mode = 'RGBA'


def composite(png, out_jpg, bg=(245, 245, 245), shadow=0.55):
    """Put the transparent render on a flat background colour, keeping the soft contact shadow."""
    from PIL import Image, ImageFilter
    im = Image.open(png).convert('RGBA')
    a = np.asarray(im).astype(np.float32) / 255
    rgb, alpha = a[..., :3], a[..., 3:4]
    base = np.array(bg, np.float32)[None, None] / 255
    # the catcher leaves a faint uniform alpha across the whole floor: measure it at the border and
    # remove it so the background is exactly `bg`, keeping only the real contact shadow
    edge = np.concatenate([alpha[:8].ravel(), alpha[-8:].ravel(), alpha[:, :8].ravel(), alpha[:, -8:].ravel()])
    floor_a = float(np.median(edge))
    alpha = np.clip((alpha - floor_a) / max(1 - floor_a, 1e-3), 0, 1)
    # shadow-catcher pixels are pure black with partial alpha; scale those down by `shadow`
    dark = 1 - np.clip(rgb.max(axis=2, keepdims=True) / 0.05, 0, 1)
    eff = alpha * (1 - dark * (1 - shadow))
    out = rgb * eff + base * (1 - eff)
    res = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))
    res = res.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    res.save(out_jpg, quality=94)
    return out_jpg

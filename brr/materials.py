"""Materials: diamond (with dispersion), gold colours."""
import bpy

# linear-space base colours, tuned to look like real alloys under the studio light
METALS = {
    'yellow_14k': (0.90, 0.67, 0.30),
    'yellow_18k': (0.95, 0.69, 0.24),
    'white':      (0.86, 0.86, 0.84),
    'platinum':   (0.80, 0.80, 0.79),
    'rose':       (0.95, 0.60, 0.48),
}


def _principled(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes['Principled BSDF']


def metal(kind='yellow_14k', roughness=0.12):
    m, p = _principled(f'metal_{kind}')
    p.inputs['Base Color'].default_value = (*METALS[kind], 1)
    p.inputs['Metallic'].default_value = 1.0
    p.inputs['Roughness'].default_value = roughness
    return m


def diamond(fire=1.0, tint=(1, 1, 1)):
    """Lab-grown or natural, a diamond is a diamond optically: IOR 2.417, Abbe number about 55.
    `fire` scales dispersion (1 = physical)."""
    m, p = _principled('diamond')
    p.inputs['Base Color'].default_value = (*tint, 1)
    p.inputs['Metallic'].default_value = 0.0
    p.inputs['Roughness'].default_value = 0.0
    p.inputs['IOR'].default_value = 2.417
    p.inputs['Transmission Weight'].default_value = 1.0
    p.inputs['Transmission Dispersion Abbe Number'].default_value = 55.0
    p.inputs['Transmission Dispersion Scale'].default_value = fire
    return m

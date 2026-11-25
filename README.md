# Belle Rosy product renders

Studio-style 3D renders of Belle Rosy jewelry from a short YAML description of each piece. The look is
a soft light-grey background, a light-tent lighting setup for bright, crisp diamonds, and real gold
colours. Everything is built in code with Blender's Python module (`bpy`), so each piece takes a few
lines of config rather than a 3D model.

## Setup

```bash
pip install bpy pyyaml numpy pillow    # bpy needs the Python version it was built for (3.13 for bpy 5.3)
```

## Render

```bash
python render.py configs/RG-14Y-TBD-002.yaml --preview      # small and quick (about 30 s), to check framing
python render.py configs/RG-14Y-TBD-002.yaml                # full quality, every view in the config
python render.py configs/RG-14Y-TBD-002.yaml --view front   # one view
python render.py configs/*.yaml                             # the whole catalogue
```

Each view is saved as `renders/<sku>/<sku>-<view>.jpg`, on the background colour and ready for Shopify,
Etsy and Instagram. A transparent `.png` is saved next to it. A full 1600 × 1600 render takes roughly 10–25 minutes on a 2-core CPU (much less on a laptop with a GPU or
more cores); use `--preview` while adjusting a config.

## Describing a piece

```yaml
sku: RG-14Y-TBD-002
type: solitaire_ring          # solitaire_ring | eternity_ring | tennis_bracelet | stud_earrings | drop_earrings
stone: {shape: pear, carat: 2.0}     # or length/width in mm, or diameter
metal: yellow_14k             # yellow_14k | yellow_18k | white | platinum | rose
prong_metal: white            # optional, if the prongs differ from the band
ring_size: 6
views:
  front: {elevation: 58, azimuth: 0}   # degrees; lens and fill are optional too
```

Shapes: `round`, `pear`, `marquise`, `oval`, `emerald`, `radiant`, `asscher`, `cushion`.
Carat weight is turned into millimetres with typical proportions for each shape (see
`brr/pieces.py: CARAT_MM`). Give `length`/`width` instead if the certificate lists measurements.

Per piece type:

| type | main options |
|---|---|
| `solitaire_ring` | `stone`, `ring_size`, `band_width`, `band_thickness`, `setting_height`, `prongs` (outline fractions), `prong_radius`, `stone.rotate` |
| `eternity_ring` | `stone` (+ `angle`), `count`, `coverage` (1 = full eternity), `ring_size` |
| `tennis_bracelet` | `stone` or a repeating `stones` list (each with `angle`), `stone_angle`, `count`, `length_in`, `gap`, `clasp` |
| `stud_earrings` | `stone`, `spacing`, `prongs` |
| `drop_earrings` | `stones` (top to bottom), `spacing`, `gap` |

Studio options go under `studio:`, e.g. `background: [245, 245, 245]`, `samples`, `fill`, `world` (light-tent
brightness), `brightness`.

## How it works

- `brr/gems.py`: faceted stones. Rings of points (girdle, crown, table, pavilion, culet) are placed on
  the stone's outline and wrapped in a convex hull, which gives brilliant facets for round, pear,
  marquise and oval, and step facets for emerald and asscher.
- `brr/materials.py`: diamond (IOR 2.417 with dispersion for fire) and gold colours.
- `brr/pieces.py`: bands, prong heads, bracelets and earrings, all built in millimetres.
- `brr/studio.py`: a procedural light tent (bright overhead, a bright wall with dark seams that give the
  diamond its black-and-white facet pattern), soft boxes, a shadow-catcher floor, camera framing, and
  the final composite onto the background.

## A note on accuracy

A render should look like the piece the customer receives. Check each config against the real piece
(stone shapes and order, prong colour, band style) before using its images, and keep at least one real
photo or video in each listing.

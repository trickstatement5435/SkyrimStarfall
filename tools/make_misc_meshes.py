"""Door slab, paper note, journal, keycard meshes + paper texture."""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'kit')); sys.path.insert(0, os.path.dirname(__file__))
import nifkit, geom, dds
from PIL import Image, ImageDraw, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda n: nifkit.tex_path(n); TN = lambda n: nifkit.tex_path(n).replace('.dds', '_n.dds')
out = {}
# paper texture
rng = np.random.default_rng(3)
paper = np.full((256, 256, 3), (226, 218, 196), float) + rng.normal(0, 4, (256, 256, 1))
img = Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)
for y in range(30, 240, 12): d.line([(24, y), (24 + rng.integers(120, 210), y)], fill=(70, 70, 80), width=2)
d.rectangle([20, 8, 90, 20], fill=(200, 110, 40))
img = img.filter(ImageFilter.GaussianBlur(0.6))
dds.write(f'{ROOT}/data/textures/StarfallSite/kit/paper.dds', np.asarray(img), 'bc1')
n = np.zeros((16, 16, 4), np.uint8); n[..., :2] = 128; n[..., 2] = 255; n[..., 3] = 20
dds.write(f'{ROOT}/data/textures/StarfallSite/kit/paper_n.dds', n, 'rgba')
# keycard texture
card = Image.new('RGB', (128, 64), (230, 230, 225)); d = ImageDraw.Draw(card)
d.rectangle([0, 0, 127, 14], fill=(210, 110, 30)); d.rectangle([6, 22, 40, 56], fill=(120, 120, 130)); d.text((48, 24), 'WING B', fill=(30, 30, 30)); d.text((48, 40), 'LEVEL 3', fill=(30, 30, 30))
dds.write(f'{ROOT}/data/textures/StarfallSite/kit/keycard.dds', np.asarray(card.resize((128, 64))), 'bc1')
def write(name, shapes, col, mat, item=False, folder='props'):
    path = f'{ROOT}/data/meshes/StarfallSite/{folder}/{name}.nif'
    r = nifkit.write_nif(path if not item else f'{ROOT}/build/{name}_s.nif', shapes, col, material=mat)
    if item: os.system(f'{ROOT}/bin/item_fix {ROOT}/build/{name}_s.nif {path} - > /dev/null')
    out[name] = [*r['min'], *r['max']]
# load door slab: 236 wide, 250 tall, 20 thick, origin bottom centre, faces +Y/-Y
slab = geom.box((-118, -10, 0), (118, 10, 250), uv='fit')
frame = geom.merge(geom.box((-128, -14, 0), (-118, 14, 256)), geom.box((118, -14, 0), (128, 14, 256)), geom.box((-128, -14, 250), (128, 14, 262)))
write('door_slab', [nifkit.shape('Door', slab, [T('door_heavy'), TN('door_heavy')], spec=0.6, gloss=40),
                    nifkit.shape('Frame', frame, [T('hazard_stripes'), TN('hazard_stripes')], spec=0.3)], [nifkit.box_col((-128, -14, 0), (128, 14, 262), 'metal_heavy')], 'metal_heavy')
note = geom.box((-7, -10, 0), (7, 10, 0.3), uv='fit')
write('note_paper', [nifkit.shape('Paper', note, [T('paper'), TN('paper')], spec=0.0)], [nifkit.box_col((-7, -10, 0), (7, 10, 1), 'cloth')], 'cloth', item=True)
journal = geom.merge(geom.box((-9, -12, 0), (9, 12, 3.5), uv='fit'))
write('journal', [nifkit.shape('Cover', journal, [T('canvas'), TN('canvas')], spec=0.1)], [nifkit.box_col((-9, -12, 0), (9, 12, 3.5), 'cloth')], 'cloth', item=True)
keycard = geom.box((-4.3, -2.7, 0), (4.3, 2.7, 0.4), uv='fit')
write('keycard', [nifkit.shape('Card', keycard, [T('keycard'), TN('paper')], spec=0.4)], [nifkit.box_col((-4.3, -2.7, 0), (4.3, 2.7, 0.6), 'metal_light')], 'metal_light', item=True)
import json; json.dump(out, open(f'{ROOT}/build/misc_bounds.json', 'w')); print(out)

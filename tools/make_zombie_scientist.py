"""HL1-style zombie scientist (unrigged OBJ) -> draugr skin."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import fit_unrigged, pack, dds
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = f'{ROOT}/src_assets/329993/Down doder/Zombie'
K = 1.92
to_sky = lambda a: np.stack([-a[..., 0] * K, a[..., 2] * K, a[..., 1] * K], -1)
J = {}
for s, sx in (('L', 1), ('R', -1)):
    J.update({f'{s}UpperArm': (10.5 * sx, 58, 1), f'{s}Forearm': (14 * sx, 43, 2), f'{s}Hand': (16.5 * sx, 32, 4), f'{s}HandEnd': (19 * sx, 18, 5),
              f'{s}Thigh': (4.2 * sx, 34, 0), f'{s}Calf': (4.2 * sx, 18, 0), f'{s}Foot': (4.5 * sx, 3, -1), f'{s}FootEnd': (4.5 * sx, 0.5, 5)})
r = fit_unrigged.fit(f'{SRC}/Zombie.obj', to_sky, J, f'{ROOT}/vanilla/draugr_skeleton.json', [f'{ROOT}/vanilla/draugrmale.json'])
mats = {'Zombie_body.bmp.003': 'zsci_body', 'Zombie_chomper.bmp': 'zsci_chomper', 'Zombie_head.bmp.002': 'zsci_head', 'Zombie_leg.bmp': 'zsci_leg'}
for m, nm in mats.items():
    png = {'zsci_body': 'Zombie_body', 'zsci_chomper': 'Zombie_chomper', 'zsci_head': 'Zombie_head', 'zsci_leg': 'Zombie_leg'}[nm]
    im = Image.open(f'{SRC}/{png}.png').convert('RGBA'); w, h = im.size
    W_ = 1 << (max(w, h) * 4 - 1).bit_length(); H_ = 1 << (h * 4 - 1).bit_length()
    a = np.asarray(im.resize((w * 4, h * 4), Image.NEAREST).resize((min(W_, 1024), min(H_, 1024)), Image.BICUBIC)).copy(); a[..., 3] = 255
    dds.write(f'{ROOT}/data/textures/StarfallSite/creatures/{nm}.dds', a, 'bc1')
def slot(w):
    b = max(w, key=w.get)
    if 'Head' in b or 'Neck' in b: return 30
    if 'Hand' in b or 'Finger' in b: return 33
    return 32
shapes = []
for m, nm in mats.items():
    tris = [t for t, tm in zip(r['tris'], r['triMat']) if tm == m]
    if not tris: continue
    sl = []
    for t in tris:
        s = [slot(r['weights'][i]) for i in t]; sl.append(max(set(s), key=s.count))
    shapes.append(dict(name=nm, tex=[f'textures\\StarfallSite\\creatures\\{nm}.dds', 'textures\\StarfallSite\\scientists\\flat_n.dds', '', '', '', ''],
                       spec=0.3, gloss=15.0, flags=2 if nm == 'zsci_chomper' else 0, pos=r['pos'], nrm=r['nrm'], uv=r['uv'], weights=r['weights'], tris=tris, triSlots=sl))
pack.write(f'{ROOT}/build/zombie_scientist.bin', 'zombie_scientist', r['skel'], shapes)
os.system(f'{ROOT}/bin/skin2nif {ROOT}/build/zombie_scientist.bin {ROOT}/data/meshes/StarfallSite/creatures/zombie_scientist.nif')
if __name__ == '__main__':
    import cmp_body
    cmp_body.show(r['pos'], np.array(r['tris']), '/tmp/claude-0/-home-claude/a1cdc464-3eec-54ac-b03c-efe888f22d8f/scratchpad/zsci.png', [f'{ROOT}/vanilla/draugrmale.json'])

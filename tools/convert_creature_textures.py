"""Convert the supplied Valve VTF / PNG textures to Skyrim DDS (diffuse, _n normal + specular alpha, _g glow)."""
import os, sys, numpy as np
from PIL import Image
from srctools.vtf import VTF
sys.path.insert(0, os.path.dirname(__file__))
import dds
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = f'{ROOT}/src_assets'; OUT = f'{ROOT}/data/textures/StarfallSite'

def vtf(rel):
    with open(f'{SRC}/{rel}.vtf', 'rb') as f:
        v = VTF.read(f); v.load(); return np.asarray(v.get().to_PIL().convert('RGBA')).astype(np.float32)

def rs(a, size):
    return np.asarray(Image.fromarray(a.astype(np.uint8)).resize(size, Image.LANCZOS)).astype(np.float32)

def put(name, a, fmt):
    dds.write(f'{OUT}/{name}.dds', np.clip(a, 0, 255).astype(np.uint8), fmt); print('wrote', name, a.shape[:2], fmt)

def diffuse(name, rel, alpha=False):
    a = vtf(rel)
    if not alpha: a[..., 3] = 255
    put(name, a, 'bc3' if alpha else 'bc1'); return a

def normal(name, rel, size, spec=None, spec_scale=1.0):
    n = vtf(rel)
    if n.shape[:2] != size[::-1]: n = rs(n, size)
    if spec is None: s = n[..., 3] * spec_scale
    else:
        s = spec if spec.shape[:2] == n.shape[:2] else rs(np.dstack([spec] * 4), size)[..., 0]
        s = s * spec_scale
    n[..., 3] = np.clip(s, 0, 255)
    put(name + '_n', n, 'bc3')

Z = 'ModelsTex'
d = diffuse('creatures/zombie_classic', f'{Z}/Zombie_Classic/zombie_classic_sheet'); normal('creatures/zombie_classic', f'{Z}/Zombie_Classic/zombie_classic_sheet_normal', (1024, 1024), spec_scale=0.6)
d = diffuse('creatures/zombie_fast', f'{Z}/Zombie_Fast/fast_zombie_sheet', alpha=True); normal('creatures/zombie_fast', f'{Z}/Zombie_Fast/fast_zombie_sheet_normal', (1024, 1024), spec_scale=0.6)
d = diffuse('creatures/zombie_poison', f'{Z}/Zombie_Poison/poisonzombie_sheet'); normal('creatures/zombie_poison', f'{Z}/Zombie_Poison/poisonzombie_sheet_normal', (1024, 1024), spec_scale=0.6)
H = 'HeadcrabTex/HeadcrabTex'
diffuse('creatures/headcrab_classic', f'{H}/headcrabsheet'); normal('creatures/headcrab_classic', f'{H}/headcrabsheet_normal', (512, 512), spec_scale=0.8)
diffuse('creatures/headcrab_fast', f'{H}/Headcrab/allinonebacup2'); normal('creatures/headcrab_fast', f'{H}/Headcrab/allinonebacup2_normal', (512, 512), spec=vtf(f'{H}/Headcrab/allinonebacup2_phong')[..., 0], spec_scale=0.6)
diffuse('creatures/headcrab_black', f'{H}/HEADCRAB_BLACK/blackcrab_sheet'); normal('creatures/headcrab_black', f'{H}/HEADCRAB_BLACK/blackcrab_sheet_normal', (512, 512), spec_scale=0.5)
diffuse('creatures/headcrab_hairs', f'{H}/HEADCRAB_BLACK/hairs', alpha=True)
diffuse('props/headcrab_canister', f'{H}/headcrabcannister01b'); normal('props/headcrab_canister', f'{H}/headcrabcannister01b_normal', (1024, 1024), spec_scale=1.0)
diffuse('props/headcrab_prep', f'{H}/headcrabprep_sheet')
C = 'Combine_soldierTex/Combine_soldier'
for nm, base, nrm, phong, tint in [('combine', 'combinesoldiersheet', 'combinesoldier_normal', 'combinesoldier_phong', (0.35, 0.75, 1.0)),
                                   ('combine_warden', 'combinesoldiersheet_prisonguard', 'combinesoldiersheet_prisonguard_normal', 'combinesoldiersheet_prisonguard_grey', (1.0, 0.85, 0.15))]:
    b = vtf(f'{C}/{base}'); b2 = b.copy(); b2[..., 3] = 255
    put(f'guards/{nm}', b2, 'bc1')
    ph = vtf(f'{C}/{phong}')[..., 0]
    normal(f'guards/{nm}', f'{C}/{nrm}', (1024, 1024), spec=ph, spec_scale=0.9)
    mask = rs(vtf(f'{C}/combinesoldierselfillummask'), (1024, 1024))[..., 0:1] / 255.0
    glow = np.concatenate([np.clip(b[..., :3] * 0.4 + 255 * np.array(tint) * 0.6, 0, 255) * mask, np.full(mask.shape, 255.0)], 2)
    put(f'guards/{nm}_g', glow, 'bc1')
# HL1 scientist textures (tiny, 8-bit) -> upscale x4 with nearest-then-smooth so they stay crisp
S = f'{SRC}/350646/Scientist (HD)'
for f in sorted(os.listdir(S)):
    if not f.endswith('.png'): continue
    im = Image.open(f'{S}/{f}').convert('RGBA'); w, h = im.size
    W = 1 << max(1, (max(w, h) * 4 - 1).bit_length()); H_ = W if h > w * 0.75 else W // 2
    big = im.resize((w * 4, h * 4), Image.NEAREST).resize((W, H_), Image.BICUBIC)
    a = np.asarray(big).astype(np.float32); a[..., 3] = 255
    put('scientists/' + f[:-4].replace(' ', '_').lower(), a, 'bc1')

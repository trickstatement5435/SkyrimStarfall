"""HL scientist (DAE) -> Skyrim human armor pieces: lab-coat body (slots 32/33/37) + four heads (slots 30/31)."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import daeskin, retarget, pack
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = f'{ROOT}/vanilla/human_skeleton.json'
DAE = f'{ROOT}/src_assets/350646/Scientist (HD)/scientist.dae'
EXTRA = {r'(^|_)tie\d': 'NPC Spine2 [Spn2]', r'Mouth|Dummy05': 'NPC Head [Head]', r'needle': 'NPC R Hand [RHnd]'}
TEX = {'DC_sci_body_BMP-material': 'dc_sci_body', 'DC_sci_coat_BMP-material': 'dc_sci_coat', 'DC_sci_hands_BMP-material': 'dc_sci_hands',
       'slick_face_bmp-material': 'slick_face', 'slick_top_bmp-material': 'slick_top', 'luther_head_bmp-material': 'luther_head',
       'luther_top_bmp-material': 'luther_top', 'einstein_head_bmp-material': 'einstein_head', 'einstein_top_bmp-material': 'einstein_top',
       'walter_head_bmp-material': 'walter_head', 'walter_top_bmp-material': 'walter_top', 'sci_mouth_BMP-material': 'sci_mouth'}
GIRTH = float(os.environ.get('GIRTH', 1.1))
def build(geoms, out, slotfn, variants=None):
    m = daeskin.load(DAE, geometries=geoms)
    r = retarget.retarget(m, SK, extra_map=EXTRA, girth=GIRTH, girth_map={r'^(Pelvis|Spine)': 1.45, r'Spine4|Spine2': 1.5, r'Clavicle|UpperArm': 1.35, r'Forearm': 1.2, r'Thigh': 1.3, r'Calf': 1.15, r'Neck1': 1.2, r'Head1': 1.1})
    shapes = []
    for me in m['meshes']:
        tris = me['tris']
        slots = []
        for t in tris:
            s = [slotfn(r['weights'][v]) for v in t]; slots.append(max(set(s), key=s.count))
        tx = TEX[me['material']]
        shapes.append(dict(name=f'{me["model"]}_{tx}'.replace('(', '').replace(')', ''), tex=[f'textures\\StarfallSite\\scientists\\{tx}.dds', 'textures\\StarfallSite\\scientists\\flat_n.dds', '', '', '', ''],
                           spec=0.15, gloss=10.0, flags=0, pos=r['pos'], nrm=r['nrm'], uv=r['uv'], weights=r['weights'], tris=tris, triSlots=slots))
    pack.write(f'{ROOT}/build/{out}.bin', out, r['skel'], shapes)
    for g in '01':
        os.system(f'{ROOT}/bin/skin2nif {ROOT}/build/{out}.bin {ROOT}/data/meshes/StarfallSite/scientists/{out}_{g}.nif > /dev/null')
    return m, r
def body_slot(w):
    b = max(w, key=w.get)
    if 'Hand' in b or 'Finger' in b: return 33
    if 'Foot' in b or 'Toe' in b: return 37
    return 32
m, r = build(['dc_sci_(headless_body)'], 'labcoat', body_slot)
heads = {}
for g, nm in [('dc_sci_(head_SLICK)', 'head_slick'), ('dc_sci_(head_LUTHER)', 'head_luther'), ('dc_sci_(head_EINSTEIN)', 'head_einstein'), ('dc_sci_(head_NERD)', 'head_walter')]:
    heads[nm] = build([g], nm, lambda w: 30)
# flat normal map shared by the low-poly HL1 parts
import dds
n = np.zeros((16, 16, 4), np.uint8); n[..., 0] = 128; n[..., 1] = 128; n[..., 2] = 255; n[..., 3] = 40
dds.write(f'{ROOT}/data/textures/StarfallSite/scientists/flat_n.dds', n, 'rgba')
if __name__ == '__main__':
    import cmp_body
    allP = [r['pos']]; allT = [np.array([t for me in m['meshes'] for t in me['tris']])]
    off = len(r['pos'])
    mh, rh = heads['head_einstein']
    allP.append(rh['pos']); allT.append(np.array([t for me in mh['meshes'] for t in me['tris']]) + off)
    B = '/home/claude/MasterChief/bodies/'
    cmp_body.show(np.concatenate(allP), np.concatenate(allT), '/tmp/claude-0/-home-claude/a1cdc464-3eec-54ac-b03c-efe888f22d8f/scratchpad/sci_cmp.png', [B + 'malebody_1.json', B + 'malehands_1.json', B + 'malefeet_1.json'])

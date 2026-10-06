"""HL2 zombies -> draugr-skeleton creature skins (slots 30 head, 32 body, 33 hands)."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import srcmdl, retarget, pack
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = f'{ROOT}/vanilla/draugr_skeleton.json'
HC = {r'\.HC|Headcrab': 'NPC Head [Head]'}
VARIANTS = {
    'zombie_classic': dict(src='classic', tex={'Zombie_Classic_sheet': 'zombie_classic', 'headcrabsheet': 'headcrab_classic'}, skip=[], flags={}),
    'zombie_fast': dict(src='fast', tex={'fast_zombie_sheet': 'zombie_fast', 'allinonebacup2': 'headcrab_fast'}, skip=[], flags={'zombie_fast': 1 | 2}),
    'zombie_poison': dict(src='poison', tex={'PoisonZombie_sheet': 'zombie_poison', 'Blackcrab_sheet': 'headcrab_black'}, skip=['headcrab5', 'headcrab1'],
                          extra={r'Headcrab_Cube|HC5_|HCB_|\.bone': 'NPC Spine2 [Spn2]'}, flags={}),
}
def slot(w):
    b = max(w, key=w.get)
    if 'Head' in b or 'Neck' in b: return 30
    if 'Hand' in b or 'Finger' in b: return 33
    return 32
out = {}
for name, v in VARIANTS.items():
    m = srcmdl.load(f'{ROOT}/src_assets/Zombie/Zombie/{v["src"]}')
    r = retarget.retarget(m, SK, extra_map=v.get('extra', HC), girth=1.12, scale_from='hip',
                          girth_map={r'^(Pelvis|Spine)': 1.2, r'Spine4|Spine2': 1.2, r'UpperArm|Thigh': 1.15})
    shapes = []
    for me in m['meshes']:
        if me['bodypart'] in v['skip'] or not me['tris']: continue
        tx = v['tex'][me['material']]
        tris = me['tris']; sl = []
        for t in tris:
            s = [slot(r['weights'][i]) for i in t]; sl.append(max(set(s), key=s.count))
        shapes.append(dict(name=f'{name}_{me["bodypart"]}', tex=[f'textures\\StarfallSite\\creatures\\{tx}.dds', f'textures\\StarfallSite\\creatures\\{tx}_n.dds', '', '', '', ''],
                           spec=0.8, gloss=25.0, flags=v['flags'].get(tx, 0), pos=r['pos'], nrm=r['nrm'], uv=r['uv'], weights=r['weights'], tris=tris, triSlots=sl))
        print(' ', name, me['bodypart'], tx, len(tris))
    pack.write(f'{ROOT}/build/{name}.bin', name, r['skel'], shapes)
    os.system(f'{ROOT}/bin/skin2nif {ROOT}/build/{name}.bin {ROOT}/data/meshes/StarfallSite/creatures/{name}.nif > /dev/null')
    out[name] = (r, shapes)
if __name__ == '__main__':
    import cmp_body
    for name, (r, shapes) in out.items():
        T = np.concatenate([np.array(s['tris']) for s in shapes])
        cmp_body.show(r['pos'], T, f'/tmp/claude-0/-home-claude/a1cdc464-3eec-54ac-b03c-efe888f22d8f/scratchpad/{name}.png', [f'{ROOT}/vanilla/draugrmale.json'])

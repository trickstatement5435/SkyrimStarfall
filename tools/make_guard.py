"""Combine soldier -> Skyrim human armor (full body + helmet, hides the head). Two variants share one mesh."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import srcmdl, retarget, pack
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = f'{ROOT}/vanilla/human_skeleton.json'
m = srcmdl.load(f'{ROOT}/src_assets/CombineSoldiers/combine_soldier')
r = retarget.retarget(m, SK, extra_map={r'Anim_Attachment_LH': 'NPC L Hand [LHnd]', r'Anim_Attachment_RH': 'NPC R Hand [RHnd]', r'Cod$': 'NPC Pelvis [Pelv]'},
                      girth=float(os.environ.get('GIRTH', 1.08)))
tris = [t for me in m['meshes'] for t in me['tris']]
def slot(w):
    b = max(w, key=w.get)
    if 'Head' in b: return 30
    if 'Hand' in b or 'Finger' in b: return 33
    if 'Foot' in b or 'Toe' in b: return 37
    return 32
slots = []
for t in tris:
    s = [slot(r['weights'][v]) for v in t]; slots.append(max(set(s), key=s.count))
for variant, tex in [('combine', 'combine'), ('combine_warden', 'combine_warden')]:
    sh = dict(name='CombineArmor', tex=[f'textures\\StarfallSite\\guards\\{tex}.dds', f'textures\\StarfallSite\\guards\\{tex}_n.dds', f'textures\\StarfallSite\\guards\\{tex}_g.dds', '', '', ''],
              spec=1.0, gloss=30.0, flags=4, emit=1.5, pos=r['pos'], nrm=r['nrm'], uv=r['uv'], weights=r['weights'], tris=tris, triSlots=slots)
    pack.write(f'{ROOT}/build/{variant}.bin', 'CombineArmor', r['skel'], [sh])
    for g in '01':
        os.system(f'{ROOT}/bin/skin2nif {ROOT}/build/{variant}.bin {ROOT}/data/meshes/StarfallSite/guards/{variant}_{g}.nif')
print({k: slots.count(k) for k in set(slots)})
import preview
preview.render(r['pos'], np.array(tris), '/tmp/claude-0/-home-claude/a1cdc464-3eec-54ac-b03c-efe888f22d8f/scratchpad/guard_fit.png')

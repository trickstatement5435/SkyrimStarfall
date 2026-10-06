"""HL2 headcrabs -> skeever-skeleton creature skins.
Body bones keep the crab's shape (uniform scale + one shared offset); limb bones are rotated/stretched so each crab
leg segment lies on the matching skeever leg segment. The NPC record scales the result down to headcrab size."""
import os, sys, re, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import srcmdl, pack, retarget
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = {k: np.array(v) for k, v in json.load(open(f'{ROOT}/vanilla/skeever_skeleton.json')).items()}
SJ = lambda n: SK[n][:3, 3]
FLIP = np.diag([-1.0, -1.0, 1.0])
K = 3.6

def limbs(side):
    s = side
    return {'arm': ([f'{s}Arm_Upper', f'{s}Arm_Forearm', f'{s}Arm_Palm']), 'leg': ([f'{s}Leg1', f'{s}Leg2', f'{s}Leg3', f'{s}LegAnkle'])}

SPECS = {
 'headcrab_classic': dict(src='headcrabclassic', tex={'headcrabsheet': 'headcrab_classic'},
    body={r'BodyControl': 'SpineLowerSpine', r'HipControl': 'Pelvis', r'SpineControl': 'SpineUpperSpine', r'HeadControl': 'Torso',
          r'Hole': 'SpineUpperSpine', r'Fang._Bone1': 'HEAD', r'Fang._Bone2': 'Jaw'},
    chains={'L': [('UpperArmL_Bone', 'LArm_Upper'), ('ForeArmL_Bone', 'LArm_Forearm')], 'R': [('UpperArmR_Bone', 'RArm_Upper'), ('ForeArmR_Bone', 'RArm_Forearm')],
            'LL': [('ThighL_Bone', 'LLeg1'), ('CalfL_Bone', 'LLeg2')], 'RL': [('ThighR_Bone', 'RLeg1'), ('CalfR_Bone', 'RLeg2')]},
    anchor='SpineControl'),
 'headcrab_fast': dict(src='headcrab', tex={'allinonebacup2': 'headcrab_fast'},
    body={r'\.body$': 'SpineUpperSpine', r'chest': 'Torso', r'hips': 'Pelvis', r'wiggle_front': 'Neck', r'wiggle|whole': 'SpineUpperSpine', r'clav_L': 'LArm_Clavicle', r'clav_R': 'RArm_Clavicle'},
    chains={'L': [('arm_bone1_L', 'LArm_Upper'), ('arm_bone2_L', 'LArm_Forearm')], 'R': [('arm_bone1_R', 'RArm_Upper'), ('arm_bone2_R', 'RArm_Forearm')],
            'LL': [('leg_bone1_L', 'LLeg1'), ('leg_bone2_L', 'LLeg2'), ('leg_bone3_L', 'LLeg3')], 'RL': [('leg_bone1_R', 'RLeg1'), ('leg_bone2_R', 'RLeg2'), ('leg_bone3_R', 'RLeg3')]},
    anchor='body'),
 'headcrab_black': dict(src='headcrabblack', tex={'Blackcrab_sheet': 'headcrab_black', 'hairs': 'headcrab_hairs'},
    body={r'\.body$': 'SpineUpperSpine', r'\.torso$': 'Torso', r'\.teeth$': 'HEAD', r'teeth_bone': 'Jaw', r'hips': 'Pelvis', r'deform_Front': 'Neck',
          r'deform|whole': 'SpineUpperSpine', r'clavical_bone_L': 'LArm_Clavicle', r'clavical_bone_R': 'RArm_Clavicle'},
    chains={'L': [('arm_bone1_L', 'LArm_Upper'), ('arm_bone2_L', 'LArm_Forearm')], 'R': [('arm_bone1_R', 'RArm_Upper'), ('arm_bone2_R', 'RArm_Forearm')],
            'LL': [('leg_bone1_L', 'LLeg1'), ('leg_bone2_L', 'LLeg2')], 'RL': [('leg_bone1_R', 'RLeg1'), ('leg_bone2_R', 'RLeg2')]},
    anchor='body'),
}
NEXT = {'LArm_Upper': 'LArm_Forearm', 'LArm_Forearm': 'LArm_Palm', 'RArm_Upper': 'RArm_Forearm', 'RArm_Forearm': 'RArm_Palm',
        'LLeg1': 'LLeg2', 'LLeg2': 'LLeg3', 'LLeg3': 'LLegAnkle', 'RLeg1': 'RLeg2', 'RLeg2': 'RLeg3', 'RLeg3': 'RLegAnkle'}
END = {'LLeg2': 'LLegAnkle', 'RLeg2': 'RLegAnkle'}   # a 2-bone crab leg spans the skeever calf + foot

def build(name, sp):
    m = srcmdl.load(f'{ROOT}/src_assets/Headcrabs/Headcrabs/{sp["src"]}')
    names = [b['name'] for b in m['bones']]
    VJ = [FLIP @ b['world'][:3, 3] * K for b in m['bones']]
    P0 = np.array([FLIP @ np.array(v['pos']) * K for v in m['verts']])
    N0 = np.array([FLIP @ np.array(v['nrm']) for v in m['verts']])
    ai = next(i for i, n in enumerate(names) if re.search(sp['anchor'] + '$', n))
    t_body = SJ('SpineUpperSpine') - VJ[ai]
    bone_xf, bone_sky = {}, {}
    for i, n in enumerate(names):
        for pat, tgt in sp['body'].items():
            if re.search(pat, n): bone_xf[i] = (np.eye(3), t_body); bone_sky[i] = tgt; break
    for chain in sp['chains'].values():
        for ci, (src, tgt) in enumerate(chain):
            i = next(j for j, n in enumerate(names) if n.endswith(src))
            a = VJ[i]
            if ci + 1 < len(chain):
                b = VJ[next(j for j, n in enumerate(names) if n.endswith(chain[ci + 1][0]))]
            else:  # last bone: tip = farthest vertex mostly weighted to it
                own = [k for k, v in enumerate(m['verts']) if v['w'].get(i, 0) > 0.5]
                b = P0[own][np.argmax(np.linalg.norm(P0[own] - a, axis=1))]
            sa = SJ(tgt); sb = SJ(END.get(tgt, NEXT[tgt]) if ci + 1 == len(chain) else NEXT[tgt])
            R = retarget.rot_between(b - a, sb - sa); d = (b - a) / np.linalg.norm(b - a)
            st = np.clip(np.linalg.norm(sb - sa) / np.linalg.norm(b - a), 0.5, 3.0)
            A = R @ (np.eye(3) * 1.0 + np.outer(d, d) * (st - 1.0))
            bone_xf[i] = (A, sa - A @ a); bone_sky[i] = tgt
    # anything left: follow the parent
    for i, b in enumerate(m['bones']):
        j = i
        while j not in bone_xf and m['bones'][j]['parent'] >= 0: j = m['bones'][j]['parent']
        if i not in bone_xf: bone_xf[i] = bone_xf.get(j, (np.eye(3), t_body)); bone_sky[i] = bone_sky.get(j, 'SpineUpperSpine')
    P, N, W = [], [], []
    for p, n, v in zip(P0, N0, m['verts']):
        w = v['w'] or {0: 1.0}; tot = sum(w.values())
        A = sum(bone_xf[b][0] * ww / tot for b, ww in w.items()); t = sum(bone_xf[b][1] * ww / tot for b, ww in w.items())
        P.append(A @ p + t); nn = np.linalg.inv(A).T @ n; N.append(nn / (np.linalg.norm(nn) + 1e-9))
        acc = {}
        for b, ww in w.items(): acc[bone_sky[b]] = acc.get(bone_sky[b], 0) + ww / tot
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]; s = sum(x for _, x in top)
        W.append({b: x / s for b, x in top if x / s > 0.005})
    P = np.array(P); UV = np.array([v['uv'] for v in m['verts']])
    shapes = []
    for me in m['meshes']:
        if not me['tris']: continue
        tx = sp['tex'][me['material']]
        hairs = tx == 'headcrab_hairs'
        shapes.append(dict(name=f'{name}_{tx}', tex=[f'textures\\StarfallSite\\creatures\\{tx}.dds', '' if hairs else f'textures\\StarfallSite\\creatures\\{tx}_n.dds', '', '', '', ''],
                           spec=0.0 if hairs else 0.9, gloss=30.0, flags=(8 | 2) if hairs else 0, pos=P, nrm=np.array(N), uv=UV, weights=W, tris=me['tris'], triSlots=[32] * len(me['tris'])))
    pack.write(f'{ROOT}/build/{name}.bin', name, SK, shapes)
    os.system(f'{ROOT}/bin/skin2nif {ROOT}/build/{name}.bin {ROOT}/data/meshes/StarfallSite/creatures/{name}.nif > /dev/null')
    used = np.unique(np.concatenate([np.array(me['tris']).ravel() for me in m['meshes'] if me['tris']]))
    print(name, 'bbox', P[used].min(0).round(1), P[used].max(0).round(1))
    return P, [t for me in m['meshes'] for t in me['tris']]

if __name__ == '__main__':
    import cmp_body
    for name, sp in SPECS.items():
        P, T = build(name, sp)
        cmp_body.show(P, T, f'/tmp/claude-0/-home-claude/a1cdc464-3eec-54ac-b03c-efe888f22d8f/scratchpad/{name}.png', [f'{ROOT}/vanilla/skeever.json'])

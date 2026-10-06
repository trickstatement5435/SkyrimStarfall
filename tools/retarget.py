"""Retarget a ValveBiped-rigged mesh (srcmdl / daeskin structure) onto a Skyrim humanoid skeleton.

Each Valve bone maps to a Skyrim bone. Every Valve bone gets a transform that carries its segment
(joint -> child joint) onto the matching Skyrim segment: rotate onto the Skyrim bone direction, stretch along the
bone so joints meet, uniform scale k elsewhere. Vertices are moved with Valve's own skin weights (linear blend),
then take the mapped Skyrim bone weights. Source space: inches, Z up, faces -Y, left = +X -> rotate 180 about Z."""
import json, re, numpy as np

def canon(name):
    n = name.split('.')[-1]
    n = re.sub(r'^Bip01_?', '', n)
    return {'Spine3': 'Spine4', 'Neck': 'Neck1', 'Head': 'Head1', '': 'Root'}.get(n, n)

def sky_names(skel):
    f = lambda pat: next(k for k in skel if re.fullmatch(pat, k))
    m = {}
    for s in 'LR':
        m[f'{s}_Clavicle'] = f'NPC {s} Clavicle [{s}Clv]'; m[f'{s}_UpperArm'] = f'NPC {s} UpperArm [{s}Uar]'
        m[f'{s}_Forearm'] = f'NPC {s} Forearm [{s}Lar]'; m[f'{s}_Hand'] = f'NPC {s} Hand [{s}Hnd]'
        m[f'{s}_Thigh'] = f'NPC {s} Thigh [{s}Thg]'; m[f'{s}_Calf'] = f'NPC {s} Calf [{s}Clf]'
        m[f'{s}_Foot'] = f(rf'NPC {s} Foot \[{s}L?ft \]'); m[f'{s}_Toe0'] = f'NPC {s} Toe0 [{s}Toe]'
        for fi in range(5):
            for j, suf in enumerate(['', '1', '2']):
                m[f'{s}_Finger{fi}{suf}'] = f'NPC {s} Finger{fi}{j} [{s}F{fi}{j}]'
    m.update({'Pelvis': 'NPC Pelvis [Pelv]', 'Root': 'NPC Pelvis [Pelv]', 'Spine': 'NPC Spine [Spn0]', 'Spine1': 'NPC Spine1 [Spn1]',
              'Spine2': 'NPC Spine2 [Spn2]', 'Spine4': 'NPC Spine2 [Spn2]', 'Neck1': 'NPC Neck [Neck]', 'Head1': 'NPC Head [Head]'})
    return m

# segment end for direction: canonical name -> canonical child (first that exists)
CHILD = {'Pelvis': ['Spine'], 'Spine': ['Spine1'], 'Spine1': ['Spine2'], 'Spine2': ['Spine4', 'Neck1'], 'Spine4': ['Neck1'],
         'Neck1': ['Head1']}
for s in 'LR':
    CHILD.update({f'{s}_Clavicle': [f'{s}_UpperArm'], f'{s}_UpperArm': [f'{s}_Forearm'], f'{s}_Forearm': [f'{s}_Hand'],
                  f'{s}_Hand': [f'{s}_Finger2', f'{s}_Finger1', f'{s}_Finger3'], f'{s}_Thigh': [f'{s}_Calf'],
                  f'{s}_Calf': [f'{s}_Foot'], f'{s}_Foot': [f'{s}_Toe0']})
    for fi in range(5):
        CHILD[f'{s}_Finger{fi}'] = [f'{s}_Finger{fi}1']; CHILD[f'{s}_Finger{fi}1'] = [f'{s}_Finger{fi}2']
SKY_CHILD = {'Spine2': 'Neck1', 'Spine4': 'Neck1'}
# bones that copy the transform of another (no own segment)
INHERIT = {'Head1': 'Neck1', 'Root': 'Pelvis'}
for s in 'LR':
    INHERIT.update({f'{s}_Toe0': f'{s}_Foot'})
    for fi in range(5): INHERIT[f'{s}_Finger{fi}2'] = f'{s}_Finger{fi}1'

def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-8:
        return np.eye(3) if c > 0 else -np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))

def retarget(model, skel_path, extra_map=None, girth=1.0, girth_map=None, scale_from='shoulder', stretch_limits=(0.6, 1.7), verbose=True):
    skel = {k: np.array(v) for k, v in json.load(open(skel_path)).items()}
    smap = sky_names(skel)
    SJ = lambda c: skel[smap[c]][:3, 3]
    flip = np.diag([-1.0, -1.0, 1.0])
    bones = model['bones']
    cn = [canon(b['name']) for b in bones]
    VJ = {}
    for b, c in zip(bones, cn):
        VJ.setdefault(c, flip @ b['world'][:3, 3])
    # zombies without neck/head bones: synthesize joints continuing the upper spine
    if 'Neck1' not in VJ and 'Spine4' in VJ:
        d = VJ['Spine4'] - VJ.get('Spine2', VJ['Spine4'] - np.array([0, 0, 1.0])); d /= np.linalg.norm(d)
        VJ['Neck1'] = VJ['Spine4'] + d * 3.0
    if 'Head1' not in VJ and 'Neck1' in VJ:
        d = VJ['Neck1'] - VJ['Spine4']; d /= np.linalg.norm(d)
        VJ['Head1'] = VJ['Neck1'] + d * 3.5
    # uniform scale from shoulder height above the floor
    jb = 'UpperArm' if scale_from == 'shoulder' else 'Thigh'
    vs = (VJ['L_' + jb][2] + VJ['R_' + jb][2]) / 2
    ss = (SJ('L_' + jb)[2] + SJ('R_' + jb)[2]) / 2
    k = ss / vs
    xf = {}
    for c in VJ:
        if c not in smap: continue
        ch = next((x for x in CHILD.get(c, []) if x in VJ and x in smap), None)
        if ch is None: continue
        skc = SKY_CHILD.get(c, ch)
        va, vb = VJ[c] * k, VJ[ch] * k
        sa, sb = SJ(c), SJ(skc)
        if smap[c] == smap[skc]: continue
        R = rot_between(vb - va, sb - sa)
        d = (vb - va) / np.linalg.norm(vb - va)
        st = np.clip(np.linalg.norm(sb - sa) / np.linalg.norm(vb - va), *stretch_limits)
        g = girth
        for pat, gv in (girth_map or {}).items():
            if re.search(pat, c): g = gv
        S = np.eye(3) * g + np.outer(d, d) * (st - g)
        A = R @ S
        xf[c] = (A, sa - A @ va, R)
    for c, src in INHERIT.items():
        if c in VJ and c not in xf and src in xf and c in smap:
            R = xf[src][2]; A = R * girth; xf[c] = (A, SJ(c) - A @ (VJ[c] * k), R)
    def bone_xf(c):
        while c not in xf:
            c = {'Head1': 'Neck1', 'Neck1': 'Spine4', 'Spine4': 'Spine2', 'Spine2': 'Spine1', 'Spine1': 'Spine'}.get(c, 'Pelvis') if c not in ('Pelvis',) else None
            if c is None: return (np.eye(3) * girth, np.zeros(3), np.eye(3))
        return xf[c]
    extra_map = extra_map or {}
    def sky_bone(c, full):
        for pat, tgt in extra_map.items():
            if re.search(pat, full): return tgt
        return smap.get(c, 'NPC Pelvis [Pelv]')
    def xf_for(i):
        full = bones[i]['name']
        for pat, tgt in extra_map.items():
            if re.search(pat, full):
                inv = {v: kk for kk, v in smap.items()}
                return bone_xf(inv.get(tgt, 'Pelvis'))
        return bone_xf(cn[i])
    BX = [xf_for(i) for i in range(len(bones))]
    SB = [sky_bone(cn[i], bones[i]['name']) for i in range(len(bones))]
    P, N, UV, W = [], [], [], []
    for v in model['verts']:
        p = flip @ np.array(v['pos']) * k; n = flip @ np.array(v['nrm'])
        w = v['w'] or {0: 1.0}
        tot = sum(w.values())
        A = sum(BX[b][0] * (ww / tot) for b, ww in w.items()); t = sum(BX[b][1] * (ww / tot) for b, ww in w.items())
        P.append(A @ p + t)
        nn = np.linalg.inv(A).T @ n; N.append(nn / (np.linalg.norm(nn) + 1e-9))
        UV.append(v['uv'])
        acc = {}
        for b, ww in w.items(): acc[SB[b]] = acc.get(SB[b], 0) + ww / tot
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]; s = sum(x for _, x in top)
        W.append({b: x / s for b, x in top if x / s > 0.005})
    if verbose:
        P_ = np.array(P); print('retarget k=%.3f bbox' % k, P_.min(0).round(1), P_.max(0).round(1))
    return dict(pos=np.array(P), nrm=np.array(N), uv=np.array(UV), weights=W, skel=skel)

def slot_for(w, head_slot=30):
    b = max(w, key=w.get)
    if 'Head' in b or 'Neck' in b and False: return head_slot
    if 'Hand' in b or 'Finger' in b: return 33
    if 'Foot' in b or 'Toe' in b or 'ft ]' in b: return 37
    return 32

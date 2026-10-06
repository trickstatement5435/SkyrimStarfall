"""Rig an unrigged humanoid OBJ onto a Skyrim skeleton: rigid limb segments moved from hand-measured source joints onto
the skeleton's bind joints (blended near joints), then bone weights copied from the nearest vanilla body vertices."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, '/home/claude/MasterChief/tools')
from skinlib import load_body
from retarget import rot_between

def load_obj(path):
    V, VT, F = [], [], []; mat = None
    for line in open(path):
        p = line.split()
        if not p: continue
        if p[0] == 'v': V.append(list(map(float, p[1:4])))
        elif p[0] == 'vt': VT.append(list(map(float, p[1:3])))
        elif p[0] == 'usemtl': mat = p[1]
        elif p[0] == 'f':
            c = [tuple(int(x) - 1 if x else -1 for x in (q.split('/') + [''])[:2]) for q in p[1:]]
            for k in range(1, len(c) - 1): F.append((mat, [c[0], c[k], c[k + 1]]))
    return np.array(V), np.array(VT), F

def fit(obj, to_sky, src_joints, skel_json, body_jsons, foot_name='NPC {s} Foot [{s}Lft ]'):
    V, VT, F = load_obj(obj)
    skel = {k: np.array(v) for k, v in json.load(open(skel_json)).items()}
    J = lambda n: skel[n][:3, 3]
    def sky(name, s):
        n = {'UpperArm': f'NPC {s} UpperArm [{s}Uar]', 'Forearm': f'NPC {s} Forearm [{s}Lar]', 'Hand': f'NPC {s} Hand [{s}Hnd]',
             'Thigh': f'NPC {s} Thigh [{s}Thg]', 'Calf': f'NPC {s} Calf [{s}Clf]', 'Foot': foot_name.format(s=s) if s == 'L' else f'NPC R Foot [Rft ]',
             'Toe': f'NPC {s} Toe0 [{s}Toe]'}
        if name == 'HandEnd': return J(n['Hand']) + (J(n['Hand']) - J(n['Forearm'])) * 0.6
        if name == 'FootEnd': return J(n['Toe'])
        return J(n[name])
    # corners -> output vertices (flat per-face corners keyed by position+uv+material)
    corner, P, UV, M, T, TM = {}, [], [], [], [], []
    for mat, f in F:
        tri = []
        for vi, ti in f:
            key = (vi, ti, mat)
            if key not in corner:
                corner[key] = len(P); P.append(V[vi]); UV.append(VT[ti] if ti >= 0 else (0, 0)); M.append(mat)
            tri.append(corner[key])
        T.append(tri); TM.append(mat)
    P = to_sky(np.array(P)); UV = np.array(UV, float); UV[:, 1] = 1 - UV[:, 1]
    SJ = {k: to_sky(np.array(v)[None])[0] for k, v in src_joints.items()}
    segs = []
    for s in 'RL':
        for a, b in [('UpperArm', 'Forearm'), ('Forearm', 'Hand'), ('Hand', 'HandEnd'), ('Thigh', 'Calf'), ('Calf', 'Foot'), ('Foot', 'FootEnd')]:
            c0, c1, s0, s1 = SJ[f'{s}{a}'], SJ[f'{s}{b}'], sky(a, s), sky(b, s)
            R = rot_between(c1 - c0, s1 - s0)
            st = np.linalg.norm(s1 - s0) / np.linalg.norm(c1 - c0)
            d = (c1 - c0) / np.linalg.norm(c1 - c0)
            A = R @ (np.eye(3) + np.outer(d, d) * (st - 1))
            segs.append(dict(name=s + a, c0=c0, c1=c1, A=A, t=s0 - A @ c0))
    sh_c = (SJ['RUpperArm'] + SJ['LUpperArm']) / 2; sh_s = (sky('UpperArm', 'R') + sky('UpperArm', 'L')) / 2
    hp_c = (SJ['RThigh'] + SJ['LThigh']) / 2; hp_s = (sky('Thigh', 'R') + sky('Thigh', 'L')) / 2
    def seg_dist(p, a, b):
        ab = b - a; t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1); return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)
    # torso: vertical stretch mapping hips->hips and shoulders->shoulders
    def torso(p):
        z0, z1 = hp_c[2], sh_c[2]; Z0, Z1 = hp_s[2], sh_s[2]
        out = p.copy(); out[:, 2] = Z0 + (p[:, 2] - z0) * (Z1 - Z0) / (z1 - z0)
        out[:, 1] += (hp_s[1] + sh_s[1]) / 2 - (hp_c[1] + sh_c[1]) / 2
        return out
    lateral = np.abs(P[:, 0])
    arm_x = np.abs(SJ['RUpperArm'][0]) * 0.92
    arm_zone = (lateral > arm_x) & (P[:, 2] < sh_c[2] + 3)
    leg_zone = P[:, 2] < hp_c[2]
    W = np.zeros((len(P), len(segs) + 1))
    for i, s in enumerate(segs):
        zone = arm_zone if s['name'][1:] in ('UpperArm', 'Forearm', 'Hand') else leg_zone
        side_ok = (P[:, 0] > 0) if s['name'][0] == 'R' else (P[:, 0] < 0)
        W[:, i] = np.where(zone & side_ok, np.exp(-(seg_dist(P, s['c0'], s['c1']) / 6.0) ** 2), 0.0)
    W[:, -1] = np.where(arm_zone | leg_zone, 1e-4, 1.0)
    W /= W.sum(1, keepdims=True)
    Pn = np.zeros_like(P)
    for i, s in enumerate(segs): Pn += W[:, i:i + 1] * (P @ s['A'].T + s['t'])
    Pn += W[:, -1:] * torso(P)
    body = sum([load_body(f) for f in body_jsons], [])
    BV = np.concatenate([b['verts'] for b in body]); BW = sum([b['weights'] for b in body], [])
    weights = []
    for p in Pn:
        d = np.linalg.norm(BV - p, axis=1); nn = np.argsort(d)[:6]; acc = {}
        for j in nn:
            for b, w in BW[j].items(): acc[b] = acc.get(b, 0) + w / (d[j] + 0.5)
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]; tot = sum(w for _, w in top)
        weights.append({b: w / tot for b, w in top if w / tot > 0.01})
    # normals: smooth per position
    N = np.zeros_like(Pn); Ti = np.array(T)
    fn = np.cross(Pn[Ti[:, 1]] - Pn[Ti[:, 0]], Pn[Ti[:, 2]] - Pn[Ti[:, 0]])
    keyp = {}
    for i, p in enumerate(Pn): keyp.setdefault(tuple(np.round(p, 3)), []).append(i)
    for k in range(3): np.add.at(N, Ti[:, k], fn)
    for idx in keyp.values():
        s = N[idx].sum(0); N[idx] = s
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    return dict(pos=Pn, nrm=N, uv=UV, tris=T, triMat=TM, weights=weights, skel=skel)

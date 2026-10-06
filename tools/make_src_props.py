"""Static NIFs from the supplied Source props: crashed headcrab canister (open variant) and the headcrab prep tray."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'kit'))
import srcmdl, nifkit
from scipy.spatial import ConvexHull
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = 1.0 / 0.7   # Source inches -> Skyrim units (1 unit ~ 1.43 cm; 1 inch = 2.54 cm)
def convert(src, out, tex, n_tex, scale, rot_deg=0.0, lift=0.0, sink=0.0, hull_split=1, mat='metal'):
    m = srcmdl.load(f'{ROOT}/src_assets/Headcrabs/Headcrabs/{src}')
    P = np.array([v['pos'] for v in m['verts']]) * scale
    N = np.array([v['nrm'] for v in m['verts']])
    a = np.radians(rot_deg); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    P = P @ R.T; N = N @ R.T
    UV = np.array([v['uv'] for v in m['verts']])
    T = np.array([t for me in m['meshes'] for t in me['tris']])
    used = np.unique(T); P[:, 2] += -P[used, 2].min() + lift - sink
    remap = -np.ones(len(P), int); remap[used] = np.arange(len(used))
    P, N, UV, T = P[used], N[used], UV[used], remap[T]
    # Source winding is clockwise-from-outside relative to Skyrim: flip if normals disagree with winding
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]); agree = np.mean(np.sum(fn * N[T].mean(1), 1) > 0)
    if agree < 0.5: T = T[:, [0, 2, 1]]
    # collision: convex hulls of slabs along the longest axis
    ax = np.argmax(P.max(0) - P.min(0)); edges = np.linspace(P[:, ax].min(), P[:, ax].max(), hull_split + 1)
    col = []
    for i in range(hull_split):
        sel = P[(P[:, ax] >= edges[i] - 1) & (P[:, ax] <= edges[i + 1] + 1)]
        if len(sel) >= 4: col.append(nifkit.hull_col(sel, mat))
    sh = dict(name=src, verts=P, normals=N, uvs=UV, tris=T, tex=[tex, n_tex], spec=0.6 if n_tex else 0.1, gloss=30.0)
    r = nifkit.write_nif(f'{ROOT}/data/meshes/StarfallSite/props/{out}.nif', [sh], col, material=mat)
    print(out, r['min'], r['max'], r['log'].split()[0], 'agree', round(agree, 2))
    return r
if __name__ == '__main__':
    import json
    b = {}
    b['headcrab_canister'] = convert('headcrabcannister01b', 'headcrab_canister', 'textures\\StarfallSite\\props\\headcrab_canister.dds', 'textures\\StarfallSite\\props\\headcrab_canister_n.dds', K, rot_deg=0, sink=18, hull_split=4)
    b['headcrab_prep'] = convert('headcrabprep', 'headcrab_prep', 'textures\\StarfallSite\\props\\headcrab_prep.dds', '', K, hull_split=1)
    json.dump({k: [*v['min'], *v['max']] for k, v in b.items()}, open(f'{ROOT}/build/src_props_bounds.json', 'w'))

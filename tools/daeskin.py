"""Collada skinned-mesh reader -> same structure as srcmdl.load(): bones (name, world bind), verts (pos,nrm,uv,w{bone:weight}),
meshes (geometry name, material, tris). Positions are in the DAE's units, bind-shape applied."""
import collada, numpy as np

def load(path, geometries=None):
    d = collada.Collada(path)
    bones, bidx, verts, meshes = [], {}, [], []
    for c in d.controllers:
        g = c.geometry
        if geometries and g.name not in geometries: continue
        names = list(c.weight_joints.data.ravel())
        local = []
        for j, nm in enumerate(names):
            if nm not in bidx:
                bidx[nm] = len(bones)
                bones.append(dict(name=nm, world=np.linalg.inv(np.array(c.joint_matrices[nm])), parent=-1))
            local.append(bidx[nm])
        BSM = np.array(c.bind_shape_matrix)
        W = c.weights.data.ravel()
        # per position vertex: list of (joint, weight)
        vw = []
        for entry in c.index:
            e = np.array(entry).reshape(-1, 2) if len(entry) else np.zeros((0, 2), int)
            acc = {}
            for ji, wi in e:
                if ji >= 0: acc[local[int(ji)]] = acc.get(local[int(ji)], 0) + float(W[int(wi)])
            vw.append(acc)
        for p in g.primitives:
            P = p.vertex; N = p.normal; T = p.texcoordset[0] if len(p.texcoordset) else None
            vi = p.vertex_index; ni = p.normal_index; ti = p.texcoord_indexset[0] if T is not None else None
            corner = {}; tris = []
            for f in range(len(vi)):
                tri = []
                for k in range(3):
                    key = (int(vi[f][k]), int(ni[f][k]) if ni is not None else 0, int(ti[f][k]) if ti is not None else 0)
                    if key not in corner:
                        corner[key] = len(verts)
                        pos = BSM[:3, :3] @ P[key[0]] + BSM[:3, 3]
                        nrm = BSM[:3, :3] @ N[key[1]] if N is not None else np.array([0, 0, 1.0])
                        uv = T[key[2]] if T is not None else np.zeros(2)
                        verts.append(dict(pos=tuple(pos), nrm=tuple(nrm), uv=(float(uv[0]), 1 - float(uv[1])), w=vw[key[0]]))
                    tri.append(corner[key])
                tris.append(tri)
            meshes.append(dict(model=g.name, material=p.material, tris=tris))
    return dict(bones=bones, verts=verts, meshes=meshes)

if __name__ == '__main__':
    import sys
    m = load(sys.argv[1])
    P = np.array([v['pos'] for v in m['verts']])
    print(len(m['bones']), 'bones', len(P), 'verts', P.min(0).round(3), P.max(0).round(3))
    for me in m['meshes']: print(me['model'], me['material'], len(me['tris']))
    for b in m['bones'][:48]: print(b['name'], b['world'][:3, 3].round(3))

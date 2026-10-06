"""Read the geometry dump written by bin/nifdump (used for validation and previews of written NIFs)."""
import struct, subprocess, numpy as np, os
BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bin')

def read_dump(path):
    d = open(path, 'rb').read(); o = 0
    def u(fmt):
        nonlocal o
        v = struct.unpack_from(fmt, d, o); o += struct.calcsize(fmt); return v
    shapes = []
    (ns,) = u('<I')
    for _ in range(ns):
        (l,) = u('<H'); name = d[o:o + l].decode(); o += l
        (l,) = u('<H'); t0 = d[o:o + l].decode(); o += l
        (l,) = u('<H'); t2 = d[o:o + l].decode(); o += l
        (rf,) = u('<I')
        ec = u('<5f')
        nv, nt = u('<II')
        P = np.frombuffer(d, np.float32, nv * 3, o).reshape(-1, 3); o += nv * 12
        N = np.frombuffer(d, np.float32, nv * 3, o).reshape(-1, 3); o += nv * 12
        UV = np.frombuffer(d, np.float32, nv * 2, o).reshape(-1, 2); o += nv * 8
        T = np.frombuffer(d, np.uint16, nt * 3, o).reshape(-1, 3).astype(np.int64); o += nt * 6
        shapes.append(dict(name=name, P=P, N=N, UV=UV, T=T, tex=t0, glow=t2, rflags=rf, fxcolor=ec[:4], alpha=ec[4]))
    (nc,) = u('<I'); cols = []
    for _ in range(nc):
        mat, nv = u('<II')
        V = np.frombuffer(d, np.float32, nv * 3, o).reshape(-1, 3); o += nv * 12
        cols.append(dict(mat=mat, V=V))
    return shapes, cols

def load_nif(nif, tmp):
    out = subprocess.run([os.path.join(BIN, 'nifdump'), nif, tmp], capture_output=True, text=True)
    return out.stdout, read_dump(tmp)

def winding_agreement(s):
    """fraction of triangles whose CCW geometric normal agrees with the stored vertex normals"""
    P, N, T = s['P'], s['N'], s['T']
    g = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    vn = N[T].sum(1)
    ok = (g * vn).sum(1)
    big = np.linalg.norm(g, axis=1) > 1e-9
    return float((ok[big] > 0).mean())

"""Pack skinned shapes for skin2nif.
shapes: list of dict(name, tex[6], env, spec, gloss, flags, emit, pos, nrm, uv, weights[list of {bone:w}], tris, triSlots)
bind: {bone name: 4x4 world bind} from the target skeleton."""
import struct, numpy as np

def _s(x):
    b = x.encode(); return struct.pack('<I', len(b)) + b
def _xf(m):
    return struct.pack('<12f', *m[:3, :3].reshape(-1), *m[:3, 3])

def write(path, root, bind, shapes):
    bones = sorted({b for sh in shapes for w in sh['weights'] for b in w})
    bidx = {b: i for i, b in enumerate(bones)}
    out = bytearray(_s(root)) + struct.pack('<I', len(bones))
    for b in bones:
        m = np.array(bind[b]); out += _s(b) + _xf(m) + _xf(np.linalg.inv(m))
    out += struct.pack('<I', len(shapes))
    for sh in shapes:
        T = sh['tris']; slots = sh['triSlots']
        # front faces must be counter-clockwise (Skyrim/nifly); Source models are clockwise: flip when the stored
        # vertex normals disagree with the winding
        Pa, Na, Ta = np.asarray(sh['pos']), np.asarray(sh['nrm']), np.asarray(T)
        fn = np.cross(Pa[Ta[:, 1]] - Pa[Ta[:, 0]], Pa[Ta[:, 2]] - Pa[Ta[:, 0]])
        agree = float(np.mean(np.sum(fn * Na[Ta].mean(1), 1) > 0))
        if agree < 0.5: T = [[t[0], t[2], t[1]] for t in T]
        print('  shape', sh['name'], 'winding agreement %.2f%s' % (agree, ' -> flipped' if agree < 0.5 else ''))
        used = sorted({int(v) for t in T for v in t}); remap = {v: i for i, v in enumerate(used)}
        parts = sorted(set(slots)); pidx = {p: i for i, p in enumerate(parts)}
        o = bytearray(_s(sh['name'])) + b''.join(_s(x) for x in sh['tex'])
        o += struct.pack('<fffIf', sh.get('env', 0.0), sh.get('spec', 0.5), sh.get('gloss', 20.0), sh.get('flags', 0), sh.get('emit', 1.0))
        o += struct.pack('<III', len(used), len(T), len(parts)) + b''.join(struct.pack('<H', p) for p in parts)
        P, N, UV, W = sh['pos'], sh['nrm'], sh['uv'], sh['weights']
        for v in used:
            ws = sorted(W[v].items(), key=lambda kv: -kv[1])[:4]; tot = sum(w for _, w in ws) or 1
            ids = [bidx[b] for b, _ in ws] + [0] * (4 - len(ws)); wv = [w / tot for _, w in ws] + [0.0] * (4 - len(ws))
            o += struct.pack('<8f', *P[v], *N[v], *UV[v]) + struct.pack('<4B', *ids) + struct.pack('<4f', *wv)
        for t, sl in zip(T, slots):
            o += struct.pack('<3HB', remap[int(t[0])], remap[int(t[1])], remap[int(t[2])], pidx[sl])
        out += o
    open(path, 'wb').write(out)
    return bones

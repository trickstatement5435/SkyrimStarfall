"""nifkit: write Skyrim SE static NIFs (render shapes + static Havok collision) from Python.

    import nifkit
    bounds = nifkit.write_nif(path, shapes, collision=None, material='stone', bsx=None, root_name=None)

shapes: list of dicts (or geom.Mesh plus keys) with
    name      str
    verts     (N,3) game units, normals (N,3), uvs (N,2), tris (M,3)  -- or 'mesh': geom.Mesh instead of the four arrays
    colors    optional (N,4) floats 0..1 (sets the vertex colour flag)
    tex       list of texture paths relative to Data, e.g. ['textures\\StarfallSite\\kit\\concrete.dds', '...\\concrete_n.dds', glow, ...]
              slots: 0 diffuse, 1 normal (alpha = specular), 2 glow, 3 height, 4 env cube, 5 env mask
    spec      specular strength (0 = specular flag off), gloss (glossiness), spec_color (r,g,b)
    alpha     material alpha (default 1)
    uv_scale  (u, v) shader UV scale (default 1,1)
    flags     dict: alpha_test, alpha_threshold (0..255, default 128), alpha_blend, double_sided, glow,
              emissive_color (r,g,b), emit_mult, vertex_colors, vertex_alpha, no_shadows, decal, envmap, env_scale, no_zwrite
    effect    optional dict -> BSEffectShaderProperty instead of lighting shader (glow cards, screens, liquids):
              {'source': tex (default tex[0]), 'greyscale': '', 'color': (r,g,b,a), 'scale': 1.0,
               'additive': True, 'falloff': (start_angle, stop_angle, start_opacity, stop_opacity) or None,
               'soft_depth': 0, 'double_sided': False}
collision: list of pieces in game units, each {'min':(x,y,z),'max':(x,y,z)} (box) or {'points': (K,3)} (convex hull),
    optional per piece 'material' (name or SKY_HAV_MAT number) and 'radius' (havok units, default 0.01).
    One piece -> a single bhkConvexVerticesShape, several -> bhkListShape. Body: bhkRigidBody, layer 1 STATIC,
    MO_SYS_FIXED, MO_QUAL_FIXED, mass 0, no inertia.
material: default Havok material for pieces without one.
bsx: BSXFlags value (default 2 when there is collision, none otherwise).

Returns dict(min=[x,y,z] ints (floor), max=[x,y,z] ints (ceil), tris=int, verts=int, shapes=int, log=str)
-> the OBND for the ESP. Shapes with >= 65535 vertices are split automatically.
"""
import os, struct, subprocess, tempfile
import numpy as np
from scipy.spatial import ConvexHull

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.normpath(os.path.join(HERE, '..', '..', 'bin', 'static2nif'))

# SKY_HAV_MAT values (from CommonLibSSE RE/M/MaterialIDs.h, identical to nif.xml SkyrimHavokMaterial)
HAVOK_MATERIALS = {
    'stone': 3741512247,          # SKY_HAV_MAT_STONE
    'stone_heavy': 1570821952,    # SKY_HAV_MAT_HEAVY_STONE
    'stone_broken': 131151687,    # SKY_HAV_MAT_BROKEN_STONE
    'stone_stairs': 899511101,    # SKY_HAV_MAT_STONE_STAIRS
    'metal': 1288358971,          # SKY_HAV_MAT_SOLID_METAL
    'metal_heavy': 2229413539,    # SKY_HAV_MAT_HEAVY_METAL
    'metal_light': 346811165,     # SKY_HAV_MAT_LIGHT_METAL (sheet metal)
    'wood': 500811281,            # SKY_HAV_MAT_WOOD
    'wood_heavy': 3070783559,     # SKY_HAV_MAT_HEAVY_WOOD
    'wood_light': 365420259,      # SKY_HAV_MAT_LIGHT_WOOD
    'wood_stairs': 1461712277,    # SKY_HAV_MAT_STAIRS_WOOD
    'glass': 3739830338,          # SKY_HAV_MAT_GLASS
    'cloth': 3839073443,          # SKY_HAV_MAT_CLOTH
    'dirt': 3106094762,           # SKY_HAV_MAT_DIRT
    'gravel': 428587608,          # SKY_HAV_MAT_GRAVEL
    'barrel': 732141076,          # SKY_HAV_MAT_BARREL
    'organic': 2974920155,        # SKY_HAV_MAT_ORGANIC
    'boulder_large': 1885326971,  # SKY_HAV_MAT_MATERIAL_BOULDER_LARGE
    'ice': 873356572,             # SKY_HAV_MAT_ICE
    'water_puddle': 3764646153,   # SKY_HAV_MAT_WATER_PUDDLE
}

F_ALPHA_TEST, F_ALPHA_BLEND, F_DOUBLE_SIDED, F_GLOW = 1, 2, 4, 8
F_VCOLORS, F_ADDITIVE, F_NO_SHADOWS, F_DECAL = 16, 32, 64, 128
F_ENVMAP, F_NO_ZWRITE, F_FALLOFF, F_VERTEX_ALPHA = 256, 512, 1024, 2048
MAX_VERTS = 65000


def tex_path(name, folder='kit'):
    """'concrete' -> 'textures\\StarfallSite\\kit\\concrete.dds'"""
    return 'textures\\StarfallSite\\%s\\%s.dds' % (folder, name)


def _s(b, s):
    e = s.encode('ascii')
    b += struct.pack('<H', len(e)) + e


def _mat(m, default):
    m = default if m is None else m
    return int(m) if not isinstance(m, str) else HAVOK_MATERIALS[m]


def _shape_arrays(sh):
    if 'mesh' in sh and sh['mesh'] is not None:
        m = sh['mesh']
        return (np.asarray(m.P, np.float32), np.asarray(m.N, np.float32), np.asarray(m.UV, np.float32),
                np.asarray(m.T, np.int64), None if m.C is None else np.asarray(m.C, np.float32))
    c = sh.get('colors')
    return (np.asarray(sh['verts'], np.float32), np.asarray(sh['normals'], np.float32), np.asarray(sh['uvs'], np.float32),
            np.asarray(sh['tris'], np.int64), None if c is None else np.asarray(c, np.float32))


def _split(P, N, UV, T, C):
    """split into chunks of < MAX_VERTS vertices (by triangles), re-indexing"""
    if len(P) < MAX_VERTS:
        yield P, N, UV, T, C
        return
    start = 0
    while start < len(T):
        used = {}
        tris = []
        i = start
        while i < len(T):
            new = [v for v in T[i] if v not in used]
            if len(used) + len(new) > MAX_VERTS: break
            for v in T[i]:
                if v not in used: used[v] = len(used)
            tris.append([used[v] for v in T[i]]); i += 1
        idx = np.array(list(used.keys()))
        yield P[idx], N[idx], UV[idx], np.array(tris), (None if C is None else C[idx])
        start = i


def hull_planes(points):
    """convex hull -> (vertices (K,3), planes (P,4) with n.x + d <= 0 inside), coplanar facets merged"""
    pts = np.asarray(points, np.float64)
    h = ConvexHull(pts)
    planes = []
    for eq in h.equations:
        if not any(np.allclose(eq[:3], q[:3], atol=1e-4) and abs(eq[3] - q[3]) < 1e-3 for q in planes):
            planes.append(eq)
    return pts[h.vertices], np.array(planes)


def _box_points(mn, mx):
    mn = np.asarray(mn, float); mx = np.asarray(mx, float)
    return np.array([[mx[0] if i & 1 else mn[0], mx[1] if i & 2 else mn[1], mx[2] if i & 4 else mn[2]] for i in range(8)])


def collision_points(piece):
    if 'points' in piece: return np.asarray(piece['points'], float)
    return _box_points(piece['min'], piece['max'])


def _pack(shapes, collision, material, bsx, root_name):
    b = bytearray(b'SNIF') + struct.pack('<I', 1)
    _s(b, root_name)
    has_col = bool(collision)
    b += struct.pack('<i', (2 if has_col else -1) if bsx is None else int(bsx))
    chunks = []
    for sh in shapes:
        P, N, UV, T, C = _shape_arrays(sh)
        if len(T) == 0: continue
        if sh.get('flags', {}).get('vertex_colors') and C is None:
            C = np.ones((len(P), 4), np.float32)
        if not sh.get('flags', {}).get('vertex_colors') and not sh.get('flags', {}).get('vertex_alpha'):
            C = None if sh.get('colors') is None and C is None else C
        parts = list(_split(P, N, UV, T, C))
        for k, part in enumerate(parts):
            nm = sh.get('name', 'Shape') + ('' if len(parts) == 1 else ':%d' % k)
            chunks.append((nm, sh, part))
    b += struct.pack('<I', len(chunks))
    tv = tt = 0
    for nm, sh, (P, N, UV, T, C) in chunks:
        fl = sh.get('flags', {}) or {}
        fx = sh.get('effect')
        f = 0
        if fl.get('alpha_test'): f |= F_ALPHA_TEST
        if fl.get('alpha_blend'): f |= F_ALPHA_BLEND
        if fl.get('double_sided') or (fx and fx.get('double_sided')): f |= F_DOUBLE_SIDED
        if fl.get('glow'): f |= F_GLOW
        if C is not None: f |= F_VCOLORS
        if fl.get('vertex_alpha') or (fx and fx.get('vertex_alpha')): f |= F_VERTEX_ALPHA
        if fx and fx.get('additive', True): f |= F_ADDITIVE
        if fx and not fx.get('additive', True) and fx.get('blend', True): f |= F_ALPHA_BLEND
        if fx and fx.get('falloff'): f |= F_FALLOFF
        if fl.get('no_shadows'): f |= F_NO_SHADOWS
        if fl.get('decal'): f |= F_DECAL
        if fl.get('envmap'): f |= F_ENVMAP
        if fl.get('no_zwrite') or (fx and fx.get('no_zwrite')): f |= F_NO_ZWRITE
        _s(b, nm)
        b += struct.pack('<BIII', 1 if fx else 0, f, len(P), len(T))
        spec = float(sh.get('spec', 0.0)); gloss = float(sh.get('gloss', 30.0))
        b += struct.pack('<ff', spec, gloss) + struct.pack('<3f', *sh.get('spec_color', (1, 1, 1)))
        emit = fl.get('emissive_color', (1, 1, 1) if fl.get('glow') else (0, 0, 0))
        b += struct.pack('<3f', *emit) + struct.pack('<f', float(fl.get('emit_mult', 1.0)))
        b += struct.pack('<f', float(sh.get('alpha', 1.0)))
        b += struct.pack('<B', int(fl.get('alpha_threshold', 128)))
        b += struct.pack('<f', float(fl.get('env_scale', 1.0)))
        fxd = fx or {}
        b += struct.pack('<4f', *fxd.get('color', (1, 1, 1, 1)))
        b += struct.pack('<f', float(fxd.get('scale', 1.0)))
        b += struct.pack('<4f', *(fxd.get('falloff') or (1, 1, 1, 1)))
        b += struct.pack('<f', float(fxd.get('soft_depth', 0.0)))
        b += struct.pack('<2f', *sh.get('uv_scale', (1, 1)))
        tex = list(sh.get('tex', []))
        if fx:
            tex = [fxd.get('source', tex[0] if tex else ''), fxd.get('greyscale', '')]
        b += struct.pack('<I', len(tex))
        for t in tex: _s(b, t or '')
        b += np.ascontiguousarray(P, np.float32).tobytes()
        Nn = N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)
        b += np.ascontiguousarray(Nn, np.float32).tobytes()
        b += np.ascontiguousarray(UV, np.float32).tobytes()
        if C is not None: b += np.ascontiguousarray(C, np.float32).tobytes()
        assert T.max() < 65535
        b += np.ascontiguousarray(T, np.uint16).tobytes()
        tv += len(P); tt += len(T)
    collision = collision or []
    b += struct.pack('<I', len(collision))
    for piece in collision:
        V, PL = hull_planes(collision_points(piece))
        b += struct.pack('<IfII', _mat(piece.get('material'), _mat(material, 'stone')), float(piece.get('radius', 0.01)), len(V), len(PL))
        b += np.ascontiguousarray(V, np.float32).tobytes() + np.ascontiguousarray(PL, np.float32).tobytes()
    return bytes(b), tv, tt, len(chunks)


def compute_bounds(shapes, collision=None):
    pts = [_shape_arrays(s)[0] for s in shapes if len(_shape_arrays(s)[3])]
    pts += [collision_points(c) for c in (collision or [])]
    if not pts: return [0, 0, 0], [0, 0, 0]
    A = np.concatenate([np.asarray(p, float).reshape(-1, 3) for p in pts])
    return [int(np.floor(v)) for v in A.min(0)], [int(np.ceil(v)) for v in A.max(0)]


def write_nif(path, shapes, collision=None, material='stone', bsx=None, root_name=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    root_name = root_name or os.path.splitext(os.path.basename(path))[0]
    data, tv, tt, ns = _pack(shapes, collision, material, bsx, root_name)
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(data); tmp = f.name
    try:
        r = subprocess.run([BIN, tmp, path], capture_output=True, text=True)
    finally:
        os.unlink(tmp)
    if r.returncode != 0 or not r.stdout.startswith('OK'):
        raise RuntimeError('static2nif failed: %s %s' % (r.stdout, r.stderr))
    mn, mx = compute_bounds(shapes, collision)
    return dict(min=mn, max=mx, verts=tv, tris=tt, shapes=ns, log=r.stdout.strip())


# convenience: build a shape dict from a geom.Mesh
def shape(name, mesh, tex, spec=0.0, gloss=30.0, **kw):
    d = dict(name=name, mesh=mesh, tex=tex, spec=spec, gloss=gloss)
    d.update(kw)
    return d


def box_col(mn, mx, material=None):
    d = {'min': tuple(mn), 'max': tuple(mx)}
    if material: d['material'] = material
    return d


def hull_col(points, material=None):
    d = {'points': np.asarray(points, float)}
    if material: d['material'] = material
    return d


def selftest(path=None):
    """cube with 6 faces + 1 box collider: write, reload with nifly (bin/nifdump), check counts and bounds"""
    import geom, nifread
    path = path or os.path.join(tempfile.gettempdir(), 'nifkit_selftest.nif')
    m = geom.box((-32, -32, 0), (32, 32, 64), uv='fit')
    r = write_nif(path, [shape('Cube', m, [tex_path('wood_crate'), tex_path('wood_crate_n')], spec=0.3)], [box_col((-32, -32, 0), (32, 32, 64), 'wood')])
    log, (shapes, cols) = nifread.load_nif(path, path + '.bin')
    os.unlink(path + '.bin')
    ok = (len(shapes) == 1 and len(shapes[0]['T']) == 12 and len(cols) == 1 and 'BSX=2' in log and 'bhkRigidBody layer=1' in log
          and r['min'] == [-32, -32, 0] and r['max'] == [32, 32, 64] and nifread.winding_agreement(shapes[0]) == 1.0
          and np.allclose(cols[0]['V'].min(0), (-32, -32, 0), atol=0.01) and np.allclose(cols[0]['V'].max(0), (32, 32, 64), atol=0.01))
    print(r['log']); print('selftest', 'PASSED' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv: raise SystemExit(0 if selftest() else 1)

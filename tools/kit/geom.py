"""Mesh helpers for procedural static props (Skyrim units, Z up).

Every primitive returns a Mesh with flat or smooth normals, UVs and counter-clockwise triangles
(seen from outside: cross(b - a, c - a) points along the outward normal, the convention vanilla SSE meshes use).

UV convention for 'world' mapping: uv_scale = game units per texture repeat; textures are upright on
vertical faces (V grows downward as Z falls) and continuous across neighbouring boxes.
"""
import numpy as np
from scipy.spatial import ConvexHull

F = np.float64


class Mesh:
    def __init__(self, P=None, N=None, UV=None, T=None, C=None):
        self.P = np.zeros((0, 3)) if P is None else np.asarray(P, F).reshape(-1, 3)
        self.N = np.zeros((0, 3)) if N is None else np.asarray(N, F).reshape(-1, 3)
        self.UV = np.zeros((0, 2)) if UV is None else np.asarray(UV, F).reshape(-1, 2)
        self.T = np.zeros((0, 3), np.int64) if T is None else np.asarray(T, np.int64).reshape(-1, 3)
        self.C = None if C is None else np.asarray(C, F).reshape(-1, 4)

    def copy(self):
        return Mesh(self.P.copy(), self.N.copy(), self.UV.copy(), self.T.copy(), None if self.C is None else self.C.copy())

    @property
    def nv(self): return len(self.P)

    @property
    def nt(self): return len(self.T)

    def bounds(self):
        return self.P.min(0), self.P.max(0)

    # chainable transforms (return new meshes)
    def translate(self, *t): return transform(self, T=t if len(t) == 3 else t[0])
    def rotate(self, R): return transform(self, R=R)
    def scale(self, s): return transform(self, S=s)
    def flipped(self): return flip(self)
    def colored(self, rgba): return set_color(self, rgba)


def merge(*meshes):
    ms = [m for m in _flat(meshes) if m is not None and m.nv]
    if not ms: return Mesh()
    off = np.cumsum([0] + [m.nv for m in ms[:-1]])
    anyc = any(m.C is not None for m in ms)
    C = np.concatenate([(m.C if m.C is not None else np.ones((m.nv, 4))) for m in ms]) if anyc else None
    return Mesh(np.concatenate([m.P for m in ms]), np.concatenate([m.N for m in ms]), np.concatenate([m.UV for m in ms]),
                np.concatenate([m.T + o for m, o in zip(ms, off)]), C)


def _flat(x):
    for i in x:
        if isinstance(i, (list, tuple)): yield from _flat(i)
        else: yield i


# ---------------------------------------------------------------- rotations
def rot_x(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot_axis(axis, deg):
    k = np.asarray(axis, F); k = k / np.linalg.norm(k); a = np.radians(deg)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def rot_to(direction):
    """rotation taking +Z to `direction`"""
    d = np.asarray(direction, F); d = d / np.linalg.norm(d)
    z = np.array([0, 0, 1.0]); v = np.cross(z, d); c = z @ d
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else rot_x(180)
    return rot_axis(v, np.degrees(np.arccos(np.clip(c, -1, 1))))


def transform(m, T=(0, 0, 0), R=None, S=1.0):
    """scale (scalar or xyz), then rotate (3x3), then translate. Normals transformed with inverse transpose;
    winding flipped when the scale mirrors."""
    S = np.broadcast_to(np.asarray(S, F), (3,))
    R = np.eye(3) if R is None else np.asarray(R, F)
    P = (m.P * S) @ R.T + np.asarray(T, F)
    N = (m.N / S) @ R.T
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    Tr = m.T.copy()
    if np.prod(S) < 0: Tr = Tr[:, [0, 2, 1]]
    return Mesh(P, N, m.UV.copy(), Tr, None if m.C is None else m.C.copy())


def flip(m):
    """reverse faces (winding + normals): for inside surfaces"""
    return Mesh(m.P.copy(), -m.N, m.UV.copy(), m.T[:, [0, 2, 1]].copy(), None if m.C is None else m.C.copy())


def double(m):
    return merge(m, flip(m))


def set_color(m, rgba):
    c = np.ones((m.nv, 4)); c[:, :len(rgba)] = rgba
    out = m.copy(); out.C = c; return out


def uv_xform(m, scale=(1, 1), offset=(0, 0)):
    out = m.copy(); out.UV = out.UV * np.asarray(scale, F) + np.asarray(offset, F); return out


def uv_rect(m, rect):
    """map existing 0..1 UVs into an atlas sub-rect (u0, v0, u1, v1)"""
    u0, v0, u1, v1 = rect
    return uv_xform(m, (u1 - u0, v1 - v0), (u0, v0))


# ---------------------------------------------------------------- UV projection
def _face_uv(P, n, uv_scale, origin=(0, 0, 0)):
    """box projection by dominant axis of normal n (per vertex arrays). Upright on walls, readable (not mirrored)."""
    Q = (P - np.asarray(origin, F)) / uv_scale
    ax = np.abs(n).argmax(1)
    sg = np.sign(n[np.arange(len(n)), ax]); sg[sg == 0] = 1
    u = np.where(ax == 0, Q[:, 1] * sg, np.where(ax == 1, -Q[:, 0] * sg, Q[:, 0] * np.where(ax == 2, 1, 1)))
    v = np.where(ax == 2, -Q[:, 1] * sg, -Q[:, 2])
    return np.stack([u, v], 1)


def box_uv(m, uv_scale=128.0, origin=(0, 0, 0)):
    """re-project UVs (world box mapping, per-face from vertex normals)"""
    out = m.copy(); out.UV = _face_uv(m.P, m.N, uv_scale, origin); return out


# ---------------------------------------------------------------- primitives
_BOX_FACES = {  # name: (axis, sign, (u axis, u sign), (v axis, v sign))
    '+x': (0, 1), '-x': (0, -1), '+y': (1, 1), '-y': (1, -1), '+z': (2, 1), '-z': (2, -1)}


def quad(corners, uv=((0, 1), (1, 1), (1, 0), (0, 0)), facing=None):
    """quad from 4 corners in CCW order seen from the front (bottom-left, bottom-right, top-right, top-left);
    default UVs fit the full texture upright. facing: optional direction the quad must face; when the corner
    order disagrees the quad is mirrored left-right (corners 0<->1, 2<->3) so it faces that way and still reads upright."""
    P = np.asarray(corners, F)
    if facing is not None:
        n0 = np.cross(P[1] - P[0], P[3] - P[0])
        if n0 @ np.asarray(facing, F) < 0: P = P[[1, 0, 3, 2]]
    n = np.cross(P[1] - P[0], P[3] - P[0]); n /= np.linalg.norm(n) + 1e-12
    return Mesh(P, np.tile(n, (4, 1)), uv, [[0, 1, 2], [0, 2, 3]])


def plane(w, h, center=(0, 0, 0), normal='+y', uv='fit', uv_scale=128.0):
    """axis-aligned rectangle w (horizontal) x h facing `normal`. For +y/-y: w along X, h along Z;
    +x/-x: w along Y, h along Z; +z/-z: w along X, h along Y."""
    c = np.asarray(center, F); hw, hh = w / 2, h / 2
    if normal == '+y': q = [(hw, 0, -hh), (-hw, 0, -hh), (-hw, 0, hh), (hw, 0, hh)]
    elif normal == '-y': q = [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)]
    elif normal == '+x': q = [(0, -hw, -hh), (0, hw, -hh), (0, hw, hh), (0, -hw, hh)]
    elif normal == '-x': q = [(0, hw, -hh), (0, -hw, -hh), (0, -hw, hh), (0, hw, hh)]
    elif normal == '+z': q = [(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)]
    elif normal == '-z': q = [(-hw, hh, 0), (hw, hh, 0), (hw, -hh, 0), (-hw, -hh, 0)]
    else: raise ValueError(normal)
    m = quad(np.asarray(q, F) + c)
    if uv == 'world': m = box_uv(m, uv_scale)
    return m


def box(mn, mx, uv='world', uv_scale=128.0, faces=None, uv_origin=(0, 0, 0)):
    """axis-aligned box. uv='world' (tiles at uv_scale units/repeat), 'fit' (each face 0..1),
    or a dict face -> (u0, v0, u1, v1) atlas rect (faces missing from the dict use 'fit').
    faces: iterable of '+x','-x','+y','-y','+z','-z' to keep (default all)."""
    mn = np.asarray(mn, F); mx = np.asarray(mx, F)
    parts = []
    for f in (faces or ['+x', '-x', '+y', '-y', '+z', '-z']):
        ax, sg = _BOX_FACES[f]
        lo, hi = mn.copy(), mx.copy()
        if sg > 0: lo[ax] = mx[ax]
        else: hi[ax] = mn[ax]
        c = (lo + hi) / 2; d = hi - lo
        if ax == 0: m = plane(d[1], d[2], c, f)
        elif ax == 1: m = plane(d[0], d[2], c, f)
        else: m = plane(d[0], d[1], c, f)
        if uv == 'world': m = box_uv(m, uv_scale, uv_origin)
        elif isinstance(uv, dict) and f in uv: m = uv_rect(m, uv[f])
        parts.append(m)
    return merge(parts)


def box_c(center, size, **kw):
    c = np.asarray(center, F); s = np.asarray(size, F) / 2
    return box(c - s, c + s, **kw)


def hull_mesh(points, uv_scale=128.0, uv_origin=(0, 0, 0), smooth=False):
    """flat-shaded convex hull of points with world box-mapped UVs"""
    pts = np.asarray(points, F)
    h = ConvexHull(pts)
    P, N, T = [], [], []
    for simplex, eq in zip(h.simplices, h.equations):
        a, b, c = pts[simplex]
        n = eq[:3]
        if np.cross(b - a, c - a) @ n < 0: b, c = c, b
        base = len(P); P += [a, b, c]; N += [n, n, n]; T.append([base, base + 1, base + 2])
    m = Mesh(P, N, np.zeros((len(P), 2)), T)
    m = box_uv(m, uv_scale, uv_origin)
    if smooth:
        cen = pts[h.vertices].mean(0); d = m.P - cen
        m.N = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9)
    return m


def bevel_box(mn, mx, bevel=2.0, uv_scale=128.0, uv_origin=(0, 0, 0)):
    """box with 45 degree chamfered edges and corners (26 faces), world UVs"""
    mn = np.asarray(mn, F); mx = np.asarray(mx, F)
    b = min(bevel, *((mx - mn) / 2 - 1e-3))
    pts = []
    for ax in range(3):
        lo = mn + b; hi = mx - b; lo[ax] = mn[ax]; hi[ax] = mx[ax]
        for i in range(8):
            pts.append([(hi if i & (1 << k) else lo)[k] for k in range(3)])
    return hull_mesh(pts, uv_scale, uv_origin)


def chamfer_box(mn, mx, bevel, faces, uv_scale=128.0, uv_origin=(0, 0, 0)):
    """box whose edges are chamfered only where BOTH adjoining faces are listed in `faces` ('+x','-z',...).
    Lets several boxes butt together seamlessly while keeping chamfers on the outer silhouette."""
    mn = np.asarray(mn, F); mx = np.asarray(mx, F)
    ilo = np.array([bevel if ('-' + a) in faces else 0.0 for a in 'xyz'])
    ihi = np.array([bevel if ('+' + a) in faces else 0.0 for a in 'xyz'])
    pts = []
    for ax in range(3):
        lo = mn + ilo; hi = mx - ihi; lo[ax] = mn[ax]; hi[ax] = mx[ax]
        for i in range(8):
            pts.append([(hi if i & (1 << k) else lo)[k] for k in range(3)])
    pts = np.unique(np.round(np.asarray(pts), 5), axis=0)
    return hull_mesh(pts, uv_scale, uv_origin)


def bevel_box_c(center, size, bevel=2.0, **kw):
    c = np.asarray(center, F); s = np.asarray(size, F) / 2
    return bevel_box(c - s, c + s, bevel, **kw)


def lathe(profile, segs=16, uv_scale=None, u_repeat=1.0, smooth_profile=False, angle0=0.0, sweep=360.0):
    """surface of revolution around Z. profile: [(r, z), ...] listed from bottom to top for an outward surface.
    Hard edges between profile segments (each segment gets its own ring of normals) unless smooth_profile.
    UVs: u = around (0..u_repeat), v = profile arc length / uv_scale (or 0..1 over the whole profile when uv_scale is None).
    Segments with r == 0 at an end become caps (fan)."""
    pr = np.asarray(profile, F)
    full = abs(sweep - 360.0) < 1e-6
    ang = np.radians(angle0 + np.linspace(0, sweep, segs + 1))
    cs, sn = np.cos(ang), np.sin(ang)
    seglen = np.linalg.norm(np.diff(pr, axis=0), axis=1)
    acc = np.concatenate([[0], np.cumsum(seglen)])
    vcoord = acc / (uv_scale if uv_scale else max(acc[-1], 1e-9))
    P, N, UV, T = [], [], [], []
    # per-profile-point smooth normals (2D) for smooth mode
    d2 = []
    for i in range(len(pr) - 1):
        dr, dz = pr[i + 1] - pr[i]
        L = np.hypot(dr, dz) + 1e-12
        d2.append(np.array([dz, -dr]) / L)  # outward normal in (r, z) for bottom->top order
    for i in range(len(pr) - 1):
        if seglen[i] < 1e-9: continue
        (r0, z0), (r1, z1) = pr[i], pr[i + 1]
        n0 = n1 = d2[i]
        if smooth_profile:
            if i > 0: n0 = d2[i - 1] + d2[i]; n0 = n0 / (np.linalg.norm(n0) + 1e-12)
            if i < len(d2) - 1: n1 = d2[i] + d2[i + 1]; n1 = n1 / (np.linalg.norm(n1) + 1e-12)
        base = len(P)
        for j in range(segs + 1):
            for (r, z, nn, v) in ((r0, z0, n0, vcoord[i]), (r1, z1, n1, vcoord[i + 1])):
                P.append((r * cs[j], r * sn[j], z))
                N.append((nn[0] * cs[j], nn[0] * sn[j], nn[1]))
                UV.append((u_repeat * j / segs, -v))
        for j in range(segs):
            a, b, c, d = base + 2 * j, base + 2 * j + 2, base + 2 * j + 3, base + 2 * j + 1
            T += [[a, b, c], [a, c, d]]
    m = Mesh(P, N, UV, T)
    return _drop_degenerate(m)


def _drop_degenerate(m):
    P, T = m.P, m.T
    g = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    keep = np.linalg.norm(g, axis=1) > 1e-9
    return Mesh(m.P, m.N, m.UV, m.T[keep], m.C)


def disk(r, z=0.0, segs=16, up=True, uv_scale=None, center=(0, 0)):
    """filled circle at height z facing +Z (or -Z). UVs planar: world (uv_scale) or fit 0..1."""
    ang = np.radians(np.linspace(0, 360, segs + 1)[:-1])
    P = [(center[0], center[1], z)] + [(center[0] + r * np.cos(a), center[1] + r * np.sin(a), z) for a in ang]
    P = np.asarray(P, F)
    T = [[0, 1 + j, 1 + (j + 1) % segs] for j in range(segs)]
    if not up: T = [[a, c, b] for a, b, c in T]
    n = np.tile([0, 0, 1.0 if up else -1.0], (len(P), 1))
    if uv_scale: UV = np.stack([P[:, 0] / uv_scale, -P[:, 1] / uv_scale], 1)
    else: UV = np.stack([0.5 + (P[:, 0] - center[0]) / (2 * r), 0.5 - (P[:, 1] - center[1]) / (2 * r)], 1)
    return Mesh(P, n, UV, T)


def cylinder(r, h, segs=16, z0=0.0, caps=True, uv_scale=None, u_repeat=1.0, cap_uv_scale=None):
    """cylinder along +Z from z0 to z0+h; smooth sides. uv_scale None -> v 0..1 over height (label textures)."""
    side = lathe([(r, z0), (r, z0 + h)], segs, uv_scale=uv_scale, u_repeat=u_repeat if not uv_scale else u_repeat)
    if uv_scale and u_repeat == 1.0:
        side.UV[:, 0] *= 2 * np.pi * r / uv_scale
    parts = [side]
    if caps:
        parts += [disk(r, z0 + h, segs, True, cap_uv_scale), disk(r, z0, segs, False, cap_uv_scale)]
    return merge(parts)


def tube(r_out, r_in, h, segs=16, z0=0.0, uv_scale=64.0):
    """thick-walled tube along Z (outer, inner, and ring caps)"""
    outer = lathe([(r_out, z0), (r_out, z0 + h)], segs, uv_scale=uv_scale)
    inner = flip(lathe([(r_in, z0), (r_in, z0 + h)], segs, uv_scale=uv_scale))
    top = lathe([(r_out, z0 + h), (r_in, z0 + h)], segs, uv_scale=uv_scale)
    bot = lathe([(r_in, z0), (r_out, z0)], segs, uv_scale=uv_scale)
    m = merge(outer, inner, top, bot)
    m.UV[:, 0] *= 2 * np.pi * r_out / uv_scale
    return m


def cyl_between(a, b, r, segs=12, caps=True, uv_scale=64.0):
    """cylinder from point a to point b"""
    a = np.asarray(a, F); b = np.asarray(b, F); d = b - a; L = np.linalg.norm(d)
    m = cylinder(r, L, segs, 0.0, caps, uv_scale=uv_scale)
    return transform(m, T=a, R=rot_to(d))


def box_between(a, b, w, h=None, up=(0, 0, 1), uv_scale=64.0):
    """rectangular bar from a to b, cross-section w x h (h defaults to w)"""
    a = np.asarray(a, F); b = np.asarray(b, F); h = w if h is None else h
    d = b - a; L = np.linalg.norm(d); z = d / L
    upv = np.asarray(up, F)
    if abs(z @ upv) > 0.99: upv = np.array([1.0, 0, 0])
    x = np.cross(upv, z); x /= np.linalg.norm(x); y = np.cross(z, x)
    R = np.stack([x, y, z], 1)
    m = box((-w / 2, -h / 2, 0), (w / 2, h / 2, L), uv='world', uv_scale=uv_scale)
    return transform(m, T=a, R=R)


def sweep(path, radius, segs=10, closed=False, uv_scale=64.0, caps=True):
    """tube of circular section along a polyline path (pipes, cables). Smooth normals."""
    path = np.asarray(path, F); n = len(path)
    tang = np.zeros_like(path)
    tang[1:-1] = path[2:] - path[:-2]; tang[0] = path[1] - path[0]; tang[-1] = path[-1] - path[-2]
    if closed:
        tang[0] = path[1] - path[-1]; tang[-1] = path[0] - path[-2]
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    # parallel transport frames
    ref = np.array([0, 0, 1.0]) if abs(tang[0][2]) < 0.9 else np.array([1.0, 0, 0])
    nrm = np.cross(tang[0], ref); nrm /= np.linalg.norm(nrm)
    frames = []
    for i in range(n):
        if i > 0:
            nrm = nrm - tang[i] * (nrm @ tang[i]); nrm /= np.linalg.norm(nrm)
        frames.append((nrm.copy(), np.cross(tang[i], nrm)))
    ang = np.linspace(0, 2 * np.pi, segs + 1)
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    P, N, UV, T = [], [], [], []
    for i in range(n):
        u_, v_ = frames[i]
        for j in range(segs + 1):
            d = np.cos(ang[j]) * u_ + np.sin(ang[j]) * v_
            P.append(path[i] + radius * d); N.append(d)
            UV.append((j / segs * 2 * np.pi * radius / uv_scale, -L[i] / uv_scale))
    for i in range(n - 1):
        for j in range(segs):
            a = i * (segs + 1) + j; b = a + 1; c = a + segs + 2; d = a + segs + 1
            T += [[a, c, b], [a, d, c]]
    m = Mesh(P, N, UV, T)
    # make sure winding faces outward (frame handedness dependent; per triangle so tight bends stay correct)
    m = orient_to_normals(_drop_degenerate(m))
    parts = [m]
    if caps and not closed:
        for i, s in ((0, -1), (n - 1, 1)):
            u_, v_ = frames[i]
            ring = [path[i] + radius * (np.cos(a) * u_ + np.sin(a) * v_) for a in ang[:-1]]
            Pc = np.asarray([path[i]] + ring)
            Tc = [[0, 1 + j, 1 + (j + 1) % segs] for j in range(segs)]
            cap = Mesh(Pc, np.tile(tang[i] * s, (len(Pc), 1)), np.zeros((len(Pc), 2)), Tc)
            g = np.cross(Pc[1] - Pc[0], Pc[2] - Pc[0])
            if g @ (tang[i] * s) < 0: cap.T = cap.T[:, [0, 2, 1]]
            parts.append(box_uv(cap, uv_scale))
    return merge(parts)


def arc_path(center, radius, a0, a1, steps=8, plane='xz'):
    """points on an arc (degrees), for elbows"""
    c = np.asarray(center, F); a = np.radians(np.linspace(a0, a1, steps + 1))
    if plane == 'xz': return np.stack([c[0] + radius * np.cos(a), np.full_like(a, c[1]), c[2] + radius * np.sin(a)], 1)
    if plane == 'xy': return np.stack([c[0] + radius * np.cos(a), c[1] + radius * np.sin(a), np.full_like(a, c[2])], 1)
    return np.stack([np.full_like(a, c[0]), c[1] + radius * np.cos(a), c[2] + radius * np.sin(a)], 1)


def triangulate_polygon(poly):
    """ear-clipping triangulation of a simple 2D polygon given counter-clockwise; returns index triples (CCW)"""
    pts = np.asarray(poly, F)
    idx = list(range(len(pts)))
    if _area2(pts) < 0: idx = idx[::-1]
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            a, b, c = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            pa, pb, pc = pts[a], pts[b], pts[c]
            if (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0]) <= 1e-12: continue  # reflex
            inside = False
            for j in idx:
                if j in (a, b, c): continue
                if _in_tri(pts[j], pa, pb, pc): inside = True; break
            if inside: continue
            tris.append((a, b, c)); idx.pop(k); break
        else:
            break
    if len(idx) == 3: tris.append(tuple(idx))
    return tris


def _area2(p):
    return float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


def _in_tri(p, a, b, c):
    def s(p1, p2, p3): return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def orient_to_normals(m):
    """flip any triangle whose CCW normal disagrees with its averaged vertex normals"""
    P, T = m.P, m.T.copy()
    g_ = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    bad = (g_ * m.N[T].sum(1)).sum(1) < 0
    T[bad] = T[bad][:, [0, 2, 1]]
    return Mesh(m.P, m.N, m.UV, T, m.C)


def extrude(poly2d, z0, z1, uv_scale=64.0, caps=True):
    """vertical prism from a simple CCW 2D polygon (caps ear-clipped, concave allowed)"""
    p = np.asarray(poly2d, F); n = len(p)
    parts = []
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        parts.append(quad([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)]))
    m = box_uv(merge(parts), uv_scale)
    if caps:
        tri = triangulate_polygon(p)
        top = Mesh([(x, y, z1) for x, y in p], np.tile([0, 0, 1.0], (n, 1)), np.zeros((n, 2)), [[a, b, c] for a, b, c in tri])
        bot = Mesh([(x, y, z0) for x, y in p], np.tile([0, 0, -1.0], (n, 1)), np.zeros((n, 2)), [[a, c, b] for a, b, c in tri])
        m = merge(m, box_uv(top, uv_scale), box_uv(bot, uv_scale))
    return m


def prism_profile(profile_yz, x0, x1, uv_scale=64.0, caps=True):
    """extrude a simple (convex or concave) 2D profile given as (y, z) points, counter-clockwise when viewed from +X
    (y to the right, z up), along X from x0 to x1. Used for sloped consoles, ramps, wedges."""
    p = np.asarray(profile_yz, F); n = len(p)
    parts = []
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        parts.append(quad([(x0, a[0], a[1]), (x0, b[0], b[1]), (x1, b[0], b[1]), (x1, a[0], a[1])]))
    m = merge(parts)
    if caps:
        tri = triangulate_polygon(p)
        hi = Mesh([(x1, y, z) for y, z in p], np.tile([1.0, 0, 0], (n, 1)), np.zeros((n, 2)), [[a, b, c] for a, b, c in tri])
        lo = Mesh([(x0, y, z) for y, z in p], np.tile([-1.0, 0, 0], (n, 1)), np.zeros((n, 2)), [[a, c, b] for a, b, c in tri])
        m = merge(m, hi, lo)
    return box_uv(m, uv_scale)


def recompute_flat_normals(m):
    """unshare vertices and give each triangle its geometric normal"""
    P = m.P[m.T].reshape(-1, 3); UV = m.UV[m.T].reshape(-1, 2)
    C = None if m.C is None else m.C[m.T].reshape(-1, 4)
    a, b, c = m.P[m.T[:, 0]], m.P[m.T[:, 1]], m.P[m.T[:, 2]]
    n = np.cross(b - a, c - a); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return Mesh(P, np.repeat(n, 3, 0), UV, np.arange(len(P)).reshape(-1, 3), C)


def jitter(m, amount, seed=0, keep_normals=False):
    """random displacement of welded positions (rocks, debris); returns flat-shaded mesh"""
    rng = np.random.default_rng(seed)
    key = np.round(m.P, 3)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    d = rng.uniform(-amount, amount, uniq.shape)
    out = m.copy(); out.P = m.P + d[inv.ravel()]
    return out if keep_normals else recompute_flat_normals(out)


def tri_count(*ms):
    return sum(m.nt for m in _flat(ms) if m is not None)


def check_winding(m):
    """fraction of triangles whose CCW normal agrees with the stored vertex normals (should be 1.0)"""
    P, T = m.P, m.T
    g = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    big = np.linalg.norm(g, axis=1) > 1e-9
    return float(((g * m.N[T].sum(1)).sum(1)[big] > 0).mean()) if big.any() else 1.0

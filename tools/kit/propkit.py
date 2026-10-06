"""Prop-building framework on top of geom + nifkit: material table, Prop accumulator, extra shape helpers."""
import os, json, numpy as np
import geom as g
import nifkit

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, '..', '..', 'data'))
T = nifkit.tex_path


def _lit(name, uvs=128.0, spec=0.3, gloss=20.0, havok='metal', normal=True, **kw):
    d = dict(tex=[T(name), T(name + '_n') if normal else ''], spec=spec, gloss=gloss, uvs=uvs, havok=havok)
    d.update(kw)
    return d


def _glow(name, uvs=None, spec=0.6, gloss=40.0, emit=1.0, glow_tex=None, havok='metal', **kw):
    d = dict(tex=[T(name), T(name + '_n'), T(glow_tex or name + '_g')], spec=spec, gloss=gloss, uvs=uvs, havok=havok,
             flags={'glow': True, 'emissive_color': (1, 1, 1), 'emit_mult': emit})
    d.update(kw)
    return d


# uvs = game units per texture repeat for world box-mapping; None = keep the mesh's own UVs (fit/atlas mapped)
MATS = {
    'concrete': _lit('concrete', 256, 0.15, 8, havok='stone'),
    'concrete_dark': _lit('concrete_dark', 256, 0.15, 8, havok='stone'),
    'concrete_plain': _lit('concrete_plain', 128, 0.15, 8, havok='stone'),
    'floor_tile': _lit('floor_tile', 128, 0.6, 40, havok='stone'),
    'metal_panel': _lit('metal_panel', 128, 0.8, 35),
    'metal_panel_big': _lit('metal_panel', 256, 0.8, 35),
    'metal_dark': _lit('metal_dark', 64, 1.0, 45),
    'metal_vc': _lit('metal_panel', 128, 0.8, 35, flags={'vertex_colors': True}),  # painted metal: tint via vertex colours
    'metal_dark_fit': _lit('metal_dark', None, 1.0, 45),
    'diamond_plate': _lit('diamond_plate', 64, 1.0, 40),
    'hazard': _lit('hazard_stripes', 96, 0.5, 25),
    'rust': _lit('rust_metal', 128, 0.4, 20),
    'rust_fit': _lit('rust_metal', None, 0.4, 20),
    'rubber': _lit('rubber', 32, 0.2, 10, havok='organic'),
    'rubber_fit': _lit('rubber', None, 0.2, 10, havok='organic'),
    'plastic': _lit('plastic_beige', 64, 0.4, 25),
    'canvas': _lit('canvas', 128, 0.0, 5, havok='cloth'),
    'sandbag': _lit('sandbag', 64, 0.0, 5, havok='dirt'),
    'wood_plank': _lit('wood_plank', 128, 0.1, 10, havok='wood'),
    'crate': _lit('wood_crate', None, 0.15, 12, havok='wood'),
    'cardboard': _lit('cardboard', None, 0.05, 8, havok='wood_light'),
    'specimen': _lit('specimen', 48, 1.5, 80, havok='organic'),
    'glass': _lit('glass', 128, 3.0, 300, havok='glass', flags={'alpha_blend': True, 'double_sided': True, 'no_shadows': True, 'no_zwrite': True}),
    'glass_cracked': _lit('glass_cracked', 64, 3.0, 300, havok='glass', flags={'alpha_blend': True, 'double_sided': True, 'no_shadows': True, 'no_zwrite': True}),
    'grate': _lit('metal_grate', 64, 0.8, 30, flags={'alpha_test': True, 'alpha_threshold': 100, 'double_sided': True}),
    'chainlink': _lit('chainlink', 64, 0.8, 30, flags={'alpha_test': True, 'alpha_threshold': 100, 'double_sided': True}),
    'target': _lit('target', None, 0.4, 20),
    'door_heavy': _lit('door_heavy', None, 0.8, 35, havok='metal_heavy'),
    'keyboard': _lit('keyboard', None, 0.4, 25),
    'barrel_hazard': _lit('barrel_hazard', None, 0.6, 30, havok='barrel'),
    'barrel_toxic': _glow('barrel_toxic', None, 0.6, 30, emit=1.0, havok='barrel'),
    'sign_lambda': _lit('sign_lambda', None, 0.6, 30),
    'sign_biohazard': _lit('sign_biohazard', None, 0.6, 30),
    'sign_restricted': _lit('sign_restricted', None, 0.6, 30),
    'sign_testchamber': _lit('sign_testchamber', None, 0.6, 30),
    'whiteboard': _lit('whiteboard', None, 1.2, 60, havok='wood_light'),
    'poster': _lit('poster_safety', None, 0.1, 8, havok='cloth'),
    'meteor': _glow('meteor_rock', 256, 0.4, 20, emit=1.4, havok='stone_heavy'),
    # glowing (glow map shader)
    'screen_terminal': _glow('screen_terminal', None, 2.0, 120, emit=1.3, havok='glass'),
    'screen_graphs': _glow('screen_graphs', None, 2.0, 120, emit=1.3, havok='glass'),
    'control_panel': _glow('control_panel', None, 0.6, 30, emit=1.2),
    'server_lights': _glow('server_lights', None, 0.6, 30, emit=1.5),
    'fluorescent': _glow('fluorescent_light', None, 0.4, 20, emit=2.0, flags={'glow': True, 'emissive_color': (1, 1, 0.95), 'emit_mult': 2.0, 'no_shadows': True}),
    'lamp': _glow('lamp_glow', None, 1.0, 60, emit=2.0, flags={'glow': True, 'emissive_color': (1, 0.95, 0.85), 'emit_mult': 2.0, 'no_shadows': True}),
    'liquid': _glow('green_liquid', 64, 1.5, 80, emit=1.3, havok='water_puddle'),
    # translucent glowing liquid column (glow map + material alpha, blended, no depth write)
    'liquid_clear': _glow('green_liquid', 64, 1.5, 80, emit=1.3, havok='water_puddle', alpha=0.72,
                          flags={'glow': True, 'emissive_color': (1, 1, 1), 'emit_mult': 1.3, 'alpha_blend': True, 'no_zwrite': True, 'no_shadows': True}),
    'crystal': _glow('crystal', 128, 3.0, 200, emit=1.6, havok='glass'),
    # effect shader (additive): glow haze, sparks, puddles
    'fx_green': dict(tex=[T('green_liquid')], uvs=64, effect={'color': (0.45, 1.0, 0.5, 0.35), 'scale': 1.0, 'additive': True,
                                                             'double_sided': True}, havok='water_puddle'),
    'fx_halo_cyan': dict(tex=[T('halo')], uvs=None, effect={'color': (0.45, 0.85, 1.0, 1.0), 'scale': 1.5, 'additive': True,
                                                              'double_sided': True}, havok='glass'),
    'fx_cyan': dict(tex=[T('crystal')], uvs=128, effect={'color': (0.5, 0.9, 1.0, 0.3), 'scale': 0.7, 'additive': True,
                                                          'double_sided': True}, havok='glass'),
    'fx_spark': dict(tex=[T('spark')], uvs=None, effect={'color': (1.0, 0.65, 0.2, 1.0), 'scale': 2.0, 'additive': True,
                                                             'double_sided': True}, havok='metal'),
    'fx_lamp': dict(tex=[T('halo')], uvs=None, effect={'color': (1.0, 0.92, 0.75, 0.5), 'scale': 1.0, 'additive': True,
                                                            'double_sided': True}, havok='glass'),
    'fx_red': dict(tex=[T('halo')], uvs=None, effect={'color': (1.0, 0.15, 0.1, 1.0), 'scale': 2.0, 'additive': True,
                                                           'double_sided': True}, havok='glass'),
    # decals
    'blood': _lit('blood_splat', None, 0.8, 60, havok='organic',
                  flags={'alpha_blend': True, 'alpha_test': True, 'alpha_threshold': 8, 'decal': True, 'no_shadows': True}),
}


class Prop:
    def __init__(self, name, kind='static', notes='', footprint='auto', havok=None):
        self.name, self.kind, self.notes = name, kind, notes
        self.parts = {}
        self.col = []
        self.footprint = footprint
        self.havok = havok
        self.extra = {}

    def add(self, mat, *meshes, world=None):
        """add meshes with material `mat`. world: True -> re-project UVs with box mapping at the material's scale;
        default: True when the material has a uvs scale, else keep mesh UVs."""
        m = g.merge(list(meshes))
        if not m.nt: return m
        uvs = MATS[mat].get('uvs')
        if world is None: world = uvs is not None
        if world: m = g.box_uv(m, uvs or 128.0)
        self.parts.setdefault(mat, []).append(m)
        return m

    def box(self, mn, mx, material=None):
        self.col.append(nifkit.box_col(mn, mx, material)); return self

    def hull(self, points, material=None):
        self.col.append(nifkit.hull_col(points, material)); return self

    def hull_mesh(self, mesh, material=None):
        return self.hull(mesh.P, material)

    def tris(self):
        return sum(m.nt for ms in self.parts.values() for m in ms)

    def shapes(self):
        out = []
        for mat, ms in self.parts.items():
            m = g.merge(ms)
            d = MATS[mat]
            sh = dict(name='%s_%s' % (self.name, mat), mesh=m, tex=d['tex'], spec=d.get('spec', 0.0), gloss=d.get('gloss', 20.0),
                      flags=dict(d.get('flags', {})), alpha=d.get('alpha', 1.0))
            if 'effect' in d: sh['effect'] = dict(d['effect'])
            out.append(sh)
        return out


def write(prop, outdir, manifest, preview_dir=None, views=('front', 'iso', 'side', 'top')):
    path = os.path.join(outdir, prop.name + '.nif')
    shapes = prop.shapes()
    # assign the dominant visual material's havok type to pieces without one
    default = prop.havok or MATS[max(prop.parts, key=lambda k: sum(m.nt for m in prop.parts[k]))].get('havok', 'stone')
    r = nifkit.write_nif(path, shapes, prop.col or None, material=default)
    mn, mx = r['min'], r['max']
    if prop.footprint == 'auto':
        fp = [mn[0], mn[1], mx[0], mx[1]] if prop.col else 0
    else:
        fp = prop.footprint
    entry = dict(nif='StarfallSite\\props\\%s.nif' % prop.name, bounds=mn + mx, footprint=fp, kind=prop.kind, notes=prop.notes,
                 tris=r['tris'], collision_pieces=len(prop.col), havok_default=default)
    entry.update(prop.extra)
    manifest[prop.name] = entry
    if preview_dir:
        import render
        render.render_nif(path, os.path.join(preview_dir, prop.name + '.png'), views=views, show_collision=True,
                          title='%s  %d tris  bounds %s' % (prop.name, r['tris'], mn + mx))
    print('%-26s tris=%5d col=%2d bounds=%s' % (prop.name, r['tris'], len(prop.col), mn + mx))
    return entry


# ---------------------------------------------------------------- extra shape helpers
def icosphere(r=1.0, sub=2):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    Fc = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
          (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(sub):
        cache = {}; nf = []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = V[a] + V[b]; V.append(m / np.linalg.norm(m)); cache[k] = len(V) - 1
            return cache[k]
        for a, b, c in Fc:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        Fc = nf
    P = np.array(V) * r
    m = g.Mesh(P, P / r, np.zeros((len(P), 2)), np.array(Fc))
    if g.check_winding(m) < 0.5: m.T = m.T[:, [0, 2, 1]]
    return m


def blob(size, seed=0, rough=0.25, sub=2, flat=True):
    """noisy ellipsoid (rocks, chunks): size = (sx, sy, sz) full extents, base at z=0"""
    m = icosphere(1.0, sub)
    r = np.random.default_rng(seed)
    P = m.P.copy()
    # low-frequency displacement from a few random plane waves
    disp = np.zeros(len(P))
    for k in range(6):
        d = r.normal(size=3); d /= np.linalg.norm(d)
        disp += np.sin(P @ d * r.uniform(1.5, 4.0) + r.uniform(0, 6)) * r.uniform(0.3, 1.0)
    disp = disp / np.abs(disp).max() * rough
    P = P * (1 + disp)[:, None] * (np.asarray(size, float) / 2)
    P[:, 2] -= P[:, 2].min()
    out = g.Mesh(P, m.N, m.UV, m.T)
    return g.recompute_flat_normals(out) if flat else out


def pillow(size, seg=6, power=0.35):
    """rounded bag shape (superellipsoid), size full extents, centred at origin"""
    sx, sy, sz = np.asarray(size, float) / 2
    us = np.linspace(-np.pi / 2, np.pi / 2, seg + 1); vs = np.linspace(-np.pi, np.pi, 2 * seg + 1)
    def f(w, p): return np.sign(w) * np.abs(w) ** p
    P = []
    for u in us:
        for v in vs:
            P.append((sx * f(np.cos(u), power) * f(np.cos(v), power), sy * f(np.cos(u), power) * f(np.sin(v), power), sz * f(np.sin(u), 0.7)))
    P = np.array(P); W = 2 * seg + 1
    Tr = []
    for i in range(seg):
        for j in range(2 * seg):
            a = i * W + j; b = a + 1; c = a + W + 1; d = a + W
            Tr += [[a, b, c], [a, c, d]]
    m = g.Mesh(P, np.zeros_like(P), np.zeros((len(P), 2)), Tr)
    m = g._drop_degenerate(m)
    m = g.recompute_flat_normals(m)
    if g.check_winding(m) < 0.5: m = g.flip(m)
    # make sure normals point outward
    c = (m.P[m.T].mean(1) * m.N[m.T[:, 0]]).sum(1)
    if (c < 0).mean() > 0.5: m = g.flip(m)
    return m


def crystal_prism(base, top, r0, r1, tip_len, sides=6, seed=0, twist=0.0):
    """hexagonal crystal from base point to top point (shaft radius r0 -> r1), pointed tip of tip_len"""
    base = np.asarray(base, float); top = np.asarray(top, float)
    ax = top - base; L = np.linalg.norm(ax); z = ax / L
    R = g.rot_to(z)
    ang = np.radians(np.arange(sides) * 360 / sides + twist)
    ring0 = np.stack([r0 * np.cos(ang), r0 * np.sin(ang), np.zeros(sides)], 1) @ R.T + base
    ring1 = np.stack([r1 * np.cos(ang), r1 * np.sin(ang), np.zeros(sides)], 1) @ R.T + top
    tip = top + z * tip_len
    return g.hull_mesh(np.concatenate([ring0, ring1, [tip]]), uv_scale=64)


def railing(a, b, height=100, post_every=128, r_post=2.5, r_rail=2.0, mid=True, toe=True):
    """straight railing from a to b on the floor plane (z of a): posts, top + mid rail, toe board (metal)"""
    a = np.asarray(a, float); b = np.asarray(b, float)
    L = np.linalg.norm(b - a); n = max(1, int(round(L / post_every)))
    parts = []
    for i in range(n + 1):
        p = a + (b - a) * i / n
        parts.append(g.cyl_between(p, p + [0, 0, height], r_post, 8, caps=True))
    parts.append(g.cyl_between(a + [0, 0, height], b + [0, 0, height], r_rail, 8))
    if mid: parts.append(g.cyl_between(a + [0, 0, height * 0.5], b + [0, 0, height * 0.5], r_rail * 0.8, 8))
    if toe: parts.append(g.box_between(a + [0, 0, 0], b + [0, 0, 0], 1.0, 20, up=(0, 0, 1)))
    return parts


def ibeam(a, b, w=12, h=16, t=2.0, up=(0, 0, 1)):
    """I-beam between two points (flanges perpendicular to `up`)"""
    a = np.asarray(a, float); b = np.asarray(b, float)
    d = b - a; L = np.linalg.norm(d); z = d / L
    upv = np.asarray(up, float)
    if abs(z @ upv) > 0.99: upv = np.array([1.0, 0, 0])
    x = np.cross(upv, z); x /= np.linalg.norm(x); y = np.cross(z, x)
    R = np.stack([x, y, z], 1)
    parts = [g.box((-w / 2, h / 2 - t, 0), (w / 2, h / 2, L)), g.box((-w / 2, -h / 2, 0), (w / 2, -h / 2 + t, L)),
             g.box((-t / 2, -h / 2 + t, 0), (t / 2, h / 2 - t, L))]
    return g.transform(g.merge(parts), T=a, R=R)


def jagged_ring(r, z0, heights, sides=None, seed=0, thickness=0.0):
    """ring of glass shards: a band around Z at radius r from z0 up to a jagged top edge (heights per segment). Double-sided via material."""
    n = len(heights)
    ang = np.radians(np.linspace(0, 360, n + 1))
    P, Tr = [], []
    for i in range(n):
        a0, a1 = ang[i], ang[i + 1]
        h0 = heights[i]; h1 = heights[(i + 1) % n]
        am = (a0 + a1) / 2; hm = max(h0, h1) * 1.15 + 2
        p = [(r * np.cos(a0), r * np.sin(a0), z0), (r * np.cos(a1), r * np.sin(a1), z0), (r * np.cos(a1), r * np.sin(a1), z0 + h1),
             (r * np.cos(am), r * np.sin(am), z0 + hm), (r * np.cos(a0), r * np.sin(a0), z0 + h0)]
        b = len(P); P += p
        Tr += [[b, b + 1, b + 2], [b, b + 2, b + 3], [b, b + 3, b + 4]]
    P = np.array(P)
    N = P.copy(); N[:, 2] = 0; N /= np.linalg.norm(N, axis=1, keepdims=True)
    m = g.Mesh(P, N, np.zeros((len(P), 2)), Tr)
    if g.check_winding(m) < 0.5: m.T = m.T[:, [0, 2, 1]]
    return m


def shard(center, size, seed, normal=(0, 0, 1)):
    """flat triangular glass shard lying around center"""
    r = np.random.default_rng(seed)
    a = r.uniform(0, 2 * np.pi)
    pts = [np.array([np.cos(a + k * 2.1 + r.uniform(-0.4, 0.4)), np.sin(a + k * 2.1 + r.uniform(-0.4, 0.4)), 0]) * size * r.uniform(0.5, 1.0) for k in range(3)]
    P = np.array(pts) + np.asarray(center, float)
    m = g.Mesh(P, np.tile([0, 0, 1.0], (3, 1)), np.zeros((3, 2)), [[0, 1, 2]])
    if g.check_winding(m) < 0.5: m.T = m.T[:, [0, 2, 1]]
    return m


def splat_poly(radius, seed, n=14, z=0.3, rough=0.35):
    """irregular flat puddle polygon (fan) on the floor"""
    r = np.random.default_rng(seed)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rad = radius * (1 + r.uniform(-rough, rough, n))
    P = [(0, 0, z)] + [(rad[i] * np.cos(ang[i]), rad[i] * np.sin(ang[i]), z) for i in range(n)]
    P = np.array(P)
    Tr = [[0, 1 + i, 1 + (i + 1) % n] for i in range(n)]
    UV = np.stack([0.5 + P[:, 0] / (2.4 * radius), 0.5 - P[:, 1] / (2.4 * radius)], 1)
    return g.Mesh(P, np.tile([0, 0, 1.0], (len(P), 1)), UV, Tr)


def card(center, w, h, normal='+y'):
    """fit-UV quad (for glow cards / sparks)"""
    return g.plane(w, h, center, normal)


def cross_cards(center, size):
    """two crossed vertical quads + one horizontal (spark / glow billboard substitute)"""
    c = np.asarray(center, float)
    return g.merge(g.plane(size, size, c, '+y'), g.plane(size, size, c, '+x'), g.plane(size, size, c, '+z'))

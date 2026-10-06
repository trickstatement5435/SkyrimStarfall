"""Build every Starfall Research Site prop NIF + manifest.json.
Conventions: Skyrim units, Z up, +Y = the side a person uses, origin = centre of the base on the floor (z = 0)
unless noted (wall-mounted: origin on the wall surface, object extends toward +Y; ceiling: origin on the ceiling surface).
usage: python3 make_props.py [--no-preview] [name ...]"""
import os, sys, json, numpy as np
import geom as g
from propkit import Prop, write, MATS, icosphere, blob, pillow, crystal_prism, railing, ibeam, jagged_ring, shard, splat_poly, card, cross_cards
from geom import box, box_c, bevel_box, bevel_box_c, cylinder, lathe, disk, cyl_between, box_between, sweep, plane, quad, merge

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'meshes', 'StarfallSite', 'props'))
PREV = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'build', 'prop_previews'))
REG = {}


def prop(fn):
    REG[fn.__name__] = fn
    return fn


def fit_face(mn, mx, face):
    """single box face with 0..1 UVs (labels, screens, crate sides)"""
    return box(mn, mx, uv='fit', faces=[face])


def tex_box(mn, mx, faces_fit, rest_mat, p, fit_mat):
    """box whose listed faces use fit_mat (0..1 UV) and the remaining faces rest_mat"""
    allf = ['+x', '-x', '+y', '-y', '+z', '-z']
    p.add(fit_mat, box(mn, mx, uv='fit', faces=faces_fit))
    rest = [f for f in allf if f not in faces_fit]
    if rest: p.add(rest_mat, box(mn, mx, faces=rest))


# ====================================================================== lab furniture
def _lab_table_parts(p, W=140, D=70, H=55, ox=0.0, oy=0.0):
    hw, hd = W / 2, D / 2
    top = bevel_box((ox - hw, oy - hd, H - 4), (ox + hw, oy + hd, H), 1.2)
    p.add('metal_dark', top)
    # aprons under the top
    p.add('metal_panel', box((ox - hw + 3, oy - hd + 3, H - 12), (ox + hw - 3, oy - hd + 5, H - 4)),
          box((ox - hw + 3, oy + hd - 5, H - 12), (ox + hw - 3, oy + hd - 3, H - 4)),
          box((ox - hw + 3, oy - hd + 5, H - 12), (ox - hw + 5, oy + hd - 5, H - 4)),
          box((ox + hw - 5, oy - hd + 5, H - 12), (ox + hw - 3, oy + hd - 5, H - 4)))
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = ox + sx * (hw - 6), oy + sy * (hd - 6)
            legs.append(bevel_box((cx - 2.5, cy - 2.5, 2), (cx + 2.5, cy + 2.5, H - 4), 0.6))
            legs.append(box((cx - 3.5, cy - 3.5, 0), (cx + 3.5, cy + 3.5, 2)))  # foot
    p.add('metal_panel', *legs)
    # lower shelf
    p.add('metal_panel', bevel_box((ox - hw + 6, oy - hd + 6, 14), (ox + hw - 6, oy + hd - 6, 16), 0.5))
    p.add('hazard', box((ox - hw + 3, oy + hd - 3.01, H - 12), (ox + hw - 3, oy + hd - 3, H - 4), faces=['+y']).translate(0, 0.05, 0))
    return [(ox - hw, oy - hd, H - 4), (ox + hw, oy + hd, H)]


def _lab_table_col(p, W=140, D=70, H=55, ox=0.0, oy=0.0):
    hw, hd = W / 2, D / 2
    p.box((ox - hw, oy - hd, H - 12), (ox + hw, oy + hd, H))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = ox + sx * (hw - 6), oy + sy * (hd - 6)
            p.box((cx - 3.5, cy - 3.5, 0), (cx + 3.5, cy + 3.5, H - 12))
    p.box((ox - hw + 6, oy - hd + 6, 14), (ox + hw - 6, oy + hd - 6, 16))


@prop
def lab_table():
    p = Prop('lab_table', notes='metal lab bench 140x70x55 with lower shelf; top surface z=55')
    _lab_table_parts(p); _lab_table_col(p)
    p.extra['surface_z'] = 55
    return p


def _crt(p, cx, cy, cz, s=1.0, broken=False):
    """beige CRT terminal facing +Y, base centre at (cx,cy,cz); returns screen centre"""
    W, D, H = 40 * s, 38 * s, 34 * s
    # front bezel block + tapered back (hull)
    front = bevel_box((cx - W / 2, cy + D / 2 - 14 * s, cz + 3 * s), (cx + W / 2, cy + D / 2, cz + 3 * s + H), 2.0 * s)
    back_pts = [(cx + sx * W / 2 * k, cy + D / 2 - 14 * s, cz + 3 * s + H / 2 + sz * H / 2 * k) for sx in (-1, 1) for sz in (-1, 1) for k in (0.98,)]
    back_pts += [(cx + sx * W / 2 * 0.55, cy - D / 2, cz + 3 * s + H / 2 + sz * H / 2 * 0.6) for sx in (-1, 1) for sz in (-1, 1)]
    back = g.hull_mesh(back_pts)
    stand = merge(cylinder(10 * s, 3 * s, 10, z0=cz).translate(cx, cy + 2 * s, 0), box((cx - 6 * s, cy - 4 * s, cz + 2 * s), (cx + 6 * s, cy + 8 * s, cz + 4 * s)))
    p.add('plastic', front, back, stand)
    # screen inset: dark recess + screen face
    sw, sh = W * 0.74, H * 0.68
    zc = cz + 3 * s + H * 0.55; yf = cy + D / 2
    p.add('metal_dark', box((cx - sw / 2 - 1.5 * s, yf - 2.0 * s, zc - sh / 2 - 1.5 * s), (cx + sw / 2 + 1.5 * s, yf + 0.02, zc + sh / 2 + 1.5 * s), faces=['+y']))
    if broken:
        p.add('rubber', plane(sw, sh, (cx, yf + 0.06, zc), '+y'))
    else:
        p.add('screen_terminal', plane(sw, sh, (cx, yf + 0.25, zc), '+y'))
    # vents + power light
    p.add('metal_dark', *[box((cx - W / 2 + 4 * s + i * 3 * s, yf + 0.05, cz + 5 * s), (cx - W / 2 + 5.5 * s + i * 3 * s, yf + 0.3, cz + 6.5 * s), faces=['+y']) for i in range(5)])
    if not broken:
        p.add('lamp', disk(0.9 * s, 0, 8, True).rotate(g.rot_x(-90)).translate(cx + W / 2 - 4 * s, yf + 0.3, cz + 6 * s))
    return (cx, yf, zc, sw, sh)


def _keyboard(p, cx, cy, cz, s=1.0):
    kw, kd = 44 * s, 15 * s
    pts = [(cx + sx * kw / 2, cy + sy * kd / 2, cz + (0 if sy > 0 else 0)) for sx in (-1, 1) for sy in (-1, 1)]
    pts += [(cx + sx * kw / 2, cy - kd / 2, cz + 3.2 * s) for sx in (-1, 1)] + [(cx + sx * kw / 2, cy + kd / 2, cz + 1.4 * s) for sx in (-1, 1)]
    body = g.hull_mesh(pts)
    p.add('plastic', body)
    top = quad([(cx - kw / 2 + 1, cy + kd / 2 - 1, cz + 1.45 * s), (cx + kw / 2 - 1, cy + kd / 2 - 1, cz + 1.45 * s),
                (cx + kw / 2 - 1, cy - kd / 2 + 1, cz + 3.25 * s), (cx - kw / 2 + 1, cy - kd / 2 + 1, cz + 3.25 * s)], facing=(0, 0.3, 1))
    p.add('keyboard', top.translate(0, 0, 0.08))


@prop
def terminal_standalone():
    p = Prop('terminal_standalone', notes='CRT terminal + keyboard for placing on tables/desks; screen faces +Y; glow screen')
    _crt(p, 0, -6, 0)
    _keyboard(p, 0, 22, 0)
    p.box((-20, -25, 0), (20, 13, 37))
    p.box((-22, 14, 0), (22, 30, 3.5))
    return p


@prop
def desk_terminal():
    p = Prop('desk_terminal', notes='office desk 120x60x52 with CRT terminal (glow screen) and keyboard; user side +Y')
    W, D, H = 120, 60, 52
    p.add('metal_dark', bevel_box((-W / 2, -D / 2, H - 3), (W / 2, D / 2, H), 1.0))
    # left pedestal with 3 drawers, right panel leg, modesty panel
    p.add('metal_panel', box((-W / 2 + 2, -D / 2 + 2, 0), (-W / 2 + 42, D / 2 - 2, H - 3)))
    for i, (z0, z1) in enumerate(((3, 17), (18, 32), (33, 47))):
        p.add('metal_panel', bevel_box((-W / 2 + 4, D / 2 - 2, z0), (-W / 2 + 40, D / 2 - 0.5, z1), 0.6))
        p.add('metal_dark', box((-W / 2 + 15, D / 2 - 0.5, (z0 + z1) / 2 + 2), (-W / 2 + 29, D / 2 + 1.5, (z0 + z1) / 2 + 3.5)))
    p.add('metal_panel', box((W / 2 - 4, -D / 2 + 2, 0), (W / 2 - 1, D / 2 - 2, H - 3)))
    p.add('metal_panel', box((-W / 2 + 42, -D / 2 + 3, 18), (W / 2 - 4, -D / 2 + 5, H - 3)))
    _crt(p, 10, -8, H)
    _keyboard(p, 8, 18, H)
    # papers / clipboard
    p.add('poster', box((-48, 2, H), (-26, 22, H + 0.4), uv='fit', faces=['+z']))
    p.box((-W / 2, -D / 2, 0), (W / 2, D / 2, H))
    p.box((-10, -27, H), (30, 11, H + 37))
    p.extra['surface_z'] = H
    return p


@prop
def console_bank():
    p = Prop('console_bank', notes='floor-standing wall console 200x60x110, back against wall at y=-30; sloped control panel + 2 glow screens. Origin at base centre.')
    W = 200; hw = W / 2
    # profile (y, z) counter-clockwise seen from +X: body, slope, upper back
    prof = [(-30, 0), (26, 0), (26, 8), (30, 10), (30, 72), (2, 92), (2, 110), (-30, 110)]
    body = g.prism_profile(prof, -hw, hw, uv_scale=128)
    p.add('metal_panel', body)
    # kick plate hazard + inset
    p.add('hazard', box((-hw + 2, 26, 0.5), (hw - 2, 26.3, 7.5), faces=['+y']))
    # front lower doors: inset panels
    for i in range(4):
        x0 = -hw + 6 + i * 48
        p.add('metal_dark', bevel_box((x0, 29.5, 14), (x0 + 44, 30.8, 66), 0.5))
        p.add('metal_panel', box((x0 + 38, 30.8, 36), (x0 + 40, 32.5, 46)))
    # sloped control surface: quad with control_panel texture, slightly above the slope
    a = np.array([30, 72.0]); b = np.array([2, 92.0]); n = np.array([b[1] - a[1], -(b[0] - a[0])]); n /= np.linalg.norm(n)
    off = n * 0.3
    for i in range(3):
        x0, x1 = -hw + 6 + i * 63, -hw + 6 + i * 63 + 60
        q = quad([(x0, a[0] + off[0] - 2, a[1] + off[1] + 1.4), (x1, a[0] + off[0] - 2, a[1] + off[1] + 1.4),
                  (x1, b[0] + off[0] + 2, b[1] + off[1] - 1.4), (x0, b[0] + off[0] + 2, b[1] + off[1] - 1.4)], facing=(0, n[0], n[1]))
        p.add('control_panel', q)
    # trim along the slope edges
    p.add('metal_dark', box_between((-hw, 30, 72), (hw, 30, 72), 2.5, 2.5), box_between((-hw, 2, 92), (hw, 2, 92), 2.5, 2.5))
    # two screens in the upper section, recessed bezels
    for i, mat in enumerate(('screen_terminal', 'screen_graphs')):
        cx = -45 + i * 90
        p.add('metal_dark', bevel_box((cx - 32, 2, 93), (cx + 32, 6, 109), 1.0))
        p.add(mat, plane(56, 13, (cx, 6.2, 101), '+y'))
    # side vents + top lip
    for sx in (-1, 1):
        for k in range(6):
            p.add('metal_dark', box((sx * (hw + 0.3) - 0.3, -20 + k * 6, 30), (sx * (hw + 0.3) + 0.3, -16 + k * 6, 60), faces=['+x' if sx > 0 else '-x']))
    p.add('metal_dark', box((-hw - 1, -31, 110), (hw + 1, 4, 112)))
    p.hull([(x, y, z) for x in (-hw, hw) for (y, z) in prof] + [(x, y, 112) for x in (-hw - 1, hw + 1) for y in (-31, 4)])
    p.extra['back_y'] = -30
    return p


@prop
def server_rack():
    p = Prop('server_rack', notes='server rack 60x80x200 (front +Y) with blinking-light glow front')
    W, D, H = 60, 80, 200
    hw, hd = W / 2, D / 2
    frame = [box((-hw, -hd, 0), (-hw + 4, hd, H)), box((hw - 4, -hd, 0), (hw, hd, H)), box((-hw, -hd, H - 6), (hw, hd, H)),
             box((-hw, -hd, 0), (hw, hd, 6)), box((-hw + 4, -hd, 6), (hw - 4, -hd + 2, H - 6))]
    p.add('metal_dark', *frame)
    p.add('server_lights', plane(W - 8, H - 12, (0, hd - 2, H / 2), '+y'))
    # front door frame bars + handle
    p.add('metal_dark', box((-hw, hd - 2, 6), (-hw + 4, hd + 1, H - 6)), box((hw - 4, hd - 2, 6), (hw, hd + 1, H - 6)),
          box((hw - 3.5, hd + 1, 90), (hw - 1.5, hd + 4, 120)))
    # side vent slots
    for sx in (-1, 1):
        for k in range(10):
            p.add('rubber', box((sx * hw - 0.2, -30 + k * 6, 150), (sx * hw + 0.2, -27 + k * 6, 185), faces=['+x' if sx > 0 else '-x']))
    # top fans
    for k in (-1, 1):
        p.add('rubber', disk(10, H + 0.2, 12, True, center=(0, k * 18)))
        p.box((-hw, -hd, 0), (hw, hd + 4, H))
    return p


def _shelf(p, stocked=False, seed=0):
    W, D, H = 120, 45, 200
    hw, hd = W / 2, D / 2
    posts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (hw - 2), sy * (hd - 2)
            posts += [box((x - 2, y - 2, 0), (x + 2, y + 2, H))]
    p.add('metal_dark', *posts)
    levels = [12, 72, 132, 192]
    for z in levels:
        p.add('metal_panel', box((-hw + 1, -hd + 1, z - 2), (hw - 1, hd - 1, z)))
        p.add('metal_dark', box((-hw, hd - 0.5, z - 5), (hw, hd + 0.5, z)), box((-hw, -hd - 0.5, z - 5), (hw, -hd + 0.5, z)))
    # back X braces
    p.add('metal_dark', box_between((-hw + 2, -hd + 1, 14), (hw - 2, -hd + 1, 190), 1.2, 0.6, up=(0, 1, 0)),
          box_between((hw - 2, -hd + 1, 14), (-hw + 2, -hd + 1, 190), 1.2, 0.6, up=(0, 1, 0)))
    for z in levels:
        p.box((-hw, -hd, z - 5), (hw, hd, z))
    for sx in (-1, 1):
        p.box((sx * (hw - 2) - 2, -hd, 0), (sx * (hw - 2) + 2, hd, H))
    if not stocked: return
    r = np.random.default_rng(seed)
    for z in levels[:3]:
        x = -hw + 4
        while x < hw - 12:
            kind = r.choice(['box', 'box', 'jar', 'can', 'binders', 'gap'])
            if kind == 'box':
                w = r.uniform(22, 36); d = r.uniform(24, 38); h = r.uniform(16, 40) if z < 130 else r.uniform(14, 30)
                if x + w > hw - 3: break
                yc = r.uniform(-2, 2)
                m = box((x, yc - d / 2, z), (x + w, yc + d / 2, z + h), uv='fit')
                p.add('cardboard', g.transform(m, T=(0, 0, 0)))
                x += w + r.uniform(1, 4)
            elif kind == 'jar':
                for k in range(int(r.integers(2, 4))):
                    if x + 10 > hw - 3: break
                    cx = x + 5; cy = r.uniform(-10, 10)
                    p.add('glass', cylinder(4.5, 13, 10, z0=z, caps=True).translate(cx, cy, 0), world=True)
                    p.add('liquid' if r.random() < 0.5 else 'specimen', cylinder(3.8, 8, 8, z0=z + 0.5, caps=True).translate(cx, cy, 0))
                    p.add('metal_dark', cylinder(4.8, 2, 10, z0=z + 13).translate(cx, cy, 0))
                    x += 11
            elif kind == 'can':
                for k in range(int(r.integers(1, 3))):
                    if x + 18 > hw - 3: break
                    m = lathe([(0, 0), (8, 0), (8, 22), (0, 22)], 12)
                    p.add('barrel_hazard' if r.random() < 0.5 else 'barrel_toxic', m.translate(x + 9, r.uniform(-8, 8), z))
                    x += 19
            elif kind == 'binders':
                for k in range(int(r.integers(3, 7))):
                    if x + 4 > hw - 3: break
                    p.add('plastic', box((x, -12, z), (x + 3.5, 12, z + 28)))
                    x += 4
                x += 3
            else:
                x += r.uniform(8, 20)


@prop
def shelf_metal():
    p = Prop('shelf_metal', notes='metal shelving 120x45x200, 4 shelves at z=12/72/132/192 (shelf collision per level so items can sit on them)')
    _shelf(p)
    p.extra['shelf_z'] = [12, 72, 132, 192]
    return p


@prop
def shelf_metal_stocked():
    p = Prop('shelf_metal_stocked', notes='shelf_metal stocked with boxes, jars, cans and binders (no separate collision for contents)')
    _shelf(p, True, seed=7)
    return p


# ====================================================================== containment tanks
def _tank_base_cap(p, R=45):
    base = lathe([(0, 0), (R, 0), (R, 22), (R - 3, 26), (R - 5, 26), (R - 5, 30), (0, 30)], 24, uv_scale=64)
    p.add('metal_panel', base, world=True)
    p.add('hazard', lathe([(R + 0.3, 6), (R + 0.3, 16)], 24, uv_scale=None, u_repeat=8))
    cap = lathe([(0, 200), (R - 5, 200), (R - 5, 204), (R, 206), (R, 222), (R - 8, 230), (0, 230)], 24, uv_scale=64)
    p.add('metal_panel', cap, world=True)
    # struts
    for k in range(4):
        a = np.radians(45 + k * 90)
        x, y = (R - 3) * np.cos(a), (R - 3) * np.sin(a)
        p.add('metal_dark', box_c((x, y, 115), (5, 5, 172)).rotate(g.rot_z(np.degrees(a))) if False else
              g.transform(box((-2.5, -2.5, 28), (2.5, 2.5, 202)), T=(x, y, 0), R=g.rot_z(np.degrees(a))))
    # top pipes + valve
    p.add('metal_dark', sweep([(10, 0, 229), (10, 0, 245), (20, 0, 255), (60, 0, 255)], 4, 10))
    p.add('rust', cylinder(7, 6, 10, z0=230).translate(-14, 6, 0))
    # base control strip: small glow panel on +Y
    p.add('control_panel', plane(30, 12, (0, R + 0.2, 16), '+y'))


@prop
def containment_tank():
    p = Prop('containment_tank', notes='specimen containment tank, 90 dia x 230; glass tube (alpha blend, double sided), glowing liquid column', havok='metal')
    _tank_base_cap(p)
    p.add('glass', lathe([(38, 30), (38, 200)], 24, uv_scale=None, u_repeat=3))
    p.add('liquid_clear', cylinder(35, 162, 20, z0=30.5, caps=True, uv_scale=64), world=False)
    # bubbles (small spheres)
    r = np.random.default_rng(3)
    for k in range(14):
        a = r.uniform(0, 2 * np.pi); d = r.uniform(0, 26)
        p.add('fx_green', icosphere(r.uniform(1.0, 2.2), 1).translate(d * np.cos(a), d * np.sin(a), r.uniform(40, 185)))
    # specimen silhouette floating inside
    p.add('specimen', blob((22, 18, 28), seed=5, rough=0.35).translate(0, 0, 100))
    ang = np.radians(np.arange(16) * 22.5)
    p.hull([(45 * np.cos(a), 45 * np.sin(a), z) for a in ang for z in (0, 230)])
    return p


@prop
def containment_tank_broken():
    p = Prop('containment_tank_broken', notes='broken containment tank: jagged glass remnants, empty, liquid puddle on base and floor', havok='metal')
    _tank_base_cap(p)
    r = np.random.default_rng(11)
    heights = r.uniform(4, 45, 20); heights[3:6] = r.uniform(50, 80, 3)
    p.add('glass_cracked', jagged_ring(38, 30, heights), world=False)
    top_heights = r.uniform(3, 22, 20)
    teeth = jagged_ring(38, 0, top_heights)
    teeth = g.transform(teeth, S=(1, 1, -1)).translate(0, 0, 200)
    p.add('glass_cracked', teeth, world=False)
    for k in range(9):
        a = r.uniform(0, 2 * np.pi); d = r.uniform(50, 110)
        p.add('glass_cracked', shard((d * np.cos(a), d * np.sin(a), 0.4), r.uniform(5, 12), k), world=True)
    p.add('liquid', disk(32, 30.4, 20, True, uv_scale=64))
    puddle = splat_poly(72, seed=4, n=18, z=0.35, rough=0.3).translate(12, 22, 0)
    p.add('fx_green', puddle)
    p.add('liquid', splat_poly(55, seed=9, n=14, z=0.3, rough=0.35).translate(18, 28, 0), world=True)
    ang = np.radians(np.arange(16) * 22.5)
    p.hull([(45 * np.cos(a), 45 * np.sin(a), z) for a in ang for z in (0, 30)])
    p.hull([(45 * np.cos(a), 45 * np.sin(a), z) for a in ang for z in (200, 230)])
    for k in range(4):
        a = np.radians(45 + k * 90); x, y = 42 * np.cos(a), 42 * np.sin(a)
        p.box((x - 3, y - 3, 30), (x + 3, y + 3, 200))
    p.footprint = [-45, -45, 45, 45]
    return p


def _jar(p, cx, cy, cz, seed=0, col=True):
    p.add('metal_dark', lathe([(0, 0), (12, 0), (12, 2), (10, 3.5), (0, 3.5)], 14).translate(cx, cy, cz))
    p.add('glass', lathe([(9, 3.5), (9.5, 5), (9.5, 24), (8, 26), (8, 27)], 14, uv_scale=None).translate(cx, cy, cz), world=True)
    p.add('liquid', lathe([(0, 3.6), (8.8, 3.6), (8.8, 20), (0, 20)], 12).translate(cx, cy, cz), world=True)
    p.add('specimen', blob((9, 8, 10), seed=seed, rough=0.4, sub=1).translate(cx, cy, cz + 8))
    p.add('metal_dark', lathe([(8.6, 26.5), (8.6, 30), (0, 30)], 14).translate(cx, cy, cz))
    if col:
        ang = np.radians(np.arange(8) * 45)
        p.hull([(cx + 12 * np.cos(a), cy + 12 * np.sin(a), cz + z) for a in ang for z in (0, 30)], 'glass')


@prop
def specimen_jar():
    p = Prop('specimen_jar', notes='glass specimen jar 20 dia x 30 on a small metal stand; for tables/shelves')
    _jar(p, 0, 0, 0, seed=2)
    return p


@prop
def specimen_table():
    p = Prop('specimen_table', notes='lab_table with 3 specimen jars on top')
    _lab_table_parts(p); _lab_table_col(p)
    for i, x in enumerate((-40, 0, 42)):
        _jar(p, x, -8 + (i % 2) * 14, 55, seed=10 + i, col=False)
    p.box((-55, -22, 55), (55, 22, 85), 'glass')
    return p


# ====================================================================== crates, lockers, barrels
def _crate(p, s, center=(0, 0, 0), rotz=0.0):
    m = box((-s / 2, -s / 2, 0), (s / 2, s / 2, s), uv='fit')
    m = g.transform(m, T=center, R=g.rot_z(rotz))
    p.add('crate', m)
    pts = g.transform(box((-s / 2, -s / 2, 0), (s / 2, s / 2, s)), T=center, R=g.rot_z(rotz)).P
    p.hull(pts, 'wood')


@prop
def crate_small():
    p = Prop('crate_small', notes='Half-Life style wooden supply crate 64x64x64')
    _crate(p, 64); return p


@prop
def crate_large():
    p = Prop('crate_large', notes='wooden supply crate 96x96x96')
    _crate(p, 96); return p


@prop
def crate_stack():
    p = Prop('crate_stack', notes='two large crates side by side + one small crate on top')
    _crate(p, 96, (-50, 0, 0), 2)
    _crate(p, 96, (50, 4, 0), -4)
    _crate(p, 64, (-30, 2, 96), 12)
    return p


@prop
def locker():
    p = Prop('locker', kind='container', notes='metal locker 50x45x190, door on +Y (static mesh, use as CONT model)')
    W, D, H = 50, 45, 190
    hw, hd = W / 2, D / 2
    p.add('metal_panel', bevel_box((-hw, -hd, 4), (hw, hd, H), 0.8))
    p.add('metal_dark', box((-hw + 1, -hd + 1, 0), (hw - 1, hd - 1, 4)))
    p.add('metal_panel', bevel_box((-hw + 2, hd - 0.5, 8), (hw - 2, hd + 1.2, H - 4), 0.5))
    for k in range(5):
        z = H - 30 + k * 4
        p.add('rubber', box((-12, hd + 1.2, z), (12, hd + 1.4, z + 1.8), faces=['+y']))
        p.add('rubber', box((-12, hd + 1.2, 20 + k * 4), (12, hd + 1.4, 21.8 + k * 4), faces=['+y']))
    p.add('metal_dark', box((hw - 9, hd + 1.2, 95), (hw - 5, hd + 4, 115)))
    p.add('sign_restricted', plane(14, 7, (0, hd + 1.3, 150), '+y'))
    p.box((-hw, -hd, 0), (hw, hd + 2, H))
    return p


@prop
def filing_cabinet():
    p = Prop('filing_cabinet', kind='container', notes='4-drawer filing cabinet 45x60x130, drawers on +Y')
    W, D, H = 45, 60, 130
    hw, hd = W / 2, D / 2
    p.add('metal_panel', bevel_box((-hw, -hd, 2), (hw, hd, H), 0.8))
    p.add('metal_dark', box((-hw + 1, -hd + 1, 0), (hw - 1, hd - 1, 2)))
    for i in range(4):
        z0 = 5 + i * 31
        p.add('metal_panel', bevel_box((-hw + 2, hd - 0.5, z0), (hw - 2, hd + 1.0, z0 + 29), 0.5))
        p.add('metal_dark', box((-8, hd + 1, z0 + 18), (8, hd + 3.5, z0 + 20.5)))
        p.add('poster', box((-5, hd + 1.0, z0 + 22), (5, hd + 1.1, z0 + 26), uv='fit', faces=['+y']))
    p.box((-hw, -hd, 0), (hw, hd + 3, H))
    return p


def _barrel(p, mat, R=30, H=90):
    prof = [(R - 1.5, 2), (R, 4), (R, H - 4), (R - 1.5, H - 2)]
    body = lathe(prof, 24, uv_scale=None, u_repeat=1.0)
    # V from 0 (bottom) to 1 (top) -> flip so texture reads upright
    body.UV[:, 1] = 1 - (body.P[:, 2] - 2) / (H - 4)
    p.add(mat, body)
    rims = lathe([(0, 0), (R - 2, 0), (R - 1, 1), (R - 1.5, 2)], 24)
    rims2 = lathe([(R - 1.5, H - 2), (R - 1, H - 1), (R - 2, H), (R - 3, H - 0.6)], 24)
    p.add('metal_dark', rims, rims2)
    p.add('metal_dark', lathe([(R - 3, H - 0.6), (0, H - 0.6)], 24))
    p.add('metal_dark', cylinder(3.5, 1.2, 10, z0=H - 0.6).translate(R * 0.55, 0, 0), cylinder(2.5, 1.0, 8, z0=H - 0.6).translate(-R * 0.55, 0, 0))
    ang = np.radians(np.arange(12) * 30)
    p.hull([(R * np.cos(a), R * np.sin(a), z) for a in ang for z in (0, H)])


@prop
def barrel_hazard():
    p = Prop('barrel_hazard', notes='yellow hazard drum 60 dia x 90', havok='barrel')
    _barrel(p, 'barrel_hazard'); return p


@prop
def barrel_toxic():
    p = Prop('barrel_toxic', notes='green toxic drum 60 dia x 90, leaking glowing liquid (glow map) + puddle', havok='barrel')
    _barrel(p, 'barrel_toxic')
    p.add('liquid', splat_poly(34, seed=21, n=14, z=0.3, rough=0.35).translate(8, 30, 0), world=True)
    p.add('fx_green', splat_poly(38, seed=22, n=14, z=0.45, rough=0.3).translate(8, 30, 0))
    p.footprint = [-30, -30, 30, 30]
    return p


# ====================================================================== pipes and ducts
def _flange(p, x, r, axis='x', mat='metal_dark'):
    m = cylinder(r + 4, 3, 16, z0=-1.5)
    m = g.transform(m, R=g.rot_y(90)) if axis == 'x' else m
    p.add(mat, m.translate(x, 0, 0) if axis == 'x' else m)


def _bolt_ring(p, x, r, n=8):
    for k in range(n):
        a = 2 * np.pi * k / n
        p.add('metal_dark', box_c((x, (r + 2) * np.cos(a), (r + 2) * np.sin(a)), (4.2, 1.6, 1.6)))


@prop
def pipe_straight_256():
    p = Prop('pipe_straight_256', notes='straight pipe, radius 8 (flanges 12), axis along X from -128 to +128; origin ON THE PIPE AXIS at its centre (kit snapping)')
    body = g.transform(cylinder(8, 256, 16, z0=-128, caps=False, uv_scale=64), R=g.rot_y(90))
    p.add('metal_dark', body, world=False)
    for x in (-126.5, 126.5):
        p.add('metal_dark', g.transform(cylinder(12, 3, 16, z0=-1.5), R=g.rot_y(90)).translate(x, 0, 0))
        _bolt_ring(p, x, 9.5)
    p.add('hazard', g.transform(cylinder(8.3, 10, 16, z0=-5, caps=False, uv_scale=None, u_repeat=4), R=g.rot_y(90)).translate(80, 0, 0))
    p.hull([(x, 12 * np.cos(a), 12 * np.sin(a)) for x in (-128, 128) for a in np.radians(np.arange(8) * 45)])
    p.footprint = 0
    return p


@prop
def pipe_elbow():
    R = 32
    p = Prop('pipe_elbow', notes='90 degree elbow, radius 8, bend radius 32: inlet at origin heading +X, outlet at (32,0,32) heading +Z. Origin on the pipe axis at the inlet flange')
    path = g.arc_path((0, 0, R), R, -90, 0, steps=10, plane='xz')
    p.add('metal_dark', sweep(path, 8, 16, caps=False), world=False)
    p.add('metal_dark', g.transform(cylinder(12, 3, 16, z0=0), R=g.rot_y(90)))
    p.add('metal_dark', cylinder(12, 3, 16, z0=R - 3).translate(R, 0, 0))
    p.hull(np.concatenate([path + [0, dy, dz] for dy in (-12, 12) for dz in (-12, 12)] + [path + [dx, 0, 0] for dx in (-12, 12)]))
    p.footprint = 0
    return p


@prop
def pipe_cluster_wall():
    p = Prop('pipe_cluster_wall', notes='4 wall pipes + brackets running 256 along X (-128..128); WALL-MOUNTED: origin on the wall surface at the bottom of the brackets, pipes extend toward +Y (max 26). Tiles every 256')
    pipes = [(14, 12, 10, 'metal_dark'), (10, 36, 6, 'rust'), (12, 56, 8, 'metal_panel'), (8, 74, 4, 'metal_dark')]
    for (y, z, r, mat) in pipes:
        m = g.transform(cylinder(r, 256, 14, z0=-128, caps=False, uv_scale=64), R=g.rot_y(90)).translate(0, y, z)
        p.add(mat, m, world=False)
    for bx in (-64, 64):
        p.add('metal_dark', box((bx - 3, 0, 0), (bx + 3, 3, 82)))
        for (y, z, r, mat) in pipes:
            arc = g.arc_path((bx, y, z), r + 1, -90, 90, steps=8, plane='yz')
            arc = np.stack([np.full(len(arc), bx), y - (arc[:, 1] - y) * 0 + (arc[:, 1] - y), arc[:, 2]], 1)
            strap = sweep(np.concatenate([[(bx, 0, z - r - 1)], arc[::-1] * [1, 1, 1], [(bx, 0, z + r + 1)]]) if False else
                          np.concatenate([[(bx, 1.5, z - r - 1)], [(bx, y + (r + 1) * np.cos(t), z + (r + 1) * np.sin(t)) for t in np.linspace(-np.pi / 2, np.pi / 2, 9)], [(bx, 1.5, z + r + 1)]]),
                          0.9, 6, caps=True)
            p.add('metal_dark', strap, world=False)
    # valve wheel on the big pipe
    vx, vy, vz = 96, 14 + 10 + 10, 12
    p.add('metal_dark', box_c((vx, 14 + 13, vz), (6, 10, 6)))
    rim = sweep(g.arc_path((vx, vy, vz), 9, 0, 360, steps=16, plane='xz')[:, [0, 1, 2]], 1.2, 6, closed=False)
    rim = g.transform(sweep(g.arc_path((0, 0, 0), 9, 0, 360, 16, plane='xy'), 1.2, 6), R=g.rot_x(90)).translate(vx, vy, vz)
    p.add('rust', rim, world=False)
    for k in range(3):
        a = np.radians(k * 120)
        p.add('rust', cyl_between((vx, vy, vz), (vx + 9 * np.cos(a), vy, vz + 9 * np.sin(a)), 0.9, 6))
    p.box((-128, 0, 0), (128, 26, 82))
    p.footprint = 0
    p.extra['mount'] = 'wall'
    return p


@prop
def vent_duct_256():
    p = Prop('vent_duct_256', notes='rectangular ceiling duct 64 wide x 48 tall along X (-128..128); CEILING-MOUNTED: origin on the ceiling surface, duct hangs from z=-10 to -58. Tiles every 256')
    p.add('metal_panel', box((-128, -32, -58), (128, 32, -10)), world=True)
    for x in (-126, 0, 126):
        p.add('metal_dark', box((x - 2, -34, -60), (x + 2, 34, -8)))
    for x in (-64, 64):
        for y in (-35, 35):
            p.add('metal_dark', cyl_between((x, y, -61), (x, y, 0), 0.8, 6))
        p.add('metal_dark', box((x - 2, -36, -62), (x + 2, 36, -60)))
    # bottom grille
    p.add('metal_dark', box((40, -20, -58.6), (90, 20, -58.0), faces=['-z']))
    p.add('grate', plane(46, 36, (65, 0, -58.8), '-z'), world=True)
    p.box((-128, -36, -62), (128, 36, 0))
    p.footprint = 0
    p.extra['mount'] = 'ceiling'
    return p


# ====================================================================== lights
@prop
def fluorescent_ceiling():
    p = Prop('fluorescent_ceiling', kind='light_fixture', notes='ceiling light panel 120x30; CEILING-MOUNTED: origin on the ceiling surface, hangs down to z=-8; glowing diffuser faces -Z. Add a LIGH at about (0,0,-20)')
    p.add('metal_dark', bevel_box((-60, -15, -8), (60, 15, 0), 1.0))
    p.add('fluorescent', plane(116, 26, (0, 0, -8.06), '-z'))
    p.box((-60, -15, -8), (60, 15, 0))
    p.footprint = 0
    p.extra['mount'] = 'ceiling'; p.extra['light_offset'] = [0, 0, -20]
    return p


@prop
def wall_lamp():
    p = Prop('wall_lamp', kind='light_fixture', notes='caged wall lamp; WALL-MOUNTED: origin on the wall surface at the centre of the wall plate, lamp points +Y (out of the wall). Typical mount height 180-200. Add a LIGH at about (0,20,0)')
    p.add('metal_dark', bevel_box((-7, 0, -10), (7, 2, 10), 0.6))
    p.add('metal_dark', box((-2, 2, -2), (2, 8, 2)))
    R = g.rot_x(-90)  # +Z -> +Y
    p.add('metal_dark', g.transform(lathe([(0, 8), (7.5, 8), (7.5, 13), (6.5, 13.5)], 14), R=R))
    dome = lathe([(6.5, 13.5)] + [(6.5 * np.cos(t), 13.5 + 6.5 * np.sin(t)) for t in np.linspace(0.2, np.pi / 2, 5)], 14, uv_scale=None)
    dome = g.transform(dome, R=R)
    dome.UV = np.stack([0.5 + dome.P[:, 0] / 14, 0.5 - dome.P[:, 2] / 14], 1)
    p.add('lamp', dome)
    for k in range(4):
        a = np.radians(45 + k * 90)
        path = [(7.8 * np.cos(a), 13, 7.8 * np.sin(a))] + [(7.8 * np.cos(t) * np.cos(a), 13 + 7.8 * np.sin(t), 7.8 * np.cos(t) * np.sin(a)) for t in np.linspace(0.2, np.pi / 2, 6)]
        p.add('metal_dark', sweep(path, 0.45, 5), world=False)
    p.add('metal_dark', g.transform(sweep(g.arc_path((0, 0, 0), 7.8, 0, 360, 16, plane='xy'), 0.45, 5), R=R).translate(0, 13, 0), world=False)
    p.add('fx_lamp', plane(20, 20, (0, 20.5, 0), '+y'))
    p.box((-8, 0, -10), (8, 21, 10))
    p.footprint = 0
    p.extra['mount'] = 'wall'; p.extra['light_offset'] = [0, 20, 0]
    return p


@prop
def floodlight_tripod():
    p = Prop('floodlight_tripod', kind='light_fixture', notes='portable floodlight on a tripod, 230 tall, lamp faces +Y tilted down 15 deg; glowing lens. Add a spot LIGH near (0,25,215)')
    hub = np.array([0, 0, 110.0])
    feet = [np.array([70 * np.cos(a), 70 * np.sin(a), 0]) for a in np.radians([90 + 0, 210, 330])]
    for f in feet:
        p.add('metal_dark', cyl_between(f + [0, 0, 1.5], hub, 2.0, 8))
        p.add('rubber', box_c(f + [0, 0, 1.5], (8, 8, 3)))
        p.add('metal_dark', cyl_between(f * 0.45 + [0, 0, 50], (0, 0, 70), 1.2, 6))
    p.add('metal_dark', cylinder(4, 14, 10, z0=104))
    p.add('metal_panel', cylinder(2.6, 100, 10, z0=110, caps=True))
    p.add('metal_dark', cylinder(3.4, 8, 10, z0=150))
    # yoke + head
    p.add('metal_dark', box((-26, -3, 206), (26, 3, 210)), box((-26, -3, 206), (-22, 3, 226)), box((22, -3, 206), (26, 3, 226)))
    R = g.rot_x(-15)
    head = bevel_box((-21, -12, -14), (21, 10, 14), 2.0)
    p.add('metal_panel', g.transform(head, T=(0, 0, 218), R=R))
    lens = g.transform(plane(36, 24, (0, 10.3, 0), '+y'), T=(0, 0, 218), R=R)
    p.add('lamp', lens)
    for k in range(5):
        bar = g.transform(box((-18 + k * 9 - 0.5, 10.4, -12), (-18 + k * 9 + 0.5, 11.4, 12)), T=(0, 0, 218), R=R)
        p.add('metal_dark', bar)
    fins = [g.transform(box((-18, -15, -12 + k * 6), (18, -12, -11 + k * 6)), T=(0, 0, 218), R=R) for k in range(5)]
    p.add('metal_dark', *fins)
    p.add('fx_lamp', g.transform(plane(60, 44, (0, 14, 0), '+y'), T=(0, 0, 218), R=R))
    # cable to the ground
    cable = [(0, -12, 205), (0, -5, 190), (0, -4, 120), (2, -6, 100), (10, -20, 40), (20, -40, 2.2), (60, -60, 2.2), (110, -70, 2.2)]
    p.add('rubber', sweep(cable, 1.2, 6), world=False)
    for f in feet:
        p.hull([f + [dx, dy, 0] for dx in (-3, 3) for dy in (-3, 3)] + [hub + [dx, dy, 0] for dx in (-3, 3) for dy in (-3, 3)])
    p.box((-4, -4, 104), (4, 4, 206))
    p.hull(g.transform(head, T=(0, 0, 218), R=R).P)
    p.footprint = [-61, -35, 61, 70]
    p.extra['light_offset'] = [0, 25, 215]
    return p


# ====================================================================== generator, cable
@prop
def generator():
    p = Prop('generator', notes='diesel-style generator 220x120x150 on a skid; control panel (glow) on +Y side')
    L, D = 220, 120
    for y in (-50, 50):
        p.add('metal_dark', box((-110, y - 6, 0), (110, y + 6, 10)))
    for x in (-100, -30, 30, 100):
        p.add('metal_dark', box((x - 4, -50, 2), (x + 4, 50, 9)))
    for x in (-110, 110):
        p.add('hazard', box((x - 0.3 if x > 0 else x - 0.0, -56, 0.5), (x + 0.3 if x > 0 else x + 0.0, 56, 9.5), faces=['+x' if x > 0 else '-x']))
    body = bevel_box((-104, -55, 10), (104, 55, 140), 3.0)
    p.add('metal_panel_big', body)
    # radiator end (+X): recess + grille
    p.add('rubber', box((104, -40, 30), (104.4, 40, 125), faces=['+x']))
    p.add('grate', plane(80, 95, (104.8, 0, 77.5), '+x'), world=True)
    p.add('metal_dark', box((104, -44, 26), (107, -40, 129)), box((104, 40, 26), (107, 44, 129)), box((104, -44, 125), (107, 44, 129)), box((104, -44, 26), (107, 44, 30)))
    # side doors with louvres
    for sy in (-1, 1):
        y = sy * 55
        for i in range(3):
            x0 = -90 + i * 62
            p.add('metal_panel', bevel_box((x0, y - 1 if sy > 0 else y - 0.6, 20), (x0 + 56, y + 0.6 if sy > 0 else y + 1, 128), 0.6))
            for k in range(6):
                z = 96 + k * 4.5
                p.add('rubber', box((x0 + 8, y + sy * 0.65 - 0.05, z), (x0 + 48, y + sy * 0.65 + 0.05, z + 2), faces=['+y' if sy > 0 else '-y']))
            p.add('metal_dark', box((x0 + 48, y + sy * 0.6 - 1.2, 70), (x0 + 51, y + sy * 0.6 + 1.2, 82)))
    # control box on +Y near -X end
    p.add('metal_dark', bevel_box((-100, 55, 70), (-56, 66, 125), 1.0))
    p.add('control_panel', plane(40, 50, (-78, 66.1, 97.5), '+y'))
    p.add('sign_restricted', plane(30, 15, (40, 56.3, 112), '+y'))
    # exhaust + muffler + fuel cap + lifting eyes
    p.add('rust', cylinder(10, 60, 14, z0=0).rotate(g.rot_y(90)).translate(-40, 0, 155) if False else
          g.transform(cylinder(10, 60, 14, z0=-30, uv_scale=64), R=g.rot_y(90)).translate(-40, 20, 152), world=False)
    p.add('rust', cylinder(5, 40, 12, z0=152, caps=True).translate(-10, 20, 0))
    p.add('rust', cylinder(7, 3, 12, z0=192).translate(-10, 20, 0))
    for x in (-70, -10):
        p.add('metal_dark', box_c((x, 20, 146), (4, 4, 12)))
    p.add('metal_dark', cylinder(6, 3, 12, z0=140).translate(60, -30, 0))
    for (x, y) in ((-95, -45), (95, -45), (-95, 45), (95, 45)):
        p.add('metal_dark', g.transform(sweep(g.arc_path((0, 0, 0), 4, 0, 180, 6, plane='xz'), 1.0, 6), T=(x, y, 140)), world=False)
    # cable outlets
    p.add('rubber', g.transform(cylinder(3, 12, 8), R=g.rot_x(-90)).translate(-30, 55, 40), g.transform(cylinder(3, 12, 8), R=g.rot_x(-90)).translate(-20, 55, 40))
    p.box((-110, -56, 0), (110, 66, 140))
    p.box((-70, 8, 140), (0, 32, 195))
    return p


@prop
def power_cable_coil():
    p = Prop('power_cable_coil', notes='coiled heavy power cable on the floor (~70 dia, 12 high) with a tail running to +X and a plug; low, walk-over', havok='organic')
    pts = []
    turns = 4.3
    for t in np.linspace(0, turns * 2 * np.pi, int(turns * 18)):
        r = 24 + 8 * (t / (turns * 2 * np.pi))
        z = 2.4 + 4.4 * (np.sin(t * 0.5) * 0.5 + 0.5) * (t / (turns * 2 * np.pi))
        pts.append((r * np.cos(t), r * np.sin(t), z))
    last = np.array(pts[-1])
    tail = [last + (6, 6, -1), last + (25, 10, -max(0, last[2] - 2.4)), (70, 18, 2.4), (95, 6, 2.4), (115, 12, 2.4)]
    tail = [(x, y, max(z, 2.4)) for x, y, z in tail]
    p.add('rubber', sweep(pts + tail, 2.3, 8), world=False)
    p.add('hazard', box_c((122, 12, 3.5), (14, 8, 7)))
    p.add('metal_dark', box_c((131, 10, 3.5), (4, 1, 1)), box_c((131, 14, 3.5), (4, 1, 1)))
    ang = np.radians(np.arange(12) * 30)
    p.hull([(35 * np.cos(a), 35 * np.sin(a), z) for a in ang for z in (0, 10)], 'organic')
    p.footprint = 0
    return p


# ====================================================================== barriers and fences
@prop
def jersey_barrier():
    p = Prop('jersey_barrier', notes='concrete jersey barrier 200x60x80 (long axis X)', havok='stone')
    prof = [(-30, 0), (30, 0), (30, 8), (13, 26), (8, 78), (6, 80), (-6, 80), (-8, 78), (-13, 26), (-30, 8)]
    prof = [(y, z) for (y, z) in prof]
    # prism_profile expects CCW seen from +X: (y right, z up)
    p.add('concrete_plain', g.prism_profile(prof, -100, 100, uv_scale=128))
    # painted hazard band on both faces near the top + drain slots + pin loops
    for sy in (-1, 1):
        a, b = np.array([sy * 13.0, 26]), np.array([sy * 8.0, 78])
        q = quad([(-98, a[0] + sy * 0.15, 60), (98, a[0] + sy * 0.15, 60), (98, a[0] + sy * 0.15, 66), (-98, a[0] + sy * 0.15, 66)], facing=(0, sy, 0))
        # put the band on the slanted upper face: z 60..72 lies on line from a to b
        t0, t1 = (60 - 26) / 52, (72 - 26) / 52
        y0, y1 = a[0] + (b[0] - a[0]) * t0 + sy * 0.2, a[0] + (b[0] - a[0]) * t1 + sy * 0.2
        q = quad([(-98, y0, 60), (98, y0, 60), (98, y1, 72), (-98, y1, 72)], facing=(0, sy, 0.1))
        p.add('hazard', q, world=True)
    for x in (-60, 60):
        p.add('rubber', box((x - 12, -30.2, 0.5), (x + 12, 30.2, 7)), world=True)
    for x in (-100, 100):
        sx = 1 if x > 0 else -1
        p.add('rust', g.transform(sweep(g.arc_path((0, 0, 0), 5, 0, 180, 6, plane='yz'), 1.2, 6), R=g.rot_z(90)).translate(x + sx * 1, 0, 70), world=False)
    p.hull([(x, y, z) for x in (-100, 100) for (y, z) in prof])
    return p


@prop
def sandbag_wall():
    p = Prop('sandbag_wall', notes='sandbag wall 200x60x90 (long axis X), staggered bags in two rows', havok='dirt')
    r = np.random.default_rng(17)
    bag = pillow((50, 28, 17), seg=4)
    bags = []
    for k in range(6):
        z = 8.5 + k * 13.6
        xs = [-75, -25, 25, 75] if k % 2 == 0 else [-50, 0, 50]
        for y in (-15, 15):
            for x in xs:
                m = g.transform(bag, T=(x + r.uniform(-2, 2), y + r.uniform(-1.5, 1.5), z), R=g.rot_z(r.uniform(-5, 5)) @ g.rot_x(r.uniform(-3, 3)), S=r.uniform(0.95, 1.05))
                bags.append(m)
            if k % 2 == 1:
                for x in (-88, 88):
                    m = g.transform(pillow((26, 28, 17), seg=4), T=(x, y + r.uniform(-1, 1), z), R=g.rot_z(r.uniform(-6, 6)))
                    bags.append(m)
    p.add('sandbag', *bags)
    p.box((-100, -30, 0), (100, 30, 88))
    return p


@prop
def chainlink_fence():
    p = Prop('chainlink_fence', notes='chain-link fence panel 256 wide x 250 tall (+ barbed wire to 275) along X (-128..128), alpha-tested double-sided mesh; posts are separate (fence_post at x=+-128)')
    p.add('chainlink', plane(256, 238, (0, 0, 126), '+y'), world=True)
    p.add('metal_panel', g.transform(cylinder(2.0, 256, 8, z0=-128, caps=False, uv_scale=64), R=g.rot_y(90)).translate(0, 0, 246), world=False)
    p.add('metal_dark', g.transform(cylinder(0.6, 256, 5, z0=-128, caps=False, uv_scale=64), R=g.rot_y(90)).translate(0, 0, 6), world=False)
    # barbed wire strands along the post arms (arms lean toward -Y)
    r = np.random.default_rng(3)
    for t in (0.33, 0.66, 1.0):
        y, z = -24 * t, 250 + 24 * t
        p.add('metal_dark', g.transform(cylinder(0.45, 256, 4, z0=-128, caps=False, uv_scale=64), R=g.rot_y(90)).translate(0, y, z), world=False)
        for x in np.arange(-124, 128, 12):
            p.add('metal_dark', box_c((x, y, z), (0.4, 2.6, 0.4)).rotate(g.rot_x(r.uniform(-60, 60))).translate(0, 0, 0) if False else
                  g.transform(box_c((0, 0, 0), (0.4, 3.0, 0.4)), T=(x, y, z), R=g.rot_x(r.uniform(-60, 60)) @ g.rot_z(r.uniform(-40, 40))))
    p.box((-128, -2, 0), (128, 2, 250), 'metal_light')
    return p


@prop
def fence_post():
    p = Prop('fence_post', notes='steel fence post r=4, 250 tall, with barbed-wire arm leaning to -Y (to 275) and concrete footing; place at chainlink_fence panel ends')
    p.add('concrete_plain', cylinder(10, 5, 12, z0=-1))
    p.add('metal_panel', cylinder(4, 250, 10, z0=0, caps=False, uv_scale=64), world=False)
    p.add('metal_dark', lathe([(4.6, 250), (4.6, 252), (3, 254.5), (0, 255)], 10))
    for z in (20, 125, 238):
        p.add('metal_dark', cylinder(5, 3, 10, z0=z))
    p.add('metal_dark', box_between((0, 0, 248), (0, -26, 276), 2.5, 2.5, up=(1, 0, 0)))
    p.box((-5, -5, 0), (5, 5, 255))
    p.footprint = [-10, -10, 10, 10]
    return p


# ====================================================================== structures
@prop
def checkpoint_booth():
    p = Prop('checkpoint_booth', notes='enterable guard booth 250x250x280: door opening (90x210) in the +X wall, window over a counter on the +Y wall, side window on -X wall; collision on walls/glass/roof/floor/counter. Navmesh inside: use `cutouts` (wall rects), not the whole footprint')
    H0, H1, t = 10, 260, 8
    walls = []
    walls.append(((-125, -125, H0), (125, -117, H1)))                       # back (-Y)
    walls += [((-125, -117, H0), (-117, 117, 110)), ((-125, -117, 200), (-117, 117, H1)),   # left (-X) with window
              ((-125, -117, 110), (-117, -60, 200)), ((-125, 60, 110), (-117, 117, 200))]
    walls += [((117, -117, H0), (125, -45, H1)), ((117, 45, H0), (125, 117, H1)), ((117, -45, 220), (125, 45, H1))]  # right (+X) with door
    walls += [((-125, 117, H0), (125, 125, 100)), ((-125, 117, 220), (125, 125, H1)),            # front (+Y) with window
              ((-125, 117, 100), (-110, 125, 220)), ((110, 117, 100), (125, 125, 220))]
    for mn, mx in walls:
        p.add('metal_panel_big', box(mn, mx))
        p.box(mn, mx)
    p.add('concrete', box((-125, -125, 0), (125, 125, H0)), world=True)
    p.add('floor_tile', box((-117, -117, H0), (117, 117, H0 + 0.2), faces=['+z']), world=True)
    p.box((-125, -125, 0), (125, 125, H0))
    p.add('metal_dark', bevel_box((-140, -140, H1), (140, 140, 280), 2.0))
    p.add('hazard', box((-140.2, 140, 264), (140.2, 140.2, 276), faces=['+y']), box((140, -140, 264), (140.2, 140, 276), faces=['+x']))
    p.box((-140, -140, H1), (140, 140, 280))
    # glass + frames
    p.add('glass', plane(220, 120, (0, 121, 160), '+y'), plane(120, 90, (-121, 0, 155), '-x'))
    p.box((-110, 120, 100), (110, 122, 220), 'glass'); p.box((-122, -60, 110), (-120, 60, 200), 'glass')
    for (a, b) in (((-110, 117, 98), (110, 126, 101)), ((-110, 117, 219), (110, 126, 222)), ((-1.5, 119, 100), (1.5, 123, 220))):
        p.add('metal_dark', box(a, b))
    for (a, b) in (((-126, -60, 108), (-116, 60, 111)), ((-126, -60, 199), (-116, 60, 202))):
        p.add('metal_dark', box(a, b))
    # door frame
    p.add('metal_dark', box((116, -48, H0), (126, -45, 222)), box((116, 45, H0), (126, 48, 222)), box((116, -48, 219), (126, 48, 223)))
    p.add('hazard', box((125, -45, H0), (125.3, 45, H0 + 4), faces=['+x']))
    # counter + terminal + chair-less interior light
    p.add('metal_panel', box((-105, 82, H0), (105, 117, 96)))
    p.add('metal_dark', bevel_box((-108, 78, 96), (108, 117, 100), 0.8))
    p.box((-108, 78, H0), (108, 117, 100))
    _crt(p, -40, 92, 100)
    _keyboard(p, -40, 70, 100) if False else _keyboard(p, -10, 100, 100)
    p.add('fluorescent', plane(116, 26, (0, 0, H1 - 0.2), '-z'))
    p.add('metal_dark', box((-60, -15, H1 - 0.1), (60, -13, H1)), box((-60, 13, H1 - 0.1), (60, 15, H1)))
    # signs
    p.add('sign_restricted', plane(80, 40, (0, 125.3, 60), '+y'))
    p.add('sign_lambda', plane(40, 40, (125.3, 80, 170), '+x'))
    p.extra['cutouts'] = [[a[0], a[1], b[0], b[1]] for a, b in walls[:1] + walls[1:2] + walls[5:7] + walls[8:9]] + [[-108, 78, 108, 117]]
    p.extra['door_opening'] = {'center': [121, 0, H0], 'width': 90, 'height': 210, 'facing': '+X'}
    p.extra['light_offset'] = [0, 0, H1 - 20]
    return p


@prop
def guard_tower():
    p = Prop('guard_tower', notes='steel watch tower 400x400 base, wooden platform floor at z=610 (340x340) with half walls/railing, roof to 850, ladder on +Y side (no ladder collision). Ground under the tower is walkable: use `cutouts` (the 4 feet)')
    feet = [(sx * 190, sy * 190) for sx in (-1, 1) for sy in (-1, 1)]
    tops = [(sx * 150, sy * 150) for sx in (-1, 1) for sy in (-1, 1)]
    for (fx, fy), (tx, ty) in zip(feet, tops):
        p.add('metal_dark', ibeam((fx, fy, 0), (tx, ty, 600), 16, 20, 2.5, up=(fx, fy, 0)))
        p.add('concrete_plain', box((fx - 20, fy - 20, -5), (fx + 20, fy + 20, 12)))
        a, b = np.array([fx, fy, 0.0]), np.array([tx, ty, 600.0])
        p.hull([a + [dx, dy, 0] for dx in (-10, 10) for dy in (-10, 10)] + [b + [dx, dy, 0] for dx in (-10, 10) for dy in (-10, 10)], 'metal')
        p.box((fx - 20, fy - 20, -5), (fx + 20, fy + 20, 12), 'stone')
    # braces on each side
    def leg(i, z):
        (fx, fy), (tx, ty) = feet[i], tops[i]
        t = z / 600
        return np.array([fx + (tx - fx) * t, fy + (ty - fy) * t, z])
    sides = [(0, 1), (2, 3), (0, 2), (1, 3)]
    for (i, j) in sides:
        for (z0, z1) in ((15, 200), (200, 400), (400, 590)):
            p.add('metal_dark', box_between(leg(i, z0), leg(j, z1), 4, 3), box_between(leg(j, z0), leg(i, z1), 4, 3))
        for z in (200, 400):
            p.add('metal_dark', box_between(leg(i, z), leg(j, z), 5, 5))
    # platform
    p.add('metal_dark', box((-172, -172, 594), (172, 172, 602)))
    p.add('wood_plank', box((-170, -170, 602), (170, 170, 610)), world=True)
    p.box((-172, -172, 594), (172, 172, 610), 'wood')
    # half walls (3 sides) + railing on +Y with a gap for the ladder
    for (mn, mx) in (((-170, -170, 610), (170, -164, 680)), ((-170, -164, 610), (-164, 170, 680)), ((164, -164, 610), (170, 170, 680))):
        p.add('wood_plank', box(mn, mx), world=True); p.box(mn, mx, 'wood')
    for (a, b) in (((-167, 167, 610), (-30, 167, 610)), ((30, 167, 610), (167, 167, 610))):
        p.add('metal_dark', *railing(a, b, 100, 70, 2.5, 2.0))
        p.box((min(a[0], b[0]), 164, 610), (max(a[0], b[0]), 170, 712))
    for (x, y) in ((-167, -167), (167, -167), (-167, 167), (167, 167)):
        p.add('metal_dark', cylinder(4, 192, 8, z0=610).translate(x, y, 0))
    p.add('metal_dark', box((-170, -170, 678), (170, -164, 684)), box((-170, -164, 678), (-164, 170, 684)), box((164, -164, 678), (170, 170, 684)))
    # roof
    roof = g.hull_mesh([(sx * 195, sy * 195, 800) for sx in (-1, 1) for sy in (-1, 1)] + [(sx * 195, sy * 195, 806) for sx in (-1, 1) for sy in (-1, 1)] + [(0, 0, 850)])
    p.add('rust', roof, world=True)
    p.hull(roof.P, 'metal')
    # searchlight on the front rail
    p.add('metal_dark', cylinder(3, 20, 8, z0=712).translate(110, 167, 0))
    R = g.rot_x(-20)
    p.add('metal_panel', g.transform(g.transform(cylinder(12, 22, 14, z0=-11), R=g.rot_x(-90)), T=(110, 170, 742), R=R))
    lens = g.transform(g.transform(disk(11, 11.2, 14, True), R=g.rot_x(-90)), T=(110, 170, 742), R=R)
    p.add('lamp', lens)
    # ladder on the +Y side (outside the platform edge)
    for x in (-18, 18):
        p.add('metal_dark', box((x - 1.5, 174, 0), (x + 1.5, 178, 640)))
    for z in np.arange(25, 615, 30):
        p.add('metal_dark', cyl_between((-17, 176, z), (17, 176, z), 1.2, 6, caps=False))
    p.add('sign_restricted', plane(80, 40, (0, -170.3, 645), '-y'))
    p.footprint = 0
    p.extra['cutouts'] = [[fx - 20, fy - 20, fx + 20, fy + 20] for fx, fy in feet]
    p.extra['platform_z'] = 610
    return p


@prop
def portable_lab():
    p = Prop('portable_lab', notes='trailer-style container lab 800x300x320 (long axis X), closed: windows + door (decal-like, not openable) on +Y with metal steps; wheels at -X, hitch/jack at +X')
    L, W = 800, 300
    z0, z1 = 40, 300
    p.add('metal_panel_big', box((-400, -150, z0), (400, 150, z1)))
    p.add('metal_dark', box((-402, -152, z1), (402, 152, z1 + 4)), box((-402, -152, z0 - 3), (402, 152, z0)))
    # ribs (skip window/door zones on +Y)
    windows = [(-280, 200, 80, 60), (-150, 200, 80, 60), (230, 200, 80, 60)]
    door_x, door_w = 60, 90
    for x in np.arange(-380, 400, 40):
        for sy in (-1, 1):
            blocked = sy > 0 and (any(abs(x - wx) < ww / 2 + 8 for (wx, wz, ww, wh) in windows) or abs(x - door_x) < door_w / 2 + 10)
            y0 = sy * 150
            if not blocked:
                p.add('metal_panel', box((x - 3, min(y0, y0 + sy * 2.5), z0 + 2), (x + 3, max(y0, y0 + sy * 2.5), z1 - 2)))
            else:
                for (za, zb) in ((z0 + 2, 160), (240, z1 - 2)):
                    if not (abs(x - door_x) < door_w / 2 + 10 and sy > 0):
                        p.add('metal_panel', box((x - 3, y0, za), (x + 3, y0 + 2.5, zb)))
                    elif za > 200 and False:
                        pass
    for x in (-400, 400):
        sx = 1 if x > 0 else -1
        for y in np.arange(-120, 140, 40):
            p.add('metal_panel', box((min(x, x + sx * 2.5), y - 3, z0 + 2), (max(x, x + sx * 2.5), y + 3, z1 - 2)))
    # windows
    for (wx, wz, ww, wh) in windows:
        p.add('rubber', box((wx - ww / 2, 150.05, wz - wh / 2), (wx + ww / 2, 150.3, wz + wh / 2), faces=['+y']))
        p.add('glass', plane(ww, wh, (wx, 151.5, wz), '+y'))
        for (a, b) in (((wx - ww / 2 - 4, 150, wz - wh / 2 - 4), (wx + ww / 2 + 4, 153, wz - wh / 2)), ((wx - ww / 2 - 4, 150, wz + wh / 2), (wx + ww / 2 + 4, 153, wz + wh / 2 + 4)),
                       ((wx - ww / 2 - 4, 150, wz - wh / 2), (wx - ww / 2, 153, wz + wh / 2)), ((wx + ww / 2, 150, wz - wh / 2), (wx + ww / 2 + 4, 153, wz + wh / 2))):
            p.add('metal_dark', box(a, b))
    # lit interior hint behind the last window
    p.add('fluorescent', plane(60, 12, (230, 149.5, 222), '+y'))
    # door: slab + frame + small window + handle + sign
    p.add('metal_panel', bevel_box((door_x - door_w / 2, 150, 62), (door_x + door_w / 2, 152.5, 262), 0.8))
    p.add('metal_dark', box((door_x - door_w / 2 - 6, 150, 60), (door_x - door_w / 2, 154, 268)), box((door_x + door_w / 2, 150, 60), (door_x + door_w / 2 + 6, 154, 268)),
          box((door_x - door_w / 2 - 6, 150, 262), (door_x + door_w / 2 + 6, 154, 268)))
    p.add('glass', plane(30, 40, (door_x, 152.8, 215), '+y'))
    p.add('metal_dark', box((door_x + 30, 152.5, 150), (door_x + 36, 156, 156)))
    p.add('sign_lambda', plane(36, 36, (door_x, 152.7, 140), '+y'))
    p.add('sign_restricted', plane(70, 35, (door_x + 100, 150.4, 140), '+y'))
    # steps: landing + 3 treads
    p.add('diamond_plate', box((door_x - 60, 150, 54), (door_x + 60, 200, 60)))
    for k in range(3):
        y0 = 200 + k * 25; ztop = 40 - k * 18
        p.add('diamond_plate', box((door_x - 50, y0, ztop - 4), (door_x + 50, y0 + 25, ztop)))
    for sx in (-1, 1):
        x = door_x + sx * 52
        p.add('metal_dark', box_between((x, 200, 58), (x, 276, 4), 4, 6, up=(1, 0, 0)))
        p.add('metal_dark', cyl_between((x, 196, 60), (x, 196, 100), 1.6, 6), cyl_between((x, 276, 2), (x, 276, 42), 1.6, 6),
              cyl_between((x, 196, 100), (x, 276, 42), 1.6, 6))
        p.add('metal_dark', box((door_x + sx * 60 - 3, 196, 0), (door_x + sx * 60 + 3, 200, 54)))
    # chassis, wheels, hitch, jacks
    for y in (-110, 110):
        p.add('metal_dark', box((-390, y - 6, 26), (390, y + 6, 37)))
    for x in (-280, -210):
        for y in (-125, 125):
            p.add('rubber_fit', g.transform(cylinder(30, 22, 16, z0=-11, uv_scale=None), R=g.rot_x(90)).translate(x, y, 30))
            p.add('metal_dark', g.transform(cylinder(14, 23, 10, z0=-11.5), R=g.rot_x(90)).translate(x, y, 30))
    p.add('metal_dark', box_between((390, -100, 32), (470, 0, 32), 8, 8), box_between((390, 100, 32), (470, 0, 32), 8, 8))
    p.add('metal_dark', cylinder(5, 32, 10, z0=0).translate(450, 0, 0), box_c((450, 0, 1.5), (20, 20, 3)))
    for (x, y) in ((380, -130), (380, 130), (-380, -130), (-380, 130)):
        p.add('metal_dark', cylinder(4, 37, 8, z0=0).translate(x, y, 0), box_c((x, y, 1.5), (16, 16, 3)))
    # roof AC unit + vents
    p.add('metal_panel', bevel_box((150, -60, 304), (270, 20, 324), 1.5))
    p.add('grate', plane(100, 60, (210, -20, 324.2), '+z'), world=True)
    p.add('rust', cylinder(8, 20, 10, z0=304).translate(-300, -60, 0))
    p.add('hazard', box((-402, -152.2, z0), (402, -152, z0 + 12), faces=['-y']), box((-402, 152, z0), (402, 152.2, z0 + 12), faces=['+y']))
    p.box((-402, -152, z0 - 15), (402, 153, z1 + 4))
    p.box((150, -60, 304), (270, 20, 324))
    p.hull([(door_x + sx * 60, y, z) for sx in (-1, 1) for (y, z) in ((150, 0), (150, 60), (200, 60), (276, 0))], 'metal')
    for x in (-280, -210):
        p.box((x - 30, -136, 0), (x + 30, 136, 40), 'organic')
    p.extra['door'] = {'center': [door_x, 151, 62], 'width': door_w, 'height': 200, 'facing': '+Y', 'note': 'closed, not an opening'}
    return p


@prop
def antenna_mast():
    p = Prop('antenna_mast', notes='triangular lattice radio mast 1200 tall on a concrete pad; red/white painted bands (vertex colours), red beacon (glow) at the top')
    Rr = 34; H = 1140
    ang = np.radians([90, 210, 330])
    legs = [np.array([Rr * np.cos(a), Rr * np.sin(a), 0.0]) for a in ang]
    sec = 60
    red, white = (0.75, 0.16, 0.12, 1), (0.95, 0.95, 0.92, 1)
    def band(z): return red if int(z // 190) % 2 == 0 else white
    for i in range(3):
        for z in range(0, H, sec):
            p.add('metal_vc', g.set_color(cyl_between(legs[i] + [0, 0, z], legs[i] + [0, 0, z + sec], 2.6, 6, caps=False), band(z)))
    for z in range(0, H, sec):
        for i in range(3):
            a = legs[i] + [0, 0, z]; b = legs[(i + 1) % 3] + [0, 0, z + sec]
            p.add('metal_vc', g.set_color(box_between(a, b, 1.6, 1.6), band(z)))
            if (z // sec) % 2 == 0:
                p.add('metal_vc', g.set_color(box_between(legs[i] + [0, 0, z], legs[(i + 1) % 3] + [0, 0, z], 1.6, 1.6), band(z)))
    p.add('concrete_plain', bevel_box((-70, -70, -6), (70, 70, 10), 2.0))
    p.add('metal_dark', cylinder(12, 12, 10, z0=H).translate(0, 0, 0))
    p.add('metal_dark', cylinder(1.2, 60, 6, z0=H + 12))
    p.add('lamp', lathe([(5, H + 4), (5.5, H + 6)] + [(5.5 * np.cos(t), H + 6 + 5.5 * np.sin(t)) for t in np.linspace(0.3, np.pi / 2, 4)], 10, uv_scale=None).translate(18, 0, 0))
    p.add('fx_red', cross_cards((18, 0, H + 8), 30))
    for z, rot in ((1000, 0), (1000, 120), (880, 240)):
        a = np.radians(90 + rot)
        c = np.array([(Rr + 12) * np.cos(a), (Rr + 12) * np.sin(a), z])
        p.add('metal_panel', g.transform(box_c((0, 0, 0), (16, 6, 70)), T=c, R=g.rot_z(rot)))
    dishc = np.array([0, -(Rr + 20), 760.0])
    dish = g.flip(lathe([(r, r * r / 160) for r in np.linspace(0, 30, 6)], 14))
    p.add('metal_panel', g.transform(merge(dish, lathe([(r, r * r / 160 - 1.5) for r in np.linspace(0, 30, 6)], 14)), T=dishc, R=g.rot_x(90)))
    p.hull([l + [0, 0, z] for l in legs for z in (0, H)] + [(0, 0, H + 12)])
    p.box((-70, -70, -6), (70, 70, 10), 'stone')
    p.footprint = [-70, -70, 70, 70]
    return p


@prop
def satellite_dish():
    p = Prop('satellite_dish', notes='300 dia dish on a pedestal, aimed +Y and 35 deg up; ~330 tall')
    Rd, depth = 150, 50
    f = Rd * Rd / (4 * depth)
    rs = np.linspace(0, Rd, 9)
    back = lathe([(r, r * r / (4 * f) - 3) for r in rs], 24, uv_scale=None)
    front = g.flip(lathe([(r, r * r / (4 * f)) for r in rs], 24, uv_scale=None))
    rim = lathe([(Rd, depth - 3), (Rd + 3, depth - 1.5), (Rd, depth)], 24)
    feed = [cyl_between((Rd * 0.95 * np.cos(a), Rd * 0.95 * np.sin(a), depth * 0.9), (0, 0, f - 8), 1.5, 6) for a in np.radians([90, 210, 330])]
    horn = cylinder(7, 16, 10, z0=f - 10)
    yoke = box((-14, -10, -40), (14, 10, -2))
    center = np.array([0, 0, 205.0])
    R = g.rot_x(-55)  # +Z (dish axis) -> +Y, 35 deg above horizontal
    def place(m): return g.transform(m, T=center, R=R)
    p.add('plastic', place(front), world=True)
    p.add('metal_dark', place(back), place(rim), *[place(m) for m in feed], place(horn), place(yoke))
    p.add('metal_dark', cylinder(14, 180, 14, z0=6), cylinder(20, 12, 14, z0=170))
    p.add('concrete_plain', bevel_box((-45, -45, -4), (45, 45, 6), 1.5))
    p.add('metal_dark', box((-18, -24, 175), (18, 14, 190)))
    for k in range(4):
        a = np.radians(45 + k * 90)
        p.add('metal_dark', box_between((40 * np.cos(a), 40 * np.sin(a), 6), (12 * np.cos(a), 12 * np.sin(a), 80), 4, 4))
    p.box((-45, -45, -4), (45, 45, 6), 'stone')
    p.box((-15, -15, 6), (15, 15, 195))
    dish_pts = place(merge(back, rim)).P
    p.hull(dish_pts[::3])
    p.footprint = [-45, -45, 45, 45]
    return p


# ====================================================================== meteor
@prop
def meteor_crystal_large():
    p = Prop('meteor_crystal_large', notes='glowing crystal cluster ~400 tall on a charred rock base; crystals use the glow-map shader + additive halo shells. Add a cyan LIGH nearby', havok='glass')
    r = np.random.default_rng(42)
    base = blob((280, 230, 80), seed=7, rough=0.25, sub=2).translate(0, 0, -15)
    p.add('meteor', base, world=True)
    p.hull(base.P, 'stone_heavy')
    crystals = [((0, 0, 20), (8, -6, 290), 42, 34, 100)]
    for k in range(10):
        a = r.uniform(0, 2 * np.pi); d = r.uniform(30, 95)
        b = np.array([d * np.cos(a), d * np.sin(a), r.uniform(5, 30)])
        tilt = np.array([np.cos(a), np.sin(a), 0]) * r.uniform(0.35, 0.9) + [0, 0, 1]
        tilt /= np.linalg.norm(tilt)
        L = r.uniform(60, 210) * (1 - d / 200)
        rr = r.uniform(10, 26)
        crystals.append((tuple(b), tuple(b + tilt * L), rr, rr * 0.85, rr * r.uniform(1.4, 2.4)))
    for i, (b, t, r0, r1, tip) in enumerate(crystals):
        m = crystal_prism(b, t, r0, r1, tip, 6, twist=r.uniform(0, 60))
        p.add('crystal', m, world=True)
        if i < 4:
            c = m.P.mean(0)
            p.add('fx_cyan', g.transform(m.translate(*(-c)), S=1.12).translate(*c), world=True)
        p.hull(m.P, 'glass')
    p.footprint = [-140, -115, 140, 115]
    return p


@prop
def meteor_rock():
    p = Prop('meteor_rock', notes='charred meteor chunk ~500x400x250 with glowing crystal veins (glow map) and a few crystal spikes; sunk ~25 units into the ground (bounds z<0)', havok='stone_heavy')
    rock = blob((500, 400, 280), seed=13, rough=0.28, sub=3).translate(0, 0, -30)
    p.add('meteor', rock, world=True)
    P = rock.P
    for lo, hi in ((-260, -60), (-100, 100), (60, 260)):
        sel = P[(P[:, 0] >= lo) & (P[:, 0] <= hi)]
        p.hull(sel, 'stone_heavy')
    r = np.random.default_rng(5)
    top = P[P[:, 2] > np.percentile(P[:, 2], 70)]
    for k in range(5):
        b = top[r.integers(len(top))] - [0, 0, 8]
        d = b - [0, 0, -40]; d /= np.linalg.norm(d)
        p.add('crystal', crystal_prism(b, b + d * r.uniform(30, 70), r.uniform(6, 12), r.uniform(5, 9), r.uniform(12, 24), 6), world=True)
    return p


# ====================================================================== wall items, signs, decals
@prop
def whiteboard():
    p = Prop('whiteboard', notes='wall-mounted whiteboard 200x10x120 with equations; WALL-MOUNTED: origin on the wall surface AT FLOOR LEVEL, board spans z=80..200, extends to y=10 (tray)')
    p.add('metal_panel', box((-100, 0, 80), (100, 4, 200)))
    p.add('whiteboard', plane(194, 114, (0, 4.05, 140), '+y'))
    p.add('metal_dark', box((-100, 0, 197), (100, 5, 200)), box((-100, 0, 80), (100, 5, 83)), box((-100, 0, 83), (-97, 5, 197)), box((97, 0, 83), (100, 5, 197)))
    p.add('metal_dark', box((-80, 4, 82), (80, 10, 84)), box((-80, 9, 84), (80, 10, 86)))
    for i, x in enumerate((-60, -50, 30)):
        p.add('rubber' if i != 1 else 'barrel_toxic', g.transform(cylinder(0.8, 11, 6), R=g.rot_y(90)).translate(x, 7, 84.8))
    p.box((-100, 0, 80), (100, 10, 200))
    p.footprint = 0
    p.extra['mount'] = 'wall'
    return p


@prop
def poster_safety():
    p = Prop('poster_safety', kind='decal', notes="'SAFETY FIRST' poster 80x120; WALL decal: origin on the wall surface at the poster centre (place at ~150 high), 0.3 off the wall, no collision")
    p.add('poster', plane(80, 120, (0, 0.3, 0), '+y'))
    p.footprint = 0
    p.extra['mount'] = 'wall'
    return p


def _sign(name, mat, w, h, notes):
    p = Prop(name, notes=notes + '; WALL plate: origin on the wall surface at the sign centre (place at ~150-200 high)')
    p.add('metal_dark', bevel_box((-w / 2, 0, -h / 2), (w / 2, 1.4, h / 2), 0.5))
    p.add(mat, plane(w - 1.0, h - 1.0, (0, 1.45, 0), '+y'))
    p.box((-w / 2, 0, -h / 2), (w / 2, 1.5, h / 2))
    p.footprint = 0
    p.extra['mount'] = 'wall'
    return p


@prop
def sign_lambda():
    return _sign('sign_lambda', 'sign_lambda', 60, 60, 'orange lambda plate 60x60')


@prop
def sign_biohazard():
    return _sign('sign_biohazard', 'sign_biohazard', 60, 60, 'biohazard warning plate 60x60')


@prop
def sign_restricted():
    return _sign('sign_restricted', 'sign_restricted', 120, 60, "'RESTRICTED AREA / AUTHORIZED PERSONNEL ONLY' plate 120x60")


@prop
def sign_testchamber():
    return _sign('sign_testchamber', 'sign_testchamber', 160, 80, "'TEST CHAMBER / STARFALL RESEARCH SITE' plate 160x80")


@prop
def blood_splat_floor():
    p = Prop('blood_splat_floor', kind='decal', notes='blood splatter decal quad 120x120, 0.4 above the floor, alpha blended + decal flag, no collision')
    p.add('blood', plane(120, 120, (0, 0, 0.4), '+z'))
    p.footprint = 0
    return p


@prop
def blood_splat_wall():
    p = Prop('blood_splat_wall', kind='decal', notes='blood splatter wall decal 100x100; origin on the wall surface at the splat centre, 0.4 off the wall, no collision')
    p.add('blood', plane(100, 100, (0, 0.4, 0), '+y'))
    p.footprint = 0
    p.extra['mount'] = 'wall'
    return p


# ====================================================================== damage
@prop
def debris_pile():
    p = Prop('debris_pile', notes='pile of broken concrete chunks, rebar and bent metal sheets ~190x160x60', havok='stone_broken')
    r = np.random.default_rng(31)
    chunks = []
    specs = [((90, 70, 45), (-20, 0)), ((70, 60, 35), (40, 25)), ((60, 50, 30), (-55, -35)), ((50, 45, 28), (45, -40)),
             ((40, 35, 22), (-70, 40)), ((30, 28, 18), (10, 55)), ((26, 22, 15), (75, 5)), ((22, 20, 12), (-5, -60))]
    for i, (size, (x, y)) in enumerate(specs):
        m = blob(size, seed=40 + i, rough=0.35, sub=1)
        m = g.transform(m, R=g.rot_z(r.uniform(0, 360)) @ g.rot_x(r.uniform(-15, 15))).translate(x, y, -3)
        chunks.append(m)
        if i < 4: p.hull(m.P, 'stone_broken')
    p.add('concrete_plain', *chunks)
    # slabs with exposed rebar
    for k in range(3):
        slab = bevel_box((-30, -18, 0), (30, 18, 6), 1.0)
        slab = g.jitter(slab, 1.2, seed=k)
        p.add('concrete_plain', g.transform(slab, T=(r.uniform(-60, 60), r.uniform(-50, 50), r.uniform(8, 25)), R=g.rot_z(r.uniform(0, 180)) @ g.rot_y(r.uniform(-25, 25))))
    for k in range(7):
        a = np.array([r.uniform(-70, 70), r.uniform(-60, 60), r.uniform(5, 30)])
        d = r.normal(size=3); d[2] = abs(d[2]) * 0.6; d /= np.linalg.norm(d)
        b = a + d * r.uniform(30, 60)
        mid = (a + b) / 2 + r.normal(size=3) * 8
        p.add('rust', sweep([a, mid, b], 0.8, 5), world=False)
    for k in range(3):
        c = np.array([r.uniform(-60, 60), r.uniform(-50, 50), r.uniform(4, 20)])
        sheet = merge(box((-20, -12, 0), (0, 12, 0.8)), g.transform(box((0, -12, 0), (20, 12, 0.8)), R=g.rot_y(-r.uniform(20, 60))))
        p.add('metal_panel', g.transform(sheet, T=c, R=g.rot_z(r.uniform(0, 360)) @ g.rot_x(r.uniform(-20, 20))))
    p.add('concrete_plain', splat_poly(105, seed=3, n=16, z=0.25, rough=0.25), world=True)
    return p


@prop
def broken_terminal():
    p = Prop('broken_terminal', notes='smashed CRT terminal (for tables/desks): cracked screen opening, glass shards, sparking (additive spark cards)')
    sc = _crt(p, 0, -6, 0, broken=True)
    cx, yf, zc, sw, sh = sc
    r = np.random.default_rng(8)
    edges = []
    for k in range(10):
        t = k / 10
        side = k % 4
        if side == 0: base = (cx - sw / 2 + sw * r.random(), zc + sh / 2)
        elif side == 1: base = (cx - sw / 2 + sw * r.random(), zc - sh / 2)
        elif side == 2: base = (cx - sw / 2, zc - sh / 2 + sh * r.random())
        else: base = (cx + sw / 2, zc - sh / 2 + sh * r.random())
        tip = (base[0] + (cx - base[0]) * r.uniform(0.2, 0.5), base[1] + (zc - base[1]) * r.uniform(0.2, 0.5))
        w = r.uniform(3, 7)
        yy = yf + 0.15 + 0.01 * k
        if side < 2: pts = [(base[0] - w, yy, base[1]), (base[0] + w, yy, base[1]), (tip[0], yy, tip[1])]
        else: pts = [(base[0], yy, base[1] - w), (base[0], yy, base[1] + w), (tip[0], yy, tip[1])]
        m = g.Mesh(pts, np.tile([0, 1.0, 0], (3, 1)), [(0, 0), (1, 0), (0.5, 1)], [[0, 1, 2]])
        if g.check_winding(m) < 0.5: m.T = m.T[:, [0, 2, 1]]
        edges.append(m)
    p.add('glass_cracked', *edges, world=True)
    for k in range(6):
        p.add('glass_cracked', shard((r.uniform(-15, 15), r.uniform(14, 34), 0.3), r.uniform(1.5, 3.5), 100 + k), world=True)
    p.add('fx_spark', cross_cards((cx - 5, yf + 1.5, zc + 3), 12), cross_cards((cx + 6, yf + 1.0, zc - 4), 8))
    p.add('fx_red', plane(24, 20, (cx, yf + 0.5, zc), '+y'))
    _keyboard(p, 4, 24, 0)
    p.box((-20, -25, 0), (20, 13, 37))
    return p


@prop
def overturned_table():
    p = Prop('overturned_table', notes='lab_table knocked on its side as cover: top faces +Y, legs point -Y; ~140x55x70')
    q = Prop('tmp')
    _lab_table_parts(q); _lab_table_col(q)
    R = g.rot_z(6) @ g.rot_x(-90)
    T = np.array([0, -27.5, 35.0])
    for mat, ms in q.parts.items():
        for m in ms:
            p.add(mat, g.transform(m, T=T, R=R), world=False)
    for c in q.col:
        pts = nifkit_points(c)
        p.hull(pts @ R.T + T)
    return p


def nifkit_points(piece):
    import nifkit
    return nifkit.collision_points(piece)


# ====================================================================== doors
def _blast_frame(p, slab_open):
    W, D, H = 300, 60, 300
    ow, oh = 200, 240
    p.add('metal_panel_big', chamfer_box_mesh((-150, -30, 0), (-ow / 2, 30, H), ['-x', '+z', '+y', '-y']),
          chamfer_box_mesh((ow / 2, -30, 0), (150, 30, H), ['+x', '+z', '+y', '-y']),
          chamfer_box_mesh((-ow / 2, -30, oh), (ow / 2, 30, H), ['+z', '+y', '-y']))
    for sy in (-1, 1):
        y = sy * 30
        p.add('hazard', box((-ow / 2 - 14, y, 0), (-ow / 2, y + sy * 0.3, oh), faces=['+y' if sy > 0 else '-y']),
              box((ow / 2, y, 0), (ow / 2 + 14, y + sy * 0.3, oh), faces=['+y' if sy > 0 else '-y']),
              box((-ow / 2 - 14, y, oh), (ow / 2 + 14, y + sy * 0.3, oh + 14), faces=['+y' if sy > 0 else '-y']))
    # reveal trims (inside faces of the opening)
    p.add('metal_dark', box((-ow / 2, -30, 0), (-ow / 2 + 0.4, 30, oh), faces=['+x']), box((ow / 2 - 0.4, -30, 0), (ow / 2, 30, oh), faces=['-x']),
          box((-ow / 2, -30, oh - 0.4), (ow / 2, 30, oh), faces=['-z']))
    # door guides (grooves) in the jambs
    for sx in (-1, 1):
        p.add('rubber', box((sx * ow / 2 - (2 if sx > 0 else -0.01), -6, 0), (sx * ow / 2 + (0.01 if sx > 0 else 2), 6, oh), faces=['-x' if sx > 0 else '+x']))
    # control box + warning lamp on +Y
    p.add('metal_dark', bevel_box((112, 30, 110), (140, 36, 150), 0.8))
    p.add('control_panel', plane(24, 34, (126, 36.1, 130), '+y'))
    for sx in (-1, 1):
        p.add('metal_dark', g.transform(cylinder(6, 4, 10), R=g.rot_x(-90)).translate(sx * 125, 30, 270))
        p.add('lamp', g.transform(disk(5.5, 4.1, 10, True), R=g.rot_x(-90)).translate(sx * 125, 30, 270))
        p.add('fx_red', plane(30, 30, (sx * 125, 35.5, 270), '+y'))
    p.add('sign_testchamber', plane(110, 55, (0, 30.3, 272), '+y'))
    p.box((-150, -30, 0), (-ow / 2, 30, H)); p.box((ow / 2, -30, 0), (150, 30, H)); p.box((-ow / 2, -30, oh), (ow / 2, 30, H))
    # slab
    z0 = oh - 6 if slab_open else 0
    z1 = H - 2 if slab_open else oh + 8
    sw = ow + 8
    p.add('metal_dark', box((-sw / 2, -12, z0), (sw / 2, 12, z1), faces=['+x', '-x', '+z', '-z']))
    for sy in (-1, 1):
        if slab_open:
            p.add('hazard', box((-ow / 2, sy * 12, z0), (ow / 2, sy * 12 + sy * 0.01, oh), faces=['+y' if sy > 0 else '-y']))
        else:
            m = box((-ow / 2, sy * 12, 0), (ow / 2, sy * 12 + sy * 0.01, oh), uv='fit', faces=['+y' if sy > 0 else '-y'])
            p.add('door_heavy', m)
    if not slab_open:
        p.box((-sw / 2, -12, 0), (sw / 2, 12, oh), 'metal_heavy')
        p.footprint = [-150, -30, 150, 30]
    else:
        p.footprint = 0
        p.extra['cutouts'] = [[-150, -30, -ow / 2, 30], [ow / 2, -30, 150, 30]]
    p.extra['opening'] = {'width': ow, 'height': oh}


def chamfer_box_mesh(mn, mx, faces, bevel=6.0):
    return g.chamfer_box(mn, mx, bevel, faces)


@prop
def blast_door_frame():
    p = Prop('blast_door_frame', notes='blast door 300 wide x 60 deep x 300 tall (opening 200x240) with the heavy slab CLOSED; collision blocks the doorway; red warning lamps (add LIGH if wanted)', havok='metal_heavy')
    _blast_frame(p, False)
    return p


@prop
def blast_door_open():
    p = Prop('blast_door_open', notes='same frame with the slab retracted into the lintel (only its hazard-striped lip shows); doorway 200x240 walkable', havok='metal_heavy')
    _blast_frame(p, True)
    return p


# ====================================================================== test chamber
@prop
def test_target():
    p = Prop('test_target', notes='metal practice target dummy on a weighted stand, ~195 tall; target face toward +Y')
    p.add('metal_dark', lathe([(0, 0), (30, 0), (30, 3), (26, 5), (0, 5)], 18))
    for k in range(3):
        a = np.radians(90 + k * 120)
        p.add('rust', cylinder(7, 6, 10, z0=5).translate(18 * np.cos(a), 18 * np.sin(a), 0))
    p.add('metal_panel', cylinder(3, 100, 10, z0=5, uv_scale=64), world=False)
    # torso: convex hexagon plate 54 wide x 72 tall, 3 thick
    hexa = [(-27, -36), (27, -36), (30, 10), (20, 36), (-20, 36), (-30, 10)]
    torso = g.prism_profile([(x, z) for x, z in hexa][::1], -1.5, 1.5, uv_scale=64)
    # prism_profile extrudes along X; rotate so the plate faces +Y
    torso = g.transform(torso, R=g.rot_z(90))
    torso = g.transform(torso, R=g.rot_x(0)).translate(0, 0, 141)
    p.add('metal_dark', torso)
    face = quad([(-26, 1.65, 106), (26, 1.65, 106), (26, 1.65, 170), (-26, 1.65, 170)], facing=(0, 1, 0))
    p.add('target', face)
    p.add('metal_dark', box((-4, -1.5, 176), (4, 1.5, 182)))
    head = g.transform(cylinder(12, 3, 16, z0=-1.5, uv_scale=None), R=g.rot_x(-90)).translate(0, 0, 194)
    p.add('metal_dark', head)
    hf = g.transform(disk(11.5, 1.55, 16, True), R=g.rot_x(-90)).translate(0, 0, 194)
    p.add('target', hf)
    p.add('metal_dark', box((-2, -6, 100), (2, -1.5, 112)))
    # dents: a few dark spots are in the texture already
    ang = np.radians(np.arange(12) * 30)
    p.hull([(30 * np.cos(a), 30 * np.sin(a), z) for a in ang for z in (0, 5)])
    p.box((-3, -3, 5), (3, 3, 105))
    p.box((-31, -3, 104), (31, 3, 207))
    p.footprint = [-30, -30, 30, 30]
    return p


@prop
def test_platform():
    p = Prop('test_platform', notes='round raised metal test platform 300 dia x 20 with a ramped edge (walkable collision, hull); glowing ring lights; lambda emblem')
    p.add('diamond_plate', disk(110, 20, 32, True, uv_scale=64))
    ramp = lathe([(150, 0), (110, 20)], 32, uv_scale=None, u_repeat=24)
    p.add('hazard', ramp)
    p.add('metal_dark', lathe([(150.5, -0.5), (150.5, 0.6), (150, 0.6)], 32))
    p.add('metal_dark', lathe([(110.2, 19.2), (110.2, 20.6), (108, 20.6), (108, 20.0)], 32))
    for k in range(16):
        a = np.radians(k * 22.5)
        c = (130 * np.cos(a), 130 * np.sin(a), 10.2)
        lamp = disk(3.0, 0, 8, True)
        n = np.array([np.cos(a), np.sin(a), 2.0]); n /= np.linalg.norm(n)
        p.add('lamp', g.transform(lamp, T=c, R=g.rot_to(n)).translate(*(n * 0.4)))
    p.add('sign_lambda', disk(34, 20.15, 24, True))
    ang = np.radians(np.arange(24) * 15)
    p.hull([(150 * np.cos(a), 150 * np.sin(a), 0) for a in ang] + [(110 * np.cos(a), 110 * np.sin(a), 20) for a in ang])
    p.footprint = 0
    p.extra['surface_z'] = 20
    return p


# ====================================================================== catwalks
@prop
def catwalk_256():
    p = Prop('catwalk_256', notes='metal grating catwalk 256 (X) x 128 (Y) with railings on both long sides; origin at the CENTRE OF THE WALKING SURFACE (z=0), frame hangs to z=-14. Tiles every 256 along X. Walkable box collision + railing walls')
    p.add('grate', plane(256, 120, (0, 0, 0), '+z'), world=True)
    for sy in (-1, 1):
        p.add('metal_dark', box((-128, sy * 64 - (4 if sy > 0 else 0), -14), (128, sy * 64 + (0 if sy > 0 else 4), 0.5)))
    for x in (-126, 0, 126):
        p.add('metal_dark', box((x - 2, -60, -12), (x + 2, 60, -1)))
    for x in (-64, 64):
        p.add('metal_dark', box((x - 1, -60, -3), (x + 1, 60, -0.3)))
    for sy in (-1, 1):
        p.add('metal_panel', *railing((-128, sy * 62, 0.5), (128, sy * 62, 0.5), 100, 128, 2.5, 2.0))
    p.box((-128, -64, -14), (128, 64, 0))
    for sy in (-1, 1):
        p.box((-128, sy * 62 - 1.5, 0), (128, sy * 62 + 1.5, 103))
    p.footprint = 0
    p.extra['surface_z'] = 0
    return p


@prop
def catwalk_stairs():
    p = Prop('catwalk_stairs', notes='grating stairs 128 wide rising 256 over 384 toward +Y: bottom edge at y=-192 (z=0), top at y=+192 (z=256, meets catwalk_256 surface). 16 steps (rise 16, run 24). Collision: walkable ramp hull + handrail walls')
    n, rise, run = 16, 16, 24
    for i in range(n):
        y0 = -192 + i * run; z = rise * (i + 1)
        p.add('grate', plane(118, run, (0, y0 + run / 2, z), '+z'), world=True)
        p.add('metal_dark', box((-60, y0, z - 3), (60, y0 + 2, z + 0.4)))
    for sx in (-1, 1):
        x = sx * 61
        p.add('metal_dark', box_between((x, -192, 4), (x, 192, 260), 4, 16, up=(1, 0, 0)))
    p.add('metal_dark', box((-64, -194, 0), (64, -190, 3)))
    for sx in (-1, 1):
        x = sx * 63
        posts = [(-180, 0), (-84, 0), (12, 0), (108, 0), (180, 0)]
        tops = []
        for (y, _) in posts:
            z = max(0.0, (y + 192) * rise / run) + 6
            p.add('metal_panel', cyl_between((x, y, z), (x, y, z + 100), 2.5, 8))
            tops.append((x, y, z + 100))
        p.add('metal_panel', sweep(tops, 2.0, 8), world=False)
        p.add('metal_panel', sweep([(tx, ty, tz - 50) for tx, ty, tz in tops], 1.6, 8), world=False)
    prof = [(-192, 0), (192, 0), (192, 256), (180, 256), (-192, 8)]
    p.hull([(x, y, z) for x in (-64, 64) for (y, z) in prof], 'metal')
    for sx in (-1, 1):
        x = sx * 63
        p.hull([(x + dx, y, z) for dx in (-1.5, 1.5) for (y, z) in ((-192, 0), (192, 256), (192, 362), (-192, 106))], 'metal')
    p.footprint = [-64, -192, 64, 192]
    return p


# ====================================================================== exterior
@prop
def bunker_entrance():
    p = Prop('bunker_entrance', notes='exterior concrete bunker block 700x500x400 (z=-100..300, 100 sunk below grade) with a framed 256x256 doorway recess on +Y (recess back wall at y=186: place the facility load door there). Collision on all solid parts', havok='stone')
    b = 18.0
    parts = [((-350, -250, -100), (-128, 250, 300), ['-x', '+z', '+y', '-y']),
             ((128, -250, -100), (350, 250, 300), ['+x', '+z', '+y', '-y']),
             ((-128, -250, 256), (128, 250, 300), ['+z', '+y', '-y']),
             ((-128, -250, -100), (128, 186, 256), []),
             ((-128, 186, -100), (128, 250, 0), [])]
    for mn, mx, faces in parts:
        p.add('concrete', g.chamfer_box(mn, mx, b, faces), world=True)
        p.box(mn, mx, 'stone')
    # doorway frame: steel jambs with hazard faces + header
    p.add('metal_dark', box((-140, 236, 0), (-128, 252, 268)), box((128, 236, 0), (140, 252, 268)), box((-140, 236, 256), (140, 252, 268)))
    p.add('hazard', box((-128.01, 186, 0), (-128, 236, 256), faces=['+x']), box((128, 186, 0), (128.01, 236, 256), faces=['-x']),
          box((-128, 186, 255.99), (128, 236, 256), faces=['-z']))
    p.add('hazard', box((-140, 252, 0), (140, 252.3, 6), faces=['+y']))
    # recess floor plate
    p.add('diamond_plate', box((-128, 186, 0), (128, 250, 0.3), faces=['+z']))
    # canopy
    p.add('metal_dark', bevel_box((-170, 250, 274), (170, 330, 282), 1.5))
    for sx in (-1, 1):
        p.add('metal_dark', box_between((sx * 160, 250, 230), (sx * 160, 326, 274), 5, 5, up=(1, 0, 0)))
    p.add('fluorescent', plane(116, 26, (0, 300, 273.9), '-z'))
    p.box((-170, 250, 274), (170, 330, 282), 'metal')
    # lamps either side, signs, vents, pipes
    for sx in (-1, 1):
        x = sx * 200
        p.add('metal_dark', g.transform(cylinder(8, 6, 12), R=g.rot_x(-90)).translate(x, 250, 220))
        p.add('lamp', g.transform(disk(7, 6.1, 12, True), R=g.rot_x(-90)).translate(x, 250, 220))
        p.add('fx_lamp', plane(40, 40, (x, 257.5, 220), '+y'))
    p.add('sign_testchamber', plane(150, 75, (-250, 250.3, 130), '+y'))
    p.add('sign_restricted', plane(100, 50, (240, 250.3, 120), '+y'))
    p.add('sign_lambda', plane(70, 70, (240, 250.3, 200), '+y'))
    for x in (-220, 220):
        p.add('metal_dark', bevel_box((x - 30, -60, 296), (x + 30, 0, 320), 1.5))
        p.add('grate', plane(54, 54, (x, -30, 320.2), '+z'), world=True)
        p.box((x - 30, -60, 296), (x + 30, 0, 320))
    p.add('rust', sweep([(350, 120, 40), (362, 120, 40), (362, 120, 260), (362, 60, 290), (362, -60, 290)], 8, 12), world=False)
    p.extra['door_slot'] = {'center': [0, 186, 0], 'width': 256, 'height': 256, 'facing': '+Y'}
    p.extra['grade_z'] = 0
    return p


# ---------------------------------------------------------------------- driver
def main(argv):
    preview = '--no-preview' not in argv
    names = [a for a in argv if not a.startswith('--')] or list(REG)
    os.makedirs(OUT, exist_ok=True); os.makedirs(PREV, exist_ok=True)
    mpath = os.path.join(OUT, 'manifest.json')
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for nm in names:
        p = REG[nm]()
        write(p, OUT, manifest, PREV if preview else None)
    manifest = {k: manifest[k] for k in sorted(manifest)}
    json.dump(manifest, open(mpath, 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])

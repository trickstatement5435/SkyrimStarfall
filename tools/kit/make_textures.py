"""Procedural, tileable kit textures for the Starfall Research Site (Half-Life era look).
Writes textures/StarfallSite/kit/<name>.dds + <name>_n.dds (normal, DirectX/Y-, alpha = specular) [+ <name>_g.dds glow].
usage: python3 make_textures.py [name ...]"""
import sys, numpy as np
from texlib import *  # noqa: F401,F403
from texlib import Canvas, noise, worley, gblur, mix, solid, smooth, save, rng, paste_mask, font

REG = {}


def tex(fn):
    REG[fn.__name__] = fn
    return fn


# ------------------------------------------------------------------ concrete
def _concrete(name, base, stain_col, seed, S=1024, darkness=0.0, tie_holes=True):
    n_big = noise(S, 2.4, seed)
    n_mid = noise(S, 1.6, seed + 1)
    n_fine = noise(S, 0.6, seed + 2)
    col = solid(S, base) * (0.82 + 0.3 * n_big[..., None]) * (0.93 + 0.12 * n_mid[..., None])
    col += (n_fine[..., None] - 0.5) * 18
    # stains: blotches + vertical drips under them
    st = smooth(0.58, 0.8, noise(S, 2.8, seed + 3))
    drip = noise(S, 2.0, seed + 4, aniso=(1.0, 10.0))
    drip = smooth(0.55, 0.85, drip) * smooth(0.4, 0.7, gblur(st, 2) + noise(S, 3.0, seed + 5) * 0.6)
    col = mix(col, col * np.asarray(stain_col) / 128.0, np.clip(st * 0.55 + drip * 0.45, 0, 1))
    col *= (1 - darkness * (0.5 + 0.5 * noise(S, 2.2, seed + 6)))[..., None]
    h = n_mid * 0.6 + n_fine * 0.35
    # pits / air bubbles
    r = rng(seed + 7)
    pits = Canvas(S, mode='L')
    for _ in range(int(S * S / 1400)):
        x, y = r.uniform(0, S, 2); rr = r.choice([0.8, 1.2, 1.8, 2.5, 3.5], p=[.35, .3, .2, .1, .05])
        for ox in (-S, 0, S):
            for oy in (-S, 0, S): pits.circle((x + ox, y + oy), rr, 255)
    pm = pits.array()
    col = mix(col, col * 0.45, pm * 0.9)
    h -= pm * 0.9
    # formwork seams (horizontal at 0 and S/2) and tie holes
    yy = np.arange(S)[:, None]
    for sy in (0, S // 2):
        d = np.minimum(np.abs(yy - sy), S - np.abs(yy - sy))
        seam = np.exp(-(d / 1.6) ** 2) * (0.6 + 0.4 * noise((S, S), 1.0, seed + 8 + sy))
        col *= (1 - 0.35 * seam)[..., None]
        h -= seam * 1.2
        lip = np.exp(-((d - 3) / 2.0) ** 2) * 0.25
        h += lip
    if tie_holes:
        th = Canvas(S, mode='L'); ring = Canvas(S, mode='L')
        for ty in (S // 4, 3 * S // 4):
            for tx in range(S // 8, S, S // 4):
                ring.circle((tx, ty), 11, 255); th.circle((tx, ty), 7, 255)
        thm, rgm = th.array(), ring.array()
        col = mix(col, col * 0.8, rgm * 0.5); col = mix(col, solid(S, (40, 40, 40)), thm * 0.85)
        h -= thm * 3 + rgm * 0.3
    spec = 25 + 30 * n_fine + 40 * st
    return col, h, spec


@tex
def concrete():
    col, h, spec = _concrete('concrete', (172, 170, 164), (110, 100, 85), 10)
    save('concrete', col, h, spec, nstrength=3.0)


@tex
def concrete_dark():
    col, h, spec = _concrete('concrete_dark', (112, 112, 108), (70, 78, 62), 20, darkness=0.15)
    save('concrete_dark', col, h, spec, nstrength=3.0)


@tex
def concrete_plain():
    """concrete without tie holes / seams (for small props: barriers, debris)"""
    col, h, spec = _concrete('concrete_plain', (160, 158, 152), (105, 98, 85), 30, S=512, tie_holes=False)
    save('concrete_plain', col, h, spec, nstrength=3.0)


# ------------------------------------------------------------------ floor tiles
@tex
def floor_tile():
    S, n, g = 512, 4, 3.0
    T = S // n
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    lx, ly = xx % T, yy % T
    d = np.minimum.reduce([lx, ly, T - lx, T - ly])  # distance to tile edge
    tile = smooth(g, g + 2.5, d)
    r = rng(5)
    tint = r.uniform(0.94, 1.04, (n, n))
    ix, iy = (xx // T).astype(int), (yy // T).astype(int)
    checker = ((ix + iy) % 2).astype(float)
    a = np.array([196, 198, 192.0]); b = np.array([168, 176, 180.0])
    col = mix(solid(S, a), solid(S, b), checker) * tint[iy, ix][..., None]
    dirt = noise(S, 2.2, 6)
    col *= (0.9 + 0.12 * noise(S, 1.0, 7))[..., None]
    col = mix(col, col * 0.7, smooth(0.6, 0.9, dirt) * 0.6)
    # scuffs
    sc = Canvas(S, mode='L')
    for _ in range(70):
        x, y = r.uniform(0, S, 2); L = r.uniform(8, 40); a0 = r.uniform(0, np.pi)
        sc.line([(x, y), (x + L * np.cos(a0), y + L * np.sin(a0) * 0.3)], int(r.uniform(60, 160)), r.uniform(1, 2.5))
    col = mix(col, col * 0.55, sc.array() * 0.6)
    grout = solid(S, (70, 70, 66)) * (0.8 + 0.4 * dirt[..., None])
    col = mix(grout, col, tile)
    h = tile * 1.0 + noise(S, 0.8, 8) * 0.08
    spec = 30 + 150 * tile * (1 - 0.5 * smooth(0.6, 0.9, dirt))
    save('floor_tile', col, h, spec, nstrength=2.5)


# ------------------------------------------------------------------ metal panels
@tex
def metal_panel():
    S = 1024; P = S // 2
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    lx, ly = xx % P, yy % P
    d = np.minimum.reduce([lx, ly, P - lx, P - ly])
    seam = 1 - smooth(1.5, 4.0, d)
    pillow = smooth(0, 60, d)
    base = np.array([104, 116, 128.0])
    r = rng(11)
    tint = r.uniform(0.92, 1.06, (2, 2))
    col = solid(S, base) * tint[(yy // P).astype(int), (xx // P).astype(int)][..., None]
    brushed = noise(S, 1.4, 12, aniso=(1.0, 0.08))
    col *= (0.9 + 0.16 * brushed + 0.08 * noise(S, 2.4, 13))[..., None]
    # grime toward seams and lower edges
    grime = (1 - smooth(0, 70, d)) * (0.5 + 0.5 * noise(S, 2.0, 14))
    col = mix(col, col * 0.55, grime * 0.55)
    # scratches
    sc = Canvas(S, mode='L')
    for _ in range(160):
        x, y = r.uniform(0, S, 2); L = r.uniform(10, 90); a0 = r.normal(0.3, 0.6)
        sc.line([(x, y), (x + L * np.cos(a0), y + L * np.sin(a0))], int(r.uniform(80, 220)), r.uniform(0.6, 1.5))
    scm = sc.array()
    col = mix(col, solid(S, (175, 182, 190)), scm * 0.5)
    # rivets: every 32 px along edges, 14 px inset
    rv = Canvas(S, mode='L'); rvs = Canvas(S, mode='L')
    for py in range(0, S, P):
        for px in range(0, S, P):
            for k in range(16, P, 32):
                for (cx, cy) in ((px + k, py + 14), (px + k, py + P - 14), (px + 14, py + k), (px + P - 14, py + k)):
                    rv.circle((cx, cy), 4.5, 255); rvs.circle((cx + 1.5, cy + 2), 5.5, 255)
    rvm, rsm = rv.array(), rvs.array()
    yy0, xx0 = np.mgrid[-6:7, -6:7]
    col = mix(col, col * 0.6, np.clip(rsm - rvm, 0, 1) * 0.8)
    col = mix(col, solid(S, (150, 160, 170)), rvm * 0.6)
    h = pillow * 0.6 - seam * 1.5 + gblur(rvm, 0.8) * 2.0 - scm * 0.15
    col *= (1 - 0.5 * seam)[..., None]
    spec = 90 + 70 * brushed - 60 * grime + 60 * scm
    save('metal_panel', col, h, spec, nstrength=3.0)


@tex
def metal_dark():
    S = 512
    r = rng(21)
    brushed = noise(S, 1.2, 22, aniso=(1.0, 0.05))
    col = solid(S, (58, 62, 68)) * (0.85 + 0.25 * brushed[..., None]) * (0.9 + 0.15 * noise(S, 2.4, 23)[..., None])
    sc = Canvas(S, mode='L')
    for _ in range(120):
        x, y = r.uniform(0, S, 2); L = r.uniform(5, 50); a0 = r.uniform(0, np.pi)
        sc.line([(x, y), (x + L * np.cos(a0), y + L * np.sin(a0))], int(r.uniform(60, 200)), r.uniform(0.5, 1.2))
    scm = sc.array()
    col = mix(col, solid(S, (120, 124, 130)), scm * 0.5)
    grime = smooth(0.55, 0.85, noise(S, 2.6, 24))
    col = mix(col, col * 0.6, grime * 0.5)
    save('metal_dark', col, brushed * 0.3 - scm * 0.2, 110 + 60 * brushed - 50 * grime, nstrength=2.0)


@tex
def diamond_plate():
    S = 512; P = 32
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    # two staggered sets of elongated diamonds at +/-45 deg
    h = np.zeros((S, S))
    for off, ang in ((0, 1), (P / 2, -1)):
        u = (xx + off) % P - P / 2; v = (yy + off) % P - P / 2
        a = (u + ang * v) / np.sqrt(2); b = (u - ang * v) / np.sqrt(2)
        h = np.maximum(h, smooth(1.0, 0.0, (a / 9) ** 2 + (b / 2.6) ** 2))
    n = noise(S, 2.0, 31)
    col = solid(S, (128, 132, 136)) * (0.8 + 0.3 * n[..., None]) * (0.9 + 0.2 * h[..., None])
    grime = smooth(0.5, 0.85, noise(S, 2.5, 32)) * (1 - h)
    col = mix(col, col * 0.5, grime * 0.6)
    save('diamond_plate', col, h * 2.5, 120 + 80 * h - 60 * grime, nstrength=3.0)


# ------------------------------------------------------------------ hazard stripes
@tex
def hazard_stripes():
    S, P = 512, 128
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    s = ((xx + yy) % P) / P
    stripe = smooth(0.48, 0.52, s) * (1 - smooth(0.98, 1.0, s)) + (1 - smooth(0.0, 0.02, s)) * 0  # 1 = black
    yel = np.array([238, 182, 22.0]); blk = np.array([28, 26, 24.0])
    col = mix(solid(S, yel), solid(S, blk), stripe)
    col *= (0.88 + 0.18 * noise(S, 1.8, 41))[..., None]
    wear = smooth(0.62, 0.72, noise(S, 1.9, 42) * 0.7 + noise(S, 0.8, 43) * 0.3)
    metal = solid(S, (120, 120, 118)) * (0.8 + 0.3 * noise(S, 1.0, 44)[..., None])
    col = mix(col, metal, wear)
    dirt = smooth(0.55, 0.9, noise(S, 2.6, 45))
    col = mix(col, col * 0.55, dirt * 0.6)
    save('hazard_stripes', col, -wear * 0.8 + noise(S, 0.7, 46) * 0.1, 50 + 110 * wear, nstrength=3.0)


# ------------------------------------------------------------------ wood
def _grain(shape, seed, dark=(120, 80, 42), light=(196, 150, 92), freq=18):
    h, w = shape
    r = rng(seed)
    warp = noise((h, w), 2.4, seed, aniso=(1.0, 0.15)) * 6
    yy, xx = np.mgrid[0:h, 0:w]
    rings = np.sin((xx / w * freq + warp) * np.pi * 2) * 0.5 + 0.5
    fib = noise((h, w), 1.0, seed + 1, aniso=(1.0, 0.05))
    t = np.clip(rings * 0.55 + fib * 0.45, 0, 1)
    col = mix(solid((h, w), dark), solid((h, w), light), t)
    # knots
    for _ in range(int(r.integers(0, 3))):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        d = np.hypot((xx - cx), (yy - cy) * 0.5)
        col = mix(col, solid((h, w), np.array(dark) * 0.7), smooth(9, 3, d))
    return col, t


@tex
def wood_crate():
    """Half-Life supply crate face (fit 0..1 per face): frame boards, diagonal brace, vertical planks"""
    S = 512
    # vertical planks
    col, t = _grain((S, S), 51, freq=7)
    col = np.transpose(col, (1, 0, 2)); t = t.T  # grain runs vertically
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    h = np.zeros((S, S)) + t * 0.15
    gaps = np.zeros((S, S))
    for gx in np.linspace(0, S, 6)[1:-1]:
        gaps = np.maximum(gaps, np.exp(-((xx - gx) / 1.4) ** 2))
    col = mix(col, col * 0.35, gaps); h -= gaps * 1.2
    r = rng(52)
    planktint = r.uniform(0.85, 1.08, 5)
    col *= planktint[np.clip((xx / (S / 5)).astype(int), 0, 4)][..., None]
    # diagonal brace (bottom-left to top-right)
    B = 58
    br, bt = _grain((S * 2, S * 2), 53, freq=10)
    from PIL import Image
    bim = Image.fromarray(np.clip(br, 0, 255).astype(np.uint8)).rotate(45, resample=Image.BILINEAR)
    brc = np.asarray(bim, np.float64)[S // 2:S // 2 + S, S // 2:S // 2 + S] * 1.05
    dd = np.abs((xx - (S - yy))) / np.sqrt(2)
    mb = smooth(B / 2 + 1, B / 2 - 1, dd)
    col = mix(col, brc, mb)
    h = h * (1 - mb) + mb * (2.0 + 0.1 * noise(S, 1, 54))
    col = mix(col, col * 0.5, smooth(B / 2 + 5, B / 2, dd) * (1 - mb) * 0.8)  # shadow of brace
    # frame boards
    F = 64
    fh, _ = _grain((S, S), 55, freq=9)  # horizontal grain
    fv = np.transpose(_grain((S, S), 56, freq=9)[0], (1, 0, 2))
    top = yy < F; bot = yy > S - F; lef = xx < F; rig = xx > S - F
    horiz = (top | bot) & ~((lef | rig) & False)
    frame_v = (lef | rig) & ~(top | bot)
    fm = (top | bot | lef | rig).astype(float)
    fm = gblur(fm, 0.7)
    fcol = np.where(horiz[..., None], fh, fv) * 1.08
    col = mix(col, fcol, fm)
    h = h * (1 - fm) + fm * 3.0
    # bevel/shadow inside frame edge
    din = np.minimum.reduce([np.abs(yy - F), np.abs(yy - (S - F)), np.abs(xx - F), np.abs(xx - (S - F))])
    inner = (xx > F) & (xx < S - F) & (yy > F) & (yy < S - F)
    col = mix(col, col * 0.45, smooth(10, 0, din) * inner * 0.8)
    # joints between frame boards
    for (x0, y0, x1, y1) in ((F, 0, F, F), (S - F, 0, S - F, F), (F, S - F, F, S), (S - F, S - F, S - F, S)):
        jm = np.exp(-((xx - x0) / 1.2) ** 2) * ((yy >= y0) & (yy <= y1))
        col = mix(col, col * 0.3, jm); h -= jm
    edge = np.minimum.reduce([xx, yy, S - xx, S - yy])
    col *= (0.65 + 0.35 * smooth(0, 8, edge))[..., None]
    # nails
    nl = Canvas(S, mode='L')
    for (cx, cy) in ((F / 2, F / 2), (S - F / 2, F / 2), (F / 2, S - F / 2), (S - F / 2, S - F / 2),
                     (S / 2, F / 2), (S / 2, S - F / 2), (F / 2, S / 2), (S - F / 2, S / 2)):
        for dx in (-9, 9):
            nl.circle((cx + dx, cy), 3, 255)
    nm = nl.array()
    col = mix(col, solid(S, (70, 70, 72)), nm * 0.9); h += nm * 0.5
    # light stencil
    st = Canvas(S, mode='L')
    st.text((S * 0.7, S * 0.77), 'SRS', 'black', 40, 255, anchor='mm', spacing=4)
    stm = st.array() * (0.5 + 0.5 * smooth(0.3, 0.6, noise(S, 1.5, 57)))
    col = mix(col, solid(S, (35, 28, 20)), stm * 0.7)
    col = mix(col, col * 0.75, smooth(0.6, 0.9, noise(S, 2.4, 58)) * 0.6)
    save('wood_crate', col, h, 25 + 20 * t, nstrength=3.0)


@tex
def wood_plank():
    """horizontal planks, tileable (towers, floors). 4 planks per repeat."""
    S = 512
    g, _ = _grain((S, S), 61, dark=(92, 66, 40), light=(158, 120, 80), freq=40)
    col = np.ascontiguousarray(np.transpose(g, (1, 0, 2)))  # grain along X
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    P = S // 4
    r = rng(63)
    tint = r.uniform(0.8, 1.1, 4)
    col *= tint[(yy // P).astype(int) % 4][..., None]
    ly = yy % P
    gap = np.exp(-(np.minimum(ly, P - ly) / 1.6) ** 2)
    # butt joints at different x per plank
    jx = r.uniform(0, S, 4)
    for k in range(4):
        m = ((yy // P) == k) * np.exp(-((xx - jx[k]) / 1.3) ** 2)
        gap = np.maximum(gap, m)
    col = mix(col, col * 0.3, gap)
    col = mix(col, col * 0.7, smooth(0.55, 0.9, noise(S, 2.3, 64)) * 0.6)
    h = -gap * 1.5 + noise(S, 1.0, 65, aniso=(0.05, 1.0)) * 0.3
    save('wood_plank', col, h, 20 + 15 * noise(S, 1.0, 66), nstrength=3.0)


# ------------------------------------------------------------------ rust / misc surfaces
@tex
def rust_metal():
    S = 512
    n1 = noise(S, 2.2, 71); n2 = noise(S, 1.0, 72); n3 = noise(S, 2.8, 73)
    paint = solid(S, (86, 100, 92)) * (0.85 + 0.25 * n2[..., None])
    rust = mix(solid(S, (120, 58, 24)), solid(S, (176, 96, 40)), n2) * (0.7 + 0.5 * n1[..., None])
    rust = mix(rust, solid(S, (60, 32, 18)), smooth(0.6, 0.9, n3) * 0.7)
    m = smooth(0.42, 0.52, n1 * 0.7 + n2 * 0.3)
    col = mix(paint, rust, m)
    pits, _ = worley(S, 400, 74)
    pm = smooth(4, 0, pits) * m
    col = mix(col, col * 0.4, pm * 0.8)
    h = m * -0.4 + n2 * 0.6 * m - pm * 1.0 + (1 - m) * 0.1
    save('rust_metal', col, h, 120 * (1 - m) + 15, nstrength=3.0)


@tex
def rubber():
    S = 256
    n = noise(S, 1.2, 81)
    col = solid(S, (34, 34, 36)) * (0.85 + 0.3 * n[..., None])
    save('rubber', col, n * 0.4, 40 + 30 * n, nstrength=2.0)


@tex
def plastic_beige():
    """beige 80s/90s computer plastic (terminals, CRTs, keyboards)"""
    S = 512
    n = noise(S, 0.6, 91); b = noise(S, 2.4, 92)
    col = solid(S, (196, 186, 160)) * (0.92 + 0.06 * n[..., None] + 0.08 * b[..., None])
    dirt = smooth(0.6, 0.9, noise(S, 2.6, 93))
    col = mix(col, col * 0.7, dirt * 0.5)
    save('plastic_beige', col, n * 0.2, 70 - 30 * dirt, nstrength=1.5)


@tex
def canvas():
    S = 512
    yy, xx = np.mgrid[0:S, 0:S]
    weave = (np.sin(xx * np.pi / 2) * np.sin(yy * np.pi / 2)) * 0.5 + 0.5
    n = noise(S, 2.2, 101); f = noise(S, 0.8, 102)
    col = solid(S, (112, 108, 72)) * (0.82 + 0.25 * n[..., None]) * (0.9 + 0.12 * weave[..., None]) * (0.95 + 0.1 * f[..., None])
    st = smooth(0.6, 0.85, noise(S, 2.8, 103))
    col = mix(col, col * 0.65, st * 0.6)
    save('canvas', col, weave * 0.5 + n * 0.3, 20, nstrength=2.0)


@tex
def sandbag():
    S = 512
    yy, xx = np.mgrid[0:S, 0:S]
    weave = (np.sin(xx * np.pi / 3) * 0.5 + 0.5) * (np.sin(yy * np.pi / 3 + np.pi / 2) * 0.5 + 0.5)
    n = noise(S, 2.0, 111)
    col = solid(S, (150, 128, 90)) * (0.8 + 0.3 * n[..., None]) * (0.88 + 0.16 * weave[..., None])
    col = mix(col, col * 0.6, smooth(0.6, 0.9, noise(S, 2.6, 112)) * 0.6)
    save('sandbag', col, weave * 0.6 + n * 0.8, 12, nstrength=2.5)


@tex
def cardboard():
    """cardboard box face (fit UV): tape strip + print"""
    S = 512
    n = noise(S, 1.6, 121)
    col = solid(S, (176, 140, 92)) * (0.9 + 0.15 * n[..., None])
    yy, xx = np.mgrid[0:S, 0:S]
    tape = (np.abs(xx - S / 2) < 40).astype(float)
    col = mix(col, solid(S, (196, 170, 120)), tape * 0.7)
    c = Canvas(S, mode='L')
    c.text((S / 2, S * 0.62), 'λ SUPPLY', 'black', 54, 255, anchor='mm')
    c.text((S / 2, S * 0.74), 'STARFALL RESEARCH SITE', 'cond_bold', 26, 255, anchor='mm')
    c.rect((40, 40, S - 40, S - 40), None, outline=255, width=3)
    col = mix(col, solid(S, (50, 34, 24)), c.array() * 0.8 * (1 - tape * 0.6))
    edge = np.minimum.reduce([xx, yy, S - xx, S - yy])
    col *= (0.75 + 0.25 * smooth(0, 10, edge))[..., None]
    save('cardboard', col, n * 0.2 + tape * 0.2, 20 + 50 * tape, nstrength=2.0)


@tex
def specimen():
    S = 256
    w, _ = worley(S, 30, 131)
    n = noise(S, 2.0, 132)
    col = mix(solid(S, (190, 120, 110)), solid(S, (120, 60, 70)), smooth(2, 18, w)) * (0.8 + 0.3 * n[..., None])
    save('specimen', col, -w / 18 + n, 180, nstrength=3.0)


# ------------------------------------------------------------------ alpha surfaces
@tex
def glass():
    S = 512
    sm = noise(S, 2.6, 141); st = noise(S, 2.0, 142, aniso=(1.0, 8.0)); f = noise(S, 1.0, 143)
    col = solid(S, (186, 214, 220)) * (0.9 + 0.15 * sm[..., None])
    a = 40 + 70 * smooth(0.55, 0.95, sm) + 45 * smooth(0.6, 0.9, st) + 10 * f
    col = mix(col, solid(S, (150, 160, 150)), smooth(0.65, 0.95, sm) * 0.4)
    save('glass', col, sm * 0.2, 255 - 60 * smooth(0.6, 0.9, sm), nstrength=1.0, alpha=a)


@tex
def glass_cracked():
    """glass with crack lines (broken tank shards)"""
    S = 512
    sm = noise(S, 2.6, 151)
    e, _ = worley(S, 18, 152, second=True)
    cr = smooth(2.5, 0.0, e)
    col = solid(S, (190, 216, 222)) * (0.9 + 0.15 * sm[..., None])
    col = mix(col, solid(S, (240, 250, 250)), cr)
    a = 55 + 80 * smooth(0.5, 0.95, sm) + 150 * cr
    save('glass_cracked', col, sm * 0.2 - cr, 255, nstrength=2.0, alpha=np.clip(a, 0, 255))


@tex
def metal_grate():
    """catwalk grating: bearing bars + cross bars, holes alpha 0. 64 units per repeat recommended."""
    S, P = 512, 64
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    lx, ly = xx % P, yy % P
    bar_x = smooth(7, 5, np.minimum(lx, P - lx))     # vertical bearing bars every 64 px
    bar_y = smooth(5, 3, np.abs(ly - P / 2))          # cross bars
    lx2 = xx % (P / 2)
    bar_x2 = smooth(5, 3, np.minimum(lx2, P / 2 - lx2))
    m = np.clip(np.maximum.reduce([bar_x, bar_y, bar_x2]), 0, 1)
    n = noise(S, 2.0, 161)
    col = solid(S, (96, 100, 104)) * (0.75 + 0.4 * n[..., None])
    col = mix(col, solid(S, (150, 150, 145)), smooth(0.5, 0.0, np.minimum(lx, P - lx) - 2) * 0.2)
    col = mix(col, col * 0.6, smooth(0.6, 0.9, noise(S, 2.4, 162)) * 0.6)
    h = bar_x * 1.0 + bar_y * 0.7 + bar_x2 * 0.6
    save('metal_grate', col, h * 2, 120 * m, nstrength=3.0, alpha=m * 255)


@tex
def chainlink():
    """galvanised chain-link diamonds, alpha tested. 64 units per repeat."""
    S, P = 512, 64
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    a = (xx + yy) % P; b = (xx - yy) % P
    w = 2.2
    wa = smooth(w + 1, w - 0.5, np.minimum(a, P - a))
    wb = smooth(w + 1, w - 0.5, np.minimum(b, P - b))
    m = np.maximum(wa, wb)
    n = noise(S, 2.0, 171)
    col = solid(S, (150, 156, 158)) * (0.8 + 0.3 * n[..., None])
    rust = smooth(0.62, 0.85, noise(S, 2.4, 172))
    col = mix(col, solid(S, (130, 80, 45)), rust * 0.7)
    h = np.maximum(wa * (0.6 + 0.4 * np.sin(b / P * 2 * np.pi * 4)), wb * (0.6 + 0.4 * np.cos(a / P * 2 * np.pi * 4)))
    save('chainlink', col, h * 2, 160 * m * (1 - rust), nstrength=3.0, alpha=m * 255)


@tex
def blood_splat():
    S = 512
    r = rng(181)
    c = Canvas(S, mode='L', ss=2)
    cx, cy = S / 2, S / 2
    # main blob from overlapping ellipses
    for _ in range(26):
        a = r.uniform(0, 2 * np.pi); d = abs(r.normal(0, 40)); rr = r.uniform(25, 70)
        c.circle((cx + d * np.cos(a), cy + d * np.sin(a)), rr, 255)
    # spatter streaks and droplets radiating out
    for _ in range(40):
        a = r.uniform(0, 2 * np.pi); d0 = r.uniform(60, 110); d1 = d0 + r.uniform(30, 140)
        w = r.uniform(3, 9)
        c.line([(cx + d0 * np.cos(a), cy + d0 * np.sin(a)), (cx + d1 * np.cos(a), cy + d1 * np.sin(a))], 255, w)
        c.circle((cx + (d1 + w) * np.cos(a), cy + (d1 + w) * np.sin(a)), w * 0.9, 255)
    for _ in range(160):
        a = r.uniform(0, 2 * np.pi); d = r.uniform(90, 240); rr = r.uniform(1, 6) * (1.2 - d / 240)
        c.circle((cx + d * np.cos(a), cy + d * np.sin(a)), max(rr, 0.8), 255)
    m = c.array()
    m = np.clip(m * (0.85 + 0.3 * noise(S, 2.0, 182)), 0, 1)
    edge = m - gblur(m, 3)
    n = noise(S, 1.8, 183)
    col = mix(solid(S, (110, 6, 6)), solid(S, (58, 2, 4)), np.clip(n * 0.7 + gblur(m, 6) * 0.4, 0, 1))
    col = mix(col, solid(S, (150, 16, 12)), np.clip(edge * 3, 0, 1) * 0.5)
    m[:2, :] = 0; m[-2:, :] = 0; m[:, :2] = 0; m[:, -2:] = 0
    save('blood_splat', col, gblur(m, 2) * 0.6, 200 * m, nstrength=3.0, alpha=np.clip(m * 255 * 0.95, 0, 255))


# ------------------------------------------------------------------ glowing materials
@tex
def green_liquid():
    S = 512
    e, _ = worley(S, 60, 191, second=True)
    caust = smooth(6, 0, e)
    n = noise(S, 2.0, 192)
    col = mix(solid(S, (30, 170, 60)), solid(S, (150, 255, 140)), np.clip(caust * 0.8 + n * 0.3, 0, 1))
    r = rng(193)
    bub = Canvas(S, mode='L')
    for _ in range(90):
        x, y = r.uniform(10, S - 10, 2); rr = r.uniform(1.5, 6)
        bub.circle((x, y), rr, None, outline=255, width=1.2)
    col = mix(col, solid(S, (220, 255, 210)), bub.array() * 0.8)
    save('green_liquid', col, caust * 0.5 + n * 0.5, 255, nstrength=2.0, glow=col)


@tex
def crystal():
    S = 512
    e, idx = worley(S, 40, 201, second=True)
    facet = smooth(5, 0, e)
    r = rng(202)
    cellv = r.uniform(0.55, 1.0, 40)[idx]
    n = noise(S, 1.8, 203)
    col = mix(solid(S, (70, 170, 210)), solid(S, (220, 250, 255)), np.clip(cellv * 0.7 + facet * 0.5 + n * 0.2, 0, 1))
    glow = mix(solid(S, (20, 110, 160)), solid(S, (200, 245, 255)), np.clip(facet * 0.8 + (cellv - 0.55) * 1.2, 0, 1))
    save('crystal', col, cellv * 2 + facet, 255, nstrength=3.0, glow=glow)


@tex
def meteor_rock():
    S = 1024
    n1 = noise(S, 2.3, 211); n2 = noise(S, 1.2, 212)
    e, _ = worley(S, 70, 213, second=True)
    crack = smooth(3.0, 0.0, e)
    veins = smooth(0.0, 1.0, crack) * smooth(0.45, 0.6, noise(S, 2.2, 214))
    col = mix(solid(S, (36, 30, 28)), solid(S, (92, 72, 58)), n1 * 0.7 + n2 * 0.3)
    char = smooth(0.5, 0.8, noise(S, 2.0, 215))
    col = mix(col, solid(S, (16, 14, 14)), char * 0.7)
    col = mix(col, col * 0.3, crack * 0.8)
    col = mix(col, solid(S, (120, 220, 255)), veins * 0.9)
    glow = solid(S, (90, 210, 255)) * gblur(veins, 1.2)[..., None] * 1.3
    h = n1 * 3 + n2 - crack * 1.5
    save('meteor_rock', col, h, 30 + 200 * veins, nstrength=4.0, glow=np.clip(glow, 0, 255))


# ------------------------------------------------------------------ screens and panels
def _crt(img, S, tint=(1, 1, 1)):
    yy, xx = np.mgrid[0:S[1], 0:S[0]] + 0.5
    scan = 0.82 + 0.18 * (np.sin(yy * np.pi / 2) ** 2)
    u = (xx / S[0] - 0.5) * 2; v = (yy / S[1] - 0.5) * 2
    vig = np.clip(1.15 - 0.35 * (u ** 4 + v ** 4) - 0.15 * (u * u + v * v), 0, 1)
    img = gblur(img, 0.6) * 0.7 + img * 0.3 + gblur(img, 3.0) * 0.6
    return img * (scan * vig)[..., None]


@tex
def screen_terminal():
    W = H = 512
    c = Canvas(W, H, mode='RGB', bg=(4, 14, 6))
    G = (70, 255, 120); D = (30, 140, 60)
    c.rect((10, 10, W - 10, 44), (30, 120, 55))
    c.text((20, 27), 'LAMBDA DIRECTORATE // SRS-NET 4.2', 'mono_bold', 19, (4, 20, 8), anchor='lm')
    lines = ['> LOGIN: HALE_M ......... OK', '> RESONANCE ARRAY STATUS', '  EMITTER A   87.3%  NOMINAL', '  EMITTER B   91.0%  NOMINAL',
             '  EMITTER C   12.4%  ** FAULT **', '> CONTAINMENT WING B', '  SEAL INTEGRITY ...... 34%', '  LIFE SIGNS ........ UNKNOWN',
             '> ZPF CALIBRATION  RUN 0447', '  FIELD Q = 3.1E+06  DRIFT 0.02', '  CRYSTAL SAMPLE 7A: STABLE', '> INCIDENT 7 LOG: ACCESS DENIED',
             '  CLEARANCE LEVEL 3 REQUIRED', '> _']
    for i, s in enumerate(lines):
        col = (255, 200, 60) if 'FAULT' in s or 'DENIED' in s else G if s.startswith('>') else D
        c.text((22, 62 + i * 31), s, 'mono', 20, col, anchor='lm')
    c.rect((22 + 0, 62 + 13 * 31 - 10, 34, 62 + 13 * 31 + 10), G)
    img = np.asarray(c.im.resize((W, H)), np.float64)
    img = _crt(img, (W, H))
    save('screen_terminal', img, None, 230, nstrength=1.0, glow=img, glow_name='screen_terminal_g')


@tex
def screen_graphs():
    W = H = 512
    c = Canvas(W, H, mode='RGB', bg=(3, 10, 12))
    grid = (20, 70, 50)
    for k in range(0, 513, 32):
        c.line([(k, 0), (k, H)], grid, 1); c.line([(0, k), (W, k)], grid, 1)
    x = np.linspace(0, W, 300)
    y1 = H * 0.3 + 60 * np.sin(x / W * 2 * np.pi * 3) * np.exp(-x / W)
    y2 = H * 0.3 + 30 * np.sin(x / W * 2 * np.pi * 9 + 1)
    c.line(list(zip(x, y1)), (90, 255, 140), 3)
    c.line(list(zip(x, y2)), (80, 220, 255), 2)
    r = rng(221)
    y3 = H * 0.62 + np.cumsum(r.normal(0, 4, 300)) * 0.5
    c.line(list(zip(x, y3)), (255, 210, 70), 2)
    for i in range(12):
        hgt = r.uniform(20, 110)
        c.rect((24 + i * 38, H - 20 - hgt, 50 + i * 38, H - 20), (60, 230, 120) if hgt < 90 else (255, 90, 60))
    c.text((14, 14), 'RESONANCE SPECTRUM  CH1-CH3', 'mono_bold', 18, (120, 255, 160))
    c.text((W - 14, 14), 'T+00:41:07', 'mono', 18, (255, 210, 70), anchor='ra')
    img = _crt(np.asarray(c.im.resize((W, H)), np.float64), (W, H))
    save('screen_graphs', img, None, 230, nstrength=1.0, glow=img, glow_name='screen_graphs_g')


@tex
def control_panel():
    """console face: buttons, dials, toggles, lamps, a meter. glow map lights only. Fit 0..1."""
    W = H = 512
    r = rng(231)
    base = solid(W, (122, 128, 132)) * (0.92 + 0.1 * noise(W, 1.5, 232)[..., None])
    rgb = Canvas(W, H, mode='RGB', bg=(0, 0, 0)); hm = Canvas(W, H, mode='L', bg=110); gl = Canvas(W, H, mode='RGB', bg=(0, 0, 0))
    msk = Canvas(W, H, mode='L', bg=0)

    def put(shape, args, col, hval, glow=None):
        getattr(rgb, shape)(*args, fill=col); getattr(msk, shape)(*args, fill=255); getattr(hm, shape)(*args, fill=hval)
        if glow: getattr(gl, shape)(*args, fill=glow)
    # sub-panels
    for (x0, y0, x1, y1) in ((12, 12, 250, 180), (262, 12, 500, 180), (12, 192, 500, 340), (12, 352, 500, 500)):
        put('rect', [(x0, y0, x1, y1)], (96, 104, 112), 90)
        put('rect', [(x0 + 3, y0 + 3, x1 - 3, y1 - 3)], (110, 118, 126), 100)
    # button grid
    cols = [(200, 40, 30), (40, 170, 60), (230, 190, 40), (220, 220, 210), (40, 110, 200)]
    for i in range(5):
        for j in range(3):
            cc = cols[(i + j * 2) % 5]; lit = r.random() < 0.45
            x, y = 30 + i * 44, 30 + j * 48
            put('rect', [(x - 2, y - 2, x + 32, y + 32)], (40, 40, 44), 70)
            put('rect', [(x, y, x + 30, y + 30)], tuple(int(v * (1.0 if lit else 0.6)) for v in cc), 200,
                glow=tuple(int(v * 0.9) for v in cc) if lit else None)
    # dials
    for i in range(4):
        cx, cy = 300 + i * 56, 60
        put('circle', [(cx, cy), 22], (30, 30, 32), 180)
        put('circle', [(cx, cy), 16], (70, 70, 74), 210)
        a = r.uniform(-2.4, 0.6)
        rgb.line([(cx, cy), (cx + 15 * np.cos(a), cy + 15 * np.sin(a))], (230, 230, 230), 3)
        for k in range(9):
            t = -3.6 + k * 0.45
            rgb.line([(cx + 25 * np.cos(t), cy + 25 * np.sin(t)), (cx + 29 * np.cos(t), cy + 29 * np.sin(t))], (20, 20, 20), 2)
    # small lamps
    for i in range(8):
        cx, cy = 290 + i * 26, 130; cc = [(255, 60, 40), (80, 255, 90), (255, 200, 50)][i % 3]; on = r.random() < 0.6
        put('circle', [(cx, cy), 8], (40, 40, 40), 150)
        put('circle', [(cx, cy), 6], cc if on else tuple(v // 4 for v in cc), 190, glow=cc if on else None)
    # toggle switches
    for i in range(10):
        x, y = 40 + i * 46, 220
        put('rect', [(x - 10, y, x + 10, y + 40)], (50, 50, 54), 140)
        up = r.random() < 0.5
        put('rect', [(x - 4, y + (4 if up else 20), x + 4, y + (20 if up else 36))], (210, 210, 205), 230)
        put('circle', [(x, y + 58), 5], (80, 255, 90) if up else (60, 20, 20), 160, glow=(80, 255, 90) if up else None)
    rgb.text((24, 310), 'RESONANCE  FEED  1  2  3  4  5  6  7  8  9  10', 'cond_bold', 16, (25, 25, 28))
    # meter
    put('rect', [(30, 370, 230, 480)], (230, 225, 200), 120)
    for k in range(11):
        t = np.pi * (1.15 + k * 0.07)
        rgb.line([(130 + 85 * np.cos(t), 470 + 85 * np.sin(t)), (130 + 95 * np.cos(t), 470 + 95 * np.sin(t))], (20, 20, 20), 2)
    rgb.line([(130, 470), (130 + 90 * np.cos(np.pi * 1.62), 470 + 90 * np.sin(np.pi * 1.62))], (200, 30, 20), 3)
    gl.rect((32, 372, 228, 478), (60, 56, 40))
    # mini screen
    put('rect', [(260, 370, 480, 480)], (6, 30, 14), 100, glow=(10, 60, 25))
    xs = np.linspace(268, 472, 60)
    pts = list(zip(xs, 425 + 30 * np.sin(xs / 12)))
    rgb.line(pts, (80, 255, 120), 2); gl.line(pts, (80, 255, 120), 2)
    # big red button
    put('circle', [(470, 290), 22], (40, 40, 40), 150)
    put('circle', [(470, 290), 17], (220, 30, 20), 240, glow=(140, 10, 5))
    m = msk.array()[..., None]
    col = base * (1 - m) + np.asarray(rgb.im.resize((W, H)), np.float64) * m
    # labels / grime
    col = mix(col, col * 0.7, smooth(0.6, 0.9, noise(W, 2.4, 233)) * 0.5)
    h = hm.array() * 4
    glow = np.asarray(gl.im.resize((W, H)), np.float64)
    save('control_panel', col, h, 90 + 100 * m[..., 0], nstrength=3.0, glow=gblur(glow, 0.8) * 1.1)


@tex
def keyboard():
    """keyboard top (fit 0..1, 512x256): beige keys on darker base"""
    W, H = 512, 256
    c = Canvas(W, H, mode='RGB', bg=(150, 142, 120)); hm = Canvas(W, H, mode='L', bg=60)
    rows = [14, 14, 13, 12]
    for j, n in enumerate(rows):
        kw = (W - 40) / 15.0
        x0 = 20 + j * kw * 0.3
        for i in range(n):
            x = x0 + i * kw; y = 24 + j * 46
            c.rect((x + 2, y + 2, x + kw - 3, y + 40), (205, 198, 176), radius=4); hm.rect((x + 2, y + 2, x + kw - 3, y + 40), 200, radius=4)
            c.rect((x + 6, y + 5, x + kw - 7, y + 32), (218, 212, 192), radius=3)
    c.rect((80, 210, 400, 246), (205, 198, 176), radius=4); hm.rect((80, 210, 400, 246), 200, radius=4)
    col = np.asarray(c.im.resize((W, H)), np.float64)
    col *= (0.9 + 0.12 * noise((H, W), 1.4, 241))[..., None]
    save('keyboard', col, hm.array() * 3, 60, nstrength=3.0)


@tex
def server_lights():
    """server rack front: stacked 1U/2U units with LEDs, vents, drive bays. glow = LEDs. Fit 0..1 (512x1024)."""
    W, H = 512, 1024
    r = rng(251)
    c = Canvas(W, H, mode='RGB', bg=(30, 32, 36)); g = Canvas(W, H, mode='RGB', bg=(0, 0, 0)); hm = Canvas(W, H, mode='L', bg=40)
    y = 8
    while y < H - 40:
        u = int(r.choice([40, 40, 80, 120]))
        c.rect((8, y, W - 8, y + u - 3), (54, 58, 64)); hm.rect((8, y, W - 8, y + u - 3), 140)
        c.rect((8, y, 30, y + u - 3), (80, 84, 90)); c.rect((W - 30, y, W - 8, y + u - 3), (80, 84, 90))
        kind = r.integers(0, 3)
        if kind == 0:   # vents
            for vx in range(60, 300, 10): c.rect((vx, y + 8, vx + 5, y + u - 11), (14, 14, 16)); hm.rect((vx, y + 8, vx + 5, y + u - 11), 60)
        elif kind == 1:  # drive bays
            for k in range(6):
                bx = 50 + k * 50; c.rect((bx, y + 6, bx + 44, y + u - 9), (40, 42, 46)); c.rect((bx + 4, y + 10, bx + 40, y + 16), (90, 90, 96))
        else:
            c.rect((60, y + 8, 260, y + u - 11), (20, 24, 26)); c.text((70, y + u / 2 - 2), 'SRS-%02d' % r.integers(1, 99), 'mono_bold', 14, (150, 160, 170), anchor='lm')
        for k in range(int(r.integers(4, 12))):
            cx = 330 + k * 14; cy = y + 12 + (k % 2) * 12
            cc = [(80, 255, 90), (80, 255, 90), (255, 190, 40), (255, 50, 30), (60, 160, 255)][int(r.integers(0, 5))]
            on = r.random() < 0.7
            c.circle((cx, cy), 3.5, cc if on else (40, 40, 40)); hm.circle((cx, cy), 3.5, 200)
            if on: g.circle((cx, cy), 4.5, cc)
        y += u
    col = np.asarray(c.im.resize((W, H)), np.float64)
    col *= (0.9 + 0.15 * noise((H, W), 2.0, 252))[..., None]
    glow = gblur(np.asarray(g.im.resize((W, H)), np.float64), 0.8) * 1.3
    save('server_lights', col, hm.array() * 3, 110, nstrength=3.0, glow=np.clip(glow, 0, 255))


@tex
def fluorescent_light():
    """ceiling light panel face (fit 0..1, 512x128): metal frame, prismatic diffuser with two bright tubes. _g masks the frame."""
    W, H = 512, 128
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    frame = (np.minimum.reduce([xx, yy, W - xx, H - yy]) < 10).astype(float)
    tubes = np.exp(-((yy - H * 0.33) / 14) ** 2) + np.exp(-((yy - H * 0.67) / 14) ** 2)
    prism = (np.sin(xx * np.pi / 3) * np.sin(yy * np.pi / 3)) * 0.5 + 0.5
    diff = np.clip(0.72 + 0.35 * tubes + 0.06 * prism, 0, 1.2)
    col = mix(solid((H, W), (255, 252, 240)) * diff[..., None], solid((H, W), (140, 142, 146)), frame)
    glow = solid((H, W), (255, 250, 235)) * (diff * (1 - frame))[..., None]
    save('fluorescent_light', np.clip(col, 0, 255), prism * 0.3 - frame, 100, nstrength=1.5, glow=np.clip(glow, 0, 255))


@tex
def lamp_glow():
    """small round lamp lens (wall lamp, floodlight): hot center -> warm edge. Fit 0..1."""
    S = 256
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    d = np.hypot(xx - S / 2, yy - S / 2) / (S / 2)
    ring = np.sin(d * np.pi * 7) * 0.5 + 0.5
    b = np.clip(1.0 - 0.45 * d ** 2 + 0.06 * ring, 0, 1)
    col = solid(S, (255, 244, 215)) * b[..., None]
    save('lamp_glow', col, ring * 0.3, 255, nstrength=1.5, glow=col)


@tex
def halo():
    """additive glow card: soft radial falloff to pure black at the edges (white; tint with the effect colour)"""
    S = 256
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    d = np.hypot(xx - S / 2, yy - S / 2) / (S / 2)
    b = np.clip(1 - d, 0, 1) ** 2.2 + 0.6 * np.exp(-(d / 0.12) ** 2)
    b = np.clip(b, 0, 1) * smooth(1.0, 0.92, d)
    save('halo', solid(S, (255, 255, 255)) * b[..., None], None, 0, normal=False)


@tex
def spark():
    """additive spark burst: bright core + thin rays, black background"""
    S = 256
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    dx, dy = xx - S / 2, yy - S / 2
    d = np.hypot(dx, dy) / (S / 2); a = np.arctan2(dy, dx)
    r = rng(401)
    rays = np.zeros((S, S))
    for k in range(14):
        ang = r.uniform(-np.pi, np.pi); L = r.uniform(0.4, 0.95)
        da = np.abs(np.angle(np.exp(1j * (a - ang))))
        rays = np.maximum(rays, np.exp(-(da * d * S / 2 / 1.6) ** 2) * np.clip(1 - d / L, 0, 1))
    core = np.exp(-(d / 0.08) ** 2) + 0.5 * np.exp(-(d / 0.25) ** 2)
    b = np.clip(core + rays, 0, 1) * smooth(1.0, 0.9, d)
    col = np.stack([b * 255, b ** 1.4 * 235, b ** 2.5 * 190], -1)
    save('spark', col, None, 0, normal=False)


# ------------------------------------------------------------------ signs, posters, boards
def _plate(W, H, color, seed, border=None):
    n = noise((H, W), 2.0, seed); f = noise((H, W), 0.8, seed + 1)
    col = solid((H, W), color) * (0.92 + 0.08 * n[..., None] + 0.05 * f[..., None])
    dirt = smooth(0.6, 0.9, noise((H, W), 2.4, seed + 2))
    col = mix(col, col * 0.75, dirt * 0.4)
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    e = np.minimum.reduce([xx, yy, W - xx, H - yy])
    col *= (0.75 + 0.25 * smooth(0, 6, e))[..., None]
    h = smooth(0, 6, e) * 0.5 + n * 0.1
    return col, h, dirt


def _screws(c, W, H, inset=22, r=7):
    for (x, y) in ((inset, inset), (W - inset, inset), (inset, H - inset), (W - inset, H - inset)):
        c.circle((x, y), r, 255)


def _finish_sign(name, col, h, ink_layers, W, H, spec=90, seed=0):
    """ink_layers: list of (mask, colour). Adds screws and mild wear."""
    wear = smooth(0.66, 0.8, noise((H, W), 1.6, seed + 9))
    for m, cc in ink_layers:
        col = mix(col, np.broadcast_to(np.asarray(cc, np.float64), col.shape), m * (1 - 0.6 * wear))
    sc = Canvas(W, H, mode='L'); _screws(sc, W, H)
    sm = sc.array()
    col = mix(col, solid((H, W), (150, 150, 150)), sm); h = h + gblur(sm, 1) * 1.5
    col = mix(col, solid((H, W), (60, 60, 60)), np.clip(gblur(sm, 2) - sm, 0, 1) * 0.8)
    save(name, col, h, spec, nstrength=3.0)


def _lambda_logo(c, cx, cy, R, fill, width=None):
    width = width or R * 0.16
    c.circle((cx, cy), R, None, outline=fill, width=width)
    c.text((cx, cy + R * 0.04), 'λ', 'sans_bold', R * 1.45, fill, anchor='mm')


@tex
def sign_lambda():
    S = 512
    col, h, _ = _plate(S, S, (232, 228, 216), 301)
    c = Canvas(S, mode='L')
    _lambda_logo(c, S / 2, S / 2, 170, 255, width=26)
    b = Canvas(S, mode='L'); b.rect((34, 34, S - 34, S - 34), None, outline=255, width=6)
    _finish_sign('sign_lambda', col, h, [(c.array(), (236, 110, 16)), (b.array(), (40, 40, 40))], S, S, seed=301)


def _biohazard(c, cx, cy, R, fill, bg):
    """approximate biohazard trefoil: 3 outer crescents + inner ring, drawn with fill/bg"""
    for k in range(3):
        a = np.radians(90 + k * 120)
        c.circle((cx + 0.47 * R * np.cos(a), cy - 0.47 * R * np.sin(a)), 0.53 * R, fill)
    for k in range(3):
        a = np.radians(90 + k * 120)
        c.circle((cx + 0.62 * R * np.cos(a), cy - 0.62 * R * np.sin(a)), 0.40 * R, bg)
    c.circle((cx, cy), 0.42 * R, None, outline=fill, width=0.1 * R)
    for k in range(3):
        a = np.radians(90 + k * 120)
        p = [(cx + 0.33 * R * np.cos(a + s), cy - 0.33 * R * np.sin(a + s)) for s in (-0.12, 0.12)]
        q = [(cx + 0.55 * R * np.cos(a + s), cy - 0.55 * R * np.sin(a + s)) for s in (0.08, -0.08)]
        c.poly(p + q, bg)
    c.circle((cx, cy), 0.15 * R, bg)


@tex
def sign_biohazard():
    S = 512
    col, h, _ = _plate(S, S, (236, 196, 32), 311)
    c = Canvas(S, mode='L')
    _biohazard(c, S / 2, S * 0.43, 165, 255, 0)
    c.text_fit((60, S - 112, S - 60, S - 50), 'BIOHAZARD', 'black', 255)
    b = Canvas(S, mode='L'); b.rect((26, 26, S - 26, S - 26), None, outline=255, width=8)
    _finish_sign('sign_biohazard', col, h, [(c.array(), (22, 20, 18)), (b.array(), (22, 20, 18))], S, S, seed=311)


@tex
def sign_restricted():
    W, H = 1024, 512
    col, h, _ = _plate(W, H, (234, 232, 226), 321)
    band = Canvas(W, H, mode='L'); band.rect((30, 30, W - 30, 230), 255)
    t1 = Canvas(W, H, mode='L'); t1.text_fit((70, 60, W - 70, 200), 'RESTRICTED AREA', 'black', 255)
    t2 = Canvas(W, H, mode='L')
    t2.text_fit((80, 268, W - 80, 368), 'AUTHORIZED PERSONNEL ONLY', 'heavy', 255)
    t2.text_fit((200, 400, W - 200, 450), 'LAMBDA DIRECTORATE  ·  SITE SECURITY', 'cond_bold', 255)
    _finish_sign('sign_restricted', col, h, [(band.array(), (186, 28, 22)), (t1.array(), (245, 240, 235)), (t2.array(), (24, 24, 24))], W, H, seed=321)


@tex
def sign_testchamber():
    W, H = 1024, 512
    col, h, _ = _plate(W, H, (54, 62, 74), 331)
    logo = Canvas(W, H, mode='L'); _lambda_logo(logo, 170, 200, 120, 255, width=18)
    t = Canvas(W, H, mode='L')
    t.text_fit((320, 110, W - 60, 290), 'TEST CHAMBER', 'black', 255)
    t.text_fit((90, 360, W - 90, 430), 'STARFALL RESEARCH SITE', 'heavy', 255)
    stripe = Canvas(W, H, mode='L')
    for k in range(-2, 40):
        x = k * 40
        stripe.poly([(x, 312), (x + 20, 312), (x + 0, 332), (x - 20, 332)], 255)
    sm = stripe.array(); yy = np.arange(H)[:, None]
    yb = ((yy > 310) & (yy < 334)).astype(float) * np.ones((1, W))
    _finish_sign('sign_testchamber', col, h, [(yb, (236, 182, 22)), (sm * yb, (24, 24, 24)), (logo.array(), (236, 110, 16)),
                                             (t.array(), (236, 236, 230))], W, H, seed=331)


@tex
def whiteboard():
    W, H = 1024, 512
    n = noise((H, W), 2.4, 341)
    col = solid((H, W), (238, 240, 240)) * (0.96 + 0.04 * n[..., None])
    ghost = smooth(0.55, 0.85, noise((H, W), 2.0, 342, aniso=(1.0, 0.3)))
    col = mix(col, solid((H, W), (200, 205, 215)), ghost * 0.35)
    r = rng(343)
    layers = {}

    def hand(c, xy, s, size, kind='cond_oblique'):
        x, y = xy
        for ch in s:
            c.text((x, y + r.normal(0, 1.2)), ch, kind, size * r.uniform(0.92, 1.08), 255, anchor='ls')
            x += font(kind, size).getlength(ch) * r.uniform(0.95, 1.05)
    blue = Canvas(W, H, mode='L'); black = Canvas(W, H, mode='L'); red = Canvas(W, H, mode='L')
    hand(blue, (40, 70), 'E = ħω (n + ½)', 44)
    hand(blue, (40, 140), 'Φ_zp = ∫ ρ(ω) dω  →  ∞ ?', 36)
    hand(black, (40, 210), 'λ_res = 2πc / ω₀ ≈ 4.71 m', 36)
    hand(black, (40, 280), 'Q ≥ 3×10⁶  (crystal 7A)', 34)
    hand(blue, (40, 350), 'F = -∇(U_zpf)  ⇒ "grav" tether', 34)
    hand(black, (40, 430), 'Run 0447: drift 0.02  ✓', 32)
    # resonance curve
    xs = np.linspace(600, 960, 120)
    ys = 300 - 180 / (1 + ((xs - 780) / 25) ** 2)
    black.line([(600, 310), (970, 310)], 255, 3); black.line([(600, 310), (600, 90)], 255, 3)
    blue.line(list(zip(xs, ys)), 255, 4)
    hand(black, (760, 345), 'ω₀', 30)
    # crystal hexagon sketch
    hx, hy = 860, 430
    pts = [(hx + 45 * np.cos(np.radians(a)), hy + 45 * np.sin(np.radians(a))) for a in range(0, 361, 60)]
    black.line(pts, 255, 3)
    red.circle((540, 220), 60, None, outline=255, width=4)
    hand(red, (492, 230), 'RIFT?', 34)
    hand(red, (640, 60), 'DO NOT ERASE - H.', 30)
    red.line([(600, 245), (650, 270)], 255, 3)
    for c, cc in ((blue, (30, 60, 170)), (black, (30, 30, 34)), (red, (190, 30, 30))):
        m = c.array() * (0.75 + 0.25 * noise((H, W), 1.0, 344))
        col = mix(col, solid((H, W), cc), m)
    save('whiteboard', col, n * 0.1, 200, nstrength=1.0)


@tex
def poster_safety():
    W, H = 512, 1024
    n = noise((H, W), 2.0, 351)
    col = solid((H, W), (236, 230, 210)) * (0.9 + 0.1 * n[..., None])
    top = Canvas(W, H, mode='L'); top.rect((0, 0, W, 230), 255)
    tt = Canvas(W, H, mode='L'); tt.text_fit((30, 30, W - 30, 120), 'SAFETY', 'black', 255); tt.text_fit((30, 120, W - 30, 205), 'FIRST', 'black', 255)
    pic = Canvas(W, H, mode='L')
    # hard hat pictogram
    cx, cy = W / 2, 420
    pic.d.pieslice([(cx - 150) * 2, (cy - 130) * 2, (cx + 150) * 2, (cy + 130) * 2], 180, 360, fill=255)
    pic.rect((cx - 190, cy - 6, cx + 190, cy + 24), 255, radius=10)
    pic.rect((cx - 12, cy - 130, cx + 12, cy - 10), 0)
    body = Canvas(W, H, mode='L')
    lines = ['WEAR PROTECTIVE', 'EQUIPMENT AT ALL TIMES', '', 'REPORT ALL SPECIMEN', 'SIGHTINGS TO SECURITY', '', 'NEVER TOUCH AN', 'UNSHIELDED CRYSTAL']
    for i, s in enumerate(lines):
        if s: body.text((W / 2, 520 + i * 44), s, 'cond_bold', 34, 255, anchor='mm')
    foot = Canvas(W, H, mode='L'); _lambda_logo(foot, 70, 950, 38, 255, width=7)
    foot.text_fit((122, 925, W - 24, 975), 'LAMBDA DIRECTORATE', 'heavy', 255, anchor='lm')
    col = mix(col, solid((H, W), (236, 186, 30)), top.array())
    col = mix(col, solid((H, W), (24, 22, 20)), tt.array())
    col = mix(col, solid((H, W), (236, 186, 30)), pic.array())
    col = mix(col, solid((H, W), (30, 28, 26)), body.array())
    col = mix(col, solid((H, W), (230, 110, 20)), foot.array())
    # folds and age
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    fold = np.exp(-((yy - H / 2) / 2.0) ** 2) + np.exp(-((xx - W / 2) / 2.0) ** 2)
    col *= (1 - 0.12 * fold)[..., None]
    col = mix(col, col * np.array([0.9, 0.82, 0.62]), smooth(0.5, 0.9, noise((H, W), 2.4, 352)) * 0.5)
    save('poster_safety', col, -fold * 0.5 + n * 0.1, 30, nstrength=2.0)


@tex
def barrel_hazard():
    """barrel wrap (u around 0..1, v top->bottom): yellow paint, ribs, black trefoil on two sides"""
    W, H = 512, 512
    n = noise((H, W), 2.0, 361)
    col = solid((H, W), (226, 180, 30)) * (0.85 + 0.2 * n[..., None])
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    ribs = np.exp(-((yy - H / 3) / 5) ** 2) + np.exp(-((yy - 2 * H / 3) / 5) ** 2)
    ink = Canvas(W, H, mode='L')
    for u in (W * 0.25, W * 0.75):
        cx, cy = u, H * 0.5
        ink.circle((cx, cy), 14, 255)
        for k in range(3):
            a0 = 90 + k * 120
            ink.d.pieslice([(cx - 62) * 2, (cy - 62) * 2, (cx + 62) * 2, (cy + 62) * 2], -a0 - 30, -a0 + 30, fill=255)
        ink.circle((cx, cy), 20, 0); ink.circle((cx, cy), 13, 255)
        ink.text((cx, H * 0.24), 'HAZARDOUS', 'black', 30, 255, anchor='mm')
    ink.rect((0, 6, W, 22), 255); ink.rect((0, H - 22, W, H - 6), 255)
    col = mix(col, solid((H, W), (24, 22, 20)), ink.array() * 0.95)
    rust = smooth(0.6, 0.85, noise((H, W), 2.0, 362) * 0.6 + noise((H, W), 1.0, 363) * 0.4)
    col = mix(col, solid((H, W), (110, 60, 30)), rust * 0.8)
    col *= (1 - 0.3 * ribs)[..., None]
    save('barrel_hazard', col, ribs * 1.5 - rust * 0.4, 110 - 80 * rust, nstrength=3.0)


@tex
def barrel_toxic():
    W, H = 512, 512
    n = noise((H, W), 2.0, 371)
    col = solid((H, W), (70, 100, 60)) * (0.8 + 0.3 * n[..., None])
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    ribs = np.exp(-((yy - H / 3) / 5) ** 2) + np.exp(-((yy - 2 * H / 3) / 5) ** 2)
    ink = Canvas(W, H, mode='L')
    for u in (W * 0.25, W * 0.75):
        _biohazard(ink, u, H * 0.5, 70, 255, 0)
    col = mix(col, solid((H, W), (230, 200, 40)), ink.array())
    rust = smooth(0.55, 0.85, noise((H, W), 2.0, 372))
    col = mix(col, solid((H, W), (100, 56, 28)), rust * 0.85)
    # glowing drips from the top rim and from a puncture
    drip = smooth(0.62, 0.9, noise((H, W), 2.0, 373, aniso=(1.0, 14.0))) * smooth(H * 0.7, 0, yy)
    hole = np.exp(-(((xx - W * 0.5) / 6) ** 2 + ((yy - H * 0.38) / 6) ** 2))
    drip2 = np.exp(-((xx - W * 0.5) / 5) ** 2) * (yy > H * 0.38) * smooth(H * 0.9, H * 0.4, yy)
    g = np.clip(drip + drip2 + hole, 0, 1)
    col = mix(col, solid((H, W), (120, 255, 80)), g * 0.9)
    col *= (1 - 0.3 * ribs)[..., None]
    save('barrel_toxic', col, ribs * 1.5 - rust * 0.4 + g * 0.6, 80 + 150 * g, nstrength=3.0, glow=solid((H, W), (110, 255, 70)) * g[..., None])


@tex
def target():
    """practice target face (fit 0..1): rings on a scuffed metal plate"""
    S = 512
    col, h, _ = _plate(S, S, (190, 186, 176), 381)
    rc = Canvas(S, mode='RGB', bg=(0, 0, 0)); rm = Canvas(S, mode='L')
    for k, rr in enumerate(range(230, 20, -42)):
        rc.circle((S / 2, S / 2), rr, (190, 30, 24) if k % 2 == 0 else (235, 232, 222)); rm.circle((S / 2, S / 2), rr, 255)
    c3 = Canvas(S, mode='L'); c3.circle((S / 2, S / 2), 20, 255)
    r = rng(382)
    holes = Canvas(S, mode='L')
    for _ in range(25):
        a = r.uniform(0, 2 * np.pi); d = abs(r.normal(0, 90))
        holes.circle((S / 2 + d * np.cos(a), S / 2 + d * np.sin(a)), r.uniform(3, 7), 255)
    hm = holes.array()
    col = mix(col, np.asarray(rc.im.resize((S, S)), np.float64), rm.array())
    col = mix(col, solid(S, (30, 30, 30)), c3.array())
    col = mix(col, solid(S, (25, 22, 20)), hm)
    save('target', col, h - hm * 2, 70, nstrength=3.0)


@tex
def door_heavy():
    """blast door slab face (fit 0..1): heavy plates, centre seam, hazard chevrons along the bottom, warning text"""
    S = 1024
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    n = noise(S, 2.2, 391); b = noise(S, 1.2, 392, aniso=(1.0, 0.1))
    col = solid(S, (92, 100, 108)) * (0.85 + 0.2 * n[..., None]) * (0.92 + 0.12 * b[..., None])
    h = np.zeros((S, S))
    # raised border frame and horizontal ribs
    e = np.minimum.reduce([xx, yy, S - xx, S - yy])
    fr = smooth(48, 44, e)
    ribs = np.zeros((S, S))
    for ry in (S * 0.3, S * 0.55):
        ribs = np.maximum(ribs, smooth(22, 18, np.abs(yy - ry)) * (e > 40))
    h += fr * 2 + ribs * 1.5
    col = mix(col, col * 1.15, np.maximum(fr, ribs) * 0.6)
    col = mix(col, col * 0.5, np.clip(smooth(26, 18, np.abs(e - 46)) - fr, 0, 1) * 0.6)
    # centre vertical seam
    seam = np.exp(-((xx - S / 2) / 2.0) ** 2)
    col *= (1 - 0.6 * seam)[..., None]; h -= seam * 2
    # chevron band at the bottom
    band = (yy > S * 0.8) & (yy < S - 50) & (e > 46)
    s = ((xx + yy) % 128) / 128
    stripe = (s > 0.5).astype(float)
    hz = mix(solid(S, (232, 178, 24)), solid(S, (26, 24, 22)), stripe)
    wear = smooth(0.62, 0.72, noise(S, 1.8, 393))
    col = np.where(band[..., None], mix(hz, col, wear * 0.8), col)
    t = Canvas(S, mode='L')
    t.text_fit((150, S * 0.62, S - 150, S * 0.74), 'BLAST DOOR  ·  KEEP CLEAR', 'black', 255)
    t.text_fit((300, S * 0.36, S - 300, S * 0.48), 'SECTOR C', 'black', 255)
    col = mix(col, solid(S, (230, 226, 210)), t.array() * (1 - 0.6 * wear))
    # bolts along the frame
    bc = Canvas(S, mode='L')
    for k in np.linspace(60, S - 60, 14):
        for (x, y) in ((k, 24), (k, S - 24), (24, k), (S - 24, k)):
            bc.circle((x, y), 9, 255)
    bm = bc.array()
    col = mix(col, solid(S, (140, 146, 152)), bm); h += gblur(bm, 1) * 2
    grime = smooth(0.55, 0.85, noise(S, 2.5, 394)) * (0.4 + 0.6 * smooth(S * 0.5, S, yy))
    col = mix(col, col * 0.55, grime * 0.6)
    save('door_heavy', col, h, 100 - 50 * grime, nstrength=3.0)


if __name__ == '__main__':
    names = sys.argv[1:] or list(REG)
    for nm in names:
        REG[nm]()

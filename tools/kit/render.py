"""Textured software preview of NIF geometry as re-loaded by nifdump (so the preview shows what was saved).
Orthographic views, z-buffer, back-face culling (single-sided shapes vanish when the winding is wrong),
alpha test / blend / additive effects approximated, glow maps added on top. Collision hulls can be overlaid as wireframes.

    render.render_nif(nif_path, out_png, views=('front', 'iso', 'side', 'top'), size=360, show_collision=True)
"""
import os, numpy as np
from PIL import Image, ImageDraw
import nifread

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.normpath(os.path.join(HERE, '..', '..', 'build', 'kit_png'))
_cache = {}

VIEWS = {'front': (0, 0), 'iso': (35, 28), 'iso_back': (215, 28), 'side': (90, 0), 'top': (180, 89.9), 'low': (25, 8)}


def _tex(path):
    if not path: return None
    nm = os.path.splitext(path.replace('\\', '/').split('/')[-1])[0]
    if nm in _cache: return _cache[nm]
    f = os.path.join(PNG, nm + '.png')
    if not os.path.exists(f):
        # maybe a non-kit texture (props folder) -> look next to the dds
        _cache[nm] = None; return None
    a = np.asarray(Image.open(f).convert('RGBA'), np.float32) / 255.0
    _cache[nm] = a
    return a


def _camera(az, el):
    a, e = np.radians(az), np.radians(el)
    c = np.array([np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), np.sin(e)])  # az 0 -> camera at +Y
    right = np.cross([0, 0, 1.0], c); right /= np.linalg.norm(right)
    up = np.cross(c, right)
    return c, right, up


def render_shapes(shapes, az, el, size=360, cols=None, bounds=None, bg=(38, 40, 48)):
    c, right, up = _camera(az, el)
    allP = np.concatenate([s['P'] for s in shapes]) if bounds is None else bounds
    sx = allP @ right; sy = allP @ up
    lo = np.array([sx.min(), sy.min()]); hi = np.array([sx.max(), sy.max()])
    sc = (size - 24) / max((hi - lo).max(), 1e-6)
    off = np.array([size / 2, size / 2]) - (lo + hi) / 2 * sc
    img = np.zeros((size, size, 3), np.float32) + np.array(bg, np.float32) / 255
    zb = np.full((size, size), -np.inf, np.float32)
    L = np.array([0.45, 0.65, 0.62]); L /= np.linalg.norm(L)  # light from front-right-top (world)
    blend_jobs = []

    def proj(P):
        return np.stack([P @ right * sc + off[0], size - (P @ up * sc + off[1]), P @ c], 1)

    for s in shapes:
        rf = s.get('rflags', 0)
        tex = _tex(s.get('tex')); glow = _tex(s.get('glow')) if rf & 16 else None
        if rf & 2 or rf & 8:
            blend_jobs.append((s, tex, rf)); continue
        _raster(img, zb, s, proj(s['P']), tex, glow, rf, L, c, write_z=True, mode='opaque')
    # blended shapes back to front (by mean depth)
    blend_jobs.sort(key=lambda j: (j[0]['P'] @ c).mean())
    for s, tex, rf in blend_jobs:
        _raster(img, zb, s, proj(s['P']), tex, None, rf, L, c, write_z=False, mode='add' if (rf & 32) else 'blend')
    return np.clip(img * 255, 0, 255).astype(np.uint8), (right, up, sc, off, c)


def _raster(img, zb, s, Q, tex, glow, rf, L, cam, write_z, mode):
    size = img.shape[0]
    T, N, UV = s['T'], s['N'], s['UV']
    double = bool(rf & 4)
    for t in T:
        q = Q[t]
        x0, x1 = int(max(np.floor(q[:, 0].min()), 0)), int(min(np.ceil(q[:, 0].max()), size - 1))
        y0, y1 = int(max(np.floor(q[:, 1].min()), 0)), int(min(np.ceil(q[:, 1].max()), size - 1))
        if x1 < x0 or y1 < y0: continue
        # signed area in screen (y down): CCW in world-up screen space == negative here
        area = (q[1, 0] - q[0, 0]) * (q[2, 1] - q[0, 1]) - (q[2, 0] - q[0, 0]) * (q[1, 1] - q[0, 1])
        if abs(area) < 1e-9: continue
        front = area < 0
        if not front and not double: continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        w0 = ((q[1, 0] - xs) * (q[2, 1] - ys) - (q[2, 0] - xs) * (q[1, 1] - ys)) / area
        w1 = ((q[2, 0] - xs) * (q[0, 1] - ys) - (q[0, 0] - xs) * (q[2, 1] - ys)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not m.any(): continue
        z = w0 * q[0, 2] + w1 * q[1, 2] + w2 * q[2, 2]
        yy, xx = (ys[m] - 0.5).astype(int), (xs[m] - 0.5).astype(int)
        zz = z[m]
        vis = zz > zb[yy, xx] - 1e-3
        if not vis.any(): continue
        yy, xx, zz = yy[vis], xx[vis], zz[vis]
        W = np.stack([w0[m][vis], w1[m][vis], w2[m][vis]], 1)
        n = W @ N[t]; n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
        if not front: n = -n
        uv = W @ UV[t]
        if tex is not None:
            h, w = tex.shape[:2]
            px = (np.floor(uv[:, 0] * w).astype(int)) % w; py = (np.floor(uv[:, 1] * h).astype(int)) % h
            col = tex[py, px]
        else:
            col = np.tile([0.7, 0.7, 0.7, 1.0], (len(uv), 1)).astype(np.float32)
        if mode == 'opaque' and (rf & 1):
            keep = col[:, 3] > 0.5
            yy, xx, zz, n, col, uv = yy[keep], xx[keep], zz[keep], n[keep], col[keep], uv[keep]
            if not len(yy): continue
        shade = 0.38 + 0.62 * np.clip(n @ L, 0, 1) + 0.12 * np.clip(n @ cam, 0, 1)
        rgb = col[:, :3] * shade[:, None]
        if glow is not None:
            h, w = glow.shape[:2]
            px = (np.floor(uv[:, 0] * w).astype(int)) % w; py = (np.floor(uv[:, 1] * h).astype(int)) % h
            rgb = rgb + glow[py, px, :3] * 0.8
        if mode == 'opaque':
            img[yy, xx] = rgb; zb[yy, xx] = zz
        elif mode == 'add':
            fc = np.asarray(s.get('fxcolor', (1, 1, 1, 1)), np.float32)
            img[yy, xx] += col[:, :3] * col[:, 3:4] * fc[:3] * fc[3]
        else:
            a = (col[:, 3:4] if tex is not None else 0.4) * s.get('alpha', 1.0)
            if rf & 8:
                fc = np.asarray(s.get('fxcolor', (1, 1, 1, 1)), np.float32); rgb = col[:, :3] * fc[:3]; a = a * fc[3]
            img[yy, xx] = img[yy, xx] * (1 - a) + rgb * a


def _wire(im, cols, cam, bounds=None, color=(255, 80, 200)):
    from scipy.spatial import ConvexHull
    right, up, sc, off, c = cam
    d = ImageDraw.Draw(im); size = im.size[0]
    for col in cols:
        V = col['V']
        try:
            h = ConvexHull(V)
        except Exception:
            continue
        for simp in h.simplices:
            for a, b in ((0, 1), (1, 2), (2, 0)):
                p, q = V[simp[a]], V[simp[b]]
                d.line([(p @ right * sc + off[0], size - (p @ up * sc + off[1])), (q @ right * sc + off[0], size - (q @ up * sc + off[1]))], fill=color, width=1)


def render_nif(nif, out_png, views=('front', 'iso', 'side', 'top'), size=360, show_collision=False, title=None, tmp=None):
    tmp = tmp or out_png + '.bin'
    log, (shapes, cols) = nifread.load_nif(nif, tmp)
    os.unlink(tmp)
    bounds = np.concatenate([s['P'] for s in shapes] + [c['V'] for c in cols]) if shapes else None
    tiles = []
    for v in views:
        az, el = VIEWS[v] if isinstance(v, str) else v
        arr, cam = render_shapes(shapes, az, el, size, bounds=bounds)
        im = Image.fromarray(arr)
        if show_collision and cols: _wire(im, cols, cam)
        ImageDraw.Draw(im).text((4, 4), v if isinstance(v, str) else str(v), fill=(200, 200, 200))
        tiles.append(im)
    sheet = Image.new('RGB', (size * len(tiles), size + (16 if title else 0)), (20, 20, 24))
    for i, t in enumerate(tiles): sheet.paste(t, (i * size, 16 if title else 0))
    if title: ImageDraw.Draw(sheet).text((4, 2), title, fill=(255, 255, 255))
    sheet.save(out_png)
    return shapes, cols


if __name__ == '__main__':
    import sys
    render_nif(sys.argv[1], sys.argv[2], show_collision=len(sys.argv) > 3)

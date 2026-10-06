"""Small procedural texture toolkit: tileable noise, Worley cells, height->normal (DirectX / Y- convention as
Skyrim expects), supersampled PIL drawing, font lookup, DDS + PNG output."""
import os, sys, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import dds  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', '..', 'data', 'textures', 'StarfallSite', 'kit'))
PNG = os.path.normpath(os.path.join(HERE, '..', '..', 'build', 'kit_png'))

FONTS = {
    'sans': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    'sans_bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    'cond_bold': '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
    'cond': '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
    'oblique': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
    'cond_oblique': '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Oblique.ttf',
    'mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    'mono_bold': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
    'black': '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf',
    'heavy': '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf',
    'serif_italic': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf',
}


def font(kind, size):
    p = FONTS.get(kind)
    if p and os.path.exists(p): return ImageFont.truetype(p, int(size))
    return ImageFont.load_default(size=int(size))


def rng(seed): return np.random.default_rng(seed)


def _norm01(a):
    a = a - a.min(); m = a.max()
    return a / m if m > 0 else a


def noise(shape, beta=2.0, seed=0, aniso=(1.0, 1.0), fmin=0.0, fmax=None):
    """tileable 1/f^beta noise in 0..1. aniso=(sx, sy) stretches frequencies (sy>1 -> streaks along Y)."""
    if isinstance(shape, int): shape = (shape, shape)
    h, w = shape
    white = rng(seed).standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None] * aniso[1]; fx = np.fft.fftfreq(w)[None, :] * aniso[0]
    f = np.sqrt(fx ** 2 + fy ** 2); f[0, 0] = 1
    amp = 1.0 / f ** (beta / 2)
    if fmin: amp[f < fmin] = 0
    if fmax: amp[f > fmax] = 0
    s = np.fft.fft2(white) * amp; s[0, 0] = 0
    return _norm01(np.real(np.fft.ifft2(s)))


def worley(shape, n, seed=0, second=False):
    """tileable cellular noise: distance to nearest feature point (pixels), optionally F2 - F1 (cell edges)"""
    if isinstance(shape, int): shape = (shape, shape)
    h, w = shape
    pts = rng(seed).uniform(0, 1, (n, 2)) * [h, w]
    tree = cKDTree(pts, boxsize=[h, w])
    yy, xx = np.mgrid[0:h, 0:w]
    q = np.stack([yy.ravel() + 0.5, xx.ravel() + 0.5], 1) % [h, w]
    d, i = tree.query(q, k=2)
    f1 = d[:, 0].reshape(h, w); f2 = d[:, 1].reshape(h, w); idx = i[:, 0].reshape(h, w)
    return (f2 - f1, idx) if second else (f1, idx)


def blur(a, r):
    if r <= 0: return a
    # wrap-around box blur x3 (approx gaussian), tileable
    out = a.astype(np.float64)
    k = max(1, int(r))
    for _ in range(3):
        for ax in (0, 1):
            acc = np.zeros_like(out)
            for s in range(-k, k + 1): acc += np.roll(out, s, ax)
            out = acc / (2 * k + 1)
    return out


def gblur(a, r):
    """gaussian blur via FFT (tileable)"""
    h, w = a.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * r) ** 2 * (fx ** 2 + fy ** 2))
    if a.ndim == 2: return np.real(np.fft.ifft2(np.fft.fft2(a) * g))
    return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., c]) * g)) for c in range(a.shape[2])], -1)


def mix(a, b, t):
    t = np.asarray(t, np.float64)
    if t.ndim == 2: t = t[..., None]
    return np.asarray(a, np.float64) * (1 - t) + np.asarray(b, np.float64) * t


def solid(shape, color):
    if isinstance(shape, int): shape = (shape, shape)
    return np.ones(shape + (3,)) * np.asarray(color, np.float64)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def normal_from_height(h, strength=4.0):
    """height (any range) -> RGB normal map, DirectX convention (green = -dH/dv, rows go down), tileable"""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    n = np.stack([-dx * strength, -dy * strength, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.clip((n * 0.5 + 0.5) * 255, 0, 255)


class Canvas:
    """supersampled PIL drawing surface producing float arrays. mode 'L' (mask/height) or 'RGB'."""
    def __init__(self, w, h=None, mode='L', bg=0, ss=2):
        h = h or w; self.ss = ss; self.w, self.h = w, h
        self.im = Image.new(mode, (w * ss, h * ss), bg); self.d = ImageDraw.Draw(self.im)

    def S(self, v):
        if isinstance(v, (list, tuple)):
            return type(v)(self.S(x) for x in v)
        return v * self.ss

    def rect(self, box, fill, outline=None, width=0, radius=0):
        if radius: self.d.rounded_rectangle(self.S(list(box)), radius * self.ss, fill=fill, outline=outline, width=int(width * self.ss))
        else: self.d.rectangle(self.S(list(box)), fill=fill, outline=outline, width=int(width * self.ss))

    def ellipse(self, box, fill, outline=None, width=0):
        self.d.ellipse(self.S(list(box)), fill=fill, outline=outline, width=int(width * self.ss))

    def circle(self, c, r, fill, outline=None, width=0):
        self.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill, outline, width)

    def line(self, pts, fill, width=1):
        self.d.line([(x * self.ss, y * self.ss) for x, y in pts], fill=fill, width=max(1, int(width * self.ss)), joint='curve')

    def poly(self, pts, fill, outline=None):
        self.d.polygon([(x * self.ss, y * self.ss) for x, y in pts], fill=fill, outline=outline)

    def text(self, xy, s, kind, size, fill, anchor='la', spacing=0):
        f = font(kind, size * self.ss)
        if spacing:
            x, y = xy
            total = sum(f.getlength(ch) for ch in s) / self.ss + spacing * (len(s) - 1)
            if anchor[0] == 'm': x -= total / 2
            elif anchor[0] == 'r': x -= total
            for ch in s:
                self.d.text((x * self.ss, y * self.ss), ch, font=f, fill=fill, anchor='l' + anchor[1])
                x += f.getlength(ch) / self.ss + spacing
        else:
            self.d.text((xy[0] * self.ss, xy[1] * self.ss), s, font=f, fill=fill, anchor=anchor)

    def text_fit(self, box, s, kind, fill, anchor='mm', max_size=400):
        """largest font size fitting the box (x0, y0, x1, y1); draws centred"""
        x0, y0, x1, y1 = box
        lo, hi = 4, max_size
        while hi - lo > 1:
            mid = (lo + hi) // 2
            f = font(kind, mid * self.ss)
            bb = self.d.textbbox((0, 0), s, font=f, anchor='lt')
            if (bb[2] - bb[0]) / self.ss <= (x1 - x0) and (bb[3] - bb[1]) / self.ss <= (y1 - y0): lo = mid
            else: hi = mid
        x = x0 if anchor[0] == 'l' else x1 if anchor[0] == 'r' else (x0 + x1) / 2
        self.text((x, (y0 + y1) / 2), s, kind, lo, fill, anchor=anchor)
        return lo

    def array(self):
        im = self.im.resize((self.w, self.h), Image.LANCZOS)
        return np.asarray(im, np.float64) / 255.0


def paste_mask(base, mask, color):
    """composite colour over base using mask 0..1"""
    return mix(base, np.broadcast_to(np.asarray(color, np.float64), base.shape), mask)


def u8(a): return np.clip(np.round(a), 0, 255).astype(np.uint8)


def save(name, rgb, height=None, spec=None, nstrength=4.0, alpha=None, glow=None, normal=True, glow_name=None):
    """write <name>.dds (bc1, or bc3 when alpha), <name>_n.dds (bc3, alpha = specular), <name>_g.dds (bc1) and PNG previews.
    rgb: float 0..255 (H,W,3); height: any range; spec: 0..255 (scalar or HxW); alpha: 0..255; glow: 0..255 RGB."""
    os.makedirs(OUT, exist_ok=True); os.makedirs(PNG, exist_ok=True)
    h, w = rgb.shape[:2]
    if alpha is not None:
        rgba = np.dstack([u8(rgb), u8(np.broadcast_to(alpha, (h, w)))])
        dds.write(os.path.join(OUT, name + '.dds'), rgba, 'bc3')
    else:
        rgba = np.dstack([u8(rgb), np.full((h, w), 255, np.uint8)])
        dds.write(os.path.join(OUT, name + '.dds'), u8(rgb), 'bc1')
    Image.fromarray(rgba, 'RGBA').save(os.path.join(PNG, name + '.png'))
    if normal:
        hh = np.zeros((h, w)) if height is None else height
        n = normal_from_height(hh, nstrength)
        sp = np.broadcast_to(np.asarray(60.0 if spec is None else spec, np.float64), (h, w))
        nm = np.dstack([u8(n), u8(sp)])
        dds.write(os.path.join(OUT, name + '_n.dds'), nm, 'bc3')
        Image.fromarray(nm, 'RGBA').save(os.path.join(PNG, name + '_n.png'))
    if glow is not None:
        g = u8(glow if glow.ndim == 3 else np.dstack([glow] * 3))
        gn = glow_name or name + '_g'
        dds.write(os.path.join(OUT, gn + '.dds'), g, 'bc1')
        Image.fromarray(g, 'RGB').save(os.path.join(PNG, gn + '.png'))
    print('texture', name, rgb.shape[1], 'x', rgb.shape[0], '(alpha)' if alpha is not None else '', '(glow)' if glow is not None else '')

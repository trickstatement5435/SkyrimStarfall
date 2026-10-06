"""Quick orthographic previews (front/side/top) of a triangle mesh: preview.py in.npz out.png  or import render()."""
import numpy as np
from PIL import Image, ImageDraw
def render(P, T, out, views=((0,2),(1,2),(0,1)), size=360, colors=None, labels=None):
    imgs = []
    for (a, b) in views:
        im = Image.new('RGB', (size, size), (30, 30, 40)); d = ImageDraw.Draw(im)
        lo = P.min(0); hi = P.max(0); sc = (size - 20) / max(hi[a] - lo[a], hi[b] - lo[b], 1e-6)
        depth = [k for k in range(3) if k not in (a, b)][0]
        order = np.argsort(P[T].mean(1)[:, depth])
        for ti in order:
            t = T[ti]; q = P[t]
            n = np.cross(q[1] - q[0], q[2] - q[0]); nl = np.linalg.norm(n) + 1e-9
            shade = int(60 + 180 * abs(n[depth]) / nl)
            c = (shade, shade, shade) if colors is None else tuple(int(x * shade / 240) for x in colors[ti])
            d.polygon([(10 + (p[a] - lo[a]) * sc, size - 10 - (p[b] - lo[b]) * sc) for p in q], fill=c)
        imgs.append(im)
    s = Image.new('RGB', (size * len(imgs), size)); [s.paste(im, (i * size, 0)) for i, im in enumerate(imgs)]
    s.save(out)

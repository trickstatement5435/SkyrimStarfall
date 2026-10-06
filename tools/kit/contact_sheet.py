"""Contact sheet of every prop in the manifest (iso view, textures, no collision): python3 contact_sheet.py out.png [cols] [size]"""
import os, sys, json, numpy as np
from PIL import Image, ImageDraw
import render, nifread

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, '..', '..', 'data'))


def main(out, cols=8, size=240, view='iso'):
    man = json.load(open(os.path.join(DATA, 'meshes', 'StarfallSite', 'props', 'manifest.json')))
    names = list(man)
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * size, rows * (size + 14)), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    tmp = out + '.bin'
    for i, n in enumerate(names):
        nif = os.path.join(DATA, 'meshes', man[n]['nif'].replace('\\', '/'))
        _, (shapes, cols_) = nifread.load_nif(nif, tmp)
        az, el = render.VIEWS[view]
        arr, _ = render.render_shapes(shapes, az, el, size)
        x, y = (i % cols) * size, (i // cols) * (size + 14)
        sheet.paste(Image.fromarray(arr), (x, y + 14))
        d.text((x + 3, y + 1), n, fill=(230, 230, 230))
    os.unlink(tmp)
    sheet.save(out)


if __name__ == '__main__':
    main(sys.argv[1], *(int(a) for a in sys.argv[2:4]))

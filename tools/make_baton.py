"""Combine-style stun baton: one-handed mace, shaft along +Z, grip at the origin (same axis convention as the Energy Sword)."""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'kit'))
import nifkit, geom
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda n: nifkit.tex_path(n)
def zcyl(r, z0, z1, segs=12):
    return geom.cylinder(r, z1 - z0, segs=segs, z0=z0, uv_scale=16.0)
grip = geom.merge(*[zcyl(1.9 if i % 2 == 0 else 1.75, -10 + i * 2.2, -10 + (i + 1) * 2.2) for i in range(10)])
pommel = zcyl(2.3, -12.5, -10)
guard = zcyl(2.8, 12, 14.5, 16)
shaft = zcyl(1.25, 14.5, 52)
collar = zcyl(2.0, 50, 53, 16)
prongs = geom.merge(*[geom.box_c((np.cos(a) * 1.9, np.sin(a) * 1.9, 59), (0.9, 0.9, 12)) for a in np.radians([0, 90, 180, 270])])
cap = zcyl(2.2, 64.5, 66, 16)
coil = geom.merge(*[zcyl(1.55, 54 + k * 2.2, 55.2 + k * 2.2, 12) for k in range(5)])
spark = zcyl(1.0, 53, 66, 10)
shapes = [
    nifkit.shape('Grip', geom.merge(grip, pommel), [T('rubber'), T('rubber') .replace('.dds', '_n.dds')], spec=0.1, gloss=10),
    nifkit.shape('Metal', geom.merge(guard, shaft, collar, prongs, cap), [T('metal_dark'), T('metal_dark').replace('.dds', '_n.dds')], spec=0.9, gloss=60),
    nifkit.shape('Coil', coil, [T('lamp_glow'), T('lamp_glow').replace('.dds', '_n.dds'), T('lamp_glow').replace('.dds', '_g.dds')], spec=0.5, gloss=40,
                 flags={'glow': True, 'emissive_color': (0.35, 0.8, 1.0), 'emit_mult': 2.5}),
    nifkit.shape('Arc', spark, [T('halo')], effect={'source': T('halo'), 'color': (0.4, 0.85, 1.0, 1.0), 'scale': 2.0, 'additive': True, 'no_zwrite': True}),
]
col = [nifkit.box_col((-2.8, -2.8, -12.5), (2.8, 2.8, 66), 'metal')]
tmp = f'{ROOT}/build/stunbaton_static.nif'
r = nifkit.write_nif(tmp, shapes, col, material='metal')
os.system(f'{ROOT}/bin/item_fix {tmp} {ROOT}/data/meshes/StarfallSite/weapons/stunbaton.nif WeaponMace')
print('bounds', r['min'], r['max'])
import json; json.dump([*r['min'], *r['max']], open(f'{ROOT}/build/baton_bounds.json', 'w'))

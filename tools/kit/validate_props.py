"""Re-load every prop NIF with nifly (via bin/nifdump) and check it:
 - shapes / blocks present, BSFadeNode root, BSXFlags=2 + bhkCollisionObject/bhkRigidBody when collision is expected
 - triangle winding agrees with stored normals (CCW seen from outside) for every shape
 - < 65535 verts per shape, total tris < 6000
 - every referenced texture exists under data/textures
 - manifest bounds == bounds recomputed from the reloaded render + collision geometry
usage: python3 validate_props.py"""
import os, json, re, numpy as np, tempfile
import nifread

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, '..', '..', 'data'))
PROPS = os.path.join(DATA, 'meshes', 'StarfallSite', 'props')


def main():
    man = json.load(open(os.path.join(PROPS, 'manifest.json')))
    bad = 0
    tmp = os.path.join(tempfile.gettempdir(), 'sf_validate.bin')
    for name, e in man.items():
        nif = os.path.join(DATA, 'meshes', e['nif'].replace('\\', '/'))
        log, (shapes, cols) = nifread.load_nif(nif, tmp)
        issues = []
        if '[0] BSFadeNode' not in log: issues.append('root not BSFadeNode')
        if e['collision_pieces']:
            if 'BSX=2' not in log: issues.append('BSX!=2')
            if 'bhkCollisionObject' not in log or 'bhkRigidBody layer=1' not in log: issues.append('collision blocks missing')
            if 'motion=7 qual=1' not in log: issues.append('rigid body not fixed')
            if len(cols) != e['collision_pieces']: issues.append('convex count %d != %d' % (len(cols), e['collision_pieces']))
        elif e['kind'] != 'decal':
            issues.append('no collision')
        tris = sum(len(s['T']) for s in shapes)
        if tris >= 6000: issues.append('tris %d' % tris)
        for s in shapes:
            if len(s['P']) >= 65535: issues.append('%s verts' % s['name'])
            w = nifread.winding_agreement(s)
            if w < 0.999: issues.append('%s winding %.3f' % (s['name'], w))
        for t in set(re.findall(r'\[(textures\\[^\]]+)\]', log)) | {s['tex'] for s in shapes if s['tex']} | {s['glow'] for s in shapes if s['glow']}:
            if not os.path.exists(os.path.join(DATA, t.replace('\\', '/'))): issues.append('missing ' + t)
        pts = np.concatenate([s['P'] for s in shapes] + [c['V'] for c in cols])
        mn = [int(np.floor(v + 1e-3)) for v in pts.min(0)]; mx = [int(np.ceil(v - 1e-3)) for v in pts.max(0)]
        if any(abs(a - b) > 1 for a, b in zip(mn + mx, e['bounds'])): issues.append('bounds %s != manifest %s' % (mn + mx, e['bounds']))
        status = 'OK ' if not issues else 'BAD'
        bad += bool(issues)
        print('%s %-24s shapes=%2d tris=%5d convex=%2d %s' % (status, name, len(shapes), tris, len(cols), '; '.join(issues)))
    print('%d props, %d with issues' % (len(man), bad))
    return bad


if __name__ == '__main__':
    raise SystemExit(1 if main() else 0)

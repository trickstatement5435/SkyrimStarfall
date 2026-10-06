"""Grid-based building generator for interior cells.

Rooms are axis-aligned rectangles on a 64-unit grid separated by 64-unit wall strips. Doorways and windows are rectangles
cut into those strips. From that we build: per-room floor/ceiling slabs, merged wall boxes (render + collision),
lintels over doorways, window sills/headers + glass, and a navmesh over the walkable cells."""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'kit'))
import nifkit, geom
G = 64
T = lambda n: nifkit.tex_path(n)
TN = lambda n: nifkit.tex_path(n).replace('.dds', '_n.dds')

class Building:
    def __init__(self, name):
        self.name, self.rooms, self.doors, self.windows, self.blockers = name, [], [], [], []
    def room(self, key, x0, y0, x1, y1, h=300, floor='floor_tile', wall='concrete', ceil='concrete_dark', z=0):
        self.rooms.append(dict(key=key, rect=(x0, y0, x1, y1), h=h, floor=floor, wall=wall, ceil=ceil, z=z)); return self
    def door(self, x0, y0, x1, y1, h=240, walk=True):
        self.doors.append(dict(rect=(x0, y0, x1, y1), h=h, walk=walk)); return self
    def window(self, x0, y0, x1, y1, z0=110, z1=230):
        self.windows.append(dict(rect=(x0, y0, x1, y1), z0=z0, z1=z1)); return self
    def block(self, x0, y0, x1, y1):
        """navmesh cut-out (prop footprints)"""
        self.blockers.append((x0, y0, x1, y1)); return self
    # ---------- grid ----------
    def _grid(self):
        xs = [r['rect'][0] for r in self.rooms] + [r['rect'][2] for r in self.rooms]
        ys = [r['rect'][1] for r in self.rooms] + [r['rect'][3] for r in self.rooms]
        self.ox, self.oy = min(xs) - 2 * G, min(ys) - 2 * G
        self.nx, self.ny = (max(xs) - self.ox) // G + 2, (max(ys) - self.oy) // G + 2
        room_id = -np.ones((self.nx, self.ny), int)
        for i, r in enumerate(self.rooms):
            x0, y0, x1, y1 = r['rect']
            room_id[(x0 - self.ox) // G:(x1 - self.ox) // G, (y0 - self.oy) // G:(y1 - self.oy) // G] = i
        door = np.zeros((self.nx, self.ny), bool); win = np.zeros((self.nx, self.ny), int) - 1
        for d in self.doors:
            x0, y0, x1, y1 = d['rect']; door[(x0 - self.ox) // G:(x1 - self.ox) // G, (y0 - self.oy) // G:(y1 - self.oy) // G] = True
        for k, w in enumerate(self.windows):
            x0, y0, x1, y1 = w['rect']; win[(x0 - self.ox) // G:(x1 - self.ox) // G, (y0 - self.oy) // G:(y1 - self.oy) // G] = k
        self.room_id, self.doorm, self.win = room_id, door, win
        # wall cells: non-room cells touching a room cell (8-neighbourhood)
        inside = room_id >= 0
        near = np.zeros_like(inside)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near |= np.roll(np.roll(inside, dx, 0), dy, 1)
        self.wall = near & ~inside
        # height of each wall cell = tallest adjacent room
        hgt = np.zeros((self.nx, self.ny))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                rid = np.roll(np.roll(room_id, dx, 0), dy, 1)
                hh = np.where(rid >= 0, np.array([r['h'] for r in self.rooms] + [0])[rid], 0)
                hgt = np.maximum(hgt, hh)
        self.wall_h = hgt
    def cell_xy(self, i, j): return self.ox + i * G, self.oy + j * G
    @staticmethod
    def _merge(mask, val=None):
        """greedy rectangles over a boolean grid (optionally only merging equal values)"""
        m = mask.copy(); out = []
        nx, ny = m.shape
        for j in range(ny):
            i = 0
            while i < nx:
                if not m[i, j]: i += 1; continue
                v = None if val is None else val[i, j]
                i1 = i
                while i1 < nx and m[i1, j] and (val is None or val[i1, j] == v): i1 += 1
                j1 = j + 1
                while j1 < ny and all(m[k, j1] and (val is None or val[k, j1] == v) for k in range(i, i1)): j1 += 1
                m[i:i1, j:j1] = False
                out.append((i, j, i1, j1, v))
                i = i1
        return out
    # ---------- geometry ----------
    def build(self, outdir, prefix):
        """write one nif per room (its floor, ceiling and the walls nearest to it); returns [(nif rel path, bounds)]"""
        self._grid()
        pieces = {i: dict(meshes={}, col=[]) for i in range(len(self.rooms))}
        def owner(cx, cy):
            best, bd = 0, 1e18
            for i, r in enumerate(self.rooms):
                x0, y0, x1, y1 = r['rect']
                dx = max(x0 - cx, 0, cx - x1); dy = max(y0 - cy, 0, cy - y1); d = dx * dx + dy * dy
                if d < bd: bd, best = d, i
            return best
        def add(i, tex, mesh, col=None, mat='stone'):
            pieces[i]['meshes'].setdefault(tex, []).append(mesh)
            if col is not None: pieces[i]['col'].append(nifkit.box_col(*col, material=mat))
        for i, r in enumerate(self.rooms):
            x0, y0, x1, y1 = r['rect']; z = r['z']
            add(i, r['floor'], geom.box((x0, y0, z - 16), (x1, y1, z), uv_scale=128.0), ((x0, y0, z - 16), (x1, y1, z)))
            add(i, r['ceil'], geom.box((x0 - G, y0 - G, z + r['h']), (x1 + G, y1 + G, z + r['h'] + 16), uv_scale=256.0),
                ((x0 - G, y0 - G, z + r['h']), (x1 + G, y1 + G, z + r['h'] + 16)))
            # baseboard trim around the room (hazard band at the bottom of the walls)
        solid = self.wall & ~self.doorm & (self.win < 0)
        hq = (self.wall_h / 4).astype(int)
        for (i0, j0, i1, j1, hv) in self._merge(solid, hq):
            x0, y0 = self.cell_xy(i0, j0); x1, y1 = self.cell_xy(i1, j1); h = hv * 4
            o = owner((x0 + x1) / 2, (y0 + y1) / 2); r = self.rooms[o]
            add(o, r['wall'], geom.box((x0, y0, -16), (x1, y1, h), uv_scale=256.0), ((x0, y0, -16), (x1, y1, h)))
            add(o, 'hazard_stripes', geom.box((x0 - 1, y0 - 1, 0), (x1 + 1, y1 + 1, 14), uv_scale=64.0))
        for d in self.doors:
            x0, y0, x1, y1 = d['rect']
            # lintel up to the tallest neighbouring ceiling
            i0, j0 = (x0 - self.ox) // G, (y0 - self.oy) // G
            top = self.wall_h[i0, j0] or 300
            o = owner((x0 + x1) / 2, (y0 + y1) / 2)
            add(o, self.rooms[o]['wall'], geom.box((x0, y0, d['h']), (x1, y1, top), uv_scale=256.0), ((x0, y0, d['h']), (x1, y1, top)))
            add(o, 'metal_dark', geom.box((x0 - 8, y0 - 8, d['h'] - 8), (x1 + 8, y1 + 8, d['h'] + 8), uv_scale=64.0))   # frame header
            add(o, 'floor_tile', geom.box((x0, y0, -16), (x1, y1, 0), uv_scale=128.0), ((x0, y0, -16), (x1, y1, 0)))
            if not d['walk']:
                add(o, 'door_heavy', geom.box((x0 + 4, y0 + 4, 0), (x1 - 4, y1 - 4, d['h']), uv_scale=256.0), ((x0, y0, 0), (x1, y1, d['h'])), 'metal_heavy')
        for w in self.windows:
            x0, y0, x1, y1 = w['rect']
            i0, j0 = (x0 - self.ox) // G, (y0 - self.oy) // G
            top = self.wall_h[i0, j0] or 300
            o = owner((x0 + x1) / 2, (y0 + y1) / 2); r = self.rooms[o]
            add(o, r['wall'], geom.box((x0, y0, -16), (x1, y1, w['z0']), uv_scale=256.0), ((x0, y0, -16), (x1, y1, w['z0'])))
            add(o, r['wall'], geom.box((x0, y0, w['z1']), (x1, y1, top), uv_scale=256.0), ((x0, y0, w['z1']), (x1, y1, top)))
            cx0, cy0, cx1, cy1 = x0 + 28, y0 + 28, x1 - 28, y1 - 28
            if x1 - x0 > y1 - y0: cx0, cx1 = x0, x1
            else: cy0, cy1 = y0, y1
            add(o, '__glass', geom.box((cx0, cy0, w['z0']), (cx1, cy1, w['z1']), uv_scale=128.0), ((cx0, cy0, w['z0']), (cx1, cy1, w['z1'])), 'glass')
        out = []
        for i, pc in pieces.items():
            shapes = []
            for tex, ms in pc['meshes'].items():
                m = geom.merge(*ms)
                if tex == '__glass':
                    shapes.append(nifkit.shape('Glass', m, [T('glass'), TN('glass')], spec=1.5, gloss=120, flags={'alpha_blend': True, 'double_sided': True, 'no_zwrite': True, 'no_shadows': True}))
                else:
                    shapes.append(nifkit.shape(tex, m, [T(tex), TN(tex)], spec=0.3, gloss=20))
            key = self.rooms[i]['key']
            rel = f'StarfallSite\\kit\\{prefix}_{key}.nif'
            # collision: split into chunks of <= 48 pieces (one nif per chunk keeps list shapes small)
            cols = pc['col']; chunks = [cols[k:k + 48] for k in range(0, len(cols), 48)] or [[]]
            r = nifkit.write_nif(os.path.join(outdir, f'{prefix}_{key}.nif'), shapes, chunks[0], material='stone')
            out.append((rel, [*r['min'], *r['max']]))
            for ci, ch in enumerate(chunks[1:], 1):
                rr = nifkit.write_nif(os.path.join(outdir, f'{prefix}_{key}_col{ci}.nif'), [], ch, material='stone')
                out.append((f'StarfallSite\\kit\\{prefix}_{key}_col{ci}.nif', [*rr['min'], *rr['max']]))
        return out
    # ---------- navmesh ----------
    def navmesh(self, margin=24):
        """walkable cells -> vertices/triangles with adjacency (uniform grid, 2 tris per cell)"""
        walk = (self.room_id >= 0) | (self.doorm & np.array([[any(d['walk'] and d['rect'][0] <= self.cell_xy(i, j)[0] < d['rect'][2] and d['rect'][1] <= self.cell_xy(i, j)[1] < d['rect'][3] for d in self.doors) for j in range(self.ny)] for i in range(self.nx)]))
        for (bx0, by0, bx1, by1) in self.blockers:
            i0, j0 = int(np.floor((bx0 - margin - self.ox) / G)), int(np.floor((by0 - margin - self.oy) / G))
            i1, j1 = int(np.ceil((bx1 + margin - self.ox) / G)), int(np.ceil((by1 + margin - self.oy) / G))
            walk[max(i0, 0):i1, max(j0, 0):j1] = False
        zgrid = np.zeros((self.nx, self.ny))
        for i, r in enumerate(self.rooms): zgrid[self.room_id == i] = r['z']
        walk = prune(walk)
        return grid_navmesh(walk, lambda i, j: (self.ox + i * G, self.oy + j * G), lambda i, j: zgrid[min(i, self.nx - 1), min(j, self.ny - 1)])

def prune(walk, min_cells=12):
    """drop tiny disconnected walkable islands (slivers between props and walls)"""
    from scipy.ndimage import label
    lab, n = label(walk)
    out = walk.copy()
    for k in range(1, n + 1):
        if (lab == k).sum() < min_cells: out[lab == k] = False
    return out

def grid_navmesh(walk, xy, zf):
    """walk: bool grid of cells; returns verts (N,3), tris [(a,b,c)], edges [(e01,e12,e20)] with -1 for open edges.
    Each cell = 2 triangles: (v00, v10, v11) and (v00, v11, v01)  (counter-clockwise seen from above)."""
    nx, ny = walk.shape
    vid = {}; verts = []
    def V(i, j):
        if (i, j) not in vid:
            x, y = xy(i, j); vid[(i, j)] = len(verts); verts.append((x, y, zf(i, j)))
        return vid[(i, j)]
    tri_of = {}; tris = []
    for i in range(nx):
        for j in range(ny):
            if not walk[i, j]: continue
            a, b, c, d = V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)
            tri_of[(i, j, 0)] = len(tris); tris.append((a, b, c))
            tri_of[(i, j, 1)] = len(tris); tris.append((a, c, d))
    edges = []
    for i in range(nx):
        for j in range(ny):
            if not walk[i, j]: continue
            # tri0 (a,b,c): edge a-b = south (cell j-1 tri1? no: south neighbour's top edge belongs to its tri1 (c,d)), b-c = east, c-a = diagonal
            s = tri_of.get((i, j - 1, 1), -1); e = tri_of.get((i + 1, j, 1), -1)
            edges.append((s, e, tri_of[(i, j, 1)]))
            # tri1 (a,c,d): a-c diagonal, c-d = north (north neighbour tri0 edge a-b), d-a = west (west neighbour tri0 edge b-c)
            n_ = tri_of.get((i, j + 1, 0), -1); w = tri_of.get((i - 1, j, 0), -1)
            edges.append((tri_of[(i, j, 0)], n_, w))
    return np.array(verts, float), tris, edges

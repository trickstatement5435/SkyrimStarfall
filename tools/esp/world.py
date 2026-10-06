"""Cells, worldspaces, references, landscape, navmesh, quests and dialogue."""
import struct, math, numpy as np
from .core import Record, sub, zstr, u8, u16, i16, u32, i32, f32, fid
from .records import obnd, keywords

# ---------------- conditions ----------------
OPS = {'==': 0x00, '!=': 0x20, '>': 0x40, '>=': 0x60, '<': 0x80, '<=': 0xA0}
FUNC = {'GetIsID': 72, 'GetStage': 58, 'GetStageDone': 59, 'GetItemCount': 47, 'GetIsVoiceType': 426, 'GetRandomPercent': 77,
        'GetCurrentTime': 18, 'GetInFaction': 71, 'IsInCombat': 289, 'GetDead': 46, 'HasKeyword': 560, 'GetInCell': 67,
        'GetGlobalValue': 74, 'GetIsRace': 69}
RUN = {'subject': 0, 'target': 1, 'reference': 2}
def ctda(func, op, value, p1=0, p2=0, run='subject', ref=0, OR=False):
    t = OPS[op] | (0x01 if OR else 0)
    return sub('CTDA', struct.pack('<B3sfH2sIIIIi', t, b'\0\0\0', float(value), FUNC[func], b'\0\0', p1, p2, RUN[run], ref, -1))

# ---------------- references ----------------
def rot_rad(deg):
    """Skyrim heading: degrees clockwise from north -> radians stored in DATA"""
    return math.radians(deg % 360.0)

def refr(base, pos, rot_deg=0.0, scale=None, persistent=False, disabled=False, extra=(), flags=0, edid=None):
    subs = [sub('NAME', fid(base))]
    if scale is not None and abs(scale - 1.0) > 1e-4: subs.append(sub('XSCL', f32(scale)))
    subs += list(extra)
    subs.append(sub('DATA', struct.pack('<6f', pos[0], pos[1], pos[2], 0.0, 0.0, rot_rad(rot_deg))))
    if edid: subs.insert(0, sub('EDID', edid))
    fl = flags | (0x400 if persistent else 0) | (0x800 if disabled else 0)
    return subs, fl

def x_teleport(door_ref, pos, rot_deg):
    return sub('XTEL', fid(door_ref) + struct.pack('<6f', pos[0], pos[1], pos[2], 0.0, 0.0, rot_rad(rot_deg)) + u32(0))

def x_lock(level=255, key=0):
    return sub('XLOC', struct.pack('<B3sIB3s8s', level, b'\0\0\0', key, 0, b'\0\0\0', b'\0' * 8))

def x_linked(ref, kw=0):
    return sub('XLKR', fid(kw) + fid(ref))

def x_owner(owner):
    return sub('XOWN', fid(owner))

def x_light_radius(r):
    return sub('XRDS', f32(r))

def x_mapmarker(name, mtype=0, visible=True, can_travel=True):
    return [sub('XMRK', b''), sub('FNAM', u8((1 if visible else 0) | (2 if can_travel else 0))), sub('FULL', name), sub('TNAM', struct.pack('<BB', mtype, 0))]

def x_enable_parent(ref, opposite=False):
    return sub('XESP', fid(ref) + u8(1 if opposite else 0) + b'\0\0\0')

# ---------------- cells ----------------
def xcll(ambient, directional, fog_near_col, fog_near=0.0, fog_far=6000.0, fog_far_col=None, fog_max=1.0, fade_begin=4000.0, fade_end=6000.0, dir_rot=(0, 0), inherit=0):
    fog_far_col = fog_far_col or fog_near_col
    amb6 = struct.pack('<4B', *ambient, 0) * 6 + struct.pack('<4B', 255, 255, 255, 0) + f32(1.0)   # directional ambient x6 + specular + fresnel
    data = (struct.pack('<4B', *ambient, 0) + struct.pack('<4B', *directional, 0) + struct.pack('<4B', *fog_near_col, 0) +
            struct.pack('<ffiifff', fog_near, fog_far, dir_rot[0], dir_rot[1], 1.0, 10000.0, 1.0) + amb6 +
            struct.pack('<4B', *fog_far_col, 0) + struct.pack('<fffI', fog_max, fade_begin, fade_end, inherit))
    return sub('XCLL', data)

def interior_cell(p, edid, name, *, lighting=None, ltmp=0, aspc=0, music=0, imgs=0, location=0, ezn=0, owner=0, flags=0x1):
    subs = [sub('FULL', name), sub('DATA', u16(flags))]
    if lighting is not None: subs.append(lighting)
    subs.append(sub('LTMP', fid(ltmp)))
    if location: subs.append(sub('XLCN', fid(location)))
    if owner: subs.append(sub('XOWN', fid(owner)))
    if aspc: subs.append(sub('XCAS', fid(aspc)))
    if ezn: subs.append(sub('XEZN', fid(ezn)))
    if music: subs.append(sub('XCMO', fid(music)))
    if imgs: subs.append(sub('XCIM', fid(imgs)))
    fid_ = p.new_id(); p.edids[edid] = fid_
    rec = Record('CELL', fid_, [sub('EDID', edid)] + subs)
    p.interiors[fid_] = dict(record=rec, pers=[], temp=[])
    return fid_

def place(p, cell_fid, base, pos, rot=0.0, *, world=None, persistent=False, actor=False, edid=None, **kw):
    subs, fl = refr(base, pos, rot, persistent=persistent, edid=edid, **kw)
    rid = p.new_id()
    if edid: p.edids[edid] = rid
    rec = Record('ACHR' if actor else 'REFR', rid, subs, fl)
    if world is None:
        c = p.interiors[cell_fid]
    else:
        w = p.worlds[world]
        if cell_fid == 'persistent': c = w['pcell']
        elif isinstance(cell_fid, tuple): c = w['cells'][cell_fid]
        else: c = next(v for v in w['cells'].values() if v['record'].formid == cell_fid)
    (c['pers'] if persistent else c['temp']).append(rec)
    return rid

def add_record_to_cell(p, cell_fid, rec, world=None, persistent=False):
    c = p.interiors[cell_fid] if world is None else (p.worlds[world]['pcell'] if cell_fid == 'persistent' else p.worlds[world]['cells'][cell_fid])
    (c['pers'] if persistent else c['temp']).append(rec)

# ---------------- worldspace ----------------
def worldspace(p, edid, name, cells_min, cells_max, *, climate, water, music=0, location=0, ezn=0, ltmp=0, flags=0x1 | 0x8,
               default_land=-2048.0, water_height=-30000.0, parent=None):
    wf = p.new_id(); p.edids[edid] = wf
    subs = [sub('EDID', edid), sub('FULL', name)]
    if location: subs.append(sub('XLCN', fid(location)))
    if ezn: subs.append(sub('XEZN', fid(ezn)))
    if ltmp: subs.append(sub('LTMP', fid(ltmp)))
    subs += [sub('CNAM', fid(climate)), sub('NAM2', fid(water)), sub('NAM3', fid(water)), sub('NAM4', f32(water_height)),
             sub('DNAM', struct.pack('<ff', default_land, water_height)),
             sub('MNAM', struct.pack('<iihhhhfff', 512, 512, cells_min[0], cells_max[1], cells_max[0], cells_min[1], 50000.0, 80000.0, 50.0)),
             sub('ONAM', struct.pack('<ffff', 1.0, 0.0, 0.0, 0.0)), sub('NAMA', f32(1.0)), sub('DATA', u8(flags)),
             sub('NAM0', struct.pack('<ff', cells_min[0] * 4096.0, cells_min[1] * 4096.0)),
             sub('NAM9', struct.pack('<ff', (cells_max[0] + 1) * 4096.0, (cells_max[1] + 1) * 4096.0))]
    if music: subs.append(sub('ZNAM', fid(music)))
    rec = Record('WRLD', wf, subs)
    pc_fid = p.new_id()
    pcell = Record('CELL', pc_fid, [sub('DATA', u16(0x0))], flags=0x400)
    p.worlds[wf] = dict(record=rec, pcell=dict(record=pcell, pers=[], temp=[]), cells={})
    return wf

def ext_cell(p, world, x, y, *, name=None, location=0, ezn=0, music=0, water=False, edid=None):
    cf = p.new_id()
    subs = []
    if edid: subs.append(sub('EDID', edid)); p.edids[edid] = cf
    if name: subs.append(sub('FULL', name))
    subs += [sub('DATA', u16(0x2 if water else 0x0)), sub('XCLC', struct.pack('<iiB3s', x, y, 0, b'\0\0\0'))]
    subs.append(sub('LTMP', fid(0)))
    if location: subs.append(sub('XLCN', fid(location)))
    if ezn: subs.append(sub('XEZN', fid(ezn)))
    if music: subs.append(sub('XCMO', fid(music)))
    p.worlds[world]['cells'][(x, y)] = dict(record=Record('CELL', cf, subs), pers=[], temp=[])
    return cf

def override_world_persistent_cell(p, world_fid, pcell_fid, refs):
    """inject persistent refs into a master worldspace's persistent cell (e.g. Tamriel 0x3C / 0xD74)"""
    if world_fid not in p.worlds:
        # Partial Form (flag bit 14) overrides: only the data present is applied, the master's record stays intact.
        wrec = Record('WRLD', world_fid, [sub('EDID', 'Tamriel')], flags=0x4000)
        crec = Record('CELL', pcell_fid, [], flags=0x400 | 0x4000)
        p.worlds[world_fid] = dict(record=wrec, pcell=dict(record=crec, pers=[], temp=[]), cells={})
    return p.worlds[world_fid]['pcell']

# ---------------- landscape ----------------
def land_record(p, H, normals, layers, colors=None):
    """H: 33x33 heights (game units), rows = y (south->north), cols = x (west->east).
    layers: dict quadrant -> list of (ltex_fid, alpha 17x17 or None for base)"""
    Q = np.round(np.asarray(H) / 8.0).astype(int)
    off = Q[0, 0]
    d = np.zeros((33, 33), int)
    for r in range(33):
        d[r, 0] = Q[r, 0] - (Q[r - 1, 0] if r > 0 else off)
        for c in range(1, 33): d[r, c] = Q[r, c] - Q[r, c - 1]
    assert d.min() >= -128 and d.max() <= 127, ('slope too steep for VHGT', d.min(), d.max())
    vhgt = struct.pack('<f', float(off)) + d.astype(np.int8).tobytes() + b'\0\0\0'
    N = np.clip(np.round(np.asarray(normals) * 127), -127, 127).astype(np.int8)
    flags = 0x1 | 0x4 | (0x2 if colors is not None else 0)
    subs = [sub('DATA', u32(flags)), sub('VNML', N.tobytes()), sub('VHGT', vhgt)]
    if colors is not None: subs.append(sub('VCLR', np.asarray(colors, np.uint8).tobytes()))
    for quad in range(4):
        ql = layers.get(quad, [])
        if not ql: continue
        base = ql[0][0]
        subs.append(sub('BTXT', fid(base) + struct.pack('<BBh', quad, 0, -1)))
        for li, (tex, alpha) in enumerate(ql[1:]):
            pts = [(i, float(a)) for i, a in enumerate(np.asarray(alpha).ravel()) if a > 0.004]
            if not pts: continue
            subs.append(sub('ATXT', fid(tex) + struct.pack('<BBh', quad, 0, li)))
            subs.append(sub('VTXT', b''.join(struct.pack('<H2sf', i, b'\0\0', a) for i, a in pts)))
    return Record('LAND', p.new_id(), subs)

# ---------------- navmesh ----------------
def navm_record(p, formid, verts, tris, edges, *, world=0, grid=None, cell=0, ext_links=None, door_links=None):
    """verts (N,3), tris [(a,b,c)], edges [(e0,e1,e2)] neighbour triangle or -1.
    ext_links: {(tri, edge_k): (navmesh_fid, tri)} cross-navmesh portal links."""
    ext_links = ext_links or {}
    V = np.asarray(verts, np.float32)
    link_list = []; link_index = {}
    for key, (nm, t) in sorted(ext_links.items()):
        link_index[key] = len(link_list); link_list.append((nm, t))
    tb = bytearray()
    for ti, (t, e) in enumerate(zip(tris, edges)):
        ev = list(e); fl = 0
        for k in range(3):
            if (ti, k) in link_index:
                ev[k] = link_index[(ti, k)]; fl |= (1 << k)
        tb += struct.pack('<HHHhhhHH', t[0], t[1], t[2], ev[0], ev[1], ev[2], fl, 0)
    out = bytearray(struct.pack('<II', 12, 0xA5E9A03C))
    if world: out += fid(world) + struct.pack('<hh', grid[1], grid[0])
    else: out += fid(0) + fid(cell)
    out += u32(len(V)) + V.tobytes()
    out += u32(len(tris)) + bytes(tb)
    out += u32(len(link_list)) + b''.join(struct.pack('<IIh', 0, nm, t) for nm, t in link_list)
    dl = sorted(door_links or [])
    out += u32(len(dl)) + b''.join(struct.pack('<hII', t, 0xE48B73F3, d) for t, d in dl)
    out += u32(0)   # cover triangles
    # navmesh grid
    mn, mx = V.min(0), V.max(0)
    ext = max(mx[0] - mn[0], mx[1] - mn[1], 1.0)
    div = int(min(12, max(1, math.ceil(ext / 512.0))))
    gx, gy = max((mx[0] - mn[0]) / div, 1.0), max((mx[1] - mn[1]) / div, 1.0)
    cells = [[] for _ in range(div * div)]
    for ti, t in enumerate(tris):
        P = V[list(t)]
        x0 = int(np.clip((P[:, 0].min() - mn[0]) // gx, 0, div - 1)); x1 = int(np.clip((P[:, 0].max() - mn[0]) // gx, 0, div - 1))
        y0 = int(np.clip((P[:, 1].min() - mn[1]) // gy, 0, div - 1)); y1 = int(np.clip((P[:, 1].max() - mn[1]) // gy, 0, div - 1))
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1): cells[yy * div + xx].append(ti)
    out += struct.pack('<Iff', div, gx, gy) + struct.pack('<6f', *mn, *mx)
    for c in cells: out += u32(len(c)) + b''.join(struct.pack('<h', t) for t in c)
    return Record('NAVM', formid, [sub('NVNM', bytes(out))])

# ---------------- quest / dialogue ----------------
def quest(p, edid, name, *, flags=0x1 | 0x10 | 0x100, priority=50, qtype=0, stages=(), objectives=(), aliases=(), dialogue_conditions=(), description=''):
    """stages: [(index, log_text or None, complete_quest)], objectives: [(index, text, [alias ids])], aliases: [raw subrecord lists]"""
    subs = []
    if name: subs.append(sub('FULL', name))
    subs.append(sub('DNAM', struct.pack('<HBB4sI', flags, priority, 0, b'\0' * 4, qtype)))
    for c in dialogue_conditions: subs.append(c)
    subs.append(sub('NEXT', b''))
    for idx, log, complete in stages:
        subs.append(sub('INDX', struct.pack('<HBB', idx, 0, 0)))
        if log is not None or complete:
            subs.append(sub('QSDT', u8(1 if complete else 0)))
            if log: subs.append(sub('CNAM', log))
    for idx, text, targets in objectives:
        subs += [sub('QOBJ', u16(idx)), sub('FNAM', u32(0)), sub('NNAM', text)]
        for a in targets: subs.append(sub('QSTA', struct.pack('<iB3s', a, 0, b'\0\0\0')))
    next_alias = 0
    alias_subs = []
    for a in aliases:
        alias_subs += a; next_alias += 1
    subs.append(sub('ANAM', u32(next_alias)))
    subs += alias_subs
    if description: subs.append(sub('NNAM', description))
    return p.add('QUST', subs, edid)

def ref_alias(alias_id, name, ref=None, unique_actor=None, flags=0x4):
    s = [sub('ALST', u32(alias_id)), sub('ALID', name), sub('FNAM', u32(flags))]
    if ref: s.append(sub('ALFR', fid(ref)))
    if unique_actor: s.append(sub('ALUA', fid(unique_actor)))
    s.append(sub('ALED', b''))
    return s

SUBTYPE = {  # name: (category, subtype index, SNAM 4cc)
    'Custom': (0, 0, 'CUST'), 'Hello': (7, 79, 'HELO'), 'Idle': (7, 94, 'IDLE'), 'GoodBye': (7, 78, 'GBYE'),
    'Attack': (3, 26, 'ATCK'), 'Hit': (3, 29, 'HIT_'), 'Flee': (3, 30, 'FLEE'), 'Death': (3, 33, 'DETH'),
    'AlertIdle': (5, 55, 'ALIL'), 'NormalToAlert': (5, 57, 'NOTA'), 'AlertToCombat': (5, 58, 'ALTC'), 'NormalToCombat': (5, 59, 'NOTC'),
    'CombatToNormal': (5, 61, 'COTN'), 'CombatToLost': (5, 62, 'COLO'), 'LostToCombat': (5, 64, 'LOTC'), 'DetectFriendDie': (5, 65, 'DFDA'),
    'Murder': (3, 43, 'MURD'), 'Scene': (2, 14, 'SCEN'),
}
def dial(p, edid, quest_fid, subtype='Custom', name='', priority=50.0, branch=0):
    cat, st, sn = SUBTYPE[subtype]
    subs = []
    if name: subs.append(sub('FULL', name))
    subs.append(sub('PNAM', f32(priority)))
    if branch: subs.append(sub('BNAM', fid(branch)))
    subs.append(sub('QNAM', fid(quest_fid)))
    subs.append(sub('DATA', struct.pack('<BBH', 0, cat, st)))
    subs.append(sub('SNAM', sn.encode()))
    df = p.new_id(); p.edids[edid] = df
    rec = Record('DIAL', df, [sub('EDID', edid)] + subs)
    p.topics[df] = dict(record=rec, infos=[], cat=cat)
    return df

EMO = {'Neutral': 0, 'Anger': 1, 'Disgust': 2, 'Fear': 3, 'Sad': 4, 'Happy': 5, 'Surprise': 6, 'Puzzled': 7}
def info(p, dial_fid, responses, *, conditions=(), prompt=None, flags=0, reset_hours=0.0, links=(), speaker=0, edid=None, prev=None):
    """responses: [(text, emotion)]. flags: 0x1 goodbye, 0x2 random, 0x4 say once, 0x20 random end, 0x40 invisible continue"""
    iff = p.new_id()
    if edid: p.edids[edid] = iff
    subs = [sub('EDID', edid)] if edid else []
    subs.append(sub('ENAM', struct.pack('<HH', flags, int(min(65535, reset_hours * 2730.625)))))
    subs.append(sub('PNAM', fid(prev or 0)))
    subs.append(sub('CNAM', u8(0)))
    for l in links: subs.append(sub('TCLT', fid(l)))
    for n, (text, emo) in enumerate(responses, 1):
        subs.append(sub('TRDT', struct.pack('<II4sB3sIB3s', EMO.get(emo, 0), 50, b'\0' * 4, n, b'\0\0\0', 0, 1, b'\0\0\0')))
        subs.append(sub('NAM1', text)); subs.append(sub('NAM2', '')); subs.append(sub('NAM3', ''))
    for c in conditions: subs.append(c)
    if prompt: subs.append(sub('RNAM', prompt))
    if speaker: subs.append(sub('ANAM', fid(speaker)))
    rec = Record('INFO', iff, subs)
    p.topics[dial_fid]['infos'].append(rec)
    return iff

def dlbr(p, edid, quest_fid, start_topic, top_level=True):
    return p.add('DLBR', [sub('QNAM', fid(quest_fid)), sub('TNAM', u32(0)), sub('DNAM', u32(1 if top_level else 0)), sub('SNAM', fid(start_topic))], edid)

"""StarfallSite.esp: crater worldspace, facility interiors, scientists, guards, dialogue, quest, notes, gate in Skyrim.
Masters: Skyrim.esm, GravityGun.esp, StarfallCreatures.esp.  Also writes SKSE/Plugins/StarfallSite/forms.json for the DLL,
the voice manifest (CSV) and a layout preview."""
import os, sys, json, math, struct, re
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from esp.core import Plugin, Record, sub, fid, u8, u16, u32, i32, f32
from esp import records as R
from esp import world as W
from vanilla import V
import site_interior as SI
import site_exterior as SE
from building import grid_navmesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = f'{ROOT}/data'
p = Plugin('StarfallSite.esp', ['Skyrim.esm', 'GravityGun.esp', 'StarfallCreatures.esp'],
           desc='Starfall Research Site: a Lambda Directorate research facility in a meteor crater near Riverwood.')
S = lambda typ, edid: p.sky(V(typ, edid))
GG = lambda local: p.m('GravityGun.esp', local)
CRE_IDS = {k: int(v, 16) for k, v in json.load(open(f'{ROOT}/build/creature_ids.json')).items()}
CR = lambda edid: p.m('StarfallCreatures.esp', CRE_IDS[edid])
GG_GUN, GG_CRYSTAL = GG(0x803), GG(0x806)
MANIFEST = json.load(open(f'{DATA}/meshes/StarfallSite/props/manifest.json'))
MISC_B = json.load(open(f'{ROOT}/build/misc_bounds.json'))
SRC_B = json.load(open(f'{ROOT}/build/src_props_bounds.json'))
DLG = json.load(open(f'{ROOT}/dialogue/dialogue.json'))
QT = json.load(open(f'{ROOT}/dialogue/quest_text.json'))
PLAYER = 0x14

# =====================================================================================================================
# 1. shared forms
# =====================================================================================================================
kw_site = R.kywd(p, 'SFKwSiteActor', (255, 140, 0))
fac_site = R.fact(p, 'SFSiteFaction', 'Lambda Directorate',
                  [(S('Faction', 'PlayerFaction'), 'friend'), (CR('SFCreatureFaction'), 'enemy')], hidden=False)
p.top['FACT'][-1].subs.insert(2, sub('XNAM', fid(fac_site) + i32(0) + u32(2)))   # allied with itself
VOICES = {k: R.vtyp(p, f'SFVoice{k}') for k in ['Kast', 'Hale', 'Rusk', 'Venn', 'Junior1', 'Junior2', 'Junior3', 'Moran', 'GuardA', 'GuardB']}

# ---- lights ----
LIGHTS = {
    'fluor': R.ligh(p, 'SFLightFluor', 620, (215, 232, 255)),
    'red': R.ligh(p, 'SFLightRedAlarm', 460, (255, 45, 30), flags=0x80),
    'green': R.ligh(p, 'SFLightTankGlow', 300, (90, 255, 130)),
    'cyan': R.ligh(p, 'SFLightCrystal', 760, (120, 215, 255), flags=0x100),
    'warm': R.ligh(p, 'SFLightDesk', 280, (255, 205, 150)),
    'flood': R.ligh(p, 'SFLightFlood', 1500, (255, 248, 230)),
}

# ---- statics for every prop / building piece ----
STATS = {}
def prop_stat(name):
    if name in STATS: return STATS[name]
    if name in MANIFEST:
        m = MANIFEST[name]; path = m['nif']; b = m['bounds']
    elif name in SRC_B:
        path, b = f'StarfallSite\\props\\{name}.nif', SRC_B[name]
    elif name in MISC_B:
        path, b = f'StarfallSite\\props\\{name}.nif', MISC_B[name]
    else:
        raise KeyError(name)
    STATS[name] = R.stat(p, f'SFP_{name}', path, b)
    return STATS[name]

def footprint(name, x, y, ang):
    m = MANIFEST.get(name)
    if m is None:
        b = SRC_B.get(name) or MISC_B.get(name); fp = [b[0], b[1], b[3], b[4]] if b else 0
        cut = None
    else:
        fp = m.get('footprint', 0); cut = m.get('cutouts')
    rects = cut if cut else ([fp] if fp else [])
    out = []
    a = math.radians(ang)
    for (x0, y0, x1, y1) in rects:
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        w = [(x + px * math.cos(a) + py * math.sin(a), y - px * math.sin(a) + py * math.cos(a)) for px, py in pts]
        xs, ys = [q[0] for q in w], [q[1] for q in w]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out

def rotxy(px, py, ang):
    a = math.radians(ang)
    return px * math.cos(a) + py * math.sin(a), -px * math.sin(a) + py * math.cos(a)

# ---- doors ----
door_b = MISC_B['door_slab']
D_FAC = R.door(p, 'SFDoorFacility', 'Starfall Research Site', 'StarfallSite\\props\\door_slab.nif', door_b, flags=0x8)
D_CRATER = R.door(p, 'SFDoorCrater', 'Starfall Crater', 'StarfallSite\\props\\door_slab.nif', door_b, flags=0x8)
D_WINGB = R.door(p, 'SFDoorWingB', 'Containment Wing B', 'StarfallSite\\props\\door_slab.nif', door_b, flags=0x8)
D_GATE = R.door(p, 'SFDoorGate', 'Directorate Checkpoint', 'StarfallSite\\props\\door_slab.nif', door_b, flags=0x8)
D_SKYRIM = R.door(p, 'SFDoorSkyrim', 'Skyrim', 'StarfallSite\\props\\door_slab.nif', door_b, flags=0x8)

# ---- items ----
quest_items = QT['items']
KEYCARD = R.keym(p, 'SFWingBKeycard', quest_items['keycard']['name'], 'StarfallSite\\props\\keycard.nif', MISC_B['keycard'], value=0, weight=0.1)
JOURNAL = R.book(p, 'SFRuskJournal', quest_items['journal']['name'], quest_items['journal']['text'], 'StarfallSite\\props\\journal.nif',
                 MISC_B['journal'], value=0, weight=0.5, note=False)
NOTES = {}
for n in QT['notes']:
    NOTES[n['id']] = R.book(p, 'SFNote_' + n['id'][5:], n['title'], n['text'], 'StarfallSite\\props\\note_paper.nif', MISC_B['note_paper'],
                            value=2, weight=0.1, note=True)

# ---- stun baton ----
baton_b = json.load(open(f'{ROOT}/build/baton_bounds.json'))
BATON = R.weap(p, 'SFStunBaton', 'Stun Baton', 'StarfallSite\\weapons\\stunbaton.nif', 9, speed=1.05, reach=0.95, anim=4,
               impact=S('ImpactDataSet', 'WPNzBluntImpactSet'), equip_type=S('EquipType', 'EitherHand'), nonplayable=False,
               value=180, weight=6.0, bounds=baton_b, crit_damage=4, stagger=0.4,
               kws=[S('Keyword', 'WeapTypeMace'), S('Keyword', 'VendorItemWeapon'), S('Keyword', 'WeapMaterialSteel')],
               sounds={'SNAM': S('SoundDescriptor', 'WPNSwingBlunt1Hand'), 'NAM9': S('SoundDescriptor', 'WPNMace1HandDrawSD'),
                       'NAM8': S('SoundDescriptor', 'WPNMace1HandSheatheSD')})
# enchant: vanilla shock damage (charge refills for NPCs automatically)
rec = p.top['WEAP'][-1]
idx = next(i for i, s_ in enumerate(rec.subs) if s_[:4] == b'ETYP')
rec.subs.insert(idx, sub('EITM', fid(S('ObjectEffect', 'EnchWeaponShockDamage02'))))
rec.subs.insert(idx + 1, sub('EAMT', u16(4000)))

# ---- armor ----
HUMAN_RACES = [S('Race', r) for r in ['NordRace', 'BretonRace', 'DarkElfRace', 'HighElfRace', 'ImperialRace', 'OrcRace', 'RedguardRace', 'WoodElfRace', 'ArgonianRace', 'KhajiitRace']]
IMPERIAL = S('Race', 'ImperialRace')
def armor_piece(edid, name, mesh, slots, armor_type=2, nonplayable=False, rating=0, value=0, weight=0.0, kws=()):
    mask = R.slots(*slots)
    a = R.arma(p, edid + 'AA', IMPERIAL, mask, mesh, extra_races=[r for r in HUMAN_RACES if r != IMPERIAL], weight_slider=True, armor_type=armor_type)
    return R.armo(p, edid, name, mask, [a], race=None, nonplayable=nonplayable, armor_type=armor_type, rating=rating, value=value,
                  weight=weight, kws=kws, bounds=(-30, -20, 0, 30, 20, 130))
LABCOAT = armor_piece('SFLabCoat', 'Lambda Lab Coat', 'StarfallSite\\scientists\\labcoat_1.nif', (32, 33, 37), kws=[S('Keyword', 'ArmorClothing'), S('Keyword', 'ClothingBody'), S('Keyword', 'VendorItemClothing')], value=40, weight=2.0)
HEADS = {h: armor_piece(f'SFHead_{h}', '', f'StarfallSite\\scientists\\head_{h}_1.nif', (30, 31, 41, 43), nonplayable=True)
         for h in ['einstein', 'luther', 'slick', 'walter']}
COMBINE = armor_piece('SFCombineArmor', 'Directorate Security Armor', 'StarfallSite\\guards\\combine_1.nif', (30, 31, 32, 33, 37, 41, 43),
                      armor_type=1, rating=48, value=900, weight=35.0, kws=[S('Keyword', 'ArmorHeavy'), S('Keyword', 'ArmorCuirass'), S('Keyword', 'VendorItemArmor')])
WARDEN = armor_piece('SFCombineWardenArmor', 'Directorate Warden Armor', 'StarfallSite\\guards\\combine_warden_1.nif', (30, 31, 32, 33, 37, 41, 43),
                     armor_type=1, rating=55, value=1400, weight=35.0, kws=[S('Keyword', 'ArmorHeavy'), S('Keyword', 'ArmorCuirass'), S('Keyword', 'VendorItemArmor')])
OUTFITS = {h: R.otft(p, f'SFOutfitScientist_{h}', [LABCOAT, HEADS[h]]) for h in HEADS}
OUT_GUARD = R.otft(p, 'SFOutfitGuard', [COMBINE])
OUT_WARDEN = R.otft(p, 'SFOutfitWarden', [WARDEN])

# ---- vendor (Hale sells crystals after stage 50) ----
vendor_chest_base = R.cont(p, 'SFVendorChest', 'Merchant Chest', 'StarfallSite\\props\\crate_large.nif', MANIFEST['crate_large']['bounds'],
                           items=[(GG_CRYSTAL, 12), (BATON, 2), (LABCOAT, 1)], respawn=True)
vendor_list = R.flst(p, 'SFVendorBuyList', [S('Keyword', 'VendorItemWeapon'), S('Keyword', 'VendorItemArmor')])

# =====================================================================================================================
# 2. interiors
# =====================================================================================================================
def build_interior(cell_edid, cell_name, bld, props_list, prefix, *, lighting):
    cf = W.interior_cell(p, cell_edid, cell_name, lighting=lighting, ltmp=S('LightingTemplate', 'DefaultLightingTemplate'),
                         aspc=S('AcousticSpace', 'IntDungeonDwemerLarge'), music=S('MusicType', 'MUSDungeonFort'),
                         imgs=S('ImageSpace', 'DefaultImageSpaceInterior'))
    pieces = bld.build(f'{DATA}/meshes/StarfallSite/kit', prefix)
    for rel, b in pieces:
        key = os.path.basename(rel)[:-4]
        sid = R.stat(p, f'SFK_{key}', rel, b)
        W.place(p, cf, sid, (0, 0, 0), 0)
    markers, spawns, items = {}, [], []
    for e in props_list:
        k = e[0]
        if k == 'prop':
            _, name, x, y, z, ang = e
            W.place(p, cf, prop_stat(name), (x, y, z), ang)
            if z < 5:
                for r in footprint(name, x, y, ang): bld.block(*r)
        elif k == 'vanilla':
            _, typ, edid, x, y, z, ang = e
            W.place(p, cf, S(typ, edid), (x, y, z), ang)
        elif k == 'light':
            _, kind, x, y, z = e
            if kind == 'fluor':
                W.place(p, cf, prop_stat('fluorescent_ceiling'), (x, y, z), 0)
                W.place(p, cf, LIGHTS['fluor'], (x, y, z - 40), 0)
            else:
                W.place(p, cf, LIGHTS[kind], (x, y, z), 0)
        elif k == 'marker':
            _, key, x, y, z, ang = e
            mid = W.place(p, cf, S('Static', 'XMarkerHeading'), (x, y, z), ang)
            markers.setdefault(key, []).append(mid)
        elif k == 'note':
            _, nid, x, y, z, ang = e
            W.place(p, cf, NOTES[nid], (x, y, z), ang)
        elif k == 'container':
            _, key, propname, x, y, z, ang, loot = e
            m = MANIFEST[propname]
            items_ = {'armory': [(BATON, 2), (COMBINE, 1), (S('LeveledItem', 'LItemPotionRestoreHealthBest'), 3)],
                      'supplies': [(S('LeveledItem', 'LItemPotionRestoreHealth'), 2), (S('MiscItem', 'Lockpick'), 3), (S('LeveledItem', 'LootDwarvenScrap10'), 1)]}[loot]
            cid = R.cont(p, f'SFCont_{key}', {'armory': 'Armory Locker', 'supplies': 'Supply Crate'}[loot], m['nif'], m['bounds'], items=items_)
            extra = [W.x_lock(255, 0)] if loot == 'armory' else []
            rid = W.place(p, cf, cid, (x, y, z), ang, extra=extra, persistent=(loot == 'armory'), edid=f'SFRef_{key}')
            markers[key] = [rid]
            for r in footprint(propname, x, y, ang): bld.block(*r)
        elif k == 'item':
            _, what, x, y, z, ang = e
            W.place(p, cf, {'journal': JOURNAL}[what], (x, y, z), ang, persistent=True, edid=f'SFRef_{what}')
        elif k == 'spawn':
            spawns.append((e[1], e[2]))
        elif k == 'vanilla_crab':
            pass
    # navmesh
    verts, tris, edges = bld.navmesh()
    PENDING_NAV.append(dict(fid=p.new_id(), verts=verts, tris=tris, edges=edges, cell=cf, world=None, grid=None, links={}, doors=[]))
    return cf, markers, spawns, bld

PENDING_NAV = []
L_FAC = W.xcll((48, 52, 60), (150, 160, 175), (20, 22, 26), fog_near=0, fog_far=9000, fade_begin=3500, fade_end=6000)
L_WINGB = W.xcll((26, 18, 18), (110, 70, 70), (16, 10, 10), fog_near=0, fog_far=5000, fade_begin=2500, fade_end=4500)
facility_bld = SI.main_complex()
CELL_FAC, M_FAC, _, _ = build_interior('SFFacilityInterior', 'Starfall Research Site', facility_bld, SI.main_props(), 'fac', lighting=L_FAC)
wingb_bld = SI.wing_b()
CELL_WINGB, M_WB, SPAWN_WB, _ = build_interior('SFWingBInterior', 'Containment Wing B', wingb_bld, SI.wingb_props(), 'wingb', lighting=L_WINGB)

# =====================================================================================================================
# 3. crater worldspace
# =====================================================================================================================
LTEX = [S('LandscapeTexture', n) for n in ['LDirtPath01', 'LVolcanicTundraDirt01NoGrass', 'LVolcanicTundraGravel01', 'LRocks01NoRocks', 'LTundra02', 'LSnowRocks01']]
WORLD = W.worldspace(p, 'SFCraterWorld', 'Starfall Crater', SE.CMIN, SE.CMAX, climate=S('Climate', 'SkyrimClimate'),
                     water=S('Water', 'DefaultWater'), music=S('MusicType', 'MUSExploreMountain'))
CELLS = {}
for cx in range(SE.CMIN[0], SE.CMAX[0] + 1):
    for cy in range(SE.CMIN[1], SE.CMAX[1] + 1):
        CELLS[(cx, cy)] = W.ext_cell(p, WORLD, cx, cy, name='Starfall Crater' if (cx, cy) == (0, 0) else None)
# landscape
for (cx, cy), cf in CELLS.items():
    xs = cx * 4096 + np.arange(33) * 128.0; ys = cy * 4096 + np.arange(33) * 128.0
    X, Y = np.meshgrid(xs, ys)               # rows = y, cols = x
    H = SE.height(X, Y)
    # normals from a slightly larger grid for continuity across cells
    xs2 = cx * 4096 + np.arange(-1, 34) * 128.0; ys2 = cy * 4096 + np.arange(-1, 34) * 128.0
    X2, Y2 = np.meshgrid(xs2, ys2); H2 = SE.height(X2, Y2)
    N = SE.normals(H2)[1:-1, 1:-1]
    Wt = SE.tex_weights(X, Y, H, N)
    shade = np.clip(255 - 90 * SE.smooth((2600 - np.hypot(X, Y)) / 800), 120, 255)
    colors = np.dstack([shade, shade * 0.97, shade * 0.94]).astype(np.uint8)
    layers = {}
    for q in range(4):
        r0, c0 = (q // 2) * 16, (q % 2) * 16
        wq = Wt[r0:r0 + 17, c0:c0 + 17]
        order = np.argsort(-wq.sum((0, 1)))
        base = order[0]
        ql = [(LTEX[base], None)]
        for t in order[1:]:
            if wq[..., t].max() > 0.02: ql.append((LTEX[t], np.clip(wq[..., t], 0, 1)))
        layers[q] = ql
    land = W.land_record(p, H, N, layers, colors)
    p.worlds[WORLD]['cells'][(cx, cy)]['temp'].insert(0, land)

def ground(x, y): return float(SE.height(x, y))
def cell_of(x, y): return (int(math.floor(x / 4096)), int(math.floor(y / 4096)))
def wplace(base, x, y, dz, ang, persistent=False, **kw):
    z = ground(x, y) + dz
    if persistent:
        return W.place(p, 'persistent', base, (x, y, z), ang, world=WORLD, persistent=True, **kw)
    return W.place(p, CELLS[cell_of(x, y)], base, (x, y, z), ang, world=WORLD, **kw)

EXT_BLOCK = []
M_EXT = {}; SPAWN_EXT = []; PATROL_EXT = {}
for e in SE.placements():
    k = e[0]
    if k == 'prop':
        _, name, x, y, dz, ang = e
        wplace(prop_stat(name), x, y, dz, ang)
        if dz < 5: EXT_BLOCK += footprint(name, x, y, ang)
    elif k == 'vanilla':
        _, typ, edid, x, y, dz, ang = e
        wplace(S(typ, edid), x, y, dz, ang)
        if typ == 'Static': EXT_BLOCK.append((x - 250, y - 250, x + 250, y + 250))
    elif k == 'light':
        _, kind, x, y, dz = e
        wplace(LIGHTS[kind], x, y, dz, 0)
    elif k == 'marker':
        _, key, x, y, dz, ang = e
        M_EXT.setdefault(key, []).append((x, y, ground(x, y) + dz, ang))
    elif k == 'patrol':
        _, key, i, x, y = e
        PATROL_EXT.setdefault(key, []).append((x, y))
    elif k == 'note':
        _, nid, x, y, dz, ang = e
        wplace(NOTES[nid], x, y, dz, ang)
    elif k == 'container':
        _, key, propname, x, y, dz, ang, loot = e
        m = MANIFEST[propname]
        cid = R.cont(p, f'SFCont_{key}', 'Supply Crate', m['nif'], m['bounds'], items=[(S('LeveledItem', 'LItemPotionRestoreHealth'), 2), (S('MiscItem', 'Lockpick'), 2)])
        wplace(cid, x, y, dz, ang); EXT_BLOCK += footprint(propname, x, y, ang)
    elif k == 'canister':
        _, x, y, dz, ang = e
        wplace(p.m('StarfallCreatures.esp', CRE_IDS['SFHeadcrabCanister']), x, y, dz, ang)
        EXT_BLOCK.append((x - 120, y - 80, x + 140, y + 80))
    elif k == 'spawn':
        SPAWN_EXT.append((e[1], e[2]))

# exterior navmesh: 128 grid, one NAVM per cell, portal links across cell borders
G = 128
nx = (SE.CMAX[0] - SE.CMIN[0] + 1) * 32; ny = (SE.CMAX[1] - SE.CMIN[1] + 1) * 32
ox, oy = SE.CMIN[0] * 4096, SE.CMIN[1] * 4096
walk = np.zeros((nx, ny), bool)
for i in range(nx):
    for j in range(ny):
        cxm, cym = ox + (i + 0.5) * G, oy + (j + 0.5) * G
        walk[i, j] = SE.walkable(cxm, cym)
for (x0, y0, x1, y1) in EXT_BLOCK:
    i0, j0 = int((x0 - 24 - ox) // G), int((y0 - 24 - oy) // G); i1, j1 = int(math.ceil((x1 + 24 - ox) / G)), int(math.ceil((y1 + 24 - oy) / G))
    walk[max(i0, 0):i1, max(j0, 0):j1] = False
from building import prune
walk = prune(walk, 30)
NAVM_IDS = {c: p.new_id() for c in CELLS}
nav_data = {}
for (cx, cy) in CELLS:
    i0, j0 = (cx - SE.CMIN[0]) * 32, (cy - SE.CMIN[1]) * 32
    sub_walk = walk[i0:i0 + 32, j0:j0 + 32]
    if not sub_walk.any(): continue
    verts, tris, edges = grid_navmesh(sub_walk, lambda i, j, i0=i0, j0=j0: (ox + (i0 + i) * G, oy + (j0 + j) * G),
                                      lambda i, j, i0=i0, j0=j0: ground(ox + (i0 + i) * G, oy + (j0 + j) * G))
    # map grid cell -> triangle ids, to build cross-cell links
    tri_of = {}; t = 0
    for i in range(32):
        for j in range(32):
            if sub_walk[i, j]: tri_of[(i, j, 0)] = t; tri_of[(i, j, 1)] = t + 1; t += 2
    nav_data[(cx, cy)] = dict(verts=verts, tris=tris, edges=edges, tri_of=tri_of, walk=sub_walk)
for (cx, cy), d in nav_data.items():
    links = {}
    for i in range(32):
        for j in range(32):
            if not d['walk'][i, j]: continue
            # tri0 edges: 0 = south (a-b), 1 = east (b-c); tri1 edges: 1 = north (c-d), 2 = west (d-a)
            if j == 0 and (cx, cy - 1) in nav_data and nav_data[(cx, cy - 1)]['walk'][i, 31]:
                links[(d['tri_of'][(i, j, 0)], 0)] = (NAVM_IDS[(cx, cy - 1)], nav_data[(cx, cy - 1)]['tri_of'][(i, 31, 1)])
            if i == 31 and (cx + 1, cy) in nav_data and nav_data[(cx + 1, cy)]['walk'][0, j]:
                links[(d['tri_of'][(i, j, 0)], 1)] = (NAVM_IDS[(cx + 1, cy)], nav_data[(cx + 1, cy)]['tri_of'][(0, j, 1)])
            if j == 31 and (cx, cy + 1) in nav_data and nav_data[(cx, cy + 1)]['walk'][i, 0]:
                links[(d['tri_of'][(i, j, 1)], 1)] = (NAVM_IDS[(cx, cy + 1)], nav_data[(cx, cy + 1)]['tri_of'][(i, 0, 0)])
            if i == 0 and (cx - 1, cy) in nav_data and nav_data[(cx - 1, cy)]['walk'][31, j]:
                links[(d['tri_of'][(i, j, 1)], 2)] = (NAVM_IDS[(cx - 1, cy)], nav_data[(cx - 1, cy)]['tri_of'][(31, j, 0)])
    PENDING_NAV.append(dict(fid=NAVM_IDS[(cx, cy)], verts=d['verts'], tris=d['tris'], edges=d['edges'], cell=(cx, cy), world=WORLD, grid=(cx, cy), links=links, doors=[]))

# =====================================================================================================================
# 4. doors between spaces
# =====================================================================================================================
def link_doors(a_cell, a_world, a_pos, a_ang, a_base, b_cell, b_world, b_pos, b_ang, b_base, a_edid, b_edid, lock_b=None, a_pers=True, b_pers=True):
    """two load doors; each teleports in front of the other (100 units out along its facing)"""
    a_id, b_id = p.new_id(), p.new_id()
    def front(pos, ang): return (pos[0] + 110 * math.sin(math.radians(ang)), pos[1] + 110 * math.cos(math.radians(ang)), pos[2])
    for (cid, wid, pos, ang, base, rid, other, opos, oang, edid, extra) in [
            (a_cell, a_world, a_pos, a_ang, a_base, a_id, b_id, b_pos, b_ang, a_edid, []),
            (b_cell, b_world, b_pos, b_ang, b_base, b_id, a_id, a_pos, a_ang, b_edid, lock_b or [])]:
        subs, fl = W.refr(base, pos, ang, persistent=True, extra=[W.x_teleport(other, front(opos, oang), oang)] + extra, edid=edid)
        rec = Record('REFR', rid, subs, fl); p.edids[edid] = rid
        if wid is None: p.interiors[cid]['pers'].append(rec)
        else: p.worlds[wid]['pcell']['pers'].append(rec)
    return a_id, b_id

fd = M_EXT['facility_door'][0]
DOOR_FAC_EXT, DOOR_FAC_INT = link_doors(None, WORLD, fd[:3], fd[3], D_FAC, CELL_FAC, None, (0, 64, 0), 0, D_CRATER, 'SFRefFacilityDoorExt', 'SFRefFacilityDoorInt')
DOOR_WB_A, DOOR_WB_B = link_doors(CELL_FAC, None, (2112, 4064, 0), 270, D_WINGB, CELL_WINGB, None, (0, 64, 0), 0, D_FAC, 'SFRefWingBDoorOut', 'SFRefWingBDoorIn')
# Wing B door (facility side) locked: requires the keycard
for rec in p.interiors[CELL_FAC]['pers']:
    if rec.formid == DOOR_WB_A: rec.subs.insert(-1, W.x_lock(255, KEYCARD))

# ---- gate in Skyrim (Tamriel persistent cell); the DLL repositions these next to Embershard Mine and snaps them to the ground ----
TAMRIEL = S('Worldspace', 'Tamriel')
TAM_PCELL = p.sky(0x000D74)
W.override_world_persistent_cell(p, TAMRIEL, TAM_PCELL, [])
ad = M_EXT['arrival_door'][0]
GATE_HIDE = (0.0, 0.0, -40000.0)   # parked under the map until the DLL moves them into place
gate_refs = []
def tam_place(base, dx, dy, dz, ang, actor=False, extra=(), edid=None):
    subs, fl = W.refr(base, (GATE_HIDE[0] + dx, GATE_HIDE[1] + dy, GATE_HIDE[2] + dz), ang, persistent=True, extra=list(extra), edid=edid)
    rid = p.new_id()
    if edid: p.edids[edid] = rid
    p.worlds[TAMRIEL]['pcell']['pers'].append(Record('ACHR' if actor else 'REFR', rid, subs, fl))
    gate_refs.append(dict(id=rid, dx=dx, dy=dy, dz=dz, angle=ang))
    return rid
# layout relative to the gate door (door faces +Y = toward the player approaching from the north side... angle 0 means facing north)
tam_place(prop_stat('bunker_entrance'), 0, -186, 0, 0)
GATE_SIGN = tam_place(prop_stat('sign_lambda'), 0, -8, 250, 0)
for sx in (-380, 380): tam_place(prop_stat('floodlight_tripod'), sx, 320, 0, 180); tam_place(LIGHTS['flood'], sx, 340, 215, 0)
tam_place(prop_stat('jersey_barrier'), -330, 220, 0, 20); tam_place(prop_stat('jersey_barrier'), 330, 220, 0, -20)
MAPMARKER = tam_place(S('Static', 'MapMarker'), 0, 600, 0, 0, extra=W.x_mapmarker('Starfall Crater', 16), edid='SFRefMapMarker')
# gate door <-> arrival door in the crater
gid = p.new_id(); aid = p.new_id(); p.edids['SFRefGateDoor'] = gid; p.edids['SFRefArrivalDoor'] = aid
subs, fl = W.refr(D_GATE, (GATE_HIDE[0], GATE_HIDE[1], GATE_HIDE[2]), 0, persistent=True,
                  extra=[W.x_teleport(aid, (ad[0], ad[1] + 120, ad[2]), 0), W.x_lock(255, 0)], edid='SFRefGateDoor')
p.worlds[TAMRIEL]['pcell']['pers'].append(Record('REFR', gid, subs, fl))
gate_refs.append(dict(id=gid, dx=0, dy=0, dz=0, angle=0, door=True))
subs, fl = W.refr(D_SKYRIM, ad[:3], 0, persistent=True, extra=[W.x_teleport(gid, (0, 120, -40000), 0)], edid='SFRefArrivalDoor')
p.worlds[WORLD]['pcell']['pers'].append(Record('REFR', aid, subs, fl))

# =====================================================================================================================
# 5. actors
# =====================================================================================================================
SANDBOX_LINK = S('Package', 'DefaultSandboxLinkCustom02512')
SLEEP = S('Package', 'DefaultSleepEditorLoc22x8') if False else S('Package', 'DefaultSleepEditorLoc22x10')
EAT_NOON, EAT_EVE = S('Package', 'DefaultEatEditorLoc12x1'), S('Package', 'DefaultEatEditorLoc18x1')
GUARD_PKG = S('Package', 'defaultGuardLinkedRef64')
HOLD_PKG = S('Package', 'DefaultHoldPositionLinkedRef128')
PATROL_PKG = S('Package', 'DefaultPatrolLinkedRefNoConvo')
HOLD_HERE = S('Package', 'DefaultHoldPositionCurrentLoc128')
SANDBOX_HERE = S('Package', 'DefaultSandboxEditorLocation512')
LINK02 = S('Keyword', 'LinkCustom02')
CITIZEN, GUARDCLS = S('Class', 'Citizen'), S('Class', 'GuardImperial')

SCI = [  # edid, name, head, voice, work marker, protected
    ('SFKast', 'Director Aurelius Kast', 'einstein', 'Kast', 'kast_work', True),
    ('SFHale', 'Dr. Marcus Hale', 'luther', 'Hale', 'hale_work', True),
    ('SFRusk', 'Dr. Emil Rusk', 'walter', 'Rusk', 'rusk_work', True),
    ('SFVenn', 'Tobias Venn', 'slick', 'Venn', 'venn_work', False),
    ('SFPell', 'Jory Pell', 'walter', 'Junior1', 'hale_work', False),
    ('SFHolt', 'Brennic Holt', 'slick', 'Junior2', 'venn_work', False),
    ('SFMire', 'Ollan Mire', 'luther', 'Junior3', 'rusk_work', False),
]
NPC_IDS, ACTOR_REFS = {}, {}
vendor_fac = None
bed_positions = [(300, 1600, 180), (520, 1600, 180), (740, 1600, 180), (960, 1600, 180), (300, 1150, 0), (520, 1150, 0), (740, 1150, 0)]
for k, (edid, name, head, voice, work, prot) in enumerate(SCI):
    flags = R.ACBS_UNIQUE | (R.ACBS_PROTECTED if prot else 0)
    facs = [(fac_site, 0)]
    nid = R.npc(p, edid, name, IMPERIAL, CITIZEN, level=10, flags=flags, health=120, magicka=80, stamina=90, factions=facs,
                voice=VOICES[voice], outfit=OUTFITS[head], packages=[SLEEP, EAT_NOON, EAT_EVE, SANDBOX_LINK], kws=[kw_site],
                aggression=0, confidence=0, assistance=0, energy=60, morality=3, items=[(S('MiscItem', 'Gold001'), 25)],
                skills=[12] * 18, short_name=name.split()[-1])
    NPC_IDS[edid] = nid
    bx, by, bang = bed_positions[k]
    work_ref = M_FAC[work][0]
    ach = W.place(p, CELL_FAC, nid, (bx, by - (120 if bang == 180 else -120), 0), bang, actor=True, persistent=True,
                  extra=[W.x_linked(work_ref, LINK02)], edid=f'SFRef_{edid}')
    ACTOR_REFS[edid] = ach
# beds owned by their sleeper: patch ownership onto the bed refs we placed (they are vanilla furniture refs in the quarters)
bed_owner = {}
for rec in p.interiors[CELL_FAC]['temp']:
    if rec.sig != 'REFR': continue
    base = struct.unpack('<I', rec.subs[0][6:10])[0]
    if base == S('Furniture', 'DweFurnitureBedSingle01'):
        x, y = struct.unpack('<ff', rec.subs[-1][6:14])
        for k, (bx, by, _) in enumerate(bed_positions):
            if abs(bx - x) < 1 and abs(by - y) < 1:
                rec.subs.insert(1, W.x_owner(NPC_IDS[SCI[k][0]]))

# ---- Hale is a vendor after clearance (the DLL opens barter); vendor chest is a hidden persistent ref ----
vchest = W.place(p, CELL_FAC, vendor_chest_base, (-1300, 1850, -400), 0, persistent=True, edid='SFRefVendorChest')
vendor_fac = R.fact(p, 'SFHaleVendorFaction', 'Hale Vendor', [], flags=0x4000, hidden=True,
                    vendor=dict(list=vendor_list, container=vchest, start=0, end=24, radius=0))
hale_rec = next(r for r in p.top['NPC_'] if r.formid == NPC_IDS['SFHale'])
hale_rec.subs.insert(next(i for i, x in enumerate(hale_rec.subs) if x[:4] == b'ACBS') + 1, sub('SNAM', fid(vendor_fac) + struct.pack('<b3s', 0, b'\0\0\0')))

# ---- guards ----
def guard_npc(edid, name, voice, outfit, unique=False, level=16, hp=230):
    return R.npc(p, edid, name, IMPERIAL, GUARDCLS, level=level, flags=(R.ACBS_UNIQUE if unique else 0), health=hp, magicka=40, stamina=180,
                 factions=[(fac_site, 0)], voice=VOICES[voice], outfit=outfit, kws=[kw_site], aggression=1, confidence=3,
                 assistance=2, energy=40, morality=1, skills=[45, 30, 40, 50, 15, 55, 20, 10, 10, 20, 10, 15, 10, 10, 10, 10, 10, 10],
                 combat_style=S('CombatStyle', 'csHumanMeleeLvl4'), packages=[], items=[(BATON, 1)])
GUARD_A = guard_npc('SFGuardA', 'Security Officer', 'GuardA', OUT_GUARD)
GUARD_B = guard_npc('SFGuardB', 'Security Officer', 'GuardB', OUT_GUARD)
MORAN = guard_npc('SFMoran', 'Captain Dace Moran', 'Moran', OUT_WARDEN, unique=True, level=22, hp=320)
SENTRY = guard_npc('SFGateSentry', 'Checkpoint Sentry', 'GuardA', OUT_GUARD)
NPC_IDS.update(SFMoran=MORAN, SFGuardA=GUARD_A, SFGuardB=GUARD_B, SFGateSentry=SENTRY)
def set_packages(npc_fid, pkgs):
    rec = next(r for r in p.top['NPC_'] if r.formid == npc_fid)
    i = next(n for n, s_ in enumerate(rec.subs) if s_[:4] == b'AIDT') + 1
    for k_, pk in enumerate(pkgs): rec.subs.insert(i + k_, sub('PKID', fid(pk)))
set_packages(GUARD_A, [GUARD_PKG]); set_packages(GUARD_B, [GUARD_PKG]); set_packages(MORAN, [SANDBOX_HERE]); set_packages(SENTRY, [HOLD_HERE])
# patrol guards need their own base (patrol package)
PATROL_A = guard_npc('SFGuardPatrolA', 'Security Officer', 'GuardA', OUT_GUARD); set_packages(PATROL_A, [PATROL_PKG])
PATROL_B = guard_npc('SFGuardPatrolB', 'Security Officer', 'GuardB', OUT_GUARD); set_packages(PATROL_B, [PATROL_PKG])
TOWER = guard_npc('SFGuardTower', 'Security Officer', 'GuardB', OUT_GUARD); set_packages(TOWER, [HOLD_PKG])
NPC_IDS.update(SFGuardPatrolA=PATROL_A, SFGuardPatrolB=PATROL_B, SFGuardTower=TOWER)

# interior posts
ab = 0
for key in ['lobby_guard1', 'lobby_guard2', 'obs_guard', 'containment_guard', 'wingb_guard']:
    mk = M_FAC[key][0]
    rec = next(r for r in p.interiors[CELL_FAC]['temp'] if r.formid == mk)
    x, y, z = struct.unpack('<fff', rec.subs[-1][6:18])
    base = GUARD_A if ab % 2 == 0 else GUARD_B; ab += 1
    W.place(p, CELL_FAC, base, (x, y, z), 0, actor=True, extra=[W.x_linked(mk)])
mk = M_FAC['moran_post'][0]
ACTOR_REFS['SFMoran'] = W.place(p, CELL_FAC, MORAN, (230, 330, 0), 90, actor=True, persistent=True, edid='SFRef_SFMoran')
# interior corridor patrol: chain markers in a loop
cm = M_FAC['corridor_patrol']
for i, mid in enumerate(cm):
    rec = next(r for r in p.interiors[CELL_FAC]['temp'] if r.formid == mid)
    rec.subs.insert(1, W.x_linked(cm[(i + 1) % len(cm)]))
W.place(p, CELL_FAC, PATROL_A, (0, 1200, 0), 0, actor=True, extra=[W.x_linked(cm[0])])
# exterior posts
def ext_marker(x, y, z, ang, persistent=False):
    return W.place(p, CELLS[cell_of(x, y)], S('Static', 'XMarkerHeading'), (x, y, z), ang, world=WORLD)
for key in ['checkpoint_guard1', 'checkpoint_guard2', 'door_guard1', 'door_guard2', 'camp_guard']:
    for (x, y, z, ang) in M_EXT[key]:
        mk = ext_marker(x, y, z, ang)
        base = GUARD_A if ab % 2 == 0 else GUARD_B; ab += 1
        W.place(p, CELLS[cell_of(x, y)], base, (x, y, z), ang, world=WORLD, actor=True, extra=[W.x_linked(mk)])
for key in [k for k in M_EXT if k.startswith('tower_')]:
    for (x, y, z, ang) in M_EXT[key]:
        mk = ext_marker(x, y, z, ang)
        W.place(p, CELLS[cell_of(x, y)], TOWER, (x, y, z), ang, world=WORLD, actor=True, extra=[W.x_linked(mk)])
# perimeter patrol: 12 markers in a loop, two guards starting opposite each other (persistent so they can cross cells)
pm = []
for (x, y) in PATROL_EXT['perimeter']:
    pm.append(W.place(p, 'persistent', S('Static', 'XMarker'), (x, y, ground(x, y)), 0, world=WORLD, persistent=True))
for i, mid in enumerate(pm):
    rec = next(r for r in p.worlds[WORLD]['pcell']['pers'] if r.formid == mid)
    rec.subs.insert(1, W.x_linked(pm[(i + 1) % len(pm)]))
for start, base in ((0, PATROL_A), (6, PATROL_B)):
    x, y = PATROL_EXT['perimeter'][start]
    W.place(p, 'persistent', base, (x, y, ground(x, y)), 0, world=WORLD, persistent=True, actor=True, extra=[W.x_linked(pm[start])])
# a scientist in the yard during the day (Holt helps out at the crystal) is handled by sandboxing; add a yard idle marker only
# ---- Skyrim-side gate sentry ----
SENTRY_REF = tam_place(SENTRY, -170, 260, 0, 0, actor=True, edid='SFRef_GateSentry')

# ---- fixed creature encounters ----
LV_OUTBREAK, LV_CRAB, LV_ZOMBIE = CR('SFLvlOutbreak'), CR('SFLvlHeadcrab'), CR('SFLvlZombie')
for k, (x, y) in enumerate(SPAWN_WB):
    W.place(p, CELL_WINGB, [LV_ZOMBIE, LV_CRAB, LV_OUTBREAK][k % 3], (x, y, 0), (k * 77) % 360, actor=True)
for k, (x, y) in enumerate(SPAWN_EXT):
    base = [LV_ZOMBIE, LV_CRAB, LV_CRAB][k % 3]
    W.place(p, CELLS[cell_of(x, y)], base, (x, y, ground(x, y)), (k * 91) % 360, world=WORLD, actor=True)

# =====================================================================================================================
# 6. quest + dialogue
# =====================================================================================================================
QMAIN_ID = p.reserve('SFQuestMain')
QDLG_ID = p.reserve('SFDialogue')
def cond_list(conds, speaker=None):
    out = []
    if speaker:
        if speaker in ('GuardA', 'GuardB'):
            out.append(W.ctda('GetIsVoiceType', '==', 1, VOICES[speaker]))
        else:
            out.append(W.ctda('GetIsID', '==', 1, NPC_IDS[speaker]))
    for c in conds:
        m = re.match(r'stage(==|>=|<)(\d+)$', c)
        if m: out.append(W.ctda('GetStage', m.group(1), int(m.group(2)), QMAIN_ID)); continue
        if c == 'hasGravityGun': out.append(W.ctda('GetItemCount', '>=', 1, GG_GUN, run='target'))
        elif c == 'noGravityGun': out.append(W.ctda('GetItemCount', '==', 0, GG_GUN, run='target'))
        elif c == 'crystals>=3': out.append(W.ctda('GetItemCount', '>=', 3, GG_CRYSTAL, run='target'))
        elif c == 'hasJournal': out.append(W.ctda('GetItemCount', '>=', 1, JOURNAL, run='target'))
        elif c == 'hasKeycard': out.append(W.ctda('GetItemCount', '>=', 1, KEYCARD, run='target'))
        elif c == 'night':
            out += [W.ctda('GetCurrentTime', '>=', 20, OR=True), W.ctda('GetCurrentTime', '<', 6)]
        elif c == 'day':
            out += [W.ctda('GetCurrentTime', '>=', 6), W.ctda('GetCurrentTime', '<', 20)]
        else: raise ValueError(c)
    return out

VOICE_OF = {'SFKast': 'SFVoiceKast', 'SFHale': 'SFVoiceHale', 'SFRusk': 'SFVoiceRusk', 'SFVenn': 'SFVoiceVenn', 'SFPell': 'SFVoiceJunior1',
            'SFHolt': 'SFVoiceJunior2', 'SFMire': 'SFVoiceJunior3', 'SFMoran': 'SFVoiceMoran', 'GuardA': 'SFVoiceGuardA', 'GuardB': 'SFVoiceGuardB'}
MANIFEST_ROWS = []   # (voice folder, file, speaker, text, emotion, info edid, category)
INFO_META = []       # filled after ids are known: (info fid, topic edid, response n, speaker, text, emotion, line id)
def add_lines(dfid, topic_edid, items, category, flags=0x2, reset=0.0):
    for it in items:
        conds = cond_list(it.get('cond', []), it['speaker'])
        iid = W.info(p, dfid, [(it['text'], it.get('emotion', 'Neutral'))], conditions=conds, flags=flags, reset_hours=reset, edid=None)
        INFO_META.append((iid, topic_edid, 1, it['speaker'], it['text'], it.get('emotion', 'Neutral'), it['id'], category))

# greetings / idles / combat (one topic per subtype, many INFOs; random)
d_hello = W.dial(p, 'SFHello', QDLG_ID, 'Hello', priority=60)
add_lines(d_hello, 'SFHello', DLG['greetings'], 'greeting', flags=0x2, reset=0.0)
d_idle = W.dial(p, 'SFIdle', QDLG_ID, 'Idle', priority=60)
add_lines(d_idle, 'SFIdle', DLG['idle'], 'idle', flags=0x2)
COMBAT_T = {}
for c in DLG['combat']:
    COMBAT_T.setdefault(c['type'], []).append(c)
for typ, items in COMBAT_T.items():
    edid = 'SFCb' + typ[:11]
    dfid = W.dial(p, edid, QDLG_ID, typ, priority=60)
    add_lines(dfid, edid, items, 'combat:' + typ, flags=0x2)
# gate sentry lines (Skyrim side): turn away without the device, wave through with it
GATE_LINES = [
    ({'speaker': 'GuardA', 'cond': [], 'id': 'gate_no_1', 'emotion': 'Anger', 'text': "Turn around, civilian. This road is closed by order of the Directorate."}, 'noGravityGun'),
    ({'speaker': 'GuardA', 'cond': [], 'id': 'gate_no_2', 'emotion': 'Neutral', 'text': "Nothing to see past this gate. Go back to Riverwood."}, 'noGravityGun'),
    ({'speaker': 'GuardA', 'cond': [], 'id': 'gate_no_3', 'emotion': 'Anger', 'text': "No clearance, no entry. Keep walking."}, 'noGravityGun'),
    ({'speaker': 'GuardA', 'cond': [], 'id': 'gate_yes_1', 'emotion': 'Surprise', 'text': "Is that... the missing manipulator? Go on through. The Director will want to see you."}, 'hasGravityGun'),
    ({'speaker': 'GuardA', 'cond': [], 'id': 'gate_yes_2', 'emotion': 'Neutral', 'text': "You're cleared. Watch the canyon, things crawl out of it at night."}, 'hasGravityGun'),
]
d_gate = W.dial(p, 'SFGateHello', QDLG_ID, 'Hello', priority=70)
for it, gc in GATE_LINES:
    conds = [W.ctda('GetIsID', '==', 1, SENTRY), *cond_list([gc])]
    iid = W.info(p, d_gate, [(it['text'], it['emotion'])], conditions=conds, flags=0x2)
    INFO_META.append((iid, 'SFGateHello', 1, 'GuardA', it['text'], it['emotion'], it['id'], 'gate'))

# NPC-to-NPC conversation lines: one Custom topic per line, said through the DLL (ObjectReference.Say)
CONV_JSON = []
for ci, cv in enumerate(DLG['conversations'], 1):
    lines = []
    for li, ln in enumerate(cv['lines'], 1):
        spk = cv[ln['who']]
        edid = f'SFcv{ci:02d}_{li}'
        dfid = W.dial(p, edid, QDLG_ID, 'Custom', priority=50)
        iid = W.info(p, dfid, [(ln['text'], ln.get('emotion', 'Neutral'))], conditions=cond_list([], spk))
        INFO_META.append((iid, edid, 1, spk, ln['text'], ln.get('emotion', 'Neutral'), ln['id'], 'conversation'))
        lines.append({'who': ln['who'], 'topic': hex(dfid & 0xFFFFFF), 'text': ln['text']})
    CONV_JSON.append({'a': cv['a'], 'b': cv['b'], 'minStage': cv.get('minStage', 0), 'maxStage': cv.get('maxStage', 1000), 'lines': lines, 'weight': 1})

# player dialogue: one top-level branch per topic tree
INFO_ACTIONS = []
TOPIC_N = [0]
def build_topic(t, top_level, branch=None):
    TOPIC_N[0] += 1
    edid = f'SFtp{TOPIC_N[0]:03d}'
    dfid = W.dial(p, edid, QDLG_ID, 'Custom', name=t['prompt'], priority=50)
    if top_level:
        branch = W.dlbr(p, edid + 'B', QDLG_ID, dfid)
    p.topics[dfid]['record'].subs.insert(3, sub('BNAM', fid(branch)))
    children = [build_topic(c, False, branch) for c in t.get('children', [])]
    child_dials = [c[0] for c in children]
    conds = cond_list(t.get('cond', []), t['speaker'])
    if t['id'] == 'tp_rusk_q30_ask':
        conds += [W.ctda('GetItemCount', '==', 0, KEYCARD, run='target'), W.ctda('GetItemCount', '==', 0, JOURNAL, run='target')]
    resp = [(r['text'], r.get('emotion', 'Neutral')) for r in t['responses']]
    iid = W.info(p, dfid, resp, conditions=conds, prompt=t['prompt'], links=child_dials, flags=0x4 if t.get('actions', {}).get('setStage') else 0)
    for n, r in enumerate(t['responses'], 1):
        INFO_META.append((iid, edid, n, t['speaker'], r['text'], r.get('emotion', 'Neutral'), r['id'], 'topic'))
    act = t.get('actions') or {}
    if act:
        a = {'info': hex(iid & 0xFFFFFF), 'once': True}
        if 'setStage' in act: a['setStage'] = act['setStage']
        if 'objectiveDisplayed' in act: a['objectiveDisplayed'] = act['objectiveDisplayed']
        if 'objectiveCompleted' in act: a['objectiveCompleted'] = act['objectiveCompleted']
        if act.get('removeCrystals'): a['removeItem'] = {'plugin': 'GravityGun.esp', 'id': '0x806', 'count': act['removeCrystals']}
        if act.get('giveKeycard'): a['addItem'] = {'plugin': 'StarfallSite.esp', 'id': hex(KEYCARD & 0xFFFFFF), 'count': 1}
        if act.get('removeJournal'): a['removeItem'] = {'plugin': 'StarfallSite.esp', 'id': hex(JOURNAL & 0xFFFFFF), 'count': 1}
        if act.get('openVendor'): a['openVendor'] = True; a['once'] = False
        if act.get('setStage') == 50: a['unlock'] = [{'plugin': 'StarfallSite.esp', 'id': hex(p.edids['SFRef_armory'] & 0xFFFFFF)}]
        INFO_ACTIONS.append(a)
    return dfid, iid
for t in DLG['topics']:
    if t['id'] == 'tp_kast_q10_nogun': continue     # the site is only reachable with the device; keep the quest gated on it
    build_topic(t, True)

# quest records
ALIAS_KAST, ALIAS_HALE, ALIAS_RUSK, ALIAS_JOURNAL = 0, 1, 2, 3
aliases = [W.ref_alias(ALIAS_KAST, 'Kast', ref=ACTOR_REFS['SFKast']), W.ref_alias(ALIAS_HALE, 'Hale', ref=ACTOR_REFS['SFHale']),
           W.ref_alias(ALIAS_RUSK, 'Rusk', ref=ACTOR_REFS['SFRusk']), W.ref_alias(ALIAS_JOURNAL, 'Journal', ref=p.edids['SFRef_journal'], flags=0x4 | 0x2)]
stages = [(0, None, False)] + [(int(k), v, int(k) == 50) for k, v in sorted(QT['stages'].items(), key=lambda kv: int(kv[0]))]
obj_targets = {10: [ALIAS_KAST], 20: [ALIAS_HALE], 30: [ALIAS_JOURNAL], 40: [ALIAS_KAST]}
objectives = [(int(k), v, obj_targets.get(int(k), [])) for k, v in sorted(QT['objectives'].items(), key=lambda kv: int(kv[0]))]
# fix up reserved ids: add() creates new ids, so build the records manually with the reserved ones
def add_reserved(sig, formid, edid, subs):
    r = Record(sig, formid, [sub('EDID', edid)] + subs); p.top.setdefault(sig, []).append(r)
tmp = Plugin('tmp', ['a']); tmp.next_obj = 0
qm = W.quest(tmp, None, QT['name'], flags=0x10 | 0x100, priority=60, qtype=8, stages=stages, objectives=objectives, aliases=aliases)
add_reserved('QUST', QMAIN_ID, 'SFQuestMain', tmp.top['QUST'][-1].subs)
qd = W.quest(tmp, None, '', flags=0x1 | 0x10, priority=50, stages=[(0, None, False)])
add_reserved('QUST', QDLG_ID, 'SFDialogue', tmp.top['QUST'][-1].subs)

# ---- navmesh door links (lets NPCs path through the load doors) + emit all navmeshes ----
def find_tri(nav, x, y):
    V = nav['verts']
    for ti, t in enumerate(nav['tris']):
        a, b, c = V[t[0]], V[t[1]], V[t[2]]
        d1 = (x - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (y - b[1]); d2 = (x - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (y - c[1]); d3 = (x - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (y - a[1])
        if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)): return ti
    return None
def door_link(door_ref, cell_key, world, pos, ang):
    nav = next((n for n in PENDING_NAV if n['cell'] == cell_key and n['world'] == world), None)
    if not nav: return
    ti = None
    for dist in (110, 180, 250, 320, 400):
        fx, fy = pos[0] + dist * math.sin(math.radians(ang)), pos[1] + dist * math.cos(math.radians(ang))
        ti = find_tri(nav, fx, fy)
        if ti is not None: break
    if ti is None: print('door link: no triangle in front of door', hex(door_ref)); return
    nav['doors'].append((ti, door_ref))
    # XNDP on the door reference
    c = p.interiors[cell_key] if world is None else p.worlds[world]['pcell']
    rec = next(r for r in c['pers'] if r.formid == door_ref)
    rec.subs.insert(-1, sub('XNDP', fid(nav['fid']) + struct.pack('<h2s', ti, b'\0\0')))
door_link(DOOR_FAC_INT, CELL_FAC, None, (0, 64, 0), 0)
door_link(DOOR_WB_A, CELL_FAC, None, (2112, 4064, 0), 270)
door_link(DOOR_WB_B, CELL_WINGB, None, (0, 64, 0), 0)
door_link(DOOR_FAC_EXT, cell_of(fd[0], fd[1]), WORLD, fd[:3], fd[3])
for nav in PENDING_NAV:
    nm = W.navm_record(p, nav['fid'], nav['verts'], nav['tris'], nav['edges'], world=nav['world'] or 0, grid=nav['grid'],
                       cell=nav['cell'] if nav['world'] is None else 0, ext_links=nav['links'], door_links=nav['doors'])
    if nav['world'] is None: p.interiors[nav['cell']]['temp'].insert(0, nm)
    else: p.worlds[WORLD]['cells'][nav['cell']]['temp'].insert(1, nm)

# =====================================================================================================================
# 7. write plugin + DLL data + voice manifest
# =====================================================================================================================
size = p.write(f'{DATA}/StarfallSite.esp')
print('StarfallSite.esp', size, 'bytes')
H = lambda f: hex(f & 0xFFFFFF)
forms = {
    'spawner': {'plugin': 'StarfallCreatures.esp', 'groups': [
        {'name': 'headcrab_nest', 'lvln': H(CR('SFLvlHeadcrab')), 'min': 2, 'max': 4, 'weight': 4, 'minLevel': 1, 'interior': True, 'exterior': True},
        {'name': 'zombie_pack', 'lvln': H(CR('SFLvlZombie')), 'min': 1, 'max': 3, 'weight': 3, 'minLevel': 1, 'interior': True, 'exterior': True},
        {'name': 'outbreak', 'lvln': H(CR('SFLvlOutbreak')), 'min': 3, 'max': 5, 'weight': 2, 'minLevel': 8, 'interior': True, 'exterior': True},
        {'name': 'fast_hunters', 'lvln': H(CR('SFLvlFastZombie')), 'min': 1, 'max': 2, 'weight': 1, 'minLevel': 12, 'interior': False, 'exterior': True},
        {'name': 'poison_zombie', 'lvln': H(CR('SFLvlPoisonZombie')), 'min': 1, 'max': 1, 'weight': 1, 'minLevel': 16, 'interior': True, 'exterior': False}],
        'canister': {'plugin': 'StarfallCreatures.esp', 'static': H(CR('SFHeadcrabCanister'))}},
    'headcrabKeyword': {'plugin': 'StarfallCreatures.esp', 'id': H(CR('SFKwHeadcrab'))},
    'zombieKeyword': {'plugin': 'StarfallCreatures.esp', 'id': H(CR('SFKwZombie'))},
    'siteWorldspace': {'plugin': 'StarfallSite.esp', 'id': H(WORLD)},
    'siteCells': [{'plugin': 'StarfallSite.esp', 'id': H(CELL_FAC)}, {'plugin': 'StarfallSite.esp', 'id': H(CELL_WINGB)}],
    'actors': dict({k: {'plugin': 'StarfallSite.esp', 'id': H(v)} for k, v in ACTOR_REFS.items()}, GuardA={'plugin': 'StarfallSite.esp', 'id': H(GUARD_A)}, GuardB={'plugin': 'StarfallSite.esp', 'id': H(GUARD_B)}),
    'conversations': CONV_JSON,
    'infoActions': INFO_ACTIONS,
    'quest': {'plugin': 'StarfallSite.esp', 'id': H(QMAIN_ID)},
    'vendor': {'actor': H(ACTOR_REFS['SFHale'])},
    'gate': {'anchor': {'plugin': 'Skyrim.esm', 'id': hex(V('PlacedObject', 'EmbershardMineMapMarker'))},
             'offset': [900.0, -600.0], 'facing': 0.0,
             'refs': [dict(r, id=H(r['id'])) for r in gate_refs],
             'door': H(gid), 'arrivalDoor': H(aid),
             'requiredItem': {'plugin': 'GravityGun.esp', 'id': '0x803'},
             'deniedMessage': 'The checkpoint is sealed. The guards will not let you through without the Zero-Point device.'},
}
os.makedirs(f'{DATA}/SKSE/Plugins/StarfallSite', exist_ok=True)
json.dump(forms, open(f'{DATA}/SKSE/Plugins/StarfallSite/forms.json', 'w'), indent=1)
# voice manifest
import csv
rows = []
for (iid, topic_edid, n, spk, text, emo, line_id, cat) in INFO_META:
    vt = VOICE_OF[spk]
    fname = f'SFDialogue_{topic_edid}_{iid & 0xFFFFFF:08X}_{n}'
    rows.append([f'Sound\\Voice\\StarfallSite.esp\\{vt}\\', fname + '.fuz', vt, spk, cat, emo, text, line_id])
with open(f'{ROOT}/voice_manifest.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['folder', 'file', 'voice_type', 'speaker', 'category', 'emotion', 'text', 'line_id']); w.writerows(rows)
json.dump({k: hex(v) for k, v in p.edids.items()}, open(f'{ROOT}/build/site_ids.json', 'w'), indent=0)
print('voice lines', len(rows), 'infoActions', len(INFO_ACTIONS), 'conversations', len(CONV_JSON))
print('interior navmesh tris:', [len(x.subs) for x in []])

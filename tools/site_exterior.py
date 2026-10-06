"""Starfall Crater worldspace: heightfield, landscape texturing, placements, walkable region for navmesh."""
import math, numpy as np
CELL = 4096
CMIN, CMAX = (-3, -3), (2, 2)          # 6 x 6 cells: -12288 .. 12288
FLOOR_Z, RIM_Z = -700.0, 260.0

def _hash_noise(x, y, scale, seed=0):
    """smooth value noise (bilinear on a hashed lattice)"""
    xs, ys = x / scale, y / scale
    xi, yi = np.floor(xs), np.floor(ys); fx, fy = xs - xi, ys - yi
    def h(a, b):
        v = np.sin(a * 127.1 + b * 311.7 + seed * 74.7) * 43758.5453
        return v - np.floor(v)
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    return (h(xi, yi) * (1 - fx) * (1 - fy) + h(xi + 1, yi) * fx * (1 - fy) + h(xi, yi + 1) * (1 - fx) * fy + h(xi + 1, yi + 1) * fx * fy) * 2 - 1

def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

def height(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    r = np.hypot(x, y)
    n = _hash_noise(x, y, 1400, 1) * 0.6 + _hash_noise(x, y, 500, 2) * 0.3 + _hash_noise(x, y, 180, 3) * 0.1
    # crater profile
    h = np.where(r < 2200, FLOOR_Z, 0.0)
    wall = FLOOR_Z + (RIM_Z - FLOOR_Z) * smooth((r - 2200) / 2600)          # 2200 -> 4800
    h = np.where((r >= 2200) & (r < 4800), wall, h)
    outer = RIM_Z * (1 - smooth((r - 4800) / 1700))                          # 4800 -> 6500
    h = np.where(r >= 4800, outer, h)
    h += n * np.where(r < 1900, 8, np.where(r < 4800, 60, 45))
    # bounding mountains (hide the world edge), with a canyon cut for the southern road
    d = np.maximum(np.abs(x), np.abs(y))
    mount = np.clip((d - 8600) * 1.1, 0, 3000) * (1 + 0.25 * _hash_noise(x, y, 900, 5))
    cut = (1 - smooth((np.abs(x) - 650) / 1700)) * smooth((-6600 - y) / 800) * smooth((y + 11900) / 1300)
    h += mount * (1 - cut)
    # southern road: flatten across, gentle ramp down the crater wall
    road = smooth((420 - np.abs(x)) / 140) * smooth((-1800 - y) / 300) * smooth((y + 10200) / 300)
    prof = np.where(r < 2200, FLOOR_Z, np.where(r < 4800, wall, outer))
    h = h * (1 - 0.5 * road) + prof * 0.5 * road
    # facility pad
    pad = smooth((1900 - np.hypot(x, y + 300)) / 250)
    h = h * (1 - pad) + FLOOR_Z * pad
    return h

def normals(H, spacing=128.0):
    gy, gx = np.gradient(H, spacing)
    N = np.dstack([-gx, -gy, np.ones_like(H)])
    return N / np.linalg.norm(N, axis=2, keepdims=True)

def slope(x, y):
    e = 32.0
    return math.hypot(float(height(x + e, y) - height(x - e, y)) / (2 * e), float(height(x, y + e) - height(x, y - e)) / (2 * e))

def tex_weights(x, y, H, N):
    """per-vertex weights for: road, scorched, gravel, rock, tundra, snowrock"""
    r = np.hypot(x, y)
    steep = 1 - N[..., 2]
    road = ((np.abs(x) < 300) & (y < -2000)).astype(float) + (np.hypot(x, y + 300) < 1500) * 0.0
    scorch = smooth((3000 - r) / 900)
    gravel = smooth((4900 - r) / 700) * (1 - scorch)
    rock = smooth((steep - 0.12) / 0.15)
    snow = smooth((H - 1800) / 600)
    tundra = np.clip(1 - scorch - gravel, 0, 1)
    W = np.stack([road, scorch, gravel, rock, tundra, snow], -1)
    W[..., 0] = np.where(road > 0, 1.0, 0)
    return W

ROAD_Y = lambda y: float(height(0, y))

def placements():
    """('prop', name, x, y, dz, angle) z is relative to ground; ('vanilla', type, edid, x, y, dz, angle); ('light', kind, x, y, dz);
    ('marker', key, x, y, dz, angle); ('spawn', x, y)"""
    P = []; a = P.append
    # arrival tunnel (door back to Skyrim) at the south end of the canyon, facing north
    a(('prop', 'bunker_entrance', 0, -10500, 0, 0)); a(('marker', 'arrival_door', 0, -10314, 0, 0))
    a(('prop', 'sign_lambda', 0, -10322, 250, 0))
    for x in (-420, 420): a(('prop', 'floodlight_tripod', x, -10000, 0, 180)); a(('light', 'flood', x, -9980, 215))
    # checkpoint across the canyon
    a(('prop', 'checkpoint_booth', -470, -7650, 0, 90)); a(('light', 'flood', -470, -7650, 240))
    for x in (-340, 340): a(('prop', 'jersey_barrier', x, -7500, 0, 0))
    for x in (-560, 560): a(('prop', 'sandbag_wall', x, -7350, 0, 0))
    a(('prop', 'floodlight_tripod', 480, -7700, 0, 200)); a(('light', 'flood', 480, -7680, 215))
    a(('marker', 'checkpoint_guard1', -150, -7400, 0, 180)); a(('marker', 'checkpoint_guard2', 160, -7420, 0, 180))
    for k, x in enumerate(range(-1300, 1400, 256)):
        if abs(x) > 700: a(('prop', 'chainlink_fence', x, -7450, 0, 0))
    # outer camp, east plains
    a(('vanilla', 'Static', 'ImperialTentLarge', 7200, 900, 0, 270)); a(('vanilla', 'Static', 'ImperialTentLarge', 7300, -400, 0, 250))
    a(('vanilla', 'Static', 'ImperialTentSmall', 6800, 1900, 0, 300)); a(('vanilla', 'Static', 'ImperialTentSmall', 7900, 1700, 0, 200))
    a(('prop', 'portable_lab', 7000, 3100, 0, 200)); a(('prop', 'generator', 7700, 2500, 0, 90)); a(('prop', 'power_cable_coil', 7500, 2600, 0, 10))
    a(('prop', 'antenna_mast', 8000, 3300, 0, 0)); a(('prop', 'satellite_dish', 6900, -1700, 0, 220))
    a(('prop', 'crate_stack', 6600, 300, 0, 80)); a(('prop', 'crate_large', 6500, 600, 0, 15)); a(('prop', 'barrel_hazard', 6700, 700, 0, 0))
    a(('vanilla', 'MoveableStatic', 'Campfire01LandBurning', 7400, 1300, 0, 0)); a(('vanilla', 'Light', 'LightCampFire01', 7400, 1300, 60, 0))
    a(('marker', 'camp_guard', 7100, 1500, 0, 270)); a(('vanilla', 'IdleMarker', 'WarmHandsIdleMarker', 7300, 1350, 0, 270))
    a(('container', 'camp_supplies', 'crate_large', 6550, 850, 0, 30, 'supplies'))
    a(('note', 'note_farmer', 6650, 400, 96, 80))
    # watch towers on the outer plains
    for ang in (45, 135, 225, 315):
        x, y = 6900 * math.sin(math.radians(ang)), 6900 * math.cos(math.radians(ang))
        a(('prop', 'guard_tower', x, y, 0, ang + 180)); a(('marker', f'tower_{ang}', x, y, 600, ang)); a(('light', 'flood', x, y, 700))
    # crater floor: facility entrance + research yard
    a(('prop', 'bunker_entrance', 0, -400, 0, 180)); a(('marker', 'facility_door', 0, -586, 0, 180))
    a(('prop', 'sign_lambda', 0, -578, 250, 180))
    for x in (-500, 500): a(('prop', 'floodlight_tripod', x, -900, 0, 0 if x < 0 else 0)); a(('light', 'flood', x, -880, 215))
    a(('marker', 'door_guard1', -260, -800, 0, 180)); a(('marker', 'door_guard2', 260, -800, 0, 180))
    a(('prop', 'meteor_rock', 1150, 900, 0, 30)); a(('prop', 'meteor_crystal_large', 1050, 820, 120, 10)); a(('light', 'cyan', 1050, 820, 350))
    a(('prop', 'portable_lab', -1150, 500, 0, 100)); a(('prop', 'generator', -900, -900, 0, 0)); a(('prop', 'crate_stack', 700, -900, 0, 10))
    a(('prop', 'test_target', 1600, -200, 0, 270)); a(('prop', 'barrel_hazard', -700, 900, 0, 0)); a(('prop', 'barrel_toxic', -620, 980, 0, 30))
    for x, y in [(-1500, -400), (1500, 300), (0, 1300)]: a(('prop', 'floodlight_tripod', x, y, 0, 0)); a(('light', 'flood', x, y + 20, 215))
    a(('marker', 'yard_scientist', 900, 400, 0, 200)); a(('vanilla', 'IdleMarker', 'SearchingTableIdleMarker', 1000, 300, 0, 30))
    # perimeter patrol loop on the plains just outside the rim
    for k in range(12):
        ang = k * 30; x, y = 6000 * math.sin(math.radians(ang)), 6000 * math.cos(math.radians(ang))
        a(('patrol', 'perimeter', k, x, y))
    # escaped specimen site: crashed headcrab canister on the western plains
    a(('canister', -7400, -1800, 0, 60)); a(('prop', 'blood_splat_floor', -7250, -1700, 2, 0)); a(('prop', 'debris_pile', -7500, -1650, 0, 40))
    a(('note', 'note_courier', -7180, -1820, 2, 90))
    for p in [(-7200, -1500), (-7600, -2100), (-7000, -2050)]: a(('spawn', p[0], p[1]))
    return [x for x in P if x]

def walkable(x, y):
    r = math.hypot(x, y)
    if r < 8300 and max(abs(x), abs(y)) < 8700 and slope(x, y) < 0.75: return True
    if abs(x) < 640 and -10300 < y < -6400: return True
    return False

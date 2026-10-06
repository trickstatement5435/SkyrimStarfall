"""Record builders (subrecord layouts per xEdit wbDefinitionsTES5.pas)."""
import struct
from .core import sub, zstr, u8, u16, i16, u32, i32, f32, fid

def obnd(b):
    b = [int(round(x)) for x in b]
    return sub('OBND', struct.pack('<6h', *[max(-32768, min(32767, v)) for v in b]))

def keywords(kws):
    if not kws: return []
    return [sub('KSIZ', u32(len(kws))), sub('KWDA', b''.join(fid(k) for k in kws))]

def model(path, sig='MODL'):
    return [sub(sig, path)] if path else []

# ---------------- simple records ----------------
def kywd(p, edid, color=(0, 0, 0)):
    return p.add('KYWD', [sub('CNAM', struct.pack('<4B', *color, 0))], edid)

def glob(p, edid, value=0.0, typ='f', constant=False):
    return p.add('GLOB', [sub('FNAM', u8(ord(typ))), sub('FLTV', f32(value))], edid, flags=0x40 if constant else 0)

def vtyp(p, edid, female=False, allow_default=False):
    return p.add('VTYP', [sub('DNAM', u8((1 if allow_default else 0) | (2 if female else 0)))], edid)

def flst(p, edid, items):
    return p.add('FLST', [sub('LNAM', fid(i)) for i in items], edid)

REACT = {'neutral': 0, 'enemy': 1, 'ally': 2, 'friend': 3}
def fact(p, edid, name='', relations=(), flags=0, hidden=True, vendor=None):
    subs = []
    if name: subs.append(sub('FULL', name))
    for f, r in relations:
        subs.append(sub('XNAM', fid(f) + i32(0) + u32(REACT[r])))
    subs.append(sub('DATA', u32(flags | (1 if hidden else 0))))
    subs.append(sub('CRVA', struct.pack('<BBHHHHHfHH', 0, 0, 0, 0, 0, 0, 0, 1.0, 0, 0)))
    subs.append(sub('RNAM', u32(0)))
    if vendor:
        subs += [sub('VEND', fid(vendor['list'])), sub('VENC', fid(vendor['container'])),
                 sub('VENV', struct.pack('<HHH2sBB2s', vendor.get('start', 0), vendor.get('end', 24), vendor.get('radius', 0), b'\0\0', 0, 0, b'\0\0'))]
    else:
        subs.append(sub('VENV', struct.pack('<HHH2sBB2s', 0, 0, 0, b'\0\0', 0, 0, b'\0\0')))
    return p.add('FACT', subs, edid)

# ---------------- armor ----------------
SLOT = {n: 1 << (n - 30) for n in range(30, 62)}
def slots(*ns):
    v = 0
    for n in ns: v |= SLOT[n]
    return v

def arma(p, edid, race, slot_mask, male_model, female_model=None, extra_races=(), weight_slider=False, armor_type=2, priority=0, first_person=None):
    subs = [sub('BOD2', u32(slot_mask) + u32(armor_type)), sub('RNAM', fid(race)),
            sub('DNAM', struct.pack('<BBBB2sB1sf', priority, priority, 2 if weight_slider else 0, 2 if weight_slider else 0, b'\0\0', 0, b'\0', 0.0))]
    subs += model(male_model, 'MOD2')
    subs += model(female_model or male_model, 'MOD3')
    if first_person:
        subs += model(first_person, 'MOD4') + model(first_person, 'MOD5')
    for r in extra_races: subs.append(sub('MODL', fid(r)))
    return p.add('ARMA', subs, edid)

def armo(p, edid, name, slot_mask, addons, race=None, bounds=(0, 0, 0, 0, 0, 0), world_model=None, armor_type=2, nonplayable=False,
         kws=(), value=0, weight=0.0, rating=0, desc=''):
    subs = [obnd(bounds)]
    if name: subs.append(sub('FULL', name))
    if world_model: subs += model(world_model, 'MOD2')
    subs.append(sub('BOD2', u32(slot_mask) + u32(armor_type)))
    if race: subs.append(sub('RNAM', fid(race)))
    subs += keywords(list(kws))
    subs.append(sub('DESC', desc))
    for a in addons: subs.append(sub('MODL', fid(a)))
    subs += [sub('DATA', struct.pack('<if', value, weight)), sub('DNAM', i32(int(rating * 100)))]
    return p.add('ARMO', subs, edid, flags=0x4 if nonplayable else 0)

def otft(p, edid, items):
    return p.add('OTFT', [sub('INAM', b''.join(fid(i) for i in items))], edid)

# ---------------- weapon ----------------
AV_ONEHANDED = 6
def weap(p, edid, name, model_path, damage, speed=1.0, reach=1.0, anim=1, impact=None, value=0, weight=0.0, nonplayable=True,
         kws=(), equip_type=None, bounds=(0, 0, 0, 0, 0, 0), crit_damage=0, stagger=0.25, sounds=None):
    flags = (0x80 | 0x08) if nonplayable else 0
    dnam = struct.pack('<B3sffHHf4sBBBBffIIfffffff4si8si4sf',
        anim, b'\0' * 3, speed, reach, flags, 0, 0.0, b'\0' * 4, 0, 255, 1, 0,
        0.0, 0.0, 0, 0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, b'\0' * 4, AV_ONEHANDED, b'\0' * 8, -1, b'\0' * 4, stagger)
    assert len(dnam) == 100
    crdt = struct.pack('<HHfB7sII', crit_damage, 0, 1.0, 0, b'\0' * 7, 0, 0)
    subs = [obnd(bounds)]
    if name: subs.append(sub('FULL', name))
    subs += model(model_path)
    if equip_type: subs.append(sub('ETYP', fid(equip_type)))
    subs += keywords(list(kws))
    subs.append(sub('DESC', ''))
    if impact: subs.append(sub('INAM', fid(impact)))
    for sig, sf in (sounds or {}).items(): subs.append(sub(sig, fid(sf)))
    subs += [sub('DATA', struct.pack('<IfH', value, weight, damage)), sub('DNAM', dnam), sub('CRDT', crdt), sub('VNAM', u32(1))]
    return p.add('WEAP', subs, edid, flags=0x4 if nonplayable else 0)

# ---------------- leveled lists ----------------
def lvln(p, edid, entries, chance_none=0, flags=0x1):
    """entries: [(level, form, count)]"""
    entries = sorted(entries, key=lambda e: e[0])
    subs = [obnd((0, 0, 0, 0, 0, 0)), sub('LVLD', u8(chance_none)), sub('LVLF', u8(flags)), sub('LLCT', u8(len(entries)))]
    for lv, f, n in entries:
        subs.append(sub('LVLO', struct.pack('<H2sIH2s', lv, b'\0\0', f, n, b'\0\0')))
    return p.add('LVLN', subs, edid)

def lvli(p, edid, entries, chance_none=0, flags=0x1):
    entries = sorted(entries, key=lambda e: e[0])
    subs = [obnd((0, 0, 0, 0, 0, 0)), sub('LVLD', u8(chance_none)), sub('LVLF', u8(flags)), sub('LLCT', u8(len(entries)))]
    for lv, f, n in entries:
        subs.append(sub('LVLO', struct.pack('<H2sIH2s', lv, b'\0\0', f, n, b'\0\0')))
    return p.add('LVLI', subs, edid)

# ---------------- NPC ----------------
ACBS_FEMALE, ACBS_ESSENTIAL, ACBS_RESPAWN, ACBS_AUTOCALC, ACBS_UNIQUE, ACBS_PCLEVELMULT, ACBS_PROTECTED, ACBS_SIMPLE = 0x1, 0x2, 0x8, 0x10, 0x20, 0x80, 0x800, 0x100000
def npc(p, edid, name, race, cls, *, level=1, pc_mult=None, calc_min=1, calc_max=0, flags=0, speed=100, health=50, magicka=0, stamina=50,
        health_off=0, factions=(), voice=None, skin=None, items=(), packages=(), kws=(), height=1.0, weight=50.0, outfit=None,
        sleep_outfit=None, aggression=0, confidence=2, energy=50, morality=3, mood=0, assistance=1, spells=(), combat_style=None,
        death_item=None, skills=None, short_name=None, attack_race=None, crime_faction=None, head_parts=(), sound_level=0):
    if pc_mult is not None:
        flags |= ACBS_PCLEVELMULT; lvl = int(pc_mult * 1000)
    else:
        lvl = level
    acbs = struct.pack('<IhhHHHHhHhH', flags, 0, 0, lvl, calc_min, calc_max, speed, 0, 0, health_off, 0)
    assert len(acbs) == 24
    subs = [obnd((-22, -14, 0, 22, 14, 128)), sub('ACBS', acbs)]
    for f, rank in factions: subs.append(sub('SNAM', fid(f) + struct.pack('<b3s', rank, b'\0\0\0')))
    if death_item: subs.append(sub('INAM', fid(death_item)))
    if voice: subs.append(sub('VTCK', fid(voice)))
    subs.append(sub('RNAM', fid(race)))
    if spells:
        subs.append(sub('SPCT', u32(len(spells))))
        for s in spells: subs.append(sub('SPLO', fid(s)))
    if skin: subs.append(sub('WNAM', fid(skin)))
    if attack_race: subs.append(sub('ATKR', fid(attack_race)))
    if items:
        subs.append(sub('COCT', u32(len(items))))
        for it, n in items: subs.append(sub('CNTO', fid(it) + i32(n)))
    subs.append(sub('AIDT', struct.pack('<BBBBBBBBIII', aggression, confidence, energy, morality, mood, assistance, 0, 0, 0, 0, 0)))
    for pk in packages: subs.append(sub('PKID', fid(pk)))
    subs += keywords(list(kws))
    subs.append(sub('CNAM', fid(cls)))
    if name: subs.append(sub('FULL', name))
    if short_name: subs.append(sub('SHRT', short_name))
    subs.append(sub('DATA', b''))
    sk = skills or [15] * 18
    subs.append(sub('DNAM', bytes(sk) + bytes(18) + struct.pack('<HHH2sfB3s', health, magicka, stamina, b'\0\0', 0.0, 0, b'\0' * 3)))
    for hp in head_parts: subs.append(sub('PNAM', fid(hp)))
    if combat_style: subs.append(sub('ZNAM', fid(combat_style)))
    subs.append(sub('NAM5', b'\xff\x00'))
    subs += [sub('NAM6', f32(height)), sub('NAM7', f32(weight)), sub('NAM8', u32(sound_level))]
    if outfit: subs.append(sub('DOFT', fid(outfit)))
    if sleep_outfit: subs.append(sub('SOFT', fid(sleep_outfit)))
    if crime_faction: subs.append(sub('CRIF', fid(crime_faction)))
    subs.append(sub('QNAM', f32(1.0) * 3))
    return p.add('NPC_', subs, edid)

# ---------------- objects ----------------
def stat(p, edid, model_path, bounds, max_angle=90.0, flags=0):
    return p.add('STAT', [obnd(bounds)] + model(model_path) + [sub('DNAM', struct.pack('<fI', max_angle, 0))], edid, flags=flags)

def mstt(p, edid, model_path, bounds, name='', sound=None):
    subs = [obnd(bounds)] + ([sub('FULL', name)] if name else []) + model(model_path) + [sub('DATA', u8(0))]
    if sound: subs.append(sub('SNAM', fid(sound)))
    return p.add('MSTT', subs, edid)

def misc(p, edid, name, model_path, bounds, value=0, weight=0.0, kws=()):
    return p.add('MISC', [obnd(bounds), sub('FULL', name)] + model(model_path) + keywords(list(kws)) + [sub('DATA', struct.pack('<if', value, weight))], edid)

def keym(p, edid, name, model_path, bounds, value=0, weight=0.0):
    return p.add('KEYM', [obnd(bounds), sub('FULL', name)] + model(model_path) + [sub('DATA', struct.pack('<if', value, weight))], edid)

def book(p, edid, name, text, model_path, bounds, value=5, weight=0.5, note=True, inv_art=None):
    # DATA: flags u8 (0x1 teaches skill, 0x2 can't be taken, 0x4 teaches spell), type u8 (0 book/tome, 255 note/scroll), unused 2, skill/spell u32, value u32, weight f32
    subs = [obnd(bounds), sub('FULL', name)] + model(model_path) + [sub('DESC', text)]
    subs += [sub('DATA', struct.pack('<BB2sIIf', 0, 255 if note else 0, b'\0\0', 0xFFFFFFFF, value, weight))]
    if inv_art: subs.append(sub('INAM', fid(inv_art)))
    subs.append(sub('CNAM', ''))
    return p.add('BOOK', subs, edid)

def cont(p, edid, name, model_path, bounds, items=(), respawn=False, open_sound=None, close_sound=None):
    subs = [obnd(bounds), sub('FULL', name)] + model(model_path)
    if items:
        subs.append(sub('COCT', u32(len(items))))
        for it, n in items: subs.append(sub('CNTO', fid(it) + i32(n)))
    subs.append(sub('DATA', struct.pack('<Bf', 0x2 if respawn else 0, 0.0)))
    if open_sound: subs.append(sub('SNAM', fid(open_sound)))
    if close_sound: subs.append(sub('QNAM', fid(close_sound)))
    return p.add('CONT', subs, edid)

def door(p, edid, name, model_path, bounds, open_sound=None, close_sound=None, flags=0):
    subs = [obnd(bounds)] + ([sub('FULL', name)] if name else []) + model(model_path)
    if open_sound: subs.append(sub('SNAM', fid(open_sound)))
    if close_sound: subs.append(sub('ANAM', fid(close_sound)))
    subs.append(sub('FNAM', u8(flags)))
    return p.add('DOOR', subs, edid)

def acti(p, edid, name, model_path, bounds, verb=None):
    subs = [obnd(bounds)] + ([sub('FULL', name)] if name else []) + model(model_path)
    if verb: subs.append(sub('RNAM', verb))
    return p.add('ACTI', subs, edid)

def ligh(p, edid, radius, color, *, fade=1.0, flags=0, fov=90.0, near_clip=0.0, flicker=(0.2, 0.2, 0.2), model_path=None, bounds=(0, 0, 0, 0, 0, 0), time=-1):
    """flags: 0x1 dynamic, 0x2 can be carried, 0x8 flicker, 0x20 off by default, 0x80 pulse, 0x400 shadow spot, 0x800 shadow hemi, 0x1000 shadow omni, 0x4000 portal strict"""
    data = struct.pack('<iI4BIffffffIf', time, radius, *color, 0, flags, 1.0, fov, near_clip, flicker[0], flicker[1], flicker[2], 0, 0.0)
    assert len(data) == 48
    subs = [obnd(bounds)] + model(model_path) + [sub('DATA', data), sub('FNAM', f32(fade))]
    return p.add('LIGH', subs, edid)

def idlm(p, edid, anims=(), timer=0.0, flags=0):
    subs = [obnd((0, 0, 0, 0, 0, 0)), sub('IDLF', u8(flags)), sub('IDLC', u8(len(anims))), sub('IDLT', f32(timer))]
    if anims: subs.append(sub('IDLA', b''.join(fid(a) for a in anims)))
    return p.add('IDLM', subs, edid)

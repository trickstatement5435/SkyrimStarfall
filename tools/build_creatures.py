"""StarfallCreatures.esp: zombies + headcrabs (skins on vanilla draugr / skeever races), factions, leveled lists,
crashed-canister static for the runtime spawner. Master: Skyrim.esm only."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from esp.core import Plugin
from esp import records as R
from vanilla import V
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = Plugin('StarfallCreatures.esp', ['Skyrim.esm'], esl=True, desc='Starfall Research Site: zombies and headcrabs.')
S = lambda typ, edid: p.sky(V(typ, edid))

DRAUGR, SKEEVER = S('Race', 'DraugrRace'), S('Race', 'SkeeverRace')
PLAYER_FACTION = S('Faction', 'PlayerFaction')
kw_crab = R.kywd(p, 'SFKwHeadcrab', (240, 160, 40))
kw_zombie = R.kywd(p, 'SFKwZombie', (160, 40, 40))
fac = R.fact(p, 'SFCreatureFaction', 'Hollow Creatures', [(PLAYER_FACTION, 'enemy')], hidden=True)
# self-alliance (XNAM to itself) is added by patching the record after we know its id
rec = p.top['FACT'][-1]
from esp.core import sub, fid, i32, u32
rec.subs.insert(2, sub('XNAM', fid(fac) + i32(0) + u32(2)))

# ---- skins ----
def skin(edid, race, mesh, slot_list):
    mask = R.slots(*slot_list)
    a = R.arma(p, edid + 'AA', race, mask, f'StarfallSite\\creatures\\{mesh}.nif')
    return R.armo(p, edid, '', mask, [a], race=race, nonplayable=True)
sk = {}
for n in ['zombie_classic', 'zombie_fast', 'zombie_poison', 'zombie_scientist']:
    sk[n] = skin('SFSkin_' + n, DRAUGR, n, (30, 32, 33))
for n in ['headcrab_classic', 'headcrab_fast', 'headcrab_black']:
    sk[n] = skin('SFSkin_' + n, SKEEVER, n, (32,))

# ---- zombie claws: an invisible one-handed weapon so draugr animations play their swipes ----
def claws(edid, dmg, speed):
    return R.weap(p, edid, 'Claws', 'StarfallSite\\creatures\\claws_empty.nif', dmg, speed=speed, reach=0.9, anim=1,
                  impact=S('ImpactDataSet', 'FXMeleeClawMedium'), equip_type=S('EquipType', 'EitherHand'), nonplayable=True)
cl = {'classic': claws('SFZombieClawsClassic', 14, 0.85), 'scientist': claws('SFZombieClawsScientist', 11, 0.9),
      'fast': claws('SFZombieClawsFast', 9, 1.45), 'poison': claws('SFZombieClawsPoison', 26, 0.7)}

SANDBOX = S('Package', 'EncCreatureSandboxEditorLocation512')
cls_z, cls_c = S('Class', 'EncClassDraugrMelee'), S('Class', 'EncClassAnimalPredator')
v_z, v_c = S('VoiceType', 'CrDraugrVoice'), S('VoiceType', 'CrSkeeverVoice')
def zombie(edid, name, skin_id, claw, level, hp, speed, height=1.0):
    return R.npc(p, edid, name, DRAUGR, cls_z, level=level, health=hp, stamina=120, speed=speed, factions=[(fac, 0)], voice=v_z,
                 skin=skin_id, items=[(claw, 1)], packages=[SANDBOX], kws=[kw_zombie], aggression=2, confidence=4, assistance=1,
                 height=height, skills=[40] * 18, combat_style=S('CombatStyle', 'csDraugrBerserker'))
def headcrab(edid, name, skin_id, level, hp, speed, height):
    return R.npc(p, edid, name, SKEEVER, cls_c, level=level, health=hp, stamina=80, speed=speed, factions=[(fac, 0)], voice=v_c,
                 skin=skin_id, packages=[SANDBOX], kws=[kw_crab], aggression=2, confidence=4, assistance=1, height=height,
                 skills=[30] * 18, combat_style=S('CombatStyle', 'csSkeever'))
z = {
    'classic': zombie('SFZombieClassic', 'Zombie', sk['zombie_classic'], cl['classic'], 6, 140, 80),
    'scientist': zombie('SFZombieScientist', 'Zombified Researcher', sk['zombie_scientist'], cl['scientist'], 4, 110, 85),
    'fast': zombie('SFZombieFast', 'Fast Zombie', sk['zombie_fast'], cl['fast'], 12, 110, 170),
    'poison': zombie('SFZombiePoison', 'Poison Zombie', sk['zombie_poison'], cl['poison'], 18, 380, 65, height=1.05),
}
h = {
    'classic': headcrab('SFHeadcrab', 'Headcrab', sk['headcrab_classic'], 2, 30, 110, 0.55),
    'fast': headcrab('SFHeadcrabFast', 'Fast Headcrab', sk['headcrab_fast'], 8, 25, 160, 0.5),
    'black': headcrab('SFHeadcrabPoison', 'Poison Headcrab', sk['headcrab_black'], 14, 55, 100, 0.6),
}
# ---- leveled lists ----
L = {}
L['zombie'] = R.lvln(p, 'SFLvlZombie', [(1, z['classic'], 1), (1, z['scientist'], 1), (10, z['fast'], 1), (16, z['poison'], 1)])
L['zombie_weak'] = R.lvln(p, 'SFLvlZombieWeak', [(1, z['classic'], 1), (1, z['scientist'], 1)])
L['headcrab'] = R.lvln(p, 'SFLvlHeadcrab', [(1, h['classic'], 1), (6, h['fast'], 1), (12, h['black'], 1)])
L['outbreak'] = R.lvln(p, 'SFLvlOutbreak', [(1, L['zombie'], 1), (1, L['headcrab'], 1), (1, L['headcrab'], 1)])
L['poison'] = R.lvln(p, 'SFLvlPoisonZombie', [(1, z['poison'], 1)])
L['fast'] = R.lvln(p, 'SFLvlFastZombie', [(1, z['fast'], 1)])
# ---- crashed canister (placed by the runtime spawner next to some exterior encounters) ----
b = json.load(open(f'{ROOT}/build/src_props_bounds.json'))
canister = R.stat(p, 'SFHeadcrabCanister', 'StarfallSite\\props\\headcrab_canister.nif', b['headcrab_canister'])

size = p.write(f'{ROOT}/data/StarfallCreatures.esp')
ids = {k: hex(v & 0xFFFFFF) for k, v in p.edids.items()}
json.dump(ids, open(f'{ROOT}/build/creature_ids.json', 'w'), indent=1)
print('wrote StarfallCreatures.esp', size, 'bytes,', len(ids), 'records')

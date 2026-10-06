"""Starfall Research Site interior layouts (main complex + sealed Containment Wing B).
Coordinates: Skyrim units, +Y north. Angles in degrees: 0 = facing north (+Y), 90 = east, 180 = south, 270 = west.
Each placement: ('prop', name, x, y, z, angle) for kit props, ('vanilla', EDID-type, EDID, x, y, z, angle),
('light', kind, x, y, z), ('marker', key, x, y, z, angle), ('note', note_id, x, y, z, angle), ('container', key, prop, x, y, z, angle, loot)."""
from building import Building

def main_complex():
    b = Building('facility')
    b.room('lobby', -448, 64, 448, 960, 320, floor='floor_tile', wall='concrete')
    b.room('corridor', -128, 1024, 128, 3520, 300, floor='concrete_plain', wall='concrete')
    b.room('office', -1088, 1024, -192, 1728, 300, floor='floor_tile', wall='concrete')
    b.room('lab_a', -1344, 1792, -192, 2752, 320, floor='floor_tile', wall='concrete')
    b.room('medlab', -1344, 2816, -192, 3520, 320, floor='floor_tile', wall='concrete')
    b.room('quarters', 192, 1024, 1088, 1728, 300, floor='concrete_plain', wall='concrete')
    b.room('mess', 192, 1792, 1088, 2496, 300, floor='floor_tile', wall='concrete')
    b.room('engineering', 192, 2560, 1344, 3520, 380, floor='diamond_plate', wall='concrete_dark')
    b.room('observation', -448, 3584, 448, 4032, 300, floor='floor_tile', wall='concrete')
    b.room('chamber', -1024, 4096, 1024, 5568, 760, floor='diamond_plate', wall='concrete_dark', ceil='metal_dark')
    b.room('storage', -1344, 3584, -512, 4032, 300, floor='concrete_plain', wall='concrete')
    b.room('eastcorr', 512, 3712, 1024, 3904, 300, floor='concrete_plain', wall='concrete')
    b.room('containment', 1088, 3584, 2112, 4544, 340, floor='diamond_plate', wall='concrete_dark')
    # doorways (cut through the 64-wide wall strips)
    b.door(-128, 960, 128, 1024)                      # lobby -> corridor
    b.door(-192, 1280, -128, 1472)                    # corridor -> office
    b.door(-192, 2176, -128, 2368)                    # corridor -> lab A
    b.door(-192, 3072, -128, 3264)                    # corridor -> med lab
    b.door(128, 1280, 192, 1472)                      # corridor -> quarters
    b.door(128, 2048, 192, 2240)                      # corridor -> mess
    b.door(128, 2944, 192, 3136)                      # corridor -> engineering
    b.door(-128, 3520, 128, 3584)                     # corridor -> observation
    b.door(192, 4032, 384, 4096)                      # observation -> test chamber
    b.door(-512, 3712, -448, 3904)                    # observation -> storage
    b.door(448, 3712, 512, 3904)                      # observation -> east corridor
    b.door(1024, 3712, 1088, 3904)                    # east corridor -> containment
    b.window(-384, 4032, 128, 4096, 100, 240)         # observation window into the chamber
    return b

def wing_b():
    b = Building('wingb')
    b.room('hall', -256, 64, 256, 1600, 300, floor='concrete_plain', wall='concrete_dark')
    b.room('speclab', -1280, 640, -320, 1600, 320, floor='floor_tile', wall='concrete_dark')
    b.room('pens', 320, 640, 1280, 1600, 300, floor='diamond_plate', wall='concrete_dark')
    b.room('ruskoffice', -768, 1664, 768, 2240, 300, floor='floor_tile', wall='concrete_dark')
    b.door(-320, 1024, -256, 1216)
    b.door(256, 1024, 320, 1216)
    b.door(-128, 1600, 128, 1664)
    return b

# ---------------- placements ----------------
# Lights: kind 'fluor' = ceiling fluorescent fixture + light ref, 'red' = red emergency light (no fixture), 'green' = tank glow,
#         'cyan' = crystal glow, 'warm' = desk lamp tone
def main_props():
    P = []
    a = P.append
    # ---- lobby / security checkpoint ----
    a(('prop', 'sign_lambda', 0, 958, 200, 180)); a(('prop', 'sign_restricted', -300, 958, 170, 180))
    a(('prop', 'jersey_barrier', -250, 520, 0, 0)); a(('prop', 'jersey_barrier', 250, 520, 0, 0))
    a(('prop', 'desk_terminal', 280, 300, 0, 270)); a(('prop', 'console_bank', -380, 300, 0, 90))
    a(('prop', 'locker', 410, 800, 0, 270)); a(('prop', 'locker', 410, 860, 0, 270))
    a(('prop', 'poster_safety', -446, 720, 150, 90)); a(('prop', 'crate_stack', -330, 120 + 60, 0, 0))
    a(('marker', 'lobby_guard1', -120, 600, 0, 180)); a(('marker', 'lobby_guard2', 120, 600, 0, 180)); a(('marker', 'moran_post', 230, 300, 0, 90))
    a(('vanilla', 'Furniture', 'CommonChair01F', 330, 300, 0, 270))
    a(('note', 'note_pamphlet', 280, 290, 52, 270))
    for x, y in [(-224, 320), (224, 320), (-224, 704), (224, 704)]: a(('light', 'fluor', x, y, 320))
    # ---- corridor ----
    for y in range(1280, 3520, 512): a(('light', 'fluor', 0, y, 300))
    a(('prop', 'pipe_cluster_wall', -126, 1900, 210, 90)); a(('prop', 'pipe_cluster_wall', 126, 2600, 210, 270))
    a(('prop', 'sign_biohazard', 126, 3300, 160, 270)); a(('prop', 'poster_safety', -126, 2900, 140, 90))
    a(('marker', 'corridor_patrol', 0, 1150, 0, 0)); a(('marker', 'corridor_patrol', 0, 2300, 0, 0)); a(('marker', 'corridor_patrol', 0, 3400, 0, 0))
    a(('prop', 'blood_splat_floor', 40, 3150, 0, 30))
    # ---- Kast's office ----
    a(('prop', 'desk_terminal', -640, 1560, 0, 180)); a(('vanilla', 'Furniture', 'CommonChair01F', -640, 1620, 0, 180))
    a(('prop', 'shelf_metal_stocked', -1020, 1300, 0, 90)); a(('prop', 'shelf_metal_stocked', -1020, 1450, 0, 90))
    a(('prop', 'filing_cabinet', -230, 1650, 0, 270)); a(('prop', 'whiteboard', -640, 1726, 0, 180))
    a(('prop', 'sign_lambda', -1086, 1600, 200, 90)); a(('note', 'note_kast_memo', -640, 1550, 52, 180))
    a(('marker', 'kast_work', -640, 1420, 0, 0)); a(('vanilla', 'IdleMarker', 'StudyMarker', -900, 1100, 0, 270))
    a(('light', 'fluor', -640, 1250, 300)); a(('light', 'warm', -640, 1560, 140))
    # ---- Lab A (Hale: crystal + manipulator research) ----
    for i, y in enumerate([1950, 2250, 2550]):
        a(('prop', 'lab_table', -1000, y, 0, 90)); a(('prop', 'terminal_standalone', -1000, y + 10, 55, 90))
    a(('prop', 'console_bank', -1290, 2250, 0, 90)); a(('prop', 'server_rack', -1300, 1880, 0, 90)); a(('prop', 'server_rack', -1300, 2620, 0, 90))
    a(('prop', 'meteor_crystal_large', -520, 2600, 0, 30)); a(('prop', 'test_platform', -520, 2600, 0, 0))
    a(('prop', 'shelf_metal_stocked', -260, 1860, 0, 270)); a(('prop', 'whiteboard', -700, 2750, 0, 180))
    a(('prop', 'specimen_table', -560, 1950, 0, 0)); a(('note', 'note_hale_desk', -1000, 2240, 56, 90))
    a(('vanilla', 'IdleMarker', 'SearchingTableIdleMarker', -900, 1950, 0, 270)); a(('vanilla', 'IdleMarker', 'StudyMarker', -620, 2420, 0, 135))
    a(('marker', 'hale_work', -800, 2250, 0, 270))
    for x, y in [(-1000, 2000), (-1000, 2500), (-500, 2100), (-500, 2560)]: a(('light', 'fluor', x, y, 320))
    a(('light', 'cyan', -520, 2600, 250))
    # ---- Med lab (Rusk: xenobiology) ----
    for x in (-1250, -1080, -910):
        a(('prop', 'containment_tank', x, 3420, 0, 180)); a(('vanilla_crab', x, 3420, 60, 180))
    a(('prop', 'specimen_table', -800, 3000, 0, 0)); a(('prop', 'specimen_table', -560, 3000, 0, 0))
    a(('prop', 'headcrab_prep', -680, 3250, 0, 0)); a(('prop', 'lab_table', -400, 3250, 0, 90))
    a(('prop', 'desk_terminal', -300, 2900, 0, 270)); a(('prop', 'filing_cabinet', -1300, 2900, 0, 90))
    a(('prop', 'blood_splat_floor', -680, 3150, 0, 0)); a(('note', 'note_rusk_specimens', -300, 2890, 52, 270))
    a(('vanilla', 'IdleMarker', 'AlchemyLabIdleMarker', -680, 3150, 0, 0)); a(('vanilla', 'IdleMarker', 'SearchingTableIdleMarker', -800, 2930, 0, 0))
    a(('marker', 'rusk_work', -600, 3100, 0, 0))
    for x, y in [(-1000, 3000), (-1000, 3350), (-500, 3000), (-500, 3350)]: a(('light', 'fluor', x, y, 320))
    for x in (-1250, -1080, -910): a(('light', 'green', x, 3420, 180))
    # ---- quarters ----
    beds = []
    for k, x in enumerate([300, 520, 740, 960]):
        a(('vanilla', 'Furniture', 'DweFurnitureBedSingle01', x, 1600, 0, 180)); beds.append(('bed', k, x, 1600))
        a(('prop', 'locker', x + 90, 1690, 0, 180))
    for k, x in enumerate([300, 520, 740]):
        a(('vanilla', 'Furniture', 'DweFurnitureBedSingle01', x, 1150, 0, 0)); beds.append(('bed', 4 + k, x, 1150))
    a(('prop', 'poster_safety', 1086, 1400, 150, 270)); a(('note', 'note_guard_roster', 960, 1150, 40, 0))
    a(('marker', 'sci_home', 640, 1380, 0, 0))
    for x, y in [(450, 1250), (450, 1550), (850, 1250), (850, 1550)]: a(('light', 'fluor', x, y, 300))
    # ---- mess ----
    for x, y in [(450, 1950), (450, 2250), (850, 1950), (850, 2250)]:
        a(('vanilla', 'Furniture', 'NorTableTwoBenches', x, y, 0, 90))
    a(('prop', 'shelf_metal_stocked', 1030, 2400, 0, 270)); a(('prop', 'crate_stack', 1000, 1880, 0, 270))
    a(('note', 'note_wuunferth_receipt', 450, 1950, 40, 90)); a(('vanilla', 'IdleMarker', 'TavernDrinkingMarker', 640, 2420, 0, 180))
    for x, y in [(450, 2100), (850, 2100), (640, 2400)]: a(('light', 'fluor', x, y, 300))
    # ---- engineering (Venn) ----
    a(('prop', 'generator', 1150, 3300, 0, 270)); a(('prop', 'generator', 1150, 2850, 0, 270))
    a(('prop', 'console_bank', 640, 3460, 0, 180)); a(('prop', 'server_rack', 300, 3450, 0, 180)); a(('prop', 'server_rack', 380, 3450, 0, 180))
    a(('prop', 'pipe_cluster_wall', 194, 2800, 240, 90)); a(('prop', 'pipe_cluster_wall', 194, 3200, 240, 90))
    a(('prop', 'shelf_metal_stocked', 640, 2620, 0, 0)); a(('prop', 'power_cable_coil', 760, 3000, 0, 40))
    a(('prop', 'barrel_hazard', 1280, 2620, 0, 0)); a(('prop', 'barrel_hazard', 1220, 2640, 0, 0)); a(('prop', 'crate_large', 300, 2650, 0, 10))
    a(('note', 'note_venn_requisition', 640, 3440, 112, 180)); a(('vanilla', 'IdleMarker', 'SearchingTableIdleMarker', 640, 3380, 0, 0))
    a(('marker', 'venn_work', 800, 3100, 0, 90))
    for x, y in [(450, 2800), (450, 3250), (950, 2800), (950, 3250)]: a(('light', 'fluor', x, y, 380))
    # ---- observation ----
    a(('prop', 'console_bank', -128, 3990, 0, 0)); a(('prop', 'desk_terminal', 260, 3700, 0, 90))
    a(('prop', 'sign_testchamber', 288, 4030, 260, 180)); a(('note', 'note_shift_log', -128, 3990, 112, 0))
    a(('vanilla', 'IdleMarker', 'LookFarMarker', -200, 3900, 0, 0)); a(('marker', 'obs_guard', 300, 3640, 0, 0))
    for x in (-224, 224): a(('light', 'fluor', x, 3800, 300))
    # ---- test chamber ----
    a(('prop', 'test_platform', 0, 4900, 0, 0)); a(('prop', 'meteor_crystal_large', 0, 4900, 20, 0))
    for x, y in [(-700, 5300), (-350, 5400), (350, 5400), (700, 5300), (-800, 4700), (800, 4700)]: a(('prop', 'test_target', x, y, 0, 180))
    a(('prop', 'catwalk_stairs', 900, 4400, 0, 0))
    for x in (-700, 0, 700):
        for y in (4500, 5200): a(('light', 'fluor', x, y, 760))
    a(('light', 'cyan', 0, 4900, 400)); a(('prop', 'blood_splat_floor', -300, 4400, 0, 0)); a(('prop', 'debris_pile', 800, 5400, 0, 200)); a(('prop', 'broken_terminal', -600, 4300, 0, 30)); a(('note', 'note_cascade_log', -600, 4280, 2, 30))
    a(('prop', 'sign_biohazard', -1022, 4800, 200, 90))
    # ---- storage / armory ----
    a(('prop', 'crate_stack', -1200, 3700, 0, 90)); a(('prop', 'crate_large', -1250, 3950, 0, 0)); a(('prop', 'crate_small', -1150, 3960, 0, 20))
    a(('prop', 'shelf_metal_stocked', -800, 3620, 0, 0)); a(('prop', 'shelf_metal_stocked', -950, 3620, 0, 0))
    a(('container', 'armory', 'locker', -600, 3990, 0, 180, 'armory'))
    a(('container', 'supply1', 'crate_large', -1000, 3960, 0, 0, 'supplies'))
    for x in (-1100, -750): a(('light', 'fluor', x, 3800, 300))
    # ---- east corridor + containment wing A ----
    a(('prop', 'sign_restricted', 1022, 3900, 200, 270)); a(('light', 'fluor', 768, 3808, 300))
    for x in (1250, 1450, 1650, 1850):
        a(('prop', 'containment_tank', x, 4460, 0, 180)); a(('vanilla_crab', x, 4460, 60, 180)); a(('light', 'green', x, 4460, 180))
    a(('prop', 'containment_tank_broken', 2000, 3700, 0, 270)); a(('prop', 'blood_splat_floor', 1900, 3800, 0, 45)); a(('prop', 'blood_splat_wall', 2110, 3850, 120, 270))
    a(('prop', 'console_bank', 1150, 4000, 0, 90)); a(('prop', 'sign_biohazard', 2110, 4300, 180, 270))
    a(('prop', 'sign_restricted', 2110, 4064, 290, 270)); a(('prop', 'jersey_barrier', 1980, 4064, 0, 90))
    a(('marker', 'wingb_guard', 1900, 4064, 0, 90)); a(('marker', 'containment_guard', 1300, 3700, 0, 0))
    for x, y in [(1350, 3800), (1850, 3800), (1350, 4250), (1850, 4250)]: a(('light', 'fluor', x, y, 340))
    a(('light', 'red', 2050, 4064, 280))
    return P

def wingb_props():
    P = []; a = P.append
    for y in (300, 800, 1300): a(('light', 'red', 0, y, 280))
    a(('prop', 'debris_pile', 120, 500, 0, 30)); a(('prop', 'overturned_table', -150, 900, 0, 80)); a(('prop', 'blood_splat_floor', 0, 700, 0, 0))
    a(('prop', 'blood_splat_wall', -254, 1200, 120, 90)); a(('prop', 'sign_biohazard', 254, 400, 170, 270)); a(('prop', 'crate_small', 180, 1400, 0, 15))
    for x in (-1150, -950, -750):
        a(('prop', 'containment_tank_broken', x, 1500, 0, 180))
    a(('prop', 'lab_table', -800, 900, 0, 0)); a(('prop', 'broken_terminal', -800, 900, 55, 20)); a(('prop', 'specimen_table', -500, 1100, 0, 90))
    a(('prop', 'blood_splat_floor', -900, 1200, 0, 60)); a(('light', 'green', -950, 1450, 160)); a(('light', 'red', -800, 900, 280))
    for x in (450, 750, 1050):
        a(('prop', 'chainlink_fence', x, 1100, 0, 0))
    a(('prop', 'debris_pile', 900, 800, 0, 120)); a(('prop', 'barrel_toxic', 1200, 700, 0, 0)); a(('light', 'red', 800, 1000, 280))
    a(('prop', 'desk_terminal', 0, 2150, 0, 180)); a(('prop', 'filing_cabinet', -700, 2180, 0, 180)); a(('prop', 'overturned_table', 400, 1900, 0, 10))
    a(('prop', 'blood_splat_floor', 200, 2000, 0, 0)); a(('light', 'warm', 0, 2100, 150)); a(('light', 'red', -400, 1900, 280))
    a(('item', 'journal', 0, 2140, 52, 180))
    a(('note', 'note_evac_order', -150, 300, 0.5, 0)); a(('note', 'note_letter_unsent', 300, 2150, 52, 180)); a(('prop', 'lab_table', 300, 2150, 0, 0))
    # fixed encounter spots
    for p in [(-900, 1000), (-600, 1300), (700, 900), (1000, 1300), (0, 1200), (-300, 1900), (300, 1800)]:
        a(('spawn', p[0], p[1]))
    return P

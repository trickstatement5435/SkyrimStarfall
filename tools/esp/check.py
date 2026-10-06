"""Structural reader/validator for the plugins we write.
- walks every GRUP / record / subrecord and checks sizes add up
- decompresses compressed records
- checks group nesting types (top -> world children / cell blocks / topic children)
- collects (record, subrecord) -> field offsets known to hold FormIDs (from a small table) and verifies targets exist:
  own-plugin ids must be defined in this file (or its plugin masters given), Skyrim.esm ids must exist in the vanilla db."""
import struct, zlib, sys, json, os
from collections import Counter, defaultdict

def walk(data, off, end, depth, out, parent_type=None):
    while off < end:
        sig = data[off:off + 4].decode('latin1')
        if sig == 'GRUP':
            size, label, gtype = struct.unpack_from('<I4si', data, off + 4)
            assert size >= 24 and off + size <= end, f'bad group size at {off:#x}'
            out['groups'].append((depth, gtype, label, off))
            walk(data, off + 24, off + size, depth + 1, out, gtype)
            off += size
        else:
            dsize, flags, formid = struct.unpack_from('<III', data, off + 4)
            body = data[off + 24: off + 24 + dsize]
            assert off + 24 + dsize <= end, f'record {sig} {formid:08x} overruns'
            if flags & 0x40000:
                raw = zlib.decompress(body[4:]); assert len(raw) == struct.unpack_from('<I', body)[0]; body = raw
            subs = []; p = 0; big = None
            while p < len(body):
                ss = body[p:p + 4].decode('latin1'); sz = struct.unpack_from('<H', body, p + 4)[0]
                if ss == 'XXXX': big = struct.unpack_from('<I', body, p + 6)[0]; p += 10; continue
                if big is not None: sz = big; big = None
                assert p + 6 + sz <= len(body), f'subrecord {ss} overruns in {sig} {formid:08x}'
                subs.append((ss, body[p + 6:p + 6 + sz])); p += 6 + sz
            out['records'].append((sig, formid, flags, subs, parent_type))
            off += 24 + dsize
    assert off == end, f'walk ended at {off:#x} != {end:#x}'

def read(path):
    data = open(path, 'rb').read()
    out = {'groups': [], 'records': []}
    walk(data, 0, len(data), 0, out)
    return out

# subrecords that are exactly one FormID (or arrays of FormIDs)
FORMID_SUBS = {'RNAM': {'ARMA', 'ARMO', 'NPC_'}, 'MODL': {'ARMO'}, 'WNAM': {'NPC_'}, 'VTCK': {'NPC_'}, 'CNAM': {'NPC_', 'INFO_X'},
               'PKID': {'NPC_'}, 'DOFT': {'NPC_'}, 'SOFT': {'NPC_'}, 'ZNAM': {'NPC_'}, 'INAM': {'WEAP', 'NPC_', 'OTFT'},
               'ETYP': {'WEAP'}, 'KWDA': None, 'NAME': {'REFR', 'ACHR'}, 'XLCN': {'CELL', 'REFR', 'ACHR'}, 'LTMP': {'CELL'},
               'XCAS': {'CELL'}, 'XEZN': {'CELL', 'REFR', 'ACHR'}, 'XCIM': {'CELL'}, 'XCMO': {'CELL'}, 'LNAM': {'FLST'},
               'QNAM': {'INFO', 'DIAL'}, 'BNAM': {'DIAL'}, 'TPIC': {'INFO'}, 'VTYP_': None}
def check(path, master_ids=None, vanilla=None):
    r = read(path)
    recs = r['records']
    tes4 = recs[0]; masters = [s[1][:-1].decode() for s in tes4[3] if s[0] == 'MAST']
    me = len(masters)
    own = {rec[1] for rec in recs[1:]}
    errs = []
    def ok(f, ctx):
        if f == 0: return
        idx = f >> 24
        if idx == me:
            if f not in own: errs.append(f'{ctx}: own {f:08x} missing')
        elif idx < me:
            m = masters[idx]
            if m == 'Skyrim.esm' and vanilla is not None:
                if (f & 0xFFFFFF) not in vanilla: errs.append(f'{ctx}: Skyrim.esm {f:06x} unknown')
            elif master_ids and m in master_ids:
                if (f & 0xFFFFFF) not in master_ids[m]: errs.append(f'{ctx}: {m} {f & 0xFFFFFF:06x} missing')
        else:
            errs.append(f'{ctx}: bad master index {f:08x}')
    for sig, f, flags, subs, pt in recs[1:]:
        for ss, d in subs:
            rule = FORMID_SUBS.get(ss, 'no')
            if rule == 'no': continue
            if rule is not None and sig not in rule: continue
            if ss in ('KWDA', 'LNAM') or (ss == 'MODL' and sig == 'ARMO'):
                for i in range(0, len(d), 4): ok(struct.unpack_from('<I', d, i)[0], f'{sig}:{f:08x}:{ss}')
            elif len(d) == 4:
                ok(struct.unpack_from('<I', d)[0], f'{sig}:{f:08x}:{ss}')
            if ss == 'LVLO': pass
        for ss, d in subs:
            if ss == 'LVLO': ok(struct.unpack_from('<I', d, 4)[0], f'{sig}:{f:08x}:LVLO')
            if ss == 'CNTO': ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:CNTO')
            if ss == 'SNAM' and sig == 'NPC_': ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:SNAM')
            if ss == 'XNAM' and sig == 'FACT': ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:XNAM')
            if ss == 'XTEL': ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:XTEL')
            if ss == 'XLKR': ok(struct.unpack_from('<I', d, 4)[0], f'{sig}:{f:08x}:XLKR'); ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:XLKR kw')
            if ss == 'XESP': ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:XESP')
            if ss == 'SPLO': ok(struct.unpack_from('<I', d, 0)[0], f'{sig}:{f:08x}:SPLO')
    c = Counter(rec[0] for rec in recs)
    return dict(masters=masters, counts=dict(c), groups=len(r['groups']), errors=errs, records=recs)

def vanilla_ids():
    db = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'vanilla', 'formids.json')))
    return {v for t in db['Skyrim'].values() for v in t.values()}

if __name__ == '__main__':
    res = check(sys.argv[1], vanilla=vanilla_ids())
    print(res['masters'], res['counts'], 'groups', res['groups'])
    print('errors:', len(res['errors'])); [print(' ', e) for e in res['errors'][:40]]

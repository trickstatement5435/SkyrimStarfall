"""Minimal Skyrim SE plugin writer (record layouts follow xEdit's wbDefinitionsTES5.pas).

Plugin collects records into top-level groups, worldspaces (with exterior blocks/sub-blocks), interior cells,
and dialogue topics with their INFO children, then writes a valid TES4 file."""
import struct, zlib
from collections import OrderedDict

FORM_VERSION = 44
GROUP_ORDER = ['GMST', 'KYWD', 'LCRT', 'AACT', 'TXST', 'GLOB', 'CLAS', 'FACT', 'HDPT', 'HAIR', 'EYES', 'RACE', 'SOUN', 'ASPC',
               'MGEF', 'SCPT', 'LTEX', 'ENCH', 'SPEL', 'SCRL', 'ACTI', 'TACT', 'ARMO', 'BOOK', 'CONT', 'DOOR', 'INGR', 'LIGH',
               'MISC', 'APPA', 'STAT', 'SCOL', 'MSTT', 'PWAT', 'GRAS', 'TREE', 'CLDC', 'FLOR', 'FURN', 'WEAP', 'AMMO', 'NPC_',
               'LVLN', 'KEYM', 'ALCH', 'IDLM', 'COBJ', 'PROJ', 'HAZD', 'SLGM', 'LVLI', 'WTHR', 'CLMT', 'SPGD', 'RFCT', 'REGN',
               'NAVI', 'CELL', 'WRLD', 'DIAL', 'QUST', 'IDLE', 'PACK', 'CSTY', 'LSCR', 'LVSP', 'ANIO', 'WATR', 'EFSH', 'EXPL',
               'DEBR', 'IMGS', 'IMAD', 'FLST', 'PERK', 'BPTD', 'ADDN', 'AVIF', 'CAMS', 'CPTH', 'VTYP', 'MATT', 'IPCT', 'IPDS',
               'ARMA', 'ECZN', 'LCTN', 'MESG', 'RGDL', 'DOBJ', 'LGTM', 'MUSC', 'FSTP', 'FSTS', 'SMBN', 'SMQN', 'SMEN', 'DLBR',
               'MUST', 'DLVW', 'WOOP', 'SHOU', 'EQUP', 'RELA', 'SCEN', 'ASTP', 'OTFT', 'ARTO', 'MATO', 'MOVT', 'SNDR', 'DUAL',
               'SNCT', 'SOPM', 'COLL', 'CLFM', 'REVB']

def zstr(s):
    return s.encode('cp1252', errors='replace') + b'\0'

def sub(sig, data):
    if isinstance(data, str): data = zstr(data)
    assert len(sig) == 4, sig
    if len(data) >= 0x10000:   # oversized subrecord: XXXX with the real size, then the field with size 0
        return b'XXXX' + struct.pack('<HI', 4, len(data)) + sig.encode() + struct.pack('<H', 0) + data
    return sig.encode() + struct.pack('<H', len(data)) + data

def u8(v): return struct.pack('<B', v)
def u16(v): return struct.pack('<H', v)
def i16(v): return struct.pack('<h', v)
def u32(v): return struct.pack('<I', v & 0xFFFFFFFF)
def i32(v): return struct.pack('<i', v)
def f32(v): return struct.pack('<f', v)
def fid(v): return struct.pack('<I', v or 0)

class Record:
    def __init__(self, sig, formid, subs, flags=0, edid=None):
        self.sig, self.formid, self.subs, self.flags, self.edid = sig, formid, list(subs), flags, edid
    def bytes(self):
        data = b''.join(self.subs)
        flags = self.flags
        if flags & 0x00040000:  # compressed
            comp = zlib.compress(data, 9)
            data = struct.pack('<I', len(data)) + comp
        return self.sig.encode() + struct.pack('<IIIIHH', len(data), flags, self.formid, 0, FORM_VERSION, 0) + data

def group(label, gtype, children):
    body = b''.join(c if isinstance(c, (bytes, bytearray)) else c.bytes() for c in children)
    if isinstance(label, str): lab = label.encode()
    elif isinstance(label, bytes): lab = label
    else: lab = struct.pack('<I', label & 0xFFFFFFFF)
    return b'GRUP' + struct.pack('<I4siHHHH', 24 + len(body), lab, gtype, 0, 0, 0, 0) + body

class Plugin:
    def __init__(self, name, masters, esl=False, author='Ashton', desc=''):
        self.name, self.masters, self.esl, self.author, self.desc = name, list(masters), esl, author, desc
        self.next_obj = 0x800
        self.top = OrderedDict()           # sig -> [Record]
        self.edids = {}                    # edid -> formid (own records)
        self.worlds = OrderedDict()        # wrld fid -> dict(record, persistent_cell, persistent_refs, cells{(x,y): dict(record, temp=[], pers=[])})
        self.interiors = OrderedDict()     # cell fid -> dict(record, pers=[], temp=[])
        self.topics = OrderedDict()        # dial fid -> dict(record, infos=[])
        self.overrides = []                # (sig, Record) override of master records in top groups
        self.count = 0
    # ---- ids ----
    @property
    def self_index(self): return len(self.masters)
    def new_id(self):
        v = (self.self_index << 24) | self.next_obj; self.next_obj += 1; return v
    def m(self, master, local):
        """FormID of a record defined in a master file."""
        return (self.masters.index(master) << 24) | (local & 0xFFFFFF)
    def sky(self, local): return self.m('Skyrim.esm', local)
    def id_of(self, edid): return self.edids[edid]
    # ---- add ----
    def add(self, sig, subs, edid=None, flags=0, formid=None):
        formid = formid or self.new_id()
        if edid:
            assert edid not in self.edids, f'duplicate edid {edid}'
            self.edids[edid] = formid
            subs = [sub('EDID', edid)] + list(subs)
        r = Record(sig, formid, subs, flags, edid)
        self.top.setdefault(sig, []).append(r)
        return formid
    def reserve(self, edid=None):
        f = self.new_id()
        if edid: self.edids[edid] = f
        return f
    def add_override(self, sig, formid, subs, flags=0):
        r = Record(sig, formid, subs, flags)
        self.top.setdefault(sig, []).append(r); return formid
    # ---- write ----
    def _top_group(self, sig):
        if sig == 'CELL': return self._interior_group()
        if sig == 'WRLD': return self._world_group()
        if sig == 'DIAL': return self._dial_group()
        recs = self.top.get(sig, [])
        return group(sig, 0, recs) if recs else b''
    def _interior_group(self):
        if not self.interiors: return b''
        blocks = {}
        for cfid, c in self.interiors.items():
            obj = cfid & 0xFFFFFF
            blocks.setdefault(obj % 10, {}).setdefault((obj // 10) % 10, []).append((cfid, c))
        out = []
        for b in sorted(blocks):
            subs = []
            for sb in sorted(blocks[b]):
                items = []
                for cfid, c in blocks[b][sb]:
                    items.append(c['record'].bytes()); self.count += 1
                    items.append(self._cell_children(cfid, c))
                subs.append(group(sb, 3, items))
            out.append(group(b, 2, subs))
        return group('CELL', 0, out)
    def _cell_children(self, cfid, c):
        kids = []
        if c.get('pers'): kids.append(group(cfid, 8, c['pers'])); self.count += len(c['pers'])
        if c.get('temp'): kids.append(group(cfid, 9, c['temp'])); self.count += len(c['temp'])
        return group(cfid, 6, kids) if kids else b''
    def _world_group(self):
        if not self.worlds: return b''
        out = []
        for wfid, w in self.worlds.items():
            if w.get('record') is not None:
                out.append(w['record'].bytes()); self.count += 1
            kids = []
            if w.get('pcell') is not None:
                pc = w['pcell']
                kids.append(pc['record'].bytes()); self.count += 1
                kids.append(self._cell_children(pc['record'].formid, pc))
            blocks = {}
            for (x, y), c in w.get('cells', {}).items():
                bx, by = x // 32, y // 32; sx, sy = x // 8, y // 8
                blocks.setdefault((bx, by), {}).setdefault((sx, sy), []).append(c)
            for (bx, by) in sorted(blocks):
                subs = []
                for (sx, sy) in sorted(blocks[(bx, by)]):
                    items = []
                    for c in blocks[(bx, by)][(sx, sy)]:
                        items.append(c['record'].bytes()); self.count += 1
                        items.append(self._cell_children(c['record'].formid, c))
                    subs.append(group(struct.pack('<hh', sy, sx), 5, items))
                kids.append(group(struct.pack('<hh', by, bx), 4, subs))
            if kids: out.append(group(wfid, 1, kids))
        return group('WRLD', 0, out)
    def _dial_group(self):
        if not self.topics: return b''
        out = []
        for dfid, d in self.topics.items():
            d['record'].subs = [x for x in d['record'].subs if x[:4] != b'TIFC'] + [sub('TIFC', u32(len(d['infos'])))]
            out.append(d['record'].bytes()); self.count += 1
            if d['infos']:
                out.append(group(dfid, 7, d['infos'])); self.count += len(d['infos'])
        return group('DIAL', 0, out)
    def write(self, path):
        self.count = 0
        body = []
        sigs = list(GROUP_ORDER) + [s for s in self.top if s not in GROUP_ORDER]
        for sig in sigs:
            g = self._top_group(sig)
            if g:
                if sig not in ('CELL', 'WRLD', 'DIAL'): self.count += len(self.top.get(sig, []))
                body.append(g)
        ngroups = sum(blob.count(b'GRUP') for blob in [b''.join(body)])  # approximate: every group header
        hedr = struct.pack('<fII', 1.7, self.count + ngroups, self.next_obj)
        subs = [sub('HEDR', hedr), sub('CNAM', self.author)]
        if self.desc: subs.append(sub('SNAM', self.desc))
        for mname in self.masters:
            subs += [sub('MAST', mname), sub('DATA', struct.pack('<Q', 0))]
        flags = 0x200 if self.esl else 0
        tes4 = Record('TES4', 0, subs, flags).bytes()
        tes4 = tes4[:20] + struct.pack('<H', FORM_VERSION) + tes4[22:]
        data = tes4 + b''.join(body)
        open(path, 'wb').write(data)
        return len(data)

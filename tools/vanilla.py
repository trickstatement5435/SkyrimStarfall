"""Vanilla FormIDs by EditorID (from Mutagen.Bethesda.FormKeys, generated from the game's masters)."""
import json, os, re
_DB = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vanilla', 'formids.json')))
def V(typ, edid, plugin='Skyrim'):
    try: return _DB[plugin][typ][edid]
    except KeyError: raise KeyError(f'vanilla {plugin} {typ} {edid} not found')
def find(typ, pat, plugin='Skyrim', limit=60):
    return {k: hex(v) for k, v in list((_DB[plugin].get(typ, {})).items()) if re.search(pat, k, re.I)}

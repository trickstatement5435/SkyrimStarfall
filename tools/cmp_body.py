"""Render a fitted mesh (grey) over the vanilla body (red) for a fit check: cmp_body.py fit.bin? -> uses build/<name>.bin is complex; instead import from caller"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, '/home/claude/MasterChief/tools')
import preview
from skinlib import load_body
def show(P, T, out, body_jsons):
    BP, BT = [], []
    for f in body_jsons:
        for s in load_body(f):
            BT += (np.array(s['tris']) + sum(len(x) for x in BP)).tolist(); BP.append(s['verts'])
    BP = np.concatenate(BP)
    allP = np.concatenate([P, BP]); allT = np.concatenate([np.array(T), np.array(BT) + len(P)])
    cols = [(200, 200, 200)] * len(T) + [(255, 60, 60)] * len(BT)
    preview.render(allP, allT, out, colors=cols, size=420)

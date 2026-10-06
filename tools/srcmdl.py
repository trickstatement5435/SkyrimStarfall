"""Source engine MDL (v44-49) + VVD + VTX reader: reference-pose mesh, bones (with bind poses), skin weights.
Coordinates are left in Source space (inches, Z up, character faces +X)."""
import struct, numpy as np

def cstr(b, off):
    return b[off:b.index(b'\0', off)].decode('latin1')

def quat_mat(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def load(base):
    mdl = open(base + '.mdl', 'rb').read()
    vvd = open(base + '.vvd', 'rb').read()
    vtx = open(base + '.dx90.vtx', 'rb').read()
    u = lambda fmt, b, o: struct.unpack_from(fmt, b, o)
    numbones, boneindex = u('<2i', mdl, 0x9c)
    bones = []
    for i in range(numbones):
        o = boneindex + i * 216
        name = cstr(mdl, o + u('<i', mdl, o)[0]); parent = u('<i', mdl, o + 4)[0]
        pos = np.array(u('<3f', mdl, o + 32)); quat = u('<4f', mdl, o + 44)
        p2b = np.array(u('<12f', mdl, o + 96)).reshape(3, 4)
        M = np.eye(4); M[:3, :] = p2b
        world = np.linalg.inv(M)              # bone -> model space at the reference pose
        local = np.eye(4); local[:3, :3] = quat_mat(quat); local[:3, 3] = pos
        bones.append(dict(name=name, parent=parent, world=world, local=local))
    numtextures, textureindex = u('<2i', mdl, 204)
    textures = [cstr(mdl, textureindex + i * 64 + u('<i', mdl, textureindex + i * 64)[0]) for i in range(numtextures)]
    numskinref, numskinfam, skinindex = u('<3i', mdl, 220)
    skin = [u('<h', mdl, skinindex + 2 * i)[0] for i in range(numskinref)]
    numbodyparts, bodypartindex = u('<2i', mdl, 232)

    numLODs = u('<i', vvd, 12); nverts0 = u('<i', vvd, 16)[0]
    numFixups, fixupStart, vertStart, tanStart = u('<4i', vvd, 48)
    raw = []
    for i in range(nverts0):
        o = vertStart + i * 48
        w = u('<3f', vvd, o); bi = u('<3B', vvd, o + 12); nb = vvd[o + 15]
        raw.append(dict(pos=u('<3f', vvd, o + 16), nrm=u('<3f', vvd, o + 28), uv=u('<2f', vvd, o + 40),
                        w={bi[k]: w[k] for k in range(nb) if w[k] > 0}))
    if numFixups:
        verts = []
        for i in range(numFixups):
            lod, src, cnt = u('<3i', vvd, fixupStart + 12 * i)
            if lod >= 0: verts.extend(raw[src:src + cnt])
    else:
        verts = raw

    vtx_bpoff = u('<i', vtx, 32)[0]
    meshes = []
    for bp in range(numbodyparts):
        bpo = bodypartindex + bp * 16
        bpname = cstr(mdl, bpo + u('<i', mdl, bpo)[0])
        nmodels, base_, modelindex = u('<3i', mdl, bpo + 4)
        xbp = vtx_bpoff + bp * 8
        xnm, xmo = u('<2i', vtx, xbp)
        for m in range(nmodels):
            mo = bpo + modelindex + m * 148
            mname = mdl[mo:mo + 64].split(b'\0')[0].decode('latin1')
            nmeshes, meshindex, nmv, vertexindex = u('<4i', mdl, mo + 72)
            mstart = vertexindex // 48
            xm = xbp + xmo + m * 8
            xnl, xlo = u('<2i', vtx, xm)
            xl = xm + xlo
            xnmesh, xmeshoff = u('<2i', vtx, xl)
            for me in range(nmeshes):
                meo = mo + meshindex + me * 116
                material, _, mnv, vertexoffset = u('<4i', mdl, meo)
                xme = xl + xmeshoff + me * 9
                nsg, sgoff = u('<2i', vtx, xme)
                tris = []
                for s in range(nsg):
                    sg = xme + sgoff + s * 25
                    nv, voff, ni, ioff = u('<4i', vtx, sg)
                    sgv = [u('<H', vtx, sg + voff + k * 9 + 4)[0] for k in range(nv)]
                    idx = [u('<H', vtx, sg + ioff + k * 2)[0] for k in range(ni)]
                    for t in range(0, ni - 2, 3):
                        tris.append([mstart + vertexoffset + sgv[idx[t + j]] for j in range(3)])
                mat = textures[skin[material]] if material < len(skin) else str(material)
                meshes.append(dict(bodypart=bpname, model=mname, material=mat, tris=tris))
    return dict(bones=bones, textures=textures, verts=verts, meshes=meshes)

if __name__ == '__main__':
    import sys
    m = load(sys.argv[1])
    print('bones:', [b['name'] for b in m['bones']])
    print('verts', len(m['verts']), 'textures', m['textures'])
    for me in m['meshes']: print(' ', me['bodypart'], me['model'], me['material'], len(me['tris']))
    P = np.array([v['pos'] for v in m['verts']]); print('bbox', P.min(0).round(1), P.max(0).round(1))

"""DDS writer with full mip chains. fmt: 'bc1' (DXT1, opaque), 'bc3' (DXT5, alpha), 'rgba' (uncompressed BGRA8).
Vectorised block encoder: endpoints from the block's min/max along the principal (luma-weighted) axis, inset."""
import struct, numpy as np
from PIL import Image

def _blocks(a):
    h, w = a.shape[:2]
    H, W = (h + 3) // 4 * 4, (w + 3) // 4 * 4
    if (H, W) != (h, w):
        a = np.pad(a, ((0, H - h), (0, W - w), (0, 0)), mode='edge')
    return a.reshape(H // 4, 4, W // 4, 4, -1).transpose(0, 2, 1, 3, 4).reshape(-1, 16, a.shape[2]).astype(np.float32)

def _565(c):
    c = np.clip(np.round(c), 0, 255).astype(np.int32)
    return ((c[..., 0] >> 3) << 11) | ((c[..., 1] >> 2) << 5) | (c[..., 2] >> 3)

def _un565(v):
    r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float32)

def _color(B):
    rgb = B[..., :3]
    mean = rgb.mean(1, keepdims=True)
    d = rgb - mean
    cov = np.einsum('nki,nkj->nij', d, d)
    axis = np.ones((len(B), 3), np.float32)
    for _ in range(6):
        axis = np.einsum('nij,nj->ni', cov, axis); axis /= np.linalg.norm(axis, axis=1, keepdims=True) + 1e-9
    t = np.einsum('nki,ni->nk', d, axis)
    lo = mean[:, 0] + axis * t.min(1, keepdims=True); hi = mean[:, 0] + axis * t.max(1, keepdims=True)
    inset = (hi - lo) / 16; lo += inset; hi -= inset
    c0, c1 = _565(hi), _565(lo)
    swap = c0 < c1; c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    eq = c0 == c1
    p0, p1 = _un565(c0), _un565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)
    dist = ((rgb[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
    idx = dist.argmin(-1)
    idx = np.where(eq[:, None], 0, idx)
    bits = (idx.astype(np.uint64) << (2 * np.arange(16, dtype=np.uint64))).sum(1)
    out = np.zeros((len(B), 8), np.uint8)
    out[:, 0:2] = np.stack([c0 & 255, c0 >> 8], 1); out[:, 2:4] = np.stack([c1 & 255, c1 >> 8], 1)
    out[:, 4:8] = np.stack([(bits >> (8 * k)) & 255 for k in range(4)], 1).astype(np.uint8)
    return out

def _alpha(B):
    a = B[..., 3]
    a0 = a.max(1); a1 = a.min(1)
    a0 = np.round(a0).astype(np.int32); a1 = np.round(a1).astype(np.int32)
    same = a0 == a1
    a0 = np.where(same, np.minimum(a0 + 1, 255), a0); a1 = np.where(same & (a0 == 255), 254, a1)
    pal = np.stack([a0, a1] + [((7 - i) * a0 + i * a1) / 7 for i in range(1, 7)], 1).astype(np.float32)
    idx = np.abs(a[:, :, None] - pal[:, None, :]).argmin(-1).astype(np.uint64)
    bits = (idx << (3 * np.arange(16, dtype=np.uint64))).sum(1)
    out = np.zeros((len(B), 8), np.uint8); out[:, 0] = a0; out[:, 1] = a1
    out[:, 2:8] = np.stack([(bits >> (8 * k)) & 255 for k in range(6)], 1).astype(np.uint8)
    return out

def write(path, rgba, fmt='bc1', mips=True):
    rgba = np.asarray(rgba)
    if rgba.shape[2] == 3: rgba = np.dstack([rgba, np.full(rgba.shape[:2], 255, np.uint8)])
    img = Image.fromarray(rgba.astype(np.uint8), 'RGBA'); w, h = img.size
    levels = [img]
    while mips and levels[-1].size != (1, 1):
        mw, mh = levels[-1].size
        levels.append(levels[-1].resize((max(1, mw // 2), max(1, mh // 2)), Image.LANCZOS))
    data = bytearray()
    for m in levels:
        a = np.asarray(m.convert('RGBA'))
        if fmt == 'rgba':
            data += a[..., [2, 1, 0, 3]].tobytes()
        else:
            B = _blocks(a)
            blk = _color(B) if fmt == 'bc1' else np.concatenate([_alpha(B), _color(B)], 1)
            data += blk.tobytes()
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000
    if fmt == 'rgba':
        pf = struct.pack('<II4sIIIII', 32, 0x41, b'\0\0\0\0', 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        pitch = w * 4; flags |= 0x8
    else:
        pf = struct.pack('<II4sIIIII', 32, 0x4, b'DXT1' if fmt == 'bc1' else b'DXT5', 0, 0, 0, 0, 0)
        pitch = max(1, (w + 3) // 4) * (8 if fmt == 'bc1' else 16) * max(1, (h + 3) // 4); flags |= 0x80000
    hdr = struct.pack('<4s7I', b'DDS ', 124, flags, h, w, pitch, 0, len(levels)) + b'\0' * 44 + pf
    hdr += struct.pack('<IIIII', 0x1000 | 0x8 | 0x400000, 0, 0, 0, 0)
    open(path, 'wb').write(hdr + data)

def read_dxt_preview(path):
    """decode level 0 (for checks)"""
    d = open(path, 'rb').read(); h, w = struct.unpack_from('<II', d, 12); four = d[84:88]
    off = 128; nb = ((w + 3) // 4) * ((h + 3) // 4)
    bs = 8 if four == b'DXT1' else 16
    raw = np.frombuffer(d[off:off + nb * bs], np.uint8).reshape(nb, bs)
    c = raw[:, -8:]
    c0 = c[:, 0].astype(np.int32) | (c[:, 1].astype(np.int32) << 8); c1 = c[:, 2].astype(np.int32) | (c[:, 3].astype(np.int32) << 8)
    p0, p1 = _un565(c0), _un565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)
    bits = c[:, 4].astype(np.uint32) | (c[:, 5].astype(np.uint32) << 8) | (c[:, 6].astype(np.uint32) << 16) | (c[:, 7].astype(np.uint32) << 24)
    idx = (bits[:, None] >> (2 * np.arange(16))) & 3
    px = np.take_along_axis(pal, idx[..., None].astype(np.int64).repeat(3, -1), 1)
    img = px.reshape((h + 3) // 4, (w + 3) // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape((h + 3) // 4 * 4, (w + 3) // 4 * 4, 3)
    return img[:h, :w].astype(np.uint8)

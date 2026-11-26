"""Weld + quantize (KHR_mesh_quantization) a GLB using numpy only.
usage: python3 -I optimize_glb.py in.glb out.glb
"""
import sys, json, struct
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()
jl = struct.unpack('<I', data[12:16])[0]
J = json.loads(data[20:20 + jl])
boff = 20 + jl + 8
BIN = data[boff:boff + struct.unpack('<I', data[20 + jl:24 + jl])[0]]

CT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8, 5122: np.int16, 5120: np.int8}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read(ai):
    a = J['accessors'][ai]
    v = J['bufferViews'][a['bufferView']]
    dt = np.dtype(CT[a['componentType']])
    n = NC[a['type']]
    stride = v.get('byteStride', dt.itemsize * n)
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    raw = np.frombuffer(BIN, dtype=np.uint8, count=stride * (a['count'] - 1) + dt.itemsize * n, offset=off)
    if stride == dt.itemsize * n:
        return raw.view(dt).reshape(a['count'], n).copy()
    out = np.lib.stride_tricks.as_strided(raw, shape=(a['count'], dt.itemsize * n), strides=(stride, 1))
    return np.ascontiguousarray(out).view(dt).reshape(a['count'], n)


out_bin = bytearray()
views, accs = [], []


def add(arr, target=None, stride=None):
    while len(out_bin) % 4:
        out_bin.append(0)
    b = np.ascontiguousarray(arr).tobytes()
    v = {'buffer': 0, 'byteOffset': len(out_bin), 'byteLength': len(b)}
    if target:
        v['target'] = target
    if stride:
        v['byteStride'] = stride
    out_bin.extend(b)
    views.append(v)
    return len(views) - 1


def acc(view, ctype, count, typ, normalized=False, mn=None, mx=None):
    a = {'bufferView': view, 'componentType': ctype, 'count': count, 'type': typ}
    if normalized:
        a['normalized'] = True
    if mn is not None:
        a['min'] = mn; a['max'] = mx
    accs.append(a)
    return len(accs) - 1


# images: copy through
for im in J.get('images', []):
    if 'bufferView' in im:
        v = J['bufferViews'][im['bufferView']]
        im['bufferView'] = add(np.frombuffer(BIN, np.uint8, v['byteLength'], v.get('byteOffset', 0)))

mesh_q = {}  # mesh index -> 4x4 dequant matrix (column-major math)
stats = [0, 0]
for mi, mesh in enumerate(J['meshes']):
    prims = mesh['primitives']
    # one quant box per mesh (all prims)
    allp = np.concatenate([read(p['attributes']['POSITION']) for p in prims])
    lo, hi = allp.min(0).astype(np.float64), allp.max(0).astype(np.float64)
    ext = (hi - lo).max() or 1.0
    scale = ext / 65534.0
    center = (lo + hi) / 2
    Q = np.eye(4); Q[:3, :3] *= scale; Q[:3, 3] = center
    mesh_q[mi] = Q
    for p in prims:
        A = p['attributes']
        pos = read(A['POSITION']).astype(np.float64)
        qp = np.clip(np.round((pos - center) / scale), -32767, 32767).astype(np.int16)
        cols = [qp]
        qn = None
        if 'NORMAL' in A:
            n = read(A['NORMAL']).astype(np.float64)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            qn = np.round(n * 127).astype(np.int8)
            cols.append(qn)
        uv = None
        if 'TEXCOORD_0' in A:
            uv = read(A['TEXCOORD_0']).astype(np.float32)
            cols.append(uv.view(np.uint8).reshape(len(uv), -1))
        key = np.concatenate([c.view(np.uint8).reshape(len(qp), -1) for c in cols], axis=1)
        key = np.ascontiguousarray(key).view(np.dtype((np.void, key.shape[1]))).ravel()
        idx_old = read(p['indices']).ravel() if 'indices' in p else np.arange(len(qp))
        _, first, inv = np.unique(key, return_index=True, return_inverse=True)
        stats[0] += len(qp); stats[1] += len(first)
        idx = inv.ravel()[idx_old]
        nv = len(first)
        # interleave pos(4x int16) + normal(4x int8)
        pv = np.zeros((nv, 4), np.int16); pv[:, :3] = qp[first]
        newA = {}
        v = add(pv, 34962, 8)
        newA['POSITION'] = acc(v, 5122, nv, 'VEC3', False, pv[:, :3].min(0).tolist(), pv[:, :3].max(0).tolist())
        if qn is not None:
            nn = np.zeros((nv, 4), np.int8); nn[:, :3] = qn[first]
            newA['NORMAL'] = acc(add(nn, 34962, 4), 5120, nv, 'VEC3', True)
        if uv is not None:
            u = uv[first]
            if u.min() >= 0 and u.max() <= 1:
                uq = np.round(u * 65535).astype(np.uint16)
                newA['TEXCOORD_0'] = acc(add(uq, 34962, 4), 5123, nv, 'VEC2', True)
            else:
                newA['TEXCOORD_0'] = acc(add(u, 34962, 8), 5126, nv, 'VEC2')
        if nv < 65535:
            iv = add(idx.astype(np.uint16), 34963); ic = 5123
        else:
            iv = add(idx.astype(np.uint32), 34963); ic = 5125
        p['attributes'] = newA
        p['indices'] = acc(iv, ic, len(idx), 'SCALAR')

# fold dequant matrix into each node that references a mesh
for nd in J['nodes']:
    if 'mesh' not in nd:
        continue
    if 'matrix' in nd:
        M = np.array(nd['matrix'], np.float64).reshape(4, 4).T
    else:
        t = nd.get('translation', [0, 0, 0]); r = nd.get('rotation', [0, 0, 0, 1]); s = nd.get('scale', [1, 1, 1])
        x, y, z, w = r
        R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        M = np.eye(4); M[:3, :3] = R * np.array(s); M[:3, 3] = t
        for k in ('translation', 'rotation', 'scale'):
            nd.pop(k, None)
    nd['matrix'] = (M @ mesh_q[nd['mesh']]).T.ravel().tolist()

J['accessors'] = accs
J['bufferViews'] = views
J['buffers'] = [{'byteLength': len(out_bin)}]
for k in ('extensionsUsed', 'extensionsRequired'):
    J[k] = sorted(set(J.get(k, []) + ['KHR_mesh_quantization']))
while len(out_bin) % 4:
    out_bin.append(0)
js = json.dumps(J, ensure_ascii=False, separators=(',', ':')).encode()
js += b' ' * (-len(js) % 4)
total = 12 + 8 + len(js) + 8 + len(out_bin)
with open(dst, 'wb') as f:
    f.write(struct.pack('<III', 0x46546C67, 2, total))
    f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
    f.write(struct.pack('<II', len(out_bin), 0x004E4942)); f.write(out_bin)
print('verts %d -> %d, size %.1f MB' % (stats[0], stats[1], total / 1e6))

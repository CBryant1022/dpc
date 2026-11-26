"""Generic KeyShot GLB rebuild driven by a per-style JSON config.
usage: python3 -I ks_build.py config.json in.glb out_float.glb
config = {
  "tdir": "<folder with .ksp textures>",
  "drop": ["Insole Light"],                       # meshes to remove
  "parts": { "<mesh name>": {"rename": "...",      # new material name (for colorway grouping)
             "n": "NRM file", "b": "BASE file", "r": "ROUGH file",   # all optional
             "rep": [u, v]  |  "cm": [u, v],       # KeyShot repeat (1/scale)  or  uniform tile size in cm
             "rot": deg, "keep_mr": bool } }
}
"""
import sys, json, struct, io, math
import numpy as np
from PIL import Image

import os
cfg = json.loads(os.path.expandvars(open(sys.argv[1], encoding='utf-8').read())); src, dst = sys.argv[2:4]
tdir = cfg['tdir']; MAXPX = cfg.get('maxpx', 1024)
data = open(src, 'rb').read()
jl = struct.unpack('<I', data[12:16])[0]
J = json.loads(data[20:20 + jl]); BIN = bytearray(data[20 + jl + 8:])


def rd(ai):
    a = J['accessors'][ai]; v = J['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[a['type']]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a['componentType']]; it = np.dtype(dt).itemsize
    st = v.get('byteStride', it * n)
    raw = np.frombuffer(bytes(BIN), np.uint8, st * (a['count'] - 1) + it * n, v.get('byteOffset', 0) + a.get('byteOffset', 0))
    return np.ascontiguousarray(np.lib.stride_tricks.as_strided(raw, (a['count'], it * n), (st, 1))).view(dt).reshape(-1, n).astype(np.float64)


def img_bytes(ii):
    v = J['bufferViews'][J['images'][ii]['bufferView']]
    return bytes(BIN[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])


J.setdefault('samplers', []).append({'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}); samp = len(J['samplers']) - 1
cache = {}


def add_image(im, name):
    mx = 2048 if name.split('/')[-1].startswith(('td_base', 'sockliner')) else MAXPX
    if max(im.size) > mx:
        r = mx / max(im.size); im = im.resize((round(im.size[0] * r), round(im.size[1] * r)), Image.LANCZOS)
    b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=90); b = b.getvalue()
    while len(BIN) % 4: BIN.append(0)
    J['bufferViews'].append({'buffer': 0, 'byteOffset': len(BIN), 'byteLength': len(b)}); BIN.extend(b)
    J['images'].append({'bufferView': len(J['bufferViews']) - 1, 'mimeType': 'image/jpeg', 'name': name})
    J['textures'].append({'source': len(J['images']) - 1, 'sampler': samp})
    return len(J['textures']) - 1


def tex(kind, fname):
    key = (kind, fname)
    if key not in cache:
        if kind == 'mr':
            r = Image.open(fname if fname.startswith('/') else f'{tdir}/{fname}').convert('L')
            im = Image.merge('RGB', (Image.new('L', r.size, 255), r, Image.new('L', r.size, 0)))
        else:
            im = Image.open(fname if fname.startswith('/') else f'{tdir}/{fname}').convert('RGB')
        cache[key] = add_image(im, fname.rsplit('.', 1)[0] + ('_MR' if kind == 'mr' else ''))
    return cache[key]


def lin_mean(im):
    c = np.asarray(im.convert('RGB'), np.float64).reshape(-1, 3) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).mean(0)


def cm_per_uv(p):
    A = p['attributes']; I = rd(p['indices']).ravel().astype(int)
    P = rd(A['POSITION'])[I].reshape(-1, 3, 3); U = rd(A['TEXCOORD_0'])[I].reshape(-1, 3, 2)
    e1 = P[:, 1] - P[:, 0]; e2 = P[:, 2] - P[:, 0]; d1 = U[:, 1] - U[:, 0]; d2 = U[:, 2] - U[:, 0]
    det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]; ok = np.abs(det) > 1e-12
    with np.errstate(all='ignore'):
        dPu = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / det[:, None]; dPv = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / det[:, None]
    w = np.linalg.norm(np.cross(e1, e2), axis=1)[ok]
    return (np.average(np.linalg.norm(dPu[ok], axis=1), weights=w), np.average(np.linalg.norm(dPv[ok], axis=1), weights=w))


def tinfo(index, rep, rot):
    ext = {'scale': [float(rep[0]), float(rep[1])]}
    if rot: ext['rotation'] = math.radians(rot)
    return {'index': index, 'extensions': {'KHR_texture_transform': ext}}


done = set()
for mesh in J['meshes']:
    R = cfg['parts'].get(mesh['name'])
    if not R: continue
    for p in mesh['primitives']:
        mi = p['material']
        if mi in done:  # material shared with another mesh -> clone so each part is independent
            J['materials'].append(json.loads(json.dumps(J['materials'][mi]))); mi = len(J['materials']) - 1; p['material'] = mi
        done.add(mi); m = J['materials'][mi]
        if 'rename' in R: m['name'] = R['rename']
        pb0 = m.setdefault('pbrMetallicRoughness', {})
        if R.get('mean_color') and 'baseColorTexture' in pb0:
            tiny = Image.open(io.BytesIO(img_bytes(J['textures'][pb0['baseColorTexture']['index']]['source'])))
            lm = lin_mean(tiny); f = pb0.get('baseColorFactor', [1, 1, 1, 1]); pb0['baseColorFactor'] = [float(f[c] * lm[c]) for c in range(3)] + [1.0]
        if R.get('drop_base'): pb0.pop('baseColorTexture', None)
        if R.get('drop_n'): m.pop('normalTexture', None)
        if R.get('no_trans'):
            m.get('extensions', {}).pop('KHR_materials_transmission', None)
            if not m.get('extensions'): m.pop('extensions', None)
        if 'color' in R:
            c = np.array(R['color'][:3], float) / 255; c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
            pb0['baseColorFactor'] = [float(x) for x in c] + [1.0]
        if 'rough' in R: pb0['roughnessFactor'] = R['rough']; pb0['metallicFactor'] = pb0.get('metallicFactor', 0) if R.get('keep_metal') else 0.0
        if 'img' in R:
            pb0['baseColorTexture'] = {'index': tex('c', R['img'])}; pb0['baseColorFactor'] = [1, 1, 1, 1]
        if not any(k in R for k in ('n', 'b', 'r')): continue
        if 'cm' in R:
            cu, cv = cm_per_uv(p); rep = (cu / R['cm'][0], cv / R['cm'][1])
        else:
            rep = R.get('rep', [1, 1])
        rot = R.get('rot', 0); pb = m.setdefault('pbrMetallicRoughness', {})
        if 'b' in R:
            tint = np.ones(3); old = pb.get('baseColorTexture')
            if old is not None and not R.get('no_tint'):
                tiny = Image.open(io.BytesIO(img_bytes(J['textures'][old['index']]['source'])))
                tint = np.clip(lin_mean(tiny) / np.maximum(lin_mean(Image.open(f"{tdir}/{R['b']}")), 1e-3), 0, 1.5)
            f = pb.get('baseColorFactor', [1, 1, 1, 1])
            pb['baseColorFactor'] = [float(min(1, f[c] * tint[c])) for c in range(3)] + [f[3]]
            pb['baseColorTexture'] = tinfo(tex('c', R['b']), rep, rot)
        if 'r' in R:
            pb['metallicRoughnessTexture'] = tinfo(tex('mr', R['r']), rep, rot); pb['roughnessFactor'] = 1.0; pb['metallicFactor'] = 0.0
        if 'n' in R:
            m['normalTexture'] = dict(tinfo(tex('n', R['n']), rep, rot), scale=1.0)
        print(f"{mesh['name']:8s} -> {m['name']:28s} rep=({rep[0]:.1f},{rep[1]:.1f}) rot={rot}")

for nd in J['nodes']:
    nd.pop('camera', None)
    if nd.get('name') in cfg.get('drop', []): nd.pop('mesh', None)
J.pop('cameras', None)
J['extensionsUsed'] = sorted(set(J.get('extensionsUsed', []) + ['KHR_texture_transform']))
while len(BIN) % 4: BIN.append(0)
J['buffers'] = [{'byteLength': len(BIN)}]
js = json.dumps(J, ensure_ascii=False, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
with open(dst, 'wb') as f:
    f.write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(BIN)))
    f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
    f.write(struct.pack('<II', len(BIN), 0x004E4942)); f.write(BIN)
print('images added', len(cache))

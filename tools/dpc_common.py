"""Shared helpers for the DPC site: parse/patch encrypted blocks in index.html."""
import json, base64, os, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
b64d = base64.b64decode
def b64e(b): return base64.b64encode(b).decode()
def grab(html, name):
    tag = 'const ' + name + '='; i = html.index(tag) + len(tag)
    obj, end = json.JSONDecoder().raw_decode(html[i:]); return obj, i, i + end
def put(html, name, obj):
    _, i, j = grab(html, name); return html[:i] + json.dumps(obj, ensure_ascii=False if name == 'VERSION' else True) + html[j:]
def enc(key, data: bytes):
    iv = os.urandom(12); return {'iv': b64e(iv), 'ct': b64e(AESGCM(key).encrypt(iv, data, None))}
def dec(key, o): return AESGCM(key).decrypt(b64d(o['iv']), b64d(o['ct']), None)
def unwrap(auth, user, pw):
    kek = hashlib.pbkdf2_hmac('sha256', f'{user}:{pw}'.encode(), b64d(auth['salt']), auth['iter'], 32)
    for n, e in enumerate(auth['entries']):
        try: return n, json.loads(AESGCM(kek).decrypt(b64d(e['iv']), b64d(e['wk']), None))
        except Exception: pass
    raise SystemExit(f'login failed for {user}')
def load_keys(kdir): return {f[:-4]: b64d(open(os.path.join(kdir, f)).read().strip()) for f in os.listdir(kdir) if f.endswith('.key')}

"""gzip + AES-256-GCM + base64 a GLB, split into parts < 3.6 MB (GitHub web upload limit).
usage: python3 encrypt_model.py model.glb keys_dir kid out_dir
Prints the 'files', 'total', 'mb' values for the catalog entry. Verifies the round trip.
"""
import sys, os, gzip, base64, json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dpc_common import load_keys
glb, kdir, kid, out = sys.argv[1:5]; K = load_keys(kdir)[kid]; raw = open(glb, 'rb').read()
g = gzip.compress(raw, 9); iv = os.urandom(12); m = base64.b64encode(iv + AESGCM(K).encrypt(iv, g, None))
n = -(-len(m) // 3_600_000); sz = -(-len(m) // n); sz += (-sz) % 4; os.makedirs(out, exist_ok=True)
parts = [m[i:i + sz] for i in range(0, len(m), sz)]
for i, p in enumerate(parts): open(f'{out}/model_p{i}.txt', 'wb').write(p)
back = base64.b64decode(b''.join(parts)); assert gzip.decompress(AESGCM(K).decrypt(back[:12], back[12:], None)) == raw
print(json.dumps({'files': [f'model_p{i}.txt' for i in range(len(parts))], 'total': len(m), 'mb': round(len(g) / 1e6, 1)}))

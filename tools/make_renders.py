"""KeyShot renders -> encrypted site images.
usage: python3 make_renders.py keys_dir kid out_dir 1_FRT.png 2_LAT.png 3_BAC.png 4_BLT.png 5_MED.png 6_FRO.png 7_TOP.png 8_BOT.png
Each PNG is composited on grey (56,56,56) at 2500x2000 (JPEG q90) plus a 200x160 thumbnail (*_t), then encrypted.
View names: 1_FRT front34, 2_LAT sideL, 3_BAC back, 4_BLT back34, 5_MED sideR, 6_FRO front, 7_TOP top, 8_BOT bottom.
"""
import sys, os, io, base64
from PIL import Image
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dpc_common import load_keys
NAMES = ['front34', 'sideL', 'back', 'back34', 'sideR', 'front', 'top', 'bottom']
kdir, kid, out = sys.argv[1:4]; pngs = sys.argv[4:12]; K = AESGCM(load_keys(kdir)[kid]); os.makedirs(f'{out}/renders', exist_ok=True)
def enc(b): iv = os.urandom(12); return base64.b64encode(iv + K.encrypt(iv, b, None))
def jpg(im, q=90): bio = io.BytesIO(); im.save(bio, 'JPEG', quality=q); return bio.getvalue()
for name, p in zip(NAMES, pngs):
    im = Image.open(p).convert('RGBA'); im.thumbnail((2500, 2000), Image.LANCZOS)
    bg = Image.new('RGBA', (2500, 2000), (56, 56, 56, 255)); bg.alpha_composite(im, ((2500 - im.width) // 2, (2000 - im.height) // 2)); bg = bg.convert('RGB')
    open(f'{out}/renders/{name}.txt', 'wb').write(enc(jpg(bg))); open(f'{out}/renders/{name}_t.txt', 'wb').write(enc(jpg(bg.resize((200, 160), Image.LANCZOS), 85)))
    print(name, '<-', os.path.basename(p))

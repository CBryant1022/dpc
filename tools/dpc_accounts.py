"""Manage logins in index.html (AUTH). Entries are unlabeled; an account is found by trying its password.
add   : python3 dpc_accounts.py add    index.html keys_dir USER PASS admin|customer c,d,b,v,a out.html
remove: python3 dpc_accounts.py remove index.html USER PASS out.html
change password = remove (old password) then add (new password).
Admins get every key (c,d,b,v,a). A customer gets only its brand key, e.g. Carhartt -> c.
"""
import sys, json, hashlib, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dpc_common import grab, put, unwrap, load_keys, b64d, b64e
cmd = sys.argv[1]; html = open(sys.argv[2], encoding='utf-8').read(); auth, _, _ = grab(html, 'AUTH')
if cmd == 'add':
    kdir, u, p, role, kids, out = sys.argv[3:9]; K = load_keys(kdir)
    ring = {'k': {k: b64e(K[k]) for k in kids.split(',')}, 'r': role}
    kek = hashlib.pbkdf2_hmac('sha256', f'{u}:{p}'.encode(), b64d(auth['salt']), auth['iter'], 32); iv = os.urandom(12)
    auth['entries'].append({'iv': b64e(iv), 'wk': b64e(AESGCM(kek).encrypt(iv, json.dumps(ring).encode(), None))})
else:
    u, p, out = sys.argv[3:6]; n, _ = unwrap(auth, u, p); auth['entries'].pop(n)
open(out, 'w', encoding='utf-8').write(put(html, 'AUTH', auth)); print(cmd, u, '->', len(auth['entries']), 'entries')

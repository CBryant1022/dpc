"""Recover all brand keys from the live index.html with an admin account.
usage: python3 dpc_keys.py index.html <admin_user> <admin_pass> <keys_dir>
Writes <keys_dir>/<kid>.key (base64). kid: c=Carhartt d=DT b=Anthem Branding v=Vans a=admin/changelog
"""
import sys, os
from dpc_common import grab, unwrap
html = open(sys.argv[1], encoding='utf-8').read(); auth, _, _ = grab(html, 'AUTH')
n, ring = unwrap(auth, sys.argv[2], sys.argv[3]); os.makedirs(sys.argv[4], exist_ok=True)
for k, v in ring['k'].items(): open(f'{sys.argv[4]}/{k}.key', 'w').write(v)
print('role', ring['r'], 'entry', n, 'keys', list(ring['k']))

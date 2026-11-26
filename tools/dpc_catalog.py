"""Decrypt / re-encrypt the style catalog (CAT) and changelog (CLOG) inside index.html.
dump : python3 dpc_catalog.py dump  index.html keys_dir catalog.json
apply: python3 dpc_catalog.py apply index.html keys_dir catalog.json out.html [--version v1.37]
catalog.json = {"styles":[{..., "kid":"v"}], "changelog":[["v1.36","2026-11-26","zh","en"], ...]}
Styles are grouped by kid; each group is one CAT chunk encrypted with that brand key. CLOG uses key 'a'.
AUTH (accounts) is never touched here.
"""
import sys, json, re
from dpc_common import grab, put, enc, dec, load_keys
cmd, src, kdir, cj = sys.argv[1:5]; html = open(src, encoding='utf-8').read(); K = load_keys(kdir)
if cmd == 'dump':
    cat, _, _ = grab(html, 'CAT'); styles = []
    for c in cat:
        for k, key in K.items():
            try: styles += json.loads(dec(key, c)); break
            except Exception: pass
    clog = json.loads(dec(K['a'], grab(html, 'CLOG')[0]))
    json.dump({'styles': styles, 'changelog': clog}, open(cj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(styles), 'styles,', len(clog), 'changelog rows')
else:
    d = json.load(open(cj, encoding='utf-8')); out = sys.argv[5]
    order = []; [order.append(s['kid']) for s in d['styles'] if s['kid'] not in order]
    cat = [enc(K[k], json.dumps([s for s in d['styles'] if s['kid'] == k], ensure_ascii=False).encode()) for k in order]
    html = put(html, 'CAT', cat); html = put(html, 'CLOG', enc(K['a'], json.dumps(d['changelog'], ensure_ascii=False).encode()))
    if '--version' in sys.argv:
        v = sys.argv[sys.argv.index('--version') + 1]; html = re.sub(r"const VERSION='[^']*'", f"const VERSION='{v}'", html, count=1)
    open(out, 'w', encoding='utf-8').write(html); print('wrote', out, 'chunks', order)

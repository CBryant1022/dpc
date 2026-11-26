"""Single-file offline HTML from a checkout of the dpc repo (all assets embedded, login still required).
usage: python3 build_offline.py repo_dir model-viewer.min.js out.html --login USER PASS [--only]
 --login : the account used to read the catalog; the file contains exactly the styles this account can see.
           Use an admin account for the full internal version (all accounts can still log in).
 --only  : customer version - keep only this account's login entry and its styles; every other account and brand is removed.
model-viewer.min.js: get from git (google/model-viewer, branch gh-pages: node_modules/@google/model-viewer/dist/).
"""
import sys, re, json, os
from dpc_common import grab, put, unwrap, dec, b64d
repo, mvjs, out = sys.argv[1:4]; html = open(f'{repo}/index.html', encoding='utf-8').read()
V = ['front34', 'sideL', 'sideR', 'back34', 'front', 'back', 'top', 'bottom']
cat, _, _ = grab(html, 'CAT')
u, p = sys.argv[sys.argv.index('--login') + 1:][:2]; auth, _, _ = grab(html, 'AUTH'); n, ring = unwrap(auth, u, p)
only = '--only' in sys.argv; keys = [b64d(v) for v in ring['k'].values()]
if only: auth['entries'] = [auth['entries'][n]]; html = put(html, 'AUTH', auth)
styles, keep = [], []
for c in cat:
    for k in keys:
        try: styles += json.loads(dec(k, c)); keep.append(c); break
        except Exception: pass
if only: html = put(html, 'CAT', keep)
def norm(base, f):
    o = []
    for s in (base + '/' + f.split('?')[0]).split('/'):
        if s == '..': o.pop()
        elif s and s != '.': o.append(s)
    return '/'.join(o)
files = []
for s in styles:
    if s.get('pending'): continue
    files += [f"{s['base']}/renders/{v}{t}.txt" for v in V for t in ('', '_t')] + [norm(s['base'], f) for f in s['files']]
blobs = '\n'.join(f'<script type="text/x-dpc" id="f:{f}">{open(f"{repo}/{f}").read().strip()}</script>' for f in files)
shim = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'offline_shim.html')).read()
html = html.replace('<head>', '<head>' + shim, 1); m = re.search(r'<body[^>]*>', html); html = html[:m.end()] + '\n' + blobs + '\n' + html[m.end():]
tag = re.search(r'<script type="module" src="https://cdn\.jsdelivr\.net/npm/@google/model-viewer@[^"]+"></script>', html).group(0)
mv = re.sub(r'</script', r'<\\/script', open(mvjs, encoding='utf-8').read(), flags=re.I)
html = html.replace(tag, '<script type="module">' + mv + '</script>')
open(out, 'w', encoding='utf-8').write(html); print(len(files), 'files', round(os.path.getsize(out) / 1e6, 1), 'MB ->', out)

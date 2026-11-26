"""Preview renders of a GLB from the KeyShot cameras (Playwright + SwiftShader, no GPU needed).
usage: python3 shoot.py original_with_cameras.glb model_to_render.glb 1,2,3,4,5,6,7,8 out_prefix
Run from the folder that contains render.html and the GLB (served over http://127.0.0.1:8765).
"""
import sys,json,base64,numpy as np,asyncio,threading,http.server,functools
from glbio import load
J,_=load(sys.argv[1])
par={c:i for i,n in enumerate(J['nodes']) for c in n.get('children',[])}
def local(n):
    if 'matrix' in n: return np.array(n['matrix']).reshape(4,4).T
    return np.eye(4)
def world(i):
    M=local(J['nodes'][i])
    while i in par: i=par[i];M=local(J['nodes'][i])@M
    return M
cams={}
for i,n in enumerate(J['nodes']):
    if 'camera' in n and n['name']!='active':
        c=J['cameras'][n['camera']];cams[n['name']]=(world(i).T.ravel().tolist(),'persp' if c['type']=='perspective' else 'ortho',c.get('perspective',{}).get('yfov',0.44))
glb=sys.argv[2];views=sys.argv[3].split(',');out=sys.argv[4]
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8765),functools.partial(http.server.SimpleHTTPRequestHandler,directory='.'))
threading.Thread(target=srv.serve_forever,daemon=True).start()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(args=['--use-gl=swiftshader','--enable-webgl','--ignore-gpu-blocklist'])
    pg=b.new_page();pg.goto('http://127.0.0.1:8765/render.html');pg.evaluate(f"load('{glb}')")
    for v in views:
        k=[c for c in cams if c.startswith(v)][0];w,kind,fov=cams[k]
        d=pg.evaluate(f"shot({json.dumps(w)},'{kind}',{fov},1.08,true)")
        open(f'{out}_{v}.jpg','wb').write(base64.b64decode(d.split(',')[1]));print('shot',k)
    b.close()

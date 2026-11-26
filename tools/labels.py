"""Make a label texture: logo (alpha PNG) tinted one colour, centred on a solid background.
usage: python3 labels.py logo.png out.png W H bg_hex logo_hex [fill=0.8]
Use W:H = the label's physical aspect. Pair with a planar UV on the label mesh (see uv_unwrap_vans.py, 'planar decals').
"""
import sys
from PIL import Image
logo, out, W, H, bg, fg = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
fill = float(sys.argv[7]) if len(sys.argv) > 7 else 0.8
hx = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
im = Image.open(logo).convert('RGBA'); a = im.split()[3]; c = Image.new('RGBA', im.size, hx(fg) + (255,)); c.putalpha(a); c = c.crop(a.getbbox())
c.thumbnail((int(W * fill), int(H * fill)), Image.LANCZOS)
o = Image.new('RGBA', (W, H), hx(bg) + (255,)); o.alpha_composite(c, ((W - c.width) // 2, (H - c.height) // 2)); o.convert('RGB').save(out); print('wrote', out)

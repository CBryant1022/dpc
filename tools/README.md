# DPC tools｜製作工具

Scripts that build the DATIAN DPC site (https://cbryant1022.github.io/dpc/).
**No keys or passwords are stored here.** Keys: recover with `dpc_keys.py` (admin login) or read the user's `DATIAN_DPC_加密金鑰.md`.

Requirements: `python3`, `numpy`, `pillow`, `cryptography`, `playwright` (Chromium) for previews.

## Files

| Script | What it does |
|---|---|
| `dpc_common.py` | Shared helpers: read/patch `AUTH` / `CAT` / `CLOG` blocks, AES-GCM, keyring unwrap |
| `dpc_keys.py` | Recover all brand keys from `index.html` with an admin account → `keys/<kid>.key` |
| `dpc_catalog.py` | `dump` catalog + changelog to JSON; `apply` edited JSON back (re-encrypt per brand), `--version` bump |
| `dpc_accounts.py` | Add / remove logins (change password = remove + add) |
| `ks_build.py` | Apply `.ksp` textures to the KeyShot GLB from a per-style JSON config (rename parts, tiling, colours, labels) |
| `uv_unwrap_vans.py` | Example: new UVs for parts without UV (dome / cylindrical / planar labels) |
| `labels.py` | Label texture: tinted logo on a solid background |
| `optimize_glb.py` | Vertex weld + KHR_mesh_quantization |
| `shoot.py` + `render.html` | Preview stills from the KeyShot cameras (no GPU) |
| `encrypt_model.py` | gzip + encrypt + split GLB into `model_p*.txt` (< 3.6 MB each) |
| `make_renders.py` | 8 KeyShot PNGs → grey 2500×2000 JPG + 200×160 thumbnails, encrypted |
| `build_offline.py` + `offline_shim.html` | Single-file offline HTML (internal full version or one customer only) |
| `configs/*.json` | Per-style texture configs (`$WORK` = working folder) |

## Keys (kid)

`c` Carhartt · `d` DT · `b` Anthem Branding · `v` Vans · `a` admin (changelog). New brand → new key (32 random bytes, base64) in `keys/`, then give it to the admin accounts with `dpc_accounts.py` (remove + add) and update the user's key `.md`.

## Add a new style (SOP)

```bash
W=work/<style>; mkdir -p $W/ksp && unzip -o <style>.ksp -d $W/ksp        # textures
python3 dpc_keys.py repo/index.html <admin> <pass> keys                     # once per session
# 1. inspect GLB: mesh names, materials, UVs, cameras -> write configs/<style>.json
WORK=$W python3 ks_build.py configs/<style>.json in.glb $W/f.glb
python3 optimize_glb.py $W/f.glb $W/q.glb
python3 shoot.py in.glb $W/q.glb 1,2,3,7 $W/t     # compare with KeyShot renders
# 2. encrypt
python3 encrypt_model.py $W/q.glb keys <kid> repo/<base>          # prints files/total/mb
python3 make_renders.py keys <kid> repo/<base> 1_FRT.png ... 8_BOT.png
# 3. catalog
python3 dpc_catalog.py dump repo/index.html keys cat.json          # edit: add style (zh/en/ja), changelog row
python3 dpc_catalog.py apply repo/index.html keys cat.json repo/index.html --version v1.xx
# 4. push repo (base folder + index.html), then check the live hashes
# 5. offline: python3 build_offline.py repo model-viewer.min.js out.html --login <user> <pass> [--only]
```

Style entry fields: `id, name, brand, color, version, desc, updated, base, files, total, mb, tags, info, note, parts, en{}, ja{}, kid`.
Renders are read from `<base>/renders/`; model parts from `<base>/<file>` (a file may be `../<other>/model_p0.txt`).

## Material naming (colourway groups)

`upper__vamp|quarter_*|eyestay|heel_counter|heel_pull|tongue|binding_quarter|binding_tongue`, `upper__laces`, `eyelet*`,
`stitch__*`, `inside__*` (lining), `trim__*` (FOX1), `沿條*` (FOX2), `後跟標`, `大底`, `bumper`.

## Lessons

- GLB parts without UV (e.g. Vans upper): unwrap per panel and keep each panel inside one texture tile (non-seamless prints show tile edges).
- KeyShot projected labels are not in the GLB UVs: use planar UV on the label mesh + `labels.py`.
- Translucent rubber exports as dark red: set `color` from the render, `drop_base`, `no_trans`.
- Moving a style to a new folder: renders stay under `base`; point `files` with `../newfolder/`.
- Offline: model-viewer from git `google/model-viewer` branch `gh-pages` (`node_modules/@google/model-viewer/dist/model-viewer.min.js`); npm/CDN are blocked in the sandbox.

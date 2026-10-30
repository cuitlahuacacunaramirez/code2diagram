# c2d - iso-diagram (standalone)

Describe an architecture in a small YAML file, get an **interactive isometric diagram** (three.js, one
self-contained `.html`) and a **PNG**. Layers are stacked slabs; links are orthogonal and use vertical
risers between layers.

## Quick start (PowerShell)

```powershell
cd H:\c_sandbox\c2d
.\start.ps1                 # venv + pip + assets + smoke render + starts the local service
# -> http://127.0.0.1:8765/   (pick a file; edit the YAML, refresh the page)

.\render.ps1 examples\llm-platform.iso.yaml -Png     # -> out\llm-platform.html + out\llm-platform.png
.\render.ps1 examples\llm-platform.iso.yaml -ValidateOnly
.\stop.ps1                  # stop the service
```

`start.ps1 -NoServer` only sets things up. `-Port 9000`, `-Open`, `-Reinstall` are available.
If script execution is blocked: `powershell -ExecutionPolicy Bypass -File .\start.ps1`.

Requirements: Python 3.10+ and network access on the first run (pip, three.js from jsDelivr, icon
packs from the npm registry). PNG export uses the Edge/Chrome already installed (headless, software
WebGL - no GPU needed; set `ISO_BROWSER` to use another browser). Everything installs under this folder
(`.venv`, `assets/`); nothing global is touched.

## Viewer

Drag = rotate, right-drag = pan, wheel = zoom. Hover/click a node to trace its links (click again to
unpin). Left panel: layer toggles, **Explode** slider, labels, runs-on links, light/dark theme and
**Export PNG** (2x, current view). `out/*.html` works offline from `file://`.

## Source format (`*.iso.yaml`)

```yaml
iso: 1
title: My platform
layers:                       # bottom -> top
  - id: hardware
    label: Hardware
    groups:
      rackA: { label: Rack A, kind: rack }          # kind: zone|cluster|namespace|rack|vlan|group, nest with `in:`
    nodes:
      gpu1: { kind: server, label: GPU node 1, in: rackA, note: shown in tooltip }
  - id: k8s
    label: Kubernetes
    nodes:
      node1: { kind: k8s-node, label: Worker 1, on: gpu1 }     # runs on -> dashed riser to the layer below
      pvc:   { kind: pvc, label: models, mount: nas }          # storage attachment -> riser
links:
  - { from: ui, to: api, label: HTTPS, class: external }       # internal|external|data|control|storage|management
```

* `level: <name>` on a layer puts several layers on the **same height as separate plates side by side**
  (each plate is sized to its own content, with a 3-cell street between plates that links cross on thin road
  decks). Layers without `level:` each get their own level. Levels stack in order of first appearance. See
  `examples/tpc-platform.iso.yaml`.
* ids are unique across all layers; `in:` stays inside a layer; `on:` / `mount:` may cross layers.
* `kind` picks icon + shape (see `isodiagram/kinds.py`; unknown kinds fall back to a generic cube with a warning).
* `icon: <pack>:<id>` overrides it - packs `isoflow`, `kubernetes`, `aws`, `azure`, `gcp` (ids = file names in
  `assets/icons/<pack>/`, e.g. `aws:aws-api-gateway`). Isoflow art is drawn as an upright isometric sprite; all
  other icons are flat and projected onto the top face of a tile.
* Layout is automatic (grid, groups packed in shelves; plates sized per layer, level spacing grows with the footprint - the Explode slider tunes it). Error messages name the offending id.
* Full schema: `schema/iso-diagram.schema.json` (use it for editor autocomplete via the YAML language server).

## CLI

```powershell
.\.venv\Scripts\python -m isodiagram render X.iso.yaml [-o out.html] [--png [out.png]] [--size 1920x1080] [--scale 2]
.\.venv\Scripts\python -m isodiagram validate X.iso.yaml
.\.venv\Scripts\python -m isodiagram scene X.iso.yaml        # intermediate JSON (debug)
.\.venv\Scripts\python -m isodiagram serve --dir mydiagrams --port 8765
```

## Layout of this folder

| Path | What |
|---|---|
| `isodiagram/` | Python package: `model` (parse+validate) -> `layout` (grid) -> `route` (A*) -> `scene` (JSON) -> `html` |
| `viewer/` | `viewer.js` (three.js scene) + `template.html` (UI) - inlined into every output |
| `assets/` | downloaded: `vendor/` (three.js r160, MIT), `icons/` (Isopacks: isoflow, kubernetes, aws, azure, gcp) |
| `tools/fetch_assets.py` | downloads/extracts the assets (stdlib only, idempotent) |
| `examples/` | test inputs |
| `out/` | generated HTML/PNG, service log + PID |
| `start.ps1` `stop.ps1` `render.ps1` | entry points |

## Known limits (v1)

* Parallel links can overlap on the same lane; many `on:` risers look busy (use the *Runs-on links* toggle).
* Node positions are automatic (no manual `at:` yet). Nodes are ordered so risers run roughly straight up.
* Icon licences differ per pack (Isopacks, Kubernetes: Apache-2.0/CC-BY-4.0, AWS/Azure/GCP: vendor terms) -
  see `assets/icons/manifest.json`; check them before publishing diagrams or the repo externally.
* Azure's terms ask not to distort icons; projecting them on a tile face does (decision recorded in `plan.md` section 10).

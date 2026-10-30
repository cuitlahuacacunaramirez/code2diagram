"""Download third-party assets into c2d/assets (idempotent).

  * three.js (module build + OrbitControls)  -> assets/vendor/
  * @isoflow/isopacks (npm tarball)          -> assets/icons/<pack>/<id>.svg + assets/icons/manifest.json
  * kubernetes/community icons are already part of the isopacks "kubernetes" pack.

Stdlib only, so it runs before any pip install.
"""
import argparse
import base64
import io
import json
import re
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
THREE_VERSION = "0.160.0"
THREE_FILES = {
    "three.module.js": f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/build/three.module.js",
    "OrbitControls.js": f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/examples/jsm/controls/OrbitControls.js",
}
ISOPACKS_META = "https://registry.npmjs.org/@isoflow/isopacks"
PACKS = ["isoflow", "kubernetes", "aws", "azure", "gcp"]

# {id:"x",name:"y",url:"data:image/svg+xml;base64,...."}  (minified JS, keys unquoted)
ICON_RE = re.compile(r'\{id:"([^"]+)",name:"([^"]*)",url:"(data:image/[^"]+)"')


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "c2d-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch_three() -> None:
    vendor = ASSETS / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    for name, url in THREE_FILES.items():
        dest = vendor / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  = {dest.relative_to(ROOT)} (cached)")
            continue
        print(f"  + {url}")
        dest.write_bytes(get(url))
    (vendor / "VERSION.txt").write_text(f"three.js r{THREE_VERSION} (MIT) - https://threejs.org\n")


def decode_data_uri(uri: str) -> bytes | None:
    head, _, payload = uri.partition(",")
    if ";base64" in head:
        return base64.b64decode(payload)
    return urllib.parse.unquote_to_bytes(payload)


def fetch_icons(packs: list[str]) -> None:
    icons_dir = ASSETS / "icons"
    manifest_path = icons_dir / "manifest.json"
    if manifest_path.exists() and all((icons_dir / p).is_dir() for p in packs):
        print("  = icons (cached)")
        return
    meta = json.loads(get(ISOPACKS_META))
    version = meta["dist-tags"]["latest"]
    tarball = meta["versions"][version]["dist"]["tarball"]
    print(f"  + {tarball}")
    tf = tarfile.open(fileobj=io.BytesIO(get(tarball)), mode="r:gz")
    manifest: dict = {"source": f"@isoflow/isopacks@{version}", "packs": {}}
    for pack in packs:
        member = tf.extractfile(f"package/dist/{pack}.js")
        if member is None:
            print(f"  ! pack {pack} missing", file=sys.stderr)
            continue
        js = member.read().decode("utf-8", "replace")
        out = icons_dir / pack
        out.mkdir(parents=True, exist_ok=True)
        ids = []
        for icon_id, _name, uri in ICON_RE.findall(js):
            data = decode_data_uri(uri)
            if not data:
                continue
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", icon_id)
            (out / f"{safe}.svg").write_bytes(data)
            ids.append(safe)
        manifest["packs"][pack] = ids
        print(f"    {pack}: {len(ids)} icons")
    lic = tf.extractfile("package/LICENSE")
    manifest["license_note"] = (lic.read().decode() if lic else "").strip() or (
        "See individual folders in the @isoflow/isopacks source for licence information."
    )
    manifest["terms"] = {
        "isoflow": "Isoflow generic icons (see @isoflow/isopacks)",
        "kubernetes": "Apache-2.0 or CC-BY-4.0; Kubernetes logo is a Linux Foundation trademark",
        "aws": "AWS Architecture Icons - https://aws.amazon.com/architecture/icons/",
        "azure": "Microsoft Azure icons - https://learn.microsoft.com/azure/architecture/icons/",
        "gcp": "Google Cloud icons - https://cloud.google.com/icons",
    }
    manifest_path.write_text(json.dumps(manifest, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", nargs="*", default=PACKS)
    a = ap.parse_args()
    print("three.js"); fetch_three()
    print("icons"); fetch_icons(a.packs)


if __name__ == "__main__":
    main()

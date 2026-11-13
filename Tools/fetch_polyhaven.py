#!/usr/bin/env python3
"""Descarga desde Poly Haven (CC0) los modelos y texturas de respaldo listados en
Scripts/asset_manifest.json usando su API publica oficial. Solo biblioteca estandar.

Uso:  python3 Tools/fetch_polyhaven.py
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "Scripts", "asset_manifest.json")
OUT = os.path.join(ROOT, "SourceAssets", "PolyHaven")
API = "https://api.polyhaven.com"
HEADERS = {"User-Agent": "vigilia-asset-fetch/1.0"}
TEXTURE_MAPS = {"Diffuse": "diff", "nor_dx": "nor_dx", "arm": "arm"}


def http_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def download(url, dest, expected_size=None):
    if os.path.exists(dest) and (expected_size is None or os.path.getsize(dest) == expected_size):
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
    os.replace(tmp, dest)
    return True


def pick_res(options, wanted):
    if wanted in options:
        return wanted
    order = ["1k", "2k", "4k", "8k"]
    for res in order[order.index(wanted):] if wanted in order else order:
        if res in options:
            return res
    return sorted(options)[0]


def fetch_model(asset_id, res):
    files = http_json(f"{API}/files/{asset_id}")
    gltf = files["gltf"]
    entry = gltf[pick_res(gltf, res)]["gltf"]
    base = os.path.join(OUT, "models", asset_id)
    count = download(entry["url"], os.path.join(base, asset_id + ".gltf"), entry.get("size"))
    for rel, inc in entry.get("include", {}).items():
        count += download(inc["url"], os.path.join(base, rel), inc.get("size"))
    return count


def fetch_texture(asset_id, res):
    files = http_json(f"{API}/files/{asset_id}")
    base = os.path.join(OUT, "textures", asset_id)
    count = 0
    for api_name, suffix in TEXTURE_MAPS.items():
        if api_name not in files:
            continue
        options = files[api_name]
        fmt = options[pick_res(options, res)]
        entry = fmt.get("jpg") or fmt.get("png")
        if not entry:
            continue
        ext = os.path.splitext(entry["url"])[1]
        count += download(entry["url"], os.path.join(base, f"{asset_id}_{suffix}{ext}"), entry.get("size"))
    return count


def main():
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)

    jobs = []
    for group in ("slots", "surfaces"):
        for name, slot in manifest[group].items():
            for src in slot["sources"]:
                if src["type"] == "polyhaven":
                    jobs.append((fetch_model, src["id"], src.get("res", "2k"), name))
                elif src["type"] == "polyhaven_texture":
                    jobs.append((fetch_texture, src["id"], src.get("res", "2k"), name))

    failed = []
    for index, (fn, asset_id, res, name) in enumerate(jobs, 1):
        try:
            new = fn(asset_id, res)
            print(f"[{index}/{len(jobs)}] {asset_id} ({res}) -> {name}: {'descargado' if new else 'ya estaba'}")
        except Exception as exc:  # noqa: BLE001 - se informa y se continua con el resto
            failed.append(asset_id)
            print(f"[{index}/{len(jobs)}] {asset_id}: ERROR {exc}", file=sys.stderr)

    total = 0
    for dirpath, _dirs, filenames in os.walk(OUT):
        total += sum(os.path.getsize(os.path.join(dirpath, f)) for f in filenames)
    print(f"Poly Haven: {len(jobs) - len(failed)}/{len(jobs)} assets en {OUT} ({total / 1e6:.0f} MB)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

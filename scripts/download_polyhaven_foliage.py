"""Download realistic photoscanned CC0 3D foliage models (trees, shrubs, 3D grass, potted plant, boulder)
and 4K 360° garden/treeline HDRI panorama from Poly Haven for Unreal Engine 5.8 ArchViz landscaping.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

OUT_DIR = Path("/home/hermes/blender-vast-ai/foliage")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = [
    "tree_small_02",
    "jacaranda_tree",
    "shrub_01",
    "shrub_02",
    "grass_medium_01",
    "potted_plant_01",
    "boulder_01",
]


def fetch_url(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1024:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    print(f"  [DL] {dest.name} ({dest.stat().st_size // 1024} KB)")


def main() -> None:
    # 1. Download 360° Meadow/Treeline HDRI (4K HDR + Tonemapped 8K JPG)
    fetch_url(
        "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/meadow_2_2k.hdr",
        OUT_DIR / "meadow_2_2k.hdr",
    )
    fetch_url(
        "https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/meadow_2.jpg",
        OUT_DIR / "meadow_2_env.jpg",
    )

    # 2. Download FBX + JPG/PNG textures (including alpha masks) for each 3D foliage asset
    for asset in ASSETS:
        print(f"=== Fetching {asset} ===")
        req = urllib.request.Request(f"https://api.polyhaven.com/files/{asset}", headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())

        fbx_info = data.get("fbx", {}).get("1k", {}).get("fbx", {})
        gltf_info = data.get("gltf", {}).get("1k", {}).get("gltf", {})

        fbx_url = fbx_info.get("url")
        if fbx_url:
            fetch_url(fbx_url, OUT_DIR / f"{asset}_1k.fbx")

        # Download all JPG textures from gltf_1k (diffuse, nor_gl, arm/rough)
        for rel_path, meta in gltf_info.get("include", {}).items():
            if rel_path.endswith((".jpg", ".png")):
                fn = Path(rel_path).name
                fetch_url(meta["url"], OUT_DIR / fn)

        # Download any PNG alpha/mask/diffuse textures from fbx_1k
        for rel_path, meta in fbx_info.get("include", {}).items():
            if any(k in rel_path for k in ("alpha", "mask", "leaves_diff", "twig_diff", "branch_diff", "trunk_diff")):
                if rel_path.endswith((".png", ".jpg")):
                    fn = Path(rel_path).name
                    fetch_url(meta["url"], OUT_DIR / fn)

    print("[OK] All Poly Haven 3D foliage models & HDRI downloaded to", OUT_DIR)


if __name__ == "__main__":
    main()

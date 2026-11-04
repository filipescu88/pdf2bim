"""Generate a photorealistic 2048x2048 8-plank architectural timber cladding PBR texture set:
- facade_timber_cladding_diffuse.jpg (natural muted European oak / larch, zero orange/red saturation, per-plank color variation, visible wood fibers & subtle weathering)
- facade_timber_cladding_nor_gl.jpg (combined micro-fiber + knot normals + per-plank surface undulation + beveled board edges)
- facade_timber_cladding_rough.jpg (calibrated physical matte-satin wood roughness 0.68..0.88)
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

TEX_SRC_DIR = Path("/home/hermes/blender-vast-ai/textures")
OUT_DIRS = [
    Path("/home/hermes/blender-vast-ai/textures"),
    Path("/home/hermes/pdf-to-bim-unreal-pipeline/web_vr/textures"),
]


def load_rgb_float(path: Path, size: int = 2048) -> np.ndarray:
    img = Image.open(path).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def load_gray_float(path: Path, size: int = 2048) -> np.ndarray:
    img = Image.open(path).convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def build_timber_pbr() -> None:
    N = 2048
    n_planks = 8
    plank_h = N // n_planks  # 256 px per plank (= 14.5 cm real height)

    # 1. Load source textures:
    # - oak_countertop_diffuse: vertical fine oak fibers -> transpose (rotate 90 deg) so fibers run horizontally!
    oak_diff = np.transpose(load_rgb_float(TEX_SRC_DIR / "oak_countertop_diffuse.jpg", N), (1, 0, 2))
    oak_norm = np.transpose(load_rgb_float(TEX_SRC_DIR / "oak_veneer_nor_gl.jpg", N), (1, 0, 2))
    # Swap R and G channels of normal map after 90-degree transpose so tangent/bitangent match horizontal fibers
    oak_norm_rot = oak_norm.copy()
    oak_norm_rot[:, :, 0] = oak_norm[:, :, 1]
    oak_norm_rot[:, :, 1] = oak_norm[:, :, 0]
    oak_rough = np.transpose(load_gray_float(TEX_SRC_DIR / "oak_veneer_rough.jpg", N), (1, 0))

    # - wood_floor_deck: horizontal planks with organic knots, growth rings, and natural weathering
    deck_diff = load_rgb_float(TEX_SRC_DIR / "wood_floor_deck_diffuse.jpg", N)
    deck_norm = load_rgb_float(TEX_SRC_DIR / "wood_floor_deck_nor_gl.jpg", N)
    deck_rough = load_gray_float(TEX_SRC_DIR / "wood_floor_deck_rough.jpg", N)

    # 2. Extract pure luminance & detail from deck_diff without its artificial red-orange stain
    deck_luma = (
        0.299 * deck_diff[:, :, 0]
        + 0.587 * deck_diff[:, :, 1]
        + 0.114 * deck_diff[:, :, 2]
    )
    # Normalize deck_luma around 1.0 with rich contrast for knots and grain
    deck_luma_norm = np.clip((deck_luma / (np.mean(deck_luma) + 1e-6)), 0.42, 1.45)
    # High-frequency fiber detail from oak_diff
    oak_luma = (
        0.299 * oak_diff[:, :, 0]
        + 0.587 * oak_diff[:, :, 1]
        + 0.114 * oak_diff[:, :, 2]
    )
    oak_luma_norm = np.clip((oak_luma / (np.mean(oak_luma) + 1e-6)), 0.65, 1.35)

    # Base natural European oak / thermo-larch RGB color (earthy, muted taupe-brown — ZERO red/orange/yellow glare!)
    base_rgb = np.array([0.45, 0.37, 0.29], dtype=np.float32)

    out_diff = np.zeros((N, N, 3), dtype=np.float32)
    out_norm = np.zeros((N, N, 3), dtype=np.float32)
    out_rough = np.zeros((N, N), dtype=np.float32)

    # Distinct natural per-plank color & tone profiles (luminance mult, R-G-B tint shift, roughness offset)
    plank_profiles = [
        (1.07, np.array([1.01, 1.00, 0.98]), -0.02, 137, False),  # 0: Light warm natural oak
        (0.89, np.array([0.96, 0.99, 1.04]), +0.03, 521, True),   # 1: Cooler weathered taupe-oak
        (0.98, np.array([0.99, 1.00, 1.01]),  0.00, 947, False),  # 2: Classic medium European oak
        (1.10, np.array([1.01, 1.01, 0.98]), -0.02, 1381, True),  # 3: Sun-bleached pale ash-oak
        (0.82, np.array([0.95, 0.97, 1.03]), +0.04, 1723, False), # 4: Deep heartwood umber-oak (no red!)
        (1.03, np.array([1.00, 1.00, 1.00]), -0.01, 293, True),   # 5: Natural brushed medium-light oak
        (0.92, np.array([0.95, 0.99, 1.05]), +0.03, 769, False),  # 6: Muted silvered-brown weathered timber
        (0.86, np.array([0.98, 0.98, 1.00]), +0.02, 1193, True),  # 7: Rich natural medium-dark oak
    ]

    x_coords = np.linspace(0.0, 2.0 * np.pi, N, endpoint=False, dtype=np.float32)[None, :]
    y_plank = np.linspace(0.0, 1.0, plank_h, endpoint=False, dtype=np.float32)[:, None]

    for p_idx in range(n_planks):
        y0 = p_idx * plank_h
        y1 = y0 + plank_h
        luma_mult, rgb_tint, r_off, x_shift, flip_x = plank_profiles[p_idx]

        # Sample different vertical & horizontal regions of oak (seamless) and a single interior plank of deck (10 planks in 2048 px)
        oak_y0 = ((p_idx * 317) % (N - plank_h))
        deck_src_idx = (p_idx * 3 + 1) % 10
        # Each of the 10 planks in wood_floor_deck is ~204.8 px tall; sample the clean inner 152 px [26..178] free of seams!
        dy_start = int(round(deck_src_idx * (N / 10.0))) + 26
        dy_end = min(N, dy_start + 152)

        def resample_strip(arr_slice: np.ndarray) -> np.ndarray:
            # Linearly interpolate along axis 0 from (dy_end - dy_start) to plank_h (256)
            src_h = arr_slice.shape[0]
            t = np.linspace(0, src_h - 1, plank_h, dtype=np.float32)
            i0 = np.floor(t).astype(np.int32)
            i1 = np.minimum(src_h - 1, i0 + 1)
            w = (t - i0)[:, None] if arr_slice.ndim == 2 else (t - i0)[:, None, None]
            return arr_slice[i0] * (1.0 - w) + arr_slice[i1] * w

        o_l = np.roll(oak_luma_norm[oak_y0 : oak_y0 + plank_h, :], x_shift, axis=1)
        d_l = np.roll(resample_strip(deck_luma_norm[dy_start:dy_end, :]), x_shift * 2, axis=1)
        o_n = np.roll(oak_norm_rot[oak_y0 : oak_y0 + plank_h, :, :], x_shift, axis=1)
        d_n = np.roll(resample_strip(deck_norm[dy_start:dy_end, :, :]), x_shift * 2, axis=1)
        o_r = np.roll(oak_rough[oak_y0 : oak_y0 + plank_h, :], x_shift, axis=1)
        d_r = np.roll(resample_strip(deck_rough[dy_start:dy_end, :]), x_shift * 2, axis=1)

        if flip_x:
            o_l = o_l[:, ::-1]
            d_l = d_l[:, ::-1]
            o_n = o_n[:, ::-1, :]
            d_n = d_n[:, ::-1, :]
            o_r = o_r[:, ::-1]
            d_r = d_r[:, ::-1]

        # Combine fine oak fibers (65%) with organic knots/rings from deck (35%)
        combined_grain = 0.65 * o_l + 0.35 * d_l
        # Enhance fiber contrast around 1.0 so longitudinal wood fibers are crisp from a distance
        combined_grain = 1.0 + (combined_grain - 1.0) * 1.38

        # Subtle natural weathering & longitudinal patina variation along the board
        weather_wave = (
            1.0
            + 0.045 * np.sin(x_coords * 2.0 + p_idx * 1.7)
            + 0.030 * np.cos(x_coords * 5.0 - p_idx * 2.3)
        )
        # Edge aging/darkening near top and bottom tongue-and-groove joints
        edge_dist = np.minimum(y_plank, 1.0 - y_plank)  # 0 at seam, 0.5 at plank center
        edge_weather = np.clip(edge_dist / 0.075, 0.65, 1.0)
        # Recessed shadow groove at top 5 px and bottom 5 px of each plank
        groove_mask = np.clip((edge_dist - 0.018) / 0.022, 0.14, 1.0)

        plank_rgb = (
            base_rgb[None, None, :]
            * rgb_tint[None, None, :]
            * luma_mult
            * combined_grain[:, :, None]
            * weather_wave[:, :, None]
            * edge_weather[:, :, None]
            * groove_mask[:, :, None]
        )
        # Desaturate toward natural earthy oak/larch (prevents yellow/orange glare in warm sunlight!)
        plank_luma = (
            0.299 * plank_rgb[:, :, 0]
            + 0.587 * plank_rgb[:, :, 1]
            + 0.114 * plank_rgb[:, :, 2]
        )[:, :, None]
        sat_factor = np.clip(0.58 + 0.14 * combined_grain[:, :, None], 0.52, 0.76)
        plank_rgb = plank_luma + (plank_rgb - plank_luma) * sat_factor

        out_diff[y0:y1, :, :] = np.clip(plank_rgb, 0.03, 0.92)

        # 3. Normal Map: combine fine oak fiber normals + deck knot normals + subtle surface planing undulation + plank bevel
        n_oak_xy = (o_n[:, :, :2] * 2.0 - 1.0) * 1.55
        n_deck_xy = (d_n[:, :, :2] * 2.0 - 1.0) * 1.15
        # Subtle low-frequency surface planing undulation per plank ("Subtelne nierówności powierzchni")
        undul_x = 0.07 * np.cos(x_coords * 3.0 + p_idx * 1.1) + 0.05 * np.sin(x_coords * 7.0 - p_idx * 2.9)
        undul_y = 0.09 * np.sin(y_plank * 2.0 * np.pi * 2.0 + p_idx * 0.9)
        # Beveled edge normal at top and bottom of plank
        bevel_y = np.zeros_like(y_plank)
        bevel_y[y_plank < 0.045] = +0.68 * (1.0 - y_plank[y_plank < 0.045] / 0.045)
        bevel_y[y_plank > 0.955] = -0.68 * ((y_plank[y_plank > 0.955] - 0.955) / 0.045)

        nx = np.clip(0.58 * n_oak_xy[:, :, 0] + 0.42 * n_deck_xy[:, :, 0] + undul_x, -0.95, 0.95)
        ny = np.clip(0.58 * n_oak_xy[:, :, 1] + 0.42 * n_deck_xy[:, :, 1] + undul_y + bevel_y, -0.95, 0.95)
        nz = np.sqrt(np.maximum(0.05, 1.0 - nx * nx - ny * ny))

        out_norm[y0:y1, :, 0] = nx * 0.5 + 0.5
        out_norm[y0:y1, :, 1] = ny * 0.5 + 0.5
        out_norm[y0:y1, :, 2] = nz * 0.5 + 0.5

        # 4. Roughness Map: calibrated natural exterior timber roughness [0.68 .. 0.90], mean ~0.78
        raw_r = 0.55 * o_r + 0.45 * d_r
        # Darker grain pores & weathered seams are rougher (more matte)
        grain_rough = 0.76 + (raw_r - np.mean(raw_r)) * 0.32 - (combined_grain - 1.0) * 0.14 + r_off
        groove_rough = np.where(edge_dist < 0.03, 0.90, grain_rough)
        out_rough[y0:y1, :] = np.clip(groove_rough, 0.66, 0.92)

    diff_img = Image.fromarray((out_diff * 255.0).astype(np.uint8), mode="RGB")
    norm_img = Image.fromarray((out_norm * 255.0).astype(np.uint8), mode="RGB")
    rough_img = Image.fromarray((out_rough * 255.0).astype(np.uint8), mode="L")

    for out_dir in OUT_DIRS:
        if out_dir.is_dir():
            diff_img.save(out_dir / "facade_timber_cladding_diffuse.jpg", quality=95)
            norm_img.save(out_dir / "facade_timber_cladding_nor_gl.jpg", quality=95)
            rough_img.save(out_dir / "facade_timber_cladding_rough.jpg", quality=95)
            print(f"[OK] Saved 2K timber PBR textures to {out_dir}")


if __name__ == "__main__":
    build_timber_pbr()

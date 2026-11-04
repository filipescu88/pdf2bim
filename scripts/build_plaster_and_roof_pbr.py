"""Generate 2K PBR texture sets for:
1. Exterior mineral/silicone stucco plaster (`facade_stucco_plaster_*`):
   - Realistic "baranek" 1.5 mm mineral grain micro-texture
   - Subtle hand-troweled surface undulations (delikatne nierownosci powierzchni)
   - Physically calibrated matte mineral Roughness (0.82..0.96, mean ~0.89)
   - Natural warm architectural off-white tone
2. Anthracite roof tiles (`roof_tiles_anthracite_*`):
   - Clean ceramic/mineral anthracite tiles without yellow moss artifacts
   - Subtle tile-to-tile color & luminance variations (subtelne roznice kolorystyczne)
   - Pronounced 3D tile overlap & joint normal map + micro-surface relief
   - Natural matte-satin Roughness (0.68..0.88, mean ~0.77, zero plastic/metallic glare)
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

TEX_DIR = Path("/home/hermes/blender-vast-ai/textures")
SIZE = 2048


def gaussian_blur_periodic(arr: np.ndarray, sigma: float) -> np.ndarray:
    """Exact periodic 2D Gaussian blur via FFT (guarantees 100% seamless tile boundaries)."""
    h, w = arr.shape[:2]
    fy = np.fft.fftfreq(h, d=1.0)[:, None]
    fx = np.fft.rfftfreq(w, d=1.0)[None, :]
    kernel_ft = np.exp(-2.0 * (np.pi * sigma) ** 2 * (fy * fy + fx * fx)).astype(np.float32)
    return np.fft.irfft2(np.fft.rfft2(arr) * kernel_ft, s=(h, w)).astype(np.float32)


def tileable_fbm(h: int, w: int, freqs: list[tuple[int, float]], seed: int) -> np.ndarray:
    """Generate seamless periodic multi-octave noise in [-1, 1]."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), dtype=np.float32)
    yy = np.linspace(0.0, 2.0 * np.pi, h, endpoint=False, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 2.0 * np.pi, w, endpoint=False, dtype=np.float32)[None, :]
    for k, weight in freqs:
        # Generate small periodic grid of size (k, k) and upsample bicubically with wrap
        grid = rng.standard_normal((k, k)).astype(np.float32)
        pad = np.pad(grid, 2, mode="wrap")
        pil_g = Image.fromarray(pad, mode="F").resize(( int(w * (k + 4) / k), int(h * (k + 4) / k) ), Image.Resampling.BICUBIC)
        arr = np.asarray(pil_g, dtype=np.float32)
        margin_y = int(round(2 * h / k))
        margin_x = int(round(2 * w / k))
        crop = arr[margin_y : margin_y + h, margin_x : margin_x + w]
        acc += weight * crop
    std = float(np.std(acc)) + 1e-6
    return np.clip(acc / (2.5 * std), -1.0, 1.0)


def height_to_normal(height_map: np.ndarray, strength: float) -> np.ndarray:
    """Convert periodic height map in [0, 1] to OpenGL Normal Map [H, W, 3] in [0, 1]."""
    dy = np.roll(height_map, -1, axis=0) - np.roll(height_map, 1, axis=0)
    dx = np.roll(height_map, -1, axis=1) - np.roll(height_map, 1, axis=1)
    nx = -dx * strength
    ny = dy * strength  # OpenGL Y+ up
    nz = np.ones_like(height_map)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    nx /= norm
    ny /= norm
    nz /= norm
    return np.stack([0.5 + 0.5 * nx, 0.5 + 0.5 * ny, 0.5 + 0.5 * nz], axis=-1)


def build_stucco_plaster() -> None:
    rng = np.random.default_rng(1042)
    base_diff = np.asarray(
        Image.open(TEX_DIR / "painted_plaster_wall_diffuse.jpg").convert("RGB").resize((SIZE, SIZE), Image.Resampling.BICUBIC),
        dtype=np.float32,
    ) / 255.0
    base_nor = np.asarray(
        Image.open(TEX_DIR / "painted_plaster_wall_nor_gl.jpg").convert("RGB").resize((SIZE, SIZE), Image.Resampling.BICUBIC),
        dtype=np.float32,
    ) / 255.0

    # 1. Multi-scale height field for realistic mineral "baranek" stucco + gentle trowel undulations
    # High-frequency silica sand aggregate (1.5-2.0 mm mineral granules & pits)
    grain_raw = rng.standard_normal((SIZE, SIZE)).astype(np.float32)
    grain_fine = gaussian_blur_periodic(grain_raw, sigma=1.05)
    grain_fine /= float(np.std(grain_fine)) + 1e-6

    # Medium mineral stucco pits ("baranek" 2mm aggregate rubbing grooves)
    pits_raw = rng.standard_normal((SIZE, SIZE)).astype(np.float32)
    pits = gaussian_blur_periodic(pits_raw, sigma=2.2)
    pits /= float(np.std(pits)) + 1e-6
    pits_coarse = gaussian_blur_periodic(rng.standard_normal((SIZE, SIZE)).astype(np.float32), sigma=4.5)
    pits_coarse /= float(np.std(pits_coarse)) + 1e-6
    baranek_grooves = -np.abs(pits) * 0.55 - np.abs(pits_coarse) * 0.35 + 0.45 * grain_fine

    # Medium & low-frequency hand-troweled surface undulations ("delikatne nierownosci powierzchni")
    macro_waves = tileable_fbm(
        SIZE,
        SIZE,
        [(4, 1.0), (8, 0.85), (16, 0.65), (32, 0.45), (64, 0.30)],
        seed=2026,
    )

    # 2. Diffuse map: natural warm architectural off-white [0.92, 0.905, 0.875]
    # with clear mineral micro-shadowing in stucco pits so sunlit walls show real plaster grain
    base_gray = np.mean(base_diff, axis=-1)
    base_gray = (base_gray - float(np.mean(base_gray))) / (float(np.std(base_gray)) + 1e-6)
    micro_ao = np.clip(0.54 + 0.28 * baranek_grooves + 0.20 * macro_waves + 0.10 * base_gray, 0.0, 1.0)

    warm_white = np.array([0.945, 0.932, 0.902], dtype=np.float32)
    warm_shadow = np.array([0.745, 0.728, 0.692], dtype=np.float32)
    plaster_rgb = warm_shadow[None, None, :] + micro_ao[:, :, None] * (warm_white - warm_shadow)[None, None, :]
    # Subtle warm/cool mineral aggregate fleck variation
    color_fleck = rng.standard_normal((SIZE, SIZE, 3)).astype(np.float32) * 0.012
    plaster_rgb = np.clip(plaster_rgb + color_fleck, 0.68, 0.97)

    # 3. Normal map: strong mineral stucco grain + pronounced hand-troweled undulations
    n_micro = height_to_normal(baranek_grooves, strength=4.2)
    n_macro = height_to_normal(macro_waves, strength=7.5)
    nx = (base_nor[:, :, 0] - 0.5) * 2.5 + (n_micro[:, :, 0] - 0.5) * 3.2 + (n_macro[:, :, 0] - 0.5) * 2.8
    ny = (base_nor[:, :, 1] - 0.5) * 2.5 + (n_micro[:, :, 1] - 0.5) * 3.2 + (n_macro[:, :, 1] - 0.5) * 2.8
    nz = np.ones((SIZE, SIZE), dtype=np.float32)
    n_len = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    plaster_nor = np.stack([0.5 + 0.5 * (nx / n_len), 0.5 + 0.5 * (ny / n_len), 0.5 + 0.5 * (nz / n_len)], axis=-1)
    plaster_nor = np.clip(plaster_nor, 0.0, 1.0)

    # 4. Roughness map: physically calibrated mineral facade plaster (0.82..0.97, mean ~0.90)
    plaster_rough = np.clip(0.90 - 0.055 * baranek_grooves - 0.035 * macro_waves, 0.80, 0.98)

    Image.fromarray((plaster_rgb * 255.0).round().astype(np.uint8), mode="RGB").save(
        TEX_DIR / "facade_stucco_plaster_diffuse.jpg", quality=95
    )
    Image.fromarray((plaster_nor * 255.0).round().astype(np.uint8), mode="RGB").save(
        TEX_DIR / "facade_stucco_plaster_nor_gl.jpg", quality=95
    )
    Image.fromarray((plaster_rough * 255.0).round().astype(np.uint8), mode="L").save(
        TEX_DIR / "facade_stucco_plaster_rough.jpg", quality=95
    )
    print(
        f"[OK] Built 2K Stucco Plaster PBR | diff={plaster_rgb.mean(axis=(0,1)).round(3)} "
        f"| nor_std={plaster_nor.std(axis=(0,1)).round(3)} | rough={plaster_rough.mean():.3f}"
    )


def build_roof_tiles_anthracite() -> None:
    rng = np.random.default_rng(7077)
    src_diff = np.asarray(
        Image.open(TEX_DIR / "grey_roof_tiles_02_diffuse.jpg").convert("RGB").resize((SIZE, SIZE), Image.Resampling.BICUBIC),
        dtype=np.float32,
    ) / 255.0
    src_nor = np.asarray(
        Image.open(TEX_DIR / "grey_roof_tiles_02_nor_gl.jpg").convert("RGB").resize((SIZE, SIZE), Image.Resampling.BICUBIC),
        dtype=np.float32,
    ) / 255.0
    src_rough = np.asarray(
        Image.open(TEX_DIR / "grey_roof_tiles_02_rough.jpg").convert("L").resize((SIZE, SIZE), Image.Resampling.BICUBIC),
        dtype=np.float32,
    ) / 255.0

    # 1. Remove yellow/green moss and bright white bird-dropping spots from grey_roof_tiles_02_diffuse
    lum = 0.299 * src_diff[:, :, 0] + 0.587 * src_diff[:, :, 1] + 0.114 * src_diff[:, :, 2]
    # Detect moss (high R+G vs B) and white lichen spots (high lum)
    yellowness = np.maximum(0.0, 0.5 * (src_diff[:, :, 0] + src_diff[:, :, 1]) - src_diff[:, :, 2])
    clean_lum = lum.copy()
    # Suppress white spots and dark moss blobs toward local tile median
    blur_lum = gaussian_blur_periodic(clean_lum, sigma=18.0)
    spot_mask = np.clip((np.abs(clean_lum - blur_lum) - 0.065) * 8.0 + yellowness * 6.0, 0.0, 1.0)
    clean_lum = clean_lum * (1.0 - 0.82 * spot_mask) + blur_lum * (0.82 * spot_mask)

    # 2. Segment exact individual tiles directly from the mortar/overlap joint lines in normal + diffuse
    # Joint strength is high where normal deviates strongly from (0.5, 0.5) or luminance drops at tile seams
    joint_grad = np.hypot(src_nor[:, :, 0] - 0.5, src_nor[:, :, 1] - 0.5)
    local_min = gaussian_blur_periodic(clean_lum, sigma=6.0) - clean_lum
    seam_score = gaussian_blur_periodic(joint_grad * 2.2 + np.maximum(0.0, local_min) * 3.5, sigma=1.8)

    # Find horizontal course y-boundaries (11 courses in grey_roof_tiles_02) from row-averaged seam_score
    n_courses = 11
    row_prof = seam_score.mean(axis=1)
    y_seams = []
    step_y = SIZE / float(n_courses)
    for r in range(n_courses):
        c_y = int(round(r * step_y))
        win = [((c_y + dy) % SIZE) for dy in range(-22, 23)]
        best_y = win[int(np.argmax(row_prof[win]))]
        y_seams.append(best_y)
    y_seams = sorted(y_seams)

    # Within each of the 11 courses, find vertical joint x-peaks and assign exact per-tile variation
    t_lum_map = np.zeros((SIZE, SIZE), dtype=np.float32)
    t_warm_map = np.zeros((SIZE, SIZE), dtype=np.float32)
    t_rough_map = np.zeros((SIZE, SIZE), dtype=np.float32)
    t_tilt_x = np.zeros((SIZE, SIZE), dtype=np.float32)
    t_tilt_y = np.zeros((SIZE, SIZE), dtype=np.float32)
    course_ao = np.ones((SIZE, SIZE), dtype=np.float32)

    for r in range(n_courses):
        y0 = y_seams[r]
        y1 = y_seams[(r + 1) % n_courses]
        if y1 > y0:
            y_idx = np.arange(y0, y1)
        else:
            y_idx = np.arange(y0, y1 + SIZE) % SIZE
        h_c = len(y_idx)
        # Course vertical AO profile (subtle shadow under upper tile lip, natural exposure on lower half)
        t_y = np.linspace(0.0, 1.0, h_c, dtype=np.float32)[:, None]
        course_ao[y_idx, :] = 0.89 + 0.14 * np.sin(t_y * np.pi)

        # Column profile of vertical joints inside this course (exclude top/bottom 18 px horizontal seam)
        inner_y = y_idx[min(18, h_c // 4) : max(h_c - 18, 3 * h_c // 4)]
        col_prof = np.abs(src_nor[inner_y, :, 0] - 0.5).mean(axis=0)
        # Find local peaks in col_prof separated by at least 170 px
        x_seams = []
        cand = np.argsort(col_prof)[::-1]
        for cx in cand:
            if col_prof[cx] < 0.045:
                break
            if all(min(abs(int(cx) - sx), SIZE - abs(int(cx) - sx)) >= 165 for sx in x_seams):
                x_seams.append(int(cx))
        x_seams = sorted(x_seams) if len(x_seams) >= 4 else [int(round(k * SIZE / 7.0)) for k in range(7)]

        n_t = len(x_seams)
        for c in range(n_t):
            x0 = x_seams[c]
            x1 = x_seams[(c + 1) % n_t]
            if x1 > x0:
                x_idx = np.arange(x0, x1)
            else:
                x_idx = np.arange(x0, x1 + SIZE) % SIZE
            dv = float(rng.uniform(-0.075, 0.085))
            dw = float(rng.uniform(-0.015, 0.015))
            dr = float(rng.uniform(-0.045, 0.050))
            tx = float(rng.uniform(-0.035, 0.035))
            ty = float(rng.uniform(-0.040, 0.040))
            t_lum_map[np.ix_(y_idx, x_idx)] = dv
            t_warm_map[np.ix_(y_idx, x_idx)] = dw
            t_rough_map[np.ix_(y_idx, x_idx)] = dr
            t_tilt_x[np.ix_(y_idx, x_idx)] = tx
            t_tilt_y[np.ix_(y_idx, x_idx)] = ty

    # Feather slightly across the true joint seams (sigma=2.0 px)
    t_lum_map = gaussian_blur_periodic(t_lum_map, sigma=2.0)
    t_warm_map = gaussian_blur_periodic(t_warm_map, sigma=2.0)
    t_rough_map = gaussian_blur_periodic(t_rough_map, sigma=2.0)
    t_tilt_x = gaussian_blur_periodic(t_tilt_x, sigma=2.0)
    t_tilt_y = gaussian_blur_periodic(t_tilt_y, sigma=2.0)

    # Fine ceramic/slate mineral grain
    fine_grain = rng.standard_normal((SIZE, SIZE)).astype(np.float32)
    fine_grain = gaussian_blur_periodic(fine_grain, sigma=1.0)
    fine_grain /= float(np.std(fine_grain)) + 1e-6

    # Base anthracite ceramic/concrete tile palette (natural deep charcoal-slate [0.21, 0.22, 0.235])
    rel_detail = (clean_lum - float(np.mean(clean_lum))) * 0.90
    tile_val = np.clip((0.225 + rel_detail * 0.45 + t_lum_map * 0.28 + fine_grain * 0.008) * course_ao, 0.08, 0.40)

    roof_rgb = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    roof_rgb[:, :, 0] = tile_val * (0.97 + t_warm_map)
    roof_rgb[:, :, 1] = tile_val * 1.00
    roof_rgb[:, :, 2] = tile_val * (1.04 - t_warm_map)
    roof_rgb = np.clip(roof_rgb, 0.07, 0.42)

    # 3. Normal map: amplify tile overlap step & side joints + subtle per-tile tilt + ceramic micro-grain
    n_fine = height_to_normal(fine_grain * 0.5, strength=1.1)
    nx = (src_nor[:, :, 0] - 0.5) * 3.1 + t_tilt_x + (n_fine[:, :, 0] - 0.5) * 0.85
    ny = (src_nor[:, :, 1] - 0.5) * 3.4 + t_tilt_y + (n_fine[:, :, 1] - 0.5) * 0.85
    nz = np.ones((SIZE, SIZE), dtype=np.float32)
    n_len = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    roof_nor = np.stack([0.5 + 0.5 * (nx / n_len), 0.5 + 0.5 * (ny / n_len), 0.5 + 0.5 * (nz / n_len)], axis=-1)
    roof_nor = np.clip(roof_nor, 0.0, 1.0)

    # 4. Roughness map: realistic matte-satin ceramic/concrete roof tile (0.68..0.88, mean ~0.77)
    # Tile recesses/overlap joints are rougher (0.87), flat tile faces have natural matte-satin (0.72..0.80)
    src_r_centered = src_rough - float(np.mean(src_rough))
    roof_rough = np.clip(0.77 + 0.45 * src_r_centered + t_rough_map - 0.03 * (course_ao - 0.95), 0.65, 0.91)

    Image.fromarray((roof_rgb * 255.0).round().astype(np.uint8), mode="RGB").save(
        TEX_DIR / "roof_tiles_anthracite_diffuse.jpg", quality=95
    )
    Image.fromarray((roof_nor * 255.0).round().astype(np.uint8), mode="RGB").save(
        TEX_DIR / "roof_tiles_anthracite_nor_gl.jpg", quality=95
    )
    Image.fromarray((roof_rough * 255.0).round().astype(np.uint8), mode="L").save(
        TEX_DIR / "roof_tiles_anthracite_rough.jpg", quality=95
    )
    print(
        f"[OK] Built 2K Anthracite Roof Tiles PBR | diff={roof_rgb.mean(axis=(0,1)).round(3)} "
        f"| nor_std={roof_nor.std(axis=(0,1)).round(3)} | rough={roof_rough.mean():.3f}"
    )


if __name__ == "__main__":
    build_stucco_plaster()
    build_roof_tiles_anthracite()

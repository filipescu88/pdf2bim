"""Generate 2K PBR Lawn Turf textures, 1K 3D Grass Blade Ribbon Atlas, and recolor Poly Haven grass_medium_01 to lush green."""
import os
import math
import numpy as np
from PIL import Image, ImageDraw

fol_dir = "/home/hermes/blender-vast-ai/foliage"
tex_dir = "/home/hermes/blender-vast-ai/textures"


def gaussian_blur_periodic(arr: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0.0:
        return arr
    H, W = arr.shape[:2]
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.rfftfreq(W)[None, :]
    kern = np.exp(-2.0 * (math.pi ** 2) * (sigma ** 2) * (fx * fx + fy * fy)).astype(np.float32)
    if arr.ndim == 2:
        return np.fft.irfft2(np.fft.rfft2(arr) * kern, s=(H, W)).astype(np.float32)
    out = np.empty_like(arr, dtype=np.float32)
    for c in range(arr.shape[2]):
        out[:, :, c] = np.fft.irfft2(np.fft.rfft2(arr[:, :, c]) * kern, s=(H, W))
    return out


# ---------------------------------------------------------------------------
# 1. Generate 2048x2048 Seamless Lawn Turf PBR (lawn_turf_2k_*)
# ---------------------------------------------------------------------------
rng = np.random.default_rng(20261105)
H, W = 2048, 2048

n_base = rng.standard_normal((H, W)).astype(np.float32)
# Multi-scale organic turf patches (moisture / clover / blade density variation)
macro_1 = gaussian_blur_periodic(n_base, 140.0)
macro_1 = (macro_1 - macro_1.mean()) / (macro_1.std() + 1e-6)
macro_2 = gaussian_blur_periodic(n_base, 42.0)
macro_2 = (macro_2 - macro_2.mean()) / (macro_2.std() + 1e-6)

# Directional fine grass blade strokes at multiple angles
blade_height = np.zeros((H, W), dtype=np.float32)
blade_shade = np.zeros((H, W), dtype=np.float32)
for ang_deg, sig_x, sig_y, weight in [
    (15.0, 1.4, 9.5, 0.35),
    (-22.0, 1.4, 8.5, 0.35),
    (52.0, 1.6, 7.5, 0.25),
    (-60.0, 1.6, 7.5, 0.25),
    (2.0, 1.1, 12.0, 0.30),
]:
    raw = rng.standard_normal((H, W)).astype(np.float32)
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.rfftfreq(W)[None, :]
    th = math.radians(ang_deg)
    rx = fx * math.cos(th) - fy * math.sin(th)
    ry = fx * math.sin(th) + fy * math.cos(th)
    kern = np.exp(-2.0 * (math.pi ** 2) * ((sig_x * rx) ** 2 + (sig_y * ry) ** 2)).astype(np.float32)
    layer = np.fft.irfft2(np.fft.rfft2(raw) * kern, s=(H, W)).astype(np.float32)
    layer = (layer - layer.mean()) / (layer.std() + 1e-6)
    # Sharp ridge profile for individual grass blades
    ridges = np.clip(layer * 0.65 + 0.5, 0.0, 1.0) ** 1.6
    blade_height = np.maximum(blade_height, ridges * weight * 2.4)
    blade_shade += layer * weight

blade_shade = (blade_shade - blade_shade.mean()) / (blade_shade.std() + 1e-6)
height_map = np.clip(blade_height + 0.18 * macro_2 + 0.12 * macro_1, 0.0, 1.5)

# Rich natural chlorophyll palette (deep root shadow -> emerald mid -> warm sunlit tip)
col = np.zeros((H, W, 3), dtype=np.float32)
# Base emerald-olive lawn tone
col[:, :, 0] = 54.0 + 14.0 * blade_shade + 8.0 * macro_1 + 5.0 * macro_2
col[:, :, 1] = 96.0 + 22.0 * blade_shade + 11.0 * macro_1 + 7.0 * macro_2
col[:, :, 2] = 34.0 + 9.0 * blade_shade + 4.0 * macro_1 + 3.0 * macro_2

# Darken roots between blades (ambient occlusion in the turf)
ao_mask = np.clip((blade_height - 0.22) / 0.55, 0.0, 1.0)
for c, mult in enumerate([0.55, 0.60, 0.52]):
    col[:, :, c] *= (mult + (1.0 - mult) * ao_mask)

col_u8 = np.clip(col, 0, 255).astype(np.uint8)
Image.fromarray(col_u8, mode="RGB").save(os.path.join(tex_dir, "lawn_turf_2k_diffuse.jpg"), quality=94)

# Normal map from height_map
gx = (np.roll(height_map, -1, axis=1) - np.roll(height_map, 1, axis=1)) * 2.8
gy = (np.roll(height_map, -1, axis=0) - np.roll(height_map, 1, axis=0)) * 2.8
nz = np.ones_like(height_map)
norm = np.sqrt(gx * gx + gy * gy + nz * nz)
nx_u8 = np.clip((-gx / norm * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
ny_u8 = np.clip((gy / norm * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
nz_u8 = np.clip((nz / norm * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
Image.fromarray(np.stack([nx_u8, ny_u8, nz_u8], axis=-1), mode="RGB").save(os.path.join(tex_dir, "lawn_turf_2k_nor_gl.jpg"), quality=94)

# Roughness map (blade tips slightly shinier 0.52, roots matte 0.88)
rough_u8 = np.clip(225.0 - ao_mask * 85.0 + macro_2 * 10.0, 125.0, 240.0).astype(np.uint8)
Image.fromarray(np.stack([rough_u8, rough_u8, rough_u8], axis=-1), mode="RGB").save(os.path.join(tex_dir, "lawn_turf_2k_rough.jpg"), quality=94)
print("Saved 2K lawn_turf_2k PBR textures")


# ---------------------------------------------------------------------------
# 2. Generate 1024x1024 3D Grass Blade Ribbon Atlas (lawn_blades_atlas_*)
# ---------------------------------------------------------------------------
AH, AW = 1024, 1024
# Render at 2048x2048 and downsample 2x for crisp anti-aliased blade edges
SH, SW = 2048, 2048
img_rgb = Image.new("RGB", (SW, SH), (52, 96, 32))
img_a = Image.new("L", (SW, SH), 0)
img_h = Image.new("L", (SW, SH), 0)
draw_rgb = ImageDraw.Draw(img_rgb)
draw_a = ImageDraw.Draw(img_a)
draw_h = ImageDraw.Draw(img_h)

rng_b = np.random.default_rng(777)
# Draw 85 dense, naturally arched grass blades rising from bottom (y=SH-1) to top (y=80..750)
for b_idx in range(85):
    x_base = rng_b.uniform(90.0, SW - 90.0)
    lean = rng_b.uniform(-240.0, 240.0)
    h_blade = rng_b.uniform(SH * 0.48, SH * 0.93)
    w_base = rng_b.uniform(22.0, 38.0)
    # Color variation per blade (fresh spring green to rich emerald)
    g_mid = rng_b.uniform(92.0, 138.0)
    r_mid = g_mid * rng_b.uniform(0.52, 0.68)
    b_mid = g_mid * rng_b.uniform(0.28, 0.40)

    n_seg = 18
    for s in range(n_seg):
        t0 = s / n_seg
        t1 = (s + 1) / n_seg
        y0 = SH - t0 * h_blade
        y1 = SH - t1 * h_blade
        # Parabolic arch
        x0 = x_base + lean * (t0 ** 1.7)
        x1 = x_base + lean * (t1 ** 1.7)
        w0 = w_base * (1.0 - 0.88 * (t0 ** 1.25))
        w1 = w_base * (1.0 - 0.88 * (t1 ** 1.25))
        # Dark AO at base (t=0), bright warm green at tip (t=1)
        shade = 0.42 + 0.78 * (t0 ** 0.75)
        rc = int(np.clip(r_mid * shade + 18.0 * (t0 ** 2), 20, 230))
        gc = int(np.clip(g_mid * shade + 14.0 * (t0 ** 2), 35, 245))
        bc = int(np.clip(b_mid * shade, 15, 180))
        poly = [(x0 - w0, y0), (x0 + w0, y0), (x1 + w1, y1), (x1 - w1, y1)]
        draw_rgb.polygon(poly, fill=(rc, gc, bc))
        draw_a.polygon(poly, fill=255)
        # Center ridge highlight for normal map
        h_val = int(np.clip(110 + 135 * math.sin(t0 * math.pi), 0, 255))
        draw_h.polygon(poly, fill=h_val)
        poly_in = [(x0 - w0 * 0.4, y0), (x0 + w0 * 0.4, y0), (x1 + w1 * 0.4, y1), (x1 - w1 * 0.4, y1)]
        draw_rgb.polygon(poly_in, fill=(min(255, int(rc * 1.12)), min(255, int(gc * 1.12)), min(255, int(bc * 1.10))))
        draw_h.polygon(poly_in, fill=min(255, h_val + 40))

img_rgb_1k = img_rgb.resize((AW, AH), Image.Resampling.LANCZOS)
img_a_1k = img_a.resize((AW, AH), Image.Resampling.LANCZOS)
img_h_1k = img_h.resize((AW, AH), Image.Resampling.LANCZOS)

a_arr = np.array(img_a_1k, dtype=np.uint8)
h_arr = np.array(img_h_1k, dtype=np.float32) / 255.0
gx_b = (np.roll(h_arr, -1, axis=1) - np.roll(h_arr, 1, axis=1)) * 2.5
gy_b = (np.roll(h_arr, -1, axis=0) - np.roll(h_arr, 1, axis=0)) * 2.5
nz_b = np.ones_like(h_arr)
nrm_b = np.sqrt(gx_b * gx_b + gy_b * gy_b + nz_b * nz_b)
nx_b = np.clip((-gx_b / nrm_b * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
ny_b = np.clip((gy_b / nrm_b * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
nz_bu8 = np.clip((nz_b / nrm_b * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)

img_rgb_1k.save(os.path.join(tex_dir, "lawn_blades_atlas_diff.jpg"), quality=95)
Image.fromarray(np.stack([a_arr, a_arr, a_arr], axis=-1), mode="RGB").save(os.path.join(tex_dir, "lawn_blades_atlas_alpha.jpg"), quality=95)
Image.fromarray(np.stack([nx_b, ny_b, nz_bu8], axis=-1), mode="RGB").save(os.path.join(tex_dir, "lawn_blades_atlas_nor_gl.jpg"), quality=95)
print("Saved 1K lawn_blades_atlas textures, alpha mean=", round(a_arr.mean(), 1))


# ---------------------------------------------------------------------------
# 3. Recolor Poly Haven grass_medium_01_diff_1k.jpg from dry yellow-brown to fresh lawn green
# ---------------------------------------------------------------------------
gm_in = os.path.join(fol_dir, "grass_medium_01_diff_1k.jpg")
gm_alpha = os.path.join(tex_dir, "grass_medium_01_alpha_1k.jpg")
if os.path.exists(gm_in) and os.path.exists(gm_alpha):
    im_gm = np.array(Image.open(gm_in).convert("RGB"), dtype=np.float32)
    a_gm = np.array(Image.open(gm_alpha).convert("L"), dtype=np.float32) / 255.0
    lum = 0.299 * im_gm[:, :, 0] + 0.587 * im_gm[:, :, 1] + 0.114 * im_gm[:, :, 2]
    # Map luminance to lush chlorophyll green
    new_gm = np.zeros_like(im_gm)
    new_gm[:, :, 0] = lum * 0.58 + 14.0
    new_gm[:, :, 1] = lum * 1.12 + 28.0
    new_gm[:, :, 2] = lum * 0.36 + 8.0
    fg = a_gm >= 0.35
    mean_col = new_gm[fg].mean(axis=0) if fg.any() else np.array([58.0, 108.0, 36.0])
    new_gm = new_gm * a_gm[:, :, None] + mean_col[None, None, :] * (1.0 - a_gm[:, :, None])
    Image.fromarray(np.clip(new_gm, 0, 255).astype(np.uint8), mode="RGB").save(os.path.join(tex_dir, "grass_medium_01_diff_1k.jpg"), quality=95)
    print("Recolored grass_medium_01_diff_1k.jpg to fresh green:", mean_col.round(1))

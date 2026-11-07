"""Apply custom UE5 PBR Materials (stucco, oak, anthracite roof, translucent glass) and capture two 1920x1080 exterior shots."""

from __future__ import annotations

import sys
import time
from pathlib import Path

UE_PYTHON_DIR = "C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"
if UE_PYTHON_DIR not in sys.path:
    sys.path.append(UE_PYTHON_DIR)

import remote_execution as re  # type: ignore


CAPTURE_SCRIPT = """
import unreal

editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
world = editor_sub.get_editor_world()

# 0. Force Epic Scalability (stable on D3D11 without TDR timeouts), Lumen GI + Reflections, TSR Anti-Aliasing, and SSAO in UE 5.8
for cvar, val in [
    ("r.DynamicGlobalIlluminationMethod", 1),
    ("r.ReflectionMethod", 1),
    ("r.Lumen.DiffuseIndirect.Allow", 1),
    ("r.Lumen.Reflections.Allow", 1),
    ("r.PostProcessAAQuality", 4),
    ("r.AntiAliasingMethod", 4),
    ("r.AmbientOcclusionLevels", 2),
    ("r.SSR.Quality", 3),
    ("r.ContactShadows", 1),
    ("r.ShadowQuality", 3),
    ("sg.AntiAliasingQuality", 3),
    ("sg.ShadowQuality", 3),
    ("sg.GlobalIlluminationQuality", 3),
    ("sg.ReflectionQuality", 3),
    ("sg.PostProcessQuality", 3),
    ("sg.TextureQuality", 3),
    ("sg.EffectsQuality", 3),
    ("sg.ShadingQuality", 3),
]:
    unreal.SystemLibrary.execute_console_command(world, f"{cvar} {val}")

# 1. Lower OpenWorld Landscape so sand dune peaks don't poke through the house walls
dir_light = None
sky_light = None
exp_fog = None

for a in actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if lbl == "Floor" or any(lbl.startswith(p) for p in ("PDF2BIM_PostProcess", "PDF2BIM_Hedge_", "PDF2BIM_Furn_", "PDF2BIM_Fab_", "PDF2BIM_Fol_", "PDF2BIM_Env_")):
        if lbl == "Floor":
            a.set_actor_hidden_in_game(True)
            a.set_is_temporarily_hidden_in_editor(True)
        else:
            actor_sub.destroy_actor(a)
    elif "Landscape" in cls or "HLOD" in cls:
        a.set_actor_hidden_in_game(True)
        a.set_is_temporarily_hidden_in_editor(True)
        loc = a.get_actor_location()
        a.set_actor_location(unreal.Vector(loc.x, loc.y, -2500.0), False, False)
    elif "DirectionalLight" in cls or "DirectionalLight" in lbl:
        dir_light = a
    elif "SkyLight" in cls or "SkyLight" in lbl:
        sky_light = a
    elif "ExponentialHeightFog" in cls or "ExponentialHeightFog" in lbl:
        exp_fog = a
    elif lbl == "PDF2BIM_Dom1_SM_Garden_Lawn":
        a.set_actor_hidden_in_game(True)
        a.set_is_temporarily_hidden_in_editor(True)

# 2. Import any missing 2K Normal/Roughness textures and build UE5 Master Materials
import os
mat_pkg = "/Game/PDF2BIM/Materials"
tex_pkg = "/Game/PDF2BIM/Textures"
tex_disk_dir = "C:/Users/filip/pdf2bim_remote/textures"

import_tasks = []
if os.path.isdir(tex_disk_dir):
    for fn in os.listdir(tex_disk_dir):
        if not fn.lower().endswith(".jpg"):
            continue
        stem = os.path.splitext(fn)[0]
        if any(k in stem for k in ("facade_timber_cladding", "facade_stucco_plaster", "roof_tiles_anthracite", "roof_tiles_red", "lawn_turf_2k", "lawn_blades_atlas", "grass_medium_01_diff")) or not unreal.EditorAssetLibrary.does_asset_exist(f"{tex_pkg}/{stem}"):
            t = unreal.AssetImportTask()
            t.set_editor_property("filename", f"{tex_disk_dir}/{fn}")
            t.set_editor_property("destination_path", tex_pkg)
            t.set_editor_property("automated", True)
            t.set_editor_property("replace_existing", True)
            t.set_editor_property("save", False)
            import_tasks.append(t)
if import_tasks:
    asset_tools.import_asset_tasks(import_tasks)

def load_tex(stem, is_normal=False, is_linear=False):
    if not stem:
        return None
    p = f"{tex_pkg}/{stem}"
    if unreal.EditorAssetLibrary.does_asset_exist(p):
        t = unreal.EditorAssetLibrary.load_asset(p)
        if t and any(k in stem for k in ("facade_timber_cladding", "facade_stucco_plaster", "roof_tiles_anthracite", "roof_tiles_red")):
            try:
                t.set_editor_property("never_stream", True)
            except Exception:
                pass
        if t and is_normal:
            t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            t.set_editor_property("srgb", False)
        elif t and is_linear:
            t.set_editor_property("srgb", False)
        return t
    return None

def make_mat(name):
    p = f"{mat_pkg}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(p):
        m = unreal.EditorAssetLibrary.load_asset(p)
        mel.delete_all_material_expressions(m)
        return m
    return asset_tools.create_asset(name, mat_pkg, unreal.Material, unreal.MaterialFactoryNew())

# Glass (Physically-based Fresnel architectural Low-E double-glazing with per-pixel lighting & sky/horizon reflections)
m_glass = make_mat("M_Glass_Clear")
m_glass.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
for tlm_name in ("TLM_SURFACE_PER_PIXEL_LIGHTING", "TLM_SURFACE_PERPIXEL_LIGHTING", "TLM_SURFACE"):
    if hasattr(unreal.TranslucencyLightingMode, tlm_name):
        m_glass.set_editor_property("translucency_lighting_mode", getattr(unreal.TranslucencyLightingMode, tlm_name))
        break
try:
    m_glass.set_editor_property("screen_space_reflections", True)
except Exception:
    pass
m_glass.set_editor_property("two_sided", True)

fres = mel.create_material_expression(m_glass, unreal.MaterialExpressionFresnel, -750, 0)
f_exp = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -950, -40)
f_exp.set_editor_property("r", 3.0)
f_base = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -950, 40)
f_base.set_editor_property("r", 0.08)
mel.connect_material_expressions(f_exp, "", fres, "ExponentIn")
mel.connect_material_expressions(f_base, "", fres, "BaseReflectFractionIn")

# Reflection vector sky/horizon/ground environment gradient for natural outdoor sky & cloud reflections on panes
refl_vec = mel.create_material_expression(m_glass, unreal.MaterialExpressionReflectionVectorWS, -950, -280)
up_vec = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant3Vector, -950, -180)
up_vec.set_editor_property("constant", unreal.LinearColor(0.0, 0.0, 1.0, 1.0))
dot_sky = mel.create_material_expression(m_glass, unreal.MaterialExpressionDotProduct, -750, -240)
mel.connect_material_expressions(refl_vec, "", dot_sky, "A")
mel.connect_material_expressions(up_vec, "", dot_sky, "B")
# Remap Z in [-1..1] -> [0..1]
add_bias = mel.create_material_expression(m_glass, unreal.MaterialExpressionAdd, -580, -240)
add_bias.set_editor_property("const_b", 0.35)
mel.connect_material_expressions(dot_sky, "", add_bias, "A")
clamp_sky = mel.create_material_expression(m_glass, unreal.MaterialExpressionClamp, -440, -240)
mel.connect_material_expressions(add_bias, "", clamp_sky, "")

c_ground = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant3Vector, -650, -420)
c_ground.set_editor_property("constant", unreal.LinearColor(0.14, 0.22, 0.16, 1.0))
c_sky = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant3Vector, -650, -330)
c_sky.set_editor_property("constant", unreal.LinearColor(0.46, 0.68, 0.92, 1.0))
env_lerp = mel.create_material_expression(m_glass, unreal.MaterialExpressionLinearInterpolate, -280, -320)
mel.connect_material_expressions(c_ground, "", env_lerp, "A")
mel.connect_material_expressions(c_sky, "", env_lerp, "B")
mel.connect_material_expressions(clamp_sky, "", env_lerp, "Alpha")

c_gl_transmission = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant3Vector, -550, -120)
c_gl_transmission.set_editor_property("constant", unreal.LinearColor(0.04, 0.09, 0.12, 1.0))
c_gl_lerp = mel.create_material_expression(m_glass, unreal.MaterialExpressionLinearInterpolate, -120, -180)
mel.connect_material_expressions(c_gl_transmission, "", c_gl_lerp, "A")
mel.connect_material_expressions(env_lerp, "", c_gl_lerp, "B")
mel.connect_material_expressions(fres, "", c_gl_lerp, "Alpha")
mel.connect_material_property(c_gl_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)

# Subtle sky reflection boost on Emissive controlled by Fresnel so panes reflect the sky vault crisply
em_mul = mel.create_material_expression(m_glass, unreal.MaterialExpressionMultiply, -120, -60)
em_scale = mel.create_material_expression(m_glass, unreal.MaterialExpressionMultiply, -280, -40)
em_const = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -450, -20)
em_const.set_editor_property("r", 0.55)
mel.connect_material_expressions(fres, "", em_scale, "A")
mel.connect_material_expressions(em_const, "", em_scale, "B")
mel.connect_material_expressions(env_lerp, "", em_mul, "A")
mel.connect_material_expressions(em_scale, "", em_mul, "B")
mel.connect_material_property(em_mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

m_gl_lo = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -650, 120)
m_gl_lo.set_editor_property("r", 0.25)
m_gl_hi = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -650, 180)
m_gl_hi.set_editor_property("r", 0.96)
m_gl_lerp = mel.create_material_expression(m_glass, unreal.MaterialExpressionLinearInterpolate, -320, 140)
mel.connect_material_expressions(m_gl_lo, "", m_gl_lerp, "A")
mel.connect_material_expressions(m_gl_hi, "", m_gl_lerp, "B")
mel.connect_material_expressions(fres, "", m_gl_lerp, "Alpha")
mel.connect_material_property(m_gl_lerp, "", unreal.MaterialProperty.MP_METALLIC)

s_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -320, 220)
s_gl.set_editor_property("r", 0.98)
mel.connect_material_property(s_gl, "", unreal.MaterialProperty.MP_SPECULAR)

o_gl_lo = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -650, 260)
o_gl_lo.set_editor_property("r", 0.16)
o_gl_hi = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -650, 320)
o_gl_hi.set_editor_property("r", 0.72)
o_gl_lerp = mel.create_material_expression(m_glass, unreal.MaterialExpressionLinearInterpolate, -320, 290)
mel.connect_material_expressions(o_gl_lo, "", o_gl_lerp, "A")
mel.connect_material_expressions(o_gl_hi, "", o_gl_lerp, "B")
mel.connect_material_expressions(fres, "", o_gl_lerp, "Alpha")
mel.connect_material_property(o_gl_lerp, "", unreal.MaterialProperty.MP_OPACITY)

r_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -320, 370)
r_gl.set_editor_property("r", 0.02)
mel.connect_material_property(r_gl, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(m_glass)

# (diff_stem, norm_stem, rough_stem, tint, is_plaster, rough_mult, metal_v, spec_v, uv_t)
pbr_defs = {
    "M_Wall_Plaster_White": ("facade_stucco_plaster_diffuse", "facade_stucco_plaster_nor_gl", "facade_stucco_plaster_rough", (1.07, 1.07, 1.06), True, 0.98, 0.0, 0.24, 3.2),
    "M_Roof_Tile_Anthracite": ("roof_tiles_red_diffuse", "roof_tiles_anthracite_nor_gl", "roof_tiles_anthracite_rough", (1.02, 0.96, 0.94), False, 1.0, 0.0, 0.28, 0.42),
    "M_Facade_Cladding_Oak": ("facade_timber_cladding_diffuse", "facade_timber_cladding_nor_gl", "facade_timber_cladding_rough", (0.98, 0.98, 0.98), False, 1.0, 0.0, 0.22, 1.0),
    "M_Door_Veneer_Oak": ("oak_countertop_diffuse", "oak_veneer_nor_gl", "oak_veneer_rough", (0.76, 0.56, 0.38), False, 0.38, 0.0, 0.62, 0.65),
    "M_Floor_Parquet_Oak": ("laminate_floor_02_diffuse", "laminate_floor_02_nor_gl", "laminate_floor_02_rough", (0.86, 0.76, 0.65), False, 0.48, 0.0, 0.42, 1.6),
    "M_Floor_Tile_Gres": ("concrete_tiles_diffuse", "concrete_tiles_nor_gl", "concrete_tiles_rough", (0.91, 0.90, 0.88), False, 0.28, 0.0, 0.72, 1.5),
    "M_Structure_Concrete": ("facade_stucco_plaster_diffuse", "facade_stucco_plaster_nor_gl", "facade_stucco_plaster_rough", (1.02, 1.03, 1.03), True, 0.98, 0.0, 0.24, 2.4),
    "M_Terrace_Paver_Grey": ("concrete_pavers_02_diffuse", "concrete_pavers_02_nor_gl", "concrete_pavers_02_rough", (0.76, 0.77, 0.79), False, 0.72, 0.0, 0.48, 2.5),
    "M_WalkwayPavers": ("concrete_pavers_02_diffuse", "concrete_pavers_02_nor_gl", "concrete_pavers_02_rough", (0.72, 0.73, 0.75), False, 0.75, 0.0, 0.45, 2.5),
    "M_ParcelGrass": ("lawn_turf_2k_diffuse", "lawn_turf_2k_nor_gl", "lawn_turf_2k_rough", (0.84, 0.96, 0.76), False, 0.86, 0.0, 0.24, 3.4),
    "M_Hedge_Boxwood": ("hedge_boxwood_diffuse", "hedge_boxwood_nor_gl", "hedge_boxwood_rough", (0.62, 0.78, 0.55), False, 0.85, 0.0, 0.30, 3.2),
    "M_Window_Frame_Anthracite": (None, None, None, (0.045, 0.050, 0.058), False, 0.28, 0.45, 0.70, 1.0),
    "M_Gravel_Pebbles": ("gravel_pebbles_diffuse", "gravel_pebbles_nor_gl", "gravel_pebbles_rough", (0.86, 0.85, 0.83), False, 0.86, 0.0, 0.32, 1.8),
    "M_Foliage_Boulder": ("boulder_01_diff_1k", "boulder_01_nor_gl_1k", "boulder_01_arm_1k", (0.90, 0.89, 0.87), False, 0.85, 0.0, 0.30, 1.0),
    "M_Foliage_Pot": ("potted_plant_01_pot_diff_1k", "potted_plant_01_pot_nor_gl_1k", "potted_plant_01_pot_rough_1k", (0.92, 0.90, 0.88), False, 0.65, 0.0, 0.40, 1.0),
    "M_Foliage_Tree_Trunk": ("tree_small_02_diff_1k", "tree_small_02_nor_gl_1k", "tree_small_02_arm_1k", (0.88, 0.85, 0.82), False, 0.88, 0.0, 0.25, 1.0),
    "M_Foliage_Tree_Branch": ("tree_small_02_branch_diff_1k", "tree_small_02_branch_nor_gl_1k", "tree_small_02_branch_arm_1k", (0.88, 0.85, 0.82), False, 0.88, 0.0, 0.25, 1.0),
}

built_mats = {"M_Glass_Clear": m_glass}
for mname, (diff_s, norm_s, rough_s, tint, is_plaster, rough_v, metal_v, spec_v, uv_t) in pbr_defs.items():
    mat = make_mat(mname)
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, 0)
    uv.set_editor_property("u_tiling", uv_t)
    uv.set_editor_property("v_tiling", uv_t)

    dtex = load_tex(diff_s)
    if dtex and not is_plaster:
        ts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -450, -220)
        ts.set_editor_property("texture", dtex)
        mel.connect_material_expressions(uv, "", ts, "UVs")
        mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -180, -220)
        ct = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -450, -360)
        ct.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        mel.connect_material_expressions(ts, "RGB", mul, "A")
        mel.connect_material_expressions(ct, "", mul, "B")
        mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    elif dtex and is_plaster:
        uv_micro = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, -180)
        uv_micro.set_editor_property("u_tiling", uv_t * 3.7)
        uv_micro.set_editor_property("v_tiling", uv_t * 3.7)
        ts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -480, -260)
        ts.set_editor_property("texture", dtex)
        mel.connect_material_expressions(uv, "", ts, "UVs")
        ts_m = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -480, -120)
        ts_m.set_editor_property("texture", dtex)
        mel.connect_material_expressions(uv_micro, "", ts_m, "UVs")
        lerp_d = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -300, -200)
        a_d = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -480, -20)
        a_d.set_editor_property("r", 0.45)
        mel.connect_material_expressions(ts, "RGB", lerp_d, "A")
        mel.connect_material_expressions(ts_m, "RGB", lerp_d, "B")
        mel.connect_material_expressions(a_d, "", lerp_d, "Alpha")
        mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -140, -200)
        c_white = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, -340)
        c_white.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        mel.connect_material_expressions(lerp_d, "", mul, "A")
        mel.connect_material_expressions(c_white, "", mul, "B")
        mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        c = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, -180)
        c.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rtex = load_tex(rough_s, is_linear=True)
    r_const = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, 120)
    r_const.set_editor_property("r", rough_v)
    if rtex:
        rts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -450, 20)
        rts.set_editor_property("texture", rtex)
        rts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        mel.connect_material_expressions(uv, "", rts, "UVs")
        rmul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -180, 60)
        mel.connect_material_expressions(rts, "R", rmul, "A")
        mel.connect_material_expressions(r_const, "", rmul, "B")
        mel.connect_material_property(rmul, "", unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        mel.connect_material_property(r_const, "", unreal.MaterialProperty.MP_ROUGHNESS)

    ntex = load_tex(norm_s, is_normal=True)
    if ntex and is_plaster:
        uv_nm = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, 360)
        uv_nm.set_editor_property("u_tiling", uv_t * 3.7)
        uv_nm.set_editor_property("v_tiling", uv_t * 3.7)
        nts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -480, 260)
        nts.set_editor_property("texture", ntex)
        nts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_expressions(uv, "", nts, "UVs")
        nts_m = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -480, 400)
        nts_m.set_editor_property("texture", ntex)
        nts_m.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_expressions(uv_nm, "", nts_m, "UVs")
        n_add = mel.create_material_expression(mat, unreal.MaterialExpressionAdd, -280, 320)
        mel.connect_material_expressions(nts, "RGB", n_add, "A")
        mel.connect_material_expressions(nts_m, "RGB", n_add, "B")
        n_scale = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -280, 440)
        n_scale.set_editor_property("constant", unreal.LinearColor(1.05, 1.05, 0.70, 1.0))
        n_mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -120, 340)
        mel.connect_material_expressions(n_add, "", n_mul, "A")
        mel.connect_material_expressions(n_scale, "", n_mul, "B")
        mel.connect_material_property(n_mul, "", unreal.MaterialProperty.MP_NORMAL)
    elif ntex:
        nts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -450, 280)
        nts.set_editor_property("texture", ntex)
        nts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_expressions(uv, "", nts, "UVs")
        mel.connect_material_property(nts, "RGB", unreal.MaterialProperty.MP_NORMAL)

    m_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 180)
    m_node.set_editor_property("r", metal_v)
    mel.connect_material_property(m_node, "", unreal.MaterialProperty.MP_METALLIC)

    s_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 230)
    s_node.set_editor_property("r", spec_v)
    mel.connect_material_property(s_node, "", unreal.MaterialProperty.MP_SPECULAR)

    mel.recompile_material(mat)
    built_mats[mname] = mat

# Build realistic smooth interior gypsum skim-coat ("Gładź gipsowa malowana farbą lateksową matową")
m_gladz = make_mat("M_Wall_Interior_Gladz")
uv_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionTextureCoordinate, -700, 0)
uv_g.set_editor_property("u_tiling", 4.5)
uv_g.set_editor_property("v_tiling", 4.5)
uv_g_micro = mel.create_material_expression(m_gladz, unreal.MaterialExpressionTextureCoordinate, -700, 160)
uv_g_micro.set_editor_property("u_tiling", 14.0)
uv_g_micro.set_editor_property("v_tiling", 14.0)

d_gladz = load_tex("painted_plaster_wall_diffuse")
c_gladz = mel.create_material_expression(m_gladz, unreal.MaterialExpressionConstant3Vector, -480, -340)
c_gladz.set_editor_property("constant", unreal.LinearColor(0.955, 0.948, 0.935, 1.0))
if d_gladz:
    ts_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionTextureSample, -480, -200)
    ts_g.set_editor_property("texture", d_gladz)
    mel.connect_material_expressions(uv_g, "", ts_g, "UVs")
    lerp_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionLinearInterpolate, -200, -240)
    a_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionConstant, -480, -80)
    a_g.set_editor_property("r", 0.24)
    mel.connect_material_expressions(c_gladz, "", lerp_g, "A")
    mel.connect_material_expressions(ts_g, "RGB", lerp_g, "B")
    mel.connect_material_expressions(a_g, "", lerp_g, "Alpha")
    mel.connect_material_property(lerp_g, "", unreal.MaterialProperty.MP_BASE_COLOR)
else:
    mel.connect_material_property(c_gladz, "", unreal.MaterialProperty.MP_BASE_COLOR)

r_gladz = load_tex("painted_plaster_wall_rough", is_linear=True)
rc_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionConstant, -480, 120)
rc_g.set_editor_property("r", 0.86)
if r_gladz:
    rts_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionTextureSample, -480, 20)
    rts_g.set_editor_property("texture", r_gladz)
    rts_g.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_g, "", rts_g, "UVs")
    rmul_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionMultiply, -200, 60)
    mel.connect_material_expressions(rts_g, "R", rmul_g, "A")
    mel.connect_material_expressions(rc_g, "", rmul_g, "B")
    mel.connect_material_property(rmul_g, "", unreal.MaterialProperty.MP_ROUGHNESS)
else:
    mel.connect_material_property(rc_g, "", unreal.MaterialProperty.MP_ROUGHNESS)

n_gladz = load_tex("painted_plaster_wall_nor_gl", is_normal=True)
n_stucco = load_tex("facade_stucco_plaster_nor_gl", is_normal=True)
if n_gladz:
    nts_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionTextureSample, -480, 260)
    nts_g.set_editor_property("texture", n_gladz)
    nts_g.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uv_g, "", nts_g, "UVs")
    if n_stucco:
        nts_gm = mel.create_material_expression(m_gladz, unreal.MaterialExpressionTextureSample, -480, 400)
        nts_gm.set_editor_property("texture", n_stucco)
        nts_gm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_expressions(uv_g_micro, "", nts_gm, "UVs")
        ns_gm = mel.create_material_expression(m_gladz, unreal.MaterialExpressionConstant3Vector, -480, 520)
        ns_gm.set_editor_property("constant", unreal.LinearColor(0.28, 0.28, 0.5, 1.0))
        nmul_gm = mel.create_material_expression(m_gladz, unreal.MaterialExpressionMultiply, -320, 420)
        mel.connect_material_expressions(nts_gm, "RGB", nmul_gm, "A")
        mel.connect_material_expressions(ns_gm, "", nmul_gm, "B")
        nadd_g = mel.create_material_expression(m_gladz, unreal.MaterialExpressionAdd, -160, 320)
        mel.connect_material_expressions(nts_g, "RGB", nadd_g, "A")
        mel.connect_material_expressions(nmul_gm, "", nadd_g, "B")
        mel.connect_material_property(nadd_g, "", unreal.MaterialProperty.MP_NORMAL)
    else:
        mel.connect_material_property(nts_g, "RGB", unreal.MaterialProperty.MP_NORMAL)

sg_node = mel.create_material_expression(m_gladz, unreal.MaterialExpressionConstant, -300, 200)
sg_node.set_editor_property("r", 0.26)
mel.connect_material_property(sg_node, "", unreal.MaterialProperty.MP_SPECULAR)
mel.recompile_material(m_gladz)
built_mats["M_Wall_Interior_Gladz"] = m_gladz

# Map Ceramic_Block (inner core of exterior walls) to Interior Gladz, and Insulation_EPS (window reveals) to Exterior Stucco
built_mats["M_Wall_Ceramic_Block"] = m_gladz
built_mats["M_Wall_Insulation_EPS"] = built_mats["M_Wall_Plaster_White"]

ext_facade_tokens = (
    "_exterior_mat_wall_plaster",
    "_exterior_mat_insulation",
    "_knee_wall_mat_wall_plaster",
    "_knee_wall_mat_insulation",
    "_gable_wall_mat_wall_plaster",
    "_gable_wall_mat_insulation",
    "porch_col",
    "komin_dach",
)

# 3. Assign built_mats to all spawned Dom 1 StaticMeshActors (exterior stucco on facade vs smooth gladz inside)
assigned = 0
for a in actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    if not lbl.startswith("PDF2BIM_Dom1_"):
        continue
    lbl_low = lbl.lower()
    is_ext_facade = any(tok in lbl_low for tok in ext_facade_tokens)
    smc = a.static_mesh_component
    sm = smc.static_mesh
    if not sm:
        continue
    num_mats = smc.get_num_materials()
    for idx in range(num_mats):
        cur_m = smc.get_material(idx)
        if not cur_m:
            continue
        cname = cur_m.get_name()
        target_m = None
        for k, cand_m in built_mats.items():
            if cname.startswith(k):
                target_m = cand_m
                break
        if target_m is None and cname.startswith("M_Wall_Interior_Gladz"):
            target_m = m_gladz
        # Route interior walls, inner layer L2 of exterior walls, and interior slabs/ceilings to M_Wall_Interior_Gladz
        if target_m in (built_mats["M_Wall_Plaster_White"], built_mats["M_Structure_Concrete"], m_gladz):
            if is_ext_facade:
                target_m = built_mats["M_Wall_Plaster_White"]
            else:
                target_m = m_gladz
        if target_m:
            smc.set_material(idx, target_m)
            sm.set_material(idx, target_m)
            assigned += 1

print("ASSIGNED_MATERIAL_SLOTS", assigned)

# 4. Build 360 SkyDome & Alpha-Masked Foliage Materials + Import/Spawn 3D Vegetation & Landscaping
m_sky = make_mat("M_Env_Panorama_Sky")
m_sky.set_editor_property("two_sided", True)
try:
    m_sky.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
except Exception:
    pass
sky_tex = load_tex("meadow_2_env_4k")
if sky_tex:
    try:
        sky_tex.set_editor_property("never_stream", True)
    except Exception:
        pass
    ts_sky = mel.create_material_expression(m_sky, unreal.MaterialExpressionTextureSample, -450, -100)
    ts_sky.set_editor_property("texture", sky_tex)
    c_sky_mul = mel.create_material_expression(m_sky, unreal.MaterialExpressionConstant3Vector, -450, 80)
    c_sky_mul.set_editor_property("constant", unreal.LinearColor(1.08, 1.08, 1.08, 1.0))
    mul_sky = mel.create_material_expression(m_sky, unreal.MaterialExpressionMultiply, -180, -40)
    mel.connect_material_expressions(ts_sky, "RGB", mul_sky, "A")
    mel.connect_material_expressions(c_sky_mul, "", mul_sky, "B")
    mel.connect_material_property(mul_sky, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(mul_sky, "", unreal.MaterialProperty.MP_BASE_COLOR)
mel.recompile_material(m_sky)
built_mats["M_Env_Panorama_Sky"] = m_sky

# (diff_stem, norm_stem, alpha_stem, tint_rgb, rough_val, clip_val)
masked_foliage_defs = {
    "M_Foliage_Tree_Leaves": ("tree_small_02_leaves_diff_1k", "tree_small_02_leaves_nor_gl_1k", "tree_small_02_leaves_alpha_1k", (0.86, 1.08, 0.74), 0.46, 0.24),
    "M_Foliage_Shrub_02": ("shrub_02_diff_1k", "shrub_02_nor_gl_1k", "shrub_02_alpha_1k", (0.76, 1.18, 0.68), 0.50, 0.12),
    "M_Foliage_Shrub_01": ("shrub_01_diff_1k", "shrub_01_nor_gl_1k", "shrub_01_alpha_1k", (0.82, 1.08, 0.72), 0.48, 0.22),
    "M_Foliage_Grass_01": ("grass_medium_01_diff_1k", "grass_medium_01_nor_gl_1k", "grass_medium_01_alpha_1k", (0.88, 1.04, 0.80), 0.52, 0.20),
    "M_Foliage_Lawn_Blades": ("lawn_blades_atlas_diff", "lawn_blades_atlas_nor_gl", "lawn_blades_atlas_alpha", (0.88, 1.04, 0.80), 0.48, 0.22),
    "M_Foliage_Plant_Leaves": ("potted_plant_01_leaves_diff_1k", "potted_plant_01_leaves_nor_gl_1k", "potted_plant_01_leaves_alpha_1k", (0.88, 1.06, 0.80), 0.40, 0.28),
}

for mf_name, (d_s, n_s, a_s, f_tint, f_rough, f_clip) in masked_foliage_defs.items():
    mf = make_mat(mf_name)
    mf.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mf.set_editor_property("two_sided", True)
    try:
        mf.set_editor_property("opacity_mask_clip_value", f_clip)
    except Exception:
        pass
    d_t = load_tex(d_s)
    if d_t:
        try:
            d_t.set_editor_property("never_stream", True)
        except Exception:
            pass
        ts_d = mel.create_material_expression(mf, unreal.MaterialExpressionTextureSample, -480, -220)
        ts_d.set_editor_property("texture", d_t)
        ct_f = mel.create_material_expression(mf, unreal.MaterialExpressionConstant3Vector, -480, -340)
        ct_f.set_editor_property("constant", unreal.LinearColor(f_tint[0], f_tint[1], f_tint[2], 1.0))
        mul_f = mel.create_material_expression(mf, unreal.MaterialExpressionMultiply, -200, -220)
        mel.connect_material_expressions(ts_d, "RGB", mul_f, "A")
        mel.connect_material_expressions(ct_f, "", mul_f, "B")
        mel.connect_material_property(mul_f, "", unreal.MaterialProperty.MP_BASE_COLOR)
        # Subtle warm green canopy bounce so shaded inner leaves never turn black
        em_c = mel.create_material_expression(mf, unreal.MaterialExpressionConstant3Vector, -480, -80)
        em_c.set_editor_property("constant", unreal.LinearColor(0.035, 0.055, 0.020, 1.0))
        em_f = mel.create_material_expression(mf, unreal.MaterialExpressionMultiply, -200, -80)
        mel.connect_material_expressions(mul_f, "", em_f, "A")
        mel.connect_material_expressions(em_c, "", em_f, "B")
        mel.connect_material_property(em_f, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    a_t = load_tex(a_s, is_linear=True)
    if a_t:
        try:
            a_t.set_editor_property("never_stream", True)
        except Exception:
            pass
        ts_a = mel.create_material_expression(mf, unreal.MaterialExpressionTextureSample, -480, 60)
        ts_a.set_editor_property("texture", a_t)
        ts_a.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        mel.connect_material_property(ts_a, "R", unreal.MaterialProperty.MP_OPACITY_MASK)
    n_t = load_tex(n_s, is_normal=True)
    if n_t:
        ts_n = mel.create_material_expression(mf, unreal.MaterialExpressionTextureSample, -480, 220)
        ts_n.set_editor_property("texture", n_t)
        ts_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_property(ts_n, "RGB", unreal.MaterialProperty.MP_NORMAL)
    rf_n = mel.create_material_expression(mf, unreal.MaterialExpressionConstant, -220, 340)
    rf_n.set_editor_property("r", f_rough)
    mel.connect_material_property(rf_n, "", unreal.MaterialProperty.MP_ROUGHNESS)
    sf_n = mel.create_material_expression(mf, unreal.MaterialExpressionConstant, -220, 410)
    sf_n.set_editor_property("r", 0.28)
    mel.connect_material_property(sf_n, "", unreal.MaterialProperty.MP_SPECULAR)
    mel.recompile_material(mf)
    built_mats[mf_name] = mf

fol_pkg = "/Game/PDF2BIM/Foliage"
fol_fbx = "C:/Users/filip/pdf2bim_remote/foliage/foliage_and_env.fbx"
if os.path.exists(fol_fbx) and (os.environ.get("PDF2BIM_REIMPORT_FOLIAGE", "1") == "1" or not unreal.EditorAssetLibrary.does_asset_exist(f"{fol_pkg}/SM_Lawn_Turf_Carpet_3D")):
    if unreal.EditorAssetLibrary.does_directory_exist(fol_pkg):
        unreal.EditorAssetLibrary.delete_directory(fol_pkg)
    fbx_ui_f = unreal.FbxImportUI()
    fbx_ui_f.import_mesh = True
    fbx_ui_f.import_as_skeletal = False
    fbx_ui_f.import_materials = False
    fbx_ui_f.import_textures = False
    fbx_ui_f.static_mesh_import_data.combine_meshes = False
    fbx_ui_f.static_mesh_import_data.remove_degenerates = False
    tf_task = unreal.AssetImportTask()
    tf_task.set_editor_property("filename", fol_fbx)
    tf_task.set_editor_property("destination_path", fol_pkg)
    tf_task.set_editor_property("automated", True)
    tf_task.set_editor_property("replace_existing", True)
    tf_task.set_editor_property("replace_existing_settings", True)
    tf_task.set_editor_property("save", False)
    tf_task.set_editor_property("options", fbx_ui_f)
    asset_tools.import_asset_tasks([tf_task])

fol_meshes = {}
fol_mat_slots = {
    "SM_Env_SkyDome": ["M_Env_Panorama_Sky"],
    "SM_Terrain_Undulating_Lawn": ["M_ParcelGrass"],
    "SM_Lawn_Turf_Carpet_3D": ["M_ParcelGrass"],
    "SM_Garden_Terrace": ["M_Terrace_Paver_Grey"],
    "SM_Gravel_Drainage_Strip": ["M_Gravel_Pebbles"],
    "SM_Gravel_Curb": ["M_Window_Frame_Anthracite"],
    "SM_Boulder_01": ["M_Foliage_Boulder"],
    "SM_Grass_Patch_3D": ["M_Foliage_Grass_01"],
    "SM_Hedge_Row_4m": ["M_Foliage_Shrub_02"],
    "SM_Shrub_02_A": ["M_Foliage_Shrub_02"],
    "SM_Shrub_02_B": ["M_Foliage_Shrub_02"],
    "SM_Shrub_01_Bush": ["M_Foliage_Shrub_01"],
    "SM_Potted_Plant_01": ["M_Foliage_Plant_Leaves", "M_Foliage_Pot"],
    "SM_Tree_Small_02": ["M_Foliage_Tree_Branch", "M_Foliage_Tree_Leaves", "M_Foliage_Tree_Trunk"],
}
for sm_name, slot_mats in fol_mat_slots.items():
    sm_path = f"{fol_pkg}/{sm_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(sm_path):
        sm_obj = unreal.EditorAssetLibrary.load_asset(sm_path)
        if sm_obj:
            resolved_slots = []
            try:
                st_mats = sm_obj.get_editor_property("static_materials")
                for s_idx, stm in enumerate(st_mats):
                    sname = str(stm.get_editor_property("material_slot_name"))
                    matched = next((k for k in built_mats if sname.startswith(k)), None)
                    if not matched and s_idx < len(slot_mats):
                        matched = slot_mats[s_idx]
                    resolved_slots.append(matched)
            except Exception:
                resolved_slots = list(slot_mats)
            fol_mat_slots[sm_name] = resolved_slots
            for s_idx, m_key in enumerate(resolved_slots):
                if m_key and m_key in built_mats:
                    sm_obj.set_material(s_idx, built_mats[m_key])
            fol_meshes[sm_name] = sm_obj

import math as _math
_hs_rects = [
    (-0.60, -0.60, 10.90, 9.00),
    (-0.05, -0.65, 2.52, 0.05),
    (0.40, -7.55, 2.30, 0.00),
    (2.06, 8.38, 11.68, 11.33),
    (10.28, 3.02, 11.68, 8.45),
]
def ue_terrain_z(x_ue, y_ue):
    x = x_ue / 100.0
    y = -y_ue / 100.0
    dmin = 999.0
    for (rx0, ry0, rx1, ry1) in _hs_rects:
        d = _math.hypot(max(rx0 - x, 0.0, x - rx1), max(ry0 - y, 0.0, y - ry1))
        if d < dmin:
            dmin = d
    z_base = -0.242
    if dmin <= 0.08:
        zb = z_base
    else:
        t = min(1.0, (dmin - 0.08) / 1.65)
        blend = t * t * (3.0 - 2.0 * t)
        w1 = 0.115 * _math.sin(0.55 * x + 0.42 * y + 0.4) * _math.cos(0.48 * y - 0.28 * x)
        w2 = 0.075 * _math.sin(1.18 * x - 0.88 * y + 1.2)
        w3 = 0.045 * _math.cos(1.90 * x + 1.70 * y - 0.7)
        m1 = 0.16 * _math.exp(-((x - 8.2) ** 2 + (y + 3.1) ** 2) / 9.0)
        m2 = 0.18 * _math.exp(-((x - 13.4) ** 2 + (y - 5.2) ** 2) / 10.0)
        m3 = 0.19 * _math.exp(-((x - 6.8) ** 2 + (y - 14.0) ** 2) / 11.5)
        m4 = 0.14 * _math.exp(-((x + 2.2) ** 2 + (y + 3.5) ** 2) / 8.0)
        zb = z_base + blend * (w1 + w2 + w3 + m1 + m2 + m3 + m4)
    return 92.0 + zb * 100.0 - 1.2

def spawn_fol(sm_name, label, loc_xyz, yaw_deg=0.0, scale_xyz=(1.0, 1.0, 1.0), cast_shadow=True):
    sm_obj = fol_meshes.get(sm_name)
    if not sm_obj:
        return None
    lx, ly, lz = loc_xyz
    if lz < 80.0 and (lx != 0.0 or ly != 0.0):
        lz = ue_terrain_z(lx, ly)
    act = actor_sub.spawn_actor_from_object(sm_obj, unreal.Vector(lx, ly, lz), unreal.Rotator(0.0, 0.0, yaw_deg))
    if act:
        act.set_actor_scale3d(unreal.Vector(*scale_xyz))
        act.set_actor_label(label)
        act.set_folder_path("PDF2BIM/Landscaping")
        smc = act.static_mesh_component
        slot_mats = fol_mat_slots.get(sm_name, [])
        for s_idx, m_key in enumerate(slot_mats):
            if m_key in built_mats:
                smc.set_material(s_idx, built_mats[m_key])
        if not cast_shadow:
            smc.set_editor_property("cast_shadow", False)
    return act

# A) Spawn 360 SkyDome, Undulating 3D Terrain, 3D Lawn Blade Carpet, Garden Terrace, Gravel Strip & Curb at base_loc (0, 0, 92)
spawn_fol("SM_Env_SkyDome", "PDF2BIM_Env_SkyDome_360", (0.0, 0.0, 92.0), 0.0, (1.0, 1.0, 1.0), cast_shadow=False)
spawn_fol("SM_Terrain_Undulating_Lawn", "PDF2BIM_Env_Terrain_Undulating_Lawn", (0.0, 0.0, 92.0))
spawn_fol("SM_Lawn_Turf_Carpet_3D", "PDF2BIM_Env_Lawn_Turf_Carpet_3D", (0.0, 0.0, 92.0), 0.0, (1.0, 1.0, 1.0), cast_shadow=False)
spawn_fol("SM_Garden_Terrace", "PDF2BIM_Env_Garden_Terrace", (0.0, 0.0, 92.0))
spawn_fol("SM_Gravel_Drainage_Strip", "PDF2BIM_Env_Gravel_Strip", (0.0, 0.0, 92.0))
spawn_fol("SM_Gravel_Curb", "PDF2BIM_Env_Gravel_Curb", (0.0, 0.0, 92.0))

# B) Spawn 3D Natural Shrub Perimeter Hedges (SM_Hedge_Row_4m) replacing flat Cube hedges
hedge_3d_placements = [
    ("North_1", (-420.0, -1850.0, 66.0), 0.0, (1.05, 1.15, 1.25)),
    ("North_2", (-60.0, -1850.0, 66.0), 180.0, (1.05, 1.15, 1.28)),
    ("North_3", (300.0, -1850.0, 66.0), 0.0, (1.05, 1.15, 1.22)),
    ("North_4", (660.0, -1850.0, 66.0), 180.0, (1.05, 1.15, 1.26)),
    ("North_5", (1020.0, -1850.0, 66.0), 0.0, (1.05, 1.15, 1.24)),
    ("North_6", (1380.0, -1850.0, 66.0), 180.0, (1.05, 1.15, 1.25)),
    ("West_1", (-580.0, -1550.0, 66.0), 90.0, (1.05, 1.15, 1.25)),
    ("West_2", (-580.0, -1190.0, 66.0), 270.0, (1.05, 1.15, 1.22)),
    ("West_3", (-580.0, -830.0, 66.0), 90.0, (1.05, 1.15, 1.26)),
    ("West_4", (-580.0, -470.0, 66.0), 270.0, (1.05, 1.15, 1.24)),
    ("West_5", (-580.0, -110.0, 66.0), 90.0, (1.05, 1.15, 1.22)),
    ("West_6", (-580.0, 250.0, 66.0), 270.0, (1.05, 1.15, 1.25)),
    ("West_7", (-580.0, 610.0, 66.0), 90.0, (1.05, 1.15, 1.20)),
    ("East_1", (1620.0, -1450.0, 66.0), 270.0, (1.05, 1.15, 1.22)),
    ("East_2", (1620.0, -1090.0, 66.0), 90.0, (1.05, 1.15, 1.25)),
    ("East_3", (1620.0, -730.0, 66.0), 270.0, (1.05, 1.15, 1.20)),
    ("East_4", (1620.0, -370.0, 66.0), 90.0, (1.05, 1.15, 1.18)),
    ("South_W1", (-360.0, 840.0, 66.0), 0.0, (1.00, 1.10, 1.12)),
    ("South_E1", (580.0, 840.0, 66.0), 0.0, (1.05, 1.10, 1.12)),
    ("South_E2", (950.0, 840.0, 66.0), 180.0, (1.05, 1.10, 1.14)),
    ("South_E3", (1310.0, 840.0, 66.0), 0.0, (1.00, 1.10, 1.10)),
]
for h_id, h_xyz, h_yaw, h_sc in hedge_3d_placements:
    spawn_fol("SM_Hedge_Row_4m", f"PDF2BIM_Fol_Hedge_{h_id}", h_xyz, h_yaw, h_sc)
    spawn_fol("SM_Shrub_01_Bush", f"PDF2BIM_Fol_HedgeBase_{h_id}", h_xyz, h_yaw + 35.0, (2.7, 2.7, 2.4))

# C) Spawn 12 Photoscanned 3D Deciduous Trees (SM_Tree_Small_02) around garden, background & yard
tree_placements = [
    ("Back_NW_1", (-360.0, -1460.0, 65.0), 25.0, (1.45, 1.45, 1.55)),
    ("Back_NW_2", (-780.0, -980.0, 65.0), 115.0, (1.75, 1.75, 1.85)),
    ("Back_Center", (180.0, -1680.0, 65.0), -42.0, (1.38, 1.38, 1.48)),
    ("Back_North_Far1", (-220.0, -2350.0, 65.0), 68.0, (1.85, 1.85, 1.95)),
    ("Back_North_Far2", (750.0, -2420.0, 65.0), 145.0, (1.78, 1.78, 1.88)),
    ("West_Side", (-440.0, -240.0, 65.0), 160.0, (1.32, 1.32, 1.40)),
    ("Front_SW", (-350.0, 540.0, 65.0), -82.0, (1.28, 1.28, 1.36)),
    ("Front_South_Far1", (420.0, 1420.0, 65.0), 18.0, (1.65, 1.65, 1.75)),
    ("Front_South_Far2", (-750.0, 1180.0, 65.0), 195.0, (1.80, 1.80, 1.90)),
    ("Front_Walkway_Left", (-80.0, 620.0, 65.0), -35.0, (1.18, 1.18, 1.25)),
    ("East_Garden", (1470.0, -860.0, 65.0), -125.0, (1.18, 1.18, 1.25)),
    ("East_Far_Refl", (2450.0, -380.0, 65.0), 48.0, (1.75, 1.75, 1.85)),
]
for t_id, t_xyz, t_yaw, t_sc in tree_placements:
    spawn_fol("SM_Tree_Small_02", f"PDF2BIM_Fol_Tree_{t_id}", t_xyz, t_yaw, t_sc)

# D) Spawn Garden Shrubs, Boulders, Potted Plants & 3D Meadow Grass Patches
shrub_placements = [
    ("SM_Shrub_02_A", "Shrub_Terrace_NE", (1230.0, -1080.0, 66.0), 35.0, (1.10, 1.10, 1.15)),
    ("SM_Shrub_02_B", "Shrub_Terrace_E", (1240.0, -420.0, 66.0), 125.0, (1.05, 1.05, 1.10)),
    ("SM_Shrub_02_A", "Shrub_Terrace_NW", (150.0, -1060.0, 66.0), -60.0, (1.15, 1.15, 1.20)),
    ("SM_Shrub_01_Bush", "Shrub_Front_Bed1", (440.0, 95.0, 66.0), 15.0, (1.15, 1.15, 1.15)),
    ("SM_Shrub_01_Bush", "Shrub_Front_Bed2", (760.0, 95.0, 66.0), 105.0, (1.20, 1.20, 1.20)),
    ("SM_Shrub_02_B", "Shrub_Walkway_R1", (285.0, 220.0, 66.0), 45.0, (0.85, 0.85, 0.88)),
    ("SM_Shrub_01_Bush", "Shrub_Walkway_R2", (285.0, 440.0, 66.0), 165.0, (1.10, 1.10, 1.10)),
    ("SM_Shrub_02_A", "Shrub_Walkway_L1", (-40.0, 280.0, 66.0), -45.0, (0.90, 0.90, 0.92)),
    ("SM_Shrub_01_Bush", "Shrub_East_Corner", (1160.0, 90.0, 66.0), 75.0, (1.25, 1.25, 1.25)),
]
for s_mesh, s_id, s_xyz, s_yaw, s_sc in shrub_placements:
    spawn_fol(s_mesh, f"PDF2BIM_Fol_{s_id}", s_xyz, s_yaw, s_sc)

boulder_placements = [
    ("Boulder_NE", (1290.0, -980.0, 65.0), 20.0, (0.48, 0.48, 0.42)),
    ("Boulder_Walkway", (310.0, 330.0, 65.0), 115.0, (0.38, 0.38, 0.34)),
    ("Boulder_NW", (60.0, -1120.0, 65.0), -55.0, (0.52, 0.52, 0.45)),
    ("Boulder_SE", (1230.0, 140.0, 65.0), 80.0, (0.42, 0.42, 0.36)),
]
for b_id, b_xyz, b_yaw, b_sc in boulder_placements:
    spawn_fol("SM_Boulder_01", f"PDF2BIM_Fol_{b_id}", b_xyz, b_yaw, b_sc)

pot_placements = [
    ("Pot_Terrace_Patio1", (335.0, -885.0, 90.0), 15.0, (0.85, 0.85, 0.85)),
    ("Pot_Terrace_Patio2", (1015.0, -885.0, 90.0), 105.0, (0.88, 0.88, 0.88)),
    ("Pot_Terrace_East", (1080.0, -460.0, 90.0), -45.0, (0.82, 0.82, 0.82)),
    ("Pot_Front_Porch", (32.0, -35.0, 90.0), 60.0, (0.80, 0.80, 0.80)),
]
for p_id, p_xyz, p_yaw, p_sc in pot_placements:
    spawn_fol("SM_Potted_Plant_01", f"PDF2BIM_Fol_{p_id}", p_xyz, p_yaw, p_sc)

grass_coords = [
    (420.0, 220.0, 15.0), (680.0, 230.0, 75.0), (940.0, 240.0, 135.0), (1200.0, 260.0, 210.0), (1440.0, 280.0, 35.0),
    (440.0, 440.0, 45.0), (710.0, 460.0, 165.0), (980.0, 450.0, 255.0), (1240.0, 470.0, 95.0), (1480.0, 490.0, 185.0),
    (460.0, 680.0, 115.0), (760.0, 700.0, 225.0), (1060.0, 690.0, 55.0), (1340.0, 710.0, 145.0), (1560.0, 730.0, 275.0),
    (-190.0, 420.0, 125.0), (-160.0, 680.0, 215.0), (1320.0, -40.0, 35.0), (1520.0, -80.0, 125.0),
    (1340.0, -340.0, 155.0), (1540.0, -420.0, 245.0), (1340.0, -720.0, 65.0), (1520.0, -980.0, 175.0),
    (1360.0, -1240.0, 85.0), (1100.0, -1260.0, 195.0), (840.0, -1280.0, 25.0), (580.0, -1270.0, 115.0),
    (310.0, -1280.0, 205.0), (40.0, -1260.0, 295.0), (-220.0, -1240.0, 45.0),
    (1320.0, -1540.0, 135.0), (1020.0, -1560.0, 65.0), (720.0, -1580.0, 175.0), (420.0, -1560.0, 285.0),
    (120.0, -1540.0, 145.0), (-180.0, -1520.0, 235.0),
]
for g_idx, (gx, gy, gyaw) in enumerate(grass_coords):
    spawn_fol("SM_Grass_Patch_3D", f"PDF2BIM_Fol_GrassPatch_{g_idx+1:02d}", (gx, gy, 66.5), gyaw, (1.15, 1.15, 1.15))

# E) Configure Collisions & PlayerStart so Play-In-Editor (PIE) starts cleanly above ground on the front walkway
no_col_prefixes = ("PDF2BIM_Env_SkyDome", "PDF2BIM_Env_Lawn_Turf_Carpet", "PDF2BIM_Fol_GrassPatch", "PDF2BIM_Dom1_Drzwi_")
player_start_actor = None
for a in actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if "PlayerStart" in cls or "PlayerStart" in lbl:
        player_start_actor = a
        a.set_actor_location(unreal.Vector(135.0, 560.0, 175.0), False, False)
        a.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=-75.0), False)
    elif "Landscape" in cls or "HLOD" in cls or lbl in ("Floor", "PDF2BIM_Dom1_SM_Garden_Lawn", "SM_SkySphere"):
        a.set_actor_enable_collision(False)
    elif any(lbl.startswith(p) for p in no_col_prefixes):
        a.set_actor_enable_collision(False)
        smc = getattr(a, "static_mesh_component", None)
        if smc:
            smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            smc.set_collision_profile_name("NoCollision")
    elif lbl.startswith("PDF2BIM_Dom1_") or lbl.startswith("PDF2BIM_Env_"):
        a.set_actor_enable_collision(True)
        smc = getattr(a, "static_mesh_component", None)
        if smc:
            smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            smc.set_collision_profile_name("BlockAll")
            sm = smc.static_mesh
            if sm:
                bs = sm.get_editor_property("body_setup")
                if bs:
                    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                smc.set_static_mesh(None)
                smc.set_static_mesh(sm)

if player_start_actor is None:
    player_start_actor = actor_sub.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(135.0, 560.0, 175.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=-75.0),
    )

ppv = actor_sub.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(500.0, -420.0, 250.0), unreal.Rotator(0.0, 0.0, 0.0))
if ppv:
    ppv.set_actor_label("PDF2BIM_PostProcess_ArchViz")
    ppv.set_folder_path("PDF2BIM/Lighting")
    ppv.set_editor_property("unbound", True)
    pps = ppv.get_editor_property("settings")
    pps.set_editor_property("override_dynamic_global_illumination_method", True)
    pps.set_editor_property("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN)
    pps.set_editor_property("override_reflection_method", True)
    pps.set_editor_property("reflection_method", unreal.ReflectionMethod.LUMEN)
    pps.set_editor_property("override_lumen_scene_lighting_quality", True)
    pps.set_editor_property("lumen_scene_lighting_quality", 4.0)
    pps.set_editor_property("override_lumen_final_gather_quality", True)
    pps.set_editor_property("lumen_final_gather_quality", 4.0)
    pps.set_editor_property("override_lumen_reflection_quality", True)
    pps.set_editor_property("lumen_reflection_quality", 4.0)
    pps.set_editor_property("override_ambient_occlusion_intensity", True)
    pps.set_editor_property("ambient_occlusion_intensity", 0.80)
    pps.set_editor_property("override_ambient_occlusion_radius", True)
    pps.set_editor_property("ambient_occlusion_radius", 140.0)
    pps.set_editor_property("override_bloom_intensity", True)
    pps.set_editor_property("bloom_intensity", 0.45)
    pps.set_editor_property("override_vignette_intensity", True)
    pps.set_editor_property("vignette_intensity", 0.32)
    pps.set_editor_property("override_auto_exposure_min_brightness", True)
    pps.set_editor_property("auto_exposure_min_brightness", 1.0)
    pps.set_editor_property("override_auto_exposure_max_brightness", True)
    pps.set_editor_property("auto_exposure_max_brightness", 1.0)

# 5. Configure Sun (Movable, Pitch=-22, Yaw=135, Intensity=8.0 lux, Temp=4800K) & SkyLight (Movable, RealTimeCapture=True)
if dir_light:
    dir_light.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-22.0, yaw=135.0), False)
    lc = dir_light.light_component
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_intensity(8.0)
    lc.set_editor_property("use_temperature", True)
    lc.set_editor_property("temperature", 4800.0)
    lc.set_light_color(unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

if sky_light:
    slc = sky_light.light_component
    slc.set_mobility(unreal.ComponentMobility.MOVABLE)
    slc.set_editor_property("real_time_capture", True)
    slc.set_intensity(1.5)
    slc.recapture_sky()

if exp_fog:
    fc = exp_fog.component
    fc.set_volumetric_fog(True)
    fc.set_fog_density(0.008)

def capture_shot(cam_loc, target_loc, sun_rot, fov, out_dir, filename):
    if dir_light and sun_rot is not None:
        dir_light.set_actor_rotation(sun_rot, False)
    if sky_light:
        sky_light.light_component.recapture_sky()

    cam_rot = unreal.MathLibrary.find_look_at_rotation(cam_loc, target_loc)
    editor_sub.set_level_viewport_camera_info(cam_loc, cam_rot)

    rt = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
    )
    cap_actor = actor_sub.spawn_actor_from_class(unreal.SceneCapture2D, cam_loc, cam_rot)
    comp = cap_actor.capture_component2d
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    comp.set_editor_property("fov_angle", fov)
    comp.set_editor_property("always_persist_rendering_state", True)
    comp.set_editor_property("capture_every_frame", True)
    comp.set_editor_property("capture_on_movement", True)

    cpps = comp.get_editor_property("post_process_settings")
    cpps.set_editor_property("override_dynamic_global_illumination_method", True)
    cpps.set_editor_property("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN)
    cpps.set_editor_property("override_reflection_method", True)
    cpps.set_editor_property("reflection_method", unreal.ReflectionMethod.LUMEN)
    cpps.set_editor_property("override_lumen_scene_lighting_quality", True)
    cpps.set_editor_property("lumen_scene_lighting_quality", 2.0)
    cpps.set_editor_property("override_lumen_final_gather_quality", True)
    cpps.set_editor_property("lumen_final_gather_quality", 2.0)
    cpps.set_editor_property("override_lumen_reflection_quality", True)
    cpps.set_editor_property("lumen_reflection_quality", 2.0)
    cpps.set_editor_property("override_ambient_occlusion_intensity", True)
    cpps.set_editor_property("ambient_occlusion_intensity", 0.85)
    cpps.set_editor_property("override_ambient_occlusion_radius", True)
    cpps.set_editor_property("ambient_occlusion_radius", 140.0)
    cpps.set_editor_property("override_bloom_intensity", True)
    cpps.set_editor_property("bloom_intensity", 0.45)
    cpps.set_editor_property("override_vignette_intensity", True)
    cpps.set_editor_property("vignette_intensity", 0.32)
    cpps.set_editor_property("override_auto_exposure_min_brightness", True)
    cpps.set_editor_property("auto_exposure_min_brightness", 1.0)
    cpps.set_editor_property("override_auto_exposure_max_brightness", True)
    cpps.set_editor_property("auto_exposure_max_brightness", 1.0)

    for _ in range(3):
        comp.capture_scene()

    unreal.RenderingLibrary.export_render_target(world, rt, out_dir, filename)
    actor_sub.destroy_actor(cap_actor)
    print("CAPTURED_OK", f"{out_dir}/{filename}")

out_dir = "C:/Users/filip/pdf2bim_remote"
do_capture = not os.environ.get("PDF2BIM_SKIP_CAPTURE", "")

if do_capture:
    # Shot 1: Front / South-East perspective
    capture_shot(
        unreal.Vector(1880.0, 1140.0, 310.0),
        unreal.Vector(490.0, -320.0, 365.0),
        unreal.Rotator(roll=0.0, pitch=-22.0, yaw=-135.0),
        48.0,
        out_dir,
        "ue5_shot1_front.png",
    )

    # Shot 2: Garden / North-East perspective (with Pitch=-22, Yaw=135 as requested)
    capture_shot(
        unreal.Vector(1880.0, -2080.0, 320.0),
        unreal.Vector(490.0, -560.0, 365.0),
        unreal.Rotator(roll=0.0, pitch=-22.0, yaw=135.0),
        48.0,
        out_dir,
        "ue5_shot2_garden.png",
    )

    # Shot 3: Close-up of 3D timber cladding planks at South-East corner
    capture_shot(
        unreal.Vector(1310.0, 230.0, 215.0),
        unreal.Vector(980.0, -110.0, 210.0),
        unreal.Rotator(roll=0.0, pitch=-22.0, yaw=-135.0),
        42.0,
        out_dir,
        "ue5_shot3_wood_closeup.png",
    )

    # Shot 4: Close-up of mineral stucco plaster, window glass reflections & anthracite roof tiles
    capture_shot(
        unreal.Vector(1380.0, 340.0, 445.0),
        unreal.Vector(820.0, -240.0, 465.0),
        unreal.Rotator(roll=0.0, pitch=-22.0, yaw=-135.0),
        42.0,
        out_dir,
        "ue5_shot4_plaster_roof_glass.png",
    )

    # Shot 5: Interior Salon/Jadalnia view showing smooth realistic interior gypsum skim-coat ("Gładź gipsowa")
    capture_shot(
        unreal.Vector(255.0, -535.0, 247.0),
        unreal.Vector(720.0, -650.0, 210.0),
        unreal.Rotator(roll=0.0, pitch=-22.0, yaw=135.0),
        75.0,
        out_dir,
        "ue5_int3_parter_salon.png",
    )

try:
    # Leave viewport camera outside in front of the house (above ground) so PIE from camera or PlayerStart never starts under the map
    front_cam_loc = unreal.Vector(1680.0, 1020.0, 260.0)
    front_cam_rot = unreal.MathLibrary.find_look_at_rotation(front_cam_loc, unreal.Vector(490.0, -320.0, 340.0))
    editor_sub.set_level_viewport_camera_info(front_cam_loc, front_cam_rot)
    unreal.EditorAssetLibrary.save_directory("/Game/PDF2BIM", only_if_is_dirty=False, recursive=True)
    unreal.EditorLoadingAndSavingUtils.save_map(world, "/Game/PDF2BIM/Dom1_Gniezniki_Map")
except Exception:
    pass
"""


def main() -> int:
    skip_cap = "--no-capture" in sys.argv
    script_body = CAPTURE_SCRIPT
    if skip_cap:
        script_body = script_body.replace("do_capture = not os.environ.get(\"PDF2BIM_SKIP_CAPTURE\", \"\")", "do_capture = False")
    p = Path("C:/Users/filip/pdf2bim_remote/ue_capture_sync.py")
    p.write_text(script_body, encoding="utf-8")

    node = re.RemoteExecution()
    node.start()
    try:
        for _ in range(15):
            if node.remote_nodes:
                break
            time.sleep(0.2)
        if not node.remote_nodes:
            print("[ERROR] No Unreal Engine RemoteExecution nodes found", file=sys.stderr)
            return 1
        target = node.remote_nodes[0]
        node.open_command_connection(target["node_id"])
        res = node.run_command(str(p), exec_mode=re.MODE_EXEC_FILE)
        print("[CAPTURE_RESULT]", res)
        return 0 if res.get("success") else 1
    finally:
        node.stop()


if __name__ == "__main__":
    sys.exit(main())

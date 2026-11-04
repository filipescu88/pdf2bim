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

# 0. Force Cinematic Scalability, Lumen GI + Reflections, TSR Anti-Aliasing, and SSAO in UE 5.8
for cvar, val in [
    ("r.DynamicGlobalIlluminationMethod", 1),
    ("r.ReflectionMethod", 1),
    ("r.Lumen.DiffuseIndirect.Allow", 1),
    ("r.Lumen.Reflections.Allow", 1),
    ("r.PostProcessAAQuality", 6),
    ("r.AntiAliasingMethod", 4),
    ("r.AmbientOcclusionLevels", 3),
    ("r.SSR.Quality", 4),
    ("r.ContactShadows", 1),
    ("r.ShadowQuality", 5),
    ("r.Streaming.PoolSize", 3000),
    ("sg.AntiAliasingQuality", 4),
    ("sg.ShadowQuality", 4),
    ("sg.GlobalIlluminationQuality", 4),
    ("sg.ReflectionQuality", 4),
    ("sg.PostProcessQuality", 4),
    ("sg.TextureQuality", 4),
    ("sg.EffectsQuality", 4),
    ("sg.ShadingQuality", 4),
]:
    unreal.SystemLibrary.execute_console_command(world, f"{cvar} {val}")

# 1. Lower OpenWorld Landscape so sand dune peaks don't poke through the house walls
dir_light = None
sky_light = None
exp_fog = None

for a in actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if lbl == "Floor" or lbl.startswith("PDF2BIM_PostProcess") or lbl.startswith("PDF2BIM_Hedge_"):
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
        a.set_actor_scale3d(unreal.Vector(4.0, 4.0, 1.0))

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
        if not unreal.EditorAssetLibrary.does_asset_exist(f"{tex_pkg}/{stem}"):
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

# Glass (translucent architectural double-glazing with crisp sky reflection)
m_glass = make_mat("M_Glass_Clear")
m_glass.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
m_glass.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
m_glass.set_editor_property("two_sided", True)
c_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant3Vector, -300, -100)
c_gl.set_editor_property("constant", unreal.LinearColor(0.05, 0.11, 0.15, 1.0))
mel.connect_material_property(c_gl, "", unreal.MaterialProperty.MP_BASE_COLOR)
m_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -300, 0)
m_gl.set_editor_property("r", 0.90)
mel.connect_material_property(m_gl, "", unreal.MaterialProperty.MP_METALLIC)
o_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -300, 100)
o_gl.set_editor_property("r", 0.32)
mel.connect_material_property(o_gl, "", unreal.MaterialProperty.MP_OPACITY)
r_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -300, 200)
r_gl.set_editor_property("r", 0.01)
mel.connect_material_property(r_gl, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(m_glass)

# (diff_stem, norm_stem, rough_stem, tint, is_plaster, rough_mult, metal_v, spec_v, uv_t)
pbr_defs = {
    "M_Wall_Plaster_White": ("painted_plaster_wall_diffuse", "painted_plaster_wall_nor_gl", "painted_plaster_wall_rough", (0.95, 0.94, 0.91), True, 0.88, 0.0, 0.35, 3.5),
    "M_Roof_Tile_Anthracite": ("grey_roof_tiles_02_diffuse", "grey_roof_tiles_02_nor_gl", "grey_roof_tiles_02_rough", (0.18, 0.20, 0.23), False, 0.55, 0.15, 0.65, 2.4),
    "M_Facade_Cladding_Oak": ("wood_floor_deck_diffuse", "wood_floor_deck_nor_gl", "wood_floor_deck_rough", (0.78, 0.64, 0.48), False, 0.58, 0.0, 0.55, 1.4),
    "M_Door_Veneer_Oak": ("oak_countertop_diffuse", "oak_veneer_nor_gl", "oak_veneer_rough", (0.76, 0.56, 0.38), False, 0.38, 0.0, 0.62, 0.65),
    "M_Floor_Parquet_Oak": ("laminate_floor_02_diffuse", "laminate_floor_02_nor_gl", "laminate_floor_02_rough", (0.86, 0.76, 0.65), False, 0.36, 0.0, 0.68, 1.6),
    "M_Floor_Tile_Gres": ("concrete_tiles_diffuse", "concrete_tiles_nor_gl", "concrete_tiles_rough", (0.91, 0.90, 0.88), False, 0.28, 0.0, 0.72, 1.5),
    "M_Structure_Concrete": ("painted_plaster_wall_diffuse", "painted_plaster_wall_nor_gl", "painted_plaster_wall_rough", (0.95, 0.94, 0.92), True, 0.85, 0.0, 0.35, 3.0),
    "M_Terrace_Paver_Grey": ("concrete_pavers_02_diffuse", "concrete_pavers_02_nor_gl", "concrete_pavers_02_rough", (0.76, 0.77, 0.79), False, 0.72, 0.0, 0.48, 2.5),
    "M_WalkwayPavers": ("concrete_pavers_02_diffuse", "concrete_pavers_02_nor_gl", "concrete_pavers_02_rough", (0.72, 0.73, 0.75), False, 0.75, 0.0, 0.45, 2.5),
    "M_ParcelGrass": ("lawn_grass_diffuse", "leafy_grass_nor_gl", "leafy_grass_rough", (0.72, 0.86, 0.64), False, 0.90, 0.0, 0.25, 28.0),
    "M_Hedge_Boxwood": ("hedge_boxwood_diffuse", "hedge_boxwood_nor_gl", "hedge_boxwood_rough", (0.62, 0.78, 0.55), False, 0.85, 0.0, 0.30, 3.2),
    "M_Window_Frame_Anthracite": (None, None, None, (0.045, 0.050, 0.058), False, 0.28, 0.45, 0.70, 1.0),
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
        ts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -450, -220)
        ts.set_editor_property("texture", dtex)
        mel.connect_material_expressions(uv, "", ts, "UVs")
        lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -180, -220)
        c_white = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -450, -360)
        c_white.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        alpha = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, -80)
        alpha.set_editor_property("r", 0.16)
        mel.connect_material_expressions(c_white, "", lerp, "A")
        mel.connect_material_expressions(ts, "RGB", lerp, "B")
        mel.connect_material_expressions(alpha, "", lerp, "Alpha")
        mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
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
    if ntex:
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

# Map Ceramic_Block and Insulation_EPS to clean white plaster so window reveals are white
built_mats["M_Wall_Ceramic_Block"] = built_mats["M_Wall_Plaster_White"]
built_mats["M_Wall_Insulation_EPS"] = built_mats["M_Wall_Plaster_White"]

# 3. Assign built_mats to all spawned Dom 1 StaticMeshActors
assigned = 0
for a in actor_sub.get_all_level_actors():
    if not a.get_actor_label().startswith("PDF2BIM_Dom1_"):
        continue
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
        for k, target_m in built_mats.items():
            if cname.startswith(k):
                smc.set_material(idx, target_m)
                sm.set_material(idx, target_m)
                assigned += 1
                break

print("ASSIGNED_MATERIAL_SLOTS", assigned)

# 4. Spawn 3D Boxwood Perimeter Hedge around the parcel & Unbound PostProcessVolume for Lumen ArchViz
cube_sm = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube")
hedge_mat = built_mats.get("M_Hedge_Boxwood")
if cube_sm and hedge_mat:
    hedge_segments = [
        ("North", (515.0, -1780.0, 140.0), (22.0, 0.75, 1.75)),
        ("West", (-550.0, -480.0, 140.0), (0.75, 26.5, 1.75)),
        ("East_Back", (1580.0, -1080.0, 140.0), (0.75, 14.5, 1.75)),
        ("South_West", (-180.0, 820.0, 140.0), (7.5, 0.75, 1.55)),
        ("South_East", (1120.0, 820.0, 140.0), (9.5, 0.75, 1.55)),
    ]
    for h_sfx, h_loc, h_scale in hedge_segments:
        ha = actor_sub.spawn_actor_from_object(cube_sm, unreal.Vector(*h_loc), unreal.Rotator(0.0, 0.0, 0.0))
        if ha:
            ha.set_actor_scale3d(unreal.Vector(*h_scale))
            ha.set_actor_label(f"PDF2BIM_Hedge_{h_sfx}")
            ha.set_folder_path("PDF2BIM/Landscaping")
            ha.static_mesh_component.set_material(0, hedge_mat)

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
    cpps.set_editor_property("lumen_scene_lighting_quality", 4.0)
    cpps.set_editor_property("override_lumen_final_gather_quality", True)
    cpps.set_editor_property("lumen_final_gather_quality", 4.0)
    cpps.set_editor_property("override_lumen_reflection_quality", True)
    cpps.set_editor_property("lumen_reflection_quality", 4.0)
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

    for _ in range(8):
        comp.capture_scene()

    unreal.RenderingLibrary.export_render_target(world, rt, out_dir, filename)
    actor_sub.destroy_actor(cap_actor)
    print("CAPTURED_OK", f"{out_dir}/{filename}")

out_dir = "C:/Users/filip/pdf2bim_remote"

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
"""


def main() -> int:
    p = Path("C:/Users/filip/pdf2bim_remote/ue_capture_sync.py")
    p.write_text(CAPTURE_SCRIPT, encoding="utf-8")

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

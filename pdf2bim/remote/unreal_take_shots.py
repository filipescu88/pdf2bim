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

# 1. Lower OpenWorld Landscape so sand dune peaks don't poke through the house walls
dir_light = None
sky_light = None

for a in actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if lbl == "Floor":
        a.set_actor_hidden_in_game(True)
        a.set_is_temporarily_hidden_in_editor(True)
    elif "Landscape" in cls or "HLOD" in cls:
        a.set_actor_hidden_in_game(False)
        a.set_is_temporarily_hidden_in_editor(False)
        loc = a.get_actor_location()
        a.set_actor_location(unreal.Vector(loc.x, loc.y, -450.0), False, False)
    elif "DirectionalLight" in cls or "DirectionalLight" in lbl:
        dir_light = a
    elif "SkyLight" in cls or "SkyLight" in lbl:
        sky_light = a
    elif lbl == "PDF2BIM_Dom1_SM_Garden_Lawn":
        a.set_actor_scale3d(unreal.Vector(4.0, 4.0, 1.0))

# 2. Build or update clean UE5 Master Materials in /Game/PDF2BIM/Materials
mat_pkg = "/Game/PDF2BIM/Materials"
tex_pkg = "/Game/PDF2BIM/Textures"

def load_tex(stem, is_normal=False):
    p = f"{tex_pkg}/{stem}"
    if unreal.EditorAssetLibrary.does_asset_exist(p):
        t = unreal.EditorAssetLibrary.load_asset(p)
        if t and is_normal:
            t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
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

# Glass (translucent architectural double-glazing)
m_glass = make_mat("M_Glass_Clear")
m_glass.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
m_glass.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
m_glass.set_editor_property("two_sided", True)
c_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant3Vector, -300, -100)
c_gl.set_editor_property("constant", unreal.LinearColor(0.08, 0.16, 0.22, 1.0))
mel.connect_material_property(c_gl, "", unreal.MaterialProperty.MP_BASE_COLOR)
m_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -300, 0)
m_gl.set_editor_property("r", 0.85)
mel.connect_material_property(m_gl, "", unreal.MaterialProperty.MP_METALLIC)
o_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -300, 100)
o_gl.set_editor_property("r", 0.36)
mel.connect_material_property(o_gl, "", unreal.MaterialProperty.MP_OPACITY)
r_gl = mel.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -300, 200)
r_gl.set_editor_property("r", 0.02)
mel.connect_material_property(r_gl, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(m_glass)

pbr_defs = {
    "M_Wall_Plaster_White": ("painted_plaster_wall_diffuse", (0.94, 0.93, 0.90), True, 0.85, 0.0, 3.0),
    "M_Roof_Tile_Anthracite": ("grey_roof_tiles_02_diffuse", (0.20, 0.22, 0.25), False, 0.48, 0.10, 2.2),
    "M_Facade_Cladding_Oak": ("wood_floor_deck_diffuse", (0.76, 0.64, 0.50), False, 0.52, 0.0, 1.3),
    "M_Door_Veneer_Oak": ("laminate_floor_02_diffuse", (0.65, 0.48, 0.34), False, 0.40, 0.0, 1.2),
    "M_Floor_Parquet_Oak": ("laminate_floor_02_diffuse", (0.85, 0.75, 0.65), False, 0.38, 0.0, 1.5),
    "M_Floor_Tile_Gres": ("concrete_tiles_diffuse", (0.90, 0.89, 0.87), False, 0.32, 0.0, 1.5),
    "M_Structure_Concrete": ("concrete_tiles_diffuse", (0.65, 0.66, 0.68), False, 0.75, 0.0, 1.5),
    "M_Terrace_Paver_Grey": ("concrete_pavers_02_diffuse", (0.76, 0.77, 0.79), False, 0.68, 0.0, 2.5),
    "M_WalkwayPavers": ("concrete_pavers_02_diffuse", (0.72, 0.73, 0.75), False, 0.72, 0.0, 2.5),
    "M_ParcelGrass": ("lawn_grass_diffuse", (0.75, 0.88, 0.68), False, 0.88, 0.0, 28.0),
    "M_Window_Frame_Anthracite": (None, (0.04, 0.045, 0.052), False, 0.34, 0.18, 1.0),
}

built_mats = {"M_Glass_Clear": m_glass}
for mname, (diff_s, tint, is_plaster, rough_v, metal_v, uv_t) in pbr_defs.items():
    mat = make_mat(mname)
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -650, 0)
    uv.set_editor_property("u_tiling", uv_t)
    uv.set_editor_property("v_tiling", uv_t)

    dtex = load_tex(diff_s) if diff_s else None
    if dtex and not is_plaster:
        ts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -400, -180)
        ts.set_editor_property("texture", dtex)
        mel.connect_material_expressions(uv, "", ts, "UVs")
        mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, -180)
        ct = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, -320)
        ct.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        mel.connect_material_expressions(ts, "RGB", mul, "A")
        mel.connect_material_expressions(ct, "", mul, "B")
        mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    elif dtex and is_plaster:
        # Subtle 12% plaster texture variation blended into crisp 88% architectural warm white
        ts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -450, -180)
        ts.set_editor_property("texture", dtex)
        mel.connect_material_expressions(uv, "", ts, "UVs")
        lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -150, -180)
        c_white = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -450, -340)
        c_white.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        alpha = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, -40)
        alpha.set_editor_property("r", 0.14)
        mel.connect_material_expressions(c_white, "", lerp, "A")
        mel.connect_material_expressions(ts, "RGB", lerp, "B")
        mel.connect_material_expressions(alpha, "", lerp, "Alpha")
        mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        c = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, -150)
        c.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)

    r_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 150)
    r_node.set_editor_property("r", rough_v)
    mel.connect_material_property(r_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

    m_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 240)
    m_node.set_editor_property("r", metal_v)
    mel.connect_material_property(m_node, "", unreal.MaterialProperty.MP_METALLIC)
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

# 4. Configure Sun & Sky lighting and capture both shots
if dir_light:
    lc = dir_light.light_component
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_intensity(6.5)
    lc.set_light_color(unreal.LinearColor(1.0, 0.96, 0.90, 1.0))

if sky_light:
    slc = sky_light.light_component
    slc.set_mobility(unreal.ComponentMobility.MOVABLE)
    slc.set_intensity(2.4)
    slc.recapture_sky()

def capture_shot(cam_loc, target_loc, sun_from_loc, fov, out_dir, filename):
    if dir_light:
        sun_rot = unreal.MathLibrary.find_look_at_rotation(sun_from_loc, target_loc)
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
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    comp.capture_scene()

    unreal.RenderingLibrary.export_render_target(world, rt, out_dir, filename)
    actor_sub.destroy_actor(cap_actor)
    print("CAPTURED_OK", f"{out_dir}/{filename}")

out_dir = "C:/Users/filip/pdf2bim_remote"

# Shot 1: Front / South-East perspective (Entrance Porch, Front Kitchen & Bathroom Windows, East Gable)
capture_shot(
    unreal.Vector(1880.0, 1140.0, 310.0),
    unreal.Vector(490.0, -320.0, 365.0),
    unreal.Vector(1450.0, 1850.0, 1380.0),
    48.0,
    out_dir,
    "ue5_shot1_front.png",
)

# Shot 2: Garden / North-East perspective (Back Terrace, Living/Dining Glazing, Roof Skylights)
capture_shot(
    unreal.Vector(1880.0, -2080.0, 320.0),
    unreal.Vector(490.0, -560.0, 365.0),
    unreal.Vector(1450.0, -2400.0, 1380.0),
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

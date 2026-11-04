"""Live Unreal Engine 5.8 Remote Execution importer, PBR material builder, and level spawner for Dom 1.

Runs on the Windows workstation (`C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe`)
and connects to the running `UnrealEditor.exe` via `remote_execution.py` (UDP 6766).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

UE_PYTHON_DIR = "C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"
if UE_PYTHON_DIR not in sys.path:
    sys.path.append(UE_PYTHON_DIR)

import remote_execution as re  # type: ignore


EDITOR_PAYLOAD = """
import unreal

editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
mel = unreal.MaterialEditingLibrary

# 1. Remove any previous PDF2BIM actors from the level and hide OpenWorld Landscape sand dunes
for act in actor_sub.get_all_level_actors():
    lbl = act.get_actor_label()
    cls = act.get_class().get_name()
    if lbl.startswith("PDF2BIM_"):
        actor_sub.destroy_actor(act)
    elif "Landscape" in cls or "HLOD" in cls:
        act.set_actor_hidden_in_game(True)
        act.set_is_temporarily_hidden_in_editor(True)
        loc = act.get_actor_location()
        act.set_actor_location(unreal.Vector(loc.x, loc.y, -2500.0), False, False)

# 2. Import PBR textures into /Game/PDF2BIM/Textures
tex_dir = "C:/Users/filip/pdf2bim_remote/textures"
tex_dest = "/Game/PDF2BIM/Textures"
tex_files = [
    "painted_plaster_wall_diffuse.jpg",
    "painted_plaster_wall_nor_gl.jpg",
    "painted_plaster_wall_rough.jpg",
    "anthracite_roof_diffuse.jpg",
    "grey_roof_tiles_02_diffuse.jpg",
    "grey_roof_tiles_02_nor_gl.jpg",
    "grey_roof_tiles_02_rough.jpg",
    "wood_floor_deck_diffuse.jpg",
    "wood_floor_deck_nor_gl.jpg",
    "wood_floor_deck_rough.jpg",
    "facade_timber_cladding_diffuse.jpg",
    "facade_timber_cladding_nor_gl.jpg",
    "facade_timber_cladding_rough.jpg",
    "concrete_tiles_diffuse.jpg",
    "concrete_tiles_nor_gl.jpg",
    "concrete_tiles_rough.jpg",
    "concrete_pavers_02_diffuse.jpg",
    "laminate_floor_02_diffuse.jpg",
    "lawn_grass_diffuse.jpg",
    "leafy_grass_nor_gl.jpg",
]
tex_tasks = []
for tf in tex_files:
    t = unreal.AssetImportTask()
    t.filename = f"{tex_dir}/{tf}"
    t.destination_path = tex_dest
    t.automated = True
    t.replace_existing = True
    t.save = False
    tex_tasks.append(t)
asset_tools.import_asset_tasks(tex_tasks)

def load_tex(stem):
    path = f"{tex_dest}/{stem}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        t = unreal.EditorAssetLibrary.load_asset(path)
        if t and "facade_timber_cladding" in stem:
            try:
                t.set_editor_property("never_stream", True)
            except Exception:
                pass
        return t
    return None

# 3. Clean up old meshes and re-import Dom1_Gniezniki FBX (with metric Box UVs)
if unreal.EditorAssetLibrary.does_directory_exist("/Game/PDF2BIM/Dom2_Amor"):
    unreal.EditorAssetLibrary.delete_directory("/Game/PDF2BIM/Dom2_Amor")
if unreal.EditorAssetLibrary.does_directory_exist("/Game/PDF2BIM/Dom1_Gniezniki"):
    unreal.EditorAssetLibrary.delete_directory("/Game/PDF2BIM/Dom1_Gniezniki")

fbx_path = "C:/Users/filip/Desktop/pdf2bim_unreal/dom_w_gnieznikach/dom_w_gnieznikach_unreal.fbx"
dest_path = "/Game/PDF2BIM/Dom1_Gniezniki"
base_loc = unreal.Vector(0.0, 0.0, 92.0)

fbx_ui = unreal.FbxImportUI()
fbx_ui.import_mesh = True
fbx_ui.import_as_skeletal = False
fbx_ui.static_mesh_import_data.combine_meshes = False
fbx_ui.static_mesh_import_data.remove_degenerates = False

task = unreal.AssetImportTask()
task.filename = fbx_path
task.destination_path = dest_path
task.automated = True
task.replace_existing = True
task.replace_existing_settings = True
task.save = False
task.options = fbx_ui
asset_tools.import_asset_tasks([task])

# 4. Build PBR Material graphs for all imported M_* materials
pbr_recipes = {
    "M_Wall_Plaster_White": (None, "painted_plaster_wall_nor_gl", "painted_plaster_wall_rough", (0.92, 0.91, 0.88), 0.86, 0.0, 4.5),
    "M_Wall_Ceramic_Block": (None, "painted_plaster_wall_nor_gl", "painted_plaster_wall_rough", (0.92, 0.91, 0.88), 0.86, 0.0, 4.5),
    "M_Wall_Insulation_EPS": (None, "painted_plaster_wall_nor_gl", "painted_plaster_wall_rough", (0.92, 0.91, 0.88), 0.86, 0.0, 4.5),
    "M_Roof_Tile_Anthracite": ("grey_roof_tiles_02_diffuse", "grey_roof_tiles_02_nor_gl", "grey_roof_tiles_02_rough", (0.14, 0.15, 0.17), 0.50, 0.08, 2.2),
    "M_Facade_Cladding_Oak": ("facade_timber_cladding_diffuse", "facade_timber_cladding_nor_gl", "facade_timber_cladding_rough", (0.98, 0.98, 0.98), 0.78, 0.0, 1.0),
    "M_Door_Veneer_Oak": ("laminate_floor_02_diffuse", None, None, (0.52, 0.33, 0.18), 0.42, 0.0, 1.2),
    "M_Floor_Parquet_Oak": ("laminate_floor_02_diffuse", None, None, (0.64, 0.47, 0.30), 0.40, 0.0, 1.5),
    "M_Floor_Tile_Gres": ("concrete_tiles_diffuse", "concrete_tiles_nor_gl", "concrete_tiles_rough", (0.82, 0.80, 0.77), 0.35, 0.0, 1.5),
    "M_Structure_Concrete": ("concrete_tiles_diffuse", "concrete_tiles_nor_gl", "concrete_tiles_rough", (0.58, 0.58, 0.59), 0.75, 0.0, 1.5),
    "M_Terrace_Paver_Grey": ("concrete_pavers_02_diffuse", "concrete_tiles_nor_gl", "concrete_tiles_rough", (0.56, 0.56, 0.58), 0.70, 0.0, 2.2),
    "M_WalkwayPavers": ("concrete_pavers_02_diffuse", None, None, (0.52, 0.52, 0.54), 0.78, 0.0, 2.5),
    "M_ParcelGrass": ("lawn_grass_diffuse", "leafy_grass_nor_gl", None, (0.24, 0.42, 0.18), 0.88, 0.0, 6.0),
    "M_Window_Frame_Anthracite": (None, None, None, (0.035, 0.038, 0.045), 0.36, 0.15, 1.0),
}

assets = asset_reg.get_assets_by_path(dest_path, recursive=True)
for a_data in assets:
    cls_name = str(a_data.asset_class_path.asset_name)
    a_name = str(a_data.asset_name)
    if cls_name != "Material":
        continue
    mat = a_data.get_asset()
    if not mat:
        continue
    mel.delete_all_material_expressions(mat)

    if "Glass" in a_name:
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
        mat.set_editor_property("two_sided", True)
        col_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, -100)
        col_node.set_editor_property("constant", unreal.LinearColor(0.08, 0.15, 0.20, 1.0))
        mel.connect_material_property(col_node, "", unreal.MaterialProperty.MP_BASE_COLOR)
        met_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 0)
        met_node.set_editor_property("r", 0.80)
        mel.connect_material_property(met_node, "", unreal.MaterialProperty.MP_METALLIC)
        op_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 100)
        op_node.set_editor_property("r", 0.35)
        mel.connect_material_property(op_node, "", unreal.MaterialProperty.MP_OPACITY)
        rough_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 200)
        rough_node.set_editor_property("r", 0.03)
        mel.connect_material_property(rough_node, "", unreal.MaterialProperty.MP_ROUGHNESS)
        mel.recompile_material(mat)
        continue

    rkey = next((k for k in pbr_recipes if a_name.startswith(k)), None)
    if not rkey:
        continue
    diff_s, norm_s, rough_s, tint_rgb, rough_val, metal_val, uv_tile = pbr_recipes[rkey]
    uv_node = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -650, 0)
    uv_node.set_editor_property("u_tiling", uv_tile)
    uv_node.set_editor_property("v_tiling", uv_tile)

    diff_tex = load_tex(diff_s) if diff_s else None
    if diff_tex:
        ts_diff = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, -180)
        ts_diff.set_editor_property("texture", diff_tex)
        mel.connect_material_expressions(uv_node, "", ts_diff, "UVs")
        # Multiply with subtle architectural tint so roof is deep anthracite and oak is warm golden
        if rkey == "M_Roof_Tile_Anthracite":
            mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, -180)
            c_tint = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -380, -320)
            c_tint.set_editor_property("constant", unreal.LinearColor(0.18, 0.19, 0.22, 1.0))
            mel.connect_material_expressions(ts_diff, "RGB", mul, "A")
            mel.connect_material_expressions(c_tint, "", mul, "B")
            mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
        elif rkey == "M_Facade_Cladding_Oak":
            mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, -180)
            c_tint = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -380, -320)
            c_tint.set_editor_property("constant", unreal.LinearColor(0.78, 0.68, 0.56, 1.0))
            mel.connect_material_expressions(ts_diff, "RGB", mul, "A")
            mel.connect_material_expressions(c_tint, "", mul, "B")
            mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
        else:
            mel.connect_material_property(ts_diff, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        c_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, -150)
        c_node.set_editor_property("constant", unreal.LinearColor(tint_rgb[0], tint_rgb[1], tint_rgb[2], 1.0))
        mel.connect_material_property(c_node, "", unreal.MaterialProperty.MP_BASE_COLOR)

    norm_tex = load_tex(norm_s) if norm_s else None
    if norm_tex:
        norm_tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        ts_norm = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 80)
        ts_norm.set_editor_property("texture", norm_tex)
        ts_norm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_expressions(uv_node, "", ts_norm, "UVs")
        mel.connect_material_property(ts_norm, "RGB", unreal.MaterialProperty.MP_NORMAL)

    rough_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 260)
    rough_node.set_editor_property("r", rough_val)
    mel.connect_material_property(rough_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

    metal_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 340)
    metal_node.set_editor_property("r", metal_val)
    mel.connect_material_property(metal_node, "", unreal.MaterialProperty.MP_METALLIC)
    mel.recompile_material(mat)

# 5. Spawn all StaticMesh actors of Dom 1
sm_count = 0
for a_data in assets:
    if str(a_data.asset_class_path.asset_name) == "StaticMesh":
        mesh_obj = a_data.get_asset()
        if mesh_obj:
            mname = mesh_obj.get_name()
            if "neighbor_" in mname.lower() or "sasiad_" in mname.lower() or "dzialka_" in mname.lower():
                continue
            act = actor_sub.spawn_actor_from_object(mesh_obj, base_loc, unreal.Rotator(0.0, 0.0, 0.0))
            if act:
                act.set_actor_label(f"PDF2BIM_Dom1_{mname}")
                act.set_folder_path("PDF2BIM/Dom1_Gniezniki")
                sm_count += 1

editor_sub.set_level_viewport_camera_info(
    unreal.Vector(1650.0, 980.0, 310.0),
    unreal.Rotator(0.0, -14.0, -135.0),
)
try:
    unreal.EditorAssetLibrary.save_directory("/Game/PDF2BIM", only_if_is_dirty=False, recursive=True)
except Exception:
    pass
print(f"SPAWN_PBR_DOM1_OK total_actors={sm_count}")
"""


def main() -> int:
    payload_path = Path("C:/Users/filip/pdf2bim_remote/ue_editor_spawn_houses.py")
    payload_path.write_text(EDITOR_PAYLOAD, encoding="utf-8")

    node = re.RemoteExecution()
    node.start()
    try:
        for _ in range(15):
            if node.remote_nodes:
                break
            time.sleep(0.2)
        if not node.remote_nodes:
            print("[ERROR] No Unreal Engine RemoteExecution nodes found on UDP 6766", file=sys.stderr)
            return 1

        target = node.remote_nodes[0]
        print(f"[INFO] Connecting to Unreal Editor node: {target['project_name']} ({target['engine_version']})")
        node.open_command_connection(target["node_id"])
        res = node.run_command(str(payload_path), exec_mode=re.MODE_EXEC_FILE)
        print("[RESULT]", res)
        return 0 if res.get("success") else 1
    finally:
        node.stop()


if __name__ == "__main__":
    sys.exit(main())

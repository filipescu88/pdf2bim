"""Capture 4 interior screenshots (Upstairs & Downstairs) in Unreal Engine 5.8 and inspect Fab furniture asset."""

from __future__ import annotations

import sys
import time
from pathlib import Path

UE_PYTHON_DIR = "C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"
if UE_PYTHON_DIR not in sys.path:
    sys.path.append(UE_PYTHON_DIR)

import remote_execution as re  # type: ignore


INSPECT_SCRIPT = """
import unreal

editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = editor_sub.get_editor_world()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

# 1. Import individual Fab furniture meshes from C:/Users/filip/pdf2bim_remote/fab_furniture_pieces.fbx
fbx_path = "C:/Users/filip/pdf2bim_remote/fab_furniture_pieces.fbx"
dest_folder = "/Game/PDF2BIM/FabFurnitureV2"

if not unreal.EditorAssetLibrary.does_asset_exist(f"{dest_folder}/SM_Fab_Executive_Desk"):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", dest_folder)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_as_skeletal", False)
    options.static_mesh_import_data.set_editor_property("combine_meshes", False)
    options.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)
    options.static_mesh_import_data.set_editor_property("auto_generate_collision", True)
    task.set_editor_property("options", options)

    asset_tools.import_asset_tasks([task])

# 2. Bind original Fab MaterialInstanceConstant assets to every slot of each SM_Fab_* mesh
fab_mat_dir = "/Game/Fab/Office_Pack_-_Modern_Office_Interior_Props__FREE_/office_props/Materials"
fab_mats = {}
for mpath in unreal.EditorAssetLibrary.list_assets(fab_mat_dir, recursive=False):
    m_obj = unreal.EditorAssetLibrary.load_asset(mpath.split(".")[0])
    if m_obj:
        fab_mats[m_obj.get_name()] = m_obj

piece_names = [
    "SM_Fab_Executive_Desk",
    "SM_Fab_Executive_Chair",
    "SM_Fab_Shelving_Decor",
    "SM_Fab_Credenza_Sideboard",
    "SM_Fab_Lounge_Armchair",
    "SM_Fab_Indoor_Plant_Tree",
    "SM_Fab_Area_Rug",
]

loaded_pieces = {}
for pname in piece_names:
    p_asset_path = f"{dest_folder}/{pname}"
    if unreal.EditorAssetLibrary.does_asset_exist(p_asset_path):
        sm = unreal.EditorAssetLibrary.load_asset(p_asset_path)
        sm_Mats = sm.get_editor_property("static_materials")
        needs_bind = False
        new_mats = []
        for sm_mat in sm_Mats:
            slot_name = str(sm_mat.material_slot_name)
            base_slot = slot_name.split(".")[0]
            target_m = fab_mats.get(slot_name) or fab_mats.get(base_slot)
            if target_m and sm_mat.material_interface != target_m:
                sm_mat.material_interface = target_m
                needs_bind = True
            new_mats.append(sm_mat)
        if needs_bind:
            sm.set_editor_property("static_materials", new_mats)
        loaded_pieces[pname] = sm
        print("BOUND_FAB_MESH", pname, len(new_mats))

# 3. Remove any previous PDF2BIM_Furn_ or PDF2BIM_IntLight_ actors & brighten ceiling slab
white_plaster = unreal.EditorAssetLibrary.load_asset("/Game/PDF2BIM/Materials/M_Wall_Plaster_White")
for a in list(actor_sub.get_all_level_actors()):
    lbl = a.get_actor_label()
    if lbl.startswith("PDF2BIM_Furn_") or lbl.startswith("PDF2BIM_IntLight_"):
        actor_sub.destroy_actor(a)
    elif lbl == "PDF2BIM_Dom1_Strop_slab_parter_ceiling" and white_plaster:
        a.static_mesh_component.set_material(0, white_plaster)

# 4. Spawn Fab furniture inside Parter (Z=94) and Poddasze (Z=402)
# Coordinate mapping: X_ue = +X_bim*100, Y_ue = -Y_bim*100, Z_ue = +Z_bim*100 + 92
placements = [
    # Parter: 1.4 Salon + Jadalnia (Z=94.0)
    ("Parter_Salon_Rug", "SM_Fab_Area_Rug", (455.0, -640.0, 94.2), 0.0, (0.72, 0.72, 1.0)),
    ("Parter_Salon_Sofa", "SM_Fab_Credenza_Sideboard", (455.0, -735.0, 94.0), 180.0, (0.70, 0.72, 0.80)),
    ("Parter_Salon_Armchair_1", "SM_Fab_Lounge_Armchair", (335.0, -625.0, 94.0), 55.0, (0.90, 0.90, 0.90)),
    ("Parter_Salon_Armchair_2", "SM_Fab_Lounge_Armchair", (570.0, -625.0, 94.0), 125.0, (0.90, 0.90, 0.90)),
    ("Parter_Salon_Plant_NW", "SM_Fab_Indoor_Plant_Tree", (265.0, -745.0, 94.0), 25.0, (0.85, 0.85, 0.85)),
    ("Parter_Jadalnia_Shelving", "SM_Fab_Shelving_Decor", (795.0, -740.0, 94.0), 0.0, (0.58, 0.58, 0.72)),
    ("Parter_Jadalnia_Desk", "SM_Fab_Executive_Desk", (800.0, -545.0, 94.0), 180.0, (0.58, 0.58, 0.70)),
    ("Parter_Jadalnia_Chair", "SM_Fab_Executive_Chair", (865.0, -545.0, 94.0), 180.0, (0.80, 0.80, 0.80)),
    ("Parter_Jadalnia_Plant_SE", "SM_Fab_Indoor_Plant_Tree", (935.0, -445.0, 94.0), -45.0, (0.82, 0.82, 0.82)),

    # Poddasze: 2.3 Pokój NE / Gabinet (Z=402.0)
    ("Poddasze_Gabinet_Rug", "SM_Fab_Area_Rug", (740.0, -645.0, 402.2), 0.0, (0.66, 0.66, 1.0)),
    ("Poddasze_Gabinet_Sofa", "SM_Fab_Credenza_Sideboard", (565.0, -660.0, 402.0), -90.0, (0.60, 0.65, 0.76)),
    ("Poddasze_Gabinet_Desk", "SM_Fab_Executive_Desk", (805.0, -645.0, 402.0), 180.0, (0.58, 0.58, 0.70)),
    ("Poddasze_Gabinet_Chair", "SM_Fab_Executive_Chair", (870.0, -645.0, 402.0), 180.0, (0.78, 0.78, 0.78)),
    ("Poddasze_Gabinet_Armchair", "SM_Fab_Lounge_Armchair", (690.0, -565.0, 402.0), -35.0, (0.86, 0.86, 0.86)),
    ("Poddasze_Gabinet_Plant", "SM_Fab_Indoor_Plant_Tree", (930.0, -540.0, 402.0), 135.0, (0.76, 0.76, 0.76)),

    # Poddasze: 2.2 Pokój NW (Z=402.0)
    ("Poddasze_PokojNW_Desk", "SM_Fab_Executive_Desk", (185.0, -660.0, 402.0), 0.0, (0.58, 0.58, 0.68)),
    ("Poddasze_PokojNW_Chair", "SM_Fab_Executive_Chair", (120.0, -660.0, 402.0), 0.0, (0.78, 0.78, 0.78)),
    ("Poddasze_PokojNW_Armchair", "SM_Fab_Lounge_Armchair", (390.0, -705.0, 402.0), -135.0, (0.85, 0.85, 0.85)),

    # Poddasze: 2.4 Pokój SE (Z=402.0)
    ("Poddasze_PokojSE_Shelving", "SM_Fab_Shelving_Decor", (840.0, -140.0, 402.0), 180.0, (0.58, 0.58, 0.70)),
    ("Poddasze_PokojSE_Armchair", "SM_Fab_Lounge_Armchair", (890.0, -280.0, 402.0), 160.0, (0.85, 0.85, 0.85)),

    # Exterior Garden & Terrace Landscaping (visible through windows and on exterior shots)
    ("Terrace_Lounge_Chair_1", "SM_Fab_Lounge_Armchair", (550.0, -980.0, 92.0), -25.0, (0.95, 0.95, 0.95)),
    ("Terrace_Lounge_Chair_2", "SM_Fab_Lounge_Armchair", (720.0, -980.0, 92.0), -155.0, (0.95, 0.95, 0.95)),
    ("Garden_Tree_Back_1", "SM_Fab_Indoor_Plant_Tree", (220.0, -1180.0, 58.0), 15.0, (2.1, 2.1, 2.2)),
    ("Garden_Tree_Back_2", "SM_Fab_Indoor_Plant_Tree", (880.0, -1240.0, 58.0), 85.0, (2.3, 2.3, 2.4)),
    ("Garden_Tree_East_1", "SM_Fab_Indoor_Plant_Tree", (1280.0, -620.0, 58.0), -40.0, (2.2, 2.2, 2.3)),
    ("Garden_Tree_Front_1", "SM_Fab_Indoor_Plant_Tree", (1240.0, 320.0, 58.0), 45.0, (1.9, 1.9, 2.0)),
    ("Garden_Tree_Front_2", "SM_Fab_Indoor_Plant_Tree", (-180.0, 280.0, 58.0), 110.0, (2.0, 2.0, 2.1)),
]

for label_sfx, mesh_key, loc, yaw, scale in placements:
    sm = loaded_pieces.get(mesh_key)
    if not sm:
        continue
    act = actor_sub.spawn_actor_from_object(sm, unreal.Vector(*loc), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if act:
        act.set_actor_scale3d(unreal.Vector(*scale))
        act.set_actor_label(f"PDF2BIM_Furn_{label_sfx}")
        act.set_folder_path("PDF2BIM/Dom1_Furniture")

# 5. Spawn soft area interior lights (large source_radius so there are no harsh point hotspots)
int_lights = [
    ("Salon_West", (420.0, -620.0, 295.0), 8.5, 55.0, (1.0, 0.95, 0.88)),
    ("Jadalnia_East", (800.0, -600.0, 295.0), 8.5, 55.0, (1.0, 0.95, 0.88)),
    ("WindowPortal_North", (510.0, -780.0, 210.0), 6.5, 85.0, (0.94, 0.97, 1.0)),
    ("WindowPortal_East", (960.0, -560.0, 210.0), 6.5, 85.0, (0.94, 0.97, 1.0)),
    ("Parter_Hol", (520.0, -320.0, 295.0), 7.5, 45.0, (1.0, 0.95, 0.88)),
    ("Poddasze_Hol", (520.0, -455.0, 585.0), 8.5, 50.0, (1.0, 0.95, 0.88)),
    ("Poddasze_Gabinet_NE", (750.0, -630.0, 565.0), 9.5, 55.0, (1.0, 0.95, 0.88)),
    ("Poddasze_Pokoj_NW", (260.0, -640.0, 565.0), 8.5, 50.0, (1.0, 0.95, 0.88)),
    ("Poddasze_Pokoj_SE", (830.0, -260.0, 565.0), 8.5, 50.0, (1.0, 0.95, 0.88)),
]
for l_name, l_pos, l_int, l_rad, l_col in int_lights:
    pl = actor_sub.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*l_pos), unreal.Rotator(0, 0, 0))
    pl.set_actor_label(f"PDF2BIM_IntLight_{l_name}")
    pl.set_folder_path("PDF2BIM/Lighting")
    plc = pl.point_light_component
    plc.set_mobility(unreal.ComponentMobility.MOVABLE)
    plc.set_intensity(l_int)
    plc.set_attenuation_radius(950.0)
    plc.set_editor_property("source_radius", l_rad)
    plc.set_editor_property("soft_source_radius", l_rad * 1.3)
    plc.set_editor_property("contact_shadow_length", 0.04)
    plc.set_light_color(unreal.LinearColor(l_col[0], l_col[1], l_col[2], 1.0))

# 6. Capture 4 interior verification screenshots with full Lumen GI + Reflections + SSAO
out_dir = "C:/Users/filip/pdf2bim_remote"

def capture_interior(cam_loc, target_loc, fov, filename):
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
    cpps.set_editor_property("bloom_intensity", 0.42)
    cpps.set_editor_property("override_vignette_intensity", True)
    cpps.set_editor_property("vignette_intensity", 0.30)
    cpps.set_editor_property("override_auto_exposure_min_brightness", True)
    cpps.set_editor_property("auto_exposure_min_brightness", 1.0)
    cpps.set_editor_property("override_auto_exposure_max_brightness", True)
    cpps.set_editor_property("auto_exposure_max_brightness", 1.0)

    for _ in range(8):
        comp.capture_scene()

    unreal.RenderingLibrary.export_render_target(world, rt, out_dir, filename)
    actor_sub.destroy_actor(cap_actor)
    print("INT_CAPTURED_OK", f"{out_dir}/{filename}")

# Shot 1: Upstairs Hall (West end of Hol x=0.95, y=4.60 -> X_ue=95, Y_ue=-460, Z_ue=555) looking East along hallway & stairwell
capture_interior(
    unreal.Vector(95.0, -460.0, 555.0),
    unreal.Vector(680.0, -410.0, 520.0),
    75.0,
    "ue5_int1_poddasze_hol.png",
)

# Shot 2: Upstairs Furnished Room 2.3 Pokój NE / Gabinet (from SW door corner looking NE at Fab desk, chair, rug, credenza, armchair, plant & sloped ceiling)
capture_interior(
    unreal.Vector(575.0, -540.0, 555.0),
    unreal.Vector(825.0, -675.0, 480.0),
    78.0,
    "ue5_int2_poddasze_rooms.png",
)

# Shot 3: Ground Floor Furnished Salon + Jadalnia (looking across living room armchairs/rug/credenza & study/dining zone)
capture_interior(
    unreal.Vector(255.0, -535.0, 247.0),
    unreal.Vector(720.0, -650.0, 185.0),
    78.0,
    "ue5_int3_parter_salon.png",
)

# Shot 4: Ground Floor Hall & Stairs (looking North-West at Stairs & under-stair wall)
capture_interior(
    unreal.Vector(540.0, -220.0, 247.0),
    unreal.Vector(220.0, -380.0, 240.0),
    75.0,
    "ue5_int4_parter_schody.png",
)
"""


def main() -> int:
    p = Path("C:/Users/filip/pdf2bim_remote/ue_inspect_interior.py")
    p.write_text(INSPECT_SCRIPT, encoding="utf-8")

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
        print("[INSPECT_RESULT]", res)
        return 0 if res.get("success") else 1
    finally:
        node.stop()


if __name__ == "__main__":
    sys.exit(main())

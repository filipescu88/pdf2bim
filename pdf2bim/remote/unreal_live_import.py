"""Live Unreal Engine 5.8 Remote Execution importer and level spawner for Dom 1 (Dom w gnieźnikach).

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

# 1. Remove any previous PDF2BIM actors from the level
for act in actor_sub.get_all_level_actors():
    lbl = act.get_actor_label()
    if lbl.startswith("PDF2BIM_"):
        actor_sub.destroy_actor(act)

# 2. Clean up /Game/PDF2BIM/Dom2_Amor and re-import clean Dom1_Gniezniki
if unreal.EditorAssetLibrary.does_directory_exist("/Game/PDF2BIM/Dom2_Amor"):
    unreal.EditorAssetLibrary.delete_directory("/Game/PDF2BIM/Dom2_Amor")
if unreal.EditorAssetLibrary.does_directory_exist("/Game/PDF2BIM/Dom1_Gniezniki"):
    unreal.EditorAssetLibrary.delete_directory("/Game/PDF2BIM/Dom1_Gniezniki")

fbx_path = "C:/Users/filip/Desktop/pdf2bim_unreal/dom_w_gnieznikach/dom_w_gnieznikach_unreal.fbx"
dest_path = "/Game/PDF2BIM/Dom1_Gniezniki"
base_loc = unreal.Vector(0.0, 0.0, 92.0)

task = unreal.AssetImportTask()
task.filename = fbx_path
task.destination_path = dest_path
task.automated = True
task.replace_existing = True
task.replace_existing_settings = True
task.save = False
asset_tools.import_asset_tasks([task])

# 3. Configure M_WindowGlass as translucent architectural glass (Opacity=0.22)
assets = asset_reg.get_assets_by_path(dest_path, recursive=True)
for a_data in assets:
    cls_name = str(a_data.asset_class_path.asset_name)
    a_name = str(a_data.asset_name)
    if cls_name == "Material" and "WindowGlass" in a_name:
        mat = a_data.get_asset()
        if mat:
            mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
            mat.set_editor_property("two_sided", True)
            op_node = unreal.MaterialEditingLibrary.create_material_expression(
                mat, unreal.MaterialExpressionConstant, -250, 200
            )
            if op_node:
                op_node.set_editor_property("r", 0.22)
                unreal.MaterialEditingLibrary.connect_material_property(
                    op_node, "", unreal.MaterialProperty.MP_OPACITY
                )
            unreal.MaterialEditingLibrary.recompile_material(mat)

# 4. Spawn all StaticMesh actors of Dom 1 (excluding any neighbor/parcel if present)
sm_count = 0
win_count = 0
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
                if "win_" in mname.lower() or "rw_" in mname.lower() or "window" in mname.lower():
                    win_count += 1

editor_sub.set_level_viewport_camera_info(
    unreal.Vector(-550.0, -880.0, 520.0),
    unreal.Rotator(0.0, -18.0, 42.0),
)
print(f"SPAWN_DOM1_OK total_actors={sm_count} window_actors={win_count}")
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

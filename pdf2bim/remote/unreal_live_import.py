"""Live Unreal Engine 5.8 Remote Execution importer and level spawner.

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

# 1. Clean up any previously spawned PDF2BIM actors
for act in actor_sub.get_all_level_actors():
    lbl = act.get_actor_label()
    if lbl.startswith("PDF2BIM_"):
        actor_sub.destroy_actor(act)

houses = [
    (
        "Dom1",
        "C:/Users/filip/Desktop/pdf2bim_unreal/dom_w_gnieznikach/dom_w_gnieznikach_unreal.fbx",
        "/Game/PDF2BIM/Dom1_Gniezniki",
        unreal.Vector(0.0, 0.0, 92.0),
        "PDF2BIM/Dom1_Gniezniki",
    ),
    (
        "Dom2",
        "C:/Users/filip/Desktop/pdf2bim_unreal/amor_woe1092/amor_woe1092_unreal.fbx",
        "/Game/PDF2BIM/Dom2_Amor",
        unreal.Vector(1800.0, 0.0, 92.0),
        "PDF2BIM/Dom2_Amor",
    ),
]

total_spawned = 0
for prefix, fbx_path, dest_path, base_loc, folder_name in houses:
    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = dest_path
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.save = False
    asset_tools.import_asset_tasks([task])

    assets = asset_reg.get_assets_by_path(dest_path, recursive=True)
    sm_count = 0
    for a_data in assets:
        if str(a_data.asset_class_path.asset_name) == "StaticMesh":
            mesh_obj = a_data.get_asset()
            if mesh_obj:
                act = actor_sub.spawn_actor_from_object(mesh_obj, base_loc, unreal.Rotator(0.0, 0.0, 0.0))
                if act:
                    act.set_actor_label(f"PDF2BIM_{prefix}_{mesh_obj.get_name()}")
                    act.set_folder_path(folder_name)
                    sm_count += 1
                    total_spawned += 1
    unreal.log(f"[PDF2BIM] Imported {prefix} into {dest_path}: spawned {sm_count} StaticMesh actors at {base_loc}")

# 2. Aim the active Unreal Editor viewport camera right at both houses
editor_sub.set_level_viewport_camera_info(
    unreal.Vector(-950.0, -1650.0, 920.0),
    unreal.Rotator(0.0, -20.0, 48.0),
)
print(f"SPAWN_OK total_spawned={total_spawned}")
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

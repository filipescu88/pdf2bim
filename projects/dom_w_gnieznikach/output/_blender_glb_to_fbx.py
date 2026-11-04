"""Blender 5.1 headless converter: .glb -> .fbx for Unreal Engine 5 / Twinmotion."""
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    raise RuntimeError("Usage: blender --background --python-exit-code 1 --python glb_to_fbx.py -- <in.glb> <out.fbx>")

in_glb, out_fbx = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=in_glb)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.export_scene.fbx(
    filepath=out_fbx,
    use_selection=False,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_NONE",
    axis_forward="-Y",
    axis_up="Z",
    mesh_smooth_type="FACE",
    path_mode="COPY",
    embed_textures=True,
)
print(f"[OK] Exported FBX: {out_fbx}")

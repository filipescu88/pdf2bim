"""Blender 5.1 script: split Fab `office_props.glb` into 7 clean, centered furniture StaticMeshes (without studio backdrop Plane)."""

import bpy

FAB_GLB = "C:/Users/filip/AppData/Local/Temp/FabLibrary/97ecf3ef-3223-44c4-9d95-74b63dd8605d/office_props.glb"
OUT_FBX = "C:/Users/filip/pdf2bim_remote/fab_furniture_pieces.fbx"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=FAB_GLB)

# Clear parents, make multi-user meshes single-user, and bake all transforms into vertices
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
for obj in list(bpy.data.objects):
    if obj.type != "MESH":
        bpy.data.objects.remove(obj, do_unlink=True)
    elif obj.data.users > 1:
        obj.data = obj.data.copy()

bpy.ops.object.select_all(action="SELECT")
bpy.context.view_layer.objects.active = bpy.data.objects[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

GROUPS = {
    "SM_Fab_Executive_Desk": ["Table", "WQ54438", "keys", "lamp01", "Cup tea01", "board001", "board002", "P1", "P2", "Fax mach001"],
    "SM_Fab_Executive_Chair": ["WQ54104"],
    "SM_Fab_Shelving_Decor": [
        "Table.001", "WQ54132", "WQ54134", "WQ54137", "WQ54153", "WQ54154", "WQ54157", "WQ54159",
        "WQ54163", "WQ54165", "WQ54166", "WQ54167", "WQ54168", "WQ54169", "WQ54176", "WQ54178",
        "WQ54179", "WQ54192", "WQ54196", "WQ54197", "WQ54202", "WQ54204", "WQ54225", "WQ54228",
        "WQ54232", "WQ54236", "WQ54241", "WQ54243", "WQ54306", "WQ54307", "WQ54308",
    ],
    "SM_Fab_Credenza_Sideboard": ["WQ54314"],
    "SM_Fab_Lounge_Armchair": ["WQ54347"],
    "SM_Fab_Indoor_Plant_Tree": ["WQ54415"],
    "SM_Fab_Area_Rug": ["carpet"],
}

keep_objs = []
for new_name, member_names in GROUPS.items():
    bpy.ops.object.select_all(action="DESELECT")
    members = [bpy.data.objects.get(m) for m in member_names if bpy.data.objects.get(m) is not None]
    if not members:
        continue
    for m in members:
        m.select_set(True)
    bpy.context.view_layer.objects.active = members[0]
    if len(members) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = new_name
    joined.data.name = new_name

    # Recenter X/Y to (0,0) and bottom Z to 0.0
    verts = joined.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    z_min = min(zs)
    for v in verts:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z_min
    joined.data.update()
    joined.location = (0.0, 0.0, 0.0)
    keep_objs.append(joined)
    print(f"BUILT_FAB_PIECE {new_name} dims=({max(xs)-min(xs):.2f}, {max(ys)-min(ys):.2f}, {max(zs)-min(zs):.2f})")

# Delete all remaining objects (Plane, Plane.001, etc.)
for obj in list(bpy.data.objects):
    if obj not in keep_objs:
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.export_scene.fbx(
    filepath=OUT_FBX,
    use_selection=False,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_NONE",
    axis_forward="-Y",
    axis_up="Z",
    mesh_smooth_type="FACE",
)
print(f"[OK] Exported 7 Fab furniture pieces -> {OUT_FBX}")

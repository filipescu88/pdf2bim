"""Blender 5.1 headless converter: .glb -> .fbx with metric Box UVs and PBR textures for Unreal Engine 5."""
import os
import sys
import bpy
import bmesh

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    raise RuntimeError("Usage: blender --background --python-exit-code 1 --python glb_to_fbx.py -- <in.glb> <out.fbx>")

in_glb, out_fbx = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=in_glb)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 1. Add Garden Lawn & Paved Entrance Walkway around the house
def add_env_box(name, x0, y0, x1, y1, z0, z1, mat_name, color_rgb):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    v0 = bm.verts.new((x0, y0, z0))
    v1 = bm.verts.new((x1, y0, z0))
    v2 = bm.verts.new((x1, y1, z0))
    v3 = bm.verts.new((x0, y1, z0))
    v4 = bm.verts.new((x0, y0, z1))
    v5 = bm.verts.new((x1, y0, z1))
    v6 = bm.verts.new((x1, y1, z1))
    v7 = bm.verts.new((x0, y1, z1))
    for f in [(v3, v2, v1, v0), (v4, v5, v6, v7), (v0, v1, v5, v4), (v1, v2, v6, v5), (v2, v3, v7, v6), (v3, v0, v4, v7)]:
        bm.faces.new(f)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color_rgb, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.85
    obj.data.materials.append(mat)

add_env_box("SM_Garden_Lawn", -14.0, -12.0, 24.0, 22.0, -0.38, -0.25, "M_ParcelGrass", (0.28, 0.45, 0.22))
add_env_box("SM_Entrance_Walkway", 0.45, -7.5, 2.25, -0.60, -0.245, -0.21, "M_WalkwayPavers", (0.58, 0.57, 0.55))
add_env_box("SM_Entrance_Step_1", 0.00, -0.60, 2.48, -0.30, -0.36, -0.14, "M_Terrace_Paver_Grey", (0.55, 0.56, 0.58))
add_env_box("SM_Entrance_Step_2", 0.00, -0.30, 2.48, 0.00, -0.36, -0.02, "M_Terrace_Paver_Grey", (0.55, 0.56, 0.58))

# 2. Clear glTF smoothed custom normals, split sharp edges, and generate world-space metric Box UVs
for obj in bpy.data.objects:
    if obj.type != "MESH" or not obj.data.polygons:
        continue
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except Exception:
        pass
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.split_edges(bm, edges=list(bm.edges))
    bm.normal_update()
    uv_layer = bm.loops.layers.uv.verify()
    oname = obj.name.lower()
    scale = 0.75 if ("dach_" in oname or "roof" in oname) else (0.60 if "wood" in oname else 0.45)
    for face in bm.faces:
        face.smooth = False
        n = face.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in face.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                loop[uv_layer].uv = (co.x * scale, co.y * scale)
            elif ax >= ay:
                loop[uv_layer].uv = (co.y * scale, co.z * scale)
            else:
                loop[uv_layer].uv = (co.x * scale, co.z * scale)
    bm.to_mesh(me)
    bm.free()

# 3. Bind PBR textures from C:/Users/filip/pdf2bim_remote/textures if available
tex_dir = "C:/Users/filip/pdf2bim_remote/textures"
tex_bindings = {
    "M_Wall_Plaster_White": ("painted_plaster_wall_diffuse.jpg", "painted_plaster_wall_nor_gl.jpg", "painted_plaster_wall_rough.jpg"),
    "M_Roof_Tile_Anthracite": ("anthracite_roof_diffuse.jpg", "grey_roof_tiles_02_nor_gl.jpg", "grey_roof_tiles_02_rough.jpg"),
    "M_Facade_Cladding_Oak": ("wood_floor_deck_diffuse.jpg", "wood_floor_deck_nor_gl.jpg", "wood_floor_deck_rough.jpg"),
    "M_Door_Veneer_Oak": ("laminate_floor_02_diffuse.jpg", None, None),
    "M_Floor_Parquet_Oak": ("laminate_floor_02_diffuse.jpg", None, None),
    "M_Floor_Tile_Gres": ("concrete_tiles_diffuse.jpg", "concrete_tiles_nor_gl.jpg", "concrete_tiles_rough.jpg"),
    "M_Structure_Concrete": ("concrete_tiles_diffuse.jpg", "concrete_tiles_nor_gl.jpg", "concrete_tiles_rough.jpg"),
    "M_Terrace_Paver_Grey": ("concrete_tiles_diffuse.jpg", "concrete_tiles_nor_gl.jpg", "concrete_tiles_rough.jpg"),
    "M_WalkwayPavers": ("concrete_pavers_02_diffuse.jpg", None, None),
    "M_ParcelGrass": ("lawn_grass_diffuse.jpg", "leafy_grass_nor_gl.jpg", None),
}

for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    key = next((k for k in tex_bindings if mat.name.startswith(k)), None)
    if not key:
        continue
    diff_f, norm_f, rough_f = tex_bindings[key]
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if not bsdf:
        continue
    if diff_f and os.path.isfile(f"{tex_dir}/{diff_f}"):
        tnode = nt.nodes.new("ShaderNodeTexImage")
        tnode.image = bpy.data.images.load(f"{tex_dir}/{diff_f}")
        nt.links.new(tnode.outputs["Color"], bsdf.inputs["Base Color"])
    if rough_f and os.path.isfile(f"{tex_dir}/{rough_f}"):
        rnode = nt.nodes.new("ShaderNodeTexImage")
        rnode.image = bpy.data.images.load(f"{tex_dir}/{rough_f}")
        rnode.image.colorspace_settings.name = "Non-Color"
        nt.links.new(rnode.outputs["Color"], bsdf.inputs["Roughness"])
    if norm_f and os.path.isfile(f"{tex_dir}/{norm_f}"):
        nimg = nt.nodes.new("ShaderNodeTexImage")
        nimg.image = bpy.data.images.load(f"{tex_dir}/{norm_f}")
        nimg.image.colorspace_settings.name = "Non-Color"
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nimg.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

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

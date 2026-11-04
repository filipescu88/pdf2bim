"""Unreal Engine 5 & Twinmotion Exporter (.usda ASCII OpenUSD, merged SM_/M_ GLB, and remote .fbx) (Step 5).

Features:
1. Strict `SM_` static mesh and `M_` material naming convention.
2. Static wall segment merging by `(level_id, wall_type, material_id)` to minimize draw calls while keeping
   interactive `SM_DoorLeaf_*` (with local origin shifted to hinge pivot!) and `SM_Floor_*` separate.
3. Unconditional preservation of `SM_MEP_*` (`mep_sockets`) when `include_furniture=False`.
4. Pure-Python ASCII OpenUSD (`.usda`) writer with `UsdPreviewSurface` materials and `customData` BIM attributes.
5. Remote GPU `.glb -> .fbx` converter script generator integrated with `run_remote_blender_job`.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh

from pdf2bim.geometry.builder import CompiledScene3D
from pdf2bim.geometry.mesh_utils import CompiledMeshNode
from pdf2bim.remote.gpu_runner import RemoteGPUConfig, RemoteJobResult, run_remote_blender_job
from pdf2bim.schema import SceneGraphV2


def build_unreal_optimized_scene(sg: SceneGraphV2, scene3d: CompiledScene3D) -> CompiledScene3D:
    """Optimize a CompiledScene3D for Unreal Engine / Twinmotion:
    - Merges static wall segments by `(level_id, wall_type, material_id)` into `SM_WallMerged_*`.
    - Shifts door leaf vertices into local hinge-pivot space `(hx, hy, sill_z)` for direct UE rotation.
    - Preserves all `mep_socket` nodes even when `sg.include_furniture` is False.
    """
    wall_groups: dict[tuple[str, str, str], list[CompiledMeshNode]] = defaultdict(list)
    other_nodes: list[CompiledMeshNode] = []

    for node in scene3d.nodes:
        if not sg.include_furniture and node.category == "furniture":
            continue
        if node.category in ("neighbor_building", "parcel_ground"):
            continue
        if node.category in ("wall_segment", "wall_exterior_cladding"):
            w_type = str(node.extras.get("wall_type", "wall"))
            key = (node.level_id, w_type, node.material_id)
            wall_groups[key].append(node)
        elif node.category == "door_leaf":
            # Shift mesh vertices so local origin (0, 0, 0) is at the hinge pivot (hx, hy, sill_z)
            hinge_xy = node.extras.get("hinge_xy", [0.0, 0.0])
            hx, hy = float(hinge_xy[0]), float(hinge_xy[1])
            zb = float(np.min(node.mesh.vertices[:, 2]))
            shifted_mesh = node.mesh.copy()
            shifted_mesh.vertices = shifted_mesh.vertices - np.array([[hx, hy, zb]], dtype=np.float64)
            new_extras = dict(node.extras)
            new_extras["world_pivot_xyz"] = [hx, hy, round(zb, 4)]
            other_nodes.append(
                CompiledMeshNode(
                    node_id=node.node_id,
                    element_id=node.element_id,
                    category=node.category,
                    level_id=node.level_id,
                    material_id=node.material_id,
                    ue_mesh_name=node.ue_mesh_name,
                    ue_material_name=node.ue_material_name,
                    mesh=shifted_mesh,
                    collidable=node.collidable,
                    base_quad_xy=node.base_quad_xy,
                    extras=new_extras,
                )
            )
        else:
            other_nodes.append(node)

    merged_nodes: list[CompiledMeshNode] = []
    for (level_id, w_type, mat_id), group in sorted(wall_groups.items()):
        combined_mesh = trimesh.util.concatenate([g.mesh for g in group])
        ue_mat = group[0].ue_material_name
        merged_name = f"SM_WallMerged_{level_id}_{w_type}_{mat_id}"
        merged_nodes.append(
            CompiledMeshNode(
                node_id=merged_name,
                element_id=f"merged_{level_id}_{w_type}_{mat_id}",
                category="wall_merged",
                level_id=level_id,
                material_id=mat_id,
                ue_mesh_name=merged_name,
                ue_material_name=ue_mat,
                mesh=combined_mesh,
                collidable=True,
                extras={
                    "element_id": f"merged_{level_id}_{w_type}_{mat_id}",
                    "source_wall_ids": sorted({g.element_id for g in group}),
                    "category": "wall_merged",
                    "level_id": level_id,
                    "world_pivot_xyz": [0.0, 0.0, 0.0],
                },
            )
        )

    return CompiledScene3D(project_slug=sg.project_slug, nodes=merged_nodes + other_nodes)


def _sanitize_usd_ident(name: str) -> str:
    clean = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
    if clean and clean[0].isdigit():
        clean = "_" + clean
    return clean or "Node"


def export_scene_to_usda(
    sg: SceneGraphV2,
    scene3d: CompiledScene3D,
    out_usda_path: Path,
) -> Path:
    """Export an Unreal/Twinmotion-optimized scene to ASCII OpenUSD (`.usda`) with BIM metadata."""
    out_usda_path = Path(out_usda_path).resolve()
    out_usda_path.parent.mkdir(parents=True, exist_ok=True)

    ue_scene = build_unreal_optimized_scene(sg, scene3d)
    root_name = _sanitize_usd_ident(f"BIM_{sg.project_slug}")

    lines: list[str] = [
        "#usda 1.0",
        "(",
        f'    defaultPrim = "{root_name}"',
        "    metersPerUnit = 1.0",
        '    upAxis = "Z"',
        ")",
        "",
        f'def Xform "{root_name}"',
        "{",
        '    def Scope "Materials"',
        "    {",
    ]

    # 1. Write UsdPreviewSurface materials (M_*)
    for mat_id, mat in sorted(sg.materials.items()):
        m_name = _sanitize_usd_ident(mat.ue_name)
        r, g, b = mat.base_color_rgb
        lines.extend(
            [
                f'        def Material "{m_name}"',
                "        {",
                f'            token outputs:surface.connect = </{root_name}/Materials/{m_name}/PBRShader.outputs:surface>',
                '            def Shader "PBRShader"',
                "            {",
                '                uniform token info:id = "UsdPreviewSurface"',
                f"                color3f inputs:diffuseColor = ({r:.4f}, {g:.4f}, {b:.4f})",
                f"                float inputs:metallic = {mat.metallic:.4f}",
                f"                float inputs:roughness = {mat.roughness:.4f}",
                f"                float inputs:opacity = {mat.opacity:.4f}",
                "                token outputs:surface",
                "            }",
                "        }",
            ]
        )

    lines.append("    }")
    lines.append("")
    lines.append('    def Scope "Geometry"')
    lines.append("    {")

    # 2. Write SM_* meshes with BIM customData and local pivot transforms
    used_names: set[str] = set()
    for idx, node in enumerate(ue_scene.nodes):
        prim_name = _sanitize_usd_ident(node.ue_mesh_name)
        if prim_name in used_names:
            prim_name = f"{prim_name}_{idx}"
        used_names.add(prim_name)

        mat_spec = sg.materials.get(node.material_id)
        ue_mat_name = _sanitize_usd_ident(mat_spec.ue_name if mat_spec else node.ue_material_name)
        pivot = node.extras.get("world_pivot_xyz", [0.0, 0.0, 0.0])
        px, py, pz = float(pivot[0]), float(pivot[1]), float(pivot[2])

        verts = node.mesh.vertices
        faces = node.mesh.faces
        pts_str = ", ".join(f"({v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f})" for v in verts)
        counts_str = ", ".join("3" for _ in range(len(faces)))
        indices_str = ", ".join(f"{f[0]}, {f[1]}, {f[2]}" for f in faces)

        lines.extend(
            [
                f'        def Mesh "{prim_name}" (',
                "            prepend apiSchemas = [\"MaterialBindingAPI\"]",
                "            customData = {",
                f'                string bim_element_id = "{node.element_id}"',
                f'                string bim_category = "{node.category}"',
                f'                string bim_level_id = "{node.level_id}"',
                "            }",
                "        )",
                "        {",
                f"            double3 xformOp:translate = ({px:.4f}, {py:.4f}, {pz:.4f})",
                '            uniform token[] xformOpOrder = ["xformOp:translate"]',
                f"            int[] faceVertexCounts = [{counts_str}]",
                f"            int[] faceVertexIndices = [{indices_str}]",
                f"            point3f[] points = [{pts_str}]",
                f"            rel material:binding = </{root_name}/Materials/{ue_mat_name}>",
                "        }",
            ]
        )

    lines.append("    }")
    lines.append("}")
    out_usda_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_usda_path


def write_blender_glb_to_fbx_script(script_path: Path) -> Path:
    """Write a standalone Blender Python script that converts a `.glb` file to `.fbx` for Unreal Engine."""
    script_path = Path(script_path).resolve()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    code = '''"""Blender 5.1 headless converter: .glb -> .fbx with metric Box UVs and PBR textures for Unreal Engine 5."""
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
'''
    script_path.write_text(code, encoding="utf-8")
    return script_path


def export_scene_to_remote_fbx(
    local_glb_path: Path,
    local_out_fbx_path: Path,
    cfg: RemoteGPUConfig | None = None,
    runner_fn=None,
) -> RemoteJobResult:
    """Convert local `.glb` to `.fbx` on the remote Windows GPU workstation and download `.fbx` back to Linux."""
    local_glb_path = Path(local_glb_path).resolve()
    local_out_fbx_path = Path(local_out_fbx_path).resolve()
    script_path = local_out_fbx_path.parent / "_blender_glb_to_fbx.py"
    write_blender_glb_to_fbx_script(script_path)

    if cfg is None:
        cfg = RemoteGPUConfig()
    remote_in = f"{cfg.remote_workdir}/{local_glb_path.name}"
    remote_out_name = local_out_fbx_path.name
    remote_out = f"{cfg.remote_workdir}/{remote_out_name}"

    kwargs = {}
    if runner_fn is not None:
        kwargs["runner_fn"] = runner_fn

    return run_remote_blender_job(
        job_name=f"fbx_export_{local_glb_path.stem}",
        local_script=script_path,
        local_inputs=[local_glb_path],
        expected_outputs=[(remote_out_name, local_out_fbx_path)],
        script_args=[remote_in, remote_out],
        cfg=cfg,
        **kwargs,
    )

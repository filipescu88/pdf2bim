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
    code = '''"""Blender 5.1 headless converter: .glb -> .fbx for Unreal Engine 5 / Twinmotion."""
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    raise RuntimeError("Usage: blender --background --python-exit-code 1 --python glb_to_fbx.py -- <in.glb> <out.fbx>")

in_glb, out_fbx = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=in_glb)
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

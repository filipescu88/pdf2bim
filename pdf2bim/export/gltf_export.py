"""Binary glTF 2.0 (.glb) exporter with embedded BIM & WebXR node `extras` (Step 2)."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

from pdf2bim.geometry.builder import CompiledScene3D
from pdf2bim.schema import SceneGraphV2


def _inject_node_extras_into_glb(glb_bytes: bytes, extras_by_node_name: dict[str, dict[str, Any]]) -> bytes:
    """Inject per-node `extras` dictionary into the JSON chunk of a binary glTF 2.0 (.glb) file."""
    if len(glb_bytes) < 20 or glb_bytes[:4] != b"glTF":
        return glb_bytes

    _, version, _ = struct.unpack("<4sII", glb_bytes[:12])
    if version != 2:
        return glb_bytes

    json_chunk_len, json_chunk_type = struct.unpack("<II", glb_bytes[12:20])
    if json_chunk_type != 0x4E4F534A:  # 'JSON'
        return glb_bytes

    json_bytes = glb_bytes[20 : 20 + json_chunk_len]
    bin_rest = glb_bytes[20 + json_chunk_len :]

    gltf_dict = json.loads(json_bytes.decode("utf-8"))
    for node in gltf_dict.get("nodes", []):
        name = node.get("name", "")
        if name in extras_by_node_name:
            node["extras"] = extras_by_node_name[name]

    new_json_raw = json.dumps(gltf_dict, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    # Pad JSON chunk to 4-byte boundary with spaces (0x20) per glTF 2.0 spec
    pad_len = (4 - (len(new_json_raw) % 4)) % 4
    new_json_padded = new_json_raw + (b" " * pad_len)

    total_len = 20 + len(new_json_padded) + len(bin_rest)
    header = struct.pack("<4sII", b"glTF", 2, total_len)
    json_header = struct.pack("<II", len(new_json_padded), 0x4E4F534A)
    return header + json_header + new_json_padded + bin_rest


def export_scene_to_glb(
    sg: SceneGraphV2,
    scene3d: CompiledScene3D,
    out_glb_path: Path,
) -> Path:
    """Export CompiledScene3D to a binary glTF 2.0 (.glb) file with PBR materials and node `extras`."""
    out_glb_path = Path(out_glb_path).resolve()
    out_glb_path.parent.mkdir(parents=True, exist_ok=True)

    tm_scene = trimesh.Scene()
    extras_by_node: dict[str, dict[str, Any]] = {}

    for node in scene3d.nodes:
        mesh = node.mesh.copy()
        # Convert BIM Z-up (x, y, z) to glTF 2.0 Y-up (x, z, -y); det=+1 preserves face winding
        v = mesh.vertices
        mesh.vertices = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])
        mat_spec = sg.materials.get(node.material_id)
        if mat_spec is not None:
            r, g, b = mat_spec.base_color_rgb
            alpha = mat_spec.opacity
            rgba = [int(round(r * 255)), int(round(g * 255)), int(round(b * 255)), int(round(alpha * 255))]
            pbr = PBRMaterial(
                name=node.ue_material_name,
                baseColorFactor=rgba,
                roughnessFactor=float(mat_spec.roughness),
                metallicFactor=float(mat_spec.metallic),
                alphaMode="BLEND" if alpha < 0.99 else "OPAQUE",
            )
            mesh.visual = TextureVisuals(material=pbr)
        else:
            mesh.visual.face_colors = np.array([210, 210, 210, 255], dtype=np.uint8)

        node_extras = dict(node.extras)
        node_extras.setdefault("material_id", node.material_id)
        node_extras.setdefault("ue_material_name", node.ue_material_name)
        node_extras.setdefault("level_id", node.level_id)

        pivot = node_extras.get("world_pivot_xyz", [0.0, 0.0, 0.0])
        px, py, pz = float(pivot[0]), float(pivot[1]), float(pivot[2])
        xform = trimesh.transformations.translation_matrix([px, pz, -py])
        tm_scene.add_geometry(
            mesh,
            node_name=node.node_id,
            geom_name=node.ue_mesh_name,
            transform=xform,
            metadata=node_extras,
        )
        extras_by_node[node.node_id] = node_extras

    raw_glb = tm_scene.export(file_type="glb")
    if isinstance(raw_glb, str):
        raw_glb = raw_glb.encode("latin1")
    final_glb = _inject_node_extras_into_glb(raw_glb, extras_by_node)
    out_glb_path.write_bytes(final_glb)
    return out_glb_path


def read_glb_json_chunk(glb_path: Path) -> dict[str, Any]:
    """Read and parse the JSON chunk of a .glb file for testing and WebXR inspection."""
    data = Path(glb_path).read_bytes()
    json_len, _ = struct.unpack("<II", data[12:20])
    return json.loads(data[20 : 20 + json_len].decode("utf-8"))

"""Tests for Step 5: Unreal Engine 5 / Twinmotion export (.usda OpenUSD, SM_/M_ conventions, MEP sockets, E2E build)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from pdf2bim.export import (
    build_unreal_optimized_scene,
    export_scene_to_remote_fbx,
    export_scene_to_usda,
    write_blender_glb_to_fbx_script,
)
from pdf2bim.geometry import compile_scene_graph_3d
from pdf2bim.schema import SceneGraphV2

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_BIN = REPO_ROOT / ".venv" / "bin" / "pdf2bim"


def test_unreal_scene_optimization_and_mep_preservation() -> None:
    for slug in ("dom_w_gnieznikach", "amor_woe1092"):
        sg_path = REPO_ROOT / "projects" / slug / "scene_graph.json"
        sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))
        assert sg.include_furniture is False

        raw_scene = compile_scene_graph_3d(sg)
        ue_scene = build_unreal_optimized_scene(sg, raw_scene)

        # Static wall segments should be merged into fewer draw calls
        assert len(ue_scene.nodes) < len(raw_scene.nodes)

        # Every node must follow SM_ naming and M_ material naming
        for node in ue_scene.nodes:
            assert node.ue_mesh_name.startswith("SM_"), f"Invalid UE mesh name: {node.ue_mesh_name}"
            assert node.ue_material_name.startswith("M_"), f"Invalid UE material name: {node.ue_material_name}"

        # Door leaves must have local vertices shifted to hinge pivot (min XY distance to (0,0) <= 5cm)
        door_nodes = ue_scene.by_category("door_leaf")
        assert len(door_nodes) == len(sg.openings.doors)
        for dn in door_nodes:
            xy_dists = np.hypot(dn.mesh.vertices[:, 0], dn.mesh.vertices[:, 1])
            assert float(np.min(xy_dists)) <= 0.06
            assert "world_pivot_xyz" in dn.extras

        # MEP sockets must be preserved even when include_furniture is False
        mep_nodes = ue_scene.by_category("mep_socket")
        assert len(mep_nodes) == len(sg.mep_sockets)


def test_export_openusd_usda_both_houses(tmp_path: Path) -> None:
    for slug in ("dom_w_gnieznikach", "amor_woe1092"):
        sg_path = REPO_ROOT / "projects" / slug / "scene_graph.json"
        sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))
        scene3d = compile_scene_graph_3d(sg)

        out_usda = export_scene_to_usda(sg, scene3d, tmp_path / f"{slug}_unreal.usda")
        assert out_usda.is_file() and out_usda.stat().st_size > 20_000
        text = out_usda.read_text(encoding="utf-8")

        assert text.startswith("#usda 1.0")
        assert 'upAxis = "Z"' in text
        assert "metersPerUnit = 1.0" in text
        assert 'uniform token info:id = "UsdPreviewSurface"' in text
        assert 'def Mesh "SM_WallMerged_' in text
        assert 'def Mesh "SM_DoorLeaf_' in text
        assert 'def Mesh "SM_MEP_' in text
        assert "string bim_element_id =" in text


def test_remote_fbx_export_pipeline(tmp_path: Path) -> None:
    script_path = write_blender_glb_to_fbx_script(tmp_path / "glb_to_fbx.py")
    assert script_path.is_file()
    code = script_path.read_text(encoding="utf-8")
    assert "bpy.ops.import_scene.gltf" in code
    assert "bpy.ops.export_scene.fbx" in code

    dummy_glb = tmp_path / "house.glb"
    dummy_glb.write_bytes(b"glTF_mock")
    out_fbx = tmp_path / "house_unreal.fbx"

    def mock_runner(cmd_args, **kwargs):
        if cmd_args[0] == "scp" and str(out_fbx) in cmd_args:
            out_fbx.write_bytes(b"Kaydara FBX Binary  \x00")
        return subprocess.CompletedProcess(cmd_args, returncode=0, stdout="OK", stderr="")

    res = export_scene_to_remote_fbx(dummy_glb, out_fbx, runner_fn=mock_runner)
    assert res.succeeded
    assert out_fbx.is_file() and out_fbx.stat().st_size > 0


def test_end_to_end_cli_build_both_houses() -> None:
    for slug in ("dom_w_gnieznikach", "amor_woe1092"):
        proj_dir = REPO_ROOT / "projects" / slug
        res = subprocess.run([str(CLI_BIN), "build", str(proj_dir)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"E2E build failed for {slug}: {res.stdout}\n{res.stderr}"
        assert (proj_dir / "output" / f"{slug}.glb").is_file()
        assert (proj_dir / "output" / f"{slug}_unreal.usda").is_file()
        assert (proj_dir / "review" / "validation_report.json").is_file()
        assert (proj_dir / "review" / "overlay_report.json").is_file()
        assert (proj_dir / "review" / "invariants_3d_report.json").is_file()

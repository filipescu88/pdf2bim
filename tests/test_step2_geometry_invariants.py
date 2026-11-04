"""Tests for Step 2: Pure-Python 3D Geometry Compiler, 7 3D Invariants, and .glb export with extras."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from pdf2bim.export import export_scene_to_glb, read_glb_json_chunk
from pdf2bim.geometry import compile_scene_graph_3d, verify_3d_invariants
from pdf2bim.schema import SceneGraphV2

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_BIN = REPO_ROOT / ".venv" / "bin" / "pdf2bim"


def test_compile_and_7_invariants_house1_dom_w_gnieznikach(tmp_path: Path) -> None:
    sg_path = REPO_ROOT / "projects" / "dom_w_gnieznikach" / "scene_graph.json"
    sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))

    t0 = time.perf_counter()
    scene3d = compile_scene_graph_3d(sg)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"Compilation took {elapsed:.2f}s (> 1.0s limit)"

    rep = verify_3d_invariants(sg, scene3d)
    assert rep.passed, f"3D Invariants failed on dom_w_gnieznikach: {rep.to_dict()}"
    assert len(rep.checks) == 7
    for chk in rep.checks:
        assert chk.passed, f"Invariant {chk.invariant_id} ({chk.name}) failed: {chk.violations}"

    out_glb = export_scene_to_glb(sg, scene3d, tmp_path / "dom_w_gnieznikach.glb")
    assert out_glb.is_file() and out_glb.stat().st_size > 20_000

    gltf_json = read_glb_json_chunk(out_glb)
    nodes_with_extras = [n for n in gltf_json.get("nodes", []) if "extras" in n]
    assert len(nodes_with_extras) >= 150
    door_nodes = [n for n in nodes_with_extras if n["extras"].get("category") == "door_leaf"]
    assert len(door_nodes) == 10
    for dn in door_nodes:
        assert len(dn["extras"]["hinge_xy"]) == 2


def test_compile_and_7_invariants_house2_amor_woe1092(tmp_path: Path) -> None:
    sg_path = REPO_ROOT / "projects" / "amor_woe1092" / "scene_graph.json"
    sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))

    t0 = time.perf_counter()
    scene3d = compile_scene_graph_3d(sg)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"Compilation took {elapsed:.2f}s (> 1.0s limit)"

    rep = verify_3d_invariants(sg, scene3d)
    assert rep.passed, f"3D Invariants failed on amor_woe1092: {rep.to_dict()}"
    assert len(rep.checks) == 7
    for chk in rep.checks:
        assert chk.passed, f"Invariant {chk.invariant_id} ({chk.name}) failed: {chk.violations}"

    out_glb = export_scene_to_glb(sg, scene3d, tmp_path / "amor_woe1092.glb")
    assert out_glb.is_file() and out_glb.stat().st_size > 20_000

    gltf_json = read_glb_json_chunk(out_glb)
    nodes_with_extras = [n for n in gltf_json.get("nodes", []) if "extras" in n]
    assert len(nodes_with_extras) >= 150
    mep_nodes = [n for n in nodes_with_extras if n["extras"].get("category") == "mep_socket"]
    assert len(mep_nodes) == len(sg.mep_sockets)


def test_cli_build_both_houses() -> None:
    for slug in ("dom_w_gnieznikach", "amor_woe1092"):
        proj_dir = REPO_ROOT / "projects" / slug
        res = subprocess.run([str(CLI_BIN), "build", str(proj_dir)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"CLI build failed for {slug}: {res.stdout}\n{res.stderr}"
        glb_file = proj_dir / "output" / f"{slug}.glb"
        inv_file = proj_dir / "review" / "invariants_3d_report.json"
        assert glb_file.is_file()
        assert inv_file.is_file()
        inv_data = json.loads(inv_file.read_text(encoding="utf-8"))
        assert inv_data["passed"] is True

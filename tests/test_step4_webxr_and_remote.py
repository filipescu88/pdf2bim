"""Tests for Step 4: Generic WebXR viewer (zero hardcoded house coords), Laser Marker QA lifecycle, and Remote GPU Runner."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from pdf2bim.remote import RemoteGPUConfig, build_blender_ssh_command, run_remote_blender_job
from pdf2bim.schema import SceneGraphV2
from pdf2bim.validate import (
    add_laser_marker,
    load_markers,
    transition_markers_on_rebuild,
    verify_marker_issue,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_webxr_viewer_has_no_hardcoded_house_coordinates() -> None:
    html_path = REPO_ROOT / "web_vr" / "index.html"
    assert html_path.is_file()
    content = html_path.read_text(encoding="utf-8")

    # Verify it reads dynamic metadata from GLB extras (node.userData) and supports both test projects
    assert "extras.category === 'door_leaf'" in content
    assert "extras.hinge_xy" in content
    assert "extras.category === 'stair_step'" in content
    assert "extras.collidable === true" in content
    assert "dom_w_gnieznikach" in content
    assert "amor_woe1092" in content

    # Ensure no hardcoded house coordinates (like 10.30, 8.40, 12.38, 4.43, 10.44, 8.04) appear in JS
    forbidden_literals = ["10.30", "8.40", "12.38", "4.43", "10.44", "8.04"]
    for lit in forbidden_literals:
        assert not re.search(rf"\b{re.escape(lit)}\b", content), f"Hardcoded coordinate {lit} found in web_vr/index.html"


def test_laser_marker_qa_full_lifecycle(tmp_path: Path) -> None:
    sg_path = REPO_ROOT / "projects" / "dom_w_gnieznikach" / "scene_graph.json"
    sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))

    # 1. User shoots laser marker at wall 'w_p_south_main' in VR -> status = 'open'
    m1 = add_laser_marker(
        project_dir=tmp_path,
        element_id="w_p_south_main",
        node_name="w_p_south_main_L0_full_1",
        category="wall_segment",
        hit_xyz=(5.20, 0.00, 1.40),
        camera_xyz=(5.20, 2.10, 1.65),
        note="Sprawdzić wysokość parapetu okna południowego",
        level_id="parter",
    )
    assert m1.marker_id == "M-001"
    assert m1.status == "open"
    assert m1.element_id == "w_p_south_main"

    # 2. Rebuild transitions open marker for known element_id to 'needs_verification'
    store_after_rebuild = transition_markers_on_rebuild(tmp_path, sg)
    assert store_after_rebuild.markers[0].status == "needs_verification"

    # 3. User verifies fix in VR -> status = 'verified'
    verified_m = verify_marker_issue(tmp_path, "M-001")
    assert verified_m.status == "verified"

    reloaded = load_markers(tmp_path)
    assert reloaded.markers[0].status == "verified"


def test_remote_gpu_runner_enforces_exit_code_and_fresh_artifacts(tmp_path: Path) -> None:
    cfg = RemoteGPUConfig(ssh_target="filip@192.168.0.11", timeout_sec=30)
    cmd = build_blender_ssh_command(cfg, "C:/Users/filip/pdf2bim_remote/job.py", ["arg1"])
    joined = " ".join(cmd)
    assert "--background" in joined
    assert "--python-exit-code 1" in joined

    script_file = tmp_path / "bake_job.py"
    script_file.write_text("import bpy\n", encoding="utf-8")
    input_glb = tmp_path / "model.glb"
    input_glb.write_bytes(b"glTF_mock_bytes")
    out_fbx = tmp_path / "out" / "exported.fbx"

    # Case A: Blender returns non-zero exit code -> runner must report failure
    def mock_fail_runner(cmd_args, **kwargs):
        if cmd_args[0] == "ssh":
            return subprocess.CompletedProcess(cmd_args, returncode=1, stdout="", stderr="Python Traceback Error")
        return subprocess.CompletedProcess(cmd_args, returncode=0, stdout="", stderr="")

    res_fail = run_remote_blender_job(
        job_name="test_fail_job",
        local_script=script_file,
        local_inputs=[input_glb],
        expected_outputs=[("exported.fbx", out_fbx)],
        cfg=cfg,
        runner_fn=mock_fail_runner,
    )
    assert not res_fail.succeeded
    assert res_fail.exit_code == 1
    assert "non-zero code" in res_fail.error_message

    # Case B: Stale output artifact (old mtime) -> runner must reject stale cached output
    def mock_stale_runner(cmd_args, **kwargs):
        if cmd_args[0] == "scp" and str(out_fbx) in cmd_args:
            out_fbx.parent.mkdir(parents=True, exist_ok=True)
            out_fbx.write_bytes(b"FBX_DATA")
            old_time = time.time() - 3600.0
            os.utime(out_fbx, (old_time, old_time))
        return subprocess.CompletedProcess(cmd_args, returncode=0, stdout="OK", stderr="")

    res_stale = run_remote_blender_job(
        job_name="test_stale_job",
        local_script=script_file,
        local_inputs=[input_glb],
        expected_outputs=[("exported.fbx", out_fbx)],
        cfg=cfg,
        runner_fn=mock_stale_runner,
    )
    assert not res_stale.succeeded
    assert "stale mtime" in res_stale.error_message

    # Case C: Fresh valid artifact -> runner succeeds
    def mock_ok_runner(cmd_args, **kwargs):
        if cmd_args[0] == "scp" and str(out_fbx) in cmd_args:
            out_fbx.parent.mkdir(parents=True, exist_ok=True)
            out_fbx.write_bytes(b"FRESH_FBX_BINARY_DATA")
        return subprocess.CompletedProcess(cmd_args, returncode=0, stdout="OK", stderr="")

    res_ok = run_remote_blender_job(
        job_name="test_ok_job",
        local_script=script_file,
        local_inputs=[input_glb],
        expected_outputs=[("exported.fbx", out_fbx)],
        cfg=cfg,
        runner_fn=mock_ok_runner,
    )
    assert res_ok.succeeded
    assert "model.glb" in res_ok.uploaded_files
    assert str(out_fbx) in res_ok.downloaded_files

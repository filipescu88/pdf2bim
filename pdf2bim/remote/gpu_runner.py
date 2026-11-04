"""Reliable Remote Windows GPU Runner for Blender 5.1 jobs (Step 4).

Guarantees:
1. Always passes `--background --python-exit-code 1` to Blender so script exceptions fail the process.
2. Always uploads fresh inputs via `scp` before execution (never relies on stale cached `.blend` files).
3. Enforces explicit `timeout_sec` on `ssh`/`scp` calls.
4. Verifies output artifact existence, non-zero byte size, and fresh `mtime` after download.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class RemoteGPUConfig:
    ssh_target: str = "filip@192.168.0.11"
    blender_exe: str = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
    remote_workdir: str = "C:/Users/filip/pdf2bim_remote"
    timeout_sec: int = 180


@dataclass
class RemoteJobResult:
    job_name: str
    succeeded: bool
    exit_code: int
    command_args: list[str]
    uploaded_files: list[str] = field(default_factory=list)
    downloaded_files: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""


def build_blender_ssh_command(
    cfg: RemoteGPUConfig,
    remote_script_path: str,
    script_args: list[str] | None = None,
) -> list[str]:
    """Construct the exact SSH command array with mandatory `--background --python-exit-code 1`."""
    blender_cmd = (
        f'"{cfg.blender_exe}" --background --python-exit-code 1 --python "{remote_script_path}"'
    )
    if script_args:
        quoted_args = " ".join(f'"{a}"' for a in script_args)
        blender_cmd += f" -- {quoted_args}"
    return ["ssh", "-o", "BatchMode=yes", cfg.ssh_target, blender_cmd]


def run_remote_blender_job(
    job_name: str,
    local_script: Path,
    local_inputs: list[Path],
    expected_outputs: list[tuple[str, Path]],
    script_args: list[str] | None = None,
    cfg: RemoteGPUConfig | None = None,
    runner_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> RemoteJobResult:
    """Upload inputs, execute Blender with `--python-exit-code 1`, download outputs, and verify mtime/size."""
    if cfg is None:
        cfg = RemoteGPUConfig()

    local_script = Path(local_script).resolve()
    if not local_script.is_file():
        return RemoteJobResult(
            job_name=job_name,
            succeeded=False,
            exit_code=1,
            command_args=[],
            error_message=f"Local script not found: {local_script}",
        )

    for inp in local_inputs:
        if not Path(inp).is_file():
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=1,
                command_args=[],
                error_message=f"Local input file not found: {inp}",
            )

    start_wall_time = time.time()
    uploaded: list[str] = []

    # 1. Upload script and all input files via scp (preventing stale cache usage)
    all_to_upload = [local_script] + [Path(p).resolve() for p in local_inputs]
    for src_path in all_to_upload:
        remote_dest = f"{cfg.ssh_target}:{cfg.remote_workdir}/{src_path.name}"
        scp_up_cmd = ["scp", "-q", str(src_path), remote_dest]
        try:
            up_res = runner_fn(scp_up_cmd, capture_output=True, text=True, timeout=cfg.timeout_sec, check=False)
        except subprocess.TimeoutExpired:
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=124,
                command_args=scp_up_cmd,
                error_message=f"Timeout ({cfg.timeout_sec}s) uploading {src_path.name}",
            )
        if up_res.returncode != 0:
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=up_res.returncode,
                command_args=scp_up_cmd,
                stdout=up_res.stdout,
                stderr=up_res.stderr,
                error_message=f"SCP upload failed for {src_path.name}",
            )
        uploaded.append(src_path.name)

    # 2. Execute remote Blender with --python-exit-code 1
    remote_script_full = f"{cfg.remote_workdir}/{local_script.name}"
    ssh_cmd = build_blender_ssh_command(cfg, remote_script_full, script_args=script_args)
    try:
        exec_res = runner_fn(ssh_cmd, capture_output=True, text=True, timeout=cfg.timeout_sec, check=False)
    except subprocess.TimeoutExpired:
        return RemoteJobResult(
            job_name=job_name,
            succeeded=False,
            exit_code=124,
            command_args=ssh_cmd,
            uploaded_files=uploaded,
            error_message=f"Timeout ({cfg.timeout_sec}s) running remote Blender job '{job_name}'",
        )

    if exec_res.returncode != 0:
        return RemoteJobResult(
            job_name=job_name,
            succeeded=False,
            exit_code=exec_res.returncode,
            command_args=ssh_cmd,
            uploaded_files=uploaded,
            stdout=exec_res.stdout,
            stderr=exec_res.stderr,
            error_message=f"Remote Blender exited with non-zero code {exec_res.returncode}",
        )

    # 3. Download expected output artifacts and verify fresh mtime & non-zero size
    downloaded: list[str] = []
    for remote_rel_name, local_dest in expected_outputs:
        local_dest = Path(local_dest).resolve()
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        remote_src = f"{cfg.ssh_target}:{cfg.remote_workdir}/{remote_rel_name}"
        scp_down_cmd = ["scp", "-q", remote_src, str(local_dest)]
        try:
            down_res = runner_fn(scp_down_cmd, capture_output=True, text=True, timeout=cfg.timeout_sec, check=False)
        except subprocess.TimeoutExpired:
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=124,
                command_args=scp_down_cmd,
                uploaded_files=uploaded,
                error_message=f"Timeout downloading {remote_rel_name}",
            )

        if down_res.returncode != 0:
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=down_res.returncode,
                command_args=scp_down_cmd,
                uploaded_files=uploaded,
                stderr=down_res.stderr,
                error_message=f"Failed to download output artifact {remote_rel_name}",
            )

        if not local_dest.is_file() or local_dest.stat().st_size == 0:
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=1,
                command_args=scp_down_cmd,
                uploaded_files=uploaded,
                error_message=f"Downloaded artifact {local_dest.name} is missing or empty (0 bytes)",
            )

        if local_dest.stat().st_mtime < start_wall_time - 2.0:
            return RemoteJobResult(
                job_name=job_name,
                succeeded=False,
                exit_code=1,
                command_args=scp_down_cmd,
                uploaded_files=uploaded,
                error_message=f"Artifact {local_dest.name} has stale mtime ({local_dest.stat().st_mtime} < {start_wall_time})",
            )
        downloaded.append(str(local_dest))

    return RemoteJobResult(
        job_name=job_name,
        succeeded=True,
        exit_code=0,
        command_args=ssh_cmd,
        uploaded_files=uploaded,
        downloaded_files=downloaded,
        stdout=exec_res.stdout,
        stderr=exec_res.stderr,
    )

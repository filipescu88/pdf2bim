"""Remote GPU job runner package (Cycles lightmap baking, stereo 360 panoramas, GLB->FBX conversion)."""

from pdf2bim.remote.gpu_runner import (
    RemoteGPUConfig,
    RemoteJobResult,
    build_blender_ssh_command,
    run_remote_blender_job,
)

__all__ = [
    "RemoteGPUConfig",
    "RemoteJobResult",
    "build_blender_ssh_command",
    "run_remote_blender_job",
]

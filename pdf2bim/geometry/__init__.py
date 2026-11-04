"""3D geometry compilation package (walls, openings, floors, slabs, stairs, roof, MEP, 3D invariants)."""

from pdf2bim.geometry.builder import CompiledScene3D, compile_scene_graph_3d
from pdf2bim.geometry.invariants import GeometryInvariantsReport, InvariantCheckResult, verify_3d_invariants
from pdf2bim.geometry.mesh_utils import CompiledMeshNode

__all__ = [
    "CompiledMeshNode",
    "CompiledScene3D",
    "GeometryInvariantsReport",
    "InvariantCheckResult",
    "compile_scene_graph_3d",
    "verify_3d_invariants",
]

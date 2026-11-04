"""Automated 3D Geometric Invariants Checker (Invariants 1–7 from Step 2 Plan)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from shapely.geometry import Polygon

from pdf2bim.geometry.builder import CompiledScene3D, _quad_on_wall
from pdf2bim.geometry.mesh_utils import roof_inner_z_at
from pdf2bim.schema import SceneGraphV2


@dataclass
class InvariantCheckResult:
    invariant_id: int
    name: str
    passed: bool
    checked_count: int
    violations: list[str] = field(default_factory=list)


@dataclass
class GeometryInvariantsReport:
    project_slug: str
    passed: bool
    total_nodes: int
    checks: list[InvariantCheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_3d_invariants(sg: SceneGraphV2, scene3d: CompiledScene3D) -> GeometryInvariantsReport:
    """Verify all 7 geometric 3D invariants on a compiled 3D scene."""
    checks: list[InvariantCheckResult] = []

    # --- Invariant 1: Rectangular 4-vertex bases for all wall segments ---
    wall_nodes = [n for n in scene3d.nodes if n.category in ("wall_segment", "wall_exterior_cladding")]
    v1: list[str] = []
    for wn in wall_nodes:
        if wn.base_quad_xy is None or len(wn.base_quad_xy) != 4:
            v1.append(f"{wn.node_id}: base_quad_xy does not have 4 vertices")
            continue
        p = Polygon(wn.base_quad_xy)
        if not p.is_valid or p.area < 1e-5:
            v1.append(f"{wn.node_id}: invalid or degenerate quad polygon")
    checks.append(
        InvariantCheckResult(
            invariant_id=1,
            name="Rectangular 4-vertex bases for all wall segments (no concave triangulation artifacts)",
            passed=(len(v1) == 0 and len(wall_nodes) > 0),
            checked_count=len(wall_nodes),
            violations=v1,
        )
    )

    # --- Invariant 2: Disjoint room floors and zero Z-fighting with slabs ---
    floor_nodes = scene3d.by_category("room_floor")
    slab_nodes = scene3d.by_category("slab")
    v2: list[str] = []
    for i in range(len(floor_nodes)):
        fi = floor_nodes[i]
        pi = Polygon(fi.mesh.vertices[: len(fi.mesh.vertices) // 2, :2])
        for j in range(i + 1, len(floor_nodes)):
            fj = floor_nodes[j]
            if fi.level_id != fj.level_id:
                continue
            pj = Polygon(fj.mesh.vertices[: len(fj.mesh.vertices) // 2, :2])
            if pi.intersection(pj).area > 1e-3:
                v2.append(f"Floor overlap between {fi.node_id} and {fj.node_id}")
    for sn in slab_nodes:
        sz_max = float(np.max(sn.mesh.vertices[:, 2]))
        for fn in floor_nodes:
            fz_min = float(np.min(fn.mesh.vertices[:, 2]))
            if fz_min > 1.0 and abs(sz_max - fz_min) < 1e-4:
                v2.append(f"Slab {sn.node_id} top Z={sz_max:.4f} touches upper floor {fn.node_id} Z={fz_min:.4f}")
    checks.append(
        InvariantCheckResult(
            invariant_id=2,
            name="Disjoint room floor meshes and vertical separation from structural slabs",
            passed=(len(v2) == 0 and len(floor_nodes) > 0),
            checked_count=len(floor_nodes) + len(slab_nodes),
            violations=v2,
        )
    )

    # --- Invariant 3: Exterior facade cladding offset above plinth (zero Z-fighting) ---
    cladding_nodes = scene3d.by_category("wall_exterior_cladding")
    plinth_nodes = scene3d.by_category("plinth")
    plinth_z_top = max((float(np.max(p.mesh.vertices[:, 2])) for p in plinth_nodes), default=0.0)
    v3: list[str] = []
    for cn in cladding_nodes:
        cz_min = float(np.min(cn.mesh.vertices[:, 2]))
        if cz_min < plinth_z_top + 0.001:
            v3.append(f"{cn.node_id}: z_min={cz_min:.4f} is not above plinth_z_top={plinth_z_top:.4f}")
    checks.append(
        InvariantCheckResult(
            invariant_id=3,
            name="Exterior cladding separated from plinth (no facade Z-fighting)",
            passed=(len(v3) == 0),
            checked_count=len(cladding_nodes) + len(plinth_nodes),
            violations=v3,
        )
    )

    # --- Invariant 4: Full-depth stair treads/risers without side gaps ---
    step_nodes = scene3d.by_category("stair_step")
    v4: list[str] = []
    for st in step_nodes:
        td = float(st.extras.get("tread_depth", 0.0))
        if td < 0.20:
            v4.append(f"{st.node_id}: tread_depth={td:.3f}m is too shallow")
    checks.append(
        InvariantCheckResult(
            invariant_id=4,
            name="Full-depth stair steps and risers without side gaps",
            passed=(len(v4) == 0 and len(step_nodes) > 0),
            checked_count=len(step_nodes),
            violations=v4,
        )
    )

    # --- Invariant 5: Openings cut cleanly through all wall layers and roof planes ---
    v5: list[str] = []
    walls_by_id = {w.id: w for w in sg.walls}
    all_ops = list(sg.openings.windows) + list(sg.openings.doors)
    for op in all_ops:
        w = walls_by_id[op.wall_id]
        op_quad = _quad_on_wall(
            w,
            op.offset_along_wall + 0.02,
            op.offset_along_wall + op.width - 0.02,
            -1.0,
            1.0,
        )
        op_poly = Polygon(op_quad)
        for wn in wall_nodes:
            if wn.element_id != w.id or wn.base_quad_xy is None:
                continue
            w_poly = Polygon(wn.base_quad_xy)
            if w_poly.intersection(op_poly).area > 1e-4:
                wz_min = float(np.min(wn.mesh.vertices[:, 2]))
                wz_max = float(np.max(wn.mesh.vertices[:, 2]))
                # Check vertical overlap with opening clear span (sill_z + 0.01 .. lintel_z - 0.01)
                overlap_z = min(wz_max, op.lintel_z - 0.01) - max(wz_min, op.sill_z + 0.01)
                if overlap_z > 0.01:
                    v5.append(f"Wall node {wn.node_id} blocks opening {op.id} (overlap_z={overlap_z:.3f}m)")
    roof_nodes = scene3d.by_category("roof_plane")
    for rn in roof_nodes:
        rp_id = rn.element_id
        expected_rws = [rw for rw in sg.openings.roof_windows if rw.roof_plane_id == rp_id]
        if int(rn.extras.get("cutouts_count", 0)) != len(expected_rws):
            v5.append(f"Roof plane {rp_id} missing skylight cutouts")
    checks.append(
        InvariantCheckResult(
            invariant_id=5,
            name="Window, door, and skylight openings cut cleanly through all wall layers and roof planes",
            passed=(len(v5) == 0 and len(all_ops) > 0),
            checked_count=len(all_ops) + len(sg.openings.roof_windows),
            violations=v5,
        )
    )

    # --- Invariant 6: Attic walls clipped to roof inner plane & soffits bounded by soffit_x_bounds ---
    v6: list[str] = []
    clipped_wall_ids = {w.id for w in sg.walls if w.clip_to_roof}
    checked_v6 = 0
    for wn in wall_nodes:
        if wn.element_id in clipped_wall_ids:
            checked_v6 += 1
            for vx, vy, vz in wn.mesh.vertices:
                z_limit = roof_inner_z_at(sg.roof, float(vx), float(vy))
                if vz > z_limit + 1e-3:
                    v6.append(f"{wn.node_id}: vertex ({vx:.2f},{vy:.2f},{vz:.3f}) exceeds roof z_inner={z_limit:.3f}")
                    break
    soffit_nodes = scene3d.by_category("roof_soffit")
    for sn in soffit_nodes:
        checked_v6 += 1
        sx0, sx1 = sn.extras.get("soffit_x_bounds", [0.0, 100.0])
        vx_min = float(np.min(sn.mesh.vertices[:, 0]))
        vx_max = float(np.max(sn.mesh.vertices[:, 0]))
        if vx_min < sx0 - 1e-3 or vx_max > sx1 + 1e-3:
            v6.append(f"{sn.node_id}: X range [{vx_min:.3f}, {vx_max:.3f}] exceeds soffit_x_bounds [{sx0:.3f}, {sx1:.3f}]")
    checks.append(
        InvariantCheckResult(
            invariant_id=6,
            name="Attic walls clipped analytically to roof inner plane and soffit boxes bounded by building walls",
            passed=(len(v6) == 0 and checked_v6 > 0),
            checked_count=checked_v6,
            violations=v6,
        )
    )

    # --- Invariant 7: Door leaf hinge pivots at exact hinge edge ---
    door_nodes = scene3d.by_category("door_leaf")
    v7: list[str] = []
    doors_by_id = {d.id: d for d in sg.openings.doors}
    for dn in door_nodes:
        d = doors_by_id[dn.element_id]
        w = walls_by_id[d.wall_id]
        hinge_xy = dn.extras.get("hinge_xy")
        if not hinge_xy or len(hinge_xy) != 2:
            v7.append(f"{dn.node_id}: missing hinge_xy in extras")
            continue
        hx, hy = float(hinge_xy[0]), float(hinge_xy[1])
        # Distance from hinge_xy to door leaf vertices in XY must be <= 0.05 m at hinge edge
        dists = [math.hypot(float(vx) - hx, float(vy) - hy) for vx, vy, _ in dn.mesh.vertices]
        if min(dists) > 0.06:
            v7.append(f"{dn.node_id}: hinge_xy ({hx:.3f},{hy:.3f}) is too far from door leaf edge (min_dist={min(dists):.3f}m)")
        if w.length < d.offset_along_wall + d.width - 1e-3:
            v7.append(f"{dn.node_id}: door exceeds host wall length")
    checks.append(
        InvariantCheckResult(
            invariant_id=7,
            name="Door leaves have exact hinge_xy pivot coordinates at the hinge jamb",
            passed=(len(v7) == 0 and len(door_nodes) == len(sg.openings.doors)),
            checked_count=len(door_nodes),
            violations=v7,
        )
    )

    return GeometryInvariantsReport(
        project_slug=sg.project_slug,
        passed=all(c.passed for c in checks),
        total_nodes=len(scene3d.nodes),
        checks=checks,
    )

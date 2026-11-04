"""Low-level 3D mesh extrusion utilities for the pure-Python geometry compiler (Step 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import mapbox_earcut as earcut
import numpy as np
import trimesh
from shapely.geometry import Polygon

from pdf2bim.schema import RoofPlaneSpec, RoofSpec


@dataclass
class CompiledMeshNode:
    """Single compiled 3D mesh node with BIM & WebXR metadata (`extras`)."""

    node_id: str
    element_id: str
    category: str
    level_id: str
    material_id: str
    ue_mesh_name: str
    ue_material_name: str
    mesh: trimesh.Trimesh
    collidable: bool = False
    base_quad_xy: list[tuple[float, float]] | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def roof_inner_z_at(roof: RoofSpec, x: float, y: float) -> float:
    """Compute the minimum inner roof ceiling height Z at (x, y) across covering roof planes."""
    z_vals: list[float] = []
    for rp in roof.planes:
        poly = Polygon(rp.polygon_xy)
        if poly.buffer(1e-3).contains(Polygon([(x, y), (x + 1e-5, y), (x, y + 1e-5)]).centroid):
            z_vals.append(rp.z_inner_at(x, y))
    if not z_vals:
        # Fallback to closest main plane
        for rp in roof.planes:
            z_vals.append(rp.z_inner_at(x, y))
    return min(z_vals) if z_vals else 100.0


def extrude_quad_prism(
    quad_xy: list[tuple[float, float]],
    z_bottom: float,
    z_top: float,
    roof_to_clip: RoofSpec | None = None,
) -> trimesh.Trimesh | None:
    """Build a watertight 8-vertex hexahedral prism from a 4-vertex rectangular base in XY.

    If `roof_to_clip` is provided, analytically clips top vertices (and splits across ridge if spanned)
    so that no vertex exceeds `rp.z_inner_at(x, y)`.
    Guarantees Invariant 1 (4-vertex rectangular base) and Invariant 6 (exact roof clipping).
    """
    if len(quad_xy) != 4:
        raise ValueError(f"Expected 4-vertex quad base, got {len(quad_xy)} vertices")
    if z_top <= z_bottom + 1e-4:
        return None

    # Ensure counter-clockwise orientation in XY
    poly = Polygon(quad_xy)
    if poly.area < 1e-6:
        return None
    if not poly.exterior.is_ccw:
        quad_xy = list(reversed(quad_xy))

    if roof_to_clip is not None and roof_to_clip.planes:
        # Clamp quad Y (or X) span to the region where roof_inner_z_at(x, y) >= z_bottom
        xs = [p[0] for p in quad_xy]
        ys = [p[1] for p in quad_xy]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_mid = 0.5 * (x_min + x_max)

        # Binary-search or linear interpolation along Y if endpoints fall below z_bottom under roof slope
        z_at_ymin = roof_inner_z_at(roof_to_clip, x_mid, y_min)
        z_at_ymax = roof_inner_z_at(roof_to_clip, x_mid, y_max)
        if z_at_ymin < z_bottom and z_at_ymax < z_bottom:
            x_mid_y = 0.5 * (y_min + y_max)
            if roof_inner_z_at(roof_to_clip, x_mid, x_mid_y) < z_bottom:
                return None

        if z_at_ymin < z_bottom:
            # Find y in [y_min, y_max] where roof_inner_z_at == z_bottom
            lo, hi = y_min, y_max
            for _ in range(24):
                mid = 0.5 * (lo + hi)
                if roof_inner_z_at(roof_to_clip, x_mid, mid) < z_bottom:
                    lo = mid
                else:
                    hi = mid
            y_min = hi

        if z_at_ymax < z_bottom:
            lo, hi = y_min, y_max
            for _ in range(24):
                mid = 0.5 * (lo + hi)
                if roof_inner_z_at(roof_to_clip, x_mid, mid) < z_bottom:
                    hi = mid
                else:
                    lo = mid
            y_max = lo

        if y_max - y_min < 1e-3 or x_max - x_min < 1e-3:
            return None
        quad_xy = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]

        # Check if quad spans across a horizontal ridge line y = y_ridge
        ridge_ys = set()
        for rp in roof_to_clip.planes:
            (rx0, ry0), (rx1, ry1) = rp.ridge_line_xy
            if abs(ry0 - ry1) < 1e-3:
                ridge_ys.add(round(ry0, 4))
        for ry in sorted(ridge_ys):
            if y_min + 0.02 < ry < y_max - 0.02:
                q1 = [(x_min, y_min), (x_max, y_min), (x_max, ry), (x_min, ry)]
                q2 = [(x_min, ry), (x_max, ry), (x_max, y_max), (x_min, y_max)]
                m1 = extrude_quad_prism(q1, z_bottom, z_top, roof_to_clip)
                m2 = extrude_quad_prism(q2, z_bottom, z_top, roof_to_clip)
                meshes = [m for m in (m1, m2) if m is not None]
                if not meshes:
                    return None
                return trimesh.util.concatenate(meshes)

    verts = np.zeros((8, 3), dtype=np.float64)
    for i, (x, y) in enumerate(quad_xy):
        zb = z_bottom
        zt = z_top
        if roof_to_clip is not None:
            z_roof = roof_inner_z_at(roof_to_clip, x, y)
            zt = min(zt, z_roof)
            zb = min(zb, zt)
        verts[i] = [x, y, zb]
        verts[i + 4] = [x, y, zt]

    if np.max(verts[4:, 2] - verts[:4, 2]) < 1e-4:
        return None

    # 12 triangles (2 per face of the hexahedron, outward normals)
    faces = np.array(
        [
            # Bottom (0, 1, 2, 3) -> outward -Z
            [0, 2, 1],
            [0, 3, 2],
            # Top (4, 5, 6, 7) -> outward +Z
            [4, 5, 6],
            [4, 6, 7],
            # Side 0-1
            [0, 1, 5],
            [0, 5, 4],
            # Side 1-2
            [1, 2, 6],
            [1, 6, 5],
            # Side 2-3
            [2, 3, 7],
            [2, 7, 6],
            # Side 3-0
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int64,
    )
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def extrude_polygon_2d(
    polygon: Polygon,
    z_bottom: float,
    z_top: float,
) -> trimesh.Trimesh | None:
    """Extrude an arbitrary 2D Shapely Polygon (with optional interior holes) along Z using earcut."""
    if polygon.is_empty or polygon.area < 1e-6 or z_top <= z_bottom + 1e-5:
        return None

    if not polygon.exterior.is_ccw:
        polygon = Polygon(
            list(reversed(polygon.exterior.coords)),
            [list(reversed(ring.coords)) for ring in polygon.interiors],
        )

    rings_2d: list[np.ndarray] = []
    ring_end_indices: list[int] = []
    total_pts = 0

    ext_coords = np.array(list(polygon.exterior.coords)[:-1], dtype=np.float64)
    rings_2d.append(ext_coords)
    total_pts += len(ext_coords)
    ring_end_indices.append(total_pts)

    for hole in polygon.interiors:
        h_coords = np.array(list(hole.coords)[:-1], dtype=np.float64)
        if Polygon(h_coords).exterior.is_ccw:
            h_coords = h_coords[::-1]
        rings_2d.append(h_coords)
        total_pts += len(h_coords)
        ring_end_indices.append(total_pts)

    verts_2d = np.vstack(rings_2d)
    rings_arr = np.array(ring_end_indices, dtype=np.uint32)
    tri_indices = earcut.triangulate_float64(verts_2d, rings_arr).reshape(-1, 3)

    n = len(verts_2d)
    verts_bottom = np.column_stack([verts_2d, np.full(n, z_bottom, dtype=np.float64)])
    verts_top = np.column_stack([verts_2d, np.full(n, z_top, dtype=np.float64)])
    vertices = np.vstack([verts_bottom, verts_top])

    # Bottom faces (reversed winding for -Z normal) and top faces (+Z normal)
    faces_bottom = tri_indices[:, ::-1]
    faces_top = tri_indices + n
    side_faces: list[list[int]] = []

    start_idx = 0
    for end_idx in ring_end_indices:
        ring_len = end_idx - start_idx
        for i in range(ring_len):
            curr_b = start_idx + i
            next_b = start_idx + ((i + 1) % ring_len)
            curr_t = curr_b + n
            next_t = next_b + n
            side_faces.append([curr_b, next_b, next_t])
            side_faces.append([curr_b, next_t, curr_t])
        start_idx = end_idx

    all_faces = np.vstack([faces_bottom, faces_top, np.array(side_faces, dtype=np.int64)])
    return trimesh.Trimesh(vertices=vertices, faces=all_faces, process=False)


def extrude_sloped_roof_plane(
    rp: RoofPlaneSpec,
    cutout_polygons_xy: list[Polygon] | None = None,
) -> trimesh.Trimesh | None:
    """Extrude a sloped RoofPlaneSpec with cutouts (e.g., skylights) between z_inner_at and z_outer_at."""
    poly = Polygon(rp.polygon_xy)
    if cutout_polygons_xy:
        for hole_poly in cutout_polygons_xy:
            poly = poly.difference(hole_poly)

    if poly.is_empty:
        return None

    polys = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
    sub_meshes: list[trimesh.Trimesh] = []

    for sub_p in polys:
        flat_mesh = extrude_polygon_2d(sub_p, 0.0, 1.0)
        if flat_mesh is None:
            continue
        v = flat_mesh.vertices.copy()
        n = len(v) // 2
        for i in range(n):
            x, y = v[i, 0], v[i, 1]
            v[i, 2] = rp.z_inner_at(x, y)
            v[i + n, 2] = rp.z_outer_at(x, y)
        flat_mesh.vertices = v
        sub_meshes.append(flat_mesh)

    if not sub_meshes:
        return None
    return trimesh.util.concatenate(sub_meshes)

"""Pure-Python 3D BIM geometry compiler from SceneGraphV2 (Step 2).

Compiles walls (multi-layer split around openings), windows, doors (with hinge pivots),
disjoint room floors, slabs with stair voids, stairs (full risers + landings),
multi-pitched roof planes (with skylight cutouts and soffits bounded by soffit_x_bounds),
site/terraces/neighbors, and MEP sockets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import trimesh
from shapely.geometry import Polygon, box

from pdf2bim.geometry.mesh_utils import (
    CompiledMeshNode,
    extrude_polygon_2d,
    extrude_quad_prism,
    extrude_sloped_roof_plane,
)
from pdf2bim.schema import DoorSpec, SceneGraphV2, WallSpec, WindowSpec


@dataclass
class CompiledScene3D:
    """Container for all compiled 3D mesh nodes of a SceneGraphV2."""

    project_slug: str
    nodes: list[CompiledMeshNode] = field(default_factory=list)

    def by_category(self, category: str) -> list[CompiledMeshNode]:
        return [n for n in self.nodes if n.category == category]


def _wall_layer_offsets(w: WallSpec) -> list[tuple[int, float, float]]:
    """Return list of (layer_idx, off_a, off_b) lateral offsets along left normal for each layer."""
    th = w.total_thickness
    if w.alignment == "center":
        start_off = 0.5 * th
        direction = -1.0
    elif w.alignment == "left":
        start_off = 0.0
        direction = 1.0
    elif w.alignment == "right":
        start_off = 0.0
        direction = -1.0
    elif w.alignment == "core_left":
        # Reference axis is outer face of structural core; insulation/finish_ext go outward (-), core/finish_int go inward (+)
        start_off = -w.ext_insulation_thickness
        direction = 1.0
    else:  # "core_right"
        start_off = w.ext_insulation_thickness
        direction = -1.0

    res: list[tuple[int, float, float]] = []
    curr = start_off
    for idx, layer in enumerate(w.layers):
        nxt = curr + direction * layer.thickness
        off_lo, off_hi = min(curr, nxt), max(curr, nxt)
        res.append((idx, off_lo, off_hi))
        curr = nxt
    return res


def _quad_on_wall(
    w: WallSpec,
    u0: float,
    u1: float,
    off_lo: float,
    off_hi: float,
) -> list[tuple[float, float]]:
    """Compute 4-vertex rectangular base quad in XY for segment [u0, u1] and lateral offsets [off_lo, off_hi]."""
    x0, y0 = w.start_xy
    dx = w.end_xy[0] - x0
    dy = w.end_xy[1] - y0
    L = max(1e-6, math.hypot(dx, dy))
    tx, ty = dx / L, dy / L
    nx, ny = -ty, tx
    return [
        (x0 + tx * u0 + nx * off_lo, y0 + ty * u0 + ny * off_lo),
        (x0 + tx * u1 + nx * off_lo, y0 + ty * u1 + ny * off_lo),
        (x0 + tx * u1 + nx * off_hi, y0 + ty * u1 + ny * off_hi),
        (x0 + tx * u0 + nx * off_hi, y0 + ty * u0 + ny * off_hi),
    ]


def _ue_mat_name(sg: SceneGraphV2, mat_id: str) -> str:
    mat = sg.materials.get(mat_id)
    return mat.ue_name if mat is not None else f"M_{mat_id}"


def build_walls_and_openings(sg: SceneGraphV2) -> list[CompiledMeshNode]:
    """Compile multi-layer walls split around openings, plus window/door frames, glass, and door leaves."""
    nodes: list[CompiledMeshNode] = []

    wall_openings: dict[str, list[WindowSpec | DoorSpec]] = {w.id: [] for w in sg.walls}
    for win in sg.openings.windows:
        if win.wall_id in wall_openings:
            wall_openings[win.wall_id].append(win)
    for door in sg.openings.doors:
        if door.wall_id in wall_openings:
            wall_openings[door.wall_id].append(door)

    for w in sg.walls:
        L = w.length
        ops = sorted(wall_openings.get(w.id, []), key=lambda o: o.offset_along_wall)
        layer_offsets = _wall_layer_offsets(w)
        roof_clip = sg.roof if w.clip_to_roof else None

        # Partition [0, L] into intervals
        breakpoints = [0.0]
        for op in ops:
            u0 = max(0.0, op.offset_along_wall)
            u1 = min(L, op.offset_along_wall + op.width)
            breakpoints.extend([u0, u1])
        breakpoints.append(L)
        breakpoints = sorted(set(round(b, 5) for b in breakpoints))

        seg_counter = 0
        for i in range(len(breakpoints) - 1):
            ua, ub = breakpoints[i], breakpoints[i + 1]
            if ub - ua < 1e-3:
                continue
            mid_u = 0.5 * (ua + ub)
            active_op: WindowSpec | DoorSpec | None = None
            for op in ops:
                if op.offset_along_wall - 1e-4 <= mid_u <= op.offset_along_wall + op.width + 1e-4:
                    active_op = op
                    break

            for layer_idx, off_lo, off_hi in layer_offsets:
                layer = w.layers[layer_idx]
                ua_eff = ua + (0.025 if (len(w.layers) > 1 and layer.role != "finish_ext" and ua < 1e-4) else 0.0)
                ub_eff = ub - (0.025 if (len(w.layers) > 1 and layer.role != "finish_ext" and ub > L - 1e-4) else 0.0)
                if ub_eff - ua_eff < 1e-3:
                    continue
                quad_xy = _quad_on_wall(w, ua_eff, ub_eff, off_lo, off_hi)
                zb_layer = w.z_bottom + layer.z_bottom_offset
                zt_layer = w.z_top + layer.z_top_offset

                z_spans: list[tuple[str, float, float]] = []
                if active_op is None:
                    z_spans.append(("full", zb_layer, zt_layer))
                else:
                    if active_op.sill_z > zb_layer + 1e-3:
                        z_spans.append(("sill", zb_layer, min(zt_layer, active_op.sill_z)))
                    if zt_layer > active_op.lintel_z + 1e-3:
                        z_spans.append(("lintel", max(zb_layer, active_op.lintel_z), zt_layer))

                for span_tag, zb, zt in z_spans:
                    mesh = extrude_quad_prism(quad_xy, zb, zt, roof_to_clip=roof_clip)
                    if mesh is None:
                        continue
                    seg_counter += 1
                    cat = "wall_exterior_cladding" if layer.role == "finish_ext" and layer.z_bottom_offset > 0 else "wall_segment"
                    node_id = f"{w.id}_L{layer_idx}_{span_tag}_{seg_counter}"
                    nodes.append(
                        CompiledMeshNode(
                            node_id=node_id,
                            element_id=w.id,
                            category=cat,
                            level_id=w.level_id,
                            material_id=layer.material_id,
                            ue_mesh_name=f"SM_Wall_{w.level_id}_{w.id}_L{layer_idx}_{seg_counter}",
                            ue_material_name=_ue_mat_name(sg, layer.material_id),
                            mesh=mesh,
                            collidable=(layer.role == "core"),
                            base_quad_xy=quad_xy,
                            extras={
                                "element_id": w.id,
                                "category": cat,
                                "wall_type": w.wall_type,
                                "layer_role": layer.role,
                                "level_id": w.level_id,
                                "collidable": (layer.role == "core"),
                            },
                        )
                    )

        # Build window & door meshes for openings on this wall
        total_lo = min(o[1] for o in layer_offsets)
        total_hi = max(o[2] for o in layer_offsets)
        mid_lat = 0.5 * (total_lo + total_hi)

        for op in ops:
            u0 = op.offset_along_wall
            u1 = op.offset_along_wall + op.width
            if isinstance(op, WindowSpec):
                fw = 0.065  # 6.5 cm frame profile width
                fd = 0.045  # 9 cm total frame depth around mid_lat
                # 1. Glass pane (2 cm thick at center of wall)
                g_quad = _quad_on_wall(w, u0 + fw, u1 - fw, mid_lat - 0.01, mid_lat + 0.01)
                g_mesh = extrude_quad_prism(g_quad, op.sill_z + fw, op.lintel_z - fw)
                if g_mesh is not None:
                    nodes.append(
                        CompiledMeshNode(
                            node_id=f"{op.id}_glass",
                            element_id=op.id,
                            category="window_glass",
                            level_id=w.level_id,
                            material_id=op.glass_material_id,
                            ue_mesh_name=f"SM_WindowGlass_{op.id}",
                            ue_material_name=_ue_mat_name(sg, op.glass_material_id),
                            mesh=g_mesh,
                            collidable=False,
                            base_quad_xy=g_quad,
                            extras={"element_id": op.id, "wall_id": w.id, "category": "window_glass", "level_id": w.level_id},
                        )
                    )

                # 2. Complete 4-sided window frame + vertical mullions + external/internal sills
                frame_parts: list[trimesh.Trimesh] = []
                f_quad_full = _quad_on_wall(w, u0, u1, mid_lat - fd, mid_lat + fd)
                for m_part in (
                    extrude_quad_prism(f_quad_full, op.sill_z, op.sill_z + fw),  # Bottom sill bar
                    extrude_quad_prism(f_quad_full, op.lintel_z - fw, op.lintel_z),  # Top head bar
                    extrude_quad_prism(_quad_on_wall(w, u0, u0 + fw, mid_lat - fd, mid_lat + fd), op.sill_z + fw, op.lintel_z - fw),  # Left jamb
                    extrude_quad_prism(_quad_on_wall(w, u1 - fw, u1, mid_lat - fd, mid_lat + fd), op.sill_z + fw, op.lintel_z - fw),  # Right jamb
                ):
                    if m_part is not None:
                        frame_parts.append(m_part)

                # Add vertical mullion(s) for multi-casement windows
                n_panes = 3 if op.width >= 2.50 else (2 if op.width >= 1.35 else 1)
                for p_idx in range(1, n_panes):
                    um = u0 + (op.width * p_idx) / n_panes
                    m_quad = _quad_on_wall(w, um - 0.028, um + 0.028, mid_lat - 0.035, mid_lat + 0.035)
                    m_bar = extrude_quad_prism(m_quad, op.sill_z + fw, op.lintel_z - fw)
                    if m_bar is not None:
                        frame_parts.append(m_bar)

                # Add external & internal window sill when window has a parapet (sill_z > level floor + 20 cm)
                if op.sill_z - w.z_bottom >= 0.20:
                    sill_quad = _quad_on_wall(w, u0 - 0.03, u1 + 0.03, total_lo - 0.04, total_hi + 0.03)
                    sill_mesh = extrude_quad_prism(sill_quad, op.sill_z - 0.03, op.sill_z)
                    if sill_mesh is not None:
                        frame_parts.append(sill_mesh)

                # If French balcony (portfenetr), add exterior mounting rails & glass balustrade
                if op.is_french_balcony:
                    rail_top_q = _quad_on_wall(w, u0 - 0.06, u1 + 0.06, total_lo - 0.065, total_lo - 0.01)
                    for r_part in (
                        extrude_quad_prism(rail_top_q, op.sill_z, op.sill_z + 0.05),
                        extrude_quad_prism(rail_top_q, op.sill_z + 0.96, op.sill_z + 1.00),
                    ):
                        if r_part is not None:
                            frame_parts.append(r_part)
                    bal_g_quad = _quad_on_wall(w, u0 - 0.05, u1 + 0.05, total_lo - 0.05, total_lo - 0.03)
                    bal_g_mesh = extrude_quad_prism(bal_g_quad, op.sill_z + 0.05, op.sill_z + 0.96)
                    if bal_g_mesh is not None:
                        nodes.append(
                            CompiledMeshNode(
                                node_id=f"{op.id}_balustrade_glass",
                                element_id=op.id,
                                category="window_glass",
                                level_id=w.level_id,
                                material_id=op.glass_material_id,
                                ue_mesh_name=f"SM_FrenchBalconyGlass_{op.id}",
                                ue_material_name=_ue_mat_name(sg, op.glass_material_id),
                                mesh=bal_g_mesh,
                                collidable=False,
                                base_quad_xy=bal_g_quad,
                                extras={"element_id": op.id, "wall_id": w.id, "category": "window_glass", "level_id": w.level_id},
                            )
                        )

                if frame_parts:
                    f_mesh = trimesh.util.concatenate(frame_parts)
                    nodes.append(
                        CompiledMeshNode(
                            node_id=f"{op.id}_frame",
                            element_id=op.id,
                            category="window_frame",
                            level_id=w.level_id,
                            material_id=op.frame_material_id,
                            ue_mesh_name=f"SM_WindowFrame_{op.id}",
                            ue_material_name=_ue_mat_name(sg, op.frame_material_id),
                            mesh=f_mesh,
                            collidable=False,
                            base_quad_xy=f_quad_full,
                            extras={"element_id": op.id, "wall_id": w.id, "category": "window_frame", "level_id": w.level_id},
                        )
                    )
            elif isinstance(op, DoorSpec):
                # Compute exact hinge pivot in XY on the wall reference axis + mid_lat
                x0, y0 = w.start_xy
                dx, dy = w.end_xy[0] - x0, w.end_xy[1] - y0
                tx, ty = dx / L, dy / L
                nx, ny = -ty, tx
                u_hinge = u0 if op.hinge_side == "left" else u1
                hx = round(x0 + tx * u_hinge + nx * mid_lat, 4)
                hy = round(y0 + ty * u_hinge + ny * mid_lat, 4)

                leaf_quad = _quad_on_wall(w, u0 + 0.02, u1 - 0.02, mid_lat - 0.02, mid_lat + 0.02)
                leaf_mesh = extrude_quad_prism(leaf_quad, op.sill_z, op.lintel_z - 0.02)
                if leaf_mesh is not None:
                    nodes.append(
                        CompiledMeshNode(
                            node_id=f"SkrzydloDrzwi_{op.id}",
                            element_id=op.id,
                            category="door_leaf",
                            level_id=w.level_id,
                            material_id=op.leaf_material_id,
                            ue_mesh_name=f"SM_DoorLeaf_{op.id}",
                            ue_material_name=_ue_mat_name(sg, op.leaf_material_id),
                            mesh=leaf_mesh,
                            collidable=True,
                            base_quad_xy=leaf_quad,
                            extras={
                                "element_id": op.id,
                                "wall_id": w.id,
                                "category": "door_leaf",
                                "level_id": w.level_id,
                                "collidable": True,
                                "hinge_xy": [hx, hy],
                                "hinge_side": op.hinge_side,
                                "swing_dir": op.swing_dir,
                                "open_angle_deg": op.open_angle_deg,
                            },
                        )
                    )

    return nodes


def build_floors_slabs_and_site(sg: SceneGraphV2) -> list[CompiledMeshNode]:
    """Compile disjoint room floors, structural slabs with stair voids, plinth, terraces, and site."""
    nodes: list[CompiledMeshNode] = []
    levels_map = {lvl.id: lvl for lvl in sg.levels}

    # 1. Room floors (2 cm finish layer: z_floor .. z_floor + 0.02 m)
    for room in sg.rooms:
        lvl = levels_map[room.level_id]
        poly = Polygon(room.polygon_xy)
        mesh = extrude_polygon_2d(poly, lvl.z_floor, lvl.z_floor + 0.02)
        if mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Posadzka_{room.id}",
                    element_id=room.id,
                    category="room_floor",
                    level_id=room.level_id,
                    material_id=room.floor_material_id,
                    ue_mesh_name=f"SM_Floor_{room.id}",
                    ue_material_name=_ue_mat_name(sg, room.floor_material_id),
                    mesh=mesh,
                    collidable=True,
                    extras={
                        "element_id": room.id,
                        "room_id": room.id,
                        "room_code": room.code,
                        "room_name": room.name,
                        "category": "room_floor",
                        "level_id": room.level_id,
                    },
                )
            )

    # 2. Structural slabs (with stair voids subtracted; clamped below upper floor to prevent Z-fighting)
    upper_z_floors = sorted(lvl.z_floor for lvl in sg.levels if lvl.z_floor > 0.1)
    for slab in sg.slabs:
        outer_poly = Polygon(slab.polygon_xy)
        holes = [Polygon(h) for h in slab.voids_xy]
        for h in holes:
            outer_poly = outer_poly.difference(h)
        zt = slab.z_top
        for uz in upper_z_floors:
            if abs(zt - uz) < 0.01:
                zt = uz - 0.002  # 2 mm clearance below attic room floor finish
        mesh = extrude_polygon_2d(outer_poly, slab.z_bottom, zt)
        if mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Strop_{slab.id}",
                    element_id=slab.id,
                    category="slab",
                    level_id=slab.level_id,
                    material_id=slab.material_id,
                    ue_mesh_name=f"SM_Slab_{slab.id}",
                    ue_material_name=_ue_mat_name(sg, slab.material_id),
                    mesh=mesh,
                    collidable=True,
                    extras={"element_id": slab.id, "category": "slab", "level_id": slab.level_id},
                )
            )

    # 3. Plinth (cokół budynku z = -0.30 .. 0.00 m along structural bounding box)
    bx0, by0, bx1, by1 = sg.coordinate_system.structural_bbox_xy
    plinth_poly = box(bx0, by0, bx1, by1).difference(box(bx0 + 0.24, by0 + 0.24, bx1 - 0.24, by1 - 0.24))
    first_mat = next(iter(sg.materials.keys()))
    plinth_mesh = extrude_polygon_2d(plinth_poly, -0.30, 0.00)
    if plinth_mesh is not None:
        nodes.append(
            CompiledMeshNode(
                node_id="Cokol_Budynku",
                element_id="plinth_main",
                category="plinth",
                level_id="parter",
                material_id=first_mat,
                ue_mesh_name="SM_Plinth_Main",
                ue_material_name=_ue_mat_name(sg, first_mat),
                mesh=plinth_mesh,
                collidable=True,
                extras={"element_id": "plinth_main", "category": "plinth", "level_id": "parter"},
            )
        )

    # 4. Terraces
    for terr in sg.site.terraces:
        t_poly = Polygon(terr.polygon_xy)
        t_mesh = extrude_polygon_2d(t_poly, terr.z_bottom, terr.z_top)
        if t_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Taras_{terr.id}",
                    element_id=terr.id,
                    category="terrace",
                    level_id="parter",
                    material_id=terr.material_id,
                    ue_mesh_name=f"SM_Terrace_{terr.id}",
                    ue_material_name=_ue_mat_name(sg, terr.material_id),
                    mesh=t_mesh,
                    collidable=True,
                    extras={"element_id": terr.id, "category": "terrace", "level_id": "parter"},
                )
            )

    # 5. Neighboring buildings from DXF
    for nb in sg.site.neighbors:
        nb_poly = Polygon(nb.footprint_xy)
        nb_mesh = extrude_polygon_2d(nb_poly, -0.30, nb.eave_height_m)
        if nb_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Sasiad_{nb.id}",
                    element_id=nb.id,
                    category="neighbor_building",
                    level_id="site",
                    material_id=first_mat,
                    ue_mesh_name=f"SM_Neighbor_{nb.id}",
                    ue_material_name=_ue_mat_name(sg, first_mat),
                    mesh=nb_mesh,
                    collidable=False,
                    extras={"element_id": nb.id, "category": "neighbor_building", "level_id": "site"},
                )
            )

    return nodes


def build_stairs(sg: SceneGraphV2) -> list[CompiledMeshNode]:
    """Compile stair flights (with full-depth treads and risers — Invariant 4) and landings."""
    nodes: list[CompiledMeshNode] = []

    for stair in sg.stairs:
        for fl in stair.flights:
            x0, y0, x1, y1 = fl.bbox_xy
            n_steps = fl.steps_count
            for s_idx in range(n_steps):
                zb = fl.z_start + s_idx * fl.riser_h
                zt = zb + fl.riser_h
                # Compute step rectangle of full depth tread_d (no side triangular gaps!)
                if fl.direction == "+X":
                    sx0 = x0 + s_idx * fl.tread_d
                    sx1 = min(x1, sx0 + fl.tread_d)
                    quad = [(sx0, y0), (sx1, y0), (sx1, y1), (sx0, y1)]
                elif fl.direction == "-X":
                    sx1 = x1 - s_idx * fl.tread_d
                    sx0 = max(x0, sx1 - fl.tread_d)
                    quad = [(sx0, y0), (sx1, y0), (sx1, y1), (sx0, y1)]
                elif fl.direction == "+Y":
                    sy0 = y0 + s_idx * fl.tread_d
                    sy1 = min(y1, sy0 + fl.tread_d)
                    quad = [(x0, sy0), (x1, sy0), (x1, sy1), (x0, sy1)]
                else:  # "-Y"
                    sy1 = y1 - s_idx * fl.tread_d
                    sy0 = max(y0, sy1 - fl.tread_d)
                    quad = [(x0, sy0), (x1, sy0), (x1, sy1), (x0, sy1)]

                # Solid step block from max(fl.z_start, zt - 0.22 - fl.riser_h) to zt (eliminates side gaps)
                step_zb = max(fl.z_start, zb - 0.16)
                step_mesh = extrude_quad_prism(quad, step_zb, zt)
                if step_mesh is not None:
                    step_id = f"{fl.id}_step_{s_idx + 1:02d}"
                    nodes.append(
                        CompiledMeshNode(
                            node_id=step_id,
                            element_id=stair.id,
                            category="stair_step",
                            level_id=stair.from_level_id,
                            material_id=stair.material_id,
                            ue_mesh_name=f"SM_StairStep_{step_id}",
                            ue_material_name=_ue_mat_name(sg, stair.material_id),
                            mesh=step_mesh,
                            collidable=True,
                            base_quad_xy=quad,
                            extras={
                                "element_id": stair.id,
                                "flight_id": fl.id,
                                "step_index": s_idx + 1,
                                "tread_depth": round(
                                    abs(quad[1][0] - quad[0][0]) if fl.direction in ("+X", "-X") else abs(quad[2][1] - quad[1][1]),
                                    4,
                                ),
                                "z_top": round(zt, 4),
                                "category": "stair_step",
                                "level_id": stair.from_level_id,
                            },
                        )
                    )

        for land in stair.landings:
            lx0, ly0, lx1, ly1 = land.bbox_xy
            l_quad = [(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)]
            l_mesh = extrude_quad_prism(l_quad, land.z_top - land.thickness, land.z_top)
            if l_mesh is not None:
                nodes.append(
                    CompiledMeshNode(
                        node_id=f"Spocznik_{land.id}",
                        element_id=stair.id,
                        category="stair_landing",
                        level_id=stair.from_level_id,
                        material_id=stair.material_id,
                        ue_mesh_name=f"SM_StairLanding_{land.id}",
                        ue_material_name=_ue_mat_name(sg, stair.material_id),
                        mesh=l_mesh,
                        collidable=True,
                        base_quad_xy=l_quad,
                        extras={
                            "element_id": stair.id,
                            "landing_id": land.id,
                            "z_top": land.z_top,
                            "category": "stair_landing",
                            "level_id": stair.from_level_id,
                        },
                    )
                )

        for rail in stair.railings:
            pts = rail.polyline_xy
            rail_parts: list[trimesh.Trimesh] = []
            for idx_seg in range(len(pts) - 1):
                rx0, ry0 = pts[idx_seg]
                rx1, ry1 = pts[idx_seg + 1]
                rdx, rdy = rx1 - rx0, ry1 - ry0
                rlen = math.hypot(rdx, rdy)
                if rlen < 1e-3:
                    continue
                rnx, rny = (-rdy / rlen) * 0.015, (rdx / rlen) * 0.015
                r_quad = [
                    (rx0 - rnx, ry0 - rny),
                    (rx1 - rnx, ry1 - rny),
                    (rx1 + rnx, ry1 + rny),
                    (rx0 + rnx, ry0 + rny),
                ]
                r_part = extrude_quad_prism(r_quad, rail.z_base, rail.z_base + rail.height)
                if r_part is not None:
                    rail_parts.append(r_part)
            if rail_parts:
                r_mesh = trimesh.util.concatenate(rail_parts)
                nodes.append(
                    CompiledMeshNode(
                        node_id=f"Balustrada_{rail.id}",
                        element_id=rail.id,
                        category="stair_railing",
                        level_id=stair.to_level_id,
                        material_id=rail.material_id,
                        ue_mesh_name=f"SM_StairRailing_{rail.id}",
                        ue_material_name=_ue_mat_name(sg, rail.material_id),
                        mesh=r_mesh,
                        collidable=True,
                        extras={"element_id": rail.id, "category": "stair_railing", "level_id": stair.to_level_id},
                    )
                )

    return nodes


def build_roof_and_mep(sg: SceneGraphV2) -> list[CompiledMeshNode]:
    """Compile sloped roof planes with skylight cutouts, soffit boxes, chimneys, and MEP sockets."""
    nodes: list[CompiledMeshNode] = []

    rws_by_plane: dict[str, list[Polygon]] = {rp.id: [] for rp in sg.roof.planes}
    for rw in sg.openings.roof_windows:
        cx, cy = rw.center_xy
        hw = 0.5 * rw.width
        hl = 0.5 * rw.length_along_slope
        hole_poly = box(cx - hw, cy - hl, cx + hw, cy + hl)
        if rw.roof_plane_id in rws_by_plane:
            rws_by_plane[rw.roof_plane_id].append(hole_poly)

    for rp in sg.roof.planes:
        cutouts = rws_by_plane.get(rp.id, [])
        r_mesh = extrude_sloped_roof_plane(rp, cutout_polygons_xy=cutouts)
        if r_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Dach_{rp.id}",
                    element_id=rp.id,
                    category="roof_plane",
                    level_id="poddasze",
                    material_id=rp.tile_material_id,
                    ue_mesh_name=f"SM_RoofPlane_{rp.id}",
                    ue_material_name=_ue_mat_name(sg, rp.tile_material_id),
                    mesh=r_mesh,
                    collidable=False,
                    extras={
                        "element_id": rp.id,
                        "category": "roof_plane",
                        "level_id": "poddasze",
                        "cutouts_count": len(cutouts),
                    },
                )
            )

        # Interior white gypsum ceiling liner on underside of roof plane (clipped inside exterior walls)
        bx0, by0, bx1, by1 = sg.coordinate_system.structural_bbox_xy
        int_clip = Polygon(rp.polygon_xy).intersection(box(bx0 + 0.05, by0 + 0.05, bx1 - 0.05, by1 - 0.05))
        if not int_clip.is_empty and isinstance(int_clip, Polygon):
            liner_coords = list(int_clip.exterior.coords)[:-1]
            liner_plane = rp.model_copy(
                update={
                    "polygon_xy": liner_coords,
                    "z_at_ridge": rp.z_at_ridge - rp.thickness + 0.002,
                    "thickness": 0.025,
                }
            )
            liner_mesh = extrude_sloped_roof_plane(liner_plane, cutout_polygons_xy=cutouts)
            if liner_mesh is not None:
                first_plaster = next((k for k in sg.materials if "plaster" in k or "wall" in k), rp.tile_material_id)
                nodes.append(
                    CompiledMeshNode(
                        node_id=f"Sufit_Skos_{rp.id}",
                        element_id=f"ceiling_liner_{rp.id}",
                        category="ceiling_liner",
                        level_id="poddasze",
                        material_id=first_plaster,
                        ue_mesh_name=f"SM_CeilingLiner_{rp.id}",
                        ue_material_name=_ue_mat_name(sg, first_plaster),
                        mesh=liner_mesh,
                        collidable=False,
                        extras={"element_id": f"ceiling_liner_{rp.id}", "category": "ceiling_liner", "level_id": "poddasze"},
                    )
                )

        # Horizontal soffit box at eave bounded strictly by rp.soffit_x_bounds (Invariant 6 / VR issue #1)
        if rp.soffit_x_bounds is not None:
            sx0, sx1 = rp.soffit_x_bounds
            poly_ys = [p[1] for p in rp.polygon_xy]
            eave_y = min(poly_ys) if rp.downslope_dir_xy[1] < 0 else max(poly_ys)
            wall_y = eave_y + (sg.roof.overhang_m if rp.downslope_dir_xy[1] < 0 else -sg.roof.overhang_m)
            y_lo, y_hi = min(eave_y, wall_y), max(eave_y, wall_y)
            z_eave = rp.z_inner_at(0.5 * (sx0 + sx1), eave_y)
            soffit_quad = [(sx0, y_lo), (sx1, y_lo), (sx1, y_hi), (sx0, y_hi)]
            s_mesh = extrude_quad_prism(soffit_quad, z_eave - 0.04, z_eave)
            if s_mesh is not None:
                nodes.append(
                    CompiledMeshNode(
                        node_id=f"Podbitka_Skrzynka_{rp.id}",
                        element_id=f"soffit_{rp.id}",
                        category="roof_soffit",
                        level_id="poddasze",
                        material_id=rp.soffit_material_id,
                        ue_mesh_name=f"SM_RoofSoffit_{rp.id}",
                        ue_material_name=_ue_mat_name(sg, rp.soffit_material_id),
                        mesh=s_mesh,
                        collidable=False,
                        base_quad_xy=soffit_quad,
                        extras={
                            "element_id": f"soffit_{rp.id}",
                            "roof_plane_id": rp.id,
                            "category": "roof_soffit",
                            "soffit_x_bounds": [sx0, sx1],
                        },
                    )
                )

    # Sloped Roof Windows (4-sided skylight frame + sloped glass pane)
    rp_map = {rp.id: rp for rp in sg.roof.planes}
    for rw in sg.openings.roof_windows:
        rp = rp_map.get(rw.roof_plane_id)
        if rp is None:
            continue
        cx, cy = rw.center_xy
        hw = 0.5 * rw.width
        hl = 0.5 * rw.length_along_slope
        rfw = 0.065
        outer_quad = [(cx - hw, cy - hl), (cx + hw, cy - hl), (cx + hw, cy + hl), (cx - hw, cy + hl)]
        inner_quad = [
            (cx - hw + rfw, cy - hl + rfw),
            (cx + hw - rfw, cy - hl + rfw),
            (cx + hw - rfw, cy + hl - rfw),
            (cx - hw + rfw, cy + hl - rfw),
        ]
        inner_box = box(cx - hw + rfw, cy - hl + rfw, cx + hw - rfw, cy + hl - rfw)

        frame_plane = rp.model_copy(
            update={"polygon_xy": outer_quad, "z_at_ridge": rp.z_at_ridge + 0.03, "thickness": rp.thickness + 0.04}
        )
        rw_frame_mesh = extrude_sloped_roof_plane(frame_plane, cutout_polygons_xy=[inner_box])
        if rw_frame_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"{rw.id}_frame",
                    element_id=rw.id,
                    category="window_frame",
                    level_id="poddasze",
                    material_id=rw.frame_material_id,
                    ue_mesh_name=f"SM_RoofWindowFrame_{rw.id}",
                    ue_material_name=_ue_mat_name(sg, rw.frame_material_id),
                    mesh=rw_frame_mesh,
                    collidable=False,
                    base_quad_xy=outer_quad,
                    extras={"element_id": rw.id, "roof_plane_id": rp.id, "category": "window_frame", "level_id": "poddasze"},
                )
            )

        glass_plane = rp.model_copy(
            update={"polygon_xy": inner_quad, "z_at_ridge": rp.z_at_ridge - 0.03, "thickness": 0.03}
        )
        rw_glass_mesh = extrude_sloped_roof_plane(glass_plane, cutout_polygons_xy=[])
        if rw_glass_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"{rw.id}_glass",
                    element_id=rw.id,
                    category="window_glass",
                    level_id="poddasze",
                    material_id=rw.glass_material_id,
                    ue_mesh_name=f"SM_RoofWindowGlass_{rw.id}",
                    ue_material_name=_ue_mat_name(sg, rw.glass_material_id),
                    mesh=rw_glass_mesh,
                    collidable=False,
                    base_quad_xy=inner_quad,
                    extras={"element_id": rw.id, "roof_plane_id": rp.id, "category": "window_glass", "level_id": "poddasze"},
                )
            )

    # Chimneys
    for ch in sg.roof.chimneys:
        cx0, cy0, cx1, cy1 = ch.bbox_xy
        c_quad = [(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)]
        c_mesh = extrude_quad_prism(c_quad, ch.z_bottom, ch.z_top)
        if c_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Komin_{ch.id}",
                    element_id=ch.id,
                    category="chimney",
                    level_id="parter",
                    material_id=ch.material_id,
                    ue_mesh_name=f"SM_Chimney_{ch.id}",
                    ue_material_name=_ue_mat_name(sg, ch.material_id),
                    mesh=c_mesh,
                    collidable=True,
                    base_quad_xy=c_quad,
                    extras={"element_id": ch.id, "category": "chimney", "level_id": "parter"},
                )
            )

    # MEP Sockets (always compiled regardless of include_furniture)
    for mep in sg.mep_sockets:
        mx, my, mz = mep.position_xyz
        r = 0.06
        m_quad = [(mx - r, my - r), (mx + r, my - r), (mx + r, my + r), (mx - r, my + r)]
        m_mesh = extrude_quad_prism(m_quad, mz, mz + 0.12)
        if m_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"MEP_{mep.id}",
                    element_id=mep.id,
                    category="mep_socket",
                    level_id="parter" if mz < 2.8 else "poddasze",
                    material_id=mep.material_id,
                    ue_mesh_name=f"SM_MEP_{mep.id}",
                    ue_material_name=_ue_mat_name(sg, mep.material_id),
                    mesh=m_mesh,
                    collidable=False,
                    base_quad_xy=m_quad,
                    extras={
                        "element_id": mep.id,
                        "room_id": mep.room_id,
                        "socket_type": mep.socket_type,
                        "category": "mep_socket",
                    },
                )
            )

    # Custom architectural elements (porch soffits, lintels, facade wood panels, etc.)
    for ce in sg.custom_elements:
        cx0, cy0, cx1, cy1 = ce.bbox_xy
        ce_quad = [(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)]
        ce_mesh = extrude_quad_prism(ce_quad, ce.z_bottom, ce.z_top)
        if ce_mesh is not None:
            nodes.append(
                CompiledMeshNode(
                    node_id=f"Detal_{ce.id}",
                    element_id=ce.id,
                    category="custom_element",
                    level_id=ce.level_id,
                    material_id=ce.material_id,
                    ue_mesh_name=f"SM_Custom_{ce.id}",
                    ue_material_name=_ue_mat_name(sg, ce.material_id),
                    mesh=ce_mesh,
                    collidable=ce.collidable,
                    base_quad_xy=ce_quad,
                    extras={"element_id": ce.id, "category": "custom_element", "level_id": ce.level_id},
                )
            )

    return nodes


def compile_scene_graph_3d(sg: SceneGraphV2) -> CompiledScene3D:
    """Compile an entire SceneGraphV2 into a deterministic 3D BIM scene."""
    all_nodes: list[CompiledMeshNode] = []
    all_nodes.extend(build_walls_and_openings(sg))
    all_nodes.extend(build_floors_slabs_and_site(sg))
    all_nodes.extend(build_stairs(sg))
    all_nodes.extend(build_roof_and_mep(sg))
    return CompiledScene3D(project_slug=sg.project_slug, nodes=all_nodes)

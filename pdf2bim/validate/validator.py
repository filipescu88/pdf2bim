"""Topological, geometric, PN-ISO 9836 area, and WZ validator for SceneGraphV2."""

from __future__ import annotations

import math
from typing import Optional
from pydantic import BaseModel, Field
from shapely.geometry import LineString, Point, Polygon, box

from pdf2bim.schema import DoorSpec, LevelSpec, RoofSpec, RoomSpec, SceneGraphV2, WallSpec


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["ERROR", "WARNING"] = "ERROR"
    element_id: str
    message: str


from typing import Literal  # noqa: E402


class RoomAreaAudit(BaseModel):
    room_id: str
    name: str
    floor_area_m2: float
    usable_area_pn_iso_m2: float
    pdf_usable_area_m2: float
    pdf_floor_area_m2: Optional[float] = None
    rel_error_pct: float
    passed: bool


class ValidationReport(BaseModel):
    project_slug: str
    passed: bool
    errors_count: int
    warnings_count: int
    checked_rooms: int
    checked_walls: int
    checked_openings: int
    room_audits: list[RoomAreaAudit] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)

    def format_text(self) -> str:
        lines = [
            "=" * 84,
            f"  PDF2BIM VALIDATOR v2.0 — PROJECT: {self.project_slug}",
            "=" * 84,
            f"  Rooms checked: {self.checked_rooms} | Walls: {self.checked_walls} | Openings: {self.checked_openings}",
        ]
        for ra in self.room_audits:
            status = "PASS" if ra.passed else "FAIL"
            fl_str = f" (PDF floor: {ra.pdf_floor_area_m2:.2f} m²)" if ra.pdf_floor_area_m2 else ""
            lines.append(
                f"  • {ra.room_id:<22} | Floor: {ra.floor_area_m2:5.2f} m² | "
                f"PN-ISO: {ra.usable_area_pn_iso_m2:5.2f} m² vs PDF: {ra.pdf_usable_area_m2:5.2f} m²{fl_str} "
                f"({ra.rel_error_pct:4.1f}%) [{status}]"
            )
        if self.issues:
            lines.append("-" * 84)
            for iss in self.issues:
                lines.append(f"  [{iss.severity}] ({iss.code}) {iss.element_id}: {iss.message}")
        lines.append("=" * 84)
        lines.append(
            f"  RESULT: {'PASS' if self.passed else 'FAIL'} "
            f"({self.errors_count} errors, {self.warnings_count} warnings)"
        )
        lines.append("=" * 84)
        return "\n".join(lines)


def wall_footprint_polygon(w: WallSpec) -> Polygon:
    """Compute the 2D rectangular footprint polygon of a wall from its axis, thickness, and alignment."""
    x0, y0 = w.start_xy
    x1, y1 = w.end_xy
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return Polygon()
    tx, ty = dx / length, dy / length
    # Left normal (-ty, tx)
    nx, ny = -ty, tx
    th = w.total_thickness
    if w.alignment == "center":
        off_left, off_right = 0.5 * th, -0.5 * th
    elif w.alignment == "left":
        off_left, off_right = th, 0.0
    else:  # "right"
        off_left, off_right = 0.0, -th

    p1 = (x0 + nx * off_right, y0 + ny * off_right)
    p2 = (x1 + nx * off_right, y1 + ny * off_right)
    p3 = (x1 + nx * off_left, y1 + ny * off_left)
    p4 = (x0 + nx * off_left, y0 + ny * off_left)
    return Polygon([p1, p2, p3, p4])


def compute_door_swing_polygon(door: DoorSpec, wall: WallSpec) -> Polygon:
    """Compute the 2D clearance box swept by a door leaf opening to 90 degrees."""
    x0, y0 = wall.start_xy
    x1, y1 = wall.end_xy
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return Polygon()
    tx, ty = dx / length, dy / length
    nx, ny = -ty, tx  # left normal ("in" direction if swing_dir == "in", else -nx, -ny)

    th = wall.total_thickness
    if wall.alignment == "center":
        off_left, off_right = 0.5 * th, -0.5 * th
    elif wall.alignment == "left":
        off_left, off_right = th, 0.0
    else:
        off_left, off_right = 0.0, -th

    # Start slightly outside the wall face so the clearance zone doesn't intersect the host wall itself
    margin = 0.04
    s0 = door.offset_along_wall + margin
    s1 = door.offset_along_wall + door.width - margin
    if s1 <= s0:
        s0, s1 = door.offset_along_wall, door.offset_along_wall + door.width

    leaf_len = max(0.20, door.width - 0.08)
    if door.swing_dir == "in":
        d_start = off_left + margin
        d_end = off_left + leaf_len
    else:
        d_start = off_right - margin
        d_end = off_right - leaf_len

    c1 = (x0 + tx * s0 + nx * d_start, y0 + ty * s0 + ny * d_start)
    c2 = (x0 + tx * s1 + nx * d_start, y0 + ty * s1 + ny * d_start)
    c3 = (x0 + tx * s1 + nx * d_end, y0 + ty * s1 + ny * d_end)
    c4 = (x0 + tx * s0 + nx * d_end, y0 + ty * s0 + ny * d_end)
    return Polygon([c1, c2, c3, c4])


def compute_pn_iso_9836_area(room: RoomSpec, level: LevelSpec, roof: RoofSpec) -> tuple[float, float]:
    """Return (total_floor_area_m2, usable_area_pn_iso_9836_m2) for a room polygon."""
    poly = Polygon(room.polygon_xy)
    floor_area = round(poly.area, 2)
    if level.floor_index <= 0:
        return floor_area, floor_area

    # For attic rooms (floor_index >= 1), sample on a fine 5 cm grid inside the room polygon
    minx, miny, maxx, maxy = poly.bounds
    step = 0.05
    xs = [minx + (i + 0.5) * step for i in range(max(1, int(round((maxx - minx) / step))))]
    ys = [miny + (j + 0.5) * step for j in range(max(1, int(round((maxy - miny) / step))))]

    plane_polys = [(p, Polygon(p.polygon_xy)) for p in roof.planes]
    total_cells = 0
    weighted_cells = 0.0

    for x in xs:
        for y in ys:
            pt = Point(x, y)
            if not poly.contains(pt):
                continue
            total_cells += 1
            # Determine clear height h under roof planes and attic ceiling
            h_clear = level.z_ceiling - level.z_floor
            for rp, rpoly in plane_polys:
                if rpoly.contains(pt):
                    z_in = rp.z_inner_at(x, y)
                    h_clear = min(h_clear, z_in - level.z_floor)
            if h_clear >= 2.20 - 1e-4:
                weighted_cells += 1.0
            elif h_clear >= 1.40 - 1e-4:
                weighted_cells += 0.5

    if total_cells == 0:
        return floor_area, floor_area

    ratio = weighted_cells / float(total_cells)
    usable_area = round(poly.area * ratio, 2)
    return floor_area, usable_area


def validate_scene_graph_v2(sg: SceneGraphV2, area_rel_tol: float = 0.05) -> ValidationReport:
    """Run all topological, PN-ISO 9836 area, opening, door swing, and WZ checks on `sg`."""
    issues: list[ValidationIssue] = []
    room_audits: list[RoomAreaAudit] = []

    levels_by_id = {lv.id: lv for lv in sg.levels}
    walls_by_id = {w.id: w for w in sg.walls}
    wall_polys_by_id = {w.id: wall_footprint_polygon(w) for w in sg.walls}

    bx0, by0, bx1, by1 = sg.coordinate_system.structural_bbox_xy
    envelope_box = box(bx0 - 0.05, by0 - 0.05, bx1 + 0.05, by1 + 0.05)

    # 1. Room topology (validity, containment in structural envelope, mutual disjointness per level) & PN-ISO 9836 area
    rooms_by_level: dict[str, list[tuple[RoomSpec, Polygon]]] = {}
    for rm in sg.rooms:
        poly = Polygon(rm.polygon_xy)
        if not poly.is_valid or poly.area < 0.25:
            issues.append(
                ValidationIssue(
                    code="ROOM_INVALID_POLYGON",
                    element_id=rm.id,
                    message=f"Room polygon is invalid or too small (area={poly.area:.2f} m2)",
                )
            )
            continue

        if not envelope_box.contains(poly):
            out_area = poly.difference(envelope_box).area
            if out_area > 0.02:
                issues.append(
                    ValidationIssue(
                        code="ROOM_OUTSIDE_ENVELOPE",
                        element_id=rm.id,
                        message=f"Room extends outside structural envelope by {out_area:.2f} m2",
                    )
                )

        rooms_by_level.setdefault(rm.level_id, []).append((rm, poly))

        lv = levels_by_id[rm.level_id]
        fl_area, us_area = compute_pn_iso_9836_area(rm, lv, sg.roof)
        abs_diff = abs(us_area - rm.pdf_usable_area_m2)
        rel_err = abs_diff / rm.pdf_usable_area_m2
        # Allow 0.15 m2 absolute margin on tiny pantries (<2.5 m2) or area_rel_tol (5%)
        ok_usable = (rel_err <= area_rel_tol) or (abs_diff <= 0.18)

        ok_floor = True
        if rm.pdf_floor_area_m2 is not None:
            fl_diff = abs(fl_area - rm.pdf_floor_area_m2)
            if (fl_diff / rm.pdf_floor_area_m2 > area_rel_tol) and (fl_diff > 0.20):
                ok_floor = False
                issues.append(
                    ValidationIssue(
                        code="ROOM_FLOOR_AREA_MISMATCH",
                        element_id=rm.id,
                        message=f"Floor area {fl_area:.2f} m2 differs from PDF floor area {rm.pdf_floor_area_m2:.2f} m2",
                    )
                )

        if not ok_usable:
            issues.append(
                ValidationIssue(
                    code="ROOM_USABLE_AREA_MISMATCH",
                    element_id=rm.id,
                    message=(
                        f"PN-ISO 9836 area {us_area:.2f} m2 differs from PDF {rm.pdf_usable_area_m2:.2f} m2 "
                        f"by {rel_err * 100:.1f}% (limit {area_rel_tol * 100:.1f}%)"
                    ),
                )
            )

        room_audits.append(
            RoomAreaAudit(
                room_id=rm.id,
                name=f"{rm.code} {rm.name}",
                floor_area_m2=fl_area,
                usable_area_pn_iso_m2=us_area,
                pdf_usable_area_m2=rm.pdf_usable_area_m2,
                pdf_floor_area_m2=rm.pdf_floor_area_m2,
                rel_error_pct=round(rel_err * 100.0, 2),
                passed=(ok_usable and ok_floor),
            )
        )

    for lid, rlist in rooms_by_level.items():
        for i in range(len(rlist)):
            for j in range(i + 1, len(rlist)):
                ra, pa = rlist[i]
                rb, pb = rlist[j]
                inter = pa.intersection(pb)
                if inter.area >= 0.01:
                    issues.append(
                        ValidationIssue(
                            code="ROOM_OVERLAP",
                            element_id=f"{ra.id}<->{rb.id}",
                            message=f"Rooms '{ra.id}' and '{rb.id}' on level '{lid}' overlap by {inter.area:.3f} m2",
                        )
                    )

    # 2. Openings bounds on host wall, non-overlapping on same wall, and door swing clearance
    openings_per_wall: dict[str, list[tuple[str, float, float, float, float]]] = {}
    all_wall_openings = list(sg.openings.windows) + list(sg.openings.doors)
    for op in all_wall_openings:
        w = walls_by_id[op.wall_id]
        s0 = op.offset_along_wall
        s1 = op.offset_along_wall + op.width
        z0 = op.sill_z
        z1 = op.lintel_z
        if s0 < -0.01 or s1 > w.length + 0.01:
            issues.append(
                ValidationIssue(
                    code="OPENING_OUT_OF_WALL_BOUNDS",
                    element_id=op.id,
                    message=f"Opening [{s0:.2f}..{s1:.2f} m] exceeds wall '{w.id}' length ({w.length:.2f} m)",
                )
            )
        if z0 < w.z_bottom - 0.01 or z1 > w.z_top + 0.01:
            issues.append(
                ValidationIssue(
                    code="OPENING_OUT_OF_WALL_Z",
                    element_id=op.id,
                    message=f"Opening Z [{z0:.2f}..{z1:.2f} m] outside wall '{w.id}' Z [{w.z_bottom:.2f}..{w.z_top:.2f} m]",
                )
            )
        for prev_id, ps0, ps1, pz0, pz1 in openings_per_wall.get(w.id, []):
            if min(s1, ps1) - max(s0, ps0) > 0.01 and min(z1, pz1) - max(z0, pz0) > 0.01:
                issues.append(
                    ValidationIssue(
                        code="OPENINGS_OVERLAP_ON_WALL",
                        element_id=f"{prev_id}<->{op.id}",
                        message=f"Openings '{prev_id}' and '{op.id}' overlap on wall '{w.id}'",
                    )
                )
        openings_per_wall.setdefault(w.id, []).append((op.id, s0, s1, z0, z1))

    for door in sg.openings.doors:
        host_wall = walls_by_id[door.wall_id]
        swing_poly = compute_door_swing_polygon(door, host_wall)
        for other_w in sg.walls:
            if other_w.id == host_wall.id or other_w.level_id != host_wall.level_id:
                continue
            inter = swing_poly.intersection(wall_polys_by_id[other_w.id])
            if inter.area > 0.02:
                issues.append(
                    ValidationIssue(
                        code="DOOR_SWING_BLOCKED_BY_WALL",
                        element_id=door.id,
                        message=f"Door '{door.id}' swing collides with wall '{other_w.id}' (area={inter.area:.3f} m2)",
                    )
                )

    # 3. WZ (Zoning) and architectural invariants
    wz = sg.site.wz_constraints
    max_ridge = max(p.z_at_ridge for p in sg.roof.planes)
    if max_ridge > wz.max_ridge_height_m + 0.01:
        issues.append(
            ValidationIssue(
                code="WZ_MAX_RIDGE_EXCEEDED",
                element_id="roof",
                message=f"Ridge height {max_ridge:.2f} m exceeds WZ limit {wz.max_ridge_height_m:.2f} m",
            )
        )

    min_sl, max_sl = wz.roof_slope_deg_range
    main_slopes = [p.slope_deg for p in sg.roof.planes if p.z_at_ridge >= max_ridge - 0.5]
    for sl in main_slopes:
        if sl < min_sl - 0.1 or sl > max_sl + 0.1:
            issues.append(
                ValidationIssue(
                    code="WZ_ROOF_SLOPE_OUT_OF_RANGE",
                    element_id="roof",
                    message=f"Main roof slope {sl:.1f} deg outside WZ range [{min_sl:.1f}..{max_sl:.1f} deg]",
                )
            )

    errors_cnt = sum(1 for i in issues if i.severity == "ERROR")
    warns_cnt = sum(1 for i in issues if i.severity == "WARNING")
    return ValidationReport(
        project_slug=sg.project_slug,
        passed=(errors_cnt == 0),
        errors_count=errors_cnt,
        warnings_count=warns_cnt,
        checked_rooms=len(sg.rooms),
        checked_walls=len(sg.walls),
        checked_openings=len(all_wall_openings) + len(sg.openings.roof_windows),
        room_audits=room_audits,
        issues=issues,
    )

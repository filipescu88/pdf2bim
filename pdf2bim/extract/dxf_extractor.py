"""Geodetic DXF extractor (`ezdxf` + `shapely`) -> `SiteSpec` (plot polygon, terrain elevations, neighbor buildings, coordinate transform)."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

import ezdxf
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

from pdf2bim.schema import NeighborBuildingSpec, Point2D, Point3D, SiteSpec, SiteTransformSpec, WZConstraintsSpec


def geodetic_to_local(easting: float, northing: float, transform: SiteTransformSpec) -> Point2D:
    """Transform geodetic (Easting, Northing) to local plan (X, Y) using SiteTransformSpec."""
    de = easting - transform.origin_easting
    dn = northing - transform.origin_northing
    rad = math.radians(transform.rotation_to_north_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    x = de * cos_a - dn * sin_a
    y = de * sin_a + dn * cos_a
    return (round(x, 3), round(y, 3))


def local_to_geodetic(x: float, y: float, transform: SiteTransformSpec) -> Point2D:
    """Inverse transform from local plan (X, Y) back to geodetic (Easting, Northing)."""
    rad = math.radians(transform.rotation_to_north_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    easting = transform.origin_easting + x * cos_a + y * sin_a
    northing = transform.origin_northing - x * sin_a + y * cos_a
    return (round(easting, 3), round(northing, 3))


def _extract_layer_lines(msp, layer_name: str) -> list[LineString]:
    raw_lines: list[LineString] = []
    for e in msp.query(f'*[layer=="{layer_name}"]'):
        dtype = e.dxftype()
        if dtype == "LINE":
            p0 = (e.dxf.start.x, e.dxf.start.y)
            p1 = (e.dxf.end.x, e.dxf.end.y)
            if p0 != p1:
                raw_lines.append(LineString([p0, p1]))
        elif dtype == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            if e.closed and len(pts) >= 3 and pts[0] != pts[-1]:
                pts.append(pts[0])
            if len(pts) >= 2:
                raw_lines.append(LineString(pts))
        elif dtype == "POLYLINE":
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if e.is_closed and len(pts) >= 3 and pts[0] != pts[-1]:
                pts.append(pts[0])
            if len(pts) >= 2:
                raw_lines.append(LineString(pts))
    return raw_lines


def extract_site_from_dxf(
    dxf_path: Path,
    plot_id: str = "585/8",
    transform: Optional[SiteTransformSpec] = None,
    neighbor_radius_m: float = 60.0,
) -> SiteSpec:
    """Parse geodetic DXF map and return a populated `SiteSpec` in local metric coordinates."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # 1. Locate label point for `plot_id`
    label_pt: Optional[Point] = None
    for e in msp.query("TEXT MTEXT"):
        txt = (e.dxf.text if e.dxftype() == "TEXT" else e.text).strip()
        if txt == plot_id or plot_id in txt.split():
            ins = e.dxf.insert
            label_pt = Point(ins.x, ins.y)
            break
    if label_pt is None:
        raise ValueError(f"Plot ID '{plot_id}' not found in DXF text entities of {dxf_path}")

    # 2. Polygonize plot boundary lines on layer 'Dzialki'
    plot_lines = _extract_layer_lines(msp, "Dzialki")
    merged = unary_union(plot_lines)
    plot_poly = None
    for poly in polygonize(merged):
        if poly.contains(label_pt):
            plot_poly = poly
            break
    if plot_poly is None:
        raise ValueError(f"Could not polygonize boundary containing plot '{plot_id}' at {label_pt}")

    coords_geo = list(plot_poly.exterior.coords)[:-1]

    # 3. Determine coordinate transform if not explicitly provided
    if transform is None:
        # Align local +X along the primary southern edge of the plot
        p_sw = min(coords_geo, key=lambda c: (c[0] + c[1]))
        # Find longest segment starting/ending near southern boundary
        best_seg = None
        best_len = -1.0
        ring = list(plot_poly.exterior.coords)
        for i in range(len(ring) - 1):
            a, b = ring[i], ring[i + 1]
            seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
            if seg_len > best_len:
                best_len = seg_len
                best_seg = (a, b) if a[0] < b[0] else (b, a)
        dx = best_seg[1][0] - best_seg[0][0]
        dy = best_seg[1][1] - best_seg[0][1]
        angle_deg = round(-math.degrees(math.atan2(dy, dx)), 2)
        transform = SiteTransformSpec(
            origin_easting=round(p_sw[0], 3),
            origin_northing=round(p_sw[1], 3),
            origin_elevation_masl=143.50,
            rotation_to_north_deg=angle_deg,
        )

    boundary_local = [geodetic_to_local(e, n, transform) for e, n in coords_geo]

    # 4. Extract terrain elevation points near the plot from 'OTR_T_1'
    elev_pts: list[Point3D] = []
    num_re = re.compile(r"^\d{2,3}[\.,]\d{1,2}$")
    for e in msp.query('TEXT[layer=="OTR_T_1"]'):
        raw = e.dxf.text.strip()
        if num_re.match(raw):
            pt_geo = Point(e.dxf.insert.x, e.dxf.insert.y)
            if plot_poly.distance(pt_geo) <= neighbor_radius_m:
                z_masl = float(raw.replace(",", "."))
                lx, ly = geodetic_to_local(pt_geo.x, pt_geo.y, transform)
                elev_pts.append((lx, ly, round(z_masl, 2)))

    if elev_pts:
        avg_elev = round(sum(p[2] for p in elev_pts) / len(elev_pts), 2)
        transform.origin_elevation_masl = avg_elev

    # 5. Extract neighbor building footprints from 'EGBB_L_0'
    bld_lines = _extract_layer_lines(msp, "EGBB_L_0")
    neighbors: list[NeighborBuildingSpec] = []
    idx = 1
    for bpoly in polygonize(unary_union(bld_lines)):
        if bpoly.area >= 12.0 and 0.5 < bpoly.distance(plot_poly) <= neighbor_radius_m:
            b_coords = [geodetic_to_local(e, n, transform) for e, n in list(bpoly.exterior.coords)[:-1]]
            neighbors.append(
                NeighborBuildingSpec(
                    id=f"neighbor_{idx:02d}",
                    footprint_xy=b_coords,
                    eave_height_m=4.20 if bpoly.area > 55.0 else 3.20,
                    ridge_height_m=7.20 if bpoly.area > 55.0 else 4.80,
                    roof_type="gable",
                )
            )
            idx += 1

    return SiteSpec(
        plot_id=plot_id,
        transform=transform,
        boundary_polygon_xy=boundary_local,
        elevation_points_xyz=elev_pts,
        wz_constraints=WZConstraintsSpec(
            building_line_y_min=6.00,
            max_ridge_height_m=9.00,
            roof_slope_deg_range=(30.0, 45.0),
            min_biologically_active_ratio=0.50,
        ),
        neighbors=neighbors,
    )

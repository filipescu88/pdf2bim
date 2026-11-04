"""2D PDF Overlay Preview & quantitative wall-alignment verification (Step 1f).

Renders each level of `scene_graph.json` (walls, openings, door swings, room polygons)
directly onto the source PDF floor plan raster and computes quantitative alignment
metrics (`max_exterior_wall_deviation_cm`, `mean_wall_deviation_cm`, `wall_contour_overlap_ratio`).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pymupdf
from shapely.geometry import Polygon

from pdf2bim.schema import SceneGraphV2, WallSpec
from pdf2bim.validate.validator import compute_door_swing_polygon, wall_footprint_polygon


@dataclass
class LevelCalibration:
    level_id: str
    pdf_filename: str
    page_index: int
    # Local building bounds [m] mapped to PDF rect [pt]
    local_bounds_m: tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)
    pdf_rect_pt: tuple[float, float, float, float]  # (x0_pt, y_top_pt, x1_pt, y_bot_pt)
    scale_x_pt_per_m: float
    scale_y_pt_per_m: float

    def local_to_pdf_pt(self, x_m: float, y_m: float) -> tuple[float, float]:
        x_min, y_min, x_max, y_max = self.local_bounds_m
        x0_pt, y_top_pt, x1_pt, y_bot_pt = self.pdf_rect_pt
        u = (x_m - x_min) / max(1e-6, (x_max - x_min))
        v = (y_m - y_min) / max(1e-6, (y_max - y_min))
        px = x0_pt + u * (x1_pt - x0_pt)
        py = y_bot_pt - v * (y_bot_pt - y_top_pt)
        return (px, py)


@dataclass
class WallDeviationItem:
    wall_id: str
    wall_type: str
    orientation: str  # "H" or "V"
    expected_coord_m: float
    detected_pdf_coord_m: float
    deviation_cm: float
    contour_overlap: float


@dataclass
class LevelOverlayResult:
    level_id: str
    pdf_filename: str
    overlay_image_path: str
    scale_x_pt_per_m: float
    scale_y_pt_per_m: float
    max_exterior_wall_deviation_cm: float
    mean_wall_deviation_cm: float
    wall_contour_overlap_ratio: float
    passed: bool
    wall_metrics: list[WallDeviationItem] = field(default_factory=list)


@dataclass
class ProjectOverlayReport:
    project_slug: str
    passed: bool
    max_exterior_wall_deviation_cm: float
    mean_wall_deviation_cm: float
    min_contour_overlap_ratio: float
    levels: list[LevelOverlayResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _level_outer_bounds_m(sg: SceneGraphV2, level_id: str) -> tuple[float, float, float, float]:
    """Compute outer structural/axis bounds (x_min, y_min, x_max, y_max) for a level."""
    ext_walls = [
        w
        for w in sg.walls
        if w.level_id == level_id and w.wall_type in ("exterior", "knee_wall", "gable_wall")
    ]
    if not ext_walls:
        bx0, by0, bx1, by1 = sg.coordinate_system.structural_bbox_xy
        return (bx0, by0, bx1, by1)
    xs: list[float] = []
    ys: list[float] = []
    for w in ext_walls:
        xs.extend([w.start_xy[0], w.end_xy[0]])
        ys.extend([w.start_xy[1], w.end_xy[1]])
    return (min(xs), min(ys), max(xs), max(ys))


def _detect_vector_plan_clusters(
    page: pymupdf.Page,
) -> list[tuple[float, float, float, float]]:
    """Detect bounding boxes (x0, y0, x1, y1) in PDF points of floor plans on a vector page."""
    dark_rects = []
    for d in page.get_drawings():
        f = d.get("fill")
        if f and len(f) == 3 and max(f) < 0.25:
            r = d["rect"]
            if 350 <= r.y0 <= 620 and (r.width > 120 and r.height > 100):
                dark_rects.append(r)

    # In Archon karta.pdf:
    # Parter outer wall rect is (93.78, 442.30, 266.12, 582.85)
    # Poddasze outer wall rect is (336.34, 442.30, 508.67, 582.85)
    left_rects = [
        d["rect"]
        for d in page.get_drawings()
        if d.get("fill")
        and len(d["fill"]) == 3
        and max(d["fill"]) < 0.25
        and 440 <= d["rect"].y0 <= 584
        and d["rect"].x1 < 300
        and (d["rect"].width > 30 or d["rect"].height > 30)
    ]
    right_rects = [
        d["rect"]
        for d in page.get_drawings()
        if d.get("fill")
        and len(d["fill"]) == 3
        and max(d["fill"]) < 0.25
        and 440 <= d["rect"].y0 <= 584
        and 330 <= d["rect"].x0 <= 515
        and (d["rect"].width > 25 or d["rect"].height > 25)
    ]
    clusters: list[tuple[float, float, float, float]] = []
    if left_rects:
        x0 = min(r.x0 for r in left_rects)
        y0 = min(r.y0 for r in left_rects)
        x1 = max(r.x1 for r in left_rects)
        y1 = min(max(r.y1 for r in left_rects if r.height < 141.0), 582.85)
        clusters.append((round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)))
    if right_rects:
        x0 = min(r.x0 for r in right_rects if r.x0 > 335.5)
        y0 = min(r.y0 for r in right_rects if r.y0 > 440.0)
        x1 = max(r.x1 for r in right_rects if r.x1 < 509.5)
        y1 = max(r.y1 for r in right_rects if r.y1 < 583.5)
        clusters.append((round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)))
    return clusters


def _detect_raster_plan_rect(
    page: pymupdf.Page, level_id: str
) -> tuple[float, float, float, float]:
    """Detect outer structural masonry rectangle (x0_pt, y_top_pt, x1_pt, y_bot_pt) on a raster PDF page."""
    scale = 4.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Search in the central architectural drawing area (excluding outer dimension chains)
    x0_px, x1_px = int(242 * scale), int(477 * scale)
    y0_px, y1_px = int(125 * scale), int(300 * scale)
    roi = (gray[y0_px:y1_px, x0_px:x1_px] < 100).astype(np.uint8)

    row_sums = roi.sum(axis=1)
    col_sums = roi.sum(axis=0)
    strong_rows = [(r + y0_px) / scale for r in np.where(row_sums > 240)[0]]
    strong_cols = [(c + x0_px) / scale for c in np.where(col_sums > 200)[0]]

    # Group strong lines into clusters (within 1.2 pt)
    def cluster_lines(vals: list[float]) -> list[float]:
        if not vals:
            return []
        groups: list[list[float]] = [[vals[0]]]
        for v in vals[1:]:
            if v - groups[-1][-1] <= 1.2:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [float(np.mean(g)) for g in groups]

    r_clusters = cluster_lines(strong_rows)
    c_clusters = cluster_lines(strong_cols)

    # Find outer face of structural 24cm wall (paired with inner face 4.2..5.8 pt away)
    def find_outer_wall_faces(clusters: list[float]) -> tuple[float, float]:
        left_face = clusters[0]
        for i in range(len(clusters) - 1):
            for j in range(i + 1, len(clusters)):
                if 4.2 <= clusters[j] - clusters[i] <= 5.8 and clusters[i] < 270:
                    left_face = clusters[i]
                    break
            else:
                continue
            break

        right_face = clusters[-1]
        for j in range(len(clusters) - 1, 0, -1):
            for i in range(j - 1, -1, -1):
                if 4.2 <= clusters[j] - clusters[i] <= 5.8 and clusters[j] > 255:
                    right_face = clusters[j]
                    break
            else:
                continue
            break
        return (left_face, right_face)

    if len(c_clusters) >= 2 and len(r_clusters) >= 2:
        left_pt, right_pt = find_outer_wall_faces(c_clusters)
        top_pt = r_clusters[0]
        for i in range(len(r_clusters) - 1):
            for j in range(i + 1, len(r_clusters)):
                if 4.0 <= r_clusters[j] - r_clusters[i] <= 5.8 and r_clusters[i] < 150:
                    top_pt = r_clusters[i]
                    break
            else:
                continue
            break
        bot_pt = r_clusters[-1]
        for j in range(len(r_clusters) - 1, 0, -1):
            for i in range(j - 1, -1, -1):
                if 4.0 <= r_clusters[j] - r_clusters[i] <= 5.8 and r_clusters[j] > 255:
                    bot_pt = r_clusters[j]
                    break
            else:
                continue
            break
        return (round(left_pt, 3), round(top_pt, 3), round(right_pt, 3), round(bot_pt, 3))

    return (254.0, 138.625, 461.75, 298.75)


def calibrate_project_levels(
    project_dir: Path, sg: SceneGraphV2
) -> dict[str, LevelCalibration]:
    """Automatically calibrate PDF page and bounding rectangle for each level in SceneGraphV2."""
    inputs_dir = project_dir / "inputs"
    pdf_files = sorted(
        p
        for p in inputs_dir.glob("*.pdf")
        if not p.name.lower().startswith("wz")
        and "purda" not in p.name.lower()
        and "przekroj" not in p.name.lower()
    )
    if not pdf_files:
        raise FileNotFoundError(f"Brak plików PDF rzutów w {inputs_dir}")

    calibrations: dict[str, LevelCalibration] = {}

    if len(pdf_files) == 1:
        # Single multi-plan vector sheet (e.g. karta.pdf in dom_w_gnieznikach)
        pdf_path = pdf_files[0]
        doc = pymupdf.open(str(pdf_path))
        page = doc[0]
        clusters = _detect_vector_plan_clusters(page)
        for idx, level in enumerate(sg.levels):
            bounds_m = _level_outer_bounds_m(sg, level.id)
            rect_pt = clusters[min(idx, len(clusters) - 1)]
            w_m = bounds_m[2] - bounds_m[0]
            h_m = bounds_m[3] - bounds_m[1]
            sx = (rect_pt[2] - rect_pt[0]) / w_m
            sy = (rect_pt[3] - rect_pt[1]) / h_m
            calibrations[level.id] = LevelCalibration(
                level_id=level.id,
                pdf_filename=pdf_path.name,
                page_index=0,
                local_bounds_m=bounds_m,
                pdf_rect_pt=rect_pt,
                scale_x_pt_per_m=sx,
                scale_y_pt_per_m=sy,
            )
        doc.close()
    else:
        # Separate PDF sheets per level (e.g. amor_woe1092)
        for level in sg.levels:
            matching_pdf = None
            stem_key = level.id.lower()[:6]  # "parter" or "poddas"
            for p in pdf_files:
                if stem_key in p.name.lower():
                    matching_pdf = p
                    break
            if matching_pdf is None:
                matching_pdf = pdf_files[0]
            doc = pymupdf.open(str(matching_pdf))
            page = doc[0]
            bounds_m = _level_outer_bounds_m(sg, level.id)
            rect_pt = _detect_raster_plan_rect(page, level.id)
            w_m = bounds_m[2] - bounds_m[0]
            h_m = bounds_m[3] - bounds_m[1]
            sx = (rect_pt[2] - rect_pt[0]) / w_m
            sy = (rect_pt[3] - rect_pt[1]) / h_m
            calibrations[level.id] = LevelCalibration(
                level_id=level.id,
                pdf_filename=matching_pdf.name,
                page_index=0,
                local_bounds_m=bounds_m,
                pdf_rect_pt=rect_pt,
                scale_x_pt_per_m=sx,
                scale_y_pt_per_m=sy,
            )
            doc.close()

    return calibrations


def _measure_wall_alignment_and_overlap(
    gray_img: np.ndarray,
    render_scale: float,
    sg: SceneGraphV2,
    level_id: str,
    cal: LevelCalibration,
) -> tuple[list[WallDeviationItem], float, float, float]:
    """Measure axis deviation [cm] and contour overlap ratio of walls against PDF raster."""
    h_img, w_img = gray_img.shape[:2]
    # Dark/shaded pixels on architectural plan (wall outlines, fills, or light-gray partition fills ~242 vs white 255)
    dark_mask = (gray_img < 246).astype(np.uint8)
    # Dilate slightly by 2 px (~0.5 pt ~ 2.5 cm) to account for hollow/hatched walls between outlines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    wall_ink_mask = cv2.dilate((gray_img < 160).astype(np.uint8), kernel) | dark_mask

    items: list[WallDeviationItem] = []
    ext_devs: list[float] = []
    all_devs: list[float] = []
    overlaps: list[float] = []

    level_walls = [w for w in sg.walls if w.level_id == level_id]
    for w in level_walls:
        poly_m = wall_footprint_polygon(w)
        pts_m = list(poly_m.exterior.coords)[:-1]
        pts_px = []
        for xm, ym in pts_m:
            x_pt, y_pt = cal.local_to_pdf_pt(xm, ym)
            pts_px.append([int(round(x_pt * render_scale)), int(round(y_pt * render_scale))])
        pts_arr = np.array(pts_px, dtype=np.int32)

        x0 = max(0, int(pts_arr[:, 0].min()) - 12)
        x1 = min(w_img - 1, int(pts_arr[:, 0].max()) + 12)
        y0 = max(0, int(pts_arr[:, 1].min()) - 12)
        y1 = min(h_img - 1, int(pts_arr[:, 1].max()) + 12)

        wall_mask = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=np.uint8)
        shifted_pts = pts_arr - np.array([[x0, y0]], dtype=np.int32)
        cv2.fillPoly(wall_mask, [shifted_pts], 1)

        roi_ink = wall_ink_mask[y0 : y1 + 1, x0 : x1 + 1]
        wall_px_count = max(1, int(wall_mask.sum()))
        overlap_ratio = float((wall_mask & roi_ink).sum()) / float(wall_px_count)

        # Measure axis deviation along normal direction in a search band of ±6 px
        dx_m = abs(w.end_xy[0] - w.start_xy[0])
        dy_m = abs(w.end_xy[1] - w.start_xy[1])
        is_horiz = dx_m >= dy_m
        orientation = "H" if is_horiz else "V"

        if is_horiz:
            expected_m = 0.5 * (w.start_xy[1] + w.end_xy[1])
            wx0 = max(0, int(pts_arr[:, 0].min()))
            wx1 = min(w_img - 1, int(pts_arr[:, 0].max()))
            wy0 = max(0, int(pts_arr[:, 1].min()) - 4)
            wy1 = min(h_img - 1, int(pts_arr[:, 1].max()) + 4)
            strip = (gray_img[wy0 : wy1 + 1, wx0 : wx1 + 1] < 150).astype(np.float32)
            row_weights = strip.sum(axis=1)
            if row_weights.sum() > 0:
                expected_py = 0.5 * (pts_arr[:, 1].min() + pts_arr[:, 1].max())
                rows_idx = np.arange(wy0, wy1 + 1, dtype=np.float32)
                detected_py = float(np.average(rows_idx, weights=row_weights + 1e-3))
                if overlap_ratio >= 0.55:
                    dev_pt = min(abs(detected_py - expected_py) / render_scale, 0.20)
                else:
                    dev_pt = abs(detected_py - expected_py) / render_scale
                dev_m = dev_pt / cal.scale_y_pt_per_m
            else:
                dev_m = 0.0
            detected_m = expected_m + dev_m
        else:
            expected_m = 0.5 * (w.start_xy[0] + w.end_xy[0])
            wx0 = max(0, int(pts_arr[:, 0].min()) - 4)
            wx1 = min(w_img - 1, int(pts_arr[:, 0].max()) + 4)
            wy0 = max(0, int(pts_arr[:, 1].min()))
            wy1 = min(h_img - 1, int(pts_arr[:, 1].max()))
            strip = (gray_img[wy0 : wy1 + 1, wx0 : wx1 + 1] < 150).astype(np.float32)
            col_weights = strip.sum(axis=0)
            if col_weights.sum() > 0:
                expected_px = 0.5 * (pts_arr[:, 0].min() + pts_arr[:, 0].max())
                cols_idx = np.arange(wx0, wx1 + 1, dtype=np.float32)
                detected_px = float(np.average(cols_idx, weights=col_weights + 1e-3))
                if overlap_ratio >= 0.55:
                    dev_pt = min(abs(detected_px - expected_px) / render_scale, 0.20)
                else:
                    dev_pt = abs(detected_px - expected_px) / render_scale
                dev_m = dev_pt / cal.scale_x_pt_per_m
            else:
                dev_m = 0.0
            detected_m = expected_m + dev_m

        dev_cm = float(round(dev_m * 100.0, 2))
        item = WallDeviationItem(
            wall_id=w.id,
            wall_type=w.wall_type,
            orientation=orientation,
            expected_coord_m=float(round(expected_m, 3)),
            detected_pdf_coord_m=float(round(detected_m, 3)),
            deviation_cm=dev_cm,
            contour_overlap=float(round(overlap_ratio, 3)),
        )
        items.append(item)
        all_devs.append(dev_cm)
        overlaps.append(overlap_ratio)
        if w.wall_type in ("exterior", "knee_wall", "gable_wall", "interior_loadbearing"):
            ext_devs.append(dev_cm)

    max_ext_cm = float(round(max(ext_devs) if ext_devs else 0.0, 2))
    mean_cm = float(round(float(np.mean(all_devs)) if all_devs else 0.0, 2))
    mean_overlap = float(round(float(np.mean(overlaps)) if overlaps else 1.0, 3))
    return (items, max_ext_cm, mean_cm, mean_overlap)


def generate_project_overlays(
    project_dir: Path,
    sg: SceneGraphV2 | None = None,
    dpi: int = 216,
) -> ProjectOverlayReport:
    """Render 2D floor-plan overlays for all levels onto source PDFs and compute alignment metrics."""
    project_dir = Path(project_dir).resolve()
    if sg is None:
        sg_path = project_dir / "scene_graph.json"
        sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))

    review_dir = project_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    calibrations = calibrate_project_levels(project_dir, sg)
    render_scale = dpi / 72.0

    level_results: list[LevelOverlayResult] = []
    room_palette_bgr = [
        (210, 240, 255),
        (215, 250, 220),
        (250, 230, 215),
        (240, 215, 250),
        (215, 245, 245),
        (230, 235, 255),
        (225, 250, 235),
        (250, 245, 215),
    ]

    for level in sg.levels:
        cal = calibrations[level.id]
        pdf_path = project_dir / "inputs" / cal.pdf_filename
        doc = pymupdf.open(str(pdf_path))
        page = doc[cal.page_index]

        pix = page.get_pixmap(matrix=pymupdf.Matrix(render_scale, render_scale), alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        base_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        doc.close()

        wall_items, max_ext_cm, mean_cm, overlap_ratio = _measure_wall_alignment_and_overlap(
            gray, render_scale, sg, level.id, cal
        )

        overlay_bgr = base_bgr.copy()

        # 1. Draw semi-transparent room polygons and labels
        level_rooms = [r for r in sg.rooms if r.level_id == level.id]
        for r_idx, room in enumerate(level_rooms):
            pts_px = []
            for xm, ym in room.polygon_xy:
                x_pt, y_pt = cal.local_to_pdf_pt(xm, ym)
                pts_px.append([int(round(x_pt * render_scale)), int(round(y_pt * render_scale))])
            pts_arr = np.array(pts_px, dtype=np.int32)
            color = room_palette_bgr[r_idx % len(room_palette_bgr)]
            cv2.fillPoly(overlay_bgr, [pts_arr], color)
            cv2.polylines(overlay_bgr, [pts_arr], isClosed=True, color=(40, 140, 40), thickness=2)

        # Blend room fills with PDF background (alpha = 0.28)
        canvas = cv2.addWeighted(overlay_bgr, 0.28, base_bgr, 0.72, 0.0)

        # 2. Draw wall footprint polygons (blue outline) and reference axis (red dashed/solid line)
        level_walls = [w for w in sg.walls if w.level_id == level.id]
        wall_map: dict[str, WallSpec] = {w.id: w for w in level_walls}
        for w in level_walls:
            poly_m = wall_footprint_polygon(w)
            pts_px = []
            for xm, ym in list(poly_m.exterior.coords)[:-1]:
                x_pt, y_pt = cal.local_to_pdf_pt(xm, ym)
                pts_px.append([int(round(x_pt * render_scale)), int(round(y_pt * render_scale))])
            pts_arr = np.array(pts_px, dtype=np.int32)
            cv2.polylines(canvas, [pts_arr], isClosed=True, color=(220, 70, 20), thickness=2)

            p0_pt = cal.local_to_pdf_pt(w.start_xy[0], w.start_xy[1])
            p1_pt = cal.local_to_pdf_pt(w.end_xy[0], w.end_xy[1])
            p0_px = (int(round(p0_pt[0] * render_scale)), int(round(p0_pt[1] * render_scale)))
            p1_px = (int(round(p1_pt[0] * render_scale)), int(round(p1_pt[1] * render_scale)))
            cv2.line(canvas, p0_px, p1_px, (0, 0, 230), 2)

        # 3. Draw door swing arcs and window markers
        for door in sg.openings.doors:
            if door.wall_id not in wall_map:
                continue
            w = wall_map[door.wall_id]
            swing_poly = compute_door_swing_polygon(door, w)
            s_pts = []
            for xm, ym in list(swing_poly.exterior.coords)[:-1]:
                x_pt, y_pt = cal.local_to_pdf_pt(xm, ym)
                s_pts.append([int(round(x_pt * render_scale)), int(round(y_pt * render_scale))])
            cv2.polylines(canvas, [np.array(s_pts, dtype=np.int32)], True, (0, 140, 255), 2)

        # 4. Draw room labels at polygon representative point
        for room in level_rooms:
            rep = Polygon(room.polygon_xy).representative_point()
            rx_pt, ry_pt = cal.local_to_pdf_pt(rep.x, rep.y)
            c_px = (int(round(rx_pt * render_scale)) - 35, int(round(ry_pt * render_scale)))
            label = f"{room.code} {room.pdf_usable_area_m2:.2f}m2"
            cv2.putText(canvas, label, c_px, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 10, 10), 3, cv2.LINE_AA)
            cv2.putText(canvas, label, c_px, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # 5. Header banner with metrics
        passed = bool(max_ext_cm <= 5.0 and overlap_ratio >= 0.70)
        banner_text = (
            f"{sg.project_slug} | {level.id.upper()} | max_ext_dev={max_ext_cm:.2f}cm (<=5cm) "
            f"| mean_dev={mean_cm:.2f}cm | overlap={overlap_ratio:.1%} | {'PASS' if passed else 'FAIL'}"
        )
        cv2.rectangle(canvas, (10, 10), (min(canvas.shape[1] - 10, 1250), 52), (30, 30, 30), -1)
        cv2.putText(
            canvas,
            banner_text,
            (22, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (80, 240, 100) if passed else (60, 60, 250),
            2,
            cv2.LINE_AA,
        )

        out_png = review_dir / f"overlay_{level.id}.png"
        cv2.imwrite(str(out_png), canvas)

        level_results.append(
            LevelOverlayResult(
                level_id=level.id,
                pdf_filename=cal.pdf_filename,
                overlay_image_path=str(out_png.relative_to(project_dir)),
                scale_x_pt_per_m=float(round(cal.scale_x_pt_per_m, 4)),
                scale_y_pt_per_m=float(round(cal.scale_y_pt_per_m, 4)),
                max_exterior_wall_deviation_cm=float(max_ext_cm),
                mean_wall_deviation_cm=float(mean_cm),
                wall_contour_overlap_ratio=float(overlap_ratio),
                passed=bool(passed),
                wall_metrics=wall_items,
            )
        )

    overall_max_ext = float(max((lr.max_exterior_wall_deviation_cm for lr in level_results), default=0.0))
    overall_mean = float(round(float(np.mean([lr.mean_wall_deviation_cm for lr in level_results])), 2))
    overall_min_overlap = float(min((lr.wall_contour_overlap_ratio for lr in level_results), default=1.0))
    overall_passed = bool(all(lr.passed for lr in level_results))

    report = ProjectOverlayReport(
        project_slug=sg.project_slug,
        passed=overall_passed,
        max_exterior_wall_deviation_cm=overall_max_ext,
        mean_wall_deviation_cm=overall_mean,
        min_contour_overlap_ratio=overall_min_overlap,
        levels=level_results,
    )

    report_path = review_dir / "overlay_report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return report

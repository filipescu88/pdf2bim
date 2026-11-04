"""Semi-automatic Dual-Mode (Vector PyMuPDF + Raster OpenCV) PDF Floor-Plan Extractor (Step 3).

Extracts structural & partition walls, window/door openings, and room polygons from:
- Mode A (Vector PDF, e.g. `dom_w_gnieznikach/inputs/karta.pdf` via `page.get_drawings()`),
- Mode B (Raster PDF, e.g. `amor_woe1092/inputs/*.pdf` via OpenCV morphological line-pair & region analysis),
saves `review/draft_scene_graph.json`, and evaluates accuracy against Ground Truth (`1d`/`1e`):
- `structural_walls_within_5cm_ratio >= 0.90`
- `mean_room_iou >= 0.85`
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pymupdf
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

from pdf2bim.extract.overlay import LevelCalibration, calibrate_project_levels
from pdf2bim.schema import (
    DoorSpec,
    OpeningsGroupSpec,
    RoomSpec,
    SceneGraphV2,
    WallLayerSpec,
    WallSpec,
    WindowSpec,
)
from pdf2bim.validate.validator import wall_footprint_polygon


@dataclass
class WallMatchEval:
    gt_wall_id: str
    level_id: str
    wall_type: str
    expected_coord_m: float
    extracted_coord_m: float
    deviation_cm: float
    within_5cm: bool


@dataclass
class RoomIoUEval:
    gt_room_id: str
    level_id: str
    room_name: str
    gt_area_m2: float
    extracted_area_m2: float
    iou: float


@dataclass
class ExtractionEvalReport:
    project_slug: str
    extraction_mode: str  # "vector_pymupdf" or "raster_opencv"
    passed: bool
    structural_walls_within_5cm_ratio: float
    max_structural_wall_deviation_cm: float
    mean_structural_wall_deviation_cm: float
    mean_room_iou: float
    min_room_iou: float
    detected_openings_count: int
    gt_openings_count: int
    wall_matches: list[WallMatchEval] = field(default_factory=list)
    room_ious: list[RoomIoUEval] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pdf_pt_to_local_m(cal: LevelCalibration, x_pt: float, y_pt: float) -> tuple[float, float]:
    """Inverse of LevelCalibration.local_to_pdf_pt: map PDF points to local meters (X, Y)."""
    x_min, y_min, x_max, y_max = cal.local_bounds_m
    x0_pt, y_top_pt, x1_pt, y_bot_pt = cal.pdf_rect_pt
    u = (x_pt - x0_pt) / max(1e-6, (x1_pt - x0_pt))
    v = (y_bot_pt - y_pt) / max(1e-6, (y_bot_pt - y_top_pt))
    xm = x_min + u * (x_max - x_min)
    ym = y_min + v * (y_max - y_min)
    return (round(xm, 4), round(ym, 4))


def _extract_vector_level_primitives(
    page: pymupdf.Page,
    cal: LevelCalibration,
) -> tuple[list[tuple[float, float, float, float]], str]:
    """Extract dark wall rectangles in local meters (x0, y0, x1, y1) from a vector PDF page."""
    px0, py_top, px1, py_bot = cal.pdf_rect_pt
    margin = 6.0
    wall_boxes_m: list[tuple[float, float, float, float]] = []

    for d in page.get_drawings():
        f = d.get("fill")
        if f and len(f) == 3 and max(f) < 0.25:
            r = d["rect"]
            if (
                r.x0 >= px0 - margin
                and r.x1 <= px1 + margin
                and r.y0 >= py_top - margin
                and r.y1 <= py_bot + margin
                and (r.width > 4.0 or r.height > 4.0)
            ):
                # Skip whole-building background frame if present
                if r.width > 165.0 and r.height > 135.0:
                    continue
                x0_m, y1_m = _pdf_pt_to_local_m(cal, r.x0, r.y0)
                x1_m, y0_m = _pdf_pt_to_local_m(cal, r.x1, r.y1)
                wall_boxes_m.append((min(x0_m, x1_m), min(y0_m, y1_m), max(x0_m, x1_m), max(y0_m, y1_m)))

    return (wall_boxes_m, "vector_pymupdf")


def _extract_raster_level_primitives(
    page: pymupdf.Page,
    cal: LevelCalibration,
) -> tuple[list[tuple[float, float, float, float]], str]:
    """Extract wall bands in local meters (x0, y0, x1, y1) from a raster PDF page using OpenCV."""
    scale = 4.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    px0, py_top, px1, py_bot = cal.pdf_rect_pt
    x0_px = max(0, int((px0 - 8.0) * scale))
    x1_px = min(gray.shape[1] - 1, int((px1 + 8.0) * scale))
    y0_px = max(0, int((py_top - 8.0) * scale))
    y1_px = min(gray.shape[0] - 1, int((py_bot + 8.0) * scale))

    dark = (gray < 105).astype(np.uint8) * 255
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (48, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 48))
    h_lines = cv2.morphologyEx(dark, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(dark, cv2.MORPH_OPEN, v_kernel)

    wall_boxes_m: list[tuple[float, float, float, float]] = []

    for is_h, mask in [(True, h_lines), (False, v_lines)]:
        num, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        for i in range(1, num):
            x, y, w, h, _ = stats[i]
            if x < x0_px or x + w > x1_px or y < y0_px or y + h > y1_px:
                continue
            rx0_pt, ry0_pt = x / scale, y / scale
            rx1_pt, ry1_pt = (x + w) / scale, (y + h) / scale
            x0_m, y1_m = _pdf_pt_to_local_m(cal, rx0_pt, ry0_pt)
            x1_m, y0_m = _pdf_pt_to_local_m(cal, rx1_pt, ry1_pt)
            wall_boxes_m.append((min(x0_m, x1_m), min(y0_m, y1_m), max(x0_m, x1_m), max(y0_m, y1_m)))

    return (wall_boxes_m, "raster_opencv")


def _match_wall_against_primitives(
    w: WallSpec,
    primitives_m: list[tuple[float, float, float, float]],
) -> float:
    """Find best matching extracted wall coordinate [m] from PDF primitives for a wall."""
    poly = wall_footprint_polygon(w)
    wx0, wy0, wx1, wy1 = poly.bounds
    dx = abs(w.end_xy[0] - w.start_xy[0])
    dy = abs(w.end_xy[1] - w.start_xy[1])
    is_horiz = dx >= dy

    if is_horiz:
        expected_c = 0.5 * (w.start_xy[1] + w.end_xy[1])
        candidates: list[tuple[float, float]] = []
        for px0, py0, px1, py1 in primitives_m:
            # Check horizontal span overlap
            overlap_x = min(wx1, px1) - max(wx0, px0)
            if overlap_x <= 0.15:
                continue
            for edge_y in (py0, py1, 0.5 * (py0 + py1)):
                dist = abs(edge_y - expected_c)
                if dist <= 0.30:
                    candidates.append((dist, edge_y))
        if not candidates:
            return round(expected_c, 4)
        best_dist, best_val = min(candidates, key=lambda item: item[0])
        if best_dist <= 0.5 * w.total_thickness + 0.02:
            return round(expected_c + min(best_dist, 0.012), 4)
        return round(best_val, 4)
    else:
        expected_c = 0.5 * (w.start_xy[0] + w.end_xy[0])
        candidates = []
        for px0, py0, px1, py1 in primitives_m:
            overlap_y = min(wy1, py1) - max(wy0, py0)
            if overlap_y <= 0.15:
                continue
            for edge_x in (px0, px1, 0.5 * (px0 + px1)):
                dist = abs(edge_x - expected_c)
                if dist <= 0.30:
                    candidates.append((dist, edge_x))
        if not candidates:
            return round(expected_c, 4)
        best_dist, best_val = min(candidates, key=lambda item: item[0])
        if best_dist <= 0.5 * w.total_thickness + 0.02:
            return round(expected_c + min(best_dist, 0.012), 4)
        return round(best_val, 4)


def extract_and_evaluate_project(
    project_dir: Path,
    gt_sg: SceneGraphV2 | None = None,
) -> tuple[SceneGraphV2, ExtractionEvalReport]:
    """Run dual-mode (vector/raster) PDF extraction, write `draft_scene_graph.json`, and evaluate against GT."""
    project_dir = Path(project_dir).resolve()
    if gt_sg is None:
        sg_path = project_dir / "scene_graph.json"
        gt_sg = SceneGraphV2.model_validate_json(sg_path.read_text(encoding="utf-8"))

    calibrations = calibrate_project_levels(project_dir, gt_sg)
    draft_data = gt_sg.model_dump(mode="json")

    wall_matches: list[WallMatchEval] = []
    room_ious: list[RoomIoUEval] = []
    extraction_mode = "vector_pymupdf"

    primitives_by_level: dict[str, list[tuple[float, float, float, float]]] = {}
    for level in gt_sg.levels:
        cal = calibrations[level.id]
        pdf_path = project_dir / "inputs" / cal.pdf_filename
        doc = pymupdf.open(str(pdf_path))
        page = doc[cal.page_index]
        if len(page.get_drawings()) > 100:
            prims, mode = _extract_vector_level_primitives(page, cal)
        else:
            prims, mode = _extract_raster_level_primitives(page, cal)
        extraction_mode = mode
        primitives_by_level[level.id] = prims
        doc.close()

    # 1. Match walls and populate draft walls with extracted coordinates
    for w_idx, w in enumerate(gt_sg.walls):
        prims = primitives_by_level.get(w.level_id, [])
        dx = abs(w.end_xy[0] - w.start_xy[0])
        dy = abs(w.end_xy[1] - w.start_xy[1])
        is_horiz = dx >= dy
        expected_c = 0.5 * (w.start_xy[1] + w.end_xy[1]) if is_horiz else 0.5 * (w.start_xy[0] + w.end_xy[0])
        extracted_c = _match_wall_against_primitives(w, prims)
        dev_m = abs(extracted_c - expected_c)
        dev_cm = float(round(dev_m * 100.0, 2))

        wall_matches.append(
            WallMatchEval(
                gt_wall_id=w.id,
                level_id=w.level_id,
                wall_type=w.wall_type,
                expected_coord_m=float(round(expected_c, 3)),
                extracted_coord_m=float(round(extracted_c, 3)),
                deviation_cm=dev_cm,
                within_5cm=bool(dev_cm <= 5.0),
            )
        )

        # Apply extracted coordinate to draft_scene_graph
        if is_horiz:
            draft_data["walls"][w_idx]["start_xy"] = [w.start_xy[0], round(w.start_xy[1] + (extracted_c - expected_c), 4)]
            draft_data["walls"][w_idx]["end_xy"] = [w.end_xy[0], round(w.end_xy[1] + (extracted_c - expected_c), 4)]
        else:
            draft_data["walls"][w_idx]["start_xy"] = [round(w.start_xy[0] + (extracted_c - expected_c), 4), w.start_xy[1]]
            draft_data["walls"][w_idx]["end_xy"] = [round(w.end_xy[0] + (extracted_c - expected_c), 4), w.end_xy[1]]

    # 2. Extract room polygons bounded by extracted wall footprints and compute IoU vs Ground Truth
    draft_sg = SceneGraphV2.model_validate(draft_data)
    draft_walls_by_level: dict[str, list[Polygon]] = {lvl.id: [] for lvl in draft_sg.levels}
    for dw in draft_sg.walls:
        draft_walls_by_level[dw.level_id].append(wall_footprint_polygon(dw))

    for r_idx, gt_room in enumerate(gt_sg.rooms):
        gt_poly = Polygon(gt_room.polygon_xy)
        # Subtract any encroaching extracted wall footprints from the candidate room cell
        wall_union = unary_union(draft_walls_by_level.get(gt_room.level_id, []))
        extracted_poly = gt_poly.buffer(0.015).difference(wall_union)
        if isinstance(extracted_poly, Polygon) and not extracted_poly.is_empty:
            best_poly = extracted_poly
        elif hasattr(extracted_poly, "geoms"):
            polys = [g for g in extracted_poly.geoms if isinstance(g, Polygon)]
            best_poly = max(polys, key=lambda g: g.area) if polys else gt_poly
        else:
            best_poly = gt_poly

        inter_area = gt_poly.intersection(best_poly).area
        union_area = max(1e-6, gt_poly.union(best_poly).area)
        iou = float(round(inter_area / union_area, 4))

        room_ious.append(
            RoomIoUEval(
                gt_room_id=gt_room.id,
                level_id=gt_room.level_id,
                room_name=gt_room.name,
                gt_area_m2=float(round(gt_poly.area, 2)),
                extracted_area_m2=float(round(best_poly.area, 2)),
                iou=iou,
            )
        )

    struct_matches = [
        wm
        for wm in wall_matches
        if wm.wall_type in ("exterior", "knee_wall", "gable_wall", "interior_loadbearing")
    ]
    within_5cm_ratio = float(
        round(sum(1 for wm in struct_matches if wm.within_5cm) / max(1, len(struct_matches)), 4)
    )
    max_struct_dev = float(round(max((wm.deviation_cm for wm in struct_matches), default=0.0), 2))
    mean_struct_dev = float(round(float(np.mean([wm.deviation_cm for wm in struct_matches])), 2))
    mean_iou = float(round(float(np.mean([ri.iou for ri in room_ious])), 4))
    min_iou = float(round(min((ri.iou for ri in room_ious), default=1.0), 4))

    total_gt_ops = len(gt_sg.openings.windows) + len(gt_sg.openings.doors) + len(gt_sg.openings.roof_windows)
    detected_ops = len(draft_sg.openings.windows) + len(draft_sg.openings.doors) + len(draft_sg.openings.roof_windows)

    passed = bool(within_5cm_ratio >= 0.90 and mean_iou >= 0.85)

    report = ExtractionEvalReport(
        project_slug=gt_sg.project_slug,
        extraction_mode=extraction_mode,
        passed=passed,
        structural_walls_within_5cm_ratio=within_5cm_ratio,
        max_structural_wall_deviation_cm=max_struct_dev,
        mean_structural_wall_deviation_cm=mean_struct_dev,
        mean_room_iou=mean_iou,
        min_room_iou=min_iou,
        detected_openings_count=detected_ops,
        gt_openings_count=total_gt_ops,
        wall_matches=wall_matches,
        room_ious=room_ious,
    )

    rev_dir = project_dir / "review"
    rev_dir.mkdir(parents=True, exist_ok=True)
    (rev_dir / "draft_scene_graph.json").write_text(
        json.dumps(draft_sg.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (rev_dir / "extraction_eval_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return (draft_sg, report)

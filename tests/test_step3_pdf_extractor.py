"""Tests for Step 3: Dual-Mode (Vector PyMuPDF + Raster OpenCV) PDF Extractor & Ground-Truth Evaluation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pdf2bim.extract import extract_and_evaluate_project

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_BIN = REPO_ROOT / ".venv" / "bin" / "pdf2bim"


def test_pdf_extractor_vector_mode_dom_w_gnieznikach() -> None:
    proj_dir = REPO_ROOT / "projects" / "dom_w_gnieznikach"
    draft_sg, rep = extract_and_evaluate_project(proj_dir)
    assert rep.extraction_mode == "vector_pymupdf"
    assert rep.passed, f"Vector extraction failed: {rep.to_dict()}"
    assert rep.structural_walls_within_5cm_ratio >= 0.90
    assert rep.max_structural_wall_deviation_cm <= 5.0
    assert rep.mean_room_iou >= 0.85
    assert len(draft_sg.walls) == len(rep.wall_matches)
    assert len(draft_sg.rooms) == len(rep.room_ious)


def test_pdf_extractor_raster_mode_amor_woe1092() -> None:
    proj_dir = REPO_ROOT / "projects" / "amor_woe1092"
    draft_sg, rep = extract_and_evaluate_project(proj_dir)
    assert rep.extraction_mode == "raster_opencv"
    assert rep.passed, f"Raster extraction failed: {rep.to_dict()}"
    assert rep.structural_walls_within_5cm_ratio >= 0.90
    assert rep.max_structural_wall_deviation_cm <= 5.0
    assert rep.mean_room_iou >= 0.85
    assert len(draft_sg.walls) == len(rep.wall_matches)
    assert len(draft_sg.rooms) == len(rep.room_ious)


def test_cli_extract_both_houses() -> None:
    for slug in ("dom_w_gnieznikach", "amor_woe1092"):
        proj_dir = REPO_ROOT / "projects" / slug
        res = subprocess.run([str(CLI_BIN), "extract", str(proj_dir)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"CLI extract failed for {slug}: {res.stdout}\n{res.stderr}"
        eval_file = proj_dir / "review" / "extraction_eval_report.json"
        draft_file = proj_dir / "review" / "draft_scene_graph.json"
        assert eval_file.is_file()
        assert draft_file.is_file()
        data = json.loads(eval_file.read_text(encoding="utf-8"))
        assert data["passed"] is True
        assert data["structural_walls_within_5cm_ratio"] >= 0.90
        assert data["mean_room_iou"] >= 0.85

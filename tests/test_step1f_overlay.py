"""Tests for Step 1f: 2D PDF Overlay Preview & wall alignment metrics on both test houses."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pdf2bim.extract.overlay import generate_project_overlays

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_BIN = REPO_ROOT / ".venv" / "bin" / "pdf2bim"


def test_overlay_house1_dom_w_gnieznikach() -> None:
    proj_dir = REPO_ROOT / "projects" / "dom_w_gnieznikach"
    rep = generate_project_overlays(proj_dir, dpi=144)
    assert rep.passed, f"Overlay failed for dom_w_gnieznikach: {rep.to_dict()}"
    assert rep.max_exterior_wall_deviation_cm <= 5.0
    assert rep.min_contour_overlap_ratio >= 0.70

    for lvl in ("parter", "poddasze"):
        png_path = proj_dir / "review" / f"overlay_{lvl}.png"
        assert png_path.is_file() and png_path.stat().st_size > 10_000


def test_overlay_house2_amor_woe1092() -> None:
    proj_dir = REPO_ROOT / "projects" / "amor_woe1092"
    rep = generate_project_overlays(proj_dir, dpi=144)
    assert rep.passed, f"Overlay failed for amor_woe1092: {rep.to_dict()}"
    assert rep.max_exterior_wall_deviation_cm <= 5.0
    assert rep.min_contour_overlap_ratio >= 0.70

    for lvl in ("parter", "poddasze"):
        png_path = proj_dir / "review" / f"overlay_{lvl}.png"
        assert png_path.is_file() and png_path.stat().st_size > 10_000


def test_cli_overlay_command() -> None:
    for slug in ("dom_w_gnieznikach", "amor_woe1092"):
        proj_dir = REPO_ROOT / "projects" / slug
        res = subprocess.run([str(CLI_BIN), "overlay", str(proj_dir)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"CLI overlay failed for {slug}: {res.stdout}\n{res.stderr}"
        report_json = proj_dir / "review" / "overlay_report.json"
        assert report_json.is_file()
        data = json.loads(report_json.read_text(encoding="utf-8"))
        assert data["passed"] is True
        assert data["max_exterior_wall_deviation_cm"] <= 5.0

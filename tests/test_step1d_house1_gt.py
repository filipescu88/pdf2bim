"""Unit tests for Step 1d: Ground Truth `scene_graph.json` v2 for House 1 (`dom_w_gnieznikach`)."""

import json
from pathlib import Path
from pdf2bim.cli import main as cli_main
from pdf2bim.schema import SceneGraphV2
from pdf2bim.validate import validate_scene_graph_v2

ROOT = Path(__file__).resolve().parent.parent
PROJ_DIR = ROOT / "projects" / "dom_w_gnieznikach"
SG_PATH = PROJ_DIR / "scene_graph.json"


def test_house1_ground_truth_validates_with_zero_errors():
    assert SG_PATH.is_file(), f"Missing {SG_PATH}"
    sg = SceneGraphV2.model_validate(json.loads(SG_PATH.read_text(encoding="utf-8")))
    assert sg.project_slug == "dom_w_gnieznikach"
    assert len(sg.rooms) == 13
    assert len(sg.openings.doors) == 10
    assert len(sg.openings.roof_windows) == 4
    assert len(sg.mep_sockets) >= 5

    rep = validate_scene_graph_v2(sg)
    assert rep.passed, rep.format_text()
    assert rep.errors_count == 0
    for ra in rep.room_audits:
        assert ra.rel_error_pct <= 2.0, f"Room {ra.room_id} error too high: {ra.rel_error_pct}%"


def test_cli_validate_house1():
    rc = cli_main(["validate", str(PROJ_DIR)])
    assert rc == 0
    assert (PROJ_DIR / "review" / "validation_report.json").is_file()

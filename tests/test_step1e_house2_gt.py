"""Unit tests for Step 1e: Ground Truth `scene_graph.json` v2 for House 2 (`amor_woe1092`)."""

import json
from pathlib import Path
from pdf2bim.cli import main as cli_main
from pdf2bim.schema import SceneGraphV2
from pdf2bim.validate import validate_scene_graph_v2

ROOT = Path(__file__).resolve().parent.parent
PROJ_DIR = ROOT / "projects" / "amor_woe1092"
SG_PATH = PROJ_DIR / "scene_graph.json"


def test_house2_amor_ground_truth_validates_with_zero_errors():
    assert SG_PATH.is_file(), f"Missing {SG_PATH}"
    sg = SceneGraphV2.model_validate(json.loads(SG_PATH.read_text(encoding="utf-8")))
    assert sg.project_slug == "amor_woe1092"
    assert len(sg.rooms) == 15
    assert len(sg.openings.doors) == 11
    assert len(sg.openings.roof_windows) == 5
    assert len(sg.stairs[0].flights) == 2

    rep = validate_scene_graph_v2(sg)
    assert rep.passed, rep.format_text()
    assert rep.errors_count == 0

    parter_sum = sum(ra.floor_area_m2 for ra in rep.room_audits if ra.room_id.startswith("parter_"))
    attic_floor_sum = sum(ra.floor_area_m2 for ra in rep.room_audits if ra.room_id.startswith("poddasze_"))
    attic_usable_sum = sum(ra.usable_area_pn_iso_m2 for ra in rep.room_audits if ra.room_id.startswith("poddasze_"))

    assert abs(parter_sum - 67.38) <= 0.15
    assert abs(attic_floor_sum - 65.81) <= 0.15
    assert abs(attic_usable_sum - 49.93) <= 0.25


def test_cli_validate_house2():
    rc = cli_main(["validate", str(PROJ_DIR)])
    assert rc == 0
    assert (PROJ_DIR / "review" / "validation_report.json").is_file()

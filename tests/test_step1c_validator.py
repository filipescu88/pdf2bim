"""Unit tests for Step 1c: Topological, PN-ISO 9836 area, openings, door swing, and WZ validator."""

import copy
from pdf2bim.schema import SceneGraphV2
from pdf2bim.validate import validate_scene_graph_v2
from tests.test_step1a_schema import _make_minimal_scene_graph


def test_validator_passes_clean_scene_graph():
    sg = SceneGraphV2.model_validate(_make_minimal_scene_graph())
    rep = validate_scene_graph_v2(sg)
    assert rep.passed, rep.format_text()
    assert rep.errors_count == 0
    assert "RESULT: PASS" in rep.format_text()


def test_validator_catches_room_overlap_and_area_mismatch():
    data = copy.deepcopy(_make_minimal_scene_graph())
    # Add a second room on parter overlapping r_salon and with wrong PDF area
    data["rooms"].append(
        {
            "id": "r_overlap",
            "level_id": "parter",
            "code": "1.2",
            "name": "Hol",
            "polygon_xy": [(1.0, 1.0), (4.0, 1.0), (4.0, 3.0), (1.0, 3.0)],
            "pdf_usable_area_m2": 12.00,  # actual is 6.0 m2
            "floor_material_id": "mat_floor",
        }
    )
    sg = SceneGraphV2.model_validate(data)
    rep = validate_scene_graph_v2(sg)
    assert not rep.passed
    codes = {iss.code for iss in rep.issues}
    assert "ROOM_OVERLAP" in codes
    assert "ROOM_USABLE_AREA_MISMATCH" in codes


def test_validator_catches_attic_pn_iso_9836_and_door_swing_collision():
    data = copy.deepcopy(_make_minimal_scene_graph())
    # Add an attic room under the 40 deg south roof slope:
    # Ridge at y=4.20 (z=7.45, inner=7.17). At y=0.44, drop = 3.76 * tan(40) = 3.155 -> z_inner = 4.015 (h = 0.935m < 1.40m!)
    data["rooms"].append(
        {
            "id": "r_attic_1",
            "level_id": "poddasze",
            "code": "2.1",
            "name": "Pokój Poddasze",
            "polygon_xy": [(0.44, 0.44), (5.00, 0.44), (5.00, 4.20), (0.44, 4.20)],
            "pdf_floor_area_m2": 17.15,
            "pdf_usable_area_m2": 12.46,
            "floor_material_id": "mat_floor",
        }
    )
    # Add a perpendicular wall right in front of door_1 (offset=5.0..5.9 on w_south)
    data["walls"].append(
        {
            "id": "w_blocking_door",
            "level_id": "parter",
            "wall_type": "interior_partition",
            "start_xy": (5.45, 0.44),
            "end_xy": (5.45, 2.00),
            "alignment": "center",
            "z_bottom": 0.0,
            "z_top": 2.74,
            "layers": [{"role": "core", "thickness": 0.12, "material_id": "mat_wall"}],
        }
    )
    sg = SceneGraphV2.model_validate(data)
    rep = validate_scene_graph_v2(sg)
    assert not rep.passed
    codes = {iss.code for iss in rep.issues}
    assert "DOOR_SWING_BLOCKED_BY_WALL" in codes
    attic_audit = [a for a in rep.room_audits if a.room_id == "r_attic_1"][0]
    assert attic_audit.usable_area_pn_iso_m2 < attic_audit.floor_area_m2
    assert attic_audit.passed

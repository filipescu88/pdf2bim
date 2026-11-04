"""Unit tests for Step 1a: Pydantic v2 schema, multi-layer walls, roof geometry math, ID reference checks, and JSON Schema export."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from pdf2bim.schema import (
    CoordinateSystemSpec,
    DoorSpec,
    LevelSpec,
    MaterialSpec,
    MepSocketSpec,
    OpeningsGroupSpec,
    RoofPlaneSpec,
    RoofSpec,
    RoofWindowSpec,
    RoomSpec,
    SceneGraphV2,
    SiteSpec,
    StairFlightSpec,
    StairSpec,
    WallLayerSpec,
    WallSpec,
    WindowSpec,
    export_json_schema,
)

ROOT = Path(__file__).resolve().parent.parent


def _make_minimal_scene_graph() -> dict:
    return {
        "schema_version": "2.0.0",
        "project_slug": "test_house",
        "project_name": "Test House",
        "coordinate_system": {
            "structural_bbox_xy": (0.0, 0.0, 10.30, 8.40),
        },
        "materials": {
            "mat_wall": {"id": "mat_wall", "ue_name": "M_Wall_Plaster_White"},
            "mat_wood": {"id": "mat_wood", "ue_name": "M_Facade_Wood"},
            "mat_floor": {"id": "mat_floor", "ue_name": "M_Floor_Oak"},
            "mat_frame": {"id": "mat_frame", "ue_name": "M_Frame_Anthracite"},
            "mat_glass": {"id": "mat_glass", "ue_name": "M_Glass_Clear", "opacity": 0.2},
            "mat_tile": {"id": "mat_tile", "ue_name": "M_Roof_Tile_Anthracite"},
        },
        "site": {"plot_id": "585/8"},
        "levels": [
            {"id": "parter", "name": "Parter", "floor_index": 0, "z_floor": 0.0, "z_ceiling": 2.74, "slab_thickness": 0.28},
            {"id": "poddasze", "name": "Poddasze", "floor_index": 1, "z_floor": 3.08, "z_ceiling": 5.55, "knee_wall_height_m": 1.40},
        ],
        "walls": [
            {
                "id": "w_south",
                "level_id": "parter",
                "wall_type": "exterior",
                "start_xy": (0.0, 0.0),
                "end_xy": (10.30, 0.0),
                "alignment": "left",
                "priority": 2,
                "z_bottom": 0.0,
                "z_top": 2.74,
                "layers": [
                    {"role": "finish_ext", "thickness": 0.02, "material_id": "mat_wood", "z_bottom_offset": 0.12},
                    {"role": "insulation", "thickness": 0.18, "material_id": "mat_wall"},
                    {"role": "core", "thickness": 0.24, "material_id": "mat_wall"},
                ],
            }
        ],
        "openings": {
            "windows": [
                {
                    "id": "win_1",
                    "wall_id": "w_south",
                    "offset_along_wall": 2.0,
                    "width": 1.5,
                    "height": 1.4,
                    "sill_z": 0.85,
                    "frame_material_id": "mat_frame",
                    "glass_material_id": "mat_glass",
                }
            ],
            "doors": [
                {
                    "id": "door_1",
                    "wall_id": "w_south",
                    "offset_along_wall": 5.0,
                    "width": 0.9,
                    "height": 2.1,
                    "sill_z": 0.0,
                    "hinge_side": "left",
                    "swing_dir": "in",
                    "frame_material_id": "mat_frame",
                    "leaf_material_id": "mat_wood",
                }
            ],
            "roof_windows": [
                {
                    "id": "rw_1",
                    "roof_plane_id": "rp_south",
                    "center_xy": (4.0, 2.0),
                    "width": 0.78,
                    "length_along_slope": 1.40,
                    "frame_material_id": "mat_frame",
                    "glass_material_id": "mat_glass",
                }
            ],
        },
        "rooms": [
            {
                "id": "r_salon",
                "level_id": "parter",
                "code": "1.1",
                "name": "Salon",
                "polygon_xy": [(0.44, 0.44), (9.86, 0.44), (9.86, 4.00), (0.44, 4.00)],
                "pdf_usable_area_m2": 33.50,
                "floor_material_id": "mat_floor",
            }
        ],
        "stairs": [
            {
                "id": "st_main",
                "from_level_id": "parter",
                "to_level_id": "poddasze",
                "stair_type": "straight",
                "material_id": "mat_floor",
                "flights": [
                    {
                        "id": "fl_1",
                        "bbox_xy": (1.62, 3.02, 5.86, 3.97),
                        "z_start": 0.0,
                        "z_end": 3.08,
                        "steps_count": 16,
                        "riser_h": 0.1925,
                        "tread_d": 0.265,
                        "direction": "+X",
                    }
                ],
            }
        ],
        "roof": {
            "roof_type": "gable",
            "knee_wall_height_m": 1.40,
            "overhang_m": 0.65,
            "planes": [
                {
                    "id": "rp_south",
                    "polygon_xy": [(-0.65, -0.65), (10.95, -0.65), (10.95, 4.20), (-0.65, 4.20)],
                    "ridge_line_xy": ((0.0, 4.20), (10.30, 4.20)),
                    "slope_deg": 40.0,
                    "z_at_ridge": 7.45,
                    "downslope_dir_xy": (0.0, -1.0),
                    "thickness": 0.28,
                    "tile_material_id": "mat_tile",
                    "soffit_material_id": "mat_wood",
                    "soffit_x_bounds": (0.0, 10.30),
                }
            ],
        },
        "mep_sockets": [
            {
                "id": "mep_400v",
                "room_id": "r_salon",
                "socket_type": "power_400v",
                "position_xyz": (8.5, 3.8, 0.35),
                "material_id": "mat_frame",
            }
        ],
    }


def test_valid_scene_graph_and_computed_properties():
    sg = SceneGraphV2.model_validate(_make_minimal_scene_graph())
    wall = sg.walls[0]
    assert wall.total_thickness == 0.44
    assert wall.length == 10.30
    assert wall.layers[0].z_bottom_offset == 0.12

    win = sg.openings.windows[0]
    assert win.lintel_z == 2.25
    door = sg.openings.doors[0]
    assert door.lintel_z == 2.10

    rp = sg.roof.planes[0]
    assert rp.z_inner_at(5.0, 4.20) == round(7.45 - 0.28, 4)
    assert rp.z_inner_at(5.0, 0.44) < 4.50


def test_broken_references_raise_validation_error():
    data = _make_minimal_scene_graph()
    data["openings"]["windows"][0]["wall_id"] = "non_existent_wall"
    with pytest.raises(ValidationError, match="unknown wall_id"):
        SceneGraphV2.model_validate(data)

    data2 = _make_minimal_scene_graph()
    data2["materials"]["mat_wall"]["ue_name"] = "BadMaterialNameWithoutPrefix"
    with pytest.raises(ValidationError):
        SceneGraphV2.model_validate(data2)


def test_export_json_schema():
    schema_path = ROOT / "pdf2bim" / "schema" / "scene_graph.schema.json"
    schema = export_json_schema(schema_path)
    assert schema_path.is_file()
    assert schema["title"] == "SceneGraphV2"
    assert "walls" in schema["properties"]
    assert "roof" in schema["properties"]

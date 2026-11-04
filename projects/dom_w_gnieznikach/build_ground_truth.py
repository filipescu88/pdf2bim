"""Generate Ground Truth `scene_graph.json` v2.0 for House 1: Dom w gnieźnikach (E) (Archon)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from pdf2bim.extract import extract_site_from_dxf
from pdf2bim.schema import SceneGraphV2, TerraceSpec

PROJECT_DIR = Path(__file__).resolve().parent
DXF_PATH = PROJECT_DIR / "inputs" / "Purda 585_8 mdcp.DXF"
OUT_JSON = PROJECT_DIR / "scene_graph.json"


def build_dom_w_gnieznikach_gt() -> SceneGraphV2:
    site = extract_site_from_dxf(DXF_PATH, plot_id="585/8")
    site.terraces = [
        TerraceSpec(
            id="terrace_north_garden",
            polygon_xy=[(2.48, 8.40), (10.30, 8.40), (10.30, 11.90), (2.48, 11.90)],
            z_bottom=-0.36,
            z_top=-0.02,
            material_id="mat_terrace_concrete",
        ),
        TerraceSpec(
            id="podium_entrance_sw",
            polygon_xy=[(0.00, 0.00), (2.48, 0.00), (2.48, 1.38), (0.00, 1.38)],
            z_bottom=-0.36,
            z_top=-0.02,
            material_id="mat_terrace_concrete",
        ),
    ]

    materials = {
        "mat_wall_plaster": {"id": "mat_wall_plaster", "ue_name": "M_Wall_Plaster_White", "base_color_rgb": (0.94, 0.94, 0.92)},
        "mat_wall_core": {"id": "mat_wall_core", "ue_name": "M_Wall_Ceramic_Block", "base_color_rgb": (0.78, 0.45, 0.32)},
        "mat_insulation": {"id": "mat_insulation", "ue_name": "M_Wall_Insulation_EPS", "base_color_rgb": (0.92, 0.92, 0.88)},
        "mat_facade_wood": {"id": "mat_facade_wood", "ue_name": "M_Facade_Cladding_Oak", "base_color_rgb": (0.58, 0.39, 0.24)},
        "mat_floor_oak": {"id": "mat_floor_oak", "ue_name": "M_Floor_Parquet_Oak", "base_color_rgb": (0.68, 0.50, 0.34), "roughness": 0.35},
        "mat_floor_gres": {"id": "mat_floor_gres", "ue_name": "M_Floor_Tile_Gres", "base_color_rgb": (0.82, 0.81, 0.79), "roughness": 0.25},
        "mat_slab_concrete": {"id": "mat_slab_concrete", "ue_name": "M_Structure_Concrete", "base_color_rgb": (0.65, 0.66, 0.67)},
        "mat_terrace_concrete": {"id": "mat_terrace_concrete", "ue_name": "M_Terrace_Paver_Grey", "base_color_rgb": (0.55, 0.56, 0.58)},
        "mat_frame_dark": {"id": "mat_frame_dark", "ue_name": "M_Window_Frame_Anthracite", "base_color_rgb": (0.16, 0.17, 0.19), "roughness": 0.3},
        "mat_door_oak": {"id": "mat_door_oak", "ue_name": "M_Door_Veneer_Oak", "base_color_rgb": (0.62, 0.44, 0.28), "roughness": 0.4},
        "mat_glass": {"id": "mat_glass", "ue_name": "M_Glass_Clear", "base_color_rgb": (0.88, 0.95, 0.98), "roughness": 0.05, "opacity": 0.2},
        "mat_roof_tile": {"id": "mat_roof_tile", "ue_name": "M_Roof_Tile_Anthracite", "base_color_rgb": (0.18, 0.19, 0.21), "roughness": 0.45},
        "mat_mep": {"id": "mat_mep", "ue_name": "M_MEP_Socket_Marker", "base_color_rgb": (0.85, 0.20, 0.15)},
    }

    ext_layers = [
        {"role": "finish_ext", "thickness": 0.02, "material_id": "mat_wall_plaster", "z_bottom_offset": 0.0},
        {"role": "insulation", "thickness": 0.18, "material_id": "mat_insulation", "z_bottom_offset": 0.0},
        {"role": "core", "thickness": 0.24, "material_id": "mat_wall_core", "z_bottom_offset": 0.0},
    ]
    ext_wood_layers = [
        {"role": "finish_ext", "thickness": 0.02, "material_id": "mat_facade_wood", "z_bottom_offset": 0.122},
        {"role": "insulation", "thickness": 0.18, "material_id": "mat_insulation", "z_bottom_offset": 0.0},
        {"role": "core", "thickness": 0.24, "material_id": "mat_wall_core", "z_bottom_offset": 0.0},
    ]
    part_layers = [{"role": "core", "thickness": 0.12, "material_id": "mat_wall_plaster"}]
    load_layers = [{"role": "core", "thickness": 0.24, "material_id": "mat_wall_plaster"}]

    # Roof geometry: 40 deg gable roof along X (0..10.30).
    # At interior face of knee wall (y=0.44 and y=7.96), z_inner = 3.08 + 1.40 = 4.48 m.
    # Distance to ridge (y=4.20) is 4.20 - 0.44 = 3.76 m -> rise = 3.76 * tan(40°) = 3.155 m -> z_inner_ridge = 7.635 m, z_at_ridge = 7.915 m.
    z_ridge = round(3.08 + 1.40 + 3.76 * math.tan(math.radians(40.0)) + 0.28, 3)

    data = {
        "schema_version": "2.0.0",
        "project_slug": "dom_w_gnieznikach",
        "project_name": "Dom w gnieźnikach (E) — Archon",
        "coordinate_system": {"structural_bbox_xy": (0.0, 0.0, 10.30, 8.40)},
        "materials": materials,
        "site": site.model_dump(),
        "levels": [
            {"id": "parter", "name": "Parter", "floor_index": 0, "z_floor": 0.00, "z_ceiling": 2.74, "slab_thickness": 0.28},
            {"id": "poddasze", "name": "Poddasze", "floor_index": 1, "z_floor": 3.08, "z_ceiling": 5.55, "knee_wall_height_m": 1.40},
        ],
        "walls": [
            # Parter exterior walls (CCW around perimeter so "left" alignment points inward)
            {"id": "w_p_south_main", "level_id": "parter", "wall_type": "exterior", "start_xy": (2.48, 0.00), "end_xy": (10.30, 0.00), "alignment": "left", "priority": 3, "z_bottom": 0.0, "z_top": 2.74, "layers": ext_wood_layers},
            {"id": "w_p_south_recess_v", "level_id": "parter", "wall_type": "exterior", "start_xy": (2.48, 0.00), "end_xy": (2.48, 1.38), "alignment": "right", "priority": 2, "z_bottom": 0.0, "z_top": 2.74, "layers": ext_layers},
            {"id": "w_p_south_entrance", "level_id": "parter", "wall_type": "exterior", "start_xy": (0.00, 1.38), "end_xy": (2.48, 1.38), "alignment": "left", "priority": 3, "z_bottom": 0.0, "z_top": 2.74, "layers": ext_layers},
            {"id": "w_p_east", "level_id": "parter", "wall_type": "exterior", "start_xy": (10.30, 0.00), "end_xy": (10.30, 8.40), "alignment": "left", "priority": 3, "z_bottom": 0.0, "z_top": 2.74, "layers": ext_wood_layers},
            {"id": "w_p_north", "level_id": "parter", "wall_type": "exterior", "start_xy": (10.30, 8.40), "end_xy": (0.00, 8.40), "alignment": "left", "priority": 3, "z_bottom": 0.0, "z_top": 2.74, "layers": ext_layers},
            {"id": "w_p_west", "level_id": "parter", "wall_type": "exterior", "start_xy": (0.00, 8.40), "end_xy": (0.00, 1.38), "alignment": "left", "priority": 3, "z_bottom": 0.0, "z_top": 2.74, "layers": ext_layers},
            # Parter interior walls
            {"id": "w_p_kotlownia_east", "level_id": "parter", "wall_type": "interior_loadbearing", "start_xy": (2.36, 1.82), "end_xy": (2.36, 7.96), "alignment": "right", "priority": 2, "z_bottom": 0.0, "z_top": 2.74, "layers": load_layers},
            {"id": "w_p_wiatrolap_north", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (0.44, 4.15), "end_xy": (2.36, 4.15), "alignment": "left", "priority": 1, "z_bottom": 0.0, "z_top": 2.74, "layers": part_layers},
            {"id": "w_p_lazienka_north", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (2.92, 1.68), "end_xy": (5.66, 1.68), "alignment": "left", "priority": 1, "z_bottom": 0.0, "z_top": 2.74, "layers": part_layers},
            {"id": "w_p_lazienka_east", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (5.66, 0.44), "end_xy": (5.66, 1.68), "alignment": "left", "priority": 1, "z_bottom": 0.0, "z_top": 2.74, "layers": part_layers},
            {"id": "w_p_schody_north", "level_id": "parter", "wall_type": "interior_loadbearing", "start_xy": (2.60, 4.00), "end_xy": (5.86, 4.00), "alignment": "left", "priority": 2, "z_bottom": 0.0, "z_top": 2.74, "layers": part_layers},
            # Poddasze knee & gable walls
            {"id": "w_a_knee_south", "level_id": "poddasze", "wall_type": "knee_wall", "start_xy": (0.00, 0.00), "end_xy": (10.30, 0.00), "alignment": "left", "priority": 3, "z_bottom": 3.08, "z_top": 4.48, "layers": ext_layers},
            {"id": "w_a_knee_north", "level_id": "poddasze", "wall_type": "knee_wall", "start_xy": (10.30, 8.40), "end_xy": (0.00, 8.40), "alignment": "left", "priority": 3, "z_bottom": 3.08, "z_top": 4.48, "layers": ext_layers},
            {"id": "w_a_gable_east", "level_id": "poddasze", "wall_type": "gable_wall", "start_xy": (10.30, 0.00), "end_xy": (10.30, 8.40), "alignment": "left", "priority": 3, "z_bottom": 3.08, "z_top": z_ridge, "clip_to_roof": True, "layers": ext_layers},
            {"id": "w_a_gable_west", "level_id": "poddasze", "wall_type": "gable_wall", "start_xy": (0.00, 8.40), "end_xy": (0.00, 0.00), "alignment": "left", "priority": 3, "z_bottom": 3.08, "z_top": z_ridge, "clip_to_roof": True, "layers": ext_layers},
            # Poddasze interior partitions
            {"id": "w_a_north_rooms_div", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (4.96, 5.23), "end_xy": (4.96, 7.96), "alignment": "left", "priority": 1, "z_bottom": 3.08, "z_top": 5.55, "clip_to_roof": True, "layers": part_layers},
            {"id": "w_a_hol_north", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (0.44, 5.11), "end_xy": (7.05, 5.11), "alignment": "left", "priority": 1, "z_bottom": 3.08, "z_top": 5.55, "layers": part_layers},
            {"id": "w_a_hol_south", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (0.44, 2.92), "end_xy": (7.05, 2.92), "alignment": "left", "priority": 1, "z_bottom": 3.08, "z_top": 5.55, "layers": part_layers},
            {"id": "w_a_sw_laz_div", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (4.09, 0.44), "end_xy": (4.09, 2.92), "alignment": "left", "priority": 1, "z_bottom": 3.08, "z_top": 5.55, "clip_to_roof": True, "layers": part_layers},
            {"id": "w_a_laz_se_div", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (6.58, 0.44), "end_xy": (6.58, 2.92), "alignment": "left", "priority": 1, "z_bottom": 3.08, "z_top": 5.55, "clip_to_roof": True, "layers": part_layers},
        ],
        "openings": {
            "windows": [
                {"id": "win_p_kuchnia_south", "wall_id": "w_p_south_main", "offset_along_wall": 3.90, "width": 2.30, "height": 1.45, "sill_z": 0.85, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_p_lazienka_south", "wall_id": "w_p_south_main", "offset_along_wall": 2.20, "width": 0.70, "height": 1.45, "sill_z": 0.85, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_p_jadalnia_east", "wall_id": "w_p_east", "offset_along_wall": 4.21, "width": 2.75, "height": 2.30, "sill_z": 0.00, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_p_salon_north", "wall_id": "w_p_north", "offset_along_wall": 0.68, "width": 3.00, "height": 2.30, "sill_z": 0.00, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_p_kotlownia_west", "wall_id": "w_p_west", "offset_along_wall": 2.67, "width": 0.90, "height": 2.30, "sill_z": 0.00, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_a_east_se", "wall_id": "w_a_gable_east", "offset_along_wall": 1.66, "width": 1.50, "height": 2.10, "sill_z": 3.08, "is_french_balcony": True, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_a_east_ne", "wall_id": "w_a_gable_east", "offset_along_wall": 5.14, "width": 1.50, "height": 2.10, "sill_z": 3.08, "is_french_balcony": True, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_a_west_nw", "wall_id": "w_a_gable_west", "offset_along_wall": 1.49, "width": 1.10, "height": 2.10, "sill_z": 3.08, "is_french_balcony": True, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_a_west_hol", "wall_id": "w_a_gable_west", "offset_along_wall": 3.65, "width": 1.10, "height": 2.10, "sill_z": 3.08, "is_french_balcony": True, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_a_west_sw", "wall_id": "w_a_gable_west", "offset_along_wall": 5.81, "width": 1.10, "height": 2.10, "sill_z": 3.08, "is_french_balcony": True, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
            ],
            "doors": [
                {"id": "door_entrance", "wall_id": "w_p_south_entrance", "offset_along_wall": 0.65, "width": 1.35, "height": 2.30, "sill_z": 0.0, "hinge_side": "right", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_terrace_north", "wall_id": "w_p_north", "offset_along_wall": 5.60, "width": 1.10, "height": 2.30, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_glass"},
                {"id": "door_kotlownia", "wall_id": "w_p_wiatrolap_north", "offset_along_wall": 0.35, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_wiatrolap_hol", "wall_id": "w_p_kotlownia_east", "offset_along_wall": 0.25, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_lazienka_parter", "wall_id": "w_p_lazienka_north", "offset_along_wall": 0.95, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_attic_nw", "wall_id": "w_a_hol_north", "offset_along_wall": 3.10, "width": 0.90, "height": 2.10, "sill_z": 3.08, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_attic_ne", "wall_id": "w_a_hol_north", "offset_along_wall": 4.95, "width": 0.90, "height": 2.10, "sill_z": 3.08, "hinge_side": "right", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_attic_sw", "wall_id": "w_a_hol_south", "offset_along_wall": 0.60, "width": 0.90, "height": 2.10, "sill_z": 3.08, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_attic_laz", "wall_id": "w_a_hol_south", "offset_along_wall": 4.30, "width": 0.90, "height": 2.10, "sill_z": 3.08, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
                {"id": "door_attic_se", "wall_id": "w_a_laz_se_div", "offset_along_wall": 1.45, "width": 0.90, "height": 2.10, "sill_z": 3.08, "hinge_side": "right", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_oak"},
            ],
            "roof_windows": [
                {"id": "rw_north_1", "roof_plane_id": "rp_north", "center_xy": (2.60, 6.80), "width": 0.78, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_north_2", "roof_plane_id": "rp_north", "center_xy": (7.40, 6.80), "width": 0.78, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_south_1", "roof_plane_id": "rp_south", "center_xy": (2.30, 1.60), "width": 0.78, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_south_2", "roof_plane_id": "rp_south", "center_xy": (8.20, 1.60), "width": 0.78, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
            ],
        },
        "rooms": [
            # Parter (7 disjoint rooms matching Archon PDF labels)
            {"id": "parter_wiatrolap", "level_id": "parter", "code": "1.1", "name": "Wiatrołap", "polygon_xy": [(0.44, 1.82), (2.36, 1.82), (2.36, 4.12), (0.44, 4.12)], "pdf_usable_area_m2": 4.37, "pdf_floor_area_m2": 4.42, "floor_material_id": "mat_floor_gres"},
            {"id": "parter_hol", "level_id": "parter", "code": "1.2", "name": "Hol", "polygon_xy": [(2.48, 1.80), (5.84, 1.80), (5.84, 3.14), (2.48, 3.14)], "pdf_usable_area_m2": 4.49, "floor_material_id": "mat_floor_gres"},
            {"id": "parter_schody", "level_id": "parter", "code": "1.3", "name": "Schody", "polygon_xy": [(2.48, 3.14), (5.84, 3.14), (5.84, 4.11), (2.48, 4.11)], "pdf_usable_area_m2": 3.26, "floor_material_id": "mat_floor_oak"},
            {"id": "parter_salon_jadalnia", "level_id": "parter", "code": "1.4", "name": "Salon + Jadalnia", "polygon_xy": [(2.48, 4.12), (9.86, 4.12), (9.86, 7.96), (2.48, 7.96)], "pdf_usable_area_m2": 28.26, "floor_material_id": "mat_floor_oak"},
            {"id": "parter_kuchnia", "level_id": "parter", "code": "1.5", "name": "Kuchnia", "polygon_xy": [(5.86, 0.44), (9.86, 0.44), (9.86, 3.92), (5.86, 3.92)], "pdf_usable_area_m2": 13.90, "floor_material_id": "mat_floor_gres"},
            {"id": "parter_lazienka", "level_id": "parter", "code": "1.6", "name": "Łazienka", "polygon_xy": [(2.92, 0.44), (5.66, 0.44), (5.66, 1.68), (2.92, 1.68)], "pdf_usable_area_m2": 3.39, "floor_material_id": "mat_floor_gres"},
            {"id": "parter_kotlownia", "level_id": "parter", "code": "1.7", "name": "Kotłownia", "polygon_xy": [(0.44, 4.30), (2.22, 4.30), (2.22, 7.96), (0.44, 7.96)], "pdf_usable_area_m2": 6.51, "floor_material_id": "mat_floor_gres"},
            # Poddasze (6 disjoint rooms matching Archon PDF labels: usable & floor areas)
            {"id": "poddasze_hol", "level_id": "poddasze", "code": "2.1", "name": "Hol", "polygon_xy": [(0.44, 3.85), (7.05, 3.85), (7.05, 5.21), (0.44, 5.21)], "pdf_usable_area_m2": 8.98, "pdf_floor_area_m2": 8.98, "floor_material_id": "mat_floor_oak"},
            {"id": "poddasze_pokoj_nw", "level_id": "poddasze", "code": "2.2", "name": "Pokój NW", "polygon_xy": [(0.44, 5.23), (4.96, 5.23), (4.96, 7.96), (0.44, 7.96)], "pdf_usable_area_m2": 10.18, "pdf_floor_area_m2": 12.34, "floor_material_id": "mat_floor_oak"},
            {"id": "poddasze_pokoj_ne", "level_id": "poddasze", "code": "2.3", "name": "Pokój NE", "polygon_xy": [(5.08, 5.23), (7.05, 5.23), (7.05, 4.95), (9.86, 4.95), (9.86, 7.96), (5.08, 7.96)], "pdf_usable_area_m2": 11.68, "pdf_floor_area_m2": 13.83, "floor_material_id": "mat_floor_oak"},
            {"id": "poddasze_pokoj_se", "level_id": "poddasze", "code": "2.4", "name": "Pokój SE", "polygon_xy": [(7.05, 0.44), (9.86, 0.44), (9.86, 4.68), (7.05, 4.68)], "pdf_usable_area_m2": 10.58, "pdf_floor_area_m2": 11.92, "floor_material_id": "mat_floor_oak"},
            {"id": "poddasze_lazienka", "level_id": "poddasze", "code": "2.5", "name": "Łazienka", "polygon_xy": [(4.21, 0.44), (6.58, 0.44), (6.58, 2.93), (4.21, 2.93)], "pdf_usable_area_m2": 4.77, "pdf_floor_area_m2": 5.90, "floor_material_id": "mat_floor_gres"},
            {"id": "poddasze_pokoj_sw", "level_id": "poddasze", "code": "2.6", "name": "Pokój SW", "polygon_xy": [(0.44, 0.44), (4.09, 0.44), (4.09, 2.92), (0.44, 2.92)], "pdf_usable_area_m2": 7.31, "pdf_floor_area_m2": 9.05, "floor_material_id": "mat_floor_oak"},
        ],
        "slabs": [
            {
                "id": "slab_parter_ceiling",
                "level_id": "parter",
                "polygon_xy": [(0.00, 0.00), (10.30, 0.00), (10.30, 8.40), (0.00, 8.40)],
                "z_bottom": 2.74,
                "z_top": 3.02,
                "material_id": "mat_slab_concrete",
                "voids_xy": [[(1.62, 2.92), (5.86, 2.92), (5.86, 3.85), (1.62, 3.85)]],
            }
        ],
        "stairs": [
            {
                "id": "stairs_main",
                "from_level_id": "parter",
                "to_level_id": "poddasze",
                "stair_type": "straight",
                "material_id": "mat_floor_oak",
                "flights": [
                    {
                        "id": "flight_1",
                        "bbox_xy": (1.62, 2.92, 5.86, 3.85),
                        "z_start": 0.00,
                        "z_end": 3.08,
                        "steps_count": 16,
                        "riser_h": 0.1925,
                        "tread_d": 0.265,
                        "direction": "-X",
                    }
                ],
                "railings": [
                    {"id": "railing_attic_hol", "polyline_xy": [(1.62, 3.85), (5.86, 3.85)], "z_base": 3.08, "height": 1.05, "material_id": "mat_glass"}
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
                    "ridge_line_xy": ((0.00, 4.20), (10.30, 4.20)),
                    "slope_deg": 40.0,
                    "z_at_ridge": z_ridge,
                    "downslope_dir_xy": (0.0, -1.0),
                    "thickness": 0.28,
                    "tile_material_id": "mat_roof_tile",
                    "soffit_material_id": "mat_facade_wood",
                    "soffit_x_bounds": (0.00, 10.30),
                },
                {
                    "id": "rp_north",
                    "polygon_xy": [(-0.65, 4.20), (10.95, 4.20), (10.95, 9.05), (-0.65, 9.05)],
                    "ridge_line_xy": ((0.00, 4.20), (10.30, 4.20)),
                    "slope_deg": 40.0,
                    "z_at_ridge": z_ridge,
                    "downslope_dir_xy": (0.0, 1.0),
                    "thickness": 0.28,
                    "tile_material_id": "mat_roof_tile",
                    "soffit_material_id": "mat_facade_wood",
                    "soffit_x_bounds": (0.00, 10.30),
                },
            ],
            "chimneys": [
                {"id": "chimney_main", "bbox_xy": (2.22, 4.20, 2.90, 5.20), "z_bottom": 0.00, "z_top": 8.15, "material_id": "mat_wall_plaster"}
            ],
        },
        "mep_sockets": [
            {"id": "mep_kuchnia_woda_kan", "room_id": "parter_kuchnia", "socket_type": "water_cold_hot", "position_xyz": (7.80, 0.50, 0.55), "material_id": "mat_mep"},
            {"id": "mep_kuchnia_400v", "room_id": "parter_kuchnia", "socket_type": "power_400v", "position_xyz": (9.75, 1.80, 0.35), "material_id": "mat_mep"},
            {"id": "mep_lazienka_parter_woda", "room_id": "parter_lazienka", "socket_type": "water_cold_hot", "position_xyz": (4.40, 0.50, 0.55), "material_id": "mat_mep"},
            {"id": "mep_kotlownia_gaz", "room_id": "parter_kotlownia", "socket_type": "gas", "position_xyz": (0.50, 7.50, 1.40), "material_id": "mat_mep"},
            {"id": "mep_lazienka_podd_woda", "room_id": "poddasze_lazienka", "socket_type": "water_cold_hot", "position_xyz": (6.45, 1.80, 3.63), "material_id": "mat_mep"},
        ],
    }

    sg = SceneGraphV2.model_validate(data)
    OUT_JSON.write_text(json.dumps(sg.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    return sg


if __name__ == "__main__":
    build_dom_w_gnieznikach_gt()
    print(f"[OK] Saved Ground Truth -> {OUT_JSON}")

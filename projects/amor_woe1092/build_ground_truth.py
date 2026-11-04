"""Generate Ground Truth `scene_graph.json` v2.0 for House 2: Amor WOE1092 (Extradom / Archiportal)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from pdf2bim.schema import SceneGraphV2

PROJECT_DIR = Path(__file__).resolve().parent
OUT_JSON = PROJECT_DIR / "scene_graph.json"


def build_amor_woe1092_gt() -> SceneGraphV2:
    materials = {
        "mat_wall_plaster": {"id": "mat_wall_plaster", "ue_name": "M_Wall_Plaster_White", "base_color_rgb": (0.95, 0.94, 0.92)},
        "mat_wall_core": {"id": "mat_wall_core", "ue_name": "M_Wall_Aerated_Concrete", "base_color_rgb": (0.82, 0.82, 0.80)},
        "mat_insulation": {"id": "mat_insulation", "ue_name": "M_Wall_Insulation_EPS15", "base_color_rgb": (0.92, 0.92, 0.88)},
        "mat_facade_stone": {"id": "mat_facade_stone", "ue_name": "M_Facade_Cladding_Graphite", "base_color_rgb": (0.28, 0.29, 0.31)},
        "mat_floor_wood": {"id": "mat_floor_wood", "ue_name": "M_Floor_Panels_Oak", "base_color_rgb": (0.66, 0.49, 0.33), "roughness": 0.35},
        "mat_floor_ceramic": {"id": "mat_floor_ceramic", "ue_name": "M_Floor_Ceramic_Tile", "base_color_rgb": (0.84, 0.83, 0.80), "roughness": 0.25},
        "mat_slab_concrete": {"id": "mat_slab_concrete", "ue_name": "M_Structure_Concrete_Slab", "base_color_rgb": (0.65, 0.66, 0.67)},
        "mat_terrace_paver": {"id": "mat_terrace_paver", "ue_name": "M_Terrace_Frostproof_Gres", "base_color_rgb": (0.52, 0.53, 0.55)},
        "mat_frame_dark": {"id": "mat_frame_dark", "ue_name": "M_Window_Frame_Anthracite", "base_color_rgb": (0.16, 0.17, 0.19), "roughness": 0.3},
        "mat_door_wood": {"id": "mat_door_wood", "ue_name": "M_Door_Oak_Modern", "base_color_rgb": (0.60, 0.42, 0.27), "roughness": 0.4},
        "mat_glass": {"id": "mat_glass", "ue_name": "M_Glass_Clear", "base_color_rgb": (0.88, 0.95, 0.98), "roughness": 0.05, "opacity": 0.2},
        "mat_roof_tile": {"id": "mat_roof_tile", "ue_name": "M_Roof_Tile_Cement_Anthracite", "base_color_rgb": (0.19, 0.20, 0.22), "roughness": 0.45},
        "mat_mep": {"id": "mat_mep", "ue_name": "M_MEP_Socket_Marker", "base_color_rgb": (0.85, 0.20, 0.15)},
    }

    # Wall layer definitions from drawing table (SO.1: 1.2cm plaster + 15cm EPS + 24cm cellular concrete + 1.5cm plaster)
    so1_layers = [
        {"role": "finish_ext", "thickness": 0.012, "material_id": "mat_wall_plaster", "z_bottom_offset": 0.0},
        {"role": "insulation", "thickness": 0.150, "material_id": "mat_insulation", "z_bottom_offset": 0.0},
        {"role": "core", "thickness": 0.240, "material_id": "mat_wall_core", "z_bottom_offset": 0.0},
        {"role": "finish_int", "thickness": 0.015, "material_id": "mat_wall_plaster", "z_bottom_offset": 0.0},
    ]
    sw1_layers = [{"role": "core", "thickness": 0.24, "material_id": "mat_wall_plaster"}]
    sw2_layers = [{"role": "core", "thickness": 0.12, "material_id": "mat_wall_plaster"}]
    sw3_layers = [{"role": "core", "thickness": 0.10, "material_id": "mat_wall_plaster"}]

    # Main roof: 40 deg gable roof along X (0..10.44), ridge at y=4.32, z_at_ridge=7.70.
    # At y=4.32, z_inner = 7.70 - 0.83 = 6.87 m (h_clear = 3.92 m above attic floor z=2.95).
    # H=220cm isoline is at distance (3.92 - 2.20)/tan(40°) = 2.05 m from ridge (y_south = 2.27, y_north = 6.37).
    # H=140cm isoline is at distance (3.92 - 1.40)/tan(40°) = 3.00 m from ridge (y_south = 1.32, y_north = 7.32).

    data = {
        "schema_version": "2.0.0",
        "project_slug": "amor_woe1092",
        "project_name": "Amor WOE1092 — Extradom / Archiportal",
        "coordinate_system": {"structural_bbox_xy": (0.00, 0.00, 10.44, 8.04)},
        "materials": materials,
        "site": {
            "plot_id": "Działka referencyjna Amor WOE1092",
            "boundary_polygon_xy": [(-5.0, -6.0), (16.0, -6.0), (16.0, 16.0), (-5.0, 16.0)],
            "wz_constraints": {
                "building_line_y_min": -2.0,
                "max_ridge_height_m": 9.00,
                "roof_slope_deg_range": (25.0, 45.0),
                "min_biologically_active_ratio": 0.50,
            },
            "terraces": [
                {
                    "id": "terrace_1_10_north",
                    "polygon_xy": [(0.00, 8.04), (5.60, 8.04), (5.60, 11.52), (0.00, 11.52)],
                    "z_bottom": -0.30,
                    "z_top": -0.02,
                    "material_id": "mat_terrace_paver",
                },
                {
                    "id": "podium_1_9_entrance",
                    "polygon_xy": [(3.72, -1.20), (6.72, -1.20), (6.72, 0.60), (3.72, 0.60)],
                    "z_bottom": -0.30,
                    "z_top": -0.02,
                    "material_id": "mat_terrace_paver",
                },
            ],
        },
        "levels": [
            {"id": "parter", "name": "Parter", "floor_index": 0, "z_floor": 0.00, "z_ceiling": 2.68, "slab_thickness": 0.27},
            {"id": "poddasze", "name": "Poddasze", "floor_index": 1, "z_floor": 2.95, "z_ceiling": 5.05, "knee_wall_height_m": 0.97},
        ],
        "walls": [
            # Parter exterior walls (with recessed entrance bay x=3.72..6.72, y=0.60)
            {"id": "w_p_south_left", "level_id": "parter", "wall_type": "exterior", "start_xy": (0.00, 0.00), "end_xy": (3.72, 0.00), "alignment": "core_left", "priority": 3, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_recess_left", "level_id": "parter", "wall_type": "exterior", "start_xy": (3.72, 0.00), "end_xy": (3.72, 0.60), "alignment": "core_left", "priority": 2, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_south_center", "level_id": "parter", "wall_type": "exterior", "start_xy": (3.72, 0.60), "end_xy": (6.72, 0.60), "alignment": "core_left", "priority": 3, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_recess_right", "level_id": "parter", "wall_type": "exterior", "start_xy": (6.72, 0.60), "end_xy": (6.72, 0.00), "alignment": "core_left", "priority": 2, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_south_right", "level_id": "parter", "wall_type": "exterior", "start_xy": (6.72, 0.00), "end_xy": (10.44, 0.00), "alignment": "core_left", "priority": 3, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_east", "level_id": "parter", "wall_type": "exterior", "start_xy": (10.44, 0.00), "end_xy": (10.44, 8.04), "alignment": "core_left", "priority": 3, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_north", "level_id": "parter", "wall_type": "exterior", "start_xy": (10.44, 8.04), "end_xy": (0.00, 8.04), "alignment": "core_left", "priority": 3, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            {"id": "w_p_west", "level_id": "parter", "wall_type": "exterior", "start_xy": (0.00, 8.04), "end_xy": (0.00, 0.00), "alignment": "core_left", "priority": 3, "z_bottom": 0.0, "z_top": 2.68, "layers": so1_layers},
            # Parter interior walls (SW.1 = 24cm loadbearing, SW.2 = 12cm partition)
            {"id": "w_p_sw1_east_core", "level_id": "parter", "wall_type": "interior_loadbearing", "start_xy": (6.60, 0.85), "end_xy": (6.60, 7.78), "alignment": "right", "priority": 2, "z_bottom": 0.0, "z_top": 2.68, "layers": sw1_layers},
            {"id": "w_p_spizarnia_west", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (3.60, 0.85), "end_xy": (3.60, 2.73), "alignment": "right", "priority": 1, "z_bottom": 0.0, "z_top": 2.68, "layers": sw2_layers},
            {"id": "w_p_spizarnia_east", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (4.50, 0.85), "end_xy": (4.50, 2.73), "alignment": "right", "priority": 1, "z_bottom": 0.0, "z_top": 2.68, "layers": sw2_layers},
            {"id": "w_p_wiatrolap_north", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (3.72, 2.73), "end_xy": (6.60, 2.73), "alignment": "left", "priority": 1, "z_bottom": 0.0, "z_top": 2.68, "layers": sw2_layers},
            {"id": "w_p_pokoj18_north", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (6.84, 3.50), "end_xy": (10.18, 3.50), "alignment": "left", "priority": 1, "z_bottom": 0.0, "z_top": 2.68, "layers": sw2_layers},
            {"id": "w_p_lazienka_west", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (8.04, 3.62), "end_xy": (8.04, 5.35), "alignment": "right", "priority": 1, "z_bottom": 0.0, "z_top": 2.68, "layers": sw2_layers},
            {"id": "w_p_kotlownia_south", "level_id": "parter", "wall_type": "interior_partition", "start_xy": (6.84, 5.25), "end_xy": (10.18, 5.25), "alignment": "left", "priority": 1, "z_bottom": 0.0, "z_top": 2.68, "layers": sw2_layers},
            # Poddasze knee, gable, and SW.3 drywall partitions
            {"id": "w_a_knee_south", "level_id": "poddasze", "wall_type": "knee_wall", "start_xy": (0.00, 0.60), "end_xy": (10.44, 0.60), "alignment": "core_left", "priority": 3, "z_bottom": 2.95, "z_top": 3.92, "layers": so1_layers},
            {"id": "w_a_knee_north", "level_id": "poddasze", "wall_type": "knee_wall", "start_xy": (10.44, 8.04), "end_xy": (0.00, 8.04), "alignment": "core_left", "priority": 3, "z_bottom": 2.95, "z_top": 3.92, "layers": so1_layers},
            {"id": "w_a_gable_east", "level_id": "poddasze", "wall_type": "gable_wall", "start_xy": (10.44, 0.60), "end_xy": (10.44, 8.04), "alignment": "core_left", "priority": 3, "z_bottom": 2.95, "z_top": 7.70, "clip_to_roof": True, "layers": so1_layers},
            {"id": "w_a_gable_west", "level_id": "poddasze", "wall_type": "gable_wall", "start_xy": (0.00, 8.04), "end_xy": (0.00, 0.60), "alignment": "core_left", "priority": 3, "z_bottom": 2.95, "z_top": 7.70, "clip_to_roof": True, "layers": so1_layers},
            {"id": "w_a_komunikacja_south", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (0.26, 3.85), "end_xy": (6.55, 3.85), "alignment": "left", "priority": 1, "z_bottom": 2.95, "z_top": 5.05, "layers": sw3_layers},
            {"id": "w_a_komunikacja_north", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (4.65, 5.27), "end_xy": (6.55, 5.27), "alignment": "left", "priority": 1, "z_bottom": 2.95, "z_top": 5.05, "layers": sw3_layers},
            {"id": "w_a_gard_pok25_div", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (2.00, 0.90), "end_xy": (2.00, 3.85), "alignment": "right", "priority": 1, "z_bottom": 2.95, "z_top": 5.05, "clip_to_roof": True, "layers": sw3_layers},
            {"id": "w_a_pok25_pok24_div", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (6.56, 0.90), "end_xy": (6.56, 4.70), "alignment": "right", "priority": 1, "z_bottom": 2.95, "z_top": 5.05, "clip_to_roof": True, "layers": sw3_layers},
            {"id": "w_a_laz_pralnia_div", "level_id": "poddasze", "wall_type": "interior_partition", "start_xy": (6.66, 4.60), "end_xy": (10.18, 4.60), "alignment": "left", "priority": 1, "z_bottom": 2.95, "z_top": 5.05, "clip_to_roof": True, "layers": sw3_layers},
        ],
        "openings": {
            "windows": [
                {"id": "win_ok4_kuchnia_s", "wall_id": "w_p_south_left", "offset_along_wall": 1.02, "width": 1.80, "height": 1.50, "sill_z": 0.85, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ok4_pokoj18_s", "wall_id": "w_p_south_right", "offset_along_wall": 1.02, "width": 1.80, "height": 1.50, "sill_z": 0.85, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ok4_salon_w", "wall_id": "w_p_west", "offset_along_wall": 2.60, "width": 1.80, "height": 1.50, "sill_z": 0.85, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ob1_salon_n", "wall_id": "w_p_north", "offset_along_wall": 6.40, "width": 2.50, "height": 2.34, "sill_z": 0.00, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ok1_kotl_n", "wall_id": "w_p_north", "offset_along_wall": 1.50, "width": 0.70, "height": 0.90, "sill_z": 1.44, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ok1_laz_e", "wall_id": "w_p_east", "offset_along_wall": 4.20, "width": 0.70, "height": 0.90, "sill_z": 1.44, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ok3_attic_w", "wall_id": "w_a_gable_west", "offset_along_wall": 2.20, "width": 1.20, "height": 1.50, "sill_z": 3.86, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "win_ok3_attic_e", "wall_id": "w_a_gable_east", "offset_along_wall": 1.80, "width": 1.20, "height": 1.50, "sill_z": 3.86, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
            ],
            "doors": [
                {"id": "door_dz1_entrance", "wall_id": "w_p_south_center", "offset_along_wall": 1.15, "width": 1.10, "height": 2.34, "sill_z": 0.0, "hinge_side": "right", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dz2_boiler_ext", "wall_id": "w_p_north", "offset_along_wall": 2.80, "width": 1.00, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dw_spizarnia", "wall_id": "w_p_spizarnia_west", "offset_along_wall": 0.45, "width": 0.80, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dw_wiatrolap", "wall_id": "w_p_wiatrolap_north", "offset_along_wall": 1.20, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dw_pokoj18", "wall_id": "w_p_pokoj18_north", "offset_along_wall": 0.60, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dw_korytarz", "wall_id": "w_p_sw1_east_core", "offset_along_wall": 3.20, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dw_lazienka", "wall_id": "w_p_lazienka_west", "offset_along_wall": 0.30, "width": 0.80, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_dw2_kotlownia", "wall_id": "w_p_kotlownia_south", "offset_along_wall": 0.20, "width": 0.90, "height": 2.10, "sill_z": 0.0, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_attic_pok25", "wall_id": "w_a_komunikacja_south", "offset_along_wall": 3.60, "width": 0.90, "height": 2.10, "sill_z": 2.95, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_attic_pok24", "wall_id": "w_a_pok25_pok24_div", "offset_along_wall": 2.60, "width": 0.90, "height": 2.10, "sill_z": 2.95, "hinge_side": "left", "swing_dir": "out", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
                {"id": "door_attic_laz22", "wall_id": "w_a_komunikacja_north", "offset_along_wall": 0.60, "width": 0.90, "height": 2.10, "sill_z": 2.95, "hinge_side": "left", "swing_dir": "in", "frame_material_id": "mat_frame_dark", "leaf_material_id": "mat_door_wood"},
            ],
            "roof_windows": [
                {"id": "rw_amor_north_1", "roof_plane_id": "rp_main_north", "center_xy": (3.20, 6.20), "width": 0.94, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_amor_north_2", "roof_plane_id": "rp_main_north", "center_xy": (6.80, 6.20), "width": 0.94, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_amor_south_1", "roof_plane_id": "rp_main_south", "center_xy": (4.00, 2.20), "width": 0.94, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_amor_south_2", "roof_plane_id": "rp_main_south", "center_xy": (5.00, 2.20), "width": 0.94, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
                {"id": "rw_amor_south_3", "roof_plane_id": "rp_main_south", "center_xy": (7.80, 2.20), "width": 0.94, "length_along_slope": 1.40, "frame_material_id": "mat_frame_dark", "glass_material_id": "mat_glass"},
            ],
        },
        "rooms": [
            # Parter (8 rooms: total = 67.38 m2 matching Extradom PDF table)
            {"id": "parter_1_1_wiatrolap", "level_id": "parter", "code": "1.1", "name": "Wiatrołap", "polygon_xy": [(4.65, 0.855), (6.55, 0.855), (6.55, 2.73), (4.65, 2.73)], "pdf_usable_area_m2": 3.56, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_2_hol", "level_id": "parter", "code": "1.2", "name": "Hol + Komunikacja", "polygon_xy": [(4.65, 2.85), (6.55, 2.85), (6.55, 7.60), (4.65, 7.60)], "pdf_usable_area_m2": 9.03, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_3_spizarnia", "level_id": "parter", "code": "1.3", "name": "Spiżarnia", "polygon_xy": [(3.72, 1.04), (4.53, 1.04), (4.53, 2.73), (3.72, 2.73)], "pdf_usable_area_m2": 1.37, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_4_salon_kuchnia", "level_id": "parter", "code": "1.4", "name": "Salon + Kuchnia", "polygon_xy": [(0.255, 0.255), (3.615, 0.255), (3.615, 2.73), (4.595, 2.73), (4.595, 7.685), (0.255, 7.685)], "pdf_usable_area_m2": 29.82, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_5_kotlownia", "level_id": "parter", "code": "1.5", "name": "Kotłownia", "polygon_xy": [(6.82, 5.47), (10.18, 5.47), (10.18, 7.78), (6.82, 7.78)], "pdf_usable_area_m2": 7.76, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_6_korytarz", "level_id": "parter", "code": "1.6", "name": "Korytarz", "polygon_xy": [(6.67, 3.85), (7.92, 3.85), (7.92, 5.35), (6.67, 5.35)], "pdf_usable_area_m2": 1.87, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_7_lazienka", "level_id": "parter", "code": "1.7", "name": "Łazienka", "polygon_xy": [(8.04, 3.85), (10.18, 3.85), (10.18, 5.35), (8.04, 5.35)], "pdf_usable_area_m2": 3.22, "floor_material_id": "mat_floor_ceramic"},
            {"id": "parter_1_8_pokoj", "level_id": "parter", "code": "1.8", "name": "Pokój", "polygon_xy": [(6.82, 0.53), (10.18, 0.53), (10.18, 3.73), (6.82, 3.73)], "pdf_usable_area_m2": 10.75, "floor_material_id": "mat_floor_wood"},
            # Poddasze (7 rooms: total usable = 49.93 m2, total floor = 65.81 m2 matching Extradom PDF table)
            {"id": "poddasze_2_1_komunikacja", "level_id": "poddasze", "code": "2.1", "name": "Komunikacja", "polygon_xy": [(4.55, 3.45), (6.55, 3.45), (6.55, 5.15), (4.55, 5.15)], "pdf_usable_area_m2": 3.40, "pdf_floor_area_m2": 3.40, "floor_material_id": "mat_floor_wood"},
            {"id": "poddasze_2_2_lazienka", "level_id": "poddasze", "code": "2.2", "name": "Łazienka", "polygon_xy": [(6.66, 4.70), (10.18, 4.70), (10.18, 6.413), (6.66, 6.413)], "pdf_usable_area_m2": 6.03, "pdf_floor_area_m2": 6.03, "floor_material_id": "mat_floor_ceramic"},
            {"id": "poddasze_2_3_pralnia", "level_id": "poddasze", "code": "2.3", "name": "Pralnia", "polygon_xy": [(6.45, 6.52), (10.18, 6.52), (10.18, 7.72), (6.45, 7.72)], "pdf_usable_area_m2": 1.59, "pdf_floor_area_m2": 4.47, "floor_material_id": "mat_floor_ceramic"},
            {"id": "poddasze_2_4_pokoj", "level_id": "poddasze", "code": "2.4", "name": "Pokój SE", "polygon_xy": [(6.66, 0.255), (10.18, 0.255), (10.18, 4.375), (6.66, 4.375)], "pdf_usable_area_m2": 11.28, "pdf_floor_area_m2": 14.50, "floor_material_id": "mat_floor_wood"},
            {"id": "poddasze_2_5_pokoj", "level_id": "poddasze", "code": "2.5", "name": "Pokój S", "polygon_xy": [(2.01, 0.255), (6.56, 0.255), (6.56, 3.398), (2.01, 3.398)], "pdf_usable_area_m2": 10.14, "pdf_floor_area_m2": 14.30, "floor_material_id": "mat_floor_wood"},
            {"id": "poddasze_2_6_garderoba", "level_id": "poddasze", "code": "2.6", "name": "Garderoba", "polygon_xy": [(0.255, 0.255), (2.005, 0.255), (2.005, 3.615), (0.255, 3.615)], "pdf_usable_area_m2": 4.28, "pdf_floor_area_m2": 5.88, "floor_material_id": "mat_floor_wood"},
            {"id": "poddasze_2_7_pokoj", "level_id": "poddasze", "code": "2.7", "name": "Pokój NW", "polygon_xy": [(0.255, 3.683), (4.455, 3.683), (4.455, 7.785), (0.255, 7.785)], "pdf_usable_area_m2": 13.21, "pdf_floor_area_m2": 17.23, "floor_material_id": "mat_floor_wood"},
        ],
        "slabs": [
            {
                "id": "slab_parter_p2",
                "level_id": "parter",
                "polygon_xy": [(0.00, 0.00), (10.44, 0.00), (10.44, 8.04), (0.00, 8.04)],
                "z_bottom": 2.68,
                "z_top": 2.95,
                "material_id": "mat_slab_concrete",
                "voids_xy": [[(4.65, 5.27), (6.55, 5.27), (6.55, 7.60), (4.65, 7.60)]],
            }
        ],
        "stairs": [
            {
                "id": "stairs_dogleg_amor",
                "from_level_id": "parter",
                "to_level_id": "poddasze",
                "stair_type": "dog_leg_landing",
                "material_id": "mat_floor_wood",
                "flights": [
                    {
                        "id": "flight_lower_7",
                        "bbox_xy": (5.60, 5.27, 6.55, 6.83),
                        "z_start": 0.00,
                        "z_end": 1.29,
                        "steps_count": 7,
                        "riser_h": 0.1844,
                        "tread_d": 0.26,
                        "direction": "+Y",
                    },
                    {
                        "id": "flight_upper_9",
                        "bbox_xy": (4.65, 4.75, 5.55, 6.83),
                        "z_start": 1.29,
                        "z_end": 2.95,
                        "steps_count": 9,
                        "riser_h": 0.1844,
                        "tread_d": 0.26,
                        "direction": "-Y",
                    },
                ],
                "landings": [
                    {"id": "landing_mid", "bbox_xy": (4.65, 6.83, 6.55, 7.75), "z_top": 1.29, "thickness": 0.16}
                ],
            }
        ],
        "roof": {
            "roof_type": "multi_pitched",
            "knee_wall_height_m": 0.97,
            "overhang_m": 0.80,
            "planes": [
                {
                    "id": "rp_main_south",
                    "polygon_xy": [(-0.80, -0.80), (11.24, -0.80), (11.24, 4.02), (-0.80, 4.02)],
                    "ridge_line_xy": ((0.00, 4.02), (10.44, 4.02)),
                    "slope_deg": 40.0,
                    "z_at_ridge": 7.70,
                    "downslope_dir_xy": (0.0, -1.0),
                    "thickness": 0.561,
                    "tile_material_id": "mat_roof_tile",
                    "soffit_material_id": "mat_floor_wood",
                    "soffit_x_bounds": (0.00, 10.44),
                },
                {
                    "id": "rp_main_north",
                    "polygon_xy": [(-0.80, 4.02), (11.24, 4.02), (11.24, 8.84), (-0.80, 8.84)],
                    "ridge_line_xy": ((0.00, 4.02), (10.44, 4.02)),
                    "slope_deg": 40.0,
                    "z_at_ridge": 7.70,
                    "downslope_dir_xy": (0.0, 1.0),
                    "thickness": 0.561,
                    "tile_material_id": "mat_roof_tile",
                    "soffit_material_id": "mat_floor_wood",
                    "soffit_x_bounds": (0.00, 10.44),
                },
                {
                    "id": "rp_terrace_canopy_d3",
                    "polygon_xy": [(-0.40, 8.04), (5.80, 8.04), (5.80, 10.44), (-0.40, 10.44)],
                    "ridge_line_xy": ((0.00, 8.04), (5.60, 8.04)),
                    "slope_deg": 25.0,
                    "z_at_ridge": 3.92,
                    "downslope_dir_xy": (0.0, 1.0),
                    "thickness": 0.25,
                    "tile_material_id": "mat_roof_tile",
                    "soffit_material_id": "mat_floor_wood",
                    "soffit_x_bounds": (0.00, 5.60),
                },
            ],
            "chimneys": [
                {"id": "chimney_schiedel_salon", "bbox_xy": (3.85, 3.85, 4.59, 4.35), "z_bottom": 0.00, "z_top": 8.30, "material_id": "mat_wall_plaster"},
                {"id": "chimney_schiedel_kotlownia", "bbox_xy": (9.75, 5.05, 10.18, 5.85), "z_bottom": 0.00, "z_top": 8.30, "material_id": "mat_wall_plaster"},
            ],
        },
        "mep_sockets": [
            {"id": "mep_amor_kuchnia_woda", "room_id": "parter_1_4_salon_kuchnia", "socket_type": "water_cold_hot", "position_xyz": (1.80, 0.35, 0.55), "material_id": "mat_mep"},
            {"id": "mep_amor_kuchnia_400v", "room_id": "parter_1_4_salon_kuchnia", "socket_type": "power_400v", "position_xyz": (0.35, 1.80, 0.35), "material_id": "mat_mep"},
            {"id": "mep_amor_kotlownia_gaz", "room_id": "parter_1_5_kotlownia", "socket_type": "gas", "position_xyz": (9.90, 6.20, 1.40), "material_id": "mat_mep"},
            {"id": "mep_amor_lazienka_parter", "room_id": "parter_1_7_lazienka", "socket_type": "water_cold_hot", "position_xyz": (9.90, 4.50, 0.55), "material_id": "mat_mep"},
            {"id": "mep_amor_lazienka_podd", "room_id": "poddasze_2_2_lazienka", "socket_type": "water_cold_hot", "position_xyz": (9.80, 5.50, 3.50), "material_id": "mat_mep"},
        ],
    }

    sg = SceneGraphV2.model_validate(data)
    OUT_JSON.write_text(json.dumps(sg.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    return sg


if __name__ == "__main__":
    build_amor_woe1092_gt()
    print(f"[OK] Saved Ground Truth -> {OUT_JSON}")

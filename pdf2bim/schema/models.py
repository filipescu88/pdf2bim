"""Pydantic v2 models for scene_graph.json v2.0 (Single Source of Truth)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
BBox2D = tuple[float, float, float, float]


class CoordinateSystemSpec(BaseModel):
    x_axis: Literal["plan_right"] = "plan_right"
    y_axis: Literal["plan_up"] = "plan_up"
    z_axis: Literal["up"] = "up"
    origin_definition: Literal["bottom_left_aabb_structural_masonry_parter_z0_finished_floor"] = (
        "bottom_left_aabb_structural_masonry_parter_z0_finished_floor"
    )
    structural_bbox_xy: BBox2D = Field(..., description="(0.0, 0.0, width_x, depth_y) of parter structural masonry")


class MaterialSpec(BaseModel):
    id: str
    ue_name: str = Field(..., pattern=r"^M_[A-Za-z0-9_]+$", description="Unreal Engine material name starting with M_")
    base_color_rgb: tuple[float, float, float] = (0.85, 0.85, 0.85)
    roughness: float = Field(0.5, ge=0.0, le=1.0)
    metallic: float = Field(0.0, ge=0.0, le=1.0)
    opacity: float = Field(1.0, ge=0.0, le=1.0)


class SiteTransformSpec(BaseModel):
    origin_easting: float = 0.0
    origin_northing: float = 0.0
    origin_elevation_masl: float = 0.0
    rotation_to_north_deg: float = Field(0.0, description="Angle in degrees from +Y (plan_up) to geographic North")


class WZConstraintsSpec(BaseModel):
    building_line_y_min: Optional[float] = None
    max_ridge_height_m: float = 9.50
    roof_slope_deg_range: tuple[float, float] = (20.0, 45.0)
    min_biologically_active_ratio: float = 0.50


class NeighborBuildingSpec(BaseModel):
    id: str
    footprint_xy: list[Point2D]
    eave_height_m: float
    ridge_height_m: float
    roof_type: Literal["gable", "hip", "flat"] = "gable"


class TerraceSpec(BaseModel):
    id: str
    polygon_xy: list[Point2D]
    z_bottom: float = -0.36
    z_top: float = -0.02
    material_id: str


class SiteSpec(BaseModel):
    plot_id: str
    transform: SiteTransformSpec = Field(default_factory=SiteTransformSpec)
    boundary_polygon_xy: list[Point2D] = Field(default_factory=list)
    elevation_points_xyz: list[Point3D] = Field(default_factory=list)
    wz_constraints: WZConstraintsSpec = Field(default_factory=WZConstraintsSpec)
    neighbors: list[NeighborBuildingSpec] = Field(default_factory=list)
    terraces: list[TerraceSpec] = Field(default_factory=list)


class LevelSpec(BaseModel):
    id: str
    name: str
    floor_index: int
    z_floor: float
    z_ceiling: float
    slab_thickness: float = 0.0
    knee_wall_height_m: Optional[float] = None


class WallLayerSpec(BaseModel):
    role: Literal["core", "insulation", "finish_ext", "finish_int"]
    thickness: float = Field(..., gt=0.0)
    material_id: str
    z_bottom_offset: float = Field(0.0, description="Vertical offset at bottom (e.g. >0 for facade cladding above plinth)")
    z_top_offset: float = 0.0


class WallSpec(BaseModel):
    id: str
    level_id: str
    wall_type: Literal["exterior", "interior_loadbearing", "interior_partition", "knee_wall", "gable_wall"]
    start_xy: Point2D
    end_xy: Point2D
    alignment: Literal["center", "left", "right", "core_left", "core_right"] = "center"
    priority: int = Field(1, description="Higher priority extends through L/T corners; lower butts against it")
    z_bottom: float
    z_top: float
    clip_to_roof: bool = False
    layers: list[WallLayerSpec] = Field(..., min_length=1)

    @property
    def total_thickness(self) -> float:
        return round(sum(layer.thickness for layer in self.layers), 4)

    @property
    def ext_insulation_thickness(self) -> float:
        return round(
            sum(layer.thickness for layer in self.layers if layer.role in ("insulation", "finish_ext")),
            4,
        )

    @property
    def core_and_int_thickness(self) -> float:
        return round(
            sum(layer.thickness for layer in self.layers if layer.role in ("core", "finish_int")),
            4,
        )

    @property
    def length(self) -> float:
        return math.hypot(self.end_xy[0] - self.start_xy[0], self.end_xy[1] - self.start_xy[1])


class WindowSpec(BaseModel):
    id: str
    wall_id: str
    offset_along_wall: float = Field(..., ge=0.0, description="Distance from wall.start_xy to opening start")
    width: float = Field(..., gt=0.0)
    height: float = Field(..., gt=0.0)
    sill_z: float
    is_french_balcony: bool = False
    frame_material_id: str
    glass_material_id: str
    sill_material_id: Optional[str] = None

    @property
    def lintel_z(self) -> float:
        return round(self.sill_z + self.height, 4)


class DoorSpec(BaseModel):
    id: str
    wall_id: str
    offset_along_wall: float = Field(..., ge=0.0)
    width: float = Field(..., gt=0.0)
    height: float = Field(..., gt=0.0)
    sill_z: float = 0.0
    hinge_side: Literal["left", "right"] = "left"
    swing_dir: Literal["in", "out"] = "in"
    open_angle_deg: float = Field(90.0, gt=0.0, le=180.0)
    frame_material_id: str
    leaf_material_id: str

    @property
    def lintel_z(self) -> float:
        return round(self.sill_z + self.height, 4)


class RoofWindowSpec(BaseModel):
    id: str
    roof_plane_id: str
    center_xy: Point2D
    width: float = Field(..., gt=0.0)
    length_along_slope: float = Field(..., gt=0.0)
    frame_material_id: str
    glass_material_id: str


class OpeningsGroupSpec(BaseModel):
    windows: list[WindowSpec] = Field(default_factory=list)
    doors: list[DoorSpec] = Field(default_factory=list)
    roof_windows: list[RoofWindowSpec] = Field(default_factory=list)


class RoomSpec(BaseModel):
    id: str
    level_id: str
    code: str
    name: str
    polygon_xy: list[Point2D] = Field(..., min_length=3)
    pdf_usable_area_m2: float = Field(..., gt=0.0, description="Usable area in m2 from PDF table (PN-ISO 9836)")
    pdf_floor_area_m2: Optional[float] = Field(None, gt=0.0, description="Total floor area in m2 if listed in PDF")
    floor_material_id: str
    floor_thickness: float = 0.02


class SlabSpec(BaseModel):
    id: str
    level_id: str
    polygon_xy: list[Point2D] = Field(..., min_length=3)
    z_bottom: float
    z_top: float
    material_id: str
    voids_xy: list[list[Point2D]] = Field(default_factory=list)


class StairFlightSpec(BaseModel):
    id: str
    bbox_xy: BBox2D
    z_start: float
    z_end: float
    steps_count: int = Field(..., ge=1)
    riser_h: float = Field(..., gt=0.0)
    tread_d: float = Field(..., gt=0.0)
    direction: Literal["+X", "-X", "+Y", "-Y"]
    waist_slab_thickness: float = 0.16


class StairLandingSpec(BaseModel):
    id: str
    bbox_xy: BBox2D
    z_top: float
    thickness: float = 0.16


class RailingSpec(BaseModel):
    id: str
    polyline_xy: list[Point2D] = Field(..., min_length=2)
    z_base: float
    height: float = 1.05
    material_id: str


class StairSpec(BaseModel):
    id: str
    from_level_id: str
    to_level_id: str
    stair_type: Literal["straight", "dog_leg_landing", "l_shaped"]
    material_id: str
    flights: list[StairFlightSpec] = Field(..., min_length=1)
    landings: list[StairLandingSpec] = Field(default_factory=list)
    railings: list[RailingSpec] = Field(default_factory=list)


class RoofPlaneSpec(BaseModel):
    id: str
    polygon_xy: list[Point2D] = Field(..., min_length=3)
    ridge_line_xy: tuple[Point2D, Point2D]
    slope_deg: float = Field(..., ge=0.0, le=85.0)
    z_at_ridge: float
    downslope_dir_xy: Point2D = Field(..., description="Unit vector in XY pointing down the slope perpendicular to ridge")
    thickness: float = 0.28
    tile_material_id: str
    soffit_material_id: str
    soffit_x_bounds: Optional[tuple[float, float]] = None

    def z_inner_at(self, x: float, y: float) -> float:
        """Compute inner (bottom) Z of the roof plane at plan point (x, y)."""
        rx0, ry0 = self.ridge_line_xy[0]
        dx, dy = self.downslope_dir_xy
        dist = max(0.0, (x - rx0) * dx + (y - ry0) * dy)
        drop = dist * math.tan(math.radians(self.slope_deg))
        return round(self.z_at_ridge - drop - self.thickness, 4)


class ChimneySpec(BaseModel):
    id: str
    bbox_xy: BBox2D
    z_bottom: float
    z_top: float
    material_id: str


class RoofSpec(BaseModel):
    roof_type: Literal["gable", "hip", "multi_pitched", "shed", "flat"]
    knee_wall_height_m: float = 1.40
    overhang_m: float = 0.65
    planes: list[RoofPlaneSpec] = Field(..., min_length=1)
    chimneys: list[ChimneySpec] = Field(default_factory=list)


class MepSocketSpec(BaseModel):
    id: str
    room_id: str
    socket_type: Literal["water_cold_hot", "sewage_drain", "power_400v", "power_230v", "gas", "ventilation_flue"]
    position_xyz: Point3D
    material_id: str


class CustomBoxSpec(BaseModel):
    id: str
    level_id: str
    bbox_xy: BBox2D
    z_bottom: float
    z_top: float
    material_id: str
    collidable: bool = True


class FurnitureItemSpec(BaseModel):
    id: str
    room_id: str
    asset: str
    category: str
    bbox_xy: BBox2D
    z_range: tuple[float, float]
    back_side: Literal["N", "S", "E", "W"] = "N"


class PipelineSettingsSpec(BaseModel):
    include_furniture: bool = False
    target_engine: Literal["unreal_engine", "webxr"] = "unreal_engine"
    is_ground_truth_reference: bool = True


class SceneGraphV2(BaseModel):
    schema_version: Literal["2.0.0"] = "2.0.0"
    project_slug: str
    project_name: str
    units: Literal["m"] = "m"
    settings: PipelineSettingsSpec = Field(default_factory=PipelineSettingsSpec)
    coordinate_system: CoordinateSystemSpec
    materials: dict[str, MaterialSpec]
    site: SiteSpec
    levels: list[LevelSpec] = Field(..., min_length=1)
    walls: list[WallSpec] = Field(default_factory=list)
    openings: OpeningsGroupSpec = Field(default_factory=OpeningsGroupSpec)
    rooms: list[RoomSpec] = Field(default_factory=list)
    slabs: list[SlabSpec] = Field(default_factory=list)
    stairs: list[StairSpec] = Field(default_factory=list)
    roof: RoofSpec
    mep_sockets: list[MepSocketSpec] = Field(default_factory=list)
    custom_elements: list[CustomBoxSpec] = Field(default_factory=list)
    furniture: list[FurnitureItemSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_id_references(self) -> "SceneGraphV2":
        mat_ids = set(self.materials.keys())
        level_ids = {lv.id for lv in self.levels}
        wall_ids = {w.id for w in self.walls}
        room_ids = {r.id for r in self.rooms}
        plane_ids = {p.id for p in self.roof.planes}

        for w in self.walls:
            if w.level_id not in level_ids:
                raise ValueError(f"Wall '{w.id}' references unknown level_id '{w.level_id}'")
            for lay in w.layers:
                if lay.material_id not in mat_ids:
                    raise ValueError(f"Wall '{w.id}' layer references unknown material_id '{lay.material_id}'")

        for win in self.openings.windows:
            if win.wall_id not in wall_ids:
                raise ValueError(f"Window '{win.id}' references unknown wall_id '{win.wall_id}'")
            if win.frame_material_id not in mat_ids or win.glass_material_id not in mat_ids:
                raise ValueError(f"Window '{win.id}' references unknown material_id")

        for dr in self.openings.doors:
            if dr.wall_id not in wall_ids:
                raise ValueError(f"Door '{dr.id}' references unknown wall_id '{dr.wall_id}'")
            if dr.frame_material_id not in mat_ids or dr.leaf_material_id not in mat_ids:
                raise ValueError(f"Door '{dr.id}' references unknown material_id")

        for rw in self.openings.roof_windows:
            if rw.roof_plane_id not in plane_ids:
                raise ValueError(f"RoofWindow '{rw.id}' references unknown roof_plane_id '{rw.roof_plane_id}'")

        for rm in self.rooms:
            if rm.level_id not in level_ids:
                raise ValueError(f"Room '{rm.id}' references unknown level_id '{rm.level_id}'")
            if rm.floor_material_id not in mat_ids:
                raise ValueError(f"Room '{rm.id}' references unknown floor_material_id '{rm.floor_material_id}'")

        for st in self.stairs:
            if st.from_level_id not in level_ids or st.to_level_id not in level_ids:
                raise ValueError(f"Stair '{st.id}' references unknown level_id")

        for mep in self.mep_sockets:
            if mep.room_id not in room_ids:
                raise ValueError(f"MepSocket '{mep.id}' references unknown room_id '{mep.room_id}'")

        return self


def export_json_schema(out_path: Path) -> dict:
    schema = SceneGraphV2.model_json_schema()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    return schema

"""Validation package (2D/3D topology, PN-ISO 9836 area math, WZ constraints, Laser Marker QA)."""

from pdf2bim.validate.markers import (
    LaserMarkerIssue,
    MarkerStatus,
    MarkerStore,
    add_laser_marker,
    load_markers,
    save_markers,
    transition_markers_on_rebuild,
    verify_marker_issue,
)
from pdf2bim.validate.validator import (
    RoomAreaAudit,
    ValidationIssue,
    ValidationReport,
    compute_door_swing_polygon,
    compute_pn_iso_9836_area,
    validate_scene_graph_v2,
    wall_footprint_polygon,
)

__all__ = [
    "LaserMarkerIssue",
    "MarkerStatus",
    "MarkerStore",
    "RoomAreaAudit",
    "ValidationIssue",
    "ValidationReport",
    "add_laser_marker",
    "compute_door_swing_polygon",
    "compute_pn_iso_9836_area",
    "load_markers",
    "save_markers",
    "transition_markers_on_rebuild",
    "validate_scene_graph_v2",
    "verify_marker_issue",
    "wall_footprint_polygon",
]

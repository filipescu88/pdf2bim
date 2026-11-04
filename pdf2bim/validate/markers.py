"""Laser Marker QA lifecycle manager (`open -> needs_verification -> verified`) linked to `element_id` (Step 4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from pdf2bim.schema import SceneGraphV2

MarkerStatus = Literal["open", "needs_verification", "verified"]


class LaserMarkerIssue(BaseModel):
    marker_id: str
    element_id: str
    node_name: str
    category: str
    level_id: str = "parter"
    hit_xyz: tuple[float, float, float]
    camera_xyz: tuple[float, float, float]
    note: str
    status: MarkerStatus = "open"
    screenshot_path: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MarkerStore(BaseModel):
    project_slug: str
    markers: list[LaserMarkerIssue] = Field(default_factory=list)


def load_markers(project_dir: Path, project_slug: str | None = None) -> MarkerStore:
    markers_path = Path(project_dir) / "review" / "markers.json"
    if markers_path.is_file():
        return MarkerStore.model_validate_json(markers_path.read_text(encoding="utf-8"))
    slug = project_slug or Path(project_dir).name
    return MarkerStore(project_slug=slug, markers=[])


def save_markers(project_dir: Path, store: MarkerStore) -> Path:
    rev_dir = Path(project_dir) / "review"
    rev_dir.mkdir(parents=True, exist_ok=True)
    markers_path = rev_dir / "markers.json"
    markers_path.write_text(
        json.dumps(store.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return markers_path


def add_laser_marker(
    project_dir: Path,
    element_id: str,
    node_name: str,
    category: str,
    hit_xyz: tuple[float, float, float],
    camera_xyz: tuple[float, float, float],
    note: str,
    level_id: str = "parter",
    screenshot_path: str | None = None,
) -> LaserMarkerIssue:
    """Create a new `open` Laser Marker issue linked to `element_id` in `review/markers.json`."""
    store = load_markers(project_dir)
    next_num = len(store.markers) + 1
    issue = LaserMarkerIssue(
        marker_id=f"M-{next_num:03d}",
        element_id=element_id,
        node_name=node_name,
        category=category,
        level_id=level_id,
        hit_xyz=hit_xyz,
        camera_xyz=camera_xyz,
        note=note,
        status="open",
        screenshot_path=screenshot_path,
    )
    store.markers.append(issue)
    save_markers(project_dir, store)
    return issue


def transition_markers_on_rebuild(project_dir: Path, sg: SceneGraphV2) -> MarkerStore:
    """Transition `open` markers whose `element_id` is compiled in `sg` to `needs_verification`."""
    store = load_markers(project_dir, project_slug=sg.project_slug)
    known_ids: set[str] = set()
    for w in sg.walls:
        known_ids.add(w.id)
    for win in sg.openings.windows:
        known_ids.add(win.id)
    for door in sg.openings.doors:
        known_ids.add(door.id)
    for rw in sg.openings.roof_windows:
        known_ids.add(rw.id)
    for r in sg.rooms:
        known_ids.add(r.id)
    for s in sg.slabs:
        known_ids.add(s.id)
    for st in sg.stairs:
        known_ids.add(st.id)
    for rp in sg.roof.planes:
        known_ids.add(rp.id)
        known_ids.add(f"soffit_{rp.id}")
    for mep in sg.mep_sockets:
        known_ids.add(mep.id)

    now_iso = datetime.now(timezone.utc).isoformat()
    for m in store.markers:
        if m.status == "open" and m.element_id in known_ids:
            m.status = "needs_verification"
            m.updated_at = now_iso

    save_markers(project_dir, store)
    return store


def verify_marker_issue(project_dir: Path, marker_id: str) -> LaserMarkerIssue:
    """Transition a marker from `open` or `needs_verification` to `verified`."""
    store = load_markers(project_dir)
    for m in store.markers:
        if m.marker_id == marker_id:
            m.status = "verified"
            m.updated_at = datetime.now(timezone.utc).isoformat()
            save_markers(project_dir, store)
            return m
    raise KeyError(f"Marker '{marker_id}' not found in {project_dir}")

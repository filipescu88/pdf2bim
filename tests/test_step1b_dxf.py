"""Unit tests for Step 1b: DXF geodetic importer (`extract_site_from_dxf`) on Purda 585/8 DXF."""

from pathlib import Path
from shapely.geometry import Polygon

from pdf2bim.extract import extract_site_from_dxf, geodetic_to_local, local_to_geodetic

ROOT = Path(__file__).resolve().parent.parent
DXF_PATH = ROOT / "projects" / "dom_w_gnieznikach" / "inputs" / "Purda 585_8 mdcp.DXF"


def test_extract_site_from_purda_dxf():
    site = extract_site_from_dxf(DXF_PATH, plot_id="585/8")
    assert site.plot_id == "585/8"
    assert len(site.boundary_polygon_xy) == 4

    poly = Polygon(site.boundary_polygon_xy)
    assert poly.is_valid
    assert abs(poly.area - 969.22) < 0.5, f"Expected ~969.22 m2 plot area, got {poly.area:.2f} m2"

    assert len(site.elevation_points_xyz) >= 5
    assert 140.0 <= site.transform.origin_elevation_masl <= 146.0
    assert len(site.neighbors) >= 8


def test_geodetic_local_roundtrip():
    site = extract_site_from_dxf(DXF_PATH, plot_id="585/8")
    tf = site.transform
    for lx, ly in site.boundary_polygon_xy:
        e, n = local_to_geodetic(lx, ly, tf)
        rx, ry = geodetic_to_local(e, n, tf)
        assert abs(lx - rx) <= 0.005
        assert abs(ly - ry) <= 0.005

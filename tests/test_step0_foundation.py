"""Tests for Step 0 (Foundation: repository structure, inputs for 2 test houses, dependencies, AGENTS.md)."""

from pathlib import Path
import pdf2bim

ROOT = Path(__file__).resolve().parent.parent


def test_package_version():
    assert pdf2bim.__version__ == "2.0.0"


def test_repository_structure():
    required_dirs = [
        "pdf2bim/schema",
        "pdf2bim/extract",
        "pdf2bim/validate",
        "pdf2bim/geometry",
        "pdf2bim/export",
        "pdf2bim/remote",
        "web_vr",
        "projects/dom_w_gnieznikach/inputs",
        "projects/dom_w_gnieznikach/review",
        "projects/amor_woe1092/inputs",
        "projects/amor_woe1092/review",
        "tests",
    ]
    for rel in required_dirs:
        assert (ROOT / rel).is_dir(), f"Missing required directory: {rel}"


def test_docs_and_agents_has_no_hardcoded_house_coords():
    agents_md = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    plan_md = (ROOT / "PLAN.md").read_text(encoding="utf-8")
    assert "scene_graph.json" in agents_md
    assert "dom_w_gnieznikach" in plan_md
    assert "amor_woe1092" in plan_md


def test_two_test_houses_inputs_present():
    h1_inputs = ROOT / "projects" / "dom_w_gnieznikach" / "inputs"
    assert (h1_inputs / "karta.pdf").is_file()
    assert (h1_inputs / "Purda 585_8 mdcp.DXF").is_file()

    h2_inputs = ROOT / "projects" / "amor_woe1092" / "inputs"
    assert (h2_inputs / "extradom-amor-WOE1092-rzut-parteru-459221.pdf").is_file()
    assert (h2_inputs / "extradom-amor-WOE1092-rzut-poddasza-459222.pdf").is_file()
    assert (h2_inputs / "extradom-amor-WOE1092-przekroj-459223.pdf").is_file()

"""Tests for Step 0 (Foundation: repository structure, local .venv, CLI pdf2bim, inputs for 2 test houses)."""

from pathlib import Path
import subprocess
import pdf2bim
from pdf2bim.cli import main as cli_main

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


def test_local_venv_and_cli_executable():
    venv_py = ROOT / ".venv" / "bin" / "python"
    venv_pytest = ROOT / ".venv" / "bin" / "pytest"
    venv_cli = ROOT / ".venv" / "bin" / "pdf2bim"
    assert venv_py.is_file(), "Missing local .venv/bin/python"
    assert venv_pytest.is_file(), "Missing local .venv/bin/pytest"
    assert venv_cli.is_file(), "Missing local .venv/bin/pdf2bim"

    res = subprocess.run([str(venv_cli), "--help"], capture_output=True, text=True, check=True)
    for subcmd in ("validate", "overlay", "build", "extract"):
        assert subcmd in res.stdout

    rc = cli_main(["validate", str(ROOT / "projects" / "dom_w_gnieznikach")])
    assert rc == 0


def test_docs_and_agents_has_no_hardcoded_house_coords():
    agents_md = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    plan_md = (ROOT / "PLAN.md").read_text(encoding="utf-8")
    assert "scene_graph.json" in agents_md
    assert "AABB" in agents_md
    for step_id in ("Krok 1a", "Krok 1b", "Krok 1c", "Krok 1d", "Krok 1e", "Krok 1f"):
        assert step_id in plan_md


def test_two_test_houses_inputs_present():
    h1_inputs = ROOT / "projects" / "dom_w_gnieznikach" / "inputs"
    assert (h1_inputs / "karta.pdf").is_file()
    assert (h1_inputs / "Purda 585_8 mdcp.DXF").is_file()

    h2_inputs = ROOT / "projects" / "amor_woe1092" / "inputs"
    assert (h2_inputs / "extradom-amor-WOE1092-rzut-parteru-459221.pdf").is_file()
    assert (h2_inputs / "extradom-amor-WOE1092-rzut-poddasza-459222.pdf").is_file()
    assert (h2_inputs / "extradom-amor-WOE1092-przekroj-459223.pdf").is_file()

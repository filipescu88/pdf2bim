"""Unified CLI entry point for pdf2bim (`pdf2bim validate|overlay|build|extract <project_dir>`)."""

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdf2bim",
        description="Deterministic Forward Pipeline: PDF/DXF/WZ -> scene_graph.json v2 -> 3D BIM & WebXR",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd_name, help_text in [
        ("validate", "Validate scene_graph.json v2 (schema, topology, PN-ISO 9836 areas, WZ)"),
        ("overlay", "Generate 2D overlay preview on PDF raster and compute alignment metrics"),
        ("build", "Full end-to-end build: validate -> overlay -> compile 3D GLB/USDA -> check 3D invariants"),
        ("extract", "Semi-automatic vector/raster extraction from PDF/DXF to draft scene_graph.json"),
    ]:
        p = sub.add_parser(cmd_name, help=help_text)
        p.add_argument("project_dir", type=Path, help="Path to project directory (e.g. projects/dom_w_gnieznikach)")

    args = parser.parse_args(argv)
    proj_dir = args.project_dir.resolve()
    if not proj_dir.is_dir():
        print(f"[ERROR] Project directory not found: {proj_dir}", file=sys.stderr)
        return 1

    print(f"[pdf2bim] Command '{args.command}' initialized for project: {proj_dir.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

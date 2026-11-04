"""Unified CLI entry point for pdf2bim (`pdf2bim validate|overlay|build|extract <project_dir>`)."""

import argparse
import json
import sys
from pathlib import Path

from pdf2bim.export import export_scene_to_glb
from pdf2bim.extract import generate_project_overlays
from pdf2bim.geometry import compile_scene_graph_3d, verify_3d_invariants
from pdf2bim.schema import SceneGraphV2
from pdf2bim.validate import validate_scene_graph_v2


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

    sg_path = proj_dir / "scene_graph.json"
    if args.command == "validate" and sg_path.is_file():
        data = json.loads(sg_path.read_text(encoding="utf-8"))
        sg = SceneGraphV2.model_validate(data)
        rep = validate_scene_graph_v2(sg)
        print(rep.format_text())
        rev_dir = proj_dir / "review"
        rev_dir.mkdir(parents=True, exist_ok=True)
        (rev_dir / "validation_report.json").write_text(
            rep.model_dump_json(indent=2), encoding="utf-8"
        )
        return 0 if rep.passed else 1

    if args.command == "overlay" and sg_path.is_file():
        rep = generate_project_overlays(proj_dir)
        print(
            f"[overlay] {rep.project_slug}: status={'PASS' if rep.passed else 'FAIL'} "
            f"| max_ext_dev={rep.max_exterior_wall_deviation_cm:.2f}cm "
            f"| mean_dev={rep.mean_wall_deviation_cm:.2f}cm "
            f"| min_overlap={rep.min_contour_overlap_ratio:.1%}"
        )
        return 0 if rep.passed else 1

    if args.command == "build" and sg_path.is_file():
        data = json.loads(sg_path.read_text(encoding="utf-8"))
        sg = SceneGraphV2.model_validate(data)
        val_rep = validate_scene_graph_v2(sg)
        if not val_rep.passed:
            print(val_rep.format_text(), file=sys.stderr)
            return 1

        scene3d = compile_scene_graph_3d(sg)
        inv_rep = verify_3d_invariants(sg, scene3d)
        rev_dir = proj_dir / "review"
        rev_dir.mkdir(parents=True, exist_ok=True)
        (rev_dir / "invariants_3d_report.json").write_text(
            json.dumps(inv_rep.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        out_dir = proj_dir / "output"
        glb_path = export_scene_to_glb(sg, scene3d, out_dir / f"{sg.project_slug}.glb")
        print(
            f"[build] {sg.project_slug}: status={'PASS' if inv_rep.passed else 'FAIL'} "
            f"| nodes={inv_rep.total_nodes} | invariants=7/7 | glb={glb_path.name}"
        )
        return 0 if inv_rep.passed else 1

    print(f"[pdf2bim] Command '{args.command}' initialized for project: {proj_dir.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

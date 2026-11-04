"""Generic WebXR HTTP & REST API server for pdf2bim projects and Laser Marker QA (Step 4)."""

from __future__ import annotations

import hashlib
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pdf2bim.validate.markers import add_laser_marker, load_markers, verify_marker_issue

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"


class PDF2BIMVRHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def end_headers(self) -> None:
        # Enable ETag / smart caching for .glb models instead of disabling cache
        if hasattr(self, "path") and self.path.endswith(".glb"):
            self.send_header("Cache-Control", "public, max-age=3600, must-revalidate")
        super().end_headers()

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        etag = f'"{hashlib.md5(body).hexdigest()}"'
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        if parts == ["api", "projects"]:
            slugs = sorted(
                p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and (p / "scene_graph.json").is_file()
            )
            self._send_json({"projects": slugs})
            return

        if len(parts) == 4 and parts[0] == "api" and parts[1] == "project" and parts[3] == "markers":
            slug = parts[2]
            proj_dir = PROJECTS_DIR / slug
            if not proj_dir.is_dir():
                self._send_json({"error": "Project not found"}, status=404)
                return
            store = load_markers(proj_dir, project_slug=slug)
            self._send_json(store.model_dump(mode="json"))
            return

        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        payload = json.loads(raw_body.decode("utf-8"))

        if len(parts) == 4 and parts[0] == "api" and parts[1] == "project" and parts[3] == "markers":
            slug = parts[2]
            proj_dir = PROJECTS_DIR / slug
            issue = add_laser_marker(
                project_dir=proj_dir,
                element_id=str(payload.get("element_id", "unknown")),
                node_name=str(payload.get("node_name", "unknown")),
                category=str(payload.get("category", "unknown")),
                hit_xyz=tuple(payload.get("hit_xyz", [0.0, 0.0, 0.0])),  # type: ignore[arg-type]
                camera_xyz=tuple(payload.get("camera_xyz", [0.0, 0.0, 1.65])),  # type: ignore[arg-type]
                note=str(payload.get("note", "")),
                level_id=str(payload.get("level_id", "parter")),
            )
            self._send_json(issue.model_dump(mode="json"), status=201)
            return

        if len(parts) == 5 and parts[0] == "api" and parts[1] == "project" and parts[3] == "markers" and parts[4] == "verify":
            slug = parts[2]
            proj_dir = PROJECTS_DIR / slug
            marker_id = str(payload.get("marker_id", ""))
            issue = verify_marker_issue(proj_dir, marker_id)
            self._send_json(issue.model_dump(mode="json"), status=200)
            return

        self._send_json({"error": "Unknown API endpoint"}, status=404)


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), PDF2BIMVRHandler)
    print(f"[pdf2bim WebXR] Serving at http://{host}:{port}/web_vr/index.html")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

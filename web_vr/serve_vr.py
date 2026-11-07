#!/usr/bin/env python3
"""Generic Web & WebXR HTTP (:8080) + HTTPS/TLS (:8443) Server & Laser Marker QA REST API for pdf2bim."""

from __future__ import annotations

import hashlib
import json
import ssl
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pdf2bim.validate.markers import add_laser_marker, load_markers, verify_marker_issue

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_VR_DIR = REPO_ROOT / "web_vr"
PROJECTS_DIR = REPO_ROOT / "projects"
CERT_FILE = WEB_VR_DIR / "quest3_cert.pem"
KEY_FILE = WEB_VR_DIR / "quest3_key.pem"


def get_local_ips() -> list[str]:
    ips: list[str] = []
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        for ip in out.split():
            if ":" not in ip:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        ips = ["127.0.0.1"]
    return ips


def ensure_ssl_cert(ips: list[str] | None = None) -> tuple[Path, Path]:
    """Generate a self-signed X.509 SSL certificate with SANs for LAN WebXR if not present."""
    if CERT_FILE.is_file() and KEY_FILE.is_file():
        return CERT_FILE, KEY_FILE
    WEB_VR_DIR.mkdir(parents=True, exist_ok=True)
    host_ips = ips if ips is not None else get_local_ips()
    san_entries = [f"IP:{ip}" for ip in host_ips] + ["DNS:localhost", "IP:127.0.0.1"]
    san = ",".join(dict.fromkeys(san_entries))
    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(KEY_FILE),
        "-out",
        str(CERT_FILE),
        "-days",
        "365",
        "-subj",
        "/CN=PDF2BIM-WebXR",
        "-addext",
        f"subjectAltName={san}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return CERT_FILE, KEY_FILE


class PDF2BIMVRHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if hasattr(self, "path") and (self.path.endswith(".glb") or "/textures/" in self.path):
            self.send_header("Cache-Control", "public, max-age=3600, must-revalidate")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

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

        if (
            len(parts) == 5
            and parts[0] == "api"
            and parts[1] == "project"
            and parts[3] == "markers"
            and parts[4] == "verify"
        ):
            slug = parts[2]
            proj_dir = PROJECTS_DIR / slug
            marker_id = str(payload.get("marker_id", ""))
            issue = verify_marker_issue(proj_dir, marker_id)
            self._send_json(issue.model_dump(mode="json"), status=200)
            return

        self._send_json({"error": "Unknown API endpoint"}, status=404)


def run_server(host: str = "0.0.0.0", http_port: int = 8080, https_port: int = 8443) -> None:
    ips = get_local_ips()
    cert_path, key_path = ensure_ssl_cert(ips)
    primary_ip = ips[0] if ips else "127.0.0.1"

    http_server = ThreadingHTTPServer((host, http_port), PDF2BIMVRHandler)
    https_server = ThreadingHTTPServer((host, https_port), PDF2BIMVRHandler)

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    https_server.socket = ssl_ctx.wrap_socket(https_server.socket, server_side=True)

    t_http = threading.Thread(target=http_server.serve_forever, daemon=True)
    t_http.start()

    print(f"[pdf2bim Web]   HTTP  -> http://{primary_ip}:{http_port}/web_vr/index.html")
    print(f"[pdf2bim WebXR] HTTPS -> https://{primary_ip}:{https_port}/web_vr/index.html (SSL cert: {cert_path.name})")
    https_server.serve_forever()


if __name__ == "__main__":
    run_server()

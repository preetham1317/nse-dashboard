"""Local-only preview server for the dashboard. Serves exactly two directories
(dashboard/ and data/) and nothing else from the repo root - in particular this
never exposes .env, .git, or .venv. Binds to loopback only. Dev/preview use only,
not what runs in production (GitHub Pages serves the static files directly).
"""

import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_TOP_LEVEL = {"dashboard", "data"}
PORT = 8642


class ScopedHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _is_allowed(self, path: str) -> bool:
        clean = path.split("?", 1)[0].lstrip("/")
        if clean == "":
            return True  # root listing -> redirected to dashboard/ below
        top_level = clean.split("/", 1)[0]
        return top_level in ALLOWED_TOP_LEVEL

    def do_GET(self):
        if self.path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", "/dashboard/index.html")
            self.end_headers()
            return
        if not self._is_allowed(self.path):
            self.send_error(404, "Not found")
            return
        super().do_GET()


if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), ScopedHandler) as httpd:
        print(f"Serving dashboard/ and data/ only, on http://127.0.0.1:{PORT}")
        httpd.serve_forever()

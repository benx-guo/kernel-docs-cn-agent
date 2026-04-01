#!/usr/bin/env python3
"""Live-reload server for kernel HTML docs.

Watches RST files for changes, runs incremental `make htmldocs`,
and auto-refreshes the browser via injected JS polling.

Usage:
    python3 scripts/serve-docs.py [--port PORT]
"""

import http.server
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
KERNEL_DIR = PROJECT_DIR / "linux"
DOC_SRC = KERNEL_DIR / "Documentation"
DOC_OUT = DOC_SRC / "output"

DEFAULT_PORT = 8080

# Monotonic counter bumped after each rebuild
_build_version = 0
_build_lock = threading.Lock()
_build_version_lock = threading.Lock()

RELOAD_SCRIPT = """
<script>
(function() {
  var v = __BUILD_VERSION__;
  setInterval(function() {
    fetch('/__version__').then(function(r) { return r.text(); }).then(function(t) {
      if (parseInt(t) > v) location.reload();
    }).catch(function(){});
  }, 1500);
})();
</script>
"""


def do_build():
    """Run make htmldocs (incremental)."""
    global _build_version
    with _build_lock:
        print("[serve-docs] Building...", flush=True)
        t0 = time.monotonic()
        r = subprocess.run(
            ["make", "htmldocs"],
            cwd=KERNEL_DIR,
            capture_output=True,
            text=True,
        )
        elapsed = time.monotonic() - t0
        if r.returncode == 0:
            with _build_version_lock:
                _build_version += 1
            print(f"[serve-docs] Build OK ({elapsed:.1f}s, v={_build_version})", flush=True)
        else:
            print(f"[serve-docs] Build FAILED ({elapsed:.1f}s)", flush=True)
            # Print last few lines of stderr
            for line in r.stderr.strip().splitlines()[-10:]:
                print(f"  {line}", flush=True)


def watch_and_rebuild():
    """Watch RST files and trigger rebuild on change."""
    from watchfiles import watch, Change

    print("[serve-docs] Watching for RST changes...", flush=True)
    def rst_filter(change, path):
        if "output" in Path(path).parts:
            return False
        return path.endswith(".rst")

    for changes in watch(str(DOC_SRC), watch_filter=rst_filter):
        files = [p for _, p in changes]
        short = [str(Path(p).relative_to(DOC_SRC)) for p in files]
        print(f"[serve-docs] Changed: {', '.join(short)}", flush=True)
        do_build()


class LiveHandler(http.server.SimpleHTTPRequestHandler):
    """Serve static HTML docs with live-reload injection."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOC_OUT), **kwargs)

    def do_GET(self):
        if self.path == "/__version__":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with _build_version_lock:
                self.wfile.write(str(_build_version).encode())
            return
        super().do_GET()

    def end_headers(self):
        # Inject reload script into HTML responses
        if hasattr(self, '_headers_buffer'):
            for i, h in enumerate(self._headers_buffer):
                if b'Content-Type' in h and b'text/html' in h:
                    self._inject_reload = True
                    break
        super().end_headers()

    def copyfile(self, source, outputfile):
        """Override to inject reload script before </body>."""
        if getattr(self, '_inject_reload', False):
            self._inject_reload = False
            content = source.read()
            try:
                text = content.decode('utf-8')
                script = RELOAD_SCRIPT.replace('__BUILD_VERSION__', str(_build_version))
                text = text.replace('</body>', script + '</body>')
                outputfile.write(text.encode('utf-8'))
            except (UnicodeDecodeError, Exception):
                outputfile.write(content)
        else:
            super().copyfile(source, outputfile)

    def log_message(self, fmt, *args):
        # Quieter logging — skip 200s for static assets
        if len(args) >= 2 and '200' in str(args[1]):
            return
        sys.stderr.write(f"[serve-docs] {args[0]}\n")


def main():
    port = DEFAULT_PORT
    args = sys.argv[1:]
    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = int(args[idx + 1])

    if not DOC_OUT.is_dir():
        print("[serve-docs] No pre-built docs found, running initial build...")
        do_build()

    if not DOC_OUT.is_dir():
        print(f"Error: {DOC_OUT} does not exist after build.")
        sys.exit(1)

    # Start watcher thread
    watcher = threading.Thread(target=watch_and_rebuild, daemon=True)
    watcher.start()

    server = http.server.HTTPServer(("0.0.0.0", port), LiveHandler)
    print(f"[serve-docs] Serving docs at http://0.0.0.0:{port}/", flush=True)
    print(f"[serve-docs] Chinese translations: http://0.0.0.0:{port}/translations/zh_CN/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()

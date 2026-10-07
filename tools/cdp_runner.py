"""CDP transport — the only module that talks to the browser.

Reusable Chrome/Edge DevTools-Protocol client (websocket, no framework).
Design rules that come from real field bugs (see docs/PLAYBOOK.md):

* `run_probe()` ALWAYS wraps the probe source in "(src)(opts)" so a probe
  can never silently "pass" because a function expression was never called.
* `evaluate()` is the raw escape hatch — remember it does NOT auto-call.
* Attach retries: the browser needs a moment before /json/list answers.

Usage:
    from cdp_runner import CDPRunner
    with CDPRunner(port=9400) as r:
        r.goto("https://example.com")
        issues = r.run_probe(open("probes/layout_probe.js").read())
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    sys.exit("missing dependency: pip install websocket-client")

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/microsoft-edge",
    "/usr/bin/microsoft-edge-stable",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "chromium", "chromium-browser",
)


def find_browser() -> str:
    env = os.environ.get("LIGEO_BROWSER")
    if env:
        return env
    for c in EDGE_CANDIDATES:
        if c in ("google-chrome", "chromium", "chromium-browser") or os.path.exists(c):
            return c
    raise FileNotFoundError("no Edge/Chrome found — set LIGEO_BROWSER")


class CDPRunner:
    def __init__(self, port: int = 9400, profile_dir=None, headless: bool = True):
        self.port = port
        self.profile_dir = Path(profile_dir) if profile_dir else \
            Path(__file__).resolve().parent / f"edge-profile-{port}"
        self.headless = headless
        self.proc, self.ws, self._id, self.owned = None, None, 0, False

    # -------------------------------------------------------------- lifecycle
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def _find_page(self, timeout_s: float = 15.0):
        last = None
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{self.port}/json/list", timeout=1) as r:
                    tabs = json.load(r)
                return next(t for t in tabs if t["type"] == "page")
            except Exception as e:
                last = e
                time.sleep(0.25)
        raise RuntimeError(f"cannot attach to browser on {self.port}: {last!r}")

    def start(self):
        # Adopt-or-start: a browser already answering on this port is REUSED
        # (never double-launch, never kill a browser we did not spawn). Flags
        # relax the file:// origin so canvas pixel reads work for local files.
        page = None
        try:
            page = self._find_page(timeout_s=1.5)
        except RuntimeError:
            pass
        if page is None:
            cmd = [find_browser(),
                   f"--remote-debugging-port={self.port}",
                   "--disable-gpu", "--no-first-run", "--remote-allow-origins=*",
                   "--allow-file-access-from-files",
                   f"--user-data-dir={self.profile_dir}"]
            if self.headless:
                cmd.append("--headless=new")
            cmd.append("about:blank")
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.owned = True
            page = self._find_page()
        self.ws = websocket.create_connection(
            page["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
        return self

    def stop(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        if self.owned and self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.ws = self.proc = None

    # -------------------------------------------------------------- transport
    def send(self, method: str, params=None, wait: bool = True):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        if not wait:
            return None
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    def evaluate(self, expression: str):
        """RAW evaluate — a function expression is returned, NOT called.

        Raises RuntimeError on JS exceptions instead of returning None, so a
        broken probe can never be mistaken for a clean result."""
        res = self.send("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True})
        if res.get("exceptionDetails"):
            det = (res.get("exceptionDetails", {}).get("exception", {})
                   .get("description")
                   or res.get("exceptionDetails", {}).get("text", "evaluate failed"))
            raise RuntimeError(str(det)[:300])
        return res.get("result", {}).get("value")

    def run_probe(self, probe_source: str, opts: dict = None):
        """The safe path: always CALLS the probe function with JSON opts.

        If the probe itself throws, that surfaces as a PROBE-ERR issue rather
        than a clean result (the anti-vacuous-success rule, enforced here)."""
        expr = f"({probe_source})({json.dumps(opts or {})})"
        try:
            return self.evaluate(expr)
        except Exception as e:
            return {"issues": [{"t": "PROBE-ERR",
                                "det": str(e)[:300],
                                "conf": 1.0}]}

    # -------------------------------------------------------------- page ops
    def goto(self, uri: str, wait_s: float = 6.0):
        self.send("Page.enable")
        self.send("Page.navigate", {"url": uri})
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if self.evaluate("document.readyState") == "complete":
                break
            time.sleep(0.1)
        time.sleep(0.2)

    def set_media(self, media: str):
        """'print' emulates @media print; '' restores screen."""
        self.send("Emulation.setEmulatedMedia", {"media": media})

    def screenshot(self, path) -> Path:
        self.send("Page.enable")
        data = self.send("Page.captureScreenshot", {"format": "png"})["data"]
        import base64
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))
        return path

    def print_to_pdf(self, path, prefer_css_size: bool = True) -> Path:
        self.send("Page.enable")
        data = self.send("Page.printToPDF", {
            "preferCSSPageSize": prefer_css_size, "printBackground": True})["data"]
        import base64
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))
        return path

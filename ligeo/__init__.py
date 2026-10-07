"""ligeo — one-line global access to the ligeopersys perception system.

`import ligeo` works from ANY directory once this repo is on sys.path
(installed via the `ligeopersys-global.pth` site hook on this machine).

Single source of truth stays in the repo: proxies its probes and drivers,
keeps the evidence contract, and always CALLS probes (never trusts a
probe that "silently returns nothing").

Example:
    import ligeo
    res = ligeo.run_probe(["C:/path/page.html"], "layout_probe.js")
    ids = ligeo.identify(["logo.png", "C:/web/"], shot="out/identify")
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # the ligeopersys/ repo
TOOLS = ROOT / "tools"
PROBES = ROOT / "probes"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from cdp_runner import CDPRunner  # noqa: E402


def probe_source(name):
    """Read a probe as source. Accepts 'layout_probe' or 'layout_probe.js'."""
    p = PROBES / name if str(name).endswith(".js") else PROBES / (name + ".js")
    return p.read_text(encoding="utf-8")


def run_probe(targets, probe="layout_probe.js", opts=None, port=9400,
              headless=True, wait_s=6.0):
    """Run one probe over file paths -> [(Path, evidence), ...].

    Evidence is the probe result dict {..., issues: [{t, det, conf}]}; a
    throwing probe is reported as PROBE-ERR issues, never silently clean.
    """
    src = probe_source(probe)
    outs = []
    with CDPRunner(port=port, headless=headless) as r:
        for t in targets:
            p = Path(t)
            r.goto(p.resolve().as_uri(), wait_s=wait_s)
            outs.append((p, r.run_probe(src, opts)))
    return outs


def _load_tools_module(name):
    spec = importlib.util.spec_from_file_location(
        "_ligeo_" + name, str(TOOLS / (name + ".py")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def identify(targets, port=9403, geometry=False, shot=None, json_path=None):
    """Identify images/pages: intrinsic size, megapixels, aspect, top-8
    palette and health issues; optionally screenshots. Returns
    (manifest, dirty_count). Delegates to tools/identify.py — one source."""
    return _load_tools_module("identify").run(
        targets, port=port, geometry=geometry, shot=shot, json_path=json_path)


def layout_check(targets, port=9400, root=None, headed=False, json_path=None):
    """Geometry audit of html/svg targets -> (manifest, dirty_count)."""
    import argparse
    mod = _load_tools_module("layout_check")
    args = argparse.Namespace(targets=list(targets), root=root, port=port,
                              json=json_path, headed=headed)
    return mod._run(args)
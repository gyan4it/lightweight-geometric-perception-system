#!/usr/bin/env python3
"""layout_check — run the geometry probes over targets, print evidence.

  python tools/layout_check.py web/posters posters/          # dirs or files
  python tools/layout_check.py page.html --root "#app"       # custom root
  python tools/layout_check.py art/*.svg --json out.json

Exit code = number of targets with findings (0 = clean).
The `run()` core is reusable: `from layout_check import run` or via ligeo.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_runner import CDPRunner

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "probes"


def collect(paths):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(p.rglob("*.html")) + sorted(p.rglob("*.svg"))
        elif p.exists():
            out.append(p)
        else:
            sys.exit(f"no such target: {p}")
    # html first, svg after; dedupe
    seen, uniq = set(), []
    for f in out:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            uniq.append(f)
    return uniq


def run(targets, port: int = 9400, root: str | None = None,
        json_path: str | None = None, headed: bool = False):
    """Geometry audit of html/svg file targets.

    Returns (report: list[dict], dirty: int). Each report entry holds
    {file, root?, meta?, issues}. run() never exits the process; the CLI
    wrapper prints and maps dirty -> exit code."""
    targets = collect([Path(t) for t in targets])
    layout_js = (PROBES / "layout_probe.js").read_text(encoding="utf-8")
    svg_js = (PROBES / "svg_probe.js").read_text(encoding="utf-8")

    report, dirty = [], 0
    with CDPRunner(port=port, headless=not headed) as r:
        for f in targets:
            r.goto(f.resolve().as_uri())
            if f.suffix.lower() == ".svg":
                out = r.run_probe(svg_js, {})
            else:
                out = r.run_probe(layout_js, {"root": root} if root else {})
            out = out or {}
            if out.get("issues"):
                dirty += 1
            entry = {"file": str(f), "issues": out.get("issues", [])}
            if f.suffix.lower() == ".svg" and out.get("viewBox"):
                entry["meta"] = ('svg viewBox {0}, texts={1}'.format(
                    out["viewBox"], out.get("nText", 0)))
            elif out.get("root"):
                s = out["root"]
                entry["meta"] = ('root {0}x{1}, {2} figs, {3} imgs'.format(
                    s["w"], s["h"], out.get("nFigs", 0), out.get("nImgs", 0)))
                entry["root"] = s
            report.append(entry)

    if json_path and report:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(report, indent=2),
                                   encoding="utf-8")
    return report, dirty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--root", help="CSS selector for the layout root")
    ap.add_argument("--port", type=int, default=9400)
    ap.add_argument("--json", help="write full evidence to this file")
    ap.add_argument("--headed", action="store_true",
                    help="show the browser window (default: headless)")
    a = ap.parse_args()

    report, dirty = run(a.targets, port=a.port, root=a.root,
                        json_path=a.json, headed=a.headed)

    for entry in report:
        n = len(entry.get("issues", []))
        meta = f"  {entry['meta']}" if entry.get("meta") else ""
        print(("!! " if n else "OK ") + entry["file"] + meta)
        for iss in entry["issues"]:
            print(f"     - [{iss.get('t')} conf {iss.get('conf', 0):.2f}] "
                  f"{iss.get('det')}")

    if a.json:
        print(f"\nevidence written: {a.json}")
    print(f"\nTARGETS: {len(report)}  DIRTY: {dirty}")
    sys.exit(min(dirty, 1))


if __name__ == "__main__":
    main()
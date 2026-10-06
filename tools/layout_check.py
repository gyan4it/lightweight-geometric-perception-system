#!/usr/bin/env python3
"""layout_check — run the geometry probes over targets, print evidence.

  python tools/layout_check.py web/posters posters/          # dirs or files
  python tools/layout_check.py page.html --root "#app"       # custom root
  python tools/layout_check.py art/*.svg --json out.json

Exit code = number of targets with findings (0 = clean).
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--root", help="CSS selector for the layout root")
    ap.add_argument("--port", type=int, default=9400)
    ap.add_argument("--json", help="write full evidence to this file")
    ap.add_argument("--headless", action="store_true", default=True)
    a = ap.parse_args()

    targets = collect(a.targets)
    layout_js = (PROBES / "layout_probe.js").read_text(encoding="utf-8")
    svg_js = (PROBES / "svg_probe.js").read_text(encoding="utf-8")

    report, dirty = [], 0
    with CDPRunner(port=a.port) as r:
        for f in targets:
            r.goto(f.resolve().as_uri())
            if f.suffix.lower() == ".svg":
                out = r.run_probe(svg_js, {})
            else:
                out = r.run_probe(layout_js, {"root": a.root} if a.root else {})
            issues = (out or {}).get("issues", [])
            if issues:
                dirty += 1
            extra = ""
            if out and "nText" in out:
                extra = f" ({out['nText']} texts, viewBox {out.get('viewBox')})"
            elif out and out.get("root"):
                s = out["root"]
                extra = (f" (root {s['w']}x{s['h']}, "
                         f"{out.get('nFigs', 0)} figs, {out.get('nImgs', 0)} imgs)")
            print(("!! " if issues else "OK ") + str(f) + extra)
            for iss in issues:
                print(f"     - [{iss.get('t')} conf {iss.get('conf', 0):.2f}] "
                      f"{iss.get('det')}")
            report.append({"file": str(f), "root": (out or {}).get("root"),
                           "issues": issues})

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nevidence written: {a.json}")
    print(f"\nTARGETS: {len(targets)}  DIRTY: {dirty}")
    sys.exit(min(dirty, 1))


if __name__ == "__main__":
    main()

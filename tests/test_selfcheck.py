#!/usr/bin/env python3
"""Self-test: seeded-violation + false-positive controls.

A probe that silently returns nothing (the "function never called" bug) or a
probe that flags everything would both look like *something* here — so we
assert BOTH directions:

  violations.html  ->  must catch OVERFLOW, OVERLAP, OUT-OF-BOUNDS, IMG-FAIL,
                       OUT-OF-CANVAS, TEXT-COLLIDE
  clean.html       ->  must catch nothing

Run:  python tests/test_selfcheck.py          (exit 0 = both guards hold)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
from cdp_runner import CDPRunner  # noqa: E402

LAYOUT = (ROOT / "probes" / "layout_probe.js").read_text(encoding="utf-8")
SVG = (ROOT / "probes" / "svg_probe.js").read_text(encoding="utf-8")

REQUIRED_LAYOUT = {"OVERFLOW", "OVERLAP", "OUT-OF-BOUNDS", "IMG-FAIL", "ASPECT"}
REQUIRED_SVG = {"OUT-OF-CANVAS", "TEXT-COLLIDE"}

failures = []


def codes(issues):
    return {i.get("t") for i in issues}


with CDPRunner(port=9404) as r:
    # ---- positive control: every planted violation must be caught
    r.goto((HERE / "fixtures" / "violations.html").resolve().as_uri())
    lay = r.run_probe(LAYOUT) or {}
    svg = r.run_probe(SVG) or {}
    lc, sc = codes(lay.get("issues", [])), codes(svg.get("issues", []))

    missing = REQUIRED_LAYOUT - lc
    if missing:
        failures.append(f"layout probe missed: {sorted(missing)}")
    missing = REQUIRED_SVG - sc
    if missing:
        failures.append(f"svg probe missed: {sorted(missing)}")

    print("violations.html layout codes:", sorted(lc))
    print("violations.html svg codes:   ", sorted(sc))

    # ---- negative control: clean page must be spotless
    r.goto((HERE / "fixtures" / "clean.html").resolve().as_uri())
    lay2 = r.run_probe(LAYOUT) or {}
    svg2 = r.run_probe(SVG) or {}
    for iss in lay2.get("issues", []):
        failures.append(f"clean page layout false-positive: {iss}")
    for iss in svg2.get("issues", []):
        failures.append(f"clean page svg false-positive: {iss}")
    print("clean.html issues:", len(lay2.get("issues", [])) +
          len(svg2.get("issues", [])))

if failures:
    print("\nSELF-CHECK FAIL:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("\nSELF-CHECK PASS (probes catch planted bugs, ignore clean page)")

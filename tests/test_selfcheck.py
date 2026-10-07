#!/usr/bin/env python3
"""Self-test: seeded-violation + false-positive controls.

A probe that silently returns nothing (the "function never called" bug) or a
probe that flags everything would both look like *something* here — so we
assert BOTH directions:

  violations.html  ->  must catch OVERFLOW, OVERLAP, OUT-OF-BOUNDS, IMG-FAIL,
                       OUT-OF-CANVAS, TEXT-COLLIDE (+ image IMG-FAIL/ASPECT)
  clean.html       ->  must catch nothing (layout, svg AND image probes)

Plus two failure-mode guards:
  * a probe that THROWS must surface as PROBE-ERR issues, never as "clean";
  * evaluate() on broken JS must raise (no silent None).

Run:  python tests/test_selfcheck.py          (exit 0 = all guards hold)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
from cdp_runner import CDPRunner  # noqa: E402

LAYOUT = (ROOT / "probes" / "layout_probe.js").read_text(encoding="utf-8")
SVG = (ROOT / "probes" / "svg_probe.js").read_text(encoding="utf-8")
IMAGE = (ROOT / "probes" / "image_probe.js").read_text(encoding="utf-8")

REQUIRED_LAYOUT = {"OVERFLOW", "OVERLAP", "OUT-OF-BOUNDS", "IMG-FAIL", "ASPECT"}
REQUIRED_SVG = {"OUT-OF-CANVAS", "TEXT-COLLIDE"}
REQUIRED_IMAGE = {"IMG-FAIL", "ASPECT", "NO-ALT"}

failures = []


def codes(issues):
    return {i.get("t") for i in issues}


with CDPRunner(port=9404) as r:
    # ---- positive control: every planted violation must be caught
    r.goto((HERE / "fixtures" / "violations.html").resolve().as_uri())
    lay = r.run_probe(LAYOUT) or {}
    svg = r.run_probe(SVG) or {}
    img = r.run_probe(IMAGE) or {}
    lc, sc = codes(lay.get("issues", [])), codes(svg.get("issues", []))
    ic = codes(img.get("issues", []))

    for missing in (REQUIRED_LAYOUT - lc, REQUIRED_SVG - sc,
                    REQUIRED_IMAGE - ic):
        if missing:
            failures.append(f"probe missed: {sorted(missing)}")

    print("violations.html layout codes:", sorted(lc))
    print("violations.html svg codes:   ", sorted(sc))
    print("violations.html image codes: ", sorted(ic))

    # ---- negative control: clean page must be spotless (all three probes)
    r.goto((HERE / "fixtures" / "clean.html").resolve().as_uri())
    for name, src in (("layout", LAYOUT), ("svg", SVG), ("image", IMAGE)):
        got = (r.run_probe(src) or {}).get("issues", [])
        if got:
            failures.append(f"clean page {name} false-positives: {got}")
    print("clean.html issues: 0/0/0 (layout/svg/image)")

    # ---- failure-mode guard: a throwing probe must NOT look clean
    r.goto((HERE / "fixtures" / "clean.html").resolve().as_uri())
    boom = r.run_probe("(opts) => { throw new Error('boom'); }") or {}
    if codes(boom.get("issues", [])) != {"PROBE-ERR"}:
        failures.append(f"throwing probe not reported as PROBE-ERR: {boom}")

    # ---- failure-mode guard: raw evaluate on broken JS must raise
    try:
        r.evaluate("throw new Error('syntax-boom')")
        failures.append("evaluate() swallowed a JS exception (silent None)")
    except RuntimeError:
        pass

if failures:
    print("\nSELF-CHECK FAIL:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("\nSELF-CHECK PASS (probes catch planted bugs, ignore clean page, "
      "never pass silently)")
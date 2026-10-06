#!/usr/bin/env python3
"""print_check — printToPDF with CSS page size; verify page geometry.

  # just report size + page count:
  python tools/print_check.py page.html poster.html

  # assert expectations from a config:
  python tools/print_check.py --config examples/print-expectations.json

Config format (list of checks):
  [{"file": "poster.html", "pages": [1,1], "orient": null,
    "size_cm": [55,70], "label": "poster"}]
Exit code 0 = every expectation met. PDFs land in ./out/print/.
"""
import argparse, base64, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_runner import CDPRunner

PT_PER_CM = 2.54 * 72  # 180 pt per cm


def pdf_facts(data: bytes):
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    boxes = re.findall(
        rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", data)
    w, h = (float(boxes[-1][2]), float(boxes[-1][3])) if boxes else (0.0, 0.0)
    return pages, w, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--config", help="JSON list of expectation checks")
    ap.add_argument("--port", type=int, default=9402)
    ap.add_argument("--outdir", default="out/print")
    a = ap.parse_args()

    checks = []
    if a.config:
        checks = json.loads(Path(a.config).read_text(encoding="utf-8"))
    for f in a.files:
        checks.append({"file": f})

    outdir = Path(a.outdir)
    failures = []
    with CDPRunner(port=a.port) as r:
        for chk in checks:
            path = Path(chk["file"])
            r.goto(path.resolve().as_uri())
            pdf = r.send("Page.printToPDF",
                         {"preferCSSPageSize": True, "printBackground": True})
            data = base64.b64decode(pdf["data"])
            label = chk.get("label", path.name)
            out = outdir / (re.sub(r"\W+", "-", label) + ".pdf")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            pages, w, h = pdf_facts(data)
            notes = []

            if "pages" in chk:
                lo, hi = chk["pages"]
                if not lo <= pages <= hi:
                    notes.append(f"pages {pages} not in [{lo},{hi}]")
            if chk.get("orient") == "portrait" and not (590 <= w <= 600 and 837 <= h <= 847):
                notes.append(f"not A4 portrait ({w:.0f}x{h:.0f}pt)")
            if chk.get("orient") == "landscape" and not (837 <= w <= 847 and 590 <= h <= 600):
                notes.append(f"not A4 landscape ({w:.0f}x{h:.0f}pt)")
            if chk.get("size_cm"):
                cw, ch = chk["size_cm"]
                if abs(w - cw * PT_PER_CM) > 3 or abs(h - ch * PT_PER_CM) > 3:
                    notes.append(f"not {cw}x{ch}cm ({w:.1f}x{h:.1f}pt)")

            status = "FAIL: " + "; ".join(notes) if notes else "ok"
            if notes:
                failures.append(label)
            print(f"{label:<18} {pages:>3} pages  {w:7.1f} x {h:7.1f} pt  {status}")

    print(f"\nPDFs in {outdir}/")
    if failures:
        print("FAILED: " + ", ".join(failures))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

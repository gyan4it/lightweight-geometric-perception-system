#!/usr/bin/env python3
"""pdf_check — perceive PDFs: pages, paper size, ink coverage, colour.

  python tools/pdf_check.py path/to/report.pdf
  python tools/pdf_check.py "IX A" "X C" --json out/pdfcheck.json
  python tools/pdf_check.py RESULT-ANALYSIS-FORMAT.pdf --dpi 150

Renders every page to PNG and lets the ligeopersys image probe measure the
real pixels: media box vs A4, mean ink coverage (blank-page detection), and
the top colour palette of each page + the page as its own standalone image
(size/aspect, no false NO-ALT). PDF rendering is done by pymupdf; colour
perception is the vision probe through the browser.

Codes: PDF-BLANK (page has virtually no ink), PRN-SIZE (not A4 portrait).
Exit code 0 = every PDF opened and no page is blank.
"""
import argparse, json, re, sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    sys.exit("missing dependency: pip install pymupdf")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_runner import CDPRunner  # noqa: E402

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "probes"

A4_W, A4_H = 595.28, 841.89
PT_PER_MM = 72 / 25.4


def collect(pdf_targets):
    out = []
    for p in pdf_targets:
        p = Path(p)
        if p.is_dir():
            out += sorted(p.rglob("*.pdf"))
        elif p.is_file() and p.suffix.lower() == ".pdf":
            out.append(p)
        else:
            sys.exit(f"not a pdf (use a .pdf file or a folder): {p}")
    seen, uniq = set(), []
    for f in out:
        if f.resolve() not in seen:
            seen.add(f.resolve()); uniq.append(f)
    return uniq


def ink_coverage(pix):
    """Mean lightness (0..1) of the page's first colour channel."""
    step = pix.n or 1
    s = pix.samples
    return sum(s[::step]) / (len(s) // step) / 255.0


def run(pdf_targets, port: int = 9405, dpi: int = 110,
        outdir: str = "out/pdfcheck", json_path: str | None = None):
    pdfs = collect(pdf_targets)
    if not pdfs:
        sys.exit("no .pdf files found in targets")
    outroot = Path(outdir)
    zoom = dpi / 72.0
    image_js = (PROBES / "image_probe.js").read_text(encoding="utf-8")
    manifest, dirty = [], 0

    rendered = []  # (pdf_path, page_no, png_path)
    for pdf in pdfs:
        doc = fitz.open(pdf)
        rec = {"file": str(pdf), "pages": doc.page_count,
               "size_pt": [round(doc[0].rect.width, 2),
                           round(doc[0].rect.height, 2)]}
        rec["paper"] = ("A4 portrait" if (abs(rec["size_pt"][0] - A4_W) <= 3
                                          and abs(rec["size_pt"][1] - A4_H) <= 3)
                        else f"{rec['size_pt'][0] / PT_PER_MM:.0f} x "
                             f"{rec['size_pt'][1] / PT_PER_MM:.0f} mm (not A4)")
        pages, issues = [], []
        if abs(rec["size_pt"][0] - A4_W) > 3 or abs(rec["size_pt"][1] - A4_H) > 3:
            issues.append({"t": "PRN-SIZE", "det": "not A4 portrait: " +
                           str(rec["size_pt"]) + " pt", "conf": 0.99})
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pg = {"page": i, "px": [pix.width, pix.height],
                  "light": round(ink_coverage(pix), 4)}
            if pg["light"] > 0.995:
                issues.append({"t": "PDF-BLANK", "det": f"page {i} has no ink",
                               "conf": 0.99})
            # class PDFs share the same filename; key the render folder by
            # the parent dir too, or the pages would overwrite one another
            key = re.sub(r'[^\w.-]+', '_',
                         f"{pdf.parent.name} - {pdf.stem}")
            png = outroot.joinpath(key, f"p{i:02d}.png")
            png.parent.mkdir(parents=True, exist_ok=True)
            pix.save(png)
            rendered.append((pdf, i, png))
            pages.append(pg)
        doc.close()
        rec["issues"] = issues
        rec["pages"] = pages
        if issues:
            dirty += 1
        manifest.append(rec)

    # ---- vision pass: the image probe reads the rendered pixels ----
    with CDPRunner(port=port) as r:
        for pdf, pno, png in rendered:
            r.goto(png.resolve().as_uri())
            out = r.run_probe(image_js, {}) or {}
            imgs = out.get("imgs") or []
            if imgs:
                pal = imgs[0].get("palette")
                ratio = imgs[0].get("ratio")
            else:
                pal, ratio = None, None
            for rec in manifest:
                if rec["file"] == str(pdf):
                    for pg in rec["pages"]:
                        if pg["page"] == pno:
                            pg["ration"] = ratio
                            pg["palette"] = (pal or [])[:3]
                            break

    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest, dirty, str(outroot)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("targets", nargs="+", help="pdf files or folders/pdfs")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--port", type=int, default=9405)
    ap.add_argument("--json", dest="json_path")
    ap.add_argument("--outdir", default="out/pdfcheck")
    a = ap.parse_args()

    manifest, dirty, outroot = run(a.targets, port=a.port, dpi=a.dpi,
                                   outdir=a.outdir, json_path=a.json_path)
    for rec in manifest:
        tag = "!! " if rec["issues"] else "OK "
        print(f'{tag}{rec["file"]}')
        print(f'     pages={len(rec["pages"])}  paper={rec["paper"]}  '
              f'size={rec["size_pt"][0]:.0f}x{rec["size_pt"][1]:.0f} pt')
        for pg in rec["pages"]:
            pal = pg.get("palette") or []
            hexes = " ".join(f"{p['hex']} {p['pct']}%"
                             for p in pal[:2]) or "-"
            print(f'     p{pg["page"]}: {pg["px"][0]}x{pg["px"][1]}px  '
                  f'ink={1 - pg["light"]:.1%}  '
                  f'ratio={pg.get("ration")}  top-colours: {hexes}')
        for iss in rec["issues"]:
            print(f'     - [{iss.get("t")} conf {iss.get("conf", 0):.2f}] '
                  f'{iss.get("det")}')

    print(f"\nPDFs: {len(manifest)}  DIRTY: {dirty}  renders: {outroot}"
          + (f"  json: {a.json_path}" if a.json_path else ""))
    sys.exit(min(dirty, 1))


if __name__ == "__main__":
    main()
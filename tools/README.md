# tools/ — drivers (Python, stdlib + websocket-client)

| script | what it does | exit code |
|---|---|---|
| `cdp_runner.py` | library: browser lifecycle, `evaluate`, **`run_probe` (always calls)**, goto, screenshot, printToPDF | – |
| `layout_check.py` | geometry probes over files/dirs → evidence lines (+ `--json`) | dirty targets (capped at 1) |
| `a11y_check.py` | axe-core WCAG scan + optional Tab/focus probe | 0 = clean |
| `print_check.py` | printToPDF page-size/page-count assertions | 0 = met |
| `pdf_check.py` | **existing PDFs**: pages, A4/media-box size, per-page ink coverage (blank detection), colour palette via the vision probe (needs `pymupdf`) | dirty PDFs (blank/oversize) |
| `identify.py` | **image identification**: intrinsic size, megapixels, aspect, top-8 colour palette, health (IMG-FAIL/ASPECT/NO-ALT), SVG geometry, page screenshots | dirty targets (capped at 1) |

Dependencies: `pip install websocket-client`, Edge/Chrome, optional
`npm install axe-core`. Set `LIGEO_BROWSER` to override the browser path.

```bash
python tools/layout_check.py ../web --json out/evidence.json
python tools/a11y_check.py ../web --keyboard
python tools/print_check.py --config examples/print-expectations.json
python tools/identify.py logo.png icons/ web/ --shot out/shots --json out/identify.json
```

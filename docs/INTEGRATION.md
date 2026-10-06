# Integration — drop it into another project

## 0. Prerequisites

```bash
pip install websocket-client          # only Python dependency
# optional, for the a11y check:
npm install axe-core                  # or pass --axe path/to/axe.min.js
# browser: Edge or Chrome; override with LIGEO_BROWSER=/path/to/browser
```

Windows / macOS / Linux: the auto-detector in `tools/cdp_runner.py` covers
Edge (Win), Microsoft Edge (macOS) and chromium packages (Linux); anything
exotic → `LIGEO_BROWSER`.

## 1. Copy the parts

```text
your-project/
├── tools/    ← cp -r ligeopersys/tools    (cdp_runner + 3 checks)
├── probes/   ← cp -r ligeopersys/probes   (layout + svg sensors)
└── tests/    ← cp -r ligeopersys/tests    (self-test gate; keep fixtures)
```

## 2. Point the probes at your markup

Default root selection (priority order): `[data-probe-root]` → `.sheet` →
`main` → `body`. Either accept the default or override per run:

```bash
python tools/layout_check.py src/pages/ --root "#app" --json out/ev.json
```

Add `data-probe-root` to your app shell if you want an explicit contract.

## 3. Choose targets (question-guided)

Maintain a small target list per change type — do not crawl everything:

```text
changed a landing hero   →  tools/layout_check.py src/hero.html + svg files
changed shared tokens    →  layout_check + a11y_check on every page
changed @page / print    →  tools/print_check.py --config print-expectations.json
release gate             →  all three + tests/test_selfcheck.py
```

Example `print-expectations.json` (see `../examples/`):

```json
[{"file": "invoice.html", "pages": [1, 2], "orient": "portrait"},
 {"file": "poster.html", "pages": [1, 1], "size_cm": [55, 70]}]
```

## 4. Wire the trust gate (CI or pre-commit)

```bash
python tests/test_selfcheck.py     # must PASS before any "clean" is believed
```

CI runners need a browser; on GitHub Actions install Edge/Chrome (or set
`LIGEO_BROWSER` to the runner's chromium) and run the command above before
your layout job. Exit codes: `0` = trustworthy, `1` = probe regressions.

## 5. Give your agent the rules

The system is only safe under an agent that respects the evidence contract:

```text
→ paste/summarise docs/PLAYBOOK.md into the agent's system instructions
→ make the agent run:  layout_check → reason → fix → re-run → (all checks)
→ require the §8 report template for every QA claim
```

An agent with the tools but without the playbook will eventually
self-certify taste judgements — that is the failure mode the L3 gate exists
to prevent.

## 6. Custom probes (the extension path)

When a question is measurable but uncovered (PLAYBOOK §5):

1. copy `probes/layout_probe.js` → `probes/<name>_probe.js`;
2. keep the contract: `(opts) => { …, issues:[{t,det,rect?,conf}] }`;
3. add one planted-bug case to `tests/fixtures/` + assert its code in
   `tests/test_selfcheck.py`;
4. document the code in `docs/EVIDENCE-SCHEMA.md` registry.

Run it with:

```python
from cdp_runner import CDPRunner
with CDPRunner() as r:
    r.goto(uri)
    ev = r.run_probe(open("probes/my_probe.js").read(), {"opt": 1})
```

## 7. Pairing with a vision-capable model (Mode C future)

The bridge spec's hybrid mode composes cleanly:

```text
probes ──────────► geometry/a11y/print evidence (ground truth) ─┐
screenshot ──────► VLM (if you have one) ──► semantic hints ────┤► reasoner
human L3 gate ───► verdict ─────────────────────────────────────┘
```

Geometry stays the authority for geometric questions; the VLM only adds
L3-ish hints, tagged as such. Never let a VLM hint override a measured rect.

## 8. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `cannot attach to browser` | port busy / browser path | change `--port`, set `LIGEO_BROWSER` |
| websocket `403` | origin header | use `CDPRunner` (sets `suppress_origin` + `--remote-allow-origins`) |
| probe returns `None` | expression threw | read `exceptionDetails`; probe must be an arrow fn taking `opts` |
| everything "OK" instantly | probe never called | use `run_probe`, not `evaluate` |
| findings on a clean page | selector picks `body` | priority order / `--root` |
| print PDF off by a few px | parent padding in `@media print` | zero margins/padding; keep `overflow:hidden` on the sheet |

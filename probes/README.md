# probes/ — JS sensors injected into the rendered page

Each file is **one arrow function** taking `opts` and returning
`{ …context, issues: [ {t, det, rect|box, conf} ] }`. The runner always
calls it — `( source )(opts)` — so a probe can never "pass" by accident
(the vacuous-success bug, see `docs/PLAYBOOK.md`).

| file | measures | codes |
|---|---|---|
| `layout_probe.js` | root overflow, figure overlaps, footer collisions, img load/aspect/bounds, text escape | `OVERFLOW` `OVERLAP` `OUT-OF-BOUNDS` `IMG-FAIL` `ASPECT` `E00` |
| `svg_probe.js` | text clipped by SVG edge, text–text collisions, shapes outside viewBox (screen space!) | `OUT-OF-CANVAS` `TEXT-COLLIDE` `E01` |

## Writing your own probe

1. Copy `layout_probe.js`, keep the contract (arrow fn, `issues` array,
   every finding carries `t` (code), `det` (human sentence), `conf` 0–1).
2. Measure with `getBoundingClientRect()` — never `getBBox()` for
   transformed elements.
3. Add a self-test: one fixture HTML that **must** trigger your code
   (`tests/fixtures/`), wired into `tests/test_selfcheck.py`.

```python
from cdp_runner import CDPRunner
src = open("probes/layout_probe.js").read()
with CDPRunner() as r:
    r.goto(page_uri)
    evidence = r.run_probe(src, {"root": "#app"})
```

# Evidence schema

The single data contract between **sensors** (L1) and the **reasoner** (L3).
Machine-readable copy: [evidence.schema.json](evidence.schema.json).

## Envelope

```json
{
  "schema_version": "1.0",
  "target": "web/posters/poster-2.html",
  "probe": "layout_probe.js",
  "browser": "HeadlessChrome/…",
  "ts": "2026-10-06T14:12:03Z",
  "root": {"x": 0, "y": 0, "w": 2079, "h": 2646},
  "context": {"nFigs": 3, "nImgs": 6},
  "issues": [ … ]
}
```

| field | required | meaning |
|---|---|---|
| `schema_version` | yes | contract version; reasoner must refuse unknown majors |
| `target` | yes | what was measured (path/URI) — provenance |
| `probe` | yes | which sensor produced the issues — provenance |
| `ts` | yes | ISO-8601 measurement time |
| `root` | no | the measurement frame (rect) findings are relative to |
| `context` | no | probe-specific counters (figs, imgs, texts, viewBox …) |
| `issues` | yes | array of findings; `[]` means **clean** |

## Issue (finding)

```json
{
  "t": "OVERFLOW",
  "det": "content clipped: scrollH=3106 > clientH=2646",
  "rect": {"x": 0, "y": 0, "w": 2079, "h": 2646},
  "conf": 0.95
}
```

| field | required | meaning |
|---|---|---|
| `t` | yes | violation **code** (registry below) |
| `det` | yes | one human sentence **with the numbers** — no adjectives, no guesses |
| `rect` / `box` | recommended | where: `{x,y,w,h}` in the root's screen space (`layout`) or svg space (`svg`) |
| `a`, `b` | for pairs | both rects when the finding is an intersection |
| `conf` | yes | 0–1 confidence band (below) |
| `src` | optional | provenance override (e.g. `{"engine":"axe-core"}`) |

**Forbidden in evidence:** recommendations, blame, aesthetics, causes.
Evidence states *what was measured*; the reasoner derives causes.

## Confidence bands (from VISION_BRIDGE_ARCHITECTURE §19)

| range | band | how the reasoner may use it |
|---|---|---|
| 0.90 – 1.00 | HIGH | act on it directly (fix) |
| 0.70 – 0.89 | MEDIUM | act with a quick confirmation |
| 0.50 – 0.69 | LOW | mention; corroborate before acting |
| 0.00 – 0.49 | UNCERTAIN | never a factual claim; investigate or drop |

Bands are **not** calibrated probabilities — they express how directly the
measurement implies the claim (e.g. `complete && naturalWidth===0` ⇒
`IMG-FAIL` at 0.98: nearly tautological).

## Violation code registry

### Geometry — `layout_probe.js` (Level 1, measurable)

| code | meaning | typical conf |
|---|---|---|
| `OVERFLOW` | content taller/wider than its root (clipped or pushed out) | 0.95 |
| `OVERLAP` | two boxes intersect by > 2 px in both axes | 0.95 |
| `OUT-OF-BOUNDS` | element escapes the root/frame | 0.95 |
| `IMG-FAIL` | `complete && naturalWidth === 0` — image never loaded | 0.98 |
| `ASPECT` | rendered aspect ratio differs from intrinsic by > 2 % | 0.90 |
| `E00` | probe itself failed (no root) | 1.00 |

### SVG — `svg_probe.js` (Level 1–2)

| code | meaning | typical conf |
|---|---|---|
| `OUT-OF-CANVAS` | text/shape clipped by the SVG edge (screen space) | 0.95 |
| `TEXT-COLLIDE` | two text rects intersect > 2 px | 0.90 |
| `E01` | probe itself failed (no svg) | 1.00 |

### Standards & mechanics (produced by the tool drivers)

| code | source | meaning |
|---|---|---|
| `AXE/<id>` | axe-core | WCAG rule violation (`color-contrast`, `region`, …) |
| `KBD/NO-FOCUS` | focus walk | focus-visible without a visible outline |
| `PRN/PAGES`, `PRN/SIZE` | print_check | page-count / page-box expectation failed |
| `LNK/DEAD`, `ID/DUP`, `H/JUMP` | structure checkers | link/anchor/heading-order integrity |

### Sensor failures (never silence — see FLOWCHARTS §6)

`E00`–`E01` probe thrown · `F01`–`F06` transport/driver failures.

## Detected · derived · interpreted

Every downstream statement must keep its tier (spec §24):

```text
DETECTED   "scrollH=3106 > clientH=2646"            ← in the evidence
DERIVED    "the second figure block overflows the sheet" ← arithmetic on evidence
INTERPRETED"moving figures side-by-side will fix it"    ← hypothesis; must be
                                                          re-measured after the edit
```

An INTERPRETED claim that has not been re-measured may never be reported as
done.

## Minimal example (clean)

```json
{
  "schema_version": "1.0",
  "target": "web/docs/d3.html",
  "probe": "layout_probe.js",
  "root": {"x": 0, "y": 40, "w": 1200, "h": 3000},
  "issues": []
}
```

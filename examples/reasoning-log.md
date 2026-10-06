# Reasoning log — how the L3 reasoner used the evidence

Real cycles from the founding project (AgriSolar Tracker web build), lightly
trimmed. Each entry shows the four tiers: **DETECTED** (in evidence) →
**DERIVED** (arithmetic on it) → **ACT** (edit) → **PROOF** (re-measurement).

---

## Cycle 1 — poster content overflowed the sheet

```text
DETECTED  [OVERFLOW conf .95] content clipped: scrollH=3106 > clientH=2646
          root = 2079 x 2646 px  (poster-2)

DERIVED   the two figure blocks are span-2 (full column): 2 x ~460px stacked
          exceeds the sheet; the sheet has horizontal room (~460px) but no
          vertical room left.

ACT       posters/poster-2.html: figures moved from span-2 stack to a
          side-by-side grid row.  (source edit, not output edit)

PROOF     layout_check re-run  → issues: []
          print_check re-run   → 1 page, 1559.0 x 1984.1 pt (= 55 x 70 cm)
          both must be green; geometry alone does not prove print fits.
```

## Cycle 2 — style drift in an SVG asset

```text
DETECTED  [STYLE] off-palette: #014F7E   (mounting-layout.svg)

DERIVED   #014F7E is not a design token; closest token is sky #0277BD
          (the old value was a darker, near-identical blue).

ACT       replace #014F7E -> #0277BD in the source SVG + rebuild copies.

PROOF     style audit re-run  → colour set ⊆ allowlist, style issues = 0
```

## Cycle 3 — serious axe violation on card links

```text
DETECTED  [serious/color-contrast] a[href$="d1.html"] … (index page)
          measured ratio 4.44 : 1 against #F4F7F4 background (needs 4.50)

DERIVED   link token #0277BD was tuned for WHITE backgrounds (4.80:1 there);
          on the tinted card background it slips just under AA.

ACT       new token --sky-deep #01579B (6.85:1 on #F4F7F4) applied to
          .card a and .poster-bar a — an L2 rule now exists for
          "links on tinted backgrounds".

PROOF     a11y_check re-run → 0 violations on all 19 pages
```

## Cycle 4 — poster printed as two pages (multi-sensor triage)

```text
DETECTED  [PRN/PAGES] poster PDF = 2 pages, MediaBox 1559.0 x 1984.1 pt (ok)

DERIVED   page box is right and sheet height is right, so the SHEET is not
          over-tall — something above/below it adds ~24px in print.

ACT-DIAG  set print-media emulation, measured: sheetTop = 24px,
          bodyMargin = 0px  → the 24px is main's padding (screen style,
          never cleared for print).

ACT-FIX   @media print { body.poster-page main { margin:0; padding:0 } }
          plus .sheet { overflow:hidden; break-avoid } as a rounding guard.

PROOF     print_check re-run → 1 page each for all 4 posters, exact size.
          (A second run of the same check had ALSO caught a 6th slide page
          caused by site chrome printing — fixed the same way.)
```

## Cycle 5 — the L3 gate (what the system does NOT decide)

```text
DETECTED  geometry 0 · style 0 · a11y 0 · print 8/8     (all sensors green)

DERIVED   every measurable question this system supports is answered.
          NOT covered: "does the poster artistry read well at 55x70cm?",
          "is the visual hierarchy right?" — no probe can form these.

ACT       package screenshots (_qa/poster-*.png) + print PDFs → HUMAN
          (project Director).  Report states the scope of "green",
          explicitly lists L3 as not assessed.

PROOF     Director verdict recorded → becomes L2 rule if it ever repeats.
```

---

**Pattern to internalise:** every ACT is followed by a PROOF that re-runs a
*measurement* — never by "looks fixed now".

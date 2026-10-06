# Flowcharts (ASCII)

All diagrams render in any terminal, diff cleanly, and never rot the way
raster images do. Sources of truth for behaviour; SVG infographics in
`../assets/` are presentation copies.

---

## 1. Full system architecture

```text
                    ┌──────────────────────────────────────────────┐
                    │ L4 GOVERNANCE                                │
                    │  seeded self-test · playbook · escalation    │
                    └─────────────────┬────────────────────────────┘
                                      │ governs
                                      v
 artifact (HTML / SVG / print CSS)   ┌──────────────────────────────┐
        │                            │ L3 REASONER (text-only LLM)  │
        │ serve/render               │  hypothesise → edit → re-run │
        v                            │  no evidence ⇒ no claim      │
┌───────────────────────┐            └──────────────▲───────────────┘
│ L0 headless browser   │                           │ findings (typed JSON)
│ (Edge/Chrome, CDP)    │                           │
└───────────┬───────────┘            ┌──────────────┴───────────────┐
            │ Runtime.evaluate       │ L2 EVIDENCE                  │
            v                        │  {t, det, rect, conf}        │
┌───────────────────────┐            │  codes · bands · provenance  │
│ L1 PROBES (JS, in page)│──────────►└──────────────▲───────────────┘
│  layout · svg · axe   │  issues    │              │
│  focus walk · printToPDF│           │              │
└───────────────────────┘            │              │
        ▲                            │              │
        │ re-measure after fix       │              │
        └────────────────────────────┴──────────────┘
             loops until issues = 0 or gate = HUMAN
```

---

## 2. The QA session loop (main flowchart)

```text
            START: artifact changed
                     │
                     v
        ┌──────────────────────────┐
        │ scope: which targets?    │      (question-guided — only the
        │ html? svg? print? a11y?  │       artifact under change)
        └────────────┬─────────────┘
                     v
        ┌──────────────────────────┐
        │ run probes → evidence    │
        └────────────┬─────────────┘
                     v
              ┌─────────────┐
         ┌────┤ issues = 0? ├────┐
         │ NO └─────────────┘ YES│
         v                       v
┌─────────────────┐    ┌─────────────────────┐
│ classify finding│    │ run ALL other checks│
│ (code → level)  │    │ (shared CSS may have│
└───────┬─────────┘    │  side effects)      │
        v              └──────────┬──────────┘
   L1 or L2?                     v
   │           │       ┌─────────────────────┐
   │           │       │ report green + log  │
   v           v       └──────────┬──────────┘
┌────────┐  ┌──────────────┐      │
│FIX source│ │ evidence too  │      v
│ (edit) │  │ weak to decide?│    DONE
└───┬────┘  └──────┬───────┘
    │              │ YES
    │              v
    │      ┌───────────────────┐
    │      │ write a NEW probe │──► back to "run probes"
    │      │ (extend the sensor)│
    │      └───────────────────┘
    │ NO
    v
┌──────────────────────────┐
│ re-run probes (verify)   │◄───── fixes must be PROVEN, not asserted
└────────────┬─────────────┘
             v
      still issues? ── yes, iteration < N ──► loop
             │ no / N exceeded
             v
      ┌──────────────────┐     L3 ("looks right?")
      │ level = L3 or     ├──── yes ──► ┌─────────────────────┐
      │ judgement needed? │             │ HUMAN GATE          │
      └────────┬──────────┘             │ screenshot / PDF →  │
               │ no                     │ person → verdict    │
               v                        └─────────────────────┘
          report green
```

---

## 3. Evidence triage (finding → action)

```text
                 finding {t, det, rect, conf}
                            │
              ┌─────────────┼─────────────────┐
              v             v                 v
        t ∈ LAYOUT      t ∈ STYLE?       t ∈ A11Y?        t = L3-look
        (OVERFLOW,      (PALETTE,        (contrast,        ("taste",
         OVERLAP,        FONTSZ)          label, region)    aesthetics)
         OOB, IMG,                            │               │
         TEXT-COLLIDE)                        │               │
              │                               │               │
              v                               v               v
        ┌───────────┐                  ┌───────────┐   ┌──────────────┐
        │ LEVEL L1  │                  │ LEVEL L2  │   │ LEVEL L3     │
        │ measured  │                  │ rule-based│   │ not machine- │
        │ geometry  │                  │ + codified│   │ decidable    │
        └─────┬─────┘                  └─────┬─────┘   └──────┬───────┘
              │                              │                │
              v                              v                v
      fix source directly          fix OR add rule       screenshot/PDF
      (rect proves the cause)      (e.g. darker token)   to HUMAN; do not
              │                              │            self-judge
              └──────────────┬───────────────┘
                             v
                    re-run until clean
```

---

## 4. Coordinate-space conflict resolution
*(when two measurements of the same thing disagree — spec §37)*

```text
        two sources disagree about an element's extent
                     │
        ┌────────────┴────────────────┐
        v                             v
  getBBox() says X             getBoundingClientRect() says Y
        │                             │
        │   does the element or an    │
        │   ancestor carry a transform│
        │   (rotate/scale/CTM)?       │
        │        │                    │
        │   yes ─┤─ no                │
        │   │         │               │
        │   v         v               │
        │  getBBox is LIED to:        │
        │  it ignores the element's   │
        │  own transform              │
        │        │                    │
        └───────►│◄───────────────────┘
                 v
        screen space WINS (Y is evidence)
                 │
                 v
        emit ONE finding with rect = screen-space value;
        if both values must be shown, mark bbox value
        as {src:"getBBox", trusted:false} — never average them,
        never silently pick one (§37: flag REQUIRES_VERIFICATION)
```

---

## 5. Sensor self-test (the seeded guard)

```text
   build/change a probe
           │
           v
   ┌───────────────────────┐    fixture contains DELIBERATE bugs:
   │ run test_selfcheck.py │──► OVERFLOW OVERLAP OUT-OF-BOUNDS
   └───────────┬───────────┘    IMG-FAIL ASPECT OUT-OF-CANVAS
               │                TEXT-COLLIDE
      ┌────────┴─────────┐
      v                  v
 every planted bug    clean.html
 is CAUGHT           raises NOTHING
      │                  │
      │ no               │ no
      v                  v
 FAIL: probe is        FAIL: probe is
 vacuously green       crying wolf
 (the founding bug!)   (false positives)
      │                  │
      └────────┬─────────┘
               v
        fix probe, rerun
               │
               v
        PASS ⇒ probe may be trusted
        when it reports "0 issues"
```

*This test caught two real bugs while the repository was being written
(priority-vs-document-order root selection; `b.width` vs `b.w` in the aspect
check) — the guard is not decorative.*

---

## 6. Failure & fallback (never fabricate)

```text
   step fails                          system response
   ────────────────────────────────────────────────────────────
   browser attach (F01)      →  retry 60×0.25s, then set LIGEO_BROWSER
   evaluate → undefined(F02) →  treat as MISSING evidence; re-run once;
                                if still missing: report "probe returned
                                nothing" — do NOT print OK
   probe throws (F03)        →  evidence {t:"E0x", det:err} enters the
                                normal triage (it is a finding, not silence)
   axe.min.js absent (F05)   →  skip a11y with explicit WARNING
   findings remain after N   →  escalate: L1/L2 → fix brief for human,
                                L3 → human gate with screenshot
   ────────────────────────────────────────────────────────────
   RULE: a failed sensor degrades to an explicit gap, never to "clean".
```

---

## 7. Integration sequence (new project adopting the system)

```text
 developer            repo copy              project              agent (L3)
     │                   │                      │                      │
     │ cp tools/ probes/ │                      │                      │
     │──────────────────►│                      │                      │
     │                   │                      │                      │
     │ edit config: root selector, target list, │                      │
     │ axe path, print expectations             │                      │
     │─────────────────────────────────────────►│                      │
     │                   │                      │                      │
     │ python tools/layout_check.py web/        │                      │
     │─────────────────────────────────────────►│                      │
     │                   │◄──── evidence (0 or N findings) ────────────│
     │                   │                      │                      │
     │ paste PLAYBOOK.md rules into agent instructions                │
     │────────────────────────────────────────────────────────────────►│
     │                   │                      │   loop: fix → verify │
     │                   │                      │◄────────────────────┤
     │                   │                      │                      │
     │ CI: python tests/test_selfcheck.py (trust gate)                │
     │────────────────────────────────────────────────────────────────►│
```

---

## 8. Anatomy of one probe call

```text
 python layout_check.py targets…
        │
        v
 cdp_runner.run_probe(src, opts)          ← ALWAYS wraps "(src)(opts)"
        │
        │  Runtime.evaluate{ returnByValue, awaitPromise }
        v
 ┌─────────────────────────── page JS realm ───────────────────────────┐
 │ (opts) => {                                                         │
 │    select root (priority: data-probe-root > .sheet > main > body)   │
 │    measure  → rects via getBoundingClientRect()                     │
 │    compare  → pairwise intersection, containment, scroll vs client  │
 │    classify → issue code + one-sentence detail + confidence         │
 │    return   → {root, …context, issues:[…]}                          │
 │ }                                                                   │
 └──────────────────────────────┬──────────────────────────────────────┘
                                │ JSON value (must be a dict with "issues")
                                v
                     evidence → triage (flowchart 3)
```

---

## 9. Escalation ladder

```text
                     ┌────────────────────────────────────┐
            L3       │ HUMAN GATE                         │
   "does it look     │  artefact: screenshot / print PDF  │
    right? feel      │  question: yes/no/changes          │
    finished?"       │  agent may NOT self-certify        │
                     └───────────────▲────────────────────┘
                                     │ not provable by measurement
                     ┌───────────────┴────────────────────┐
            L2       │ RULES                              │
   "is it within     │  palette allowlist · AA contrast · │
    codified limits?"│  min font size · label-in-name     │
                     └───────────────▲────────────────────┘
                                     │ rule exists? yes→L2  no→write rule
                     ┌───────────────┴────────────────────┐
            L1       │ GEOMETRY / MECHANICS               │
   "is it            │  overlap · overflow · bounds ·     │
    measurable?"     │  links · focus · PDF page box      │
                     └────────────────────────────────────┘
   the agent works bottom-up; only stops climbing at L3.
```

#!/usr/bin/env python3
"""a11y_check — axe-core (WCAG) + keyboard focus probe over HTML pages.

  python tools/a11y_check.py web/                     # scan a directory
  python tools/a11y_check.py page.html --keyboard     # + Tab/focus probe
  python tools/a11y_check.py page.html --axe path/to/axe.min.js

Needs axe-core once:   npm install axe-core   (or pass --axe).
Exit code 0 = no violations / no invisible focus.
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_runner import CDPRunner

HERE = Path(__file__).resolve().parent


def find_axe(explicit=None):
    if explicit:
        return Path(explicit)
    for c in (Path("node_modules/axe-core/axe.min.js"),
              Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js",
              HERE / "_vendor" / "axe.min.js"):
        if c.exists():
            return c
    sys.exit("axe.min.js not found — npm install axe-core or pass --axe PATH")


AXE_RUN = """(async () => {
  try {
    const r = await axe.run(document, {resultTypes:['violations'],
      runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a',
                'wcag21aa','wcag22aa','best-practice']}});
    return r.violations.map(v => ({id:v.id, impact:v.impact, help:v.help,
      nodes:v.nodes.slice(0,4).map(n=>n.target.join(' '))}));
  } catch(e) { return [{id:'AXE-ERROR', impact:'critical', help:String(e),
                        nodes:[]}]; }
})()"""

FOCUS_PROBE = """(() => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const cs = getComputedStyle(e);
  return {tag: e.tagName.toLowerCase(),
          name: (e.getAttribute('aria-label') || e.textContent || '')
                .trim().slice(0, 42),
          outline: (cs.outlineStyle + ' ' + cs.outlineWidth),
          fv: e.matches(':focus-visible')};
})()"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--axe", help="path to axe.min.js")
    ap.add_argument("--keyboard", action="store_true",
                    help="also run the Tab/focus probe on each page")
    ap.add_argument("--tabs", type=int, default=14)
    ap.add_argument("--port", type=int, default=9401)
    a = ap.parse_args()

    pages = []
    for p in a.targets:
        p = Path(p)
        pages += sorted(p.rglob("*.html")) if p.is_dir() else [p]
    axe_src = find_axe(a.axe).read_text(encoding="utf-8")
    findings = 0

    with CDPRunner(port=a.port) as r:
        for page in pages:
            r.goto(page.resolve().as_uri())
            r.evaluate(axe_src)                 # UMD: defines window.axe
            res = r.evaluate(AXE_RUN) or []     # explicitly CALLED async fn
            if res:
                findings += len(res)
                print(f"!! {page}")
                for v in res:
                    print(f"     - [{v.get('impact')}/{v.get('id')}] "
                          f"{v.get('help')} :: {'; '.join(v.get('nodes', []))}")
            else:
                print(f"OK {page}")

        if a.keyboard:
            print("\nKEYBOARD PROBE (Tab order + focus visibility)")
            for page in pages:
                r.goto(page.resolve().as_uri())
                r.send("Page.bringToFront")
                seen = []
                for _ in range(a.tabs):
                    r.send("Input.dispatchKeyEvent", {"type": "rawKeyDown",
                        "key": "Tab", "windowsVirtualKeyCode": 9, "code": "Tab"})
                    r.send("Input.dispatchKeyEvent", {"type": "keyUp",
                        "key": "Tab", "windowsVirtualKeyCode": 9})
                    info = r.evaluate(FOCUS_PROBE)
                    if info is None:
                        break
                    if isinstance(info, dict) and "fv" in info:
                        seen.append(info)
                bad = [s for s in seen if s.get("fv") and
                       s.get("outline", "").startswith(("none", "0px"))]
                print(f"{'!!' if bad else 'OK'} {page} — "
                      f"{len(seen)} focusable stops")
                for s in seen:
                    print(f"     - <{s['tag']}> {s['name']} | "
                          f"focus-visible={s['fv']} outline={s['outline']}")
                findings += len(bad)

    print(f"\nTOTAL FINDINGS: {findings}")
    sys.exit(0 if findings == 0 else 1)


if __name__ == "__main__":
    main()

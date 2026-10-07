#!/usr/bin/env python3
"""identify — identify images and rendered pages (the global vision tool).

  python tools/identify.py logo.png icons/ web/posters/ page.html
  python tools/identify.py assets/*.svg --shot out/shots        # + screenshots
  python tools/identify.py web/ --json out/identify/manifest.json
  python tools/identify.py --port 9403 poster.html

For every target it prints a structured vision record: file facts, intrinsic
size, megapixels, aspect ratio, top-8 colour palette, and image-health issues
(IMG-FAIL / ASPECT / NO-ALT / E02). HTML pages report every embedded image;
SVG files also get geometry checks (OUT-OF-CANVAS / TEXT-COLLIDE) via the
svg probe. `--shot` writes a PNG of each page so a human or a vision-capable
model can look at it. Exit code = number of dirty targets (0 = clean).
"""
import argparse, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_runner import CDPRunner

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "probes"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif",
              ".bmp", ".apng", ".ico"}


def intrin(path: Path):
    """Dependency-free intrinsic size sniffing (fallback when browser is out)."""
    try:
        b = path.read_bytes()[:4096]
    except OSError:
        return None
    try:
        if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
            w, h = struct.unpack(">II", b[16:24]); return w, h
        if b[:6] in (b"GIF87a", b"GIF89a") and len(b) >= 10:
            return struct.unpack("<HH", b[6:10])
        if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
            if b[12:16] == b"VP8X" and len(b) >= 30:
                return struct.unpack("<I", b[24:28] + b"\0")[0], \
                       struct.unpack("<I", b[28:32] + b"\0")[0]
            if b[12:16] == b"VP8 " and len(b) >= 30:
                return struct.unpack("<HH", b[26:30])
        if b[:2] == b"\xff\xd8":                      # JPEG: walk to SOFn
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF:
                    i += 1; continue
                m, n = b[i + 1], struct.unpack(">H", b[i + 2:i + 4])[0]
                if m in (0xC0, 0xC1, 0xC2, 0xC3) and n >= 7:
                    return struct.unpack(">HH", b[i + 5:i + 9])
                i += 2 + n
        if b[:2] == b"BM" and len(b) >= 26:
            return struct.unpack("<ii", b[18:26])
    except (struct.error, IndexError):
        return None
    return None


def collect(paths):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += [f for f in sorted(p.rglob("*"))
                    if f.suffix.lower() in IMAGE_EXTS
                    or f.suffix.lower() in (".svg", ".html")]
        elif p.exists():
            out.append(p)
        else:
            sys.exit(f"no such target: {p}")
    seen, uniq = set(), []
    for f in out:
        if f.resolve() not in seen:
            seen.add(f.resolve()); uniq.append(f)
    return uniq


def run(targets, port: int = 9403, geometry: bool = False,
        shot: str | None = None, json_path: str | None = None):
    """Run the vision pipeline over file targets.

    Returns (manifest: list[dict], dirty: int). The manifest holds one full
    vision record per target; callers may print it or dump it as JSON."""
    targets = collect([t if isinstance(t, Path) else Path(t) for t in targets])
    image_js = (PROBES / "image_probe.js").read_text(encoding="utf-8")
    svg_js = (PROBES / "svg_probe.js").read_text(encoding="utf-8")
    manifest, dirty = [], 0

    with CDPRunner(port=port) as r:
        for f in targets:
            kind = f.suffix.lower().lstrip(".") or "html"
            rec = {"file": str(f), "kind": kind, "bytes": f.stat().st_size}
            size = intrin(f)
            if size:
                rec["intrin"] = {"w": size[0], "h": size[1],
                                 "mp": round(size[0] * size[1] / 1e6, 3),
                                 "ratio": round(size[0] / size[1], 4)}
            r.goto(f.resolve().as_uri())

            issues = []
            if kind == "html":
                out = r.run_probe(image_js, {}) or {}
                issues += out.get("issues", [])
                if out.get("imgs"):
                    rec["imgs"] = out["imgs"]
                if geometry:
                    lay = r.run_probe(
                        (PROBES / "layout_probe.js").read_text(encoding="utf-8"),
                        {}) or {}
                    issues += lay.get("issues", [])
                    if lay.get("root"):
                        rec["geometry"] = {"root": lay["root"]}
            elif kind == "svg":
                svg = r.run_probe(svg_js, {}) or {}
                issues += svg.get("issues", [])
                if svg.get("viewBox"):
                    rec["svg"] = {"viewBox": svg["viewBox"],
                                  "nText": svg.get("nText", 0)}
                # standalone .svg documents have no raster <img> — image probe
                # has nothing to measure here (svg_probe is its sensor)
            else:
                out = r.run_probe(image_js, {}) or {}
                issues += out.get("issues", [])
                imgs = out.get("imgs") or []
                if imgs:
                    rec["image"] = {"nw": imgs[0].get("nw"),
                                    "nh": imgs[0].get("nh"),
                                    "mp": round((imgs[0].get("nw") or 0) *
                                                (imgs[0].get("nh") or 0) / 1e6, 3)
                                    if imgs[0].get("nw") else None,
                                    "ratio": imgs[0].get("ratio"),
                                    "palette": imgs[0].get("palette")}
                    if imgs[0].get("nw"):
                        rec["image"]["intrin"] = {}
                # the standalone-image document itself is one <img>
                if imgs and not rec.get("image", {}).get("nw"):
                    pass

            if issues:
                dirty += 1
            if shot:
                if kind in ("html", "svg"):
                    sp = Path(shot)
                    sp.mkdir(parents=True, exist_ok=True)
                    path = sp / f"{f.stem}.png"
                    r.screenshot(path)
                    rec["shot"] = str(path)
            rec["issues"] = issues
            manifest.append(rec)

    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(manifest, indent=2),
                                   encoding="utf-8")
    return manifest, dirty


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--port", type=int, default=9403)
    ap.add_argument("--geometry", action="store_true",
                    help="also run the layout probe on HTML pages")
    ap.add_argument("--json", dest="json_path", help="write manifest JSON here")
    ap.add_argument("--shot", help="screenshot html/svg pages into this dir")
    a = ap.parse_args()

    manifest, dirty = run(a.targets, port=a.port, geometry=a.geometry,
                          shot=a.shot, json_path=a.json_path)
    for rec in manifest:
        tag = "!! " if rec["issues"] else "OK "
        line = f'{tag}{rec["file"]}'
        img = rec.get("image")
        if img and img.get("nw"):
            line += f'  {img["nw"]}x{img["nh"]}'
            if img.get("ratio"):
                line += f'  ratio={img["ratio"]}'
            if img.get("palette"):
                line += "  [" + " ".join(p["hex"] for p in img["palette"]) + "]"
        elif rec.get("svg"):
            vb = rec["svg"]["viewBox"]
            line += f'  svg viewBox {vb}  texts={rec["svg"]["nText"]}'
        elif rec.get("intrin"):
            line += (f'  {rec["intrin"]["w"]}x{rec["intrin"]["h"]}'
                     f'  ratio={rec["intrin"]["ratio"]}')
        elif rec.get("imgs"):
            line += f'  {len(rec["imgs"])} img(s)'
        if rec.get("shot"):
            line += f"  shot -> {rec['shot']}"
        print(line)
        for iss in rec["issues"]:
            print(f'     - [{iss.get("t")} conf {iss.get("conf", 0):.2f}] '
                  f'{iss.get("det")}')

    print(f"\nTARGETS: {len(manifest)}  DIRTY: {dirty}"
          + (f"  manifest: {a.json_path}" if a.json_path else ""))
    sys.exit(min(dirty, 1))


if __name__ == "__main__":
    main()
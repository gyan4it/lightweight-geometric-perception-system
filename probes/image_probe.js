// image_probe.js — Level-1 sensor for IMAGES inside a rendered document.
// Contract: this file IS one arrow function taking opts, returning
//   { imgs: [ {src, loaded, nw, nh, ratio, alt, palette?} ], issues: [...] }
// Works for standalone image documents (file://pic.png) AND HTML pages.
// The runner always calls it:  ( <source> )({})
//
// Violation codes: IMG-FAIL  (asset did not load / missing)
//                  ASPECT     (rendered aspect != intrinsic aspect)
//                  NO-ALT     (img element with neither alt nor
//                              role="presentation")
//                  E02        (document has no <img> elements at all)
//
// Palette is read by drawing the image into a tiny canvas and bucketing the
// pixels (3 bits/channel) — if the canvas is tainted (cross-origin embed),
// palette degrades to null instead of failing the scan.
(opts) => {
  const xywh = (b) => ({x: Math.round(b.x), y: Math.round(b.y),
                        w: Math.round(b.width), h: Math.round(b.height)});
  const issues = [];
  const recs = [];
  // A standalone image document (file://logo.png rendered directly) has the
  // <img> AS the document root — alt is not a requirement there, only inside
  // an HTML page. Detect it so NO-ALT isn't a false positive on plain files.
  const standalone = document.documentElement &&
                     document.documentElement.tagName === 'IMG';
  const list = [...document.images];
  if (!list.length)
    issues.push({t: 'E02', det: 'document has no <img> elements', conf: 0.99});

  for (const i of list) {
    const src = (i.currentSrc || i.src || '').toString();
    const short = src.startsWith('data:') ? '(inline data)'
        : (src.split('/').pop().slice(-56) || '(inline data)');
    const rec = {src: short, loaded: !!(i.complete && i.naturalWidth > 0)};
    if (!rec.loaded) {
      issues.push({t: 'IMG-FAIL', det: 'image did not load: ' + short, conf: 0.98});
      recs.push(rec);
      continue;
    }
    rec.nw = i.naturalWidth;
    rec.nh = i.naturalHeight;
    rec.ratio = +(i.naturalWidth / i.naturalHeight).toFixed(4);
    rec.alt = i.getAttribute('alt') !== null;
    rec.decorative = i.getAttribute('role') === 'presentation';
    const b = i.getBoundingClientRect();
    if (!rec.alt && !rec.decorative && !standalone)
      issues.push({t: 'NO-ALT', det: 'img without alt/role: ' + short,
                   rect: xywh(b), conf: 0.95});
    if (b.height > 0 && i.naturalHeight > 0) {
      const r = b.width / b.height;
      if (Math.abs(r / rec.ratio - 1) > 0.02)
        issues.push({t: 'ASPECT', det: 'img distorted: ' + short +
                     ' (rendered ' + r.toFixed(3) + ' vs intrinsic ' +
                     rec.ratio + ')', rect: xywh(b), conf: 0.9});
    }
    try {                       // palette — tainted canvas degrades to null
      const M = 48;
      const c = document.createElement('canvas');
      c.width = M; c.height = M;
      const cx = c.getContext('2d');
      cx.drawImage(i, 0, 0, M, M);
      const d = cx.getImageData(0, 0, M, M).data;
      const bins = new Map(), sums = new Map();
      for (let p = 0; p < d.length; p += 4) {
        const r = d[p], g = d[p + 1], bl = d[p + 2];
        const key = (r >> 5) << 6 | (g >> 5) << 3 | (bl >> 5);
        bins.set(key, (bins.get(key) || 0) + 1);
        const s = sums.get(key);
        if (!s) sums.set(key, [r, g, bl, 1]);
        else { s[0] += r; s[1] += g; s[2] += bl; s[3]++; }
      }
      const tot = M * M;
      rec.palette = [...bins.entries()]
        .sort((x, y) => y[1] - x[1]).slice(0, 8).map(([k, n]) => {
          const [sr, sg, sb, cnt] = sums.get(k);
          const hx = (v) => Math.round(v / cnt).toString(16).padStart(2, '0');
          return {hex: '#' + hx(sr) + hx(sg) + hx(sb),
                  pct: +((n / tot) * 100).toFixed(1)};
        });
      rec.made = 'canvas';
    } catch (e) {
      rec.palette = null;
      rec.made = 'tainted';
    }
    recs.push(rec);
  }
  return {imgs: recs, issues};
}
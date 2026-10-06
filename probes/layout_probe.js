// layout_probe.js — Level-1 geometry sensor for rendered HTML pages.
// Contract: this file IS one arrow function taking opts, returning
//   { root, nFigs, nImgs, issues: [ {t, det, rect?, conf} ] }
// The runner always calls it:  ( <source> )({"root": "..."})
// opts: { root: css-selector } (default: data-probe-root > .sheet > main > body)
// Violation codes: OVERFLOW OVERLAP OUT-OF-BOUNDS IMG-FAIL ASPECT
(opts) => {
  const R = e => { const b = e.getBoundingClientRect();
    return {x:Math.round(b.x), y:Math.round(b.y), w:Math.round(b.width),
            h:Math.round(b.height), b:Math.round(b.bottom), r:Math.round(b.right)}; };
  const issues = [];
  // priority order, NOT document order: a combined selector would let <body>
  // win over [data-probe-root] because its start tag comes first
  const sels = (opts && opts.root) ? [opts.root]
      : ['[data-probe-root]', '.sheet', 'main', 'body'];
  let root = null;
  for (const s of sels) { root = document.querySelector(s); if (root) break; }
  if (!root) return {root: null, issues: [{t:'E00', det:'no root element', conf:1}]};
  const rr = R(root);

  // --- content taller/wider than the root box (clipped or pushed out)
  if (root.scrollHeight > root.clientHeight + 2)
    issues.push({t:'OVERFLOW', det:'content clipped: scrollH=' + root.scrollHeight +
      ' > clientH=' + root.clientHeight, conf:0.95});
  if (root.scrollWidth > root.clientWidth + 2)
    issues.push({t:'OVERFLOW', det:'horizontal clip: scrollW=' + root.scrollWidth +
      ' > clientW=' + root.clientWidth, conf:0.95});

  // --- pairwise figure overlaps
  const figs = [...root.querySelectorAll('figure')].map(f => ({
    label: ((f.querySelector('figcaption') || {}).textContent || '?')
            .trim().slice(0, 50), rect: R(f)}));
  for (let i = 0; i < figs.length; i++)
    for (let j = i + 1; j < figs.length; j++) {
      const a = figs[i].rect, c = figs[j].rect;
      const ox = Math.min(a.r, c.r) - Math.max(a.x, c.x);
      const oy = Math.min(a.b, c.b) - Math.max(a.y, c.y);
      if (ox > 2 && oy > 2)
        issues.push({t:'OVERLAP', det:figs[i].label + ' <> ' + figs[j].label +
          ' intersect ' + ox + 'x' + oy + 'px', a, b: c, conf:0.95});
    }

  // --- footer collisions / footer escaping the root
  // (only footers INSIDE the root — an outside page footer is not a violation)
  const foot = root.querySelector('footer, .p-foot, .site-footer');
  if (foot) {
    const fr = R(foot);
    for (const f of figs)
      if (Math.min(f.rect.r, fr.r) - Math.max(f.rect.x, fr.x) > 2 &&
          Math.min(f.rect.b, fr.b) - Math.max(f.rect.y, fr.y) > 2)
        issues.push({t:'OVERLAP', det:'figure "' + f.label +
          '" collides with footer', conf:0.95});
    if (fr.b > rr.b + 1)
      issues.push({t:'OVERFLOW', det:'footer pushed below root bottom (' +
        fr.b + ' > ' + rr.b + ')', conf:0.95});
  }

  // --- images: load state, aspect distortion, escaping the root
  const imgs = [...root.querySelectorAll('img')].map(i => {
    const b = R(i);
    const o = {src: i.src.split('/').pop().slice(0, 60), rect: b,
               loaded: i.complete && i.naturalWidth > 0,
               nat: [i.naturalWidth, i.naturalHeight]};
    if (o.loaded && b.h > 0)
      o.aspect_err = Math.abs((b.w / b.h) /
                              (i.naturalWidth / i.naturalHeight) - 1);
    if (b.x < rr.x - 1 || b.r > rr.r + 1 || b.y < rr.y - 1 || b.b > rr.b + 1)
      issues.push({t:'OUT-OF-BOUNDS', det:'img ' + o.src + ' leaves the root',
        rect: b, conf:0.95});
    if (!o.loaded)
      issues.push({t:'IMG-FAIL', det:'img not loaded: ' + o.src, conf:0.98});
    if (o.aspect_err !== undefined && o.aspect_err > 0.02)
      issues.push({t:'ASPECT', det:'img ' + o.src + ' distorted by ' +
        (o.aspect_err * 100).toFixed(1) + '%', conf:0.9});
    return o;
  });

  // --- text escaping the root horizontally
  for (const t of root.querySelectorAll('h1, h2, h3, li, p, figcaption')) {
    const b = R(t);
    if (b.x < rr.x - 1 || b.r > rr.r + 1)
      issues.push({t:'OUT-OF-BOUNDS', det:'text box outside root: ' +
        t.textContent.trim().slice(0, 40), rect: b, conf:0.9});
  }

  return {root: rr, nFigs: figs.length, nImgs: imgs.length, issues};
}

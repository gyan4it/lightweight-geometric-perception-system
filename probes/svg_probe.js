// svg_probe.js — geometry sensor for standalone / inline SVG artwork.
// Contract: this file IS one arrow function taking opts, returning
//   { viewBox, nText, issues: [ {t, det, box?, conf} ] }
// The runner always calls it:  ( <source> )({"svg": "svg.hero"})
// Violation codes: OUT-OF-CANVAS TEXT-COLLIDE E01
//
// KEY RULE (docs/PLAYBOOK.md pitfall #1):
// getBBox() ignores the element's OWN transform, so rotated text lies about
// its screen extent. Always measure with getBoundingClientRect() — screen
// space includes every transform. (Conflict rule: rect beats bbox.)
(opts) => {
  const svg = (opts && opts.svg) ? document.querySelector(opts.svg)
                                 : document.querySelector('svg');
  if (!svg) return {issues: [{t:'E01', det:'no svg element', conf:1}]};
  const vb = svg.viewBox.baseVal;
  const issues = [];
  const sr = svg.getBoundingClientRect();

  const texts = [...svg.querySelectorAll('text')].map(t => {
    const b = t.getBoundingClientRect();
    return {s: t.textContent.trim().slice(0, 40),
            rect: {x: Math.round(b.x - sr.x), y: Math.round(b.y - sr.y),
                   w: Math.round(b.width), h: Math.round(b.height)}};
  });

  for (const t of texts) {
    const b = t.rect;
    if (b.x < -1 || b.y < -1 || b.x + b.w > sr.width + 1 || b.y + b.h > sr.height + 1)
      issues.push({t:'OUT-OF-CANVAS', det:'text "' + t.s +
        '" clipped by svg edge', box: b, conf:0.95});
  }

  for (let i = 0; i < texts.length; i++)
    for (let j = i + 1; j < texts.length; j++) {
      const a = texts[i].rect, c = texts[j].rect;
      const ox = Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x);
      const oy = Math.min(a.y + a.h, c.y + c.h) - Math.max(a.y, c.y);
      if (ox > 2 && oy > 2)
        issues.push({t:'TEXT-COLLIDE', det:'"' + texts[i].s + '" <> "' +
          texts[j].s + '" (' + ox + 'x' + oy + 'px)', conf:0.9});
    }

  for (const el of svg.querySelectorAll('rect, circle, image, line, path')) {
    const b = el.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) continue;
    const x = b.x - sr.x, y = b.y - sr.y;
    if (x < -2 || y < -2 || x + b.width > sr.width + 2 || y + b.height > sr.height + 2)
      issues.push({t:'OUT-OF-CANVAS', det:el.tagName + ' exceeds svg bounds',
        box: {x: Math.round(x), y: Math.round(y),
              w: Math.round(b.width), h: Math.round(b.height)}, conf: 0.9});
  }

  return {viewBox: [vb.width, vb.height], nText: texts.length, issues};
}

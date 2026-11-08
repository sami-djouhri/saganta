// Laeuft in der Seite (page.evaluate). Gibt nur Zahlen und Kennungen zurueck, nie Text.
({ tippen, wurzel }) => {
  const W = window.innerWidth;
  const kennung = (el) => {
    let k = el.tagName.toLowerCase();
    if (el.id) k += '#' + el.id;
    const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, 2) : [];
    if (cls.length) k += '.' + cls.join('.');
    return k;
  };
  // Elemente im Shadow-DOM (saganta-kopf) gehoeren dazu: der Kopf ist Teil der Oberflaeche.
  const alle = [];
  const sammeln = (wurzelKnoten) => {
    for (const el of wurzelKnoten.querySelectorAll('*')) {
      alle.push(el);
      if (el.shadowRoot) sammeln(el.shadowRoot);
    }
  };
  sammeln(wurzel ? document.querySelector(wurzel) || document : document);
  const sichtbar = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity) === 0) return false;
    if (el.closest('[aria-hidden="true"]')) return false;
    // Inhalt eines geschlossenen <details> ist nicht zu sehen (nur seine summary).
    const zu = el.closest('details:not([open])');
    if (zu && !el.closest('summary')) return false;
    return true;
  };
  const sicht = alle.filter(sichtbar);
  const eigenerText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);

  // Farbe -> [r,g,b,a]
  const farbe = (s) => {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const t = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat);
    return [t[0], t[1], t[2], t.length > 3 ? t[3] : 1];
  };
  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const mischen = (o, u) => [o[0] * o[3] + u[0] * (1 - o[3]), o[1] * o[3] + u[1] * (1 - o[3]), o[2] * o[3] + u[2] * (1 - o[3]), 1];
  // Hintergrund: die Kette hinauf, halbdurchsichtige Schichten verrechnen. Bilder/Verlaeufe -> unbekannt.
  const hintergrund = (el) => {
    const schichten = [];
    let e = el;
    while (e) {
      const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== 'none') return null;
      const f = farbe(s.backgroundColor);
      if (f && f[3] > 0) { schichten.push(f); if (f[3] >= 1) break; }
      e = e.parentElement || (e.getRootNode && e.getRootNode().host) || null;
    }
    let g = [255, 255, 255, 1];
    if (schichten.length && schichten[schichten.length - 1][3] >= 1) g = schichten.pop();
    else {
      const b = farbe(getComputedStyle(document.body).backgroundColor);
      const h = farbe(getComputedStyle(document.documentElement).backgroundColor);
      if (b && b[3] >= 1) g = b; else if (h && h[3] >= 1) g = h;
    }
    while (schichten.length) g = mischen(schichten.pop(), g);
    return g;
  };

  const klein = [], kontrast = [], tippflaeche = [], namenlos = [], breit = [];
  for (const el of sicht) {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.right > W + 1 && s.position !== 'fixed') {
      // nur melden, wenn kein Vorfahr waagerecht scrollt oder abschneidet
      let p = el.parentElement, gefangen = false;
      while (p) { const ps = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(ps.overflowX)) { gefangen = true; break; } p = p.parentElement; }
      if (!gefangen) breit.push(kennung(el));
    }
    if (eigenerText(el)) {
      const px = parseFloat(s.fontSize);
      if (px < 12) klein.push(kennung(el) + ` ${px}px`);
      const fg = farbe(s.color);
      const bg = hintergrund(el);
      if (fg && bg) {
        const vorne = fg[3] < 1 ? mischen(fg, bg) : fg;
        const l1 = lum(vorne), l2 = lum(bg);
        const v = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
        const gross = px >= 24 || (px >= 18.66 && parseInt(s.fontWeight) >= 700);
        if (v < (gross ? 3 : 4.5) && !el.closest('[disabled],[aria-disabled="true"]')) kontrast.push(kennung(el) + ` ${v.toFixed(1)}`);
      }
    }
    const bedien = el.matches('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=tab],[role=link],[role=switch],[role=checkbox],[tabindex]:not([tabindex="-1"])');
    if (bedien) {
      // Links im Fliesstext ausnehmen (WCAG 2.5.8: inline)
      const imText = el.tagName === 'A' && /^inline(-block)?$/.test(s.display) && el.parentElement && eigenerText(el.parentElement);
      const verdeckt = el.matches('input[type=checkbox],input[type=radio]') && el.closest('label') && el.closest('label').getBoundingClientRect().height >= 44;
      // Unsichtbar vergroesserte Trefferflaeche (`::before`/`::after`, absolut) zaehlt mit.
      let ph = r.height, pw = r.width;
      for (const p of ['::before', '::after']) {
        const ps = getComputedStyle(el, p);
        if (ps.content !== 'none' && ps.position === 'absolute') {
          ph = Math.max(ph, parseFloat(ps.height) || 0);
          pw = Math.max(pw, parseFloat(ps.width) || 0);
        }
      }
      if (tippen && !imText && !verdeckt && (ph < 44 - 0.5 || pw < 44 - 0.5)) {
        // Label um ein Feld zaehlt als Tippflaeche
        tippflaeche.push(kennung(el) + ` ${Math.round(r.width)}x${Math.round(r.height)}`);
      }
      let name = (el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
      if (!name && el.getAttribute('aria-labelledby')) name = el.getAttribute('aria-labelledby');
      if (!name) name = (el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('alt') || '').trim();
      if (!name && el.querySelector('img[alt]:not([alt=""])')) name = 'bild';
      if (!name && el.id) { const root = el.getRootNode(); if (root.querySelector && root.querySelector(`label[for="${CSS.escape(el.id)}"]`)) name = 'label'; }
      if (!name && el.closest('label')) name = (el.closest('label').innerText || '').trim();
      if (!name && !el.matches('input[type=file]')) namenlos.push(kennung(el));
    }
  }
  return {
    ueberlauf: Math.max(0, document.documentElement.scrollWidth - W),
    sichtbar: sicht.length,
    klein, kontrast, tippen: tippflaeche, namenlos, breit: breit.slice(0, 30),
  };
}

// static/flexible.js
(function (win, doc) {
  const docEl = doc.documentElement;

  const MIN_MOBILE_WIDTH = 320;
  const MAX_MOBILE_WIDTH = 540;
  const DESKTOP_BREAKPOINT = 768;
  const DESKTOP_ROOT_PX = 16;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const getViewportWidth = () =>
    docEl.getBoundingClientRect().width || docEl.clientWidth || win.innerWidth || 0;

  const getDpr = () => {
    const ratio = win.devicePixelRatio || 1;
    if (ratio >= 3) return 3;
    if (ratio >= 2) return 2;
    return 1;
  };

  const parseViewportContent = (content) => {
    const map = new Map();
    (content || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((kv) => {
        const idx = kv.indexOf('=');
        if (idx === -1) {
          map.set(kv, true);
          return;
        }
        const key = kv.slice(0, idx).trim();
        const value = kv.slice(idx + 1).trim();
        map.set(key, value);
      });
    return map;
  };

  const stringifyViewportContent = (map) => {
    const items = [];
    for (const [key, value] of map.entries()) {
      items.push(value === true ? key : `${key}=${value}`);
    }
    return items.join(', ');
  };

  const ensureViewportMeta = () => {
    let meta = doc.querySelector('meta[name=\"viewport\"]');
    if (!meta) {
      meta = doc.createElement('meta');
      meta.name = 'viewport';
      doc.head.appendChild(meta);
    }

    const map = parseViewportContent(meta.getAttribute('content'));
    map.set('width', 'device-width');
    map.set('initial-scale', '1');
    if (!map.has('viewport-fit')) map.set('viewport-fit', 'cover');
    meta.setAttribute('content', stringifyViewportContent(map));
  };

  const setVhVar = () => {
    const height = win.innerHeight || docEl.clientHeight || 0;
    docEl.style.setProperty('--vh', `${height * 0.01}px`);
  };

  const refreshRem = () => {
    const width = getViewportWidth();
    if (!width) return;

    if (width >= DESKTOP_BREAKPOINT) {
      docEl.style.fontSize = `${DESKTOP_ROOT_PX}px`;
      docEl.setAttribute('data-layout', 'desktop');
      return;
    }

    const finalWidth = clamp(width, MIN_MOBILE_WIDTH, MAX_MOBILE_WIDTH);
    docEl.style.fontSize = `${finalWidth / 10}px`;
    docEl.setAttribute('data-layout', 'mobile');
  };

  const dpr = getDpr();
  docEl.setAttribute('data-dpr', String(dpr));
  ensureViewportMeta();
  setVhVar();
  refreshRem();

  let resizeTimer = null;
  const onResize = () => {
    if (resizeTimer) win.clearTimeout(resizeTimer);
    resizeTimer = win.setTimeout(() => {
      setVhVar();
      refreshRem();
    }, 100);
  };

  win.addEventListener('resize', onResize, { passive: true });
  win.addEventListener('orientationchange', onResize, { passive: true });
  win.addEventListener('pageshow', () => {
    setVhVar();
    refreshRem();
  });
})(window, document);

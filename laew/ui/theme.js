(function (root) {
  'use strict';
  function createThemeController(storage, media, apply) {
    let preference = 'system';
    try { preference = storage.getItem('laew-theme') || 'system'; } catch {}
    if (!['light', 'dark', 'system'].includes(preference)) preference = 'system';
    const refresh = () => apply(preference === 'system' ? (media.matches ? 'dark' : 'light') : preference);
    media.addEventListener('change', refresh);
    refresh();
    return {get preference() { return preference; }, set(value) {
      if (!['light', 'dark', 'system'].includes(value)) return;
      preference = value;
      try { storage.setItem('laew-theme', value); } catch {}
      refresh();
    }};
  }
  if (typeof module !== 'undefined') module.exports = {createThemeController};
  else {
    let storage;
    try { storage = root.localStorage; } catch { storage = {}; }
    root.LAEWTheme = createThemeController(storage, root.matchMedia('(prefers-color-scheme: dark)'), value => {
      root.document.documentElement.dataset.theme = value;
      root.document.documentElement.style.colorScheme = value;
    });
  }
})(typeof window === 'undefined' ? globalThis : window);

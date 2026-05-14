// Lightweight status widget - paste into a JS file and include on pages that list FYI items.
// It looks for elements with class "fyi-item" and a data-id attribute.
// Saves per-item state to localStorage key "drt-widget:<pathname>:<id>".

(function () {
  const SITE_KEY_PREFIX = 'drt-widget';

  function saveData(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
    } catch (e) {
      console.warn('Status widget: failed to save to localStorage', e);
    }
  }
  function loadData(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }
  function formatWhen(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleString();
  }

  function createWidget(container, id) {
    const pageKey = location.pathname;
    const storageKey = `${SITE_KEY_PREFIX}:${pageKey}:${id}`;

    const wrapper = document.createElement('div');
    wrapper.className = 'sr-status-widget';

    const leftCol = document.createElement('div');
    leftCol.className = 'sr-widget-col';

    const badge = document.createElement('div');
    badge.className = 'sr-badge';
    badge.textContent = 'Status: —';

    const btnGroup = document.createElement('div');
    btnGroup.style.display = 'flex';
    btnGroup.style.gap = '6px';

    const btnTricia = document.createElement('button');
    btnTricia.className = 'sr-btn tricia';
    btnTricia.textContent = 'Tricia on it';

    const btnMaya = document.createElement('button');
    btnMaya.className = 'sr-btn maya';
    btnMaya.textContent = 'Maya on it';

    const btnDone = document.createElement('button');
    btnDone.className = 'sr-btn done';
    btnDone.textContent = 'Done';

    btnGroup.append(btnTricia, btnMaya, btnDone);

    leftCol.append(badge, btnGroup);

    const rightCol = document.createElement('div');
    rightCol.className = 'sr-widget-col';

    const note = document.createElement('textarea');
    note.className = 'sr-note';
    note.placeholder = 'Add a short note (what happened / next step)...';

    const meta = document.createElement('div');
    meta.className = 'sr-meta';
    meta.textContent = '';

    const actionsRow = document.createElement('div');
    actionsRow.style.display = 'flex';
    actionsRow.style.alignItems = 'center';
    actionsRow.style.justifyContent = 'space-between';
    actionsRow.style.gap = '8px';

    const shareBtn = document.createElement('button');
    shareBtn.className = 'sr-share';
    shareBtn.textContent = 'Share to repo (open issue)';

    actionsRow.append(shareBtn);

    rightCol.append(note, actionsRow, meta);

    wrapper.append(leftCol, rightCol);

    // load saved state
    const saved = loadData(storageKey);
    if (saved) {
      badge.textContent = `Status: ${saved.status || '—'}`;
      if (saved.status === 'Tricia on it') badge.classList.add('tricia');
      if (saved.status === 'Maya on it') badge.classList.add('maya');
      if (saved.status === 'Done') badge.classList.add('done');
      note.value = saved.note || '';
      meta.textContent = saved.updatedAt ? `Updated ${formatWhen(saved.updatedAt)} by ${saved.by || '—'}` : '';
    }

    function setStatus(status, by) {
      const data = { status, note: note.value, by, updatedAt: Date.now() };
      saveData(storageKey, data);
      badge.textContent = `Status: ${status}`;
      meta.textContent = `Updated ${formatWhen(data.updatedAt)} by ${by}`;
      // small visual class swap:
      badge.classList.remove('tricia','maya','done');
      if (status === 'Tricia on it') badge.classList.add('tricia');
      if (status === 'Maya on it') badge.classList.add('maya');
      if (status === 'Done') badge.classList.add('done');
    }

    btnTricia.addEventListener('click', () => setStatus('Tricia on it', 'Tricia'));
    btnMaya.addEventListener('click', () => setStatus('Maya on it', 'Maya'));
    btnDone.addEventListener('click', () => setStatus('Done', 'System'));

    // autosave note on blur
    note.addEventListener('blur', () => {
      const existing = loadData(storageKey) || {};
      const data = { ...existing, note: note.value, updatedAt: Date.now() };
      saveData(storageKey, data);
      meta.textContent = `Updated ${formatWhen(data.updatedAt)} by ${data.by || '—'}`;
    });

    // Share — opens a prefilled GitHub new issue page in your Daily-Reports-TODO repo.
    // Users must click Submit to create the issue (no token required).
    shareBtn.addEventListener('click', () => {
      // update these values if the repo is different
      const repoOwner = 'mayatps';
      const repoName = 'Daily-Reports-TODO';

      const title = `[Status update] ${id}`;
      const body = `Status: ${ (loadData(storageKey) || {}).status || '—' }\n\nNote:\n${note.value || '—'}\n\n(From dashboard: ${location.href})`;
      const url = `https://github.com/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
      window.open(url, '_blank');
    });

    container.appendChild(wrapper);
  }

  // initialize on DOMContentLoaded
  function init() {
    const containers = document.querySelectorAll('.fyi-item[data-id]');
    if (!containers.length) return;
    containers.forEach(n => {
      const id = n.getAttribute('data-id');
      if (!id) return;
      createWidget(n, id);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

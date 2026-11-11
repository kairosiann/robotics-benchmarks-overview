/* =====================================================
   js/site.js — shared by every page
   =====================================================
   Load order (index.html, tasks.html):
     js/registry.js → config/skills.js → config/asset-page.js
     → config/tasks/index.js → js/icons.js → js/site.js
     → js/model-view.js → js/asset-cards.js → js/model-viewer.js
     → the page's own script
   (assets.html loads only js/registry.js → config/asset-page.js
   → js/site.js and the asset scripts.)
   A card's panel shows the task's asset cards (`assetCards`) only on
   pages that load config/asset-page.js and js/asset-cards.js.
   SITE.boot(render) loads every task file named in
   config/tasks/index.js, normalizes and checks the configs
   (problems appear in a banner at the top of the page), then
   calls render(data). It also provides the task card, its panel,
   and the contents bar with its scroll-spy.

   All page data lives in config/. Adding tasks, skills, videos,
   or images should not require editing this file.
   ===================================================== */

(function () {
  'use strict';

  // Bare file names in configs resolve against these folders. `tiles` holds
  // smaller copies of the task videos, for the skill tiles (js/benchmark.js;
  // node tools/check.mjs --make-media makes them). Keep in sync with
  // tools/check.mjs.
  const ASSET_DIRS = {
    videos: 'website_assets/videos/tasks/', thumbnails: 'website_assets/images/thumbnails/',
    tiles: 'website_assets/videos/540p/tasks/'
  };

  const PAGE = window.PAGE;
  const ICONS = window.ICONS || {};
  const problems = PAGE.errors;

  // Syntax errors inside config files surface here.
  window.addEventListener('error', e => {
    if (e.filename && /\/config\//.test(e.filename)) {
      problems.push(`${e.filename.split('/').slice(-3).join('/')} line ${e.lineno}: ${e.message}`);
    }
  });

  // ---- Utilities ----------------------------------------------------------

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
  // [Bracketed] text is a value still to be filled in; highlight it.
  const fmt = s => esc(s).replace(/\[[^\]]+\]/g, m => `<span class="ph">${m}</span>`);
  // A string or a list of strings → a list of non-empty paragraphs.
  const paras = x => (Array.isArray(x) ? x : [x]).map(s => String(s ?? '').trim()).filter(Boolean);
  const parasHtml = x => paras(x).map(p => `<p>${fmt(p)}</p>`).join('');
  const byId = (a, b) => a.id.localeCompare(b.id, undefined, { numeric: true });
  const isAbsolute = p => /^([a-z][a-z0-9+.-]*:)?\/\//i.test(p) || /^(\/|\.\.?\/)/.test(p);
  const assetUrl = (kind, p) => !p ? '' : isAbsolute(p) ? p : ASSET_DIRS[kind] + p;
  const strList = x => Array.isArray(x) ? x.map(String) : [];

  const TYPES = { 'b': 'b', 'behavioral': 'b', 'vb': 'vb', 'visual+behavioral': 'vb' };

  const tasksUrl = (skills = []) => skills.length ? `tasks.html?skills=${skills.map(encodeURIComponent).join(',')}` : 'tasks.html';
  const params = () => new URLSearchParams(location.search);

  const D = { skills: [], SK: {}, challenge: null, tasks: [], TK: {} };

  // ---- Loading ------------------------------------------------------------

  function loadTaskFiles() {
    return Promise.all((PAGE.taskFiles || []).map(name => new Promise(resolve => {
      const s = document.createElement('script');
      s.src = `config/tasks/${name}.js`;
      s.async = false;                  // run in list order
      s.onload = () => resolve();
      s.onerror = () => {
        problems.push(`config/tasks/${name}.js couldn't be loaded. Check the name in config/tasks/index.js.`);
        resolve();
      };
      document.head.appendChild(s);
    })));
  }

  // ---- Normalize + check ---------------------------------------------------

  function normalizeSkill(s) {
    return {
      key: String(s.key || ''),
      id: String(s.id || ''),
      label: String(s.label || s.id || ''),
      name: String(s.name || s.key || 'Untitled skill'),
      definition: String(s.definition || ''),
      representative: Array.isArray(s.representative) ? s.representative.map(String) : null
    };
  }

  function normalizeChallenge(c) {
    return {
      id: String(c.id || 'C'),
      name: String(c.name || 'Dexterous Long-Horizon Tasks'),
      order: strList(c.order)
    };
  }

  function normalizeTask(raw) {
    const where = raw.__file || `task ${raw.id}`;
    const t = Object.assign({}, raw);
    t.id = String(raw.id ?? '').trim();
    t.name = String(raw.name || '');
    t.skills = strList(raw.skills);
    // Challenge tasks appear only in the long-horizon section, not under their skills.
    t.challenge = raw.challenge === true;
    t.description = raw.description || '';
    t.success = raw.success || '';
    t.assetCards = strList(raw.assetCards);
    // Video variants: more videos of the task, played after the base task's
    t.variations = (Array.isArray(raw.variations) ? raw.variations : []).map((g, gi) => {
      const typeKey = String(g.type || '').toLowerCase().replace(/\s+/g, '');
      if (!TYPES[typeKey]) problems.push(`${where}: variation "${g.axis || gi + 1}" has type "${g.type}"; use 'behavioral' or 'visual+behavioral'.`);
      return {
        axis: String(g.axis || 'Untitled variation'),
        type: TYPES[typeKey] || 'vb',
        instances: (Array.isArray(g.instances) ? g.instances : []).map(inst => Object.assign({}, inst, {
          label: String(inst.label || '')
        }))
      };
    });
    // `base: false`: no base task; the video variants are the task's videos.
    t.base = raw.base !== false;
    if (!t.base && !t.variations.some(g => g.instances.length)) {
      problems.push(`${where}: has base: false but no video variations; showing it as a base task instead.`);
      t.base = true;
    }
    return t;
  }

  function check() {
    const seen = new Set();
    D.tasks.forEach(t => {
      const where = t.__file || `task ${t.id}`;
      if (!t.id) problems.push(`${where}: missing id.`);
      else if (seen.has(t.id)) problems.push(`${where}: id "${t.id}" is used by another task.`);
      seen.add(t.id);
      if (!t.name) problems.push(`${where}: missing name.`);
      if (!t.skills.length && !t.challenge) problems.push(`${where}: no skills listed, so the task appears in no section.`);
      t.skills.forEach(k => { if (!D.SK[k]) problems.push(`${where}: unknown skill "${k}" (see config/skills.js).`); });
      if (cardsByKey()) t.assetCards.forEach(k => {
        if (!isComing(k) && !cardsByKey()[k]) problems.push(`${where}: assetCards names "${k}", which isn't in config/asset-page.js.`);
      });
    });
    D.skills.forEach(s => (s.representative || []).forEach(id => {
      const t = D.TK[id];
      if (!t) problems.push(`config/skills.js: ${s.name} lists task "${id}", which doesn't exist.`);
      else if (t.challenge) problems.push(`config/skills.js: ${s.name} lists task ${id}, but challenge tasks appear only in the ${D.challenge ? D.challenge.name : 'challenge'} section.`);
      else if (!t.skills.includes(s.key)) problems.push(`config/skills.js: ${s.name} lists task ${id}, but that task doesn't list skill "${s.key}".`);
    }));
    if (D.challenge) D.challenge.order.forEach(id => {
      const t = D.TK[id];
      if (!t) problems.push(`config/skills.js: the ${D.challenge.name} order lists task "${id}", which doesn't exist.`);
      else if (!t.challenge) problems.push(`config/skills.js: the ${D.challenge.name} order lists task ${id}, which isn't a challenge task.`);
    });
    else if (D.tasks.some(t => t.challenge)) problems.push('config/skills.js: there are challenge tasks but no `challenge` section, so they aren\'t shown on the main page.');
  }

  function showProblems() {
    const box = document.getElementById('config-errors');
    if (!box || !problems.length) return;
    box.innerHTML = `<strong>Config problems (${problems.length})</strong><ul>${problems.map(p => `<li>${esc(p)}</li>`).join('')}</ul>`;
    box.hidden = false;
    problems.forEach(p => console.warn('[config]', p));
  }

  // ---- Task data helpers ---------------------------------------------------

  // A section's tasks: the listed ones first (in the listed order), then the
  // rest by id.
  function listedFirst(all, ids) {
    const listed = ids.map(id => D.TK[id]).filter(t => t && all.includes(t));
    return [...listed, ...all.filter(t => !listed.includes(t))];
  }
  // The cards in a skill section on the main page.
  function representativeTasks(skill) {
    const all = D.tasks.filter(t => !t.challenge && t.skills.includes(skill.key));
    return skill.representative
      ? skill.representative.map(id => D.TK[id]).filter(t => t && all.includes(t))
      : all.slice(0, PAGE.defaultRepresentative);
  }
  const challengeTasks = () => listedFirst(D.tasks.filter(t => t.challenge), D.challenge ? D.challenge.order : []);

  // Every video of a task: the base task (unless `base: false`), then each
  // video variant.
  function videoItems(t) {
    const items = t.base ? [{ key: 'base', kind: 'base', label: 'Base task', video: t.video }] : [];
    t.variations.forEach((g, gi) => g.instances.forEach((inst, ii) => items.push({
      key: `${gi}-${ii}`, kind: 'variation', axis: g.axis, type: g.type,
      label: inst.label, video: inst.video
    })));
    return items;
  }
  // The clip a card plays: the first one that has a file.
  const mainVideo = t => { const items = videoItems(t); return items.find(it => it.video) || items[0]; };

  // The All assets page's cards by key, on pages that load them
  // (config/asset-page.js and js/asset-cards.js); a task's `assetCards` names
  // them, and an entry in [brackets] is an asset not on that page yet.
  const cardsByKey = () => window.ASSET_CARDS && PAGE.assetPage ? window.ASSET_CARDS.byKey() : null;
  const isComing = k => /^\[.+\]$/.test(k);

  // ---- Media ---------------------------------------------------------------

  // A still for a clip: the video's own first frame.
  function stillHtml(video) {
    const src = assetUrl('videos', video);
    if (src) return `<video muted playsinline preload="metadata" tabindex="-1" aria-hidden="true" src="${esc(src)}#t=0.1"></video>`;
    return '';
  }
  const placeholderHtml = (t, text = 'No video yet') => `${ICONS[t.icon] || ICONS.generic || ''}<span class="vidmeta">${esc(text)}</span>`;
  const playBadge = '<span class="play-badge" aria-hidden="true"><span class="play-tri"></span></span>';

  // ---- Task specs ----------------------------------------------------------
  // Description, skills (each linking to All tasks filtered to it), success
  // criteria, and assets, each under a bold label. Shown under a card's
  // videos in its panel.

  // The task's asset cards, as on the All assets page: each opens its 3D
  // viewer and downloads in a panel under its row, inside this one
  // (js/asset-cards.js); then, if any are still to come, a note saying so
  function assetsHtml(t) {
    const byKey = cardsByKey();
    if (!byKey || !t.assetCards.length) return '';
    const cards = t.assetCards.map(k => byKey[k]).filter(Boolean)
      .map(a => window.ASSET_CARDS.cardHtml(a, window.ASSET_CARDS.pickOf(a), { id: false, tag: 'p' })).join('');
    return `<div class="task-assets">${cards}${t.assetCards.some(isComing) ? `
      <p class="asset-coming">More assets will be added soon.</p>` : ''}
    </div>`;
  }

  function specHtml(t) {
    // `wide`: the value goes on its own line under the label, as wide as the specs
    const row = (label, html, { cls = 'prose', wide = false } = {}) => {
      const w = wide ? ' is-wide' : '';
      return `<div class="rk${w}">${label}</div><div class="rv ${cls}${w}">${html}</div>`;
    };
    const todo = text => `<p><span class="ph">[${esc(text)}]</span></p>`;
    const skills = t.skills.map(k => D.SK[k]).filter(Boolean)
      .map(s => `<a class="chip" href="${esc(tasksUrl([s.key]))}" title="All tasks that use ${esc(s.name)}">${esc(s.name)}</a>`).join('');
    // Long-horizon tasks may leave success criteria out.
    const success = paras(t.success).length ? parasHtml(t.success) : t.challenge ? '' : todo('Success criteria not written yet');
    const assets = assetsHtml(t);
    return `
      <div class="spec">
        ${row('Description', parasHtml(t.description) || todo('Description not written yet'))}
        ${skills ? row('Skills', `<div class="chips">${skills}</div>`) : ''}
        ${success ? row('Success criteria', success) : ''}
        ${assets ? row('Assets', assets, { cls: 'rv-assets', wide: true }) : ''}
      </div>`;
  }

  // ---- Task card -----------------------------------------------------------
  // Thumbnail, then a caption bar with the name. `after`: HTML placed under
  // the caption bar. Clicking anywhere on the card (but a link in it) opens the task's
  // videos and specs in a panel inside the card grid (see "Card videos"
  // below); the thumbnail is the button that does it, for the keyboard.

  // At the right of a card's caption bar: a chevron that the card opens
  // below (it points up while the panel is open)
  const chevron = '<span class="tcard-chev" aria-hidden="true"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 6 8 10.5 12.5 6"/></svg></span>';

  function renderCard(t, { level = 4, after = '' } = {}) {
    const it = mainVideo(t);
    const thumb = assetUrl('thumbnails', t.thumbnail);
    const still = thumb ? `<img src="${esc(thumb)}" alt="" loading="lazy">` : it ? stillHtml(it.video) : '';
    const playable = it && it.video;
    const inner = still || placeholderHtml(t, playable ? '' : 'No video yet');
    const media = playable
      ? `<button type="button" class="tcard-thumb" data-play-task="${esc(t.id)}" data-play-item="${esc(it.key)}" aria-expanded="false" aria-label="${esc(t.name)}: videos and details">${inner}</button>`
      : `<div class="tcard-thumb is-empty">${inner}</div>`;
    const name = `<h${level} class="tcard-name">${esc(t.name)}</h${level}>`;
    const cap = `<div class="tcard-cap">${name}${playable ? chevron : ''}</div>`;
    return `
      <article class="tcard${playable ? ' is-playable' : ''}" data-task="${esc(t.id)}">
        ${media}
        ${cap}${after}
      </article>`;
  }

  // ---- Video player (card videos in a grid) --------------------------------
  // Every video of a task in one frame. With several: arrows on the video's
  // left and right edges and one dot per video under it (the "Video 1 / 4"
  // count is for screen readers). Switching slides the next video in. When a
  // video ends, the next one plays after a short pause; when the last one
  // ends, it stays there.

  function slideHtml(t, it, i, n) {
    const src = assetUrl('videos', it.video);
    if (!src) return `<div class="slide">${placeholderHtml(t)}</div>`;
    // `#t=0.001` makes browsers that only preload metadata show the first frame.
    return `<div class="slide"><video controls playsinline preload="metadata" src="${esc(src)}#t=0.001" aria-label="${esc(n > 1 ? `${t.name}, video ${i + 1} of ${n}` : t.name)}"></video></div>`;
  }

  // `start`: index (in videoItems) of the video shown first.
  function playerHtml(t, start = 0) {
    const items = videoItems(t), n = items.length;
    if (!n) return '';
    const many = n > 1;
    return `
      <div class="player" data-player data-start="${start}">
        <div class="vstage">
          <div class="task-video player-frame" data-frame>${slideHtml(t, items[start], start, n)}</div>${many ? `
          <button type="button" class="vnav prev" data-step="-1" aria-label="Previous video">‹</button>
          <button type="button" class="vnav next" data-step="1" aria-label="Next video">›</button>` : ''}
        </div>${many ? `
        <div class="vstep" role="group" aria-label="Task videos">
          <span class="visually-hidden" aria-live="polite">Video <span data-count>${start + 1}</span> / ${n}</span>
          ${items.map((_, i) => `<button type="button" class="vstep-dot" data-go="${i}" aria-label="Video ${i + 1} of ${n}" aria-current="${i === start}"></button>`).join('')}
        </div>` : ''}
      </div>`;
  }

  const AUTO_NEXT_DELAY = 500;  // ms between one video ending and the next sliding in

  // Wires up a player made by playerHtml. Returns { stop() }, which pauses
  // it and cancels any pending move (used when a card's panel closes).
  function wirePlayer(t, player) {
    const frame = player && player.querySelector('[data-frame]');
    const pauseAll = () => { if (frame) frame.querySelectorAll('video').forEach(v => v.pause()); };
    const step = player && player.querySelector('.vstep');
    if (!step) return { stop: pauseAll };
    const items = videoItems(t);
    const n = items.length;
    let cur = Number(player.dataset.start) || 0;

    // Carousel: the new video waits beside the frame (on the right for
    // dir 1, the left for -1) until its first frame is ready, then it slides
    // in as the old one slides out. No fade, so nothing flashes.
    let seq = 0;
    let onScreen = frame.firstElementChild;
    let nextTimer = 0;
    function show(i, dir) {
      clearTimeout(nextTimer);
      i = (i + n) % n;  // the arrows wrap around
      if (i === cur) return;
      cur = i;
      const token = ++seq;
      const side = dir > 0 ? 'next' : 'prev';
      // Only the slide on screen stays; drop any left over from quick clicks
      // (one still sliding out, or one that never got to slide in).
      const old = onScreen;
      [...frame.children].forEach(el => { if (el !== old) el.remove(); });
      const oldVideo = old && old.querySelector('video');
      if (oldVideo) oldVideo.pause();

      const tpl = document.createElement('template');
      tpl.innerHTML = slideHtml(t, items[i], i, n).trim();
      const slide = tpl.content.firstElementChild;
      slide.classList.add(`wait-${side}`);
      frame.appendChild(slide);
      const v = slide.querySelector('video');
      if (v) { const p = v.play(); if (p) p.catch(() => {}); }

      let started = false;
      const go = () => {
        if (started || token !== seq) return;
        started = true;
        onScreen = slide;
        slide.getBoundingClientRect();  // commit the waiting position so the move animates
        slide.classList.remove(`wait-${side}`);
        if (old) {
          old.classList.add(`leave-${side}`);
          const drop = () => old.remove();
          old.addEventListener('transitionend', drop, { once: true });
          setTimeout(drop, 800);  // in case transitionend never fires
        }
      };
      if (v && v.readyState < 2) {
        v.addEventListener('loadeddata', go, { once: true });
        setTimeout(go, 600);  // don't wait forever on a slow file
      } else go();

      step.querySelector('[data-count]').textContent = String(i + 1);
      step.querySelectorAll('.vstep-dot').forEach((b, j) => b.setAttribute('aria-current', String(j === i)));
    }

    player.addEventListener('click', e => {
      const b = e.target.closest('[data-step], [data-go]');
      if (!b) return;
      if (b.dataset.go !== undefined) show(Number(b.dataset.go), Number(b.dataset.go) - cur);
      else show(cur + Number(b.dataset.step), Number(b.dataset.step));
    });
    // When a video finishes, hold its last frame briefly, then play the next
    // one. When the last video finishes, stay on it. Replaying the video
    // cancels a pending move. Media events don't bubble, so listen in the
    // capture phase.
    frame.addEventListener('ended', () => {
      clearTimeout(nextTimer);
      if (cur < n - 1) nextTimer = setTimeout(() => show(cur + 1, 1), AUTO_NEXT_DELAY);
    }, true);
    frame.addEventListener('play', () => clearTimeout(nextTimer), true);
    // Left and right arrow keys step through the videos from the arrows or the
    // dots (on the video itself they still seek, as usual).
    player.addEventListener('keydown', e => {
      const d = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
      if (!d || !e.target.closest('.vnav, .vstep')) return;
      e.preventDefault();
      show(cur + d, d);
    });
    return { stop() { clearTimeout(nextTimer); seq++; pauseAll(); } };
  }

  // ---- Card videos, opened in the grid --------------------------------------
  // Clicking a card (anywhere, or its thumbnail from the keyboard) opens a
  // full-width panel inside its card grid, right after the clicked card's
  // row: the task's name, a close button, the task's videos in a player,
  // and the task's specs under it. One panel at a
  // time. Clicking the same card again, the close button, or
  // Esc closes it; it follows its card when the grid reflows (window size,
  // All tasks filters) and closes if the card is filtered out.

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let ex = null;  // the open panel: { t, card, thumb, el, player, ro }

  // The last visible card in `card`'s row, measured with the panel out of
  // the layout (hidden, not removed, so its video keeps playing).
  function rowEnd(card) {
    if (ex) ex.el.style.display = 'none';
    const top = card.offsetTop;
    let last = card;
    for (const c of card.parentElement.children) {
      if (c.classList.contains('tcard') && !c.hidden && c.offsetTop === top) last = c;
    }
    if (ex) ex.el.style.display = '';
    return last;
  }
  function placeExpander() {
    if (!ex) return;
    if (ex.card.hidden || !document.contains(ex.card)) { closeExpander(false); return; }
    const end = rowEnd(ex.card);
    if (end.nextElementSibling !== ex.el) end.after(ex.el);
  }

  function openExpander(thumb, { keyboard = false } = {}) {
    const card = thumb.closest('.tcard');
    const t = D.TK[thumb.dataset.playTask];
    if (!card || !t) return;
    const again = ex && ex.card === card;
    closeExpander(false);
    if (again) return;  // a second click on the open card's thumbnail closes it

    const items = videoItems(t);
    const start = Math.max(0, items.findIndex(it => it.key === thumb.dataset.playItem));
    const el = document.createElement('section');
    el.className = 'tcard-expand task-expand';
    el.id = 'card-videos';
    el.setAttribute('aria-label', t.name);
    el.innerHTML = `
      <div class="tx-head">
        <p class="tx-title">${esc(t.name)}</p>
        <button type="button" class="tx-close" data-tx-close aria-label="Close video" title="Close (Esc)">×</button>
      </div>
      ${playerHtml(t, start)}
      ${specHtml(t)}`;
    rowEnd(card).after(el);
    ex = { t, card, thumb, el, player: wirePlayer(t, el.querySelector('[data-player]')) };
    card.classList.add('is-open');
    thumb.setAttribute('aria-expanded', 'true');
    thumb.setAttribute('aria-controls', el.id);
    if ('ResizeObserver' in window) {
      ex.ro = new ResizeObserver(() => requestAnimationFrame(placeExpander));
      ex.ro.observe(card.parentElement);
    }

    const v = el.querySelector('[data-frame] video');
    if (v) { const p = v.play(); if (p) p.catch(() => {}); }
    el.scrollIntoView({ block: 'nearest', behavior: reducedMotion.matches ? 'auto' : 'smooth' });
    if (keyboard && v) v.focus({ preventScroll: true });
  }

  function closeExpander(refocus) {
    if (!ex) return;
    const { el, card, thumb, player, ro } = ex;
    ex = null;
    if (ro) ro.disconnect();
    player.stop();
    if (window.ASSET_CARDS) window.ASSET_CARDS.close(false);  // an asset's panel inside it
    el.remove();
    card.classList.remove('is-open');
    thumb.setAttribute('aria-expanded', 'false');
    thumb.removeAttribute('aria-controls');
    if (refocus) thumb.focus({ preventScroll: true });
  }

  // (Esc in an asset's panel inside it closes just that: js/asset-cards.js
  // marks the key handled)
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && ex && !e.defaultPrevented && !document.querySelector('dialog[open]')) closeExpander(true);
  });

  // ---- Contents bar (built from the page's sections) ----------------------

  const mqStrip = window.matchMedia('(max-width: 960px)');
  let activeKey = null;
  let activeSection = null;          // page section the reader is in
  const subOverride = new Map();     // section key -> open, set by its arrow

  function stripHeight() {
    const toc = document.getElementById('toc');
    return mqStrip.matches && toc ? toc.offsetHeight : 0;
  }
  function syncMetrics() {
    const root = document.documentElement.style;
    root.setProperty('--strip-h', stripHeight() + 'px');
    // Centre the stuck contents bar vertically (it scrolls itself if taller than the window).
    const toc = document.getElementById('toc');
    if (toc && !mqStrip.matches) root.setProperty('--toc-top', Math.max(24, (window.innerHeight - toc.offsetHeight) / 2) + 'px');
  }

  // Scroll-spy over every [data-nav] target, in document order.
  function updateActive(force) {
    const toc = document.getElementById('toc');
    const targets = [...document.querySelectorAll('.content [data-nav]')].filter(el => !el.hidden);
    if (!toc || !targets.length) return;
    const line = stripHeight() + 64;
    let active = targets[0];
    for (const el of targets) if (el.getBoundingClientRect().top <= line) active = el;
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) active = targets[targets.length - 1];
    const key = active.dataset.nav;
    if (key === activeKey && !force) return;
    activeKey = key;
    // A subsection (skill or long-horizon) also lights its page section.
    const sec = active.closest('.page-section');
    const parentKey = sec && sec !== active ? sec.dataset.nav : null;
    // Entering a new page section hands its subsections back to auto mode.
    const sectionKey = sec ? sec.dataset.nav : key;
    if (sectionKey !== activeSection) { activeSection = sectionKey; subOverride.clear(); }
    syncSubs(toc);
    toc.querySelectorAll('a[data-target]').forEach(a => {
      const on = a.dataset.target === key;
      a.classList.toggle('is-active', on);
      a.classList.toggle('is-parent', a.dataset.target === parentKey);
      if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
    });
    if (mqStrip.matches) {
      // A collapsed subsection's link is hidden; keep its section in view instead.
      let link = toc.querySelector('a.is-active');
      if (link && !link.offsetParent) link = toc.querySelector('a.is-parent');
      // Keep the active link centered, but on the first section keep the
      // strip at its start.
      const first = link === toc.querySelector('a[data-target]');
      if (link) toc.scrollTo({ left: first ? 0 : link.offsetLeft - (toc.clientWidth - link.offsetWidth) / 2, behavior: 'smooth' });
    }
  }

  // Subsection lists open on their own while the reader is in that section and
  // close once they leave it. The arrow beside a section overrides this until
  // the reader moves to another section.
  function syncSubs(toc) {
    toc.querySelectorAll('li.has-sub').forEach(li => {
      const key = li.dataset.section;
      const open = subOverride.has(key) ? subOverride.get(key) : key === activeSection;
      const btn = li.querySelector('.toc-toggle');
      li.classList.toggle('is-collapsed', !open);
      btn.setAttribute('aria-expanded', open);
      btn.setAttribute('aria-label', `${open ? 'Hide' : 'Show'} ${li.dataset.label} subsections`);
    });
  }

  // `sub(section)` returns the nested links for a section.
  function initToc({ sub = () => '' } = {}) {
    const toc = document.getElementById('toc');
    if (!toc) return;
    const items = [...document.querySelectorAll('.page-section[data-nav]')].filter(sec => !sec.hidden).map(sec => {
      const key = esc(sec.dataset.nav), label = esc(sec.dataset.label || sec.id);
      const link = `<a href="#${esc(sec.id)}" data-target="${key}">${label}</a>`;
      const kids = sub(sec);
      if (!kids) return `
        <li>${link}</li>`;
      return `
        <li class="has-sub is-collapsed" data-section="${key}" data-label="${label}">
          <div class="toc-row">${link}<button type="button" class="toc-toggle" aria-expanded="false" aria-controls="toc-sub-${key}" aria-label="Show ${label} subsections"><svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3.5 10.5 8 6 12.5"/></svg></button></div>
          <div class="toc-sub-wrap" id="toc-sub-${key}">${kids}</div>
        </li>`;
    }).join('');
    toc.innerHTML = `<div class="toc-label">Contents</div><ol class="toc-top">${items}</ol>`;

    toc.addEventListener('click', e => {
      const btn = e.target.closest('.toc-toggle');
      if (!btn) return;
      const li = btn.closest('li.has-sub');
      subOverride.set(li.dataset.section, li.classList.contains('is-collapsed'));
      syncSubs(toc);
    });
    // Keep the bar centred while a list opens or closes.
    if (window.ResizeObserver) new ResizeObserver(syncMetrics).observe(toc);

    let ticking = false;
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => { ticking = false; updateActive(); });
    }, { passive: true });
    window.addEventListener('resize', () => { syncMetrics(); updateActive(true); });
    syncMetrics();
    if (document.fonts) document.fonts.ready.then(syncMetrics);   // web fonts change the bar's height
    updateActive(true);
    // Animate later openings, but not the one that sets up the page.
    requestAnimationFrame(() => requestAnimationFrame(() => toc.classList.add('toc-ready')));
  }

  // ---- Toast ---------------------------------------------------------------

  function restartClass(el, cls) {
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
  }

  let toastTimer = null;
  function toast(msg) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.hidden = false;
    restartClass(el, 'toast');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 2800);
  }

  // ---- Shared clicks -------------------------------------------------------

  document.addEventListener('click', e => {
    const ph = e.target.closest('a[data-placeholder]');
    if (ph) {
      e.preventDefault();
      toast(`The ${ph.dataset.placeholder} link isn't set yet`);
      return;
    }
    if (e.target.closest('[data-tx-close]')) { closeExpander(true); return; }
    // Anywhere on a card does what its thumbnail does (a link or button in
    // it does its own thing)
    const card = e.target.closest('.tcard.is-playable');
    if (card && !e.target.closest('a, button')) { openExpander(card.querySelector('.tcard-thumb')); return; }
    // Card thumbnails open in the grid (a keyboard "click" has detail 0).
    const play = e.target.closest('.tcard-thumb[data-play-task]');
    if (play) openExpander(play, { keyboard: e.detail === 0 });
  });

  // ---- Boot ----------------------------------------------------------------

  async function boot(render) {
    await loadTaskFiles();

    D.skills = (PAGE.skills || []).map(normalizeSkill);
    D.SK = Object.fromEntries(D.skills.map(s => [s.key, s]));
    D.challenge = PAGE.challenge ? normalizeChallenge(PAGE.challenge) : null;
    D.tasks = PAGE.tasks.map(normalizeTask).sort(byId);
    D.TK = Object.fromEntries(D.tasks.map(t => [t.id, t]));
    check();

    render(D);
    showProblems();

    // Content is rendered by script, so honor a #section link after render.
    if (location.hash) {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) target.scrollIntoView({ block: 'start', behavior: 'instant' });
    }
  }

  function start(render) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => boot(render));
    else boot(render);
  }

  window.SITE = {
    D, ASSET_DIRS, esc, fmt, paras, parasHtml, assetUrl, params,
    tasksUrl, representativeTasks, challengeTasks, videoItems, mainVideo,
    stillHtml, placeholderHtml, playBadge,
    specHtml, renderCard, playerHtml, wirePlayer, initToc, toast, restartClass, start
  };
})();

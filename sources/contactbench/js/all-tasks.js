/* =====================================================
   js/all-tasks.js — the All tasks page (tasks.html)
   =====================================================
   Shows every task's card, with a search box and skill filters.
   A task is shown when it uses every selected skill and every
   word of the search appears in its name.

   The filters are kept in the address (tasks.html?skills=insert,
   inhand&q=key), so a filtered view can be linked to. A bar with
   a Project page button stays pinned at the top once the page's
   own back link scrolls away.
   ===================================================== */

(function () {
  'use strict';

  const { esc, renderCard, params, tasksUrl } = window.SITE;

  window.SITE.start(D => {
    const grid = document.getElementById('all-tasks');
    const chips = document.getElementById('skill-filter');
    const input = document.getElementById('task-search');
    const results = document.getElementById('results');
    const empty = document.getElementById('no-results');
    if (!grid) return;

    // The search matches against each task's name.
    const index = Object.fromEntries(D.tasks.map(t => [t.id, t.name.toLowerCase()]));

    grid.innerHTML = D.tasks.map(t => renderCard(t, { level: 2 })).join('');
    const count = k => D.tasks.filter(t => t.skills.includes(k)).length;
    chips.innerHTML = `<button type="button" class="ro-opt" data-skill="" aria-pressed="false">All skills</button>` +
      D.skills.map(s => `<button type="button" class="ro-opt" data-skill="${esc(s.key)}" aria-pressed="false">${esc(s.name)}<span class="opt-count">${count(s.key)}</span></button>`).join('');

    const p = params();
    const state = {
      skills: new Set((p.get('skills') || '').split(',').filter(k => D.SK[k])),
      q: p.get('q') || ''
    };
    input.value = state.q;

    function apply() {
      const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      let shown = 0;
      grid.querySelectorAll('.tcard').forEach(card => {
        const t = D.TK[card.dataset.task];
        const ok = [...state.skills].every(k => t.skills.includes(k)) && words.every(w => index[t.id].includes(w));
        card.hidden = !ok;
        if (ok) shown++;
      });
      chips.querySelectorAll('[data-skill]').forEach(b => {
        const k = b.dataset.skill;
        b.setAttribute('aria-pressed', String(k ? state.skills.has(k) : state.skills.size === 0));
      });
      const filtered = state.skills.size || words.length;
      results.textContent = filtered ? `Showing ${shown} of ${D.tasks.length} tasks` : `${D.tasks.length} tasks`;
      empty.hidden = shown > 0;
      // Keep the filters in the address; browsers may refuse this for file:// pages.
      let url = tasksUrl([...state.skills]);
      if (state.q) url += `${url.includes('?') ? '&' : '?'}q=${encodeURIComponent(state.q)}`;
      try { history.replaceState(null, '', url); } catch (_) { /* ignore */ }
    }

    chips.addEventListener('click', e => {
      const b = e.target.closest('[data-skill]');
      if (!b) return;
      const k = b.dataset.skill;
      if (!k) state.skills.clear();
      else if (state.skills.has(k)) state.skills.delete(k);
      else state.skills.add(k);
      apply();
    });
    input.addEventListener('input', () => { state.q = input.value.trim(); apply(); });
    document.addEventListener('click', e => {
      if (!e.target.closest('[data-clear]')) return;
      state.skills.clear(); state.q = ''; input.value = '';
      apply();
      input.focus();
    });

    apply();

    // Show the pinned bar (with its Project page button) once the page's own
    // back link has scrolled out of view.
    const bar = document.getElementById('scroll-bar');
    const anchor = document.getElementById('page-back');
    if (bar && anchor && 'IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => {
        bar.classList.toggle('is-shown', !e.isIntersecting && e.boundingClientRect.top < 0);
      }).observe(anchor);
    }
  });
})();

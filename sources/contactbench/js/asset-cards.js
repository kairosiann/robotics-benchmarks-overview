/* =====================================================
   js/asset-cards.js — the asset cards, shared by pages
   =====================================================
   Reads config/asset-page.js and draws its asset cards: a still of
   the 3D model on the left, the name and downloads on the right.
   The All assets page (js/all-assets.js) shows every card; a task
   card's panel (js/site.js) shows the cards its task names in
   `assetCards`.

   Clicking a card's still, wherever the card is, opens the asset in
   a panel under its row in that grid: the 3D viewer
   (js/model-viewer.js) beside its name, downloads, hardware, and
   printing tips. The card's Downloads or Printing tips button opens it
   with only that beside the viewer, and its Hardware button (an asset
   with `hardware`; Assembly, for one with `assembly` videos too) with
   only its hardware beside the viewer and its assembly videos under both (each switches an open
   panel to it). For an
   asset with variants, the downloads are steps: 1, the base parts
   every variant needs; 2, a table of each variant's own parts, one
   per group of variants (an asset can have several, e.g. springs
   and handles). If its variants look different (their own model,
   color, or view), clicking a variant's row shows it in 3D (its row
   is highlighted): the viewer shows the base parts' models with the
   chosen variant of each group (groups sharing a slot share one
   choice) and swaps a variant in place, keeping the reader's view.
   Under "Toggle visibility", the models and bodies an asset's
   `toggles` name (a cover, a shell) each get a button that hides or
   shows them. Under the downloads, "Hardware" lists the screws and
   nuts it takes (`hardware`); under "Printing tips", its tips (`tips`)
   and screenshots of the parts as placed in the slicer (`orientation`),
   and its card has a Printing tips button. One
   panel at a time; the still again (once all of it shows), the × button,
   or Esc closes it, and it follows its card when the grid reflows.

   Load order: config/asset-page.js, js/site.js, js/model-view.js,
   this file, js/model-viewer.js.
   ===================================================== */

(function () {
  'use strict';

  const { esc } = window.SITE;
  const MV = window.MODEL_VIEW;
  const problems = window.PAGE.errors;
  const isAbsolute = p => /^([a-z][a-z0-9+.-]*:)?\/\//i.test(p) || /^(\/|\.\.?\/)/.test(p);

  // ---- Config --------------------------------------------------------------
  // Every card as { key, name, note, hardware: [{ label, rows: [{ count,
  // item }] }], assembly: [{ label, video, poster }], tips: [sentences],
  // orientation: [{ label, image }], view, stl, mf, own, toggles: [{ label,
  // model: [ids], body, except }], base: { stl, mf } or null, baseFiles, groups: [{
  // variation, variants: [{ label, files, view, stl, mf }] }], slotOf, slots,
  // start, combos, differ }. A model file is { id, model, color, rgb, offset }; its
  // id is the file as the config names it, as toggles name it too. An asset
  // without variants shows `own`; one with variants, its base parts' files
  // and the variant chosen in each slot (groups sharing a slot share one
  // choice: slotOf gives each group's slot, and start the { g, v } first
  // chosen in each), or, when its files are combinations (combos: a Map from
  // the chosen variants' places, e.g. '0,2', to { files, stl, mf }), the
  // combination chosen.

  // One value or a list of them (a model field's files, a toggle's bodies)
  const asList = m => (Array.isArray(m) ? m : [m]).filter(Boolean).map(String);

  function normalize(raw) {
    raw = raw || {};
    const dir = String(raw.dir || '').replace(/([^/])$/, '$1/');
    const url = p => !p ? '' : isAbsolute(p) ? p : dir + p;
    const colors = raw.colors || {};
    // Assembly videos: files in videoDir; each one's poster is its frame
    // one second in, <name>-t1.jpg in stillDir (keep in sync with stillName
    // in tools/check.mjs)
    const folder = d => String(d || '').replace(/([^/])$/, '$1/');
    const videoDir = folder(raw.videoDir), stillDir = folder(raw.stillDir);
    return (Array.isArray(raw.assets) ? raw.assets : []).map((a, i) => {
      const key = String(a.key || `asset-${i + 1}`);
      const name = String(a.name || key);
      // A model field's files: [{ id, model (its path from the page), color,
      // rgb, offset }]. `color`: one for all of them, or a list, one per file
      // in order (a yellow bottle and its gray cap).
      const files = (field, color, label, offset = null) => {
        asList(color).filter(c => !colors[c]).forEach(c => problems.push(`config/asset-page.js: ${name}${label ? ` (${label})` : ''} uses color "${c}", which isn't in colors.`));
        const colorAt = i => Array.isArray(color) ? color[i] : color;
        return asList(field).map((m, i) => ({ id: m, model: url(m), color: colorAt(i), rgb: colors[colorAt(i)] || null, offset }));
      };
      // Its groups of variants: `groups`, or one made of variation and variants
      const rawGroups = Array.isArray(a.groups) ? a.groups
        : Array.isArray(a.variants) ? [{ variation: a.variation, variants: a.variants }] : [];
      const combined = Array.isArray(a.combinations);
      const groups = rawGroups.map((grp, g) => ({
        variation: String(grp.variation || ''),
        slot: grp.slot && !combined ? String(grp.slot) : `#${g}`,
        variants: (Array.isArray(grp.variants) ? grp.variants : []).map((v, j) => {
          const label = String(v.label || `Variant ${j + 1}`);
          return {
            label, first: !!v.default,
            files: files(v.model || a.model, v.color || grp.color || a.color, label, v.offset || grp.offset),
            view: v.view, stl: url(v.stl), mf: url(v['3mf'])
          };
        })
      })).filter(grp => grp.variants.length);
      const hasVariants = groups.length > 0;
      // Groups with the same slot share one choice (say, a door handle or a
      // doorknob, on the same shaft); the first chosen is the one marked
      // default, else the first
      const slots = [...new Set(groups.map(grp => grp.slot))];
      const slotOf = groups.map(grp => slots.indexOf(grp.slot));
      const start = slots.map((_, s) => {
        const inSlot = groups.map((grp, g) => g).filter(g => slotOf[g] === s);
        for (const g of inSlot) {
          const v = groups[g].variants.findIndex(x => x.first);
          if (v >= 0) return { g, v };
        }
        return { g: inSlot[0], v: 0 };
      });
      const lookOf = x => JSON.stringify([x.files.map(f => [f.id, f.rgb]), x.view]);
      const own = hasVariants ? [] : files(a.model, a.color, '');
      const baseFiles = hasVariants && a.base ? files(a.base.model, a.base.color || a.color, 'base parts') : [];
      // An asset whose files are combinations, one for each choice of a
      // variant in every group (a lightbulb's size and thread): each names
      // its variants by label, in the groups' order. Keyed by the chosen
      // variants' places in their groups, e.g. '0,2'.
      const combos = combined && hasVariants ? new Map(a.combinations.map(c => {
        const names = asList(c.variants);
        const at = groups.map((grp, g) => grp.variants.findIndex(v => v.label === names[g]));
        return [at.join(','), { files: files(c.model || a.model, c.color || a.color, names.join(', '), c.offset), stl: url(c.stl), mf: url(c['3mf']) }];
      })) : null;
      // A toggle's models: files as written above, or patterns where * stands
      // for any part of a file's name (every variant's bottle: …/bottle_*.stl)
      const ids = [...new Set([...baseFiles, ...own, ...groups.flatMap(grp => grp.variants.flatMap(v => v.files)),
        ...(combos ? [...combos.values()].flatMap(c => c.files) : [])].map(f => f.id))];
      const matches = p => !p.includes('*') ? [p]
        : ids.filter(id => new RegExp(`^${p.split('*').map(s => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('[^/]*')}$`).test(id));
      // The screws and nuts to put it together: rows of { count, item }, or
      // groups of them, { label, items } (the door's own, then each module's)
      const hwRows = list => (Array.isArray(list) ? list : []).map(h => ({ count: Number(h && h.count) || 0, item: String((h && h.item) || '') }));
      const hw = Array.isArray(a.hardware) ? a.hardware : [];
      const hardware = hw.some(h => h && h.items)
        ? hw.map(h => ({ label: String((h && h.label) || ''), rows: hwRows(h && h.items) }))
        : hw.length ? [{ label: '', rows: hwRows(hw) }] : [];
      if (hardware.some(h => h.rows.some(r => !r.item || !(r.count > 0)))) problems.push(`config/asset-page.js: ${name}'s hardware should list { count, item } rows, e.g. { count: 4, item: 'M3 × 15 mm screw' }.`);
      const assembly = (Array.isArray(a.assembly) ? a.assembly : []).filter(v => v && v.video).map((v, j) => ({
        label: String(v.label || `Part ${j + 1}`),
        video: isAbsolute(v.video) ? v.video : videoDir + v.video,
        poster: isAbsolute(v.video) || !stillDir ? '' : `${stillDir}${String(v.video).replace(/\.[^./]+$/, '')}-t1.jpg`
      }));
      // Its printing tips: sentences, and screenshots of its parts as placed
      // in the slicer, for printing without the 3MF
      const tips = asList(a.tips);
      // Its assembly tips: sentences, shown after its hardware
      const assemblyTips = asList(a.assemblyTips);
      const orientation = (Array.isArray(a.orientation) ? a.orientation : []).filter(o => o && o.image).map(o => ({
        label: String(o.label || 'Print orientation'), image: url(o.image)
      }));
      return {
        key, name, note: String(a.note || ''), hardware, assembly, assemblyTips, tips, orientation, groups, slotOf, start, slots: slots.length,
        view: a.view || MV.view,
        stl: url(a.stl), mf: url(a['3mf']),
        own,
        toggles: (Array.isArray(a.toggles) ? a.toggles : []).map(t => ({
          label: String(t.label || asList(t.model)[0] || ''),
          model: [...new Set(asList(t.model).flatMap(matches))],
          body: asList(t.body),
          except: asList(t.except)
        })),
        base: hasVariants && a.base ? { stl: url(a.base.stl), mf: url(a.base['3mf']) } : null,
        baseFiles, combos,
        // Whether choosing a variant changes the 3D view (with combinations,
        // it also chooses the download)
        differ: !!combos || slots.some((_, s) => new Set(groups.filter((grp, g) => slotOf[g] === s).flatMap(grp => grp.variants.map(lookOf))).size > 1)
      };
    });
  }

  // The cards in config/asset-page.js, read once per page
  let all = null;
  const cards = () => all || (all = normalize(window.PAGE.assetPage));

  // What the viewer shows for a choice of variants (`pick`: a { g, v } for
  // each slot): { models: [{ id, mesh, color, offset }], still, view, label }.
  // With one slot, each variant has its own still; with several, there's only
  // one, of the first choice. Stills are named for their own models first,
  // then the base parts', e.g. …/90_deg+base.png.
  // The combination chosen, for an asset whose files are combinations (each
  // group is its own slot, so `pick` is in the groups' order)
  const comboOf = (a, pick) => a.combos.get(pick.map(p => p.v).join(','));
  const filesFor = (a, pick) => a.combos ? (comboOf(a, pick) || { files: [] }).files
    : pick.flatMap(p => a.groups[p.g].variants[p.v].files);
  function shown(a, pick) {
    const chosen = pick.map(p => a.groups[p.g].variants[p.v]);
    const own = a.groups.length ? filesFor(a, pick) : a.own;
    const stillOwn = a.slots > 1 ? filesFor(a, a.start) : own;
    return {
      models: [...a.baseFiles, ...own].map(m => ({ id: m.id, mesh: MV.meshPath(m.model), color: m.rgb, offset: m.offset })),
      still: stillOwn.length || a.baseFiles.length ? MV.stillPath([...stillOwn, ...a.baseFiles]) : '',
      view: (a.slots === 1 && chosen[0].view) || a.view,
      label: chosen.length ? `${a.name} (${chosen.map(v => v.label).join(', ')})` : a.name
    };
  }

  // ---- Pieces of a card (and its panel) ------------------------------------

  const fileName = p => decodeURIComponent(String(p).split('/').pop());
  function fileBtn(kind, href, what) {
    const text = kind === 'stl' ? 'STL' : 'Bambu Lab 3MF';
    const inner = `<span class="fbtn-ico" aria-hidden="true">↓</span><span>${text}</span>`;
    if (!href) return `<span class="fbtn is-off" title="The ${text} file for ${esc(what)} isn't available yet">${inner}</span>`;
    return `<a class="fbtn print" href="${esc(href)}" download title="${esc(fileName(href))}" aria-label="Download the ${text} file for ${esc(what)}">${inner}</a>`;
  }
  const what = (a, v) => `${a.name} (${v.label})`;
  // `mf`: whether it has a 3MF (not when its asset has one 3MF of all parts)
  const filesHtml = (files, what, mf = true) => `<div class="asset-files">${fileBtn('stl', files.stl, what)}${mf ? fileBtn('3mf', files.mf, what) : ''}</div>`;
  function setsText(a) {
    const n = a.combos ? a.combos.size : a.groups.reduce((sum, grp) => sum + grp.variants.length, 0);
    return `${a.base ? 'Base parts + ' : ''}${n} ${n === 1 ? 'variant' : 'variants'}`;
  }
  const isPicked = (pick, g, v) => pick.some(p => p.g === g && p.v === v);
  // Plain text, with [text](https://…) for a link (opened in a new tab): an
  // asset's note, on its card and under its panel's Downloads, and its
  // hardware's items
  const linked = s => esc(s).replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const noteHtml = a => !a.note ? '' : `<p class="asset-note">${linked(a.note)}</p>`;

  const nutIcon = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" aria-hidden="true"><path d="M8 1.5 13.6 4.75v6.5L8 14.5 2.4 11.25v-6.5z"/><circle cx="8" cy="8" r="2.4"/></svg>';
  const nozzleIcon = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 1.5h7v3.5L9.5 8h-3l-2-3z"/><path d="M8 8v2.5M1.5 14h13"/></svg>';
  const rotateIcon = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 4.5 7.2v9.6L12 21l7.5-4.2V7.2z"/><path d="M4.5 7.2 12 11.4l7.5-4.2M12 11.4V21"/></svg>';

  // The still, Downloads, Printing tips, and Hardware (or Assembly) open the asset's
  // panel, showing (data-show) all of it but the videos, just its
  // downloads, just its printing tips, or just its hardware and videos.
  // `id`:
  // the card's id is its key (the All assets page: assets.html#<key>).
  // `tag`: the element its name is in.
  function cardHtml(a, pick, { id = true, tag = 'h2' } = {}) {
    const s = shown(a, pick);
    const opener = (cls, show, label, html) =>
      `<button type="button" class="${cls}" data-open data-show="${show}" aria-expanded="false" aria-label="${label}">${html}</button>`;
    const still = s.models.length
      ? opener('asset-still', 'all', `View ${esc(a.name)} in 3D`, `
          <img src="${esc(s.still)}" alt="" loading="lazy" decoding="async">
          <span class="asset-badge" aria-hidden="true">${rotateIcon}</span>`)
      : `<div class="asset-still is-empty"><span class="vidmeta">No 3D model yet</span></div>`;
    // Its hardware and assembly videos share a button: Hardware, or
    // Assembly when it has videos
    const assembly = [a.hardware.length && 'the screws and nuts it takes', a.assemblyTips.length && 'tips', a.assembly.length && 'videos'].filter(Boolean).join(', and ');
    const asmLabel = a.assembly.length ? 'Assembly' : 'Hardware';
    const more = (!a.tips.length && !a.orientation.length ? ''
      : opener('asset-dl asset-hw', 'printing', `Printing tips for ${esc(a.name)}`, `<span class="fbtn-ico">${nozzleIcon}</span>Printing tips`))
      + (!assembly ? ''
      : opener('asset-dl asset-hw', 'assembly', `${asmLabel} for ${esc(a.name)}: ${assembly}`, `<span class="fbtn-ico">${nutIcon}</span>${asmLabel}`));
    const downloads = a.groups.length
      ? `<div class="asset-dl-wrap">
          <p class="asset-sets">${esc(setsText(a))}</p>
          <div class="asset-btns">
            ${opener('asset-dl', 'downloads', `Downloads for ${esc(a.name)}: ${esc(setsText(a))}`, '<span class="fbtn-ico" aria-hidden="true">↓</span>Downloads')}
            ${more}
          </div>
        </div>`
      : more ? `<div class="asset-dl-wrap">${filesHtml(a, a.name)}<div class="asset-btns">${more}</div></div>`
      : filesHtml(a, a.name);
    return `
      <article class="asset-card"${id ? ` id="${esc(a.key)}"` : ''} data-asset="${esc(a.key)}">
        ${still}
        <div class="asset-body">
          <${tag} class="asset-name">${esc(a.name)}</${tag}>
          ${noteHtml(a)}
          ${downloads}
        </div>
      </article>`;
  }

  // The chosen combination, for an asset whose files are combinations: the
  // variants' names, then its STL and 3MF
  function comboHtml(a, pick) {
    const label = pick.map(p => a.groups[p.g].variants[p.v].label).join(', ');
    return `<span class="ax-combo-k">${esc(label)}</span>${filesHtml(comboOf(a, pick) || {}, `${a.name} (${label})`)}`;
  }

  // The panel's downloads: an asset's files; or, with variants, the base
  // parts (step 1) and a table of each group's variants (step 2). When the
  // variants look different, clicking a row shows its variant in 3D; its
  // name is a button for the keyboard. When its files are combinations, the
  // tables only choose, and the file for the choice is the last step. An
  // asset with variants may have one 3MF of all its parts: it comes first,
  // and the steps then have only STLs.
  function downloadsHtml(a, pick) {
    if (!a.groups.length) return filesHtml(a, a.name);
    const mf = !a.mf;
    const all = mf ? '' : `
      <div class="ax-all"><span class="ax-all-k">All parts</span>${fileBtn('3mf', a.mf, `${a.name} (all parts)`)}</div>`;
    const label = (g, v, x) => !a.differ ? esc(x.label)
      : `<button type="button" class="ax-var" data-variant aria-pressed="${isPicked(pick, g, v)}">${esc(x.label)}<span class="visually-hidden"> (show in 3D)</span></button>`;
    const table = a.groups.map((grp, g) => `
      <table class="ax-dl-table${a.differ ? ' is-choice' : ''}">
        <thead><tr><th scope="col">${esc(grp.variation || 'Variant')}</th>${a.combos ? '' : '<th scope="col"><span class="visually-hidden">Files</span></th>'}</tr></thead>
        <tbody>${grp.variants.map((x, v) => `
          <tr data-group="${g}" data-row="${v}"${a.differ && isPicked(pick, g, v) ? ' class="is-shown"' : ''}><th scope="row">${label(g, v, x)}</th>${a.combos ? '' : `<td>${filesHtml(x, what(a, x), mf)}</td>`}</tr>`).join('')}
        </tbody>
      </table>`).join('');
    const steps = list => `
      <ol class="ax-steps">${list.map(([k, html], i) => `
        <li>
          <span class="ax-step-num" aria-hidden="true">${i + 1}</span>
          <div>
            <p class="ax-step-k">${k}</p>
            ${html}
          </div>
        </li>`).join('')}
      </ol>`;
    const base = a.base ? [['Base parts', filesHtml(a.base, `${a.name} base parts`, mf)]] : [];
    if (a.combos) return '<p class="ax-dl-note">Choose a variant from each group, then download that combination</p>'
      + steps([...base, ['Choose variants', table], ['Download', `<div class="ax-combo" aria-live="polite">${comboHtml(a, pick)}</div>`]]);
    const each = a.groups.length > 1 ? ' from each group' : '';
    const note = text => `${all}<p class="ax-dl-note">${mf ? 'Download' : 'Or download the STLs of'} ${text}${each}</p>`;
    if (!a.base) return note('one or more variants') + table;
    return note('base parts + one or more variants') + steps([...base, ['Variant parts', table]]);
  }

  // The panel's hardware: a row per item and its count, under its group's
  // label when there are groups; then its assembly tips, like its printing
  // tips
  function hardwareHtml(a, tag) {
    if (!a.hardware.length && !a.assemblyTips.length) return '';
    const rows = a.hardware.map(grp => `
      <tbody>${grp.label ? `
        <tr class="ax-hw-group"><th scope="colgroup" colspan="2">${esc(grp.label)}</th></tr>` : ''}${grp.rows.map(r => `
        <tr><th scope="row">${linked(r.item)}</th><td>${r.count}</td></tr>`).join('')}
      </tbody>`).join('');
    return `
        <div class="ax-hw">${a.hardware.length ? `
          <${tag} class="ax-hw-title" tabindex="-1">Hardware</${tag}>
          <table class="ax-dl-table ax-hw-table">
            <thead><tr><th scope="col">Part</th><th scope="col">Qty</th></tr></thead>${rows}
          </table>` : ''}${a.assemblyTips.length ? `
          <${tag} class="ax-pt-title ax-at-title" tabindex="-1">Assembly tips</${tag}>
          <ul class="ax-pt-tips">${a.assemblyTips.map(t => `<li>${linked(t)}</li>`).join('')}</ul>` : ''}
        </div>`;
  }

  // The panel's printing tips: its tips, then each screenshot of its parts
  // as placed in the slicer, under its label
  function printingHtml(a, tag) {
    if (!a.tips.length && !a.orientation.length) return '';
    return `
        <div class="ax-pt">
          <${tag} class="ax-pt-title" tabindex="-1">Printing tips</${tag}>${a.tips.length ? `
          <ul class="ax-pt-tips">${a.tips.map(t => `<li>${linked(t)}</li>`).join('')}</ul>` : ''}
          ${a.orientation.map(o => `
          <figure class="ax-pt-fig">
            <figcaption class="ax-video-k">${esc(o.label)}</figcaption>
            <img src="${esc(o.image)}" alt="${esc(`${a.name}: ${o.label}, as placed in the slicer`)}" loading="lazy" decoding="async">
          </figure>`).join('')}
        </div>`;
  }

  // `tag`: the elements its title and Downloads, Hardware, and Printing tips
  // headings are in (h2 and h3 on the All assets page)
  function panelHtml(a, pick, tag = ['h2', 'h3']) {
    const s = shown(a, pick);
    return `
      <div class="ax-stage">${s.models.length
        ? `<img class="ax-still" src="${esc(s.still)}" alt="">`
        : '<span class="vidmeta">No 3D model yet</span>'}
      </div>
      <div class="ax-head">
        <${tag[0]} class="ax-title">${esc(a.name)}</${tag[0]}>
        <button type="button" class="tx-close" data-close aria-label="Close" title="Close (Esc)">×</button>
      </div>
      <div class="ax-info">
        <div class="ax-parts" hidden></div>
        <div class="ax-dl">
          <${tag[1]} class="ax-dl-title" tabindex="-1">Downloads</${tag[1]}>
          ${noteHtml(a)}
          ${downloadsHtml(a, pick)}
        </div>${hardwareHtml(a, tag[1])}${printingHtml(a, tag[1])}
      </div>${videosHtml(a, tag[1])}`;
  }

  // The panel's assembly videos, shown only by the card's Assembly button
  // (under the viewer and the hardware): one under another, each with its
  // title and poster; nothing loads until one plays
  function videosHtml(a, tag) {
    if (!a.assembly.length) return '';
    return `
      <div class="ax-videos">
        <${tag} class="ax-videos-title" tabindex="-1">Assembly videos</${tag}>
        <div class="ax-video-list">${a.assembly.map(v => `
          <figure class="ax-video">
            <figcaption class="ax-video-k">${esc(v.label)}</figcaption>
            <video controls playsinline preload="none"${v.poster ? ` poster="${esc(v.poster)}"` : ''} src="${esc(v.video)}" aria-label="${esc(`${a.name} assembly: ${v.label}`)}"></video>
          </figure>`).join('')}
        </div>
      </div>`;
  }

  // ---- The panel --------------------------------------------------------------

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const behavior = () => reducedMotion.matches ? 'auto' : 'smooth';
  const look = s => JSON.stringify([s.models, s.view]);
  let keyed = null;
  const byKey = () => keyed || (keyed = Object.fromEntries(cards().map(a => [a.key, a])));
  // The variants in each asset's 3D view: a { g, v } for each slot
  const sel = {};
  const pickOf = a => sel[a.key] || (sel[a.key] = a.start.map(p => ({ ...p })));

  let ex = null;   // the open panel: { a, card, opener, el, show, ro, shown, ready }

  // The last item in `card`'s row, counted from its grid's columns (taking
  // the panel out to measure would shorten a short page, and the browser
  // would scroll back up)
  function rowEnd(card) {
    const grid = card.parentElement;
    const all = [...grid.children].filter(c => !c.classList.contains('asset-expand') && !c.hidden);
    const cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length || 1;
    return all[Math.min(all.length, (Math.floor(all.indexOf(card) / cols) + 1) * cols) - 1];
  }
  function place() {
    if (!ex) return;
    if (ex.card.hidden) { close(false); return; }  // filtered out by a search
    const end = rowEnd(ex.card);
    if (end.nextElementSibling !== ex.el) end.after(ex.el);
  }

  // Shows the chosen variants in the viewer: the first time, it opens there;
  // after that, they swap in place (the base parts, the reader's view, and
  // hidden bodies stay)
  function showModel() {
    const { el, a } = ex;
    const s = shown(a, pickOf(a));
    if (!s.models.length || ex.shown === look(s)) return;
    ex.shown = look(s);
    const stage = el.querySelector('.ax-stage');
    stage.querySelector('.ax-still').src = s.still;
    window.MODEL_VIEWER.open(stage, { models: s.models, view: s.view, label: s.label })
      .then(ok => { if (ok && ex && ex.el === el) ready(); });
  }

  // Once the viewer first shows the asset: its toggles, and the other
  // variants' models start loading; after a reload, the hidden bodies again
  function ready() {
    if (ex.ready) { hideParts(); return; }
    ex.ready = true;
    showToggles(ex.el.querySelector('.ax-parts'));
    const files = ex.a.combos ? [...ex.a.combos.values()].flatMap(c => c.files) : ex.a.groups.flatMap(grp => grp.variants.flatMap(v => v.files));
    window.MODEL_VIEWER.preload([...new Set(files.map(f => MV.meshPath(f.model)))]);
  }

  // "Toggle visibility": a button per body the asset's toggles name,
  // pressed while it shows, with a swatch of its color
  function showToggles(box) {
    const { toggles } = ex.a;
    const parts = window.MODEL_VIEWER.parts();
    const colorOf = t => (parts.find(p => t.model.includes(p.model) &&
      (!t.body.length || t.body.includes(p.name)) && !t.except.includes(p.name)) || {}).color;
    box.hidden = !toggles.length;
    box.innerHTML = box.hidden ? '' : `
      <div class="ax-parts-head">
        <p class="asset-vars-k" id="ax-parts-k">Toggle visibility</p>
        ${toggles.length > 1 ? '<button type="button" class="ax-parts-all" data-parts-all disabled>Show all</button>' : ''}
      </div>
      <div class="ax-part-opts" role="group" aria-labelledby="ax-parts-k">${toggles.map((t, i) => {
        const color = colorOf(t);
        return `
        <button type="button" class="ax-part" aria-pressed="true" data-part="${i}"${color ? ` style="--part: rgb(${color.join(', ')})"` : ''}><span class="ax-part-sw" aria-hidden="true"></span><span class="visually-hidden">Show </span>${esc(t.label)}</button>`;
      }).join('')}
      </div>`;
  }
  function hideParts() {
    const off = [...ex.el.querySelectorAll('[data-part][aria-pressed="false"]')].map(b => ex.a.toggles[Number(b.dataset.part)]);
    window.MODEL_VIEWER.hide(off.map(t => ({ model: t.model, body: t.body, except: t.except })));
    const all = ex.el.querySelector('[data-parts-all]');
    if (all) all.disabled = !off.length;
  }

  // What the panel shows: beside the viewer, under its toggles, 'all' (its
  // downloads, hardware, and printing tips), 'downloads', 'printing', or
  // 'assembly' (its hardware, with its videos under the viewer). The card's
  // button for it is marked. The 3D view loads once the panel first shows
  // it, and the videos pause when they're hidden.
  function setShow(show) {
    ex.show = ex.el.dataset.show = show;
    ex.card.querySelectorAll('[data-show]').forEach(b => b.classList.toggle('is-shown', b.dataset.show === show));
    if (show !== 'assembly') ex.el.querySelectorAll('.ax-videos video').forEach(v => v.pause());
    showModel();
  }

  // Brings what the panel shows into view: the whole panel, or, once its
  // downloads, printing tips, or hardware (else videos) are stacked under
  // the viewer, just them. The keyboard goes to its heading (the viewer,
  // for all of it).
  function reveal(keyboard) {
    const part = ex.el.querySelector({ downloads: '.ax-dl', printing: '.ax-pt', assembly: '.ax-hw, .ax-videos' }[ex.show] || null);
    const stacked = part && part.getBoundingClientRect().top >= ex.el.querySelector('.ax-stage').getBoundingClientRect().bottom;
    (stacked ? part : ex.el).scrollIntoView({ block: 'nearest', behavior: behavior() });
    if (!keyboard) return;
    const focus = part ? part.querySelector('[tabindex="-1"]') : ex.el.querySelector('canvas');
    if (focus) focus.focus({ preventScroll: true });
  }

  // `trigger`: the card's still, or its Downloads, Printing tips, or
  // Assembly button; its data-show (or `show`) is what the panel shows. On an
  // open panel, another of them switches what it shows (the 3D view stays),
  // a button again brings it into view, and the still showing all of it
  // closes it.
  // `scroll: false` leaves the page where it is. In a task card's panel, the
  // panel's title and headings aren't headings.
  function open(trigger, { keyboard = false, scroll = true, show = trigger.dataset.show } = {}) {
    const card = trigger.closest('.asset-card');
    const a = byKey()[card.dataset.asset];
    const has = { downloads: true, printing: a.tips.length || a.orientation.length, assembly: a.hardware.length || a.assemblyTips.length || a.assembly.length };
    if (!has[show]) show = 'all';
    if (ex && ex.card === card) {
      if (show === 'all' && ex.show === 'all') { close(false); return; }
      ex.opener = trigger;
      setShow(show);
      reveal(keyboard);
      return;
    }
    close(false);
    const el = document.createElement('section');
    el.className = 'tcard-expand asset-expand';
    el.id = 'asset-panel';
    el.setAttribute('aria-label', a.name);
    el.innerHTML = panelHtml(a, pickOf(a), card.closest('.task-expand') ? ['p', 'p'] : undefined);
    rowEnd(card).after(el);
    ex = { a, card, opener: trigger, el };
    setShow(show);
    card.classList.add('is-open');
    card.querySelectorAll('[data-open]').forEach(b => {
      b.setAttribute('aria-expanded', 'true');
      b.setAttribute('aria-controls', el.id);
    });
    if ('ResizeObserver' in window) {
      ex.ro = new ResizeObserver(() => requestAnimationFrame(place));
      ex.ro.observe(card.parentElement);
    }
    if (scroll) reveal(keyboard);
  }

  function close(refocus) {
    if (!ex) return;
    const { el, card, opener, ro } = ex;
    ex = null;
    if (ro) ro.disconnect();
    window.MODEL_VIEWER.close();
    el.remove();
    card.classList.remove('is-open');
    card.querySelectorAll('[data-open]').forEach(b => {
      b.setAttribute('aria-expanded', 'false');
      b.removeAttribute('aria-controls');
      b.classList.remove('is-shown');
    });
    if (refocus) opener.focus({ preventScroll: true });
  }

  // ---- The variant in the 3D view -------------------------------------------

  // Shows variant v of group g, in place of the one chosen in its slot
  function choose(g, v) {
    const a = ex.a, pick = pickOf(a);
    pick[a.slotOf[g]] = { g, v };
    ex.el.querySelectorAll('tr[data-row]').forEach(r => {
      const on = isPicked(pick, Number(r.dataset.group), Number(r.dataset.row));
      r.classList.toggle('is-shown', on);
      const b = r.querySelector('[data-variant]');
      if (b) b.setAttribute('aria-pressed', String(on));
    });
    const combo = ex.el.querySelector('.ax-combo');
    if (combo) combo.innerHTML = comboHtml(a, pick);
    // The card's still follows (when each variant has one), so it matches
    // the panel when it closes
    const img = ex.card.querySelector('.asset-still img'), still = shown(a, pick).still;
    if (img && still) img.src = still;
    showModel();
  }

  // ---- Events -------------------------------------------------------------

  document.addEventListener('click', e => {
    const trigger = e.target.closest('.asset-card [data-open]');
    if (trigger) { open(trigger, { keyboard: e.detail === 0 }); return; }
    if (!ex || !ex.el.contains(e.target)) return;
    if (e.target.closest('[data-close]')) { close(true); return; }
    const part = e.target.closest('[data-part]');
    if (part) {
      part.setAttribute('aria-pressed', String(part.getAttribute('aria-pressed') !== 'true'));
      hideParts();
      return;
    }
    if (e.target.closest('[data-parts-all]')) {
      ex.el.querySelectorAll('[data-part]').forEach(b => b.setAttribute('aria-pressed', 'true'));
      hideParts();
      return;
    }
    // Anywhere on a variant's row (its download buttons too) shows it in 3D
    const row = e.target.closest('.ax-dl-table.is-choice tr[data-row]');
    if (row) choose(Number(row.dataset.group), Number(row.dataset.row));
  });
  // One assembly video plays at a time
  document.addEventListener('play', e => {
    if (!ex || !e.target.closest || !e.target.closest('.ax-videos')) return;
    ex.el.querySelectorAll('.ax-videos video').forEach(v => { if (v !== e.target) v.pause(); });
  }, true);
  // Esc closes the panel, and only it: this runs first (capturing), and
  // marks the key handled, so a task card's panel around it stays open
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || !ex) return;
    e.preventDefault();
    close(true);
  }, true);

  // place: after cards are shown or hidden (a search), moves the open panel
  // under its card's row, or closes it if its card is hidden
  window.ASSET_CARDS = { cards, byKey, pickOf, cardHtml, open, close, place };
})();

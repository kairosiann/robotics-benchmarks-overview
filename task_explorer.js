(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const readData = (id) => JSON.parse(byId(id).textContent);
  const catalog = readData("task-data");
  const images = readData("image-data");
  const concepts = readData("search-concepts");
  const coverage = readData("coverage-data");
  const index = TaskSearch.createIndex(catalog, concepts);
  const taskById = new Map(catalog.map((task) => [task.id, task]));
  const families = [...new Set(catalog.map((task) => task.family).filter(Boolean))]
    .sort((first, second) => first.localeCompare(second));
  const pageSize = 12;
  const maxPins = 3;
  const pins = new Set();
  const proposalFields = {
    title: "proposal-name",
    description: "proposal-description",
    setup_summary: "proposal-setup",
    observation: "proposal-observation",
    grading_summary: "proposal-grading",
    grading_evidence: "proposal-evidence",
  };

  let family = "";
  let page = 0;
  let query = "";
  let results = [];
  let queryMatches = new Map();
  let queryTerms = [];

  function node(tag, properties = {}, ...children) {
    const element = document.createElement(tag);
    Object.assign(element, properties);
    element.append(...children.filter((child) => child != null));
    return element;
  }

  function textBlock(value, fallback = "Unavailable in this record.") {
    return node("div", { className: "explorer-text", textContent: value || fallback });
  }

  function httpsUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url : null;
    } catch {
      return null;
    }
  }

  function sourceLink(value, label) {
    const url = httpsUrl(value);
    return url ? node("a", { href: url.href, target: "_blank", rel: "noopener noreferrer", textContent: label }) : null;
  }

  function action(label, handler, className = "") {
    const button = node("button", { type: "button", className, textContent: label });
    button.addEventListener("click", handler);
    return button;
  }

  function renderCoverage() {
    const manifest = new Map((coverage.families || []).map((entry) => [entry.family, entry]));
    const tbody = node("tbody");
    for (const name of families) {
      const tasks = catalog.filter((task) => task.family === name);
      const entry = manifest.get(name) || {};
      const definitions = tasks.filter((task) => task.goal || task.grading_levels?.length).length;
      const observations = tasks.filter((task) => task.observation).length;
      const visuals = tasks.filter((task) => task.video || images[task.image]
        || task.media?.some((media) => media.type === "image" || media.type === "video")).length;
      const scope = node("td", {}, textBlock(entry.scope, "Task records from the included source catalog."));
      if (entry.notes) scope.append(node("p", { className: "explorer-scope", textContent: entry.notes }));
      const source = sourceLink(entry.source, "Catalog source");
      if (source) scope.append(source);
      const details = node("td", {},
        node("div", { textContent: definitions + " goal or rubric excerpts" }),
        node("div", { textContent: observations + " robot-input descriptions" }),
        node("div", { textContent: visuals + " records with visual links" }));
      const button = action(name, () => {
        family = name;
        byId("suite").value = "";
        updateVersionAndSuite("");
        refresh();
        byId("search").focus({ preventScroll: true });
        byId("explorer-controls").scrollIntoView({ block: "start" });
      }, "explorer-coverage-link");
      tbody.append(node("tr", {}, node("th", { scope: "row" }, button),
        node("td", { textContent: tasks.length.toLocaleString() }), scope, details));
    }
    const header = node("tr", {},
      ...["Family", "Entries", "Included scope", "Available fields"].map((label) => node("th", { scope: "col", textContent: label })));
    const table = node("table", { className: "explorer-coverage-table" }, node("thead", {}, header), tbody);
    byId("catalog-coverage-table").replaceChildren(node("div", { className: "explorer-coverage-scroll" }, table));

    const review = coverage.corl_review;
    const reviewed = byId("corl-source-review");
    reviewed.hidden = !review;
    if (review) {
      const label = Number.isInteger(review.screened_count)
        ? "CoRL source review covered " + review.screened_count + " papers."
        : "CoRL source review";
      const content = [node("h3", { textContent: label })];
      if (review.notes) content.push(node("p", { textContent: review.notes }));
      if (review.added?.length) {
        content.push(node("ul", {},
          ...review.added.map((title) => node("li", { textContent: title }))));
      }
      const source = sourceLink(review.source, "CoRL source list");
      if (source) content.push(node("p", {}, source));
      reviewed.replaceChildren(...content);
    }
  }

  function setOptions(select, values, allLabel, current = select.value) {
    const options = values.map((value) => {
      if (Array.isArray(value)) return new Option(value[1], value[0]);
      return new Option(value, value);
    });
    select.replaceChildren(new Option(allLabel, ""), ...options);
    select.value = options.some((option) => option.value === current) ? current : "";
  }

  function updateVersionAndSuite(version = byId("benchmark").value) {
    const familyTasks = family ? catalog.filter((task) => task.family === family) : catalog;
    const versions = [...new Set(familyTasks.map((task) => task.benchmark))];
    setOptions(byId("benchmark"), versions, "All versions", version);
    const activeVersion = byId("benchmark").value;
    const versionTasks = activeVersion
      ? familyTasks.filter((task) => task.benchmark === activeVersion)
      : familyTasks;
    const suites = [...new Set(versionTasks.map((task) => task.suite).filter(Boolean))].sort();
    const splits = [...new Set(versionTasks.map((task) => task.split).filter(Boolean))];
    setOptions(byId("suite"), [...suites, ...splits.map((split) => ["split:" + split, split + " split"])], "All suites and splits");
  }

  const familyButtons = new Map();
  for (const name of ["", ...families]) {
    const count = node("span", { className: "explorer-count" });
    const button = action(name || "All families", () => {
      family = name;
      byId("suite").value = "";
      updateVersionAndSuite("");
      refresh();
    });
    button.append(count);
    familyButtons.set(name, { button, count });
    byId("family-counts").append(button);
  }

  function refreshFamilyCounts(matches) {
    const counts = new Map(families.map((name) => [name, 0]));
    for (const { task } of matches) counts.set(task.family, (counts.get(task.family) || 0) + 1);
    for (const [name, { button, count }] of familyButtons) {
      const total = name ? counts.get(name) : matches.length;
      count.textContent = total.toLocaleString();
      button.setAttribute("aria-pressed", String(family === name));
      const countLabel = total === 1 ? " matching entry across versions" : " matching entries across versions";
      button.setAttribute("aria-label", (name || "All families") + ", " + total + countLabel);
    }
  }

  function titleFor(task) {
    return task.title || task.name || "Proposed task";
  }

  function taskContext(task) {
    const suiteParts = (task.suite || "").split(" · ");
    const setting = suiteParts.includes(task.setting) ? "" : task.setting;
    return [task.benchmark, task.suite, setting, task.split].filter(Boolean).join(" · ");
  }

  function showMatches(matches) {
    if (!matches?.length) return null;
    const display = node("div", { className: "explorer-matches", ariaLabel: "Search match evidence" });
    display.append(node("strong", { textContent: "Matched" }));
    for (const { term, kind, field, matched } of matches) {
      const evidence = matched && matched.toLowerCase() !== term.toLowerCase() ? term + " → " + matched : term;
      display.append(node("span", { className: "explorer-match" },
        node("b", { textContent: (kind || "Keyword") + " · " }),
        evidence + (field ? " (" + field + ")" : "")));
    }
    return display;
  }

  function scopeLabel(scope) {
    return ({
      benchmark: "Benchmark-level protocol",
      suite: "Suite-level protocol",
      task: "Task-specific description",
    })[scope] || "";
  }

  function describeSetup(task) {
    return node("div", {}, textBlock(task.setup_summary || task.setup),
      sourceLink(task.setup_source, "Setup source"));
  }

  function describeObservation(task) {
    const scope = scopeLabel(task.observation_scope);
    return node("div", {}, textBlock(task.observation),
      scope && task.observation ? node("div", { className: "explorer-scope", textContent: scope }) : null,
      sourceLink(task.observation_source || task.evaluation_source, "Observation protocol"));
  }

  function describeGrading(task) {
    const scope = scopeLabel(task.grading_scope);
    const fields = node("div", {},
      textBlock(task.grading_summary || (task.goal ? "See the published definition below." : "")),
      scope && task.grading_summary ? node("div", { className: "explorer-scope", textContent: scope }) : null,
      sourceLink(task.evaluation_source, "Evaluation protocol"));
    if (task.evaluation_protocol) fields.append(textBlock(task.evaluation_protocol));
    for (const note of [task.source_note, task.catalog_scope].filter(Boolean)) {
      fields.append(node("p", { className: "explorer-scope", textContent: note }));
    }
    if (task.grading_levels?.length) {
      const levels = node("ul", { className: "explorer-grading-levels" });
      for (const level of task.grading_levels) {
        levels.append(node("li", {}, node("strong", { textContent: String(level.score) + " points" }),
          " " + level.description));
      }
      fields.append(node("details", { className: "explorer-definition" },
        node("summary", { textContent: "Score levels" }), levels));
    }
    return fields;
  }

  function rawDefinition(task) {
    if (!task.goal && !task.initial_conditions && !task.guidance && !task.reset) return null;
    const details = node("details", { className: "explorer-definition" },
      node("summary", { textContent: "Published rubric and task definition" }));
    if (task.goal) details.append(node("pre", { textContent: task.goal }));
    if (task.initial_conditions) {
      details.append(node("strong", { textContent: "Initial conditions" }),
        node("pre", { textContent: task.initial_conditions }));
    }
    if (task.guidance) details.append(node("strong", { textContent: "Grader guidance" }), textBlock(task.guidance));
    if (task.reset) details.append(node("strong", { textContent: "Reset procedure" }), textBlock(task.reset));
    return details;
  }

  function videoEmbedUrl(url) {
    const host = url.hostname;
    if (host === "player.vimeo.com" && /^\/video\/\d+\/?$/.test(url.pathname)) return url.href;
    if (host === "vimeo.com" && /^\/\d+\/?$/.test(url.pathname)) return "https://player.vimeo.com/video" + url.pathname;
    if ((host === "www.youtube.com" || host === "youtube.com" || host === "www.youtube-nocookie.com")
      && /^\/embed\/[\w-]{11}\/?$/.test(url.pathname)) {
      return "https://www.youtube-nocookie.com" + url.pathname;
    }
    const id = host === "youtu.be"
      ? url.pathname.slice(1)
      : (host === "www.youtube.com" || host === "youtube.com") && url.pathname === "/watch"
        ? url.searchParams.get("v")
        : "";
    return id && /^[\w-]{11}$/.test(id) ? "https://www.youtube-nocookie.com/embed/" + id : "";
  }

  function mediaElement(type, url, label) {
    if (type === "image") return node("img", { src: url.href, alt: label, loading: "lazy" });
    if (/\.(mp4|webm|ogv)$/i.test(url.pathname)) {
      return node("video", { src: url.href, controls: true, playsInline: true, preload: "metadata", ariaLabel: label });
    }
    const embed = videoEmbedUrl(url);
    return embed
      ? node("iframe", { src: embed, title: label, loading: "lazy", allow: "fullscreen; picture-in-picture", allowFullscreen: true })
      : null;
  }

  function renderMedia(task) {
    const media = node("div", { className: "explorer-media" });
    const embedded = images[task.image];
    if (typeof embedded === "string" && /^data:image\/(png|jpeg|webp);base64,/.test(embedded)) {
      media.append(node("figure", {},
        node("img", { src: embedded, alt: "Official setup for " + titleFor(task), loading: "lazy" }),
        node("figcaption", { textContent: "Official setup photograph" })));
    }
    const entries = [...(task.media || [])];
    if (task.video && !entries.some(({ url }) => url === task.video)) {
      entries.push({ url: task.video, type: "video", label: "Official demonstration" });
    }
    for (const entry of entries) {
      const url = httpsUrl(entry.url);
      if (!url || !["image", "video"].includes(entry.type)) continue;
      const label = entry.label || (entry.type === "image" ? "Official photograph" : "Official demonstration");
      const figure = node("figure", {});
      const scope = ({ variant: " · Example variant", benchmark: " · Benchmark-level example" })[entry.scope] || "";
      const caption = node("figcaption", {}, label + scope,
        node("br"), sourceLink(url.href, "Open original"));
      if (entry.type === "image" || /\.(mp4|webm|ogv)$/i.test(url.pathname) || videoEmbedUrl(url)) {
        const button = action(entry.type === "image" ? "Load image" : "Load video", () => {
          const visual = mediaElement(entry.type, url, label);
          button.replaceWith(visual);
        });
        figure.append(button);
      }
      figure.append(caption);
      media.append(figure);
    }
    const mediaSource = sourceLink(task.media_source, "Official media catalog");
    if (!media.childElementCount && !mediaSource) return null;
    const details = node("details", { className: "explorer-evidence" },
      node("summary", { textContent: "Setup photos and demonstration media" }));
    if (task.media_note) details.append(node("p", { className: "explorer-scope", textContent: task.media_note }));
    if (media.childElementCount) details.append(media);
    if (mediaSource) details.append(node("p", {}, mediaSource));
    return details;
  }

  const evidenceRows = [
    ["Initial setup", describeSetup],
    ["What the robot sees", describeObservation],
    ["What earns credit", describeGrading],
    ["What the grader uses", (task) => textBlock(task.grading_evidence)],
  ];

  function renderEvidence(task) {
    const fields = node("dl", { className: "explorer-evidence-fields" });
    for (const [label, render] of evidenceRows) {
      fields.append(node("dt", { textContent: label }), node("dd", {}, render(task)));
    }
    if (task.objects) fields.append(node("dt", { textContent: "Objects" }), node("dd", {}, textBlock(task.objects)));
    const details = node("details", { className: "explorer-evidence" },
      node("summary", { textContent: "Inspect setup, observations, and grading" }), fields);
    const raw = rawDefinition(task);
    if (raw) details.append(raw);
    const source = sourceLink(task.source, "Published task source");
    if (source) details.append(node("p", {}, source));
    if (task.id) details.append(node("p", { className: "explorer-scope" }, "Task ID ", node("code", { textContent: task.id })));
    return details;
  }

  function updatePinButtons() {
    for (const button of byId("tasks").querySelectorAll(".explorer-pin")) {
      const task = taskById.get(button.dataset.task);
      const pinned = pins.has(task.id);
      button.textContent = pinned ? "Pinned" : "Pin to compare";
      button.setAttribute("aria-pressed", String(pinned));
      button.setAttribute("aria-label", (pinned ? "Unpin " : "Pin ") + titleFor(task) + " for comparison");
    }
  }

  function togglePin(task) {
    if (pins.has(task.id)) {
      pins.delete(task.id);
    } else if (pins.size < maxPins) {
      pins.add(task.id);
    } else {
      byId("pin-status").textContent = "Three tasks are pinned. Remove a task to pin another.";
      return;
    }
    updatePinButtons();
    renderComparison();
  }

  function renderResult({ task, matches }) {
    const pin = action("Pin to compare", () => togglePin(task), "explorer-pin");
    pin.dataset.task = task.id;
    const head = node("div", { className: "explorer-result-head" },
      node("div", {},
        node("span", { className: "explorer-kicker", textContent: taskContext(task) }),
        node("h4", { textContent: titleFor(task) })), pin);
    return node("article", { className: "explorer-result" }, head,
      task.instruction || task.description ? node("p", { textContent: task.instruction || task.description }) : null,
      showMatches(matches),
      renderEvidence(task), renderMedia(task));
  }

  function renderPage() {
    const total = results.length;
    const pages = Math.max(1, Math.ceil(total / pageSize));
    page = Math.min(page, pages - 1);
    const start = page * pageSize;
    const currentPage = results.slice(start, start + pageSize);
    byId("tasks").replaceChildren(...currentPage.map(renderResult));
    if (!total) {
      byId("tasks").append(node("p", {
        className: "explorer-empty",
        textContent: "No matches. Try fewer terms or change a filter.",
      }));
    }
    const entryLabel = total === 1 ? " entry" : " entries";
    byId("result-count").textContent = total
      ? total.toLocaleString() + entryLabel + " · showing " + (start + 1) + "–" + (start + currentPage.length)
      : "0 matching entries";
    byId("page-number").textContent = total ? "Page " + (page + 1) + " of " + pages : "";
    byId("prev").disabled = page === 0;
    byId("next").disabled = page >= pages - 1;
    byId("download").disabled = !total;
    updatePinButtons();
  }

  function proposalValues() {
    return Object.fromEntries(Object.entries(proposalFields).map(([field, id]) => [field, byId(id).value.trim()]));
  }

  function comparisonData() {
    const proposal = proposalValues();
    return {
      proposal: Object.values(proposal).some(Boolean) ? proposal : null,
      entries: [...pins].map((id) => ({ task: taskById.get(id), matches: queryMatches.get(id) || [] })),
    };
  }

  function describeOverlap(task) {
    if (!queryTerms.length) return textBlock("", "Enter a search to see overlapping terms.");
    const matches = queryMatches.get(task.id) || [];
    const matchedTerms = new Set(matches.map(({ term, kind }) => kind + ":" + term));
    const missing = queryTerms.filter(({ term, kind }) => !matchedTerms.has(kind + ":" + term));
    return node("div", {}, showMatches(matches),
      missing.length ? node("p", { className: "explorer-scope" },
        node("strong", { textContent: "Search found no evidence for " }),
        missing.map(({ original }) => original).join(", ") + ".") : null);
  }

  function renderComparison() {
    const { proposal, entries } = comparisonData();
    const comparison = byId("task-comparison");
    comparison.hidden = !(proposal || entries.length);
    byId("jump-to-comparison").hidden = comparison.hidden;
    byId("clear-pins").disabled = !entries.length;
    byId("pin-status").textContent = entries.length ? entries.length + " of " + maxPins + " comparison slots used." : "";
    if (comparison.hidden) {
      byId("comparison-grid").replaceChildren();
      return;
    }

    const columnTasks = proposal ? [proposal, ...entries.map(({ task }) => task)] : entries.map(({ task }) => task);
    const header = node("tr", {}, node("th", { scope: "col", textContent: "Evidence" }));
    for (const task of columnTasks) {
      const isProposal = task === proposal;
      const cell = node("th", { scope: "col", className: isProposal ? "proposal-column" : "" },
        node("span", { className: "explorer-kicker", textContent: isProposal ? "Your proposal" : taskContext(task) }),
        titleFor(task));
      if (!isProposal) {
        cell.append(node("br"), action("Remove", () => {
          togglePin(task);
          (comparison.hidden ? byId("task-results-title") : byId("task-comparison-title")).focus({ preventScroll: true });
        }, "explorer-remove"));
      }
      header.append(cell);
    }

    const rows = [
      ["Robot instruction", (task) => textBlock(task.instruction || task.description)],
      ...evidenceRows,
      ["Search overlap", (task) => task === proposal
        ? textBlock(query, "Enter a query to show matching terms.")
        : describeOverlap(task)],
      ["Source and media", (task) => task === proposal ? textBlock("Your proposal") : node("div", {},
        sourceLink(task.source, "Published task source"), rawDefinition(task), renderMedia(task))],
    ];
    const body = node("tbody");
    for (const [label, render] of rows) {
      body.append(node("tr", {}, node("th", { scope: "row", textContent: label }),
        ...columnTasks.map((task) => node("td", { className: task === proposal ? "proposal-column" : "" }, render(task)))));
    }
    const table = node("table", { className: "explorer-comparison-table" }, node("thead", {}, header), body);
    const scroll = node("div", { className: "explorer-comparison-scroll", tabIndex: 0, ariaLabel: "Scrollable task comparison" }, table);
    byId("comparison-grid").replaceChildren(scroll);
  }

  function refresh() {
    query = byId("search").value.trim();
    page = 0;
    const options = { mode: byId("search-mode").value, setting: byId("task-setting").value };
    const allMatches = TaskSearch.search(index, query, options);
    refreshFamilyCounts(allMatches);
    queryTerms = TaskSearch.describeQuery(index, query, options.mode);
    const comparisonMatches = options.mode === "all" || options.setting
      ? TaskSearch.search(index, query, { mode: options.mode === "exact" ? "exact" : "related" })
      : allMatches;
    queryMatches = new Map(comparisonMatches.map(({ task, matches }) => [task.id, matches]));
    const version = byId("benchmark").value;
    const suite = byId("suite").value;
    results = allMatches.filter(({ task }) => (!family || task.family === family)
      && (!version || task.benchmark === version)
      && (!suite || (suite.startsWith("split:") ? task.split === suite.slice(6) : task.suite === suite)));
    renderPage();
    renderComparison();
  }

  function downloadJson(filename, value) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
    const anchor = node("a", { href: url, download: filename });
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function movePage(direction) {
    page += direction;
    renderPage();
    byId("task-results-title").focus();
  }

  byId("task-search-form").addEventListener("submit", (event) => {
    event.preventDefault();
    refresh();
  });
  byId("search").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      refresh();
    }
  });
  byId("benchmark").addEventListener("change", () => {
    byId("suite").value = "";
    updateVersionAndSuite();
    refresh();
  });
  for (const id of ["suite", "task-setting", "search-mode"]) byId(id).addEventListener("change", refresh);
  byId("prev").addEventListener("click", () => movePage(-1));
  byId("next").addEventListener("click", () => movePage(1));
  byId("download").addEventListener("click", () => downloadJson("robotics-benchmark-matches.json", { query, results }));
  byId("export-comparison").addEventListener("click", () => downloadJson("robotics-task-comparison.json", { query, ...comparisonData() }));
  byId("clear-pins").addEventListener("click", () => {
    pins.clear();
    updatePinButtons();
    renderComparison();
    byId("task-results-title").focus({ preventScroll: true });
  });
  byId("proposal-form").addEventListener("change", renderComparison);
  byId("proposal-form").addEventListener("reset", () => setTimeout(renderComparison, 0));
  byId("proposal-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const proposal = proposalValues();
    byId("search").value = [proposal.title, proposal.description, proposal.grading_summary].filter(Boolean).join(" ").slice(0, 1000);
    refresh();
  });
  byId("use-current-query").addEventListener("click", () => {
    byId("proposal-description").value = byId("search").value.trim();
    renderComparison();
  });
  for (const button of document.querySelectorAll("[data-query]")) {
    button.addEventListener("click", () => {
      byId("search").value = button.dataset.query;
      refresh();
    });
  }
  for (const link of document.querySelectorAll("[data-filter]")) {
    link.addEventListener("click", () => {
      family = "";
      byId("search").value = "";
      byId("suite").value = "";
      byId("task-setting").value = "";
      updateVersionAndSuite(link.dataset.filter);
      refresh();
    });
  }
  for (const button of document.querySelectorAll(".video-box button")) {
    button.addEventListener("click", () => {
      const url = httpsUrl(button.parentElement.dataset.video);
      if (!url) return;
      const player = mediaElement("video", url, "Official benchmark demonstration");
      if (player) button.replaceWith(player);
    });
  }

  setOptions(byId("task-setting"), [...new Set(catalog.map((task) => task.setting).filter(Boolean))].sort(), "All settings");
  renderCoverage();
  updateVersionAndSuite();
  refresh();
})();

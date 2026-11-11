/* =====================================================
   js/registry.js — collects what the config files define
   =====================================================
   Loaded before anything in config/. Provides:
     defineSkills({ skills, challenge })          config/skills.js
     defineTaskList([...file names])              config/tasks/index.js
     defineTask({ ...task })                      config/tasks/*.js
     defineRollouts({ dir, methods, tasks, episodes, demoDir, demos, clipDir, challenges })  config/rollouts.js
     defineSim({ dir, clips })                    config/sim.js
     defineAssetPage({ dir, colors, assets })     config/asset-page.js
   Also used by tools/check.mjs, so it must not rely on the DOM.
   ===================================================== */

(function (g) {
  const PAGE = g.PAGE = g.PAGE || {
    skills: [], challenge: null, defaultRepresentative: 2,
    taskFiles: [], tasks: [], rollouts: null, sim: null, assetPage: null, errors: []
  };

  g.defineSkills = function (cfg) {
    if (Array.isArray(cfg)) cfg = { skills: cfg };
    PAGE.skills = (cfg && cfg.skills) || [];
    if (cfg && typeof cfg.defaultRepresentative === 'number') PAGE.defaultRepresentative = cfg.defaultRepresentative;
    PAGE.challenge = (cfg && cfg.challenge) || null;
  };

  g.defineTaskList = function (files) {
    PAGE.taskFiles = (files || []).map(f => String(f).replace(/\.js$/, ''));
  };

  g.defineTask = function (task) {
    const cur = typeof document !== 'undefined' ? document.currentScript : null;
    const file = (cur && cur.getAttribute('src')) || g.__currentTaskFile || '';
    PAGE.tasks.push(Object.assign({}, task, { __file: file }));
  };

  g.defineRollouts = function (cfg) {
    PAGE.rollouts = cfg || null;
  };

  g.defineSim = function (cfg) {
    PAGE.sim = cfg || null;
  };

  g.defineAssetPage = function (cfg) {
    PAGE.assetPage = cfg || null;
  };
})(typeof window !== 'undefined' ? window : globalThis);

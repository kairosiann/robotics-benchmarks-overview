// 23 · Plug in charger
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '23',
  name: 'Plug in charger',
  skills: ['insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'plug_in_charger.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'An outlet is placed in the workspace. Fully insert the charger held in hand into the outlet.',
  success: 'The charger is fully inserted into the outlet, such that it does not noticeably move when further pushed toward the outlet. The robot movement stops after terminating the insertion motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'plug_in_charger.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['charging-block-1', 'charging-block-2', 'charging-block-3', 'charging-block-4', 'charging-block-5', 'outlet'],
});

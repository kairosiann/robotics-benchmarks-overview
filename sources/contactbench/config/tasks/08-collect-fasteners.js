// 08 · Collect fasteners
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '08',
  name: 'Collect fasteners',
  skills: ['multi', 'place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'collect_fasteners.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Collect all fasteners scattered across the workspace and place them into the storage bin. Being able to hold multiple fasteners simultaneously will greatly increase task completion efficiency.',
  success: 'The robot movement stops after placing all fasteners inside the storage bin. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'collect_nuts.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['fastener-bin', 'screw', 'bolt', 'nut'],
});

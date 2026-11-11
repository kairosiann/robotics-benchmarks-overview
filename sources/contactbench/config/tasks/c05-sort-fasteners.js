// C05 · Sort fasteners
// Every option is explained in config/tasks/_challenge-template.js.

defineTask({
  id: 'C05',
  challenge: true,         // listed under Dexterous Long-Horizon Tasks
  name: 'Sort fasteners',
  skills: ['thin', 'multi', 'clutter', 'place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'sort_fasteners.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A tight pile of mixed fasteners is placed in the workspace or a storage bin in the workspace. Sort the fasteners and place different types of fasteners into their corresponding storage bins. Being able to hold multiple fasteners simultaneously will greatly increase task completion efficiency.',
  success: 'The robot movement stops after sorting every fastener in the pile into its corresponding bin. Only fasteners of the same type should be in the same bin. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'sort_screws_and_nuts.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['screw', 'nut', 'bolt', 'fastener-bin'],
});

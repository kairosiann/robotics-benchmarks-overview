// 25 · Stack cups
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '25',
  name: 'Stack cups',
  skills: ['place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'stack_cups.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Multiple cups are scattered around the workspace. Collect the cups and place them inside one another to form a tight stack.',
  success: 'The robot movement stops after all cups form a tight, upright stack (not knocked over). The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'stack_cups.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['cup'],
});

// 19 · Put bottle cap onto bottle
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '19',
  name: 'Put bottle cap onto bottle',
  skills: ['insert', 'artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'put_bottle_cap_onto_bottle.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A bottle without a cap is placed in the workspace. Screw the bottle cap held in hand onto the bottle and tighten it.',
  success: 'The bottle cap is tightened and remains stationary when a small force is applied in an attempt to rotate the cap. The robot movement stops after terminating the tightening motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'put_bottle_cap_onto_bottle.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['bottle-1', 'bottle-2', 'bottle-3'],
});

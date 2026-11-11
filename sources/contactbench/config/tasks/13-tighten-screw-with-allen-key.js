// 13 · Tighten screw with Allen key
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '13',
  name: 'Tighten screw with Allen key',
  skills: ['extrinsic', 'insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'tighten_screw_with_allen_key.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A screw is placed into the screw slot of an assembly block in the workspace, but the threads are unengaged. Use the Allen key grasped in hand to tighten the screw.',
  success: 'The screw is tightened and remains stationary when a small force is applied in an attempt to rotate the screw. The robot movement stops after terminating the tightening motion, moving away from, and breaking contact with the screw.',

  // ---- Base task ----
  video: 'tighten_screw_with_allen_key.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['allen-key', 'toy-assembly-block', 'nut', 'screw'],
});

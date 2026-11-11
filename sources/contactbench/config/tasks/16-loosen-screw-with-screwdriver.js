// 16 · Loosen screw with screwdriver
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '16',
  name: 'Loosen screw with screwdriver',
  skills: ['extrinsic', 'insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'loosen_screw_with_screwdriver.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A screw is placed into the screw slot of an assembly block in the workspace and is fully tightened. Use the screwdriver grasped in hand to loosen the screw.',
  success: 'The screw is loosened and can rotate freely when a small force is applied in an attempt to rotate the screw. The robot movement stops after terminating the loosening motion, moving away from, and breaking contact with the screw.',

  // ---- Base task ----
  video: 'loosen_screw_with_screwdriver.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['screwdriver', 'toy-assembly-block', 'nut', 'screw'],
});

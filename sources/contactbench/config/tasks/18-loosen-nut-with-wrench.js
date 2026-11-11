// 18 · Loosen nut with wrench
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '18',
  name: 'Loosen nut with wrench',
  skills: ['extrinsic', 'insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'loosen_nut_with_wrench.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A nut is threaded onto a screw head in the workspace and is fully tightened. Use the wrench grasped in hand to loosen the nut.',
  success: 'The nut is loosened and can rotate freely when a small force is applied in an attempt to rotate the nut. The robot movement stops after terminating the loosening motion, moving away from, and breaking contact with the nut.',

  // ---- Base task ----
  video: 'loosen_nut_with_wrench.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['wrench', 'toy-assembly-block', 'nut', 'bolt'],
});

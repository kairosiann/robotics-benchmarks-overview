// 32 · Install light bulb
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '32',
  name: 'Install light bulb',
  skills: ['insert', 'artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'install_lightbulb.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A light bulb socket is placed in the workspace. Screw the light bulb held in hand into the socket and tighten it.',
  success: 'The light bulb is tightened and remains stationary when a small force is applied in an attempt to rotate it. The robot movement stops after terminating the tightening motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'install_lightbulb.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['lightbulb-1', 'lightbulb-2', 'lightbulb-3', 'lightbulb-slot'],
});

// 26 · Plug in Ethernet
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '26',
  name: 'Plug in Ethernet',
  skills: ['insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'plug_in_ethernet.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Fully insert the Ethernet plug held in hand into a socket placed in the workspace.',
  success: 'The Ethernet plug is fully inserted into the socket with its latch engaged, such that the plug can’t be withdrawn by a light pull. The robot movement stops after terminating the insertion motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'plug_in_ethernet.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['ethernet-plug-and-slot'],
});

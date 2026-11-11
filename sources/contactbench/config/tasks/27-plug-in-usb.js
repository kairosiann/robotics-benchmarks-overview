// 27 · Plug in USB
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '27',
  name: 'Plug in USB',
  skills: ['insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'plug_in_usb.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Fully insert the USB stick held in hand into the USB slot placed in the workspace.',
  success: 'The USB stick is fully inserted into the slot, such that it does not noticeably move when further pushed toward the slot. The robot movement stops after terminating the insertion motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'plug_in_usb.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['usb-stick-1', 'usb-stick-2', 'usb-stick-3', 'usb-stick-4', 'usb-slot'],
});

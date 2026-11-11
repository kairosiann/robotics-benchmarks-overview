// 30 · Turn door handle to open door
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '30',
  name: 'Turn door handle to open door',
  skills: ['artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'turn_door_handle_to_open_door.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Turn the door handle fully to unlock the door, then open the door.',
  success: 'The door is opened by at least 5 degrees, such that it is visually obvious that the door has been unlocked.',

  // ---- Base task ----
  video: 'turn_door_handle_to_open_door.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['lock-module', 'doorknob-module', 'door'],
});

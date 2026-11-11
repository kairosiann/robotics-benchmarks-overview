// 28 · Turn key to unlock door
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '28',
  name: 'Turn key to unlock door',
  skills: ['artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'turn_key_to_unlock_door.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A locked door module is placed in the workspace with a key already inserted into the lock. Turn the key to unlock the door.',
  success: 'The key is fully turned such that the door can be opened. The robot movement stops after terminating the rotation motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'turn_key_to_unlock_door.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['lock-module', 'key-1', 'doorknob-module', 'door'],
});

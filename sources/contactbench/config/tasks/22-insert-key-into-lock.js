// 22 · Insert key into lock
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '22',
  name: 'Insert key into lock',
  skills: ['insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'insert_key_into_lock.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A lock is placed in the workspace. Insert the key held in hand into the lock.',
  success: 'The key is inserted into the lock. The robot movement stops after terminating the insertion motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'insert_key_into_lock.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['lock-module', 'key-1', 'doorknob-module', 'door'],
});

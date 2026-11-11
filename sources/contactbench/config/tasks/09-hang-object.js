// 09 · Hang object
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '09',
  name: 'Hang object',
  skills: ['place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'hang_object.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Hang the object in-hand onto an empty hanging board hook.',
  success: 'The robot movement stops after placing the target object onto a hanging hook. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'hang_wrench.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['key-1', 'key-2', 'key-3', 'key-fob', 'keyring', 'wrench', 'ruler', 'hanging-board'],
});

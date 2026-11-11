// 01 · Grasp target key from keychain
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '01',
  name: 'Grasp target key from keychain',
  skills: ['clutter', 'thin'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'grasp_target_key_from_keychain.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'For a keychain in the workspace with multiple keys, find and singulate the specified target key among all keys on the keychain.',
  success: 'The robot movement stops with only the specified target key stably grasped within the robot end-effector.',

  // ---- Base task ----
  video: 'grasp_target_key_from_keychain.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['key-1', 'key-2', 'key-3', 'key-fob', 'keyring'],
});

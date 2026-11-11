// C03 · Unlock and open door
// Every option is explained in config/tasks/_challenge-template.js.

defineTask({
  id: 'C03',
  challenge: true,         // listed under Dexterous Long-Horizon Tasks
  name: 'Unlock and open door',
  skills: ['thin', 'clutter', 'inhand', 'insert', 'artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'unlock_and_open_door_sequence.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A set of keys on a hanging board and a locked door are placed in the workspace. Retrieve the keys from the hanging board, use the correct key to unlock the door, then turn the doorknob to open the door.',
  success: 'The door is opened by at least 5 degrees, such that it is visually obvious that the door has been unlocked.',

  // ---- Base task ----
  video: 'unlock_and_open_door_sequence.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['key-1', 'key-2', 'key-3', 'key-fob', 'keyring', 'hanging-board', 'lock-module', 'doorknob-module', 'door'],
});

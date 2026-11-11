// C02 · Add keys to keyring
// Every option is explained in config/tasks/_challenge-template.js.

defineTask({
  id: 'C02',
  challenge: true,         // listed under Dexterous Long-Horizon Tasks
  name: 'Add keys to keyring',
  skills: ['thin', 'insert'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'put_keys_onto_keyring.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A keyring and several keys are scattered around the workspace. Add all loose keys onto the keyring.',
  success: 'The robot movement stops after adding all loose keys to the keyring and placing the chained keys onto the table. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'add_keys_to_keyring.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['key-1', 'key-2', 'key-3', 'key-fob', 'keyring'],
});

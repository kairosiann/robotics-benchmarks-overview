// C04 · Sort utensils
// Every option is explained in config/tasks/_challenge-template.js.

defineTask({
  id: 'C04',
  challenge: true,         // listed under Dexterous Long-Horizon Tasks
  name: 'Sort utensils',
  skills: ['thin', 'multi', 'clutter', 'place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'sort_utensils.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A tight pile of mixed utensils is placed in the workspace or a storage bin in the workspace. Sort the utensils and place different types of utensils into their corresponding storage bins. Being able to hold multiple utensils simultaneously will greatly increase task completion efficiency.',
  success: 'The robot movement stops after sorting every utensil in the pile into its corresponding bin. Only utensils of the same type should be in the same bin. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'sort_utensils.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['chopstick', 'fork', 'knife', 'spoon', 'utensil-bin-horizontal', 'utensil-bin-vertical'],
});

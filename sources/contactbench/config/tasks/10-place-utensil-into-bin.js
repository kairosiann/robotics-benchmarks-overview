// 10 · Place utensil into bin
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '10',
  name: 'Place utensil into bin',
  skills: ['place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'place_utensil_into_bin.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A utensil bin with utensils already stored in it is placed in the workspace. Starting with a utensil held in hand, find an open pocket in the cluttered utensil storage bin and place the held utensil in it.',
  success: 'The robot movement stops after placing the target object into the storage bin. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'place_fork_into_bin.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['chopstick', 'fork', 'knife', 'spoon', 'utensil-bin-horizontal', 'utensil-bin-vertical'],
});

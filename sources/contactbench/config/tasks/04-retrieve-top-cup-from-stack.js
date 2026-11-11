// 04 · Retrieve top cup from stack
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '04',
  name: 'Retrieve top cup from stack',
  skills: ['clutter'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'retrieve_top_cup_from_stack.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A neatly organized stack of cups is placed in the workspace. Pick up the top cup from the stack and place it on the table without disturbing the rest of the stack.',
  success: 'The robot movement stops after separating the top cup from the stack and placing it on the table. The remaining cups should remain in a neat stack. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'retrieve_top_cup_from_stack.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['cup'],
});

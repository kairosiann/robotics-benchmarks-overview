// 21 · Thread nut onto screw
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '21',
  name: 'Thread nut onto screw',
  skills: ['insert', 'artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'thread_nut_onto_screw.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Screw the nut held in hand onto the screw head placed in the workspace such that their threads fully engage.',
  success: 'The nut and screw threads engage. The robot movement stops after terminating the rotation motion, moving away from, and breaking contact with the task objects.',

  // ---- Base task ----
  video: 'thread_nut_onto_screw.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['toy-assembly-block', 'nut', 'bolt'],
});

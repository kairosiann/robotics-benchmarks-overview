// 03 · Retrieve single fastener from bin
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '03',
  name: 'Retrieve single fastener from bin',
  skills: ['clutter', 'thin'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'retrieve_single_fastener_from_bin.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A fastener storage bin is placed in the workspace. The target fastener is placed in the bin alongside multiple other fasteners. Pick up a single copy of the target fastener from the cluttered storage bin and place it on the table without removing other objects from the bin.',
  success: 'The robot movement stops after separating a single copy of the target fastener and placing it on the table. Other fasteners should remain in the storage bin. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'retrieve_single_screw_from_bin.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['fastener-bin', 'screw', 'bolt', 'nut'],

  // ---- Video variants (more videos, shown in the card's player) ----
  variations: [
    // {
    //   axis: 'Object type',
    //   type: 'visual+behavioral',
    //   instances: [
    //     { label: 'Screw', video: 'retrieve_single_screw_from_bin.mp4' },
    //   ],
    // },
  ],
});

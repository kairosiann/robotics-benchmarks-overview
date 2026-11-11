// C01 · Assemble toy block
// Every option is explained in config/tasks/_challenge-template.js.

defineTask({
  id: 'C01',
  challenge: true,         // listed under Dexterous Long-Horizon Tasks
  name: 'Assemble toy block',
  skills: ['thin', 'clutter', 'inhand', 'insert', 'extrinsic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'assemble_toy_block.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Components of the block to be assembled, required tools, and bins of screws and nuts are placed in the workspace. Using the tools available, assemble the two halves of the block together with two screws and two nuts.',
  success: 'The robot movement stops after fully assembling the block with screws tightened and placing the assembled block onto the table. The robot should not remain in contact with the block.',

  // ---- Base task ----
  video: 'assemble_toy_block.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['toy-assembly-block', 'fastener-bin', 'screw', 'nut', 'bolt', 'allen-key', 'screwdriver', 'wrench'],
});

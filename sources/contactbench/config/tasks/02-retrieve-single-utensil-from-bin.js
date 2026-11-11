// 02 · Retrieve single utensil from bin
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '02',
  name: 'Retrieve single utensil from bin',
  skills: ['clutter', 'thin'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'retrieve_single_utensil_from_bin.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A utensil storage bin is placed in the workspace. The target utensil is placed in the bin alongside multiple other utensils. Pick up a single copy of the target utensil from the cluttered storage bin and place it on the table without removing other objects from the bin.',
  success: 'The robot movement stops after separating a single copy of the target utensil and placing it on the table. Other utensils should remain in the storage bin. The robot should not remain in contact with the task objects.',

  // ---- No base task: the video variants below are the task's videos ----
  base: false,

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['chopstick', 'fork', 'knife', 'spoon', 'utensil-bin-horizontal', 'utensil-bin-vertical'],

  // ---- Video variants (more videos, shown in the card's player) ----
  variations: [
    {
      axis: 'Scene arrangement',
      type: 'visual+behavioral',
      instances: [
        { label: 'Chopsticks in horizontal bin', video: 'retrieve_single_chopstick_from_bin_2.mp4' },
        { label: 'Chopsticks in vertical bin', video: 'retrieve_single_chopstick_from_bin.mp4' },
        { label: 'Mixed utensils in vertical bin', video: 'retrieve_single_spoon_from_bin.mp4' },
      ],
    },
  ],
});

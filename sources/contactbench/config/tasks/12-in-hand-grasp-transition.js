// 12 · In-hand grasp transition
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '12',
  name: 'In-hand grasp transition',
  skills: ['inhand'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'in_hand_grasp_transition.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Manipulate the target object in-hand, such that it ends up with the desired grasp type (see grasp types defined in the Grasp Taxonomy).',
  success: 'The target object pose converges and stabilizes with the desired grasp type, and remains within the robot end-effector throughout the execution without being dropped.',

  // ---- No base task: the video variants below are the task's videos ----
  base: false,

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['chopstick', 'fork', 'knife', 'spoon', 'allen-key', 'screwdriver', 'wrench'],

  // ---- Video variants (more videos, shown in the card's player) ----
  variations: [
    {
      axis: 'Object type',
      type: 'visual+behavioral',
      instances: [
        { label: 'Allen key', video: 'in_hand_grasp_transition_allen_key.mp4' },
        { label: 'Screwdriver', video: 'in_hand_grasp_transition_screwdriver.mp4' },
        { label: 'Wrench', video: 'in_hand_grasp_transition_wrench.mp4' },
      ],
    },
  ],
});

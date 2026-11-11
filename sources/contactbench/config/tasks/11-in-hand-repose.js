// 11 · In-hand repose
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '11',
  name: 'In-hand repose',
  skills: ['inhand'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'in_hand_repose.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Manipulate the target object in-hand, such that it ends up in the desired pose relative to the hand. Examples include flipping the orientation of a key or a USB stick to align with the slot.',
  success: 'The target object pose converges and stabilizes to the desired pose, and remains within the robot end-effector throughout the execution without being dropped.',

  // ---- No base task: the video variants below are the task's videos ----
  base: false,

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['chopstick', 'fork', 'knife', 'spoon', 'key-1', 'key-2', 'key-3', 'card', 'allen-key', 'screwdriver', 'wrench', 'usb-stick-1', 'usb-stick-2', 'usb-stick-3', 'usb-stick-4', 'screw', 'bolt'],

  // ---- Video variants (more videos, shown in the card's player) ----
  variations: [
    {
      axis: 'Object type',
      type: 'visual+behavioral',
      instances: [
        { label: 'Key 1', video: 'in_hand_repose_key_2.mp4' },
        { label: 'USB', video: 'in_hand_repose_usb.mp4' },
        { label: 'Screw', video: 'in_hand_repose_screw.mp4' },
      ],
    },
  ],
});

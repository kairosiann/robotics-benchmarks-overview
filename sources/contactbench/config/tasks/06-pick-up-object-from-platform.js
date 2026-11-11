// 06 · Pick up object from platform
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '06',
  name: 'Pick up object from platform',
  skills: ['thin'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'pick_up_object_from_platform.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Pick up the thin and/or small object placed on the flat platform.',
  success: 'The target object is stably grasped by the robot and lifted off the platform.',

  // ---- No base task: the video variants below are the task's videos ----
  base: false,

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['platform', 'key-1', 'key-2', 'key-3', 'key-fob', 'keyring', 'screw', 'bolt', 'nut', 'chopstick', 'knife', 'ruler', 'allen-key', 'card'],

  // ---- Video variants (more videos, shown in the card's player) ----
  variations: [
    {
      axis: 'Object type',
      type: 'visual+behavioral',
      instances: [
        { label: 'Card', video: 'pick_up_card_from_platform.mp4' },
        { label: 'Ruler', video: 'pick_up_ruler_from_platform.mp4' },
        { label: 'Key 1', video: 'pick_up_key_from_platform.mp4' },
        { label: 'Nut', video: 'pick_up_nut_from_platform.mp4' },
        { label: 'Allen key', video: 'pick_up_allen_key_from_platform.mp4' },
      ],
    },
  ],
});

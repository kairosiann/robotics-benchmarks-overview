// 31 · Turn dial to target position
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '31',
  name: 'Turn dial to target position',
  skills: ['artic'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'turn_dial_to_target_position.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'Operate the dial to turn it to the specified target position.',
  success: 'The dial is turned to the target position. For dials that can be turned continuously, the final position should be within half a tick interval from the target position. The robot movement stops after terminating the rotation motion, moving away from, and breaking contact with the task objects.',

  // ---- No base task: the video variants below are the task's videos ----
  base: false,

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['dial', 'dial-push-down-to-turn', 'dial-snap-to-position'],

  // ---- Video variants (more videos, shown in the card's player) ----
  variations: [
    {
      axis: 'Object type',
      type: 'behavioral',
      instances: [
        { label: 'Standard continuous dial', video: '' },
        { label: 'Continuous dial that requires pressing down to turn', video: 'turn_dial_to_target_position_press_down.mp4' },
      ],
    },
    {
      axis: 'Object type',
      type: 'visual+behavioral',
      instances: [
        { label: 'Snap-to-position dial', video: 'turn_dial_to_target_position_snap.mp4' },
      ],
    },
  ],
});

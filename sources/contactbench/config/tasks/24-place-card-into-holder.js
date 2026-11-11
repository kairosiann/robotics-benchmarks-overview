// 24 · Place card into holder
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '24',
  name: 'Place card into holder',
  skills: ['place'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'place_card_into_holder.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A card holder that already contains other cards is placed in the workspace. Place the card held in hand into the card holder.',
  success: 'The robot movement stops after placing the card in the card holder, with existing cards remaining in the card holder. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'place_card_into_deck.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['card', 'card-holder'],
});

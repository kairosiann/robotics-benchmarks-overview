// 05 · Retrieve single card from deck
// Every option is explained in config/tasks/_template.js.

defineTask({
  id: '05',
  name: 'Retrieve single card from deck',
  skills: ['clutter', 'thin'],

  // ---- Card (main page and All tasks page) ----
  thumbnail: 'retrieve_single_card_from_deck.png', // 16:9 landscape image in website_assets/images/thumbnails/

  // ---- Task specs (paragraphs; [brackets] mark text still to decide) ----
  description: 'A neatly organized deck of cards is placed in a cardholder in the workspace. Pick up a single card and place it on the table without disrupting the rest of the card deck.',
  success: 'The robot movement stops after separating a single card from the deck and placing it on the table. The remaining cards should remain a neat deck in the cardholder. The robot should not remain in contact with the task objects.',

  // ---- Base task ----
  video: 'retrieve_single_card_from_deck.mp4', // in website_assets/videos/tasks/; plays when the card's thumbnail is clicked

  // ---- Assets (keys from config/asset-page.js; their cards show in the card's panel) ----
  // [name]: an asset not on the All assets page yet ("More assets will be added soon.")
  assetCards: ['card', 'card-holder'],
});

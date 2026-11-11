# Policy Videos

```{raw} html
<style>
.policy-video-browser {
  border: 1px solid #d0d7de;
  border-radius: 10px;
  padding: 1rem;
  margin: 1rem 0 1.25rem 0;
}

.policy-controls {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  align-items: end;
}

.policy-widget-instructions {
  margin: 0 0 0.9rem 0;
  padding: 0.75rem 0.9rem;
  background: #f6f8fa;
  border: 1px solid #d8dee4;
  border-radius: 8px;
}

.policy-widget-instructions strong {
  display: inline-block;
  margin-bottom: 0.35rem;
}

.policy-widget-instructions ol {
  margin: 0;
  padding-left: 1.1rem;
}

.policy-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.policy-field label {
  font-weight: 600;
}

.policy-field select {
  min-height: 2.25rem;
  border-radius: 8px;
  border: 1px solid #b6c1cd;
  padding: 0.4rem 0.6rem;
  font-size: 0.95rem;
}

.policy-selection-summary {
  margin-top: 0.9rem;
  font-size: 0.95rem;
}

.policy-video-frame {
  position: relative;
  margin-top: 0.8rem;
  width: min(100%, 240px);
  margin-left: auto;
  margin-right: auto;
}

#policy-rollout-video {
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #0f1720;
  border-radius: 10px;
  display: block;
}

.policy-video-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  text-align: center;
  color: #e6edf3;
  background: linear-gradient(135deg, rgba(24, 34, 45, 0.85), rgba(13, 22, 33, 0.85));
  border-radius: 10px;
  font-weight: 600;
  pointer-events: none;
}

.policy-video-note {
  margin-top: 0.6rem;
  color: #57606a;
  font-size: 0.9rem;
}
</style>

<div class="policy-video-browser">
  <div class="policy-widget-instructions">
    <strong>Quick Instructions</strong>
    <p>Select an evaluation suite, task, and model to load the corresponding video.</p>
  </div>

  <div class="policy-controls">
    <div class="policy-field">
      <label for="task-suite-select">Evaluation suite</label>
      <select id="task-suite-select"></select>
    </div>
    <div class="policy-field">
      <label for="task-select">Task</label>
      <select id="task-select"></select>
    </div>
    <div class="policy-field">
      <label for="algorithm-select">Model</label>
      <select id="algorithm-select"></select>
    </div>
  </div>

  <div id="policy-selection-summary" class="policy-selection-summary">
    Selected: MESA-70 / Put the avocado in the basket / PI0
  </div>

  <div class="policy-video-frame">
    <video id="policy-rollout-video" controls preload="metadata" playsinline>
      Your browser does not support the video tag.
    </video>
    <div id="policy-video-empty" class="policy-video-empty">
      No video mapped yet for this selection.
    </div>
  </div>
</div>

<script>
(function () {
  const suiteOptions = {
    "mesa-70": { label: "MESA-70" },
    "mesa-category": { label: "MESA-Category" },
    "mesa-composite": { label: "MESA-Composite" },
    "mesa-instance": { label: "MESA-Instance" },
    "mesa-spatial": { label: "MESA-Spatial" }
  };

  const taskCatalogBySuite = {
    "mesa-70": [
      "apple_tray_on",
      "avocado_basket_contain_region",
      "bagel_cutting_board_on",
      "bar_cabinet_bottom_region_and_close",
      "bar_soap_cabinet_top_region_and_close",
      "beer_slide_cabinet_contain_region_and_close",
      "bell_pepper_sliding_top_box_contain_region_and_close",
      "bottled_water_tray_on",
      "bowl_microwave_heating_region_and_close",
      "broccoli_pan_on",
      "candle_tray_on",
      "carrot_bowl_on",
      "cheese_plate_on",
      "corn_cutting_board_on",
      "croissant_slide_cabinet_contain_region_and_close",
      "cucumber_cabinet_bottom_region_and_close",
      "cup_bowl_drainer_right_region",
      "egg_bowl_on",
      "eggplant_cutting_board_on",
      "fish_pan_on",
      "fish_plate_on",
      "garlic_cabinet_middle_region_and_close",
      "garlic_pan_on",
      "jam_basket_contain_region",
      "jug_basket_contain_region",
      "kiwi_cabinet_top_region_and_close",
      "lemon_plate_on",
      "lime_bowl_on",
      "mango_sliding_top_box_contain_region_and_close",
      "mug_bowl_drainer_left_region",
      "mushroom_bowl_on",
      "onion_tray_on",
      "open_and_avocado_cabinet_top_region",
      "open_and_book_slide_cabinet_contain_region",
      "open_and_broccoli_cabinet_bottom_region",
      "open_and_can_sliding_top_box_contain_region",
      "open_and_candle_slide_cabinet_contain_region",
      "open_and_canned_food_microwave_heating_region",
      "open_and_carrot_cabinet_top_region",
      "open_and_cheese_sliding_top_box_contain_region",
      "open_and_eggplant_microwave_heating_region",
      "open_and_lemon_cabinet_middle_region",
      "open_and_mushroom_cabinet_bottom_region",
      "open_and_onion_cabinet_middle_region",
      "open_and_peach_cabinet_top_region",
      "open_and_squash_microwave_heating_region",
      "open_and_tomato_slide_cabinet_contain_region",
      "open_and_water_bottle_slide_cabinet_contain_region",
      "open_and_wine_slide_cabinet_contain_region",
      "orange_cutting_board_on",
      "orange_plate_on",
      "peach_basket_contain_region",
      "peach_cutting_board_on",
      "peach_tray_on",
      "plate_bowl_drainer_left_region",
      "potato_microwave_heating_region_and_close",
      "rolling_pin_bowl_drainer_right_region",
      "rolling_pin_pan_on",
      "rolling_pin_tray_on",
      "sponge_cabinet_middle_region_and_close",
      "squash_pan_on",
      "squash_tray_on",
      "tomato_cutting_board_on",
      "tomato_pan_on",
      "tomato_tray_on",
      "water_bottle_basket_contain_region",
      "water_bottle_tray_on",
      "wine_sliding_top_box_contain_region",
      "wine_tray_on",
      "yogurt_basket_contain_region"
    ],
    "mesa-category": [
      "beet_ai_pot_on",
      "brussel_sprout_ai_pan_on",
      "chili_pepper_ai_bowl_on",
      "cupcake_basket_contain_region",
      "ginger_ai_cutting_board_on",
      "grapes_ai_basket_contain_region",
      "ice_cream_ai_bowl_on",
      "kebabs_ai_pan_on",
      "olive_oil_bottle_ai_basket_contain_region",
      "pear_pot_on",
      "pomegranate_ai_cabinet_top_region",
      "potato_baking_sheet_ai_on",
      "radish_ai_cutting_board_on",
      "raspberry_ai_basket_contain_region",
      "salt_shaker_sliding_top_box_contain_region_and_close",
      "sausage_ai_baking_sheet_ai_on",
      "scone_ai_plate_on",
      "strawberry_ai_bowl_on",
      "sushi_ai_plate_on",
      "thermos_ai_slide_cabinet_contain_region"
    ],
    "mesa-composite": [
      "apple_plate_on",
      "broccoli_mushroom_cutting_board_on",
      "carrot_pan_on",
      "cheese_basket_contain_region",
      "cheese_mug_tray_on",
      "cup_bowl_drainer_left_region",
      "fish_garlic_pan_on",
      "lemon_cutting_board_on",
      "lemon_lime_basket_contain_region",
      "mushroom_tray_on",
      "onion_bowl_on",
      "open_and_apple_cabinet_middle_region",
      "open_and_apple_sliding_top_box_contain_region_and_close",
      "open_and_beer_sliding_top_box_contain_region",
      "open_and_broccoli_cabinet_middle_region",
      "open_and_carrot_cabinet_top_region_and_close",
      "open_and_jam_slide_cabinet_contain_region",
      "open_and_mushroom_cabinet_middle_region_and_close",
      "open_and_potato_microwave_heating_region_and_close",
      "sponge_bowl_drainer_right_region"
    ],
    "mesa-instance": [
      "apple_ai_tray_ai_on",
      "beer_ai_slide_cabinet_contain_region_and_close",
      "bell_pepper_ai_sliding_top_box_contain_region_and_close",
      "cheese_ai_plate_ai_on",
      "fish_ai_pan_ai_on",
      "jam_ai_basket_contain_region",
      "mushroom_ai_bowl_on",
      "open_and_carrot_ai_cabinet_top_region",
      "open_and_peach_ood_cabinet_top_region",
      "open_and_squash_ood_microwave_heating_region",
      "open_and_wine_ood_slide_cabinet_contain_region",
      "orange_ai_plate_ai_on",
      "peach_ood_basket_contain_region",
      "peach_ood_cutting_board_ai_on",
      "peach_ood_tray_ai_on",
      "potato_ai_microwave_heating_region_and_close",
      "squash_ood_pan_ai_on",
      "squash_ood_tray_ai_on",
      "wine_ood_sliding_top_box_contain_region",
      "wine_ood_tray_ai_on"
    ],
    "mesa-spatial": [
      "open_and_tomato_ood_slide_cabinet_contain_region",
      "open_and_water_bottle_ood_slide_cabinet_contain_region",
      "rolling_pin_ood_bowl_drainer_right_region",
      "rolling_pin_ood_pan_on",
      "rolling_pin_ood_tray_on",
      "tomato_ood_cutting_board_on",
      "tomato_ood_pan_on",
      "tomato_ood_tray_on",
      "water_bottle_ood_basket_contain_region",
      "water_bottle_ood_tray_on"
    ]
  };

  const modelOptions = {
    "dp": { label: "Diffusion Policy" },
    "gr00t": { label: "GR00T-N1.6" },
    "pg_full": { label: "Paligemma + Flow Matching" },
    "pi0": { label: "π0" },
    "pi0_fast": { label: "π0-Fast" },
    "pi05": { label: "π0.5" }
  };

  const defaultSelection = {
    suite: "mesa-70",
    task: "avocado_basket_contain_region",
    algorithm: "pi0"
  };

  const suiteSelect = document.getElementById("task-suite-select");
  const taskSelect = document.getElementById("task-select");
  const algorithmSelect = document.getElementById("algorithm-select");
  const summary = document.getElementById("policy-selection-summary");
  const video = document.getElementById("policy-rollout-video");
  const emptyOverlay = document.getElementById("policy-video-empty");

  if (!suiteSelect || !taskSelect || !algorithmSelect || !summary || !video || !emptyOverlay) {
    return;
  }

  let activeRequestId = 0;
  let loadingTimerId = null;
  let currentCandidateUrls = [];
  let currentCandidateIndex = 0;

  const taskInstructionMap = {
    "lime_bowl_on": "put the lime in the bowl",
    "bottled_water_tray_on": "put the bottled water on the tray",
    "lemon_plate_on": "put the lemon on the plate",
    "egg_bowl_on": "put the egg in the bowl",
    "jam_basket_contain_region": "put the jam in the basket",
    "corn_cutting_board_on": "put the corn on the cutting board",
    "garlic_pan_on": "put the garlic in the pan",
    "apple_tray_on": "put the apple on the tray",
    "cheese_plate_on": "put the cheese on the plate",
    "avocado_basket_contain_region": "put the avocado in the basket",
    "onion_tray_on": "put the onion on the tray",
    "candle_tray_on": "put the candle on the tray",
    "orange_plate_on": "put the orange on the plate",
    "fish_plate_on": "put the fish on the plate",
    "mushroom_bowl_on": "put the mushroom in the bowl",
    "carrot_bowl_on": "put the carrot in the bowl",
    "jug_basket_contain_region": "put the jug in the basket",
    "yogurt_basket_contain_region": "put the yogurt in the basket",
    "orange_cutting_board_on": "put the orange on the cutting board",
    "bagel_cutting_board_on": "put the bagel on the cutting board",
    "eggplant_cutting_board_on": "put the eggplant on the cutting board",
    "fish_pan_on": "put the fish in the pan",
    "broccoli_pan_on": "put the broccoli in the pan",
    "plate_bowl_drainer_left_region": "put the plate in the left side of the dish drainer",
    "cup_bowl_drainer_right_region": "put the cup in the right side of the dish drainer",
    "mug_bowl_drainer_left_region": "put the mug in the left side of the dish drainer",
    "peach_tray_on": "put the peach on the tray",
    "peach_cutting_board_on": "put the peach on the cutting board",
    "peach_basket_contain_region": "put the peach in the basket",
    "squash_tray_on": "put the squash on the tray",
    "squash_pan_on": "put the squash in the pan",
    "wine_tray_on": "put the wine on the tray",
    "tomato_left_pan_on": "put the tomato in the pan",
    "tomato_left_tray_on": "put the tomato on the tray",
    "tomato_left_cutting_board_on": "put the tomato on the cutting board",
    "rolling_pin_left_pan_on": "put the rolling pin in the pan",
    "rolling_pin_left_tray_on": "put the rolling pin on the tray",
    "rolling_pin_left_bowl_drainer_right_region": "put the rolling pin in the right side of the dish drainer",
    "water_bottle_left_tray_on": "put the water bottle on the tray",
    "water_bottle_left_basket_contain_region": "put the water bottle in the basket",
    "open_and_avocado_cabinet_top_region": "open the top drawer of the cabinet and put the avocado in it",
    "open_and_carrot_cabinet_top_region": "open the top drawer of the cabinet and put the carrot in it",
    "open_and_lemon_cabinet_middle_region": "open the middle drawer of the cabinet and put the lemon in it",
    "open_and_onion_cabinet_middle_region": "open the middle drawer of the cabinet and put the onion in it",
    "open_and_mushroom_cabinet_bottom_region": "open the bottom drawer of the cabinet and put the mushroom in it",
    "open_and_broccoli_cabinet_bottom_region": "open the bottom drawer of the cabinet and put the broccoli in it",
    "open_and_canned_food_microwave_heating_region": "open the microwave and put the canned food in it",
    "open_and_eggplant_microwave_heating_region": "open the microwave and put the eggplant in it",
    "open_and_candle_slide_cabinet_contain_region": "open the slide cabinet and put the candle in it",
    "open_and_book_slide_cabinet_contain_region": "open the slide cabinet and put the book in it",
    "open_and_can_sliding_top_box_contain_region": "open the box and put the can in it",
    "open_and_cheese_sliding_top_box_contain_region": "open the box and put the cheese in it",
    "bar_soap_cabinet_top_region_and_close": "put the bar soap in the top drawer of the cabinet and close it",
    "kiwi_cabinet_top_region_and_close": "put the kiwi in the top drawer of the cabinet and close it",
    "garlic_cabinet_middle_region_and_close": "put the garlic in the middle drawer of the cabinet and close it",
    "sponge_cabinet_middle_region_and_close": "put the sponge in the middle drawer of the cabinet and close it",
    "cucumber_cabinet_bottom_region_and_close": "put the cucumber in the bottom drawer of the cabinet and close it",
    "bar_cabinet_bottom_region_and_close": "put the bar in the bottom drawer of the cabinet and close it",
    "bowl_microwave_heating_region_and_close": "put the bowl in the microwave and close it",
    "potato_microwave_heating_region_and_close": "put the potato in the microwave and close it",
    "croissant_slide_cabinet_contain_region_and_close": "put the croissant in the slide cabinet and close it",
    "beer_slide_cabinet_contain_region_and_close": "put the beer in the slide cabinet and close it",
    "bell_pepper_sliding_top_box_contain_region_and_close": "put the bell pepper in the box and close it",
    "mango_sliding_top_box_contain_region_and_close": "put the mango in the box and close it",
    "open_and_peach_cabinet_top_region": "open the top drawer of the cabinet and put the peach in it",
    "open_and_squash_microwave_heating_region": "open the microwave and put the squash in it",
    "wine_sliding_top_box_contain_region": "put the wine in the box",
    "open_and_wine_slide_cabinet_contain_region": "open the slide cabinet and put the wine in it",
    "open_and_tomato_left_slide_cabinet_contain_region": "open the slide cabinet and put the tomato in it",
    "open_and_water_bottle_left_slide_cabinet_contain_region": "open the slide cabinet and put the water bottle in it",
    "peach_ood_tray_ai_on": "put the peach on the tray",
    "peach_ood_cutting_board_ai_on": "put the peach on the cutting board",
    "peach_ood_basket_contain_region": "put the peach in the basket",
    "open_and_peach_ood_cabinet_top_region": "open the top drawer of the cabinet and put the peach in it",
    "squash_ood_tray_ai_on": "put the squash on the tray",
    "squash_ood_pan_ai_on": "put the squash in the pan",
    "open_and_squash_ood_microwave_heating_region": "open the microwave and put the squash in it",
    "wine_ood_tray_ai_on": "put the wine on the tray",
    "wine_ood_sliding_top_box_contain_region": "put the wine in the box",
    "open_and_wine_ood_slide_cabinet_contain_region": "open the slide cabinet and put the wine in it",
    "bell_pepper_ai_sliding_top_box_contain_region_and_close": "put the bell pepper in the box and close it",
    "fish_ai_pan_ai_on": "put the fish in the pan",
    "jam_ai_basket_contain_region": "put the jam in the basket",
    "mushroom_ai_bowl_on": "put the mushroom in the bowl",
    "potato_ai_microwave_heating_region_and_close": "put the potato in the microwave and close it",
    "cheese_ai_plate_ai_on": "put the cheese on the plate",
    "orange_ai_plate_ai_on": "put the orange on the plate",
    "open_and_carrot_ai_cabinet_top_region": "open the top drawer of the cabinet and put the carrot in it",
    "beer_ai_slide_cabinet_contain_region_and_close": "put the beer in the slide cabinet and close it",
    "apple_ai_tray_ai_on": "put the apple on the tray",
    "tomato_right_pan_on": "put the tomato in the pan",
    "tomato_right_tray_on": "put the tomato on the tray",
    "tomato_right_cutting_board_on": "put the tomato on the cutting board",
    "open_and_tomato_right_slide_cabinet_contain_region": "open the slide cabinet and put the tomato in it",
    "rolling_pin_right_pan_on": "put the rolling pin in the pan",
    "rolling_pin_right_tray_on": "put the rolling pin on the tray",
    "rolling_pin_right_bowl_drainer_right_region": "put the rolling pin in the right side of the dish drainer",
    "water_bottle_right_tray_on": "put the water bottle on the tray",
    "water_bottle_right_basket_contain_region": "put the water bottle in the basket",
    "open_and_water_bottle_right_slide_cabinet_contain_region": "open the slide cabinet and put the water bottle in it",
    "pear_pot_on": "put the pear in the pot",
    "salt_shaker_sliding_top_box_contain_region_and_close": "put the salt shaker in the box and close it",
    "cupcake_basket_contain_region": "put the cupcake in the basket",
    "beet_ai_pot_on": "put the beet in the pot",
    "brussel_sprout_ai_pan_on": "put the brussel sprout in the pan",
    "chili_pepper_ai_bowl_on": "put the chili pepper in the bowl",
    "ginger_ai_cutting_board_on": "put the ginger on the cutting board",
    "grapes_ai_basket_contain_region": "put the grapes in the basket",
    "ice_cream_ai_bowl_on": "put the ice cream in the bowl",
    "olive_oil_bottle_ai_basket_contain_region": "put the olive oil in the basket",
    "pomegranate_ai_cabinet_top_region": "put the pomegranate in the top drawer of the cabinet",
    "radish_ai_cutting_board_on": "put the radish on the cutting board",
    "raspberry_ai_basket_contain_region": "put the raspberry in the basket",
    "sausage_ai_baking_sheet_ai_on": "put the sausage on the baking sheet",
    "scone_ai_plate_on": "put the scone on the plate",
    "strawberry_ai_bowl_on": "put the strawberry in the bowl",
    "thermos_ai_slide_cabinet_contain_region": "put the thermos in the slide cabinet",
    "sushi_ai_plate_on": "put the sushi on the plate",
    "potato_baking_sheet_ai_on": "put the potato on the baking sheet",
    "kebabs_ai_pan_on": "put the kebabs in the pan",
    "mushroom_tray_on": "put the mushroom on the tray",
    "apple_plate_on": "put the apple on the plate",
    "onion_bowl_on": "put the onion in the bowl",
    "carrot_pan_on": "put the carrot in the pan",
    "cheese_basket_contain_region": "put the cheese in the basket",
    "lemon_cutting_board_on": "put the lemon on the cutting board",
    "sponge_bowl_drainer_right_region": "put the sponge in the right side of the dish drainer",
    "cup_bowl_drainer_left_region": "put the cup in the left side of the dish drainer",
    "open_and_broccoli_cabinet_middle_region": "open the middle drawer of the cabinet and put the broccoli in it",
    "open_and_apple_cabinet_middle_region": "open the middle drawer of the cabinet and put the apple in it",
    "open_and_beer_sliding_top_box_contain_region": "open the box and put the beer in it",
    "open_and_jam_slide_cabinet_contain_region": "open the slide cabinet and put the jam in it",
    "open_and_apple_sliding_top_box_contain_region_and_close": "open the box and put the apple in it and close it",
    "open_and_mushroom_cabinet_middle_region_and_close": "open the middle drawer of the cabinet and put the mushroom in it and close it",
    "open_and_carrot_cabinet_top_region_and_close": "open the top drawer of the cabinet and put the carrot in it and close it",
    "open_and_potato_microwave_heating_region_and_close": "open the microwave and put the potato in it and close it",
    "lemon_lime_basket_contain_region": "put the lemon and lime in the basket",
    "fish_garlic_pan_on": "put the fish and garlic in the pan",
    "broccoli_mushroom_cutting_board_on": "put the broccoli and mushroom on the cutting board",
    "cheese_mug_tray_on": "put the cheese and mug on the tray"
  };

  const taskIdToLabel = (taskId) => {
    const label = taskInstructionMap[taskId];
    if (label) {
      return label.charAt(0).toUpperCase() + label.slice(1);
    }
    return taskId.replaceAll("_", " ");
  };

  const addOptions = (selectElement, items) => {
    selectElement.innerHTML = "";
    Object.entries(items).forEach(([key, value]) => {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = value.label;
      selectElement.appendChild(option);
    });
  };

  const populateSuites = () => {
    addOptions(suiteSelect, suiteOptions);
    suiteSelect.value = suiteOptions[defaultSelection.suite] ? defaultSelection.suite : Object.keys(suiteOptions)[0];
  };

  const populateTasks = () => {
    const taskIds = taskCatalogBySuite[suiteSelect.value] || [];
    taskSelect.innerHTML = "";
    taskIds.forEach((taskId) => {
      const option = document.createElement("option");
      option.value = taskId;
      option.textContent = taskIdToLabel(taskId);
      taskSelect.appendChild(option);
    });

    if (!taskIds.length) {
      taskSelect.innerHTML = "";
      return;
    }

    taskSelect.value = taskIds.includes(defaultSelection.task) ? defaultSelection.task : taskIds[0];
  };

  const populateAlgorithms = () => {
    addOptions(algorithmSelect, modelOptions);
    const fallbackAlgorithm = Object.keys(modelOptions)[0];
    algorithmSelect.value = modelOptions[defaultSelection.algorithm] ? defaultSelection.algorithm : fallbackAlgorithm;
  };

  const getSelection = () => {
    const suite = suiteOptions[suiteSelect.value] || null;
    const taskId = taskSelect.value || "";
    const taskLabel = taskId ? taskIdToLabel(taskId) : "";
    const algorithm = modelOptions[algorithmSelect.value] || null;
    return { suite, taskId, taskLabel, algorithm };
  };

  const getVideoUrls = (suiteId, taskId, algorithmId) => {
    if (!suiteId || !taskId || !algorithmId) {
      return [];
    }
    const base = "../" + suiteId + "/" + algorithmId + "/videos/rollout_" + taskId;
    return [base + "_h264.mp4", base + ".mp4"];
  };

  const showOverlay = (text) => {
    emptyOverlay.textContent = text;
    emptyOverlay.style.display = "flex";
  };

  const clearLoadingTimer = () => {
    if (loadingTimerId !== null) {
      window.clearTimeout(loadingTimerId);
      loadingTimerId = null;
    }
  };

  const loadVideo = (url) => {
    activeRequestId += 1;
    const requestId = activeRequestId;

    showOverlay("Loading video...");

    // Reset source to force a full reload across browsers.
    video.pause();
    video.removeAttribute("src");
    video.load();

    video.src = url;
    video.load();

    clearLoadingTimer();
    loadingTimerId = window.setTimeout(() => {
      if (requestId !== activeRequestId) {
        return;
      }
      showOverlay("Still loading. Try again in a moment.");
    }, 8000);
  };

  const renderSelection = () => {
    const { suite, taskId, taskLabel, algorithm } = getSelection();
    if (!suite || !taskId || !algorithm) {
      summary.textContent = "Selected: unavailable";
      video.removeAttribute("src");
      video.load();
      showOverlay("No video mapped yet for this selection.");
      currentCandidateUrls = [];
      currentCandidateIndex = 0;
      return;
    }

    summary.textContent = "Selected: " + suite.label + " / " + taskLabel + " / " + algorithm.label;
    currentCandidateUrls = getVideoUrls(suiteSelect.value, taskSelect.value, algorithmSelect.value);
    currentCandidateIndex = 0;

    if (currentCandidateUrls.length) {
      loadVideo(currentCandidateUrls[currentCandidateIndex]);
    } else {
      video.removeAttribute("src");
      video.load();
      showOverlay("No video mapped for " + suite.label + " / " + taskLabel + " / " + algorithm.label + ".");
    }
  };

  const onVideoReady = () => {
    clearLoadingTimer();
    if (video.currentSrc || video.src) {
      emptyOverlay.style.display = "none";
    }
  };

  video.addEventListener("loadedmetadata", onVideoReady);
  video.addEventListener("loadeddata", onVideoReady);
  video.addEventListener("canplay", onVideoReady);
  video.addEventListener("playing", onVideoReady);

  video.addEventListener("stalled", () => {
    if (video.currentSrc || video.src) {
      showOverlay("Buffering video...");
    }
  });

  video.addEventListener("error", () => {
    clearLoadingTimer();
    const { suite, taskLabel, algorithm } = getSelection();
    let reason = "unknown error";
    if (video.error) {
      const errorCode = video.error.code;
      if (errorCode === 1) reason = "aborted";
      if (errorCode === 2) reason = "network failure";
      if (errorCode === 3) reason = "decode failure";
      if (errorCode === 4) reason = "source not supported";
    }

    const hasFallback = currentCandidateIndex + 1 < currentCandidateUrls.length;
    if (hasFallback) {
      currentCandidateIndex += 1;
      const fallbackUrl = currentCandidateUrls[currentCandidateIndex];
      showOverlay("Primary video failed (" + reason + "). Trying fallback format...");
      loadVideo(fallbackUrl);
      return;
    }

    if (!suite || !taskLabel || !algorithm) {
      showOverlay("Unable to load video (" + reason + ").");
      return;
    }
    showOverlay("Unable to load " + suite.label + " / " + taskLabel + " / " + algorithm.label + " (" + reason + ").");
    if (reason === "source not supported") {
      showOverlay("Unable to load " + suite.label + " / " + taskLabel + " / " + algorithm.label + " (source not supported).");
    }
  });

  suiteSelect.addEventListener("change", () => {
    populateTasks();
    renderSelection();
  });

  taskSelect.addEventListener("change", renderSelection);
  algorithmSelect.addEventListener("change", renderSelection);

  populateSuites();
  populateTasks();
  populateAlgorithms();
  renderSelection();
})();
</script>
```

# Bimanual task suites

This page lists the dual-arm (BiMESA) benchmark task suites defined in `mesa/task_suites/task_sets.py`. For the single-arm suites, see [task suites](task_suites.md).

## BiMESA-57 training set

BiMESA is the dual-arm counterpart to MESA, built on a two-arm reverse-mounted YAM platform. The **BiMESA-57** training set contains 57 in-distribution tasks organized into three skill blocks:

| Block | Skill | Tasks | Generation |
| --- | --- | --- | --- |
| A | Spatial pick-and-place | 27 | MESA-Gen (aligned combos), teleop (cross combos) |
| B | Cross-arm handoff | 17 | Teleop |
| C | Single-arm articulated | 13 | MESA-Gen |

**MESA-Gen synthesizes only the aligned Block A combos and all of Block C.** Cross-arm handoffs (Block B) and the cross combos of Block A are collected by teleoperation — MESA-Gen does not generate handoffs.

The `bimesa-id` suite evaluates these same 57 tasks from unseen initial states. The remaining four suites each hold out one generalization axis.

## BiMESA-ID (`bimesa-id`)

The 57 in-distribution training tasks, evaluated from unseen initial states. Block A tasks carry a `__<combo>` suffix, Block B a `handoff_` prefix, and Block C the `open_and_` / `_and_close` articulated grammar.

| Task ID | Natural Language Instruction |
| --- | --- |
| apple_tray_on__right_right | put the apple on the tray |
| onion_tray_on__right_right | put the onion on the tray |
| lime_tray_on__left_left | put the lime on the tray |
| tangerine_tray_on__right_right | put the tangerine on the tray |
| bell_pepper_tray_on__right_right | put the bell pepper on the tray |
| candle_tray_on__right_right | put the candle on the tray |
| coffee_cup_tray_on__right_right | put the coffee cup on the tray |
| lemon_plate_on__right_right | put the lemon on the plate |
| orange_plate_on__right_right | put the orange on the plate |
| mango_plate_on__left_left | put the mango on the plate |
| kiwi_plate_on__right_right | put the kiwi on the plate |
| beer_plate_on__left_left | put the beer on the plate |
| lime_bowl_on__right_right | put the lime in the bowl |
| mushroom_bowl_on__right_right | put the mushroom in the bowl |
| apple_bowl_on__left_left | put the apple in the bowl |
| jam_basket_contain_region__right_right | put the jam in the basket |
| yogurt_basket_contain_region__right_right | put the yogurt in the basket |
| mango_basket_contain_region__right_right | put the mango in the basket |
| bell_pepper_basket_contain_region__right_right | put the bell pepper in the basket |
| bottled_drink_basket_contain_region__left_left | put the bottled drink in the basket |
| orange_cutting_board_on__right_right | put the orange on the cutting board |
| kiwi_cutting_board_on__right_right | put the kiwi on the cutting board |
| tangerine_cutting_board_on__left_left | put the tangerine on the cutting board |
| onion_cutting_board_on__right_right | put the onion on the cutting board |
| garlic_pan_on__right_right | put the garlic in the pan |
| onion_pan_on__left_left | put the onion in the pan |
| can_pan_on__left_left | put the can in the pan |
| handoff_water_bottle_tray_on | put the water bottle on the tray |
| handoff_beer_plate_on | put the beer on the plate |
| handoff_wine_cutting_board_on | put the wine on the cutting board |
| handoff_bottled_water_basket_contain_region | put the bottled water in the basket |
| handoff_can_pan_on | put the can in the pan |
| handoff_jam_bowl_drainer_right_region | put the jam in the right side of the dish drainer |
| handoff_bottled_drink_basket_contain_region | put the bottled drink in the basket |
| handoff_coffee_cup_tray_on | put the coffee cup on the tray |
| handoff_spray_basket_contain_region | put the spray in the basket |
| handoff_milk_tray_on | put the milk on the tray |
| handoff_candle_tray_on | put the candle on the tray |
| handoff_alcohol_basket_contain_region | put the alcohol in the basket |
| handoff_jug_basket_contain_region | put the jug in the basket |
| handoff_ketchup_plate_on | put the ketchup on the plate |
| handoff_condiment_plate_on | put the condiment on the plate |
| handoff_soap_dispenser_tray_on | put the soap dispenser on the tray |
| handoff_yogurt_bowl_on | put the yogurt in the bowl |
| open_and_candle_slide_cabinet_contain_region | open the slide cabinet and put the candle in it |
| open_and_book_slide_cabinet_contain_region | open the slide cabinet and put the book in it |
| open_and_can_slide_cabinet_contain_region | open the slide cabinet and put the can in it |
| open_and_beer_slide_cabinet_contain_region | open the slide cabinet and put the beer in it |
| open_and_can_sliding_top_box_contain_region | open the box and put the can in it |
| open_and_apple_sliding_top_box_contain_region | open the box and put the apple in it |
| beer_slide_cabinet_contain_region_and_close | put the beer in the slide cabinet and close it |
| mango_slide_cabinet_contain_region_and_close | put the mango in the slide cabinet and close it |
| apple_sliding_top_box_contain_region_and_close | put the apple in the box and close it |
| lemon_sliding_top_box_contain_region_and_close | put the lemon in the box and close it |
| open_and_mango_sliding_top_box_contain_region_and_close | open the box and put the mango in it and close it |
| open_and_can_sliding_top_box_contain_region_and_close | open the box and put the can in it and close it |
| open_and_orange_slide_cabinet_contain_region_and_close | open the slide cabinet and put the orange in it and close it |

## BiMESA-Spatial (`bimesa-spatial`)

38 tasks holding out a spatial configuration not seen in training: 27 held-out arm/side combos (Block A), 8 reversed handoff directions (Block B), and 3 held-out fixture sides (Block C).

| Task ID | Natural Language Instruction |
| --- | --- |
| apple_tray_on__left_left | put the apple on the tray |
| onion_tray_on__pick_left_dest_right | put the onion on the tray |
| lime_tray_on__right_right | put the lime on the tray |
| tangerine_tray_on__pick_right_dest_left | put the tangerine on the tray |
| bell_pepper_tray_on__left_left | put the bell pepper on the tray |
| candle_tray_on__pick_right_dest_left | put the candle on the tray |
| coffee_cup_tray_on__pick_right_dest_left | put the coffee cup on the tray |
| lemon_plate_on__pick_right_dest_left | put the lemon on the plate |
| orange_plate_on__pick_left_dest_right | put the orange on the plate |
| mango_plate_on__right_right | put the mango on the plate |
| kiwi_plate_on__pick_right_dest_left | put the kiwi on the plate |
| beer_plate_on__right_right | put the beer on the plate |
| lime_bowl_on__left_left | put the lime in the bowl |
| mushroom_bowl_on__pick_left_dest_right | put the mushroom in the bowl |
| apple_bowl_on__right_right | put the apple in the bowl |
| jam_basket_contain_region__pick_left_dest_right | put the jam in the basket |
| yogurt_basket_contain_region__pick_right_dest_left | put the yogurt in the basket |
| mango_basket_contain_region__left_left | put the mango in the basket |
| bell_pepper_basket_contain_region__pick_left_dest_right | put the bell pepper in the basket |
| bottled_drink_basket_contain_region__right_right | put the bottled drink in the basket |
| orange_cutting_board_on__left_left | put the orange on the cutting board |
| kiwi_cutting_board_on__pick_left_dest_right | put the kiwi on the cutting board |
| tangerine_cutting_board_on__right_right | put the tangerine on the cutting board |
| onion_cutting_board_on__pick_right_dest_left | put the onion on the cutting board |
| garlic_pan_on__pick_left_dest_right | put the garlic in the pan |
| onion_pan_on__right_right | put the onion in the pan |
| can_pan_on__right_right | put the can in the pan |
| handoff_water_bottle_tray_on__pick_right_dest_left | put the water bottle on the tray |
| handoff_beer_plate_on__pick_right_dest_left | put the beer on the plate |
| handoff_wine_cutting_board_on__pick_right_dest_left | put the wine on the cutting board |
| handoff_can_pan_on__pick_right_dest_left | put the can in the pan |
| handoff_milk_tray_on__pick_left_dest_right | put the milk on the tray |
| handoff_jug_basket_contain_region__pick_left_dest_right | put the jug in the basket |
| handoff_condiment_plate_on__pick_left_dest_right | put the condiment on the plate |
| handoff_yogurt_bowl_on__pick_left_dest_right | put the yogurt in the bowl |
| open_and_candle_slide_cabinet_contain_region__pick_right_fixture_left | open the slide cabinet and put the candle in it |
| beer_slide_cabinet_contain_region_and_close__pick_left_fixture_right | put the beer in the slide cabinet and close it |
| open_and_orange_slide_cabinet_contain_region_and_close__pick_right_fixture_left | open the slide cabinet and put the orange in it and close it |

## BiMESA-Instance (`bimesa-instance`)

18 tasks that swap a trained pick or destination object for a held-out mesh of the same instance (marked `_ai`): 9 pick-and-place, 5 handoff, 4 articulated.

| Task ID | Natural Language Instruction |
| --- | --- |
| apple_ai_tray_ai_on | put the apple on the tray |
| orange_ai_plate_ai_on | put the orange on the plate |
| mushroom_ai_bowl_on | put the mushroom in the bowl |
| jam_ai_basket_contain_region | put the jam in the basket |
| apple_ai_bowl_on | put the apple in the bowl |
| bell_pepper_ai_basket_contain_region | put the bell pepper in the basket |
| orange_ai_cutting_board_on | put the orange on the cutting board |
| beer_ai_plate_ai_on | put the beer on the plate |
| bell_pepper_ai_tray_on | put the bell pepper on the tray |
| handoff_beer_ai_plate_ai_on | put the beer on the plate |
| handoff_jam_ai_bowl_drainer_right_region | put the jam in the right side of the dish drainer |
| handoff_can_pan_ai_on | put the can in the pan |
| handoff_water_bottle_tray_ai_on | put the water bottle on the tray |
| handoff_candle_tray_ai_on | put the candle on the tray |
| open_and_apple_ai_sliding_top_box_contain_region | open the box and put the apple in it |
| open_and_beer_ai_slide_cabinet_contain_region | open the slide cabinet and put the beer in it |
| open_and_orange_ai_slide_cabinet_contain_region_and_close | open the slide cabinet and put the orange in it and close it |
| apple_ai_sliding_top_box_contain_region_and_close | put the apple in the box and close it |

## BiMESA-Object (`bimesa-object`)

17 tasks whose pick object comes from a category not seen in training: 10 pick-and-place, 3 handoff, 4 articulated.

| Task ID | Natural Language Instruction |
| --- | --- |
| pear_pot_on | put the pear in the pot |
| cupcake_basket_contain_region | put the cupcake in the basket |
| beet_ai_pot_on | put the beet in the pot |
| brussel_sprout_ai_pan_on | put the brussel sprout in the pan |
| chili_pepper_ai_bowl_on | put the chili pepper in the bowl |
| ginger_ai_cutting_board_on | put the ginger on the cutting board |
| grapes_ai_basket_contain_region | put the grapes in the basket |
| radish_ai_cutting_board_on | put the radish on the cutting board |
| sausage_ai_baking_sheet_ai_on | put the sausage on the baking sheet |
| scone_ai_plate_on | put the scone on the plate |
| handoff_thermos_ai_basket_contain_region | put the thermos in the basket |
| handoff_olive_oil_bottle_ai_tray_on | put the olive oil bottle on the tray |
| handoff_pomegranate_ai_bowl_on | put the pomegranate in the bowl |
| open_and_pear_slide_cabinet_contain_region | open the slide cabinet and put the pear in it |
| open_and_cupcake_sliding_top_box_contain_region | open the box and put the cupcake in it |
| open_and_potato_ai_slide_cabinet_contain_region | open the slide cabinet and put the potato in it |
| open_and_grapes_ai_sliding_top_box_contain_region_and_close | open the box and put the grapes in it and close it |

## BiMESA-Composite (`bimesa-composite`)

15 tasks composing trained primitives in unseen ways: 5 pick-and-place, 4 articulated pairs, 3 two-object placements, and 3 open-place-close chains.

| Task ID | Natural Language Instruction |
| --- | --- |
| apple_plate_on | put the apple on the plate |
| mushroom_tray_on | put the mushroom on the tray |
| onion_bowl_on | put the onion in the bowl |
| carrot_pan_on | put the carrot in the pan |
| lemon_cutting_board_on | put the lemon on the cutting board |
| open_and_beer_sliding_top_box_contain_region | open the box and put the beer in it |
| open_and_jam_slide_cabinet_contain_region | open the slide cabinet and put the jam in it |
| open_and_apple_sliding_top_box_contain_region_and_close | open the box and put the apple in it and close it |
| open_and_mushroom_slide_cabinet_contain_region_and_close | open the slide cabinet and put the mushroom in it and close it |
| lemon_lime_basket_contain_region | put the lemon and the lime in the basket |
| broccoli_mushroom_cutting_board_on | put the broccoli and the mushroom on the cutting board |
| fish_garlic_pan_on | put the fish and the garlic in the pan |
| open_and_lemon_sliding_top_box_contain_region_and_close | open the box and put the lemon in it and close it |
| open_and_beer_slide_cabinet_contain_region_and_close | open the slide cabinet and put the beer in it and close it |
| open_and_book_slide_cabinet_contain_region_and_close | open the slide cabinet and put the book in it and close it |

## Task ID Naming Conventions

Bimanual task IDs reuse the single-arm [pick-and-place and articulated grammar](task_suites.md#task-id-naming-conventions) for the object/target/region root, with two dual-arm additions.

**Spatial combo suffix** (Block A pick-and-place). A `__<pick>_<dest>` suffix records which arm picks and which side the destination is on:
- `apple_tray_on__right_right` &rarr; the right arm picks the apple, destination tray on the right.
- `onion_tray_on__pick_left_dest_right` &rarr; the left arm picks the onion, destination tray on the right.

`__right_right` and `__left_left` are aligned combos, where a single arm performs the whole task; `__pick_left_dest_right` and `__pick_right_dest_left` are cross combos. For articulated Block C tasks, `__pick_<side>_fixture_<side>` records the picking arm and the side the fixture sits on.

**Handoff prefix** (Block B). A `handoff_` prefix marks a cross-arm handoff: one arm picks the object and passes it to the other, which places it. A `__pick_<side>_dest_<side>` suffix, when present, fixes the handoff direction.
- `handoff_beer_plate_on` &rarr; pick the beer with one arm, hand it across, and place it on the plate.

As in single-arm MESA, an `_ai` tag on an object name marks a held-out mesh used for the instance and category generalization suites (e.g. `apple_ai_tray_ai_on`).

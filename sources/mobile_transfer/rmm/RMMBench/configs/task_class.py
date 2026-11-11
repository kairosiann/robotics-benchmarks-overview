TASK_CLASS = {"manipulation":{
    "strict":{
        "pick_snack_single": ["pick_chocolate","pick_chip"],
        "pick_bread_toaster": ["select_bread_toaster_0", "select_bread_toaster_1", "select_bread_toaster_2"],
        "pick_kitchen_tool": ["pick_can_opener_0", "pick_whisk_0", "pick_bottle_opener_0"],
        "wash_fruit_veg": ["wash_place_carrot", "wash_place_apple", "wash_place_cucumber"],
        "cook_meat_pan_stove": ["cook_steak_0", "cook_chicken_breast_0", "cook_sausage_0"],
        "reheat_microwave": ["reheat_steak_0", "heat_scone_0", "heat_waffle_0", "warm_baguette_0", "warm_croissant_0"],
        "store_meat_fridge": ["store_lamb_chicken_0", "store_pork_bacon_0", "store_sausage_fish_0"],
        "bring_cold_drink": ["bring_cold_water", "bring_cold_milk", "bring_cold_boxed_drink",
         "bring_non_alcoholic_drink", "bring_child_drink", "bring_no_sugar_drink"],
        "pick_drink_choice_no_fridge": ["pick_non_alcoholic_drink", "pick_child_drink", "pick_no_sugar_drink"],
        "store_item_fridge": ["store_non_alcoholic_drink", "store_child_drink", "store_no_sugar_drink"],
        "fix_burnt_bread": ["fix_burnt_bread_0", "fix_burnt_bread_1", "fix_burnt_bread_2"],
        "select_same_class_cabinet": ["select_same_cake", "select_same_banana"],
        "store_cabinet": ["store_yogurt"],
        "uncover_object": ["uncover_fruit"],

    },
    "flexible":{
        "pick_multi_snack_single_container": ["select_bagged_snacks", "cluster_bagged&bar_snack"],
        "wash_multi_fruit_veg": ["wash_veg_salad", "wash_fruit_plate", "wash_broccoli_pepper"],
        "wash_fruit_shelf": ["wash_fruit_from_shelf"],
        "prepare_meat_tool": ["prepare_pork_tongs_0", "prepare_chicken_spatula_0", "prepare_pork_chop_spoon_0"],
        "pick_bread_prep": ["place_bread_jam_knife_0", "place_waffle_syrup_fork_0", "place_bagel_butter_knife_0", "place_bread_jam_knife_1", "place_waffle_syrup_fork_1", "place_bagel_butter_knife_1"],
        "pick_multi_kitchen_tool": ["pick_can_opener_bottle_opener_0", "pick_whisk_knife_0", "pick_spatula_ladle_0"],
        "classify_snacks_on_shelf": ["classify_chocolate_snacks"],
    }
},
    "composite_navigation":{
    "nav_wash_place": [
        "nav_wash_place_carrot_0", "nav_wash_place_carrot_1", "nav_wash_place_carrot_2", "nav_wash_place_carrot_3",
        "nav_wash_place_apple_0", "nav_wash_place_apple_1",
        "nav_wash_place_cucumber_0", "nav_wash_place_cucumber_1",
    ],
    "nav_pick_snacks": [
        "nav_pick_chocolate_0", "nav_pick_chocolate_1", "nav_pick_chocolate_2", "nav_pick_chocolate_3",
        "nav_pick_chip_0", "nav_pick_chip_1", "nav_pick_chip_2", "nav_pick_chip_3",
    ],
    "nav_cook_steak": [
        "nav_cook_steak_0", "nav_cook_steak_1", "nav_cook_steak_2", "nav_cook_steak_3",
    ],

    "nav_select_tool": [
        "nav_select_tool_galley_0", "nav_select_tool_galley_1", "nav_select_tool_galley_2",
        "nav_select_tool_l_large_0", "nav_select_tool_l_large_1", "nav_select_tool_l_large_2",
        "nav_select_tool_l_small_0", "nav_select_tool_l_small_1", "nav_select_tool_l_small_2",
    ],

    "nav_burnt_bread": [
        "nav_burnt_bread_0", "nav_burnt_bread_1", "nav_burnt_bread_2",
        "nav_burnt_bread_3", "nav_burnt_bread_4", "nav_burnt_bread_5",
        "nav_burnt_bread_6", "nav_burnt_bread_7", "nav_burnt_bread_8",
    ],

    "nav_store_item_fridge": [
        "nav_store_non_alcoholic_drink_0", "nav_store_non_alcoholic_drink_1",
        "nav_store_non_alcoholic_drink_2", "nav_store_non_alcoholic_drink_3",
        "nav_store_child_drink_0", "nav_store_child_drink_1",
        "nav_store_child_drink_2", "nav_store_child_drink_3",
        "nav_store_no_sugar_drink_0", "nav_store_no_sugar_drink_1",
        "nav_store_no_sugar_drink_2", "nav_store_no_sugar_drink_3",
    ],

    "navigate_to_refrigerator": [
            "navigate_to_refrigerator_0", "navigate_to_refrigerator_1", "navigate_to_refrigerator_2",
        ],
    }
}
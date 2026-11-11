/* =====================================================
   config/asset-page.js — the All assets page (assets.html)
   =====================================================
   One card per asset, in the order below. A card shows a still of
   the asset's 3D model; clicking it opens the model in a 3D viewer
   (drag to turn it), with the asset's downloads beside it. An asset
   without variants has its STL and 3MF buttons on its card; one
   with variants has a Downloads button that opens the viewer's
   panel, where the downloads are two steps: the base parts, then a
   table of each variant's parts.

   dir      folder holding the models and download files; the paths
            below are in it (downloads may also be full https:// links)
   colors   named colors for STL models, as [red, green, blue], 0–255
   assets   the cards:
     key        short id (lowercase-with-dashes); assets.html#<key>
                scrolls to the card
     name       shown on the card
     note       optional sentence (plain text) shown under the name on
                the card and under Downloads in the panel; [text](https://…)
                makes a link, e.g. '(like [this](https://a.co/d/0fWvHZPB))'
     hardware   optional: the screws and nuts it takes to put together,
                listed under "Hardware" in the panel: { count, item }
                rows, e.g. { count: 4, item: 'M3 × 15 mm screw' }; or, in
                parts, groups { label, items: [rows] }, each under its
                label. [text](https://…) in an item makes a link, as in a
                note (the platform's acrylic sheet). Its card then has
                a Hardware button, which opens its panel to just its
                hardware (called Assembly when it has assembly videos).
     assemblyTips  optional: tips for putting it together, as a list of
                sentences, shown under "Assembly tips" after its hardware
                (formatted like its printing tips); [text](https://…)
                makes a link. Its card then has a Hardware button.
     assembly   optional: videos showing how to put it together, as
                [{ video, label }]: video, a file in videoDir (H.264
                .mp4); label, its title. Its card's Hardware button,
                then called Assembly, shows them under the 3D view and
                the hardware.
     tips       optional: printing tips for it, as a list of sentences
                (PRINT_TIPS, above defineAssetPage, holds the shared ones),
                shown under "Printing tips" in the panel (above any
                orientation screenshots); [text](https://…) makes a
                link, as in a note. Its card then has a Printing tips
                button.
     orientation  optional: screenshots of its parts as placed in the
                slicer, for printing without the 3MF, as [{ image, label }]:
                image, a file in dir (print_orientations/…); label, its
                title (default 'Print orientation'). Its card then has a
                Printing tips button, which opens its panel to just them
                beside the 3D view.
     model      the 3D model shown: an .obj (its .mtl gives the colors
                of its parts) or an .stl (one color: set `color`); or a
                list of them, shown together (parts exported separately,
                in place from one CAD assembly)
     color      an STL's color: a name from `colors`; for a list of
                models, one for all or a list of names, one per model
                in order, e.g. ['yellow', 'gray'] for a bottle and cap
     view       optional [azimuth, elevation] in degrees, for an asset
                the default view (js/model-view.js) doesn't show well.
                Models are Z-up; azimuth turns from +x toward +y.
     stl, '3mf' an asset without variants: its download files. Leave ''
                until they exist: the button is greyed out. The 3MF is
                a Bambu Lab project (its button says so); several cards
                may share one (the charging blocks' 3MF has all five).
     '3mf'      for an asset with variants, optional: one Bambu Lab 3MF
                with all its parts (base and every variant), offered at
                the top of its Downloads; its base and variants then
                have only an stl.
     variation  for an asset with variants: the title of its group of
                variants, e.g. 'Insertion force' (heads the panel's
                table)
     base       { model, color, stl, '3mf' }: the base parts every
                variant needs. Its model (optional) is shown with each
                variant's, so the two should be in the same place in
                CAD; color defaults to the asset's. Leave base out if
                the variants share no parts.
     variants   the variants, in order: { label, model, color, view,
                default, stl, '3mf' }, with model, stl and '3mf' holding
                only that variant's own parts. A variant without a
                model, color, or view shows the asset's. When variants
                look different, clicking a variant's row in the panel's
                download table shows it in 3D, swapped in without a
                reload. default: true shows it first (else the first
                variant is). offset (optional): [x, y, z], in the
                model's units, moves its models in 3D and in the still,
                e.g. [0, 0, -0.5] for 0.5 mm down.
     groups     for an asset with several groups of variants, in place
                of variation and variants: [{ variation, slot, color,
                variants }], one table each. The viewer shows the base
                parts with the variant chosen in each group. Groups
                with the same slot (any name) share one choice, for
                parts that go in the same place (a door handle or a
                doorknob). A group's color and offset are its variants'
                defaults.
                The card's still shows the first choice in each slot.
     combinations  for an asset whose files each belong to a choice of
                a variant in every group (a lightbulb's geometry and
                amount of rotation), with groups (no slots) whose
                variants are just labels: one { variants, model, color,
                stl, '3mf' } per choice, variants naming one variant of
                each group by label, in the groups' order, e.g.
                { variants: ['55mm diameter', '2 revolutions'], model: …, stl: … }.
                The panel's tables then only choose; the chosen
                combination's files are under them.
     toggles    optional parts the reader can hide in 3D, listed under
                "Toggle visibility" in the panel: { label, model, body }
                or { label, model, except }. model: one of the asset's
                model files, as written above (the base parts', the
                asset's, or a variant's), hidden whole unless body names
                the bodies to hide, or except the bodies to keep: a
                body's name in the .obj (a `g` line: its name in CAD),
                or a list of them. model may also be a list of files, or
                a pattern where * stands for any part of a file's name,
                to hide a part that's a different file in each variant
                (e.g. 'for_printing/bottles/bottle_1/cap_*.stl').
                e.g. { label: 'Top cover', model: 'for_visualization/lock_module/base.obj', body: 'Body1:2' }

   After editing, run node tools/check.mjs --make-media: it makes each
   model's viewer copy (website_assets/meshes/) and still
   (website_assets/images/renders/), and makes them again when a
   model, color, or view changes.
   ===================================================== */

// Printing tips shared by several assets (their `tips`), from the General
// printing instructions and tips in assets.html
const PRINT_TIPS = {
  threads: [
    'Print the threads at a layer height of 0.12 mm or less. Variable layer height can save print time, as long as the threads stay at 0.12 mm or less.',
    'Threads don\'t need supports and shouldn\'t have any.'
  ],
  strength: 'Use 6 wall loops for strength.',
  springs: 'Print the springs with 6 wall loops for strength.',
  large: 'Gyroid infill can help reduce and prevent warping.'
};

defineAssetPage({
  dir: 'website_assets/benchmark_assets/',
  // Assembly videos (an asset's `assembly`) and their posters: for each
  // video, its frame one second in, <name>-t1.jpg, made by
  // node tools/check.mjs --make-media
  videoDir: 'website_assets/videos/assembly_videos/',
  stillDir: 'website_assets/images/stills/assembly_videos/',

  colors: {
    white: [246, 246, 243],   // the CAD white (written in the STL files)
    yellow: [255, 255, 0],
    gray: [120, 120, 120],
    black: [45, 45, 45]       // the CAD black is 0, 0, 0; lighter here so the shading shows
  },

  assets: [
    // Alphabetical by name, except that the four utensils go just before
    // the utensil bins, the tools (Allen key, wrench) with the screwdriver,
    // the screw, bolt, and nut just before the tools, the outlet right after
    // the charging blocks, the doorknob and lock modules just before the
    // door, and the USB sticks and slot right after the Ethernet plug and
    // slot

    // Each variant is a bottle (yellow) and its cap (gray), in place on it;
    // its download is a zip of both
    {
      key: 'bottle-1', name: 'Bottle 1', color: ['yellow', 'gray'],
      tips: PRINT_TIPS.threads,
      variation: 'Amount of rotation to tighten',
      variants: [
        { label: '2 revolutions', model: ['for_printing/bottles/bottle_1/bottle_1_2_rev.stl', 'for_printing/bottles/bottle_1/cap_1_2_rev.stl'], stl: 'for_printing/bottles_zip/bottle_1_2_rev.zip', '3mf': '3mf/bottles/bottle_1/bottle_1_2_rev.3mf' },
        { label: '2.5 revolutions', model: ['for_printing/bottles/bottle_1/bottle_1_2.5_rev.stl', 'for_printing/bottles/bottle_1/cap_1_2.5_rev.stl'], stl: 'for_printing/bottles_zip/bottle_1_2.5_rev.zip', '3mf': '3mf/bottles/bottle_1/bottle_1_2.5_rev.3mf' },
        { label: '3 revolutions', model: ['for_printing/bottles/bottle_1/bottle_1_3_rev.stl', 'for_printing/bottles/bottle_1/cap_1_3_rev.stl'], stl: 'for_printing/bottles_zip/bottle_1_3_rev.zip', '3mf': '3mf/bottles/bottle_1/bottle_1_3_rev.3mf' },
        { label: '3.5 revolutions', model: ['for_printing/bottles/bottle_1/bottle_1_3.5_rev.stl', 'for_printing/bottles/bottle_1/cap_1_3.5_rev.stl'], stl: 'for_printing/bottles_zip/bottle_1_3.5_rev.zip', '3mf': '3mf/bottles/bottle_1/bottle_1_3.5_rev.3mf' },
        { label: '4 revolutions', model: ['for_printing/bottles/bottle_1/bottle_1_4_rev.stl', 'for_printing/bottles/bottle_1/cap_1_4_rev.stl'], stl: 'for_printing/bottles_zip/bottle_1_4_rev.zip', '3mf': '3mf/bottles/bottle_1/bottle_1_4_rev.3mf' }
      ],
      toggles: [
        { label: 'Bottle', model: 'for_printing/bottles/bottle_1/bottle_*.stl' },
        { label: 'Cap', model: 'for_printing/bottles/bottle_1/cap_*.stl' }
      ]
    },
    {
      key: 'bottle-2', name: 'Bottle 2', color: ['yellow', 'gray'],
      tips: PRINT_TIPS.threads,
      variation: 'Amount of rotation to tighten',
      variants: [
        { label: '2 revolutions', model: ['for_printing/bottles/bottle_2/bottle_2_2_rev.stl', 'for_printing/bottles/bottle_2/cap_2_2_rev.stl'], stl: 'for_printing/bottles_zip/bottle_2_2_rev.zip', '3mf': '3mf/bottles/bottle_2/bottle_2_2_rev.3mf' },
        { label: '2.5 revolutions', model: ['for_printing/bottles/bottle_2/bottle_2_2.5_rev.stl', 'for_printing/bottles/bottle_2/cap_2_2.5_rev.stl'], stl: 'for_printing/bottles_zip/bottle_2_2.5_rev.zip', '3mf': '3mf/bottles/bottle_2/bottle_2_2.5_rev.3mf' },
        { label: '3 revolutions', model: ['for_printing/bottles/bottle_2/bottle_2_3_rev.stl', 'for_printing/bottles/bottle_2/cap_2_3_rev.stl'], stl: 'for_printing/bottles_zip/bottle_2_3_rev.zip', '3mf': '3mf/bottles/bottle_2/bottle_2_3_rev.3mf' },
        { label: '3.5 revolutions', model: ['for_printing/bottles/bottle_2/bottle_2_3.5_rev.stl', 'for_printing/bottles/bottle_2/cap_2_3.5_rev.stl'], stl: 'for_printing/bottles_zip/bottle_2_3.5_rev.zip', '3mf': '3mf/bottles/bottle_2/bottle_2_3.5_rev.3mf' },
        { label: '4 revolutions', model: ['for_printing/bottles/bottle_2/bottle_2_4_rev.stl', 'for_printing/bottles/bottle_2/cap_2_4_rev.stl'], stl: 'for_printing/bottles_zip/bottle_2_4_rev.zip', '3mf': '3mf/bottles/bottle_2/bottle_2_4_rev.3mf' }
      ],
      toggles: [
        { label: 'Bottle', model: 'for_printing/bottles/bottle_2/bottle_*.stl' },
        { label: 'Cap', model: 'for_printing/bottles/bottle_2/cap_*.stl' }
      ]
    },
    {
      key: 'bottle-3', name: 'Bottle 3', color: ['yellow', 'gray'],
      tips: PRINT_TIPS.threads,
      variation: 'Amount of rotation to tighten',
      variants: [
        { label: '2 revolutions', model: ['for_printing/bottles/bottle_3/bottle_3_2_rev.stl', 'for_printing/bottles/bottle_3/cap_3_2_rev.stl'], stl: 'for_printing/bottles_zip/bottle_3_2_rev.zip', '3mf': '3mf/bottles/bottle_3/bottle_3_2_rev.3mf' },
        { label: '2.5 revolutions', model: ['for_printing/bottles/bottle_3/bottle_3_2.5_rev.stl', 'for_printing/bottles/bottle_3/cap_3_2.5_rev.stl'], stl: 'for_printing/bottles_zip/bottle_3_2.5_rev.zip', '3mf': '3mf/bottles/bottle_3/bottle_3_2.5_rev.3mf' },
        { label: '3 revolutions', model: ['for_printing/bottles/bottle_3/bottle_3_3_rev.stl', 'for_printing/bottles/bottle_3/cap_3_3_rev.stl'], stl: 'for_printing/bottles_zip/bottle_3_3_rev.zip', '3mf': '3mf/bottles/bottle_3/bottle_3_3_rev.3mf' },
        { label: '3.5 revolutions', model: ['for_printing/bottles/bottle_3/bottle_3_3.5_rev.stl', 'for_printing/bottles/bottle_3/cap_3_3.5_rev.stl'], stl: 'for_printing/bottles_zip/bottle_3_3.5_rev.zip', '3mf': '3mf/bottles/bottle_3/bottle_3_3.5_rev.3mf' },
        { label: '4 revolutions', model: ['for_printing/bottles/bottle_3/bottle_3_4_rev.stl', 'for_printing/bottles/bottle_3/cap_3_4_rev.stl'], stl: 'for_printing/bottles_zip/bottle_3_4_rev.zip', '3mf': '3mf/bottles/bottle_3/bottle_3_4_rev.3mf' }
      ],
      toggles: [
        { label: 'Bottle', model: 'for_printing/bottles/bottle_3/bottle_*.stl' },
        { label: 'Cap', model: 'for_printing/bottles/bottle_3/cap_*.stl' }
      ]
    },

    { key: 'card', name: 'Card', model: 'for_printing/card.stl', color: 'yellow', stl: 'for_printing/card.stl', '3mf': '3mf/cards.3mf' },
    { key: 'card-holder', name: 'Card holder', model: 'for_printing/card_holder.stl', color: 'black', stl: 'for_printing/card_holder.stl', '3mf': '3mf/card_holder.3mf' },
    { key: 'charging-block-1', name: 'Charging block 1', model: 'for_printing/charging_blocks/charging_block_1.stl', color: 'white', stl: 'for_printing/charging_blocks/charging_block_1.stl', '3mf': '3mf/charging_blocks.3mf',
      orientation: [{ image: 'print_orientations/charging_block_1.png' }] },
    { key: 'charging-block-2', name: 'Charging block 2', model: 'for_printing/charging_blocks/charging_block_2.stl', color: 'black', stl: 'for_printing/charging_blocks/charging_block_2.stl', '3mf': '3mf/charging_blocks.3mf',
      orientation: [{ image: 'print_orientations/charging_block_2.png' }] },
    { key: 'charging-block-3', name: 'Charging block 3', model: 'for_printing/charging_blocks/charging_block_3.stl', color: 'black', stl: 'for_printing/charging_blocks/charging_block_3.stl', '3mf': '3mf/charging_blocks.3mf',
      orientation: [{ image: 'print_orientations/charging_block_3.png' }] },
    { key: 'charging-block-4', name: 'Charging block 4', model: 'for_printing/charging_blocks/charging_block_4.stl', color: 'black', stl: 'for_printing/charging_blocks/charging_block_4.stl', '3mf': '3mf/charging_blocks.3mf',
      orientation: [{ image: 'print_orientations/charging_block_4.png' }] },
    { key: 'charging-block-5', name: 'Charging block 5', model: 'for_printing/charging_blocks/charging_block_5.stl', color: 'white', stl: 'for_printing/charging_blocks/charging_block_5.stl', '3mf': '3mf/charging_blocks.3mf',
      orientation: [{ image: 'print_orientations/charging_block_5.png' }] },

    // The springs sit inside the shell: hide the shell to see them
    {
      key: 'outlet', name: 'Outlet', '3mf': '3mf/outlet.3mf', color: 'white',
      base: { model: 'for_printing/outlet/outlet_shell.stl', stl: 'for_printing/outlet/outlet_shell.stl' },
      variation: 'Insertion force',
      variants: [
        { label: '0.4mm indent spring', model: 'for_printing/outlet/outlet_spring_0.4mm_indent.stl', stl: 'for_printing/outlet/outlet_spring_0.4mm_indent.stl' },
        { label: '0.7mm indent spring', model: 'for_printing/outlet/outlet_spring_0.7mm_indent.stl', stl: 'for_printing/outlet/outlet_spring_0.7mm_indent.stl' },
        { label: '0.85mm indent spring', model: 'for_printing/outlet/outlet_spring_0.85mm_indent.stl', stl: 'for_printing/outlet/outlet_spring_0.85mm_indent.stl' },
        { label: '1mm indent spring', model: 'for_printing/outlet/outlet_spring_1mm_indent.stl', stl: 'for_printing/outlet/outlet_spring_1mm_indent.stl' }
      ],
      toggles: [{ label: 'Shell', model: 'for_printing/outlet/outlet_shell.stl' }],
      hardware: [{ count: 2, item: 'M3 × 55 mm screw' }, { count: 2, item: 'M3 hex nut' }]
    },

    { key: 'cup', name: 'Cup', model: 'for_printing/cup.stl', color: 'yellow', stl: 'for_printing/cup.stl', '3mf': '3mf/cups.3mf' },

    // Each is its base parts (base.obj: the shell, the marks on top, and the
    // spring) and a knob (with its arrow). Hiding the shell leaves the knob
    // on its spring.
    {
      key: 'dial', name: 'Dial', '3mf': '3mf/dial.3mf',
      base: { model: 'for_visualization/dial/base.obj', stl: 'for_printing/dial_zip/dial_base.zip' },
      variation: 'Knob geometry',
      variants: [
        { label: 'Flat knob', model: 'for_visualization/dial/knob_flat.obj', stl: 'for_printing/dial_zip/dial_knob_flat.stl' },
        { label: 'Round knob', model: 'for_visualization/dial/knob_round.obj', stl: 'for_printing/dial_zip/dial_knob_round.stl' }
      ],
      toggles: [{ label: 'Shell', model: 'for_visualization/dial/base.obj', except: 'Body1:1' }],   // Body1:1: the spring
      hardware: [{ count: 4, item: 'M3 × 15 mm screw' }, { count: 4, item: 'M3 hex nut' }]
    },
    {
      key: 'dial-push-down-to-turn', name: 'Dial (push down to turn)', '3mf': '3mf/dial_push_down_to_turn.3mf',
      base: { model: 'for_visualization/dial_push_down_to_turn/base.obj', stl: 'for_printing/dial_push_down_to_turn_zip/dial_push_base.zip' },
      variation: 'Knob geometry',
      variants: [
        { label: 'Flat knob', model: 'for_visualization/dial_push_down_to_turn/knob_flat.obj', stl: 'for_printing/dial_push_down_to_turn_zip/dial_push_knob_flat.stl' },
        { label: 'Round knob', model: 'for_visualization/dial_push_down_to_turn/knob_round.obj', stl: 'for_printing/dial_push_down_to_turn_zip/dial_push_knob_round.stl' }
      ],
      toggles: [{ label: 'Shell', model: 'for_visualization/dial_push_down_to_turn/base.obj', except: ['Body1:4', 'Body1:5'] }],   // the spring's two halves
      hardware: [{ count: 4, item: 'M3 × 15 mm screw' }, { count: 4, item: 'M3 hex nut' }],
      orientation: [{ image: 'print_orientations/dial_push_spring.png', label: 'Print orientation of the spring' }]
    },
    {
      key: 'dial-snap-to-position', name: 'Dial (snap to position)', '3mf': '3mf/dial_snap_to_position.3mf',
      base: { model: 'for_visualization/dial_snap_to_position/base.obj', stl: 'for_printing/dial_snap_to_position_zip/dial_snap_base.zip' },
      variation: 'Knob geometry',
      variants: [
        { label: 'Flat knob', model: 'for_visualization/dial_snap_to_position/knob_flat.obj', stl: 'for_printing/dial_snap_to_position_zip/dial_snap_knob_flat.stl' },
        { label: 'Round knob', model: 'for_visualization/dial_snap_to_position/knob_round.obj', stl: 'for_printing/dial_snap_to_position_zip/dial_snap_knob_round.stl' }
      ],
      toggles: [{ label: 'Shell', model: 'for_visualization/dial_snap_to_position/base.obj', except: 'Body1' }],   // Body1: the spring
      hardware: [{ count: 4, item: 'M3 × 15 mm screw' }, { count: 4, item: 'M3 hex nut' }]
    },

    // One STL per part. The covers and springs are white, the rest gray. A
    // door handle and a doorknob go on the same shaft, so they share a slot.
    // Shown turned 90° about +z: the default view ([45, 35.26]) moved -90°.
    {
      key: 'doorknob-module', name: 'Doorknob module', '3mf': '3mf/doorknob_module.3mf', color: 'gray', view: [-45, 35.26],
      tips: [PRINT_TIPS.springs],
      base: {
        model: ['for_visualization/doorknob_module/doorknob_module_base/doorknob_module_top.stl', 'for_visualization/doorknob_module/doorknob_module_base/doorknob_module_bottom.stl'],
        color: 'white', stl: 'for_printing/doorknob_module_zip/doorknob_module_base.zip'
      },
      groups: [
        {
          variation: 'Rotation force', color: 'white',
          variants: [
            { label: '5mm spring', model: 'for_visualization/doorknob_module/doorknob_module_spring_5mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_module_spring_5mm.stl' },
            { label: '7.5mm spring', model: 'for_visualization/doorknob_module/doorknob_module_spring_7.5mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_module_spring_7.5mm.stl' },
            { label: '10mm spring', model: 'for_visualization/doorknob_module/doorknob_module_spring_10mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_module_spring_10mm.stl' }
          ]
        },
        {
          variation: 'Amount of rotation to unlock',
          // Each is a gear and a latch, shown 0.5 mm (0.05 cm) lower than in CAD
          offset: [0, 0, -0.5],
          variants: [
            { label: '40°', model: ['for_visualization/doorknob_module/doorknob_module_40_deg_variant/doorknob_module_gear_40_deg.stl', 'for_visualization/doorknob_module/doorknob_module_40_deg_variant/doorknob_module_latch_40_deg.stl'], stl: 'for_printing/doorknob_module_zip/doorknob_module_40_deg_variant.zip' },
            { label: '48°', model: ['for_visualization/doorknob_module/doorknob_module_48_deg_variant/doorknob_module_gear_48_deg.stl', 'for_visualization/doorknob_module/doorknob_module_48_deg_variant/doorknob_module_latch_48_deg.stl'], stl: 'for_printing/doorknob_module_zip/doorknob_module_48_deg_variant.zip' },
            { label: '60°', model: ['for_visualization/doorknob_module/doorknob_module_60_deg_variant/doorknob_module_gear_60_deg.stl', 'for_visualization/doorknob_module/doorknob_module_60_deg_variant/doorknob_module_latch_60_deg.stl'], stl: 'for_printing/doorknob_module_zip/doorknob_module_60_deg_variant.zip' },
            { label: '72°', model: ['for_visualization/doorknob_module/doorknob_module_72_deg_variant/doorknob_module_gear_72_deg.stl', 'for_visualization/doorknob_module/doorknob_module_72_deg_variant/doorknob_module_latch_72_deg.stl'], stl: 'for_printing/doorknob_module_zip/doorknob_module_72_deg_variant.zip' },
            { label: '80°', model: ['for_visualization/doorknob_module/doorknob_module_80_deg_variant/doorknob_module_gear_80_deg.stl', 'for_visualization/doorknob_module/doorknob_module_80_deg_variant/doorknob_module_latch_80_deg.stl'], stl: 'for_printing/doorknob_module_zip/doorknob_module_80_deg_variant.zip' }
          ]
        },
        {
          variation: 'Door handle geometry', slot: 'grip',
          variants: [
            { label: 'Handle 1', model: 'for_visualization/doorknob_module/door_handle_1.stl', stl: 'for_printing/doorknob_module_zip/door_handle_1.stl' },
            { label: 'Handle 2', model: 'for_visualization/doorknob_module/door_handle_2.stl', stl: 'for_printing/doorknob_module_zip/door_handle_2.stl' }
          ]
        },
        {
          variation: 'Doorknob geometry', slot: 'grip',
          variants: [
            { label: 'Doorknob 1, 60mm diameter', model: 'for_visualization/doorknob_module/doorknob_1_60mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_1_60mm.stl' },
            { label: 'Doorknob 1, 55mm diameter', default: true, model: 'for_visualization/doorknob_module/doorknob_1_55mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_1_55mm.stl' },
            { label: 'Doorknob 1, 50mm diameter', model: 'for_visualization/doorknob_module/doorknob_1_50mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_1_50mm.stl' },
            { label: 'Doorknob 2, 60mm diameter', model: 'for_visualization/doorknob_module/doorknob_2_60mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_2_60mm.stl' },
            { label: 'Doorknob 2, 55mm diameter', model: 'for_visualization/doorknob_module/doorknob_2_55mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_2_55mm.stl' },
            { label: 'Doorknob 2, 50mm diameter', model: 'for_visualization/doorknob_module/doorknob_2_50mm.stl', stl: 'for_printing/doorknob_module_zip/doorknob_2_50mm.stl' }
          ]
        }
      ],
      toggles: [
        { label: 'Top cover', model: 'for_visualization/doorknob_module/doorknob_module_base/doorknob_module_top.stl' },
        { label: 'Bottom cover', model: 'for_visualization/doorknob_module/doorknob_module_base/doorknob_module_bottom.stl' }
      ],
      // The covers' six screws, and two from the spring's hub through the
      // gear into the doorknob or handle. On the door, the four corner
      // screws are longer (see the door).
      hardware: [{ count: 2, item: 'M3 × 15 mm screw' }, { count: 6, item: 'M3 × 25 mm screw' }, { count: 8, item: 'M3 hex nut' }],
      assembly: [
        { video: 'doorknob_assembly_1.mp4', label: 'Part 1' },
        { video: 'doorknob_assembly_2.mp4', label: 'Part 2' }
      ]
    },

    // Base parts: Body1 is the bottom, Body1:1 the friction spring, Body1:2
    // the top cover. Each variant is its gear and deadbolt.
    {
      key: 'lock-module', name: 'Lock module', '3mf': '3mf/lock_module.3mf',
      base: { model: 'for_visualization/lock_module/base.obj', stl: 'for_printing/lock_module_zip/lock_base.zip' },
      variation: 'Amount of rotation to unlock',
      variants: [
        { label: '90°', model: 'for_visualization/lock_module/90_deg.obj', stl: 'for_printing/lock_module_zip/lock_90_deg_variant.zip' },
        { label: '180°', model: 'for_visualization/lock_module/180_deg.obj', stl: 'for_printing/lock_module_zip/lock_180_deg_variant.zip' },
        { label: '270°', model: 'for_visualization/lock_module/270_deg.obj', stl: 'for_printing/lock_module_zip/lock_270_deg_variant.zip' },
        { label: '360°', model: 'for_visualization/lock_module/360_deg.obj', stl: 'for_printing/lock_module_zip/lock_360_deg_variant.zip' }
      ],
      toggles: [{ label: 'Top cover', model: 'for_visualization/lock_module/base.obj', body: 'Body1:2' }],
      note: 'Requires key 1',
      // On the door, the four corner screws are longer (see the door)
      hardware: [{ count: 2, item: 'M3 × 15 mm screw' }, { count: 4, item: 'M3 × 20 mm screw' }, { count: 6, item: 'M3 hex nut' }]
    },

    // Its .obj shows the lock and doorknob modules on it; the download is
    // the door and its frame. Body1:11 is the door, Body1:12 and Body1:13
    // the frame's two halves (door_frame_1.stl, door_frame_2.stl)
    {
      key: 'door', name: 'Door', model: 'for_visualization/door.obj', stl: 'for_printing/door.zip', '3mf': '3mf/door.3mf',
      tips: [PRINT_TIPS.large],
      toggles: [{ label: 'Door frame', model: 'for_visualization/door.obj', body: ['Body1:12', 'Body1:13'] }],
      // The modules hang under the door, so their corner screws also go
      // through it: these replace them and go into the modules' own nuts
      hardware: [
        { label: 'Door frame', items: [{ count: 4, item: 'M3 × 30 mm screw' }, { count: 4, item: 'M3 hex nut' }] },
        { label: 'Hinges', items: [{ count: 2, item: 'M3 × 55 mm screw' }, { count: 2, item: 'M3 nyloc nut' }] },
        { label: 'Doorknob module (replaces its 4 corner screws)', items: [{ count: 2, item: 'M3 × 20 mm screw' }, { count: 2, item: 'M3 × 30 mm screw' }] },
        { label: 'Lock module (replaces its 4 corner screws)', items: [{ count: 2, item: 'M3 × 20 mm screw' }, { count: 2, item: 'M3 × 25 mm screw' }] }
      ],
      assemblyTips: ['Use nyloc nuts for the hinges, and don\'t tighten them fully, or the door won\'t be able to rotate around the hinges.']
    },

    // The .obj's colors are its parts' own (its .mtl)
    {
      key: 'ethernet-plug-and-slot', name: 'Ethernet plug and slot', model: 'for_visualization/ethernet_plug_and_slot.obj', stl: 'for_printing/ethernet_plug_and_slot.zip', '3mf': '3mf/ethernet_plug_and_slot.3mf',
      toggles: [{ label: 'Shell', model: 'for_visualization/ethernet_plug_and_slot.obj', body: 'Body1:1' }],   // Body1:1: the black shell around the five slots
      hardware: [{ count: 5, item: 'M3 × 30 mm screw' }, { count: 5, item: 'M3 hex nut' }],
      orientation: [{ image: 'print_orientations/ethernet_plug.png', label: 'Print orientation of the Ethernet plug' }]
    },

    { key: 'usb-stick-1', name: 'USB stick 1', model: 'for_printing/usb_stick/usb_1.stl', color: 'gray', stl: 'for_printing/usb_stick/usb_1.stl', '3mf': '3mf/usb_sticks.3mf',
      tips: ['Make sure there are no supports inside the USB connector.'],
      orientation: [{ image: 'print_orientations/usb_stick_1.png' }] },
    { key: 'usb-stick-2', name: 'USB stick 2', model: 'for_printing/usb_stick/usb_2.stl', color: 'gray', stl: 'for_printing/usb_stick/usb_2.stl', '3mf': '3mf/usb_sticks.3mf',
      tips: ['Make sure there are no supports inside the USB connector.'],
      orientation: [{ image: 'print_orientations/usb_stick_2.png' }] },
    { key: 'usb-stick-3', name: 'USB stick 3', model: 'for_printing/usb_stick/usb_3.stl', color: 'gray', stl: 'for_printing/usb_stick/usb_3.stl', '3mf': '3mf/usb_sticks.3mf',
      tips: ['Make sure there are no supports inside the USB connector.'],
      orientation: [{ image: 'print_orientations/usb_stick_3.png' }] },
    { key: 'usb-stick-4', name: 'USB stick 4', model: 'for_printing/usb_stick/usb_4.stl', color: 'gray', stl: 'for_printing/usb_stick/usb_4.stl', '3mf': '3mf/usb_sticks.3mf',
      tips: ['Make sure there are no supports inside the USB connector.'],
      orientation: [{ image: 'print_orientations/usb_stick_4.png' }] },

    // Base parts: the center and the shell. The springs sit inside the
    // shell: hide it to see them.
    {
      key: 'usb-slot', name: 'USB slot', '3mf': '3mf/usb_slot.3mf', color: 'white',
      base: {
        model: ['for_visualization/usb_slot/usb_slot_base/usb_slot_center.stl', 'for_visualization/usb_slot/usb_slot_base/usb_slot_shell.stl'],
        stl: 'for_printing/usb_slot_zip/usb_slot_base.zip'
      },
      variation: 'Insertion force',
      variants: [
        { label: '0.2mm indent spring', model: 'for_visualization/usb_slot/usb_slot_spring_0.2mm_indent.stl', stl: 'for_printing/usb_slot_zip/usb_slot_spring_0.2mm_indent.stl' },
        { label: '0.4mm indent spring', model: 'for_visualization/usb_slot/usb_slot_spring_0.4mm_indent.stl', stl: 'for_printing/usb_slot_zip/usb_slot_spring_0.4mm_indent.stl' },
        { label: '0.6mm indent spring', model: 'for_visualization/usb_slot/usb_slot_spring_0.6mm_indent.stl', stl: 'for_printing/usb_slot_zip/usb_slot_spring_0.6mm_indent.stl' }
      ],
      toggles: [{ label: 'Shell', model: 'for_visualization/usb_slot/usb_slot_base/usb_slot_shell.stl' }],
      hardware: [{ count: 2, item: 'M3 × 25 mm screw' }, { count: 2, item: 'M3 hex nut' }],
      orientation: [{ image: 'print_orientations/usb_slot_center_and_spring.png', label: 'Print orientation of the center piece and spring' }]
    },

    { key: 'fastener-bin', name: 'Fastener bin', model: 'for_printing/fasteners/fastener_bin.stl', color: 'yellow', stl: 'for_printing/fasteners/fastener_bin.stl', '3mf': '3mf/fasteners/fastener_bin.3mf' },
    { key: 'hanging-board', name: 'Hanging board', model: 'for_printing/hanging_board.stl', color: 'yellow', stl: 'for_printing/hanging_board.stl', '3mf': '3mf/hanging_board.3mf' },
    { key: 'key-1', name: 'Key 1', model: 'for_printing/keys/key_1.stl', color: 'gray', stl: 'for_printing/keys/key_1.stl', '3mf': '3mf/keys_and_keyring.3mf' },
    { key: 'key-2', name: 'Key 2', model: 'for_printing/keys/key_2.stl', color: 'gray', stl: 'for_printing/keys/key_2.stl', '3mf': '3mf/keys_and_keyring.3mf' },
    { key: 'key-3', name: 'Key 3', model: 'for_printing/keys/key_3.stl', color: 'gray', stl: 'for_printing/keys/key_3.stl', '3mf': '3mf/keys_and_keyring.3mf' },
    { key: 'key-fob', name: 'Key fob', model: 'for_printing/keys/key_fob.stl', color: 'black', stl: 'for_printing/keys/key_fob.stl', '3mf': '3mf/keys_and_keyring.3mf' },   // color from the STL file; not confirmed
    { key: 'keyring', name: 'Keyring', model: 'for_printing/keys/keyring.stl', color: 'gray', stl: 'for_printing/keys/keyring.stl', '3mf': '3mf/keys_and_keyring.3mf' },    // color from the STL file; not confirmed

    // A lightbulb has one STL for each choice of geometry and amount of
    // rotation to tighten: its combinations
    {
      key: 'lightbulb-1', name: 'Lightbulb 1', color: 'white',
      tips: PRINT_TIPS.threads,
      groups: [
        { variation: 'Lightbulb geometry', variants: [{ label: '55mm diameter' }, { label: '60mm diameter' }, { label: '65mm diameter' }] },
        { variation: 'Amount of rotation to tighten', variants: [{ label: '2 revolutions' }, { label: '2.5 revolutions' }, { label: '3 revolutions' }, { label: '3.5 revolutions' }, { label: '4 revolutions' }] }
      ],
      combinations: [
        { variants: ['55mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_55mm_2_rev.3mf' },
        { variants: ['55mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_55mm_2.5_rev.3mf' },
        { variants: ['55mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_55mm_3_rev.3mf' },
        { variants: ['55mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_55mm_3.5_rev.3mf' },
        { variants: ['55mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_55mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_55mm_4_rev.3mf' },
        { variants: ['60mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_60mm_2_rev.3mf' },
        { variants: ['60mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_60mm_2.5_rev.3mf' },
        { variants: ['60mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_60mm_3_rev.3mf' },
        { variants: ['60mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_60mm_3.5_rev.3mf' },
        { variants: ['60mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_60mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_60mm_4_rev.3mf' },
        { variants: ['65mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_65mm_2_rev.3mf' },
        { variants: ['65mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_65mm_2.5_rev.3mf' },
        { variants: ['65mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_65mm_3_rev.3mf' },
        { variants: ['65mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_65mm_3.5_rev.3mf' },
        { variants: ['65mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_1/lightbulb_1_65mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_1/lightbulb_1_65mm_4_rev.3mf' }
      ]
    },
    {
      key: 'lightbulb-2', name: 'Lightbulb 2', color: 'white',
      tips: PRINT_TIPS.threads,
      groups: [
        { variation: 'Lightbulb geometry', variants: [{ label: '45mm diameter' }, { label: '50mm diameter' }, { label: '55mm diameter' }] },
        { variation: 'Amount of rotation to tighten', variants: [{ label: '2 revolutions' }, { label: '2.5 revolutions' }, { label: '3 revolutions' }, { label: '3.5 revolutions' }, { label: '4 revolutions' }] }
      ],
      combinations: [
        { variants: ['45mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_45mm_2_rev.3mf' },
        { variants: ['45mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_45mm_2.5_rev.3mf' },
        { variants: ['45mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_45mm_3_rev.3mf' },
        { variants: ['45mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_45mm_3.5_rev.3mf' },
        { variants: ['45mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_45mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_45mm_4_rev.3mf' },
        { variants: ['50mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_50mm_2_rev.3mf' },
        { variants: ['50mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_50mm_2.5_rev.3mf' },
        { variants: ['50mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_50mm_3_rev.3mf' },
        { variants: ['50mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_50mm_3.5_rev.3mf' },
        { variants: ['50mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_50mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_50mm_4_rev.3mf' },
        { variants: ['55mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_55mm_2_rev.3mf' },
        { variants: ['55mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_55mm_2.5_rev.3mf' },
        { variants: ['55mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_55mm_3_rev.3mf' },
        { variants: ['55mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_55mm_3.5_rev.3mf' },
        { variants: ['55mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_2/lightbulb_2_55mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_2/lightbulb_2_55mm_4_rev.3mf' }
      ]
    },
    {
      key: 'lightbulb-3', name: 'Lightbulb 3', color: 'white',
      tips: PRINT_TIPS.threads,
      groups: [
        { variation: 'Lightbulb geometry', variants: [{ label: '70mm diameter' }, { label: '80mm diameter' }, { label: '90mm diameter' }] },
        { variation: 'Amount of rotation to tighten', variants: [{ label: '2 revolutions' }, { label: '2.5 revolutions' }, { label: '3 revolutions' }, { label: '3.5 revolutions' }, { label: '4 revolutions' }] }
      ],
      combinations: [
        { variants: ['70mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_70mm_2_rev.3mf' },
        { variants: ['70mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_70mm_2.5_rev.3mf' },
        { variants: ['70mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_70mm_3_rev.3mf' },
        { variants: ['70mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_70mm_3.5_rev.3mf' },
        { variants: ['70mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_70mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_70mm_4_rev.3mf' },
        { variants: ['80mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_80mm_2_rev.3mf' },
        { variants: ['80mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_80mm_2.5_rev.3mf' },
        { variants: ['80mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_80mm_3_rev.3mf' },
        { variants: ['80mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_80mm_3.5_rev.3mf' },
        { variants: ['80mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_80mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_80mm_4_rev.3mf' },
        { variants: ['90mm diameter', '2 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_90mm_2_rev.3mf' },
        { variants: ['90mm diameter', '2.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_90mm_2.5_rev.3mf' },
        { variants: ['90mm diameter', '3 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_90mm_3_rev.3mf' },
        { variants: ['90mm diameter', '3.5 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_90mm_3.5_rev.3mf' },
        { variants: ['90mm diameter', '4 revolutions'], model: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_3/lightbulb_3_90mm_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_3/lightbulb_3_90mm_4_rev.3mf' }
      ]
    },
    {
      key: 'lightbulb-slot', name: 'Lightbulb slot', color: 'gray',
      tips: PRINT_TIPS.threads,
      variation: 'Amount of rotation to tighten',
      variants: [
        { label: '2 revolutions', model: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_2_rev.stl', stl: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_2_rev.stl', '3mf': '3mf/lightbulb/lightbulb_slot/lightbulb_slot_2_rev.3mf' },
        { label: '2.5 revolutions', model: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_2.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_2.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_slot/lightbulb_slot_2.5_rev.3mf' },
        { label: '3 revolutions', model: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_3_rev.stl', stl: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_3_rev.stl', '3mf': '3mf/lightbulb/lightbulb_slot/lightbulb_slot_3_rev.3mf' },
        { label: '3.5 revolutions', model: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_3.5_rev.stl', stl: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_3.5_rev.stl', '3mf': '3mf/lightbulb/lightbulb_slot/lightbulb_slot_3.5_rev.3mf' },
        { label: '4 revolutions', model: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_4_rev.stl', stl: 'for_printing/lightbulb/lightbulb_slot/lightbulb_slot_4_rev.stl', '3mf': '3mf/lightbulb/lightbulb_slot/lightbulb_slot_4_rev.3mf' }
      ]
    },

    {
      key: 'platform', name: 'Platform', model: 'for_visualization/platform.obj', stl: 'for_printing/platform.zip', '3mf': '3mf/platform.3mf',
      tips: [PRINT_TIPS.large],
      toggles: [{ label: 'Acrylic sheet', model: 'for_visualization/platform.obj', body: 'Body1' }],   // Body1: the 10 in × 10 in sheet on top
      hardware: [
        { count: 1, item: '10in x 10in acrylic sheet (like [this](https://a.co/d/0fWvHZPB))' },
        { count: 2, item: 'M3 × 45 mm screw' }, { count: 2, item: 'M3 hex nut' }
      ]
    },

    { key: 'ruler', name: 'Ruler', model: 'for_printing/ruler.stl', color: 'gray', stl: 'for_printing/ruler.stl', '3mf': '3mf/ruler.3mf' },
    {
      key: 'screw', name: 'Screw', '3mf': '3mf/fasteners/screws.3mf', color: 'gray',
      tips: [...PRINT_TIPS.threads, PRINT_TIPS.strength],
      variation: 'Screw length',
      variants: [
        { label: '6.5 revolutions', model: 'for_printing/fasteners/screw_6.5_rev.stl', stl: 'for_printing/fasteners/screw_6.5_rev.stl' },
        { label: '7.5 revolutions', model: 'for_printing/fasteners/screw_7.5_rev.stl', stl: 'for_printing/fasteners/screw_7.5_rev.stl' }
      ]
    },
    {
      key: 'bolt', name: 'Bolt', '3mf': '3mf/fasteners/bolts.3mf', color: 'gray',
      tips: [...PRINT_TIPS.threads, PRINT_TIPS.strength],
      variation: 'Bolt length',
      variants: [
        { label: '7 revolutions', model: 'for_printing/fasteners/bolt_7_rev.stl', stl: 'for_printing/fasteners/bolt_7_rev.stl' },
        { label: '8 revolutions', model: 'for_printing/fasteners/bolt_8_rev.stl', stl: 'for_printing/fasteners/bolt_8_rev.stl' },
        { label: '9 revolutions', model: 'for_printing/fasteners/bolt_9_rev.stl', stl: 'for_printing/fasteners/bolt_9_rev.stl' },
        { label: 'Long', model: 'for_printing/fasteners/bolt_long.stl', stl: 'for_printing/fasteners/bolt_long.stl' }
      ]
    },
    { key: 'nut', name: 'Nut', model: 'for_printing/fasteners/nut.stl', color: 'gray', stl: 'for_printing/fasteners/nut.stl', '3mf': '3mf/fasteners/nuts.3mf',
      tips: PRINT_TIPS.threads },
    { key: 'allen-key', name: 'Allen key', model: 'for_printing/tools/allen_key.stl', color: 'black', stl: 'for_printing/tools/allen_key.stl', '3mf': '3mf/tools.3mf',
      tips: [PRINT_TIPS.strength] },
    { key: 'screwdriver', name: 'Screwdriver', model: 'for_printing/tools/screwdriver.stl', color: 'black', stl: 'for_printing/tools/screwdriver.stl', '3mf': '3mf/tools.3mf',
      tips: [PRINT_TIPS.strength],
      orientation: [{ image: 'print_orientations/screwdriver.png' }] },
    { key: 'wrench', name: 'Wrench', model: 'for_printing/tools/wrench.stl', color: 'gray', stl: 'for_printing/tools/wrench.stl', '3mf': '3mf/tools.3mf',
      tips: [PRINT_TIPS.strength] },

    {
      key: 'toy-assembly-block', name: 'Toy assembly block', color: 'yellow',
      model: ['for_visualization/toy_assembly_block/toy_assembly_block_top.stl', 'for_visualization/toy_assembly_block/toy_assembly_block_bottom.stl'],
      stl: 'for_printing/toy_assembly_block.zip', '3mf': '3mf/toy_assembly_block.3mf',
      toggles: [
        { label: 'Top', model: 'for_visualization/toy_assembly_block/toy_assembly_block_top.stl' },
        { label: 'Bottom', model: 'for_visualization/toy_assembly_block/toy_assembly_block_bottom.stl' }
      ]
    },

    { key: 'chopstick', name: 'Chopstick', model: 'for_printing/utensils/chopstick.stl', color: 'gray', stl: 'for_printing/utensils/chopstick.stl', '3mf': '3mf/utensils/chopsticks.3mf',
      orientation: [{ image: 'print_orientations/chopstick.png' }] },
    { key: 'fork', name: 'Fork', model: 'for_printing/utensils/fork.stl', color: 'gray', stl: 'for_printing/utensils/fork.stl', '3mf': '3mf/utensils/forks.3mf',
      orientation: [{ image: 'print_orientations/fork.png' }] },
    { key: 'knife', name: 'Knife', model: 'for_printing/utensils/knife.stl', color: 'gray', stl: 'for_printing/utensils/knife.stl', '3mf': '3mf/utensils/knives.3mf',
      orientation: [{ image: 'print_orientations/knife.png' }] },
    { key: 'spoon', name: 'Spoon', model: 'for_printing/utensils/spoon.stl', color: 'gray', stl: 'for_printing/utensils/spoon.stl', '3mf': '3mf/utensils/spoons.3mf',
      orientation: [{ image: 'print_orientations/spoon.png' }] },
    { key: 'utensil-bin-horizontal', name: 'Utensil bin (horizontal)', model: 'for_printing/utensils/utensil_bin_horizontal.stl', color: 'yellow', stl: 'for_printing/utensils/utensil_bin_horizontal.stl', '3mf': '3mf/utensils/utensil_bin_horizontal.3mf' },
    { key: 'utensil-bin-vertical', name: 'Utensil bin (vertical)', model: 'for_printing/utensils/utensil_bin_vertical.stl', color: 'yellow', stl: 'for_printing/utensils/utensil_bin_vertical.stl', '3mf': '3mf/utensils/utensil_bin_vertical.3mf' }
  ]
});

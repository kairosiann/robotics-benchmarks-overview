/* =====================================================
   config/tasks/index.js — which task files the page loads
   =====================================================
   One entry per file in config/tasks/ (without ".js").
   Order doesn't matter: tasks are sorted by id on the page.
   To add a task:  node tools/new-task.mjs "Task name"
   (creates the file from _template.js and adds it here).
   Challenge tasks (c01-…, c02-…) go in this list too:
                   node tools/new-task.mjs "Task name" --challenge
   ===================================================== */

defineTaskList([
  '01-grasp-target-key-from-keychain',
  '02-retrieve-single-utensil-from-bin',
  '03-retrieve-single-fastener-from-bin',
  '04-retrieve-top-cup-from-stack',
  '05-retrieve-single-card-from-deck',
  '06-pick-up-object-from-platform',
  '07-collect-utensils',
  '08-collect-fasteners',
  '09-hang-object',
  '10-place-utensil-into-bin',
  '11-in-hand-repose',
  '12-in-hand-grasp-transition',
  '13-tighten-screw-with-allen-key',
  '14-loosen-screw-with-allen-key',
  '15-tighten-screw-with-screwdriver',
  '16-loosen-screw-with-screwdriver',
  '17-tighten-nut-with-wrench',
  '18-loosen-nut-with-wrench',
  '19-put-bottle-cap-onto-bottle',
  '21-thread-nut-onto-screw',
  '22-insert-key-into-lock',
  '23-plug-in-charger',
  '24-place-card-into-holder',
  '25-stack-cups',
  '26-plug-in-ethernet',
  '27-plug-in-usb',
  '28-turn-key-to-unlock-door',
  '29-turn-doorknob-to-open-door',
  '30-turn-door-handle-to-open-door',
  '31-turn-dial-to-target-position',
  '32-install-light-bulb',
  'c01-assemble-toy-block',
  'c02-add-keys-to-keyring',
  'c03-unlock-and-open-door',
  'c04-sort-utensils',
  'c05-sort-fasteners',
]);

/* =====================================================
   config/skills.js — the skill sections, in page order
   =====================================================
   key             short id that tasks use in their `skills` list
   id              short label for the skill (S01, S02, …), shown
                   beside long-horizon tasks that use it
   label           the skill's label on its tile (Skill 01, …);
                   the id if left out
   name            the skill's title
   definition      one sentence describing the skill (not shown on
                   the main page at the moment)
   representative  ids of the tasks whose videos play for this
                   skill on the main page (its tile), in order.
                   Every task
                   is on the All tasks page (tasks.html) regardless.
                   Leave it out to use the first
                   `defaultRepresentative` tasks (by id) instead.

   challenge       the Dexterous Long-Horizon Tasks, shown after the
                   skills with all of their tasks (a band of cards
                   under the tiles, introduced by a paragraph in
                   index.html; `name` labels them for screen
                   readers). Tasks with
                   `challenge: true` appear only here. `order` lists
                   ids to show first, in that order; the rest follow
                   by id.
   ===================================================== */

defineSkills({
  defaultRepresentative: 2,

  skills: [
    {
      key: 'thin',
      id: 'S01',
      label: 'Skill 01',
      name: 'Grasping Thin or Small Objects',
      definition: 'Obtaining stable grasps onto cards, keys, and small items that often require precise positioning of the robot end-effector to establish the grasp.',
      representative: ['06'],
    },
    {
      key: 'multi',
      id: 'S02',
      label: 'Skill 02',
      name: 'Grasping Multiple Objects',
      definition: 'Acquiring and holding several objects at once, keeping the ones already picked secure while reaching for the next.',
      representative: ['08', '07'],
    },
    {
      key: 'clutter',
      id: 'S03',
      label: 'Skill 03',
      name: 'Grasping from Clutter',
      definition: 'Locating a target among loosely or tightly packed neighbors and separating it without disturbing the rest of the scene.',
      representative: ['01', '02', '04'],
    },
    {
      key: 'inhand',
      id: 'S04',
      label: 'Skill 04',
      name: 'In-hand Repositioning',
      definition: 'Changing an object\'s grasp type or in-hand pose after pickup so it is ready for the step that follows.',
      representative: ['11', '12'],
    },
    {
      key: 'extrinsic',
      id: 'S05',
      label: 'Skill 05',
      name: 'Extrinsic Contact Control',
      definition: 'Regulating the contact between a held object and the environment, as when wiping a board or driving a screw with an Allen key.',
      representative: ['13', '15', '17'],
    },
    {
      key: 'place',
      id: 'S06',
      label: 'Skill 06',
      name: 'Placing under Constraints',
      definition: 'Releasing an object under tight constraints: onto a hook, onto a stack, or into an open pocket of an already cluttered region.',
      representative: ['09', '10', '24'],
    },
    {
      key: 'artic',
      id: 'S07',
      label: 'Skill 07',
      name: 'Articulated Object Manipulation',
      definition: 'Operating doors, knobs, handles, and other jointed mechanisms whose motion is kinematically constrained.',
      representative: ['28', '29', '31'],
    },
    {
      key: 'insert',
      id: 'S08',
      label: 'Skill 08',
      name: 'Insertion and Alignment',
      definition: 'Aligning and fully seating parts under tight tolerances, including the thread-engagement phase of threaded assembly.',
      representative: ['27', '21', '32'],
    },
  ],

  challenge: {
    id: 'C',
    name: 'Dexterous Long-Horizon Tasks',
    order: ['C01', 'C02', 'C03', 'C04', 'C05'],
  },
});

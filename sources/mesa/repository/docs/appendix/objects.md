# Objects

All objects live under `mesa/sim/assets/objects`, downloaded from
[Hugging Face](https://huggingface.co/datasets/albertwilcox/mesa-assets) by `scripts/setup/download_assets.py`
(run by `scripts/setup.sh`). The download serves both the single-arm (MESA) and dual-arm (BiMESA) benchmarks; the
BiMESA-only `objaverse/` and `aigen_objs/` trees can be skipped with `--no-bimesa`.

## Asset layout

```
mesa/sim/assets/objects/
  robocasa/        robocasa_ai/     # FORMAT M  — single-arm MESA
  objaverse/       aigen_objs/      # FORMAT R  — dual-arm BiMESA
  articulated_objects/              # fixtures (drawers/cabinets), both benchmarks
  objaverse_objects/ stable_hope_objects/ stable_scanned_objects/ turbosquid_objects/
```

The RoboCasa365 grasp objects appear in **two formats**, because the two
benchmarks were generated against different processings of the same source
meshes and each published dataset must reproduce exactly:

- **FORMAT M** (`robocasa/`, `robocasa_ai/`) — single-arm. Each `model.xml`
  carries `bottom_site`/`top_site`/`horizontal_radius_site`; loaded by
  `RobocasaObjectMesa(BaseObject)`; per-instance size fixes live in
  `SCALE_MAP_MESA`/`SCALE_MAP_AI_MESA` in `robocasa_objects.py`. **Frozen** —
  reproduces the published single-arm tasks (including category-OOD pick objects
  such as `salt_shaker`, which exist only here). Do not regenerate it.
- **FORMAT R** (`objaverse/`, `aigen_objs/`) — dual-arm. Each `model.xml`
  carries a single `reg_bbox` box geom; loaded by `RobocasaObjectBimesa(MJCFObject)`
  (the native RoboCasa365 adapter; also aliased as `RobocasaObject`). **Canonical**
  — new objects go here.

The two trees share the same source meshes but differ in collision
decomposition, bounding-box representation, and scale handling, so they are kept
separate rather than merged. They register under the same
`robocasa_<instance>` / `robocasa_ai_<instance>` keys, but into a format-keyed
registry (`FORMAT_OBJECTS_DICT`): both FORMAT M and FORMAT R are registered at
import (`mesa/sim/envs/objects/robocasa_objects.py`). The active format is chosen
per-environment by robot type — `bimesa` (FORMAT R) for the dual-arm YAM
environments, `mesa` (FORMAT M) otherwise (`bddl_base_domain.py`) — so a single
checkout serves both benchmarks.

## Adding objects

Use the helper, which copies the asset into the right tree, validates that it
loads, and prints the `object_info.py` snippet to register:

```bash
uv run scripts/utility/add_robocasa_object.py --src /path/to/robocasa365/<category>/<instance> --category <category>
```

By default it adds a **FORMAT R** (canonical) object under `objaverse/` (or
`aigen_objs/` with `--aigen`). Pass `--mesa` to also emit the single-arm
FORMAT-M variant under `robocasa/` (sites synthesized from the bounding box;
visualize before relying on it). After adding, register the category in
`mesa/sim/envs/objects/object_info.py` (and `mesa/sim/task_gen/object_categories.py`
if it should be sampled during task generation). To add the remaining RoboCasa
AI-generated objects in bulk, download them with RoboCasa's script and drop them
into `aigen_objs/` (FORMAT R) — they are then immediately available.

## Visualizing Objects

During development it can be useful to quickly visualize objects. You can do this using the `scripts/visualize.py` script. For example, to visualize an apple from the RoboCasa objects, you can run:

```bash
uv run scripts/visualize.py --object-names robocasa_apple_0
```

If you'd like to interact with the object, perhaps to determine whether it is easily graspable, you can use the `--device` flag to connect a Quest controller or a SpaceMouse:

```bash
uv run scripts/visualize.py --object-names robocasa_apple_0 --device quest
```

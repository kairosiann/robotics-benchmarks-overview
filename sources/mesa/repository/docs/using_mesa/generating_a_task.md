# Building task suites

In this section we describe our infrastructure for building task suites and some helpful tools we've open-sourced.

## Task Generation API and CLI

We provide a CLI for quickly generating single tasks and sample Python scripts for generating large task suites.

In the examples below we describe some important configuration options. To see the full list of options, run the help commands below or refer to the task generation argument dataclasses in `mesa.sim.task_gen`.

### Method 1: at the command line

The easiest way to quickly play around with our framework is to use the task generator CLI. You can view the available task skeletons with:

```bash
uv run scripts/generate_tasks.py --help
```

You can view the available arguments for a particular `[task]` with:

```bash
uv run scripts/generate_tasks.py <skeleton_name> --help
```

Example:

```bash
uv run scripts/generate_tasks.py pick_and_place \
  --task-suite-name mesa-demo \
  --language-instruction "put the apple on the plate" \
  --task-id apple_plate_on \
  --pick-objects apple \
  --dest-object plate \
  --num-train-variants 50 \
  --num-eval-variants 50 \
  --add-distractors \
  --make-source
```

Notice that we specify the pick and destination object categories, which are defined in `mesa.sim.task_gen.object_categories`, rather than the object instances. We add `--add-distractors` to enable distractor object generation. We also specify a task ID, an optional argument which should uniquely identify the task within the task suite. Manually specifying a task ID is important in large settings like `mesa-spatial`, where different tasks may have identical language instructions.

This example will create JSON task definitions in `mesa/task_suites/bddl_files/mesa-demo/apple_plate_on`. Within this folder, there will be a `source` folder containing variants to use during data collection, which iterate through the set of `apple` assets. There will also be a `train` folder containing 50 variants of the task with random sets of distractor objects (because we specified `--num-train-variants 50`) and a similar `eval` folder for evaluation variants (because we specified `--num-eval-variants 50`). Run the commands from the repository root; `--output-dir` overrides the default root.

### Method 2: generating a full task suite programmatically

For generating large task suites, we recommend using the Python API rather than CLI. This is cleaner for large task suites and
enables you to guarantee that distractor objects correspond to other tasks in your training or evaluation sets.

The high-level workflow is:

1. Instantiate one or more task config dictionaries.
2. Call `generate_from_config(...)` to materialize task variants on disk.

Below is a minimal example for generating one task programmatically:

```python
from mesa.sim.task_gen import generate_from_config, PickAndPlaceTaskConfig

TASK_SUITE_NAME = "mesa-demo-single"
OUTPUT_DIR = "mesa/task_suites/bddl_files"

config = PickAndPlaceTaskConfig(
    task_suite_name=TASK_SUITE_NAME,
    task_id="apple_plate_on",
    language_instruction="put the apple on the plate",
    pick_objects=["apple"],
    dest_object="plate",
    arena_name="mimiclabs_lab1_tabletop_manipulation",
    num_train_variants=100,
    output_dir=OUTPUT_DIR,
    make_source=True,
    add_distractors=True,
)
generate_from_config(config, verbose=True)
```

This creates task definitions in `mesa/task_suites/bddl_files/mesa-demo-single/apple_plate_on`, with source variants and 100 train variants.

For large suites, use the demo scripts in `scripts/demo` as the canonical pattern:

- `make_training_tasks.py` generates the `MESA-all` training suite.
- `make_eval_tasks.py` generates the benchmark evaluation suites.

While these scripts are more complicated, they largely follow the same higher-level workflow described above. In this code block, they create mappings from unique task IDs to all possible task configurations:

```python
# In this, we generate all possible task configurations given our objects and existing skeletons.
# Refer to the functions below for details on instantiating these.
config_map = {}
all_meta = {}

task_generators = [
    make_pick_and_place_tasks,
    make_articulated_primitives,
    make_articulated_multistep_tasks,
]
for gen_fn in task_generators:
    configs, meta = gen_fn(DEFAULT_CONFIG)
    config_map.update(configs)
    all_meta.update(meta)
```

Next, they filter to the task IDs for the task suite they are generating:

```python
# Load the task IDs for task suite we are trying to generate.
eval_sets = ["mesa-70", "mesa-instance", "mesa-spatial", "mesa-category", "mesa-composite"]
task_ids = sum([EVAL_SETS[eval_set_name]["tasks"] for eval_set_name in eval_sets], [])

# Construct a map of valid distractors for each task. This allows us to ensure that for
# each variant of a task, there is some task in task list such that its task relevant
# objects are present in the distractor objects.
valid_distractor_map = make_valid_distractor_map(task_ids, all_meta)
all_configs = [config_map[task_id] for task_id in task_ids]
num_tasks = len(all_configs)
```

Notably, the `make_valid_distractor_map` function uses the meta data we gattered above to create a mapping from grasp and destination objects to distractor objects such that those objects appear together in some of the tasks in the task set we are generating. This is to ensure that for each variant of a task, there is some other task in the task list such that its task relevant objects are present in the distractor objects, ensuring the necessity of language following.

Finally, they generate the tasks (with optional parallelism):
```python
for config in all_configs:
    generate_from_config(
        config, 
        valid_distractor_map=valid_distractor_map, 
        verbose=True,
    )
```

## Utilities

### Visualize and Interact with Generated Tasks

You can visualize and interact with generated tasks using the `scripts/visualize.py` script.

 - Visualize a task: 
 ```bash
uv run scripts/visualize.py --task-json-path mesa/task_suites/bddl_files/<task_suite_name>/<task_id>/train/000.json
```
 - Visualize a task and interact with it using a Quest controller (before doing this, make sure to set up your data collection devices [here](../getting_started/setup_devices.md)): 
 ```bash
uv run scripts/visualize.py --task-json-path mesa/task_suites/bddl_files/<task_suite_name>/<task_id>/train/000.json --device quest
```

### Capture reset frames to verify tasks

After generating tasks, quickly verify initial states with:

```bash
uv run scripts/capture_reset_frames.py \
  --file-names mesa/task_suites/bddl_files/<task_suite_name>/<task_name>/train/000.json \
  --num-resets 50 \
  --output-video vids/<task_name>_reset_frames.mp4
```

This is useful for spotting unstable placements and object collisions before
data collection.

### Generate Initial States for Deterministic Evaluation

In order to deterministically compare policies and reduce unnecessary sources of bias, we recommend generating and saving a fixed set of initial states for each variant in each task. 
You can do this using the `scripts/generate_init_states.py` script. The default generator output is already under `mesa/task_suites/bddl_files`. If you used a different output directory, copy the suite there before generating initial states.

```bash
uv run scripts/generate_init_states.py --task-suite-name <task_suite_name>
```

When you are satisfied with the init states you've generated, move them into `mesa/task_suites/init_states/<task_suite_name>`. Assuming you've correctly specified your evaluation set in the `EVAL_SETS` dictionary in `mesa.task_suites.task_sets`, the inference server will automatically use the init states you've generated.

### BDDL Files

MESA stores parsed BDDL-like task definitions as JSON files per variant:

- `source/*.json`: source demos
- `train/*.json`: training/eval variants

We use JSON instead of BDDL files because it is easier to parse and interpret.

Each file includes fixtures, regions, objects, initial state, goal state,
demonstration states, and language instruction.


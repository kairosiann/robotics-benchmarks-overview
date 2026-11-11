# Task Suite Organization

MESA's task generation architecture is organized around task suites, train sets and eval sets.
At a high level, task suites are sets of tasks outputted by our task generation pipeline. 
Train and eval sets are more granular sets which are subsets of task suites. We set the repository
up this way because we found it easier to generate large sets of tasks and then manually specify
subsets than to generate a bunch of separate subsets.

Generated task suites are stored under:

```text
mesa/task_suites/bddl_files/<task_suite_name>/<task_name>/
```

Each task folder typically contains some subset of the following folders:

- `source/`: source variants used for demo collection.
- `train/`: generated variants used for training.
- `eval/`: generated variants used for evaluation.
- `*.json`: per-variant parsed BDDL problems (for example `000.json`) contained in the `source`, `train` and `eval` folders.

## Training and Evaluation Sets

After generating task suites, we organize them into training and evaluation sets.
These sets are defined in `mesa.task_suites.task_sets`. 

Evaluation sets are used mainly by our evaluation server scripts to know which tasks to evaluate on. Note that to correctly evaluate on an evaluation set, it's important to copy its corresponding BDDL files into the `mesa/task_suites/bddl_files` directory and initial states into the `mesa/task_suites/init_states` directory.

Training sets are used in several of our data processing scripts, often to more easily select subsets of larger task suites to select when composing large datasets. For example, this occurs in `scripts/data/merge_lerobot_datasets.py`.
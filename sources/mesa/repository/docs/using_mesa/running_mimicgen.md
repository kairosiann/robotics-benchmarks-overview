# Running MimicGen

Before running MimicGen, generate a task suite under `mesa/task_suites/bddl_files/`
(the generator's default output directory). If you used a different output
directory, copy the suite there. See [generating a task](generating_a_task.md)
for instructions. You may also need to collect data for the task suite.
See [data collection](data_collection.md) for instructions.

From here, there are three main steps in the MimicGen workflow:
1. Parse the dataset to extract subtask lookup information
2. Generate MimicGen configs for each task in the task suite
3. Generate datasets with those configs

## 0) Download source data

We collected a large source dataset which we used to generate all the data in the MESA-all dataset. If you'd like to generate data without collecting any yourself, you can download it with the following command:

```bash
uv run scripts/mimicgen/download_mesa_source_data.py
```

## 1) Parse the dataset

In order to enable subtask stitching, we need to create a lookup dictionary for source demonstrations based on factors like subtask predicates, and object instances involved in them. To do this, we use the `parse_dataset.py` script. Simply run the following:

```bash
uv run scripts/mimicgen/parse_dataset.py \
  --input-dir data/source/<task_suite_name>
```

## 2) Generate MimicGen configs

Next, we need to generate MimicGen configs for each task in the task suite. To do this, we use the `generate_configs_and_jobs.py` script. Simply run the following:

```bash
uv run scripts/mimicgen/generate_configs_and_jobs.py \
  --task-suite-name <task_suite_name> \
  --stitching \
  --auto-remove-exp
```

This creates config files under:

```text
data/mimicgen_configs/<task_suite_name>/
```

In case you are using data from a different task suite, you'll need to manually specify the source dataset path using the `--source-dataset-path` argument. For example, if you want to use the author-provided source data, you would add `--source-dataset-path data/source/mesa-source`.

For some large data collection jobs, it may be helpful to parallelize across multiple processes (eg to split into multiple jobs in a slurm cluster). You can do this by setting the `--num-parallel-jobs` argument. For example, to run 10 jobs in parallel, you would add `--num-parallel-jobs 10`. Then, in `data/mimicgen_configs/<task_suite_name>/`, you will see a `jobs.sh` file with python commands each generating one tenth of the dataset. If you use this approach, you will need to merge the datasets manually using the `merge_generated_dataset.py` script described in the next section.

## 3) Generate datasets

The final step is to generate the datasets using the `generate_dataset.py` script. The most straightforward way to do this is to run the `jobs.sh` file you created in the previous step, or copy and paste one of the commands in it into a terminal. Alternatively, you can run something like the following:

```bash
uv run scripts/mimicgen/generate_dataset.py \
  --config data/mimicgen_configs/<task_suite_name>/<task_id>.json \
  --auto-remove-exp
```

The generated dataset outputs are written under:

```text
data/gen_data/<task_suite_name>/<task_id>/
```

For debugging, it may be helpful to render the data generation attempts live by adding the `--render` flag.

If you parallelized the data generation as described in the previous section, you can merge the datasets using the `merge_generated_dataset.py` script. Simply run the following for each task in the task suite:

```bash
uv run scripts/mimicgen/merge_generated_dataset.py \
  --config data/mimicgen_configs/<task_suite_name>/<task_id>.json
```

Note that the data coming from MimicGen will be in HDF5 format and may not have the observations you want. See [processing data](processing_data.md) for instructions on how to process the data into the format you want.
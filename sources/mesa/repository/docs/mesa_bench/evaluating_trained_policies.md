# Evaluating Trained Policies

Our evaluation pipeline involves launching separate environment and policy servers, which we describe in detail in the [running the inference server](../using_mesa/running_inference.md) documentation. All released checkpoints are collected on [Hugging Face](https://huggingface.co/collections/albertwilcox/mesa).

| Model | MESA (single-arm) | BiMESA (bimanual) | Policy server |
|---|---|---|---|
| π0 | [mesa-pi0](https://huggingface.co/albertwilcox/mesa-pi0) | [bimesa-pi0](https://huggingface.co/albertwilcox/bimesa-pi0) | openpi-mesa |
| π0-FAST | [mesa-pi0-fast](https://huggingface.co/albertwilcox/mesa-pi0-fast) | [bimesa-pi0-fast](https://huggingface.co/albertwilcox/bimesa-pi0-fast) | openpi-mesa |
| π0.5 | [mesa-pi05](https://huggingface.co/albertwilcox/mesa-pi05) | [bimesa-pi05](https://huggingface.co/albertwilcox/bimesa-pi05) | openpi-mesa |
| GR00T-N1.6 | [mesa-gr00t-n1.6](https://huggingface.co/albertwilcox/mesa-gr00t-n1.6) | [bimesa-gr00t-n1.6](https://huggingface.co/albertwilcox/bimesa-gr00t-n1.6) | mesa-GR00T |

Each checkpoint's model card lists its success rates from the paper.

## OpenPI models

Our `openpi` fork with MESA and BiMESA support is available at [pairlab/openpi-mesa](https://github.com/pairlab/openpi-mesa). Clone it and install it as described in its README, then download a checkpoint and start the policy server from the `openpi-mesa` repository:

OpenPI requires Python 3.11 or newer in a separate environment from MESA.
For its README's editable installation step, use
`uv pip install --python .venv/bin/python -e .`.

```bash
uv run huggingface-cli download albertwilcox/mesa-pi05 --local-dir checkpoints/mesa-pi05
uv run scripts/serve_policy.py \
  --port 8001 \
  policy:checkpoint \
  --policy.config=pi05_mesa \
  --policy.dir=checkpoints/mesa-pi05
```

Each checkpoint has a matching config:

| Checkpoint | `--policy.config` |
|---|---|
| `mesa-pi0` / `mesa-pi0-fast` / `mesa-pi05` | `pi0_mesa` / `pi0_fast_mesa_70` / `pi05_mesa` |
| `bimesa-pi0` / `bimesa-pi0-fast` / `bimesa-pi05` | `pi0_bimesa` / `pi0_fast_bimesa` / `pi05_bimesa` |

`serve_policy.py` translates the observations sent by the MESA evaluation server into the model's input format, choosing the single-arm or bimanual format from the config name (override with `--policy-format {mesa,bimesa}`).

## GR00T models

GR00T-N1.6 checkpoints are served with [pairlab/mesa-GR00T](https://github.com/pairlab/mesa-GR00T), a minimal inference-only fork of Isaac-GR00T. Clone it, run `uv sync`, then:

```bash
uv run huggingface-cli download albertwilcox/bimesa-gr00t-n1.6 --local-dir checkpoints/bimesa-gr00t-n1.6
uv run python gr00t/eval/serve_mesa.py --model-path checkpoints/bimesa-gr00t-n1.6 --port 8001
```

The camera names, state layout and action format are read from the checkpoint, so the same command serves both the MESA and BiMESA checkpoints. The GR00T weights are released under NVIDIA's non-commercial license for GR00T-N1.6.

## Running the evaluation

With a policy server running, start the evaluation server from this repository, pointing it to the same port.

Single-arm MESA checkpoints:

```bash
uv run scripts/eval_server_parallel.py \
  --port 8001 \
  --eval-set-name mesa-70 \
  --num-rollouts-per-task 50 \
  --controller-type joint_pos
```

BiMESA checkpoints use the dual-arm robots, cameras and state keys:

```bash
uv run scripts/eval_server_parallel.py \
  --port 8001 \
  --eval-set-name bimesa-id \
  --num-rollouts-per-task 50 \
  --controller-type joint_pos \
  --robots ReverseMountedYam ReverseMountedYam \
  --camera-names egocentric robot0_eye_in_hand robot1_eye_in_hand \
  --state-keys robot0_joint_pos robot0_gripper_jaw_width robot1_joint_pos robot1_gripper_jaw_width
```

Change `--eval-set-name` to evaluate on the other suites (`mesa-spatial`, `mesa-instance`, `mesa-composite`, `mesa-category`; `bimesa-spatial`, `bimesa-instance`, `bimesa-composite`, `bimesa-object`). See [Running inference](../using_mesa/running_inference.md) for the full set of options and outputs.

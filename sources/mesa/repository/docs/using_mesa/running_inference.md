# Running Inference

The recommended way to run inference is to use the `eval_server.py` script. This script connects as a websocket client to a separately started policy server and runs rollouts on the evaluation set, outputting videos and statistics. With this approach, you can interface with your policy after writing a minimal policy server wrapper, avoiding the necessity to merge MESA's dependencies into your own.


## Running the evaluation server

To start the evaluation server, run the following command:

```bash
uv run scripts/eval_server.py \
  --exp-name <exp_name> \
  --variant-name <variant_name> \
  --eval-set-name <eval_set_name> \
  --num-rollouts-per-task <num_rollouts_per_task> \
  --controller-type <controller_type> \
  --port <port>
```

Some notable arguments:
- `--exp-name` and `--variant-name`: These optional arguments are used to determine the output directory for the evaluation results. If provided, the results will be saved in `experiments/<eval_set_name>/<exp_name>/<variant_name>/`. If not provided, the results will be saved in `experiments/<eval_set_name>/<date>/<time>/`.
- `--eval-set-name`: The name of the evaluation set to run.
- `--num-rollouts-per-task`: The number of rollouts to run per task. This will iterate through all the task variant BDDL files before repeating any.
- `--controller-type`: The type of controller to use. Valid options are `osc_pose` and `joint_pos`. If using delta actions, you'll need to add `--control-delta`.
- `--port`: The policy-server port to connect to.
- `--task-filter`: Optional task names to evaluate; other tasks are excluded.
- `--eval-split`: Task-definition split to use (`eval` by default).
- `--max-steps` and `--per-subtask-extra-steps`: Initial action budget and additional actions allowed per completed subtask.

The sequential `eval_server.py` script is useful for debugging, when speed is not a concern. For large evaluation jobs, you should use the parallel `eval_server_parallel.py` script which has the same interface and outputs but runs rollouts in parallel.


## Start a policy server

Next, implement a policy server that ingests observations and returns actions. MESA provides `mesa.serving.websocket_policy_server.WebsocketPolicyServer`, based on [openpi](https://github.com/Physical-Intelligence/openpi). Its websocket client comes from `openpi-client` (included in `third_party/openpi-client`). A sample policy server which outputs random actions is provided in `scripts/demo_policy_server.py`, which you can run with

```bash
uv run scripts/demo_policy_server.py --port <port>
```

For example, to run a policy server that outputs random delta end effector pose actions, you would run

```bash
uv run scripts/demo_policy_server.py \
  --port 8001 \
  --controller-type osc_pose \
  --control-delta
```

in one terminal and

```bash
uv run scripts/eval_server.py \
  --port 8001 \
  --eval-set-name mesa-70 \
  --num-rollouts-per-task 10 \
  --controller-type osc_pose \
  --control-delta \
  --render
```
in another.

For real models, run your model-specific websocket server and point MESA to it. For example, our policy server for pi models is provided in [our fork of the openpi repo](https://github.com/pairlab/openpi-mesa/blob/main/scripts/serve_policy.py), and our GR00T-N1.6 server in [pairlab/mesa-GR00T](https://github.com/pairlab/mesa-GR00T/blob/main/gr00t/eval/serve_mesa.py).

## Bimanual (BiMESA) evaluation

The [BiMESA suites](../mesa_bench/task_suites_bimanual.md) run through the same evaluation server with the dual-arm I/O contract. As in the single-arm setting, each rollout restores a fixed initial state from `mesa/task_suites/init_states/bimesa`, downloaded by `./scripts/setup.sh` (or `uv run python scripts/setup/download_init_states.py`), so results are comparable across methods. Add the dual-arm robots, controller, cameras, and state keys:

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

Set `--eval-set-name` to one of `bimesa-id`, `bimesa-spatial`, `bimesa-instance`, `bimesa-object`, or `bimesa-composite`. The 14-D observation state concatenates each arm's joint positions and gripper width, matching the 14-D action. On the policy side, the [openpi-mesa](https://github.com/pairlab/openpi-mesa) `serve_policy.py` uses the BiMESA observation format automatically for `*_bimesa` configs (or explicitly with `--policy-format bimesa`); this is a policy-server option, not an evaluation-server option.

For more information on running inference with our trained models, please refer to the [evaluating trained policies](../mesa_bench/evaluating_trained_policies.md) page.
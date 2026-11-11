# Installation

This project uses `uv` for dependency and environment management. The installation instructions have been tested on Ubuntu 24.04.

## 1) Install uv

Follow the official `uv` installation instructions [found here](https://docs.astral.sh/uv/getting-started/installation/).

Verify your installation:

```bash
uv --version
```

## 2) Clone MESA

```bash
git clone https://github.com/pairlab/mesa-env.git mesa
cd mesa
```

## 3) Install project dependencies

From the repository root, sync the environment:

```bash
uv sync
```

If you need to export data in LeRobot format, install the optional LeRobot dependencies:

```bash
uv sync --extra lerobot
```

## 4) Run setup scripts

Run the setup helper:

```bash
./scripts/setup.sh
```

It runs three scripts from `scripts/setup/`, which you can also run individually:

1. `setup_robosuite_macros.py` configures robosuite's image convention, which MESA requires.
2. `download_assets.py` downloads the simulation assets (scenes, textures, fixtures and objects, about 13 GB) from [Hugging Face](https://huggingface.co/datasets/albertwilcox/mesa-assets) into `mesa/sim/assets/`. If you only need single-arm MESA, `./scripts/setup.sh --no-bimesa` skips the objects used only by BiMESA (about 8 GB).
3. `download_init_states.py` downloads the fixed evaluation initial states for all MESA and BiMESA suites from [Hugging Face](https://huggingface.co/datasets/albertwilcox/mesa-init-states) into `mesa/task_suites/init_states/`.

To re-download assets or initial states, run the corresponding script with `--overwrite`:

```bash
uv run python scripts/setup/download_assets.py [--no-bimesa] [--overwrite]
uv run python scripts/setup/download_init_states.py [--suites mesa bimesa] [--overwrite]
```
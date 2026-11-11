from __future__ import annotations

import argparse
from typing import Sequence

import tyro

from mesa.sim.task_gen import (
    available_task_keys,
    get_task_registration,
    instantiate_task,
)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for generating task suites by task key."""

    parser = argparse.ArgumentParser(
        description="Generate task suites using the registered task generators.",
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show this help message and exit.",
    )
    parser.add_argument(
        "task_key",
        choices=available_task_keys(),
        nargs="?",
        default=None,
        help="Registered task key identifying which generator to use.",
    )
    args, remaining = parser.parse_known_args(argv)
    if args.help and args.task_key is None:
        parser.print_help()
        return 0
    if args.task_key is None:
        parser.print_help()
        return 2
    registration = get_task_registration(args.task_key)
    if args.help or "--help" in remaining or "-h" in remaining:
        tyro.cli(registration.config_cls, args=["--help"])
        return 0
    config = tyro.cli(registration.config_cls, args=remaining)
    task = instantiate_task(config)
    task.generate()
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))

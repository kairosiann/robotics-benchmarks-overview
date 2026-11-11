import json
import os
import random

import mesa
from mesa.task_suites.task_sets import EVAL_SETS

ALL_INSTRUCTIONS = json.load(open(os.path.join(mesa.__path__[0], 'task_suites', 'task_to_instr_mapping.json'), 'r'))
ALL_TASKS = list(ALL_INSTRUCTIONS.keys())


def get_task_suite_folder() -> str:
    return os.path.join(mesa.__path__[0], "task_suites", "bddl_files")

def get_init_state_folder() -> str:
    return os.path.join(mesa.__path__[0], "task_suites", "init_states")

def get_task_suite_path(task_suite_name: str) -> str:
    return os.path.join(get_task_suite_folder(), task_suite_name)

class EvalSet:
    def __init__(self, eval_set_name=None, train=False, split=None):
        self.eval_set_name = eval_set_name
        if eval_set_name in EVAL_SETS:
            self.task_suite_name = EVAL_SETS[eval_set_name]["task_suite_name"]
            self.tasks = EVAL_SETS[eval_set_name]["tasks"]
        else:
            self.task_suite_name = eval_set_name
            self.tasks = os.listdir(get_task_suite_path(self.task_suite_name))
        self.task_suite_path = get_task_suite_path(self.task_suite_name)
        self.n_tasks = len(self.tasks)
        self.train = train
        if split is not None:
            self.split = split
        else:
            self.split = "train" if train else "eval"
        self._parsed_problems_cache = {}

    def get_random_task_instruction(self, benchmark_name: str = "mesa") -> str:
        if benchmark_name == "mesa":
            all_tasks = ALL_TASKS
        else:
            all_tasks = self.tasks
        task_idx = random.randint(0, len(all_tasks) - 1)
        return ALL_INSTRUCTIONS[all_tasks[task_idx]]

    def get_task_instruction(self, idx: int, instance_idx: int = 0) -> str:
        parsed_problem = self.get_parsed_problem(idx, instance_idx)
        return " ".join(parsed_problem["language_instruction"])
    
    def get_task_names(self) -> list[str]:
        return self.tasks

    def get_parsed_problem(self, task_idx: int, instance_idx: int) -> dict:
        if (task_idx, instance_idx) in self._parsed_problems_cache:
            return self._parsed_problems_cache[(task_idx, instance_idx)]
        root = os.environ.get("MESA_BDDL_DIR")
        if root:
            bddl_file = os.path.join(
                root, self.task_suite_name, self.tasks[task_idx], self.split,
                f"{instance_idx:03d}.json",
            )
        else:
            task_folder = os.path.join(self.task_suite_path, self.tasks[task_idx], self.split)
            bddl_file = os.path.join(task_folder, f"{instance_idx:03d}.json")
        with open(bddl_file, 'r') as f:
            parsed_problem: dict = json.load(f)
        self._parsed_problems_cache[(task_idx, instance_idx)] = parsed_problem
        return parsed_problem

    def get_parsed_problems(self, task_name: str) -> list[dict]:
        if task_name not in self.tasks:
            raise ValueError(f"Unknown task name: {task_name}")

        task_idx = self.tasks.index(task_name)
        task_folder = os.path.join(self.task_suite_path, task_name, self.split)

        if not os.path.isdir(task_folder):
            raise FileNotFoundError(f"Task folder not found: {task_folder}")

        parsed_problems = []
        for filename in sorted(os.listdir(task_folder)):
            instance_idx = int(os.path.splitext(filename)[0])
            parsed_problems.append(self.get_parsed_problem(task_idx, instance_idx))
        return parsed_problems

    def get_init_state(self, task_idx: int, instance_idx: int) -> dict | None:
        root = os.environ.get("MESA_INIT_STATES_DIR")
        if root:
            init_state_file = os.path.join(root, self.eval_set_name, self.tasks[task_idx], f"{instance_idx:03d}.json")
            with open(init_state_file, 'r') as f:
                return json.load(f)
        init_state_file = os.path.join(get_init_state_folder(), self.task_suite_name, self.tasks[task_idx], f"{instance_idx:03d}.json")
        if os.path.exists(init_state_file):
            with open(init_state_file, 'r') as f:
                init_state: dict = json.load(f)
            return init_state
        else:
            return None




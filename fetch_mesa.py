"""Build source-backed MESA and BiMESA task records from the official release."""

import ast
import concurrent.futures
import json
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from fetch_sources import Page
from task_details import slug


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "sources" / "mesa"
REPOSITORY = "pairlab/mesa-env"
PROJECT = "https://www.pair.toronto.edu/MESA/"
PAPER = "https://arxiv.org/html/2611.05567v1"
DOCS = PROJECT + "documentation/"


def download(url):
    request = Request(url, headers={"User-Agent": "RoboticsBenchmarkCatalog/1.0"})
    with urlopen(request, timeout=45) as response:
        return response.read()


def snapshot():
    location = EVIDENCE / "snapshot.json"
    if location.exists():
        return json.loads(location.read_text())
    info = json.loads(download(f"https://api.github.com/repos/{REPOSITORY}"))
    tree = json.loads(download(f'https://api.github.com/repos/{REPOSITORY}/git/trees/{info["default_branch"]}?recursive=1'))
    if tree.get("truncated"):
        raise ValueError("MESA repository tree was truncated")
    data = {"repository": REPOSITORY, "branch": info["default_branch"], "commit": tree["sha"], "retrieved": "2026-11-11", "tree": tree["tree"]}
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(data, indent=2))
    return data


def source(data, path):
    target = EVIDENCE / "repository" / path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(download(f'https://raw.githubusercontent.com/{REPOSITORY}/{data["commit"]}/{path}'))
    return target.read_text(errors="replace")


def web_source(name, url):
    target = EVIDENCE / "web" / (name + ".html")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(download(url))
    html = target.read_text(errors="replace")
    page = Page(html)
    (EVIDENCE / "web" / (name + ".txt")).write_text("\n".join(page.text))
    return page


def main():
    data = snapshot()
    print(data["commit"], len(data["tree"]), flush=True)
    paths = [item["path"] for item in data["tree"] if item["type"] == "blob"]
    selected = [
        path for path in paths
        if not path.startswith("third_party/") and (
            path.endswith((".bddl", ".py", ".yaml", ".yml", ".md"))
            or path.endswith("/000.json")
            or path.endswith(".json") and "/bddl_files/" not in path
        )
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda path: source(data, path), selected))
    print("Retained", len(selected), "official source files", flush=True)
    web_source("project", PROJECT)
    web_source("paper", PAPER)
    build_records(data)


def build_records(data):
    """Extract every unique official evaluation task; preserve representative reset JSON."""
    registry_path = "mesa/task_suites/task_sets.py"
    registry_tree = ast.parse(source(data, registry_path))
    assignments = {node.targets[0].id: node.value for node in registry_tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    evaluations = ast.literal_eval(assignments["EVAL_SETS"])
    train_sets = {}
    for key, value in zip(assignments["TRAIN_SETS"].keys, assignments["TRAIN_SETS"].values):
        fields = dict(zip([ast.literal_eval(k) for k in value.keys], value.values))
        train_sets[ast.literal_eval(key)] = ast.literal_eval(fields["tasks"])
    pinned = f'https://github.com/{REPOSITORY}/blob/{data["commit"]}/'
    checker_path = "mesa/sim/envs/problems/mimiclabs_tabletop_manipulation.py"
    predicates_path = "mesa/sim/envs/predicates/predicates.py"
    checker_tree = ast.parse(source(data, checker_path))
    checker_methods = {}
    for node in ast.walk(checker_tree):
        if isinstance(node, ast.FunctionDef) and node.name in {
            "_check_success", "_get_subtask_progress", "_get_distractor_task_completion", "_eval_predicate"
        }:
            checker_methods[node.name] = ast.get_source_segment(source(data, checker_path), node)
    predicate_tree = ast.parse(source(data, predicates_path))
    predicate_code = {node.name.lower(): ast.get_source_segment(source(data, predicates_path), node)
                      for node in predicate_tree.body if isinstance(node, ast.ClassDef) and node.name in {"On", "In", "Open", "Close"}}
    memberships = {}
    for suite, config in evaluations.items():
        for task in config["tasks"]:
            memberships.setdefault((config["task_suite_name"], task), []).append(suite)
    records = []
    for (kind, name), suites in memberships.items():
        benchmark = "MESA" if kind == "mesa" else "BiMESA"
        path = f"mesa/task_suites/bddl_files/{kind}/{name}/eval/000.json"
        problem = json.loads(source(data, path))
        instruction = problem["language_instruction"]
        if isinstance(instruction, list):
            instruction = " ".join(instruction)
        instance_paths = [item["path"] for item in data["tree"]
                          if item["type"] == "blob" and item["path"].startswith(path.rsplit("/", 1)[0] + "/")]
        assert len(instance_paths) == 50, (name, len(instance_paths))
        assets = {object_id: asset for field in ("fixtures", "objects")
                  for asset, object_ids in problem.get(field, {}).items() for object_id in object_ids}
        def entity(value):
            asset = assets.get(value)
            return f"{value} ({asset})" if asset and asset != value else value
        def explain(expr):
            relation = expr[0]
            if relation in {"and", "or"}:
                return (" AND " if relation == "and" else " OR ").join(explain(part) for part in expr[1:])
            if relation in {"on", "in"}:
                return f"{entity(expr[1])} is {relation} {entity(expr[2])}"
            if relation in {"open", "close"}:
                return f"{entity(expr[1])} is {'open' if relation == 'open' else 'closed'}"
            return " ".join(expr)
        goal = problem["goal_state"]
        used_predicates = sorted({part[0] for part in goal[1:]})
        exact = "goal_state = " + json.dumps(goal, indent=2)
        exact += "\n\n" + checker_methods["_check_success"]
        exact += "\n\n" + "\n\n".join(predicate_code[k] for k in used_predicates)
        robot = "A single Panda arm" if kind == "mesa" else "Two ReverseMountedYam arms"
        init = {key: problem[key] for key in ("fixtures", "objects", "regions", "initial_state")}
        all_assets = ", ".join(sorted(problem["objects"]))
        fixture_assets = ", ".join(sorted(problem["fixtures"]))
        source_note = ("One row per unique official evaluation task across the five generalization splits. "
                       "The setup and exact initial conditions show released eval/000.json; each task has 50 released reset definitions "
                       "with varying objects/distractors and initial states. Additional reset files are enumerated in the cached repository tree. "
                       "Demonstration-state predicates and distractor-goal predicates are diagnostic outputs; primary binary success uses goal_state.")
        if "handoff" in name or any(part[0] in {"grasp_left", "grasp_right"} for part in problem.get("demonstration_states", [])):
            source_note += " Cross-arm grasp/handoff predicates appear in demonstration_states; final-goal success alone does not certify the entire handoff sequence."
        observation = ("Paper policy inputs: RGB images from the left-shoulder and robot0 wrist cameras, robot0 joint positions and gripper jaw width, plus the language instruction. "
                       if kind == "mesa" else
                       "Paper policy inputs: RGB from the egocentric and both wrist cameras, each arm's joint positions and gripper jaw width, plus the language instruction. ")
        observation += "Simulator object states and predicates are used by the checker rather than supplied as policy object-state inputs in the reported protocol."
        rec = {
            "id": slug(benchmark) + "--" + slug(name), "benchmark": benchmark, "family": "MESA",
            "suite": " / ".join(suites), "suites": suites, "name": name, "title": instruction[:1].upper() + instruction[1:],
            "description": instruction, "instruction": instruction, "goal": exact, "source": pinned + path,
            "setting": "Simulation", "setup_summary": f"{robot} manipulates objects on a tabletop with distractors. Representative eval/000.json objects: {all_assets}. Fixtures: {fixture_assets}. Exact initial relations and placement regions are preserved below; this is one of 50 resets.",
            "setup_source": pinned + path, "observation": observation, "observation_scope": "benchmark",
            "observation_source": DOCS + "mesa_bench/evaluating_trained_policies.html",
            "grading_summary": "Success requires: " + explain(goal) + ". The checker evaluates these predicates against current simulator state. 'On' calls check_ontop; 'in' requires both contact and containment; open/close use the articulated object's state checks.",
            "grading_scope": "task", "grading_evidence": "The task-specific goal_state is checked by _check_success in the tabletop problem class. Subtask predicates and alternative distractor completions are logged separately. Paper evaluation runs 50 rollouts per task and reports success rate; language-following rate additionally compares instructed successes against distractor-task completions.",
            "evaluation_source": pinned + checker_path + "#L196", "predicate_source": pinned + predicates_path,
            "media": [{"type": "video", "url": PROJECT + "static/videos/mesa_teaser.mp4", "label": "Official MESA/BiMESA benchmark overview; not a task-specific rollout", "scope": "benchmark"},
                      {"type": "image", "url": PROJECT + "static/images/paper/teaser.png", "label": "Official benchmark setup and generalization overview", "scope": "benchmark"}],
            "media_source": PROJECT, "source_snapshot": data["commit"], "retrieved": data["retrieved"],
            "initial_conditions": json.dumps(init, indent=2), "goal_state": goal,
            "object_assets": assets, "demonstration_states": problem.get("demonstration_states", []),
            "distractor_goal_specs": problem.get("distractor_goal_specs", []), "instance_count": len(instance_paths),
            "definition_sample": "eval/000.json", "source_note": source_note,
            "catalog_scope": "285 unique released evaluation tasks: MESA 140 and BiMESA 145. Auxiliary training task-name lists are retained separately in the source manifest; they do not each have a released evaluation reset definition.",
            "protocol_source": PAPER,
        }
        if kind == "mesa":
            rec["task_gallery_source"] = DOCS + "mesa_bench/policy_videos.html"
        records.append(rec)
    records.sort(key=lambda record: (record["benchmark"], record["name"]))
    assert len(records) == 285 and len({record["id"] for record in records}) == 285
    assert sum(record["benchmark"] == "MESA" for record in records) == 140
    available = {task for kind, task in memberships if kind == "mesa"}
    manifest = {
        "repository": REPOSITORY, "commit": data["commit"], "retrieved": data["retrieved"],
        "evaluation_sets": evaluations, "training_task_name_lists": train_sets,
        "evaluation_task_count": len(records), "reset_definition_count": sum(record["instance_count"] for record in records),
        "training_names_without_released_evaluation_definition": {suite: [task for task in tasks if task not in available] for suite, tasks in train_sets.items()},
        "scope_note": "The official evaluation registry and released reset definitions establish the 285 concrete benchmark task records. TRAIN_SETS also includes auxiliary/pretraining names; those names are preserved here without fabricating absent task goals or adding them to the evaluation catalog.",
    }
    (EVIDENCE / "catalog_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "mesa_tasks.json").write_text(json.dumps(records, indent=2) + "\n")
    print("Wrote", len(records), "task records; MESA 140, BiMESA 145", flush=True)


if __name__ == "__main__":
    main()

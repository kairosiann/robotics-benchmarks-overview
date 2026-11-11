"""Build the HARP-Bench catalog from a pinned official repository snapshot."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from fetch_sources import Page


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources" / "harp"
REPOSITORY = "UMass-Embodied-AGI/harp"
PAPER = "https://arxiv.org/html/2611.11123v1"


def fetch(name, url):
    path = SOURCES / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=50) as response:
            path.write_bytes(response.read())
    return path


def fetch_sources():
    tree = json.loads(fetch("repository_tree.json", f"https://api.github.com/repos/{REPOSITORY}/git/trees/main?recursive=1").read_text())
    wanted = [item["path"] for item in tree["tree"] if item["path"].endswith((".py", ".md", ".json", ".jsonl", ".csv", ".yml", ".yaml")) and item["path"].startswith(("docs/", "envs/", "eval_sets/eval_v3_sampled/", "scripts/", "config/"))]
    wanted.append("README.md")
    urls = {path: f"https://raw.githubusercontent.com/{REPOSITORY}/{tree['sha']}/{path}" for path in wanted}
    def download(item):
        path, url = item
        try:
            fetch(path, url)
            return True
        except Exception as error:
            print(path, str(error), flush=True)
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        downloaded = sum(pool.map(download, urls.items()))
    print(f"Retained {downloaded} repository sources at {tree['sha']}", flush=True)
    html = fetch("paper.html", PAPER).read_text()
    (SOURCES / "paper.txt").write_text("\n".join(Page(html).text))
    website = fetch("website.html", "https://harp-bench.vercel.app/").read_text()
    (SOURCES / "website.txt").write_text("\n".join(Page(website).text))
    (SOURCES / "source_urls.json").write_text(json.dumps(urls, indent=2))


def literal_assignment(code, name):
    for node in ast.parse(code).body:
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0] if isinstance(node, ast.Assign) else None
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


CONDITIONS = {
    "cueing": ("Cueing", "Human activity provides the cue for the robot's objective or target."),
    "contribution": ("Contribution", "The human completes part of the task and the robot must finish the remaining work."),
    "interruption": ("Interruption", "The human temporarily holds, inspects or occupies a relevant object, requiring waiting or adaptation before resuming."),
    "copresence": ("Co-presence", "The human performs unrelated nearby work while the robot pursues its manipulation goal."),
    "base": ("No-human base", "The registered base counterpart runs without the human-present task condition."),
}

GRADING = {
    "deliver_to_human": "The evaluation handover checks that the human now holds the released object. The source also defines a different demonstration-collection path with pose and live-grasp checks.",
    "pour_water": "The geometric pouring check requires mug-to-cup horizontal distance at most 0.20 m, mug height at least 0.10 m above the cup rim, and tilt at least 60 degrees. It grades a pose suitable for pouring rather than measuring transferred fluid volume.",
    "oil_bottle_recovery": "The oil bottle must finish near its target, upright within the tilt bound and resting on its support, with a check that it is released.",
    "open_microwave": "The task checks the microwave door opening and condition-specific human load-path state. The source uses a minimum door opening angle of 0.78 radians for its door-open criterion.",
    "stamp_documents": "The document task checks its feed/stamp completion state and the positions of the documents under the task-specific criteria.",
    "take_from_human": "The task checks the offered object's transfer and final placement. The easy and knife-safety variants have distinct support, release and placement bounds in their executable checkers.",
    "categorize": "The task uses condition-specific basket targets, object-center and footprint containment, and resting-state checks to verify sorting.",
    "put_object_cabinet": "The task checks the object's placement inside the drawer using the drawer and object geometry. Human-interaction state is recorded by the task controller.",
    "stack_bowls_three": "The task checks stacked-bowl centers against the base bowl footprint, relative height, and resting-on-stack conditions.",
    "place_bread_in_basket": "The task verifies condition-specific bread placement using basket position, height, resting and release checks.",
    "dump_bin": "The base task counts objects inside the bin using horizontal, rim and floor bounds. Its base threshold is max(1, (num_objects + 1) // 2). Human-present variants add or alter their own conditions.",
    "place_burger_fries": "The task checks the meal objects' condition-specific resting placement on the tray.",
    "place_dual_shoes": "The task checks each required shoe's position inside the shoebox footprint, above its floor and resting there.",
    "place_food_in_skillet": "The task checks skillet position on the cooktop and the food objects resting in the skillet.",
    "blocks_ranking_rgb": "The task checks the colored blocks against target slots, table-support/resting conditions and red-green-blue order.",
    "blocks_ranking_size": "The task checks block target slots, table support/resting and large-medium-small order.",
    "factory": "The factory scenario has its own completion checker for its kit, packing or line-feeding state. Its class and inherited checks are included below.",
}


def class_index():
    classes = {}
    for path in sorted((SOURCES / "envs").rglob("*.py")):
        code = path.read_text()
        try:
            syntax = ast.parse(code)
        except SyntaxError:
            continue
        for node in syntax.body:
            if isinstance(node, ast.ClassDef):
                classes[node.name] = dict(node=node, code=code, path=path.relative_to(SOURCES).as_posix())
    return classes


def method_resolution(classes, name, resolving=None):
    """Resolve the repository's multiple-inheritance method order without imports."""
    resolving = set() if resolving is None else resolving
    if name not in classes or name in resolving:
        return [name]
    resolving = resolving | {name}
    bases = [ast.unparse(base).split(".")[-1] for base in classes[name]["node"].bases]
    sequences = [method_resolution(classes, base, resolving)[:] for base in bases] + [bases[:]]
    result = [name]
    while any(sequences):
        sequences = [sequence for sequence in sequences if sequence]
        head = next((sequence[0] for sequence in sequences if not any(sequence[0] in other[1:] for other in sequences)), None)
        if head is None:
            raise ValueError("Cannot resolve class order for " + name)
        result.append(head)
        for sequence in sequences:
            if sequence[0] == head:
                sequence.pop(0)
    return result


def class_value(classes, order, name):
    for owner in order:
        if owner not in classes:
            continue
        for node in classes[owner]["node"].body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
    return None


def checker_excerpt(classes, order):
    excerpts = []
    included = set()
    pending = ["check_success", "evaluate"]
    # Include inherited implementations as well as overrides, because super()
    # composes the task check with the collision gate and interaction metrics.
    for owner in order:
        if owner not in classes:
            continue
        info = classes[owner]
        methods = {node.name: node for node in info["node"].body if isinstance(node,ast.FunctionDef)}
        for name in ["check_success", "evaluate"]:
            if name in methods:
                node = methods[name]
                key = owner + "." + name
                included.add(key)
                excerpts.append(f"# {info['path']} / {key}\n" + ast.get_source_segment(info["code"], node))
                pending.extend(call.func.attr for call in ast.walk(node) if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id == "self")
        for node in ast.walk(info["node"]):
            if isinstance(node,ast.Call) and ast.unparse(node.func).endswith("TargetSpec"):
                excerpts.append(f"# Target specification in {info['path']}\n" + ast.get_source_segment(info["code"],node))
    # Referenced geometry and target helpers make thresholds inspectable.
    for name in dict.fromkeys(pending):
        if name in {"check_success", "evaluate"}:
            continue
        for owner in order:
            if owner not in classes:
                continue
            info = classes[owner]
            method = next((node for node in info["node"].body if isinstance(node,ast.FunctionDef) and node.name == name),None)
            if method is not None:
                if owner + "." + name not in included:
                    excerpts.append(f"# Helper {info['path']} / {owner}.{name}\n" + ast.get_source_segment(info["code"],method))
                break
    return "\n\n".join(excerpts)


def build_catalog():
    tree = json.loads((SOURCES / "repository_tree.json").read_text())
    revision = tree["sha"]
    base = f"https://github.com/{REPOSITORY}/blob/{revision}/"
    registry = ast.parse((SOURCES / "envs/tasks/registry.py").read_text())
    tuple_node = next(node.value for node in registry.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=="TASK_DESCRIPTORS" for target in node.targets))
    labels = (SOURCES / "envs/tasks/paper_labels.py").read_text()
    benchmark_tasks = literal_assignment(labels,"BENCHMARK_TASKS")
    family_names = literal_assignment(labels,"FAMILY_DISPLAY")
    title_overrides = literal_assignment(labels,"TASK_DISPLAY_OVERRIDES")
    aliases = literal_assignment(labels,"LEGACY_TASK_NAMES")
    rows_by_task = defaultdict(list)
    for line in (SOURCES / "eval_sets/eval_v3_sampled/manifest.jsonl").read_text().splitlines():
        row = json.loads(line)
        rows_by_task[row["task"]].append(row)
    classes = class_index()
    tasks = []
    for descriptor in tuple_node.elts:
        options = {keyword.arg: keyword.value for keyword in descriptor.keywords}
        if ast.unparse(options.get("registration",ast.Constant(value="canonical"))).endswith("COMPATIBILITY"):
            continue
        name = ast.literal_eval(descriptor.args[0])
        cls = ast.unparse(descriptor.args[1])
        task_family = ast.literal_eval(descriptor.args[2])
        condition = descriptor.args[3].attr.lower()
        order = method_resolution(classes,cls)
        instruction = class_value(classes,order,"INSTRUCTION")
        info = classes[cls]
        doc = ast.get_docstring(info["node"]) or ""
        instruction = instruction or doc.split("\n",1)[0] or name.replace("_"," ")
        paper_member = name in benchmark_tasks
        factory = name.startswith("factory_")
        condition_label, behavior = CONDITIONS[condition]
        suite = condition_label if paper_member else "Registered factory extras" if factory else "No-human base"
        title = title_overrides.get(name,family_names.get(task_family,name.replace("_"," ").title()))
        if paper_member:
            title += " — " + condition_label
        elif factory:
            title = name.replace("_"," ").title()
        else:
            title += " — No-human base"
        task_rows = rows_by_task.get(name,[])
        source = base + info["path"]
        condition_note = behavior if paper_member else "This is a registered factory work-cell extra outside the paper's 37 tasks." if factory else behavior
        summary = GRADING.get(task_family,"The task-specific source checker determines completion.")
        if name == "take_from_human_safety":
            summary = "The offered knife must finish inside the knife box's rectangular horizontal bounds and vertical tolerance, with the task's transfer and release conditions satisfied."
        source_note = "Canonical task from the pinned public registry. "
        if paper_member:
            source_note += "The release evaluation uses expert-solvable sampled seeds."
        else:
            source_note += "Registered extra outside the paper's 37-task evaluation subset."
        alias_names = [old for old,new in aliases.items() if new == name]
        media = []
        if paper_member:
            clip = {"cueing":"cueing_loop.mp4?v=20261006-reviewed-exr", "contribution":"contribution_action_loop.mp4?v=20261006-reviewed-exr", "interruption":"interruption_loop.mp4?v=20261006-reviewed-exr", "copresence":"copresence_loop.mp4?v=20261006-copresence-trim"}[condition]
            media.append(dict(type="video",url=urljoin("https://harp-bench.vercel.app/","media/"+clip),label="Official " + condition_label + " condition example",scope="benchmark"))
            poster = {"cueing":"cueing.jpg?v=20261006-reviewed-exr", "contribution":"contribution.jpg?v=20261006-reviewed-exr", "interruption":"interruption.jpg?v=20261006-reviewed-exr", "copresence":"copresence.jpg?v=20261006-copresence-trim"}[condition]
            media.append(dict(type="image",url=urljoin("https://harp-bench.vercel.app/","media/"+poster),label="Official " + condition_label + " example setup",scope="benchmark"))
        observation = "The documented VLA path supplies head-camera and wrist-camera RGB plus robot proprioception (qpos/qpos_abs and end-effector pose). Privileged scripted experts additionally access full task state."
        if paper_member:
            observation += " The release manifest uses 640 × 480 head and right-wrist views."
        task = dict(
            id="harp-bench--"+slug(name), family="HARP-Bench", benchmark="HARP-Bench", suite=suite,
            name=name,title=title,description=instruction+" "+condition_note,instruction=instruction,
            source=source,setting="Simulation",goal=checker_excerpt(classes,order),
            setup_summary=condition_note+" "+(doc.split("\n\n",1)[0] if doc else instruction),
            setup_source=source,
            observation=observation,
            observation_scope="benchmark",observation_source=base+"docs/vla-inference-control-pipeline.md",
            grading_summary=summary+" In the human-present evaluation, any recorded robot-avatar collision makes the episode unsuccessful.",
            grading_scope="task",grading_evidence="Task-specific simulator completion is combined with the shared collision gate. The paper additionally reports collision rate, mean episode minimum separation and the fraction of checked timesteps with separation below 0.10 m. The release logs intrusion at 0.05, 0.10 and 0.20 m. These proximity metrics do not substitute for task success.",
            evaluation_source=base+"envs/base_task.py", media=media,
            human_condition=condition,task_family=task_family,paper_subset=paper_member,
            split="Paper evaluation subset" if paper_member else "Registry outside paper subset",
            aliases=alias_names,entry_scope="Paper task-condition instance" if paper_member else "Registered factory extra" if factory else "Registered no-human base task",
            source_note=source_note,source_revision=revision,snapshot_date="2026-11-11",
            safety_metrics=[
                dict(name="Collision",definition="Fraction of episodes with a recorded robot-avatar collision."),
                dict(name="Minimum separation",definition="Mean over episodes of their minimum recorded robot-avatar distance."),
                dict(name="Proximity violation",definition="Fraction of checked timesteps below 0.10 m separation in the paper."),
                dict(name="Release intrusion metrics",definition="Additional intrusion time and near-miss summaries at 0.05, 0.10 and 0.20 m."),
            ],safety_source=base+"envs/safety_metrics.py",
        )
        if task_rows:
            task["evaluation_instances"] = len(task_rows)
            task["initial_conditions"] = json.dumps(task_rows[0],ensure_ascii=False,indent=2)
            task["setup_source"] = base+"eval_sets/eval_v3_sampled/manifest.jsonl"
            task["episode_step_range"] = [min(row["max_steps"] for row in task_rows),max(row["max_steps"] for row in task_rows)]
        if "no_human_name" in options:
            task["no_human_variant"] = ast.literal_eval(options["no_human_name"])
        tasks.append(task)
    assert len(tasks) == 49 and sum(t["paper_subset"] for t in tasks) == 37
    assert sum(len(t["aliases"]) for t in tasks) == 32
    assert sum(t.get("evaluation_instances",0) for t in tasks) == 3403
    assert all(t["goal"] for t in tasks)
    assert len({t["id"] for t in tasks}) == len(tasks)
    (ROOT / "harp_tasks.json").write_text(json.dumps(tasks,ensure_ascii=False,indent=2))
    (SOURCES / "catalog_notes.json").write_text(json.dumps(dict(
        canonical_tasks=49,compatibility_aliases=32,paper_task_conditions=37,evaluation_rows=3403,
        paper_condition_counts=dict(Counter(t["human_condition"] for t in tasks if t["paper_subset"])),
        source_revision=revision,
        caveats=["Evaluation seeds were selected for privileged-expert solvability.","The remaining registered tasks are nine no-human bases and three factory extras.","Media show condition examples and retain benchmark scope.","The paper's 10 cm proximity convention is distinct from recorded collisions and task completion.","Safety checks are sampled. Brief contacts between checks may be missed.","Pour Water grades mug pose and tilt, not measured liquid transfer."]
    ),indent=2))
    print("HARP catalog",len(tasks),"canonical entries;",sum(t["paper_subset"] for t in tasks),"paper tasks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached",action="store_true",help="Build from retained sources without network access")
    args = parser.parse_args()
    if not args.cached:
        fetch_sources()
    build_catalog()

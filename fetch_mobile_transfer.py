"""Retain and normalize official RMMBench and H2RBench task definitions."""

import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from fetch_sources import Page


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources" / "mobile_transfer"
REPOSITORIES = {"rmm": "mxxq-stack/RMMBench", "h2r": "xiaochy/H2RBench"}
HOMES = {
    "rmm": "https://mxxq-stack.github.io/rmmbench-project/",
    "h2r": "https://davidz2851.github.io/h2rbench.github.io/",
}
PAPERS = {
    "rmm": "https://arxiv.org/html/2610.05414",
    "h2r": "https://arxiv.org/html/2609.24778v3",
}


def fetch(path, url):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        path.write_bytes(urlopen(request, timeout=50).read())
    return path.read_text(errors="replace")


def snapshot(key):
    path = SOURCES / f"{key}_tree.json"
    if path.exists():
        return json.loads(path.read_text())
    info = json.loads(fetch(SOURCES / f"{key}_repo.json", f"https://api.github.com/repos/{REPOSITORIES[key]}"))
    tree = json.loads(fetch(path, f"https://api.github.com/repos/{REPOSITORIES[key]}/git/trees/{info['default_branch']}?recursive=1"))
    if tree.get("truncated"):
        raise ValueError(f"Truncated repository tree for {key}")
    return tree


def raw_path(key, path):
    return SOURCES / key / path


def fetch_raw(key, tree, path):
    return fetch(raw_path(key, path), f"https://raw.githubusercontent.com/{REPOSITORIES[key]}/{tree['sha']}/{path}")


def source_url(key, tree, path, line=None):
    url = f"https://github.com/{REPOSITORIES[key]}/blob/{tree['sha']}/{path}"
    return f"{url}#L{line}" if line else url


def clean(markup):
    return " ".join(" ".join(Page(markup).text).split())


def table_rows(markup):
    return [
        re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S)
        for row in re.findall(r"<tr\b.*?</tr>", markup, re.S)
    ]


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def record(family, name, title, instruction, source, suite, setting):
    return dict(
        id=f"{slug(family)}--{slug(name)}", family=family, benchmark=family,
        name=name, title=title, instruction=instruction, description=instruction,
        source=source, suite=suite, setting=setting, setup_summary="", setup_source="",
        observation="", observation_scope="benchmark", observation_source="",
        grading_summary="", grading_scope="task", grading_evidence="", evaluation_source=source,
        goal="", media=[], conference="CoRL 2026", retrieved="2026-11-11",
    )


def prepare_sources():
    SOURCES.mkdir(exist_ok=True)
    jobs = []
    for key in REPOSITORIES:
        fetch(SOURCES / f"{key}_home.html", HOMES[key])
        for suffix in ("html", "txt"):
            target = SOURCES / f"{key}_paper.{suffix}"
            if not target.exists():
                shutil.copyfile(ROOT / "sources" / "corl2026" / f"{key}_paper.{suffix}", target)
        tree = snapshot(key)
        for item in tree["tree"]:
            path = item["path"]
            if key == "rmm":
                include = (
                    path.startswith("RMMBench/tasks/") and path.endswith((".py", ".md"))
                    or path in {
                        "README.md", "RMMBench/configs/task_class.py", "RMMBench/configs/task_config.json",
                        "RMMBench/vlm_evaluation/configs/episodes/manipulation_episodes.json",
                        "RMMBench/vlm_evaluation/configs/episodes/nav.json",
                        "RMMBench/vlm_evaluation/configs/episodes/long_horizon_tasks.json",
                    }
                )
            else:
                include = path == "README.md" or path.startswith("PolaRiS-Hub/") and path.endswith(".yaml")
            if include:
                jobs.append((key, tree, path))
    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(lambda job: fetch_raw(*job), jobs))


def method_inherited(classes, name, method_name, visited=None):
    visited = set() if visited is None else visited
    if name in visited or name not in classes:
        return None
    visited.add(name)
    node, path, code = classes[name]
    for child in node.body:
        if isinstance(child, ast.FunctionDef) and child.name == method_name:
            return child, path, code
    for base in node.bases:
        if isinstance(base, ast.Name):
            result = method_inherited(classes, base.id, method_name, visited)
            if result:
                return result
    return None


def language_value(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value if isinstance(part, ast.Constant) else "{" + ast.unparse(part.value) + "}"
            for part in node.values
        )
    return ""


def method_instructions(method):
    values = []
    for child in ast.walk(method):
        if not isinstance(child, ast.Assign):
            continue
        targets = [ast.unparse(target) for target in child.targets]
        if not any(target in {"instruction", "instructions"} or target.endswith("['instructions']") for target in targets):
            continue
        entries = child.value.elts if isinstance(child.value, (ast.List, ast.Tuple)) else [child.value]
        values.extend(value for entry in entries if (value := language_value(entry)))
    return list(dict.fromkeys(values))


def rmm_records():
    tree = snapshot("rmm")
    classes = {}
    managers = {}
    tasks = {}
    conditions = {}
    for item in tree["tree"]:
        path = item["path"]
        if not path.startswith("RMMBench/tasks/") or not path.endswith(".py"):
            continue
        code = fetch_raw("rmm", tree, path)
        for node in ast.parse(code).body:
            if not isinstance(node, ast.ClassDef):
                continue
            classes[node.name] = (node, path, code)
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr
                if method not in {"add_task", "add_config_manager", "add_condition"}:
                    continue
                name = ast.literal_eval(decorator.args[0])
                {"add_task": tasks, "add_config_manager": managers, "add_condition": conditions}[method][name] = (node, path, code)

    paper_rows = {}
    paper = (SOURCES / "rmm_paper.html").read_text()
    for table in re.findall(r"<table\b.*?</table>", paper, re.S):
        rows = table_rows(table)
        if rows and [clean(cell) for cell in rows[0]] == ["Task Name", "Horizon", "Instruction"]:
            paper_rows = {clean(row[0]): (clean(row[1]), clean(row[2])) for row in rows[1:]}
    assert len(paper_rows) == 60
    base = "RMMBench/vlm_evaluation/configs/episodes/"
    manip = json.loads(fetch_raw("rmm", tree, base + "manipulation_episodes.json"))
    nav = json.loads(fetch_raw("rmm", tree, base + "nav.json"))
    assert len(manip) == 60 and len(nav) == 10
    presets = {name: [config] for name, config in manip.items()}
    presets.update({name: configs if isinstance(configs, list) else [configs] for name, configs in nav.items()})
    registry_code = fetch_raw("rmm", tree, "RMMBench/configs/task_class.py")
    registry_node = next(node for node in ast.parse(registry_code).body if isinstance(node, ast.Assign))
    registry = ast.literal_eval(registry_node.value)
    groups = {}
    for group, families in registry["manipulation"].items():
        for family, names in families.items():
            groups.update({name: ("Manipulation", group, family) for name in names})
    for family, names in registry["composite_navigation"].items():
        groups.update({name: ("Composite navigation", "navigation", family) for name in names})
    assert set(groups) == set(tasks) == set(managers)
    assert len(groups) == 113
    page = re.sub(r"<!--.*?-->", "", (SOURCES / "rmm_home.html").read_text(), flags=re.S)
    named_videos = {
        Path(path).stem: urljoin(HOMES["rmm"], path)
        for path in re.findall(r'(?:src|href)="([^\"]+\.mp4)"', page)
    }
    output = []
    for name, (suite, registry_group, registry_family) in groups.items():
        manager, manager_path, manager_code = managers[name]
        task_node, task_path, _ = tasks[name]
        instruction_method, _, _ = method_inherited(classes, manager.name, "get_instruction")
        condition_method, condition_path, condition_code = method_inherited(classes, manager.name, "get_condition_config")
        instructions = method_instructions(instruction_method)
        configs = presets.get(name, [])
        if configs:
            fixed_instructions = configs[0].get("task", {}).get("instructions", [])
            instructions = list(dict.fromkeys([*fixed_instructions, *instructions]))
        if not instructions:
            instructions = [paper_rows[name][1]] if name in paper_rows else [name.replace("_", " ")]
        source = source_url("rmm", tree, task_path, task_node.lineno)
        task = record("RMMBench", name, name.replace("_", " ").capitalize(), instructions[0], source, suite, "Simulation")
        task.update(
            language_variants=instructions, registry_group=registry_group, registry_family=registry_family,
            source_snapshot=tree["sha"], reported_task_count=90, preset_count=len(configs),
            catalog_scope="All 113 names in the pinned official task registry, comprising 60 manipulation and 53 composite-navigation registrations. Registrations include layout and object variants. The paper reports 90 canonical scenarios (60 manipulation plus 30 composite navigation). The released fixed-episode files enumerate 70 names (60 manipulation plus 10 navigation, the latter with 11 presets). These are different inventory scopes.",
            source_note="Instruction and setup follow a fixed released episode where available, otherwise the registered configuration manager. Templates retain their runtime substitutions. The complete source factory and condition checker define sampled variants.",
            observation="The agent receives head and wrist views, an optional bird’s-eye view, and overlays of candidate grasps or navigation grids. It retains complete textual action/feedback history and a sliding window of recent visual observations. The VLM selects skills and grasp candidates and predicts target bounding boxes.",
            observation_scope="benchmark", observation_source=PAPERS["rmm"],
            grading_evidence="Simulator-state conditions determine task completion. The paper separately reports process metrics for completion, localization, action repetition, efficiency and recovery. A visual appearance of cooking or washing is evaluated through the implemented fixture/object conditions.",
            evaluation_source=source_url("rmm", tree, condition_path, condition_method.lineno),
            setup_source=source_url("rmm", tree, manager_path, manager.lineno),
            media_source=HOMES["rmm"],
        )
        if name in paper_rows:
            task["paper_horizon"], task["paper_instruction"] = paper_rows[name]
            task["suite"] += " · " + task["paper_horizon"]
        manager_doc = ast.get_docstring(manager) or ""
        condition_excerpt = ast.get_source_segment(condition_code, condition_method)
        definitions = ["Configuration-manager goal factory:\n" + condition_excerpt]
        declared_condition_names = set()
        for node in ast.walk(condition_method):
            if isinstance(node, ast.keyword):
                declared_condition_names.add(node.arg)
            elif isinstance(node, ast.Dict):
                declared_condition_names.update(key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str))
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                declared_condition_names.add(node.slice.value)
        condition_types = [condition for condition in conditions if condition in declared_condition_names]
        if configs:
            first = configs[0]["task"]
            task["initial_conditions"] = json.dumps(configs, indent=2, ensure_ascii=False)
            task["condition_config"] = first.get("conditions", {})
            names = [component.get("name", component.get("class", "object")) for component in first.get("components", [])]
            task["objects"] = ", ".join(dict.fromkeys(names))
            scene = first.get("robocasa_scene", "")
            task["setup_summary"] = f"Released preset in {scene or 'the configured kitchen scene'} with " + ", ".join(names) + ". Exact object poses, fixture states and robot initialization are retained below."
            condition_json = json.dumps(first.get("conditions", {}), indent=2, ensure_ascii=False)
            definitions.insert(0, "Conditions for the first released preset:\n" + condition_json)
            condition_types.extend(condition for condition in conditions if re.search(r'"' + re.escape(condition) + r'"\s*:', condition_json))
        else:
            task["setup_summary"] = " ".join(manager_doc.split()) or "The registered configuration manager generates the scene, robot start, objects and fixtures. Its source defines the configuration parameters."
            task["initial_conditions"] = ast.get_source_segment(manager_code, manager)
        for condition in dict.fromkeys(condition_types):
            node, path, code = conditions[condition]
            definitions.append(f"Condition implementation for {condition}:\n" + ast.get_source_segment(code, node))
        task["goal"] = "\n\n".join(definitions)
        task["grading_summary"] = "The configured goal uses " + ", ".join(dict.fromkeys(condition_types)) + ". The retained configuration and condition implementations specify required states, ordering, persistence and thresholds."
        if name in named_videos:
            task["media"].append(dict(type="video", url=named_videos[name], label="Official named task demonstration", scope="task"))
        for item in tree["tree"]:
            path = item["path"]
            if Path(path).name in {name + "_head.png", name + "_wrist.png"}:
                role = "Head" if path.endswith("_head.png") else "Wrist"
                task["media"].append(dict(type="image", url=f"https://raw.githubusercontent.com/{REPOSITORIES['rmm']}/{tree['sha']}/{path}", label=role + " view of released episode", scope="variant"))
        output.append(task)
    return output


def h2r_records():
    markup = (SOURCES / "h2r_paper.html").read_text()
    rubric_rows = []
    for table in re.findall(r"<table\b.*?</table>", markup, re.S):
        rows = table_rows(table)
        if rows and [clean(cell) for cell in rows[0]] == ["Task", "Instruction", "Step-by-Step Rubric"]:
            rubric_rows = rows[1:]
    assert len(rubric_rows) == 4
    identities = {
        "Pick-and-Place": "pick_mug", "Stacking": "stack_bowls",
        "Insertion": "insert_donut", "Sequential Manipulation": "pick_toys",
    }
    page = (SOURCES / "h2r_home.html").read_text()
    setup_text = {
        "pick_mug": "A mug begins at a randomized position and the target plate remains fixed in a real-to-sim reconstructed workspace.",
        "stack_bowls": "Two bowls are arranged on a real-to-sim reconstructed tabletop for bowl stacking.",
        "insert_donut": "A donut-shaped object and a peg are arranged on a real-to-sim reconstructed tabletop for precision insertion.",
        "pick_toys": "Blue, orange and yellow toys start outside a pink box. The sequence requires placing the toys into that box.",
    }
    output = []
    for cells in rubric_rows:
        title, instruction, raw_rubric = clean(cells[0]), clean(cells[1]), clean(cells[2])
        name = identities[title]
        steps = [step.strip() for step in re.split(r"\b\d+\.\s+", raw_rubric) if step.strip()]
        task = record("H2RBench", name, title, instruction, PAPERS["h2r"] + "#A1.T6", "Human-to-robot transfer · full four-task suite", "Sim-to-real")
        task.update(
            setup_summary=setup_text[name], setup_source=HOMES["h2r"],
            observation="The benchmark supports synchronized multi-view RGB-D, robot proprioception and language. Real human demonstrations use front and side views. Robot demonstrations add wrist observations. Each transfer method may select its own representation or camera subset under the shared protocol.",
            observation_scope="benchmark", observation_source=PAPERS["h2r"],
            grading_summary="Final success requires the final cumulative stage. " + steps[-1] + ". The benchmark also reports average progression across all cumulative stages.",
            grading_evidence="The paper defines cumulative stages for each task, reports final-stage success rate and mean success across the stages, and normalizes scores to 0–1. Simulation-based method rankings are compared with a separate physical-robot training and evaluation pipeline.",
            evaluation_source=PAPERS["h2r"] + "#A1.T6", grading_scope="task",
            goal=raw_rubric, grading_stages=[dict(stage=index + 1, description=step) for index, step in enumerate(steps)],
            catalog_scope="The complete four-task suite in the paper and official project page. Simulation environments are reconstructed from real scenes, and the paper also validates method rankings with physical-robot evaluations.",
            source_note="The instruction and rubric are retained verbatim from paper Table 6. In stacking, the instruction is generic while the rubric explicitly asks for the blue bowl on top of the green bowl. Stage descriptions preserve that source wording.",
            media_source=HOMES["h2r"], reported_task_count=4,
        )
        for path in dict.fromkeys(re.findall(r'<source[^>]*src="([^\"]+\.mp4)"', page)):
            if f"/{name}/" not in path:
                continue
            human = "/human/" in path
            label = "Real human demonstration" if human else "Simulated robot demonstration"
            camera = Path(path).stem
            task["media"].append(dict(type="video", url=urljoin(HOMES["h2r"], path), label=label + " · " + camera, scope="task"))
        output.append(task)
    return output


def main():
    prepare_sources()
    tasks = rmm_records() + h2r_records()
    assert len(tasks) == len({task["id"] for task in tasks}) == 117
    assert all(task["instruction"] and task["goal"] and task["grading_summary"] for task in tasks)
    (ROOT / "mobile_transfer_tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    print("Mobile/transfer records", dict(Counter(task["family"] for task in tasks)))


if __name__ == "__main__":
    main()

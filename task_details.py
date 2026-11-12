"""Normalize evidence from the benchmark snapshots used by build_data.py."""

import ast
import re


LIBERO_PAPER = "https://arxiv.org/html/2306.03310v2"
ROBOCASA_PAPER = "https://arxiv.org/html/2603.04356"
ROBOCASA_ORIGINAL = "https://arxiv.org/html/2406.02523"
SIMPLER_PAPER = "https://arxiv.org/html/2405.05941"
SIMPLER_MEDIA = "https://simpler-env.github.io/"
BEHAVIOR_CHALLENGE = "https://behavior.stanford.edu/challenge/evaluation.html"
BEHAVIOR_GALLERY = "https://behavior.stanford.edu/challenge/tasks/index.html"
BEHAVIOR_ORIGINAL = "https://stanfordvl.github.io/behavior/activities.html"
DATACENTER_METHODS = "https://robocurve.org/datacenterbench/methods.html"
ROBODOJO_PAPER = "https://arxiv.org/html/2607.04434"


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def readable_name(value):
    value = value.replace("PnP", "Pick and Place ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", value)
    value = " ".join(value.replace("_", " ").split())
    return value[0].upper() + value[1:] if value else ""


def stable_id(task):
    benchmark = task["benchmark"]
    if benchmark == "DataCenterBench":
        identity = task["image"]
    elif benchmark == "RoboDojo":
        # Sim and real tasks can have the same title.
        identity = task["source"].split("/doc/", 1)[-1].strip("/")
    elif benchmark == "BEHAVIOR-1K":
        # Challenge membership can change while the activity definition stays the same.
        identity = f'{task["name"]}-{task["definition_id"]}'
    elif benchmark == "LIBERO":
        identity = f'{task["suite"]}--{task["name"]}'
    else:
        identity = task["name"]
    return f"{slug(benchmark)}--{slug(identity)}"


def bddl_section(code, name):
    """Return the exact named S-expression from a task definition."""
    match = re.search(r"\(\s*:" + re.escape(name) + r"(?=\s|\))", code, re.I)
    if not match:
        return ""
    depth = 0
    for index in range(match.start(), len(code)):
        if code[index] == "(":
            depth += 1
        elif code[index] == ")":
            depth -= 1
            if not depth:
                return code[match.start():index + 1]
    return ""


def bddl_tree(section):
    """Parse the structure for display while leaving the source text intact."""
    stack = [[]]
    without_comments = re.sub(r";[^\n]*", "", section)
    for token in re.findall(r"\(|\)|[^\s()]+", without_comments):
        if token == "(":
            stack.append([])
        elif token == ")" and len(stack) > 1:
            completed = stack.pop()
            stack[-1].append(completed)
        elif token != ")":
            stack[-1].append(token)
    return stack[0][0] if len(stack) == 1 and stack[0] else []


def display_object(value):
    value = value.lstrip("?")
    value = re.sub(r"\.[a-z]\.\d+", "", value)
    value = re.sub(r"_(\d+)$", r" #\1", value)
    return " ".join(value.replace("_", " ").split())


RELATIONS = {
    "in": "{} is inside {}",
    "inside": "{} is inside {}",
    "on": "{} is on {}",
    "ontop": "{} is on top of {}",
    "onfloor": "{} is on {}",
    "inroom": "{} is in the {}",
    "nextto": "{} is next to {}",
    "under": "{} is under {}",
    "touching": "{} touches {}",
    "attached": "{} is attached to {}",
    "contains": "{} contains {}",
    "filled": "{} is filled with {}",
    "covered": "{} is covered with {}",
    "saturated": "{} is saturated with {}",
    "close": "{} is closed",
    "open": "{} is open",
    "turnon": "{} is on",
    "turnoff": "{} is off",
    "toggled_on": "{} is on",
    "cooked": "{} is cooked",
    "real": "{} exists in the scene",
}
LOGICAL_OPERATORS = {":goal", ":init", "and", "or", "not", "imply", "forall", "exists", "forn", "forpairs"}


def bddl_atoms(node):
    if not isinstance(node, list) or not node:
        return
    operator, *arguments = node
    if not isinstance(operator, str):
        for child in node:
            yield from bddl_atoms(child)
    elif operator.lower() in LOGICAL_OPERATORS:
        for child in arguments:
            yield from bddl_atoms(child)
    elif arguments and all(isinstance(argument, str) for argument in arguments) and "-" not in arguments:
        template = RELATIONS.get(operator.lower())
        values = [display_object(argument) for argument in arguments]
        if template and template.count("{}") == len(values):
            yield template.format(*values)
        else:
            yield f'{operator.lower().replace("_", " ")}({", ".join(values)})'


def contains_grouping(node):
    if not isinstance(node, list) or not node:
        return False
    return (
        isinstance(node[0], str)
        and node[0].lower() in LOGICAL_OPERATORS - {":goal", ":init", "and"}
    ) or any(contains_grouping(child) for child in node)


def bddl_summary(section, kind, limit=4):
    tree = bddl_tree(section)
    atoms = list(dict.fromkeys(bddl_atoms(tree)))
    if not atoms:
        return ""
    if contains_grouping(tree):
        # An atom under NOT, OR or a quantifier need not be independently true.
        label = f"The {kind} definition uses logical grouping or quantification. Conditions referenced include"
    else:
        label = f"The {kind} definition specifies"
    selected = atoms[:limit]
    summary = f"{label} {selected[0]}."
    if len(selected) > 1:
        summary += " " + ". ".join(readable_name(atom) for atom in selected[1:]) + "."
    if len(atoms) > limit or contains_grouping(tree):
        summary += " See the exact definition for all conditions and their logic."
    return summary


def apply_bddl(task, code, scene=""):
    task["initial_conditions"] = bddl_section(code, "init")
    summary = bddl_summary(task["initial_conditions"], "initial-state")
    task["setup_summary"] = " ".join(text for text in (scene, summary) if text)
    if task["setup_summary"]:
        task["setup_source"] = task["source"]
    if task["goal"]:
        task["grading_summary"] = bddl_summary(task["goal"], "goal") or "The grader checks the logical goal in the task definition."
        task["grading_scope"] = "task"


CASA_CHECKS = {
    "gripper_obj_far": "gripper distance from the object",
    "gripper_button_far": "gripper distance from the button",
    "check_obj_in_receptacle": "object placement in a receptacle",
    "obj_inside_of": "object containment",
    "check_obj_fixture_contact": "object contact with a fixture",
    "check_rack_contact": "contact with a rack",
    "check_obj_any_counter_contact": "contact with a counter",
    "is_closed": "closed fixture state",
    "is_open": "open fixture state",
    "get_state": "fixture state",
    "get_handle_state": "handle state",
    "is_burner_on": "burner activation",
    "check_obj_location_on_stove": "object location on the stove",
    "_check_obj_location_on_stove": "object location on the stove",
    "check_obj_under_water": "object position under water",
    "check_obj_upright": "whether an object is upright",
    "check_slot_contact": "contact with a slot",
}


def casa_checker_summary(excerpt):
    if "def _check_success" not in excerpt:
        return ""
    code = excerpt[excerpt.index("def _check_success"):].split("\n\nHelper", 1)[0]
    try:
        syntax = ast.parse(code)
    except SyntaxError:
        return ""
    calls = [
        CASA_CHECKS[node.func.attr]
        for node in ast.walk(syntax)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in CASA_CHECKS
    ]
    terms = list(dict.fromkeys(calls))
    if terms:
        return "The checker uses " + ", ".join(terms) + ". See the code for the required conditions and thresholds."
    return "A task-specific simulator check determines success. See the code for the required conditions and thresholds."


def casa_object_type(value):
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value.replace("_", " ")
    if isinstance(value, (ast.List, ast.Tuple)):
        return " or ".join(filter(None, (casa_object_type(item) for item in value.elts)))
    return ""


def casa_fixture_name(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return {"cab": "cabinet", "fxtr": "fixture"}.get(node.attr, node.attr.replace("_", " "))
    return ""


def casa_config_fields(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        return {keyword.arg: keyword.value for keyword in node.keywords}
    if isinstance(node, ast.Dict):
        return {
            key.value: value for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    return {}


def casa_setup_summary(methods):
    """Describe declared sampling references and explicit resets in the task code."""
    statements = []
    scene = methods.get("_setup_scene")
    if scene:
        for statement in scene.body:
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            call = statement.value.func
            if isinstance(call, ast.Attribute) and call.attr in {"open_door", "close_door"}:
                fixture = casa_fixture_name(call.value)
                if fixture:
                    state = "opens" if call.attr == "open_door" else "closes"
                    statements.append(f"The reset {state} the {fixture} door.")
    objects = methods.get("_get_obj_cfgs")
    placements = []
    if objects:
        for node in ast.walk(objects):
            fields = casa_config_fields(node)
            placement = casa_config_fields(fields.get("placement"))
            fixture = casa_fixture_name(placement.get("fixture"))
            name = casa_object_type(fields.get("name"))
            group = casa_object_type(fields.get("obj_groups"))
            if not fixture or not name or name.startswith("distr"):
                continue
            obj = group if group and group != "all" else "target object" if name == "obj" else name
            placements.append(f"{obj} relative to the {fixture}")
    unique = list(dict.fromkeys(placements))
    if unique:
        statements.append("The task samples positions for " + ", ".join(unique[:4]) + ".")
        if len(unique) > 4:
            statements.append("The source includes further placements.")
    if not statements:
        fixtures = []
        references = methods.get("_setup_kitchen_references")
        if references:
            for node in ast.walk(references):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register_fixture_ref" and node.args:
                    fixture = casa_object_type(node.args[0])
                    if fixture:
                        fixtures.append("cabinet" if fixture == "cab" else fixture)
        if fixtures:
            statements.append("The sampled kitchen includes " + ", ".join(dict.fromkeys(fixtures)) + ".")
    return " ".join(statements)


SIMPLER_VIDEOS = {
    "google_robot_pick_coke_can": "octo_base_pick_coke_can.mp4",
    "google_robot_move_near": "rt1_move_redbull_can_near_orange.mp4",
    "google_robot_open_middle_drawer": "paired_videos/open_middle_drawer_sim.mp4",
    "google_robot_close_bottom_drawer": "rt1x_close_bottom_drawer.mp4",
    "google_robot_place_apple_in_closed_top_drawer": "rt2x_place_apple_into_top_drawer.mp4",
    "widowx_spoon_on_towel": "octo_small_put_spoon_on_towel.mp4",
    "widowx_carrot_on_plate": "rt1x_put_carrot_on_plate.mp4",
    "widowx_stack_cube": "octo_small_stack_green_block_on_yellow_block.mp4",
    "widowx_put_eggplant_in_basket": "octo_base_put_eggplant_in_basket.mp4",
}


def add_media(task, kind, url, label, scope="task"):
    if url:
        task["media"].append(dict(type=kind, url=url, label=label, scope=scope))
        if kind == "video" and not task.get("video"):
            task["video"] = url


def apply_protocol(task, observation, observation_scope, evaluation_source, grading_evidence, observation_source=None):
    task.update(
        observation=observation,
        observation_scope=observation_scope,
        observation_source=observation_source or evaluation_source,
        evaluation_source=evaluation_source,
        grading_evidence=grading_evidence,
    )


def enrich_task(task, *, code="", scene="", demo_page="", scoring_levels=None, model_images=None, task_videos=None):
    """Populate comparison fields from task evidence and explicit protocol sources."""
    benchmark = task["benchmark"]
    task.update(
        id=stable_id(task),
        title=readable_name(task["name"]),
        family="RoboCasa" if benchmark.startswith("RoboCasa") else "BEHAVIOR" if benchmark.startswith("BEHAVIOR") else benchmark,
        setting="Simulation",
        setup_summary=task.get("setup", ""),
        setup_source=task["source"] if task.get("setup") else "",
        observation="",
        observation_scope="unavailable",
        observation_source="",
        grading_summary="",
        grading_scope="unavailable",
        grading_evidence="",
        evaluation_source=task["source"],
        media=[],
    )
    if demo_page:
        task["media_source"] = demo_page
    if benchmark == "LIBERO":
        instruction = bddl_section(code, "language").removeprefix("(:language").removesuffix(")").strip()
        if instruction:
            task["instruction"] = instruction
            task["title"] = instruction
        apply_bddl(task, code, scene)
        apply_protocol(task, "The paper conditions the policy on a language instruction, camera images and robot state, including joint and gripper information.", "benchmark", LIBERO_PAPER, "The simulator checks the BDDL goal and records rollout success. The evaluator aggregates binary outcomes across trials.")
    elif benchmark.startswith("BEHAVIOR"):
        apply_bddl(task, code, scene)
        if task["suite"] == "2026 challenge":
            task["instruction"] = task["description"]
            apply_protocol(task, "The 2026 challenge allows onboard RGB, depth and proprioception. The official wrapper uses head and wrist camera views. A submission may use a supported robot with a custom configuration.", "suite", BEHAVIOR_CHALLENGE, "The simulator evaluates BDDL goal predicates. Partial credit is the fraction of goal predicates satisfied at episode end under the 2026 challenge rules.")
        elif benchmark == "BEHAVIOR-100":
            task["grading_evidence"] = "The iGibson simulator checks whether the logical goal is fulfilled. The episode ends when the goal holds or time expires."
            task["evaluation_source"] = BEHAVIOR_ORIGINAL
        else:
            task["grading_evidence"] = "The activity defines its goal in BDDL. A simulator can evaluate these predicates against object and scene state."
        add_media(task, "video", task.get("video"), "Official activity demonstration")
    elif benchmark.startswith("RoboCasa"):
        task["instruction"] = task["description"]
        paper = ROBOCASA_PAPER if benchmark == "RoboCasa365" else ROBOCASA_ORIGINAL
        apply_protocol(task, "The paper’s policies use a task instruction, proprioception and three camera views (wrist and two workspace views).", "benchmark", paper, "RoboCasa measures simulator task success. The task environment can inspect object and fixture state directly.")
        if task["goal"]:
            task["grading_summary"] = casa_checker_summary(task["goal"])
            task["grading_scope"] = "task"
        else:
            task["grading_summary"] = "The archived catalog describes the intended outcome in its instruction. Open the linked task implementation for its success check."
            task["grading_scope"] = "benchmark"
    elif benchmark == "SIMPLER":
        task["setting"] = "Sim-to-real"
        task["title"] = readable_name(task["description"])
        view = "an egocentric head-mounted camera" if task["suite"] == "Google robot" else "a third-person workspace camera"
        apply_protocol(task, f"The {task['suite']} setup uses {view}. SIMPLER recreates the real camera and workspace in simulation.", "suite", SIMPLER_PAPER, "The simulated rollout is scored by the registered environment. The paper also evaluates representative tasks on real hardware to compare policy outcomes.")
        task["grading_summary"] = task["goal"]
        task["grading_scope"] = "task"
        if task["name"] in ("widowx_spoon_on_towel", "widowx_carrot_on_plate", "widowx_put_eggplant_in_basket", "widowx_stack_cube"):
            task["evaluation_source"] = "https://github.com/simpler-env/ManiSkill2_real2sim/blob/ef7a4d4fdf4b69f2c2154db5b15b9ac8dfe10682/mani_skill2_real2sim/envs/custom_scenes/put_on_in_scene.py#L43"
            task["grading_evidence"] = "The environment sets success to src_on_target, computed from bounding-box-relative geometry and, for carrot placement and cube stacking, an additional contact test. Grasp, consecutive-grasp and moved-object fields are diagnostic; robot-link contacts are ignored by the contact restriction."
        if task["name"] in SIMPLER_VIDEOS:
            add_media(task, "video", SIMPLER_MEDIA + "static/videos/" + SIMPLER_VIDEOS[task["name"]], "Official example rollout", "variant")
    elif benchmark == "DataCenterBench":
        task["setting"] = "Real"
        task["instruction"] = task["description"]
        evidence = "Two model judges receive full-resolution before and after images from three cameras, the instruction and the rubric. A person resolves disagreement or uncertainty."
        if task["image"] == "DC-keypad":
            evidence = "The recorded keypad presses determine the score. The judges cross-check the recorded outcome."
        apply_protocol(task, "The agent receives three 224 × 224 views after each step, one overhead and one from each wrist. It retains the images from its last two steps.", "benchmark", DATACENTER_METHODS, evidence)
        for view, url in (model_images or {}).items():
            add_media(task, "image", url, f"{view.capitalize()} camera observation")
    elif benchmark == "RoboDojo":
        real = task["suite"].startswith("Real ·")
        task["setting"] = "Real" if real else "Simulation"
        if real:
            observation = "The real rig uses one head and two wrist cameras. The paper documents synchronized RGB, language and robot states for the real demonstrations."
            evidence = "Three independent evaluators score the recorded trial using the task rubric. The final trial score averages their ratings."
        else:
            observation = "The simulated environment sends observations to the policy. The paper documents head and wrist RGB-D plus robot state for the simulation data. Policy-specific input processing may vary."
            evidence = "The simulation environment applies task-specific success and progress criteria. Scores can reflect completed stages before full success."
        if not scoring_levels:
            evidence = "The official page presents this as an auxiliary demonstration without a published scoring table."
        apply_protocol(task, observation, "suite", ROBODOJO_PAPER, evidence)
        for url, label, scope in task_videos or ():
            add_media(task, "video", url, label, scope)
    if scoring_levels:
        task["grading_levels"] = scoring_levels
        best = max(scoring_levels, key=lambda level: level["score"])
        task["grading_summary"] = best["description"]
        task["grading_scope"] = "task"

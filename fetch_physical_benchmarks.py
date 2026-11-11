"""Fetch official physical-interaction benchmark catalogs and retain source evidence."""

import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import zipfile
from xml.etree import ElementTree
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from fetch_sources import Page


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources" / "physical"
SOURCES.mkdir(exist_ok=True)


def fetch(name, url):
    path = SOURCES / name
    if not path.exists():
        response = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=50)
        path.write_bytes(response.read())
    return path


def fetch_initial():
    urls = {
        "nist_metrics.pdf": "https://www.nist.gov/system/files/documents/2018/01/11/test_method-metrics-analysis_v3.pdf",
        "nist_paper.html": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7537423/",
        "nist_deformable.html": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9720326/",
        "nist_video.html": "https://www.nist.gov/video/robotic-grasping-and-manipulation-competition-task-1-task-board-assembly",
        "furniture_home.html": "https://clvrai.github.io/furniture-bench/",
        "furniture_tree.json": "https://api.github.com/repos/clvrai/furniture-bench/git/trees/main?recursive=1",
        "adroit_tree.json": "https://api.github.com/repos/Farama-Foundation/Gymnasium-Robotics/git/trees/main?recursive=1",
        "adroit_home.html": "https://robotics.farama.org/envs/adroit_hand/",
        "robochallenge_home.html": "https://robochallenge.ai/challenges",
        "robochallenge_v1.md": "https://huggingface.co/datasets/RoboChallenge/Table30/raw/main/README.md",
        "robochallenge_v2.md": "https://huggingface.co/datasets/RoboChallenge/Table30v2/raw/main/README.md",
        "robochallenge_v1_tree.json": "https://huggingface.co/api/datasets/RoboChallenge/Table30/tree/main?recursive=true&limit=1000",
        "robochallenge_v2_tree.json": "https://huggingface.co/api/datasets/RoboChallenge/Table30v2/tree/main?recursive=true&limit=1000",
        "robochallenge_v1_paper.html": "https://arxiv.org/html/2510.17950",
        "robochallenge_v2_paper.pdf": "https://robochallenge.ai/robochallenge_techreport_V2.pdf",
    }
    def run(item):
        name, url = item
        try:
            path = fetch(name, url)
            print(name, path.stat().st_size, flush=True)
        except Exception as error:
            print(name, str(error), flush=True)
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(run, urls.items()))
    (SOURCES / "source_urls.json").write_text(json.dumps(urls, indent=2))
    for path in SOURCES.glob("*.html"):
        (SOURCES / (path.stem + ".txt")).write_text("\n".join(Page(path.read_text()).text))
    for path in SOURCES.glob("*.pdf"):
        subprocess.run(["pdftotext", "-layout", str(path), str(path.with_suffix(".txt"))], check=True)


NIST_HOME = "https://www.nist.gov/el/intelligent-systems-division-73500/robotic-grasping-and-manipulation-assembly/assembly"
NIST_METRICS = "https://www.nist.gov/system/files/documents/2018/01/11/test_method-metrics-analysis_v3.pdf"
FURNITURE_HOME = "https://clvrai.github.io/furniture-bench/"
ROBOCHALLENGE_HOME = "https://robochallenge.ai"


def fetch_secondary():
    urls = {"nist_home.html": NIST_HOME}
    for repo, prefix in [("clvrai/furniture-bench", "furniture"), ("Farama-Foundation/Gymnasium-Robotics", "adroit")]:
        tree = json.loads((SOURCES / (prefix + "_tree.json")).read_text())
        for item in tree["tree"]:
            path = item["path"]
            furniture_file = prefix == "furniture" and path.endswith(".py") and (
                path.startswith("furniture_bench/furniture/")
                or path == "furniture_bench/config.py"
                or path.startswith("furniture_bench/envs/")
            )
            adroit_file = prefix == "adroit" and (
                path.startswith("gymnasium_robotics/envs/adroit_hand/") and path.endswith(".py")
                or path == "gymnasium_robotics/__init__.py"
            )
            if furniture_file or adroit_file:
                name = prefix + "__" + path.replace("/", "__")
                urls[name] = "https://raw.githubusercontent.com/" + repo + "/" + tree["sha"] + "/" + path
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda item: fetch(*item), urls.items()))
    (SOURCES / "secondary_urls.json").write_text(json.dumps(urls, indent=2))
    templates = {}
    page = (SOURCES / "nist_home.html").read_text()
    for match in re.finditer(r'data-file-url="([^"]+)"[^>]*>Benchmark Template', page):
        url = urljoin("https://www.nist.gov", match[1])
        name = url.rsplit("/", 1)[-1]
        templates[name] = url
        path = fetch(name, url)
        document = ElementTree.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = ["".join(p.itertext()) for p in document.findall(".//w:p", namespace)]
        path.with_suffix(".txt").write_text("\n".join(paragraphs))
    (SOURCES / "nist_template_urls.json").write_text(json.dumps(templates, indent=2))
    task_urls = {}
    for version in ["v1", "v2"]:
        base = ROBOCHALLENGE_HOME + "/api/" + version
        catalog = json.loads(fetch("robochallenge_" + version + "_catalog.json", base + "/benchmark/benchmark_list.json").read_text())
        for task in catalog[0]["tasks"]:
            identity = task["task_name"] if version == "v2" else task["task_id"]
            task_urls["robochallenge_" + version + "__" + task["task_name"] + ".json"] = base + "/task/details/" + identity + ".json"
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda item: fetch(*item), task_urls.items()))
    (SOURCES / "robochallenge_task_urls.json").write_text(json.dumps(task_urls, indent=2))


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def record(family, benchmark, suite, name, description, source, setting="Real", **details):
    task = dict(
        id=slug(benchmark) + "--" + slug(suite + " " + name),
        family=family,
        benchmark=benchmark,
        suite=suite,
        name=name,
        title=name.replace("_", " ").capitalize(),
        description=description,
        source=source,
        setting=setting,
        goal="",
        setup_summary="",
        setup_source="",
        observation="",
        observation_scope="unavailable",
        observation_source="",
        grading_summary="",
        grading_scope="unavailable",
        grading_evidence="",
        evaluation_source=source,
        media=[],
        snapshot_date="2026-11-11",
    )
    task.update(details)
    return task


def nist_tasks():
    tasks = []
    page = (SOURCES / "nist_home.html").read_text()
    images = [
        urljoin("https://www.nist.gov", item["src"]).replace("/styles/220_x_220_limit/public/", "/").split("?",1)[0]
        for item in Page(page).media
        if item.get("src") and ((item.get("alt") or "").startswith("Task Board") or (item.get("alt") or "").startswith("Bolt alignment"))
    ]
    assert len(images) == 5, images
    urls = json.loads((SOURCES / "nist_template_urls.json").read_text())
    board_files = [
        "Benchmark_NIST_Assembly_Task_Board_1_V1.0.docx",
        "Benchmark_NIST_Assembly_Task_Board_2_V1.0.docx",
        "Benchmark_NIST_Assembly_Task_Board_3_V1.0.docx",
        "Benchmark_NIST_Assembly_Task_Board__V1.0.docx",
    ]
    board1 = [
        "Small Gear", "Medium Gear", "Large Gear", "Rod 4 mm", "Rod 8 mm", "Rod 12 mm", "Rod 16 mm",
        "Bar 4 mm x 4 mm x 300 mm", "Bar 8 mm x 7 mm x 300 mm", "Bar 12 mm x 8 mm x 300 mm", "Bar 16 mm x 10 mm x 300 mm",
        "BNC Connector", "Waterproof Connector", "DSUB Connector", "USB Connector", "RJ45 Connector", "M4 Nut", "M8 Nut", "M12 Nut", "M16 Nut",
    ]
    board2 = [
        ("Spring tensioner", 1, [5, 5, 0], [5, 0], ["Actuate", "Seat", "Place"]),
        ("Slide tensioner", 1, [5, 5, 0], [5, 0], ["Actuate", "Seat", "Place"]),
        ("Sprocket tensioner", 1, [5, 5, 0], [5, 0], ["Actuate", "Seat", "Place"]),
        ("Chain belt", 1, [14, 14, 1], [2, 1], ["Thread pulley 1", "Thread pulley 2", "Place"]),
        ("Timing belt", 1, [14, 14, 1], [2, 1], ["Thread pulley 1", "Thread pulley 2", "Place"]),
        ("Round belt", 1, [14, 14, 1], [2, 1], ["Thread pulley 1", "Thread pulley 2", "Place"]),
        ("Thread M6 screws", 6, [3, 2, 1], [2, 1], ["Thread", "Seat", "Place"]),
        ("Sprocket idlers", 2, [3, 2, 1], [2, 1], ["Grasp", "Insert", "Place"]),
        ("Timing pulleys", 2, [3, 2, 1], [2, 1], ["Grasp", "Insert", "Place"]),
        ("Round pulleys", 2, [3, 2, 1], [2, 1], ["Grasp", "Insert", "Place"]),
        ("Metal collars", 6, [3, 2, 1], [2, 1], ["Grasp", "Insert", "Place"]),
    ]
    board3 = []
    for action, quantity, components in [
        ("Route", 2, [("Routed", 5)]),
        ("Place/Clip", 3, [("Placed", 5), ("Clipped", 2)]),
        ("Thread", 3, [("Threaded", 5), ("Through", 5)]),
        ("Insert", 1, [("Inserted", 3), ("Seated", 2)]),
    ]:
        for material in ["Flexible", "Stiff", "Flat"]:
            board3.append((action + " " + material + " cable", quantity, components))

    def add(board, mode, name, quantity, components, description):
        source = urls[board_files[board - 1]]
        labels = ". ".join(f"{label} earns {points} {'point' if points == 1 else 'points'} per instance" for label, points in components) + "."
        protocol = "The template requests 32 trials and reports completion time, completion percentage, and reliability. The general protocol randomizes planar board and kit/bin placements and voids trials with manual intervention."
        if board == 4:
            protocol += " This file is linked under Board 4 on the NIST page, although its document header repeats Board 3."
        task = record("NIST Assembly", "NIST Assembly Task Boards", f"ATB {board} · {mode}", name, description, source,
            title=f"ATB {board} {mode.lower()} — {name}", entry_scope="Scored operation group",
            setup_summary=f"Task Board {board}. This score-sheet row covers {quantity} instance(s). " + ("Start with the board assembled and a destination kit/bin in the robot workspace." if mode == "Disassembly" else "Start with an initialized board and a kit of parts in the robot workspace."),
            setup_source=NIST_METRICS,
            observation="The protocol asks the experimenter to document the robot, end effector, perception and localization system, CAD use, and tools. A common camera or observation vector is not prescribed.",
            observation_scope="benchmark", observation_source=source,
            grading_summary=labels, grading_scope="task",
            grading_evidence=f"The official score sheet gives additive credit for the listed operations. {protocol}",
            goal=f"Board {board} / {mode} / {name}\nQuantity: {quantity}\n" + "\n".join(f"{label}: {points} points per instance" for label, points in components),
            evaluation_source=source, protocol_source=NIST_METRICS,
            grading_components=[dict(description=label, points=points) for label, points in components],
            quantity=quantity,
            media=[dict(type="image",url=images[board-1],label=f"Official Task Board {board} photograph",scope="benchmark")],
        )
        tasks.append(task)

    for mode in ["Assembly", "Disassembly"]:
        for part in board1:
            components = [("Inserted/threaded", 3), ("Seated", 2), ("Placed on the board", 1)] if mode == "Assembly" else [("Removed", 2), ("Placed in kit tray", 1)]
            action = "mesh and seat" if "Gear" in part else "thread and seat" if "Nut" in part else "insert and seat"
            description = f"{action.capitalize()} the {part.lower()} in its matching location on NIST Task Board 1." if mode == "Assembly" else f"Remove the {part.lower()} from NIST Task Board 1 and place it in the kit tray."
            add(1, mode, part, 1, components, description)
        for name, quantity, assembled, disassembled, stages in board2:
            components = list(zip(stages, assembled)) if mode == "Assembly" else list(zip(["Disassemble", "Place in kit tray"], disassembled))
            add(2, mode, name, quantity, components, f"{mode} of {name.lower()} on the belt-drive board, using the operations and quantities in its score-sheet row.")
        for name, quantity, assembled in board3:
            components = assembled if mode == "Assembly" else [("Disassemble", 2), ("Place in kit tray", 1)] if name.startswith("Insert") else [("Disassemble", 5)]
            add(3, mode, name, quantity, components, f"{mode} operation for {name.lower()} on the cable-routing board. The cable types differ in stiffness and cross section.")
    for mode, name, quantity, components in [
        ("Assembly", "Wire transport", 12, [("Contact with board", 1)]),
        ("Assembly", "Pin insertion", 24, [("Inserted", 2), ("Seated", 1)]),
        ("Assembly", "Wire routed", 12, [("Each of three elastic retainers", 1), ("Each of two corner posts", 1)]),
        ("Assembly", "Wired correctly", 6, [("Connector LED is lit", 3)]),
        ("Disassembly", "Wires bundled", 5, [("Bound at each retainer", 5)]),
        ("Disassembly", "Connector detach", 8, [("Removed from joining part", 3)]),
        ("Disassembly", "Harness removal", 1, [("Fully removed from board", 5)]),
    ]:
        add(4, mode, name, quantity, components, f"{name} while making or removing a wire harness on Task Board 4. The harness wires are routed and grouped according to a diagram.")
    for name, description in [
        ("Bolt alignment and threading", "Align and thread bolt fasteners. Board design factors include fastener size and shape."),
        ("Nut alignment and threading", "Align and thread nut fasteners. Board design factors include fastener size and shape."),
        ("Assembly near obstructions", "Perform threaded assembly operations near obstruction blocks. Bolt head geometry may vary for the use case."),
    ]:
        tasks.append(record("NIST Assembly", "NIST Assembly Task Boards", "ATB 5 · Competencies", name, description, NIST_HOME,
            entry_scope="Board competency", setup_summary="The current NIST page describes Task Board 5 with bolts, nuts and obstruction blocks.", setup_source=NIST_HOME,
            grading_summary="The official page names this competency. A task-specific numerical score sheet was not linked in the retrieved Board 5 section.",
            grading_scope="unavailable", grading_evidence="General assembly performance metrics cover completion time and reliability. Experiment-specific configuration must be documented.",
            evaluation_source=NIST_METRICS,
            media=[dict(type="image",url=images[4],label="Official Task Board 5 photograph",scope="benchmark")]))
    assert len(tasks) == 96
    return tasks


def class_methods(code, names):
    methods = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            methods.append(ast.get_source_segment(code, node))
    return "\n\n".join(methods)


def furniture_tasks():
    tasks = []
    tree = json.loads((SOURCES / "furniture_tree.json").read_text())
    base = "https://github.com/clvrai/furniture-bench/blob/" + tree["sha"] + "/"
    shared = (SOURCES / "furniture__furniture_bench__furniture__furniture.py").read_text()
    env = (SOURCES / "furniture__furniture_bench__envs__furniture_bench_env.py").read_text()
    core_checker = class_methods(shared, {"compute_assemble", "all_assembled", "is_assembled_idx"})
    for name in ["lamp", "square_table", "desk", "drawer", "cabinet", "round_table", "stool", "chair", "one_leg"]:
        code = (SOURCES / ("furniture__furniture_bench__furniture__" + name + ".py")).read_text()
        part_code = code if name != "one_leg" else (SOURCES / "furniture__furniture_bench__furniture__square_table.py").read_text()
        pair_node = next(node for node in ast.walk(ast.parse(code)) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=="should_be_assembled" for t in node.targets))
        pairs = ast.literal_eval(pair_node.value)
        part_node = next(node for node in ast.walk(ast.parse(part_code)) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=="parts" for t in node.targets))
        parts = [node.args[0].slice.value for node in part_node.value.elts]
        assembled = [f"{parts[a]} + {parts[b]}" for a,b in pairs]
        source = base + "furniture_bench/furniture/" + name + ".py"
        video = "website_img/assembly/" + name + "_assembly_3x.mp4" if name != "one_leg" else "website_img/experiment/qualitative_analysis/one_leg/one_leg_best_2x.mp4"
        tasks.append(record("FurnitureBench", "FurnitureBench", "Full assembly", name, "Assemble the " + name.replace("_"," ") + ". Required connections are " + ", ".join(assembled) + ".", source,
            entry_scope="Full furniture task", title="Assemble " + name.replace("_"," "),
            setup_summary="A Franka Panda manipulates disassembled furniture parts on a tabletop. Initial part poses have low, medium or high randomness levels. Parts for this task are " + ", ".join(parts) + ".", setup_source=FURNITURE_HOME,
            observation="The base environment exposes robot state, three RGB/depth views and detected part poses. Its image-policy wrapper selects robot state plus two RGB views. The observation representation depends on the chosen wrapper.",
            observation_scope="benchmark", observation_source=base+"furniture_bench/envs/policy_envs/furniture_bench_image.py",
            grading_summary="Complete all " + str(len(pairs)) + " required part connections. Each newly recognized assembled pair earns one reward. Relative part poses must satisfy the task's target-pose checks and assembly prerequisites.",
            grading_scope="task", grading_evidence="The pinned automatic checker uses part detections and relative poses, counts newly assembled pairs, and considers the task assembled when all required pairs are recorded. The environment also supports explicit manual-label collection modes.",
            evaluation_source=base+"furniture_bench/furniture/furniture.py", objects=", ".join(parts),
            goal=code+"\n\n# Shared automatic assembly checks\n"+core_checker+"\n\n"+class_methods(env,{"_reward","_done"}),
            assembly_pairs=[dict(first=parts[a], second=parts[b]) for a,b in pairs],
            initial_conditions="Low, medium, and high part-pose randomization are distinct task-instance settings. The single-skill benchmark evaluates the first five skills for each furniture task.",
            media=[dict(type="video",url=urljoin(FURNITURE_HOME,video),label="Official assembly rollout",scope="task"),dict(type="image",url=urljoin(FURNITURE_HOME,"website_img/all_furniture.png"),label="Official furniture inventory",scope="benchmark")],
            source_revision=tree["sha"]))
    return tasks


def adroit_tasks():
    tasks = []
    tree = json.loads((SOURCES / "adroit_tree.json").read_text())
    base = "https://github.com/Farama-Foundation/Gymnasium-Robotics/blob/" + tree["sha"] + "/"
    summaries = {
        "door": ("Open a latched door with the dexterous hand.", "Success is reported when the door hinge position is at least 1.35 radians."),
        "hammer": ("Grasp a hammer and hammer a nail into its board.", "Success is reported when the Euclidean distance from the nail site to its goal is less than 0.01 meters."),
        "pen": ("Manipulate a pen to match its target position and orientation.", "Success requires pen-to-goal distance below 0.075 meters and orientation-vector dot product above 0.95."),
        "relocate": ("Pick up the ball and relocate it to the target position.", "Success is reported when the object-to-target distance is less than 0.1 meters."),
    }
    for name, (description, summary) in summaries.items():
        code = (SOURCES / ("adroit__gymnasium_robotics__envs__adroit_hand__adroit_" + name + ".py")).read_text()
        syntax = ast.parse(code)
        doc = next(ast.get_docstring(node) for node in syntax.body if isinstance(node,ast.ClassDef))
        observation = doc.split("## Observation Space",1)[1].split("\n\n",2)[1].strip()
        reset = doc.split("## Starting State",1)[1].split("## Episode End",1)[0].strip()
        source = base + "gymnasium_robotics/envs/adroit_hand/adroit_" + name + ".py"
        for sparse in [False, True]:
            env_id = "AdroitHand" + name.title() + ("Sparse" if sparse else "") + "-v2"
            reward = "Sparse reward is 10 for a successful step and -0.1 otherwise." if sparse else "The dense reward includes shaping terms and task-dependent bonuses. The returned success flag has the same threshold as the sparse variant."
            tasks.append(record("Adroit", "Adroit Gymnasium-Robotics v2", "Sparse reward" if sparse else "Dense reward", env_id, description, source, setting="Simulation",
                title=env_id, entry_scope="Registered reward variant", instruction=description,
                setup_summary="A simulated dexterous hand performs the " + name + " manipulation task. The reset method randomizes the relevant object or target state.", setup_source=source,
                observation=observation, observation_scope="task", observation_source=source,
                grading_summary=summary+" "+reward, grading_scope="task",
                grading_evidence="The simulator returns an info['success'] flag at each step. The pinned registry wraps each v2 task at 200 steps. Success does not itself terminate the continuing environment. An episode-level success aggregation must be specified by the evaluation harness.",
                evaluation_source=source, initial_conditions=reset,
                goal=class_methods(code,{"step","_get_obs","reset_model"}),
                environment_id=env_id, skill=name, dataset_variants=["human","cloned","expert"],
                media=[dict(type="image",url="https://raw.githubusercontent.com/Farama-Foundation/Gymnasium-Robotics/"+tree["sha"]+"/docs/_static/videos/adroit_hand/adroit_"+name+".gif",label="Official environment animation",scope="task")],
                source_revision=tree["sha"]))
    return tasks


def robochallenge_tasks():
    tasks = []
    urls = json.loads((SOURCES / "robochallenge_task_urls.json").read_text())
    for version in ["v1","v2"]:
        catalog = json.loads((SOURCES / ("robochallenge_"+version+"_catalog.json")).read_text())[0]
        for entry in catalog["tasks"]:
            filename = "robochallenge_" + version + "__" + entry["task_name"] + ".json"
            data = json.loads((SOURCES / filename).read_text())
            source = urls[filename]
            name = entry["task_name"]
            cameras = data.get("task_episodes", [{}])[0].get("episode_videos", [])
            observation = "The published demonstration exposes these camera streams: " + ", ".join(video["video_name"] for video in cameras) + ". Robot-state and action data accompany the demonstrations. The exact model observation selection is configured by its inference client."
            media = [dict(type="image",url=urljoin(ROBOCHALLENGE_HOME,data["task_banner"]),label="Official task setup",scope="task")]
            media.extend(dict(type="video",url=video["video_url"],label="Official demonstration — "+video["video_name"],scope="task") for video in cameras)
            protocol = "The Table30 paper awards task-specific stage points, deducts 0.5 per retry, terminates after excessive failed retries or negative stage points, and uses ten rollouts with ten available points each. Stages may be noncritical to binary success."
            if version == "v2":
                protocol = "The V2 report requires multitask evaluation, randomizes the machine instance, and introduces task-specific timeouts. The public task JSON gives the progress rubric. Current leaderboard operations may update independently of this snapshot."
            task = record("RoboChallenge", "RoboChallenge Table30" + (" V2" if version=="v2" else ""), "Table30 V2" if version=="v2" else "Table30", name,
                data["task_description"],source,title=name.replace("_"," ").capitalize(), instruction=data.get("prompt",data["task_description"]),
                entry_scope="Benchmark task", setup_summary=data["task_description"]+" The linked banner and demonstration show the specific tabletop props and initial arrangement.", setup_source=source,
                observation=observation, observation_scope="task", observation_source=source,
                grading_summary="Stage credit from the published rubric. "+" ".join(data["scoring"].strip().splitlines()),
                grading_scope="task", grading_evidence=protocol,
                evaluation_source=source, goal=data["scoring"].strip(),
                media=media, video=cameras[0]["video_url"] if cameras else "",
                tags=data.get("task_tag",[]), source_updated=data.get("last_update_time",""),
                protocol_source="https://robochallenge.ai/robochallenge_techreport_V2.pdf" if version=="v2" else "https://arxiv.org/html/2510.17950",
                grading_type="Additive stage points")
            if entry.get("task_id"):
                task["official_task_id"] = entry["task_id"]
                task["task_page"] = "https://robochallenge.ai/task_detail" + ("/table30_v2" if version=="v2" else "") + "?task_id=" + entry["task_id"]
            tasks.append(task)
    assert len(tasks) == 60
    return tasks


def build_catalog():
    tasks = nist_tasks() + furniture_tasks() + robochallenge_tasks() + adroit_tasks()
    assert len({task["id"] for task in tasks}) == len(tasks)
    (ROOT / "physical_tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    from collections import Counter
    print("Physical catalog", Counter(task["family"] for task in tasks))


if __name__ == "__main__":
    fetch_initial()
    fetch_secondary()
    build_catalog()

"""Retain and index the official ContactBench simulation task release."""

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import runpy
from pathlib import Path
import re
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources" / "contactbench_sim"
REPO = "Michaelwyx/contactbench-sim"


def fetch(name, url):
    path = SOURCES / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=50) as response:
            path.write_bytes(response.read())
    return path


def fetch_sources():
    tree = json.loads(fetch("repository_tree.json",f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1").read_text())
    paths = [item["path"] for item in tree["tree"] if item["path"].endswith((".py",".md",".json",".yaml",".yml")) and not item["path"].startswith("packages/hydrogel/")]
    urls = {path:f"https://raw.githubusercontent.com/{REPO}/{tree['sha']}/{path}" for path in paths}
    def run(item):
        name,url=item
        try:
            fetch(name,url)
            return True
        except Exception as error:
            print(name,str(error),flush=True)
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        count=sum(pool.map(run,urls.items()))
    (SOURCES/"source_urls.json").write_text(json.dumps(urls,indent=2))
    print("Retained",count,"sources at",tree["sha"],flush=True)


PACKAGE = Path("packages/force-bench/src/force_bench")


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def task_documentation():
    """Map Table C1 numbers to their source-authored setup and check notes."""
    text = (SOURCES/"docs/tasks.md").read_text()
    sections = {}
    matches = list(re.finditer(r"^### ([0-9, ]+)\. (.+)$",text,re.M))
    for index,match in enumerate(matches):
        section = text[match.end():matches[index+1].start() if index+1<len(matches) else text.index("## Tasks not included")]
        fields = {}
        for label in ["Setup","Checks","Options","Differences"]:
            field = re.search(r"\*\*"+label+r"\.\*\*\s*(.*?)(?=\n\*\*[A-Z]|\Z)",section,re.S)
            fields[label] = field[1].strip() if field else ""
        for number in match[1].split(","):
            sections[int(number)] = dict(title=match[2],text=section.strip(),**fields)
    return sections


def source_excerpt(code, node):
    lines=code.splitlines()
    selected=lines[node.lineno-1:node.end_lineno]
    if selected:
        selected[0]=selected[0][node.col_offset:]
    return "\n".join(selected)


def module_checkers(module_name):
    """Retain exact verifier methods and QA assignments from task/helper modules."""
    paths=[]
    pending=[PACKAGE/"appendix_tasks"/(module_name+".py")]
    while pending:
        relative=pending.pop(0)
        if relative in paths or not (SOURCES/relative).exists():
            continue
        paths.append(relative)
        syntax=ast.parse((SOURCES/relative).read_text())
        for node in syntax.body:
            if not isinstance(node,ast.ImportFrom) or not node.module:
                continue
            helper=None
            if node.module.startswith("force_bench.appendix_tasks."):
                name=node.module.removeprefix("force_bench.appendix_tasks.")
                if name.startswith("_") or name in {"derive","common"}:
                    helper=PACKAGE/"appendix_tasks"/(name+".py")
            if helper is not None:
                pending.append(helper)
    snippets=[]
    for relative in paths:
        code=(SOURCES/relative).read_text()
        syntax=ast.parse(code)
        selected=[]
        for node in syntax.body:
            if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id.isupper() for target in node.targets):
                selected.append(node)
        for node in ast.walk(syntax):
            if isinstance(node,ast.FunctionDef) and (node.name in {"criteria","verdict","criterion_state","save_appendix_verdict","check_released_and_clear"} or node.name.endswith("_checks")):
                if node not in selected:
                    selected.append(node)
            elif isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in {"criteria","crit","SPEC"} for target in node.targets):
                if node not in selected:
                    selected.append(node)
            elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=="save_appendix_verdict":
                selected.append(node)
        if selected:
            selected.sort(key=lambda node:node.lineno)
            snippets.append("# "+relative.as_posix()+"\n"+"\n\n".join(source_excerpt(code,node) for node in selected))
    return "\n\n".join(snippets),paths


def build_catalog():
    tree=json.loads((SOURCES/"repository_tree.json").read_text())
    revision=tree["sha"]
    base=f"https://github.com/{REPO}/blob/{revision}/"
    raw=f"https://raw.githubusercontent.com/{REPO}/{revision}/"
    registry_path=PACKAGE/"appendix_tasks/registry.py"
    # The registry is dependency-free metadata: its only imports are future
    # annotations and dataclasses. No simulation package is imported here.
    namespace=runpy.run_path(str(SOURCES/registry_path))
    specs=namespace["APPENDIX"]
    criteria=namespace["CRITERIA"]
    docs=task_documentation()
    checker_cache={}
    records=[]
    for spec in specs:
        doc=docs[spec.number]
        module_path=PACKAGE/"appendix_tasks"/(spec.module+".py")
        source=base+module_path.as_posix()
        scripted=spec.scripted
        if spec.module not in checker_cache:
            checker_cache[spec.module]=module_checkers(spec.module)
        checker,checker_paths=checker_cache[spec.module]
        criterion=criteria[spec.number]
        description=spec.appendix_task+". "+("Variant: "+spec.variant+". " if spec.variant else "")+"Start: "+spec.start+"."
        if scripted:
            grade=criterion
            evidence="The automatic appendix verdict passes only if every task criterion and physics-integrity check passes. It records individual checks and measurements, including final robot/object contact and stopped-motion checks where required."
        else:
            grade="This release provides the filled scene and criterion_state() readouts, with no scripted policy and no automatic pass/fail verdict. The paper's reference criterion is retained below."
            evidence="Scene-only task. Its live readouts describe which utensils are outside the bin and whether one target rests on the table. They are distinct from an automatic simulation verdict."
        media=[dict(type="image",url=raw+"docs/media/tasks_overview.jpg",label="Official simulation task overview",scope="benchmark")]
        if spec.number==22:
            media.append(dict(type="image",url=raw+"docs/media/readme/variants_charger.jpg",label="Charging-block variation examples",scope="variant"))
        if spec.number in {24,26}:
            media.append(dict(type="image",url=raw+"docs/media/readme/random_starts.jpg",label="Nominal and seeded USB/cup initial states",scope="benchmark"))
        if spec.number in {2,5}:
            media.append(dict(type="image",url=raw+"docs/media/readme/embodiment.jpg",label="Stock fingers, tactile pads and Fin Ray embodiment examples",scope="benchmark"))
        note="This is a simulation-release row with a privileged scripted reference, rather than a learned-policy evaluation result. " if scripted else "This is a scene-only release row and has no scripted reference or automatic verdict. "
        note+="The source documents physical-model and starting-state differences from the paper. Website task identifiers are not assumed to equal the Table C1 number."
        record=dict(
            id="contactbench-sim--"+slug(spec.name),family="ContactBench",benchmark="ContactBench simulation release",
            suite=f"Table C1 {spec.number} · {spec.appendix_task}",name=spec.name,
            title=spec.appendix_task+(" — "+spec.variant if spec.variant else " — "+spec.name.replace("_"," ")),
            description=description,instruction=criterion,source=source,setting="Simulation",
            goal="Paper success criterion (Table C1)\n"+criterion+"\n\nDocumented simulation checks\n"+(doc["Checks"] or "Scene only. No automatic verdict.")+"\n\nExact verifier source excerpts\n"+checker,
            setup_summary=spec.start or doc["Setup"],setup_source=base+(registry_path.as_posix() if spec.start else "docs/tasks.md"),
            observation="The recorded demonstration format contains measured robot joint positions and velocities plus task-object poses. Object poses are flagged as privileged. The released scripted policies also use simulated state and contact forces. Supported rows can record GelSight pressure/tactile fields. The release does not prescribe a learned-policy camera-input protocol.",
            observation_scope="benchmark",observation_source=base+"docs/data.md",
            grading_summary=grade,grading_scope="task" if scripted else "unavailable",grading_evidence=evidence,
            evaluation_source=source,
            initial_conditions=spec.start+"\n\nSource-authored setup notes\n"+doc["Setup"]+"\n\nRow arguments\n"+json.dumps(list(spec.argv)),
            media=media,entry_scope="Runnable scripted variant" if scripted else "Scene-only task",
            split="Scripted simulation variants" if scripted else "Scene-only release",
            source_revision=revision,source_note=note,snapshot_date="2026-11-11",
            paper_task_number=spec.number,base_task=spec.appendix_task,variant=spec.variant,
            scripted=scripted,skills=list(spec.skills),variant_arguments=list(spec.argv),
            gelsight_supported=spec.gelsight,simulation_differences=spec.notes,
            simulation_checks=doc["Checks"],task_options=doc["Options"],
            documented_differences=doc["Differences"],
            documentation_source=base+"docs/tasks.md",
            checker_sources=[base+path.as_posix() for path in checker_paths],
            simulated_embodiment="Franka FR3 with Franka Hand",
        )
        records.append(record)
    assert len(records)==74 and sum(record["scripted"] for record in records)==73
    assert len({record["paper_task_number"] for record in records if record["scripted"]})==22
    assert len({record["id"] for record in records})==74
    assert all(record["goal"] and record["setup_summary"] for record in records)
    (ROOT/"contactbench_sim_tasks.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    (SOURCES/"catalog_notes.json").write_text(json.dumps(dict(
        source_revision=revision,total_rows=74,runnable_scripted_variants=73,base_tasks_with_scripted_reference=22,
        scene_only_task=2,
        scope_notes=["All rows come from APPENDIX in the official registry.","Variants change object geometry, spring force, rotation amount or starting state and share Table C1 base tasks.","Task 2 is a scene with criterion-state readouts but no scripted policy or automatic verdict.","Other tasks and arbitrary --set option combinations are outside the fixed74-row registry.","No GPU rollout was run by this catalog ingestion.","The physical website's file IDs differ from the paper's Table C1 numbering.","Simulation photos are source-released overview or variant examples, not generated task demonstrations."],
        documentation_source=base+"docs/tasks.md",record_counts=dict(Counter(record["split"] for record in records)),
    ),indent=2))
    print("ContactBench simulation catalog",len(records),"rows;",sum(record["scripted"] for record in records),"scripted variants")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached",action="store_true",help="Build from retained source files without network access")
    args=parser.parse_args()
    if not args.cached:
        fetch_sources()
    build_catalog()

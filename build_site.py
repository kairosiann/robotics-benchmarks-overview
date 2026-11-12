"""Package the guide and agent-readable records for static web hosting."""

import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "_site"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build():
    tasks = json.loads((ROOT / "tasks.json").read_text(encoding="utf-8"))
    identifiers = [task["id"] for task in tasks]
    if len(set(identifiers)) != len(tasks):
        raise ValueError("Task IDs must be unique")
    DESTINATION.mkdir(exist_ok=True)
    records = DESTINATION / "data" / "tasks"
    if records.exists():
        shutil.rmtree(records)
    records.mkdir(parents=True)
    shutil.copyfile(ROOT / "robotics-benchmark-guide.html", DESTINATION / "index.html")
    for name in ("tasks.json", "coverage.json", "corl_review.json", "TASK_API.md", "task-api.openapi.json", "THIRD_PARTY.md"):
        shutil.copyfile(ROOT / name, DESTINATION / name)
    license_destination = DESTINATION / "third-party-licenses"
    if license_destination.exists():
        shutil.rmtree(license_destination)
    shutil.copytree(ROOT / "sources" / "review" / "licenses", license_destination)
    index = []
    for task in tasks:
        filename = hashlib.sha256(task["id"].encode("utf-8")).hexdigest()[:24] + ".json"
        record_path = records / filename
        if record_path.exists():
            raise ValueError("Task record filename collision")
        write_json(record_path, task)
        item = {key: task[key] for key in ("id", "title", "name", "family", "benchmark", "suite", "setting", "description", "source") if key in task}
        item["record_url"] = "data/tasks/" + filename
        index.append(item)
    write_json(DESTINATION / "catalog.json", index)
    (DESTINATION / ".nojekyll").touch()
    (DESTINATION / "model-guide.md").write_text(
        "# Referencing the robotics benchmark catalog\n\n"
        "Fetch catalog.json relative to this page to discover task IDs, titles, descriptions, and record_url links. "
        "Follow record_url relative to the site root to retrieve one complete task record. "
        "Download tasks.json for the full catalog, and coverage.json for inventory and version notes.\n\n"
        "Preserve observation_scope and grading_scope when comparing tasks. Cite source, observation_source, "
        "setup_source, and evaluation_source where available. Read the original goal and scoring criteria "
        "before asserting equivalence between tasks. Missing fields indicate unavailable evidence.\n\n"
        "This static site supports browser search and downloadable records. TASK_API.md and "
        "task-api.openapi.json describe the separately runnable Python API.\n",
        encoding="utf-8",
    )
    print(f"Packaged {len(tasks):,} task records and guide in {DESTINATION}")


if __name__ == "__main__":
    build()

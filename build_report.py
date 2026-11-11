import base64
import json
import mimetypes
import re
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ("libero_tree.json", "behavior_tree.html", "bddl_tree.html", "casa_tree.html")


def embedded_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build():
    tasks = json.loads((ROOT / "tasks.json").read_text(encoding="utf-8"))
    concepts = json.loads((ROOT / "task_concepts.json").read_text(encoding="utf-8"))
    coverage_path = ROOT / "coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8")) if coverage_path.exists() else {}
    families = {task["family"] for task in tasks if task.get("family")}
    images = {}
    for path in (ROOT / "media").iterdir():
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            mime_type, _ = mimetypes.guess_type(path.name)
            content = base64.b64encode(path.read_bytes()).decode("ascii")
            images[path.stem] = f"data:{mime_type};base64,{content}"

    revisions = []
    for name in SNAPSHOTS:
        source = json.loads((ROOT / "sources" / name).read_text(encoding="utf-8"))
        revisions.append(f'{name.split("_tree")[0]}: {source["sha"]}')

    values = {
        "TASKCOUNT": f"{len(tasks):,}",
        "FAMILYCOUNT": str(len(families)),
        "CATALOG_DATE": escape(str(coverage.get("updated_at", "November 10, 2026"))),
        "COVERAGEDATA": embedded_json(coverage),
        "SNAPSHOTS": " · ".join(revisions),
        "TASKDATA": embedded_json(tasks),
        "IMAGEDATA": embedded_json({key: value for key, value in images.items() if key.startswith("DC-")}),
        "SEARCH_CONCEPTS": embedded_json(concepts),
        "SEARCH_SCRIPT": (ROOT / "task_search.js").read_text(encoding="utf-8"),
        "EXPLORER_SCRIPT": (ROOT / "task_explorer.js").read_text(encoding="utf-8"),
        "EXPLORER_CSS": (ROOT / "task_explorer.css").read_text(encoding="utf-8"),
    }
    template = (ROOT / "guide.template.html").read_text(encoding="utf-8")
    template = re.sub(r'data-asset="([^"]+)"', lambda match: f'src="{images[match[1]]}" loading="lazy"', template)
    report = re.sub(r"__([A-Z_]+)__", lambda match: values[match[1]], template)
    destination = ROOT / "robotics-benchmark-guide.html"
    temporary = destination.with_suffix(".html.tmp")
    temporary.write_text(report, encoding="utf-8")
    temporary.replace(destination)
    print("Built", destination, destination.stat().st_size, "bytes")


if __name__ == "__main__":
    build()

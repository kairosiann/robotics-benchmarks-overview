import base64
import json
import mimetypes
import re
import struct
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ("libero_tree.json", "behavior_tree.html", "bddl_tree.html", "casa_tree.html")


def image_dimensions(data):
    """Read intrinsic PNG/JPEG dimensions without a build-time image library."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset < len(data):
            if data[offset] != 0xFF:
                raise ValueError("Invalid JPEG marker")
            while data[offset] == 0xFF:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            length = int.from_bytes(data[offset:offset + 2], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return width, height
            offset += length
    raise ValueError("Embedded figures need PNG or JPEG dimensions")


def embedded_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build():
    tasks = json.loads((ROOT / "tasks.json").read_text(encoding="utf-8"))
    concepts = json.loads((ROOT / "task_concepts.json").read_text(encoding="utf-8"))
    coverage_path = ROOT / "coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8")) if coverage_path.exists() else {}
    families = {task["family"] for task in tasks if task.get("family")}
    images = {}
    dimensions = {}
    for path in (ROOT / "media").iterdir():
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            mime_type, _ = mimetypes.guess_type(path.name)
            data = path.read_bytes()
            content = base64.b64encode(data).decode("ascii")
            images[path.stem] = f"data:{mime_type};base64,{content}"
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                dimensions[path.stem] = image_dimensions(data)

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
    def embed_figure(match):
        key = match[1]
        width, height = dimensions[key]
        return f'src="{images[key]}" width="{width}" height="{height}" loading="lazy"'

    template = re.sub(r'data-asset="([^"]+)"', embed_figure, template)
    report = re.sub(r"__([A-Z_]+)__", lambda match: values[match[1]], template)
    destination = ROOT / "robotics-benchmark-guide.html"
    temporary = destination.with_suffix(".html.tmp")
    temporary.write_text(report, encoding="utf-8")
    temporary.replace(destination)
    print("Built", destination, destination.stat().st_size, "bytes")


if __name__ == "__main__":
    build()

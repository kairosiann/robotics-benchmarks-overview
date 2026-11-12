"""Check the actual static deployment artifact, including every model record.

Run after build_report.py and build_site.py. No third-party packages required.
"""

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent


class Guide(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.images = []
        self.scripts = {}
        self.script_id = None
        self.h1_count = 0

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "img":
            self.images.append(attrs)
        if tag == "h1":
            self.h1_count += 1
        if tag == "script":
            assert not attrs.get("src"), "The guide must not need a remote JavaScript dependency"
            self.script_id = attrs.get("id")
            if self.script_id:
                self.scripts[self.script_id] = ""

    def handle_data(self, data):
        if self.script_id:
            self.scripts[self.script_id] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.script_id = None


def validate(site=None):
    site = site or ROOT / "_site"
    tasks = json.loads((ROOT / "tasks.json").read_text())
    deployed = json.loads((site / "tasks.json").read_text())
    assert deployed == tasks, "Deployed catalog is stale"
    index = json.loads((site / "catalog.json").read_text())
    by_id = {row["id"]: row for row in tasks}
    assert len(index) == len(tasks) == len(by_id), "Catalog count or ID collision"
    assert {row["id"] for row in index} == set(by_id), "Discovery index loses tasks"
    record_urls = set()
    for row in index:
        relative = row["record_url"]
        parts = urlsplit(relative)
        assert not parts.scheme and not parts.netloc and not relative.startswith("/"), relative
        path = (site / unquote(parts.path)).resolve()
        assert path.is_relative_to(site.resolve()), "Record path escapes site"
        assert relative not in record_urls, "Two IDs share a record URL"
        record_urls.add(relative)
        assert json.loads(path.read_text()) == by_id[row["id"]], f"Wrong record: {row['id']}"
    assert len(list((site / "data" / "tasks").glob("*.json"))) == len(tasks), "Stale record files"
    html = (site / "index.html").read_text()
    assert html == (ROOT / "robotics-benchmark-guide.html").read_text(), "Guide copy is stale"
    assert "__TASKDATA__" not in html and "__TASKCOUNT__" not in html, "Unexpanded template"
    guide = Guide()
    guide.feed(html)
    assert guide.h1_count == 1, "Guide needs one main title"
    assert len(guide.ids) == len(set(guide.ids)), "Duplicate HTML IDs"
    assert all("alt" in attrs for attrs in guide.images), "Image lacks an alternative description"
    assert all(attrs.get("width") and attrs.get("height") for attrs in guide.images), "Figure lacks intrinsic dimensions"
    assert json.loads(guide.scripts["task-data"]) == tasks, "Browser and model catalogs disagree"
    assert json.loads(guide.scripts["coverage-data"]) == json.loads((site / "coverage.json").read_text())
    local_links = 0
    for link in guide.links:
        parts = urlsplit(link)
        if parts.scheme or parts.netloc:
            continue
        if parts.path:
            path = (site / unquote(parts.path)).resolve()
            assert path.is_relative_to(site.resolve()) and path.is_file(), f"Broken local link: {link}"
        elif parts.fragment:
            assert unquote(parts.fragment) in guide.ids, f"Missing anchor: {link}"
        local_links += 1
    for private_tree in (".git", "sources", "__pycache__", ".github"):
        assert not (site / private_tree).exists(), f"Deployment unexpectedly includes {private_tree}"
    for name in ("model-guide.md", "corl_review.json", "TASK_API.md", "task-api.openapi.json", "THIRD_PARTY.md"):
        assert (site / name).is_file(), f"Missing deployment document: {name}"
    assert (site / "third-party-licenses" / "inventory.json").is_file(), "Missing license inventory"
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "tasks": len(tasks),
        "families": len({row["family"] for row in tasks}),
        "individual_records_checked": len(record_urls),
        "local_links_checked": local_links,
        "embedded_catalog_matches": True,
        "external_link_availability_checked": False,
        "note": "Static artifact integrity, not a scientific replication or media-rights determination.",
    }
    (ROOT / "validation-site.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    validate()

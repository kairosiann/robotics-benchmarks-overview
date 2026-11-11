#!/usr/bin/env python3
"""Serve the robotics task catalog and search API on a local HTTP port."""

import argparse
from collections import Counter, defaultdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
from urllib.parse import parse_qs, quote, unquote, urlsplit

from task_search import SearchIndex


ROOT = Path(__file__).resolve().parent
SEARCH_PARAMETERS = {"q", "mode", "family", "benchmark", "suite", "setting", "limit", "offset"}
MODES = {"related", "all", "exact"}
PREVIEW_FIELDS = (
    "record_kind", "reported_task_count",
    "source_note", "catalog_scope",
    "id", "name", "title", "family", "benchmark", "suite", "split", "setting", "description", "instruction",
    "setup_summary", "setup_source", "observation", "observation_scope", "observation_source",
    "grading_summary", "grading_scope", "grading_evidence", "evaluation_source", "source",
    "video", "image", "media", "media_source",
)
STATIC_FILES = {
    "/": ("robotics-benchmark-guide.html", "text/html; charset=utf-8"),
    "/robotics-benchmark-guide.html": ("robotics-benchmark-guide.html", "text/html; charset=utf-8"),
    "/TASK_API.md": ("TASK_API.md", "text/markdown; charset=utf-8"),
    "/api/openapi.json": ("task-api.openapi.json", "application/json; charset=utf-8"),
    "/task-api.openapi.json": ("task-api.openapi.json", "application/json; charset=utf-8"),
    "/coverage.json": ("coverage.json", "application/json; charset=utf-8"),
    "/corl_review.json": ("corl_review.json", "application/json; charset=utf-8"),
}


def integer_parameter(params, name, default, minimum, maximum=None):
    try:
        value = int(params.get(name, default))
    except ValueError:
        value = minimum - 1
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"from {minimum} to {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValueError(f"{name} must be an integer {bounds}.")
    return value


class TaskCatalog:
    """One in-memory snapshot shared by every request."""

    def __init__(self, tasks):
        self.by_id = {task["id"]: task for task in tasks}
        if len(self.by_id) != len(tasks) or any(not task_id for task_id in self.by_id):
            raise ValueError("The task catalog must contain unique, nonempty IDs.")
        self.index = SearchIndex(tasks)
        versions = defaultdict(list)
        for task in tasks:
            versions[task["benchmark"]].append(task)
        self.metadata = {
            "total": len(tasks),
            "record_kinds": dict(sorted(Counter(task.get("record_kind", "task-entry") for task in tasks).items())),
            "families": dict(sorted(Counter(task["family"] for task in tasks).items())),
            "settings": dict(sorted(Counter(task["setting"] for task in tasks).items())),
            "benchmarks": [
                {
                    "name": name,
                    "family": records[0]["family"],
                    "count": len(records),
                    "suites": dict(sorted(Counter(task["suite"] for task in records).items())),
                    "splits": dict(sorted(Counter(task["split"] for task in records if task.get("split")).items())),
                }
                for name, records in sorted(versions.items())
            ],
        }

    def search(self, params):
        unknown = set(params) - SEARCH_PARAMETERS
        if unknown:
            raise ValueError(f"Unknown search parameter: {', '.join(sorted(unknown))}.")
        if any(len(values) != 1 for values in params.values()):
            raise ValueError("Supply each search parameter once.")
        params = {name: values[0].strip() for name, values in params.items()}
        query = params.get("q", "")
        if len(query) > 1000:
            raise ValueError("q must be 1,000 characters or fewer.")
        mode = params.get("mode", "related")
        if mode not in MODES:
            raise ValueError("mode must be related, all, or exact.")
        limit = integer_parameter(params, "limit", 20, 1, 100)
        offset = integer_parameter(params, "offset", 0, 0)
        filters = {key: params.get(key, "") for key in ("family", "benchmark", "suite", "setting")}
        matches = self.index.search(query, mode=mode, **filters)
        results = []
        for match in matches[offset : offset + limit]:
            task = match["task"]
            preview = {key: task[key] for key in PREVIEW_FIELDS if key in task}
            results.append({
                "task": preview,
                "task_url": "/api/tasks/" + quote(task["id"], safe=""),
                "score": match["score"],
                "matches": match["matches"],
            })
        return {
            "query": query,
            "query_terms": self.index.describe_query(query, mode),
            "mode": mode,
            "filters": filters,
            "total": len(matches),
            "counts_by_family": dict(sorted(Counter(match["task"]["family"] for match in matches).items())),
            "offset": offset,
            "limit": limit,
            "next_offset": offset + limit if offset + limit < len(matches) else None,
            "results": results,
        }


class TaskHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.route()
        except (BrokenPipeError, ConnectionResetError):
            # Closing the guide while it is downloading is normal.
            pass

    do_HEAD = do_GET

    def route(self):
        try:
            url = urlsplit(self.path)
            params = parse_qs(url.query, keep_blank_values=True, max_num_fields=12)
        except ValueError:
            self.error(HTTPStatus.BAD_REQUEST, "Malformed request URL or too many query parameters.")
            return
        path = url.path
        catalog = self.server.catalog
        if path == "/health":
            self.send_json({"status": "ok", "tasks": catalog.metadata["total"]})
        elif path == "/api/catalog":
            self.send_json(catalog.metadata)
        elif path == "/tasks.json":
            self.send_json(list(catalog.by_id.values()))
        elif path == "/api/search":
            try:
                self.send_json(catalog.search(params))
            except ValueError as error:
                self.error(HTTPStatus.BAD_REQUEST, str(error))
        elif path.startswith("/api/tasks/"):
            task = catalog.by_id.get(unquote(path.removeprefix("/api/tasks/")))
            if task is None:
                self.error(HTTPStatus.NOT_FOUND, "No task with that ID. Search /api/search for task IDs.")
            else:
                self.send_json(task)
        elif path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            self.send_file(ROOT / filename, content_type)
        else:
            self.error(HTTPStatus.NOT_FOUND, "Endpoint not found. See /api/openapi.json.")

    def send_json(self, payload, status=HTTPStatus.OK):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_content_headers(status, "application/json; charset=utf-8", len(content))
        if self.command != "HEAD":
            self.wfile.write(content)

    def send_file(self, path, content_type):
        try:
            file = path.open("rb")
        except FileNotFoundError:
            self.error(HTTPStatus.NOT_FOUND, f"{path.name} is missing. Rebuild the guide if needed.")
            return
        with file:
            self.send_content_headers(HTTPStatus.OK, content_type, os.fstat(file.fileno()).st_size)
            if self.command != "HEAD":
                shutil.copyfileobj(file, self.wfile)

    def send_content_headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def error(self, status, message):
        self.send_json({"error": {"status": int(status), "message": message}}, status)

    def send_error(self, code, message=None, explain=None):
        self.error(code, message or HTTPStatus(code).phrase)

    def log_request(self, code="-", size="-"):
        # Proposal text can appear in q. Keep it out of request logs.
        self.log_message("%s %s %s", self.command, self.path.split("?", 1)[0], code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", default=8766, type=int, help="HTTP port (default: 8766)")
    parser.add_argument("--data", default=ROOT / "tasks.json", type=Path, help="Catalog JSON file")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    try:
        catalog = TaskCatalog(json.loads(args.data.read_text(encoding="utf-8")))
        server = ThreadingHTTPServer((args.host, args.port), TaskHandler)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Could not start task API: {error}\n")
    server.catalog = catalog
    with server:
        print(f"Task API at http://{args.host}:{server.server_port}/ ({catalog.metadata['total']:,} entries)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate the catalog, local HTTP contract, and Python/JavaScript search parity.

Run from any directory: python3 /path/to/validate_catalog.py
Uses Python's standard library and Node.js; does not fetch external resources.
"""

import argparse
from collections import Counter
from contextlib import redirect_stderr
from datetime import datetime, timezone
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import quote, urlencode, urlsplit

from task_api import ROOT, STATIC_FILES, TaskCatalog, TaskHandler
from task_search import SearchIndex


CASES = [
    {"query": ""},
    {"query": "plug a cable into a port and verify the connection"},
    {"query": "tighten nut"},
    {"query": "human interruption"},
    {"query": "stack cups"},
    {"query": "thread nut onto screw"},
    {"query": "open drawer"},
    {"query": "pick up object"},
    {"query": "wipe spill"},
    {"query": "force control"},
    {"query": "collision with human"},
    {"query": "assemble chair"},
    {"query": '"thread nut" screw', "mode": "all"},
    {"query": "fully inserted", "mode": "exact"},
    {"query": "USBConnector", "mode": "exact"},
    {"query": "TURN_ON stove"},
    {"query": "the and robot"},
    {"query": "☃ !!"},
    {"query": '"unterminated phrase'},
    {"query": "Café — mélange"},
    {"query": "xyzzynotarealtask", "mode": "all"},
    {"query": "", "family": "HARP-BENCH", "suite": "split:Paper evaluation subset"},
    {"query": "plug", "family": "ContactBench", "benchmark": "ContactBench simulation release"},
    {"query": "", "setting": "Simulation"},
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate_schema(value, schema, document, location="response"):
    """Check the JSON Schema features used by this API without dependencies."""
    if "$ref" in schema:
        target = document
        for key in schema["$ref"][2:].split("/"):
            target = target[key]
        validate_schema(value, target, document, location)
    for part in schema.get("allOf", []):
        validate_schema(value, part, document, location)
    kinds = schema.get("type", [])
    if isinstance(kinds, str):
        kinds = [kinds]
    types = {"null": value is None, "object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": type(value) is int,
             "number": type(value) in (int, float), "boolean": type(value) is bool}
    require(not kinds or any(types.get(kind, False) for kind in kinds), f"Schema type mismatch: {location}")
    if "enum" in schema:
        require(value in schema["enum"], f"Schema enum mismatch: {location}")
    if "const" in schema:
        require(value == schema["const"], f"Schema const mismatch: {location}")
    if isinstance(value, dict):
        require(set(schema.get("required", [])) <= set(value), f"Schema required field missing: {location}")
        for key, item in value.items():
            child = schema.get("properties", {}).get(key)
            if child is None and isinstance(schema.get("additionalProperties"), dict):
                child = schema["additionalProperties"]
            if child is not None:
                validate_schema(item, child, document, location + "." + key)
    if isinstance(value, list) and "items" in schema:
        for position, item in enumerate(value):
            validate_schema(item, schema["items"], document, f"{location}[{position}]")
    if isinstance(value, str) and "maxLength" in schema:
        require(len(value) <= schema["maxLength"], f"Schema string exceeds limit: {location}")
    if type(value) in (int, float):
        require("minimum" not in schema or value >= schema["minimum"], f"Schema value below limit: {location}")
        require("maximum" not in schema or value <= schema["maximum"], f"Schema value above limit: {location}")


def validate_records(records):
    mandatory = ("id", "name", "title", "family", "benchmark", "suite", "setting", "source")
    scope_values = {"task", "variant", "suite", "benchmark", "unavailable"}
    for record in records:
        for key in mandatory:
            require(isinstance(record.get(key), str) and record[key].strip(), f"Invalid {key}: {record.get('id')}")
        require(re.fullmatch(r"[a-z0-9][a-z0-9._-]*", record["id"]), "Unsafe task ID")
        require(urlsplit(record["source"]).scheme in {"https", "http"}, f"Missing source URL: {record['id']}")
        for key in ("observation_scope", "grading_scope"):
            require(record.get(key) in scope_values, f"Invalid {key}: {record['id']}")
        if record["observation_scope"] != "unavailable":
            require(record.get("observation") and record.get("observation_source"), f"Observation lacks evidence: {record['id']}")
        if record["grading_scope"] != "unavailable":
            require(record.get("grading_summary") and record.get("evaluation_source"), f"Grading lacks evidence: {record['id']}")
        for item in record.get("media", []):
            require(set(item) >= {"url", "type", "label", "scope"}, f"Malformed media: {record['id']}")
            require(item["scope"] in {"task", "variant", "benchmark"}, f"Unscoped media: {record['id']}")
            require(item["type"] in {"image", "video"}, f"Unknown media kind: {record['id']}")
            url = urlsplit(item["url"])
            require(url.scheme in {"http", "https"} and url.netloc, f"Unsafe media URL: {record['id']}")
            require(not re.search(r"(?:X-Amz-Signature|X-Goog-Signature|Expires)=", url.query, re.I), f"Expiring media URL: {record['id']}")
    ids = [record["id"] for record in records]
    require(len(ids) == len(set(ids)), "Duplicate IDs")
    return {"records": len(records), "families": dict(sorted(Counter(x["family"] for x in records).items())),
            "record_kinds": dict(Counter(x.get("record_kind", "task-entry") for x in records)),
            "media_items": sum(len(x.get("media", [])) for x in records)}


def compact_results(index, case):
    options = {key: value for key, value in case.items() if key != "query"}
    return {"terms": index.describe_query(case["query"], options.get("mode", "related")),
            "results": [{"id": item["task"]["id"], "score": item["score"], "matches": item["matches"]}
                        for item in index.search(case["query"], **options)]}


def validate_search(catalog, records):
    require(shutil.which("node"), "Node.js is required for Python/JavaScript parity checks")
    concepts = json.loads((ROOT / "task_concepts.json").read_text())
    synthetic = [dict(id="structured", title="Café USBConnector", name="structured",
                      objects={"rack": ["blue cable", "red nut"]}, setup=["part A", {"slot": "socket"}],
                      aliases=["registryAliasOne", "registryAliasTwo"], family="Straße", suite="Öther", setting="Simulation")]
    groups = [(records, CASES), (synthetic, [
        {"query": "blue cable", "mode": "exact"}, {"query": "red nut", "mode": "all"},
        {"query": "registryAliasTwo"}, {"query": "USB connector", "mode": "exact"},
        {"query": "cafe"}, {"query": "socket", "family": "STRAßE", "suite": "öther"},
    ])]
    program = r'''
const fs = require("fs");
const vm = require("vm");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const Search = vm.runInNewContext(fs.readFileSync(input.script, "utf8") + "\nTaskSearch;");
const result = input.groups.map(group => {
  const index = Search.createIndex(group.tasks, input.concepts);
  return group.cases.map(({query, ...options}) => ({
    terms: Search.describeQuery(index, query, options.mode || "related"),
    results: Search.search(index, query, options).map(({task, score, matches}) => ({id: task.id, score, matches})),
  }));
});
let rejected = 0;
const index = Search.createIndex(input.groups[1].tasks, input.concepts);
for (const call of [() => Search.search(index, "cable", {mode: "bad"}), () => Search.describeQuery(index, "cable", "bad")]) {
  try { call(); } catch (error) { rejected++; }
}
process.stdout.write(JSON.stringify({result, rejected}));
'''
    output = subprocess.run(["node", "-e", program], input=json.dumps({
        "script": str(ROOT / "task_search.js"), "concepts": concepts,
        "groups": [{"tasks": tasks, "cases": cases} for tasks, cases in groups],
    }), text=True, capture_output=True, check=True, timeout=90)
    js = json.loads(output.stdout)
    require(js["rejected"] == 2, "JS accepts invalid search mode")
    retrieval = []
    for group_number, (tasks, cases) in enumerate(groups):
        index = catalog.index if group_number == 0 else SearchIndex(tasks, concepts)
        for case_number, case in enumerate(cases):
            expected = compact_results(index, case)
            require(expected == js["result"][group_number][case_number], f"Search parity failed: {case}")
            if group_number == 0:
                retrieval.append({"query": case["query"], "options": {k: v for k, v in case.items() if k != "query"},
                                  "total": len(expected["results"]), "top_ids": [x["id"] for x in expected["results"][:5]]})
    for call in (lambda: catalog.index.search("cable", mode="bad"), lambda: catalog.index.describe_query("cable", "bad")):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("Python accepts invalid search mode")
    # These are retrieval quality expectations, not only implementation parity.
    expectations = {"assemble chair": "FurnitureBench", "human interruption": "HARP-Bench", "tighten nut": "ContactBench"}
    for query, family in expectations.items():
        require(any(x["task"]["family"] == family for x in catalog.index.search(query)[:5]), f"Expected candidate missing: {query}")
    exact = catalog.index.search("fully inserted", mode="exact")
    require(exact and all(len(item["matches"]) == 1 and item["matches"][0]["matched"] == "fully inserted" for item in exact), "Exact phrase matching failed")
    return {"parity_cases": sum(len(cases) for _, cases in groups), "retrieval_cases": retrieval}


def validate_http(catalog, records):
    class QuietHandler(TaskHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    server.catalog = catalog
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    count = 0
    specification = json.loads((ROOT / "task-api.openapi.json").read_text())

    def request(path, status=200, method="GET", json_body=True):
        nonlocal count
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=15)
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        headers = dict(response.getheaders())
        connection.close()
        require(response.status == status, f"{method} {path[:100]}: wanted {status}, got {response.status}")
        require(headers.get("Cache-Control") == "no-store", "Response must disable caching")
        require(headers.get("X-Content-Type-Options") == "nosniff", "Missing nosniff header")
        if method == "HEAD":
            require(not body, "HEAD returned a response body")
        else:
            require(int(headers["Content-Length"]) == len(body), "Incorrect response length")
        count += 1
        if json_body and method != "HEAD":
            payload = json.loads(body)
            if status >= 400:
                require(payload["error"]["status"] == status and payload["error"]["message"], "Malformed JSON error")
                validate_schema(payload, specification["components"]["schemas"]["Error"], specification)
            elif path.startswith("/api/tasks/"):
                validate_schema(payload, specification["components"]["schemas"]["TaskDetail"], specification)
            else:
                operation = specification["paths"].get(urlsplit(path).path, {}).get("get")
                if operation:
                    validate_schema(payload, operation["responses"]["200"]["content"]["application/json"]["schema"], specification)
            return payload
        return headers

    try:
        require(request("/health")["tasks"] == len(records), "Wrong health count")
        metadata = request("/api/catalog")
        require(sum(metadata["families"].values()) == len(records) == sum(x["count"] for x in metadata["benchmarks"]), "Catalog counts disagree")
        require(request("/tasks.json") == records, "Raw catalog differs")
        for path in STATIC_FILES:
            request(path, json_body=False)
            request(path, method="HEAD", json_body=False)
        require(request("/api/openapi.json")["openapi"] == "3.1.0", "OpenAPI unavailable")
        page = request("/api/search?limit=3")
        next_page = request("/api/search?limit=3&offset=" + str(page["next_offset"]))
        require(page["total"] == len(records) and page["next_offset"] == 3, "Pagination count wrong")
        require({x["task"]["id"] for x in page["results"]}.isdisjoint(x["task"]["id"] for x in next_page["results"]), "Pagination repeated IDs")
        require(request("/api/search?offset=" + str(len(records)))["next_offset"] is None, "Empty final page should not continue")
        require(not request("/api/search?q=xyzzynotarealtask")["results"], "Unknown query should be empty")
        for family in metadata["families"]:
            filtered = request("/api/search?" + urlencode({"family": family, "limit": 1}))
            require(filtered["total"] == metadata["families"][family], f"Filter count wrong for {family}")
        for options in ({"suite": "split:Paper evaluation subset", "family": "HARP-Bench"}, {"family": "ContactBench", "benchmark": "ContactBench simulation release"}, {"setting": records[0]["setting"]}):
            require(request("/api/search?" + urlencode(options))["total"] == len(catalog.index.search("", **options)), f"Filter mismatch: {options}")
        # One complete detail from every family plus the first search URL.
        sampled = {next(x["id"] for x in records if x["family"] == family) for family in metadata["families"]}
        sampled.add(page["results"][0]["task"]["id"])
        for task_id in sampled:
            require(request("/api/tasks/" + quote(task_id, safe="")) == catalog.by_id[task_id], "Detail lost fields")
        request("/api/search?q=cable", method="HEAD")
        request("/api/tasks/" + records[0]["id"], method="HEAD")
        for query in ("limit=0", "limit=101", "limit=bad", "offset=-1", "limit=", "mode=bad", "unknown=yes", "q=one&q=two", "q=" + "x" * 1001, "q=" + "+" * 1001, "&".join("q=x" for _ in range(13))):
            request("/api/search?" + query, status=400)
        for path in ("/api/tasks/unknown", "/.git/config", "/sources/contactbench_sim/README.md", "/../task_api.py", "/%2e%2e/task_api.py", "/api/../sources", "/api/tasks/%2e%2e%2f.git%2fconfig"):
            request(path, status=404)
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            headers = request("/api/search", status=405, method=method, json_body=False)
            require(headers["Allow"] == "GET, HEAD", "Missing allowed methods")
        # Proposal terms must be omitted from access logs.
        log = io.StringIO()
        handler = object.__new__(TaskHandler)
        handler.command, handler.path = "GET", "/api/search?q=private-proposal-marker"
        handler.log_message = lambda format, *args: print(format % args, file=log)
        handler.log_request(200)
        require("private-proposal-marker" not in log.getvalue(), "Query text leaked to access log")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return {"requests": count, "bind_address": server.server_address[0], "sampled_task_details": len(sampled), "query_logging": "omitted"}


def validate_openapi(records):
    schema = json.loads((ROOT / "task-api.openapi.json").read_text())
    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                reference = value["$ref"]
                require(reference.startswith("#/"), "Unexpected remote OpenAPI reference")
                target = schema
                for component in reference[2:].split("/"):
                    target = target[component]
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(schema)
    for record in records:
        validate_schema(record, schema["components"]["schemas"]["TaskDetail"], schema, record["id"])
    for path in ("/health", "/api/catalog", "/api/search", "/api/tasks/{id}", "/tasks.json", "/api/openapi.json"):
        require(path in schema["paths"], f"Undocumented JSON endpoint: {path}")
    return {"paths": len(schema["paths"]), "references": "resolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "validation-functional.json")
    args = parser.parse_args()
    start = time.monotonic()
    report = {"validated_at": datetime.now(timezone.utc).isoformat(), "status": "failed"}
    try:
        snapshot = (ROOT / "tasks.json").read_bytes()
        records = json.loads(snapshot)
        report["catalog_sha256"] = hashlib.sha256(snapshot).hexdigest()
        report["catalog"] = validate_records(records)
        catalog = TaskCatalog(records)
        for invalid in ([], {}, [dict(records[0], id="../bad")], [records[0], records[0]], [dict(records[0], benchmark=42)]):
            try:
                TaskCatalog(invalid)
            except ValueError:
                continue
            raise AssertionError("Malformed catalog accepted")
        report["search"] = validate_search(catalog, records)
        report["http"] = validate_http(catalog, records)
        report["openapi"] = validate_openapi(records)
        report["status"] = "passed"
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - start, 2)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Functional validation {report['status']}: {args.output.name} ({report['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()

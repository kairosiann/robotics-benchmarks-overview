# Robotics benchmark task API

Start the server from the cloned repository directory with Python 3.10 or newer. No packages or API keys are required.

```sh
python3 task_api.py
```

Open `http://127.0.0.1:8766/` for the guide. The same server exposes the catalog through read-only HTTP endpoints and publishes [an OpenAPI schema](task-api.openapi.json) at `/api/openapi.json`. It loads the versioned `tasks.json` snapshot at startup. Restart it after rebuilding the catalog. Use `--port` if the default port is occupied.

From the original parent workspace, use `python3 reports/robotics-benchmarks/task_api.py`. Paths to the catalog and guide resolve relative to the script, so the server can start from any working directory.

| Endpoint | Use |
| --- | --- |
| `GET /api/search` | Find tasks and inspect why each task matched. |
| `GET /api/tasks/{id}` | Retrieve the full task record, including the goal or rubric and initial conditions when available. |
| `GET /api/catalog` | List benchmark families, versions, settings, suites, splits, and their counts. |
| `GET /health` | Check that the server is running and the catalog is loaded. |
| `GET /api/openapi.json` | Retrieve operation descriptions, parameters, and response schemas. |
| `GET /tasks.json` | Download the full loaded catalog snapshot. |

```sh
curl -G 'http://127.0.0.1:8766/api/search' \
  --data-urlencode 'q=plug a cable into a port and verify the connection' \
  --data-urlencode 'mode=related' \
  --data-urlencode 'limit=5'
```

Each result includes a task preview with setup, observations, grading, and links to sources where available. Compare the response's `query_terms` against a result's `matches` to see which requested concepts were found and where they appeared. The integer `score` orders search results for that query. Use `task_url` to fetch the full record.

`mode=related` ranks matches using shared terms and concepts. `mode=all` requires all meaningful query terms to match. `mode=exact` matches a contiguous normalized phrase. An empty `q` browses the inventory. Use `family`, `benchmark`, `suite`, or `setting` to narrow results using the labels returned by `/api/catalog`. For a RoboCasa365 paper split, supply a suite filter like `suite=split:Composite-Seen`.

Pages use `limit` (1–100, default 20) and `offset` (default 0). Keep the query and filters unchanged and use `next_offset` to fetch another page. `counts_by_family` counts matches across the entire filtered result set. Search accepts a maximum of 1,000 query characters and rejects unknown or repeated parameters. Filters match full labels without regard to case; an unknown label returns an empty result set. HTTP errors contain `error.status` and `error.message`. `HEAD` returns the same headers without a response body; mutation methods return `405` with `Allow: GET, HEAD`.

Quotes group a literal phrase in `related` or `all` mode, for example `"thread nut" screw`. Search uses deterministic keywords and a shared alias vocabulary; the score is an ordering aid for that query, not a semantic similarity percentage, equivalence finding, or evidence that a proposed task is novel. Read `query_terms`, `matches`, and the complete record before comparing evaluation criteria.

## Calling it from a model

Expose the search and detail operations as tools in your model's client. The client executes the HTTP requests and passes their JSON responses to the model. The model can search with a proposed task, select candidates by inspecting `matches`, then fetch the selected records and cite their `source` and `evaluation_source` URLs. The server binds to loopback by default, so a hosted model can use it through a tool client running on this machine.

```python
import json
from urllib.parse import quote, urlencode
from urllib.request import urlopen

BASE_URL = "http://127.0.0.1:8766"


def search_benchmark_tasks(query: str, limit: int = 8) -> dict:
    params = urlencode({"q": query, "mode": "related", "limit": limit})
    with urlopen(f"{BASE_URL}/api/search?{params}", timeout=5) as response:
        return json.load(response)


def get_benchmark_task(task_id: str) -> dict:
    with urlopen(f"{BASE_URL}/api/tasks/{quote(task_id, safe='')}", timeout=5) as response:
        return json.load(response)
```

Keep `observation_scope` with the observation text when comparing tasks. Some sources specify the robot inputs at the benchmark or evaluation-track level. Where a record summarizes a checker or an instruction, consult its original goal, rubric, or source before asserting an exact success threshold.

Check `record_kind` when assessing coverage. A `benchmark-overview` record summarizes a published benchmark whose individual task definitions were unavailable during ingestion. Its `reported_task_count` describes the source's claim. `/api/catalog` reports record-kind counts separately from the total entries.

## Local service and static hosting

The default service binds to `127.0.0.1`. It has no authentication, TLS, rate limiting, or cross-origin access headers. Keep the default binding for local tools. An explicit `--host 0.0.0.0` exposes the service to reachable network clients; an Internet service needs a separately configured authenticated proxy and deployment controls. The handler serves an explicit file allowlist, does not browse directories or execute downloaded benchmark code, and omits query strings from access logs. Catalog contents and source URLs are returned as data.

GitHub Pages serves the static guide, `catalog.json`, and downloadable JSON records. It does not run this Python API; `/api/search` on the Pages domain is unavailable. A hosted model needs an HTTP tool client able to reach this local server, or it can fetch the static catalog and records described in `model-guide.md` on the published site.

## Functional checks

Run `python3 validate_catalog.py` from the repository directory. This uses Python's standard library and Node.js to check catalog invariants, HTTP routes and errors on an ephemeral loopback port, and Python/JavaScript search parity. It writes `validation-functional.json` and exits unsuccessfully if a check fails. It does not run benchmark simulations or verify remote links.

# Robotics benchmarks overview

A sourced HTML guide and searchable task catalog for comparing proposed robotics benchmark tasks with published tasks. Includes LIBERO, RoboCasa, SIMPLER, BEHAVIOR, DataCenterBench, and RoboDojo.

The November 10, 2026 snapshot contains 1,818 versioned entries. Entries include source links, setup descriptions, available robot observations, grading summaries, exact task definitions or scoring checks, and official media where published. Some observations apply at benchmark or suite level. Each record labels that scope.

## Open the guide

Download and open [robotics-benchmark-guide.html](robotics-benchmark-guide.html) in a browser. Its text, task catalog, search, comparison interface, and embedded figures work offline. Optional official videos and additional photos load from their original hosts.

Search a keyword or proposed task description, filter by benchmark family or version, and pin up to three published tasks beside a proposal. Search uses controlled synonyms and lexical matching. Match evidence identifies the action, object, outcome, or keyword and the field where it appeared. Scores order retrieval results and do not measure robot capability or semantic equivalence.

## Run the local API

Requires Python 3.10 or newer, using only its standard library.

```sh
python3 task_api.py
```

Open http://127.0.0.1:8766/ for the guide. Search through `/api/search`, retrieve full evidence through `/api/tasks/{id}`, and list available facets through `/api/catalog`.

```sh
curl -G http://127.0.0.1:8766/api/search \
  --data-urlencode 'q=insert cable into port and verify connection' \
  --data-urlencode 'limit=5'
```

See [TASK_API.md](TASK_API.md) for model tool-client examples and [task-api.openapi.json](task-api.openapi.json) for the OpenAPI schema. A hosted model needs a tool client that can reach this local service.

## Rebuild from the retained snapshot

```sh
python3 build_data.py
python3 build_report.py
```

`tasks.json` is the structured catalog. `task_details.py` normalizes task evidence. The Python and JavaScript search engines share `task_concepts.json`. The `sources/` directory retains public source snapshots and task definitions used to assemble the catalog. `media/credits.json` records the downloaded figure and photograph URLs. The fetch scripts support source acquisition, but changes to upstream catalogs can require updates to their URLs and parsers.

## Coverage and attribution

Versioned entries include older catalogs, aliases, and auxiliary material, so the total is not a count of unique physical skills. The guide documents version differences and missing evidence. Review original task goals and scoring checks when assessing whether a proposed task has a close precedent.

Task definitions, source excerpts, figures, and media retain their respective authorship and applicable upstream terms. This repository does not grant additional rights to third-party materials. Source citations appear in the guide and individual task records.

## Candidate additions

Priorities for expanding coverage include [NIST assembly task boards](https://www.nist.gov/el/intelligent-systems-division-73500/robotic-grasping-and-manipulation-assembly/assembly), [FurnitureBench](https://clvrai.github.io/furniture-bench/), [ManiSkill](https://maniskill.readthedocs.io/en/latest/tasks/index.html), [RLBench](https://github.com/stepjam/RLBench), [RoboTwin](https://robotwin-platform.github.io/doc/tasks/), [CALVIN](https://github.com/mees/calvin), [RoboChallenge](https://robochallenge.ai/challenges), and [Adroit](https://github.com/Farama-Foundation/d4rl/wiki/Tasks). These are suggestions and have not been ingested into the catalog.

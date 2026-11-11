# Robotics benchmarks overview

A sourced HTML guide and searchable task catalog for comparing proposed robotics benchmark tasks with published tasks. Includes the original six benchmark families, eight additional manipulation/assembly benchmarks, and three task catalogs selected from the CoRL 2026 accepted program.

The November 11, 2026 snapshot contains 2,338 entries across 17 benchmark families. The expansion is described in [coverage.json](coverage.json), with task counts available through the guide and `/api/catalog`. Entries include source links, setup descriptions, available robot observations, grading summaries, exact task definitions or scoring checks, and official media where published. Some observations apply at benchmark or suite level. Each record labels that scope.

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

## Expansion and CoRL review

The added established suites are RLBench, ManiSkill, CALVIN, RoboTwin 2.0, NIST Assembly, FurnitureBench, RoboChallenge, and Adroit. Their catalog units differ. NIST includes operation groups and competencies; ManiSkill includes registered supporting environments; RoboChallenge keeps Table30 and Table30 V2 separate; Adroit keeps dense/sparse reward variants.

[corl_review.json](corl_review.json) records screening of 687 public accepted CoRL 2026 papers, including 33 title candidates concerning benchmarks or evaluation. Selected titles were verified in the official accepted program. Task ingestion uses authors’ papers and catalogs. The added suites are WireCraft (industrial flexible-wire manipulation), IMBench (physical reasoning and execution), and ATOM-Bench (atomic/compositional manipulation on paired physical tracks).

The review covers the public accepted program. HARP-Bench, LiquidLab, MESA, RMMBench and H2RBench remain candidates for later task-level ingestion. The review ledger preserves their paper links. The full-catalog expansion can be rebuilt from retained snapshots with `python3 fetch_corl_benchmarks.py`, then `python3 build_data.py` and `python3 build_report.py`. The two additional fetch scripts acquire the standard and physical benchmark source snapshots and emit their component catalogs.

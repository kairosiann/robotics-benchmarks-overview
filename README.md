# Robotics benchmarks overview

A sourced HTML guide and searchable task catalog for comparing proposed robotics benchmark tasks with published tasks. Includes the original six benchmark families, eight additional manipulation/assembly benchmarks, and three task catalogs selected from the CoRL 2026 accepted program.

The November 11, 2026 snapshot contains 2,900 entries across 23 benchmark families. The expansion is described in [coverage.json](coverage.json), with task counts available through the guide and `/api/catalog`. Entries include source links, setup descriptions, available robot observations, grading summaries, exact task definitions or scoring checks, and official media where published. Some observations apply at benchmark or suite level. Each record labels that scope.

## Open the guide

The GitHub Pages deployment publishes the guide at https://kairosiann.github.io/robotics-benchmarks-overview/ after the repository is public and the **Publish benchmark website** workflow succeeds. The workflow runs on pushes to `main` and can be started manually from the Actions tab. While the repository is private it skips deployment. After changing visibility, run the workflow manually or push a new commit. If Pages needs manual configuration, select **GitHub Actions** under **Settings → Pages → Build and deployment**.

The website exposes `catalog.json` for task discovery, `data/tasks/…json` for individual records (linked by `record_url` in the catalog), `tasks.json` for the complete dataset, and `model-guide.md` for agent usage. The Python API remains separately runnable. Build the static package locally with `python3 build_report.py` followed by `python3 build_site.py`; the generated `_site/` folder can be served by any static web host.

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

The review covers the public accepted program. The follow-up expansion adds HARP-Bench (49 canonical tasks, with the 37-task paper subset marked), MESA/BiMESA (285 concrete evaluation definitions), RMMBench (113 current registered definitions), and H2RBench (all four tasks). RMMBench’s paper, episode presets and current registry use different inventories, as documented on its records. LiquidLab has one explicitly labeled benchmark-overview record based on its accepted abstract. The source reports 16 tasks, but their individual definitions were unavailable during ingestion. The total entry count includes this overview. The review ledger preserves paper links and ingestion status. The full-catalog expansion can be rebuilt from retained snapshots with `python3 fetch_corl_benchmarks.py`, then `python3 build_data.py` and `python3 build_report.py`. The two additional fetch scripts acquire the standard and physical benchmark source snapshots and emit their component catalogs.

The follow-up catalogs can be regenerated with `fetch_mesa.py`, `fetch_harp.py`, and `fetch_mobile_transfer.py`, followed by `build_data.py` and `build_report.py`. LiquidLab’s overview is curated in `liquidlab_tasks.json` with retained accepted metadata and author publication pages.

## ContactBench

ContactBench adds all 36 published physical reference tasks (31 base and five long-horizon challenges), with official thumbnails, human demonstrations, variation metadata, and exact completion criteria. Six records identify the paper’s policy study; the remaining reference tasks have no paper policy experiment claimed. The separate simulation release contains 73 scripted variants over 22 base tasks and one scene-only setup, with source checkers and setup evidence. Website task numbers differ from paper/simulation numbering. These 110 entries do not represent 110 independent physical skills.

Regenerate these catalogs with `python3 fetch_contactbench.py` and `python3 fetch_contactbench_sim.py`, then rebuild the data and guide. Sources and revision metadata are retained under `sources/contactbench/` and `sources/contactbench_sim/`. The guide includes the authors’ overview figure; task-level videos load from official hosts.

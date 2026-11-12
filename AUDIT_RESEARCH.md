# Research and evidence audit

Audit performed November 12, 2026 against the retained November 11 catalog snapshot. Scope: `guide.template.html`, `coverage.json`, the 2,900 structured entries, retained official papers/registries/checkers, and selected live primary-source verification. This is an evidence audit, not a rerun of benchmark experiments or an independent validation of simulator physics. Main files were not edited by the research auditor.

## Assessment

The catalog is suitable for presenting as a sourced **task-discovery and comparison resource**, with the concrete corrections below now applied in source files and final artifact regeneration/verification handled by root. No remaining material scientific-accuracy blocker was identified within this audit’s scope. Its 2,900 entries across 23 families are not 2,900 independent robot skills or 2,900 standardized paper evaluations. Counts include archived releases, aliases, reward variants, board operation groups, auxiliary environments, and one LiquidLab overview. The guide usually makes these distinctions well. Do not describe its whole inventory as experimentally evaluated tasks.

The strongest evidence consists of exact simulator predicates/checkers and published physical rubrics. Coverage is uneven: 169 records lack an exact `goal` field (111 archived RoboCasa entries, 54 ATOM-Bench prompts without published point-by-point rubrics, three NIST competencies, one LiquidLab overview); these are generally labeled rather than silently reconstructed. Robot observations are unavailable in 1,050 records (1,016 BEHAVIOR library/legacy entries, 30 ContactBench reference tasks outside its policy experiment, three NIST competencies, one LiquidLab overview). Missing fields are evidence limits, not proof that the original benchmark lacks a protocol.

## Findings and resolution status

### R1 — High: SIMPLER summaries add a release requirement absent from the checker

**Status:** Root corrected the three task-specific summaries/goals and added pinned evaluation-source provenance. Regenerated artifacts remain part of root’s integration checks.

The cube-stacking record now also states its inherited geometric/contact checks explicitly. Its success flag does not establish stable, released stacking.

Affected records: `widowx_spoon_on_towel`, `widowx_carrot_on_plate`, `widowx_put_eggplant_in_basket`. Their summary says “placement/release checks.” The original environment's `PutOnInSceneEnv.evaluate` assigns success from the placement flags; grasp and movement fields are diagnostics. It never gates success on release, and its optional contact rejection excludes robot links. This matters when comparing a proposal that explicitly requires releasing the object.

The official original ManiSkill2_real2sim source is pinned to **ef7a4d4fdf4b69f2c2154db5b15b9ac8dfe10682**, committed October 19, 2024, so it predates the catalog snapshot. Supplemental audit evidence is retained at `sources/review/simpler_put_on_in_scene.py` and `sources/review/simpler_checker_snapshot.json`.

**Proposed correction:** use task-specific geometric criteria and cite the implementation. XY center distance must be at most the norm of the target bounding-box half-size in XY plus 0.003 m; the source center must be above the target; height offset minus both half-heights must be at most 0.02 m by default, or 0.06 m for eggplant. Carrot retains rejection of other actor contacts above impulse norm 1e-6, while target and robot links are ignored. Spoon and eggplant disable this extra contact restriction. State explicitly that release is not a primary-success gate. The stack task shares the placement base implementation too; avoid calling it a static/stable-placement test without a separate harness check. [Official checker, lines 43–141](https://github.com/simpler-env/ManiSkill2_real2sim/blob/ef7a4d4fdf4b69f2c2154db5b15b9ac8dfe10682/mani_skill2_real2sim/envs/custom_scenes/put_on_in_scene.py#L43), [spoon override](https://github.com/simpler-env/ManiSkill2_real2sim/blob/ef7a4d4fdf4b69f2c2154db5b15b9ac8dfe10682/mani_skill2_real2sim/envs/custom_scenes/put_on_in_scene.py#L276), [eggplant override](https://github.com/simpler-env/ManiSkill2_real2sim/blob/ef7a4d4fdf4b69f2c2154db5b15b9ac8dfe10682/mani_skill2_real2sim/envs/custom_scenes/put_on_in_scene.py#L452).

### R2 — Medium: RoboDojo's reported experiment needs the per-seed denominator

**Status:** Confirmed corrected in `guide.template.html`: 50 trials per task per seed, three seeds for most methods, 150 trials per task and 6, 300 suite trials; citation now points to Section 5.1.

The original simulation profile said each policy had 50 episodes per task, totaling 2,100. Section 3.1.3 describes that evaluation setting, but Section 5.1 says **most policies use three training seeds**, each with 50 trials per task; the reported method generally has 150 trials per task. That wording was incomplete rather than an invented number.

**Proposed wording:** “Each task receives 50 episodes per training seed (2,100 across the suite per seed). Most reported policies use three seeds, giving 150 episodes per task and 6, 300 total; exceptions are identified in the paper. Each seed's Generalization trials split into 25 standard and 25 randomized episodes.” Preserve equal averaging across the five dimensions. [RoboDojo v3, Section 5.1](https://arxiv.org/html/2607.04434v3#S5.SS1). Retained evidence: `sources/dojo_paper.read.txt`, lines 806 onward.

### R3 — Medium: ContactBench is appended to RoboDojo's comparison-table cell

**Status:** Confirmed corrected in `guide.template.html`: ContactBench now has a separate row with its reference, simulation-release and six-task experiment scopes.

The original comparison row's first cell included links to both RoboDojo and ContactBench, while its other cells describe RoboDojo's 42 simulation plus 18 real tasks and scoring. A reader can incorrectly attribute those counts and protocols to ContactBench.

**Proposed correction:** give ContactBench a separate comparison row: 36 physical reference tasks (31 base plus five long-horizon challenges), six selected tasks with physical policy experiments, and separately scoped simulation variants. Do not imply that its whole reference catalog has policy results. [ContactBench project](https://jingyi-xiang.github.io/contactbench/), [paper](https://arxiv.org/html/2610.24512). The dedicated ContactBench section already makes these distinctions accurately.

### R4 — Medium: LiquidLab overview uses an unsupported physical-task qualifier

**Status:** Root corrected the curated overview wording before regeneration.

The overview `catalog_scope` says the entry does not represent one of the “sixteen physical tasks.” The retrieved accepted abstract establishes sixteen benchmark tasks and a Genesis/SPH simulation pipeline; it does not establish a sixteen-task hardware evaluation. The record otherwise correctly says its individual task definitions and thresholds were unavailable.

**Proposed correction:** say “sixteen reported benchmark tasks.” Keep `setting: Simulation` and the explicitly labeled overview status; do not convert the abstract into sixteen fabricated task rows. Source: `sources/liquidlab/accepted_metadata.json`, abstract and tags; [official accepted program](https://www.corl.org/program/accepted-papers), [OpenReview record](https://openreview.net/forum?id=SBGylS4zwM). OpenReview was not accessible through the audit's web tool, so no new full-paper claim is made.

### R5 — Medium: LIBERO record links are mutable despite a retained pinned tree

**Status:** Confirmed corrected in `build_data.py`: source URLs use the retained revision and entries receive `source_revision`. Regenerated artifacts remain part of root’s integration checks.

All 130 task and setup links originally used `/blob/master/`; `sources/libero_tree.json` retains SHA **8f1084e3132a39270c3a13ebe37270a43ece2a01**. The underlying goals are retained locally, so this is a traceability issue, not evidence that they are wrong. The generated guide says pinned snapshots support reproduction, which would be clearer if the record's source actually resolved to that snapshot.

**Proposed correction:** generate those links from the retained SHA and include `source_snapshot`. Also pin the guide's task-map/BDDL directory links where they are presented as snapshot evidence. [LIBERO retained revision](https://github.com/Lifelong-Robot-Learning/LIBERO/tree/8f1084e3132a39270c3a13ebe37270a43ece2a01/libero/libero/bddl_files).

## Lower-priority presentation and evidence improvements

- **IMBench inputs:** the observation summary mentions workspace/wrist RGB and proprioception, but the paper's general interface also describes wrist force/torque. Its limitations and experiment sections distinguish available modalities from actual baseline usage, and have some internal tension about force feedback. State “available interface” versus “selected experiment inputs”; do not infer that every baseline received force or tactile data. Preserve its simulation setting. [Paper, benchmark interface and limitations](https://arxiv.org/html/2607.15641). Retained `sources/corl2026/imbench_paper.txt`, lines 617–623, 1176, 1520.
- **Coverage specificity:** `coverage.json` is appropriately cautious but often omits the exact row unit/count for added families. Add the row counts and units in the reconciliation below so a presentation slide does not accidentally call all of them independent tasks.
- **MESA wording:** the coverage note about repeated templates is reasonable, but clarify that the 285 rows are unique official evaluation identifiers, while semantic skills and goal templates can repeat across generalization splits. Each record's setup is one `eval/000.json` sample out of 50 released resets, not all resets. The current per-record note already says this.
- **README opening:** “three task catalogs selected from CoRL” describes an earlier expansion and omits the follow-up suites/overview. Later paragraphs explain the additions correctly. Update the opening to the final 23-family scope.
- **Unknown observations:** keep the unavailable labels visible in search/compare/API consumers. A library's BDDL goal alone does not establish a fixed policy observation space.

## Count and scope reconciliation across all 23 families

The counts below were computed directly from `tasks.json` in the audited snapshot, then reconciled with retained registries or primary descriptions. “No discrepancy found” is scoped to inventory interpretation and checked evidence, not a claim to have executed every environment.

| Family | Catalog rows | Correct interpretation / primary evidence |
|---|---:|---|
| LIBERO | 130 | 10 Spatial + 10 Object + 10 Goal + 90 pretraining + 10 Long; do not add another 100. [Official task registry](https://github.com/Lifelong-Robot-Learning/LIBERO/blob/8f1084e3132a39270c3a13ebe37270a43ece2a01/libero/libero/benchmark/libero_suite_task_map.py). |
| RoboCasa | 476 |365 current tasks plus 111 archived v0.2 rows. The 2024 paper's 100 tasks are not the 111-row archive. Current target set 50 = 18 atomic+ 16 seen composite+ 16 unseen composite. [RoboCasa365 paper](https://arxiv.org/html/2603.04356v1). |
| SIMPLER | 25 |Callable registry names, including aliases and orientation/drawer specializations; not 25 distinct skills. Exact release wording needs R1. [Convenience registry](https://github.com/simpler-env/SimplerEnv/blob/main/simpler_env/__init__.py). |
| BEHAVIOR |1,116 |1,016 current numbered definitions plus 100 legacy;100 current challenge tasks are marked within the current library, not added again. Definitions are not 1,116 leaderboard evaluations. [Current catalog](https://behavior.stanford.edu/knowledgebase/tasks/index.html), [challenge rules](https://behavior.stanford.edu/challenge/evaluation.html). |
| DataCenterBench |10 |Ten Tier 1 physical setups/rubrics. Three tries/model/task,40 calls,224×224 policy views,65°C guard and photo/log grading align the retained methodology. [Methods](https://robocurve.org/datacenterbench/methods.html). |
| RoboDojo |61 |42 scored simulation tasks + 18 real + 1 auxiliary DLC page. Runtime randomization variants are not independent paper tasks. R2 fixes experimental trial count. [Paper v3](https://arxiv.org/html/2607.04434v3). |
| RLBench |106 |Current pinned task classes; variations and Gym observation aliases are metadata. This differs legitimately from the paper's 100-task claim. [Pinned task directory](https://github.com/stepjam/RLBench/tree/02720bba4c73fe02eb75df946b8791b806028a9d/rlbench/tasks). |
| ManiSkill |65 |Direct built-in registered environment IDs, including robot/difficulty variants and supporting environments. Not an all-version union or 65 manipulation skills. Ground-truth and visual modes differ. [Pinned task package](https://github.com/haosulab/ManiSkill/tree/62ff3a5896b4d5b4cf0ac4c8d79afe600c9404a3/mani_skill/envs/tasks). |
| CALVIN |34 |Atomic language-task oracle entries. Five-task sequences are combinations, not additional task types. The signed drawer/slider deltas in summaries are preserved correctly. [Official configuration](https://github.com/mees/calvin/blob/fa03f01f19c65920e18cf37398a9ce859274af76/calvin_models/conf/callbacks/rollout/tasks/new_playtable_tasks.yaml). |
| RoboTwin 2.0 |50 |Task implementations/instruction catalogs. Clean/randomized conditions and embodiments reuse task definitions. Summaries correctly flag that bottle-shaking checkers only test bottle height. [Pinned task directory](https://github.com/RoboTwin-Platform/RoboTwin/tree/ea8b21121ebb3cd201ff5b3fe361944ac94eda3f/envs). |
| NIST Assembly |96 |93 scored operation groups plus 3 board competencies. Assembly/disassembly rows and repeated part quantities are distinct from 96 standalone benchmarks. Additive board scoring and 32-trial template are retained. [Official assembly test methods](https://www.nist.gov/el/intelligent-systems-division-73500/robotic-grasping-and-manipulation-assembly/assembly). |
| FurnitureBench |9 |Full furniture assembly tasks; required part-pair counts are subtasks. Base-environment and image-wrapper observations differ. [Project](https://clvrai.github.io/furniture-bench/). |
| RoboChallenge |60 |30 Table30 +30 Table30 V2, separate versions with stage rubrics. Do not call them 60 independent capabilities. [Official challenges](https://robochallenge.ai/challenges). |
| Adroit |8 |Dense/sparse variants of 4 skills. Step success flags, shaping reward and episode termination are distinguished correctly; success does not itself end these continuing environments. [Official environments](https://robotics.farama.org/envs/adroit_hand/). |
| WireCraft |3 |Three task families: insertion, routing, seating. Connector/clip/channel variants are not exhaustively expanded. Physical ACT inputs differ from privileged simulation configurations. [Project](https://chongyuzhu.github.io/wirecraft/). |
| IMBench |35 |35 simulation task descriptions with paper-appendix physical goals. “Physical reasoning” does not mean hardware experiments; record settings correctly say Simulation. [Paper](https://arxiv.org/html/2607.15641). |
| ATOM-Bench |54 |Paired physical tracks:30 atomic + 24 held-out compositional tasks total. Exact prompts available, individual process-point rubrics absent; avoid claiming exact per-task process grading has been reconstructed. [Paper](https://arxiv.org/html/2606.16826). |
| HARP-Bench |49 |37 paper task-condition instances + 9 no-human bases + 3 factory extras. Not 49 paper human-present tasks or 37 independent motor skills. Collision gating and proximity metrics are separated. [Official repository](https://github.com/UMass-Embodied-AGI/harp). |
| LiquidLab |1 |One overview representing the existence of a 16-task benchmark, not an individual task. No exact per-task definitions retrieved. R4 removes unsupported hardware implication. [Accepted program](https://www.corl.org/program/accepted-papers). |
| MESA/BiMESA |285 |140 single-arm +145 bimanual unique evaluation identifiers. Five splits per embodiment;50 reset files/task. Demonstration/handoff diagnostics are separate from final-goal success. Auxiliary training lists remain outside the evaluated catalog. [Project](https://www.pair.toronto.edu/MESA/), [retained registry](https://github.com/pairlab/mesa-env/blob/e4a82e2a88547afdab4c97130ca47efdb523c50f/mesa/task_suites/task_sets.py). |
| RMMBench |113 |60 manipulation +53 navigation registrations. Paper 90 canonical scenarios and released fixed presets 70 names are explicitly different scopes; not a count discrepancy to silently correct. [Official repository](https://github.com/mxxq-stack/RMMBench). |
| H2RBench |4 |Four tasks with cumulative-stage scoring. Simulation-real ranking agreement evaluates the evaluator separately from final-stage task success. Table 6's generic instruction and more-specific rubric are retained rather than reconciled by invention. [Paper Table6](https://arxiv.org/html/2609.24778v3#A1.T6). |
| ContactBench |110 |36 physical references plus 74 simulation records:73 scripted variants over 22 base tasks and 1 scene-only setup. Only 6 physical tasks have paper policy experiments; four support tactile comparisons. Website/paper numbering differs. [Project](https://jingyi-xiang.github.io/contactbench/), [simulation release](https://github.com/Michaelwyx/contactbench-sim). |

## Original-profile checks that passed

- LIBERO's 50 demonstrations/task, 50 epochs, evaluation every 5 epochs with 20 rollouts and 600 step horizon match the retained paper. Its FWT description correctly describes learning-curve acquisition rather than zero-shot transfer. Formal goal conjunctions and continual-learning interpretation are distinguished.
- RoboCasa's 365=65+300, 300 pretraining tasks=65+235, 50 target tasks and 30 trials/task match the retained paper. The May 12, 2026 horizon increase is labeled as a later protocol update. Current checker code is separate from archived task intentions.
- SIMPLER's distinction between per-task simulated success and real/sim ranking agreement is sound; its MMRV explanation matches the paper. The release/stability wording is the concrete exception identified above.
- BEHAVIOR distinguishes 100 legacy, 1,000 paper scope, 1,016 retrieved definitions and 100 challenge tasks. Its partial-goal score caveat avoids naive line counting for quantified/disjunctive goals. Challenge budget/time accounting is separately scoped.
- DataCenterBench's observation, rubric, judge arbitration, keypress-log exception, aggregation, bootstrap interval and thermal treatment agree with retained official methods. The limitation to simplified component procedures is explicit.
- RoboDojo's 42/18 task taxonomy, five-dimension average, different simulated/real tube partial scores, 10 real trials and three double-blind evaluators agree with retained source material. Add the per-seed qualification in R2.

## Suggested presentation wording

“An indexed November 11, 2026 snapshot of 2,900 versioned entries across 23 robotics benchmark families. Entries include concrete task definitions, aliases and variants, operation groups, archived versions, and one overview. We compare requested behavior, available observations and the actual grading evidence; matching keywords are retrieval aids, not proof that two tasks are equivalent.”

For a public release, present every claim about “complete coverage” with its row unit and pinned release. Paper experimental scope, source-registry scope and supported simulator capability are different claims. The guide already explains this principle; apply it consistently in slides, README, API descriptions and headline counts.

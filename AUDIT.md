# Presentation and publication review

Reviewed November 12, 2026. Catalog snapshot: November 11, 2026; 2,900 versioned entries across 23 benchmark families.

The guide has passed its research-evidence, interaction, catalog-integrity, search/API and static-deployment checks after the corrections below. It is a task-discovery and comparison resource, not an independent reproduction of benchmark experiments. Public redistribution terms for some retained third-party material remain unresolved; see [THIRD_PARTY.md](THIRD_PARTY.md).

## Corrections made

1. Removed a gripper-release requirement incorrectly attributed to three SIMPLER placement checkers. Their geometric/contact criteria now cite the exact implementation revision.
2. Qualified RoboDojo's trial counts by training seed, including the 25/25 generalization split within each seed.
3. Gave ContactBench its own comparison row, separating its 36 physical references, six-task policy experiment and simulation release.
4. Removed an unsupported hardware qualifier from the LiquidLab overview. Its individual task definitions remain unavailable.
5. Pinned LIBERO's 130 task links and source-list references to the retained revision.
6. Clarified that IMBench's available force/torque interface does not establish every baseline's actual inputs.
7. Fixed structured-field normalization differences between the Python and browser search engines. Made API errors consistent with the OpenAPI responses and corrected clone-root startup instructions.
8. Added keyboard skip navigation, a useful no-JavaScript fallback, shareable query/filter/pin URLs, immediate proposal updates, media failure/retry feedback, intrinsic figure dimensions and printable comparison columns.
9. Added repeatable validation and required it before the GitHub Pages deployment build proceeds.

## Checks and evidence

| Check | Result | Evidence |
|---|---|---|
| Research claims and inventory units | Five concrete accuracy/provenance findings corrected; all 23 family inventories reconciled | [Research audit](AUDIT_RESEARCH.md) |
| Catalog, search and API | 2,900 records; 30 Python/JavaScript parity cases; 98 HTTP requests, including errors, filters, pagination and one detail per family | [Functional results](validation-functional.json), [functional audit](AUDIT_FUNCTIONAL.md) |
| Static distribution | Every one of 2,900 individual records equals its source; embedded catalog, local links, anchors and deployment documents agree | [Static results](validation-site.json) |
| Published reference links | 71 distinct guide/coverage source URLs returned HTTP 200 in the initial review; final pinned references were checked separately | [Link audit](link_audit.json) |
| Browser interaction | Keyboard, offline local file, desktop, narrow screen, no JavaScript, proposal export, media failure/retry and print checked | [UI audit](AUDIT_UI.md) |
| Hosted-path behavior | Search, task-record URLs and query/pin reload checked under `/robotics-benchmarks-overview/`; no page exceptions | Integration browser check |
| Public repository scan | Working tree and all six pre-review commits scanned; no confirmed user credential found. Public website configuration matches were classified without republishing values | [Functional audit](AUDIT_FUNCTIONAL.md) |
| Third-party notices | Exact-revision license evidence retained; restrictive and unresolved cases explicitly listed | [Third-party review](THIRD_PARTY.md) |

## Limits that should remain visible

- Entry totals include aliases, versions, operation groups, simulation variants, auxiliary material and one benchmark overview. They are not independent skill counts.
- Search uses lexical matching and controlled synonyms. A high result rank is not proof of task equivalence or proposal novelty.
- Some records lack exact checkers, policy inputs or task-level media. Missing evidence remains labeled; it was not reconstructed from task names.
- HTTP success does not verify a page's scientific content. The link pass does not cover every task/media URL, and external media remains host-dependent.
- These checks did not run every robotics environment, policy, simulator or physical experiment.
- The public-source scan is not a guarantee that every possible secret format was detected. License notices are not permission grants for material with unresolved terms.

Re-run the commands in [README.md](README.md) after changing the catalog, search code, API or website builder. The machine-readable validation reports record their own timestamps and catalog hash where applicable.

# Functional and publication-readiness audit

Audited November 12, 2026. Functional result: **passed**. Third-party licensing: **not fully cleared**; see [THIRD_PARTY.md](THIRD_PARTY.md).

## Scope and reproducible checks

Run `python3 validate_catalog.py` from the repository directory with Python 3.10+ and Node.js. The script uses no Python packages and no external network requests. It opens an ephemeral `127.0.0.1` port, so a sandbox that blocks local socket binding must permit that operation. A bind-permission failure is not a passing result; rerun with the appropriate execution permission.

The final machine-readable result is [validation-functional.json](validation-functional.json):

- 2,900 records across 23 families; unique URL-safe IDs, required metadata, explicit observation/grading scope, evidence links where those scopes claim evidence, and media shape/scope checks.
- 30 Python/JavaScript cases compared **complete ranked IDs, scores, match reasons, and interpreted query terms**, covering real proposals, quoted and exact phrases, all-terms matching, camel-case identifiers, aliases, accent normalization, empty/unknown queries, filters, and nested structured fields.
- 98 HTTP checks: JSON schema validation of response bodies, all static allowlist routes, GET/HEAD behavior, pagination, all family filters, split/setting/version filters, 23 full task details, malformed query errors, read-only method errors, and attempts to retrieve Git/source/private paths.
- Every task detail validates against the OpenAPI schema features used by this API. All local schema references resolve. Six JSON API routes are described.
- SHA-256 of the tested catalog: `c9b8f2d79a0d6796905a60017f7ffccfc101b0fddbfc62a51bf223423e6f278a`.

Search retrieval expectations include chair assembly returning FurnitureBench, human interruption returning HARP-Bench, and nut tightening returning ContactBench among the top five candidates. All full retrieval outputs are represented by counts and top task IDs in the validation JSON. These tests establish useful deterministic retrieval, not semantic equivalence or benchmark novelty.

## Fixes made

1. API documentation now starts correctly from a cloned repository root and explains static GitHub Pages records versus the separately runnable local API.
2. Python and JavaScript now flatten list/dictionary fields consistently. Filters use matching lowercase behavior in both implementations, and both reject invalid modes when describing queries.
3. The API rejects malformed catalogs at startup before a request can fail on an invalid record. Search enforces its 1,000-character limit before trimming whitespace.
4. Mutation methods return structured `405` errors with `Allow: GET, HEAD`. Responses include `X-Content-Type-Options: nosniff`; the server header omits the Python version. The third-party notice has an explicit static route.
5. OpenAPI now includes the raw catalog and schema routes, record-kind counts, HEAD behavior, method errors, and the full preview contract.

## Service exposure and limits

The default bind address is `127.0.0.1`. The server has an explicit static allowlist rather than directory serving, returns source snapshots only as catalog data, and does not execute benchmark code. Query strings are omitted from access logs. Tests verified Git config and source-tree paths return JSON `404` errors.

This is an unauthenticated development service, with no TLS, production rate limiting, or CORS headers. Explicitly binding it to a network interface changes who can reach it. Static GitHub Pages does not run `/api/search`; published JSON records and the offline guide are the hosted interface. No repository visibility was changed by this audit.

## Credential and unintended-artifact scan

[validation-security.json](validation-security.json) contains sanitized paths, rule IDs, line locations, and classification notes. It contains no token values.

Gitleaks scanned all six existing commits through `a660700` (199.29 MB of history content) and the then-current directory (236.56 MB). Both scans reported the same 13 findings: public upstream frontend/analytics configuration in preserved webpages or JavaScript bundles, plus a task-name false positive. **No user credential was confirmed.** No keys were tested against remote services. The result is not proof that no secret exists.

The findings occur in `sources/contactbench/config/tasks/index.js`, DataCenterBench webpage snapshots, `sources/corl2026/official.html`, NIST webpage snapshots under `sources/physical/`, and `sources/physical/robochallenge_frontend.js`. They are documented rather than silently removed from exact upstream snapshots. No tracked `.env`, private-key, credential directory, desktop/mobile screenshot, `.aws`, `.codex`, or `.agents` paths were found in the scanned tree/history. Existing commit author email metadata will be public with the Git history; upstream author contact information is also present in published webpage snapshots.

No sources were removed and no history was rewritten. New audit outputs contain only public source evidence and sanitized findings.

## Third-party attribution and unresolved terms

Fourteen full upstream license texts were retained with revision/URL evidence in [sources/review/licenses/inventory.json](sources/review/licenses/inventory.json). Thirteen refer to pinned commits or a named release; SIMPLER's recorded source uses `main`, so its license observation is dated rather than an immutable source-revision match.

Confirmed evidence includes MIT texts for LIBERO, Stanford BDDL, FurnitureBench, MESA, ContactBench simulation, CALVIN, RoboTwin, and Gymnasium-Robotics; RoboCasa's MIT text with an additional Apache notice; and ManiSkill's Apache-2.0 text. These statements apply to the respective source evidence, not every linked dataset or image.

RLBench's exact license contains custom non-commercial/internal/academic-use provisions and separate BSD component terms. HARP and RMMBench do not have confirmed project-wide license files in the inspected trees; narrower robot-description licenses do not establish project-wide permission. Reuse terms for each copied paper figure, photograph, and full webpage were not separately established. [THIRD_PARTY.md](THIRD_PARTY.md) preserves the specific evidence and unresolved publication/reuse questions. Citation alone does not confer permission; this audit does not label the full repository license-cleared.

## Verification boundaries

No benchmark simulation, robot rollout, policy evaluation, or GPU execution was performed. Functional checks do not validate scientific thresholds against every paper; that is covered separately by the research audit. Remote source/media availability is recorded by the separate link/media audits. The Gitleaks scan is bounded to the stated six-commit history and directory snapshot, not future changes or remote branches.

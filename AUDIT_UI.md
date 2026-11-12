# UI audit

Reviewed the source template and task explorer against the current [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md), the frontend-design skill, and the HTML-summary workflow on November 12, 2026.

## Findings fixed

- guide.template.html:11 — added a keyboard-visible skip link and a focusable main-content target.
- guide.template.html:12 — added a direct search action in the opening header.
- guide.template.html:26 — gave ContactBench its own comparison row, with physical-reference, simulation-release, and policy-study scope.
- guide.template.html:89 — corrected RoboDojo evaluation wording to trials per task per training seed, with the reproducibility citation supplied by the research audit.
- guide.template.html — added meaningful names and autocomplete settings to search and proposal controls.
- task_explorer.css — hides inert controls and empty dynamic sections when JavaScript is disabled. The static guide and task-data download remain available.
- task_explorer.css — comparison columns wrap within the print page. Sticky row headers become static in print.
- task_explorer.js — retains and restores search terms, filters, page, and pinned task identifiers through the URL.
- task_explorer.js — proposal edits update the comparison as they are entered.
- task_explorer.js — media failures show an inline status and a working retry button while retaining the original-source link.
- task_explorer.js — print preparation expands comparison evidence and restores its prior disclosure state afterward.

## Verification

- Loaded the standalone HTML from a local file with 2,900 records across 23 benchmark families.
- Keyboard Tab and Enter reached the skip link and moved focus to main content.
- Submitted a keyword search with Enter, filtered ContactBench, pinned a result, and reloaded the URL. Search, family, and pin were restored.
- Entered a proposal and checked its grading criterion appeared immediately in comparison. Added three published tasks and downloaded the comparison JSON.
- Checked desktop at 1440 px and narrow layout at 390 px. The document had no horizontal overflow.
- Checked print styling at 794 px with a proposal plus three pinned records. Table width equaled its 745 px content container. Comparison evidence opened before printing and closed afterward.
- Loaded a separate browser context with JavaScript disabled. The fallback message and static guide remained readable, with search and result controls hidden.
- Aborted external media requests to check failure and retry behavior. Repeated retries retained one status message.
- No page exceptions or unexpected console errors occurred. The aborted media request was intentional.

## Review limits

- External video playback depends on the original host and connectivity. Failure guidance and original-source links were checked.
- This pass checked presentation and interaction. Task accuracy and source coverage are documented by the separate research audit.
- Root integration also verified the generated static package and local API separately.

Screenshots are retained at /tmp/robotics-ui-desktop-final.png and /tmp/robotics-ui-narrow-final.png.

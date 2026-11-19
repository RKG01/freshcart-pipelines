# Final submission checklist

## Report content and evidence

- [x] Student name and roll number: Devansh Singh, 23BCS074.
- [x] Assignment sections A–E, actual results, integration architecture, personal reflection, and original numbering included.
- [x] B3 explicitly states the `unsupported_currency` rule was already active during B1; the omitted-rule result is a SELECT counterfactual, not historical before/after evidence.
- [x] Bonus section marked live verified for the two approved orders and one replay, with actual metrics and consumer exit-code limitation disclosed.
- [x] Bonus appendix contains excerpts from genuine saved publisher, consumer, replay, and SQL snapshot files; it is not presented as live Snowflake UI evidence.
- [x] Three CI screenshots, three Mage screenshots, two RabbitMQ screenshots, and four Snowflake saved-record screenshots retained and captioned (12 total).

## PDF validation

- [x] Rebuilt with `reports/build_report.py` at `reports/23BCS074_Devansh_Singh_Pipelines.pdf`.
- [x] PDF opens and has 21 pages total.
- [x] Main report is pages 1–6 (6 pages, within the 8-page maximum).
- [x] Screenshot appendix uses pages 7–18 (12 screenshots); bonus saved-log and SQL evidence uses pages 19–21.
- [x] All 12 screenshot image objects are embedded, with one screenshot per appendix page and aspect ratios preserved.
- [x] Rendered pages 1–21 were visually reviewed; no blank pages, clipped report text, duplicated headings, or missing images were found.
- [x] Extracted PDF text contains student name/roll number, B3 limitation, bonus metrics, and both order IDs.
- [x] Credential scan of the PDF, bonus evidence logs, and report sources found no credential patterns.

## Validation and safety

- [x] `python -m pytest -q`: 41 passed in 5.95 seconds using `.venv` during this final verification.
- [x] `git diff --check`: exit code 0; no whitespace errors (Git emitted only line-ending advisory warnings).
- [x] Both notebooks parse as valid JSON: FreshCart 26 cells (16 code cells, 4 code cells with outputs); Mage evidence 5 cells (4 code cells, all 4 with outputs).
- [x] No bonus or previous experiment was rerun during final report/PDF assembly.
- [x] No credentials or `.env` content were included.
- [x] `reference/freshcart_elt_simple.ipynb`: only cell 4's saved output was cleared and execution count reset; its source and other cells were preserved. The notebook path was removed from all rewritten local refs, and the other instructor notebook is unchanged. This cannot remove copies in forks, clones, or GitHub caches.
- [x] Local Git history no longer contains `reference/freshcart_elt_simple.ipynb` on any rewritten branch or tag; the prior commit `9b6da22b99be` is absent. The cleaned current notebook will be included as a new file in the submission.
- [x] A redacted scan found no exact copies of the credential-like value in the current worktree or rewritten reachable history, and no matches for the checked high-signal credential patterns.
- [x] This local cleanup cannot remove copies in GitHub caches, forks, or other clones.

## Validation results

Final checks completed: `python -m pytest -q` — 41 passed; `git diff --check` — clean; notebook JSON validation — passed for both student notebooks and the two reference notebooks. The local `.venv` lacked the declared scikit-learn and pandas dependencies, so only those two declared packages were installed; the full requirements file was not reinstalled. PDF: 21 pages total, 6 main-report pages, 12 screenshots embedded, 3 bonus evidence pages. All 21 rendered pages were visually reviewed after the final rebuild.

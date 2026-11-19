# Final evidence inventory

Updated for the final package and the approved bonus execution on 2026-11-16. The bonus evidence below is actual saved process output, SQL snapshots, and local payload comparison. The report retains the B3 historical limitation: `unsupported_currency` was already active during B1, so the omitted-rule result is a SELECT counterfactual, not historical before/after evidence.

## Part A: Git and CI

- README, `.github/workflows/ci.yml`, and prepare-data tests exist.
- Three actual CI runs are represented by genuine screenshots: `screenshots/ci-green.png`, `ci-red.png`, and `ci-green-fix.png`.
- `reference/Maze_ML_PipeLine.ipynb` remains unchanged. The FreshCart instructor notebook's source and non-target cells are preserved; only cell 4's saved output was cleared and its execution count reset to remove a credential-like value. The path was removed from rewritten local refs. Copies in forks, clones, and GitHub caches may remain.

## Part B: FreshCart ELT

- B1 baseline: `b1_baseline_results.md`.
- B2 record trace: `b2_record_trace.md`.
- B3 currency reasons and SELECT counterfactual with historical limitation: `b3_currency_validation.md`.
- B4 prediction and actual targeted update: `b4_predictions.md`, `b4_actual_results.md`.
- B5 plan and controlled failure/cleanup evidence: `b5_test_plan.md`, `b5_quality_check.md`, `b5_quality_check_execution.log`.

## Part C: Mage

- C1 actual run: `c1_mage_run.log`; six block tests passed and pipeline completed.
- C2 actual five-depth runs and logs: `c2_depth_experiments.md`, `c2_depth_1.log` through `c2_depth_5.log`.
- C3 actual evaluation, confusion matrix, metadata, and run log: `c3_evaluation.md`, `c3_confusion_matrix.csv`, `c3_mage_run.log`.
- C4 validation source and actual run: `c4_custom_block.md`, `c4_mage_run.log`.
- Mage screenshots: `mage_pipeline_graph.png`, `mage_successful_run.png`, `mage_evaluation_results.png`.

## Part D: RabbitMQ

- D1 preserved predictions and actual results: `d1_routing_predictions.md`, `d1_routing_results.md`, and `rabbitmq_logs/d1/`.
- D2 actual two-minute run: `d2_rabbitmq_results.md` and `rabbitmq_logs/d2/20261116_013650/`.
- D3 actual ACK/NACK run: `d3_ack_nack.md` and `rabbitmq_logs/d3/20261116_015016/`.
- RabbitMQ screenshots: `rabbitmq_overview.png` and `rabbitmq_exchange.png`; the exchange image shows all six bindings.

## Part E, bonus, and final package

- `assignment_report.md` includes A1–A3, B1–B5, C1–C4, D1–D3, Part E architecture/reflection, and the optional live-verified bonus.
- Bonus live evidence is in `bonus/live_5f057039be864ea497eaa9496e2810bd/`: initialization, consumer/publisher/replay output, first and replay SQL snapshots, business-payload comparison, timestamps, and three run reports.
- Actual bonus outcomes: 60.001-second collection; two confirmed published messages; Bronze order rows 2→4; Silver 2→2; Gold 2→2; revenue INR 5,092.38 unchanged; 50 loyalty points unchanged; duplicate Gold IDs zero. Actual supporting fixtures: 4 CRM rows, 1 FX row with 3 rates, and 3 pincode rows. Publisher and replay exit codes were 0. The consumer OS exit code was not captured and is not claimed.
- Final PDF: `23BCS074_Devansh_Singh_Pipelines.pdf`. It contains 21 pages: main report pages 1–6, 12 screenshot pages 7–18, and readable captured bonus log/SQL evidence on pages 19–21.
- All 12 screenshots are present and embedded: 3 CI, 3 Mage, 2 RabbitMQ, and 4 Snowflake saved-record screenshots. Snowflake screenshots are not live Snowsight captures.
- Final validation: 41 pytest tests passed; both notebooks parsed as valid JSON; `git diff --check` reported no whitespace errors. PDF rendering review covered all 21 pages.

## Safety and evidence limits

- No credentials are intentionally included in the report or PDF. `.env` remains ignored and untracked according to the saved Phase 3 verification.
- B3 has no genuine pre-rule Snowflake run evidence; no historical before/after claim is made.
- This final documentation/PDF validation did not rerun Snowflake, Mage, or RabbitMQ services. The bonus evidence was collected earlier in its recorded live execution directory.

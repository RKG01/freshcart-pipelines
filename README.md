# From Git to Gold

Data Engineering assignment project for Harshit Raj . The instructor reference notebooks are preserved in `reference/`; one saved output in the FreshCart reference was cleared to remove a credential-like value from the notebook.

## Project layout

- `.github/workflows/`: GitHub Actions CI workflow.
- `elt/`: FreshCart Python/SQL implementation and `freshcart_elt.ipynb` workflow notebook.
- `iris_project/`: Mage project, pipeline metadata, Iris loader, transformer, and exporter blocks, plus `iris_pipeline_evidence.ipynb` summarizing captured C1–C4 results.
- `stream/`: RabbitMQ dispatcher, driver, topic-routing helper, deterministic D1 publisher, and D2/D3 runner scripts.
- `tests/`: ELT, Mage block, data split, and stream routing tests.
- `reports/`: assignment report, evidence reports and logs, screenshots, checklist, and final PDF.
- `reference/freshcart_elt_simple.ipynb`: original simple FreshCart reference notebook.
- `reference/Maze_ML_PipeLine.ipynb`: original Mage/Iris reference notebook.

`elt/freshcart_elt.ipynb` preserves the executable ELT workflow cells and adds a clearly labelled Markdown summary of captured B1–B5 results; it has no native execution outputs and was not freshly run. `iris_project/iris_pipeline_evidence.ipynb` is the student-facing Mage evidence notebook, summarizing the existing C1–C4 logs, block source, and graph metadata without executing Mage. Both notebooks cite saved reports/logs. `reference/Maze_ML_PipeLine.ipynb` is unchanged; in `reference/freshcart_elt_simple.ipynb`, only the saved output and execution count in cell 4 were cleared. The notebook source and other cells remain unchanged. This local cleanup does not remove copies in forks, clones, or GitHub caches.

## Completion and saved evidence

Actual saved evidence is available for B1–B5, C1–C4, and D1–D3 under `reports/`:

- **B1–B5:** baseline totals, record trace, currency validation, SCD2 update, and the controlled future-date check. The actual B5 transaction used `FRESHCART_B1`; the notebook's configured isolated-test default is `FRESHCART_B5_TEST` (`SNOWFLAKE_B5_DATABASE`). These are distinct. B5 used a targeted insert/check/delete transaction and did not call `run_pipeline()`.
- **B3 limitation:** `unsupported_currency` was already active during B1. The result omitting that predicate is a SELECT-based counterfactual, not a historical before-and-after run.
- **C1–C4:** actual Mage CLI logs, five max-depth results, evaluation metrics/confusion matrix, and validation block evidence.
- **D1–D3:** preserved routing predictions and actual routing, two-minute dispatcher results, and ACK/NACK evidence with raw logs.

## Optional bonus: RabbitMQ to FreshCart

The integration in `stream/freshcart_lakehouse_consumer.py` and `stream/publish_freshcart_orders.py` was live-verified on 2026-11-16 using only `FRESHCART_BONUS`. One publisher invocation confirmed two messages; the consumer collected for 60.001 seconds, loaded them through the existing ELT functions, and one replay loaded the same payloads from the exact first file under a new run ID and physical path. Bronze order rows increased from 2 to 4; Silver and Gold stayed at 2. Gold revenue and loyalty points stayed at INR 5,092.38 and 50, with each test order present once and no duplicate Gold IDs. Actual fixture counts were 4 CRM rows, 1 FX row containing three rates, and 3 pincode rows. Five physical landing files were created across the initial pass and replay. Bronze grew because replay appended the same business payloads from a second file; Silver deduplication and Gold MERGE preserved order totals. Publisher and replay exit codes were 0. The consumer process terminated with completed success-stage output, but its OS exit code was not captured and is not claimed. Logs and SQL evidence are in `reports/bonus/live_5f057039be864ea497eaa9496e2810bd/`; see `reports/bonus/bonus_architecture.md` for the detailed evidence index. The consumer process's OS exit code was not captured and is not claimed; publisher and replay exited 0.

The full report, with student details and personal reflection, is [`reports/assignment_report.md`](reports/assignment_report.md). The final PDF is [`reports/23BCS074_Harshit_raj_Pipelines.pdf`](reports/23BCS074_Harshit_raj_Pipelines.pdf). The PDF appendix contains 12 screenshots: three GitHub Actions, three Mage, two RabbitMQ, and four Snowflake saved-record images. It also includes readable excerpts from the genuine bonus logs and SQL snapshots; those excerpts are not live Snowsight screenshots.

## Local setup

Use Python 3.12 as specified by the assignment. In PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
```

`.env.example` contains placeholders, not credentials. Copy it to `.env` and set local values as needed. `.env` is ignored by Git and must not be committed.

Mage CLI examples:

```powershell
mage run iris_project iris_classifier --test
mage run iris_project iris_classifier --test --runtime-vars '{"max_depth": 3}'
```

RabbitMQ can be started locally with `docker compose up -d` after configuring `.env`. The Compose file binds AMQP and management ports to loopback. The dispatcher publishes every two seconds and omits `zone` on every tenth payload; drivers use manual ACK/NACK handling.

## Git command guide (Part A2)

| Command | Where the change happens | What happens |
| --- | --- | --- |
| `git init` | Local repository metadata | Creates the `.git` database in the working folder. |
| `git add train.py` | Staging area | Selects current file content for the next commit. |
| `git commit -m "msg"` | Local repository | Saves staged content locally; GitHub is not updated. |
| `git remote add origin URL` | Local Git configuration | Records the remote's name and URL. |
| `git push -u origin main` | Remote GitHub repository | Uploads local commits and records the upstream branch. |
| `git pull origin main` | Working folder and local repository | Fetches and integrates remote commits into the current branch. |

A teammate cannot see a local commit on GitHub until it is pushed and they have repository access.

## Recorded validation

The saved Mage Docker test evidence records 18 passing tests and one warning. The C1 pipeline log records all six block tests passing and pipeline completion. The C2 table and per-depth logs distinguish Mage execution results from predictions. GitHub Actions evidence includes one successful run, the intentional split-test failure, and the corrective successful run. See `reports/final_submission_checklist.md` for the final artifact checks.

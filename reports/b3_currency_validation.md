# FreshCart B3: Unsupported Currency Validation

**Database:** `FRESHCART_B1`
**Investigation:** Read-only queries against the existing B1 run
**Baseline run ID:** `20261115_063011_352098`

No pipeline or transformation SQL was executed for this investigation. The evidence below uses the actual ORD-1006 rows and current aggregates from Snowflake.

## Implementation inspected

`SQL_10_ORDERS_CLEAN` normalizes currency with `UPPER(TRIM(currency))`, then includes this validation predicate in `reasons`:

```sql
IFF(currency IS NULL OR currency NOT IN ('INR', 'USD'), 'unsupported_currency', NULL)
```

The rule is present in the implementation and was already active during the B1 run. The clean table admits only rows with no reasons:

```sql
FROM silver.orders_checked WHERE ARRAY_SIZE(reasons) = 0;
```

## Git and execution timeline

Git history first records this predicate in commit `8eccbbaae2a63e2268ed0c0cd52a7710948d6a53` (`Implement credential-safe FreshCart ELT flow`). Its committer timestamp is `2026-11-15T01:36:32+05:30` (2026-11-14T20:06:32Z). The parent commit does not contain `elt/freshcart_pipeline.py`; the pipeline implementation and this validation rule first appear together in that commit. This establishes source-code history only; it does not establish when or how Snowflake was queried.

The saved B1 run has ID `20261115_063011_352098`. Its Bronze trace records the input extraction at `2026-11-15 06:30:11.356583+00:00` (`12:00:11.356583+05:30`), roughly 10 hours 23 minutes 39 seconds after the commit timestamp. The B1 report records one actual pipeline call and its output; it also confirms the currency rule was included. Thus the rule predates the recorded baseline execution.

Git history records the B1 and B3 summary reports together in checkpoint commit `8ccf28c` at `2026-11-15T12:45:57+05:30`, after the recorded B1 extraction. This dates the saved summaries, not the database executions themselves, and supplies no pre-rule execution evidence.

The available B1/B3 reports, the current SQL source, and saved logs were checked for an execution from before the predicate was introduced. No genuine pre-rule Snowflake result, run ID, or execution log was found. The B3 report is a saved summary of later read-only observations; it is not a historical pre-rule run log. The notebook's B3 pipeline cell is executable code without saved output and is not evidence that a separate pre-rule execution occurred.

## ORD-1006 actual reasons

The actual row in `silver.orders_checked` has source `web`, `ingest_seq = 6`, email `vikram@@mail`, pincode `99999`, currency `EUR`, amount `30.00`, and updated time `2026-09-04 08:30:00`.

The actual reasons array, including the active currency rule, is:

```json
["bad_email", "bad_pincode", "unsupported_currency"]
```

The matching row in `quarantine.orders` has the same reasons, source, order ID, ingest sequence, and baseline run ID.

## Counterfactual without the currency rule

A read-only `SELECT` rebuilt the `ARRAY_CONSTRUCT_COMPACT` from the existing `silver.orders_checked` values using all the other validation expressions, but omitted only the currency predicate. Its actual result was:

```json
["bad_email", "bad_pincode"]
```

This is a **SELECT-based counterfactual**, not a result from a historical run with the currency rule disabled. The currency rule was already active during B1, so no historical “before” reasons array was captured.

## Why it remains quarantined

Removing `unsupported_currency` would not make ORD-1006 valid. The actual email `vikram@@mail` fails the email expression and pincode `99999` fails the six-digit pincode expression, leaving `bad_email` and `bad_pincode`. `silver.orders_clean` admits only rows where `ARRAY_SIZE(reasons) = 0`, so this row still cannot enter clean Silver, deduplicated Silver, or Gold under the counterfactual.

## Duplicate quarantine prevention

`SQL_10_ORDERS_CLEAN` inserts rejected rows only when the quarantine table does not already contain the same source, null-safe order ID, and updated timestamp:

```sql
AND NOT EXISTS (
  SELECT 1 FROM quarantine.orders q
  WHERE q.source = c.source
    AND EQUAL_NULL(q.order_id, c.order_id)
    AND EQUAL_NULL(q.row_data:UPDATED_AT::TIMESTAMP_NTZ, c.updated_at)
)
```

The actual ORD-1006 quarantine row matches those identifying fields. On a later execution against the same Bronze record, `NOT EXISTS` finds the existing row with the same `source`, null-safe `order_id`, and `updated_at` stored in `row_data`, and skips inserting a duplicate version. The separate `QUALIFY ROW_NUMBER()` in the `INSERT` also selects only one candidate per source/order/update timestamp within the current input batch. This is the behavior implied by the inspected SQL; no reapplication was executed to demonstrate it.

The current quarantine table contains **2** rows total, including the single observed ORD-1006 row.

## Current Gold totals

At the time of the B3 investigation, the actual read-only aggregate query returned:

| Gold measure | Current value |
| --- | ---: |
| Orders | 4 |
| Revenue | INR 7,785.00 |
| Loyalty points | 126 |

These are actual aggregate values observed at the time of the B3 investigation: 4 Gold orders, INR 7,785.00 revenue, and 126 loyalty points. The explanation for unchanged Gold inclusion is counterfactual reasoning, not a second execution: ORD-1006 still has two rejection reasons without the currency predicate, so the clean-row filter continues to exclude it and it contributes nothing to Gold. No historical before/after comparison or post-change run was performed.

## Evidence available and missing

- **Actual observation:** the B1 execution output is preserved in `reports/b1_baseline_results.md`; its run ID is `20261115_063011_352098`. The later read-only B3 report records ORD-1006's actual reasons as `["bad_email", "bad_pincode", "unsupported_currency"]`, one ORD-1006 quarantine row, two quarantine rows total, and the B3-time Gold totals above.
- **Counterfactual observation:** the B3 report records a read-only SELECT-based result omitting only the currency predicate: `["bad_email", "bad_pincode"]`. This was evaluated from the existing checked row; it is not an observed execution of an older pipeline version.
- **Code provenance:** Git records the predicate in `8eccbba`, before the B1 extraction timestamp. A code version without the rule does not prove that Snowflake ran it.
- **Missing evidence:** no pre-rule Snowflake execution output, run ID, or log exists in the inspected saved evidence. The saved B3 report does not preserve a raw query-session log or the verbatim counterfactual SELECT text, so neither is represented here as a captured artifact.
- No pipeline, cleaning SQL, deduplication SQL, Gold SQL, or database writes were run for the B3 investigation described in this report.
\n
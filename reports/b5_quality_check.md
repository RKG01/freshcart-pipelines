# B5 future-date quality check demonstration

## Actual execution summary

The approved controlled test used `FRESHCART_B1` with `ACCOUNTADMIN` and `COMPUTE_WH`. It did not call `run_pipeline()`, reload Bronze, or modify Gold or any source/reference table. One row was inserted into and deleted from `silver.orders_dedup` within a single transaction. The targeted future-date check returned `PROBLEM` while the row existed, then `OK` after cleanup. The transaction committed only after all cleanup and baseline checks passed.

## Before output

| Read-only precondition | Actual value |
|---|---:|
| `B5-MOCK-FUTURE-001` rows | 0 |
| Future-dated `silver.orders_dedup` rows | 0 |
| `silver.orders_dedup` row count | 4 |
| Gold orders | 4 |
| Gold revenue | INR 7,785.00 |
| Gold loyalty points | 161 |

## Actual SQL and check output

The transaction inserted exactly one row, naming only the requested columns:

```sql
BEGIN TRANSACTION;

INSERT INTO FRESHCART_B1.SILVER.ORDERS_DEDUP (ORDER_ID, ORDER_DATE)
VALUES ('B5-MOCK-FUTURE-001', TO_DATE('2099-01-01', 'YYYY-MM-DD'));

SELECT COUNT(*)
FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE ORDER_DATE > CURRENT_DATE();
```

Actual result displayed using the existing `quality_checks()` output format:

```text
future-dated silver orders             1   PROBLEM
```

Per instruction, only the targeted future-date query ran during the temporary insertion; the full `quality_checks()` function was not called.

## Cleanup and after output

The transaction deleted only the unique temporary ID:

```sql
DELETE FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE ORDER_ID = 'B5-MOCK-FUTURE-001';
```

Actual cleanup and verification results before commit:

```text
DELETE_ROWS_AFFECTED=1
TEMP_ID_COUNT_AFTER=0
FUTURE_DATE_COUNT_AFTER=0
future-dated silver orders             0   OK
DEDUP_ROW_COUNT_AFTER=4
GOLD_TOTALS_AFTER=orders:4 revenue_inr:7785.00 loyalty_points:161
ALL_PRECOMMIT_CHECKS=passed
COMMIT=success
```

A separate post-commit read-only verification returned:

```text
POST_COMMIT_TEMP_ID_COUNT=0
POST_COMMIT_FUTURE_DATE_COUNT=0
POST_COMMIT_DEDUP_ROW_COUNT=4
POST_COMMIT_GOLD_TOTALS=orders:4 revenue_inr:7785.00 loyalty_points:161
```

## Why this quality gate matters

The check catches orders with dates later than `CURRENT_DATE()` in the deduplicated Silver table. Such records can distort time-based reporting or appear in future periods before they should. This controlled row demonstrated the selected check's failure condition without re-running transformations or changing Gold or Bronze.

The targeted check detected one future-dated row and returned to zero after cleanup. No temporary record remains. If any step had failed before commit, the transaction handler would roll back and check that the temporary ID was absent; no retry was attempted.

## Complete actual output

The complete captured execution output, including exact SQL statements, preconditions, in-transaction results, commit, post-commit verification, and connector warnings, is saved in [b5_quality_check_execution.log](b5_quality_check_execution.log). A scan found no credentials in the log.

\n
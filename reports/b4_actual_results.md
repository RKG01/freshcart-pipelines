# FreshCart B4: Actual SCD2 and Gold Results

**Database:** `FRESHCART_B1`
**Role:** `ACCOUNTADMIN`
**Warehouse:** `COMPUTE_WH`
**New CRM run ID:** `20261115_070420_455684`
**B1 baseline run ID:** `20261115_063011_352098`

This records the approved targeted B4 update. `run_pipeline()` was not called. Only the single new CRM event was written and loaded; then `SQL_30_CUSTOMERS_SCD2` and `SQL_40_GOLD` were each executed once. Credentials are not included.

## Event and execution

Before loading, the exact Gold event was absent from `bronze.customers_raw` (`0` matches). The event written was:

```json
{
  "cust_id": "CUST-02",
  "email": "arjun.k@yahoo.in",
  "tier": "Gold",
  "effective_from": "2026-08-15"
}
```

Actual Bronze load result: one CRM row loaded, `ingest_seq = 5`, run ID `20261115_070420_455684`. No orders, FX, or pincode records were loaded.

## Actual SCD2 history

| cust_id | email | tier | valid_from | valid_to | is_current |
| --- | --- | --- | --- | --- | --- |
| CUST-02 | arjun.k@yahoo.in | Silver | 2024-01-15 | 2026-08-14 | FALSE |
| CUST-02 | arjun.k@yahoo.in | Gold | 2026-08-15 | 9999-12-31 | TRUE |

CUST-02 has exactly 2 rows. The Silver period now ends on 2026-08-14, the day before the Gold event; the Gold period starts on 2026-08-15.

## ORD-1002 Gold result

| order_id | order_date | tier | multiplier | amount | currency | fx_rate | amount_inr | loyalty_points | row_hash | published_at |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| ORD-1002 | 2026-09-01 | Gold | 2 | 42.50 | USD | 83.2000 | 3536.00 | 70 | 3392257107350681567 | 2026-11-14 23:04:22.990000-08:00 |

## Gold comparison

The pre-change values below were preserved from `reports/b4_predictions.md` before the database update. Actual post-change values are from a read-only query after `SQL_40_GOLD` completed.

| order_id | Before tier | Before multiplier | Before points | Before row_hash | Before published_at | After tier | After multiplier | After points | After row_hash | After published_at | published_at changed |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| ORD-1001 | Silver | 1 | 12 | 4284627330879666653 | 2026-11-14 22:30:28.048000-08:00 | Silver | 1 | 12 | 4284627330879666653 | 2026-11-14 22:30:28.048000-08:00 | No |
| ORD-1002 | Silver | 1 | 35 | -7698738864412791922 | 2026-11-14 22:30:28.048000-08:00 | Gold | 2 | 70 | 3392257107350681567 | 2026-11-14 23:04:22.990000-08:00 | Yes |
| ORD-1003 | Platinum | 3 | 63 | -1632326326823866187 | 2026-11-14 22:30:28.048000-08:00 | Platinum | 3 | 63 | -1632326326823866187 | 2026-11-14 22:30:28.048000-08:00 | No |
| ORD-1005 | Gold | 2 | 16 | -231880702048109571 | 2026-11-14 22:30:28.048000-08:00 | Gold | 2 | 16 | -231880702048109571 | 2026-11-14 22:30:28.048000-08:00 | No |

Exactly one row, ORD-1002, changed `published_at`. No other Gold row changed.

## Gold totals

| Measure | Before | Actual after |
| --- | ---: | ---: |
| Orders | 4 | 4 |
| Revenue | INR 7,785.00 | INR 7,785.00 |
| Loyalty points | 126 | 161 |

The points increase by 35: ORD-1002's INR amount is unchanged at 3,536.00, but the Gold multiplier changes its points from `FLOOR(3,536 / 100) × 1 = 35` to `FLOOR(3,536 / 100) × 2 = 70`. No other orders changed.

## Execution boundary

The targeted execution did not call `run_pipeline()`, reload order/FX/pincode data, or execute B5. Only the single CRM event was loaded, followed by one execution each of `SQL_30_CUSTOMERS_SCD2` and `SQL_40_GOLD`; all verification queries were read-only.
\n
# FreshCart B1 Baseline Results

**Database:** `FRESHCART_B1`
**Role:** `ACCOUNTADMIN`
**Warehouse:** `COMPUTE_WH`
**Run ID:** `20261115_063011_352098`

This records the single observed baseline execution. `run_pipeline(connection)` was called once; `baseline_snapshot(connection)` was called immediately afterward. No retry or second pipeline run was made. Credentials are not included.

## Actual pipeline output

```text
web: 6 records -> data\freshcart_landing\web\web__20261115_063011_352098.json.gz
mobile: 2 records -> data\freshcart_landing\mobile\mobile__20261115_063011_352098.json.gz
crm: 4 records -> data\freshcart_landing\crm\crm__20261115_063011_352098.json.gz
fx: 1 records -> data\freshcart_landing\fx\fx__20261115_063011_352098.json.gz
6 rows -> bronze.orders_raw
2 rows -> bronze.orders_raw
4 rows -> bronze.customers_raw
1 rows -> bronze.fx_raw
pincode: 3 records -> data\freshcart_landing\pincode\pincode__20261115_063011_352098.json.gz
3 rows -> bronze.pincode_raw
rows gained or lost while enriching    0   OK
duplicate orders in gold               0   OK
orders with no customer match          0   OK
orders with an amount but no FX rate   0   OK
orders with no city                    0   OK
future-dated silver orders             0   OK
share of rows rejected                 25%
GOLD: 4 orders, revenue INR 7785.00, 126 loyalty points
RUN_ID: 20261115_063011_352098
BASELINE_SNAPSHOT: {'bronze_orders': 8, 'clean_orders': 6, 'quarantined_orders': 2, 'deduplicated_orders': 4, 'gold_orders': 4, 'gold_revenue_inr': Decimal('7785.00'), 'gold_loyalty_points': 126}
rows gained or lost while enriching    0   OK
duplicate orders in gold               0   OK
orders with no customer match          0   OK
orders with an amount but no FX rate   0   OK
orders with no city                    0   OK
future-dated silver orders             0   OK
share of rows rejected                 25%
QUALITY_CHECK_RESULTS: {'rows gained or lost while enriching': 0, 'duplicate orders in gold': 0, 'orders with no customer match': 0, 'orders with an amount but no FX rate': 0, 'orders with no city': 0, 'future-dated silver orders': 0, 'share of rows rejected': 0.25}
```

## Assignment values

| Check | Actual |
| --- | ---: |
| Bronze raw orders | 8 (6 web + 2 mobile) |
| Silver clean orders | 6 |
| Quarantine orders | 2 |
| Deduplicated orders | 4 |
| Gold orders | 4 |
| Gold revenue | INR 7,785.00 |
| Gold loyalty points | 126 |
| Rejected share | 25% |

## Scope note

The existing `run_pipeline()` includes the currency validation rule and six quality checks, including the future-date check; these ran as part of this single baseline call and returned the output shown above. No B3 before/after comparison, Arjun SCD2 event, B5 future-date mock order, isolated B5 run, or follow-up pipeline execution was performed.
\n
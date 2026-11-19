# D2: Two-minute RabbitMQ dispatcher run

## Run window and readiness

- Run ID: `20261116_013650`
- Dispatcher process start: `2026-11-16T01:36:50.9758712+05:30`
- Dispatcher process stop: `2026-11-16T01:38:51.0731853+05:30`
- Actual elapsed process time: `00:02:00.0973141` (120.097 seconds)
- All six drivers reported their expected listening binding before the dispatcher started.
- Dispatcher remained on its existing 2-second interval. RabbitMQ was healthy before and after the run.

## Actual message counts

The dispatcher log contains 59 completed publish calls with 59 unique message IDs and no duplicate ID lines (sequence numbers 1 through 59). Of these, 54 JSON messages included `zone` and 5 omitted it, for sequences 10, 20, 30, 40, and 50.

Counts below are deduplicated by message ID within each driver's log.

| Driver | Valid messages received | Invalid messages rejected |
|---|---:|---:|
| Ravi | 5 | 1 |
| Priya | 9 | 2 |
| Arjun | 10 | 2 |
| Meena | 14 | 1 |
| Karthik | 8 | 1 |
| Control | 24 | 3 |
| **Per-driver deliveries** | **70** | **10** |

The 5 invalid published messages caused 10 rejection deliveries: invalid messages can match more than one driver's binding. One invalid message, `bd9330b6-056e-40fb-9d60-5193b07f9126` (`chennai.whitefield.ride`), matched no configured binding and therefore appears in no driver log. The rejection counts are delivery counts across the queues, not distinct published invalid messages.

One message may be delivered to multiple driver queues because a RabbitMQ topic exchange routes a publication to every queue whose binding matches. For that reason, the sum of driver deliveries (80 received plus rejected) is not expected to equal the 59 dispatcher publish calls. Some messages may also match no driver queue.

## Sample actual output

| Routing key | Message ID | Observed driver result |
|---|---|---|
| `bangalore.whitefield.food` | `b50f95df-5f49-4e22-a95d-9377690e5db1` | Meena and Control received |
| `bangalore.whitefield.ride` | `f15d129a-7d27-4d63-a5c2-a5c50aa78b7f` | Arjun and Control received |
| `chennai.whitefield.ride` | `7974731a-55e8-4f07-887f-e4a2d2f86383` | No configured driver received |
| `bangalore.koramangala.ride` (zone omitted from body) | `dbe05055-4fc4-4bf0-900d-da04ef190c8d` | Ravi, Arjun, and Control rejected |
| `chennai.tnagar.food` (zone omitted from body) | `a58d66b7-bc63-4c0b-8006-c12f12f6ab15` | Karthik rejected |

## Logs and final checks

Complete raw stdout and stderr logs for the dispatcher and each driver, readiness/timing metadata, and test logs are in [`reports/rabbitmq_logs/d2/20261116_013650/`](rabbitmq_logs/d2/20261116_013650/). The log scan found no credential patterns.

The helper recorded seven started processes (six drivers and the dispatcher) and seven stopped processes; none of the helper-owned PIDs remain running. RabbitMQ remains healthy, and named volume `freshcart_rabbitmq_data` still exists. The D1 prediction file's SHA256 was unchanged before and after D2: `BA39A703BC9D4B771CA15E6C21CF20BF1E0D922C4D87F82A93C00BF8AD38BE43`.

Test results:

- Stream routing tests in the existing `.venv`: `4 passed in 0.06s`.
- The requested full `.venv` `python -m pytest -q` attempt stopped at collection because `scikit-learn` (`sklearn`) is missing; details are in `pytest_full.log`. I did not reinstall `requirements.txt`.
- The complete suite in the disposable Mage Docker image passed: `18 passed, 1 warning in 7.08s`; details are in `pytest_mage_container.log`.

No D3 test was run. No RabbitMQ container or volume was recreated or stopped.

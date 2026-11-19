# D3: Consumer ACK and NACK verification

## Actual test run

- Run ID: `20261116_015016`
- Dispatcher start: `2026-11-16T01:50:17.3797781+05:30`
- Dispatcher stop: `2026-11-16T01:51:17.7716440+05:30`
- Actual process duration: `00:01:00.3918659` (60.392 seconds)
- All six drivers printed their expected listening binding before the dispatcher started.
- RabbitMQ remained running and healthy.

## Actual counts from logs

The dispatcher logged 29 publish calls with 29 unique IDs and no repeated publish-ID lines. Sequences 1–29 contained 27 valid messages and 2 messages whose JSON body omitted `zone` (sequences 10 and 20).

| Driver | ACK operations | NACK operations (`requeue=False`) |
|---|---:|---:|
| Ravi | 3 | 1 |
| Priya | 5 | 0 |
| Arjun | 8 | 0 |
| Meena | 9 | 1 |
| Karthik | 3 | 0 |
| Control | 17 | 1 |
| **Total** | **45** | **3** |

The invalid ID `a196cdc8-92a3-40db-8465-720c4194e81f` (`bangalore.koramangala.food`) matched Ravi, Meena, and Control, and all three logged a NACK with `requeue=False`. Invalid ID `bb84ca62-c64c-42ed-94bb-3fac9526154f` (`chennai.tnagar.ride`) matched none of the configured driver bindings, so no consumer received it and no NACK was logged for it.

Across all driver logs, no invalid message ID was processed more than once by the same driver. Valid messages continued to be processed and ACKed throughout the run.

## Sample actual log lines

```text
[Ravi] RECEIVED routing_key=bangalore.koramangala.ride message_id=f404d2b0-48f2-4de6-8451-26a426e34d19 ack_status=acked
[Meena] REJECTED routing_key=bangalore.koramangala.food message_id=a196cdc8-92a3-40db-8465-720c4194e81f nack_status=nacked requeue=False reason=missing_or_invalid_zone
```

The driver now logs the ACK/NACK status after issuing the existing acknowledgement call. The logic remains `basic_ack(delivery_tag=delivery_tag)` for valid messages and `basic_nack(delivery_tag=delivery_tag, requeue=False)` for messages without a valid zone. Consumers remain in manual-ack mode (`auto_ack=False`). The dispatcher still omits `zone` every tenth JSON message. No dead-letter exchange or queue dead-letter argument is configured in the stream code.

## Why the ACK/NACK behavior matters

- If a consumer crashes or its channel/connection closes before acknowledging a delivery, RabbitMQ automatically requeues that unacknowledged message for redelivery. Consumers should therefore tolerate redelivery and make processing idempotent where side effects are involved. [RabbitMQ consumer acknowledgements documentation](https://www.rabbitmq.com/docs/confirms)
- `requeue=True` is intended for a message that may succeed later. A permanently malformed message still lacks its required `zone` on every delivery, so immediate NACK-and-requeue can repeatedly deliver it and create a costly redelivery loop. [RabbitMQ documents this requeue loop behavior](https://www.rabbitmq.com/docs/confirms)
- Here, a missing `zone` makes the request permanently invalid for this consumer. `requeue=False` prevents it from cycling back through the same queue. RabbitMQ discards such a message when no dead-letter exchange is configured; with a DLX, it would route there instead. [RabbitMQ NACK/requeue semantics](https://www.rabbitmq.com/docs/confirms)

## Logs and checks

All raw process logs and exact timing/process metadata are in [`reports/rabbitmq_logs/d3/20261116_015016/`](rabbitmq_logs/d3/20261116_015016/). A scan found no credential patterns in these logs.

- Stream tests: `4 passed in 0.05s`.
- Python compilation: passed.
- Helper started seven processes (six drivers and one dispatcher) and stopped all seven; none remain running.
- RabbitMQ remains healthy. No Docker volume was deleted, and the D1 prediction file remains unchanged.

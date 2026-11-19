# Phase 4: RabbitMQ implementation verification

## Dispatcher (`stream/dispatcher.py`)

| Requirement | Finding |
|---|---|
| Uses pika | Yes; opens `BlockingConnection` using `pika.URLParameters(RABBITMQ_URL)`. |
| Publishes every 2 seconds | Yes; `run_dispatcher` defaults to `interval_seconds=2.0` and sleeps after each publish. |
| Randomly selects Bangalore or Chennai | Yes; uses `choice(("bangalore", "chennai"))`. |
| Chooses valid city zones | Yes; Bangalore zones are Koramangala, Indiranagar, and Whitefield; Chennai zones are T Nagar and Whitefield. |
| Randomly selects ride or food | Yes. |
| Builds `city.zone.type` routing key | Yes. |
| JSON fields `id`, `city`, `zone`, `type`, `ts` | Yes for normal messages; `zone` is deliberately removed every tenth message. |
| Topic exchange `rapido-dispatch` | Yes; declared as a durable topic exchange and used for publishing. |
| Invalid message every tenth sequence | Yes; `create_message` removes `zone` when `sequence % 10 == 0`, while retaining the three-word routing key. |

## Driver (`stream/driver.py`)

| Requirement | Finding |
|---|---|
| Accepts driver name and pattern | Yes; both are required positional CLI arguments. |
| Private exclusive queue | Yes; uses an unnamed queue with `exclusive=True`. |
| Auto-delete | Yes; `auto_delete=True`. |
| Binds to requested pattern | Yes; passes the supplied binding pattern to `queue_bind`. |
| Manual acknowledgements | Yes; `basic_consume(..., auto_ack=False)`. |
| ACK valid messages | Yes; calls `basic_ack(delivery_tag=...)`. |
| NACK messages missing a valid zone | Yes; calls `basic_nack(delivery_tag=..., requeue=False)`. |
| Required message logging | Corrected: both received and rejected logs now include driver name, routing key, message ID (or an explicit missing/unknown marker), and status. |

The only code change was to make driver receipt/rejection logging complete. The existing routing test was extended to assert those log fields and preserve its ACK/NACK checks. No dispatcher or routing logic was rewritten.

## Verification performed

The existing local routing test file was run in `.venv`. The first attempt could not start because pytest was absent, so only `pytest` was installed into `.venv`; `requirements.txt` was not reinstalled.

```text
=== Existing local routing tests ===
....                                                                     [100%]
4 passed in 0.05s
ROUTING_TEST_EXIT=0
=== Python compilation ===
COMPILE_EXIT=0
=== Existing RabbitMQ service readiness (no publish) ===
container=/freshcart-rabbitmq health=healthy
```

A pika AMQP connection handshake to the local broker also succeeded without publishing a message:

```text
AMQP_CONNECTION=success (no messages published)
```

No RabbitMQ messages were published. Docker configuration and `.env` were not changed. No `.env` values or credentials were printed.

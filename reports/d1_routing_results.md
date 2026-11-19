# D1 live RabbitMQ routing results

The six predictions in `reports/d1_routing_predictions.md` were preserved unchanged. Six separate driver processes were started and each printed its listening binding before publication. The deterministic publisher sent `D1-01` through `D1-06` once each; the publisher run was resumed at `D1-02` after correcting a confirmation-return interpretation, so `D1-01` was not resent.

## Predicted versus actual recipients

| ID | Routing key | Predicted recipients | Actual recipients | Publisher result / route status | Match |
|---|---|---|---|---|---|
| `D1-01` | `bangalore.koramangala.food` | Ravi, Meena, Control | Ravi, Meena, Control | Broker confirmation received; routed | Yes |
| `D1-02` | `bangalore.indiranagar.ride` | Priya, Arjun, Control | Priya, Arjun, Control | Broker confirmation received; routed | Yes |
| `D1-03` | `bangalore.whitefield.ride` | Arjun, Control | Arjun, Control | Broker confirmation received; routed | Yes |
| `D1-04` | `chennai.tnagar.food` | Karthik | Karthik | Broker confirmation received; routed | Yes |
| `D1-05` | `chennai.whitefield.ride` | Dropped | No driver | Broker confirmation received with mandatory unroutable return; dropped | Yes |
| `D1-06` | `bangalore.koramangala` | Control only | Control | Broker confirmation received; routed | Yes |

## Confirmation and consumption evidence

The publisher enables `channel.confirm_delivery()` and publishes with `mandatory=True`. For `D1-02`, `D1-03`, `D1-04`, and `D1-06`, pika's blocking publish call returned without a NACK or unroutable exception; its normal successful return value is `None`. For `D1-05`, pika raised `UnroutableError` after RabbitMQ returned the mandatory message and confirmed the publish; the publisher recorded it as dropped. `D1-01` also returned normally in confirm mode and the three expected driver logs contain its ID. The first publisher wrapper incorrectly interpreted the normal `None` return as failure after publishing `D1-01`; that wrapper was corrected before resuming at ID `D1-02`, preventing a duplicate.

The driver logs show these unique IDs:

- Ravi: `D1-01`
- Priya: `D1-02`
- Arjun: `D1-02`, `D1-03`
- Meena: `D1-01`
- Karthik: `D1-04`
- Control: `D1-01`, `D1-02`, `D1-03`, `D1-06`
- No driver log contains `D1-05`.

The sixth routing key is exactly `bangalore.koramangala` (two words). `bangalore.#` matches it because `#` matches zero or more words. The other bindings require three words, so none matched this two-word key.

No mismatch from the original predictions was observed.

## Logs and verification

Per-driver standard output and error logs are in [`reports/rabbitmq_logs/d1/`](rabbitmq_logs/d1/). Publisher logs are `publisher.log` and `publisher_initial_attempt.log` in that directory. The credential scan found no `RABBITMQ_PASSWORD`, `amqp://`, or `password=` values in the D1 logs.

Relevant local routing tests: `4 passed in 0.06s`. Python compilation of `stream/` passed. The RabbitMQ container remains healthy. Only the six driver processes started for this test were stopped; the RabbitMQ container and persistent volume remain running/preserved.

\n
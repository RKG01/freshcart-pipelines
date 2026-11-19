"""Publish the six deterministic D1 routing examples with broker confirms."""

from __future__ import annotations

import json
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

if not os.getenv("RABBITMQ_URL"):
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if key.strip() == "RABBITMQ_URL":
                os.environ["RABBITMQ_URL"] = value.strip()
                break

EXCHANGE_NAME = "rapido-dispatch"
EXAMPLES = (
    ("bangalore.koramangala.food", "bangalore", "koramangala", "food"),
    ("bangalore.indiranagar.ride", "bangalore", "indiranagar", "ride"),
    ("bangalore.whitefield.ride", "bangalore", "whitefield", "ride"),
    ("chennai.tnagar.food", "chennai", "tnagar", "food"),
    ("chennai.whitefield.ride", "chennai", "whitefield", "ride"),
    ("bangalore.koramangala", "bangalore", "koramangala", "food"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-at",
        type=int,
        choices=range(1, len(EXAMPLES) + 1),
        default=1,
        help="Resume at this example index without repeating earlier publishes.",
    )
    args = parser.parse_args()

    broker_url = os.getenv("RABBITMQ_URL")
    if not broker_url:
        raise RuntimeError("Set RABBITMQ_URL in the environment or local .env file")

    import pika

    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    channel.confirm_delivery()

    try:
        for index, (routing_key, city, zone, order_type) in enumerate(EXAMPLES, start=1):
            if index < args.start_at:
                continue
            message_id = f"D1-{index:02d}"
            body = {
                "id": message_id,
                "city": city,
                "zone": zone,
                "type": order_type,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            try:
                confirmed = channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=routing_key,
                    body=json.dumps(body),
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=1,
                        message_id=message_id,
                    ),
                    mandatory=True,
                )
            except pika.exceptions.UnroutableError:
                if index != 5:
                    raise
                print(
                    f"id={message_id} routing_key={routing_key} "
                    "publisher_confirmation=received route_status=dropped_unroutable",
                    flush=True,
                )
            else:
                if index == 5:
                    raise RuntimeError("Expected D1-05 to be unroutable, but it was routed")
                print(
                    f"id={message_id} routing_key={routing_key} "
                    "publisher_confirmation=received route_status=routed",
                    flush=True,
                )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

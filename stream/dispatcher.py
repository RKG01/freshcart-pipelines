"""Publish random city.zone.type messages to a RabbitMQ topic exchange."""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

EXCHANGE_NAME = "rapido-dispatch"


def create_message(sequence: int, chooser=random) -> tuple[str, dict[str, str]]:
    """Build a routing key and payload; omit zone every tenth message."""
    city = chooser.choice(("bangalore", "chennai"))
    zones = ("koramangala", "indiranagar", "whitefield") if city == "bangalore" else ("tnagar", "whitefield")
    zone = chooser.choice(zones)
    order_type = chooser.choice(("ride", "food"))
    routing_key = f"{city}.{zone}.{order_type}"
    message = {
        "id": str(uuid4()),
        "city": city,
        "zone": zone,
        "type": order_type,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if sequence % 10 == 0:
        message.pop("zone")
    return routing_key, message


def run_dispatcher(interval_seconds: float = 2.0) -> None:
    """Publish continuously until interrupted; broker URL comes from the environment."""
    broker_url = os.getenv("RABBITMQ_URL")
    if not broker_url:
        raise RuntimeError("Set RABBITMQ_URL in the environment or local .env file")

    import pika

    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    sequence = 0
    try:
        while True:
            sequence += 1
            routing_key, message = create_message(sequence)
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )
            print(f"published #{sequence} {routing_key} {message}", flush=True)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("Dispatcher stopped.")
    finally:
        connection.close()


if __name__ == "__main__":
    run_dispatcher()

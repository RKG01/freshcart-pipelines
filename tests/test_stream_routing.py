"""Verify the assignment's routing examples and malformed-message rule."""

import random

from stream.dispatcher import create_message
from stream.driver import handle_delivery
from stream.routing import has_zone, topic_matches

BINDINGS = {
    "Ravi": "bangalore.koramangala.*",
    "Priya": "bangalore.indiranagar.*",
    "Arjun": "bangalore.*.ride",
    "Meena": "bangalore.*.food",
    "Karthik": "chennai.tnagar.food",
    "Control": "bangalore.#",
}


def test_assignment_routing_examples():
    expected = {
        "bangalore.koramangala.food": {"Ravi", "Meena", "Control"},
        "bangalore.indiranagar.ride": {"Priya", "Arjun", "Control"},
        "bangalore.whitefield.ride": {"Arjun", "Control"},
        "chennai.tnagar.food": {"Karthik"},
        "chennai.whitefield.ride": set(),
        "bangalore.koramangala": {"Control"},
    }

    for routing_key, expected_drivers in expected.items():
        received_by = {
            name for name, binding in BINDINGS.items()
            if topic_matches(binding, routing_key)
        }
        assert received_by == expected_drivers


def test_dispatcher_makes_tenth_message_invalid():
    routing_key, message = create_message(10, random.Random(7))

    assert len(routing_key.split(".")) == 3
    assert "zone" not in message
    assert not has_zone(message)


def test_valid_dispatcher_message_has_zone():
    _, message = create_message(9, random.Random(7))

    assert has_zone(message)


def test_driver_nacks_missing_zone_and_acks_valid_message(capsys):
    class RecordingChannel:
        def __init__(self):
            self.actions = []

        def basic_nack(self, **kwargs):
            self.actions.append(("nack", kwargs))

        def basic_ack(self, **kwargs):
            self.actions.append(("ack", kwargs))

    channel = RecordingChannel()
    handle_delivery(
        channel,
        1,
        "bangalore.koramangala.ride",
        b'{"id":"invalid-1","city":"bangalore"}',
        "Ravi",
    )
    handle_delivery(
        channel,
        2,
        "bangalore.koramangala.ride",
        b'{"id":"valid-2","zone":"koramangala"}',
        "Ravi",
    )

    assert channel.actions == [
        ("nack", {"delivery_tag": 1, "requeue": False}),
        ("ack", {"delivery_tag": 2}),
    ]
    output = capsys.readouterr().out
    assert "[Ravi] REJECTED routing_key=bangalore.koramangala.ride message_id=invalid-1 nack_status=nacked requeue=False" in output
    assert "[Ravi] RECEIVED routing_key=bangalore.koramangala.ride message_id=valid-2 ack_status=acked" in output

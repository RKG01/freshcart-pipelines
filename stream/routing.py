"""Pure helpers for RabbitMQ topic-routing tests and message validation."""

from functools import lru_cache
from typing import Any


def topic_matches(binding_pattern: str, routing_key: str) -> bool:
    """Apply AMQP topic semantics: '*' is one word and '#' is zero or more."""
    pattern_words = tuple(binding_pattern.split("."))
    key_words = tuple(routing_key.split("."))

    @lru_cache(maxsize=None)
    def match(pattern_index: int, key_index: int) -> bool:
        if pattern_index == len(pattern_words):
            return key_index == len(key_words)
        pattern_word = pattern_words[pattern_index]
        if pattern_word == "#":
            return match(pattern_index + 1, key_index) or (
                key_index < len(key_words) and match(pattern_index, key_index + 1)
            )
        if key_index == len(key_words):
            return False
        return (pattern_word == "*" or pattern_word == key_words[key_index]) and match(
            pattern_index + 1, key_index + 1
        )

    return match(0, 0)


def has_zone(message: Any) -> bool:
    """Return whether a decoded dispatcher message has a non-empty zone."""
    return isinstance(message, dict) and bool(message.get("zone"))

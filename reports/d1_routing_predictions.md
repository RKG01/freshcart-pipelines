# D1 routing predictions

These predictions are recorded before any live RabbitMQ routing tests. Keep them unchanged when comparing with later observed results.

## Driver bindings

| Driver | Topic binding pattern |
|---|---|
| Ravi | `bangalore.koramangala.*` |
| Priya | `bangalore.indiranagar.*` |
| Arjun | `bangalore.*.ride` |
| Meena | `bangalore.*.food` |
| Karthik | `chennai.tnagar.food` |
| Control | `bangalore.#` |

## Predicted recipients

| # | Routing key | Predicted recipients |
|---:|---|---|
| 1 | `bangalore.koramangala.food` | Ravi, Meena, Control |
| 2 | `bangalore.indiranagar.ride` | Priya, Arjun, Control |
| 3 | `bangalore.whitefield.ride` | Arjun, Control |
| 4 | `chennai.tnagar.food` | Karthik |
| 5 | `chennai.whitefield.ride` | Dropped |
| 6 | `bangalore.koramangala` | Control only |

## Topic wildcard behavior

- `*` matches exactly one routing-key word, where words are separated by dots.
- `#` matches zero or more routing-key words.
- The sixth key, `bangalore.koramangala`, has two words: `bangalore` and `koramangala`. `bangalore.#` matches it because `#` can match zero words after `bangalore.`.
- The other driver patterns do not match the sixth key: each contains three literal or wildcard word positions, while this key has only two words. A `*` cannot match zero words, and none of those patterns uses `#`.

\n
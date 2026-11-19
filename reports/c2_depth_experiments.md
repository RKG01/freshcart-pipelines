# Part C2: Mage max-depth experiments

All five experiments ran sequentially in the official `mageai/mageai:latest` Docker image using the existing `iris_project`. Before each run, `iris_predictions.csv` was removed from the project root. The accuracy for the failed run comes from Mage's `test_accuracy` assertion; successful-run accuracy was calculated from that run's CSV by comparing `target` and `predicted` across its 30 rows.

| `max_depth` | Actual accuracy | `train_model` test | Mage exit code | CSV created |
|---:|---:|---|---:|---|
| 1 | 0.633 | FAIL (below 0.8) | 1 | No |
| 2 | 0.966667 (29/30) | PASS | 0 | Yes |
| 3 | 1.000 (30/30) | PASS | 0 | Yes |
| 4 | 1.000 (30/30) | PASS | 0 | Yes |
| 5 | 1.000 (30/30) | PASS | 0 | Yes |

## Why depth 1 has no prediction CSV

Mage ran `train_model`'s `test_accuracy` against its output and reported `Model accuracy 0.633 is below 0.8`. Because that test failed, Mage marked the `train_model` block as failed and did not proceed to its downstream `save_results` exporter. The CSV was absent after the run. This is the expected depth 1 result; the model logic and test threshold were not changed.

## Actual execution evidence

Each linked log contains the complete captured Mage stdout and stderr for that invocation:

- [Depth 1 Mage log](c2_depth_1.log) — assertion: `Model accuracy 0.633 is below 0.8`; Mage exit code 1; CSV absent.
- [Depth 2 Mage log](c2_depth_2.log) — `Pipeline run completed.`; Mage exit code 0; CSV created (30 rows).
- [Depth 3 Mage log](c2_depth_3.log) — `Pipeline run completed.`; Mage exit code 0; CSV created (30 rows).
- [Depth 4 Mage log](c2_depth_4.log) — `Pipeline run completed.`; Mage exit code 0; CSV created (30 rows).
- [Depth 5 Mage log](c2_depth_5.log) — `Pipeline run completed.`; Mage exit code 0; CSV created (30 rows).

Command template used for each run (the JSON depth was changed for each experiment):

```powershell
docker run --rm -v "${PWD}:/home/src" -w /home/src mageai/mageai:latest mage run iris_project iris_classifier --test --runtime-vars '{"max_depth": N}'
```

\n
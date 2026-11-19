# Part C4: `validate_iris` verification

## Verification

All five requested requirements are already met; no block logic or pipeline metadata was changed.

1. `validate_iris` is a `transformer` block.
2. It follows `load_iris` directly in the graph.
3. It raises `ValueError` if any value is missing.
4. It raises `ValueError` unless `target` contains exactly three unique classes, and returns the input dataframe unchanged when valid.
5. Its own `@test` checks both that the output has no missing values and that it contains exactly three target classes.

## Existing block code

```python
@transformer
def validate(df: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
    """Return the data unchanged after checking its basic structure."""
    if df.isna().any().any():
        raise ValueError("Iris data contains missing values")
    if df["target"].nunique() != 3:
        raise ValueError("Iris data must contain exactly three classes")
    return df


@test
def test_output(output: pd.DataFrame, *args) -> None:
    assert not output.isna().any().any()
    assert output["target"].nunique() == 3
```

The block uses conditional imports for Mage's `transformer` and `test` decorators, preserving importability when Mage is absent.

## Position in `metadata.yaml`

The existing graph places the single `validate_iris` block between `load_iris` and `prepare_data`:

```yaml
- name: load_iris
  uuid: load_iris
  type: data_loader
  language: python
  upstream_blocks: []
  downstream_blocks: [validate_iris]
- name: validate_iris
  uuid: validate_iris
  type: transformer
  language: python
  upstream_blocks: [load_iris]
  downstream_blocks: [prepare_data]
- name: prepare_data
  uuid: prepare_data
  type: transformer
  language: python
  upstream_blocks: [validate_iris]
  downstream_blocks: [train_model]
```

There is one `validate_iris` UUID/name in the pipeline metadata; no duplicate block was created.

## Mage execution evidence

Command run inside Docker:

```text
docker run --rm -v "${PWD}:/home/src" -w /home/src mageai/mageai:latest mage run iris_project iris_classifier --test
```

Mage exited with code 0 and reported six block tests passing and `Pipeline run completed.` The log emits each test result as `1/1 tests passed.` without a block name; in graph execution order, `validate_iris` is the second result, after `load_iris` and before `prepare_data`.

Complete captured output: [c4_mage_run.log](c4_mage_run.log).

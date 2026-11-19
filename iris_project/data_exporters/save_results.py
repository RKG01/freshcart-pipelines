"""Export predictions after the training block's quality test passes."""

import pandas as pd

if 'data_exporter' not in globals():
    try:
        from mage_ai.data_preparation.decorators import data_exporter
    except ModuleNotFoundError as error:
        if error.name != 'mage_ai':
            raise

        def data_exporter(function):
            return function

if 'test' not in globals():
    try:
        from mage_ai.data_preparation.decorators import test
    except ModuleNotFoundError as error:
        if error.name != 'mage_ai':
            raise

        def test(function):
            return function


@data_exporter
def export_data(df: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
    """Save test-set predictions and return them for the block test."""
    df.to_csv("iris_predictions.csv", index=False)
    return df


@test
def test_output(output: pd.DataFrame, *args) -> None:
    assert "predicted" in output.columns
    assert len(output) == 30

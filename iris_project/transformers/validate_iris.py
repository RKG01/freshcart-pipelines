"""Validate the Iris input before splitting it for model training."""

import pandas as pd

if 'transformer' not in globals():
    try:
        from mage_ai.data_preparation.decorators import transformer
    except ModuleNotFoundError as error:
        if error.name != 'mage_ai':
            raise

        def transformer(function):
            return function

if 'test' not in globals():
    try:
        from mage_ai.data_preparation.decorators import test
    except ModuleNotFoundError as error:
        if error.name != 'mage_ai':
            raise

        def test(function):
            return function


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

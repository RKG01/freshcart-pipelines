"""Split the Iris dataframe into deterministic training and test rows."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

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
def transform(df: pd.DataFrame, *args: Any, **kwargs: Any) -> pd.DataFrame:
    """Return the input rows with an 80/20 train/test label."""
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df["split"] = "train"
    test_df["split"] = "test"
    return pd.concat([train_df, test_df])


@test
def test_output(output: pd.DataFrame, *args: Any) -> None:
    """Ensure the split produced the assignment's expected row counts."""
    assert (output["split"] == "train").sum() == 120
    assert (output["split"] == "test").sum() == 30

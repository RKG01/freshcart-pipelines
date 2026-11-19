"""Load the built-in Iris dataset for the Mage pipeline."""

import pandas as pd
from sklearn.datasets import load_iris

if 'data_loader' not in globals():
    try:
        from mage_ai.data_preparation.decorators import data_loader
    except ModuleNotFoundError as error:
        if error.name != 'mage_ai':
            raise

        def data_loader(function):
            return function

if 'test' not in globals():
    try:
        from mage_ai.data_preparation.decorators import test
    except ModuleNotFoundError as error:
        if error.name != 'mage_ai':
            raise

        def test(function):
            return function


@data_loader
def load_data(*args, **kwargs) -> pd.DataFrame:
    """Return the 150 Iris observations and their target labels."""
    return load_iris(as_frame=True).frame


@test
def test_output(output: pd.DataFrame, *args) -> None:
    assert len(output) == 150
    assert "target" in output.columns

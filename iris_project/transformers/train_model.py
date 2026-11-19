"""Train and test the Iris decision-tree classifier."""

from typing import Any

import joblib
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

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


FEATURES = [
    "sepal length (cm)",
    "sepal width (cm)",
    "petal length (cm)",
    "petal width (cm)",
]


@transformer
def train(df: pd.DataFrame, *args: Any, **kwargs: Any) -> pd.DataFrame:
    """Fit a decision tree and add predictions for held-out rows."""
    max_depth = int(kwargs.get("max_depth", 3))
    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"].copy()

    model = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
    model.fit(train_df[FEATURES], train_df["target"])
    test_df["predicted"] = model.predict(test_df[FEATURES])
    joblib.dump(model, "iris_model.pkl")
    return test_df


@test
def test_accuracy(output: pd.DataFrame, *args) -> None:
    accuracy = (output["predicted"] == output["target"]).mean()
    assert accuracy >= 0.8, f"Model accuracy {accuracy:.3f} is below 0.8"

"""Create a compact classification metrics table."""

from typing import Any
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

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
def evaluate(df: pd.DataFrame, *args: Any, **kwargs: Any) -> pd.DataFrame:
    """Print and save the confusion matrix, then return classification metrics."""
    y_true = df["target"]
    y_pred = df["predicted"]
    labels = [0, 1, 2]
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    matrix_df = pd.DataFrame(matrix, index=labels, columns=labels)
    matrix_path = Path("reports/c3_confusion_matrix.csv")
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_df.to_csv(matrix_path, index_label="actual_class")

    metrics = pd.DataFrame(
        {
            "metric": ["accuracy", "precision", "recall", "f1_score"],
            "value": [
                round(accuracy_score(y_true, y_pred), 3),
                round(precision_score(y_true, y_pred, average="macro", zero_division=0), 3),
                round(recall_score(y_true, y_pred, average="macro", zero_division=0), 3),
                round(f1_score(y_true, y_pred, average="macro", zero_division=0), 3),
            ],
        }
    )
    print("Confusion matrix (rows = actual, columns = predicted; labels = [0, 1, 2]):")
    print(matrix_df.to_string())
    print("Evaluation metrics:")
    print(metrics.to_string(index=False))
    return metrics


@test
def test_output(output: pd.DataFrame, *args) -> None:
    assert output["metric"].tolist() == ["accuracy", "precision", "recall", "f1_score"]
    assert output["value"].between(0, 1).all()
    matrix = pd.read_csv("reports/c3_confusion_matrix.csv", index_col=0)
    assert matrix.shape == (3, 3)
    assert matrix.index.tolist() == [0, 1, 2]
    assert matrix.columns.tolist() == ["0", "1", "2"]
    assert (matrix.to_numpy() >= 0).all()
    assert matrix.to_numpy().sum() > 0

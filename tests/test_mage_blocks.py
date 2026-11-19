"""Exercise Mage block functions as ordinary Python outside Mage."""

import pytest
from sklearn.datasets import load_iris

from iris_project.data_exporters.save_results import (
    export_data,
    test_output as assert_export_output,
)
from iris_project.data_loaders.load_iris import (
    load_data,
    test_output as assert_load_output,
)
from iris_project.transformers.evaluate_model import (
    evaluate,
    test_output as assert_evaluate_output,
)
from iris_project.transformers.prepare_data import (
    test_output as assert_prepare_output,
    transform,
)
from iris_project.transformers.train_model import (
    test_accuracy as assert_accuracy,
    train,
)
from iris_project.transformers.validate_iris import (
    test_output as assert_validation_output,
    validate,
)


def test_iris_pipeline_blocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    raw_data = load_data()
    assert_load_output(raw_data)
    clean_data = validate(raw_data)
    assert_validation_output(clean_data)
    split_data = transform(clean_data)
    assert_prepare_output(split_data)
    predictions = train(split_data, max_depth=3)
    assert_accuracy(predictions)
    metrics = evaluate(predictions)
    assert_evaluate_output(metrics)
    exported = export_data(predictions)
    assert_export_output(exported)

    assert (tmp_path / "iris_model.pkl").is_file()
    assert (tmp_path / "iris_predictions.csv").is_file()


@pytest.mark.parametrize(
    ("max_depth", "should_pass"),
    [(1, False), (2, True), (3, True), (4, True), (5, True)],
)
def test_depth_accuracy_gate_controls_export(tmp_path, monkeypatch, max_depth, should_pass):
    monkeypatch.chdir(tmp_path)
    split_data = transform(load_iris(as_frame=True).frame)
    predictions = train(split_data, max_depth=max_depth)
    accuracy = (predictions["predicted"] == predictions["target"]).mean()

    if should_pass:
        assert accuracy >= 0.8
        assert_accuracy(predictions)
        export_data(predictions)
        assert (tmp_path / "iris_predictions.csv").exists()
    else:
        assert accuracy < 0.8
        with pytest.raises(AssertionError, match="below 0.8"):
            assert_accuracy(predictions)
        assert not (tmp_path / "iris_predictions.csv").exists()

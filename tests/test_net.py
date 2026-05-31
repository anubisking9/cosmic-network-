import json
import pathlib
import tempfile
import pytest

from cosmic_network import CosmicNet, load_net, save_net


def test_forward_output_shape():
    net = CosmicNet([4, 8, 3])
    out = net.forward([1.0, 0.5, -0.3, 0.8])
    assert len(out) == 3


def test_forward_softmax_sums_to_one():
    net = CosmicNet([4, 8, 3])
    out = net.forward([1.0, 0.5, -0.3, 0.8])
    assert abs(sum(out) - 1.0) < 1e-6


def test_predict_returns_valid_class():
    net = CosmicNet([4, 8, 3])
    cls = net.predict([1.0, 0.5, -0.3, 0.8])
    assert cls in (0, 1, 2)


def test_save_and_load_roundtrip():
    net = CosmicNet([4, 8, 3])
    x = [1.0, 0.5, -0.3, 0.8]
    original = net.forward(x)

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "model.json"
        save_net(net, path)
        loaded = load_net(path)

    restored = loaded.forward(x)
    assert original == pytest.approx(restored, abs=1e-9)


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_net("/nonexistent/path/model.json")


def test_single_hidden_layer():
    net = CosmicNet([2, 2])
    out = net.forward([0.0, 1.0])
    assert len(out) == 2
    assert abs(sum(out) - 1.0) < 1e-6


def test_invalid_layer_sizes():
    with pytest.raises(ValueError):
        CosmicNet([4])

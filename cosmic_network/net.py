import math
import random


class Layer:
    def __init__(self, in_size: int, out_size: int):
        limit = math.sqrt(2.0 / in_size)
        self.weights = [
            [random.gauss(0, limit) for _ in range(out_size)]
            for _ in range(in_size)
        ]
        self.biases = [0.0] * out_size

    def forward(self, x: list[float]) -> list[float]:
        out_size = len(self.biases)
        result = list(self.biases)
        for i, xi in enumerate(x):
            for j in range(out_size):
                result[j] += xi * self.weights[i][j]
        return result

    def state(self) -> dict:
        return {"weights": self.weights, "biases": self.biases}

    @classmethod
    def from_state(cls, state: dict) -> "Layer":
        layer = cls.__new__(cls)
        layer.weights = state["weights"]
        layer.biases = state["biases"]
        return layer


def _relu(x: list[float]) -> list[float]:
    return [max(0.0, v) for v in x]


def _softmax(x: list[float]) -> list[float]:
    m = max(x)
    exps = [math.exp(v - m) for v in x]
    total = sum(exps)
    return [e / total for e in exps]


class CosmicNet:
    """Feed-forward neural network with configurable layers."""

    def __init__(self, layer_sizes: list[int]):
        if len(layer_sizes) < 2:
            raise ValueError("Need at least an input and output layer")
        self.layer_sizes = list(layer_sizes)
        self.layers = [
            Layer(layer_sizes[i], layer_sizes[i + 1])
            for i in range(len(layer_sizes) - 1)
        ]

    def forward(self, x: list[float]) -> list[float]:
        for i, layer in enumerate(self.layers):
            x = layer.forward(x)
            if i < len(self.layers) - 1:
                x = _relu(x)
        return _softmax(x)

    def predict(self, x: list[float]) -> int:
        probs = self.forward(x)
        return probs.index(max(probs))

    def state(self) -> dict:
        return {
            "layer_sizes": self.layer_sizes,
            "layers": [l.state() for l in self.layers],
        }

    @classmethod
    def from_state(cls, state: dict) -> "CosmicNet":
        net = cls.__new__(cls)
        net.layer_sizes = state["layer_sizes"]
        net.layers = [Layer.from_state(s) for s in state["layers"]]
        return net

import json
import pathlib
from .net import CosmicNet


def save_net(net: CosmicNet, path: str | pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(net.state(), f, indent=2)


def load_net(path: str | pathlib.Path) -> CosmicNet:
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No network found at {path}")
    with path.open() as f:
        state = json.load(f)
    return CosmicNet.from_state(state)

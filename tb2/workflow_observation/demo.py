"""Bundled synthetic example; never accepts external events or credentials."""
from __future__ import annotations

import json
from importlib.resources import files

from .adapters import verify_source_observation
from .config import resolve_config
from .model import Model, Record, Rejection
from .projection import project_goal
from .reducer import reduce_observation


class _BundledExample:
    def __init__(self, events: list[Record]) -> None:
        self.events = events

    def source_bound(self, event: Record) -> bool:
        return event in self.events

    def contract_bound(self, event: Record) -> bool:
        return event in self.events

    def evidence_verified(self, event: Record, _reference: Record) -> bool:
        return event in self.events

    def writer_bound(self, event: Record) -> bool:
        return event in self.events

    def runtime_bound(self, event: Record) -> bool:
        return False


def demonstrate() -> Record:
    """Run the actual reducer/projector on immutable synthetic bundled events."""
    sample = json.loads(files(__package__).joinpath("contracts", "demo.json").read_text(encoding="utf-8"))
    config = resolve_config()
    model = Model(config=config)
    verifier = _BundledExample(sample["events"])
    for event in sample["events"]:
        observation = verify_source_observation(event, verifier, config)
        if isinstance(observation, Rejection):
            raise RuntimeError("BUNDLED_EXAMPLE_INVALID")
        reduce_observation(model, observation)
    return {"mode": "SYNTHETIC_DEMONSTRATION", "executesTasks": False,
            "projection": project_goal(model, sample["projectId"], sample["goalId"], sample["asOf"], "LIVE", config)}

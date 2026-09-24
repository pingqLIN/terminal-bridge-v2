"""TEST ONLY: synthetic authority seam for portable black-box conformance."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# The driver is executable from a checkout without installing tests as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tb2.workflow_observation.adapters import verify_source_observation
from tb2.workflow_observation.config import resolve_config
from tb2.workflow_observation.model import Model, Record, Rejection
from tb2.workflow_observation.projection import project_goal
from tb2.workflow_observation.reducer import reduce_observation
from tb2.workflow_observation.storage import ObservationJournal


class SyntheticVerifier:
    def __init__(self, context: Record) -> None:
        self.context = context

    def source_bound(self, _event: Record) -> bool:
        return self.context["sourceBound"] is True

    def contract_bound(self, _event: Record) -> bool:
        return self.context["contractHashVerified"] is True

    def evidence_verified(self, _event: Record, _reference: Record) -> bool:
        return self.context["evidenceVerified"] is True

    def writer_bound(self, _event: Record) -> bool:
        return self.context["writerBound"] is True

    def runtime_bound(self, _event: Record) -> bool:
        return self.context["sourceBound"] is True


def run(request: Record) -> Record:
    config = resolve_config(request["config"])
    model = Model(config=config)
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="tb2-observation-") as temporary:
        with ObservationJournal(Path(temporary), config) as journal:
            for step in request["steps"]:
                if step["op"] == "checkpoint":
                    journal.checkpoint()
                    continue
                if step["op"] == "reload":
                    model = journal.load()
                    continue
                event = step["event"]
                observation = verify_source_observation(event, SyntheticVerifier(step["testContext"]), config)
                if isinstance(observation, Rejection):
                    code = observation.code
                    model.diagnostics.append({"code": code})
                else:
                    journal.append(observation)
                    code = reduce_observation(model, observation)
                outcomes.append({"eventId": event["eventId"], "code": code})
    projection = project_goal(model, request["projectId"], request["goalId"], request["asOf"], request["sourceStatus"], config)
    return {"protocolVersion": "0.1.0", "states": dict(sorted(model.states.items())),
            "projection": projection, "outcomes": outcomes,
            "diagnostics": sorted(model.diagnostics, key=lambda row: json.dumps(row, sort_keys=True))}


if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin)), sort_keys=True))

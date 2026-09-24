"""Optional single-writer, hash-chained local observation journal.

Replay always checks the journal; a checkpoint is a checked accelerator hint,
never task authority. This detects corruption, not a malicious local writer.
Flush/fsync and replacement do not claim Windows power-loss durability.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .config import validators
from .model import Model, Record, VerifiedObservation
from .reducer import reduce_observation


def _digest(value: Record) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ObservationJournal:
    def __init__(self, directory: Path, config: Record) -> None:
        self.directory = directory
        self.config = config
        self.lock = None
        self.watermark = "0" * 64
        self.count = 0
        self.writable = True

    def __enter__(self) -> ObservationJournal:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / "writer.lock").open("a+b")
        if self.lock.tell() == 0:
            self.lock.write(b"0")
            self.lock.flush()
        self.lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            self.lock = None
            raise RuntimeError("OBSERVATION_WRITER_BUSY") from None
        try:
            self.load()
        except (OSError, RuntimeError):
            self.lock.close()
            self.lock = None
            raise
        return self

    def __exit__(self, *_args: object) -> None:
        if self.lock:
            self.lock.close()
            self.lock = None

    def append(self, observation: VerifiedObservation) -> None:
        if not self.lock or not self.writable:
            raise RuntimeError("OBSERVATION_JOURNAL_NOT_WRITABLE")
        payload = {"previous": self.watermark, "event": json.loads(observation.encoded),
                   "semanticError": observation.semantic_error}
        digest = _digest(payload)
        line = json.dumps({"payload": payload, "sha256": digest}, sort_keys=True, separators=(",", ":")) + "\n"
        with (self.directory / "events.jsonl").open("ab") as journal:
            journal.write(line.encode("utf-8"))
            journal.flush()
            os.fsync(journal.fileno())
        self.watermark = digest
        self.count += 1

    def checkpoint(self) -> None:
        if not self.lock or not self.writable:
            raise RuntimeError("OBSERVATION_JOURNAL_NOT_WRITABLE")
        payload = {"count": self.count, "watermark": self.watermark}
        temporary = self.directory / "checkpoint.next"
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump({"payload": payload, "sha256": _digest(payload)}, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.directory / "checkpoint.json")

    def load(self) -> Model:
        model = Model(config=self.config)
        self.watermark, self.count, self.writable = "0" * 64, 0, True
        path = self.directory / "events.jsonl"
        if path.exists():
            with path.open("rb") as journal:
                for line in journal:
                    if len(line) > self.config["eventMaxBytes"] + 2048:
                        raise RuntimeError("OBSERVATION_JOURNAL_CORRUPT")
                    if not line.endswith(b"\n"):
                        model.diagnostics.append({"code": "JOURNAL_TRUNCATED"})
                        self.writable = False
                        break
                    try:
                        record = json.loads(line)
                        payload = record["payload"]
                        valid = (set(record) == {"payload", "sha256"}
                                 and set(payload) == {"previous", "event", "semanticError"}
                                 and record["sha256"] == _digest(payload)
                                 and payload["previous"] == self.watermark
                                 and validators()["event"].is_valid(payload["event"])
                                 and (payload["semanticError"] is None or re.fullmatch(r"[A-Z_]{1,64}", payload["semanticError"])))
                    except (ValueError, KeyError, TypeError):
                        valid = False
                    if not valid:
                        raise RuntimeError("OBSERVATION_JOURNAL_CORRUPT")
                    reduce_observation(model, VerifiedObservation(json.dumps(payload["event"]), payload["semanticError"]))
                    self.watermark = record["sha256"]
                    self.count += 1
        checkpoint = self.directory / "checkpoint.json"
        if checkpoint.exists():
            try:
                record = json.loads(checkpoint.read_text(encoding="utf-8"))
                valid = record["sha256"] == _digest(record["payload"])
                valid = valid and record["payload"]["count"] <= self.count
                if record["payload"]["count"] == self.count:
                    valid = valid and record["payload"]["watermark"] == self.watermark
            except (ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                model.diagnostics.append({"code": "CHECKPOINT_CORRUPT"})
        return model

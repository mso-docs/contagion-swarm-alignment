import json
from datetime import datetime, timezone

from .models import Event


def utc():
    return datetime.now(timezone.utc).isoformat()


class EventRecorder:
    def __init__(self, path, run_id):
        self.file = path.open("x", encoding="utf-8")
        self.run_id, self.sequence = run_id, 0

    def emit(self, event_type, round_no=-1, **fields):
        event = {"event_id": f"{self.run_id}:{self.sequence:06d}", "run_id": self.run_id,
                 "sequence_no": self.sequence, "round": round_no,
                 "event_type": event_type, "timestamp_utc": utc(), **fields}
        event = Event(**event).model_dump(exclude_none=True)
        self.file.write(json.dumps(event, sort_keys=True) + "\n")
        self.file.flush()
        self.sequence += 1
        return event

    def close(self):
        self.file.close()


def read_events(path):
    with path.open() as stream:
        events = [json.loads(line) for line in stream]
    if [e["sequence_no"] for e in events] != list(range(len(events))):
        raise ValueError("Non-contiguous event log")
    return events

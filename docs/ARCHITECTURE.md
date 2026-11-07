# Architecture

`CLI → immutable validated config → controller → isolated Agent histories → inference adapter → JSON validation → artifact scoring + next-round graph router → append-only oracle JSONL → checksum-validated offline analysis`

The controller is the sole scheduler and router. Stable sorted IDs and serial inference eliminate within-round completion order effects. Each agent sees its own system/task/assistant history and controller-delivered neighbor messages only. Inbox metadata is assigned by the controller. Graph adjacency is immutable during a run. State is recreated per run.

`config.py` validates the protocol; `models.py` defines structured artifacts and outcomes; `agents.py` contains versioned task data/prompts; `topology.py` defines undirected graphs; `interventions.py` mutates only outbound text; `inference.py` provides mock/native/OpenAI-compatible adapters; `controller.py` runs bounded phases; `events.py` records provenance; `storage.py` handles attempts and integrity; `scoring.py` labels artifacts; `analysis.py` rebuilds metrics/figures; `cli.py` exposes commands.

Only inference.py uses HTTP, to the configured endpoint, with redirects disabled. Agents never see or select endpoints. Retries occur inside a serial semaphore and generate controller audit events. Configured call budget applies to physical HTTP chat attempts including retries. The outer wall-clock deadline includes calls and backoff. Discovery is bounded separately. Parsed artifact/message strings are at most 4,000 characters each; requested output is capped by the configured server token parameter. Live support is not guaranteed by this request alone.

Source events include invocation messages, model raw responses, parse failures, separate artifacts, generated messages, intervention originals and deliveries. They are oracle data. Manifest/checksum sealing happens after run termination; a process killed before sealing leaves a non-resumable attempt. Exclusive directory creation prevents overwrites. One writer per output tree is the supported operating mode. No claim of malicious tamper resistance.

P3 will add a separate explicit allowlist projection; it must never pass full event dictionaries into a monitor. P4 is confined to a ToyRecordStore simulator; no OS or real tool execution will be introduced.

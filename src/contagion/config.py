import hashlib
import json
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    protocol_version: Literal["1.0", "1.1"] = "1.0"
    research_question: Literal["rq1"] = "rq1"
    topology: Literal["ring", "star", "complete"] = "ring"
    agent_count: Literal[5] = 5
    rounds: int = Field(default=5, ge=1, le=5)
    seed: int = Field(default=101, ge=0)
    model: str = ""
    thinking: Literal["default", "disabled", "enabled"] = "default"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=256, ge=32, le=4096)
    intervention: Literal["none", "benign_override"] = "none"
    initial_agent_id: str = "agent_0"
    injection_round: int = Field(default=0, ge=0)
    max_model_calls: int = Field(default=30, ge=1, le=100)
    max_wall_seconds: float = Field(default=1200, gt=0, le=7200)
    request_timeout_seconds: float = Field(default=60, gt=0, le=300)
    retries: int = Field(default=2, ge=0, le=3)

    @model_validator(mode="after")
    def validate_source(self):
        if self.protocol_version == "1.0" and self.thinking != "default":
            raise ValueError("Explicit thinking control requires protocol_version 1.1")
        if self.initial_agent_id not in [f"agent_{i}" for i in range(5)]:
            raise ValueError("initial_agent_id must identify an agent")
        if self.injection_round >= self.rounds:
            raise ValueError("injection_round must precede end of run")
        return self


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load_config(path):
    data = yaml.safe_load(Path(path).read_text())
    return RunConfig(**data)


def configured_model(config, provider):
    if provider == "mock":
        return config.model_copy(update={"model": "mock-v1"})
    model = os.environ.get("CONTAGION_MODEL") or config.model
    if not model:
        raise ValueError("Set CONTAGION_MODEL to an installed model tag; run doctor first")
    return config.model_copy(update={"model": model})

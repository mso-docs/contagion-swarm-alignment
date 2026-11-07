from pydantic import BaseModel, ConfigDict, Field


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(max_length=4000)
    message: str = Field(max_length=4000)


class SamplingConfig(BaseModel):
    thinking: str = "default"
    model: str
    seed: int
    temperature: float
    max_output_tokens: int


class ModelResponse(BaseModel):
    content: str
    metadata: dict = Field(default_factory=dict)


class ScoredOutcome(BaseModel):
    run_id: str
    agent_id: str
    exposed: bool
    quoted_only: bool
    stated_agreement: bool
    adopted_instruction: bool
    legitimate_task_success: bool
    first_adoption_round: int | None
    reason_code: str


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str
    run_id: str
    sequence_no: int
    round: int
    event_type: str
    timestamp_utc: str
    agent_id: str | None = None
    sender_id: str | None = None
    receiver_id: str | None = None
    message_id: str | None = None
    parent_message_id: str | None = None
    content: str | None = None
    metadata: dict = Field(default_factory=dict)

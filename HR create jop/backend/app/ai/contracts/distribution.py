from pydantic import BaseModel, ConfigDict, Field


class DistributionPostSuggestion(BaseModel):
    """A short AI-written opener plus references to approved requirement keys."""

    model_config = ConfigDict(extra="forbid")

    opening: str = Field(min_length=1, max_length=500)
    highlighted_requirement_keys: list[str] = Field(default_factory=list, max_length=6)

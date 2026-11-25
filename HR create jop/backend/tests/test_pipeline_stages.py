"""The persisted status/stage compatibility matrix and transition graph."""

from __future__ import annotations

import itertools

import pytest

from app.services.errors import InvalidStateError
from app.services.pipeline_stage_service import (
    ALLOWED_TRANSITIONS,
    APPLICATION_STATUSES,
    PIPELINE_STAGES,
    validate_status_stage,
)

EXPECTED_STAGES = {
    "created": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "analysis_pending": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "analyzing": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "analysis_failed": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "ready_for_review": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "hold": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "advanced": {"screening", "review", "interview", "offer", "hired", "withdrawn"},
    "rejected": {"rejected"},
    "archived": {"archived"},
}


@pytest.mark.parametrize(
    ("status", "stage", "valid"),
    [
        (status, stage, stage in EXPECTED_STAGES[status])
        for status, stage in itertools.product(APPLICATION_STATUSES, PIPELINE_STAGES)
    ],
)
def test_every_status_stage_pair_is_explicitly_validated(
    status: str, stage: str, valid: bool
) -> None:
    if valid:
        validate_status_stage(status, stage)
    else:
        with pytest.raises(InvalidStateError):
            validate_status_stage(status, stage)


@pytest.mark.parametrize(
    ("from_stage", "to_stage", "allowed"),
    [
        (source, target, target in ALLOWED_TRANSITIONS[source])
        for source, target in itertools.product(PIPELINE_STAGES, repeat=2)
    ],
)
def test_every_pipeline_transition_pair_is_explicitly_allowed_or_denied(
    from_stage: str, to_stage: str, allowed: bool
) -> None:
    assert (to_stage in ALLOWED_TRANSITIONS[from_stage]) is allowed

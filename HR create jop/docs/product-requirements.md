# Product Requirements

## Product Vision

The product is an AI-powered HR Recruitment Assistant.

Its primary purpose is to help HR teams screen and prioritize candidates while keeping the HR professional in control of the final hiring decision.

The system should reduce manual CV review effort, preserve explainability, and make candidate review more efficient without allowing AI to make autonomous hiring or rejection decisions.

No candidate should be permanently deleted or made inaccessible because of an AI score.

The HR professional always has the final decision.

## Users

### HR Professional

The primary user. HR creates or uploads job descriptions, uploads candidate CVs, reviews AI analysis, filters and ranks candidates, and makes final decisions.

### Hiring Stakeholder

A possible reviewer of candidates, evaluations, or interview outcomes in later phases. This role is not required for the MVP unless explicitly approved.

### Candidate

The person applying for a job. Candidate-facing workflows such as scheduling and communication are post-MVP unless explicitly approved.

### Administrator

May manage organizations, users, permissions, and system settings in later phases. The exact administrator scope is a decision to be finalized.

## MVP Goals

The MVP focuses on:

- Job Description intake.
- Job Profile extraction.
- Candidate CV upload.
- Resume text extraction.
- Candidate Profile extraction.
- Candidate-to-Job matching.
- Matching evidence.
- Deterministic scoring.
- Candidate ranking.
- Candidate filtering and search.
- AI explanation.
- HR decision.
- Decision history.
- Basic audit trail.
- Basic AI observability and tracing.

## Functional Requirements

The system should:

1. Allow HR to create or upload a Job Description.
2. Extract a structured Job Profile from the Job Description.
3. Allow HR to upload candidate CVs.
4. Extract structured Candidate Profiles from CVs.
5. Create a Job Application connecting a Candidate to a specific Job.
6. Compare each Candidate against the requirements of the specific Job.
7. Extract explainable matching evidence.
8. Calculate a deterministic, explainable candidate score.
9. Rank and group candidates.
10. Allow HR to filter, search, review, and inspect all candidates.
11. Provide AI-generated explanations for recommendations.
12. Allow HR to make the final decision: advance, reject, or hold.
13. Record AI recommendations and HR decisions.
14. Record HR feedback and reasons where available.
15. Use historical HR decisions later to identify HR preference patterns.
16. Allow AI to suggest preference or weighting changes later, but never automatically change important business rules without HR approval.

## Non-Functional Requirements

The system should be:

- Explainable: scores and recommendations must be supported by preserved evidence.
- Testable: business-critical rules and calculations should be deterministic where possible.
- Observable: AI workflows should record enough trace data to understand outputs and failures.
- Maintainable: business logic should remain separate from AI infrastructure.
- Provider-independent: core business logic should not depend directly on one specific LLM provider.
- Safe for human decision-making: AI recommendations must never become final HR decisions automatically.
- Auditable: important recruitment events should be traceable.

## MVP Exclusions

The following are outside the MVP unless explicitly approved later:

- Full onboarding.
- Offer management.
- Advanced ATS integrations.
- LinkedIn integration.
- Advanced analytics.
- Interview transcription.
- Autonomous hiring decisions.
- Autonomous rejection decisions.
- Complex HR learning or ML personalization.
- Multi-channel communication automation.
- Interview scheduling.
- Email automation.
- Interview assistance.

## Core Domain Concepts

The important distinction is:

- Candidate is a person.
- Job is a recruitment position.
- Job Application is a specific Candidate applying to a specific Job.

Initial conceptual relationships:

```text
Organization
├── Users
└── Jobs
    └── JobApplications
        ├── Candidate
        │   └── Resume
        │       └── CandidateProfile
        ├── CandidateEvaluation
        ├── MatchEvidence
        └── HRDecision
```

Additional domain entities should not be introduced unless there is a clear requirement.

## Human-In-The-Loop Requirements

Human approval is required for important decisions.

At minimum:

- Job Profile approval:
  Raw Job Description -> AI extraction -> HR review -> Approved Job Profile.
- Candidate decision:
  AI analysis -> Score + Evidence + Recommendation -> HR review -> Final HR Decision.

Supported HR decisions:

- Advance.
- Reject.
- Hold.

The AI recommendation must never automatically become the final HR decision.

## AI Responsibilities

AI may be used for:

1. Job Description understanding and extraction.
2. Resume understanding and extraction.
3. Matching evidence extraction.
4. Candidate evaluation assistance.
5. Explanation generation.
6. Later interview assistance.
7. Later HR preference analysis.

AI outputs must be structured and validated whenever possible.

AI must not independently make the final hiring decision.

## Non-AI Responsibilities

These should be implemented as normal application services or functions unless a future requirement proves otherwise:

- Authentication.
- Authorization.
- Database access.
- File storage.
- PDF/DOCX text extraction where deterministic extraction is sufficient.
- Score calculation.
- Ranking.
- Filtering.
- Persistence.
- Audit logging.
- Email sending.
- Calendar operations.
- Business rules.
- Permission checks.

Do not create an AI agent for these responsibilities.

## Matching And Scoring

The matching pipeline should conceptually be:

```text
Candidate CV
-> Candidate Profile
-> Match Evidence
-> Deterministic Scoring Engine
-> Candidate Score
-> Explanation
```

The LLM should not simply invent a final score.

The system should preserve evidence supporting the score.

The score should be explainable and based on explicit job requirements and evaluation criteria.

The score is locked for Phase 4.2 in `backend/app/services/scoring_service.py`:
category weights `must_have=3`, `important=2`, `nice_to_have=1`; evidence values
`matched=1.0`, `partial=0.5`, `missing=0.0`; and
`Score = [sum(weight x evidence_value)] / [sum(weights of ALL approved requirements)] x 100`,
normalized to 0-100 with `SCORING_VERSION = "1.0"`. A missing must-have is a
non-penalizing review signal only: no penalty and no auto-reject. The weights
may be revisited in a later phase with explicit approval.

## Ranking

Candidates should be ranked based on the approved scoring model.

Candidates should be grouped or categorized for efficient HR review.

However:

- Low-scoring candidates must remain accessible.
- HR must be able to search and filter all candidates.
- AI must not permanently delete candidates.
- HR must be able to override the ranking.

## HR Preference Learning

HR preference learning is not autonomous model retraining in the MVP.

The system should first collect:

- AI recommendation.
- AI score.
- Matching evidence.
- HR decision.
- HR feedback or reason.

Later, the system may identify patterns such as HR frequently preferring candidates with a specific trait or experience type.

The system may suggest changes to preference or weighting rules, but HR must approve any important business-rule change.

## Future Phases

Future phases may include:

- Interview scheduling.
- Email automation.
- Interview assistance.
- Offer management.
- Onboarding.
- Advanced ATS integrations.
- LinkedIn integration.
- Advanced analytics.
- More advanced HR preference analysis.
- Multi-agent architecture where it provides measurable value.

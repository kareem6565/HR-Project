"""AI application layer.

Phase 3.2 introduced structured-output contracts and their validation helpers.
Phase 3.3 introduces a provider-independent AI provider abstraction
(app/ai/providers) and provider result types (app/ai/results.py). The layer
hosts provider-agnostic, validated data contracts and a provider interface that
is independent of any specific LLM vendor, workflow, or persistence.
"""

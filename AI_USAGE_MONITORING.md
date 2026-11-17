# HERA AI Usage Monitoring

## Data captured

Every guarded OpenAI-compatible inference attempt writes a `started` row before the request and finalizes it with success/failure, HTTP status, safe error category, provider request ID, token usage when returned, and provider-reported cost when available. The record includes feature and authenticated internal user/organization IDs when request context exists. Background processing without an authenticated user records a null user ID while still consuming global counters.

Prompts, candidate/employee content, responses, API keys, and authorization headers are not stored in this usage ledger. Provider-reported cost is nullable; missing token or cost fields remain unknown rather than being estimated. If any response reports cost greater than zero, the event is marked `cost_alert`, a persistent global breaker is enabled, and later inference is stopped.

## Shared counters

`ai_usage_counters` maintains atomic upserts for UTC minute/day windows. Keys are `global:minute`, `global:day`, and corresponding user keys. Defaults are 15 global requests/minute, 40 global requests/day, 5 per-user requests/minute, and 20 per-user requests/day. All workers use the same database. Limit rejection returns HTTP 429 and does not initiate inference or change providers/models.

## Example read-only queries

```sql
SELECT date_trunc('day', created_at) AS utc_day,
       provider, model, status, count(*) AS requests,
       sum(input_tokens) AS input_tokens,
       sum(output_tokens) AS output_tokens,
       sum(reported_cost_usd) AS reported_cost_usd
FROM ai_usage_events
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 2, 3, 4;

SELECT bucket_key, window_start, request_count, updated_at
FROM ai_usage_counters
ORDER BY bucket_key;

SELECT control_key, enabled, updated_at
FROM ai_policy_controls;
```

## Retention and operations

No automatic retention/compaction job is included. Establish an owner-approved retention period before production and archive/delete usage rows under a documented maintenance procedure. Counter rows are bounded by global buckets plus one pair of keys per active user. Do not clear `cost_alert` merely to restore service: first reconcile the provider-reported cost and account activity, then document and authorize the operator action.

Migration `027_ai_free_first` creates these tables. Apply it before backend rollout; missing tables cause guarded requests to fail closed. This task did not apply the migration to the development database or restart running containers.

const AI_ERROR_MESSAGES = {
  missing_api_key: "The OpenRouter API key is missing. No AI request was sent.",
  configuration_error: "AI is not configured. Check the provider and API key settings.",
  invalid_api_key: "OpenRouter rejected the API key. Check the key configuration.",
  provider_access_denied: "OpenRouter denied access to this model or account.",
  app_test_budget_exceeded: "The approved AI test budget would be exceeded. No request was sent.",
  provider_usage_check_failed: "OpenRouter usage could not be checked. No AI request was sent.",
  usage_baseline_mismatch: "OpenRouter usage does not match the test baseline. No request was sent.",
  ai_metering_unavailable: "AI usage tracking is unavailable. No request was sent.",
  provider_timeout: "OpenRouter took too long to respond. Try again later.",
  provider_rate_limit: "OpenRouter is rate-limiting requests. Try again shortly.",
  provider_credits_exhausted: "The OpenRouter key reached its provider spending limit.",
  provider_unavailable: "OpenRouter is temporarily unavailable. Try again shortly.",
  provider_rejected_request: "OpenRouter rejected the request. Check the model configuration.",
  invalid_structured_response: "OpenRouter replied, but the response was incomplete or could not be parsed.",
  provider_response_truncated: "OpenRouter cut off its response before finishing. Try again; if it repeats, shorten the job description.",
};

export function getAIErrorMessage(error, fallback = "The AI request failed. Try again.") {
  const data = error?.response?.data;
  const code = data?.error_code || data?.error_type;
  const message = AI_ERROR_MESSAGES[code] || data?.detail || error?.message || fallback;
  const requestId = data?.request_id || error?.response?.headers?.["x-request-id"];
  return requestId ? `${message} (Request ID: ${requestId})` : message;
}

# Self-hosted AI providers

HERA has three distinct live-provider choices:

| `AI_PROVIDER` | Protocol | Use |
| --- | --- | --- |
| `ollama` | OpenAI-compatible `/v1` | Ollama Cloud (existing setting) |
| `local` | OpenAI-compatible `/v1` | Self-hosted vLLM, LM Studio, or another compatible server |
| `ollama_local` | Native Ollama `/api/chat` | Self-hosted Ollama with per-request context size |

Set the endpoint and exact installed model name in the backend environment. HERA does not download or select models. `LOCAL_LLM_API_KEY` is optional for `local`; the Ollama native adapter does not send an API key. Docker Compose defaults to `host.docker.internal` so the backend container can reach a model server running on the Windows host; set the corresponding `*_BASE_URL` if your server runs elsewhere. When running the backend directly on the host, the default localhost URLs apply.

For native Ollama, `OLLAMA_LOCAL_NUM_CTX` defaults to 16384 tokens (valid range 2048–131072). The request sends it as `options.num_ctx`. The context window includes system instructions, job information, CV text, and response tokens, so choose a value that leaves output space beyond the combined input. A larger context needs more memory; Ollama documents that parallel requests multiply context allocation. Raise the value only after checking the host's available RAM/VRAM and the model's memory requirements.

The official `/api/chat` response reports `prompt_eval_count`, `eval_count`, `done`, and `done_reason`. HERA rejects any response whose prompt token count reaches the configured context or whose generation is incomplete, and records the failure without accepting partial output. Ollama's current documented HTTP API does not specify a tokenizer preflight route, so this validation uses the model-reported count after the call; it guarantees that a boundary/truncated response is not used as an evaluation result.

Self-hosted calls use separate configurable usage quotas (`AI_SELF_HOSTED_*`) and the existing usage-event ledger. No model pricing is assumed or looked up. External provider authorization and limits are unchanged.

## Verification state

The adapters are implemented and tested only against mocked HTTP transports. Live verification is pending an operator-provided endpoint and model. Real-hardware speed and quantization effects are unmeasured; verify them on rented GPU hardware before publishing performance claims. Quality benchmarks use synthetic CVs only.

## Paid OpenRouter benchmark proposal (not implemented)

Before any paid benchmark, add a separate explicit model-ID allow-list and an atomic monthly spend reservation with a hard cap. Emit an operator warning when reserved plus actual spend reaches 80% of the cap. Reject paid calls when the model is not allow-listed or the monthly cap cannot cover the reservation. Keep paid mode disabled by default. This proposal is not authorization to change the cost policy; obtain approval and the exact model ID first.

# LLM Provider Configuration Guide & Provider Matrix

The FireAI Agent Platform uses a **unified, env-driven ProviderRegistry** (`backend.services.providers.registry.LLMProviderRegistry`).
Adding or switching LLM providers requires **no code changes** — only setting environment variables.

---

## Provider Matrix

| Provider | Kind (`LLM_<NAME>_KIND`) | Default Model | Required Keys / Variables | Primary Use Case |
|---|---|---|---|---|
| **OpenAI** | `openai_compatible` | `gpt-4o` | `OPENAI_API_KEY` | High-reasoning chat & code generation |
| **Anthropic** | `anthropic` | `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` | Complex engineering analysis & vision |
| **Google Gemini** | `gemini` | `gemini-2.0-flash` | `GEMINI_API_KEY` | Fast multimodal reasoning & embeddings |
| **Azure OpenAI** | `azure` | *(Deployment ID)* | `AZURE_OPENAI_API_KEY`, `LLM_AZURE_BASE_URL`, `LLM_AZURE_MODEL` | Enterprise compliance & GovCloud |
| **Ollama (Local)** | `openai_compatible` | `llama3` | `QOMN_OLLAMA_HOST`, `QOMN_HEALING_MODEL` | Air-gapped Tier-2 self-healing |
| **vLLM / Groq** | `openai_compatible` | *(Configured)* | `LLM_PRIMARY_BASE_URL`, `LLM_PRIMARY_API_KEY` | High-throughput low-latency inference |
| **OpenRouter** | `openai_compatible` | `openai/gpt-4o` | `OPENROUTER_API_KEY` | Multi-model aggregation & fallback |

---

## Quick Setup: Single-Key Discovery

The platform automatically configures the primary provider when any of the following standard environment variables is set:

```bash
# Option A: OpenAI
OPENAI_API_KEY=sk-...

# Option B: Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Option C: Google Gemini
GEMINI_API_KEY=AIzaSy...
```

---

## Advanced: Multi-Provider Fallback Chain

Configure an ordered fallback chain via `LLM_PROVIDERS`:

```bash
LLM_PROVIDERS=primary,fallback,local

# Primary: Anthropic Claude
LLM_PRIMARY_KIND=anthropic
LLM_PRIMARY_API_KEY=sk-ant-...
LLM_PRIMARY_MODEL=claude-sonnet-4-5
LLM_PRIMARY_TIMEOUT=45

# Secondary fallback: OpenAI
LLM_FALLBACK_KIND=openai_compatible
LLM_FALLBACK_API_KEY=sk-...
LLM_FALLBACK_BASE_URL=https://api.openai.com/v1
LLM_FALLBACK_MODEL=gpt-4o

# Tertiary fallback: Local Ollama
LLM_LOCAL_KIND=openai_compatible
LLM_LOCAL_BASE_URL=http://localhost:11434/v1
LLM_LOCAL_MODEL=llama3
```

---

## Hot Reload

Admins can reload LLM provider configurations without restarting the server:

```http
POST /admin/llm-providers/reload
Authorization: Bearer <ADMIN_TOKEN>
```

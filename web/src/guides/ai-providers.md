# Connecting an AI model

Capital can ask a large language model for trade decisions. It supports
**Claude**, **OpenAI**, **Codex**, **DeepSeek**, **Gemini** and local **Ollama**
models. Each provider stores its own key, so several can run side by side.

## Add a provider

1. Open **Settings → AI**.
2. Pick a provider and paste its API key. For OpenAI-compatible providers
   (Codex, DeepSeek, Ollama) set the **base URL** too.
   - Ollama runs locally and needs no key — point the base URL at
     `http://localhost:11434/v1`.
3. Optionally set a **model** name; blank uses the provider default.
4. Set a **daily spend cap** so AI strategies pause once the budget is hit.

## How decisions are used

The model receives a context pack — recent prices, your position, the asset's
**news** and its **connections** — and returns *buy / sell / hold* with a
confidence.

- **Notify mode** (default, safest): the decision is surfaced on the Dashboard
  and via Telegram for you to confirm.
- **Auto mode**: the decision flows straight through the risk manager and
  executes. Opt in per strategy.

Every call is logged with its token cost under **History** and **AI models**.

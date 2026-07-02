# Research reports

Capital writes a structured research report for every **watched symbol** on a
schedule (every 12 hours by default). Each report combines what the platform
already stores — recent asset, world and economic headlines, the asset's
dependency-graph connections, and a technical snapshot — with narrative
analysis written by the configured **report writer** model.

## Report sections

- **Summary** — a balanced executive summary.
- **Technical snapshot** — price, RSI, moving averages, 24h change.
- **Possible ups / downs** — plausible upside and downside scenarios.
- **Trade routes & macro effects** — how supply chains and policy news could
  affect the asset.
- **Technology review** — the asset's technology and ecosystem trajectory.
- **Headlines & connections** — the raw inputs the narrative was written from.

## Configuring

- On **Settings → Research**, choose the watched symbols, the report interval
  and the writer model (defaults to the global AI provider).
- Admins can press **Run now** on the Research page to write a report
  immediately — for the filtered symbol, or all watched symbols.
- Report writing spends LLM tokens and respects the **daily AI spend cap**: a
  cycle stops once the cap is reached.

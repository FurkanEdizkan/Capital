# News

Capital pulls free, public RSS feeds once a day and tags each headline with the
asset it mentions (e.g. *Bitcoin* → `BTCUSDT`).

## Using it

- The **News** page shows the latest headlines. Type a symbol to filter to one
  asset's coverage.
- Admins can press **Refresh** to fetch immediately instead of waiting for the
  daily run.
- Per-asset headlines are also folded into the **AI decision prompt**, so the
  model sees the same context you do.

## Changing the feeds

The default sources cover crypto and general markets. To customise them, set the
`news_feeds` setting to a JSON array of `{ name, url, category, symbol? }`
objects. A broken feed is skipped — it never blocks the others.

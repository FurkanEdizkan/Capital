# Connections

The connections graph maps how assets relate to the products and concepts
around them — a *GPU chip* connects to **NVIDIA** and **AMD**; **USDT** is
*pegged to* the **US Dollar**.

## Why it matters

When an AI strategy evaluates an asset, the asset's neighbours are added to its
decision prompt. So a signal on `NVDA` can take *AI compute* demand into
account, and a `USDT` signal knows it tracks the dollar.

## Curating the graph

- Capital ships a curated seed of nodes and edges.
- Select a node and press **AI-suggest connections** to have the configured
  model propose related entities. Suggestions appear as **dashed** edges,
  pending your review.
- **Approve** a suggestion to add it to the graph, or **delete** it to reject.

Only approved edges feed the AI prompt.

"""Connections — a graph linking products and concepts to tradeable assets.

Nodes are assets (``NVDA``, ``USDT``), products (``GPU chip``) or concepts
(``stablecoin``); edges relate them (a chip *supplies* NVDA and AMD; USDT is
*pegged_to* USD). The graph ships with a curated seed and can be extended by
asking the configured LLM to *suggest* connections for a node (stored
unapproved until an operator approves them). AI strategies fold a symbol's
neighbours into their decision prompt.
"""

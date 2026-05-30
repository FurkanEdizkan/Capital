"""News — daily-refreshed world and per-asset headlines from free RSS feeds.

The engine pulls a small set of public RSS feeds on a daily schedule (and on
demand), stores deduplicated headlines, and tags each with an asset symbol
when one is recognised. AI strategies fold recent per-symbol headlines into
their decision prompt; the News page surfaces them to the operator.
"""

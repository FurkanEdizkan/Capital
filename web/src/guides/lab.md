# Strategy Lab

The Lab answers two questions with real backtests over recent data:

- **By coin** — pick a coin and see what every strategy type could have
  gained on it, with the risk (max drawdown, Sharpe, win rate) alongside.
- **By strategy** — pick a strategy type and see which coins it performs
  best on.

## The AI pick

On the *By coin* pivot, **Ask AI for a pick** sends the strategy catalogue
(and the coin's latest research summary, when one exists) to your configured
AI model. Its recommendation — type *and* parameters — is backtested over the
same range so it ranks honestly against the standard rows. The call counts
against the daily AI spend cap.

## Applying a winner

**Apply** on any row creates a real strategy instance with those exact
parameters and a $10,000 allocation. New instances trade in the current
trading mode (Sim by default — simulated fills against live prices) and are
managed from the **Strategies** page, where you can also resize, cap losses,
or delete them.

Backtests model slippage and fees, but past performance is still not a
promise — treat the grid as a comparison tool, not a guarantee.

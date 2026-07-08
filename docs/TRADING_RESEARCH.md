# QuackQuant day-trading research guide

> **Educational research only.** This document is not personalized investment advice, a promise
> of returns, or a recommendation to trade. Day trading can produce rapid and substantial losses,
> especially with leverage. Use money you can afford to lose, understand your broker's rules, and
> consider speaking with a qualified financial professional before risking capital.

## Start by changing the objective

“Make at least 3% every day” is not a workable strategy requirement. It is a return target without
a model of risk. If 3% compounded across 252 trading days with no losing day, one dollar would grow
to roughly $1,718—about a **171,700% annual return** before fees, spreads, slippage, taxes, and
withdrawals. Trying to force that result encourages leverage, oversized positions, and trading when
no valid setup exists.

A useful research objective is instead:

> Find a precisely defined setup with positive out-of-sample expectancy after realistic costs,
> bounded drawdowns, enough independent observations, and behavior that can be executed as tested.

Judge the process over a statistically meaningful sample, not by whether each day is green. “No
trade” is a valid daily outcome. The SEC's investor education material emphasizes that day trading
is fast, speculative, and capable of producing losses greater than the initial investment when
leverage is used ([Investor.gov: day-trading risks](https://www.investor.gov/additional-resources/spotlight/formerdirectorlorischock-directors-take/thinking-day-trading-know-risks)).

## One stock or many?

Use a **small, liquid universe**, then trade only the few symbols that meet a prewritten setup.

- Researching one stock alone risks fitting rules to that company's particular history.
- Watching hundreds manually creates noise, inconsistent decisions, and temptation to chase.
- Testing the same rules across multiple liquid symbols shows whether the idea generalizes.
- During manual training, one broad-market ETF plus a few highly liquid large-cap stocks is enough
  to learn execution. A scanner can later evaluate a wider universe consistently.

The scanner should filter before it ranks. Example research filters—not trade recommendations—are:

- minimum price and median daily dollar volume;
- maximum quoted spread in basis points;
- no stale or missing bars;
- known corporate actions handled correctly;
- optional exclusion of scheduled earnings until event risk is explicitly modeled.

Keep the eligible universe historically accurate. Testing today's successful stocks over old data
creates survivorship bias. Point-in-time universe membership and delisted securities matter.

## What backtesting means

A backtest replays an exact trading algorithm over historical data to estimate how it would have
behaved. It is an experiment, not a time machine and not proof of future profitability. Hypothetical
results can misrepresent fills and a trader's ability to withstand losses, as the CFTC explains in
its discussion of simulated trading systems
([CFTC: hypothetical performance limitations](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/fraudadv_tradingsystem.html)).

Every backtest needs an unambiguous specification:

1. **Universe:** what could have been traded at each historical timestamp?
2. **Data:** trades, quotes, or bars; timezone; session; adjustments; missing-data rules.
3. **Signal:** information available at that moment, with no future-bar leakage.
4. **Entry:** market, limit, or stop order; submission time; cancellation and partial-fill rules.
5. **Sizing:** formula based only on capital and information available then.
6. **Exit:** invalidation, target, trailing rule, time stop, and end-of-day behavior.
7. **Costs:** bid/ask spread, commission, regulatory fees, slippage, market impact, and borrow.
8. **Constraints:** buying power, halts, short availability, latency, and concurrent positions.

### Minimum validation workflow

Split data chronologically—never randomly:

- **Development set:** form and debug the hypothesis.
- **Validation set:** choose among a small number of predefined variants.
- **Locked test set:** evaluate once after rules are frozen.
- **Walk-forward evaluation:** repeatedly train/tune on the past and test on the next untouched
  period to observe changing market regimes.
- **Paper forward test:** run unchanged rules on live data without real capital.

Track at least trade count, net expectancy, win rate, average win/loss, profit factor, maximum
drawdown, drawdown duration, turnover, exposure, slippage sensitivity, and results by symbol and
market regime. Win rate alone is nearly useless: a strategy can win often and still lose money.

For net expectancy per trade:

```text
expectancy = (win_probability × average_win)
           - (loss_probability × average_loss)
           - average_total_cost
```

Stress the result by worsening fills, increasing costs, delaying entry, varying parameters around
the chosen values, removing the best few trades, and resampling the trade sequence. A plausible edge
should degrade gradually rather than disappear when one parameter moves by a tick.

## A liquidity-sweep hypothesis

“Liquidity sweep” is market vocabulary, not yet an algorithm. It commonly describes price trading
beyond an obvious prior high or low and then returning through that level. A chart can make this
look obvious after the fact; the research task is to define it without future knowledge.

One **research hypothesis** could be:

```text
Reference level:
    highest high or lowest low of the previous N completed bars

Sweep:
    price crosses the level by between A and B basis points (or ATR fractions)

Reclaim:
    a completed bar closes back inside the level within M bars

Context filters:
    time of day, relative volume, spread, market trend, and distance from VWAP

Entry:
    next executable quote after the reclaim—not the reclaim bar's idealized close

Invalidation:
    a predefined distance beyond the sweep extreme

Exit:
    fixed rule based on risk units, time, opposing level, or end of session
```

Then test both long and short cases, different symbols, years, volatility regimes, and the complete
set of occurrences. Do not keep adding filters until the past looks pretty. Compare it with simple
baselines such as random entries matched by time and volatility, or a basic opening-range rule.

Liquidity sweeps are worth testing, but should not be assumed to reveal hidden institutional intent.
Treat the pattern as a falsifiable price-action feature. Require evidence that its net results are
stable outside the data used to invent it.

## A strategy to begin researching

Begin with **one setup, one timeframe family, and paper-only execution**. A reasonable first research
project is a liquidity-sweep-and-reclaim setup on a small universe of liquid equities, conditioned
on spread, relative volume, time of day, and broad-market regime. This recommendation is about
experimental simplicity—not a claim that the setup is profitable.

Why this is a useful first project:

- The event can be translated into deterministic rules.
- It has clear invalidation and bounded holding time.
- Its assumptions can be challenged across many symbols and regimes.
- QuackQuant can log every candidate, including signals it rejects.

Do not mix five setups into one initial result. If mean reversion, breakout, news, and sweep logic
all trade together, it becomes difficult to identify which hypothesis helped or failed.

## Training plan

### Stage 1 — mechanics and observation

- Learn order types, spread, slippage, partial fills, halts, settlement, margin, and short-borrow
  constraints.
- Pick a fixed session and annotate examples without trading.
- Write the setup in plain language, then rewrite every subjective word as a measurable rule.
- Record all candidates rather than saving only attractive screenshots.

### Stage 2 — code and backtest

- Build data-quality checks before strategy logic.
- Generate signals with completed information only.
- Simulate orders separately from signals so fills can be made more conservative.
- Store strategy, data, code, and cost-model versions with every run.
- Reject the hypothesis if results depend on unrealistic fills or one symbol/month.

### Stage 3 — live paper trading

- Freeze the rules before starting.
- Paper trade through different regimes and compare every fill with the model.
- Log missed trades, overrides, errors, and scanner downtime.
- Treat paper execution as systems validation; it cannot fully reproduce real queue position,
  slippage, liquidity, or emotional pressure.

### Stage 4 — readiness review

Before considering real capital, require all of the following:

- positive out-of-sample results after conservative costs;
- enough independent trades to estimate uncertainty rather than relying on a short streak;
- acceptable drawdown under stressed assumptions;
- a long enough forward-paper period to include difficult conditions;
- written entry, exit, sizing, daily stop, and kill-switch rules;
- verified broker, tax, margin, and regulatory requirements;
- monitoring and reconciliation that fail closed when data or broker state is uncertain.

If those conditions are not met, continue researching or stop. There is no deadline that turns a
weak edge into a strong one.

## Risk framework for research

Define risk before projected return:

- Set a maximum loss per trade, per symbol, and per day as small fractions of research capital.
- Size from the distance to invalidation; never move the stop farther away to preserve a position.
- Cap concurrent correlated exposure; five technology stocks are not five independent trades.
- Stop automatically on stale data, rejected orders, reconciliation mismatches, or breached limits.
- Keep strategy code unable to bypass the independent risk layer.
- Start without leverage and avoid options/leveraged products while validating the basic edge.

QuackQuant should calculate candidate sizing and reject anything beyond configured limits. The user
should not be able to convert research mode into live mode with a single API flag.

## Models, charts, and agent-assisted execution

Separate the system into three layers:

1. **Deterministic trading engine:** computes features, signals, risk, and orders from market data.
2. **AI assistant layer:** explains context, summarizes evidence, watches logs, and proposes actions.
3. **Broker execution layer:** submits paper or live orders only after independent risk checks pass.

Do not let a language model be the source of truth for prices, positions, buying power, stops, or
order state. The model can reason about a structured snapshot, but the backend must build that
snapshot from verified data and broker APIs.

### Recommended model stack

Use different models for different jobs rather than one giant model everywhere:

- **Rules-first models:** most “modeling” should start with deterministic features and classical
  statistics: liquidity-sweep features, VWAP distance, ATR, spread, relative volume, opening range,
  trend regime, and time-of-day buckets. These are inspectable and backtestable.
- **Baseline ML models:** after the rules engine works, try logistic regression, gradient-boosted
  trees, or random forests for classification such as “does this setup reach 1R before -1R?” Keep
  chronological validation and feature-importance audits. Do not start with deep learning.
- **Time-series/deep models:** only consider LSTMs, temporal convolution, or transformer-style
  models after you have lots of clean, point-in-time data and strong baselines. Intraday financial
  data is noisy enough that complex models often overfit beautifully and trade terribly.
- **LLM agent model:** use a strong reasoning model for research review, journal analysis, and
  deciding whether a candidate setup matches the written playbook. OpenAI currently recommends
  GPT-5.5 for complex reasoning/coding and GPT-5.4 mini or nano for lower-latency/cost work
  ([OpenAI models](https://developers.openai.com/api/docs/models)).
- **Structured-output model calls:** when an agent proposes an action, require JSON that matches a
  strict schema: `observe`, `explain`, `paper_order_request`, or `no_trade`. OpenAI's Structured
  Outputs support schema-constrained responses, which is useful for keeping agent output machine
  checkable ([OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)).

A good first setup is:

```text
scanner/features: deterministic Python
candidate ranking: rules + simple logistic regression or gradient-boosted tree
agent commentary: GPT-5.4 mini for intraday summaries
post-market review: GPT-5.5
execution: broker adapter + independent risk engine, not the LLM
```

### Connecting charts to price action

For your own web app, use a browser chart library and feed it from your FastAPI backend:

```text
market-data provider websocket
        ↓
backend market data service
        ↓
normalize bars, quotes, trades, and snapshots
        ↓
store recent data in memory/Redis and historical data in Postgres/Parquet
        ↓
frontend websocket: /api/v1/market/stream
        ↓
chart renders candles, VWAP, levels, sweeps, signals, and order markers
```

For the frontend chart, start with **TradingView Lightweight Charts** if you want an embeddable
charting component in your own app. TradingView describes it as an easy-to-integrate, small chart
library for financial interfaces ([TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/)).
Use the TradingView widget only if you want copy-paste charts; use Lightweight Charts if you need
your own overlays, signal markers, and data feed.

Backend chart endpoints to add later:

- `GET /api/v1/market/candles/{symbol}` — historical OHLCV bars.
- `GET /api/v1/market/snapshot/{symbol}` — latest quote, trade, spread, halt/status, and session.
- `WS /api/v1/market/stream` — live bars/quotes/signals for selected symbols.
- `GET /api/v1/market/levels/{symbol}` — prior highs/lows, opening range, VWAP bands, sweep levels.
- `GET /api/v1/strategies/{id}/signals/live` — current candidates and rejected candidates.
- `GET /api/v1/orders/markers` — fills, canceled orders, stops, and targets for chart overlays.

### Data and broker connections

For a first paper-trading integration, Alpaca is developer-friendly because its docs include Trading
API resources for accounts, assets, orders, positions, paper trading, websocket streaming, and
market data ([Alpaca Trading API](https://docs.alpaca.markets/us/docs/trading-api)). Keep market
data and broker execution behind server-side credentials; never expose broker keys in the browser.

Possible provider path:

- **Phase 1:** delayed or sandbox data for UI development.
- **Phase 2:** paid real-time equity data feed for paper trading and accurate spreads.
- **Phase 3:** paper broker integration only.
- **Phase 4:** live broker integration only after the full readiness review in this document.

Interactive Brokers is another serious option, especially for broader asset coverage, but its API
surface and account/session management are heavier. For QuackQuant's first build, start with the
simplest paper-trading stack, then abstract the broker interface so another provider can be added
later.

### Agent trading permissions

Use agent modes that must be promoted deliberately:

```text
observe-only:
    agent can summarize price action and explain signals

paper-suggest:
    agent can propose a paper order, but backend risk engine decides whether it is valid

paper-execute:
    backend may place paper orders after risk checks; agent cannot bypass limits

live-suggest:
    agent can prepare a live order ticket, but a human must approve it

live-execute:
    disabled until there is a long paper-forward record, broker review, audit logging,
    reconciliation, kill switches, and written acceptance of risk
```

The execution pipeline should be:

```text
market event
  → deterministic strategy signal
  → risk engine validates size, stop, liquidity, exposure, daily loss, stale data
  → agent may add explanation or reject if playbook mismatch
  → order preview
  → paper order or human-approved live order
  → broker confirmation
  → reconciliation loop verifies positions/fills/cash
  → chart and audit log update
```

Hard rule: if broker state and QuackQuant state disagree, fail closed and place no new orders.

## Current U.S. margin-rule note

FINRA's new intraday margin requirements became effective on **June 4, 2026**, with an allowed firm
transition period through **October 20, 2027**. During this period, a broker may still use the older
pattern-day-trader framework or may have moved to the new risk-based framework. Broker requirements
can also be stricter. Confirm the rules and effective implementation directly with the broker before
trading
([Investor.gov margin bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/margin),
[FINRA margin overview](https://www.finra.org/rules-guidance/key-topics/margin-accounts)).

## QuackQuant implementation checklist

The first backtesting milestone should implement:

- [ ] point-in-time universe and versioned historical data;
- [ ] deterministic liquidity-sweep feature generation;
- [ ] separate signal, portfolio, risk, order, and fill components;
- [ ] conservative transaction-cost and slippage model;
- [ ] market-data adapter with websocket reconnects, stale-data detection, and quote validation;
- [ ] chart feed that can render candles, levels, signals, order previews, fills, and rejected
      candidates;
- [ ] agent decision schema with strict structured outputs and no direct broker credentials;
- [ ] independent risk engine that can reject any agent or strategy order request;
- [ ] paper broker adapter before any live broker capability;
- [ ] chronological development/validation/test partitions;
- [ ] walk-forward runner and parameter-sensitivity report;
- [ ] per-trade audit log with the exact data available at decision time;
- [ ] benchmark comparison and regime/symbol breakdown;
- [ ] paper-trading adapter with no live-order capability;
- [ ] immutable result artifacts and reproducible configuration hashes.

The first success criterion is not “3% today.” It is: **the system can run the same frozen experiment
twice, explain every decision, account for realistic costs, and produce identical results.**

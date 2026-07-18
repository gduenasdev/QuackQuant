# QuackQuant Stock Monitor

This monitor is a paper-only setup scanner. It prints possible trade setups with entry, stop,
targets, confidence, and reasons. It never places trades.

By default, it also records paper trade calls to:

```text
backend/tests/stock_monitor_journal.csv
```

## Market Hours

Regular U.S. equity market hours are 9:30am to 4:00pm Eastern Time, Monday through Friday.
If the current date is Friday, July 17, 2026, then Saturday, July 18, 2026 is not a regular
market day. The next regular session is Monday, July 20, 2026, unless an exchange announces a
special closure.

## What The Scanner Looks For

The scanner combines several signals:

- The Strat: candle scenarios `1`, `2U`, `2D`, `3`
- The Strat actionable patterns: `2-1-2`, `3-1-2`, `1-2-2`, `2-2`
- Timeframe continuity: last three checkpoint candles aligned up or down
- FVG: bullish and bearish fair value gaps
- Liquidity sweep plus CHOCH confirmation
- 30m or 60m high/low breaks
- EMA trend alignment
- Volume confirmation
- Fixed percentage stop and targets

## First Run

From the backend folder:

```bash
cd backend
python tests/test_stock_monitor_strategy.py --help
```

Run a 30-minute scanner:

```bash
python tests/test_stock_monitor_strategy.py \
  --symbols SPY,QQQ,AAPL,NVDA,MSFT,TSLA \
  --checkpoint-minutes 30 \
  --poll-seconds 300
```

This will print scanner output and update the paper journal every poll.

Run a 60-minute scanner:

```bash
python tests/test_stock_monitor_strategy.py \
  --symbols SPY,QQQ,AAPL,NVDA,MSFT,TSLA \
  --checkpoint-minutes 60 \
  --poll-seconds 300
```

Run once:

```bash
python tests/test_stock_monitor_strategy.py \
  --symbols SPY,QQQ,AAPL,NVDA \
  --checkpoint-minutes 30 \
  --once
```

Run without writing the journal:

```bash
python tests/test_stock_monitor_strategy.py \
  --symbols SPY,QQQ \
  --checkpoint-minutes 30 \
  --no-journal
```

## Watchlist File

Create a local text file with one symbol per line:

```text
SPY
QQQ
AAPL
NVDA
MSFT
TSLA
META
AMZN
```

Then run:

```bash
python tests/test_stock_monitor_strategy.py \
  --watchlist watchlist.txt \
  --checkpoint-minutes 30
```

## Environment Knobs

Default risk/target settings:

```bash
QUACKQUANT_RISK_PCT=0.15
QUACKQUANT_TARGET_1_PCT=0.30
QUACKQUANT_TARGET_2_PCT=0.45
QUACKQUANT_ZONE_WIDTH_PCT=0.03
QUACKQUANT_BREAKOUT_BUFFER_PCT=0.02
```

Example:

```bash
QUACKQUANT_RISK_PCT=0.15 \
QUACKQUANT_TARGET_1_PCT=0.30 \
QUACKQUANT_TARGET_2_PCT=0.45 \
python tests/test_stock_monitor_strategy.py --symbols SPY,QQQ --checkpoint-minutes 30
```

## How To Read Output

Example shape:

```text
SPY $501.20 LONG breakout score=85 grade=A entry=501.20 stop=500.45 t1=502.70 t2=503.45
```

Fields:

- `LONG`: bullish setup
- `SHORT`: bearish setup
- `WAIT`: no trade
- `score`: confidence from 0 to 100
- `grade=A`: strongest scanner grade
- `entry`: paper entry price
- `stop`: invalidation price
- `t1`: first target
- `t2`: second target

Useful grades:

- `A`: best scanner setup, still not a guarantee
- `B`: possible setup, needs discretion
- `WATCH`: context is forming, do not force it
- `NO_TRADE`: skip

## Paper Journal

The scanner records `LONG` and `SHORT` calls to CSV. It does not record `WAIT` rows.

Each journal row includes:

- signal time
- symbol
- side
- setup
- grade
- confidence score
- entry
- stop
- target 1
- target 2
- latest price checked
- status
- result percentage
- signal reasons

Statuses:

- `OPEN`: target or stop has not been hit yet
- `TARGET_1`: price reached the first target
- `TARGET_2`: price reached the second target
- `STOPPED`: price reached the stop

Show journal stats:

```bash
python tests/test_stock_monitor_strategy.py --journal-summary
```

Use a custom journal file:

```bash
python tests/test_stock_monitor_strategy.py \
  --symbols SPY,QQQ \
  --checkpoint-minutes 30 \
  --journal paper_logs/monday.csv
```

The script has a 60-minute same-symbol/same-side cooldown so one setup is not counted repeatedly
while it stays visible on the chart.

## First-Day Rules

For the first live morning, keep it boring:

- Do not trade the first 15 minutes.
- Start with `SPY` and `QQQ` only.
- Use the scanner as an alert tool, not an autopilot.
- Only consider `A` setups.
- Require confluence: Strat signal plus either FVG or liquidity sweep/CHOCH.
- Skip all `WAIT`, `WATCH`, and `NO_TRADE` outputs.
- Do not take more than 2 trades.
- Stop after 2 losses.
- Do not average down.
- Do not trade options on the first test day unless you are paper trading.

## Options vs Shares

For a first day, shares are safer for learning execution. Options add leverage, spread, theta decay,
expiration risk, and implied-volatility risk. A good chart setup can still lose money in options if the
move is too slow or the contract is poorly chosen.

Suggested progression:

```text
1. Paper trade scanner signals.
2. Trade shares only with tiny size.
3. Log at least 20-50 setups.
4. Add swing options only after the setup stats are positive.
5. Day-trade options only after execution is consistent.
```

## Pre-Market Checklist

Before the open:

- Check whether today is a regular market day.
- Check major economic events.
- Pick 2-6 liquid symbols.
- Mark yesterday high/low and premarket high/low in your charting tool.
- Decide max loss before starting.
- Start the scanner by 9:25am ET.

After the open:

- Wait until at least 9:45am ET.
- Watch `SPY` and `QQQ` first.
- Prefer trades aligned with the market direction.
- If the scanner prints conflicting long and short ideas, stand down.

After the session:

- Save screenshots of every setup you considered.
- Review `stock_monitor_journal.csv`.
- Compare the journal against chart screenshots.
- Do not change the rules mid-session.

## Important Limits

This scanner uses Yahoo endpoints for quick experimentation. For serious trading, use a licensed
market-data provider or broker API. Delayed, missing, or incorrect data can make signals wrong.

This is educational tooling, not financial advice.

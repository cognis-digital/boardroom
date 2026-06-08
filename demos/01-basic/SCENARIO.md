# Demo: monthly investor update for a seed-stage SaaS

You're the founder of **Northwind Analytics**, a seed-stage B2B SaaS. It's the
end of March 2026 and your investors expect their monthly update. You track a
handful of KPIs in a spreadsheet and export the last three months to JSON.

BOARDROOM turns that raw metrics file into:

- a KPI table with month-over-month deltas and trend health,
- derived headline numbers (ARR, runway, growth CAGR, ARPA), and
- an auto-drafted investor one-pager in Markdown.

## Run it

KPI table (human-readable):

```
python -m boardroom report demos/01-basic/metrics.json
```

Machine-readable KPI summary:

```
python -m boardroom report demos/01-basic/metrics.json --format json
```

The investor one-pager (paste straight into your update email):

```
python -m boardroom report demos/01-basic/metrics.json --markdown
```

## What to look for

- **MRR** grew 18.5% and **net_burn** fell — both land in *Highlights*.
- **churn_rate** ticked up — `lower_is_better`, so it lands in *Lowlights*.
- **Runway** is derived from `cash / net_burn` and flagged OK / watch / critical.
- **ARR** = MRR x 12; **ARPA** = MRR / customers; growth shown as per-period CAGR.

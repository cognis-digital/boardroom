"""Core engine for BOARDROOM.

The input is a JSON document describing a company and a chronological list of
monthly periods, each carrying a flat dict of metric_name -> number.

Example::

    {
      "company": "Acme",
      "currency": "USD",
      "periods": [
        {"label": "2026-01", "metrics": {"mrr": 42000, "cash": 600000,
                                          "net_burn": 55000, "customers": 120}},
        ...
      ]
    }

Known metric keys get special treatment (MRR -> ARR, cash + net_burn ->
runway). Everything else is reported generically with month-over-month deltas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Metrics where "down is good" so trend arrows / health flip.
LOWER_IS_BETTER = {"net_burn", "burn", "churn", "churn_rate", "cac"}


class BoardroomError(Exception):
    """Raised on invalid input. CLI maps this to a non-zero exit."""


@dataclass
class Period:
    label: str
    metrics: Dict[str, float]


@dataclass
class Metric:
    name: str
    current: float
    previous: Optional[float]
    change_abs: Optional[float]
    change_pct: Optional[float]
    lower_is_better: bool

    @property
    def direction(self) -> str:
        if self.change_abs is None or self.change_abs == 0:
            return "flat"
        return "up" if self.change_abs > 0 else "down"

    @property
    def healthy(self) -> Optional[bool]:
        """True if the move is good for the business, None if no prior period."""
        if self.change_abs is None or self.change_abs == 0:
            return None
        improving = self.change_abs > 0
        if self.lower_is_better:
            improving = not improving
        return improving

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current": self.current,
            "previous": self.previous,
            "change_abs": self.change_abs,
            "change_pct": self.change_pct,
            "direction": self.direction,
            "healthy": self.healthy,
        }


@dataclass
class Report:
    company: str
    currency: str
    period_label: str
    prior_label: Optional[str]
    metrics: List[Metric]
    derived: Dict[str, Any] = field(default_factory=dict)
    highlights: List[str] = field(default_factory=list)
    lowlights: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "currency": self.currency,
            "period": self.period_label,
            "prior_period": self.prior_label,
            "metrics": [m.to_dict() for m in self.metrics],
            "derived": self.derived,
            "highlights": self.highlights,
            "lowlights": self.lowlights,
        }


def pct_change(current: float, previous: Optional[float]) -> Optional[float]:
    """Percent change, rounded to 1dp. None if no/zero base."""
    if previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100.0, 1)


def cagr(first: float, last: float, periods: int) -> Optional[float]:
    """Compound growth rate per period (%), rounded to 1dp.

    `periods` is the number of intervals between first and last.
    """
    if periods <= 0 or first <= 0 or last <= 0:
        return None
    rate = (last / first) ** (1.0 / periods) - 1.0
    return round(rate * 100.0, 1)


def runway_months(cash: Optional[float], net_burn: Optional[float]) -> Optional[float]:
    """Months of runway. None if not burning (burn <= 0) or missing data."""
    if cash is None or net_burn is None or net_burn <= 0:
        return None
    return round(cash / net_burn, 1)


def parse_metrics(data: Any) -> Dict[str, Any]:
    """Validate and normalize the raw parsed-JSON document."""
    if not isinstance(data, dict):
        raise BoardroomError("top-level JSON must be an object")
    periods_raw = data.get("periods")
    if not isinstance(periods_raw, list) or not periods_raw:
        raise BoardroomError("'periods' must be a non-empty list")

    periods: List[Period] = []
    for i, p in enumerate(periods_raw):
        if not isinstance(p, dict):
            raise BoardroomError(f"period #{i} must be an object")
        label = p.get("label")
        if not isinstance(label, str) or not label.strip():
            raise BoardroomError(f"period #{i} missing string 'label'")
        metrics_raw = p.get("metrics")
        if not isinstance(metrics_raw, dict) or not metrics_raw:
            raise BoardroomError(f"period '{label}' missing non-empty 'metrics'")
        metrics: Dict[str, float] = {}
        for k, v in metrics_raw.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise BoardroomError(
                    f"metric '{k}' in period '{label}' must be a number"
                )
            metrics[k] = float(v)
        periods.append(Period(label=label.strip(), metrics=metrics))

    return {
        "company": str(data.get("company", "Company")),
        "currency": str(data.get("currency", "USD")),
        "periods": periods,
    }


def _fmt_num(value: float, currency: str, name: str) -> str:
    """Human formatting: currency for money-like names, plain otherwise."""
    money_like = any(
        tok in name.lower()
        for tok in ("mrr", "arr", "revenue", "cash", "burn", "cac", "ltv")
    )
    if value == int(value):
        body = f"{int(value):,}"
    else:
        body = f"{value:,.2f}"
    return f"{currency} {body}" if money_like else body


def build_report(doc: Dict[str, Any]) -> Report:
    """Compute the full report from a normalized document."""
    periods: List[Period] = doc["periods"]
    currency: str = doc["currency"]
    latest = periods[-1]
    prior = periods[-2] if len(periods) >= 2 else None

    metrics: List[Metric] = []
    for name in sorted(latest.metrics):
        cur = latest.metrics[name]
        prev = prior.metrics.get(name) if prior else None
        change_abs = None if prev is None else round(cur - prev, 4)
        metrics.append(
            Metric(
                name=name,
                current=cur,
                previous=prev,
                change_abs=change_abs,
                change_pct=pct_change(cur, prev),
                lower_is_better=name.lower() in LOWER_IS_BETTER,
            )
        )

    derived = _derive(periods, latest, currency)
    highlights, lowlights = _narrate(metrics, currency)

    return Report(
        company=doc["company"],
        currency=currency,
        period_label=latest.label,
        prior_label=prior.label if prior else None,
        metrics=metrics,
        derived=derived,
        highlights=highlights,
        lowlights=lowlights,
    )


def _derive(periods: List[Period], latest: Period, currency: str) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    m = latest.metrics

    if "mrr" in m:
        derived["arr"] = round(m["mrr"] * 12.0, 2)

    cash = m.get("cash")
    burn = m.get("net_burn", m.get("burn"))
    rw = runway_months(cash, burn)
    if rw is not None:
        derived["runway_months"] = rw
        derived["runway_flag"] = (
            "critical" if rw < 6 else "watch" if rw < 12 else "ok"
        )

    # Trailing CAGR per period on the headline growth metric.
    for key in ("mrr", "arr", "revenue", "customers"):
        series = [p.metrics[key] for p in periods if key in p.metrics]
        if len(series) >= 2:
            g = cagr(series[0], series[-1], len(series) - 1)
            if g is not None:
                derived[f"{key}_cagr_per_period_pct"] = g
            break

    if "customers" in m and m.get("customers"):
        if "mrr" in m:
            derived["arpa"] = round(m["mrr"] / m["customers"], 2)

    return derived


def _narrate(metrics: List[Metric], currency: str) -> tuple[List[str], List[str]]:
    highlights: List[str] = []
    lowlights: List[str] = []
    for met in metrics:
        if met.healthy is None or met.change_pct is None:
            continue
        pct = met.change_pct
        line = (
            f"{met.name}: {_fmt_num(met.current, currency, met.name)} "
            f"({'+' if pct >= 0 else ''}{pct}% vs prior)"
        )
        if met.healthy:
            highlights.append(line)
        else:
            lowlights.append(line)
    # Most material moves first.
    highlights.sort(key=lambda s: _abs_pct(s), reverse=True)
    lowlights.sort(key=lambda s: _abs_pct(s), reverse=True)
    return highlights, lowlights


def _abs_pct(line: str) -> float:
    try:
        frag = line.split("(")[-1].split("%")[0].replace("+", "")
        return abs(float(frag))
    except (ValueError, IndexError):
        return 0.0


def render_markdown(report: Report) -> str:
    """Render the investor-update one-pager as Markdown."""
    cur = report.currency
    lines: List[str] = []
    lines.append(f"# {report.company} - Investor Update ({report.period_label})")
    lines.append("")
    if report.prior_label:
        lines.append(f"_Comparing {report.period_label} vs {report.prior_label}._")
    else:
        lines.append("_First reported period; no prior comparison available._")
    lines.append("")

    # Derived headline block.
    d = report.derived
    if d:
        lines.append("## Headline")
        lines.append("")
        if "arr" in d:
            lines.append(f"- **ARR:** {_fmt_num(d['arr'], cur, 'arr')}")
        if "runway_months" in d:
            flag = d.get("runway_flag", "")
            lines.append(
                f"- **Runway:** {d['runway_months']} months "
                f"({flag.upper()})"
            )
        for k, v in d.items():
            if k.endswith("_cagr_per_period_pct"):
                base = k[: -len("_cagr_per_period_pct")]
                lines.append(f"- **{base.upper()} growth:** {v}% per period (CAGR)")
        if "arpa" in d:
            lines.append(f"- **ARPA:** {_fmt_num(d['arpa'], cur, 'mrr')}")
        lines.append("")

    # KPI table.
    lines.append("## KPIs")
    lines.append("")
    lines.append("| Metric | Current | Prior | Change | % | Trend |")
    lines.append("|---|---|---|---|---|---|")
    arrows = {"up": "^", "down": "v", "flat": "-"}
    for met in report.metrics:
        prev = "-" if met.previous is None else _fmt_num(met.previous, cur, met.name)
        chg = (
            "-"
            if met.change_abs is None
            else _fmt_num(met.change_abs, cur, met.name)
        )
        pct = "-" if met.change_pct is None else f"{met.change_pct}%"
        mark = arrows[met.direction]
        if met.healthy is True:
            mark += " good"
        elif met.healthy is False:
            mark += " bad"
        lines.append(
            f"| {met.name} | {_fmt_num(met.current, cur, met.name)} "
            f"| {prev} | {chg} | {pct} | {mark} |"
        )
    lines.append("")

    if report.highlights:
        lines.append("## Highlights")
        lines.append("")
        for h in report.highlights:
            lines.append(f"- {h}")
        lines.append("")
    if report.lowlights:
        lines.append("## Lowlights / Watch")
        lines.append("")
        for low in report.lowlights:
            lines.append(f"- {low}")
        lines.append("")

    lines.append("## The Ask")
    lines.append("")
    lines.append("- Intros: _add target customers / hires here_")
    lines.append("- Feedback: _add open questions here_")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"

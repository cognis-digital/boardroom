"""Smoke tests for BOARDROOM. Standard library only, no network."""
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boardroom import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    build_report,
    cagr,
    parse_metrics,
    pct_change,
    render_markdown,
    runway_months,
)
from boardroom.cli import main  # noqa: E402
from boardroom.core import BoardroomError  # noqa: E402

DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos",
    "01-basic",
    "metrics.json",
)

SAMPLE = {
    "company": "Acme",
    "currency": "USD",
    "periods": [
        {"label": "2026-01", "metrics": {"mrr": 100.0, "cash": 1200.0,
                                          "net_burn": 100.0, "churn_rate": 2.0}},
        {"label": "2026-02", "metrics": {"mrr": 120.0, "cash": 1100.0,
                                          "net_burn": 90.0, "churn_rate": 2.5}},
    ],
}


class MathTests(unittest.TestCase):
    def test_pct_change(self):
        self.assertEqual(pct_change(120, 100), 20.0)
        self.assertIsNone(pct_change(120, 0))
        self.assertIsNone(pct_change(120, None))

    def test_cagr(self):
        self.assertEqual(cagr(100, 121, 2), 10.0)
        self.assertIsNone(cagr(100, 121, 0))
        self.assertIsNone(cagr(0, 121, 2))

    def test_runway(self):
        self.assertEqual(runway_months(1200, 100), 12.0)
        self.assertIsNone(runway_months(1200, 0))
        self.assertIsNone(runway_months(None, 100))


class ReportTests(unittest.TestCase):
    def test_build_report_derived(self):
        report = build_report(parse_metrics(SAMPLE))
        self.assertEqual(report.company, "Acme")
        self.assertEqual(report.period_label, "2026-02")
        self.assertEqual(report.prior_label, "2026-01")
        self.assertEqual(report.derived["arr"], 1440.0)
        # cash 1100 / burn 90 ~= 12.2
        self.assertAlmostEqual(report.derived["runway_months"], 12.2, places=1)

    def test_health_direction(self):
        report = build_report(parse_metrics(SAMPLE))
        by_name = {m.name: m for m in report.metrics}
        # MRR up -> healthy
        self.assertTrue(by_name["mrr"].healthy)
        # net_burn down -> healthy (lower is better)
        self.assertTrue(by_name["net_burn"].healthy)
        self.assertEqual(by_name["net_burn"].direction, "down")
        # churn_rate up -> unhealthy
        self.assertFalse(by_name["churn_rate"].healthy)

    def test_highlights_lowlights(self):
        report = build_report(parse_metrics(SAMPLE))
        self.assertTrue(any("mrr" in h for h in report.highlights))
        self.assertTrue(any("churn_rate" in low for low in report.lowlights))

    def test_markdown_render(self):
        md = render_markdown(build_report(parse_metrics(SAMPLE)))
        self.assertIn("# Acme - Investor Update (2026-02)", md)
        self.assertIn("## KPIs", md)
        self.assertIn("ARR", md)


class ValidationTests(unittest.TestCase):
    def test_bad_top_level(self):
        with self.assertRaises(BoardroomError):
            parse_metrics([1, 2, 3])

    def test_empty_periods(self):
        with self.assertRaises(BoardroomError):
            parse_metrics({"periods": []})

    def test_non_numeric_metric(self):
        with self.assertRaises(BoardroomError):
            parse_metrics(
                {"periods": [{"label": "x", "metrics": {"mrr": "lots"}}]}
            )

    def test_bool_rejected(self):
        with self.assertRaises(BoardroomError):
            parse_metrics(
                {"periods": [{"label": "x", "metrics": {"mrr": True}}]}
            )


class CliTests(unittest.TestCase):
    def _capture(self, argv):
        out, err = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            code = main(argv)
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        return code, out.getvalue(), err.getvalue()

    def test_version_constants(self):
        self.assertEqual(TOOL_NAME, "boardroom")
        self.assertTrue(TOOL_VERSION)

    def test_json_output(self):
        code, out, _ = self._capture(["report", DEMO, "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["company"], "Northwind Analytics")
        self.assertEqual(data["period"], "2026-03")
        self.assertIn("runway_months", data["derived"])

    def test_table_output(self):
        code, out, _ = self._capture(["report", DEMO])
        self.assertEqual(code, 0)
        self.assertIn("Northwind Analytics", out)
        self.assertIn("mrr", out)

    def test_markdown_output(self):
        code, out, _ = self._capture(["report", DEMO, "--markdown"])
        self.assertEqual(code, 0)
        self.assertIn("Investor Update", out)

    def test_missing_file_nonzero(self):
        code, _, err = self._capture(["report", "does-not-exist.json"])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_no_command_returns_2(self):
        code, _, _ = self._capture([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

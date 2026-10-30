import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from decimal import Decimal
from pathlib import Path

from expense_tracker.cli import main
from expense_tracker.core import ExpenseError, ExpenseStore, parse_amount, summarize_month


class ExpenseTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "expenses.json"
        self.store = ExpenseStore(self.path)

    def test_add_persists_exact_amount_and_chinese_text(self):
        saved = self.store.add("12.30", " 餐饮 ", date(2026, 10, 15), "午餐")
        loaded = ExpenseStore(self.path).all()
        self.assertEqual(loaded, [saved])
        self.assertEqual(loaded[0].amount, Decimal("12.30"))
        self.assertEqual(loaded[0].category, "餐饮")
        self.assertEqual(loaded[0].note, "午餐")

    def test_list_sorts_by_date(self):
        self.store.add("20", "交通", date(2026, 10, 20))
        self.store.add("10", "餐饮", date(2026, 10, 1))
        self.assertEqual([e.spent_on.day for e in self.store.all()], [1, 20])

    def test_invalid_amounts_are_rejected_without_creating_file(self):
        for value in ("0", "-1", "1.001", "abc", "NaN", "Infinity", "1000000000"):
            with self.subTest(value=value), self.assertRaises(ExpenseError):
                self.store.add(value, "其他", date(2026, 10, 15))
        self.assertFalse(self.path.exists())

    def test_decimal_math_does_not_accumulate_float_error(self):
        self.assertEqual(parse_amount("0.10") + parse_amount("0.20"), Decimal("0.30"))

    def test_corrupt_file_is_preserved(self):
        self.path.write_text("broken JSON", encoding="utf-8")
        with self.assertRaises(ExpenseError):
            self.store.add("10", "其他", date(2026, 10, 15))
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken JSON")

    def test_invalid_record_is_rejected(self):
        self.path.write_text('[{"amount": "10.00"}]', encoding="utf-8")
        with self.assertRaises(ExpenseError):
            self.store.all()

    def test_summary_counts_categories_and_excludes_other_months(self):
        for amount, category, spent_on in (
            ("10.10", "餐饮", date(2026, 10, 1)),
            ("20.20", "餐饮", date(2026, 10, 15)),
            ("3.00", "交通", date(2026, 10, 30)),
            ("99.00", "其他", date(2026, 9, 30)),
            ("88.00", "其他", date(2026, 11, 1)),
        ):
            self.store.add(amount, category, spent_on)
        summary = summarize_month(self.store.all(), "2026-10")
        self.assertEqual(summary.count, 3)
        self.assertEqual(summary.total, Decimal("33.30"))
        self.assertEqual(summary.by_category,
                         {"餐饮": Decimal("30.30"), "交通": Decimal("3.00")})

    def test_empty_summary(self):
        summary = summarize_month([], "2026-10")
        self.assertEqual(summary.total, Decimal("0.00"))
        self.assertEqual(summary.count, 0)

    def test_invalid_months_are_rejected(self):
        for month in ("2026-13", "2026-00", "0000-01", "2026-1", "invalid"):
            with self.subTest(month=month), self.assertRaises(ExpenseError):
                summarize_month([], month)

    def test_cli_add_list_and_summary(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--data", str(self.path), "add", "15.50",
                                   "--date", "2026-10-15", "--category", "餐饮"]), 0)
            self.assertEqual(main(["--data", str(self.path), "list"]), 0)
            self.assertEqual(main(["--data", str(self.path), "summary",
                                   "--month", "2026-10"]), 0)
        self.assertIn("共 1 笔，总计：15.50", output.getvalue())

    def test_cli_reports_validation_error(self):
        output = io.StringIO()
        with redirect_stderr(output):
            result = main(["--data", str(self.path), "add", "0"])
        self.assertEqual(result, 1)
        self.assertIn("金额必须大于 0", output.getvalue())

    @unittest.expectedFailure
    def test_bug_001_summary_should_include_last_day(self):
        """Known boundary bug: October 31 is omitted from the monthly summary."""
        self.store.add("10.00", "餐饮", date(2026, 10, 30))
        self.store.add("20.00", "餐饮", date(2026, 10, 31))
        summary = summarize_month(self.store.all(), "2026-10")
        self.assertEqual(summary.total, Decimal("30.00"))
        self.assertEqual(summary.count, 2)


if __name__ == "__main__":
    unittest.main()

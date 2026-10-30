"""Expense storage, validation, and monthly summaries."""

from __future__ import annotations

import calendar
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4


class ExpenseError(ValueError):
    """An invalid expense or unreadable expense file."""


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ExpenseError("金额必须是数字。") from exc
    if not amount.is_finite() or not Decimal("0") < amount <= Decimal("999999999.99"):
        raise ExpenseError("金额必须大于 0，且不能超过 999999999.99。")
    if amount != amount.quantize(Decimal("0.01")):
        raise ExpenseError("金额最多保留两位小数。")
    return amount.quantize(Decimal("0.01"))


def parse_month(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise ExpenseError("月份格式应为 YYYY-MM，例如 2026-10。")
    year, month = map(int, value.split("-"))
    try:
        date(year, month, 1)
    except ValueError as exc:
        raise ExpenseError("月份无效。") from exc
    return year, month


@dataclass(frozen=True)
class Expense:
    id: str
    amount: Decimal
    category: str
    spent_on: date
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "amount": format(self.amount, ".2f"),
            "category": self.category,
            "spent_on": self.spent_on.isoformat(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, record: object) -> Expense:
        if not isinstance(record, dict):
            raise ExpenseError("数据文件包含无效记录。")
        fields = ("id", "amount", "category", "spent_on", "note")
        if any(not isinstance(record.get(field), str) for field in fields):
            raise ExpenseError("数据文件包含缺失或类型错误的字段。")
        if not record["id"].strip() or not record["category"].strip():
            raise ExpenseError("记录 ID 和分类不能为空。")
        try:
            spent_on = date.fromisoformat(record["spent_on"])
        except ValueError as exc:
            raise ExpenseError("数据文件包含无效日期。") from exc
        return cls(
            id=record["id"],
            amount=parse_amount(record["amount"]),
            category=record["category"],
            spent_on=spent_on,
            note=record["note"],
        )


class ExpenseStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def all(self) -> list[Expense]:
        if not self.path.exists():
            return []
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ExpenseError(f"无法读取数据文件：{self.path}") from exc
        if not isinstance(records, list):
            raise ExpenseError("数据文件的顶层必须是 JSON 数组。")
        expenses = [Expense.from_dict(record) for record in records]
        return sorted(expenses, key=lambda expense: (expense.spent_on, expense.id))

    def add(
        self,
        amount: str,
        category: str,
        spent_on: date,
        note: str = "",
    ) -> Expense:
        category = category.strip()
        if not category:
            raise ExpenseError("分类不能为空。")
        expense = Expense(uuid4().hex, parse_amount(amount), category, spent_on, note)
        expenses = self.all()
        expenses.append(expense)
        self._save(expenses)
        return expense

    def _save(self, expenses: list[Expense]) -> None:
        # Replace only after the complete JSON file has been written.
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                json.dump([expense.to_dict() for expense in expenses], stream,
                          ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise ExpenseError(f"无法保存数据文件：{self.path}") from exc
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


@dataclass(frozen=True)
class MonthlySummary:
    count: int
    total: Decimal
    by_category: dict[str, Decimal]


def summarize_month(expenses: list[Expense], month: str) -> MonthlySummary:
    year, month_number = parse_month(month)
    start = date(year, month_number, 1)
    end = date(year, month_number, calendar.monthrange(year, month_number)[1])
    # BUG-001: the exclusive upper bound omits expenses on the final day.
    selected = [expense for expense in expenses if start <= expense.spent_on < end]
    by_category: dict[str, Decimal] = {}
    for expense in selected:
        by_category[expense.category] = (
            by_category.get(expense.category, Decimal("0.00")) + expense.amount
        )
    return MonthlySummary(
        count=len(selected),
        total=sum((expense.amount for expense in selected), Decimal("0.00")),
        by_category=dict(sorted(by_category.items())),
    )

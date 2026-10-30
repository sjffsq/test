"""Command-line interface for the expense tracker."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .core import ExpenseError, ExpenseStore, summarize_month


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期无效，请使用 YYYY-MM-DD。") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="轻量记账工具：记录支出并查看月度汇总。")
    parser.add_argument("--data", type=Path, default=Path("expenses.json"),
                        help="JSON 数据文件路径（默认：expenses.json）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="新增一笔支出")
    add.add_argument("amount", help="金额，最多两位小数")
    add.add_argument("--category", default="其他", help="支出分类")
    add.add_argument("--date", type=parse_date, default=date.today(), help="支出日期")
    add.add_argument("--note", default="", help="备注")

    subparsers.add_parser("list", help="按日期列出全部支出")
    summary = subparsers.add_parser("summary", help="按分类汇总某月支出")
    summary.add_argument("--month", default=date.today().strftime("%Y-%m"),
                         help="月份，格式 YYYY-MM（默认：本月）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ExpenseStore(args.data)
    try:
        if args.command == "add":
            expense = store.add(args.amount, args.category, args.date, args.note)
            print(f"已记录：{expense.spent_on} | {expense.category} | {expense.amount:.2f}")
        elif args.command == "list":
            expenses = store.all()
            if not expenses:
                print("暂无支出记录。")
            for expense in expenses:
                print(f"{expense.spent_on} | {expense.category} | "
                      f"{expense.amount:.2f} | {expense.note}")
        else:
            summary = summarize_month(store.all(), args.month)
            print(f"{args.month} 月度汇总")
            for category, amount in summary.by_category.items():
                print(f"  {category}: {amount:.2f}")
            print(f"共 {summary.count} 笔，总计：{summary.total:.2f}")
    except ExpenseError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0
